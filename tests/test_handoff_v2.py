import copy
from contextlib import closing
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tests.studio_fixtures import setup_session, complete, act

ROOT = Path(__file__).resolve().parents[1]
LONG = Path(os.getenv("LONG_AUTOMATION_ROOT", str(ROOT / "integrations" / "long-v2"))).resolve()
sys.path.append(str(ROOT / ".test-deps"))
sys.path.insert(0, str(LONG / "python-service"))
hv = importlib.import_module("app.handoff_v2")


class FakeNotion:
    def __init__(self):
        self.page_data = {}
        self.query_database_ids = []
        self.children = {}
        self.count = 0
        self.append_calls = 0
        self.fail_at = None
        self.databases = SimpleNamespace(query=self.query)
        self.pages = SimpleNamespace(create=self.create_page, update=self.update_page)
        self.blocks = SimpleNamespace(children=SimpleNamespace(list=self.list_children, append=self.append_children))

    def query(self, **kw):
        self.query_database_ids.append(kw["database_id"])
        req = kw["filter"]["title"]["equals"]
        return {"results": [copy.deepcopy(p) for p in self.page_data.values() if p["parent"]["database_id"] == kw["database_id"] and p["properties"]["request_id"]["title"][0]["text"]["content"] == req]}

    def create_page(self, **kw):
        self.count += 1
        pid = f"page-{self.count}"
        page = {"id": pid, "parent": copy.deepcopy(kw["parent"]), "properties": copy.deepcopy(kw["properties"])}
        self.page_data[pid] = page
        return copy.deepcopy(page)

    def update_page(self, page_id, properties):
        self.page_data[page_id]["properties"].update(copy.deepcopy(properties))
        return copy.deepcopy(self.page_data[page_id])

    def list_children(self, block_id, **kw):
        return {"results": copy.deepcopy(self.children.get(block_id, [])), "has_more": False}

    def append_children(self, block_id, children):
        self.append_calls += 1
        if self.append_calls == self.fail_at:
            raise RuntimeError("Simulated Notion interruption")
        result = []
        for child in children:
            self.count += 1
            value = copy.deepcopy(child)
            value["id"] = f"block-{self.count}"
            self.children.setdefault(block_id, []).append(value)
            result.append(value)
        return {"results": copy.deepcopy(result)}


