"""
TESTS/TEST_WEBHOOK_INTEGRATION.PY
==================================
Automated test suite verifying:
1. R1: Asynchronous execution of POST /generate (< 5s response)
2. R2: Webhook integration on port 5678 at /webhook/ai-agent-callback
3. Strict adherence to Step 4 API contract schema
4. Success, QC failure, and exception handling paths
5. Default webhook URL resolution (no URL in payload)
6. Concurrent request handling
7. Helper function edge cases
"""

import json
import time
import socket
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest import TestCase, main
from unittest.mock import patch

from starlette.testclient import TestClient

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app, _request_log, _active_threads, build_webhook_payload, send_webhook


class MockWebhookHandler(BaseHTTPRequestHandler):
    received_requests = []
    response_code = 200
    response_body = b'{"status": "received", "message": "Payload received and saved to Notion"}'

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        parsed_body = json.loads(body.decode("utf-8")) if body else {}

        MockWebhookHandler.received_requests.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": parsed_body,
        })

        self.send_response(MockWebhookHandler.response_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(MockWebhookHandler.response_body)

    def log_message(self, format, *args):
        # Silence HTTP server log output during test runs
        pass


class TestWebhookIntegration(TestCase):
    mock_server = None
    mock_server_thread = None
    mock_port = 5678

    @classmethod
    def setUpClass(cls):
        MockWebhookHandler.received_requests = []
        try:
            cls.mock_server = HTTPServer(("0.0.0.0", cls.mock_port), MockWebhookHandler)
        except OSError:
            try:
                cls.mock_server = HTTPServer(("127.0.0.1", cls.mock_port), MockWebhookHandler)
            except OSError:
                cls.mock_server = HTTPServer(("127.0.0.1", 0), MockWebhookHandler)
                cls.mock_port = cls.mock_server.server_port

        cls.mock_server_thread = threading.Thread(target=cls.mock_server.serve_forever, daemon=True)
        cls.mock_server_thread.start()

    @classmethod
    def tearDownClass(cls):
        if cls.mock_server:
            cls.mock_server.shutdown()
            cls.mock_server.server_close()

    def setUp(self):
        MockWebhookHandler.received_requests.clear()
        MockWebhookHandler.response_code = 200
        MockWebhookHandler.response_body = b'{"status": "received", "message": "Payload received and saved to Notion"}'
        _request_log.clear()
        _active_threads.clear()
        self.client = TestClient(app)

    def test_post_generate_returns_immediately_under_5s(self):
        """Acceptance Criteria 1: POST /generate returns immediately (< 5s)."""
        def slow_pipeline(*args, **kwargs):
            time.sleep(1.0)
            return {
                "request_id": "test_async_01",
                "status": "success",
                "ai_result": {
                    "hook_text": "Sample hook",
                    "voice_over_text": "Sample voice over",
                    "text_on_screen": "Sample text",
                    "image_prompt_en": "Sample image prompt",
                    "bgm_vibe": "Upbeat",
                    "post_caption": "Caption",
                    "hashtags": ["#tag1", "#tag2"],
                    "qc_score": 9.0,
                    "qc_feedback": "Looks great",
                    "retry_count": 0,
                },
                "metadata": {
                    "processing_time_seconds": 1,
                    "model_used": "gemini-3.8-flash",
                    "created_at": "2026-10-09T09:00:00Z",
                },
                "error": None,
            }

        payload = {
            "request_id": "test_async_01",
            "product": {
                "name": "Serum duong trang",
                "price": "299000",
                "brand_name": "GlowSkin",
                "key_features": ["Sang da", "Mo tham"],
                "target_audience": "Nu 18-35",
                "product_link": "https://example.com/serum",
            },
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", side_effect=slow_pipeline):
            start = time.time()
            response = self.client.post("/generate", json=payload)
            elapsed = time.time() - start

            # R1: Return immediately in under 5 seconds
            self.assertLess(elapsed, 5.0, f"Response took {elapsed:.2f}s, exceeding 5s limit!")
            self.assertEqual(response.status_code, 200)

            data = response.json()
            self.assertEqual(data["request_id"], "test_async_01")
            self.assertEqual(data["status"], "processing")
            self.assertIn("message", data)

            # Wait for background thread to finish
            if "test_async_01" in _active_threads:
                _active_threads["test_async_01"].join(timeout=5.0)

    def test_mock_server_port_5678_receives_webhook_callback(self):
        """Acceptance Criteria 2: Mock server on port 5678 receives POST request at /webhook/ai-agent-callback."""
        mock_pipeline_result = {
            "request_id": "req_step4_verify",
            "status": "success",
            "ai_result": {
                "hook_text": "3 bi quyet cham soc da mua hanh",
                "voice_over_text": "Kich ban voice over chi tiet trong 30 giay",
                "text_on_screen": "Bi quyet da dep",
                "image_prompt_en": "Cinematic shot of skincare serum bottle",
                "bgm_vibe": "Chill lofi acoustic",
                "post_caption": "Bi quyet giu da am min ca ngay #skincare #review",
                "hashtags": ["#skincare", "#review", "#giamgia"],
                "qc_score": 9.5,
                "qc_feedback": "Kich ban tot, dung tone",
                "retry_count": 0,
            },
            "metadata": {
                "processing_time_seconds": 32,
                "model_used": "gemini-3.8-flash",
                "created_at": "2026-10-09T09:30:00Z",
            },
            "error": None,
        }

        payload = {
            "request_id": "req_step4_verify",
            "product": {
                "name": "Kem duong am",
                "price": "350000",
            },
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", return_value=mock_pipeline_result):
            response = self.client.post("/generate", json=payload)
            self.assertEqual(response.status_code, 200)

            # Wait for background thread to complete
            if "req_step4_verify" in _active_threads:
                _active_threads["req_step4_verify"].join(timeout=5.0)

        # Assert mock server received the request
        self.assertEqual(len(MockWebhookHandler.received_requests), 1)
        received = MockWebhookHandler.received_requests[0]
        self.assertEqual(received["path"], "/webhook/ai-agent-callback")

    def test_webhook_payload_strictly_matches_step4_contract(self):
        """Acceptance Criteria 3: Webhook JSON body matches Step 4 API contract exactly."""
        mock_pipeline_result = {
            "request_id": "req_contract_01",
            "status": "success",
            "ai_result": {
                "hook_text": "Hook 3 giay",
                "voice_over_text": "Voice over text day du",
                "text_on_screen": "Chu tren man hinh",
                "scenes": [{"time": "0:00-0:03", "visual": "...", "audio": "..."}], # extra field in pipeline
                "image_prompt_en": "Product photo 4k",
                "bgm_vibe": "Pop upbeat",
                "post_caption": "Caption tiktok",
                "hashtags": ["#tag1", "#tag2"],
                "hashtag_string": "#tag1 #tag2", # extra field in pipeline
                "qc_score": 9.2,
                "qc_feedback": "Dat tieu chuan",
                "retry_count": 0,
            },
            "metadata": {
                "processing_time_seconds": 28.4,
                "model_used": "gemini-3.8-flash",
                "created_at": "2026-10-09T09:30:00Z",
                "log": ["[Start]", "[QC] Score=9.2"], # extra field in pipeline
            },
            "error": None,
        }

        payload = {
            "request_id": "req_contract_01",
            "product": {
                "name": "Son moi velvet",
                "price": "199000",
            },
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", return_value=mock_pipeline_result):
            self.client.post("/generate", json=payload)
            if "req_contract_01" in _active_threads:
                _active_threads["req_contract_01"].join(timeout=5.0)

        self.assertEqual(len(MockWebhookHandler.received_requests), 1)
        body = MockWebhookHandler.received_requests[0]["body"]

        # 1. Top-level contract keys
        expected_top_keys = {"request_id", "status", "ai_result", "metadata", "error"}
        self.assertEqual(set(body.keys()), expected_top_keys)
        self.assertEqual(body["request_id"], "req_contract_01")
        self.assertEqual(body["status"], "success")
        self.assertIsNone(body["error"])

        # 2. ai_result schema
        expected_ai_keys = {
            "hook_text",
            "voice_over_text",
            "text_on_screen",
            "image_prompt_en",
            "bgm_vibe",
            "post_caption",
            "hashtags",
            "qc_score",
            "qc_feedback",
            "retry_count",
        }
        self.assertEqual(set(body["ai_result"].keys()), expected_ai_keys)
        self.assertIsInstance(body["ai_result"]["hook_text"], str)
        self.assertIsInstance(body["ai_result"]["voice_over_text"], str)
        self.assertIsInstance(body["ai_result"]["text_on_screen"], str)
        self.assertIsInstance(body["ai_result"]["image_prompt_en"], str)
        self.assertIsInstance(body["ai_result"]["bgm_vibe"], str)
        self.assertIsInstance(body["ai_result"]["post_caption"], str)
        self.assertIsInstance(body["ai_result"]["hashtags"], list)
        self.assertIsInstance(body["ai_result"]["qc_score"], (int, float))
        self.assertIsInstance(body["ai_result"]["qc_feedback"], str)
        self.assertIsInstance(body["ai_result"]["retry_count"], int)

        # 3. metadata schema
        expected_meta_keys = {"processing_time_seconds", "model_used", "created_at"}
        self.assertEqual(set(body["metadata"].keys()), expected_meta_keys)
        self.assertIsInstance(body["metadata"]["processing_time_seconds"], int)
        self.assertEqual(body["metadata"]["processing_time_seconds"], 28)
        self.assertIsInstance(body["metadata"]["model_used"], str)
        self.assertIsInstance(body["metadata"]["created_at"], str)

    def test_default_webhook_url_port_5678(self):
        """When webhook_url is not provided in payload, default URL is used."""
        if self.mock_port != 5678:
            self.skipTest("Port 5678 was not available for mock server")

        mock_pipeline_result = {
            "request_id": "req_default_url_01",
            "status": "success",
            "ai_result": {
                "hook_text": "Default URL hook",
                "voice_over_text": "Voice",
                "text_on_screen": "Text",
                "image_prompt_en": "Prompt",
                "bgm_vibe": "Chill",
                "post_caption": "Caption",
                "hashtags": ["#default"],
                "qc_score": 9.0,
                "qc_feedback": "Good",
                "retry_count": 0,
            },
            "metadata": {
                "processing_time_seconds": 12,
                "model_used": "gemini-3.8-flash",
                "created_at": "2026-10-09T09:00:00Z",
            },
            "error": None,
        }

        # Notice: NO webhook_url in request payload or config!
        payload = {
            "request_id": "req_default_url_01",
            "product": {"name": "Default Test", "price": "100000"},
        }

        with patch("api.main.run_pipeline", return_value=mock_pipeline_result):
            self.client.post("/generate", json=payload)
            if "req_default_url_01" in _active_threads:
                _active_threads["req_default_url_01"].join(timeout=5.0)

        self.assertEqual(len(MockWebhookHandler.received_requests), 1)
        req = MockWebhookHandler.received_requests[0]
        self.assertEqual(req["path"], "/webhook/ai-agent-callback")
        self.assertEqual(req["body"]["request_id"], "req_default_url_01")

    def test_pipeline_failure_sends_failed_webhook(self):
        """When pipeline status is failed (e.g. QC failure), webhook is still sent."""
        mock_pipeline_result = {
            "request_id": "req_failed_01",
            "status": "failed",
            "ai_result": {
                "hook_text": "Bad hook",
                "voice_over_text": "Bad script",
                "text_on_screen": "",
                "image_prompt_en": "",
                "bgm_vibe": "",
                "post_caption": "",
                "hashtags": [],
                "qc_score": 5.0,
                "qc_feedback": "Chua dat yeu cau",
                "retry_count": 1,
            },
            "metadata": {
                "processing_time_seconds": 15,
                "model_used": "gemini-3.8-flash",
                "created_at": "2026-10-09T09:30:00Z",
            },
            "error": "QC_MAX_RETRY_EXCEEDED",
        }

        payload = {
            "request_id": "req_failed_01",
            "product": {"name": "Test fail", "price": "100000"},
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", return_value=mock_pipeline_result):
            self.client.post("/generate", json=payload)
            if "req_failed_01" in _active_threads:
                _active_threads["req_failed_01"].join(timeout=5.0)

        self.assertEqual(len(MockWebhookHandler.received_requests), 1)
        body = MockWebhookHandler.received_requests[0]["body"]
        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["ai_result"]["qc_score"], 5.0)
        self.assertEqual(body["error"], {"message": "QC_MAX_RETRY_EXCEEDED"})

    def test_pipeline_exception_sends_error_webhook(self):
        """When pipeline raises an unhandled exception, webhook is still sent with error details."""
        payload = {
            "request_id": "req_exception_01",
            "product": {"name": "Test exception", "price": "100000"},
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", side_effect=RuntimeError("Gemini API connection error")):
            self.client.post("/generate", json=payload)
            if "req_exception_01" in _active_threads:
                _active_threads["req_exception_01"].join(timeout=5.0)

        self.assertEqual(len(MockWebhookHandler.received_requests), 1)
        body = MockWebhookHandler.received_requests[0]["body"]
        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["request_id"], "req_exception_01")
        self.assertIn("Gemini API connection error", body["error"]["message"])
        self.assertIn("processing_time_seconds", body["metadata"])
        self.assertIn("created_at", body["metadata"])

    def test_status_endpoint_tracks_progress_and_completion(self):
        """GET /status/{request_id} reflects background progress and webhook status."""
        req_id = "req_status_01"
        payload = {
            "request_id": req_id,
            "product": {"name": "Test status", "price": "100000"},
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        mock_pipeline_result = {
            "request_id": req_id,
            "status": "success",
            "ai_result": {
                "hook_text": "Status hook",
                "voice_over_text": "Voice",
                "text_on_screen": "Text",
                "image_prompt_en": "Prompt",
                "bgm_vibe": "Chill",
                "post_caption": "Caption",
                "hashtags": ["#tag"],
                "qc_score": 9.0,
                "qc_feedback": "Good",
                "retry_count": 0,
            },
            "metadata": {
                "processing_time_seconds": 10,
                "model_used": "gemini-3.8-flash",
                "created_at": "2026-10-09T09:00:00Z",
            },
            "error": None,
        }

        with patch("api.main.run_pipeline", return_value=mock_pipeline_result):
            self.client.post("/generate", json=payload)
            if req_id in _active_threads:
                _active_threads[req_id].join(timeout=5.0)

        resp = self.client.get(f"/status/{req_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data.get("webhook_sent"))
        self.assertEqual(data.get("webhook_status_code"), 200)

    def test_webhook_unreachable_does_not_crash_app(self):
        """If webhook URL cannot be reached, the server logs and handles it gracefully."""
        req_id = "req_unreachable_01"
        payload = {
            "request_id": req_id,
            "product": {"name": "Test unreachable", "price": "100000"},
            "webhook_url": "http://127.0.0.1:59999/webhook/ai-agent-callback",
        }

        mock_pipeline_result = {
            "request_id": req_id,
            "status": "success",
            "ai_result": {},
            "metadata": {},
            "error": None,
        }

        with patch("api.main.run_pipeline", return_value=mock_pipeline_result):
            resp = self.client.post("/generate", json=payload)
            self.assertEqual(resp.status_code, 200)
            if req_id in _active_threads:
                _active_threads[req_id].join(timeout=10.0)

        log = _request_log.get(req_id, {})
        self.assertFalse(log.get("webhook_sent"))
        self.assertIn("webhook_error", log)

    def test_concurrent_generate_requests(self):
        """Multiple concurrent requests run independently and both trigger webhooks."""
        req1 = "req_concurrent_1"
        req2 = "req_concurrent_2"

        def mock_pipeline(request_id, product, config):
            return {
                "request_id": request_id,
                "status": "success",
                "ai_result": {"hook_text": f"Hook for {request_id}"},
                "metadata": {"processing_time_seconds": 1},
                "error": None,
            }

        with patch("api.main.run_pipeline", side_effect=mock_pipeline):
            resp1 = self.client.post("/generate", json={
                "request_id": req1,
                "product": {"name": "P1", "price": "100"},
                "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
            })
            resp2 = self.client.post("/generate", json={
                "request_id": req2,
                "product": {"name": "P2", "price": "200"},
                "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
            })

            self.assertEqual(resp1.status_code, 200)
            self.assertEqual(resp2.status_code, 200)

            if req1 in _active_threads:
                _active_threads[req1].join(timeout=5.0)
            if req2 in _active_threads:
                _active_threads[req2].join(timeout=5.0)

        self.assertEqual(len(MockWebhookHandler.received_requests), 2)
        received_ids = {r["body"]["request_id"] for r in MockWebhookHandler.received_requests}
        self.assertEqual(received_ids, {req1, req2})

    def test_build_webhook_payload_hashtags_coercion(self):
        """String hashtags are properly parsed into a list."""
        payload = build_webhook_payload(
            request_id="req_tags",
            status="success",
            raw_ai_result={"hashtags": "#skincare #glow #trend"},
            raw_metadata={"processing_time_seconds": 10},
        )
        self.assertEqual(payload["ai_result"]["hashtags"], ["#skincare", "#glow", "#trend"])

    def test_webhook_http_500_response_marked_as_failed_in_request_log(self):
        """When webhook returns HTTP 500, webhook_sent is False and webhook_error is recorded."""
        req_id = "req_server_err_01"
        MockWebhookHandler.response_code = 500
        MockWebhookHandler.response_body = b'{"status": "error", "message": "Internal Database Error"}'

        mock_pipeline_result = {
            "request_id": req_id,
            "status": "success",
            "ai_result": {"hook_text": "Test hook"},
            "metadata": {"processing_time_seconds": 5},
            "error": None,
        }

        payload = {
            "request_id": req_id,
            "product": {"name": "Test Product", "price": "100000"},
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", return_value=mock_pipeline_result):
            resp = self.client.post("/generate", json=payload)
            self.assertEqual(resp.status_code, 200)

            if req_id in _active_threads:
                _active_threads[req_id].join(timeout=5.0)

        log = _request_log.get(req_id, {})
        self.assertFalse(log.get("webhook_sent"))
        self.assertEqual(log.get("webhook_status_code"), 500)
        self.assertIn("HTTP 500", log.get("webhook_error", ""))

    def test_webhook_http_404_response_marked_as_failed_in_request_log(self):
        """When webhook returns HTTP 404, webhook_sent is False and webhook_error is recorded."""
        req_id = "req_not_found_01"
        MockWebhookHandler.response_code = 404
        MockWebhookHandler.response_body = b'{"message": "Webhook not found"}'

        mock_pipeline_result = {
            "request_id": req_id,
            "status": "success",
            "ai_result": {},
            "metadata": {},
            "error": None,
        }

        payload = {
            "request_id": req_id,
            "product": {"name": "Test Product", "price": "100000"},
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", return_value=mock_pipeline_result):
            resp = self.client.post("/generate", json=payload)
            self.assertEqual(resp.status_code, 200)

            if req_id in _active_threads:
                _active_threads[req_id].join(timeout=5.0)

        log = _request_log.get(req_id, {})
        self.assertFalse(log.get("webhook_sent"))
        self.assertEqual(log.get("webhook_status_code"), 404)
        self.assertIn("HTTP 404", log.get("webhook_error", ""))

    def test_post_generate_empty_request_id_returns_400(self):
        """An empty or whitespace-only request_id is rejected with 400 Bad Request immediately."""
        resp = self.client.post("/generate", json={
            "request_id": "   ",
            "product": {"name": "Test Product"},
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("request_id is required", resp.json()["detail"])

    def test_generate_with_notion_product_name_and_integer_price(self):
        """Supports Notion schema product_name and integer prices without validation error."""
        req_id = "req_notion_compat_01"
        received_product = {}

        def mock_pipeline(request_id, product, config):
            nonlocal received_product
            received_product = product
            return {
                "request_id": request_id,
                "status": "success",
                "ai_result": {"hook_text": "Compatible hook"},
                "metadata": {"processing_time_seconds": 1},
                "error": None,
            }

        payload = {
            "request_id": req_id,
            "product": {
                "product_name": "Serum Vitamin C",
                "price": 299000,  # integer price
                "brand_name": "GlowSkin",
            },
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", side_effect=mock_pipeline):
            resp = self.client.post("/generate", json=payload)
            self.assertEqual(resp.status_code, 200)

            if req_id in _active_threads:
                _active_threads[req_id].join(timeout=5.0)

        self.assertEqual(received_product.get("name"), "Serum Vitamin C")
        self.assertEqual(received_product.get("product_name"), "Serum Vitamin C")
        self.assertEqual(received_product.get("price"), "299000")
        self.assertEqual(received_product.get("brand_name"), "GlowSkin")

    def test_generate_with_flat_root_level_fields_notion_intake(self):
        """Supports flat Notion intake payloads where product fields are at root level."""
        req_id = "req_flat_intake_01"
        received_product = {}

        def mock_pipeline(request_id, product, config):
            nonlocal received_product
            received_product = product
            return {
                "request_id": request_id,
                "status": "success",
                "ai_result": {"hook_text": "Flat intake hook"},
                "metadata": {"processing_time_seconds": 1},
                "error": None,
            }

        # Flat payload matching Notion intake
        payload = {
            "request_id": req_id,
            "product_name": "Kem Chong Nang",
            "product_link": "https://example.com/sunscreen",
            "brand_name": "SunShield",
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", side_effect=mock_pipeline):
            resp = self.client.post("/generate", json=payload)
            self.assertEqual(resp.status_code, 200)

            if req_id in _active_threads:
                _active_threads[req_id].join(timeout=5.0)

        self.assertEqual(received_product.get("name"), "Kem Chong Nang")
        self.assertEqual(received_product.get("product_link"), "https://example.com/sunscreen")
        self.assertEqual(received_product.get("brand_name"), "SunShield")

    def test_build_webhook_payload_comma_hashtags_and_missing_hash_prefix(self):
        """Comma-delimited hashtags and tags without # prefix are properly formatted."""
        payload1 = build_webhook_payload(
            request_id="req_comma_tags",
            status="success",
            raw_ai_result={"hashtags": "skincare, beauty, review"},
            raw_metadata={"processing_time_seconds": 10},
        )
        self.assertEqual(payload1["ai_result"]["hashtags"], ["#skincare", "#beauty", "#review"])

        payload2 = build_webhook_payload(
            request_id="req_list_tags",
            status="success",
            raw_ai_result={"hashtags": ["xuhuong", "#review", "giamgia"]},
            raw_metadata={"processing_time_seconds": 10},
        )
        self.assertEqual(payload2["ai_result"]["hashtags"], ["#xuhuong", "#review", "#giamgia"])

    def test_build_webhook_payload_success_guarantees_null_error(self):
        """On success, the error field must strictly be None per Step 4 contract."""
        payload = build_webhook_payload(
            request_id="req_succ_err",
            status="success",
            raw_ai_result={},
            raw_metadata={},
            error="Non-fatal warning string",
        )
        self.assertIsNone(payload["error"])

    def test_build_webhook_payload_failed_without_error_provides_default_error_dict(self):
        """When status is failed and error is None, a default error dict is provided."""
        payload = build_webhook_payload(
            request_id="req_fail_no_err",
            status="failed",
            raw_ai_result={},
            raw_metadata={},
            error=None,
        )
        self.assertIsInstance(payload["error"], dict)
        self.assertEqual(payload["error"], {"message": "Pipeline execution failed"})

    def test_post_generate_empty_product_name_returns_400(self):
        """Reject generate request with 400 Bad Request if product name is empty."""
        resp = self.client.post("/generate", json={
            "request_id": "req_no_prod_name",
            "product": {"name": "   ", "price": "100000"},
        })
        self.assertEqual(resp.status_code, 400)
        self.assertIn("product name is required", resp.json()["detail"])

    def test_generate_with_hybrid_merged_product_fields(self):
        """Nested product fields override root, while missing nested fields fall back to root."""
        req_id = "req_hybrid_01"
        received_product = {}

        def mock_pipeline(request_id, product, config):
            nonlocal received_product
            received_product = product
            return {
                "request_id": request_id,
                "status": "success",
                "ai_result": {"hook_text": "Hybrid hook"},
                "metadata": {"processing_time_seconds": 1},
                "error": None,
            }

        payload = {
            "request_id": req_id,
            "product": {
                "name": "Son Moi Li",
                "price": 180000,
            },
            # Root fields that fill in missing attributes
            "brand_name": "VelvetBeauty",
            "product_link": "https://example.com/lipstick",
            "target_audience": "Nu 20-30",
            "key_features": ["Lau troi", "Min moi"],
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", side_effect=mock_pipeline):
            resp = self.client.post("/generate", json=payload)
            self.assertEqual(resp.status_code, 200)

            if req_id in _active_threads:
                _active_threads[req_id].join(timeout=5.0)

        self.assertEqual(received_product["name"], "Son Moi Li")
        self.assertEqual(received_product["price"], "180000")
        self.assertEqual(received_product["brand_name"], "VelvetBeauty")
        self.assertEqual(received_product["product_link"], "https://example.com/lipstick")
        self.assertEqual(received_product["target_audience"], "Nu 20-30")
        self.assertEqual(received_product["key_features"], ["Lau troi", "Min moi"])

    def test_idempotent_duplicate_request_does_not_spawn_extra_pipeline(self):
        """Sending duplicate request_id while pipeline is actively running returns processing without extra thread."""
        req_id = "req_dup_01"
        pipeline_call_count = 0
        barrier = threading.Barrier(2)

        def blocking_pipeline(request_id, product, config):
            nonlocal pipeline_call_count
            pipeline_call_count += 1
            barrier.wait(timeout=5.0)
            time.sleep(0.5)
            return {
                "request_id": request_id,
                "status": "success",
                "ai_result": {"hook_text": "Hook"},
                "metadata": {"processing_time_seconds": 1},
                "error": None,
            }

        payload = {
            "request_id": req_id,
            "product": {"name": "San pham trung lap", "price": "100000"},
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", side_effect=blocking_pipeline):
            resp1 = self.client.post("/generate", json=payload)
            self.assertEqual(resp1.status_code, 200)

            # Wait until the first thread enters blocking_pipeline
            barrier.wait(timeout=5.0)

            # Attempt to send duplicate while first thread is actively running
            resp2 = self.client.post("/generate", json=payload)
            self.assertEqual(resp2.status_code, 200)
            self.assertEqual(resp2.json()["status"], "processing")
            self.assertIn("already running", resp2.json()["message"])

            if req_id in _active_threads:
                _active_threads[req_id].join(timeout=5.0)

        self.assertEqual(pipeline_call_count, 1)

    def test_key_features_string_coerced_to_list(self):
        """Comma-separated key_features string is converted into a list of strings."""
        req_id = "req_feats_str"
        received_product = {}

        def mock_pipeline(request_id, product, config):
            nonlocal received_product
            received_product = product
            return {
                "request_id": request_id,
                "status": "success",
                "ai_result": {},
                "metadata": {},
                "error": None,
            }

        payload = {
            "request_id": req_id,
            "product": {
                "name": "Kem Chống Nắng",
                "key_features": "Kiem dau, Chong tia UV, Khang nuoc",
            },
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", side_effect=mock_pipeline):
            resp = self.client.post("/generate", json=payload)
            self.assertEqual(resp.status_code, 200)

            if req_id in _active_threads:
                _active_threads[req_id].join(timeout=5.0)

        self.assertEqual(received_product["key_features"], ["Kiem dau", "Chong tia UV", "Khang nuoc"])

    def test_build_webhook_payload_hashtags_deduplication_and_filtering(self):
        """Hashtags are deduplicated case-insensitively and bare '#' or None items are removed."""
        payload = build_webhook_payload(
            request_id="req_dedup_tags",
            status="success",
            raw_ai_result={
                "hashtags": ["#skincare", "skincare", "#Beauty", "#", None, "makeup", "#beauty"]
            },
            raw_metadata={"processing_time_seconds": 10},
        )
        self.assertEqual(payload["ai_result"]["hashtags"], ["#skincare", "#Beauty", "#makeup"])

    def test_send_webhook_rejects_invalid_url_protocol(self):
        """Invalid protocol like ftp:// or plain string is immediately rejected."""
        success, code, err = send_webhook("ftp://invalid-server/callback", {"test": 1})
        self.assertFalse(success)
        self.assertIsNone(code)
        self.assertIn("Invalid webhook URL protocol", err)

        success2, code2, err2 = send_webhook("not-a-url", {"test": 1})
        self.assertFalse(success2)
        self.assertIsNone(code2)
        self.assertIn("Invalid webhook URL protocol", err2)

    def test_concurrent_status_and_generate_requests_thread_safety(self):
        """Concurrent requests to /generate and /status do not raise exceptions or deadlock."""
        mock_pipeline_result = {
            "request_id": "req_conc_safe",
            "status": "success",
            "ai_result": {"hook_text": "Concurrent safe hook"},
            "metadata": {"processing_time_seconds": 1},
            "error": None,
        }

        with patch("api.main.run_pipeline", return_value=mock_pipeline_result):
            def make_call(idx):
                client = TestClient(app)
                req_id = f"req_conc_{idx}"
                client.post("/generate", json={
                    "request_id": req_id,
                    "product": {"name": f"Product {idx}"},
                    "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
                })
                client.get(f"/status/{req_id}")

            threads = [threading.Thread(target=make_call, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5.0)

            # Wait for any active background threads to finish
            for i in range(5):
                req_id = f"req_conc_{i}"
                if req_id in _active_threads:
                    _active_threads[req_id].join(timeout=5.0)

    def test_run_server_imports_without_name_error(self):
        """Verifies run_server module imports cleanly without NameError: load_dotenv."""
        import importlib
        import run_server
        importlib.reload(run_server)
        self.assertTrue(hasattr(run_server, "PORT"))
        self.assertEqual(run_server.PORT, 8000)

    def test_thread_cleans_up_from_active_threads_in_finally_block(self):
        """When background pipeline completes, the thread removes itself from _active_threads."""
        req_id = "req_thread_cleanup_01"
        mock_pipeline_result = {
            "request_id": req_id,
            "status": "success",
            "ai_result": {},
            "metadata": {},
            "error": None,
        }

        payload = {
            "request_id": req_id,
            "product": {"name": "Test Product", "price": "100000"},
            "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
        }

        with patch("api.main.run_pipeline", return_value=mock_pipeline_result):
            resp = self.client.post("/generate", json=payload)
            self.assertEqual(resp.status_code, 200)

            # Wait briefly for thread to finish
            max_wait = 5.0
            start_wait = time.time()
            while req_id in _active_threads and (time.time() - start_wait) < max_wait:
                time.sleep(0.05)

        # Thread must have removed itself from _active_threads
        self.assertNotIn(req_id, _active_threads)

    def test_send_webhook_retries_on_connection_error(self):
        """send_webhook executes retries when transient connection errors occur."""
        call_count = 0

        def flaky_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("Transient connection refused")
            # Second attempt succeeds
            class MockResponse:
                status_code = 200
                is_success = True
            return MockResponse()

        with patch("httpx.Client.post", side_effect=flaky_post):
            success, code, err = send_webhook(
                f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
                {"test": 1},
                max_retries=2,
            )
            self.assertTrue(success)
            self.assertEqual(code, 200)
            self.assertEqual(call_count, 2)

    def test_hashtags_triple_hash_and_fallback_to_hashtag_string(self):
        """###hash is cleaned to #hash, and hashtag_string is used when hashtags list is empty."""
        payload1 = build_webhook_payload(
            request_id="req_triple_hash",
            status="success",
            raw_ai_result={"hashtags": ["###skincare", "##beauty", "#review"]},
            raw_metadata={"processing_time_seconds": 10},
        )
        self.assertEqual(payload1["ai_result"]["hashtags"], ["#skincare", "#beauty", "#review"])

        payload2 = build_webhook_payload(
            request_id="req_str_fallback",
            status="success",
            raw_ai_result={"hashtags": [], "hashtag_string": "#trend #fyp #viral"},
            raw_metadata={"processing_time_seconds": 10},
        )
        self.assertEqual(payload2["ai_result"]["hashtags"], ["#trend", "#fyp", "#viral"])

    def test_request_log_pruning_on_max_capacity(self):
        """When _request_log reaches MAX_REQUEST_LOG_SIZE, oldest entries are pruned."""
        from api.main import MAX_REQUEST_LOG_SIZE, _request_log
        # Pre-fill log up to capacity
        for i in range(MAX_REQUEST_LOG_SIZE):
            _request_log[f"old_req_{i}"] = {"status": "done"}

        self.assertEqual(len(_request_log), MAX_REQUEST_LOG_SIZE)

        # Trigger generate which should prune 100 oldest entries
        with patch("api.main.run_pipeline", return_value={"status": "success", "ai_result": {}, "metadata": {}}):
            resp = self.client.post("/generate", json={
                "request_id": "new_req_pruning",
                "product": {"name": "New Pruning Product"},
                "webhook_url": f"http://127.0.0.1:{self.mock_port}/webhook/ai-agent-callback",
            })
            self.assertEqual(resp.status_code, 200)

        # Oldest key old_req_0 should be pruned
        self.assertNotIn("old_req_0", _request_log)
        self.assertIn("new_req_pruning", _request_log)
        self.assertLessEqual(len(_request_log), MAX_REQUEST_LOG_SIZE + 1)


if __name__ == "__main__":
    main()
