"""Read-only, versioned session chat. Content actions remain in Studio."""
import hashlib
import json
import os
import unicodedata
from datetime import datetime, timedelta, timezone
from google.genai import types
from agents.pipeline import get_client
from knowledge_base.loader import get_policy_rules_summary
from prompts.chat import SYSTEM, STEPS, NOTEBOOK
from studio.ai import error_code
from studio.chat_models import ChatAnswer
from studio.store import Conflict, now


class ChatUnavailable(ValueError):
    pass


def settings():
    model = os.getenv("CHAT_MODEL", "").strip()
    key = os.getenv("GEMINI_API_KEY", "").strip()
    # Bind a manual Free-tier check to this key AND model; never expose either key/hash.
    fingerprint = hashlib.sha256((key + "\0" + model).encode()).hexdigest()
    enabled = (os.getenv("CHAT_AI_ENABLED") == "1" and bool(key and model) and
               os.getenv("CHAT_FREE_TIER_FINGERPRINT", "") == fingerprint)
    try:
        limit = max(1, min(100, int(os.getenv("CHAT_DAILY_LIMIT", "20"))))
    except ValueError:
        limit = 20
    return {"ai_enabled": enabled, "model": model if enabled else None, "daily_limit": limit,
            "reason": "" if enabled else "Gemini chưa bật: cần xác nhận Free tier cho khóa và model đang dùng. Hướng dẫn có sẵn vẫn dùng được."}


def budget_day():
    return datetime.now(timezone(timedelta(hours=7))).date().isoformat()


def next_step(s):
    if s["step"] != 7 or not s.get("bundle"):
        return STEPS[s["step"] - 1]
    revision = s["bundle"]["revision"]
    video = s.get("video") or {}
    handoff = s.get("handoff") or {}
    if video.get("bundle_revision") != revision:
        return STEPS[6]
    state = video.get("status")
    prefix = f"Theo dữ liệu đã lưu: bộ prompt r{revision}, MP4 v{video['version']}. "
    if state == "APPROVED":
        if s.get('content_mode', 'tiktok_shop') == 'ordinary':
            action = "Mở Đăng TikTok, kiểm tra tài khoản, caption, hashtag và giờ đăng. Chỉ gửi khi đã đủ quyền và cấu hình; lượt nghiệm thu chọn Chỉ mình tôi."
        else:
            action = "Đây là Video TikTok Shop, chưa hỗ trợ đăng tự động. Dùng MP4 và nội dung đã duyệt để thao tác trực tiếp trên TikTok."
        return prefix + "Video đã duyệt. " + action + " Không cần tạo lại hoặc gửi duyệt lại nếu không thay nội dung/video. Chưa có bằng chứng bài đã đăng trong dữ liệu này."
    if state == "PENDING_REVIEW":
        return prefix + "Video đang chờ duyệt. Xem tin duyệt trên Telegram rồi bấm Cập nhật trạng thái duyệt ở Bước 7."
    if state == "NEEDS_REVISION":
        return prefix + "Video cần sửa. Xem góp ý duyệt, sửa clip, tải MP4 thay thế và gửi duyệt lại."
    if handoff.get("status") != "received" or handoff.get("revision") != revision:
        return prefix + "Video đã tải lên. Xem hết clip, bấm Lưu nội dung vào Notion cho bản hiện tại, rồi Gửi video để duyệt trên Telegram."
    return prefix + "Video đã tải lên và nội dung đã lưu Notion. Xem hết clip rồi bấm Gửi video để duyệt trên Telegram."


