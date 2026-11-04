import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import httpx
from studio.ai import Gateway, GenerationError
from studio.models import Analysis


class RemoteError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__("remote-secret-must-not-leak")


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.clock = 0.0
        self.call = Mock()
        client = SimpleNamespace(models=SimpleNamespace(generate_content=self.call))
        for context in (
            patch.dict("os.environ", {"GEMINI_MODEL": "primary", "GEMINI_FALLBACK_MODEL": "fallback"}),
            patch("studio.ai.get_client", return_value=client),
            patch("studio.ai.time.monotonic", side_effect=lambda: self.clock),
            patch("studio.ai.time.sleep", side_effect=self.sleep),
            patch("studio.ai.random.uniform", return_value=0),
        ):
            context.start()
            self.addCleanup(context.stop)

    def sleep(self, seconds):
        self.clock += seconds

    @staticmethod
    def valid():
        return SimpleNamespace(text=json.dumps({"summary": "Sản phẩm", "suggestions": [],
                                                "product_description_en": "A product"}))

    def test_success_disables_sdk_retries_and_records_model(self):
        self.call.return_value = self.valid()
        ai = Gateway()
        self.assertEqual(ai.generate("analysis", {}, Analysis)["summary"], "Sản phẩm")
        self.assertEqual(ai.last_model, "primary")
        config = self.call.call_args.kwargs["config"]
        self.assertEqual(config.http_options.timeout, 30000)
        self.assertEqual(config.http_options.retry_options.attempts, 1)
        self.assertTrue(config.automatic_function_calling.disable)
        self.assertEqual(config.response_json_schema, Analysis.model_json_schema())

    def test_transient_failure_falls_back_after_three_primary_attempts(self):
        self.call.side_effect = [RemoteError(503), RemoteError(503), RemoteError(503), self.valid()]
        ai = Gateway()
        ai.generate("analysis", {}, Analysis)
        self.assertEqual([x.kwargs["model"] for x in self.call.call_args_list], ["primary"] * 3 + ["fallback"])
        self.assertEqual(ai.last_model, "fallback")
        self.assertEqual(self.clock, 7)
        self.assertEqual(len(ai.last_attempts), 4)

    def test_five_attempts_maximum_without_secret_in_error(self):
        self.call.side_effect = RemoteError(503)
        ai = Gateway()
        with self.assertRaises(GenerationError) as result:
            ai.generate("analysis", {}, Analysis)
        self.assertEqual(self.call.call_count, 5)
        self.assertEqual(len(result.exception.attempts), 5)
        self.assertNotIn("remote-secret", str(result.exception))
        self.assertIsNone(ai.last_model)

    def test_client_errors_are_not_retried_or_fallen_back(self):
        for code in (400, 401, 403, 404, 429):
            with self.subTest(code=code):
                self.call.reset_mock()
                self.call.side_effect = RemoteError(code)
                with self.assertRaises(GenerationError):
                    Gateway().generate("analysis", {}, Analysis)
                self.assertEqual(self.call.call_count, 1)

    def test_invalid_json_retries_once_and_never_falls_back(self):
        self.call.return_value = SimpleNamespace(text="not-json")
        ai = Gateway()
        with self.assertRaisesRegex(GenerationError, "JSON chưa đúng schema"):
            ai.generate("analysis", {}, Analysis)
        self.assertEqual(self.call.call_count, 2)

    def test_schema_retry_can_succeed(self):
        self.call.side_effect = [SimpleNamespace(text="{}"), self.valid()]
        self.assertEqual(Gateway().generate("analysis", {}, Analysis)["summary"], "Sản phẩm")
        self.assertEqual(self.call.call_count, 2)

    def test_deadline_prevents_another_request(self):
        def slow(**kwargs):
            self.clock += 179
            raise httpx.ReadTimeout("secret-url")
        self.call.side_effect = slow
        with self.assertRaises(GenerationError):
            Gateway().generate("analysis", {}, Analysis)
        self.assertEqual(self.call.call_count, 1)

    def test_duplicate_fallback_model_is_not_called_again(self):
        self.call.side_effect = RemoteError(503)
        with patch.dict("os.environ", {"GEMINI_FALLBACK_MODEL": "primary"}):
            with self.assertRaises(GenerationError):
                Gateway().generate("analysis", {}, Analysis)
        self.assertEqual(self.call.call_count, 3)
