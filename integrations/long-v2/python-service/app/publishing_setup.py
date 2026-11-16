"""Local configuration checks; never return credentials or claim TikTok approval."""
from urllib.parse import urlsplit

from cryptography.fernet import Fernet


def configuration(env):
    checks = []

    def add(identifier, label, ok, action):
        checks.append({'id': identifier, 'label': label, 'ok': bool(ok),
                       'action': '' if ok else action})

    def supplied(name):
        value = env.get(name, '').strip()
        return bool(value) and not any(marker in value.lower() for marker in
                                      ('your_', 'your-', 'replace_me', 'example.com'))

    add('TIKTOK_CLIENT_KEY', 'Mã ứng dụng TikTok của dự án', supplied('TIKTOK_CLIENT_KEY'),
        'Dùng lại mã ứng dụng của dự án đã được bàn giao; chưa cần tạo ứng dụng mới.')
    add('TIKTOK_CLIENT_SECRET', 'Khóa ứng dụng TikTok của dự án', supplied('TIKTOK_CLIENT_SECRET'),
        'Người quản lý lưu khóa ứng dụng vào cấu hình riêng trên máy chủ.')
    root = env.get('STUDIO_PUBLIC_URL', '').strip().rstrip('/')
    try:
        url = urlsplit(root)
        public_ok = bool(url.scheme == 'https' and url.hostname and not
                         (url.username or url.password or url.query or url.fragment or url.path))
        _ = url.port
    except ValueError:
        public_ok = False
    add('STUDIO_PUBLIC_URL', 'Địa chỉ HTTPS của Content Studio', public_ok,
        'Cấu hình địa chỉ HTTPS đang hoạt động, trỏ tới cổng web công khai 8080.')
    add('TIKTOK_V2_REDIRECT_URI', 'Địa chỉ quay lại sau khi kết nối TikTok',
        public_ok and env.get('TIKTOK_V2_REDIRECT_URI', '').strip() == root + '/api/v2/tiktok/callback',
        'Khai báo địa chỉ HTTPS của web + /api/v2/tiktok/callback trong ứng dụng TikTok và cấu hình máy chủ; giữ callback v1 nếu còn dùng.')
    try:
        Fernet(env.get('TIKTOK_TOKEN_ENCRYPTION_KEY', '').encode())
        encryption_ok = True
    except (ValueError, TypeError):
        encryption_ok = False
    add('TIKTOK_TOKEN_ENCRYPTION_KEY', 'Bảo vệ kết nối của từng tài khoản', encryption_ok,
        'Cấu hình khóa mã hóa hợp lệ; giữ nguyên khóa đã dùng để lưu các kết nối cũ.')
    connect_ready = all(item['ok'] for item in checks)
    add('TIKTOK_MEDIA_URL_VERIFIED', 'Tên miền tải MP4 đã được xác minh',
        env.get('TIKTOK_MEDIA_URL_VERIFIED') == '1',
        'Xác minh tên miền hoặc tiền tố /media/tiktok/ trong cùng ứng dụng TikTok trước khi bật đăng.')
    ready = all(item['ok'] for item in checks)
    enabled = env.get('TIKTOK_SCHEDULER_ENABLED') == '1'
    add('TIKTOK_SCHEDULER_ENABLED', 'Bộ xử lý lịch đăng', enabled,
        'Bật bộ xử lý sau khi kiểm tra cấu hình; chỉ dùng workflow Publishing Scheduler v2 cho dữ liệu này.')
    message = ('Cấu hình trên máy đã đủ. Kết nối tài khoản để TikTok xác nhận quyền đăng.' if ready else
               'Chưa đủ cấu hình để đăng thật. Kiểm tra các mục còn thiếu bên dưới.')
    if ready and not enabled:
        message = 'Đã đủ cấu hình trên máy; bộ xử lý lịch chưa bật nên chưa gửi bài mới.'
    return {'ready': ready, 'connect_ready': connect_ready,
            'missing': [item['id'] for item in checks[:-1] if not item['ok']],
            'checks': checks, 'audited': env.get('TIKTOK_APP_AUDITED') == '1',
            'scheduler_enabled': enabled, 'message': message,
            'permission_note': 'Cấu hình có mặt không chứng minh quyền video.publish còn hiệu lực. Mỗi tài khoản cần kết nối và được TikTok xác nhận.'}
