"""
=============================================
PROTOTYPE 2B: DUNG GOOGLE GEMINI (MIEN PHI!)
=============================================

Muc dich: Goi AI that de viet kich ban TikTok.
          Dung Google Gemini API - HOAN TOAN MIEN PHI!

Can:   API key Google Gemini (mien phi)
       Lay tai: https://aistudio.google.com/apikey
Chay:  python prototypes/02b_test_gemini.py

Chi phi: $0 (MIEN PHI!)
"""

import os
import sys
import time
from dotenv import load_dotenv
load_dotenv()

# Kiem tra API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key.startswith("AIza-xxxx"):
    print("=" * 60)
    print("CHUA CO GEMINI API KEY!")
    print("=" * 60)
    print()
    print("Buoc 1: Lay API key (MIEN PHI)")
    print("   -> Vao https://aistudio.google.com/apikey")
    print("   -> Dang nhap bang tai khoan Google (Gmail)")
    print("   -> Nhan 'Create API Key'")
    print("   -> Copy key (bat dau bang 'AIza...')")
    print()
    print("Buoc 2: Dien API key")
    print("   -> Mo file .env trong thu muc tiktok-ai-agent")
    print("   -> Them dong: GEMINI_API_KEY=AIza...")
    print("   -> Luu file")
    print()
    print("Roi chay lai file nay!")
    sys.exit(1)

from google import genai
from google.genai import types

# Tao client ket noi den Google Gemini
client = genai.Client(api_key=api_key)

# Danh sach model de thu (neu model 1 qua tai thi thu model 2)
MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash"]

def call_gemini(prompt, max_retries=3):
    """Goi Gemini API voi retry va fallback model"""
    for model in MODELS:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                    ),
                )
                print(f"   (Dung model: {model})")
                return response.text
            except Exception as e:
                error_msg = str(e)
                if "503" in error_msg or "UNAVAILABLE" in error_msg:
                    print(f"   Model {model} dang qua tai, thu lai sau 5 giay...")
                    time.sleep(5)
                elif "404" in error_msg or "no longer available" in error_msg:
                    print(f"   Model {model} khong kha dung, thu model khac...")
                    break  # Thu model tiep theo
                else:
                    print(f"   Loi: {error_msg[:100]}")
                    if attempt < max_retries - 1:
                        time.sleep(3)
    
    print("Khong the goi duoc AI. Vui long thu lai sau.")
    sys.exit(1)


print("=" * 60)
print("TEST 2B: Goi AI That - Google Gemini (MIEN PHI!)")
print("=" * 60)
print()

# =============================================
# SAN PHAM TEST
# =============================================
product_name = "Kem chong nang ABC"
product_info = """
- Chi so chong nang: SPF50+ PA++++
- Dac diem: Khong gay bong nhon, tham nhanh
- Phu hop: Da dau, da hon hop
- Gia: 199.000 VND
- Dung tich: 50ml
- Thanh phan noi bat: Centella Asiatica (rau ma), Niacinamide
"""

print(f"San pham: {product_name}")
print(f"Thong tin: {product_info}")

# =============================================
# BUOC 1: GOI AI DE NGHIEN CUU SAN PHAM
# =============================================
print("=" * 40)
print("BUOC 1: AI NGHIEN CUU SAN PHAM")
print("=" * 40)
print("Dang goi Gemini...")

research_result = call_gemini(f"""Phan tich san pham sau cho video TikTok:

San pham: {product_name}
Thong tin: {product_info}

Hay cho biet:
1. Doi tuong muc tieu chi tiet
2. 3 diem noi bat (USP) hap dan nhat
3. 3 goc tiep can video TikTok phu hop
4. Nhung pain point (van de) cua khach hang ma san pham giai quyet

Tra loi bang tieng Viet, ngan gon, de hieu.""")

print()
print("KET QUA NGHIEN CUU:")
print("-" * 40)
print(research_result)
print()

# =============================================
# BUOC 2: GOI AI DE VIET KICH BAN
# =============================================
print("=" * 40)
print("BUOC 2: AI VIET KICH BAN")
print("=" * 40)
print("Dang goi Gemini...")

script_result = call_gemini(f"""Viet kich ban video TikTok 30 giay cho san pham:

San pham: {product_name}
Thong tin: {product_info}
Nghien cuu: {research_result}

YEU CAU FORMAT:
- HOOK (0:00 - 0:03): Cau mo dau gay to mo, khien nguoi xem dung luot
- BODY (0:03 - 0:25): Trinh bay 2-3 diem noi bat, ke chuyen hap dan
- CTA (0:25 - 0:30): Keu goi hanh dong tu nhien

- VOICE-OVER: Script doc voice day du
- HINH ANH: Goi y hinh anh/canh quay cho tung phan
- CAPTION: Caption cho post TikTok (ngan gon, co emoji)
- HASHTAGS: 5-8 hashtag phu hop

Viet bang tieng Viet, giong dieu tre trung, hap dan Gen Z.""")

print()
print("KICH BAN TIKTOK:")
print("-" * 40)
print(script_result)
print()

# =============================================
# TONG KET
# =============================================
print("=" * 60)
print("TONG KET")
print("=" * 60)
print(f"   Chi phi: $0 (MIEN PHI!)")
print()
print("Ban vua dung Google Gemini (MIEN PHI) de:")
print("1. Phan tich san pham (Research Agent)")
print("2. Viet kich ban TikTok (Script Writer Agent)")
print()
print("Google Gemini mien phi cho:")
print("- 15 request/phut (du dung cho dev & test)")
print("- 1500 request/ngay")
print()
print("Du an nay co the dung Gemini lam model CHINH de tiet kiem chi phi!")
