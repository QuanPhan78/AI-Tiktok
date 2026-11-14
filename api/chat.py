from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Query, Request
from api.studio import get_store
from studio.chat import Chat, ChatUnavailable
from studio.chat_models import MessageInput
from studio.store import Conflict

router = APIRouter(prefix="/api/v2/sessions", tags=["Trợ lý theo phiên"])
workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix="chat")


@router.get("/{sid}/chat/messages")
def messages(sid: str, before: int | None = Query(None, ge=1)):
    try:
        return Chat(get_store()).read(sid, before)
    except KeyError:
        raise HTTPException(404, "Không tìm thấy phiên.") from None


@router.post("/{sid}/chat/messages", status_code=202)
def send(sid: str, message: MessageInput, request: Request):
    origin = request.headers.get("origin")
    if origin and origin not in {"http://127.0.0.1:8001", "http://localhost:8001", str(request.base_url).rstrip("/")}:
        raise HTTPException(403, "Gửi câu hỏi từ trang Content Studio đang mở.")
    chat = Chat(get_store())
    body = message.model_dump(mode="json")
    try:
        claimed = chat.claim(sid, body)
        if claimed:
            try:
                workers.submit(chat.execute, sid, body["message_id"])
            except Exception:
                chat.finish(sid, body["message_id"], error="Không khởi tạo được tác vụ chat. Hãy thử lại.")
        return chat.read(sid)
    except KeyError:
        raise HTTPException(404, "Không tìm thấy phiên.") from None
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from None
    except ChatUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
