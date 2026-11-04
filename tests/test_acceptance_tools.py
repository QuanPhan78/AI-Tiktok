import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from tests.studio_fixtures import setup_session, complete
from scripts.acceptance import canonical, compare, preflight


class AcceptanceToolsTests(unittest.TestCase):
    def setUp(self):
        folder = Path(__file__).resolve().parents[1] / "data" / "test-runs"
        folder.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=folder)
        self.addCleanup(self.temp.cleanup)
        store, engine, ai, session = setup_session(self.temp.name)
        self.store = store
        self.product = session["product"]
        self.bundle = complete(store, engine, session)["bundle"]
        digest = hashlib.sha256(canonical(self.bundle)).hexdigest()
        self.receipt = {"success": True, "data": {"request_id": self.bundle["request_id"],
            "revision": self.bundle["revision"], "notion_page_id": "page-test",
            "notion_database_id": "acceptance", "payload_sha256": digest}}
        self.readback = {"success": True, "status": "received", "data": copy.deepcopy(self.bundle),
            "notion_database_id": "acceptance", "payload_sha256": digest}

    def test_full_data_match_does_not_claim_human_video_acceptance(self):
        report = compare(self.bundle, self.receipt, self.readback, "acceptance")
        self.assertTrue(report["technical_checks_passed"])
        self.assertFalse(report["manual_acceptance_complete"])

    def test_missing_scene_and_changed_prompt_are_rejected(self):
        for field in ("scene", "prompt"):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.readback)
                if field == "scene": changed["data"]["scenes"].pop()
                else: changed["data"]["scenes"][0]["prompt_en"] = "cut short"
                with self.assertRaisesRegex(ValueError, "JSON đọc lại"):
                    compare(self.bundle, self.receipt, changed, "acceptance")

    def test_wrong_revision_database_or_digest_are_rejected(self):
        for field, value in (("revision", 0), ("notion_database_id", "production"), ("payload_sha256", "bad")):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.receipt)
                changed["data"][field] = value
                with self.assertRaises(ValueError):
                    compare(self.bundle, changed, self.readback, "acceptance")

    def test_zip_with_changed_reference_photo_is_rejected(self):
        archive = Path(self.temp.name) / "bad-images.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("handoff.json", json.dumps(self.bundle))
            z.writestr("prompts.md", "\n".join(s["prompt_en"] for s in self.bundle["scenes"]))
            z.writestr("product.png", b"changed-reference-photo")
        with self.assertRaisesRegex(ValueError, "Ảnh trong ZIP khác"):
            compare(self.bundle, self.receipt, self.readback, "acceptance", archive)

    def test_preflight_never_contacts_notion_without_a_separate_database(self):
        env = {"NOTION_TOKEN": "test-secret", "NOTION_DATABASE_ID": "existing", "NOTION_V2_DATABASE_ID": "existing"}
        with patch.dict(os.environ, env), patch("scripts.acceptance.urlopen") as remote:
            report = preflight("long")
        self.assertFalse(report["configuration_ready"])
        remote.assert_not_called()
        self.assertNotIn("test-secret", json.dumps(report))

    def test_quan_preflight_detects_missing_remote_configuration(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key", "WEBHOOK_V2_URL": "", "WEBHOOK_V2_TOKEN": ""}):
            report = preflight("quan")
        self.assertFalse(report["configuration_ready"])
        self.assertEqual(len(report["errors"]), 2)
