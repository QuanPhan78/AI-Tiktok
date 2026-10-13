"""
=============================================
PROTOTYPE 3B: LANGGRAPH + GEMINI (MIEN PHI!)
=============================================
Muc dich: Xay he thong 4 agent bang LangGraph + Google Gemini.
Chi phi: $0 (MIEN PHI!)
"""
import os
import sys
import time
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key or api_key.startswith("AIza-xxxx"):
    print("Chua co GEMINI_API_KEY!")
    sys.exit(1)

from google import genai
from google.genai import types
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

print("=" * 60)
print("TEST 3B: LangGraph + Gemini (MIEN PHI!)")
print("=" * 60)
print()

client = genai.Client(api_key=api_key)
MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash"]

def call_gemini(prompt, max_retries=3):
    for model in MODELS:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.7)
                )
                return response.text
            except Exception as e:
                error_msg = str(e)
                if "503" in error_msg or "UNAVAILABLE" in error_msg:
                    time.sleep(3)
                elif "404" in error_msg or "no longer available" in error_msg:
                    break
                else:
                    if attempt < max_retries - 1:
                        time.sleep(2)
    return "Loi: Khong the goi API"

class AgentState(TypedDict):
    product_name: str
    product_info: str
    research_result: str
    script_result: str
    hashtags: str
    quality_result: str

def research_node(state: AgentState) -> dict:
    print("[Research Agent] Dang phan tich san pham...")
    result = call_gemini(f"Phan tich san pham cho TikTok:\nSan pham: {state['product_name']}\nThong tin: {state['product_info']}\nTra loi ngan gon 4 y: Doi tuong, USP, Goc tiep can, Pain point.")
    print("   Done!")
    return {"research_result": result}

def script_node(state: AgentState) -> dict:
    print("[Script Writer] Dang viet kich ban...")
    result = call_gemini(f"Viet kich ban TikTok 80 giay:\nSan pham: {state['product_name']}\nNghien cuu: {state['research_result']}\nYeu cau: Hook(3s), Body(22s), CTA(5s), Voice-over, Hinh anh. Giong Gen Z.")
    print("   Done!")
    return {"script_result": result}

def hashtag_node(state: AgentState) -> dict:
    print("[Hashtag Agent] Dang chon hashtag...")
    result = call_gemini(f"Tao 5-8 hashtag TikTok cho kich ban:\n{state['script_result'][:300]}")
    print("   Done!")
    return {"hashtags": result}

def quality_check_node(state: AgentState) -> dict:
    print("[Quality Check] Dang kiem tra...")
    result = call_gemini(f"Cham diem (1-10) kich ban TikTok nay va cho nhan xet:\n{state['script_result']}\nHashtags: {state['hashtags']}")
    print("   Done!")
    return {"quality_result": result}

graph = StateGraph(AgentState)
graph.add_node("research", research_node)
graph.add_node("script", script_node)
graph.add_node("hashtag", hashtag_node)
graph.add_node("quality_check", quality_check_node)
graph.add_edge(START, "research")
graph.add_edge("research", "script")
graph.add_edge("script", "hashtag")
graph.add_edge("hashtag", "quality_check")
graph.add_edge("quality_check", END)
app = graph.compile()

print("Bat dau chay pipeline 4 agent (LangGraph)...")
result = app.invoke({
    "product_name": "Kem chong nang ABC",
    "product_info": "SPF50+ PA++++, khong bong nhon, tham nhanh, chiet xuat rau ma, gia 199k, cho da dau",
    "research_result": "",
    "script_result": "",
    "hashtags": "",
    "quality_result": "",
})

print("\n--- KET QUA CUOI CUNG ---")
print("✅ HOAN THANH PIPELINE LANGGRAPH!\n")

print("=" * 60)
print("📊 1. KẾT QUẢ NGHIÊN CỨU")
print("=" * 60)
print(result["research_result"])

print("\n" + "=" * 60)
print("🎬 2. KỊCH BẢN TIKTOK")
print("=" * 60)
print(result["script_result"])

print("\n" + "=" * 60)
print("#️⃣ 3. HASHTAGS")
print("=" * 60)
print(result["hashtags"])

print("\n" + "=" * 60)
print("🔎 4. ĐÁNH GIÁ CHẤT LƯỢNG (QC)")
print("=" * 60)
print(result["quality_result"])
