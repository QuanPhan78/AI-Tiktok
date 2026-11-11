import asyncio
import hashlib
import importlib
import io
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from api import studio as studio_api
from contracts.handoff_v2 import HandoffV2
from studio.output import build_bundle
from studio.video import save_mp4
from tests.studio_fixtures import act, complete, setup_session
from tests.test_handoff_v2 import FakeNotion, hv


review = importlib.import_module("app.video_review_v2")


def box(kind, content):
    return struct.pack(">I4s", len(content) + 8, kind) + content


def mp4_structure(payload=b"example"):
    handler = box(b"hdlr", b"\x00" * 8 + b"vide")
    return (box(b"ftyp", b"isom\x00\x00\x00\x00") + box(b"mdat", payload) +
            box(b"moov", box(b"trak", box(b"mdia", handler))))


class VideoReviewTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / "data" / "test-runs"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = self.enterContext(tempfile.TemporaryDirectory(dir=root))
        self.store, self.engine, _, initial = setup_session(self.temp)
        self.session = complete(self.store, self.engine, initial)
        self.bundle = self.session["bundle"]
        self.sid = self.session["id"]
        self.req = self.bundle["request_id"]
        self.rev = self.bundle["revision"]
        self.local = FastAPI()
        self.local.include_router(studio_api.router)
        self.enterContext(patch.object(studio_api, "get_store", return_value=self.store))

        self.notion = FakeNotion()
        self.notion.pages.retrieve = lambda page_id: self.notion.page_data[page_id]
        self.enterContext(patch.object(hv.nc, "notion", self.notion))
        self.enterContext(patch.dict(os.environ, {
            "HANDOFF_DATA_DIR": str(Path(self.temp) / "automation"), "NOTION_V2_DATABASE_ID": "synthetic-db",
            "CONTENT_V2_ACCEPTANCE_MODE": "0", "WEBHOOK_V2_TOKEN": "test-content",
            "TELEGRAM_BOT_TOKEN": "12345:fakebot", "TELEGRAM_CHAT_ID": "-12345",
            "TELEGRAM_AUTHORIZED_USER_IDS": "1212", "TELEGRAM_WEBHOOK_SECRET": "test-callback",
        }))
        self.page_id = hv.receive(HandoffV2.model_validate(self.bundle))["data"]["notion_page_id"]
        self.long = FastAPI()
        self.long.include_router(review.router)
        self.video_url = f"/api/v2/content/{self.req}/video-review"
        self.sent = []
        self.enterContext(patch.object(review, "telegram", side_effect=self.mock_telegram))

    def mock_telegram(self, token, method, **kwargs):
        if method == "sendVideo":
            self.sent.append(kwargs["files"]["video"][1].read())
            return {"message_id": len(self.sent)}
        return True

    def request(self, app, method, url, **kwargs):
        async def call():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                return await client.request(method, url, **kwargs)

        return asyncio.run(call())

    def page_status(self):
        return self.notion.page_data[self.page_id]["properties"]["status"]["select"]["name"]

    def upload(self, revision, raw):
        return self.request(self.local, "POST", f"/api/v2/sessions/{self.sid}/videos",
                            data={"revision": revision}, files={"file": ("sample.mp4", raw, "video/mp4")})

    def send(self, version, raw, digest=None, auth="test-content"):
        return self.request(self.long, "POST", self.video_url, headers={"X-Content-Token": auth},
                            data={"revision": self.rev, "version": version, "sha256": digest or hashlib.sha256(raw).hexdigest()},
                            files={"file": ("sample.mp4", raw, "video/mp4")})

    def click(self, review_id, message, decision="a", user=1212, secret="test-callback"):
        return self.request(self.long, "POST", "/api/v2/content/telegram-video-callback",
                            headers={"X-Telegram-Bot-Api-Secret-Token": secret}, json={"callback_query": {
                                "data": f"v2|{review_id}|{decision}", "id": "callback-id", "from": {"id": user},
                                "message": {"message_id": message, "chat": {"id": -12345}},
                            }})

    def test_attachment_is_private_to_revision_and_does_not_send_review(self):
        raw = mp4_structure()
        self.assertEqual(self.upload(self.session["revision"], b"not MP4").status_code, 400)
        saved = self.upload(self.session["revision"], raw)
        self.assertEqual(saved.status_code, 201, saved.text)
        current = saved.json()
        video = current["video"]
        self.assertEqual((video["version"], video["bundle_revision"], video["status"]), (1, self.rev, "ATTACHED"))
        self.assertEqual(build_bundle(current, self.store, self.rev), self.bundle)
        self.assertEqual(self.page_status(), "DRAFT")
        self.assertEqual(self.sent, [])
        url = f"/api/v2/sessions/{self.sid}/videos/1"
        part = self.request(self.local, "GET", url, headers={"Range": "bytes=0-15"})
        self.assertEqual((part.status_code, part.content), (206, raw[:16]))
        self.assertEqual(self.upload(self.session["revision"], raw).status_code, 409)
        duplicate = self.upload(current["revision"], raw).json()
        self.assertEqual(duplicate["revision"], current["revision"])
        act(self.store, self.engine, self.sid, "reopen", {"step": 4})
        self.assertEqual(self.request(self.local, "GET", url).status_code, 404)

    def test_correct_callback_only_and_retry_is_idempotent(self):
        raw = mp4_structure()
        self.assertEqual(self.send(1, raw, auth="wrong").status_code, 403)
        self.assertEqual(self.send(1, raw, digest="0" * 64).status_code, 400)
        self.assertEqual(self.page_status(), "DRAFT")
        posted = self.send(1, raw)
        self.assertEqual(posted.status_code, 200, posted.text)
        result = posted.json()["data"]
        review_id = result["review_id"]
        self.assertEqual(self.page_status(), "PENDING_REVIEW")
        self.assertEqual(self.send(1, raw).json()["data"], result)
        self.assertEqual(self.sent, [raw])
        self.assertEqual(self.click(review_id, 1, secret="wrong").status_code, 403)
        self.assertEqual(self.click(review_id, 1, user=999).status_code, 403)
        self.assertFalse(self.click(review_id, 999).json()["success"])
        self.assertEqual(self.page_status(), "PENDING_REVIEW")
        approved = self.click(review_id, 1).json()["data"]
        self.assertEqual(approved["status"], "APPROVED")
        self.assertEqual(self.click(review_id, 1).json()["data"], approved)
        self.assertFalse(self.click(review_id, 1, "r").json()["success"])
        self.assertEqual(self.page_status(), "APPROVED")

    def test_replacement_requires_fresh_review_and_cannot_overwrite_scheduled(self):
        first = self.send(1, mp4_structure(b"first")).json()["data"]
        self.assertTrue(self.click(first["review_id"], 1).json()["success"])
        next_raw = mp4_structure(b"replacement")
        second = self.send(2, next_raw).json()["data"]
        self.assertEqual(self.page_status(), "PENDING_REVIEW")
        self.assertFalse(self.click(first["review_id"], 1).json()["success"])
        self.assertEqual(self.send(1, mp4_structure(b"first")).status_code, 409)
        self.assertEqual(self.send(2, mp4_structure(b"different")).status_code, 409)
        self.assertEqual(self.click(second["review_id"], 2, "r").json()["data"]["status"], "NEEDS_REVISION")
        self.notion.page_data[self.page_id]["properties"]["status"]["select"]["name"] = "SCHEDULED"
        self.assertEqual(self.send(3, mp4_structure(b"third")).status_code, 409)
        self.assertEqual(self.page_status(), "SCHEDULED")

    def test_failed_notion_update_reuses_message_and_retries(self):
        raw = mp4_structure()
        with patch.object(review, "update_page", side_effect=review.HTTPException(502, "simulated")):
            self.assertEqual(self.send(1, raw).status_code, 502)
        self.assertEqual(self.page_status(), "DRAFT")
        self.assertEqual(self.send(1, raw).json()["data"]["status"], "PENDING_REVIEW")
        self.assertEqual(self.sent, [raw])

    def test_mp4_validation_rejects_file_without_video_track(self):
        path = Path(self.temp) / "no-video.mp4"
        with self.assertRaisesRegex(ValueError, "luồng hình ảnh"):
            save_mp4(io.BytesIO(box(b"ftyp", b"isom\x00\x00\x00\x00") + box(b"mdat", b"example")), path)
