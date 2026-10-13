"""
API/MAIN.PY
===========
FastAPI server nhan request tu Automation (Long) va tra ve ket qua AI.

Endpoints:
  POST /generate            <- Long gui JSON san pham vao day (Async background execution)
  GET  /health              <- Kiem tra server con song
  GET  /status/{request_id} <- Xem log cua 1 request
"""

import os
import sys
import time
import re
import logging
import threading
from datetime import datetime, timezone
from typing import Optional, List, Any

from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_path):
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.pipeline import run_pipeline

# --- LOGGING CONFIG ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("api.main")

# --- KHOI TAO APP ---
app = FastAPI(
    title="TikTok AI Agent API",
    description="He thong AI tu dong tao kich ban TikTok tu thong tin san pham.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Luu log cac request da chay (trong RAM, du dung de test)
_request_log: dict = {}
_active_threads: dict = {}
_state_lock: threading.Lock = threading.Lock()

DEFAULT_WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:5678/webhook/ai-agent-callback")
MAX_REQUEST_LOG_SIZE = 1000


# --- DATA MODELS (dinh nghia cau truc JSON) ---
class ProductInput(BaseModel):
    name: Optional[str] = None
    product_name: Optional[str] = None
    price: Optional[Any] = ""
    brand_name: Optional[str] = ""
    key_features: Optional[Any] = []
    target_audience: Optional[str] = ""
    product_link: Optional[str] = ""

    def get_effective_name(self) -> str:
        return str(self.name or self.product_name or "").strip()

    def get_effective_price(self) -> str:
        if self.price is None:
            return ""
        return str(self.price).strip()

    def get_effective_key_features(self) -> List[str]:
        if isinstance(self.key_features, list):
            return [str(f).strip() for f in self.key_features if f is not None and str(f).strip()]
        if isinstance(self.key_features, str):
            return [f.strip() for f in self.key_features.split(",") if f.strip()]
        return []


class ConfigInput(BaseModel):
    video_duration_seconds: int = 30
    tone: str = "professional"  # professional | gen_z
    platform: str = "tiktok"
    webhook_url: Optional[str] = None


class GenerateRequest(BaseModel):
    request_id: str
    product: Optional[ProductInput] = None
    # Ho tro ca cac truong phang o root payload (Notion intake style)
    name: Optional[str] = None
    product_name: Optional[str] = None
    price: Optional[Any] = ""
    brand_name: Optional[str] = ""
    key_features: Optional[Any] = []
    target_audience: Optional[str] = ""
    product_link: Optional[str] = ""
    config: Optional[ConfigInput] = None
    webhook_url: Optional[str] = None


# --- HELPER FUNCTIONS ---
def get_webhook_url(request: GenerateRequest) -> str:
    """Xac dinh webhook URL uu tien: request body -> config -> env -> default."""
    if request.webhook_url and request.webhook_url.strip():
        return request.webhook_url.strip()
    if request.config and request.config.webhook_url and request.config.webhook_url.strip():
        return request.config.webhook_url.strip()
    env_url = os.getenv("WEBHOOK_URL")
    if env_url and env_url.strip():
        return env_url.strip()
    return DEFAULT_WEBHOOK_URL


def build_webhook_payload(
    request_id: str,
    status: str,
    raw_ai_result: Optional[dict] = None,
    raw_metadata: Optional[dict] = None,
    error: Optional[Any] = None,
    start_time: Optional[float] = None,
) -> dict:
    """
    Dong goi JSON payload gui ve n8n webhook callback tuan thu nghiem ngat
    theo schema tai Step 4 API contract (api-contract-step4.md).
    """
    if raw_ai_result is None:
        raw_ai_result = {}
    if raw_metadata is None:
        raw_metadata = {}

    # Chuan hoa hashtags: ho tro list, chuoi phan tach boi dau phay hoac khoang trang,
    # ho tro hashtag_string fallback, va dam bao tat ca tag deu co 1 tien to '#' duy nhat
    hashtags = raw_ai_result.get("hashtags") or raw_ai_result.get("hashtag_string")
    if isinstance(hashtags, list):
        raw_tags = [str(tag) for tag in hashtags if tag is not None]
    elif isinstance(hashtags, str):
        raw_tags = [tag.strip() for tag in re.split(r"[,\s]+", hashtags) if tag.strip()]
    else:
        raw_tags = []

    formatted_hashtags = []
    seen = set()
    for t in raw_tags:
        cleaned = t.strip()
        core = cleaned.lstrip("#").strip()
        if not core:
            continue
        tag = f"#{core}"
        if tag.lower() not in seen:
            seen.add(tag.lower())
            formatted_hashtags.append(tag)

    # Chuan hoa qc_score
    try:
        qc_score = round(float(raw_ai_result.get("qc_score", 0.0) or 0.0), 2)
    except (ValueError, TypeError):
        qc_score = 0.0

    # Chuan hoa retry_count
    try:
        retry_count = max(0, int(raw_ai_result.get("retry_count", 0) or 0))
    except (ValueError, TypeError):
        retry_count = 0

    image_prompt = (
        raw_ai_result.get("image_prompt_en")
        or raw_ai_result.get("image_generation_prompt_en")
        or raw_ai_result.get("image_prompt")
        or raw_ai_result.get("image_generation_prompt")
        or ""
    )

    ai_result = {
        "hook_text": str(raw_ai_result.get("hook_text", "") or ""),
        "voice_over_text": str(raw_ai_result.get("voice_over_text", "") or ""),
        "text_on_screen": str(raw_ai_result.get("text_on_screen", "") or ""),
        "image_prompt_en": str(image_prompt or ""),
        "bgm_vibe": str(raw_ai_result.get("bgm_vibe", "") or ""),
        "post_caption": str(raw_ai_result.get("post_caption", "") or ""),
        "hashtags": formatted_hashtags,
        "qc_score": qc_score,
        "qc_feedback": str(raw_ai_result.get("qc_feedback", "") or ""),
        "retry_count": retry_count,
    }

    # Chuan hoa processing_time_seconds
    raw_proc_time = raw_metadata.get("processing_time_seconds")
    if raw_proc_time is not None:
        try:
            proc_seconds = max(0, int(round(float(raw_proc_time))))
        except (ValueError, TypeError):
            proc_seconds = max(0, int(round(time.time() - start_time))) if start_time else 0
    elif start_time:
        proc_seconds = max(0, int(round(time.time() - start_time)))
    else:
        proc_seconds = 0

    raw_created = raw_metadata.get("created_at")
    if raw_created and isinstance(raw_created, str) and raw_created.strip():
        created_at = raw_created.strip()
    else:
        created_at = datetime.now(timezone.utc).isoformat()

    metadata = {
        "processing_time_seconds": proc_seconds,
        "model_used": str(raw_metadata.get("model_used", "") or ""),
        "created_at": str(created_at),
    }

    # Chuan hoa error: Step 4 contract yeu cau null khi thanh cong
    # Python-service yeu cau Optional[dict]
    norm_status = str(status).strip().lower()
    if norm_status == "success":
        formatted_error = None
    elif error is None:
        formatted_error = {"message": "Pipeline execution failed"}
    elif isinstance(error, dict):
        formatted_error = error
    else:
        formatted_error = {"message": str(error)}

    return {
        "request_id": str(request_id),
        "status": norm_status,
        "ai_result": ai_result,
        "metadata": metadata,
        "error": formatted_error,
    }


def send_webhook(
    webhook_url: str,
    payload: dict,
    timeout: float = 15.0,
    max_retries: int = 2,
) -> tuple[bool, Optional[int], Optional[str]]:
    """
    Gui POST request voi JSON payload den webhook (n8n callback).
    Tra ve (success, status_code, error_message).
    - success la True CHI KHI nhan duoc HTTP 2xx response tu webhook.
    - Neu status code >= 400 hoac co exception, success la False va co error_message.
    """
    cleaned_url = webhook_url.strip() if webhook_url else ""
    if not cleaned_url or not cleaned_url.startswith(("http://", "https://")):
        err_msg = f"Invalid webhook URL protocol: {webhook_url}"
        logger.error(err_msg)
        return False, None, err_msg

    logger.info(f"Bat dau gui webhook den: {cleaned_url} cho request_id={payload.get('request_id')}")
    last_status = None
    last_error = None

    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    cleaned_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                last_status = resp.status_code
                if resp.is_success:
                    logger.info(f"Webhook response status: {resp.status_code} (Success)")
                    return True, resp.status_code, None
                else:
                    err_text = resp.text[:300] if resp.text else f"Status code {resp.status_code}"
                    last_error = f"HTTP {resp.status_code}: {err_text}"
                    logger.warning(f"Webhook attempt {attempt + 1} returned error: {last_error}")
                    # Neu la loi client 4xx (400, 404, etc.) thi khong can retry
                    if 400 <= resp.status_code < 500:
                        return False, resp.status_code, last_error
        except Exception as e:
            logger.error(f"Loi khi gui webhook den {cleaned_url} (attempt {attempt + 1}): {e}")
            last_error = str(e)
            last_status = None

        if attempt < max_retries - 1:
            time.sleep(0.5)

    return False, last_status, last_error


def run_pipeline_background(
    request_id: str,
    product_dict: dict,
    config_dict: dict,
    webhook_url: str,
    start_time: float,
):
    """
    Chay pipeline AI trong background thread va gui callback ve webhook khi hoan thanh.
    Xu ly tat ca truong hop thanh cong hoac loi ngoai le, va luon don dep thread khi ket thuc.
    """
    logger.info(f"[Background] Bat dau pipeline cho request_id={request_id}")
    try:
        try:
            # Chay LangGraph pipeline
            result = run_pipeline(
                request_id=request_id,
                product=product_dict,
                config=config_dict,
            )

            pipeline_status = result.get("status", "failed")
            raw_ai_result = result.get("ai_result", {})
            raw_metadata = result.get("metadata", {})
            raw_error = result.get("error")

            # Cap nhat log
            with _state_lock:
                _request_log[request_id] = {
                    "status": pipeline_status,
                    "result": result,
                    "finished_at": time.time(),
                }

            # Dong goi webhook payload theo Step 4 contract
            webhook_payload = build_webhook_payload(
                request_id=request_id,
                status=pipeline_status,
                raw_ai_result=raw_ai_result,
                raw_metadata=raw_metadata,
                error=raw_error,
                start_time=start_time,
            )

        except Exception as e:
            logger.error(f"[Background] Loi khi chay pipeline cho request_id={request_id}: {e}")
            elapsed = round(time.time() - start_time, 1)

            with _state_lock:
                _request_log[request_id] = {
                    "status": "failed",
                    "error": str(e),
                    "finished_at": time.time(),
                }

            webhook_payload = build_webhook_payload(
                request_id=request_id,
                status="failed",
                raw_ai_result={},
                raw_metadata={
                    "processing_time_seconds": int(round(elapsed)),
                    "model_used": "none",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                error={"message": str(e)},
                start_time=start_time,
            )

        # Gui ket qua toi webhook (bat ke thanh cong hay that bai)
        try:
            success, status_code, err_msg = send_webhook(webhook_url, webhook_payload)
        except Exception as exc:
            logger.error(f"[Background] Ngoai le khi gui webhook cho request_id={request_id}: {exc}")
            success, status_code, err_msg = False, None, str(exc)

        with _state_lock:
            if request_id in _request_log:
                _request_log[request_id]["webhook_sent"] = success
                _request_log[request_id]["webhook_status_code"] = status_code
                if err_msg:
                    _request_log[request_id]["webhook_error"] = err_msg
                _request_log[request_id]["webhook_payload"] = webhook_payload

    finally:
        with _state_lock:
            _active_threads.pop(request_id, None)


# --- ENDPOINTS ---

@app.get("/health")
def health_check():
    """Kiem tra server con song. Long goi endpoint nay de biet API ready chua."""
    return {
        "status": "ok",
        "message": "TikTok AI Agent dang chay",
        "version": "1.0.0",
    }


@app.post("/generate")
def generate_script(request: GenerateRequest):
    """
    Nhan thong tin san pham, khoi chay pipeline 4 AI Agent duoi dang background task,
    tra ve phan hoi ngay lap tuc (< 5 giay) de tranh n8n timeout.
    Ket qua cuoi cung se duoc ban ve webhook callback cua Long qua POST.
    """
    if not request.request_id or not request.request_id.strip():
        raise HTTPException(
            status_code=400,
            detail="request_id is required and cannot be empty",
        )

    req_id = request.request_id.strip()
    start = time.time()

    # Kiem tra request dang chay de tranh chay trung lap
    with _state_lock:
        if req_id in _active_threads and _active_threads[req_id].is_alive():
            logger.warning(f"Request {req_id} is already actively running. Returning processing status.")
            return {
                "request_id": req_id,
                "status": "processing",
                "message": "AI pipeline already running in background",
            }

    # Chuan hoa va merge thong tin san pham tu ca nested va flat root payload
    p = request.product or ProductInput()
    eff_name = (
        p.get_effective_name()
        or str(request.name or request.product_name or "").strip()
    )
    if not eff_name:
        raise HTTPException(
            status_code=400,
            detail="product name is required and cannot be empty",
        )

    eff_price = (
        p.get_effective_price()
        or (str(request.price).strip() if request.price is not None else "")
    )
    eff_brand = str(p.brand_name or request.brand_name or "").strip()
    eff_link = str(p.product_link or request.product_link or "").strip()
    eff_audience = str(p.target_audience or request.target_audience or "").strip()

    nested_feats = p.get_effective_key_features()
    if nested_feats:
        eff_features = nested_feats
    elif isinstance(request.key_features, list):
        eff_features = [str(f).strip() for f in request.key_features if f is not None and str(f).strip()]
    elif isinstance(request.key_features, str):
        eff_features = [f.strip() for f in request.key_features.split(",") if f.strip()]
    else:
        eff_features = []

    product_dict = {
        "name": eff_name,
        "product_name": eff_name,
        "price": eff_price,
        "brand_name": eff_brand,
        "key_features": eff_features,
        "target_audience": eff_audience,
        "product_link": eff_link,
    }
    config_dict = request.config.model_dump() if request.config else {}

    # Xac dinh webhook URL
    webhook_url = get_webhook_url(request)

    # Don dep threads cu de tranh ro ri bo nho va luu trang thai
    with _state_lock:
        dead_keys = [k for k, t in _active_threads.items() if not t.is_alive()]
        for k in dead_keys:
            del _active_threads[k]

        # Gioi han kich thuoc _request_log tranh tran bo nho
        if len(_request_log) >= MAX_REQUEST_LOG_SIZE:
            for k in list(_request_log.keys())[:100]:
                _request_log.pop(k, None)

        _request_log[req_id] = {
            "status": "processing",
            "started_at": start,
        }

    # Khoi chay background thread
    thread = threading.Thread(
        target=run_pipeline_background,
        args=(
            req_id,
            product_dict,
            config_dict,
            webhook_url,
            start,
        ),
        daemon=True,
    )
    thread.start()

    with _state_lock:
        _active_threads[req_id] = thread

    return {
        "request_id": req_id,
        "status": "processing",
        "message": "AI pipeline started in background",
    }


@app.get("/status/{request_id}")
def get_status(request_id: str):
    """
    Xem trang thai va log cua 1 request theo request_id.
    Long co the goi endpoint nay de biet request dang xu ly den dau.
    """
    req_id = request_id.strip()
    with _state_lock:
        if req_id not in _request_log:
            raise HTTPException(
                status_code=404,
                detail=f"Khong tim thay request_id: {req_id}",
            )
        return dict(_request_log[req_id])


@app.get("/")
def root():
    return {
        "message": "TikTok AI Agent API",
        "docs": "/docs",
        "health": "/health",
        "generate": "POST /generate",
    }
