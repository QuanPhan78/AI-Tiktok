"""No live credentials: exercise isolation, durable jobs and ambiguous delivery."""
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from studio import auth
from studio.store import Store
from api import studio as api
from tests.test_handoff_v2 import hv
from tests.test_video_review_v2 import mp4_structure
from app import publishing_v2 as pub, publication_store as ps
from app.tiktok_v2 import TikTokError

ROOT = Path(__file__).resolve().parents[1]


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory(dir=ROOT/'data/test-runs'))
        self.enterContext(patch.dict(os.environ, STUDIO_DATA_DIR=self.temp, STUDIO_AUTH_ENABLED='1',
                                    STUDIO_PUBLIC_MODE='0', STUDIO_PUBLIC_URL=''))
        self.store = Store()
        self.enterContext(patch.object(api,'get_store',return_value=self.store))
        app = FastAPI(); app.middleware('http')(auth.middleware)
        app.include_router(auth.router); app.include_router(api.router)
        self.client = TestClient(app,base_url='http://127.0.0.1:8001',client=('127.0.0.1',50001))
        self.creds = {'username':'sample_admin','password':'synthetic-password-only'}
        self.product = {'name':'Hộp bút','uses':'Đựng bút','price':'20.000đ','product_link':'https://example.com/p'}

    def setup(self):
        r = self.client.post('/api/v2/auth/setup',json=self.creds)
        self.assertEqual(r.status_code,200,r.text)
        self.client.headers['X-CSRF-Token'] = r.json()['csrf']
        return r.json()

    def test_bootstrap_preserves_existing_json_and_assigns_owner(self):
        old = self.store.create(self.product)
        self.setup()
        self.assertEqual(self.store.get(old['id']),old)
        self.assertEqual(self.client.get('/api/v2/sessions').json()[0]['id'],old['id'])
        self.assertEqual(self.client.post('/api/v2/auth/setup',json=self.creds).status_code,409)

    def test_login_csrf_origin_and_logout(self):
        self.assertEqual(self.client.get('/api/v2/sessions').status_code,401)
        self.setup()
        self.assertEqual(self.client.post('/api/v2/sessions',json=self.product,headers={'X-CSRF-Token':''}).status_code,403)
        self.assertEqual(self.client.post('/api/v2/sessions',json=self.product,headers={'Origin':'https://evil.invalid'}).status_code,403)
        self.assertEqual(self.client.post('/api/v2/sessions',json=self.product).status_code,201)
        self.client.post('/api/v2/auth/logout')
        self.assertEqual(self.client.get('/api/v2/sessions').status_code,401)

    def test_cross_user_session_export_history_video_and_chat_hidden(self):
        self.setup()
        sid = self.client.post('/api/v2/sessions',json=self.product).json()['id']
        r = self.client.post('/api/v2/auth/register',json={**self.creds,'username':'second_user'})
        self.assertEqual(r.status_code,201,r.text)
        self.client.headers['X-CSRF-Token'] = r.json()['csrf']
        self.assertEqual(self.client.get('/api/v2/sessions').json(),[])
        for suffix in ('','/history','/export/zip','/videos/1','/chat/messages'):
            self.assertEqual(self.client.get('/api/v2/sessions/'+sid+suffix).status_code,404)
        self.assertEqual(self.client.post('/api/v2/sessions/'+sid+'/actions',json={}).status_code,404)

    def test_asset_ownership_and_password_recovery_single_use(self):
        result = self.setup()
        self.store.save_asset({'id':'private-image','path':'no-file'})
        context=auth.identity.set(result['user'])
        try: auth.own('asset','private-image',self.store)
        finally: auth.identity.reset(context)
        self.client.post('/api/v2/auth/register',json={**self.creds,'username':'second_user'})
        self.client.headers['X-CSRF-Token']=self.client.get('/api/v2/auth/me').json()['csrf']
        self.assertEqual(self.client.get('/api/v2/assets/private-image').status_code,404)
        self.assertEqual(self.client.post('/api/v2/sessions',json={**self.product,'asset_id':'private-image'}).status_code,404)
        recovery={**self.creds,'recovery_code':result['recovery_code'],'password':'replacement-password-only'}
        self.assertEqual(self.client.post('/api/v2/auth/recover',json=recovery).status_code,200)
        self.assertEqual(self.client.post('/api/v2/auth/recover',json=recovery).status_code,401)
        self.assertEqual(self.client.post('/api/v2/auth/login',json=self.creds).status_code,401)
        self.assertEqual(self.client.post('/api/v2/auth/login',json={k:v for k,v in recovery.items() if k!='recovery_code'}).status_code,200)

    def test_public_setup_and_legacy_endpoints_are_not_exposed(self):
        remote=TestClient(self.client.app,base_url='https://studio.example',client=('203.0.113.2',1234))
        self.assertEqual(remote.post('/api/v2/auth/setup',json=self.creds).status_code,403)
        with patch.dict(os.environ,STUDIO_PUBLIC_MODE='1'):
            self.assertEqual(remote.get('/docs').status_code,404)
            self.assertEqual(remote.post('/generate',json={}).status_code,404)

    def test_delete_requires_password_keeps_admin_and_clears_only_owner(self):
        self.setup()
        self.assertEqual(self.client.request('DELETE','/api/v2/auth/account',json={'password':self.creds['password'],'confirm_username':self.creds['username']}).status_code,409)
        second={**self.creds,'username':'second_user'}
        result=self.client.post('/api/v2/auth/register',json=second).json();self.client.headers['X-CSRF-Token']=result['csrf']
        self.client.post('/api/v2/sessions',json=self.product)
        with patch('api.publications.call',return_value={'revoked_at_tiktok':True}) as remote:
            self.assertEqual(self.client.request('DELETE','/api/v2/auth/account',json={'password':'wrong','confirm_username':'second_user'}).status_code,400)
            remote.assert_not_called()
            self.assertEqual(self.client.request('DELETE','/api/v2/auth/account',json={'password':second['password'],'confirm_username':'second_user'}).status_code,200)
        self.assertEqual(self.client.get('/api/v2/sessions').status_code,401)
        with self.store.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0],1)


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory(dir=ROOT/'data/test-runs'))
        self.enterContext(patch.dict(os.environ, HANDOFF_DATA_DIR=self.temp,WEBHOOK_V2_TOKEN='test-only',
            TIKTOK_CLIENT_KEY='sample',TIKTOK_CLIENT_SECRET='sample',TIKTOK_V2_REDIRECT_URI='https://studio.example/api/v2/tiktok/callback',
            TIKTOK_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),STUDIO_PUBLIC_URL='https://studio.example',
            TIKTOK_MEDIA_URL_VERIFIED='1',TIKTOK_APP_AUDITED='0',TIKTOK_SCHEDULER_ENABLED='1'))
        app=FastAPI(); app.include_router(pub.router); app.include_router(pub.media_router)
        self.http=TestClient(app,headers={'X-Content-Token':'test-only'})
        self.base='/api/v2/publishing/owners/owner-a'
        self.fake=Mock()
        self.fake.creator.return_value={'creator_nickname':'Sample','privacy_level_options':['SELF_ONLY','PUBLIC_TO_EVERYONE'],
            'max_video_post_duration_sec':60,'comment_disabled':False,'duet_disabled':True,'stitch_disabled':True}
        self.fake.publish.return_value={'publish_id':'real-shaped-test-id'}
        self.fake.status.return_value={'status':'PROCESSING_UPLOAD'}
        self.enterContext(patch.object(pub,'client',self.fake))
        self.enterContext(patch.object(pub,'probe',return_value=8.0))
        self.aid=secrets.token_hex(16)
        with ps.db() as db:
            db.execute('INSERT INTO accounts VALUES(?,?,?,?,?,1)',(self.aid,'owner-a','sample-open-id','Sample',ps.encrypt({
                'access_token':'fake-access','refresh_token':'fake-refresh','expires_at':time.time()+86400,'scope':'video.publish'})))
        self.raw=mp4_structure()
        self.meta={'request_id':'vid_'+'a'*32,'revision':26,'version':1,'sha256':hashlib.sha256(self.raw).hexdigest(),
                   'review_mode':'web','caption':'Video minh họa tổng hợp','shop_callout':False}
        self.vid=self.upload().json()['id']

    def upload(self,meta=None):
        return self.http.post(self.base+'/videos',data={'metadata':json.dumps(meta or self.meta)},files={'file':('test.mp4',self.raw,'video/mp4')})

    def approve(self):
        r=self.http.post(self.base+'/videos/'+self.vid+'/review',json={'approve':True,'watched':True,'sha256':self.meta['sha256']})
        self.assertEqual(r.status_code,200,r.text)

    def body(self,**kw):
        return {'operation_id':secrets.token_hex(16),'video_id':self.vid,'account_id':self.aid,
                'consent':True,'watched':True,'no_shop_required':True,
                'post':{'title':'Video tổng hợp #demo','privacy_level':'SELF_ONLY'},**kw}

    def job(self,body=None):
        self.approve()
        r=self.http.post(self.base+'/jobs',json=body or self.body())
        self.assertEqual(r.status_code,201,r.text)
        return r.json()

    def row(self,jid):
        with ps.db() as db:return dict(db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())

    def test_no_anonymous_bridge_no_cross_owner_access(self):
        self.assertEqual(self.http.get(self.base+'/jobs',headers={'X-Content-Token':''}).status_code,403)
        self.assertEqual(self.http.get('/api/v2/publishing/owners/other/accounts/'+self.aid+'/creator').status_code,404)
        self.assertEqual(self.http.get('/api/v2/publishing/owners/other/jobs').json(),[])

    def test_repeated_upload_uses_same_id_and_stale_or_bad_metadata_fails(self):
        self.assertEqual(self.upload().json()['id'],self.vid)
        self.assertEqual(self.upload({**self.meta,'revision':25}).status_code,409)
        self.assertEqual(self.http.post(self.base+'/videos',data={'metadata':'{}'},files={'file':('a.mp4',self.raw)}).status_code,422)
        self.assertEqual(self.upload({**self.meta,'sha256':'0'*64}).status_code,400)

    def test_approval_exact_file_and_no_shop(self):
        self.assertEqual(self.http.post(self.base+'/jobs',json=self.body()).status_code,409)
        self.assertEqual(self.http.post(self.base+'/videos/'+self.vid+'/review',json={'approve':True,'watched':True,'sha256':'0'*64}).status_code,409)
        self.approve()
        with ps.db() as db:db.execute('UPDATE videos SET meta=? WHERE id=?',(json.dumps({**self.meta,'shop_callout':True}),self.vid))
        self.assertEqual(self.http.post(self.base+'/jobs',json=self.body()).status_code,409)

    def test_idempotency_and_conflicting_operation(self):
        body=self.body(); first=self.job(body)
        self.assertEqual(self.http.post(self.base+'/jobs',json=body).json()['id'],first['id'])
        self.assertEqual(self.http.post(self.base+'/jobs',json={**body,'post':{'title':'changed','privacy_level':'SELF_ONLY'}}).status_code,409)
        self.assertEqual(self.http.post(self.base+'/jobs',json=self.body()).status_code,409)

    def test_shop_mode_cannot_be_removed_from_same_video(self):
        changed = {**self.meta, 'content_mode': 'tiktok_shop'}
        self.assertEqual(self.upload(changed).status_code, 409)
        newer = self.upload({**changed, 'version': 2})
        self.assertEqual(newer.status_code, 200, newer.text)
        self.vid = newer.json()['id']
        self.approve()
        self.assertEqual(self.http.post(self.base+'/jobs', json=self.body()).status_code, 409)

    def test_post_caption_cannot_add_shop_to_ordinary_video(self):
        self.approve()
        body = self.body()
        body['post']['title'] = 'Bấm giỏ hàng nhé!'
        self.assertEqual(self.http.post(self.base+'/jobs', json=body).status_code, 422)
        self.fake.publish.assert_not_called()

    def test_retry_receipt_survives_paused_or_incomplete_configuration(self):
        body=self.body(); first=self.job(body)
        with patch.dict(os.environ,TIKTOK_SCHEDULER_ENABLED='0',TIKTOK_CLIENT_KEY=''):
            response=self.http.post(self.base+'/jobs',json=body)
            self.assertEqual(response.status_code,201,response.text)
            self.assertEqual(response.json()['id'],first['id'])
        self.fake.publish.assert_not_called()

    def test_reusing_blocked_schedule_cannot_duplicate_replacement(self):
        old=self.job()
        with ps.db() as db:ps.set_status(db,old['id'],'BLOCKED')
        replacement=self.http.post(self.base+'/jobs',json=self.body()).json()
        response=self.http.post(self.base+'/jobs/'+old['id']+'/actions',json={
            'version':self.row(old['id'])['version'],'action':'reschedule','scheduled_at':'2099-11-16T10:00:00+07:00'})
        self.assertEqual(response.status_code,409,response.text)
        pub.tick();self.fake.publish.assert_called_once()
        self.assertEqual(self.row(replacement['id'])['status'],'PROCESSING')

    def test_paused_dispatch_still_tracks_accepted_post_and_syncs_notion(self):
        first=self.job();pub.tick()
        with ps.db() as db:db.execute('UPDATE jobs SET next_poll=0 WHERE id=?',(first['id'],))
        self.fake.status.return_value={'status':'PUBLISH_COMPLETE'}
        with patch.dict(os.environ,TIKTOK_SCHEDULER_ENABLED='0',STUDIO_PUBLIC_URL=''), patch.object(pub,'sync_notion') as sync:
            result=pub.tick();sync.assert_called_once()
        self.assertFalse(result['enabled']);self.assertEqual(result['checked'],1)
        self.assertEqual(self.row(first['id'])['status'],'PUBLISHED')
        self.fake.publish.assert_called_once()

    def test_configuration_distinguishes_connection_from_posting_without_secrets(self):
        with patch.dict(os.environ,TIKTOK_MEDIA_URL_VERIFIED='0',TIKTOK_SCHEDULER_ENABLED='0'):
            result=pub.readiness()
            self.assertTrue(result['connect_ready']);self.assertFalse(result['ready'])
            pub.connect_account('owner-a')
            self.approve()
            self.assertEqual(self.http.post(self.base+'/jobs',json=self.body()).status_code,503)
        for changes in ({'TIKTOK_V2_REDIRECT_URI':'https://wrong.example/callback'},
                        {'TIKTOK_TOKEN_ENCRYPTION_KEY':'invalid-secret-value'},
                        {'TIKTOK_CLIENT_KEY':'your_tiktok_client_key_here'},
                        {'STUDIO_PUBLIC_URL':'https://user:secret@studio.example'}):
            with patch.dict(os.environ,**changes):
                result=pub.readiness();self.assertFalse(result['connect_ready'])
                for value in changes.values():self.assertNotIn(value,json.dumps(result))
                self.assertEqual(self.http.post(self.base+'/connect').status_code,503)

    def test_expired_token_refreshes_only_its_owner_and_failure_never_posts(self):
        with ps.db() as db:db.execute('UPDATE accounts SET tokens=? WHERE id=?',(ps.encrypt({
            'access_token':'expired','refresh_token':'fake-refresh','expires_at':0,'scope':'video.publish'}),self.aid))
        self.fake.refresh.return_value={'access_token':'fresh','refresh_token':'rotated','expires_in':3600}
        job=self.job();pub.tick()
        self.fake.refresh.assert_called_once_with('fake-refresh')
        self.assertEqual(self.fake.publish.call_args.args[0],'fresh')
        with ps.db() as db:
            row=db.execute('SELECT tokens FROM accounts WHERE id=?',(self.aid,)).fetchone()
            self.assertNotIn('rotated',row['tokens'])
            token=ps.decrypt(row['tokens']);token['expires_at']=0
            db.execute('UPDATE accounts SET tokens=? WHERE id=?',(ps.encrypt(token),self.aid))
            db.execute('UPDATE jobs SET next_poll=0 WHERE id=?',(job['id'],))
        self.fake.refresh.side_effect=TikTokError('invalid_grant')
        pub.tick()
        self.fake.publish.assert_called_once()
        self.assertEqual(self.row(job['id'])['status'],'PROCESSING')

    def test_bridge_to_automation_uses_owner_and_round_trips_real_contract(self):
        import httpx
        from api import publications as bridge
        self.approve()
        private=self.http
        real_client=httpx.Client
        def transport(request):
            response=private.request(request.method,request.url.path,
                                     headers=dict(request.headers),content=request.content)
            return httpx.Response(response.status_code,json=response.json())
        def local_client(**kwargs):
            return real_client(transport=httpx.MockTransport(transport),**kwargs)
        app=FastAPI();app.include_router(bridge.router)
        browser=TestClient(app)
        identity=auth.identity.set({'id':'owner-a','role':'admin'})
        try:
            with patch.object(bridge.httpx,'Client',side_effect=local_client):
                result=browser.get('/api/v2/tiktok/accounts')
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(result.json()['accounts'][0]['id'],self.aid)
                first=browser.post('/api/v2/publications',json=self.body())
                self.assertEqual(first.status_code,201,first.text)
                pub.tick()
                listing=browser.get('/api/v2/publications').json()
                self.assertEqual(listing[0]['status'],'PROCESSING')
                self.assertEqual(listing[0]['video']['sha256'],self.meta['sha256'])
                other=auth.identity.set({'id':'owner-b','role':'user'})
                try:self.assertEqual(browser.get('/api/v2/publications').json(),[])
                finally:auth.identity.reset(other)
        finally:auth.identity.reset(identity)

    def test_private_only_and_required_consent(self):
        self.approve()
        for changes in ({'consent':False},{'post':{'title':'x','privacy_level':'PUBLIC_TO_EVERYONE'}},{'scheduled_at':'2099-11-16T10:00:00'}):
            self.assertIn(self.http.post(self.base+'/jobs',json=self.body(**changes)).status_code,(400,409))
        self.assertEqual(pub.creator('owner-a',self.aid)['privacy_level_options'],['SELF_ONLY'])

    def test_schedule_utc_edit_cancel_and_restart(self):
        first=self.job(self.body(scheduled_at='2099-11-16T10:00:00+07:00'))
        from datetime import datetime
        self.assertEqual(first['due'],datetime.fromisoformat('2099-11-16T03:00:00+00:00').timestamp())
        pub.tick();self.fake.publish.assert_not_called()
        self.assertEqual(self.http.post(self.base+'/jobs/'+first['id']+'/actions',json={'version':0,'action':'cancel'}).status_code,409)
        self.http.post(self.base+'/videos/'+self.meta['request_id']+'/prepare-edit')
        self.assertEqual(self.row(first['id'])['status'],'CANCELLED')
        self.assertEqual(self.upload().status_code,409)
        newer=self.upload({**self.meta,'version':2});self.assertEqual(newer.status_code,200)
        self.assertEqual(newer.json()['status'],'ATTACHED')

    def test_tick_publish_id_status_and_no_duplicate_init(self):
        job=self.job();pub.tick();pub.tick()
        self.assertEqual(self.fake.publish.call_count,1)
        self.assertEqual(self.row(job['id'])['status'],'PROCESSING')
        with ps.db() as db:db.execute('UPDATE jobs SET next_poll=0 WHERE id=?',(job['id'],))
        self.fake.status.return_value={'status':'PUBLISH_COMPLETE','publicaly_available_post_id':['12345']}
        pub.tick()
        row=self.row(job['id']);self.assertEqual(row['status'],'PUBLISHED');self.assertEqual(json.loads(row['post_ids']),['12345'])
        self.fake.status.assert_called_with('fake-access','real-shaped-test-id')
        self.fake.publish.assert_called_once()

    def test_signed_media_expires_and_checks_file(self):
        self.job();pub.tick()
        url=self.fake.publish.call_args.args[2]
        path=url.replace('https://studio.example','')
        self.assertEqual(self.http.get(path).content,self.raw)
        with ps.db() as db:db.execute('UPDATE grants SET expires=0')
        self.assertEqual(self.http.get(path).status_code,404)

    def test_timeout_and_crash_do_not_retry_init(self):
        job=self.job();self.fake.publish.side_effect=TikTokError('connection_uncertain',ambiguous=True)
        pub.tick();pub.tick();self.fake.publish.assert_called_once()
        self.assertEqual(self.row(job['id'])['status'],'RECONCILE')
        self.assertEqual(self.http.post(self.base+'/videos/'+self.meta['request_id']+'/prepare-edit').status_code,409)
        self.assertEqual(self.http.delete(self.base+'/accounts/'+self.aid).status_code,409)
        with ps.db() as db:db.execute("UPDATE jobs SET status='INITIATING',lease_until=0 WHERE id=?",(job['id'],))
        pub.tick();self.fake.publish.assert_called_once();self.assertEqual(self.row(job['id'])['status'],'RECONCILE')

    def test_missed_schedule_needs_explicit_reschedule(self):
        job=self.job()
        with ps.db() as db:db.execute('UPDATE jobs SET due=? WHERE id=?',(time.time()-901,job['id']))
        pub.tick();self.fake.publish.assert_not_called()
        self.assertEqual(self.row(job['id'])['status'],'MISSED')

    def test_broken_video_and_disabled_service_never_publish(self):
        job=self.job()
        with ps.db() as db:
            path=Path(db.execute('SELECT path FROM videos WHERE id=?',(self.vid,)).fetchone()[0]);path.write_bytes(b'changed')
        pub.tick();self.fake.publish.assert_not_called();self.assertEqual(self.row(job['id'])['status'],'BLOCKED')
        with patch.dict(os.environ,TIKTOK_SCHEDULER_ENABLED='0'):
            self.assertFalse(pub.tick()['enabled'])

    def test_oauth_state_owner_encrypted_tokens_and_replay(self):
        self.fake.authorization_url.side_effect=lambda state:'https://www.tiktok.com/?state='+state
        url=pub.connect_account('owner-b')['url'];state=url.split('state=')[1]
        self.fake.exchange.return_value={'access_token':'another-secret','refresh_token':'refresh','open_id':'new-open-id','scope':'video.publish','expires_in':3600}
        self.assertEqual(self.http.post('/api/v2/publishing/callback',json={'state':state,'code':'example-code'}).status_code,200)
        self.assertEqual(self.http.post('/api/v2/publishing/callback',json={'state':state,'code':'example-code'}).status_code,400)
        with ps.db() as db:
            row=db.execute("SELECT * FROM accounts WHERE owner='owner-b'").fetchone()
            self.assertNotIn('another-secret',row['tokens']);self.assertEqual(ps.decrypt(row['tokens'])['access_token'],'another-secret')
        self.assertNotIn('tokens',pub.accounts('owner-b')[0])

    def test_disconnect_cancels_jobs_and_revocation_failure_is_honest(self):
        job=self.job();self.fake.revoke.side_effect=TikTokError('offline')
        result=pub.disconnect('owner-a',self.aid)
        self.assertFalse(result['revoked_at_tiktok']);self.assertEqual(self.row(job['id'])['status'],'CANCELLED')
        pub.tick();self.fake.publish.assert_not_called()

    def test_standalone_video_list_preview_and_account_delete(self):
        meta={**self.meta,'request_id':'vid_'+'b'*32,'standalone':True}
        vid=self.upload(meta).json()['id']
        listing=self.http.get(self.base+'/ordinary-videos').json()
        self.assertEqual([x['id'] for x in listing],[vid])
        self.assertEqual(self.http.get(self.base+'/ordinary-videos/'+vid+'/file').content,self.raw)
        self.assertEqual(self.http.get('/api/v2/publishing/owners/other/ordinary-videos/'+vid+'/file').status_code,404)
        self.job()
        self.assertTrue(pub.delete_owner('owner-a')['deleted'])
        self.assertEqual(pub.jobs('owner-a'),[])
        self.assertEqual(list(Path(self.temp).glob('*.mp4')),[])
        pub.tick();self.fake.publish.assert_not_called()

    def test_concurrent_ticks_claim_once_and_status_failure_never_resends(self):
        from concurrent.futures import ThreadPoolExecutor
        job=self.job()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:pub.tick(),range(2)))
        self.fake.publish.assert_called_once()
        with ps.db() as db:db.execute('UPDATE jobs SET next_poll=0 WHERE id=?',(job['id'],))
        self.fake.status.side_effect=TikTokError('connection_uncertain')
        pub.tick();self.assertEqual(self.row(job['id'])['status'],'PROCESSING')
        self.fake.publish.assert_called_once()

    def test_notion_failure_does_not_retry_post(self):
        job=self.job()
        with ps.db() as db:db.execute('UPDATE videos SET meta=? WHERE id=?',(json.dumps({**self.meta,'notion_page_id':'fake-page'}),self.vid))
        fake_notion=Mock();fake_notion.pages.retrieve.side_effect=RuntimeError('offline')
        with patch.object(hv.nc,'notion',fake_notion):
            pub.tick();pub.tick()
        self.fake.publish.assert_called_once()
        with ps.db() as db:self.assertIsNotNone(db.execute('SELECT error FROM sync_queue WHERE job_id=?',(job['id'],)).fetchone()[0])
        fake_notion.pages.retrieve.side_effect=None
        fake_notion.pages.retrieve.return_value={'properties':{'scheduled_at':{},'published_at':{}}}
        with ps.db() as db:db.execute('UPDATE jobs SET next_poll=0 WHERE id=?',(job['id'],))
        self.fake.status.return_value={'status':'PUBLISH_COMPLETE'}
        with patch.object(hv.nc,'notion',fake_notion):pub.tick()
        self.assertEqual(self.row(job['id'])['status'],'PUBLISHED')
        self.assertEqual(fake_notion.pages.update.call_args.kwargs['properties']['status']['select']['name'],'PUBLISHED')
        self.fake.publish.assert_called_once()
        with ps.db() as db:self.assertEqual(db.execute('SELECT count(*) FROM sync_queue').fetchone()[0],0)


if __name__=='__main__':unittest.main()
