"""
AGENTS/PIPELINE.PY
==================
LangGraph pipeline ket noi 4 Agent: Research -> Script -> Hashtag -> QC
Co vong lap tu dong sua loi neu QC < 8 diem (toi da 2 lan retry).
"""

import os
import sys
import time
import json
import re
from typing import TypedDict, List, Dict, Any
from dotenv import load_dotenv

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from knowledge_base.validator import validate_script
from knowledge_base.loader import (
    get_formatted_hooks_for_prompt,
    get_formatted_ctas_for_prompt,
    get_brand_guidelines_summary,
    get_policy_rules_summary,
)

_env_path = os.path.join(_project_root, ".env")
if os.path.exists(_env_path):
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

from google import genai
from google.genai import types
from langgraph.graph import StateGraph, START, END

# --- KHOI TAO GEMINI ---
_api_key = os.getenv("GEMINI_API_KEY")
_client = None


def get_client():
    """Lay hoac khoi tao Gemini client, ho tro lazy init tranh crash khi import."""
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("Thieu GEMINI_API_KEY trong file .env")
        _client = genai.Client(api_key=key)
    return _client


if _api_key:
    try:
        _client = genai.Client(api_key=_api_key)
    except Exception:
        _client = None
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]

QC_PASS_SCORE = 8.0
MAX_RETRY = 2  # Toi da 2 lan retry de Agent sua loi policy hoac QC


# --- TRANG THAI PIPELINE ---
class PipelineState(TypedDict):
    request_id: str
    product: dict
    config: dict
    research_result: str
    script_result: str
    hashtag_result: str
    qc_result: str
    qc_score: float
    policy_passed: bool
    policy_violations: list
    retry_count: int
    model_used: str
    log: list
    final_output: dict


# --- HAM GOI AI ---
def call_gemini(prompt: str) -> tuple[str, str]:
    """Goi Gemini API voi retry va fallback model. Tra ve (text, model_name)."""
    try:
        client = get_client()
    except Exception as e:
        return f'{{"error": "{str(e)}"}}', "none"

    for model in MODELS:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.7),
                )
                return response.text, model
            except Exception as e:
                err = str(e)
                if "503" in err or "UNAVAILABLE" in err:
                    time.sleep(2)
                elif "404" in err or "no longer" in err:
                    break  # Thu model tiep theo
                else:
                    if attempt < 2:
                        time.sleep(1)
    return '{"error": "Khong the goi AI"}', "none"


def parse_json(text: str) -> dict:
    """Trich xuat JSON tu response cua AI (co the bi boc bang markdown hoac co text xung quanh). Luon tra ve dict."""
    if not text or not isinstance(text, str):
        return {}

    def _ensure_dict(obj: Any) -> dict:
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list):
            if len(obj) == 1 and isinstance(obj[0], dict):
                return obj[0]
            return {"items": obj}
        return {"value": obj}

    stripped = text.strip()
    try:
        return _ensure_dict(json.loads(stripped))
    except Exception:
        pass

    # Tim block ```json ... ``` hoac ``` ... ```
    code_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if code_match:
        try:
            return _ensure_dict(json.loads(code_match.group(1).strip()))
        except Exception:
            pass

    # Tim khoang {...} lon nhat
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        try:
            return _ensure_dict(json.loads(brace_match.group(0).strip()))
        except Exception:
            pass

    # Neu brace_match that bai do co '{' trong preamble (vi du: "Doi voi {san pham}: {"key": "val"}"),
    # thu tim khoang tu cac '{' tiep theo den dau '}' cuoi cung
    for match in re.finditer(r"\{", text):
        start_idx = match.start()
        last_brace = text.rfind("}")
        if last_brace > start_idx:
            candidate = text[start_idx : last_brace + 1].strip()
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue

    # Fallback don dep code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    try:
        return _ensure_dict(json.loads(cleaned))
    except Exception:
        return {"raw": text}


# =============================================
# 4 AGENT NODES
# =============================================

