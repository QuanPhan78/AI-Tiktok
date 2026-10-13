"""
RUN_SERVER.PY
=============
Chay 1 lenh nay la xong tat ca:
  - Khoi dong FastAPI server tren cong 8000
  - Tao duong ham Ngrok de Long goi tu may khac

Cach dung:
  python run_server.py
"""

import os
import sys
import time
import threading
import uvicorn
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

PORT = 8000


def start_ngrok():
    """Tao ngrok tunnel va in URL ra man hinh."""
    try:
        from pyngrok import ngrok, conf

        # Neu co NGROK_AUTH_TOKEN thi dung, khong thi dung free tier
        auth_token = os.getenv("NGROK_AUTH_TOKEN")
        if auth_token:
            conf.get_default().auth_token = auth_token

        # Cho server khoi dong truoc
        time.sleep(3)

        tunnel = ngrok.connect(PORT, "http")
        public_url = tunnel.public_url

        print()
        print("=" * 60)
        print("NGROK TUNNEL DA SAN SANG!")
        print("=" * 60)
        print(f"  Local URL : http://localhost:{PORT}")
        print(f"  Public URL: {public_url}")
        print()
        print("GUI URL NAY CHO LONG DE TEST:")
        print(f"  Health check : {public_url}/health")
        print(f"  Generate API : POST {public_url}/generate")
        print(f"  API Docs     : {public_url}/docs")
        print()
        print("Nhan Ctrl+C de dung server.")
        print("=" * 60)

    except ImportError:
        print("Chua cai pyngrok. Chay: pip install pyngrok")
    except Exception as e:
        print(f"Khong the khoi dong ngrok: {e}")
        print(f"Server van chay tai: http://localhost:{PORT}")


if __name__ == "__main__":
    print("=" * 60)
    print("TIKTOK AI AGENT SERVER")
    print("=" * 60)
    print(f"Dang khoi dong FastAPI tren cong {PORT}...")
    print(f"API Docs: http://localhost:{PORT}/docs")

    # Chay ngrok trong thread rieng de khong block server
    ngrok_thread = threading.Thread(target=start_ngrok, daemon=True)
    ngrok_thread.start()

    # Khoi dong server chinh
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level="warning",  # Giam noise log
    )
