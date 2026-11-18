"""New modes use synthetic data; no external generation, review or posting evidence."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from contracts.handoff_v2 import parse_handoff
from studio.models import CTA
from studio.output import build_bundle, notebook_markdown
from tests.studio_fixtures import FakeGateway, setup_session, complete, act
from tests.test_handoff_v2 import hv, FakeNotion, LONG

ROOT = Path(__file__).resolve().parents[1]


class ModeGateway(FakeGateway):
    def generate(self, kind, context, schema):
        result = super().generate(kind, context, schema)
        if context.get('content_mode') == 'ordinary':
            if kind == 'publishing':
                result['captions'] = [f'Góc bàn ngăn nắp mỗi ngày — minh họa {i}.' for i in range(3)]
                result['hashtags'][-1] = '#goclamviec'
                result['pinned_comment'] = 'Thông tin tham khảo: ' + context['product']['product_link']
            if kind == 'plan':
                result['scenes'][-1]['part'] = 'Lời kết'
        return result


class ContentModesTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'data/test-runs').mkdir(parents=True, exist_ok=True)
        self.folder = self.enterContext(tempfile.TemporaryDirectory(dir=ROOT / 'data/test-runs'))
        self.store, self.engine, _, legacy = setup_session(self.folder)
        self.engine.gateway = ModeGateway()
        self.legacy = legacy
        self.s = self.store.create(legacy['product'])

    def test_modes_four_five_speaking_voiceover(self):
        for mode in ('ordinary', 'tiktok_shop'):
            for count in (4, 5):
                for audio in ('speaking', 'voiceover'):
                    with self.subTest(mode=mode, count=count, audio=audio):
                        s = self.store.create(self.s['product'], content_mode=mode)
                        s = complete(self.store, self.engine, s, count, audio)
                        b = s['bundle']
                        self.assertEqual((b['schema_version'], b['content_mode']), ('2.1', mode))
                        self.assertEqual(parse_handoff(b).model_dump(), b)
                        self.assertEqual(build_bundle(s, self.store, b['revision']), b)
                        self.assertEqual(b['scenes'][-1]['dialogue_vi'] == CTA, mode == 'tiktok_shop')
                        self.assertEqual(b['scenes'][-1]['dialogue_vi'], s['approved']['5']['4'])
                        from app.contracts_v2 import parse_handoff as long_parse
                        self.assertEqual(long_parse(b).model_dump(), b)
                        from studio.chat import next_step
                        s['video'] = {'bundle_revision': b['revision'], 'version': 1, 'status': 'APPROVED'}
                        self.assertIn('Mở Đăng TikTok' if mode == 'ordinary' else 'chưa hỗ trợ đăng tự động', next_step(s))

    def test_default_api_and_store_are_ordinary(self):
        from api import studio as api
        from studio import auth
        app = FastAPI(); app.include_router(api.router)
        with patch.object(api, 'get_store', return_value=self.store), patch.object(auth, 'enabled', return_value=False):
            response = TestClient(app).post('/api/v2/sessions', json=self.s['product'])
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()['content_mode'], 'ordinary')

    def test_final_ordinary_dialogue_needs_approval_and_can_be_reopened(self):
        s = complete(self.store, self.engine, self.s, stop_at=5)
        for _ in range(3):
            act(self.store, self.engine, s['id'], 'generate')
            s = act(self.store, self.engine, s['id'], 'approve')
        self.assertEqual(s['step'], 5)
        self.assertNotIn('4', s['dialogues'])
        self.assertNotIn('5', s['approved'])
        s = complete(self.store, self.engine, s)
        line = s['dialogues']['4']
        s = act(self.store, self.engine, s['id'], 'reopen', {'step': 5, 'scene_id': '4'})
        self.assertEqual(s['draft']['text'], line)
        self.assertEqual(list(s['dialogues']), ['1', '2', '3'])

    def test_mode_change_requires_step_one_and_invalidates_dependents(self):
        s = complete(self.store, self.engine, self.s)
        b = copy.deepcopy(s['bundle'])
        s = act(self.store, self.engine, s['id'], 'revise', {'content_mode': 'tiktok_shop', 'product': s['product']})
        self.assertEqual(s['status'], 'error')
        self.assertEqual(s['bundle'], b)
        s = act(self.store, self.engine, s['id'], 'reopen', {'step': 1})
        s = act(self.store, self.engine, s['id'], 'revise', {'content_mode': 'tiktok_shop', 'product': s['product']})
        self.assertEqual(s['content_mode'], 'tiktok_shop')
        self.assertFalse(s['approved']); self.assertFalse(s['dialogues'])
        self.assertNotIn('bundle', s); self.assertIsNone(s['handoff'])
        self.assertGreater(s['revision'], b['revision'])
        done = complete(self.store, self.engine, s)
        self.assertEqual(done['dialogues']['4'], CTA)

    def test_shop_references_block_all_rendered_ordinary_fields(self):
        b = complete(self.store, self.engine, self.s)['bundle']
        for path in ('action_vi', 'dialogue_vi', 'prompt_en', 'overlay_text'):
            changed = copy.deepcopy(b)
            changed['scenes'][0][path] += ' Bấm giỏ hàng nhé!'
            with self.subTest(path=path), self.assertRaises(ValueError):
                parse_handoff(changed)
        for field in ('captions', 'hashtags', 'slogans', 'pinned_comment'):
            changed = copy.deepcopy(b)
            if field == 'pinned_comment': changed['publishing'][field] += ' TikTok Shop'
            else: changed['publishing'][field][0] = '#tiktokshop'
            with self.subTest(field=field), self.assertRaises(ValueError): parse_handoff(changed)

    def test_legacy_payload_and_digest_are_unchanged(self):
        raw = json.loads((ROOT / 'examples/handoff-v2/handoff.json').read_text(encoding='utf-8'))
        canonical = hv.canonical(raw)
        restored = parse_handoff(raw)
        self.assertTrue(restored.is_shop())
        self.assertNotIn('content_mode', restored.model_dump())
        self.assertEqual(canonical, hv.canonical(restored.model_dump()))
        s = complete(self.store, self.engine, self.legacy)
        self.assertEqual(build_bundle(s, self.store, s['bundle']['revision']), s['bundle'])

    def test_new_bundle_notebook_and_zip_use_same_revision(self):
        from api import studio as api
        s = complete(self.store, self.engine, self.s)
        with patch.object(api, 'get_store', return_value=self.store):
            app = FastAPI(); app.include_router(api.router)
            r = TestClient(app).get(f"/api/v2/sessions/{s['id']}/export/zip?revision={s['bundle']['revision']}")
        self.assertEqual(r.status_code, 200, r.text if r.status_code != 200 else '')
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            self.assertIn('gemini-notebook.md', z.namelist())
            note = z.read('gemini-notebook.md').decode('utf-8')
            self.assertIn('Video thường', note)
            self.assertIn('r' + str(s['bundle']['revision']), note)
            for scene in s['bundle']['scenes']: self.assertIn(scene['prompt_en'], note)

    def test_long_new_payload_n8n_notion_retry_readback(self):
        s = complete(self.store, self.engine, self.s, count=5)
        b = copy.deepcopy(s['bundle'])
        for scene in b['scenes']: scene['prompt_en'] += ' Stable camera with natural light.' * 170
        flow = json.loads((LONG / 'n8n/Content Studio - AI Agent Callback v2.json').read_text(encoding='utf-8'))
        code = next(n['parameters']['jsCode'] for n in flow['nodes'] if n['type'] == 'n8n-nodes-base.code')
        js = 'const p=JSON.parse(require("fs").readFileSync(0,"utf8")); const $input={first:()=>({json:{body:p}})}; const out=(()=>{'+code+'})();process.stdout.write(JSON.stringify(out[0].json));'
        result = subprocess.run(['node', '-e', js], input=json.dumps(b), capture_output=True, text=True, encoding='utf-8', check=True)
        transported = json.loads(result.stdout)
        self.assertEqual(transported, b)
        notion = FakeNotion(); notion.fail_at = 3
        app = FastAPI(); app.include_router(hv.router)
        with patch.dict(os.environ, HANDOFF_DATA_DIR=self.folder+'/handoff', CONTENT_V2_ACCEPTANCE_MODE='0', NOTION_V2_DATABASE_ID=''), patch.object(hv.nc, 'notion', notion), patch.object(hv.nc, 'NOTION_DATABASE_ID', 'test-only'):
            client = TestClient(app)
            self.assertEqual(client.post('/api/v2/content/ai-output', json=transported).status_code, 502)
            notion.fail_at = None
            sent = client.post('/api/v2/content/ai-output', json=transported)
            self.assertEqual(sent.status_code, 200, sent.text)
            self.assertTrue(client.post('/api/v2/content/ai-output', json=transported).json()['data']['duplicate'])
            read = client.get(f"/api/v2/content/{b['request_id']}/revisions/{b['revision']}").json()
            self.assertEqual(read['data'], b)
            self.assertEqual(read['payload_sha256'], hashlib.sha256(hv.canonical(b).encode()).hexdigest())
            from scripts.acceptance import compare
            self.assertTrue(compare(b, sent.json(), read)['technical_checks_passed'])
            self.assertEqual(len(notion.page_data), 1)
            self.assertIn('Video thường', json.dumps(notion.children, ensure_ascii=False))

    def test_free_gateway_target_and_runtime_never_fake_online(self):
        from scripts.start_personal import gateway_domain, tunnel_target
        self.assertEqual(gateway_domain('https://demo.ngrok-free.dev'), 'https://demo.ngrok-free.dev')
        self.assertTrue(tunnel_target('http://127.0.0.1:8080'))
        self.assertFalse(tunnel_target('http://127.0.0.1:8001'))
        for value in ('http://demo.ngrok-free.dev', 'https://demo.ngrok-free.dev.evil.test', 'https://user:pass@demo.ngrok-free.dev'):
            with self.assertRaises(ValueError): gateway_domain(value)
        from api import runtime
        with patch.dict(os.environ, STUDIO_PUBLIC_URL=''), patch.object(runtime, '_last', (None, 0, {})), patch.object(runtime.httpx, 'Client') as client:
            status = runtime.external_status()
            self.assertFalse(status['connected']); self.assertFalse(status['configured']); client.assert_not_called()
