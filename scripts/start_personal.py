"""Start the existing personal Docker project; optionally open its gateway through ngrok."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'integrations/long-v2'


def gateway_domain(value):
    url = urlsplit(value)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password or
            url.port or url.query or url.fragment or url.path not in ('', '/') or
            not url.hostname.endswith(('.ngrok-free.dev', '.ngrok-free.app'))):
        raise ValueError('STUDIO_PUBLIC_URL phải là tên miền phát triển ngrok miễn phí của tài khoản bạn.')
    return 'https://' + url.hostname


def tunnel_target(value):
    u = urlsplit(value)
    return u.scheme == 'http' and u.hostname in ('localhost', '127.0.0.1') and u.port == 8080


def find_tool(name):
    found = shutil.which(name)
    if found:
        return found
    paths = {
        'docker': [Path(os.getenv('LOCALAPPDATA', '')) / 'Programs/DockerDesktop/resources/bin/docker.exe',
                   Path(os.getenv('PROGRAMFILES', '')) / 'Docker/Docker/resources/bin/docker.exe'],
        'ngrok': [Path(sys.executable).parent / 'ngrok.exe', Path(os.getenv('LOCALAPPDATA', '')) / 'Programs/Python/Python314/Scripts/ngrok.exe'],
    }
    for path in paths.get(name, []):
        if path.is_file():
            return str(path)
    raise ValueError('Chưa tìm thấy ' + name + '. Cài công cụ hoặc thêm vào PATH rồi chạy lại.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tunnel', action='store_true')
    parser.add_argument('--project', default='sejoy-stage1')
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    envfile = PACKAGE / '.env'
    if not envfile.is_file():
        raise ValueError('Tạo integrations/long-v2/.env theo file mẫu trước.')
    config = dotenv_values(envfile, interpolate=False)
    # No config/secret contents in command output. Never change existing keys or data.
    command = [find_tool('docker'), 'compose', '--env-file', str(envfile), '-p', args.project,
               '-f', 'docker-compose.yml', '-f', 'docker-compose.public.yml']
    subprocess.run(command + ['up', '-d', '--build'], cwd=PACKAGE, check=True)
    subprocess.run(command + ['exec', '-T', 'studio-public-gateway', 'nginx', '-s', 'reload'], cwd=PACKAGE, check=True)
    print('Mở Content Studio: http://127.0.0.1:8001/app (không cần tài khoản Studio).')
    if not args.tunnel:
        print('Chưa mở kết nối ngoài máy. Dùng --tunnel sau khi xác nhận tên miền ngrok của bạn.')
        return 0
    if config.get('NGROK_DOMAIN_CONFIRMED') != '1':
        raise ValueError('Đăng nhập ngrok, xác nhận tên miền trong tài khoản và đặt NGROK_DOMAIN_CONFIRMED=1. Chưa mở tunnel.')
    domain = gateway_domain(config.get('STUDIO_PUBLIC_URL') or '')
    with httpx.Client(timeout=3, trust_env=False) as client:
        try:
            tunnels = client.get('http://127.0.0.1:4040/api/tunnels').json()['tunnels']
        except (httpx.HTTPError, ValueError, KeyError):
            tunnels = []
    if tunnels:
        if any(t.get('public_url') == domain and tunnel_target(t.get('config', {}).get('addr', '')) for t in tunnels):
            print('Tunnel hiện có đang trỏ đúng gateway 8080; không mở thêm.')
            return 0
        raise ValueError('Đã có tunnel khác. Kiểm tra và dừng tunnel đó trước, tránh mở hai hệ thống.')
    process_env = dict(os.environ)
    if config.get('NGROK_AUTHTOKEN'):
        process_env['NGROK_AUTHTOKEN'] = config['NGROK_AUTHTOKEN']
    logs = ROOT / 'data/runtime'
    logs.mkdir(parents=True, exist_ok=True)
    log = (logs / 'ngrok.log').open('ab')
    process = subprocess.Popen([find_tool('ngrok'), 'http', '--url=' + domain, '--inspect=false',
                                'http://127.0.0.1:8080'], env=process_env, stdout=log, stderr=log,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    log.close()
    (logs / 'ngrok-process.json').write_text(json.dumps({'pid': process.pid, 'domain': domain}), encoding='utf-8')
    print('Đã khởi động ngrok cho gateway 8080. Xem trạng thái kết nối trên Studio; chưa xác nhận Telegram/TikTok hoạt động.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(str(exc) if isinstance(exc, ValueError) else 'Docker chưa khởi động xong. Mở Docker Desktop rồi thử lại.')
        raise SystemExit(1)