def research_node(state: PipelineState) -> dict:
    """Agent 1: Phan tich san pham, tim insight va tich hop Knowledge Base."""
    product = state.get("product") or {}
    brand_summary = get_brand_guidelines_summary()
    hook_patterns = get_formatted_hooks_for_prompt(max_items=4)
    policy_summary = get_policy_rules_summary()

    raw_feat = product.get("key_features", [])
    feat_str = ", ".join(str(f) for f in raw_feat) if isinstance(raw_feat, list) else str(raw_feat or "")

    prompt = f"""Phan tich san pham sau cho video TikTok. Tra ve JSON thuan tuy, khong them text gi ngoai JSON.

San pham: {product.get('name', '')}
Thuong hieu: {product.get('brand_name', '')}
Gia: {product.get('price', '')} VND
Tinh nang chinh: {feat_str}
Doi tuong: {product.get('target_audience', '')}

{brand_summary}

GOI Y CAC GOC TIEP CAN HOOK (KNOWLEDGE BASE):
{hook_patterns}

{policy_summary}

Tra ve JSON:
{{
  "target_audience": {{"age_range": "", "gender": "", "occupation": "", "behavior": ""}},
  "usp": ["USP1", "USP2", "USP3"],
  "pain_points": ["Pain1", "Pain2"],
  "tiktok_angle": {{"primary": "Problem-Agitation / Curiosity / Statistics / Question", "hook_idea": ""}},
  "competitive_advantage": ""
}}
Ngon ngu: Tieng Viet, chuyen nghiep."""

    result, model = call_gemini(prompt)
    log = state.get("log", [])
    log.append(f"[Research] Done - model: {model}")
    return {
        "research_result": result,
        "model_used": model,
        "log": log,
    }


def script_node(state: PipelineState) -> dict:
    """Agent 2: Viet kich ban TikTok 30 giay dua tren insight va Knowledge Base."""
    product = state.get("product") or {}
    config = state.get("config", {})
    tone = config.get("tone", "professional")
    fix_note = ""

    # Neu dang retry, lay huong dan sua tu QC (bao gom chi tiet tu cam tu validator)
    if state.get("retry_count", 0) > 0:
        qc_data = parse_json(state.get("qc_result", "{}"))
        fix_instructions = qc_data.get("fix_instructions", "")
        if fix_instructions:
            fix_note = f"\n\nHUONG DAN SUA CHI TIET (TU QC & POLICY GUARDRAIL):\n{fix_instructions}"

    tone_note = "Chuyen nghiep, dang tin cay. KHONG dung tieng long." if tone == "professional" else "Tre trung, gan gui, dung tieng long nhe nhang."

    # Xac dinh angle tu research de lay hook library tuong ung
    research_raw = state.get("research_result", "")
    research_json = parse_json(research_raw)
    primary_angle = None
    if isinstance(research_json, dict):
        t_angle = research_json.get("tiktok_angle")
        if isinstance(t_angle, dict):
            primary_angle = t_angle.get("primary")
        elif isinstance(t_angle, str):
            primary_angle = t_angle

    hook_templates_str = get_formatted_hooks_for_prompt(angle=primary_angle, max_items=4)
    cta_templates_str = get_formatted_ctas_for_prompt(max_items=4)
    brand_summary = get_brand_guidelines_summary()
    policy_summary = get_policy_rules_summary()

    prompt = f"""Viet kich ban TikTok 30 giay. Tra ve JSON thuan tuy, khong them text gi ngoai JSON.

San pham: {product.get('name', '')}
Thuong hieu: {product.get('brand_name', '')}
Gia: {product.get('price', '')} VND
Link: {product.get('product_link', '')}
Nghien cuu: {research_raw[:600]}{fix_note}

{brand_summary}

{policy_summary}

MAU HOOK GOI Y (Tham khao de tao Hook hap dan trong 3 giay dau):
{hook_templates_str}

MAU CTA CHUAN TIKTOK SHOP (Dieu huong tu nhien vao gio hang vang):
{cta_templates_str}

Tra ve JSON:
{{
  "hook_text": "Cau mo dau, toi da 15 tu",
  "voice_over_text": "Toan bo loi thoai 30 giay ~ 85 tu",
  "text_on_screen": "Chu hien tren man hinh, ngan gon",
  "scenes": [
    {{"time": "0:00-0:03", "visual": "...", "audio": "..."}},
    {{"time": "0:03-0:25", "visual": "...", "audio": "..."}},
    {{"time": "0:25-0:30", "visual": "CTA - chi tay vao gio hang", "audio": "..."}}
  ],
  "image_generation_prompt_en": "English prompt for AI image, cinematic, 4k",
  "bgm_vibe": "Mo ta nhac nen",
  "post_caption": "Caption dang bai TikTok ngan gon co emoji"
}}
Giong dieu: {tone_note}
LUU Y DAC BIET: TUYET DOI KHONG dung cac tu cam TikTok Shop nhu: cam ket 100%, tri dut diem, chua khoi hoan toan, so 1, vinh vien, tuyet doi, an toan tuyet doi."""

    result, model = call_gemini(prompt)
    log = state.get("log", [])
    log.append(f"[Script] Done - retry#{state.get('retry_count', 0)} - model: {model}")
    return {
        "script_result": result,
        "model_used": model,
        "log": log,
    }


