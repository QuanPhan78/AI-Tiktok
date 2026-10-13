"""
TESTS/TEST_POLICY_VALIDATOR.PY
===============================
Automated test suite verifying:
1. Acceptance Criteria: Data & Schema Integrity
   - hooks_library.json, cta_templates.json, prohibited_words.json, brand/guidelines.md exist.
   - Valid JSON and Markdown.
   - Prohibited words count >= 15 (actual: 40+).
   - Hook templates count >= 10 (actual: 16 across 4 required angles).
   - CTA templates count >= 10 (actual: 14).
2. Acceptance Criteria: Policy Validator Accuracy
   - Flags 100% of synthetic test inputs containing prohibited words.
   - Returns clear violation details (word, field, category, context).
   - Returns formatted fix instructions detailing banned words.
   - Case-insensitivity and punctuation resilience.
   - Word boundary protection (no false positives on "số 10" or "top 10").
   - Compliant inputs pass with zero violations.
"""

import json
import os
import sys
import unittest

# Ensure project root is in sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from knowledge_base.loader import (
    load_hooks_library,
    load_cta_templates,
    load_prohibited_words,
    load_brand_guidelines,
    get_formatted_hooks_for_prompt,
    get_formatted_ctas_for_prompt,
)
from knowledge_base.validator import (
    PolicyValidator,
    validate_script,
    validate_text,
    get_default_validator,
)


class TestKnowledgeBaseDataIntegrity(unittest.TestCase):
    """Kiem tra tinh toan ven du lieu cua Knowledge Base (R1)."""

    def setUp(self):
        self.kb_dir = os.path.join(_PROJECT_ROOT, "knowledge_base")
        self.hooks_path = os.path.join(self.kb_dir, "tiktok", "hooks_library.json")
        self.cta_path = os.path.join(self.kb_dir, "tiktok", "cta_templates.json")
        self.prohibited_path = os.path.join(self.kb_dir, "tiktok", "prohibited_words.json")
        self.guidelines_path = os.path.join(self.kb_dir, "brand", "guidelines.md")

    def test_all_files_exist(self):
        """Kiem tra tat ca cac file KB bat buoc deu ton tai tren o dia."""
        self.assertTrue(os.path.exists(self.hooks_path), "Thieu hooks_library.json")
        self.assertTrue(os.path.exists(self.cta_path), "Thieu cta_templates.json")
        self.assertTrue(os.path.exists(self.prohibited_path), "Thieu prohibited_words.json")
        self.assertTrue(os.path.exists(self.guidelines_path), "Thieu brand/guidelines.md")

    def test_json_files_are_valid(self):
        """Kiem tra cac file JSON hop le va parse duoc."""
        for path in [self.hooks_path, self.cta_path, self.prohibited_path]:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertIsInstance(data, dict, f"File {path} khong phai JSON object hop le")

    def test_hooks_library_counts_and_angles(self):
        """Kiem tra hooks_library chua it nhat 10+ templates va du 4 goc tiep can."""
        hooks_data = load_hooks_library()
        categories = hooks_data.get("categories", {})
        
        required_angles = ["Problem-Agitation", "Curiosity", "Statistics", "Question"]
        for angle in required_angles:
            self.assertIn(angle, categories, f"Thieu danh muc angle '{angle}' trong hooks_library")

        total_templates = 0
        for cat_key, cat_data in categories.items():
            temps = cat_data.get("templates", [])
            total_templates += len(temps)
            for t in temps:
                self.assertIn("id", t)
                self.assertIn("template", t)
                self.assertIn("example", t)
                self.assertTrue(len(t["template"].strip()) > 0)
                self.assertTrue(len(t["example"].strip()) > 0)

        self.assertGreaterEqual(total_templates, 10, f"hooks_library phai co >= 10 templates, thuc te co {total_templates}")

    def test_cta_templates_count_and_compliance(self):
        """Kiem tra cta_templates chua it nhat 10+ templates hop le voi TikTok Shop."""
        cta_data = load_cta_templates()
        categories = cta_data.get("categories", {})
        self.assertTrue(len(categories) > 0)

        total_ctas = 0
        for cat_key, cat_data in categories.items():
            temps = cat_data.get("templates", [])
            total_ctas += len(temps)
            for t in temps:
                self.assertIn("id", t)
                self.assertIn("template", t)
                self.assertIn("compliance_note", t)
                self.assertTrue(len(t["template"].strip()) > 0)

        self.assertGreaterEqual(total_ctas, 10, f"cta_templates phai co >= 10 templates, thuc te co {total_ctas}")

    def test_prohibited_words_count_and_categories(self):
        """Kiem tra prohibited_words chua it nhat 15+ tu cam va phan loai ro rang."""
        data = load_prohibited_words()
        categories = data.get("categories", {})
        self.assertTrue(len(categories) >= 3, "Phai co it nhat 3 nhom vi pham")

        all_words = []
        for cat_key, cat_data in categories.items():
            self.assertIn("name", cat_data)
            self.assertIn("severity", cat_data)
            self.assertIn("words", cat_data)
            words = cat_data.get("words", [])
            all_words.extend(words)

        self.assertGreaterEqual(len(all_words), 15, f"prohibited_words phai co >= 15 tu, thuc te co {len(all_words)}")

        # Kiem tra cac tu khoa tieu bieu bat buoc phai co
        expected_samples = ["trị dứt điểm", "cam kết 100%", "chữa khỏi hoàn toàn", "tuyệt đối", "số 1", "vĩnh viễn"]
        for sample in expected_samples:
            self.assertTrue(
                any(sample.lower() in w.lower() for w in all_words),
                f"Thieu tu khoa bat buoc '{sample}' trong prohibited_words.json"
            )

    def test_brand_guidelines_content(self):
        """Kiem tra brand guidelines ton tai va chua cac quy tac cot loi."""
        content = load_brand_guidelines()
        self.assertTrue(len(content) > 100)
        self.assertIn("Tone of Voice", content)
        self.assertIn("trị dứt điểm", content)
        self.assertIn("cam kết 100%", content)


