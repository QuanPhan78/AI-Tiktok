"""
KNOWLEDGE_BASE/LOADER.PY
=========================
Module ho tro doc, cache va dinh dang du lieu tu Knowledge Base
(hooks_library, cta_templates, prohibited_words, brand guidelines)
de inject vao cac Agent prompts.
"""

import json
import os
from typing import Optional, List, Dict, Any

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_HOOKS_FILE = os.path.join(_BASE_DIR, "tiktok", "hooks_library.json")
_CTA_FILE = os.path.join(_BASE_DIR, "tiktok", "cta_templates.json")
_PROHIBITED_FILE = os.path.join(_BASE_DIR, "tiktok", "prohibited_words.json")
_GUIDELINES_FILE = os.path.join(_BASE_DIR, "brand", "guidelines.md")

_cache: Dict[str, Any] = {}


def load_hooks_library(force_reload: bool = False) -> Dict[str, Any]:
    """Doc thu vien hook templates."""
    if not force_reload and "hooks" in _cache:
        return _cache["hooks"]
    if not os.path.exists(_HOOKS_FILE):
        return {"categories": {}}
    with open(_HOOKS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    _cache["hooks"] = data
    return data


def load_cta_templates(force_reload: bool = False) -> Dict[str, Any]:
    """Doc thu vien CTA templates."""
    if not force_reload and "ctas" in _cache:
        return _cache["ctas"]
    if not os.path.exists(_CTA_FILE):
        return {"categories": {}}
    with open(_CTA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    _cache["ctas"] = data
    return data


def load_prohibited_words(force_reload: bool = False) -> Dict[str, Any]:
    """Doc danh sach tu cam va chinh sach TikTok Shop."""
    if not force_reload and "prohibited" in _cache:
        return _cache["prohibited"]
    if not os.path.exists(_PROHIBITED_FILE):
        return {"categories": {}}
    with open(_PROHIBITED_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    _cache["prohibited"] = data
    return data


def load_brand_guidelines(force_reload: bool = False) -> str:
    """Doc Brand Voice & Compliance Guidelines Markdown file."""
    if not force_reload and "guidelines" in _cache:
        return _cache["guidelines"]
    if not os.path.exists(_GUIDELINES_FILE):
        return ""
    with open(_GUIDELINES_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    _cache["guidelines"] = content
    return content


def get_formatted_hooks_for_prompt(angle: Optional[str] = None, max_items: int = 4) -> str:
    """
    Lay danh sach mau hook duoc dinh dang de truyen vao prompt.
    Neu chi dinh angle (vi du: 'Problem-Agitation', 'Curiosity', 'Statistics', 'Question'),
    uu tien lay templates tu category do.
    """
    data = load_hooks_library()
    categories = data.get("categories", {})
    if not categories:
        return ""

    lines = []
    selected_templates = []

    matched_cat = None
    if angle:
        norm_target = angle.lower().replace(" ", "").replace("-", "")
        for cat_key in categories:
            if cat_key.lower().replace(" ", "").replace("-", "") == norm_target:
                matched_cat = cat_key
                break

    if matched_cat and matched_cat in categories:
        cat_data = categories[matched_cat]
        selected_templates.extend(cat_data.get("templates", [])[:max_items])
    else:
        # Lay moi category 1-2 template
        for cat_key, cat_data in categories.items():
            temps = cat_data.get("templates", [])
            if temps:
                selected_templates.append(temps[0])
            if len(selected_templates) >= max_items:
                break

    for i, t in enumerate(selected_templates, 1):
        angle_name = t.get("angle", "")
        template = t.get("template", "")
        example = t.get("example", "")
        lines.append(f"{i}. [{angle_name}] Mau: \"{template}\" -> Vi du: \"{example}\"")

    return "\n".join(lines)


def get_formatted_ctas_for_prompt(max_items: int = 4) -> str:
    """
    Lay danh sach mau CTA tuant hu chinh sach de truyen vao prompt.
    """
    data = load_cta_templates()
    categories = data.get("categories", {})
    if not categories:
        return ""

    selected = []
    for cat_key, cat_data in categories.items():
        for t in cat_data.get("templates", []):
            selected.append(t)
            if len(selected) >= max_items:
                break
        if len(selected) >= max_items:
            break

    lines = []
    for i, t in enumerate(selected, 1):
        lines.append(f"{i}. \"{t.get('template', '')}\" ({t.get('compliance_note', '')})")

    return "\n".join(lines)


def get_brand_guidelines_summary() -> str:
    """
    Lay ban tom tat Brand Voice & Quy tac tuan thu de nhe prompt.
    """
    return (
        "NGUYEN TAC THUONG HIEU & GIONG DIEU:\n"
        "- Giong dieu: Chuyen nghiep, dang tin cay, dong cam, khoa hoc nhung de hieu. KHONG dung tieng long.\n"
        "- Quy tac y te & suc khoe: My pham / TPCN KHONG PHAI LA THUOC. KHONG dung tu ngu dieu tri/chua khoi.\n"
        "- Thay the hop le: Dung 'ho tro cai thien', 'giup giam', 'cham soc phuc hoi', 'dong hanh cung suc khoe'."
    )


def get_policy_rules_summary() -> str:
    """
    Lay tom tat cac tu cam quan trong nhat tren TikTok Shop VN.
    """
    prohibited_data = load_prohibited_words()
    categories = prohibited_data.get("categories", {})
    banned_samples = []
    for cat_data in categories.values():
        banned_samples.extend(cat_data.get("words", [])[:3])

    sample_str = ", ".join(f"'{w}'" for w in banned_samples[:10])
    return (
        "QUY TAC CHINH SACH QUANG CAO TIKTOK SHOP VN (BAT BUOC TUAN THU 100%):\n"
        f"- TUYET DOI KHONG dung cac tu cam va cam ket qua muc nhu: {sample_str}...\n"
        "- KHONG cam ket 100%, vinh vien, tri dut diem, so 1 hay khoi benh sau thoi gian ngan.\n"
        "- CTA phai ro rang, tu nhien, dieu huong hop le vao gio hang goc trai."
    )
