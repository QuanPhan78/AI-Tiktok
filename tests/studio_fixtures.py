"""Explicitly synthetic inputs: these are not a real product acceptance record."""
import hashlib
import json
import uuid
from pathlib import Path
from PIL import Image
from studio.store import Store
from studio.service import Studio
from studio.models import CTA


class FakeGateway:
    model_name = "fake-test"
    def __init__(self):
        self.calls = []
        self.fail = False
        self.bad_quality = False

    def generate(self, kind, context, schema):
        self.calls.append(kind)
        if self.fail:
            raise RuntimeError("Simulated AI failure")
        if kind == "analysis":
            return {"summary": "Hộp đựng bút cho góc bàn gọn gàng.", "suggestions": [], "product_description_en": "a simple pen holder"}
        if kind == "situations":
            return {"items": [{"title": f"Sắp xếp góc bàn {i}", "reason": "Muốn tìm bút dễ hơn", "emotion": "Nhẹ nhàng"} for i in range(4)]}
        if kind == "recommendation":
            return {"character_id": "NV5", "backup_id": "NV1", "reason": "Bối cảnh góc làm việc phù hợp."}
        if kind == "plan":
            return {"style_vi": "Bối cảnh bàn làm việc, trang phục nhân vật giữ nguyên.", "lighting_en": "soft natural daylight",
                    "scenes": [{"id": sid, "part": "Hoàn cảnh" if sid == "1" else "Giới thiệu" if sid == "2" else "Chốt đơn" if sid == "4" else "Công dụng",
                                "action_vi": "Nhân vật sắp xếp bút trên bàn." if sid != "4" else "Nhân vật mỉm cười nhẹ.",
                                "idea_vi": "Giữ góc bàn ngăn nắp.",
                                "direction_en": "The character stands at the desk, gently arranges pens, filmed with a stable medium smartphone shot in natural realism. Quiet room sounds. Stable pose for the first and last half second.",
                                "shot_en": "Steady medium shot",
                                "start_en": "The character stands next to the desk.",
                                "end_en": "The character keeps a hand on the desk.",
                                "product_visible": sid != "1"} for sid in context["required_scene_ids"]]}
        if kind == "dialogue":
            return {"text": "Mình muốn góc bàn gọn hơn nên thử sắp xếp lại bút, nhờ vậy việc tìm đồ cũng thuận tiện hơn mỗi ngày."}
        if kind == "publishing":
            return {"slogans": ["Góc bàn gọn gàng", "Bút có chỗ riêng", "Gọn hơn mỗi ngày", "Nhẹ nhàng sắp xếp", "Một góc nhỏ ngăn nắp"],
                    "captions": [f"Góc bàn của mình{' nè' * i}. Bấm giỏ hàng nhé!" for i in range(3)],
                    "hashtags": ["#hopdungbut", "#but", "#gocban", "#ngannap", "#sapxep", "#vanphong", "#muasam", "#review", "#tiktokshop"],
                    "pinned_comment": "Tham khảo ở giỏ hàng: " + context["product"]["product_link"],
                    "overlay_scene2": "Hộp đựng bút", "overlay_scene4": context["product"]["price"], "selected_caption": 0}
        if kind == "quality":
            return {"qc_score": 5 if self.bad_quality else 9, "feedback": "Cần kiểm tra" if self.bad_quality else "Nội dung phù hợp dữ liệu đã duyệt.",
                    "issues": [{"field": "dialogues.2", "quote": context["dialogues"]["2"],
                                "message": "Cảnh 2 cần xem lại", "category": "content"}] if self.bad_quality else [],
                    "warnings": []}
        raise AssertionError(kind)


def setup_session(path, with_image=True):
    store = Store(Path(path) / "studio.sqlite3")
    gateway = FakeGateway()
    engine = Studio(store, gateway, lambda url: {"status": "unavailable", "message": "Không đọc link trong test.", "text": ""})
    asset_id = None
    if with_image:
        image = Path(path) / "synthetic-product.png"
        Image.new("RGB", (32, 32), "white").save(image)
        raw = image.read_bytes()
        asset_id = str(uuid.uuid4())
        store.save_asset({"id": asset_id, "filename": image.name, "path": str(image), "size": len(raw),
                          "sha256": hashlib.sha256(raw).hexdigest(), "media_type": "image/png"})
    session = store.create({"name": "Hộp đựng bút (dữ liệu kiểm thử)", "uses": "Đựng bút trên bàn", "price": "59.000 đồng",
                            "product_link": "https://example.com/test-product", "asset_id": asset_id})
    return store, engine, gateway, session


def act(store, engine, sid, action, data=None, opid=None):
    s = store.get(sid)
    req = {"revision": s["revision"], "operation_id": opid or str(uuid.uuid4()), "action": action, "data": data or {}}
    before, claimed = store.claim(sid, req)
    if claimed:
        engine.execute(sid, req, before)
    return store.get(sid)


def complete(store, engine, s, count=4, mode="speaking", stop_at=7):
    sid = s["id"]
    while (s := store.get(sid))["step"] < stop_at:
        step = s["step"]
        if not s.get("draft"):
            s = act(store, engine, sid, "generate", {"scene_count": count} if step == 4 else {})
            if s["status"] == "error":
                raise AssertionError(s["error"])
        data = {"index": 0} if step == 2 else {"audio_mode": mode} if step == 3 else {}
        s = act(store, engine, sid, "approve", data)
        if s["status"] in ("error", "needs_changes"):
            raise AssertionError(s.get("error", s.get("validation")))
    return s
