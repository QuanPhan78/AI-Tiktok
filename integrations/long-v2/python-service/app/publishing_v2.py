"""Authenticated Studio bridge, durable scheduling and real TikTok outcomes."""
import hashlib
import json
import os
import re
import secrets
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from app.contracts_v2 import shop_reference
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from app import publication_store as ps
from app import handoff_v2 as handoff
from app.video_review_v2 import require_studio, save_upload
from app.tiktok_v2 import TikTokV2, TikTokError
from app.publishing_setup import configuration

router = APIRouter(prefix='/api/v2/publishing', dependencies=[Depends(require_studio)])
media_router = APIRouter()
client = TikTokV2()


def readiness():
    return configuration(os.environ)


def require_ready(connect_only=False):
    result = readiness()
    if not result['connect_ready' if connect_only else 'ready']:
        raise HTTPException(503,result['message'])
    root = os.environ['STUDIO_PUBLIC_URL'].rstrip('/')
    u = urlsplit(root)
    redirect = os.environ['TIKTOK_V2_REDIRECT_URI']
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path:
        raise HTTPException(503,'STUDIO_PUBLIC_URL phải là địa chỉ gốc HTTPS hợp lệ.')
    if redirect != root + '/api/v2/tiktok/callback':
        raise HTTPException(503,'URL callback TikTok chưa khớp website hiện tại.')
    ps.cipher()
    return root


def account_token(owner, aid):
    with ps.lock:
        with ps.db() as db:
            row = ps.owned(db,'accounts',aid,owner)
            if not row['connected']:
                raise HTTPException(409,'Tài khoản TikTok đã ngắt kết nối.')
            data = ps.decrypt(row['tokens'])
        if data.get('expires_at',0) < time.time()+120:
            refreshed = client.refresh(data['refresh_token'])
            if not refreshed.get('access_token') or (refreshed.get('open_id') and refreshed['open_id'] != row['open_id']):
                raise HTTPException(502,'TikTok chưa xác nhận làm mới đúng tài khoản.')
            data.update(refreshed)
            data['expires_at'] = time.time()+int(refreshed.get('expires_in',0))
            with ps.db() as db:
                db.execute('UPDATE accounts SET tokens=? WHERE id=?', (ps.encrypt(data),aid))
        if 'video.publish' not in data.get('scope','').split(','):
            raise HTTPException(409,'Tài khoản chưa cấp quyền video.publish. Hãy kết nối lại.')
        return data['access_token']


@router.get('/capabilities')
def capabilities():
    return readiness()


@router.get('/owners/{owner}/accounts')
def accounts(owner: str):
    with ps.db() as db:
        return [dict(r) for r in db.execute('SELECT id,nickname,connected FROM accounts WHERE owner=?', (owner,))]


@router.delete('/owners/{owner}')
def delete_owner(owner: str):
    with ps.lock,ps.db() as db:
        db.execute('BEGIN IMMEDIATE')
        jobs=db.execute('SELECT * FROM jobs WHERE owner=?',(owner,)).fetchall()
        if any(r['status'] in ps.INFLIGHT for r in jobs):
            raise HTTPException(409,'Có lượt đăng đang xử lý/cần đối chiếu. Chưa thể xóa tài khoản.')
        accounts=db.execute('SELECT * FROM accounts WHERE owner=?',(owner,)).fetchall()
        videos=db.execute('SELECT * FROM videos WHERE owner=?',(owner,)).fetchall()
        for row in jobs:
            for table in ('publish_events','sync_queue'):db.execute(f'DELETE FROM {table} WHERE job_id=?',(row['id'],))
        for row in videos:db.execute('DELETE FROM grants WHERE video_id=?',(row['id'],))
        for table in ('jobs','videos','accounts','oauth'):db.execute(f'DELETE FROM {table} WHERE owner=?',(owner,))
    revoked=True
    for row in accounts:
        if row['connected']:
            try:client.revoke(ps.decrypt(row['tokens'])['access_token'])
            except Exception:revoked=False
    for row in videos:
        path=Path(row['path'])
        if path.resolve().is_relative_to(handoff.folder().resolve()):path.unlink(missing_ok=True)
    return {'deleted':True,'revoked_at_tiktok':revoked}