class TestPolicyValidatorAccuracy(unittest.TestCase):
    """Kiem tra do chinh xac va tinh nghiem ngat cua Policy Guardrail Validator (R2)."""

    def setUp(self):
        self.validator = get_default_validator()

    def test_detects_prohibited_words_in_text(self):
        """Kiem tra phat hien 100% cac tu khoa vi pham tong hop."""
        banned_phrases = [
            "trị dứt điểm",
            "cam kết 100%",
            "chữa khỏi hoàn toàn",
            "tuyệt đối",
            "số 1",
            "vĩnh viễn",
            "khỏi hẳn",
            "thần dược",
            "sau 1 đêm",
            "không tác dụng phụ",
            "hoàn tiền 200%",
        ]

        for phrase in banned_phrases:
            text = f"Sản phẩm thảo dược này giúp {phrase} mọi vấn đề về da."
            result = validate_text(text, field_name="voice_over_text")
            self.assertFalse(result["is_valid"], f"Khong phat hien duoc tu cam: '{phrase}'")
            self.assertGreater(result["violation_count"], 0)
            self.assertTrue(
                any(v["word"].lower() == phrase.lower() for v in result["violations"]),
                f"Violation list khong chua '{phrase}'"
            )
            # Kiem tra co huong dan sua ro rang
            self.assertTrue(len(result["fix_instructions"]) > 0)
            self.assertIn(phrase, result["fix_instructions"])

    def test_case_insensitivity_and_accents(self):
        """Kiem tra phat hien khong phan biet hoa thuong va giu nguyen dau tieng Viet."""
        variations = [
            "TRỊ DỨT ĐIỂM",
            "Trị Dứt Điểm",
            "CAM KẾT 100%",
            "Cam Kết 100%",
            "CHỮA KHỎI HOÀN TOÀN",
            "Số 1",
            "SỐ 1",
            "VĨNH VIỄN",
            "Vĩnh Viễn",
        ]

        for var in variations:
            text = f"Giải pháp {var} cho cả gia đình bạn."
            res = validate_text(text)
            self.assertFalse(res["is_valid"], f"Khong bat duoc bien the chu hoa/thuong: '{var}'")

    def test_punctuation_and_attached_symbols(self):
        """Kiem tra bat duoc tu cam khi co dau cham, dau phay, cham than kem theo."""
        cases = [
            ("Sản phẩm số 1!", "số 1"),
            ("Chúng tôi cam kết 100%.", "cam kết 100%"),
            ("Hiệu quả vĩnh viễn, không lo tái phát.", "vĩnh viễn"),
            ("Cam kết: trị dứt điểm hoàn toàn?", "trị dứt điểm"),
        ]

        for text, expected_word in cases:
            res = validate_text(text)
            self.assertFalse(res["is_valid"], f"Khong bat duoc khi co dau cau: '{text}'")
            self.assertIn(expected_word, res["banned_words_found"])

    def test_word_boundary_avoids_false_positives(self):
        """Kiem tra regex lookaround khong bat nham cac tu hop le (vi du: 'so 10', 'top 10')."""
        valid_cases = [
            "Top 10 mẹo chăm sóc sức khỏe mùa hanh khô.",
            "Bài tập số 10 trong giáo trình thể thao.",
            "Uống 100ml nước mỗi sáng.",
            "Chiết xuất 100% thảo mộc tự nhiên được chứng nhận.",  # '100%' dung don le khong cam ket qua muc
        ]

        for text in valid_cases:
            res = validate_text(text)
            # Khong duoc bat nham 'so 1' tu 'so 10'
            self.assertNotIn("số 1", res["banned_words_found"], f"False positive bat nham 'số 1' trong: '{text}'")
            self.assertNotIn("top 1", res["banned_words_found"], f"False positive bat nham 'top 1' trong: '{text}'")

    def test_validate_script_inspects_all_fields(self):
        """Kiem tra validate_script quet qua ca hook_text, voice_over_text, text_on_screen, post_caption, scenes."""
        bad_script = {
            "hook_text": "Sản phẩm số 1 Việt Nam trị dứt điểm rụng tóc!",
            "voice_over_text": "Chúng tôi cam kết 100% mọc tóc dày trở lại sau 1 đêm.",
            "text_on_screen": "Hiệu quả vĩnh viễn",
            "scenes": [
                {"time": "0:00-0:03", "visual": "Thần dược cho mái tóc", "audio": "An toàn tuyệt đối"}
            ],
            "post_caption": "Trị khỏi hoàn toàn ngay hôm nay! #tocdep",
        }

        res = validate_script(bad_script)
        self.assertFalse(res["is_valid"])
        self.assertGreaterEqual(res["violation_count"], 5)

        fields_flagged = set(v["field"] for v in res["violations"])
        self.assertIn("hook_text", fields_flagged)
        self.assertIn("voice_over_text", fields_flagged)
        self.assertIn("text_on_screen", fields_flagged)
        self.assertIn("post_caption", fields_flagged)
        self.assertTrue(any(f.startswith("scenes[") for f in fields_flagged))

        # Kiem tra cac tu bi phat hien
        for expected in ["số 1", "trị dứt điểm", "cam kết 100%", "sau 1 đêm", "vĩnh viễn", "thần dược", "an toàn tuyệt đối", "trị khỏi hoàn toàn"]:
            self.assertIn(expected, res["banned_words_found"])

        # Kiem tra fix instructions co chi tiet
        fix_text = res["fix_instructions"]
        self.assertIn("CẢNH BÁO VI PHẠM CHÍNH SÁCH TIKTOK SHOP", fix_text)
        self.assertIn("YÊU CẦU BẮT BUỘC ĐỐI VỚI SCRIPT AGENT", fix_text)

    def test_compliant_input_passes_with_zero_violations(self):
        """Kiem tra kich ban hop le, tuan thu 100% Brand Guidelines phai pass khong co vi pham nao."""
        compliant_script = {
            "hook_text": "Nếu bạn đang bị tóc rụng nhiều mỗi khi gội, hãy dừng thói quen này lại!",
            "voice_over_text": (
                "Rụng tóc kéo dài khiến bạn mất tự tin? Đừng lo lắng quá! "
                "Serum thảo mộc cô đặc này bổ sung dưỡng chất tự nhiên từ vỏ bưởi và bồ kết, "
                "hỗ trợ cải thiện nang tóc yếu và giúp giảm gãy rụng rõ rệt khi dùng đều đặn. "
                "Sản phẩm lành tính, được rất nhiều bạn tin dùng mỗi ngày."
            ),
            "text_on_screen": "Hỗ trợ giảm rụng tóc tự nhiên",
            "scenes": [
                {"time": "0:00-0:03", "visual": "Cô gái ngắm tóc trước gương", "audio": "Nếu bạn đang bị tóc rụng nhiều..."},
                {"time": "0:03-0:25", "visual": "Cận cảnh nhỏ serum bưởi", "audio": "Serum thảo mộc bổ sung dưỡng chất..."},
                {"time": "0:25-0:30", "visual": "Chỉ tay vào giỏ hàng vàng góc trái", "audio": "Bấm ngay vào giỏ hàng để nhận ưu đãi hôm nay!"}
            ],
            "post_caption": "Bí quyết chăm sóc mái tóc bồng bềnh tại nhà 🌿 Ghé giỏ hàng góc trái nhé! #chamsocda #serumbuoi",
        }

        res = validate_script(compliant_script)
        self.assertTrue(res["is_valid"], f"Kich ban hop le bi bat loi oan: {res['violations']}")
        self.assertEqual(res["violation_count"], 0)
        self.assertEqual(len(res["violations"]), 0)
        self.assertEqual(len(res["banned_words_found"]), 0)
        self.assertEqual(res["fix_instructions"], "")

    def test_unicode_nfd_normalization(self):
        """Kiem tra ky tu tieng Viet to hop (NFD) duoc chuan hoa va phat hien 100%."""
        import unicodedata
        nfd_phrases = [
            unicodedata.normalize("NFD", "trị dứt điểm"),
            unicodedata.normalize("NFD", "chữa khỏi hoàn toàn"),
            unicodedata.normalize("NFD", "cam kết 100%"),
            unicodedata.normalize("NFD", "vĩnh viễn"),
        ]
        for phrase in nfd_phrases:
            text = f"Sản phẩm giúp {phrase} cho người dùng."
            res = validate_text(text)
            self.assertFalse(res["is_valid"], f"Khong bat duoc chuoi NFD: {repr(phrase)}")
            self.assertGreater(res["violation_count"], 0)

    def test_multiline_and_whitespace_variation(self):
        """Kiem tra tu cam xuong dong hoac nhieu khoang trang van bi phat hien."""
        multiline_cases = [
            "Trị\ndứt điểm mụn lưng",
            "Cam kết\n100% hiệu quả",
            "Sản phẩm trị   dứt   điểm",
            "Chữa khỏi\nhoàn toàn bệnh da liễu",
        ]
        for text in multiline_cases:
            res = validate_text(text)
            self.assertFalse(res["is_valid"], f"Khong bat duoc khi xuong dong/nhieu khoang trang: '{text}'")

    def test_intra_phrase_punctuation_and_separators(self):
        """Kiem tra tu cam co dau phan tach (dau hai cham, gach ngang, ngoac, ba cham)."""
        punct_cases = [
            ("Cam kết: 100% chất lượng", "cam kết 100%"),
            ("Cam kết - 100% hài lòng", "cam kết 100%"),
            ("Cam kết (100%) an toàn", "cam kết 100%"),
            ("Trị... dứt điểm", "trị dứt điểm"),
            ("Trị - dứt điểm", "trị dứt điểm"),
            ("#trị_dứt_điểm", "trị dứt điểm"),
            ("#cam_kết_100%", "cam kết 100%"),
        ]
        for text, expected in punct_cases:
            res = validate_text(text)
            self.assertFalse(res["is_valid"], f"Khong bat duoc khi co ky tu phan tach: '{text}'")
            self.assertIn(expected, res["banned_words_found"])

    def test_percentage_non_word_boundary(self):
        """Kiem tra tu ket thuc bang % khong bi nuot khi viet lien voi tu khac."""
        cases = [
            "Cam kết 100%hiệu quả",
            "Cam kết 100%thành công",
            "Hoàn tiền 200%ngay lập tức",
        ]
        for text in cases:
            res = validate_text(text)
            self.assertFalse(res["is_valid"], f"Khong bat duoc tu ket thuc bang %: '{text}'")

    def test_validate_script_inspects_hashtags(self):
        """Kiem tra validate_script phat hien tu cam trong hashtags va hashtag_string."""
        bad_script_with_tags = {
            "hook_text": "Mẹo chăm sóc tóc tự nhiên",
            "voice_over_text": "Serum bưởi dưỡng tóc nhẹ nhàng mỗi ngày",
            "text_on_screen": "Chăm sóc tóc",
            "post_caption": "Tóc đẹp tự nhiên",
            "hashtags": ["#TocDep", "#tri_dut_diem", "#cam_kết_100%"],
            "hashtag_string": "#so_1 #ThanDuoc",
        }
        res = validate_script(bad_script_with_tags)
        self.assertFalse(res["is_valid"])
        fields_flagged = [v["field"] for v in res["violations"]]
        self.assertTrue(any("hashtags" in f for f in fields_flagged), f"Khong flag hashtags: {fields_flagged}")
        self.assertIn("hashtag_string", fields_flagged)

    def test_unaccented_vietnamese_detection(self):
        """Kiem tra tieng Viet khong dau (unaccented ASCII) van bi phat hien 100%."""
        unaccented_cases = [
            ("Sản phẩm này giúp tri dut diem moi loai mun.", "trị dứt điểm"),
            ("Chúng tôi cam ket 100% hai long.", "cam kết 100%"),
            ("Thuong hieu so 1 Viet Nam hien nay.", "số 1"),
            ("Tac dung vinh vien khong lo tai phat.", "vĩnh viễn"),
            ("Day la than duoc cho lan da cua ban.", "thần dược"),
            ("Giup chua khoi hoan toan benh nam da.", "chữa khỏi hoàn toàn"),
            ("Cam ket khoi han sau 1 lieu trinh.", "khỏi hẳn"),
        ]
        for text, expected in unaccented_cases:
            res = validate_text(text)
            self.assertFalse(res["is_valid"], f"Khong bat duoc tieng Viet khong dau: '{text}'")
            self.assertIn(expected, res["banned_words_found"])

    def test_interspersed_leetspeak_and_punctuation_fuzzing(self):
        """Kiem tra leetspeak co dau cham, gach ngang xen giua cac chu cai (t.r.i, tr.i, k.h.o.i)."""
        leetspeak_cases = [
            ("Serum tr.ị dứt đ.iểm mụn nhanh chóng", "trị dứt điểm"),
            ("Hiệu quả t-r-ị d-ứ-t đ-i-ể-m rõ rệt", "trị dứt điểm"),
            ("K.h.ỏ.i h.ẳ.n sau vài ngày sử dụng", "khỏi hẳn"),
            ("Giải pháp c-a-m k-ế-t 100% uy tín", "cam kết 100%"),
            ("Bảo đảm t-r-i-d-u-t-d-i-e-m tận gốc", "trị dứt điểm"),
            ("Công thức t.r.ị d.ứ.t đ.i.ể.m độc quyền", "trị dứt điểm"),
        ]
        for text, expected in leetspeak_cases:
            res = validate_text(text)
            self.assertFalse(res["is_valid"], f"Khong bat duoc leetspeak: '{text}'")
            self.assertIn(expected, res["banned_words_found"])

    def test_hashtag_compound_unspaced_forms(self):
        """Kiem tra hashtag viet lien khong dau cach, khong dau hoac co dau (#tridutdiem, #TrịDứtĐiểm, #so1, #so_1)."""
        hashtag_cases = [
            ("#tridutdiem", "trị dứt điểm"),
            ("#TrịDứtĐiểm", "trị dứt điểm"),
            ("#camket100", "cam kết 100%"),
            ("#camket100%", "cam kết 100%"),
            ("#CamKết100%", "cam kết 100%"),
            ("#so1", "số 1"),
            ("#Số1", "số 1"),
            ("#so_1", "số 1"),
            ("#top1", "top 1"),
            ("#thanduoc", "thần dược"),
            ("#ThầnDược", "thần dược"),
            ("#vinhvien", "vĩnh viễn"),
        ]
        for tag, expected in hashtag_cases:
            res = validate_text(tag, field_name="hashtags")
            self.assertFalse(res["is_valid"], f"Khong bat duoc hashtag lien: '{tag}'")
            self.assertIn(expected, res["banned_words_found"])

    def test_percentage_with_zero_separator(self):
        """Kiem tra 100% viet lien voi tu tiep theo van bi phat hien."""
        cases = [
            ("Cam kết 100%hiệu quả cho khách hàng", "100% hiệu quả"),
            ("Sản phẩm 100% hiệu quả vượt trội", "100% hiệu quả"),
            ("#100hieuqua", "100% hiệu quả"),
        ]
        for text, expected in cases:
            res = validate_text(text)
            self.assertFalse(res["is_valid"], f"Khong bat duoc: '{text}'")
            self.assertIn(expected, res["banned_words_found"])

    def test_quantity_and_currency_avoid_false_positives(self):
        """Kiem tra cac con so so luong (1000 phan qua, 100k nguoi) va tien te (200k, 200000 dong) khong bi bat nham."""
        safe_cases = [
            "Shop cam kết 1000 phần quà cho khách hàng nhanh tay nhất.",
            "Chúng tôi cam kết 100k người tham gia sự kiện.",
            "Hoàn tiền 200k nếu kiện hàng bị móp méo trong vận chuyển.",
            "Hoàn tiền 200000 đồng vào ví cho đơn hàng hủy.",
            "Đã điều trị cho hơn 1000 bệnh nhân phục hồi tốt.",
            "Cam kết 100 voucher ưu đãi mỗi ngày.",
            "Cam kết 100 đơn hàng đầu tiên được nhận quà.",
            "Hoàn tiền 200 đơn hàng bị lỗi kỹ thuật.",
        ]
        for text in safe_cases:
            res = validate_text(text)
            self.assertNotIn("cam kết 100%", res["banned_words_found"], f"False positive bat nham 'cam kết 100%' trong: '{text}'")
            self.assertNotIn("hoàn tiền 200%", res["banned_words_found"], f"False positive bat nham 'hoàn tiền 200%' trong: '{text}'")

    def test_multichar_and_spaced_leetspeak_evasion(self):
        """Kiem tra leetspeak co nhieu ky tu phan tach hoac khoang trang (t--r--i, t - r - i, t r i)."""
        evasion_cases = [
            ("Sản phẩm t--r--ị d--ứ--t đ--i--ể--m mụn hiệu quả", "trị dứt điểm"),
            ("Công thức t..r..ị d..ứ..t đ..i..ể..m gia truyền", "trị dứt điểm"),
            ("Hiệu quả t...r...ị d...ứ...t đ...i...ể...m rõ rệt", "trị dứt điểm"),
            ("Cam kết t - r - ị d - ứ - t đ - i - ể - m", "trị dứt điểm"),
            ("Serum t . r . i d . u . t d . i . e . m", "trị dứt điểm"),
            ("Giải pháp t / r / i d / u / t d / i / e / m", "trị dứt điểm"),
            ("Thảo mộc t | r | i d | u | t d | i | e | m", "trị dứt điểm"),
            ("Serum t|r|i d|u|t d|i|e|m trị thâm", "trị dứt điểm"),
            ("Tinh chất t||r||i d||u||t d||i||e||m", "trị dứt điểm"),
            ("Liệu trình t r ị  d ứ t  đ i ể m mụn lưng", "trị dứt điểm"),
            ("Bí quyết t r i  d u t  d i e m", "trị dứt điểm"),
        ]
        for text, expected in evasion_cases:
            res = validate_text(text)
            self.assertFalse(res["is_valid"], f"Khong bat duoc leetspeak tinh vi: '{text}'")
            self.assertIn(expected, res["banned_words_found"])

    def test_self_incrimination_immunity_in_validate_script(self):
        """Kiem tra script_data co chua fix_instructions hoac qc_feedback khong bi bat loi oan tren chinh huong dan sua."""
        script_with_diagnostic_fields = {
            "hook_text": "Mẹo chăm sóc tóc tự nhiên tại nhà",
            "voice_over_text": "Serum bưởi dưỡng tóc nhẹ nhàng mỗi ngày, hỗ trợ nang tóc khỏe.",
            "text_on_screen": "Chăm sóc tóc",
            "post_caption": "Bí quyết tóc đẹp #tocdep",
            "fix_instructions": "CẢNH BÁO: Xóa bỏ hoàn toàn từ cấm 'trị dứt điểm', 'cam kết 100%' trong kịch bản.",
            "qc_feedback": "Phát hiện vi phạm từ cấm trị dứt điểm ở bản nháp trước.",
            "issues": ["Vi phạm từ cấm 'số 1'"],
        }
        res = validate_script(script_with_diagnostic_fields)
        self.assertTrue(res["is_valid"], f"Bat loi oan tren truong chan doan: {res['violations']}")
        self.assertEqual(res["violation_count"], 0)

    def test_validate_script_inspects_string_scenes(self):
        """Kiem tra validate_script phat hien tu cam ca khi scenes la list cac chuoi hoac chuoi don."""
        script_with_string_scenes = {
            "hook_text": "Mẹo nhỏ cho bạn",
            "voice_over_text": "Trà thảo mộc lành tính",
            "text_on_screen": "Trà ngon",
            "scenes": [
                "Cảnh 1: Giới thiệu trà thảo mộc",
                "Cảnh 2: Trị dứt điểm mất ngủ kinh niên",
            ],
            "post_caption": "Trà ngủ ngon",
        }
        res = validate_script(script_with_string_scenes)
        self.assertFalse(res["is_valid"])
        self.assertIn("trị dứt điểm", res["banned_words_found"])
        self.assertTrue(any("scenes[1]" in v["field"] for v in res["violations"]))

    def test_new_blacklist_variants_detection(self):
        """Kiem tra cac bien the moi duoc bo sung: so mot, top mot, hieu qua 100%, dut diem 100%."""
        cases = [
            ("Thương hiệu số một trên thị trường", "số một"),
            ("Sản phẩm top một Việt Nam", "top một"),
            ("Mang lại hiệu quả 100% cho người dùng", "hiệu quả 100%"),
            ("Hỗ trợ dứt điểm 100% tình trạng ngứa", "dứt điểm 100%"),
            ("#somot", "số một"),
            ("#topmot", "top một"),
            ("#hieuqua100", "hiệu quả 100%"),
        ]
        for text, expected in cases:
            res = validate_text(text)
            self.assertFalse(res["is_valid"], f"Khong bat duoc bien the blacklist: '{text}'")
            self.assertIn(expected, res["banned_words_found"])


if __name__ == "__main__":
    unittest.main()