def hashtag_node(state: PipelineState) -> dict:
    """Agent 3: Tao hashtag SEO TikTok."""
    product = state.get("product") or {}
    policy_summary = get_policy_rules_summary()
    fix_note = ""

    # Neu dang retry, truyen huong dan sua tu QC & Policy de Agent loai bo tu cam
    if state.get("retry_count", 0) > 0:
        qc_data = parse_json(state.get("qc_result", "{}"))
        fix_instructions = qc_data.get("fix_instructions", "")
        if fix_instructions:
            fix_note = f"\n\nHUONG DAN SUA CHI TIET (TU QC & POLICY GUARDRAIL):\n{fix_instructions}\n"

    prompt = f"""Tao hashtag TikTok toi uu cho san pham. Tra ve JSON thuan tuy.

San pham: {product.get('name', '')}
Thuong hieu: {product.get('brand_name', '')}
Doi tuong: {product.get('target_audience', '')}{fix_note}

{policy_summary}

Tra ve JSON:
{{
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5", "#tag6"],
  "hashtag_string": "#tag1 #tag2 ...",
  "strategy_note": "Giai thich ngan"
}}
LUU Y DAC BIET: TUYET DOI KHONG tao hashtag chua tu cam nhu: #tridutdiem, #camket100, #so1, #thanduoc, #vinhvien."""

    result, model = call_gemini(prompt)
    log = state.get("log", [])
    log.append(f"[Hashtag] Done - model: {model}")
    return {
        "hashtag_result": result,
        "model_used": model,
        "log": log,
    }


