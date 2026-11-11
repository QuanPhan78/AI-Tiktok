"""Review the exact MP4 handed off for an approved Content Studio revision."""

import hashlib
import json
import os
import re
import secrets

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile

from app import handoff_v2 as handoff
from app import notion_client as nc


router = APIRouter(prefix="/api/v2/content", tags=["Content Studio video review"])
MAX_BYTES = 45 * 1024 * 1024
REVIEWABLE = {"DRAFT", "PENDING_REVIEW", "NEEDS_REVISION", "APPROVED"}
DECISIONS = {"a": "APPROVED", "r": "NEEDS_REVISION"}


def require_secret(name, supplied):
    expected = os.getenv(name, "").strip()
    if not expected:
        raise HTTPException(503, "Chưa cấu hình xác thực duyệt video.")
    if not supplied or not secrets.compare_digest(expected.encode(), supplied.encode()):
        raise HTTPException(403, "Xác thực duyệt video không hợp lệ.")


def require_studio(x_content_token: str = Header(default="")):
    require_secret("WEBHOOK_V2_TOKEN", x_content_token)


def telegram_config():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    users = {x.strip() for x in os.getenv("TELEGRAM_AUTHORIZED_USER_IDS", "").split(",") if x.strip()}
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if (not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token) or not re.fullmatch(r"-?[0-9]+", chat) or
            not users or not all(x.isdecimal() for x in users) or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret)):
        raise HTTPException(503, "Cần cấu hình bot, chat, người duyệt và webhook Telegram trước khi gửi.")
    return token, chat, users


def telegram(token, method, **kwargs):
    try:
        with httpx.Client(timeout=90, trust_env=False) as client:
            response = client.post(f"https://api.telegram.org/bot{token}/{method}", **kwargs)
        body = response.json()
        if response.is_success and body.get("ok") is True:
            return body["result"]
    except (httpx.HTTPError, KeyError, ValueError):
        pass
    raise HTTPException(502, "Telegram chưa xác nhận thao tác.")


def send_video(token, chat, row, path):
    keyboard = {"inline_keyboard": [[
        {"text": "Duyệt video", "callback_data": f"v2|{row['id']}|a"},
        {"text": "Cần sửa", "callback_data": f"v2|{row['id']}|r"},
    ]]}
    caption = f"Video cần duyệt\n{row['request_id']}\nBản prompt r{row['revision']} · MP4 v{row['version']}"
    with path.open("rb") as file:
        result = telegram(token, "sendVideo", files={"video": ("video.mp4", file, "video/mp4")},
                          data={"chat_id": chat, "caption": caption, "reply_markup": json.dumps(keyboard)})
    if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
        raise HTTPException(502, "Telegram chưa trả mã tin nhắn.")
    return result["message_id"]


def ensure_table(db):
    db.execute("""CREATE TABLE IF NOT EXISTS video_reviews(
      id TEXT PRIMARY KEY, request_id TEXT NOT NULL, revision INTEGER NOT NULL, version INTEGER NOT NULL,
      sha256 TEXT NOT NULL, status TEXT NOT NULL, message_id INTEGER, reviewer_id TEXT,
      UNIQUE(request_id, revision, version))""")
    db.commit()


def latest_video(db, request_id):
    return db.execute("SELECT * FROM video_reviews WHERE request_id=? ORDER BY revision DESC, version DESC LIMIT 1",
                      (request_id,)).fetchone()


def latest_receipt(db, request_id, revision):
    row = db.execute("SELECT * FROM receipts WHERE request_id=? AND status='received' ORDER BY revision DESC LIMIT 1",
                     (request_id,)).fetchone()
    if not row or row["revision"] != revision or not row["page_id"]:
        raise HTTPException(409, "Cần bàn giao bản prompt hiện tại trước khi duyệt video.")
    if not handoff.same_database(row["database_id"], handoff.database_id()):
        raise HTTPException(409, "Biên nhận prompt thuộc bảng Notion khác.")
    return row


def page_status(receipt):
    try:
        page = nc.notion.pages.retrieve(page_id=receipt["page_id"])
        status = page.get("properties", {}).get("status", {})
        return (status.get("select") or {}).get("name")
    except Exception as exc:
        raise HTTPException(502, "Không đọc được trạng thái duyệt trên Notion.") from exc


def update_page(receipt, status):
    try:
        nc.notion.pages.update(page_id=receipt["page_id"], properties={"status": {"select": {"name": status}}})
    except Exception as exc:
        raise HTTPException(502, "Chưa cập nhật được trạng thái duyệt trên Notion.") from exc


def response(row):
    keys = ("request_id", "revision", "version", "sha256", "status")
    return {"success": True, "data": {**{key: row[key] for key in keys}, "review_id": row["id"]}}


def save_upload(source, path, expected):
    size = 0
    digest = hashlib.sha256()
    first = source.read(12)
    if len(first) < 12 or first[4:8] != b"ftyp":
        raise HTTPException(400, "Cần tệp MP4 hợp lệ.")
    source.seek(0)
    with path.open("xb") as file:
        while chunk := source.read(256 * 1024):
            size += len(chunk)
            if size > MAX_BYTES:
                raise HTTPException(413, "Tệp MP4 tối đa 45 MB.")
            digest.update(chunk)
            file.write(chunk)
    if not secrets.compare_digest(digest.hexdigest(), expected):
        raise HTTPException(400, "SHA-256 của MP4 không khớp.")


