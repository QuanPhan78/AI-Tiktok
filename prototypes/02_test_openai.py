"""
=============================================
PROTOTYPE 2: DÙNG AI THẬT (OpenAI GPT) - KHÔNG FRAMEWORK
=============================================

Mục đích: Gọi AI thật để viết kịch bản TikTok.
           Hiểu cách gọi API của OpenAI.

Cần:   API key OpenAI (điền vào file .env)
Chạy:  python prototypes/02_test_openai.py

💰 Chi phí: Khoảng 200-500 VND mỗi lần chạy (rất rẻ)
"""

import os
import sys
from dotenv import load_dotenv

# Đọc API key từ file .env
load_dotenv()

# Kiểm tra API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key.startswith("sk-xxxx"):
    print("=" * 60)
    print("⚠️  CHƯA CÓ API KEY!")
    print("=" * 60)
    print()
    print("Bạn cần làm 2 bước:")
    print()
    print("Bước 1: Lấy API key")
    print("   → Vào https://platform.openai.com/api-keys")
    print("   → Đăng nhập (hoặc tạo tài khoản mới)")
    print("   → Nhấn 'Create new secret key'")
    print("   → Copy key (bắt đầu bằng 'sk-...')")
    print()
    print("Bước 2: Điền API key")
    print("   → Mở file .env trong thư mục tiktok-ai-agent")
    print("   → Dán key vào dòng OPENAI_API_KEY=sk-...")
    print("   → Lưu file")
    print()
    print("Rồi chạy lại file này!")
    sys.exit(1)

# Import OpenAI
from openai import OpenAI

# Tạo client (kết nối đến OpenAI)
client = OpenAI()

print("=" * 60)
print("🤖 TEST 2: Gọi AI Thật (OpenAI GPT)")
print("=" * 60)
print()

# =============================================
# SẢN PHẨM TEST
# =============================================
product_name = "Kem chống nắng ABC"
product_info = """
- Chỉ số chống nắng: SPF50+ PA++++
- Đặc điểm: Không gây bóng nhờn, thấm nhanh
- Phù hợp: Da dầu, da hỗn hợp
- Giá: 199.000 VND
- Dung tích: 50ml
- Thành phần nổi bật: Centella Asiatica (rau má), Niacinamide
"""

print(f"📦 Sản phẩm: {product_name}")
print(f"📋 Thông tin: {product_info}")

# =============================================
# BƯỚC 1: GỌI AI ĐỂ NGHIÊN CỨU SẢN PHẨM
# =============================================
print("=" * 40)
print("BƯỚC 1: AI NGHIÊN CỨU SẢN PHẨM")
print("=" * 40)
print("⏳ Đang gọi AI... (đợi 5-15 giây)")

research_response = client.chat.completions.create(
    # Model nào?
    # - "gpt-4o-mini" = rẻ, nhanh, đủ tốt cho task đơn giản
    # - "gpt-4o" = đắt hơn, thông minh hơn, cho task phức tạp
    model="gpt-4o-mini",
    
    # Tin nhắn gửi cho AI
    messages=[
        {
            # "system" = hướng dẫn AI nó là ai, làm gì
            "role": "system",
            "content": """Bạn là chuyên gia phân tích sản phẩm cho TikTok marketing 
            tại Việt Nam. Bạn am hiểu xu hướng TikTok, hành vi người dùng Gen Z."""
        },
        {
            # "user" = câu hỏi/yêu cầu cụ thể
            "role": "user",
            "content": f"""Phân tích sản phẩm sau cho video TikTok:

Sản phẩm: {product_name}
Thông tin: {product_info}

Hãy cho biết:
1. Đối tượng mục tiêu chi tiết
2. 3 điểm nổi bật (USP) hấp dẫn nhất
3. 3 góc tiếp cận video TikTok phù hợp
4. Những pain point (vấn đề) của khách hàng mà sản phẩm giải quyết

Trả lời ngắn gọn, dễ hiểu."""
        }
    ],
    
    # temperature = độ "sáng tạo" của AI
    # 0.0 = rất chính xác, ít sáng tạo
    # 1.0 = rất sáng tạo, có thể bất ngờ
    # 0.7 = cân bằng (khuyên dùng)
    temperature=0.7,
)

