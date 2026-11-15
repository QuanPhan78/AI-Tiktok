"""Durable, account-bound jobs and approvals for the public Studio."""
import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from cryptography.fernet import Fernet
from fastapi import HTTPException
from app.handoff_v2 import folder

lock = threading.RLock()
ACTIVE = ('QUEUED', 'SCHEDULED', 'INITIATING', 'PROCESSING', 'RECONCILE')
INFLIGHT = ('INITIATING', 'PROCESSING', 'RECONCILE')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def cipher():
    try:
        return Fernet(os.environ['TIKTOK_TOKEN_ENCRYPTION_KEY'].encode())
    except (KeyError, ValueError):
        raise HTTPException(503, 'Chưa cấu hình khóa mã hóa kết nối TikTok.') from None


def encrypt(value):
    return cipher().encrypt(canonical(value).encode()).decode()


def decrypt(value):
    try:
        return json.loads(cipher().decrypt(value.encode()))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Không mở được kết nối TikTok. Kiểm tra khóa mã hóa trên máy chủ.') from None


@contextmanager
def db():
    connection = sqlite3.connect(folder() / 'publications.sqlite3', timeout=30)
    connection.row_factory = sqlite3.Row
    connection.executescript('''
      CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,owner TEXT NOT NULL,open_id TEXT UNIQUE NOT NULL,
        nickname TEXT NOT NULL,tokens TEXT NOT NULL,connected INTEGER NOT NULL DEFAULT 1);
      CREATE TABLE IF NOT EXISTS oauth(state TEXT PRIMARY KEY,owner TEXT NOT NULL,expires REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS videos(id TEXT PRIMARY KEY,owner TEXT NOT NULL,request_id TEXT NOT NULL,
        revision INTEGER NOT NULL,version INTEGER NOT NULL,sha256 TEXT NOT NULL,size INTEGER NOT NULL,
        duration REAL NOT NULL,path TEXT NOT NULL,review_mode TEXT NOT NULL,status TEXT NOT NULL,
        current INTEGER NOT NULL,meta TEXT NOT NULL,reviewed_at REAL,reviewer TEXT,
        UNIQUE(owner,request_id,revision,version));
      CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,operation_id TEXT NOT NULL,
        request TEXT NOT NULL,video_id TEXT NOT NULL,account_id TEXT NOT NULL,status TEXT NOT NULL,
        due REAL NOT NULL,created REAL NOT NULL,updated REAL NOT NULL,version INTEGER NOT NULL DEFAULT 1,
        publish_id TEXT,error TEXT,post_ids TEXT,attempted REAL,next_poll REAL,lease_until REAL,
        UNIQUE(owner,operation_id));
      CREATE TABLE IF NOT EXISTS grants(token TEXT PRIMARY KEY,video_id TEXT NOT NULL,expires REAL NOT NULL);
      CREATE TABLE IF NOT EXISTS publish_events(id INTEGER PRIMARY KEY,job_id TEXT NOT NULL,at REAL NOT NULL,
        status TEXT NOT NULL,detail TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS sync_queue(job_id TEXT PRIMARY KEY,status TEXT NOT NULL,error TEXT);
      CREATE INDEX IF NOT EXISTS jobs_due ON jobs(status,due);
    ''')
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def event(conn, jid, status, detail=''):
    conn.execute('INSERT INTO publish_events(job_id,at,status,detail) VALUES(?,?,?,?)', (jid,time.time(),status,detail))


def set_status(conn, jid, status, error=None, **fields):
    values = {'status': status, 'error': error, 'updated': time.time(), 'lease_until': None, **fields}
    conn.execute('UPDATE jobs SET ' + ','.join(k+'=?' for k in values) + ',version=version+1 WHERE id=?', (*values.values(),jid))
    event(conn,jid,status,error or '')
    conn.execute('INSERT OR REPLACE INTO sync_queue VALUES(?,?,NULL)', (jid,status))


def owned(conn, table, identifier, owner):
    assert table in ('accounts','videos','jobs')
    row = conn.execute(f'SELECT * FROM {table} WHERE id=? AND owner=?', (identifier,owner)).fetchone()
    if not row:
        raise HTTPException(404, 'Không tìm thấy dữ liệu của bạn.')
    return row


def cancel_for_video(conn, owner, request_id):
    rows = conn.execute('SELECT jobs.* FROM jobs JOIN videos ON videos.id=jobs.video_id WHERE jobs.owner=? AND videos.request_id=?', (owner,request_id)).fetchall()
    if any(r['status'] in INFLIGHT for r in rows):
        raise HTTPException(409, 'Video đang gửi hoặc cần đối chiếu TikTok. Chưa thể thay bản đang xử lý.')
    for row in rows:
        if row['status'] in ('QUEUED','SCHEDULED','MISSED','BLOCKED'):
            set_status(conn,row['id'],'CANCELLED','Nội dung/video được mở lại để sửa.')
    conn.execute('UPDATE videos SET current=0 WHERE owner=? AND request_id=?', (owner,request_id))


def public_job(row):
    data = dict(row)
    req = json.loads(data.pop('request'))
    data['post'] = req['post']
    data['post_ids'] = json.loads(data['post_ids'] or '[]')
    data['timezone'] = 'Asia/Ho_Chi_Minh'
    for key in ('lease_until','operation_id','owner'):
        data.pop(key,None)
    with db() as conn:
        video=conn.execute('SELECT revision,version,sha256 FROM videos WHERE id=?',(row['video_id'],)).fetchone()
        account=conn.execute('SELECT nickname FROM accounts WHERE id=?',(row['account_id'],)).fetchone()
        sync=conn.execute('SELECT error FROM sync_queue WHERE job_id=?',(row['id'],)).fetchone()
    data['video']=dict(video) if video else None
    data['account_name']=account['nickname'] if account else ''
    data['notion_sync_error']=sync['error'] if sync else None
    return data