@router.post("/{request_id}/video-review", dependencies=[Depends(require_studio)])
def submit(request_id: str, revision: int = Form(..., ge=1), version: int = Form(..., ge=1),
           sha256: str = Form(..., pattern=r"^[a-f0-9]{64}$"), file: UploadFile = File(...)):
    token, chat, _ = telegram_config()
    temporary = handoff.folder() / (secrets.token_hex(16) + ".upload")
    try:
        save_upload(file.file, temporary, sha256)
        with handoff._lock:
            db = handoff.connect()
            try:
                ensure_table(db)
                receipt = latest_receipt(db, request_id, revision)
                row = latest_video(db, request_id)
                if row and (revision, version) < (row["revision"], row["version"]):
                    raise HTTPException(409, "Video này đã được thay bằng phiên bản mới.")
                if row and (revision, version) == (row["revision"], row["version"]):
                    if row["sha256"] != sha256:
                        raise HTTPException(409, "Phiên bản video đã gắn với tệp khác.")
                    if row["status"] != "DELIVERING":
                        return response(row)
                    review_id = row["id"]
                else:
                    review_id = secrets.token_hex(16)
                    row = None
                if page_status(receipt) not in REVIEWABLE:
                    raise HTTPException(409, "Trang Notion đã sang lập lịch, đăng hoặc ở trạng thái không thể gửi duyệt.")
                path = handoff.folder() / (review_id + ".mp4")
                temporary.replace(path)
                if row is None:
                    db.execute("INSERT INTO video_reviews(id,request_id,revision,version,sha256,status) VALUES(?,?,?,?,?,'DELIVERING')",
                               (review_id, request_id, revision, version, sha256))
                    db.commit()
                    row = latest_video(db, request_id)
                if not row["message_id"]:
                    message_id = send_video(token, chat, row, path)
                    db.execute("UPDATE video_reviews SET message_id=? WHERE id=?", (message_id, review_id))
                    db.commit()
                update_page(receipt, "PENDING_REVIEW")
                db.execute("UPDATE video_reviews SET status='PENDING_REVIEW' WHERE id=?", (review_id,))
                db.commit()
                return response(latest_video(db, request_id))
            finally:
                db.close()
    finally:
        temporary.unlink(missing_ok=True)


@router.get("/{request_id}/video-review", dependencies=[Depends(require_studio)])
def status(request_id: str, revision: int, version: int, sha256: str):
    with handoff._lock:
        db = handoff.connect()
        try:
            ensure_table(db)
            latest_receipt(db, request_id, revision)
            row = latest_video(db, request_id)
            if not row or (revision, version, sha256) != (row["revision"], row["version"], row["sha256"]):
                raise HTTPException(409, "Phiên bản MP4 này không còn là bản đang xét.")
            return response(row)
        finally:
            db.close()


def decide(review_id, action, message_id, reviewer_id):
    with handoff._lock:
        db = handoff.connect()
        try:
            ensure_table(db)
            row = db.execute("SELECT * FROM video_reviews WHERE id=?", (review_id,)).fetchone()
            if not row or row["message_id"] != message_id or latest_video(db, row["request_id"])["id"] != review_id:
                raise HTTPException(409, "Phiên bản video đã cũ hoặc mã tin nhắn không khớp.")
            receipt = latest_receipt(db, row["request_id"], row["revision"])
            wanted = DECISIONS[action]
            if row["status"] == wanted:
                return response(row)
            if row["status"] != "PENDING_REVIEW" or page_status(receipt) not in ("PENDING_REVIEW", wanted):
                raise HTTPException(409, "Video không còn chờ duyệt.")
            update_page(receipt, wanted)
            db.execute("UPDATE video_reviews SET status=?,reviewer_id=? WHERE id=?", (wanted, reviewer_id, review_id))
            db.commit()
            return response(latest_video(db, row["request_id"]))
        finally:
            db.close()


@router.post("/telegram-video-callback")
def telegram_callback(update: dict, x_telegram_bot_api_secret_token: str = Header(default="")):
    require_secret("TELEGRAM_WEBHOOK_SECRET", x_telegram_bot_api_secret_token)
    token, chat, users = telegram_config()
    query = update.get("callback_query") or {}
    message = query.get("message") or {}
    user = str((query.get("from") or {}).get("id", ""))
    if str((message.get("chat") or {}).get("id", "")) != chat or user not in users:
        raise HTTPException(403, "Tài khoản hoặc nhóm này không có quyền duyệt video.")
    match = re.fullmatch(r"v2\|([0-9a-f]{32})\|([ar])", str(query.get("data", "")))
    if not match or not isinstance(message.get("message_id"), int) or not query.get("id"):
        raise HTTPException(400, "Nút duyệt video không hợp lệ.")
    try:
        result = decide(*match.groups(), message["message_id"], user)
        text = "Đã duyệt video." if result["data"]["status"] == "APPROVED" else "Đã yêu cầu sửa video."
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        result = {"success": False, "error": exc.detail}
        text = exc.detail
    try:
        telegram(token, "answerCallbackQuery", json={"callback_query_id": query["id"], "text": text, "show_alert": not result["success"]})
    except HTTPException:
        pass  # The durable decision is already recorded, even if Telegram's toast expired.
    return result
