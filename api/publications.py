"""Browser-facing, owner-scoped bridge to the private Automation service."""
import json
import os
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter, HTTPException, Request, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.responses import HTMLResponse
from studio import auth
from api.studio import get_store, lookup
from studio.output import build_bundle
from studio.service import validate_copy

router = APIRouter(prefix='/api/v2')


def connection():
    base = os.getenv('VIDEO_REVIEW_API_URL','http://127.0.0.1:8000').rstrip('/')
    u = urlsplit(base)
    token = os.getenv('WEBHOOK_V2_TOKEN','')
    local_hosts = ('localhost','127.0.0.1','::1','python-service')
    if not token or u.username or u.password or u.query or u.fragment or not (u.scheme=='https' or u.scheme=='http' and u.hostname in local_hosts):
        raise HTTPException(503,'Chưa cấu hình kết nối Automation trên máy chủ.')
    return base,token


def call(path, method='GET', body=None, files=None, data=None):
    base,token=connection()
    try:
        with httpx.Client(timeout=150,trust_env=False,follow_redirects=False,headers={'X-Content-Token':token}) as client:
            response = client.request(method,base+'/api/v2/publishing'+path,json=body,files=files,data=data)
        result = response.json()
    except (httpx.HTTPError,ValueError):
        raise HTTPException(502,'Không đọc được kết quả Automation. Giữ nguyên yêu cầu và cập nhật lại; chưa xác nhận thành công.') from None
    if not response.is_success:
        message = result.get('detail')
        raise HTTPException(response.status_code,message if isinstance(message,str) else 'Dữ liệu gửi chưa hợp lệ.')
    return result


def prefix():
    return '/owners/'+auth.current()['id']


def guard_edit(sid, store):
    auth.init(store)
    with store.db() as db:
        row = db.execute('SELECT owner FROM publication_bindings WHERE session_id=?',(sid,)).fetchone()
    if row:
        call('/owners/'+row['owner']+'/videos/'+store.get(sid)['request_id']+'/prepare-edit','POST')


@router.get('/tiktok/accounts')
def accounts():
    return {'capabilities':call('/capabilities'),'accounts':call(prefix()+'/accounts')}


@router.post('/tiktok/accounts/connect')
def connect():
    return call(prefix()+'/connect','POST')


@router.get('/tiktok/accounts/{aid}/creator')
def creator(aid: str):
    return call(prefix()+'/accounts/'+safe_id(aid)+'/creator')


def safe_id(value):
    import re
    if not re.fullmatch(r'[a-f0-9]{32}',value): raise HTTPException(404)
    return value


@router.delete('/tiktok/accounts/{aid}')
def disconnect(aid: str):
    return call(prefix()+'/accounts/'+safe_id(aid),'DELETE')


@router.get('/tiktok/callback', response_class=HTMLResponse)
def callback(state: str='', code: str='', error: str=''):
    # Do not echo the code, state or upstream error HTML.
    if error or not state or not code:
        return HTMLResponse('<meta charset="utf-8"><p>Kết nối chưa được cấp quyền. Quay lại Content Studio và thử lại.</p><a href="/app">Mở Content Studio</a>',status_code=400)
    call('/callback','POST',{'state':state,'code':code})
    return '<meta charset="utf-8"><p>Đã kết nối TikTok với tài khoản Content Studio của bạn.</p><a href="/app">Quay lại Content Studio</a>'


@router.get('/sessions/{sid}/publication')
def video(sid: str):
    s = lookup(sid)
    return call(prefix()+'/videos/'+s['request_id'])


@router.post('/sessions/{sid}/publication')
def register(sid: str):
    store = get_store(); s = lookup(sid)
    b, v = s.get('bundle') or {}, s.get('video') or {}
    if s['step']!=7 or s['status']=='processing' or not v or v['bundle_revision']!=b.get('revision'):
        raise HTTPException(409,'Tải đúng MP4 cho bản prompt hiện tại trước khi duyệt.')
    if build_bundle(s,store,b['revision'])!=b:
        raise HTTPException(409,'Nội dung khác bản đã duyệt.')
    mode = 'telegram' if s.get('handoff') else 'web'
    if mode=='telegram' and auth.current()['role']!='admin':
        raise HTTPException(403,'Kết nối Telegram SEJOY chỉ dành cho dữ liệu của quản trị.')
    p = b['publishing']; caption = p['captions'][p['selected_caption']]+'\n'+' '.join(p['hashtags'])
    metadata = {'request_id':s['request_id'],'revision':b['revision'],'version':v['version'],'sha256':v['sha256'],
                'review_mode':mode,'caption':caption,'shop_callout':any('giỏ hàng' in x.get('dialogue_vi','').lower() for x in b['scenes'])}
    try:
        with store.video_path(v).open('rb') as file:
            result = call(prefix()+'/videos','POST',files={'file':('video.mp4',file,'video/mp4')},data={'metadata':json.dumps(metadata)})
    except FileNotFoundError:
        raise HTTPException(409,'Không tìm thấy MP4 đã tải lên.') from None
    with auth.init(store).db() as db:
        db.execute('INSERT OR REPLACE INTO publication_bindings VALUES(?,?)',(sid,auth.current()['id']))
    return result


