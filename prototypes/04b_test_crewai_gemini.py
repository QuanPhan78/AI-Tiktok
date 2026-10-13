"""
=============================================
PROTOTYPE 4B: CREWAI STYLE + GEMINI (MIEN PHI!)
=============================================
Muc dich: Giao viec cho Agent co Role/Goal/Backstory dung Gemini.
Chi phi: $0 (MIEN PHI!)
"""
import os
import sys
import time
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    sys.exit(1)

from google import genai
from google.genai import types

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
    return "Loi"

class SimpleAgent:
    def __init__(self, role, goal, backstory):
        self.role = role
        self.goal = goal
        self.backstory = backstory
    
    def execute(self, task_description, context=""):
        prompt = f"""Vai tro: {self.role}
Muc tieu: {self.goal}
Background: {self.backstory}

Ket qua tu buoc truoc (neu co):
{context}

Nhiem vu cua ban:
{task_description}"""
        return call_gemini(prompt)

print("=" * 60)
print("TEST 4B: CrewAI Style + Gemini (MIEN PHI!)")
print("=" * 60)

researcher = SimpleAgent(
    role="Chuyen gia nghien cuu Tiktok",
    goal="Tim insight viral",
    backstory="Am hieu Gen Z va xu huong TikTok VN."
)
scriptwriter = SimpleAgent(
    role="Bien kich Tiktok",
    goal="Viet script 30s",
    backstory="Biet cach hook nguoi xem ngay 3s dau."
)

product = "Kem chong nang ABC, SPF50+, cho da dau, 199k."

print("\n1. Giao viec cho Chuyen gia nghien cuu...")
research = researcher.execute(f"Phan tich nhanh san pham: {product}")
print("   Done!")

print("\n2. Giao viec cho Bien kich...")
script = scriptwriter.execute("Viet kich ban 180s.", context=research)
print("   Done!")

print("\n--- KET QUA KICH BAN ---")
print(script[:500] + "...\n(Kich ban da duoc tao thanh cong!)")
