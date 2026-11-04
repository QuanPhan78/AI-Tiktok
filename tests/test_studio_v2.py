import copy
import io
import json
import tempfile
import time
import unittest
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from contracts.handoff_v2 import HandoffV2
from studio.models import CTA
from studio.store import Store, Conflict
from studio.output import build_bundle
from tests.studio_fixtures import setup_session, act, complete


class StudioV2Tests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / "data" / "test-runs"
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.addCleanup(self.temp.cleanup)
        self.store, self.engine, self.ai, self.s = setup_session(self.temp.name)
        self.sid = self.s["id"]

    def test_four_and_five_scene_roundtrip_and_fixed_cta(self):
        for count in (4, 5):
            with self.subTest(count=count):
                s = self.store.create(self.s["product"])
                done = complete(self.store, self.engine, s, count)
                bundle = done["bundle"]
                self.assertEqual(done["status"], "ready")
                self.assertEqual(len(bundle["scenes"]), count)
                self.assertTrue(all(x["duration_seconds"] == 8 for x in bundle["scenes"]))
                self.assertEqual(bundle["scenes"][-1]["dialogue_vi"], CTA)
                self.assertEqual(bundle["scenes"][-1]["overlay_text"], self.s["product"]["price"])
                self.assertEqual(bundle, HandoffV2.model_validate_json(json.dumps(bundle)).model_dump())
                self.assertEqual(bundle["metadata"]["model_used"], "fake-test")
                self.assertEqual(bundle["metadata"]["models_by_step"]["dialogue:1"], "fake-test")

    def test_cannot_approve_without_draft_or_export_early(self):
        out = act(self.store, self.engine, self.sid, "approve", {"step": 7})
        self.assertEqual(out["step"], 1)
        self.assertEqual(out["status"], "error")
        from api.main import app
        with patch("api.studio.get_store", return_value=self.store):
            client = TestClient(app)
            self.assertEqual(client.get(f"/api/v2/sessions/{self.sid}/export/json").status_code, 409)

    def test_operation_id_and_revision_guard_before_ai(self):
        req = {"revision": 0, "operation_id": "same", "action": "generate", "data": {}}
        before, claimed = self.store.claim(self.sid, req)
        self.assertTrue(claimed)
        self.assertFalse(self.store.claim(self.sid, req)[1])
        with self.assertRaises(Conflict):
            self.store.claim(self.sid, {**req, "operation_id": "other", "revision": 1})
        self.engine.execute(self.sid, req, before)
        self.assertFalse(self.store.claim(self.sid, req)[1])
        self.assertEqual(self.ai.calls, ["analysis"])
        with self.assertRaises(Conflict):
            self.store.claim(self.sid, {**req, "operation_id": "new"})
        with self.assertRaises(Conflict):
            self.store.claim(self.sid, {**req, "data": {"modified": True}})

    def test_resume_after_restart_and_interruption_preserves_approvals(self):
        s = complete(self.store, self.engine, self.s, stop_at=4)
        req = {"revision": s["revision"], "operation_id": "interrupted", "action": "generate", "data": {}}
        self.store.claim(self.sid, req)
        recovered = Store(self.store.path)
        recovered.recover()
        current = recovered.get(self.sid)
        self.assertEqual(current["approved"], s["approved"])
        self.assertEqual(current["status"], "error")
        self.assertIn("gián đoạn", current["error"])
        self.assertGreater(current["revision"], s["revision"])

    def test_reopening_invalidates_dependents_and_keeps_dialogue_drafts(self):
        done = complete(self.store, self.engine, self.s)
        original = copy.deepcopy(done["dialogues"])
        changed = act(self.store, self.engine, self.sid, "reopen", {"step": 5, "scene_id": "2"})
        self.assertEqual(changed["dialogues"], {"1": original["1"]})
        self.assertEqual(changed["draft"]["text"], original["2"])
        self.assertNotIn("bundle", changed)
        self.assertNotIn("6", changed["approved"])
        changed = act(self.store, self.engine, self.sid, "approve", {"text": "Thế là mình sắp bút vào hộp để có thêm khoảng trống trên bàn, lúc cần dùng cũng dễ tìm hơn."})
        self.assertEqual(changed["draft"]["text"], original["3"])
        act(self.store, self.engine, self.sid, "reopen", {"step": 2})
        self.assertEqual(set(self.store.get(self.sid)["approved"]), {"1"})
        self.assertEqual(self.store.get(self.sid)["dialogues"], {})
        reopened = self.store.get(self.sid)
        self.assertEqual(len(reopened["draft"]["items"]), 4)
        out = act(self.store, self.engine, self.sid, "approve", {"index": 1})
        self.assertEqual(out["step"], 3)
        self.assertEqual(out["approved"]["2"], reopened["draft"]["items"][1])

    def test_ai_failure_does_not_erase_approved_data(self):
        s = complete(self.store, self.engine, self.s, stop_at=4)
        self.ai.fail = True
        out = act(self.store, self.engine, self.sid, "generate")
        self.assertEqual(out["approved"], s["approved"])
        self.assertEqual(out["status"], "error")

    def test_safe_attempt_trace_survives_ai_failure(self):
        from studio.ai import GenerationError
        trace = [{"model": "gemini-test", "http_code": 503, "status": "error"}]
        with patch.object(self.ai, "generate", side_effect=GenerationError("AI tạm lỗi", trace)):
            out = act(self.store, self.engine, self.sid, "generate")
        self.assertEqual(out["last_ai_attempts"], trace)
        self.assertEqual(out["approved"], {})

    def test_existing_v2_bundle_without_model_trace_can_still_be_exported(self):
        from studio.output import build_bundle
        done = complete(self.store, self.engine, self.s)
        done.pop("models_by_step", None)
        done.pop("model_used", None)
        done["bundle"]["metadata"].pop("models_by_step", None)
        done["bundle"]["metadata"]["model_used"] = "configured"
        self.assertEqual(build_bundle(done, self.store, done["bundle"]["revision"]), done["bundle"])

    def test_gateway_reports_quota_error_without_remote_secret(self):
        from studio.ai import Gateway
        from studio.models import Analysis
        from types import SimpleNamespace
        class RemoteError(Exception):
            code = 429
        def unavailable(**kwargs):
            raise RemoteError("secret-value-must-not-leak")
        client = SimpleNamespace(models=SimpleNamespace(generate_content=unavailable))
        with patch("studio.ai.get_client", return_value=client), patch("studio.ai.time.sleep"):
            with self.assertRaises(ValueError) as result:
                Gateway().generate("analysis", {}, Analysis)
        self.assertIn("hạn mức", str(result.exception))
        self.assertNotIn("secret-value", str(result.exception))

    def test_low_qc_does_not_rewrite_dialogue_and_can_retry(self):
        s = complete(self.store, self.engine, self.s, stop_at=6)
        original = copy.deepcopy(s["dialogues"])
        act(self.store, self.engine, self.sid, "generate")
        self.ai.bad_quality = True
        out = act(self.store, self.engine, self.sid, "approve")
        self.assertEqual(out["status"], "needs_changes")
        self.assertEqual(out["step"], 6)
        self.assertEqual(out["dialogues"], original)
        self.ai.bad_quality = False
        out = act(self.store, self.engine, self.sid, "approve")
        self.assertEqual(out["status"], "ready")
        self.assertEqual(out["dialogues"], original)

    def test_missing_image_or_invalid_copy_blocks_finalization(self):
        s = complete(self.store, self.engine, self.s, stop_at=6)
        act(self.store, self.engine, self.sid, "generate")
        Path(self.store.asset(self.s["product"]["asset_id"])["path"]).unlink()
        out = act(self.store, self.engine, self.sid, "approve")
        self.assertEqual(out["status"], "needs_changes")
        self.assertEqual(out["step"], 6)
        self.assertNotIn("bundle", out)

    def test_voiceover_omits_spoken_line_in_prompt(self):
        done = complete(self.store, self.engine, self.s, mode="voiceover")
        for scene in done["bundle"]["scenes"]:
            self.assertNotIn('(b) "', scene["prompt_en"])
            self.assertIn("No dialogue, no voice-over", scene["prompt_en"])
            self.assertTrue(scene["dialogue_vi"])

    def test_custom_character_snapshot_and_reopen_keep_audio_mode(self):
        s = complete(self.store, self.engine, self.s, stop_at=3)
        s = act(self.store, self.engine, self.sid, "generate")
        custom = copy.deepcopy(s["draft"]["character"])
        custom.update(id="NV9", name="Nhân vật kiểm thử", image_filename="", asset_id=self.s["product"]["asset_id"])
        s = act(self.store, self.engine, self.sid, "approve", {"new_character": custom, "audio_mode": "voiceover"})
        self.assertEqual(s["approved"]["3"]["character"], custom)
        done = complete(self.store, self.engine, s, mode="voiceover")
        self.assertEqual(done["bundle"]["character"]["image"]["id"], custom["asset_id"])
        s = act(self.store, self.engine, self.sid, "reopen", {"step": 3})
        self.assertEqual(s["draft"]["character"], custom)
        self.assertEqual(s["draft"]["audio_mode"], "voiceover")

    def test_missing_product_image_and_late_caption_violation_show_errors(self):
        s = complete(self.store, self.engine, self.s)
        changed = copy.deepcopy(s)
        changed["product"]["asset_id"] = None
        with self.assertRaisesRegex(ValueError, "Thiếu ảnh sản phẩm"):
            build_bundle(changed, self.store, 1)
        changed = copy.deepcopy(s)
        changed["approved"]["6"]["captions"][2] = "Chữa khỏi hoàn toàn. Bấm giỏ hàng nhé!"
        with self.assertRaisesRegex(ValueError, "Nội dung cần sửa"):
            build_bundle(changed, self.store, 1)

    def test_bundle_rejects_dialogue_change_price_url_and_hashtag(self):
        bundle = complete(self.store, self.engine, self.s)["bundle"]
        for edit in ("dialogue", "price", "url", "hashtag", "order"):
            with self.subTest(edit=edit):
                b = copy.deepcopy(bundle)
                if edit == "dialogue": b["scenes"][0]["dialogue_vi"] += " Thay đổi."
                if edit == "price": b["scenes"][0]["prompt_en"] += b["product"]["price"]
                if edit == "url": b["scenes"][0]["prompt_en"] += " https://example.com"
                if edit == "hashtag": b["publishing"]["hashtags"][0] = "#códấu"
                if edit == "order": b["scenes"][1]["order"] = 4
                with self.assertRaises(ValueError): HandoffV2.model_validate(b)

    def test_ui_and_export_include_exact_images_and_full_prompts(self):
        done = complete(self.store, self.engine, self.s)
        from api.main import app
        with patch("api.studio.get_store", return_value=self.store):
            client = TestClient(app)
            self.assertEqual(client.get("/app").status_code, 200)
            self.assertEqual(client.get("/static/studio.js").status_code, 200)
            archive = client.get(f"/api/v2/sessions/{self.sid}/export/zip")
            self.assertEqual(archive.status_code, 200, archive.text if archive.status_code != 200 else "")
            with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
                self.assertEqual(json.loads(z.read("handoff.json")), done["bundle"])
                self.assertIn("product.png", z.namelist())
                self.assertIn("character.png", z.namelist())
                self.assertIn(done["bundle"]["scenes"][0]["prompt_en"], z.read("prompts.md").decode())

    def test_upload_validation_and_api_async_revision(self):
        from api.main import app
        with patch("api.studio.get_store", return_value=self.store), patch("api.studio.get_studio", return_value=self.engine):
            client = TestClient(app)
            r = client.post("/api/v2/assets", files={"file": ("bad.png", b"not an image", "image/png")})
            self.assertEqual(r.status_code, 400)
            req = {"revision": 0, "operation_id": "api-operation", "action": "generate", "data": {}}
            r = client.post(f"/api/v2/sessions/{self.sid}/actions", json=req)
            self.assertEqual(r.status_code, 202)
            for _ in range(100):
                if self.store.get(self.sid)["status"] != "processing": break
                time.sleep(.02)
            self.assertEqual(self.store.get(self.sid)["status"], "awaiting_approval")
            self.assertEqual(client.post(f"/api/v2/sessions/{self.sid}/actions", json=req).status_code, 202)
            self.assertEqual(self.ai.calls, ["analysis"])
            self.assertEqual(client.post(f"/api/v2/sessions/{self.sid}/actions", json={**req,"operation_id":"stale"}).status_code, 409)


if __name__ == "__main__":
    unittest.main()
