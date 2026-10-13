"""
=============================================
PROTOTYPE 3: DÙNG LANGGRAPH
=============================================

Mục đích: Xây hệ thống agent bằng LangGraph framework.
           So sánh với cách custom (prototype 2).

LangGraph là gì?
- Framework giúp tạo WORKFLOW (luồng xử lý) cho AI agent
- Mình vẽ một GRAPH (sơ đồ) các bước, rồi LangGraph chạy theo
- Giống như vẽ flowchart, rồi máy tự chạy theo flowchart đó

Cần:   API key OpenAI
Chạy:  python prototypes/03_test_langgraph.py

💰 Chi phí: Khoảng 200-500 VND mỗi lần chạy
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

# Kiểm tra API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key.startswith("sk-xxxx"):
    print("⚠️  Chưa có API key! Xem hướng dẫn trong file 02_test_openai.py")
    sys.exit(1)

# Import thư viện
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated

print("=" * 60)
print("🤖 TEST 3: Agent với LangGraph")
print("=" * 60)
print()

# =============================================
# BƯỚC 1: ĐỊNH NGHĨA STATE (TRẠNG THÁI)
# =============================================
# State = "bộ nhớ" chung mà tất cả agent đều đọc/ghi vào
# Giống như một tờ giấy mà mọi người truyền tay nhau,
# mỗi người đọc thông tin và ghi thêm phần của mình

class AgentState(TypedDict):
    # Thông tin đầu vào
    product_name: str         # Tên sản phẩm
    product_info: str         # Mô tả sản phẩm
    
    # Kết quả từ các agent (ban đầu trống, sẽ được điền dần)
    research_result: str      # Kết quả từ Research Agent
    script_result: str        # Kết quả từ Script Writer
    hashtags: str             # Kết quả từ Hashtag Agent
    quality_result: str       # Kết quả từ Quality Check


# =============================================
# BƯỚC 2: TẠO AI MODEL
# =============================================
# Đây là "bộ não" mà các agent sẽ dùng
llm = ChatOpenAI(
    model="gpt-4o-mini",      # Model nào (gpt-4o-mini = rẻ, nhanh)
    temperature=0.7,           # Độ sáng tạo (0.7 = cân bằng)
)


# =============================================
# BƯỚC 3: TẠO CÁC AGENT (MỖI AGENT LÀ 1 FUNCTION)
# =============================================

def research_node(state: AgentState) -> dict:
    """
    AGENT 1: Nghiên cứu sản phẩm
    Nhận: tên + info sản phẩm
    Trả: insight + góc tiếp cận TikTok
    """
    print("🔍 [Research Agent] Đang phân tích sản phẩm...")
    
    prompt = f"""Phân tích sản phẩm cho video TikTok:
    
Sản phẩm: {state['product_name']}
Thông tin: {state['product_info']}

Cho biết ngắn gọn:
1. Đối tượng mục tiêu
2. 3 điểm nổi bật (USP)
3. Góc tiếp cận TikTok hay nhất
4. Pain point khách hàng"""

    result = llm.invoke(prompt)
    print("   ✅ Research xong!")
    
    # Trả kết quả → ghi vào state
    return {"research_result": result.content}


def script_node(state: AgentState) -> dict:
    """
    AGENT 2: Viết kịch bản TikTok
    Nhận: thông tin sản phẩm + nghiên cứu
    Trả: kịch bản hoàn chỉnh
    """
    print("✍️  [Script Writer] Đang viết kịch bản...")
    
    prompt = f"""Viết kịch bản TikTok 30 giây:

Sản phẩm: {state['product_name']}
Nghiên cứu: {state['research_result']}

Format:
- HOOK (3s): Câu gây tò mò
- BODY (22s): Trình bày USP hấp dẫn
- CTA (5s): Kêu gọi hành động
- VOICE-OVER: Script đọc đầy đủ
- HÌNH ẢNH: Gợi ý cảnh quay

Tiếng Việt, giọng Gen Z, vui tươi."""

    result = llm.invoke(prompt)
    print("   ✅ Script xong!")
    return {"script_result": result.content}


def hashtag_node(state: AgentState) -> dict:
    """
    AGENT 3: Sinh hashtag
    Nhận: kịch bản + thông tin sản phẩm
    Trả: danh sách hashtag
    """
    print("#️⃣  [Hashtag Agent] Đang chọn hashtag...")
    
    prompt = f"""Tạo hashtag cho video TikTok:

Sản phẩm: {state['product_name']}
Kịch bản: {state['script_result'][:200]}