@router.post('/owners/{owner}/connect')
def connect_account(owner: str):
    require_ready(connect_only=True)
    state = secrets.token_urlsafe(32)
    with ps.db() as db:
        db.execute('DELETE FROM oauth WHERE expires<?', (time.time(),))
        db.execute('INSERT INTO oauth VALUES(?,?,?)', (ps.hashlib.sha256(state.encode()).hexdigest(),owner,time.time()+600))
    return {'url': client.authorization_url(state)}


class Callback(BaseModel):
    state: str = Field(min_length=20,max_length=200)
    code: str = Field(min_length=1,max_length=3000)


@router.post('/callback')
def oauth_callback(body: Callback):
    require_ready(connect_only=True)
    with ps.db() as db:
        db.execute('BEGIN IMMEDIATE')
        key = hashlib.sha256(body.state.encode()).hexdigest()
        row = db.execute('SELECT * FROM oauth WHERE state=? AND expires>?', (key,time.time())).fetchone()
        if not row:
            raise HTTPException(400,'Lượt kết nối đã hết hạn hoặc đã dùng. Bấm kết nối lại.')
        db.execute('DELETE FROM oauth WHERE state=?', (key,))
    try:
        token = client.exchange(body.code)
        if not all(token.get(k) for k in ('access_token','refresh_token','open_id')):
            raise HTTPException(502,'TikTok chưa trả đủ thông tin kết nối.')
        if 'video.publish' not in token.get('scope','').split(','):
            raise HTTPException(403,'TikTok chưa cấp quyền video.publish.')
        info = client.creator(token['access_token'])
        token['expires_at'] = time.time()+int(token.get('expires_in',0))
        with ps.db() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM accounts WHERE open_id=?', (token['open_id'],)).fetchone()
            if existing and existing['owner'] != row['owner']:
                raise HTTPException(409,'Tài khoản TikTok đang thuộc một tài khoản Content Studio khác.')
            aid = existing['id'] if existing else secrets.token_hex(16)
            db.execute('INSERT OR REPLACE INTO accounts VALUES(?,?,?,?,?,1)',
                       (aid,row['owner'],token['open_id'],info.get('creator_nickname','TikTok'),ps.encrypt(token)))
        return {'connected':True}
    except TikTokError as exc:
        raise HTTPException(502,str(exc)) from None


@router.get('/owners/{owner}/accounts/{aid}/creator')
def creator(owner: str, aid: str):
    try:
        info = client.creator(account_token(owner,aid))
    except TikTokError as exc:
        raise HTTPException(502,str(exc)) from None
    if os.getenv('TIKTOK_APP_AUDITED') != '1':
        info['privacy_level_options'] = [x for x in info.get('privacy_level_options',[]) if x == 'SELF_ONLY']
    return info


@router.delete('/owners/{owner}/accounts/{aid}')
def disconnect(owner: str, aid: str):
    with ps.lock, ps.db() as db:
        db.execute('BEGIN IMMEDIATE')
        account = ps.owned(db,'accounts',aid,owner)
        rows = db.execute('SELECT * FROM jobs WHERE owner=? AND account_id=?', (owner,aid)).fetchall()
        if any(r['status'] in ps.INFLIGHT for r in rows):
            raise HTTPException(409,'Có lượt đăng đang xử lý/cần đối chiếu. Hoàn tất kiểm tra trước khi ngắt kết nối.')
        for row in rows:
            if row['status'] in ('QUEUED','SCHEDULED','MISSED','BLOCKED'):
                ps.set_status(db,row['id'],'CANCELLED','Tài khoản đã ngắt kết nối.')
        db.execute('UPDATE accounts SET connected=0 WHERE id=?', (aid,))
    # Local disconnection always stops dispatch. Report revocation failure honestly.
    revoked = False
    try:
        client.revoke(ps.decrypt(account['tokens'])['access_token']); revoked = True
    except (TikTokError,HTTPException):
        pass
    with ps.db() as db:
        db.execute('UPDATE accounts SET tokens=? WHERE id=?', (ps.encrypt({}),aid))
    return {'disconnected':True,'revoked_at_tiktok':revoked}


