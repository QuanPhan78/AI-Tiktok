"""
KNOWLEDGE_BASE/VALIDATOR.PY
============================
Deterministic Policy Guardrail Validator cho TikTok Shop VN.
Kiem tra nhanh, xac dinh (khong can LLM) cac tu cam va vi pham chinh sach
trong kich ban video TikTok.
Ho tro Unicode NFD/NFC, khong phan biet hoa/thuong, khong dau (unaccented),
tu phan tach/xuong dong, leetspeak xen dau cau (t.r.i, tr.i) va hashtag lien tu (#tridutdiem).
"""

import os
import re
import json
import unicodedata
from typing import Dict, List, Any, Optional, Union

from .loader import load_prohibited_words


def remove_vietnamese_diacritics(text: str) -> str:
    """
    Chuyen doi van ban tieng Viet co dau thanh khong dau (ASCII).
    Xu ly ca d/D dac thu cua tieng Viet va toan bo to hop dau thanh.
    """
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", stripped)


def deobfuscate_text(text: str) -> str:
    """
    Loai bo cac ky tu phan tach xen giua cac chu cai de phong chong bypass leetspeak.
    Vi du: tr.ị -> trị, t-r-ị -> trị, k.h.ỏ.i -> khỏi, t-r-i-d-u-t-d-i-e-m -> tridutdiem
    Ho tro ca dau lap (-- , ..), dau co khoang trang xung quanh (t - r - i), va chu cai cach nhau bang space (t r i).
    """
    if not text:
        return ""
    # 1. Xoa cac dau phan tach (cham, gach, sao, nga, gach cheo, gach dung) co the kem khoang trang nam giua 2 ky tu chu cai
    cleaned = re.sub(r"(?<=[^\W\d_])\s*[._\-*~,:|/\\]+\s*(?=[^\W\d_])", "", text, flags=re.UNICODE)
    # 2. Gop cac chu cai don le dung cach nhau bang khoang trang (vi du: t r i d u t d i e m -> tridutdiem)
    cleaned = re.sub(r"(?<=\b[^\W\d_])\s+(?=[^\W\d_]\b)", "", cleaned, flags=re.UNICODE)
    return cleaned


