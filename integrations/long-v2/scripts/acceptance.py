"""Read-only acceptance checks. Never approve content, send a webhook, or publish."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import zipfile
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if (ROOT / "contracts").exists():
    from contracts.handoff_v2 import HandoffV2
else:
    sys.path.insert(0, str(ROOT / "python-service"))
    from app.contracts_v2 import HandoffV2


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def same_database(left, right):
    return str(left or "").replace("-", "").lower() == str(right or "").replace("-", "").lower()


def compare(bundle, receipt, readback, expected_database=None, archive=None):
    if not all(isinstance(value, dict) for value in (bundle, receipt, readback)):
        raise ValueError("Cần ba đối tượng JSON hợp lệ.")
    try:
        HandoffV2.model_validate(bundle)
    except ValueError:
        raise ValueError("Gói xuất không khớp schema v2.") from None
    digest = hashlib.sha256(canonical(bundle)).hexdigest()
    data = receipt.get("data") or {}
    if not isinstance(data, dict):
        raise ValueError("Biên nhận chưa đúng cấu trúc.")
    if receipt.get("success") is not True or not data.get("notion_page_id"):
        raise ValueError("Biên nhận chưa xác nhận lưu Notion thành công.")
    if data.get("request_id") != bundle["request_id"] or data.get("revision") != bundle["revision"]:
        raise ValueError("Biên nhận khác mã yêu cầu hoặc revision.")
    if data.get("payload_sha256") != digest:
        raise ValueError("SHA-256 trong biên nhận không khớp gói xuất.")
    if readback.get("success") is not True or readback.get("status") != "received":
        raise ValueError("Bản đọc lại chưa ở trạng thái received.")
    if readback.get("data") != bundle or readback.get("payload_sha256") != digest:
        raise ValueError("JSON đọc lại bị thiếu hoặc khác nội dung đã duyệt.")
    if expected_database and (not same_database(data.get("notion_database_id"), expected_database)
                              or not same_database(readback.get("notion_database_id"), expected_database)):
        raise ValueError("Biên nhận hoặc bản đọc lại không thuộc database thử đã chọn.")
    if archive:
        with zipfile.ZipFile(archive) as z:
            if json.loads(z.read("handoff.json")) != bundle:
                raise ValueError("JSON trong ZIP không trùng bản đã duyệt.")
            md = z.read("prompts.md").decode("utf-8")
            if any(scene["prompt_en"] not in md for scene in bundle["scenes"]):
                raise ValueError("Markdown thiếu hoặc cắt prompt.")
            for role, meta in (("product", bundle["product"]["images"][0]), ("character", bundle["character"]["image"])):
                names = [n for n in z.namelist() if n.startswith(role + ".") and "/" not in n]
                if len(names) != 1:
                    raise ValueError("ZIP thiếu ảnh hoặc có nhiều ảnh cùng vai trò: " + role)
                raw = z.read(names[0])
                if len(raw) != meta["size"] or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
                    raise ValueError("Ảnh trong ZIP khác ảnh đã duyệt: " + role)
    return {"technical_checks_passed": True, "request_id": bundle["request_id"], "revision": bundle["revision"],
            "payload_sha256": digest, "notion_page_id": data["notion_page_id"],
            "notion_database_id": data.get("notion_database_id"), "scene_count": len(bundle["scenes"]),
            "zip_images_checked": bool(archive), "manual_acceptance_complete": False,
            "still_requires": ["Bảo xác nhận clip Cảnh 2", "Long xác nhận Notion và lưu trữ sau restart", "Quân chốt biên bản"]}


def preflight(side):
    errors = []
    if side == "quan":
        if not os.getenv("GEMINI_API_KEY"):
            errors.append("Thiếu GEMINI_API_KEY.")
        url = urlsplit(os.getenv("WEBHOOK_V2_URL", ""))
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            errors.append("Thiếu URL HTTPS production v2 hợp lệ của Long.")
        if not os.getenv("WEBHOOK_V2_TOKEN", "").strip():
            errors.append("Thiếu WEBHOOK_V2_TOKEN; không đặt token trong URL hoặc chat.")
    else:
        target = os.getenv("NOTION_V2_DATABASE_ID", "").strip()
        primary = os.getenv("NOTION_DATABASE_ID", "").strip()
        token = os.getenv("NOTION_TOKEN", "").strip()
        if not target or "your_" in target:
            errors.append("Thiếu NOTION_V2_DATABASE_ID của database thử.")
        elif not primary or same_database(target, primary):
            errors.append("Cần khai báo database đang dùng và một database v2 thử khác nó.")
        if not token or "your_" in token:
            errors.append("Thiếu NOTION_TOKEN có quyền truy cập database thử.")
        if not errors:
            expected = {"request_id": "title", "product_name": "rich_text", "product_link": "url",
                        "hook_text": "rich_text", "voice_over_text": "rich_text", "text_on_screen": "rich_text",
                        "image_prompt_en": "rich_text", "post_caption": "rich_text", "hashtags": "rich_text",
                        "qc_score": "number", "qc_feedback": "rich_text", "status": "select"}
            request = Request("https://api.notion.com/v1/databases/" + target,
                              headers={"Authorization": "Bearer " + token, "Notion-Version": "2022-06-28"})
            try:
                with urlopen(request, timeout=15) as response:
                    properties = json.load(response).get("properties", {})
                for name, kind in expected.items():
                    if properties.get(name, {}).get("type") != kind:
                        errors.append("Sai hoặc thiếu cột " + name + " (cần " + kind + ").")
                options = properties.get("status", {}).get("select", {}).get("options", [])
                if "DRAFT" not in {v.get("name") for v in options}:
                    errors.append("Cột status chưa có lựa chọn DRAFT.")
            except HTTPError as exc:
                errors.append("Notion chưa đọc được database thử (HTTP " + str(exc.code) + ").")
            except (URLError, TimeoutError, ValueError):
                errors.append("Không kiểm tra được kết nối hoặc schema Notion.")
    return {"side": side, "configuration_ready": not errors, "errors": errors,
            "note": "Kiểm tra cấu hình/đọc schema; chưa gửi dữ liệu hoặc xác nhận nghiệm thu."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("preflight")
    check.add_argument("--side", choices=("quan", "long"), required=True)
    check = commands.add_parser("compare")
    for key in ("bundle", "receipt", "readback"):
        check.add_argument("--" + key, required=True)
    check.add_argument("--database-id")
    check.add_argument("--zip")
    args = parser.parse_args()
    load_dotenv(args.env_file, override=False)
    try:
        if args.command == "preflight":
            report = preflight(args.side)
            code = 0 if report["configuration_ready"] else 2
        else:
            read = lambda path: json.loads(Path(path).read_text(encoding="utf-8-sig"))
            report = compare(read(args.bundle), read(args.receipt), read(args.readback), args.database_id, args.zip)
            code = 0
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile):
        report = {"technical_checks_passed": False, "error": "Dữ liệu/bằng chứng không hợp lệ hoặc chưa khớp; không ghi nhận nghiệm thu."}
        code = 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
