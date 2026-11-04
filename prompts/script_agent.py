"""Canonical prompt templates used by the legacy graph and the reviewed studio."""

def build_legacy_script_prompt(*, product, research_raw, fix_note, brand_summary, policy_summary, hook_templates_str, cta_templates_str, tone_note):
    return f"""Viet kich ban TikTok 30 giay. Tra ve JSON thuan tuy, khong them text gi ngoai JSON.

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