def sources_for(s):
    approved = s.get("approved", {})
    bundle = s.get("bundle") or {}
    char = (approved.get("3") or {}).get("character") or {}
    raw = {
        "session": ("Bước và phiên bản hiện tại", {"step": s["step"], "revision": s["revision"],
                    "bundle_revision": bundle.get("revision"), "status": s["status"], "updated_at": s["updated_at"]}),
        "product": ("Thông tin sản phẩm", {"content_mode": s.get("content_mode", "tiktok_shop"), "approval": "đã duyệt bước 1" if "1" in approved else "chưa duyệt bước 1",
                    **{k: s["product"].get(k) for k in ("name", "uses", "price", "product_link")}}),
        "character": ("Nhân vật và giọng", {k: char.get(k) for k in ("id", "name", "voice", "setting", "outfit")}),
        "plan": ("Kế hoạch cảnh đã duyệt", approved.get("4")),
        "dialogues": ("Lời thoại đã duyệt", s.get("dialogues", {})),
        "draft": ("Bản nháp chưa duyệt", s.get("draft")),
        "quality": ("Kiểm tra nội dung", {k: s.get(k) for k in ("validation", "validation_details", "warnings", "quality")}),
        "publishing": ("Nội dung đăng đã duyệt", approved.get("6")),
        "video": ("Trạng thái MP4 đã lưu", {k: (s.get("video") or {}).get(k) for k in ("version", "bundle_revision", "status", "updated_at")}),
        "handoff": ("Biên nhận Notion đã lưu", {k: (s.get("handoff") or {}).get(k) for k in ("status", "revision")}),
        "guide": ("Hướng dẫn của Content Studio", {"next": next_step(s), "notebook": NOTEBOOK,
                  "audio_mode": s.get("audio_mode"), "scene_order": [x["id"] for x in bundle.get("scenes", [])]}),
        "rules": ("Quy tắc nội dung đang cấu hình", get_policy_rules_summary()),
    }
    result = {}
    for key, (label, value) in raw.items():
        text = json.dumps(value, ensure_ascii=False)
        limit = 3000 if key in ("plan", "dialogues", "draft") else 2000
        result[key] = {"label": label, "excerpt": text[:limit], "truncated": len(text) > limit}
    return result


def guide_answer(s, question):
    q = ''.join(c for c in unicodedata.normalize('NFD', question.lower().replace('đ', 'd')) if unicodedata.category(c) != 'Mn')
    if any(word in q for word in ("trang thai", "duyet chua", "da duyet", "mp4", "tiep theo", "lam gi tiep")):
        answer = f"Bạn đang ở Bước {s['step']}/7. {next_step(s)}"
        if s["step"] == 7:
            answer += " Đây là trạng thái đã lưu; Cập nhật trạng thái duyệt ở Bước 7 mới đồng bộ Telegram."
        refs = ["session", "video", "handoff", "guide"]
    elif any(word in q for word in ("gemini", "notebook", "tao video", "prompt")):
        answer, refs = NOTEBOOK, ["guide", "session"]
    elif any(word in q for word in ("video", "telegram")):
        video = s.get("video") or {}
        label = {"ATTACHED": "đã tải lên, chưa gửi duyệt", "PENDING_REVIEW": "đang chờ duyệt",
                 "APPROVED": "đã duyệt", "NEEDS_REVISION": "cần sửa"}.get(video.get("status"), "chưa có MP4")
        answer = f"Theo trạng thái đã lưu, video {label}."
        if video:
            answer += f" MP4 v{video['version']}, bộ prompt r{video['bundle_revision']}."
        answer += " Đây không phải truy vấn trực tiếp Telegram. Dùng Cập nhật trạng thái duyệt ở Bước 7 để lấy quyết định mới nhất."
        refs = ["video", "guide"]
    elif any(word in q for word in ("loi", "kiem tra", "qc", "canh bao")):
        issues = (s.get("validation") or []) + (s.get("warnings") or [])
        answer = "\n".join(str(x) for x in issues) if issues else "Phiên chưa ghi nhận lỗi hoặc cảnh báo ở bước hiện tại. Điều đó chưa đồng nghĩa video đã đạt kiểm tra."
        answer += "\nXem đúng trường/cảnh được chỉ ra trên web. Lời thoại sửa ở Bước 5; chốt tổng hợp ở Bước 6."
        refs = ["quality", "guide"]
    elif any(word in q for word in ("san pham", "cong dung", "gia bao", "gia hien")):
        p = s["product"]
        answer = f"{p['name']}\nCông dụng người dùng nhập: {p.get('uses', '')}\nGiá nguyên văn: {p.get('price', '')}\n"
        answer += "Thông tin đã duyệt ở Bước 1." if "1" in s.get("approved", {}) else "Thông tin này chưa được duyệt ở Bước 1."
        refs = ["product"]
    else:
        answer = f"Bạn đang ở Bước {s['step']}/7. {next_step(s)}\nChế độ hướng dẫn dùng nội dung có sẵn, chưa phân tích câu hỏi tự do bằng AI. Chọn Gemini nếu muốn trao đổi sâu hơn."
        refs = ["session", "guide"]
    return ChatAnswer(answer=answer[:5000], source_ids=refs)