Yêu cầu:
- 5-8 hashtag tiếng Việt + tiếng Anh
- Mix: hashtag trending + hashtag niche (chuyên ngành)
- Mỗi hashtag trên 1 dòng, giải thích ngắn tại sao chọn"""

    result = llm.invoke(prompt)
    print("   ✅ Hashtag xong!")
    return {"hashtags": result.content}


def quality_check_node(state: AgentState) -> dict:
    """
    AGENT 4: Kiểm tra chất lượng
    Nhận: kịch bản hoàn chỉnh
    Trả: đánh giá + gợi ý cải thiện
    """
    print("🔎 [Quality Check] Đang kiểm tra chất lượng...")
    
    prompt = f"""Kiểm tra chất lượng kịch bản TikTok sau:

{state['script_result']}

Hashtags: {state['hashtags']}

Chấm điểm (1-10) theo các tiêu chí:
1. Hook có gây tò mò không?
2. Body có trình bày USP rõ ràng không?
3. CTA có tự nhiên không?
4. Giọng điệu có phù hợp Gen Z không?
5. Tổng thể có viral potential không?

Cho điểm tổng và gợi ý cải thiện (nếu có)."""

    result = llm.invoke(prompt)
    print("   ✅ Quality Check xong!")
    return {"quality_result": result.content}


# =============================================
# BƯỚC 4: XÂY GRAPH (NỐI CÁC AGENT LẠI)
# =============================================
# Graph = sơ đồ các bước chạy theo thứ tự
# START → research → script → hashtag → quality_check → END

print("🔨 Đang xây dựng Graph (sơ đồ agent)...")

# Tạo graph với state
graph = StateGraph(AgentState)

# Thêm các node (mỗi node = 1 agent)
graph.add_node("research", research_node)
graph.add_node("script", script_node)
graph.add_node("hashtag", hashtag_node)
graph.add_node("quality_check", quality_check_node)

# Nối các node theo thứ tự
graph.add_edge(START, "research")            # Bắt đầu → Research
graph.add_edge("research", "script")          # Research → Script
graph.add_edge("script", "hashtag")           # Script → Hashtag
graph.add_edge("hashtag", "quality_check")    # Hashtag → QC
graph.add_edge("quality_check", END)          # QC → Kết thúc

# Compile (biên dịch) graph
app = graph.compile()

print("   ✅ Graph đã sẵn sàng!")
print()

# =============================================
# BƯỚC 5: CHẠY!
# =============================================
print("🚀 Bắt đầu chạy pipeline...")
print("   (Sẽ gọi AI 4 lần, đợi khoảng 30-60 giây)")
print()

result = app.invoke({
    "product_name": "Kem chống nắng ABC",
    "product_info": "SPF50+ PA++++, không bóng nhờn, thấm nhanh, chiết xuất rau má, giá 199k, cho da dầu",
    "research_result": "",
    "script_result": "",
    "hashtags": "",
    "quality_result": "",
})

# =============================================
# BƯỚC 6: HIỂN THỊ KẾT QUẢ
# =============================================
print()
print("=" * 60)
print("📊 KẾT QUẢ NGHIÊN CỨU")
print("=" * 60)
print(result["research_result"])

print()
print("=" * 60)
print("📝 KỊCH BẢN TIKTOK")
print("=" * 60)
print(result["script_result"])

print()
print("=" * 60)
print("#️⃣  HASHTAGS")
print("=" * 60)
print(result["hashtags"])

print()
print("=" * 60)
print("✅ ĐÁNH GIÁ CHẤT LƯỢNG")
print("=" * 60)
print(result["quality_result"])

print()
print("=" * 60)
print("📖 GIẢI THÍCH LANGGRAPH:")
print("=" * 60)
print("""
LangGraph hoạt động thế nào:

1. Mình định nghĩa STATE (bộ nhớ chung)
   → Giống tờ giấy truyền tay

2. Mình tạo các NODE (agent)
   → Mỗi agent là 1 function, đọc state và ghi kết quả vào state

3. Mình nối các EDGE (đường nối)
   → Xác định thứ tự: Research → Script → Hashtag → QC

4. LangGraph tự chạy theo graph
   → Mình chỉ cần gọi app.invoke() là xong!

ƯU ĐIỂM LangGraph:
+ Kiểm soát được thứ tự từng bước
+ Dễ thêm/bớt agent
+ Có thể tạo nhánh (if/else), vòng lặp
+ Nhìn rõ luồng xử lý

NHƯỢC ĐIỂM:
- Code dài hơn custom
- Cần học thêm concepts (state, node, edge)
""")
