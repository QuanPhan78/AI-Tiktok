"""Read-only installation checks. Output contains setting names, never their values."""
import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ('studio', 'automation', 'publishing')


def supplied(value):
    value = (value or '').strip()
    return bool(value) and '${' not in value and not any(marker in value.lower() for marker in
                                  ('your_', 'your-', 'replace_me', 'example.com'))


def tool_path(name):
    found = shutil.which(name)
    if found:
        return found
    if name == 'docker':
        for folder in (Path(os.getenv('PROGRAMFILES', '')) / 'Docker/Docker/resources/bin',
                       Path(os.getenv('LOCALAPPDATA', '')) / 'Programs/DockerDesktop/resources/bin'):
            path = folder / 'docker.exe'
            if path.is_file():
                return str(path)
    return None


def command_ok(command):
    try:
        return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=10, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def inspect_setup(root=ROOT, profile='studio', runtime=False):
    checks = []

    def add(label, ok, action):
        checks.append({'label': label, 'ok': bool(ok), 'action': '' if ok else action})

    add('Python', sys.version_info.major == 3 and sys.version_info >= (3, 12),
        'Cài Python 3.12/3.13 rồi chạy lại bộ cài.')
    missing = []
    for module in ('dotenv', 'fastapi', 'uvicorn', 'httpx', 'pydantic', 'PIL',
                   'pwdlib', 'cryptography', 'multipart', 'langgraph', 'google.genai'):
        try:
            if importlib.util.find_spec(module) is None:
                missing.append(module)
        except (ImportError, ValueError):
            missing.append(module)
    add('Thư viện chạy', not missing, 'Chạy scripts/setup_windows.ps1 bằng PowerShell.')
    if 'dotenv' in missing:
        return checks
    from dotenv import dotenv_values

    def read(relative):
        path = root / relative
        add(relative, path.is_file(), 'Chạy bộ cài để tạo cấu hình mẫu; điền khóa tại máy.')
        if not path.is_file():
            return {}
        try:
            # Do not interpolate inherited credentials or print parser diagnostics.
            import io
            from contextlib import redirect_stderr
            with redirect_stderr(io.StringIO()):
                return {k: v or '' for k, v in dotenv_values(path, interpolate=False).items()}
        except (OSError, UnicodeError):
            add(relative + ' đọc được', False, 'Lưu cấu hình bằng UTF-8 và kiểm tra quyền đọc file.')
            return {}

    def require(config, key, location):
        add(location + ': ' + key, supplied(config.get(key)),
            'Điền ' + key + ' trong ' + location + ' theo docs/SETUP_WINDOWS.md.')

    studio = read('.env')
    require(studio, 'GEMINI_API_KEY', '.env')
    if profile != 'studio':
        automation = read('integrations/long-v2/.env')
        for key in ('GEMINI_API_KEY', 'WEBHOOK_V2_TOKEN', 'NOTION_TOKEN', 'NOTION_DATABASE_ID',
                    'NOTION_V2_DATABASE_ID', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID',
                    'TELEGRAM_WEBHOOK_SECRET', 'TELEGRAM_AUTHORIZED_USER_IDS'):
            require(automation, key, 'integrations/long-v2/.env')
        require(studio, 'WEBHOOK_V2_TOKEN', '.env')
        add('WEBHOOK_V2_TOKEN khớp hai file', supplied(studio.get('WEBHOOK_V2_TOKEN')) and
            studio.get('WEBHOOK_V2_TOKEN') == automation.get('WEBHOOK_V2_TOKEN'),
            'Dùng cùng một token cho hai file và Header Auth trong n8n; không thay khóa đang dùng khi cập nhật.')
        target = automation.get('NOTION_V2_DATABASE_ID', '').replace('-', '').lower()
        primary = automation.get('NOTION_DATABASE_ID', '').replace('-', '').lower()
        add('Database thử v2 riêng', supplied(target) and supplied(primary) and target != primary,
            'Dùng database thử v2 khác database v1; cấp quyền cho integration Notion.')
        docker = tool_path('docker')
        add('Docker Compose', docker and command_ok([docker, 'compose', 'version']),
            'Cài Docker Desktop với Compose rồi mở lại PowerShell.')
        add('Docker đang chạy', docker and command_ok([docker, 'info']),
            'Mở Docker Desktop, chờ khởi động xong rồi kiểm tra lại.')
        if profile == 'publishing':
            add('ngrok', tool_path('ngrok'), 'Cài ngrok và đăng nhập tài khoản của bạn.')
            add('Tên miền ngrok đã xác nhận', automation.get('NGROK_DOMAIN_CONFIRMED') == '1',
                'Xác nhận tên miền thuộc tài khoản của bạn trước khi đặt NGROK_DOMAIN_CONFIRMED=1.')
            if not any(name in missing for name in ('httpx', 'cryptography')):
                sys.path.insert(0, str(ROOT))
                from scripts.start_personal import gateway_domain
                try:
                    gateway_domain(automation.get('STUDIO_PUBLIC_URL', ''))
                    domain_ok = True
                except (ValueError, TypeError):
                    domain_ok = False
                add('Tên miền tương thích lệnh mở tunnel', domain_ok,
                    'STUDIO_PUBLIC_URL phải là tên miền HTTPS ngrok miễn phí theo hướng dẫn.')
                sys.path.insert(0, str(ROOT / 'integrations/long-v2/python-service'))
                from app.publishing_setup import configuration
                for item in configuration(automation)['checks']:
                    add(item['label'], item['ok'], item['action'])
    if runtime:
        urls = [('Studio /health', 'http://127.0.0.1:8001/health')]
        if profile != 'studio':
            urls += [('Automation /health', 'http://127.0.0.1:8000/health'),
                     ('n8n', 'http://127.0.0.1:5678/healthz'),
                     ('Gateway /policy', 'http://127.0.0.1:8080/policy')]
        opener = build_opener(ProxyHandler({}), NoRedirects())
        for label, url in urls:
            try:
                with opener.open(url, timeout=3) as response:
                    ok = response.status == 200
            except (OSError, ValueError):
                ok = False
            add(label, ok, 'Khởi động đúng hệ thống hiện có rồi kiểm tra lại.')
    return checks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, default='studio')
    parser.add_argument('--runtime', action='store_true', help='Đọc trạng thái dịch vụ trên localhost.')
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    checks = inspect_setup(profile=args.profile, runtime=args.runtime)
    for item in checks:
        print(('OK' if item['ok'] else 'THIẾU') + ' | ' + item['label'])
        if item['action']:
            print('  ' + item['action'])
    print('Kiểm tra chỉ đọc cấu hình' + (' và dịch vụ localhost.' if args.runtime else '.'))
    print('Chưa xác nhận khóa hợp lệ, workflow đã bật, quyền tài khoản hoặc video đã đăng thật.')
    return 0 if all(item['ok'] for item in checks) else 1


if __name__ == '__main__':
    raise SystemExit(main())