class HandoffV2Tests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / "data" / "test-runs"
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"HANDOFF_DATA_DIR": str(Path(self.temp.name) / "long"),
                                          "CONTENT_V2_ACCEPTANCE_MODE": "0",
                                          "NOTION_V2_DATABASE_ID": "", "WEBHOOK_V2_TOKEN": "",
                                          "WEBHOOK_V2_URL": "http://127.0.0.1:5678/webhook/ai-agent-callback-v2"})
        self.env.start(); self.addCleanup(self.env.stop)
        self.notion = FakeNotion()
        self.p1 = patch.object(hv.nc, "notion", self.notion)
        self.p2 = patch.object(hv.nc, "NOTION_DATABASE_ID", "test-database")
        self.p1.start(); self.p2.start()
        self.addCleanup(self.p1.stop); self.addCleanup(self.p2.stop)
        self.store, self.engine, self.ai, s = setup_session(self.temp.name)
        self.done = complete(self.store, self.engine, s)
        self.bundle = self.done["bundle"]
        app = FastAPI(); app.include_router(hv.router)
        self.client = TestClient(app)

    def send(self, bundle=None):
        return self.client.post("/api/v2/content/ai-output", json=bundle or self.bundle)

    def test_schema_copies_are_identical(self):
        self.assertEqual((ROOT / "contracts/handoff_v2.py").read_bytes(), (LONG / "python-service/app/contracts_v2.py").read_bytes())

    def test_receive_readback_and_duplicate_do_not_create_extra_blocks(self):
        response = self.send()
        self.assertEqual(response.status_code, 200, response.text)
        count = self.notion.count
        second = self.send()
        self.assertTrue(second.json()["data"]["duplicate"])
        self.assertEqual(count, self.notion.count)
        req, rev = self.bundle["request_id"], self.bundle["revision"]
        saved = self.client.get(f"/api/v2/content/{req}/revisions/{rev}").json()
        self.assertTrue(saved["success"])
        self.assertEqual(saved["data"], self.bundle)
        self.assertEqual(saved["payload_sha256"], response.json()["data"]["payload_sha256"])
        page = next(iter(self.notion.page_data.values()))
        self.assertEqual(page["properties"]["status"]["select"]["name"], "DRAFT")

    def test_conflicting_payload_stale_revision_and_approved_protection(self):
        self.assertEqual(self.send().status_code, 200)
        conflict = copy.deepcopy(self.bundle)
        conflict["publishing"]["selected_caption"] = 1
        self.assertEqual(self.send(conflict).status_code, 409)
        page = next(iter(self.notion.page_data.values()))
        page["properties"]["status"]["select"]["name"] = "APPROVED"
        newer = copy.deepcopy(self.bundle); newer["revision"] += 1
        self.assertEqual(self.send(newer).status_code, 409)
        self.assertEqual(page["properties"]["status"]["select"]["name"], "APPROVED")
        page["properties"]["status"]["select"]["name"] = "DRAFT"
        self.assertEqual(self.send(newer).status_code, 200)
        self.assertEqual(self.send().status_code, 409)

    def test_long_prompts_survive_notion_chunks_and_partial_retry(self):
        b = copy.deepcopy(self.bundle)
        # Keep each source dialogue exact while testing realistic prompt lengths > 2000.
        for scene in b["scenes"]:
            scene["prompt_en"] += " Gentle stable camera movement." * 170
        self.notion.fail_at = 3
        self.assertEqual(self.send(b).status_code, 502)
        self.notion.fail_at = None
        self.assertEqual(self.send(b).status_code, 200)
        self.assertEqual(len(self.notion.page_data), 1)
        page = next(iter(self.notion.page_data))
        sections = self.notion.children[page]
        self.assertEqual(len(sections), 1)
        blocks = self.notion.children[sections[0]["id"]]
        expected = hv.blocks_for(hv.HandoffV2.model_validate(b))
        self.assertEqual(len(blocks), len(expected))
        prompts = "".join(t["text"]["content"] for x in blocks if x["type"] == "code" for t in x["code"]["rich_text"])
        self.assertEqual(prompts, "".join(s["prompt_en"] for s in b["scenes"]))
        self.assertTrue(all(len(t["text"]["content"]) <= 1700 for x in blocks for t in x[x["type"]]["rich_text"]))

    def test_n8n_transform_retains_wire_data_and_uses_v2_route(self):
        flow = json.loads((LONG / "n8n/Content Studio - AI Agent Callback v2.json").read_text(encoding="utf-8"))
        webhook = next(n for n in flow["nodes"] if n["type"] == "n8n-nodes-base.webhook")
        self.assertEqual(webhook["parameters"]["authentication"], "headerAuth")
        self.assertIn("httpHeaderAuth", webhook["credentials"])
        self.assertEqual(flow["settings"]["saveDataSuccessExecution"], "none")
        self.assertEqual(flow["settings"]["saveDataErrorExecution"], "none")
        self.assertFalse(flow["settings"]["saveManualExecutions"])
        code = next(n["parameters"]["jsCode"] for n in flow["nodes"] if n["type"] == "n8n-nodes-base.code")
        js = "const fs=require('fs'); const p=JSON.parse(fs.readFileSync(0,'utf8')); const fn=new Function('$input'," + json.dumps(code) + "); process.stdout.write(JSON.stringify(fn({first:()=>({json:{body:p}})})[0].json));"
        node = shutil.which("node")
        if not node: self.skipTest("Node unavailable")
        result = subprocess.run([node, "-e", js], input=json.dumps(self.bundle), text=True, encoding="utf-8", capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout), self.bundle)
        self.assertIn("/api/v2/content/ai-output", next(n["parameters"]["url"] for n in flow["nodes"] if n["type"] == "n8n-nodes-base.httpRequest"))

    def test_studio_to_long_receipt_roundtrip_and_failure_state(self):
        outer = self
        class Bridge:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def post(self, url, json, **kwargs):
                return outer.client.post("/api/v2/content/ai-output", json=json)
        with patch("studio.service.httpx.Client", return_value=Bridge()):
            out = act(self.store, self.engine, self.done["id"], "handoff")
        self.assertEqual(out["status"], "ready", out.get("error"))
        self.assertEqual(out["handoff"]["status"], "received")
        with patch("studio.service.httpx.Client", side_effect=ConnectionError("test")):
            failed = act(self.store, self.engine, self.done["id"], "handoff")
        self.assertEqual(failed["status"], "error")
        self.assertEqual(failed["bundle"], self.bundle)

    def test_v2_database_is_isolated_and_receipt_cannot_change_target(self):
        with patch.dict(os.environ, {"NOTION_V2_DATABASE_ID": "acceptance-only"}):
            response = self.send()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["notion_database_id"], "acceptance-only")
            self.assertEqual(self.notion.query_database_ids, ["acceptance-only"])
            page = next(iter(self.notion.page_data.values()))
            self.assertEqual(page["parent"]["database_id"], "acceptance-only")
            self.assertEqual(hv.nc.NOTION_DATABASE_ID, "test-database")
        self.assertEqual(self.send().status_code, 409)
        self.assertEqual(len(self.notion.page_data), 1)

    def test_missing_notion_configuration_does_not_acknowledge(self):
        with patch.object(hv.nc, "NOTION_DATABASE_ID", None):
            self.assertEqual(self.send().status_code, 503)
        self.assertFalse(self.notion.page_data)

    def test_acceptance_mode_cannot_fall_back_to_the_production_database(self):
        with patch.dict(os.environ, {"CONTENT_V2_ACCEPTANCE_MODE": "1", "NOTION_V2_DATABASE_ID": ""}):
            self.assertEqual(self.send().status_code, 503)
        self.assertFalse(self.notion.page_data)

    def test_legacy_receipt_migration_preserves_duplicate_and_readback(self):
        self.assertEqual(self.send().status_code, 200)
        with closing(hv.connect()) as db:
            db.execute("ALTER TABLE receipts DROP COLUMN database_id")
            db.commit()
        response = self.send()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["duplicate"])
        saved = hv.read_snapshot(self.bundle["request_id"], self.bundle["revision"])
        self.assertEqual(saved["notion_database_id"], "test-database")
        self.assertEqual(saved["data"], self.bundle)
        self.assertEqual(len(self.notion.page_data), 1)

    def test_remote_handoff_requires_https_and_token_before_transmission(self):
        for url, token in (("https://example.test/webhook/v2", ""), ("http://example.test/webhook/v2", "test-secret")):
            with self.subTest(url=url), patch.dict(os.environ, {"WEBHOOK_V2_URL": url, "WEBHOOK_V2_TOKEN": token}), patch("studio.service.httpx.Client") as client:
                out = act(self.store, self.engine, self.done["id"], "handoff")
                self.assertEqual(out["status"], "error")
                client.assert_not_called()
                self.assertEqual(out["bundle"], self.bundle)
                self.assertNotIn("test-secret", json.dumps(out))

    def test_remote_token_is_header_only_and_handoff_uses_longer_timeout(self):
        outer = self
        class Bridge:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def post(self, url, json, headers):
                outer.assertEqual(headers, {"X-Content-Token": "test-secret"})
                return outer.client.post("/api/v2/content/ai-output", json=json)
        with patch.dict(os.environ, {"WEBHOOK_V2_URL": "https://example.test/webhook/v2", "WEBHOOK_V2_TOKEN": "test-secret"}), patch("studio.service.httpx.Client", return_value=Bridge()) as client:
            out = act(self.store, self.engine, self.done["id"], "handoff")
        client.assert_called_once_with(timeout=150, trust_env=False, follow_redirects=False)
        self.assertEqual(out["handoff"]["status"], "received")
        self.assertNotIn("test-secret", json.dumps(out))


if __name__ == "__main__": unittest.main()
