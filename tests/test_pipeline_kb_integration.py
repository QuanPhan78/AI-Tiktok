"""
TESTS/TEST_PIPELINE_KB_INTEGRATION.PY
=====================================
Automated test suite verifying:
1. R3: Dynamic injection of Knowledge Base assets into Research and Script prompts.
2. R3: Policy validator integration in QC stage triggering retry when prohibited words detected.
3. R3: Automated retry resolution with specific fix instructions detailing banned words.
4. Acceptance Criteria: End-to-End Pipeline Compliance
   - Execution of run_pipeline with a health/lifestyle product produces an output
     script that passes policy validation with 0 prohibited words and achieves qc_score >= 8.0.
"""

import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from agents.pipeline import (
    research_node,
    script_node,
    qc_node,
    should_retry,
    finalize,
    run_pipeline,
    PipelineState,
    QC_PASS_SCORE,
    MAX_RETRY,
)
from knowledge_base.validator import validate_script


class TestPipelineKnowledgeBaseIntegration(unittest.TestCase):
    """Kiem tra tich hop Knowledge Base va Policy Guardrails vao Pipeline."""

    def setUp(self):
        self.sample_product = {
            "name": "Trà Thảo Mộc Ngủ Ngon An Miên",
            "brand_name": "Mộc An Natural",
            "price": "189000",
            "key_features": ["Thành phần tâm sen và lạc tiên", "Hỗ trợ ngủ sâu giấc", "Vị thanh dịu dễ uống"],
            "target_audience": "Dân văn phòng, người thường xuyên căng thẳng khó ngủ",
            "product_link": "https://example.com/tra-an-mien",
        }

    def test_research_node_injects_brand_and_hooks(self):
        """Kiem tra research_node tiem Brand Guidelines va Hook Patterns vao prompt."""
        captured_prompts = []

        def mock_call_gemini(prompt: str):
            captured_prompts.append(prompt)
            return json.dumps({
                "target_audience": {"age_range": "25-40", "gender": "Cả hai"},
                "usp": ["Tâm sen và lạc tiên tự nhiên", "Hỗ trợ an thần tự nhiên", "Không hương liệu nhân tạo"],
                "pain_points": ["Khó vào giấc", "Tỉnh giấc giữa đêm"],
                "tiktok_angle": {"primary": "Problem-Agitation", "hook_idea": "Mất ngủ làm giảm năng suất làm việc"},
                "competitive_advantage": "Công thức thảo mộc truyền thống lành tính"
            }), "gemini-mock"

        with patch("agents.pipeline.call_gemini", side_effect=mock_call_gemini):
            state: PipelineState = {
                "request_id": "test_req_research",
                "product": self.sample_product,
                "config": {"tone": "professional"},
                "research_result": "",
                "script_result": "",
                "hashtag_result": "",
                "qc_result": "",
                "qc_score": 0.0,
                "policy_passed": True,
                "policy_violations": [],
                "retry_count": 0,
                "model_used": "",
                "log": [],
                "final_output": {},
            }
            res = research_node(state)
            self.assertTrue(len(captured_prompts) > 0)
            sent_prompt = captured_prompts[0]

            # Kiem tra da inject Brand Guidelines & Hook suggestions
            self.assertIn("NGUYEN TAC THUONG HIEU & GIONG DIEU", sent_prompt)
            self.assertIn("GOI Y CAC GOC TIEP CAN HOOK", sent_prompt)
            self.assertIn("QUY TAC CHINH SACH QUANG CAO TIKTOK SHOP VN", sent_prompt)

    def test_script_node_injects_hooks_ctas_and_policy(self):
        """Kiem tra script_node tiem Hook Templates, CTA Templates va Policy Rules."""
        captured_prompts = []

        def mock_call_gemini(prompt: str):
            captured_prompts.append(prompt)
            return json.dumps({
                "hook_text": "Nếu bạn hay trằn trọc mất ngủ, dừng ngay việc uống trà sữa muộn lại!",
                "voice_over_text": "Trà thảo mộc An Miên hỗ trợ giấc ngủ sâu hơn mỗi tối...",
                "text_on_screen": "Hỗ trợ ngủ sâu giấc",
                "scenes": [],
                "image_generation_prompt_en": "Calm chamomile tea on wooden desk",
                "bgm_vibe": "Relaxing lo-fi acoustic",
                "post_caption": "Bí quyết ngủ ngon 🌿 #traanmien"
            }), "gemini-mock"

        with patch("agents.pipeline.call_gemini", side_effect=mock_call_gemini):
            state: PipelineState = {
                "request_id": "test_req_script",
                "product": self.sample_product,
                "config": {"tone": "professional"},
                "research_result": json.dumps({"tiktok_angle": {"primary": "Problem-Agitation"}}),
                "script_result": "",
                "hashtag_result": "",
                "qc_result": "",
                "qc_score": 0.0,
                "policy_passed": True,
                "policy_violations": [],
                "retry_count": 0,
                "model_used": "",
                "log": [],
                "final_output": {},
            }
            res = script_node(state)
            self.assertTrue(len(captured_prompts) > 0)
            sent_prompt = captured_prompts[0]

            self.assertIn("MAU HOOK GOI Y", sent_prompt)
            self.assertIn("MAU CTA CHUAN TIKTOK SHOP", sent_prompt)
            self.assertIn("QUY TAC CHINH SACH QUANG CAO TIKTOK SHOP", sent_prompt)
            self.assertIn("TUYET DOI KHONG dung cac tu cam", sent_prompt)

    def test_qc_node_catches_prohibited_words_and_forces_retry(self):
        """Kiem tra khi kịch bản chứa từ cấm, QC node phát hiện và bắt buộc retry."""
        # Giả lập Script Agent vô tình tạo ra kịch bản chứa từ cấm
        bad_script = {
            "hook_text": "Sản phẩm số 1 Việt Nam cam kết 100% giúp ngủ ngay!",
            "voice_over_text": "Trà thảo mộc này trị dứt điểm mất ngủ kinh niên vĩnh viễn sau 1 đêm.",
            "text_on_screen": "Chữa khỏi hoàn toàn",
            "scenes": [
                {"time": "0:00-0:03", "visual": "Thần dược cho giấc ngủ", "audio": "An toàn tuyệt đối"}
            ],
            "post_caption": "Trị dứt điểm mất ngủ! #ngungon"
        }

        # Giả lập Gemini QC bất cẩn cho điểm cao 9.0
        mock_gemini_qc_response = json.dumps({
            "scores": {"hook": 2, "usp_clarity": 2, "cta_quality": 2, "tone_match": 1.5, "policy_compliance": 1.5},
            "qc_score": 9.0,
            "qc_passed": True,
            "qc_feedback": "Kịch bản nghe hấp dẫn",
            "issues": [],
            "fix_instructions": ""
        })

        with patch("agents.pipeline.call_gemini", return_value=(mock_gemini_qc_response, "gemini-mock")):
            state: PipelineState = {
                "request_id": "test_req_qc_fail",
                "product": self.sample_product,
                "config": {"tone": "professional"},
                "research_result": "",
                "script_result": json.dumps(bad_script),
                "hashtag_result": "",
                "qc_result": "",
                "qc_score": 0.0,
                "policy_passed": True,
                "policy_violations": [],
                "retry_count": 0,
                "model_used": "",
                "log": [],
                "final_output": {},
            }
            qc_output = qc_node(state)

            # Deterministic Policy Validator PHẢI chặn đứng, không cho pass:
            self.assertFalse(qc_output["policy_passed"])
            self.assertGreater(len(qc_output["policy_violations"]), 0)
            self.assertLess(qc_output["qc_score"], QC_PASS_SCORE)  # Bị ép xuống <= 5.0

            qc_data = json.loads(qc_output["qc_result"])
            self.assertFalse(qc_data["qc_passed"])
            self.assertEqual(qc_data["scores"]["policy_compliance"], 0)
            
            # Hướng dẫn sửa phải có chi tiết các từ cấm
            fix_instructions = qc_data["fix_instructions"]
            self.assertIn("trị dứt điểm", fix_instructions)
            self.assertIn("cam kết 100%", fix_instructions)
            self.assertIn("số 1", fix_instructions)

            # Kiểm tra should_retry phải trả về 'retry'
            updated_state = {**state, **qc_output}
            decision = should_retry(updated_state)
            self.assertEqual(decision, "retry")

    def test_pipeline_retry_loop_resolves_and_passes(self):
        """Kiem tra vong lap retry: Luot 1 vi pham -> QC bat loi -> Luot 2 sua xong -> Pass."""
        attempts = [0]

        def dynamic_gemini_call(prompt: str):
            if "Phan tich san pham sau" in prompt:
                return json.dumps({
                    "target_audience": {"age_range": "25-45"},
                    "usp": ["Tâm sen và lạc tiên", "Vị ngọt dịu tự nhiên"],
                    "pain_points": ["Khó ngủ"],
                    "tiktok_angle": {"primary": "Problem-Agitation", "hook_idea": "Mất ngủ kéo dài"},
                    "competitive_advantage": "Thảo mộc tự nhiên lành tính"
                }), "gemini-mock"

            elif "Viet kich ban TikTok" in prompt:
                attempts[0] += 1
                if attempts[0] == 1:
                    # Lần 1: Tạo kịch bản dính từ cấm
                    return json.dumps({
                        "hook_text": "Trà số 1 giúp trị dứt điểm mất ngủ!",
                        "voice_over_text": "Chúng tôi cam kết 100% ngủ ngay sau 1 đêm.",
                        "text_on_screen": "Trị dứt điểm",
                        "scenes": [{"time": "0:00-0:03", "visual": "Trà thảo mộc", "audio": "An toàn tuyệt đối"}],
                        "image_generation_prompt_en": "Herbal tea cup",
                        "bgm_vibe": "Calm",
                        "post_caption": "Trà ngủ ngon #ngungon"
                    }), "gemini-mock"
                else:
                    # Lần 2 (Retry): Đã đọc hướng dẫn sửa từ QC, loại bỏ từ cấm và dùng từ chuẩn
                    return json.dumps({
                        "hook_text": "Nếu bạn hay trằn trọc khó vào giấc mỗi đêm, dừng thói quen này lại!",
                        "voice_over_text": (
                            "Mất ngủ khiến ngày mới uể oải? Hãy thử ngay tách trà thảo mộc An Miên ấm áp này nhé. "
                            "Với tâm sen và lạc tiên tự nhiên, trà hỗ trợ làm dịu thần kinh và giúp bạn có giấc ngủ sâu hơn. "
                            "Thành phần lành tính, được rất nhiều người tin dùng mỗi tối."
                        ),
                        "text_on_screen": "Hỗ trợ giấc ngủ sâu tự nhiên",
                        "scenes": [
                            {"time": "0:00-0:03", "visual": "Người mệt mỏi nhìn đồng hồ", "audio": "Nếu bạn hay trằn trọc..."},
                            {"time": "0:03-0:25", "visual": "Rót trà thảo mộc bốc khói", "audio": "Với tâm sen và lạc tiên..."},
                            {"time": "0:25-0:30", "visual": "Chỉ tay vào giỏ hàng vàng", "audio": "Bấm ngay vào giỏ hàng góc trái để trải nghiệm hôm nay nhé!"}
                        ],
                        "image_generation_prompt_en": "Peaceful bedroom with cup of herbal tea, warm cozy light",
                        "bgm_vibe": "Acoustic chill relaxing",
                        "post_caption": "Bí quyết cho giấc ngủ trọn vẹn mỗi đêm 🌿 Bấm giỏ hàng góc trái nhé! #traanmien #ngungon"
                    }), "gemini-mock"

            elif "Tao hashtag TikTok" in prompt:
                return json.dumps({
                    "hashtags": ["#MocAnNatural", "#TraAnMien", "#TraNguNgon", "#HealthyLiving", "#ChamSocSucKhoe"],
                    "hashtag_string": "#MocAnNatural #TraAnMien #TraNguNgon #HealthyLiving #ChamSocSucKhoe",
                    "strategy_note": "Mix Brand + Nganh Hang + Trending"
                }), "gemini-mock"

            elif "Cham diem kich ban" in prompt:
                # Nếu kịch bản lần 2 chuẩn, cho điểm cao
                if attempts[0] == 1:
                    return json.dumps({
                        "scores": {"hook": 1, "usp_clarity": 1.5, "cta_quality": 1.5, "tone_match": 1.0, "policy_compliance": 0},
                        "qc_score": 5.0,
                        "qc_passed": False,
                        "qc_feedback": "Có từ cấm cần sửa",
                        "issues": ["Vi phạm từ cấm"],
                        "fix_instructions": "Xóa từ cấm"
                    }), "gemini-mock"
                else:
                    return json.dumps({
                        "scores": {"hook": 1.8, "usp_clarity": 1.8, "cta_quality": 1.8, "tone_match": 1.8, "policy_compliance": 1.8},
                        "qc_score": 9.0,
                        "qc_passed": True,
                        "qc_feedback": "Kịch bản xuất sắc, tuân thủ chính sách",
                        "issues": [],
                        "fix_instructions": ""
                    }), "gemini-mock"

            return "{}", "gemini-mock"

        with patch("agents.pipeline.call_gemini", side_effect=dynamic_gemini_call):
            result = run_pipeline("test_retry_success", self.sample_product)

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["error"], None)
            
            ai_res = result["ai_result"]
            self.assertGreaterEqual(ai_res["qc_score"], 8.0)
            self.assertEqual(ai_res["retry_count"], 1)
            self.assertTrue(ai_res["policy_passed"])
            self.assertEqual(len(ai_res["policy_violations"]), 0)

            # Xác thực lại kịch bản cuối cùng bằng validator độc lập
            val_final = validate_script(ai_res)
            self.assertTrue(val_final["is_valid"], f"Kịch bản cuối cùng vẫn còn vi phạm: {val_final['violations']}")

    def test_pipeline_exceeds_max_retry_when_violating_persistently(self):
        """Kiem tra khi kich ban lien tuc vi pham qua MAX_RETRY, pipeline ket thuc status='failed'."""
        bad_response = json.dumps({
            "hook_text": "Trị dứt điểm mất ngủ 100%!",
            "voice_over_text": "Cam kết 100% số 1 vĩnh viễn.",
            "text_on_screen": "Trị dứt điểm",
            "scenes": [],
            "image_generation_prompt_en": "Tea",
            "bgm_vibe": "Calm",
            "post_caption": "Trà"
        })

        def mock_call(prompt: str):
            if "Phan tich" in prompt:
                return json.dumps({"target_audience": {}, "usp": [], "pain_points": [], "tiktok_angle": {}, "competitive_advantage": ""}), "m"
            if "Viet kich ban" in prompt:
                return bad_response, "m"
            if "Tao hashtag" in prompt:
                return json.dumps({"hashtags": [], "hashtag_string": "", "strategy_note": ""}), "m"
            if "Cham diem" in prompt:
                return json.dumps({"scores": {}, "qc_score": 3.0, "qc_passed": False, "qc_feedback": "Fail", "issues": [], "fix_instructions": ""}), "m"
            return "{}", "m"

        with patch("agents.pipeline.call_gemini", side_effect=mock_call):
            res = run_pipeline("test_max_retry_fail", self.sample_product)
            self.assertEqual(res["status"], "failed")
            self.assertEqual(res["error"], "QC_MAX_RETRY_EXCEEDED")
            self.assertFalse(res["ai_result"]["policy_passed"])
            self.assertGreater(len(res["ai_result"]["policy_violations"]), 0)

    def test_qc_node_catches_prohibited_hashtags_and_triggers_retry(self):
        """Kiem tra khi Script Agent viet chuan nhung Hashtag Agent dinh tu cam, QC node phat hien va ep retry."""
        compliant_script = {
            "hook_text": "Nếu bạn khó ngủ mỗi tối, thử mẹo tự nhiên này nhé!",
            "voice_over_text": "Trà thảo mộc tâm sen và lạc tiên hỗ trợ giấc ngủ êm dịu, lành tính.",
            "text_on_screen": "Hỗ trợ ngủ sâu",
            "scenes": [],
            "post_caption": "Trà ngon ngủ tốt",
        }
        banned_hashtags = {
            "hashtags": ["#TraAnMien", "#tri_dut_diem", "#so_1"],
            "hashtag_string": "#TraAnMien #tri_dut_diem #so_1",
            "strategy_note": "mix"
        }

        mock_gemini_qc = json.dumps({
            "scores": {"hook": 2, "usp_clarity": 2, "cta_quality": 2, "tone_match": 2, "policy_compliance": 2},
            "qc_score": 10.0,
            "qc_passed": True,
            "qc_feedback": "Script tot",
            "issues": [],
            "fix_instructions": ""
        })

        with patch("agents.pipeline.call_gemini", return_value=(mock_gemini_qc, "gemini-mock")):
            state: PipelineState = {
                "request_id": "test_req_qc_hashtag_fail",
                "product": self.sample_product,
                "config": {"tone": "professional"},
                "research_result": "",
                "script_result": json.dumps(compliant_script),
                "hashtag_result": json.dumps(banned_hashtags),
                "qc_result": "",
                "qc_score": 0.0,
                "policy_passed": True,
                "policy_violations": [],
                "retry_count": 0,
                "model_used": "",
                "log": [],
                "final_output": {},
            }
            qc_output = qc_node(state)

            # QC node PHAI chan vi hashtags vi pham:
            self.assertFalse(qc_output["policy_passed"])
            self.assertGreater(len(qc_output["policy_violations"]), 0)
            flagged_fields = [v["field"] for v in qc_output["policy_violations"]]
            self.assertTrue(any("hashtags" in f for f in flagged_fields))
            self.assertLess(qc_output["qc_score"], QC_PASS_SCORE)

            updated_state = {**state, **qc_output}
            self.assertEqual(should_retry(updated_state), "retry")

    def test_parse_json_robustness_with_preamble_and_markdown(self):
        """Kiem tra parse_json xu ly thanh cong response Gemini co text preamble va markdown code blocks."""
        from agents.pipeline import parse_json

        # Case 1: Preamble + markdown json block + postamble
        raw_llm_text = (
            "Dưới đây là kịch bản video TikTok 30 giây bạn yêu cầu:\n\n"
            "```json\n"
            "{\n"
            '  "hook_text": "Vì sao bạn khó ngủ?",\n'
            '  "voice_over_text": "Giải pháp thảo mộc tự nhiên."\n'
            "}\n"
            "```\n\n"
            "Chúc bạn có một chiến dịch thành công!"
        )
        parsed = parse_json(raw_llm_text)
        self.assertIn("hook_text", parsed)
        self.assertEqual(parsed["hook_text"], "Vì sao bạn khó ngủ?")

        # Case 2: Outermost curly braces with commentary
        raw_commentary = (
            "Tôi đã phân tích sản phẩm. Đây là kết quả: "
            '{"target_audience": {"age_range": "20-35"}, "usp": ["usp1"]}. '
            "Hy vọng hữu ích!"
        )
        parsed2 = parse_json(raw_commentary)
        self.assertIn("target_audience", parsed2)
        self.assertEqual(parsed2["target_audience"]["age_range"], "20-35")

        # Case 3: Preamble with curly braces like {san pham} followed by valid JSON dict
        raw_preamble_braces = (
            "Đối với sản phẩm {Trà An Miên}: "
            '{"target_audience": {"age_range": "25-45"}, "usp": ["tự nhiên"]}\n'
            "Kịch bản kết thúc."
        )
        parsed3 = parse_json(raw_preamble_braces)
        self.assertIn("target_audience", parsed3)
        self.assertEqual(parsed3["target_audience"]["age_range"], "25-45")

    def test_hashtag_node_receives_fix_instructions_on_retry(self):
        """Kiem tra hashtag_node nhan duoc fix_instructions tu QC khi retry_count > 0."""
        from agents.pipeline import hashtag_node

        captured_prompts = []

        def mock_call_gemini(prompt: str):
            captured_prompts.append(prompt)
            return json.dumps({
                "hashtags": ["#TraAnMien", "#HealthyLiving"],
                "hashtag_string": "#TraAnMien #HealthyLiving",
                "strategy_note": "Clean tags"
            }), "gemini-mock"

        with patch("agents.pipeline.call_gemini", side_effect=mock_call_gemini):
            mock_qc_fix = json.dumps({
                "qc_score": 4.0,
                "qc_passed": False,
                "fix_instructions": "Xóa bỏ hoàn toàn từ cấm 'trị dứt điểm' trong hashtags."
            })
            state: PipelineState = {
                "request_id": "test_hashtag_retry_note",
                "product": self.sample_product,
                "config": {"tone": "professional"},
                "research_result": "",
                "script_result": "{}",
                "hashtag_result": "",
                "qc_result": mock_qc_fix,
                "qc_score": 4.0,
                "policy_passed": False,
                "policy_violations": [],
                "retry_count": 1,  # Đang retry
                "model_used": "",
                "log": [],
                "final_output": {},
            }
            res = hashtag_node(state)
            self.assertTrue(len(captured_prompts) > 0)
            sent_prompt = captured_prompts[0]
            self.assertIn("HUONG DAN SUA CHI TIET (TU QC & POLICY GUARDRAIL)", sent_prompt)
            self.assertIn("trị dứt điểm", sent_prompt)

    def test_parse_json_list_response_does_not_crash_qc_node(self):
        """Kiem tra khi Gemini tra ve JSON array [...] chu khong phai object {...}, parse_json va qc_node van hoat dong an toan."""
        raw_list_script = json.dumps([
            {
                "hook_text": "Mẹo ngủ ngon tự nhiên mỗi tối",
                "voice_over_text": "Trà thảo mộc tâm sen và lạc tiên hỗ trợ thư giãn.",
                "text_on_screen": "Hỗ trợ ngủ ngon",
                "scenes": [],
                "post_caption": "Trà ngủ ngon #healthy"
            }
        ])

        mock_qc_score = json.dumps({
            "scores": {"hook": 2, "usp_clarity": 2, "cta_quality": 2, "tone_match": 2, "policy_compliance": 2},
            "qc_score": 9.0,
            "qc_passed": True,
            "qc_feedback": "Tot",
            "issues": [],
            "fix_instructions": ""
        })

        with patch("agents.pipeline.call_gemini", return_value=(mock_qc_score, "gemini-mock")):
            state: PipelineState = {
                "request_id": "test_list_script",
                "product": self.sample_product,
                "config": {"tone": "professional"},
                "research_result": "",
                "script_result": raw_list_script,
                "hashtag_result": json.dumps({"hashtags": ["#tag1"]}),
                "qc_result": "",
                "qc_score": 0.0,
                "policy_passed": True,
                "policy_violations": [],
                "retry_count": 0,
                "model_used": "",
                "log": [],
                "final_output": {},
            }
            # Khong duoc throw TypeError: 'list' object is not a mapping
            qc_output = qc_node(state)
            self.assertTrue(qc_output["policy_passed"])
            self.assertEqual(qc_output["qc_score"], 9.0)

    def test_pipeline_empty_product_resilience(self):
        """Kiem tra pipeline xu ly an toan khi product rong hoac thieu truong, khong vang KeyError."""
        def mock_call(prompt: str):
            if "Phan tich" in prompt:
                return json.dumps({"target_audience": {}, "usp": [], "pain_points": [], "tiktok_angle": {}, "competitive_advantage": ""}), "m"
            if "Viet kich ban" in prompt:
                return json.dumps({
                    "hook_text": "San pham tot",
                    "voice_over_text": "Ho tro suc khoe tu nhien",
                    "text_on_screen": "Tot",
                    "scenes": [],
                    "post_caption": "Caption"
                }), "m"
            if "Tao hashtag" in prompt:
                return json.dumps({"hashtags": ["#tag"], "hashtag_string": "#tag", "strategy_note": ""}), "m"
            if "Cham diem" in prompt:
                return json.dumps({"scores": {}, "qc_score": 8.5, "qc_passed": True, "qc_feedback": "OK", "issues": [], "fix_instructions": ""}), "m"
            return "{}", "m"

        with patch("agents.pipeline.call_gemini", side_effect=mock_call):
            empty_product = {}
            res = run_pipeline("test_empty_product", empty_product)
            self.assertEqual(res["status"], "success")
            self.assertGreaterEqual(res["ai_result"]["qc_score"], 8.0)


if __name__ == "__main__":
    unittest.main()