def generate_answer(context, history, question):
    config = settings()
    if not config["ai_enabled"]:
        raise ChatUnavailable(config["reason"])
    response = get_client().models.generate_content(
        model=config["model"], contents=json.dumps({"sources": context, "history": history, "question": question}, ensure_ascii=False),
        config=types.GenerateContentConfig(system_instruction=SYSTEM, temperature=0.2, max_output_tokens=2048,
            response_mime_type="application/json", response_json_schema=ChatAnswer.model_json_schema(),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            http_options=types.HttpOptions(timeout=30000, retry_options=types.HttpRetryOptions(attempts=1))),
    )
    return ChatAnswer.model_validate_json(response.text)


class Chat:
    def __init__(self, store):
        self.store = store
        with store.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS chat_turns(seq INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id TEXT NOT NULL,message_id TEXT NOT NULL,revision INTEGER NOT NULL,
              mode TEXT NOT NULL,request TEXT NOT NULL,context TEXT NOT NULL,status TEXT NOT NULL,
              reply TEXT,error TEXT,created TEXT NOT NULL,finished TEXT,budget_day TEXT NOT NULL,
              UNIQUE(session_id,message_id));
            CREATE INDEX IF NOT EXISTS chat_session_seq ON chat_turns(session_id,seq);
            CREATE INDEX IF NOT EXISTS chat_budget ON chat_turns(mode,budget_day);
            """)

    def claim(self, sid, request):
        encoded = self.store.dump(request)
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT body FROM sessions WHERE id=?", (sid,)).fetchone()
            if not row:
                raise KeyError(sid)
            existing = db.execute("SELECT * FROM chat_turns WHERE session_id=? AND message_id=?", (sid, request["message_id"])).fetchone()
            if existing:
                if existing["request"] != encoded:
                    raise Conflict("Mã tin nhắn đã dùng cho câu hỏi khác.")
                return False
            s = json.loads(row[0])
            if s["revision"] != request["expected_revision"] or s["status"] == "processing":
                raise Conflict("Phiên đang thay đổi. Đợi xử lý xong rồi mở lại phiên trước khi gửi câu hỏi.")
            if db.execute("SELECT 1 FROM chat_turns WHERE session_id=? AND status='running'", (sid,)).fetchone():
                raise Conflict("Trợ lý đang trả lời một câu hỏi của phiên này.")
            config = settings()
            if request["mode"] == "gemini":
                if not config["ai_enabled"]:
                    raise ChatUnavailable(config["reason"])
                count = db.execute("SELECT COUNT(*) FROM chat_turns WHERE mode='gemini' AND budget_day=?", (budget_day(),)).fetchone()[0]
                if count >= config["daily_limit"]:
                    raise ChatUnavailable("Đã hết số lượt Gemini cho phép trong ứng dụng hôm nay. Bạn vẫn dùng được Hướng dẫn có sẵn.")
            context = {"sources": sources_for(s), "guide": guide_answer(s, request["text"]).model_dump(),
                       "model": config["model"] if request["mode"] == "gemini" else None}
            db.execute("INSERT INTO chat_turns(session_id,message_id,revision,mode,request,context,status,created,budget_day) VALUES(?,?,?,?,?,?,'running',?,?)",
                (sid, request["message_id"], s["revision"], request["mode"], encoded, self.store.dump(context), now(), budget_day()))
        return True

    def finish(self, sid, message_id, reply=None, error=None):
        with self.store.db() as db:
            db.execute("UPDATE chat_turns SET reply=?,error=?,status=?,finished=? WHERE session_id=? AND message_id=? AND status='running'",
                (self.store.dump(reply) if reply else None, error, "error" if error else "done", now(), sid, message_id))

    def execute(self, sid, message_id):
        try:
            with self.store.db() as db:
                row = db.execute("SELECT * FROM chat_turns WHERE session_id=? AND message_id=?", (sid, message_id)).fetchone()
                if not row or row["status"] != "running":
                    return
                previous = db.execute("SELECT request,reply,revision FROM chat_turns WHERE session_id=? AND seq<? AND status='done' ORDER BY seq DESC LIMIT 4", (sid, row["seq"])).fetchall()
            context = json.loads(row["context"])
            history = [{"question": json.loads(p["request"])["text"][:500], "answer": json.loads(p["reply"])["answer"][:1000], "revision": p["revision"]} for p in reversed(previous)]
            if row["mode"] == "gemini" and context["model"] != settings()["model"]:
                raise ChatUnavailable("Cấu hình Gemini đã thay đổi. Hãy gửi câu hỏi mới.")
            answer = (generate_answer(context["sources"], history, json.loads(row["request"])["text"])
                      if row["mode"] == "gemini" else ChatAnswer.model_validate(context["guide"]))
            if any(ref not in context["sources"] for ref in answer.source_ids):
                raise ValueError("Invalid source")
            reply = {"answer": answer.answer, "warnings": answer.warnings,
                     "sources": [{"id": ref, **context["sources"][ref]} for ref in dict.fromkeys(answer.source_ids)],
                     "model": context["model"]}
            self.finish(sid, message_id, reply)
        except Exception as exc:
            error = {429: "Gemini đã báo hết hạn mức hoặc quá nhiều yêu cầu. Hãy chờ rồi thử lại; không tự đổi model.",
                     503: "Gemini đang quá tải. Câu hỏi đã lưu; bạn có thể thử lại sau.",
                     504: "Gemini chưa trả lời kịp. Câu hỏi đã lưu; bạn có thể thử lại sau."}.get(error_code(exc),
                     "Chưa nhận được câu trả lời hợp lệ. Câu hỏi đã lưu, nội dung đã duyệt không thay đổi. Hãy kiểm tra kết nối/cấu hình rồi thử lại.")
            self.finish(sid, message_id, error=error)

    def read(self, sid, before=None):
        s = self.store.get(sid)
        with self.store.db() as db:
            rows = db.execute("SELECT * FROM chat_turns WHERE session_id=? AND seq<? ORDER BY seq DESC LIMIT 51", (sid, before or 9223372036854775807)).fetchall()
            used = db.execute("SELECT COUNT(*) FROM chat_turns WHERE mode='gemini' AND budget_day=?", (budget_day(),)).fetchone()[0]
        more = len(rows) > 50
        rows = rows[:50]
        messages = [{"seq": r["seq"], "message_id": r["message_id"], "revision": r["revision"], "mode": r["mode"],
                     "text": json.loads(r["request"])["text"], "status": r["status"], "reply": json.loads(r["reply"]) if r["reply"] else None,
                     "error": r["error"], "created_at": r["created"], "stale": r["revision"] != s["revision"]} for r in reversed(rows)]
        return {"session_id": sid, "revision": s["revision"], "messages": messages,
                "next_before": rows[-1]["seq"] if more else None, "config": {**settings(), "used_today": used}}

    def recover(self):
        with self.store.db() as db:
            db.execute("UPDATE chat_turns SET status='error',error=?,finished=? WHERE status='running'",
                       ("Trợ lý bị gián đoạn khi máy chủ dừng. Câu hỏi đã lưu; bấm thử lại để gửi lượt mới.", now()))
