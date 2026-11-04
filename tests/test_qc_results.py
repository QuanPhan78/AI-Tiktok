import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from studio.models import CTA
from studio.quality import review_fields
from tests.studio_fixtures import setup_session, act, complete


class QualityResultsTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "data" / "test-runs"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.store, self.engine, self.ai, self.session = setup_session(self.temp.name)
        self.sid = self.session["id"]
        s = complete(self.store, self.engine, self.session, stop_at=6)
        self.before = act(self.store, self.engine, self.sid, "generate")

    def approve(self, quality, publishing=None):
        with patch.object(self.ai, "generate", return_value=quality):
            return act(self.store, self.engine, self.sid, "approve", {"publishing": publishing or self.before["draft"]})

    @staticmethod
    def report(score=8, issues=None, warnings=None):
        return {"qc_score": score, "feedback": "Đã kiểm tra nội dung.", "issues": issues or [], "warnings": warnings or []}

    def unchanged_approved(self, result):
        self.assertEqual(result["dialogues"], self.before["dialogues"])
        for step in ("1", "2", "3", "4", "5"):
            self.assertEqual(result["approved"][step], self.before["approved"][step])

    def test_eight_points_with_only_warnings_can_export(self):
        warning = "Kiểm tra tốc độ nói trong clip thật."
        result = self.approve(self.report(warnings=[warning]))
        self.assertEqual(result["step"], 7)
        self.assertIn(warning, result["bundle"]["qc"]["warnings"])
        self.unchanged_approved(result)

    def test_fixed_cta_style_and_length_are_not_blocking(self):
        issues = [{"field": "dialogues.4", "quote": CTA, "message": "Cần sửa câu chốt.", "category": category}
                  for category in ("style", "length")]
        result = self.approve(self.report(issues=issues))
        self.assertEqual(result["step"], 7)
        self.assertEqual(result["quality"]["issues"], [])
        self.assertTrue(result["quality"]["warnings"])
        self.assertEqual(result["bundle"]["scenes"][-1]["dialogue_vi"], CTA)
        self.unchanged_approved(result)

    def test_real_content_issue_has_field_and_quote_and_blocks(self):
        quote = self.before["dialogues"]["2"][:35]
        result = self.approve(self.report(issues=[{"field": "dialogues.2", "quote": quote,
             "message": "Cần xác nhận căn cứ cho câu này.", "category": "content"}]))
        self.assertEqual(result["step"], 6)
        self.assertEqual(result["status"], "needs_changes")
        self.assertEqual(result["validation_details"][0]["label"], "Lời thoại cảnh 2")
        self.assertEqual(result["validation_details"][0]["quote"], quote)
        self.assertNotIn("bundle", result)
        self.unchanged_approved(result)

    def test_hallucinated_quote_cannot_be_accepted(self):
        result = self.approve(self.report(issues=[{"field": "dialogues.2", "quote": "không có câu này trong nội dung",
             "message": "Lỗi giả định", "category": "content"}]))
        self.assertEqual(result["status"], "error")
        self.assertIn("trích đoạn khớp", result["error"])
        self.assertEqual(result["step"], 6)
        self.unchanged_approved(result)

    def test_below_eight_still_blocks_with_visible_reason(self):
        result = self.approve(self.report(score=7, warnings=["Gợi ý cải thiện cách trình bày."]))
        self.assertEqual(result["status"], "needs_changes")
        self.assertIn("7/10", result["validation"][0])
        self.assertEqual(result["step"], 6)
        self.unchanged_approved(result)

    def test_ai_error_preserves_publishing_edits_and_dialogues(self):
        edited = copy.deepcopy(self.before["draft"])
        edited["captions"][0] = "Bản caption người dùng vừa sửa. Bấm giỏ hàng nhé!"
        with patch.object(self.ai, "generate", side_effect=RuntimeError("simulated outage")):
            result = act(self.store, self.engine, self.sid, "approve", {"publishing": edited})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["draft"], edited)
        self.assertNotIn("quality", result)
        self.unchanged_approved(result)

    def test_warning_does_not_bypass_hard_hashtag_validation(self):
        edited = copy.deepcopy(self.before["draft"])
        edited["hashtags"][0] = "#códấu"
        result = self.approve(self.report(warnings=["Đây chỉ là lời nhắc."]), edited)
        self.assertEqual(result["step"], 6)
        self.assertEqual(result["status"], "needs_changes")
        self.assertEqual(result["draft"], edited)
        self.assertNotIn("bundle", result)
        self.unchanged_approved(result)

    def test_plain_text_issue_is_not_silently_treated_as_passed(self):
        result = self.approve(self.report(issues=["Cần xem lại."]))
        self.assertEqual(result["step"], 6)
        self.assertEqual(result["status"], "error")
        self.assertNotIn("bundle", result)

    def test_source_url_and_price_are_not_semantic_ad_copy(self):
        publishing = copy.deepcopy(self.before["draft"])
        url = self.before["product"]["product_link"]
        publishing["pinned_comment"] = "Nội dung cần kiểm tra: " + url
        fields = review_fields(self.before, publishing)
        self.assertNotIn("publishing.overlay_scene4", fields)
        self.assertEqual(fields["publishing.pinned_comment"], "Nội dung cần kiểm tra: ")
        self.assertEqual(publishing["pinned_comment"], "Nội dung cần kiểm tra: " + url)

    def test_claim_outside_source_url_still_blocks(self):
        edited = copy.deepcopy(self.before["draft"])
        edited["pinned_comment"] = "Chữa khỏi bệnh " + self.before["product"]["product_link"]
        result = self.approve(self.report(issues=[{"field": "publishing.pinned_comment", "quote": "Chữa khỏi bệnh",
            "message": "Tuyên bố điều trị chưa có căn cứ.", "category": "content"}]), edited)
        self.assertEqual(result["status"], "needs_changes")
        self.assertEqual(result["validation_details"][0]["quote"], "Chữa khỏi bệnh")
        self.unchanged_approved(result)