def qc_node(state: PipelineState) -> dict:
    """Agent 4: Cham diem chat luong kich ban va thuc thi Policy Guardrail."""
    product = state.get("product") or {}
    script_data = parse_json(state.get("script_result", "{}"))
    hashtag_data = parse_json(state.get("hashtag_result", "{}"))
    hook = script_data.get("hook_text", "")
    voice_over = script_data.get("voice_over_text", "")

    # 1. Chay Deterministic Policy Guardrail Validator tren ca script lan hashtags
    full_data_to_validate = {**script_data} if isinstance(script_data, dict) else {}
    if isinstance(hashtag_data, dict):
        if "hashtags" in hashtag_data:
            full_data_to_validate["hashtags"] = hashtag_data["hashtags"]
        if "hashtag_string" in hashtag_data:
            full_data_to_validate["hashtag_string"] = hashtag_data["hashtag_string"]

    policy_check = validate_script(full_data_to_validate)
    policy_passed = policy_check["is_valid"]
    violations = policy_check["violations"]

    prompt = f"""Cham diem kich ban TikTok chuyen nghiep. Tra ve JSON thuan tuy.

Hook: {hook}
Voice-over: {voice_over[:400]}
San pham: {product.get('name', '')} - {product.get('brand_name', '')}

Tieu chi (moi tieu chi toi da 2 diem):
1. Hook: Gay chu y ngay 3 giay dau
2. USP ro rang: Diem noi bat san pham ro
3. CTA chat luong: Keu goi hanh dong ro rang, tu nhien, dung chinh sach gio hang
4. Dung tone: Chuyen nghiep, dang tin cay, khong dung tieng long
5. Chinh sach TikTok: KHONG vi pham tu cam (tri dut diem, cam ket 100%, so 1, vinh vien...)

Tra ve JSON:
{{
  "scores": {{"hook": 0, "usp_clarity": 0, "cta_quality": 0, "tone_match": 0, "policy_compliance": 0}},
  "qc_score": 0.0,
  "qc_passed": false,
  "qc_feedback": "Nhan xet ngan gon 1-2 cau",
  "issues": ["Van de 1 neu co"],
  "fix_instructions": "Huong dan cu the de Script Agent viet lai (neu qc_passed = false)"
}}
qc_passed = true neu qc_score >= {QC_PASS_SCORE}"""

    result, model = call_gemini(prompt)
    qc_data = parse_json(result)

    # 2. Ket hop ket qua tu Deterministic Policy Guardrail
    scores = qc_data.get("scores", {})
    if not isinstance(scores, dict):
        scores = {}

    issues = qc_data.get("issues", [])
    if not isinstance(issues, list):
        issues = [str(issues)] if issues else []

    existing_fix = qc_data.get("fix_instructions", "") or ""

    if not policy_passed:
        # Phat hien tu cam: ep diem policy = 0 va khoa khong cho pass
        scores["policy_compliance"] = 0
        policy_issues = [
            f"Vi pham tu cam TikTok '{v['word']}' tai {v['field']} ({v['category_name']})"
            for v in violations
        ]
        issues.extend(policy_issues)

        combined_fix = policy_check["fix_instructions"]
        if existing_fix and existing_fix != "Huong dan cu the de Script Agent viet lai (neu qc_passed = false)":
            combined_fix += f"\n\nBo sung tu QC Reviewer:\n{existing_fix}"

        qc_data["fix_instructions"] = combined_fix
        qc_data["issues"] = issues
        qc_data["qc_passed"] = False

        try:
            gemini_score = float(qc_data.get("qc_score", 0) or 0)
        except (ValueError, TypeError):
            gemini_score = 0.0
        # Ep diem toi da 5.0 khi co vi pham chinh sach nghiem trong de dam bao khong qua nguong 8.0
        score = min(gemini_score, 5.0)
        qc_data["qc_score"] = score
        qc_data["policy_violations"] = violations
    else:
        # Khong vi pham chinh sach
        try:
            score = float(qc_data.get("qc_score", 0) or 0)
        except (ValueError, TypeError):
            score = 0.0
        if "policy_compliance" not in scores or scores.get("policy_compliance") == 0:
            if score > 0:
                scores["policy_compliance"] = 2.0
        qc_data["policy_violations"] = []

    qc_data["scores"] = scores
    qc_data["policy_passed"] = policy_passed

    result_str = json.dumps(qc_data, ensure_ascii=False)
    log = state.get("log", [])
    log.append(f"[QC] Score={score} - Passed={score >= QC_PASS_SCORE and policy_passed} - PolicyPassed={policy_passed} - Violations={len(violations)} - model: {model}")
    return {
        "qc_result": result_str,
        "qc_score": score,
        "policy_passed": policy_passed,
        "policy_violations": violations,
        "model_used": model,
        "log": log,
    }


def should_retry(state: PipelineState) -> str:
    """Quyet dinh: Retry hay ket thuc?"""
    score = state.get("qc_score", 0)
    policy_passed = state.get("policy_passed", True)
    retry_count = state.get("retry_count", 0)

    if score >= QC_PASS_SCORE and policy_passed:
        return "pass"
    if retry_count < MAX_RETRY:
        return "retry"
    return "fail"


def increment_retry(state: PipelineState) -> dict:
    """Tang bien dem retry."""
    return {"retry_count": state.get("retry_count", 0) + 1}


