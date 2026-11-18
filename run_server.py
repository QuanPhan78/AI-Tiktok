"""
RUN_SERVER.PY
=============
Chay 1 lenh nay la xong tat ca:
  - Khoi dong FastAPI va Content Studio tren cong 8001
  - Tunnel chi di qua gateway 8080 bang scripts/start_personal.py --tunnel

Cach dung:
  python run_server.py
"""

import os
import uvicorn
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

PORT = int(os.getenv("PORT", "8001"))


def start_ngrok():
    """Tao ngrok tunnel va in URL ra man hinh."""
    print("Dùng scripts/start_personal.py --tunnel để mở gateway 8080. Không mở web chỉnh sửa qua tunnel.")


if __name__ == "__main__":
    print("=" * 60)
    print("TIKTOK AI AGENT SERVER")
    print("=" * 60)
    print(f"Dang khoi dong FastAPI tren cong {PORT}...")
    print(f"API Docs: http://localhost:{PORT}/docs")

    # Chay ngrok trong thread rieng de khong block server
    if os.getenv("ENABLE_NGROK", "0") == "1":
        start_ngrok()

    # Khoi dong server chinh
    uvicorn.run(
        "api.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=PORT,
        reload=False,
        log_level="warning",  # Giam noise log
    )