@router.post('/sessions/{sid}/publication/review')
async def review(sid: str, request: Request):
    s = lookup(sid)
    row = call(prefix()+'/videos/'+s['request_id'])
    if not row or row['version']!=(s.get('video') or {}).get('version') or row['revision']!=(s.get('bundle') or {}).get('revision'):
        raise HTTPException(409,'Video đã thay đổi. Đồng bộ và xem lại trước khi duyệt.')
    body = await request.json()
    if set(body) != {'approve','watched'} or any(type(x) is not bool for x in body.values()): raise HTTPException(422,'Quyết định chưa hợp lệ.')
    return call(prefix()+'/videos/'+row['id']+'/review','POST',{**body,'sha256':row['sha256']})


@router.get('/publications')
def jobs():
    return call(prefix()+'/jobs')


@router.get('/publication-videos')
def ordinary_videos():
    return call(prefix()+'/ordinary-videos')


@router.post('/publication-videos')
def ordinary_upload(file: UploadFile=File(...), caption: str=Form(...,max_length=4400), operation_id: str=Form(...,pattern=r'^[a-f0-9]{32}$')):
    from studio.video import save_mp4
    import tempfile
    try:validate_copy({'post_caption':caption})
    except ValueError:raise HTTPException(422,'Kiểm tra lại nội dung caption và hashtag.') from None
    # Streaming into a bounded temporary file avoids holding 45 MB in memory.
    with tempfile.TemporaryDirectory(dir=get_store().path.parent) as folder:
        from pathlib import Path
        path=Path(folder)/'upload.mp4'
        try: meta=save_mp4(file.file,path)
        except OverflowError:raise HTTPException(413,'MP4 tối đa 45 MB.') from None
        except ValueError:raise HTTPException(400,'Tệp MP4 chưa hợp lệ.') from None
        body={'request_id':'vid_'+operation_id,'revision':1,'version':1,'sha256':meta['sha256'],
              'caption':caption,'review_mode':'web','shop_callout':False,'standalone':True}
        with path.open('rb') as stream:
            result=call(prefix()+'/videos','POST',files={'file':('video.mp4',stream,'video/mp4')},data={'metadata':json.dumps(body)})
    return {**result,'caption':caption}


@router.get('/publication-videos/{vid}/file')
def ordinary_file(vid: str, request: Request):
    from starlette.background import BackgroundTask
    base,token=connection()
    client=httpx.Client(timeout=150,trust_env=False,follow_redirects=False)
    headers={'X-Content-Token':token}
    if request.headers.get('range'):headers['Range']=request.headers['range']
    try:
        response=client.send(client.build_request('GET',base+'/api/v2/publishing'+prefix()+'/ordinary-videos/'+safe_id(vid)+'/file',headers=headers),stream=True)
        if not response.is_success:
            status=response.status_code;response.close();client.close()
            raise HTTPException(status,'Không đọc được video của bạn.')
    except httpx.HTTPError:
        client.close();raise HTTPException(502,'Automation chưa trả được video.') from None
    def close():response.close();client.close()
    out={k:v for k,v in response.headers.items() if k in ('content-length','content-range','accept-ranges')}
    out['Cache-Control']='private, no-store'
    return StreamingResponse(response.iter_bytes(65536),status_code=response.status_code,media_type='video/mp4',headers=out,background=BackgroundTask(close))


@router.post('/publication-videos/{vid}/review')
async def ordinary_review(vid: str,request: Request):
    return call(prefix()+'/videos/'+safe_id(vid)+'/review','POST',await request.json())


@router.post('/publications',status_code=201)
async def schedule(request: Request):
    body = await request.json()
    try:
        validate_copy({'post_caption':body['post']['title']})
    except (ValueError,KeyError,TypeError) as exc:
        raise HTTPException(422,'Kiểm tra lại caption và hashtag trước khi đăng.') from exc
    return call(prefix()+'/jobs','POST',body)


@router.post('/publications/{jid}/actions')
async def job_action(jid: str, request: Request):
    return call(prefix()+'/jobs/'+safe_id(jid)+'/actions','POST',await request.json())