def finalize(state: PipelineState) -> dict:
    """Dong goi du lieu cuoi cung."""
    policy_passed = state.get("policy_passed", True)
    policy_violations = state.get("policy_violations", [])
    try:
        script_data = parse_json(state.get("script_result", "{}"))
        hashtag_data = parse_json(state.get("hashtag_result", "{}"))
        qc_data = parse_json(state.get("qc_result", "{}"))
        qc_score = float(state.get("qc_score", 0) or 0)
        status = "success" if (qc_score >= QC_PASS_SCORE and policy_passed) else "failed"
    except Exception:
        script_data, hashtag_data, qc_data = {}, {}, {}
        qc_score = 0.0
        status = "failed"

    output = {
        "status": status,
        "ai_result": {
            "hook_text": script_data.get("hook_text", ""),
            "voice_over_text": script_data.get("voice_over_text", ""),
            "text_on_screen": script_data.get("text_on_screen", ""),
            "scenes": script_data.get("scenes", []),
            "image_prompt_en": script_data.get("image_generation_prompt_en", "") or script_data.get("image_prompt_en", ""),
            "bgm_vibe": script_data.get("bgm_vibe", ""),
            "post_caption": script_data.get("post_caption", ""),
            "hashtags": hashtag_data.get("hashtags", []),
            "hashtag_string": hashtag_data.get("hashtag_string", ""),
            "qc_score": qc_score,
            "qc_feedback": qc_data.get("qc_feedback", ""),
            "retry_count": state.get("retry_count", 0),
            "policy_passed": policy_passed,
            "policy_violations": policy_violations,
        },
    }

    log = state.get("log", [])
    log.append(f"[Final] status={status}, qc_score={qc_score}, policy_passed={policy_passed}")
    return {"final_output": output, "log": log}


# =============================================
# XAY GRAPH LANGGRAPH
# =============================================

_graph_builder = StateGraph(PipelineState)

_graph_builder.add_node("research", research_node)
_graph_builder.add_node("script", script_node)
_graph_builder.add_node("hashtag", hashtag_node)
_graph_builder.add_node("qc", qc_node)
_graph_builder.add_node("increment_retry", increment_retry)
_graph_builder.add_node("finalize", finalize)

_graph_builder.add_edge(START, "research")
_graph_builder.add_edge("research", "script")
_graph_builder.add_edge("script", "hashtag")
_graph_builder.add_edge("hashtag", "qc")

_graph_builder.add_conditional_edges(
    "qc",
    should_retry,
    {
        "pass": "finalize",
        "retry": "increment_retry",
        "fail": "finalize",
    },
)
_graph_builder.add_edge("increment_retry", "script")
_graph_builder.add_edge("finalize", END)

pipeline = _graph_builder.compile()


def run_pipeline(request_id: str, product: dict, config: dict = None) -> dict:
    """
    Chay pipeline AI cho 1 san pham.
    Tra ve dict chua request_id, status, ai_result, metadata.
    """
    import datetime

    if config is None:
        config = {"tone": "professional", "platform": "tiktok"}

    start_time = time.time()

    initial_state: PipelineState = {
        "request_id": request_id,
        "product": product,
        "config": config,
        "research_result": "",
        "script_result": "",
        "hashtag_result": "",
        "qc_result": "",
        "qc_score": 0.0,
        "policy_passed": True,
        "policy_violations": [],
        "retry_count": 0,
        "model_used": "",
        "log": [f"[Start] request_id={request_id}"],
        "final_output": {},  # Quan trong: phai khoi tao de LangGraph biet key nay ton tai
    }

    final_state = pipeline.invoke(initial_state)
    elapsed = round(time.time() - start_time, 1)

    output = final_state.get("final_output", {})
    return {
        "request_id": request_id,
        "status": output.get("status", "failed"),
        "ai_result": output.get("ai_result", {}),
        "metadata": {
            "processing_time_seconds": elapsed,
            "model_used": final_state.get("model_used", ""),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "log": final_state.get("log", []),
        },
        "error": None if output.get("status") == "success" else "QC_MAX_RETRY_EXCEEDED",
    }
