"""
=============================================
PROTOTYPE 4: PHONG CÁCH CREWAI (Giả lập)
=============================================

Mục đích: Trải nghiệm CÁCH TIẾP CẬN của CrewAI — tạo agent với 
           role/goal/backstory — nhưng dùng OpenAI API trực tiếp.

Tại sao không cài CrewAI thật?
- CrewAI chưa hỗ trợ Python 3.14 (phiên bản mới nhất của bạn)
- Nhưng CÁCH NGHĨ của CrewAI rất hay, mình sẽ giả lập nó!
- Khi CrewAI update hỗ trợ Python 3.14, bạn có thể chuyển sang dễ dàng

Cần:   API key OpenAI
Chạy:  python prototypes/04_test_crewai.py

💰 Chi phí: Khoảng 300-800 VND mỗi lần chạy
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

# Kiểm tra API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key.startswith("sk-xxxx"):
    print("Chua co API key! Xem huong dan trong file 02_test_openai.py")
    sys.exit(1)

from openai import OpenAI
client = OpenAI()

print("=" * 60)
print("TEST 4: Phong cach CrewAI (Agent voi Role/Goal/Backstory)")
print("=" * 60)
print()

# =============================================
# CREWAI STYLE: Mỗi agent có ROLE, GOAL, BACKSTORY
# =============================================
# Đây chính là ý tưởng cốt lõi của CrewAI:
# Thay vì viết prompt dài, bạn "tuyển nhân viên" bằng cách
# mô tả vai trò, mục tiêu, và background của họ.

class SimpleAgent:
    """
    Agent đơn giản theo phong cách CrewAI.
    Mỗi agent có: role (vai trò), goal (mục tiêu), backstory (background).
    """
    
    def __init__(self, role, goal, backstory, model="gpt-4o-mini"):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.model = model
    
    def execute(self, task_description, context=""):
        """Thực hiện nhiệm vụ"""
        
        # Tự động tạo system prompt từ role/goal/backstory
        system_prompt = f"""Vai tro: {self.role}
Muc tieu: {self.goal}
Background: {self.backstory}

Ban hay hoan thanh nhiem vu duoi day mot cach tot nhat co the."""
        
        # Thêm context (kết quả từ agent trước) nếu có
        user_prompt = task_description
        if context:
            user_prompt = f"""Ket qua tu buoc truoc:
{context}

---

Nhiem vu cua ban:
{task_description}"""
        
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
        )
        
        return response.choices[0].message.content


# =============================================
# BƯỚC 1: "TUYỂN" 4 NHÂN VIÊN AI
# =============================================
print("Dang 'tuyen' 4 nhan vien AI...")
print()

# Nhân viên 1: Chuyên gia nghiên cứu
researcher = SimpleAgent(
    role="Chuyen gia nghien cuu san pham & thi truong TikTok",
    goal="Phan tich san pham, tim insight va goc tiep can TikTok tot nhat cho thi truong Viet Nam",
    backstory="""Ban la chuyen gia marketing voi 5 nam kinh nghiem phan tich 
    san pham tieu dung tai Viet Nam. Ban am hieu xu huong TikTok, hanh vi 
    mua sam cua Gen Z, va biet cach tim ra goc tiep can viral."""
)
print(f"  [1] Da tuyen: {researcher.role}")

# Nhân viên 2: Biên kịch
scriptwriter = SimpleAgent(
    role="Bien kich TikTok chuyen nghiep",
    goal="Viet kich ban video TikTok 30 giay hap dan, co kha nang viral cao",
    backstory="""Ban la bien kich content viral hang dau Viet Nam, chuyen viet 
    script cho cac brand tren TikTok. Phong cach viet: tre trung, gan gui, 
    nhu dang noi chuyen voi ban be. Ban gioi tao hook gay to mo va CTA tu nhien."""
)
print(f"  [2] Da tuyen: {scriptwriter.role}")

# Nhân viên 3: Chuyên gia hashtag
hashtag_expert = SimpleAgent(
    role="Chuyen gia Hashtag & TikTok SEO",
    goal="Chon bo hashtag toi uu de video dat reach cao nhat",
    backstory="""Ban la chuyen gia TikTok SEO, am hieu thuat toan TikTok. 
    Ban biet cach mix hashtag trending voi hashtag niche de toi uu 
    kha nang len For You Page."""
)
print(f"  [3] Da tuyen: {hashtag_expert.role}")

# Nhân viên 4: Biên tập viên QC
quality_checker = SimpleAgent(
    role="Bien tap vien kiem duyet noi dung",
    goal="Dam bao kich ban dat chat luong cao, phu hop brand va co kha nang viral",
    backstory="""Ban la bien tap vien cap cao voi con mat tinh tuong. 
    Ban kiem tra chat luong content theo cac tieu chi: hook hap dan, 
    USP ro rang, CTA tu nhien, phu hop target audience."""
)
print(f"  [4] Da tuyen: {quality_checker.role}")

print()
print("Da tuyen du 4 nhan vien!")
print()

# =============================================
# BƯỚC 2: GIAO NHIỆM VỤ TUẦN TỰ
# =============================================
product = """
Ten: Kem chong nang ABC
- SPF50+ PA++++
- Khong gay bong nhon, tham nhanh  
- Chiet xuat rau ma (Centella Asiatica) + Niacinamide
- Phu hop da dau, da hon hop
- Gia: 199.000 VND / 50ml
"""

print("=" * 60)
print("BUOC 1: Nghien cuu san pham")
print("=" * 60)
print("Dang xu ly... (doi 10-15 giay)")

research_result = researcher.execute(
    f"""Phan tich san pham sau cho video TikTok:
{product}