class PolicyValidator:
    """
    Validator kiem tra kieu deterministic cac tu khoa vi pham chinh sach quang cao TikTok Shop.
    """

    def __init__(self, prohibited_data: Optional[Dict[str, Any]] = None):
        if prohibited_data is None:
            prohibited_data = load_prohibited_words()
        self.prohibited_data = prohibited_data
        self.rules: List[Dict[str, Any]] = []
        self._compile_rules()

    def _compile_single_pattern(self, phrase_str: str) -> Optional[re.Pattern]:
        """Bien dich 1 cum tu thanh regex pattern linh hoat."""
        parts = phrase_str.split()
        if not parts:
            return None

        is_start_word = bool(re.match(r"^\w", phrase_str, re.UNICODE))
        is_end_word = bool(re.search(r"\w$", phrase_str, re.UNICODE))

        lookbehind = r"(?<![^\W_])" if is_start_word else r""
        lookahead = r"(?![^\W_])" if is_end_word else r""

        # Cho phep cac tu trong cum tu phan tach boi khoang trang, dau cau, hoac lien nhau (trong hashtag)
        sep = r"[\s\-_:.,/()~*|+?!]*"
        non_space_sep = r"[\-_:.,/()~*|+?!]*"

        if parts[-1].endswith("%") and len(parts) > 1:
            core = parts[-1][:-1]
            prev_parts = []
            for p in parts[:-1]:
                if p.startswith("100%"):
                    tail = p[4:]
                    prev_parts.append(rf"100%?{re.escape(tail)}" if tail else r"100%?")
                elif p.endswith("%"):
                    c = p[:-1]
                    prev_parts.append(rf"{re.escape(c)}%?")
                else:
                    prev_parts.append(re.escape(p))

            # Nhanh 1: Co ky tu '%' o cuoi (cho phep khoang trang va dau cau giua cac tu, va truoc %)
            pat_with_pct = sep.join(prev_parts + [rf"{re.escape(core)}\s*%"])
            # Nhanh 2: Khong co ky tu '%' o cuoi - chi ap dung cho hashtag/tu lien khong khoang trang (vi du #camket100, #hieuqua100)
            pat_unspaced = non_space_sep.join(prev_parts + [rf"{re.escape(core)}(?![^\W_])"])
            body_pattern = rf"(?:{pat_with_pct}|{pat_unspaced})"
        else:
            escaped_parts = []
            for i, p in enumerate(parts):
                if p.endswith("%"):
                    core = p[:-1]
                    escaped_parts.append(rf"{re.escape(core)}\s*%" if i == len(parts) - 1 else rf"{re.escape(core)}%?")
                elif p.startswith("100%"):
                    tail = p[4:]
                    escaped_parts.append(rf"100%?{re.escape(tail)}" if tail else r"100%?")
                else:
                    escaped_parts.append(re.escape(p))
            body_pattern = sep.join(escaped_parts)
        pattern_str = rf"{lookbehind}{body_pattern}{lookahead}"
        try:
            return re.compile(pattern_str, re.IGNORECASE | re.UNICODE)
        except Exception:
            return None

    def _compile_rules(self):
        """Bien dich cac quy tac tu danh sach tu cam thanh regex pattern toi uu."""
        self.rules.clear()
        categories = self.prohibited_data.get("categories", {})

        for cat_key, cat_data in categories.items():
            cat_name = cat_data.get("name", cat_key)
            severity = cat_data.get("severity", "high")
            policy_rule = cat_data.get("policy_rule", "")
            alternatives = cat_data.get("suggested_alternatives", [])
            words = cat_data.get("words", [])

            for word in words:
                word_clean = unicodedata.normalize("NFC", str(word).strip())
                if not word_clean:
                    continue

                # 1. Bien dich pattern co dau goc (NFC)
                accented_pattern = self._compile_single_pattern(word_clean)
                if accented_pattern:
                    self.rules.append({
                        "word": word_clean,
                        "pattern": accented_pattern,
                        "category": cat_key,
                        "category_name": cat_name,
                        "severity": severity,
                        "policy_rule": policy_rule,
                        "suggested_alternatives": alternatives,
                        "is_unaccented": False,
                    })

                # 2. Bien dich pattern khong dau (ASCII) de bat tieng Viet khong dau va hashtag khong dau
                word_unaccented = remove_vietnamese_diacritics(word_clean)
                if word_unaccented and word_unaccented != word_clean:
                    unaccented_pattern = self._compile_single_pattern(word_unaccented)
                    if unaccented_pattern:
                        self.rules.append({
                            "word": word_clean,  # Luon bao cao tu goc chuan
                            "pattern": unaccented_pattern,
                            "category": cat_key,
                            "category_name": cat_name,
                            "severity": severity,
                            "policy_rule": policy_rule,
                            "suggested_alternatives": alternatives,
                            "is_unaccented": True,
                        })

    def validate_text(self, text: Union[str, Any], field_name: str = "text") -> List[Dict[str, Any]]:
        """
        Kiem tra 1 doan van ban.
        Tra ve danh sach cac vi pham duoc tim thay.
        """
        if not text or not isinstance(text, str):
            return []

        # 1. Chuan hoa Unicode ve NFC
        norm_text = unicodedata.normalize("NFC", text)

        # 2. Tao ban go bo leetspeak phan tach (tr.ị -> trị, t-r-ị -> trị)
        deobf_text = deobfuscate_text(norm_text)

        # 3. Tao ban khong dau (tri dut diem, so 1, vinh vien)
        unaccented_deobf = remove_vietnamese_diacritics(deobf_text)

        violations = []
        covered_spans = set()  # set of (word, start, end) de tranh trung lap

        for rule in self.rules:
            target_text = unaccented_deobf if rule["is_unaccented"] else deobf_text
            targets = [(target_text, False)]
            if not rule["is_unaccented"] and norm_text != deobf_text:
                targets.append((norm_text, True))

            for current_text, is_raw in targets:
                for match in rule["pattern"].finditer(current_text):
                    start, end = match.span()
                    word_key = rule["word"]

                    # Tranh ghi nhan vi pham trung lap cho cung 1 tu o vi tri giao nhau
                    overlap = any(
                        w == word_key and not (end <= es or start >= ee)
                        for w, es, ee in covered_spans
                    )
                    if overlap:
                        continue
                    covered_spans.add((word_key, start, end))

                    # Trich xuat doan text ngu canh xung quanh tu text goc
                    ctx_start = max(0, start - 25)
                    ctx_end = min(len(norm_text), end + 25)
                    context_prefix = "..." if ctx_start > 0 else ""
                    context_suffix = "..." if ctx_end < len(norm_text) else ""
                    context = f"{context_prefix}{norm_text[ctx_start:ctx_end].strip()}{context_suffix}"

                    violations.append({
                        "word": rule["word"],
                        "matched_text": match.group(0),
                        "category": rule["category"],
                        "category_name": rule["category_name"],
                        "severity": rule["severity"],
                        "field": field_name,
                        "position": (start, end),
                        "context": context,
                        "policy_rule": rule["policy_rule"],
                        "suggested_alternatives": rule["suggested_alternatives"],
                    })

        return violations

    def validate_script(self, script_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kiem tra toan bo du lieu kich ban TikTok duoc tao ra boi Script Agent.
        Bao gom cac truong:
        - hook_text
        - voice_over_text
        - text_on_screen
        - post_caption
        - scenes (visual, audio, text va moi thuoc tinh khac)
        - hashtags (list hoac chuoi)
        - hashtag_string
        - cac truong mo rong (bgm_vibe, image_prompt_en, raw,...)
        
        Tra ve dict co cau truc:
        {
            "is_valid": bool,
            "violations": list[dict],
            "violation_count": int,
            "banned_words_found": list[str],
            "fix_instructions": str
        }
        """
        if not isinstance(script_data, dict):
            return {
                "is_valid": False,
                "violations": [{
                    "word": "INVALID_SCHEMA",
                    "matched_text": "",
                    "category": "schema_error",
                    "category_name": "Lỗi định dạng kịch bản",
                    "severity": "high",
                    "field": "root",
                    "context": "Dữ liệu kịch bản không phải là JSON dict hợp lệ",
                    "policy_rule": "Kịch bản phải là JSON hợp lệ",
                    "suggested_alternatives": [],
                }],
                "violation_count": 1,
                "banned_words_found": ["INVALID_SCHEMA"],
                "fix_instructions": "LỖI ĐỊNH DẠNG: Kịch bản trả về phải là một JSON Object hợp lệ.",
            }

        all_violations: List[Dict[str, Any]] = []
        checked_fields = set()

        # 1. Kiem tra cac truong van ban chinh
        primary_fields = ["hook_text", "voice_over_text", "text_on_screen", "post_caption"]
        for field in primary_fields:
            val = script_data.get(field)
            checked_fields.add(field)
            if isinstance(val, str):
                v_list = self.validate_text(val, field_name=field)
                all_violations.extend(v_list)

        # 2. Kiem tra cac truong trong scenes (ho tro ca list dict, list str va chuoi scenes)
        scenes = script_data.get("scenes")
        checked_fields.add("scenes")
        if isinstance(scenes, list):
            for i, scene in enumerate(scenes):
                if isinstance(scene, dict):
                    for sub_key, sub_val in scene.items():
                        if sub_key != "time" and isinstance(sub_val, str):
                            v_list = self.validate_text(sub_val, field_name=f"scenes[{i}].{sub_key}")
                            all_violations.extend(v_list)
                elif isinstance(scene, str):
                    v_list = self.validate_text(scene, field_name=f"scenes[{i}]")
                    all_violations.extend(v_list)
        elif isinstance(scenes, str):
            v_list = self.validate_text(scenes, field_name="scenes")
            all_violations.extend(v_list)

        # 3. Kiem tra hashtags va hashtag_string (R2 policy guardrail)
        hashtags = script_data.get("hashtags")
        checked_fields.add("hashtags")
        if isinstance(hashtags, list):
            for i, tag in enumerate(hashtags):
                if isinstance(tag, str):
                    v_list = self.validate_text(tag, field_name=f"hashtags[{i}]")
                    all_violations.extend(v_list)
                elif isinstance(tag, dict):
                    for k, v in tag.items():
                        if isinstance(v, str):
                            v_list = self.validate_text(v, field_name=f"hashtags[{i}].{k}")
                            all_violations.extend(v_list)
        elif isinstance(hashtags, str):
            v_list = self.validate_text(hashtags, field_name="hashtags")
            all_violations.extend(v_list)

        hashtag_str = script_data.get("hashtag_string")
        checked_fields.add("hashtag_string")
        if isinstance(hashtag_str, str):
            v_list = self.validate_text(hashtag_str, field_name="hashtag_string")
            all_violations.extend(v_list)

        # 4. Kiem tra tat ca cac truong chuoi con lai o root level
        # Bo qua cac truong chuan doan, huong dan sua va danh gia tu QC de tranh bat nham loi tren chinh huong dan sua
        skip_keys = {
            "scores",
            "violations",
            "banned_words_found",
            "policy_violations",
            "fix_instructions",
            "qc_feedback",
            "issues",
            "log",
            "strategy_note",
        }
        for extra_key, extra_val in script_data.items():
            if extra_key not in checked_fields and extra_key not in skip_keys:
                if isinstance(extra_val, str):
                    v_list = self.validate_text(extra_val, field_name=extra_key)
                    all_violations.extend(v_list)

        # Sap xep va loc cac tu cam tim duoc
        banned_words_found = sorted(list(set(v["word"] for v in all_violations)))
        is_valid = len(all_violations) == 0

        # Tao huong dan sua loi chi tiet cho AI Agent
        fix_instructions = self._build_fix_instructions(all_violations) if not is_valid else ""

        return {
            "is_valid": is_valid,
            "violations": all_violations,
            "violation_count": len(all_violations),
            "banned_words_found": banned_words_found,
            "fix_instructions": fix_instructions,
        }

    def _build_fix_instructions(self, violations: List[Dict[str, Any]]) -> str:
        """Xay dung prompt huong dan sua chi tiet cho Script Agent."""
        lines = [
            "CẢNH BÁO VI PHẠM CHÍNH SÁCH TIKTOK SHOP (BẮT BUỘC SỬA LẠI):",
            "Phát hiện các từ khóa bị cấm và tuyên bố quá mức trong nội dung kịch bản:",
        ]

        # Nhom vi pham theo truong
        by_field: Dict[str, List[Dict[str, Any]]] = {}
        for v in violations:
            f = v.get("field", "unknown")
            by_field.setdefault(f, []).append(v)

        for field_name, v_list in by_field.items():
            lines.append(f"\n[Tại trường: {field_name}]")
            for item in v_list:
                w = item["word"]
                cat_name = item["category_name"]
                ctx = item.get("context", "")
                alts = item.get("suggested_alternatives", [])
                alt_hint = f" (Gợi ý thay thế: {', '.join(alts[:2])})" if alts else ""
                lines.append(f"- Từ cấm: \"{w}\" (Thuộc nhóm: {cat_name}){alt_hint}")
                if ctx:
                    lines.append(f"  Ngữ cảnh phát hiện: \"{ctx}\"")

        banned_words = sorted(list(set(v["word"] for v in violations)))
        banned_str = ", ".join(f"\"{w}\"" for w in banned_words)

        lines.append(f"\nYÊU CẦU BẮT BUỘC ĐỐI VỚI SCRIPT AGENT:")
        lines.append(f"1. XÓA BỎ HOÀN TOÀN các từ ngữ cấm sau: {banned_str}.")
        lines.append("2. TUYỆT ĐỐI KHÔNG cam kết chữa khỏi 100%, trị dứt điểm, số 1 hay hiệu quả tức thì.")
        lines.append("3. THAY THẾ bằng ngôn từ hợp lệ theo Brand Guidelines: 'hỗ trợ cải thiện', 'giúp giảm', 'chăm sóc phục hồi', 'được nhiều người tin dùng'.")
        lines.append("4. Giữ nguyên cấu trúc JSON đầy đủ của kịch bản.")

        return "\n".join(lines)


# Singleton instance
_default_validator: Optional[PolicyValidator] = None


def get_default_validator() -> PolicyValidator:
    """Lay hoac khoi tao instance PolicyValidator mac dinh."""
    global _default_validator
    if _default_validator is None:
        _default_validator = PolicyValidator()
    return _default_validator


def validate_script(script_data: Dict[str, Any]) -> Dict[str, Any]:
    """Ham tien ich kiem tra nhanh 1 kich ban."""
    return get_default_validator().validate_script(script_data)


def validate_text(text: str, field_name: str = "text") -> Dict[str, Any]:
    """Ham tien ich kiem tra nhanh 1 chuoi van ban."""
    validator = get_default_validator()
    violations = validator.validate_text(text, field_name=field_name)
    banned_words = sorted(list(set(v["word"] for v in violations)))
    is_valid = len(violations) == 0
    fix_instructions = validator._build_fix_instructions(violations) if not is_valid else ""
    return {
        "is_valid": is_valid,
        "violations": violations,
        "violation_count": len(violations),
        "banned_words_found": banned_words,
        "fix_instructions": fix_instructions,
    }
