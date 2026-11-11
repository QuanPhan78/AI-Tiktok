import copy
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from knowledge_base.validator import validate_script
from studio.ai import Gateway, GenerationError, characters
from studio.links import read_product_link
from studio.models import (Analysis, Situations, Recommendation, Plan, Dialogue,
                           Publishing, Quality, Product, Character, CTA)
from studio.output import build_bundle, character_asset
from studio.quality import review_fields, classify_quality
from studio.video import review_request


def validate_copy(value):
    result = validate_script(value)
    if not result["is_valid"]:
        raise ValueError("Cần sửa nội dung: " + "; ".join(f"{v['field']}: {v['word']}" for v in result["violations"]))


class Studio:
    def __init__(self, store, gateway=None, reader=None):
        self.store = store
        self.gateway = gateway or Gateway()
        self.reader = reader or read_product_link

    def generate(self, kind, s, schema, **extra):
        context = {"product": s["product"], "approved": s["approved"], "dialogues": s["dialogues"], **extra}
        result = self.gateway.generate(kind, context, schema)
        value = schema.model_validate(result).model_dump()
        model = getattr(self.gateway, "last_model", None) or getattr(self.gateway, "model_name", "custom-provider")
        key = kind + ":" + extra["current_scene"]["id"] if kind == "dialogue" else kind
        s.setdefault("models_by_step", {})[key] = model
        s["model_used"] = model
        s["last_ai_attempts"] = copy.deepcopy(getattr(self.gateway, "last_attempts", []))
        return value

    def draft(self, s, data):
        step = s["step"]
        if step == 1:
            page = self.reader(s["product"]["product_link"])
            value = self.generate("analysis", s, Analysis, source_page=page)
            value["link_read"] = {k: v for k, v in page.items() if k != "text"}
        elif step == 2:
            value = self.generate("situations", s, Situations)
        elif step == 3:
            library = characters()
            recommended = self.generate("recommendation", s, Recommendation, library=library)
            value = {**recommended, "character": next(x for x in library if x["id"] == recommended["character_id"]),
                     "audio_mode": "speaking"}
        elif step == 4:
            count = data.get("scene_count", 4)
            if count not in (4, 5):
                raise ValueError("Chọn 4 hoặc 5 cảnh.")
            ids = ["1", "2", "3", "4"] if count == 4 else ["1", "2", "3A", "3B", "4"]
            value = self.generate("plan", s, Plan, required_scene_ids=ids)
            if [x["id"] for x in value["scenes"]] != ids:
                raise ValueError("AI trả số cảnh khác số đã chọn. Hãy thử lại.")
            if any(not scene["shot_en"].strip() for scene in value["scenes"]):
                raise ValueError("AI chưa trả đủ cỡ cảnh, trạng thái đầu và cuối cho từng cảnh. Hãy thử lại.")
        elif step == 5:
            scene = s["approved"]["4"]["scenes"][s["scene_cursor"]]
            value = self.generate("dialogue", s, Dialogue, current_scene=scene)
        elif step == 6:
            value = self.generate("publishing", s, Publishing)
            value["overlay_scene4"] = s["product"]["price"]
            # URL comes from the confirmed product, not from AI synthesis.
            link = s["product"]["product_link"]
            if link not in value["pinned_comment"]:
                value["pinned_comment"] += " " + link
        else:
            raise ValueError("Prompt cuối được lắp từ nội dung đã duyệt, không sinh lại bằng AI.")
        s["draft"] = value
        s["validation"] = []
        s["validation_details"] = []
        s["warnings"] = []
        if step == 6:
            s.pop("quality", None)
        if step == 5:
            words = len(value["text"].split())
            if not 18 <= words <= 24:
                s["warnings"] = [f"Bản nháp có {words} từ, ngoài khoảng gợi ý 18–24. Hãy kiểm tra nhịp đọc khi có clip."]
            if re.search(r"\d", value["text"]):
                s["warnings"].append("Lời thoại chứa chữ số. Hãy kiểm tra cách đọc khi có clip.")

    def approve(self, s, data):
        step = s["step"]
        draft = copy.deepcopy(s.get("draft"))
        if draft is None:
            raise ValueError("Cần tạo hoặc nhập bản nháp trước khi duyệt.")
        if step == 1:
            value = Analysis.model_validate({**{k: draft[k] for k in ("summary", "suggestions", "product_description_en")},
                                             **{k: v for k, v in data.items() if k in Analysis.model_fields}}).model_dump()
            validate_copy({"summary": value["summary"], "suggestions": "\n".join(value["suggestions"])})
            s["approved"]["1"] = value
        elif step == 2:
            if data.get("custom"):
                selected = {"title": data["custom"], "reason": "Tình huống do người dùng chọn", "emotion": "Tự nhiên"}
            else:
                index = data.get("index")
                if type(index) is not int or not 0 <= index < 4:
                    raise ValueError("Chọn một trong bốn tình huống hoặc nhập tình huống riêng.")
                selected = Situations.model_validate(draft).items[index].model_dump()
            validate_copy(selected)
            s["situation_options"] = copy.deepcopy(draft)
            s["approved"]["2"] = selected
        elif step == 3:
            cid = data.get("character_id", draft["character"]["id"])
            if "new_character" in data:
                char = Character.model_validate(data["new_character"]).model_dump()
                if int(char["id"][2:]) < 9 or not char["asset_id"]:
                    raise ValueError("Nhân vật mới phải từ NV9 và có ảnh tham chiếu.")
                if "[PRODUCT]" not in char["consistency_block"]:
                    raise ValueError("Khối nhân vật mới phải có [PRODUCT].")
            else:
                char = next((x for x in characters() if x["id"] == cid), None)
                if not char:
                    raise ValueError("Nhân vật không tồn tại.")
            character_asset(char, self.store)
            mode = data.get("audio_mode", draft.get("audio_mode", "speaking"))
            if mode not in ("speaking", "voiceover"):
                raise ValueError("Chọn nhân vật nói hoặc thuyết minh.")
            s["audio_mode"] = mode
            s["approved"]["3"] = {"character": copy.deepcopy(char), "audio_mode": mode}
        elif step == 4:
            plan = Plan.model_validate(data.get("plan", draft)).model_dump()
            validate_copy({"scenes": [{"visual": x["action_vi"], "idea": x["idea_vi"]} for x in plan["scenes"]]})
            s["approved"]["4"] = plan
            s["scene_cursor"] = 0
            s["dialogues"] = {}
        elif step == 5:
            scene = s["approved"]["4"]["scenes"][s["scene_cursor"]]
            text = Dialogue.model_validate({"text": data.get("text", draft["text"])}).text
            if s["product"]["product_link"] in text or re.search(r"https?://", text):
                raise ValueError("Lời thoại không được chứa link.")
            if s["product"]["price"] in text:
                raise ValueError("Lời thoại không được chứa giá.")
            validate_copy({"voice_over_text": text})
            s["dialogues"][scene["id"]] = text
            s["scene_cursor"] += 1
            scenes = s["approved"]["4"]["scenes"]
            if s["scene_cursor"] < len(scenes) - 1:
                next_id = scenes[s["scene_cursor"]]["id"]
                old = s.get("dialogue_drafts", {}).get(next_id)
                s["draft"] = {"text": old} if old else None
                return
            s["dialogues"]["4"] = CTA
            s["approved"]["5"] = dict(s["dialogues"])
            s["warnings"] = ["Cảnh 4 dùng câu cố định; cần kiểm tra nhịp nói trong clip thật."]
        elif step == 6:
            value = Publishing.model_validate(data.get("publishing", draft)).model_dump()
            s["draft"] = value
            if value["overlay_scene4"] != s["product"]["price"]:
                raise ValueError("Giá hiển thị phải giữ nguyên thông tin đã nhập.")
            fields = review_fields(s, value)
            quality = self.generate("quality", s, Quality, publishing=value,
                                    review_fields=fields, fixed_closing_line=CTA)
            blocking, warnings = classify_quality(quality, fields)
            quality["issues"] = [{k: v for k, v in issue.items() if k != "label"} for issue in blocking]
            quality["warnings"] = warnings
            s["quality"] = quality
            s["warnings"] = warnings
            s["validation_details"] = blocking
            if quality["qc_score"] < 8 or blocking:
                s["validation"] = [f"{issue['label']}: {issue['message']} — “{issue['quote']}”" for issue in blocking]
                if quality["qc_score"] < 8:
                    s["validation"].insert(0, f"Điểm QC {quality['qc_score']:g}/10, cần ít nhất 8. " + quality["feedback"])
                s["status"] = "needs_changes"
                return
            s["approved"]["6"] = value
            try:
                s["bundle"] = build_bundle(s, self.store, s["revision"] + 1)
            except (ValueError, KeyError, OSError) as exc:
                s["approved"].pop("6", None)
                s["validation"] = [str(exc)]
                s["status"] = "needs_changes"
                return
        else:
            raise ValueError("Đã hoàn tất. Bạn có thể xuất gói hoặc gửi sang Long.")
        s["step"] += 1
        s["draft"] = None
        s["validation"] = []
        s["validation_details"] = []

    def revise(self, s, data):
        step = s["step"]
        if step == 7:
            raise ValueError("Quay về bước cần chỉnh trước khi sửa.")
        if step == 1 and "product" in data:
            s["product"] = Product.model_validate(data["product"]).model_dump()
            s["draft"] = None
        elif "draft" in data:
            value = data["draft"]
            schema = {1: Analysis, 2: Situations, 4: Plan, 5: Dialogue, 6: Publishing}.get(step)
            if not schema:
                raise ValueError("Chọn nhân vật trong bước 3 rồi bấm duyệt.")
            extra = {"link_read": s["draft"].get("link_read")} if step == 1 and s.get("draft") else {}
            s["draft"] = {**schema.model_validate(value).model_dump(), **extra}
        else:
            raise ValueError("Không có nội dung chỉnh sửa.")
        s["validation"] = []
        s["validation_details"] = []
        s.pop("quality", None)

    def reopen(self, s, data):
        target = data.get("step")
        if type(target) is not int or not 1 <= target <= min(s["step"], 6):
            raise ValueError("Chỉ quay lại bước hiện tại hoặc bước trước.")
        previous = copy.deepcopy(s["approved"].get(str(target)))
        if target == 2:
            previous = copy.deepcopy(s.get("situation_options"))
        if target <= 4:
            s["dialogues"] = {}
            s["dialogue_drafts"] = {}
            s["scene_cursor"] = 0
        elif target == 5:
            scenes = s["approved"]["4"]["scenes"][:-1]
            ids = [x["id"] for x in scenes]
            sid = data.get("scene_id", ids[0])
            if sid not in ids:
                raise ValueError("Chọn cảnh có lời thoại cần duyệt.")
            s["scene_cursor"] = ids.index(sid)
            s["dialogue_drafts"] = {**s.get("dialogue_drafts", {}), **s["dialogues"]}
            s["dialogues"] = {k: v for k, v in s["dialogues"].items() if k in ids[:s["scene_cursor"]]}
            old = s["dialogue_drafts"].get(sid)
            previous = {"text": old} if old else None
        for key in list(s["approved"]):
            if int(key) >= target:
                del s["approved"][key]
        stages = {"analysis": 1, "situations": 2, "recommendation": 3, "plan": 4,
                  "dialogue": 5, "publishing": 6, "quality": 6}
        for key in list(s.get("models_by_step", {})):
            if stages.get(key.split(":")[0], 7) >= target:
                if target == 5 and key.startswith("dialogue:") and key.split(":")[1] in s["dialogues"]:
                    continue
                del s["models_by_step"][key]
        s.update(step=target, draft=previous, validation=[], validation_details=[], warnings=[], handoff=None)
        s.pop("bundle", None)
        s.pop("quality", None)

    def handoff(self, s):
        if s["step"] != 7 or not s.get("bundle"):
            raise ValueError("Chỉ gửi sau khi hoàn tất bước 7.")
        bundle = s["bundle"]
        # Recheck local assets and deterministic compilation before transmission.
        rebuilt = build_bundle(s, self.store, bundle["revision"])
        if rebuilt != bundle:
            raise ValueError("Đầu ra thay đổi; cần quay lại duyệt tổng hợp.")
        url = os.getenv("WEBHOOK_V2_URL", "http://127.0.0.1:5678/webhook/ai-agent-callback-v2")
        parsed = urlsplit(url)
        local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
        token = os.getenv("WEBHOOK_V2_TOKEN", "").strip()
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("WEBHOOK_V2_URL không hợp lệ; không đặt token trong URL.")
        if not local and (parsed.scheme != "https" or not token):
            raise ValueError("Webhook máy Long phải dùng HTTPS và có WEBHOOK_V2_TOKEN trong .env.")
        headers = {"X-Content-Token": token} if token else {}
        with httpx.Client(timeout=150, trust_env=False, follow_redirects=False) as client:
            response = client.post(url, json=bundle, headers=headers)
            if 300 <= response.status_code < 400:
                raise ValueError("Webhook chuyển hướng; kiểm tra lại URL production v2 của Long.")
            response.raise_for_status()
            result = response.json()
        if result.get("success") is not True:
            raise ValueError("Long chưa xác nhận lưu thành công. Kiểm tra workflow và Notion, sau đó gửi lại.")
        data = result.get("data") or {}
        if data.get("request_id") != bundle["request_id"] or data.get("revision") != bundle["revision"]:
            raise ValueError("Phản hồi bàn giao không khớp mã yêu cầu hoặc phiên bản.")
        encoded = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if data.get("payload_sha256") != hashlib.sha256(encoded).hexdigest():
            raise ValueError("Bản nhận của Long chưa khớp toàn bộ nội dung đã gửi.")
        allowed = ("request_id", "revision", "notion_page_id", "notion_database_id", "payload_sha256", "duplicate")
        s["handoff"] = {"status": "received", **{k: data[k] for k in allowed if k in data}}

    def video_review(self, s, data, method):
        bundle = s.get("bundle") or {}
        handoff = s.get("handoff") or {}
        video = s.get("video") or {}
        if s["step"] != 7 or not video or bundle.get("revision") != video["bundle_revision"]:
            raise ValueError("Cần gắn MP4 cho đúng bản prompt đã chốt.")
        if data.get("version") != video["version"]:
            raise ValueError("Phiên bản MP4 đã thay đổi. Hãy tải lại và xem trước video.")
        if handoff.get("status") != "received" or handoff.get("revision") != video["bundle_revision"]:
            raise ValueError("Cần bàn giao bản prompt hiện tại sang Automation trước khi gửi video.")
        if method == "GET" and video["status"] == "ATTACHED":
            raise ValueError("Hãy bấm Gửi duyệt video trước khi đọc trạng thái.")
        path = self.store.video_path(video)
        if method == "POST" and not path.is_file():
            raise ValueError("Tệp MP4 bị thiếu. Hãy tải lại tệp.")
        receipt = review_request(s, {**video, "path": path}, method)
        video.update(status=receipt["status"], review_id=receipt.get("review_id"))

    def execute(self, sid, request, before):
        try:
            s = copy.deepcopy(before)
            s["status"] = "awaiting_input"
            action = request["action"]
            if action == "generate":
                self.draft(s, request["data"])
            elif action == "approve":
                self.approve(s, request["data"])
            elif action == "revise":
                self.revise(s, request["data"])
            elif action == "reopen":
                self.reopen(s, request["data"])
            elif action == "handoff":
                self.handoff(s)
            elif action == "submit_video_review":
                self.video_review(s, request["data"], "POST")
            elif action == "refresh_video_review":
                self.video_review(s, request["data"], "GET")
            if s.get("status") != "needs_changes":
                s["status"] = "ready" if s["step"] == 7 else "awaiting_approval" if s["draft"] else "awaiting_input"
            s.pop("error", None)
            self.store.finish(sid, request["operation_id"], result=s)
        except Exception as exc:
            # Pydantic errors may contain values; those are user content, never credentials.
            msg = str(exc) if isinstance(exc, ValueError) else "Tác vụ chưa hoàn tất (" + type(exc).__name__ + "). Hãy kiểm tra kết nối/cấu hình và thử lại."
            failed = copy.deepcopy(before)
            if request["action"] == "approve" and before["step"] == 6:
                # The validated publishing edits must survive a QC/API failure.
                failed["draft"] = copy.deepcopy(s.get("draft", before.get("draft")))
                failed.update(validation=[], validation_details=[])
                failed.pop("quality", None)
            if isinstance(exc, GenerationError):
                failed["last_ai_attempts"] = exc.attempts
            self.store.finish(sid, request["operation_id"], result=failed, error=msg[:2500])
