"""
TESTS/TEST_LIVE_E2E_PIPELINE.PY
===============================
Acceptance Criteria: End-to-End Pipeline Compliance
- End-to-end execution of run_pipeline with a health/lifestyle product
  produces an output script that passes policy validation with 0 prohibited words
  and achieves qc_score >= 8.0.
"""

import json
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from agents.pipeline import run_pipeline
from knowledge_base.validator import validate_script

def run_live_e2e_test():
    sys.stdout.reconfigure(encoding="utf-8")
    print("=== STARTING LIVE END-TO-END PIPELINE EXECUTION ===")
    
    product_payload = {
        "name": "Trà Thảo Mộc Tâm An Miên",
        "brand_name": "Mộc An Natural",
        "price": "189000",
        "key_features": [
            "Chiết xuất 100% thảo mộc tự nhiên: tâm sen, lạc tiên, hoa cúc La Mã",
            "Hỗ trợ làm dịu tinh thần, giúp vào giấc ngủ tự nhiên và sâu hơn",
            "Hương vị thanh mát dễ uống, không đường, không chất bảo quản"
        ],
        "target_audience": "Người làm việc văn phòng căng thẳng, người khó ngủ, trằn trọc ban đêm",
        "product_link": "https://tiktok.com/@mocannatural/tra-tam-an-mien",
    }

    config = {
        "tone": "professional",
        "platform": "tiktok"
    }

    request_id = "live_e2e_health_test_01"
    print(f"Product: {product_payload['name']} ({product_payload['brand_name']})")
    print(f"Executing run_pipeline for request_id: {request_id}...")

    result = run_pipeline(request_id=request_id, product=product_payload, config=config)

    print("\n=== PIPELINE RESULT ===")
    print(f"Status: {result.get('status')}")
    print(f"Error: {result.get('error')}")

    metadata = result.get("metadata", {})
    print(f"Processing time: {metadata.get('processing_time_seconds')}s")
    print(f"Model used: {metadata.get('model_used')}")
    print("Log:")
    for l in metadata.get("log", []):
        print(f"  {l}")

    ai_result = result.get("ai_result", {})
    qc_score = ai_result.get("qc_score")
    policy_passed = ai_result.get("policy_passed")
    violations = ai_result.get("policy_violations", [])
    retry_count = ai_result.get("retry_count", 0)

    print(f"\nQC Score: {qc_score}")
    print(f"Policy Passed: {policy_passed}")
    print(f"Violations count: {len(violations)}")
    print(f"Retry count: {retry_count}")
    print(f"Hook Text: {ai_result.get('hook_text')}")
    print(f"Voice-over Text: {ai_result.get('voice_over_text')}")
    print(f"Text on screen: {ai_result.get('text_on_screen')}")
    print(f"Post caption: {ai_result.get('post_caption')}")
    print(f"Hashtags: {ai_result.get('hashtags')}")

    # Chạy độc lập Policy Validator để kiểm tra lại kết quả
    independent_val = validate_script(ai_result)
    print(f"\nIndependent Validator is_valid: {independent_val['is_valid']}")
    if not independent_val['is_valid']:
        print(f"Violations detected: {independent_val['violations']}")
        print(f"Banned words: {independent_val['banned_words_found']}")

    # Kiểm tra theo Acceptance Criteria
    assert result.get("status") == "success", f"Pipeline status is {result.get('status')}, expected 'success'!"
    assert qc_score is not None and qc_score >= 8.0, f"QC Score {qc_score} is less than 8.0!"
    assert policy_passed is True, "Pipeline reported policy_passed is not True!"
    assert len(violations) == 0, f"Pipeline reported {len(violations)} policy violations: {violations}"
    assert independent_val["is_valid"] is True, f"Independent validator found violations: {independent_val['violations']}"
    assert len(independent_val["banned_words_found"]) == 0, f"Banned words found: {independent_val['banned_words_found']}"

    print("\n>>> ACCEPTANCE CRITERIA MET: 100% SUCCESSFUL END-TO-END RUN <<<")
    return True

if __name__ == "__main__":
    success = run_live_e2e_test()
    if not success:
        sys.exit(1)