# Lấy kết quả
research_result = research_response.choices[0].message.content
print()
print("📊 KẾT QUẢ NGHIÊN CỨU:")
print("-" * 40)
print(research_result)
print()

# Xem chi phí
usage1 = research_response.usage
print(f"💰 Token đã dùng: {usage1.total_tokens} tokens")
print(f"   (Input: {usage1.prompt_tokens}, Output: {usage1.completion_tokens})")
print()

# =============================================
# BƯỚC 2: GỌI AI ĐỂ VIẾT KỊCH BẢN
# =============================================
print("=" * 40)
print("BƯỚC 2: AI VIẾT KỊCH BẢN")
print("=" * 40)
print("⏳ Đang gọi AI... (đợi 10-20 giây)")

script_response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "system",
            "content": """Bạn là biên kịch TikTok chuyên nghiệp tại Việt Nam.
Bạn chuyên viết content viral, thu hút Gen Z.
Giọng điệu: trẻ trung, gần gũi, như nói chuyện với bạn bè."""
        },
        {
            "role": "user",
            "content": f"""Viết kịch bản video TikTok 30 giây cho sản phẩm:

Sản phẩm: {product_name}
Thông tin: {product_info}
Nghiên cứu: {research_result}

YÊU CẦU FORMAT:
📌 HOOK (0:00 - 0:03): Câu mở đầu gây tò mò, khiến người xem dừng lướt
📌 BODY (0:03 - 0:25): Trình bày 2-3 điểm nổi bật, kể chuyện hấp dẫn
📌 CTA (0:25 - 0:30): Kêu gọi hành động tự nhiên

📌 VOICE-OVER: Script đọc voice đầy đủ
📌 HÌNH ẢNH: Gợi ý hình ảnh/cảnh quay cho từng phần
📌 CAPTION: Caption cho post TikTok (ngắn gọn, có emoji)
📌 HASHTAGS: 5-8 hashtag phù hợp

Viết bằng tiếng Việt."""
        }
    ],
    temperature=0.8,
)

script_result = script_response.choices[0].message.content
print()
print("📝 KỊCH BẢN TIKTOK:")
print("-" * 40)
print(script_result)
print()

usage2 = script_response.usage
print(f"💰 Token đã dùng: {usage2.total_tokens} tokens")
print()

# =============================================
# TỔNG KẾT
# =============================================
total_tokens = usage1.total_tokens + usage2.total_tokens
# Giá GPT-4o-mini: ~$0.00015/1K input + $0.0006/1K output
estimated_cost = total_tokens * 0.0003 / 1000  # ước tính trung bình
estimated_vnd = estimated_cost * 25000

print("=" * 60)
print("📊 TỔNG KẾT")
print("=" * 60)
print(f"   Tổng token: {total_tokens}")
print(f"   Chi phí ước tính: ~${estimated_cost:.4f} (~{estimated_vnd:.0f} VND)")
print(f"   Thời gian: ~15-30 giây")
print()
print("=" * 60)
print("📖 GIẢI THÍCH:")
print("=" * 60)
print("""
Bạn vừa dùng AI thật (GPT-4o-mini) để:
1. Phân tích sản phẩm (Research Agent)
2. Viết kịch bản TikTok (Script Writer Agent)

Cách hoạt động:
- Mình gửi PROMPT (hướng dẫn) cho AI qua API
- AI đọc prompt, suy nghĩ, và trả kết quả
- Mình nhận kết quả và hiển thị

Đây là cách thủ công (custom) — gọi API trực tiếp.
Ở prototype tiếp theo, mình sẽ dùng FRAMEWORK (LangGraph, CrewAI)
để quản lý các agent dễ dàng hơn.
""")
