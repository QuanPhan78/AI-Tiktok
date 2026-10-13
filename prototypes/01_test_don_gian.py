"""
=============================================
PROTOTYPE 1: TEST ĐƠN GIẢN (KHÔNG CẦN API KEY)
=============================================

Mục đích: Kiểm tra xem Python và thư viện đã cài đúng chưa.
           Hiểu cách một "agent" đơn giản hoạt động.

Chạy: python prototypes/01_test_don_gian.py
"""

print("=" * 60)
print("🧪 TEST 1: Agent Đơn Giản (Không cần API key)")
print("=" * 60)
print()

# =============================================
# BƯỚC 1: Giả lập một "Agent" bằng Python thuần
# =============================================
# Agent = một function (hàm) biết nhận dữ liệu và trả kết quả
# Ở đây mình chưa dùng AI thật, chỉ dùng text có sẵn để test cấu trúc

def research_agent(product_name, product_info):
    """
    Agent Nghiên Cứu — phân tích sản phẩm
    Nhận vào: tên sản phẩm + thông tin
    Trả ra: kết quả phân tích
    """
    print(f"🔍 Research Agent đang phân tích: {product_name}...")
    
    # Giả lập kết quả (sau này sẽ thay bằng AI thật)
    result = {
        "doi_tuong": "Nữ 18-25 tuổi, quan tâm skincare",
        "usp": f"Điểm nổi bật của {product_name}: {product_info}",
        "goc_tiep_can": "Review trải nghiệm thực tế, before/after"
    }
    
    print(f"   ✅ Đã phân tích xong!")
    return result


def script_writer_agent(product_name, research_result):
    """
    Agent Viết Kịch Bản — viết script TikTok
    Nhận vào: tên sản phẩm + kết quả nghiên cứu
    Trả ra: kịch bản video
    """
    print(f"✍️  Script Writer đang viết kịch bản...")
    
    # Giả lập kịch bản (sau này sẽ thay bằng AI thật)
    script = {
        "hook": f"Dừng lại! Bạn có biết {product_name} đang viral không?",
        "body": f"Mình đã thử {product_name} trong 7 ngày. "
                f"Đối tượng: {research_result['doi_tuong']}. "
                f"{research_result['usp']}",
        "cta": "Link sản phẩm trong bio, hôm nay giảm 30%!",
        "hashtags": ["#skincare", "#review", "#viral", "#tiktokvietnam"]
    }
    
    print(f"   ✅ Đã viết xong kịch bản!")
    return script


def quality_check_agent(script):
    """
    Agent Kiểm Tra — kiểm tra chất lượng kịch bản
    Nhận vào: kịch bản
    Trả ra: kết quả kiểm tra (đạt/không đạt)
    """
    print(f"🔎 Quality Check đang kiểm tra...")
    
    # Kiểm tra đơn giản
    checks = []
    
    # Check 1: Hook có đủ ngắn không?
    if len(script["hook"]) < 100:
        checks.append("✅ Hook đủ ngắn, gọn")
    else:
        checks.append("❌ Hook quá dài, cần rút ngắn")
    
    # Check 2: Có CTA không?
    if script["cta"]:
        checks.append("✅ Có CTA (kêu gọi hành động)")
    else:
        checks.append("❌ Thiếu CTA")
    
    # Check 3: Có hashtag không?
    if len(script["hashtags"]) >= 3:
        checks.append(f"✅ Có {len(script['hashtags'])} hashtag")
    else:
        checks.append("❌ Cần thêm hashtag")
    
    passed = all("✅" in c for c in checks)
    
    print(f"   {'✅ ĐẠT!' if passed else '❌ CHƯA ĐẠT'}")
    return {"passed": passed, "checks": checks}


# =============================================
# BƯỚC 2: Chạy pipeline (nối các agent lại)
# =============================================
print()
print("📦 THÔNG TIN SẢN PHẨM:")
print("-" * 40)

product_name = "Kem chống nắng ABC"
product_info = "SPF50+, không gây bóng nhờn, giá 199k, cho da dầu"

print(f"   Tên: {product_name}")
print(f"   Info: {product_info}")
print()

# Bước 1: Research
print("=" * 40)
print("BƯỚC 1: NGHIÊN CỨU")
print("=" * 40)
research_result = research_agent(product_name, product_info)
print(f"   Đối tượng: {research_result['doi_tuong']}")
print(f"   USP: {research_result['usp']}")
print(f"   Góc tiếp cận: {research_result['goc_tiep_can']}")
print()

# Bước 2: Viết kịch bản
print("=" * 40)
print("BƯỚC 2: VIẾT KỊCH BẢN")
print("=" * 40)
script = script_writer_agent(product_name, research_result)
print(f"   HOOK: {script['hook']}")
print(f"   BODY: {script['body']}")
print(f"   CTA: {script['cta']}")
print(f"   HASHTAGS: {' '.join(script['hashtags'])}")
print()

# Bước 3: Kiểm tra chất lượng
print("=" * 40)
print("BƯỚC 3: KIỂM TRA CHẤT LƯỢNG")
print("=" * 40)
qc_result = quality_check_agent(script)
for check in qc_result["checks"]:
    print(f"   {check}")
print()

# Kết quả cuối cùng
print("=" * 60)
if qc_result["passed"]:
    print("🎉 HOÀN THÀNH! Kịch bản đã sẵn sàng.")
else:
    print("⚠️  Kịch bản cần chỉnh sửa.")
print("=" * 60)

print()
print("=" * 60)
print("📖 GIẢI THÍCH:")
print("=" * 60)
print("""
Bạn vừa chạy một PIPELINE (đường ống xử lý) gồm 3 AGENT:

1. Research Agent: nhận sản phẩm → phân tích → trả insight
2. Script Writer Agent: nhận insight → viết kịch bản
3. Quality Check Agent: nhận kịch bản → kiểm tra chất lượng

Đây chỉ là bản giả lập (dùng text có sẵn, chưa dùng AI thật).
Ở các prototype tiếp theo, mình sẽ thay bằng AI thật (GPT-4o)!

Cấu trúc này giống y hệt hệ thống thật mình sẽ xây:
  Sản phẩm → Research → Script → QC → Kịch bản hoàn chỉnh
""")
