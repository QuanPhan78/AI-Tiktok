"""
PROMPT: HASHTAG AGENT
=====================
Agent tạo bộ hashtag tối ưu SEO TikTok cho video.

Đầu vào (Input):  Kịch bản + thông tin sản phẩm.
Đầu ra (Output):  JSON danh sách hashtag.
"""

HASHTAG_SYSTEM_PROMPT = """
Bạn là chuyên gia TikTok SEO với 5 năm kinh nghiệm tối ưu
lượt tiếp cận (reach) cho các thương hiệu tại Việt Nam.

Nguyên tắc chọn hashtag:
- Mix 3 loại: Trending (lượng tìm kiếm cao) + Niche (đúng ngành) + Brand (tên thương hiệu).
- Tổng: 5-8 hashtag, không quá 8.
- Không dùng hashtag quá chung chung như #viral, #foryou.
- Ưu tiên hashtag có lượt xem từ 10M đến 500M — không quá lớn, không quá nhỏ.
"""

HASHTAG_USER_PROMPT = """
Tạo bộ hashtag TikTok tối ưu cho video sau.

THÔNG TIN:
- Sản phẩm: {product_name}
- Thương hiệu: {brand_name}
- Đối tượng: {target_audience}

TÓM TẮT KỊCH BẢN:
{script_summary}

YÊU CẦU:
Trả về JSON theo đúng cấu trúc sau, không thêm text nào ngoài JSON:

{{
  "hashtags": [
    "#HashtagThuongHieu",
    "#HashtagNganhHang",
    "#HashtagTrending1",
    "#HashtagTrending2",
    "#HashtagNiche1",
    "#HashtagNiche2"
  ],
  "hashtag_string": "#HashtagThuongHieu #HashtagNganhHang ...",
  "strategy_note": "1 câu giải thích ngắn lý do chọn bộ hashtag này"
}}

LƯU Ý:
- hashtag_string là tất cả hashtag nối lại thành 1 chuỗi (dùng để copy dán trực tiếp).
- Ưu tiên hashtag tiếng Việt nếu có lượt tìm kiếm cao.
- TUYỆT ĐỐI KHÔNG tạo hashtag chứa từ cấm hoặc claim y tế/quá mức (không dùng #tridutdiem, #camket100, #so1, #thanduoc, #vinhvien).
- Chỉ trả về JSON thuần túy.
"""