class VideoMeta(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(pattern=r'^vid_[a-f0-9]{32}$')
    revision: int = Field(ge=1)
    version: int = Field(ge=1)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    review_mode: str = Field(pattern=r'^(web|telegram)$')
    caption: str = Field(max_length=10000)
    shop_callout: bool = False
    standalone: bool = False
    content_mode: Literal["ordinary", "tiktok_shop"] | None = None


def probe(path):
    try:
        result = subprocess.run([os.getenv('FFPROBE_BIN','ffprobe'),'-v','error','-show_entries',
            'format=duration:stream=codec_type,codec_name','-of','json',str(path)], capture_output=True, timeout=20, check=True)
        body = json.loads(result.stdout)
        duration = float(body['format']['duration'])
        if duration <= 0 or duration > 3600 or not any(s.get('codec_type')=='video' and s.get('codec_name')=='h264' for s in body['streams']):
            raise ValueError()
        return duration
    except FileNotFoundError:
        raise HTTPException(503,'Máy chủ chưa có ffprobe để kiểm tra MP4.') from None
    except (subprocess.SubprocessError,ValueError,KeyError):
        raise HTTPException(400,'Cần MP4 có hình H.264 và thời lượng đọc được.') from None


def telegram_approval(meta):
    with handoff.connect() as db:
        from app.video_review_v2 import latest_video, latest_receipt, ensure_table
        ensure_table(db)
        receipt = latest_receipt(db,meta.request_id,meta.revision)
        row = latest_video(db,meta.request_id)
        if not row or (row['revision'],row['version'],row['sha256']) != (meta.revision,meta.version,meta.sha256):
            raise HTTPException(409,'Video không khớp bản đã gửi Telegram.')
        return row['status'],receipt['page_id']


@router.post('/owners/{owner}/videos')
def register_video(owner: str, metadata: str = Form(...), file: UploadFile = File(...)):
    try:
        meta = VideoMeta.model_validate_json(metadata)
    except ValidationError:
        raise HTTPException(422,'Thông tin MP4 chưa đúng cấu trúc.') from None
    snapshot = handoff.folder() / f"{meta.request_id}_r{meta.revision}.json"
    if snapshot.is_file():
        recorded = json.loads(snapshot.read_text(encoding="utf-8"))
        recorded_mode = recorded.get("content_mode", "tiktok_shop")
        if meta.content_mode is not None and meta.content_mode != recorded_mode:
            raise HTTPException(409, "Loại nội dung khác bản đã lưu vào Notion.")
        meta.content_mode = recorded_mode
    if meta.content_mode is None:
        meta.content_mode = "tiktok_shop" if meta.shop_callout else "ordinary"
    if meta.content_mode == "ordinary" and shop_reference(meta.caption):
        raise HTTPException(422, "Caption Video thường không được chứa nội dung giỏ hàng/TikTok Shop.")
    path = handoff.folder() / (secrets.token_hex(16)+'.mp4')
    keep = False
    try:
        save_upload(file.file,path,meta.sha256)
        duration = probe(path)
        initial, page = telegram_approval(meta) if meta.review_mode=='telegram' else ('ATTACHED',None)
        with ps.lock, ps.db() as db:
            db.execute('BEGIN IMMEDIATE')
            latest = db.execute('SELECT * FROM videos WHERE owner=? AND request_id=? ORDER BY revision DESC,version DESC LIMIT 1', (owner,meta.request_id)).fetchone()
            if latest:
                old = (latest['revision'],latest['version'])
                new = (meta.revision,meta.version)
                if new < old or (new == old and latest['sha256'] != meta.sha256):
                    raise HTTPException(409,'Phiên bản video cũ hoặc nội dung file đã thay đổi.')
                if new == old:
                    previous_meta = json.loads(latest['meta'])
                    for key in ('content_mode', 'caption', 'shop_callout', 'standalone', 'review_mode'):
                        default = 'ordinary' if key == 'content_mode' else False if key in ('shop_callout', 'standalone') else None
                        if previous_meta.get(key, default) != getattr(meta, key):
                            raise HTTPException(409, 'Cùng MP4/phiên bản nhưng thông tin đăng đã đổi. Cần duyệt bản mới.')
                    if not latest['current']:
                        raise HTTPException(409,'Video đã được mở lại để sửa. Hãy tải và duyệt phiên bản mới.')
                    if meta.review_mode=='telegram':
                        db.execute('UPDATE videos SET status=? WHERE id=?', (initial,latest['id']))
                    return {'id':latest['id'],'status':initial if meta.review_mode=='telegram' else latest['status'],'duration':duration,'sha256':meta.sha256}
            ps.cancel_for_video(db,owner,meta.request_id)
            vid = secrets.token_hex(16)
            values = meta.model_dump(); values['notion_page_id'] = page
            db.execute('INSERT INTO videos VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (vid,owner,meta.request_id,meta.revision,meta.version,meta.sha256,path.stat().st_size,duration,str(path),meta.review_mode,initial,1,ps.canonical(values),time.time() if initial=='APPROVED' else None,'telegram' if initial=='APPROVED' else None))
            keep = True
            return {'id':vid,'status':initial,'duration':duration,'sha256':meta.sha256}
    finally:
        if not keep:
            path.unlink(missing_ok=True)


@router.get('/owners/{owner}/videos/{request_id}')
def video_status(owner: str, request_id: str):
    with ps.db() as db:
        row = db.execute('SELECT * FROM videos WHERE owner=? AND request_id=? AND current=1', (owner,request_id)).fetchone()
        if not row: return None
        return {k:row[k] for k in ('id','revision','version','sha256','status','duration','review_mode')}


@router.get('/owners/{owner}/ordinary-videos')
def ordinary_videos(owner: str):
    with ps.db() as db:
        rows=db.execute('SELECT * FROM videos WHERE owner=? AND current=1 ORDER BY rowid DESC LIMIT 200',(owner,)).fetchall()
    return [{**{k:r[k] for k in ('id','revision','version','sha256','status','duration')},'caption':json.loads(r['meta'])['caption']}
            for r in rows if json.loads(r['meta']).get('standalone')]


@router.get('/owners/{owner}/ordinary-videos/{vid}/file')
def ordinary_file(owner: str,vid: str):
    with ps.db() as db:row=ps.owned(db,'videos',vid,owner)
    if not json.loads(row['meta']).get('standalone'):raise HTTPException(404)
    path=Path(row['path'])
    if not path.is_file():raise HTTPException(404)
    return FileResponse(path,media_type='video/mp4',headers={'Cache-Control':'private, no-store'})


class Decision(BaseModel):
    sha256: str
    approve: bool
    watched: bool


@router.post('/owners/{owner}/videos/{vid}/review')
def decide(owner: str, vid: str, body: Decision):
    with ps.lock, ps.db() as db:
        db.execute('BEGIN IMMEDIATE')
        row = ps.owned(db,'videos',vid,owner)
        if not row['current'] or row['sha256']!=body.sha256 or row['review_mode']!='web' or not body.watched:
            raise HTTPException(409,'Xem đúng bản video đang chờ duyệt trên web trước khi xác nhận.')
        if db.execute("SELECT 1 FROM jobs WHERE video_id=? AND status IN ('QUEUED','SCHEDULED','INITIATING','PROCESSING','RECONCILE')", (vid,)).fetchone():
            raise HTTPException(409,'Hủy lịch đang có trước khi thay quyết định duyệt.')
        status = 'APPROVED' if body.approve else 'NEEDS_REVISION'
        db.execute('UPDATE videos SET status=?,reviewed_at=?,reviewer=? WHERE id=?', (status,time.time(),owner,vid))
        return {'status':status}


@router.post('/owners/{owner}/videos/{request_id}/prepare-edit')
def prepare_edit(owner: str, request_id: str):
    with ps.lock,ps.db() as db:
        db.execute('BEGIN IMMEDIATE'); ps.cancel_for_video(db,owner,request_id)
    return {'cancelled':True}


class PostInfo(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(max_length=4400)
    privacy_level: str = Field(pattern=r'^(SELF_ONLY|PUBLIC_TO_EVERYONE|MUTUAL_FOLLOW_FRIENDS|FOLLOWER_OF_CREATOR)$')
    disable_comment: bool = True
    disable_duet: bool = True
    disable_stitch: bool = True
    brand_content_toggle: bool = False
    brand_organic_toggle: bool = False
    is_aigc: bool = True

    @model_validator(mode='after')
    def valid(self):
        if shop_reference(self.title):
            raise ValueError('Chưa hỗ trợ nội dung giỏ hàng/TikTok Shop trong lượt đăng tự động.')
        if len(self.title.encode('utf-16-le'))//2 > 2200:
            raise ValueError('Caption và hashtag tối đa 2200 ký tự UTF-16.')
        if self.brand_content_toggle and self.privacy_level=='SELF_ONLY':
            raise ValueError('Nội dung hợp tác thương hiệu không được đặt riêng tư.')
        return self


class Publication(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation_id: str = Field(pattern=r'^[a-zA-Z0-9-]{16,100}$')
    video_id: str
    account_id: str
    scheduled_at: datetime | None = None
    post: PostInfo
    consent: bool
    watched: bool
    no_shop_required: bool


def validate_creator(post, info, duration):
    if post['privacy_level'] not in info.get('privacy_level_options',[]):
        raise HTTPException(409,'Quyền riêng tư không còn phù hợp tài khoản. Chọn lại trước khi đăng.')
    for key in ('comment','duet','stitch'):
        if info.get(key+'_disabled') and not post['disable_'+key]:
            raise HTTPException(409,'Thiết lập tương tác đã thay đổi trên TikTok. Hãy kiểm tra lại.')
    if duration > info.get('max_video_post_duration_sec',0):
        raise HTTPException(409,'Video vượt thời lượng tài khoản TikTok cho phép.')
    if os.getenv('TIKTOK_APP_AUDITED')!='1' and post['privacy_level']!='SELF_ONLY':
        raise HTTPException(409,'Ứng dụng chưa được xét duyệt để đăng công khai.')


@router.post('/owners/{owner}/jobs', status_code=201)
def create_job(owner: str, body: Publication):
    if not (body.consent and body.watched and body.no_shop_required):
        raise HTTPException(400,'Cần xem video, đồng ý gửi TikTok và xác nhận video không cần gắn giỏ hàng.')
    encoded = ps.canonical(body.model_dump(mode='json'))
    with ps.db() as db:
        duplicate = db.execute('SELECT * FROM jobs WHERE owner=? AND operation_id=?', (owner,body.operation_id)).fetchone()
        if duplicate:
            if duplicate['request']!=encoded: raise HTTPException(409,'Mã yêu cầu đã được dùng cho nội dung khác.')
            return ps.public_job(duplicate)
        video = ps.owned(db,'videos',body.video_id,owner)
        ps.owned(db,'accounts',body.account_id,owner)
    require_ready()
    if os.getenv('TIKTOK_SCHEDULER_ENABLED')!='1':
        raise HTTPException(503,'Chưa bật bộ xử lý lịch đăng trên máy chủ.')
    if json.loads(video['meta']).get('shop_callout') or json.loads(video['meta']).get('content_mode') == 'tiktok_shop':
        raise HTTPException(409,'Bản này là nội dung TikTok Shop. Chưa hỗ trợ đăng tự động; hãy dùng Video thường đã được duyệt.')
    info = creator(owner,body.account_id)
    validate_creator(body.post.model_dump(),info,video['duration'])
    due = time.time()
    if body.scheduled_at:
        if body.scheduled_at.tzinfo is None: raise HTTPException(400,'Lịch đăng phải có múi giờ.')
        due = body.scheduled_at.timestamp()
        if due < time.time()+30: raise HTTPException(400,'Chọn giờ đăng trong tương lai, cách ít nhất 30 giây.')
    with ps.lock,ps.db() as db:
        db.execute('BEGIN IMMEDIATE')
        duplicate = db.execute('SELECT * FROM jobs WHERE owner=? AND operation_id=?', (owner,body.operation_id)).fetchone()
        if duplicate:
            if duplicate['request']!=encoded: raise HTTPException(409,'Mã yêu cầu đã dùng.')
            return ps.public_job(duplicate)
        video = ps.owned(db,'videos',body.video_id,owner)
        if not video['current'] or video['status']!='APPROVED':
            raise HTTPException(409,'Chỉ đăng đúng MP4 hiện tại đã duyệt.')
        if db.execute("SELECT 1 FROM jobs WHERE video_id=? AND account_id=? AND status NOT IN ('FAILED','CANCELLED','MISSED','BLOCKED')", (body.video_id,body.account_id)).fetchone():
            raise HTTPException(409,'Đã có lượt đăng cho video và tài khoản này. Hãy theo dõi lượt đang có.')
        jid, now = secrets.token_hex(16),time.time()
        status = 'SCHEDULED' if body.scheduled_at else 'QUEUED'
        db.execute('INSERT INTO jobs(id,owner,operation_id,request,video_id,account_id,status,due,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (jid,owner,body.operation_id,encoded,body.video_id,body.account_id,status,due,now,now))
        ps.event(db,jid,status,'Người dùng xác nhận gửi đúng video và nội dung đăng.')
        db.execute('INSERT OR REPLACE INTO sync_queue VALUES(?,?,NULL)', (jid,status))
        return ps.public_job(ps.owned(db,'jobs',jid,owner))


@router.get('/owners/{owner}/jobs')
def jobs(owner: str):
    with ps.db() as db:
        return [ps.public_job(r) for r in db.execute('SELECT * FROM jobs WHERE owner=? ORDER BY created DESC LIMIT 200', (owner,))]


class JobAction(BaseModel):
    version: int
    action: str = Field(pattern=r'^(cancel|reschedule)$')
    scheduled_at: datetime | None = None


@router.post('/owners/{owner}/jobs/{jid}/actions')
def job_action(owner: str, jid: str, body: JobAction):
    with ps.lock,ps.db() as db:
        db.execute('BEGIN IMMEDIATE')
        row = ps.owned(db,'jobs',jid,owner)
        if row['version']!=body.version or row['status'] not in ('QUEUED','SCHEDULED','MISSED','BLOCKED'):
            raise HTTPException(409,'Lượt đăng đã thay đổi hoặc đang gửi; không thể đổi lịch/hủy lúc này.')
        if body.action=='cancel':
            ps.set_status(db,jid,'CANCELLED')
        else:
            if not body.scheduled_at or not body.scheduled_at.tzinfo or body.scheduled_at.timestamp()<time.time()+30:
                raise HTTPException(400,'Chọn giờ trong tương lai và có múi giờ.')
            video = ps.owned(db,'videos',row['video_id'],owner)
            if not video['current'] or video['status']!='APPROVED': raise HTTPException(409,'Video không còn được duyệt.')
            account = ps.owned(db,'accounts',row['account_id'],owner)
            if not account['connected']:
                raise HTTPException(409,'Kết nối lại tài khoản TikTok trước khi đổi lịch.')
            if db.execute("SELECT 1 FROM jobs WHERE video_id=? AND account_id=? AND id!=? AND status NOT IN ('FAILED','CANCELLED','MISSED','BLOCKED')",
                          (row['video_id'],row['account_id'],jid)).fetchone():
                raise HTTPException(409,'Đã có lượt đăng khác cho video và tài khoản này. Theo dõi lượt đó để tránh đăng trùng.')
            ps.set_status(db,jid,'SCHEDULED',due=body.scheduled_at.timestamp())
        return ps.public_job(ps.owned(db,'jobs',jid,owner))


def check_video(video):
    path = Path(video['path'])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=video['sha256']:
        raise HTTPException(409,'File MP4 đã thiếu hoặc khác bản duyệt.')
    if not video['current'] or video['status']!='APPROVED':
        raise HTTPException(409,'Video không còn là bản hiện tại đã duyệt.')
    if video['review_mode']=='telegram':
        meta = json.loads(video['meta']); meta.pop('notion_page_id',None)
        status,_ = telegram_approval(VideoMeta.model_validate(meta))
        if status!='APPROVED': raise HTTPException(409,'Telegram chưa duyệt bản này.')


def process_job(jid):
    with ps.db() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone()
        video = ps.owned(db,'videos',row['video_id'],row['owner'])
    body = json.loads(row['request'])
    try:
        require_ready(); check_video(video)
        token = account_token(row['owner'],row['account_id'])
        info = client.creator(token)
        validate_creator(body['post'],info,video['duration'])
        grant = secrets.token_urlsafe(32)
        with ps.db() as db:
            db.execute('INSERT INTO grants VALUES(?,?,?)',(hashlib.sha256(grant.encode()).hexdigest(),video['id'],time.time()+7200))
            db.execute('UPDATE jobs SET attempted=? WHERE id=?', (time.time(),jid))
        result = client.publish(token,body['post'],os.environ['STUDIO_PUBLIC_URL'].rstrip('/')+'/media/tiktok/'+grant)
        publish_id = result.get('publish_id')
        if not isinstance(publish_id,str) or not publish_id or publish_id.startswith('v_pub_sandbox_'):
            raise TikTokError('missing_publish_id',ambiguous=True)
        with ps.db() as db:
            ps.set_status(db,jid,'PROCESSING',publish_id=publish_id,next_poll=time.time()+30)
    except (HTTPException,TikTokError) as exc:
        ambiguous = isinstance(exc,TikTokError) and exc.ambiguous
        status = 'RECONCILE' if ambiguous else 'BLOCKED'
        with ps.db() as db: ps.set_status(db,jid,status,error=exc.detail if isinstance(exc,HTTPException) else str(exc))
    except Exception:
        with ps.db() as db: ps.set_status(db,jid,'RECONCILE',error='Lượt gửi bị gián đoạn; cần đối chiếu TikTok trước khi thao tác tiếp.')


def poll_job(jid):
    with ps.db() as db: row = db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
    try:
        result = client.status(account_token(row['owner'],row['account_id']),row['publish_id'])
        status = result.get('status')
        with ps.db() as db:
            if status=='PUBLISH_COMPLETE':
                ids = result.get('publicaly_available_post_id') or []
                ids = [str(x) for x in ids if str(x).isdigit()]
                ps.set_status(db,jid,'PUBLISHED',post_ids=json.dumps(ids))
            elif status=='FAILED':
                reason = str(result.get('fail_reason','publish_failed'))
                reason = reason if re.fullmatch(r'[a-zA-Z0-9_]{1,100}',reason) else 'publish_failed'
                ps.set_status(db,jid,'FAILED',error=reason)
            else:
                db.execute('UPDATE jobs SET lease_until=NULL,next_poll=?,error=NULL WHERE id=?',(time.time()+60,jid))
    except Exception:
        with ps.db() as db:
            db.execute('UPDATE jobs SET lease_until=NULL,next_poll=?,error=? WHERE id=?',
                       (time.time()+300,'Chưa đọc được kết quả TikTok; giữ nguyên mã đăng, không gửi lại.',jid))


def sync_notion():
    from app import notion_client as nc
    with ps.db() as db:
        pending = db.execute('SELECT sync_queue.*,videos.meta,jobs.due,jobs.updated FROM sync_queue JOIN jobs ON jobs.id=sync_queue.job_id JOIN videos ON videos.id=jobs.video_id LIMIT 20').fetchall()
    for row in pending:
        page = json.loads(row['meta']).get('notion_page_id')
        if page:
            try:
                status = {'QUEUED':'SCHEDULED','INITIATING':'PUBLISHING','PROCESSING':'PUBLISHING','BLOCKED':'FAILED','RECONCILE':'FAILED','MISSED':'FAILED','CANCELLED':'APPROVED'}.get(row['status'],row['status'])
                props = {'status':{'select':{'name':status}}}
                available = nc.notion.pages.retrieve(page_id=page).get('properties',{})
                if 'scheduled_at' in available:
                    props['scheduled_at'] = {'date':{'start':datetime.fromtimestamp(row['due'],timezone.utc).isoformat()} if row['status']!='CANCELLED' else None}
                if 'published_at' in available and row['status']=='PUBLISHED':
                    props['published_at'] = {'date':{'start':datetime.fromtimestamp(row['updated'],timezone.utc).isoformat()}}
                nc.notion.pages.update(page_id=page,properties=props)
            except Exception:
                with ps.db() as db: db.execute('UPDATE sync_queue SET error=? WHERE job_id=?',('Chưa đồng bộ Notion; không gửi đăng lại.',row['job_id']))
                continue
        with ps.db() as db: db.execute('DELETE FROM sync_queue WHERE job_id=? AND status=?',(row['job_id'],row['status']))


@router.post('/tick')
def tick():
    # Pausing new dispatch must not abandon already accepted posts or Notion sync.
    enabled = os.getenv('TIKTOK_SCHEDULER_ENABLED') == '1'
    now = time.time()
    send_ids, poll_ids = [],[]
    with ps.lock,ps.db() as db:
        db.execute('BEGIN IMMEDIATE')
        for row in db.execute("SELECT * FROM jobs WHERE status='INITIATING' AND lease_until<?",(now,)).fetchall():
            ps.set_status(db,row['id'],'RECONCILE',error='Máy chủ dừng khi bắt đầu gửi. Kiểm tra TikTok trước khi thử lại.')
        rows = db.execute("SELECT * FROM jobs WHERE status IN ('QUEUED','SCHEDULED') AND due<=? ORDER BY due LIMIT 3",(now,)).fetchall() if enabled else []
        for row in rows:
            if now-row['due']>900:
                ps.set_status(db,row['id'],'MISSED',error='Lịch trễ hơn 15 phút. Chọn lại giờ đăng.')
                continue
            ps.set_status(db,row['id'],'INITIATING',lease_until=now+600)
            send_ids.append(row['id'])
        for row in db.execute("SELECT * FROM jobs WHERE status='PROCESSING' AND next_poll<=? AND (lease_until IS NULL OR lease_until<?) LIMIT 10",(now,now)).fetchall():
            db.execute('UPDATE jobs SET lease_until=? WHERE id=?',(now+600,row['id']))
            poll_ids.append(row['id'])
    for jid in send_ids: process_job(jid)
    for jid in poll_ids: poll_job(jid)
    sync_notion()
    return {'enabled':enabled,'processed':len(send_ids),'checked':len(poll_ids)}


@media_router.get('/media/tiktok/{grant}')
def media(grant: str):
    if not re.fullmatch(r'[A-Za-z0-9_-]{40,60}',grant): raise HTTPException(404)
    with ps.db() as db:
        row = db.execute('SELECT videos.* FROM grants JOIN videos ON videos.id=grants.video_id WHERE token=? AND expires>?',
                         (hashlib.sha256(grant.encode()).hexdigest(),time.time())).fetchone()
    if not row: raise HTTPException(404,'Đường tải đã hết hạn.')
    path = Path(row['path'])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']: raise HTTPException(404)
    return FileResponse(path,media_type='video/mp4',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
