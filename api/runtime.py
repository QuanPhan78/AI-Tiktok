"""Bounded read-only probe of the configured public gateway; never declares posting ready."""
import os
import time
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter

router = APIRouter(prefix='/api/v2')
_last = (None, 0, {})


@router.get('/external-status')
def external_status():
    global _last
    root = os.getenv('STUDIO_PUBLIC_URL', '').rstrip('/')
    cached_root, stamp, result = _last
    if cached_root == root and time.monotonic() - stamp < 30:
        return result
    u = urlsplit(root)
    configured = bool(u.scheme == 'https' and u.hostname and not (u.username or u.password or u.query or u.fragment or u.path))
    connected = False
    if configured:
        try:
            with httpx.Client(timeout=3, trust_env=False, follow_redirects=False) as client:
                with client.stream('GET', root + '/policy', headers={'ngrok-skip-browser-warning': '1'}) as response:
                    connected = response.status_code == 200 and response.headers.get('X-Content-Studio-Gateway') == '1'
        except httpx.HTTPError:
            pass
    result = {'configured': configured, 'connected': connected, 'message':
              'Kết nối ngoài máy đang bật. Telegram và TikTok vẫn cần được cấu hình, cấp quyền riêng.' if connected else
              'Kết nối ngoài máy đang tắt hoặc chưa kiểm tra được. Bạn vẫn làm nội dung tại đây; Telegram và TikTok chưa thể nhận kết quả.'}
    _last = (root, time.monotonic(), result)
    return result
