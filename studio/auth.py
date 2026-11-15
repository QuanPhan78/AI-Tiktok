"""Local user identities; resource ownership never comes from a browser field."""
import hashlib
import os
import re
import secrets
import time
from contextvars import ContextVar
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from pwdlib import PasswordHash

from studio.store import Store

identity = ContextVar('studio_user', default=None)
passwords = PasswordHash.recommended()
router = APIRouter(prefix='/api/v2/auth', tags=['Tài khoản'])
COOKIE = 'studio_login'


def enabled():
    return os.getenv('STUDIO_AUTH_ENABLED', '0') == '1'


def current():
    return identity.get() or {'id': 'local', 'username': 'Máy này', 'role': 'admin'}


def tables(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,
      recovery TEXT NOT NULL,role TEXT NOT NULL,created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS logins(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,csrf TEXT NOT NULL,expires REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS ownership(kind TEXT NOT NULL,resource TEXT NOT NULL,owner TEXT NOT NULL,
      PRIMARY KEY(kind,resource));
    CREATE TABLE IF NOT EXISTS auth_attempts(bucket TEXT NOT NULL,at REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS auth_attempt_bucket ON auth_attempts(bucket,at);
    CREATE TABLE IF NOT EXISTS publication_bindings(session_id TEXT PRIMARY KEY,owner TEXT NOT NULL);
    ''')


def init(store=None):
    store = store or Store()
    with store.db() as db:
        tables(db)
    return store


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def own(kind, resource, store=None):
    with init(store).db() as db:
        db.execute('INSERT INTO ownership(kind,resource,owner) VALUES(?,?,?)', (kind, resource, current()['id']))


def require_owner(kind, resource, store=None):
    if not enabled():
        return
    with init(store).db() as db:
        row = db.execute('SELECT owner FROM ownership WHERE kind=? AND resource=?', (kind, resource)).fetchone()
    if not row or row[0] != current()['id']:
        raise HTTPException(404, 'Không tìm thấy nội dung của bạn.')


def throttle(bucket, limit=10, seconds=900, store=None):
    with init(store).db() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM auth_attempts WHERE at<?', (time.time() - 86400,))
        count = db.execute('SELECT COUNT(*) FROM auth_attempts WHERE bucket=? AND at>?', (bucket, time.time()-seconds)).fetchone()[0]
        if count >= limit:
            raise HTTPException(429, 'Quá nhiều yêu cầu. Vui lòng thử lại sau.')
        db.execute('INSERT INTO auth_attempts VALUES(?,?)', (bucket, time.time()))


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(pattern=r'^[a-zA-Z0-9_.-]{3,40}$')
    password: str = Field(min_length=12, max_length=200)


class Recovery(Credentials):
    recovery_code: str = Field(min_length=20, max_length=200)


class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(min_length=12, max_length=200)


def create_user(creds, bootstrap=False, store=None):
    store = init(store)
    uid, recovery = secrets.token_hex(16), secrets.token_urlsafe(32)
    hashed = passwords.hash(creds.password)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if bootstrap != (count == 0):
            raise HTTPException(409, 'Thiết lập quản trị trên máy trước khi mở đăng ký.' if not count else 'Quản trị đã được thiết lập.')
        if db.execute('SELECT 1 FROM users WHERE username=?', (creds.username.lower(),)).fetchone():
            raise HTTPException(409, 'Tên đăng nhập đã được sử dụng.')
        db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)', (uid, creds.username.lower(), hashed, digest(recovery), 'admin' if bootstrap else 'user', time.time()))
        if bootstrap:
            # Only ownership metadata changes; approved JSON and its digest are untouched.
            for kind, table in [('session', 'sessions'), ('asset', 'assets')]:
                db.execute(f'INSERT OR IGNORE INTO ownership SELECT ?,id,? FROM {table}', (kind, uid))
            db.execute("UPDATE ownership SET owner=? WHERE owner='local'", (uid,))
            db.execute("UPDATE publication_bindings SET owner=? WHERE owner='local'", (uid,))
    return {'id': uid, 'username': creds.username.lower(), 'role': 'admin' if bootstrap else 'user', 'recovery_code': recovery}


def login_cookie(user, response, request):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    with init().db() as db:
        db.execute('INSERT INTO logins VALUES(?,?,?,?)', (digest(token), user['id'], csrf, time.time()+86400*7))
    secure = request.url.scheme == 'https'
    response.set_cookie(COOKIE, token, max_age=86400*7, httponly=True, secure=secure, samesite='lax', path='/')
    return {'user': {k: user[k] for k in ('id', 'username', 'role')}, 'csrf': csrf}


@router.get('/me')
def me(request: Request):
    with init().db() as db:
        setup = not db.execute('SELECT 1 FROM users LIMIT 1').fetchone()
    return {'enabled': enabled(), 'setup_required': setup, 'user': getattr(request.state, 'user', None),
            'csrf': getattr(request.state, 'csrf', ''), 'support_contact':os.getenv('STUDIO_SUPPORT_CONTACT','')}


class DeleteAccount(BaseModel):
    password: str = Field(max_length=200)
    confirm_username: str


@router.delete('/account')
def delete_account(body: DeleteAccount, response: Response):
    import json
    from pathlib import Path
    store=init(); uid=current()['id']
    with store.db() as db:
        user=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not user or body.confirm_username!=user['username'] or not passwords.verify(body.password,user['password']):
            raise HTTPException(400,'Nhập đúng mật khẩu và tên đăng nhập để xác nhận xóa.')
        if user['role']=='admin':
            raise HTTPException(409,'Tài khoản quản trị giữ dữ liệu dự án. Cần chuyển quyền quản trị và sao lưu trước khi xóa.')
        sessions=db.execute("SELECT sessions.* FROM sessions JOIN ownership ON resource=sessions.id AND kind='session' WHERE owner=?",(uid,)).fetchall()
        assets=db.execute("SELECT assets.* FROM assets JOIN ownership ON resource=assets.id AND kind='asset' WHERE owner=?",(uid,)).fetchall()
        if any(json.loads(s['body'])['status']=='processing' for s in sessions):
            raise HTTPException(409,'Đợi tác vụ nội dung đang chạy hoàn tất trước khi xóa.')
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='chat_turns'").fetchone():
            if db.execute("SELECT 1 FROM chat_turns JOIN ownership ON resource=session_id AND kind='session' WHERE owner=? AND status IN ('running','pending')",(uid,)).fetchone():
                raise HTTPException(409,'Đợi trợ lý trả lời xong trước khi xóa.')
    from api.publications import call
    result=call('/owners/'+uid,'DELETE')
    paths=[Path(json.loads(a['body'])['path']) for a in assets]
    for s in sessions:
        data=json.loads(s['body'])
        if data.get('video'):paths.append(store.video_path(data['video']))
    for path in paths:
        if path.resolve().is_relative_to(store.path.parent.resolve()):path.unlink(missing_ok=True)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        for s in sessions:
            for table,column in [('operations','session_id'),('history','session_id'),('chat_turns','session_id'),('publication_bindings','session_id'),('sessions','id')]:
                if db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():
                    db.execute(f'DELETE FROM {table} WHERE {column}=?',(s['id'],))
        for a in assets:db.execute('DELETE FROM assets WHERE id=?',(a['id'],))
        db.execute('DELETE FROM ownership WHERE owner=?',(uid,))
        db.execute('DELETE FROM logins WHERE user_id=?',(uid,))
        db.execute('DELETE FROM users WHERE id=?',(uid,))
    response.delete_cookie(COOKIE)
    return {'deleted':True,'revoked_at_tiktok':result['revoked_at_tiktok']}


@router.post('/setup')
def setup(creds: Credentials, request: Request, response: Response):
    local = request.client.host in ('localhost','127.0.0.1','::1') or os.getenv('STUDIO_BOOTSTRAP_LOCAL_PROXY')=='1'
    if not local or request.url.hostname not in ('localhost', '127.0.0.1', '::1') or request.headers.get('x-forwarded-for'):
        raise HTTPException(403, 'Chỉ thiết lập quản trị trực tiếp trên máy chủ.')
    user = create_user(creds, bootstrap=True)
    return {**login_cookie(user, response, request), 'recovery_code': user['recovery_code']}


@router.post('/register', status_code=201)
def register(creds: Credentials, request: Request, response: Response):
    if os.getenv('STUDIO_PUBLIC_MODE')=='1' and not os.getenv('STUDIO_SUPPORT_CONTACT','').strip():
        raise HTTPException(503,'Người quản lý cần thiết lập địa chỉ hỗ trợ trước khi mở đăng ký.')
    throttle('register:' + request.client.host, limit=5, seconds=3600)
    user = create_user(creds)
    return {**login_cookie(user, response, request), 'recovery_code': user['recovery_code']}


@router.post('/login')
def login(creds: Credentials, request: Request, response: Response):
    throttle('login:' + request.client.host)
    throttle('login-user:' + creds.username.lower(), limit=20)
    with init().db() as db:
        row = db.execute('SELECT * FROM users WHERE username=?', (creds.username.lower(),)).fetchone()
    if not row or not passwords.verify(creds.password, row['password']):
        raise HTTPException(401, 'Tên đăng nhập hoặc mật khẩu chưa đúng.')
    return login_cookie(dict(row), response, request)


@router.post('/recover')
def recover(creds: Recovery, request: Request):
    throttle('recover:' + request.client.host, limit=5)
    code = secrets.token_urlsafe(32)
    with init().db() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM users WHERE username=?', (creds.username.lower(),)).fetchone()
        if not row or not secrets.compare_digest(row['recovery'], digest(creds.recovery_code)):
            raise HTTPException(401, 'Thông tin khôi phục chưa đúng.')
        db.execute('UPDATE users SET password=?,recovery=? WHERE id=?', (passwords.hash(creds.password), digest(code), row['id']))
        db.execute('DELETE FROM logins WHERE user_id=?', (row['id'],))
    return {'recovery_code': code, 'message': 'Đã đổi mật khẩu. Lưu mã khôi phục mới rồi đăng nhập lại.'}


@router.post('/password')
def change_password(body: ChangePassword):
    with init().db() as db:
        row = db.execute('SELECT password FROM users WHERE id=?', (current()['id'],)).fetchone()
        if not row or not passwords.verify(body.old_password, row[0]):
            raise HTTPException(400, 'Mật khẩu hiện tại chưa đúng.')
        db.execute('UPDATE users SET password=? WHERE id=?', (passwords.hash(body.new_password), current()['id']))
        db.execute('DELETE FROM logins WHERE user_id=?', (current()['id'],))
    return {'message': 'Đã đổi mật khẩu. Vui lòng đăng nhập lại trên các thiết bị.'}


@router.post('/logout')
def logout(request: Request, response: Response):
    with init().db() as db:
        db.execute('DELETE FROM logins WHERE token=?', (digest(request.cookies.get(COOKIE, '')),))
    response.delete_cookie(COOKIE)
    return {'success': True}


async def middleware(request, call_next):
    from starlette.responses import JSONResponse
    path = request.url.path
    user = None
    try:
        if enabled():
            token = request.cookies.get(COOKIE, '')
            with init().db() as db:
                row = db.execute('SELECT users.id,username,role,csrf FROM logins JOIN users ON users.id=logins.user_id WHERE token=? AND expires>?', (digest(token), time.time())).fetchone()
            if row:
                user = {k: row[k] for k in ('id', 'username', 'role')}
                request.state.csrf = row['csrf']
            public = path in ('/api/v2/auth/me', '/api/v2/auth/setup', '/api/v2/auth/login', '/api/v2/auth/register', '/api/v2/auth/recover', '/api/v2/tiktok/callback') or path.startswith('/media/tiktok/')
            if path.startswith('/api/') and not public and not user:
                raise HTTPException(401, 'Đăng nhập để sử dụng Content Studio.')
            if request.method not in ('GET', 'HEAD', 'OPTIONS') and path.startswith('/api/'):
                origin = request.headers.get('origin')
                allowed = {str(request.base_url).rstrip('/'), 'http://127.0.0.1:8001', 'http://localhost:8001', os.getenv('STUDIO_PUBLIC_URL', '').rstrip('/')}
                if origin and origin not in allowed:
                    raise HTTPException(403, 'Yêu cầu phải gửi từ Content Studio.')
                if not public and (not row or not secrets.compare_digest(request.headers.get('x-csrf-token', ''), row['csrf'])):
                    raise HTTPException(403, 'Phiên đăng nhập thay đổi. Tải lại trang.')
        if os.getenv('STUDIO_PUBLIC_MODE') == '1':
            if not enabled():
                raise HTTPException(503, 'Cần bật đăng nhập trước khi mở website.')
            if path.startswith(('/generate', '/status', '/docs', '/redoc', '/openapi.json', '/api/v1')):
                raise HTTPException(404, 'Không tìm thấy trang.')
        request.state.user = user
        context = identity.set(user)
        try:
            match = re.match(r'^/api/v2/sessions/([^/]+)', path)
            if match:
                require_owner('session', match[1])
            match = re.match(r'^/api/v2/assets/([^/]+)', path)
            if match:
                require_owner('asset', match[1])
            return await call_next(request)
        finally:
            identity.reset(context)
    except HTTPException as exc:
        return JSONResponse({'detail': exc.detail}, status_code=exc.status_code)