Hay cho biet:
1. Doi tuong muc tieu chi tiet
2. 3 diem noi bat (USP) hap dan nhat
3. 3 goc tiep can video TikTok phu hop
4. Pain points cua khach hang"""
)

print()
print(research_result)
print()

# -----

print("=" * 60)
print("BUOC 2: Viet kich ban")
print("=" * 60)
print("Dang xu ly... (doi 10-20 giay)")

script_result = scriptwriter.execute(
    f"""Viet kich ban video TikTok 30 giay cho san pham:
{product}

FORMAT BAT BUOC:
- HOOK (0:00 - 0:03): Cau mo dau gay to mo
- BODY (0:03 - 0:25): Trinh bay 2-3 USP hap dan
- CTA (0:25 - 0:30): Keu goi hanh dong tu nhien
- VOICE-OVER: Script doc voice day du
- HINH ANH: Goi y canh quay cho tung phan
- CAPTION: Caption cho post TikTok (ngan gon, co emoji)

Viet bang tieng Viet, giong Gen Z, vui tuoi.""",
    context=research_result  # Truyền kết quả nghiên cứu
)

print()
print(script_result)
print()

# -----

print("=" * 60)
print("BUOC 3: Chon hashtag")
print("=" * 60)
print("Dang xu ly... (doi 5-10 giay)")

hashtag_result = hashtag_expert.execute(
    """Tao bo hashtag toi uu cho video TikTok nay.

Yeu cau:
- 5-8 hashtag mix tieng Viet + tieng Anh
- Co hashtag trending (luong view cao)
- Co hashtag niche (dung nganh)
- Moi hashtag tren 1 dong, giai thich ngan tai sao chon""",
    context=script_result  # Truyền kịch bản
)

print()
print(hashtag_result)
print()

# -----

print("=" * 60)
print("BUOC 4: Kiem tra chat luong")
print("=" * 60)
print("Dang xu ly... (doi 10-15 giay)")

quality_result = quality_checker.execute(
    """Kiem tra chat luong kich ban TikTok.

Cham diem (1-10) theo cac tieu chi:
1. Hook: Co gay to mo, dung luot trong 3 giay dau?
2. USP: Diem noi bat san pham co ro rang?
3. CTA: Loi keu goi co tu nhien?
4. Tone: Giong dieu co phu hop Gen Z?
5. Viral: Tong the co tiem nang viral?

Cho diem tong /50 va goi y cai thien.""",
    context=f"Kich ban:\n{script_result}\n\nHashtags:\n{hashtag_result}"
)

print()
print(quality_result)

# =============================================
# TỔNG KẾT
# =============================================
print()
print("=" * 60)
print("GIAI THICH PHONG CACH CREWAI:")
print("=" * 60)
print("""
CrewAI tiep can the nao:

1. Tao AGENT bang cach mo ta: role, goal, backstory
   -> Giong nhu viet JD (job description) tuyen nhan vien

2. Giao TASK (nhiem vu) cho tung agent
   -> Giong nhu giao viec cho nhan vien

3. Agent tu dong truyen ket qua cho nhau
   -> Nhan vien truoc lam xong, gui ket qua cho nguoi tiep theo

UU DIEM phong cach CrewAI:
+ Rat truc quan — giong quan ly doi nhom that
+ Code ngan gon, de doc
+ De thay doi agent (chi can sua role/goal)

NHUOC DIEM:
- It kiem soat chi tiet flow
- Kho tao logic phuc tap (if/else, retry)

SO SANH VOI LANGGRAPH:
- CrewAI: "Tuyen nhan vien, giao viec, de ho tu lam"
- LangGraph: "Ve so do chi tiet, kiem soat tung buoc"

CA HAI DEU TOT — tuy vao nhu cau du an:
- Can linh hoat, nhanh -> CrewAI
- Can kiem soat, phuc tap -> LangGraph
""")
