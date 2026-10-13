"""
=============================================
BẢNG SO SÁNH FRAMEWORK — Điền sau khi chạy cả 3 prototype
=============================================

Chạy:  python prototypes/05_so_sanh.py
"""

print("=" * 70)
print("📊 BẢNG SO SÁNH 3 PHƯƠNG ÁN")
print("=" * 70)
print()

# Bạn sẽ tự điền điểm sau khi chạy cả 3 prototype
# Thang điểm: 1 (kém) → 5 (tốt nhất)

criteria = [
    "Dễ setup & cài đặt",
    "Code dễ hiểu, dễ đọc",
    "Kết quả kịch bản tốt",
    "Dễ thêm agent mới",
    "Dễ sửa khi lỗi (debug)",
    "Tài liệu & tutorial nhiều",
]

print("Hướng dẫn: Chấm điểm 1-5 cho mỗi ô (1=kém, 5=tốt nhất)")
print()

# Header
print(f"{'Tiêu chí':<30} {'Custom':>10} {'LangGraph':>12} {'CrewAI':>10}")
print("-" * 70)

for c in criteria:
    print(f"{c:<30} {'?':>10} {'?':>12} {'?':>10}")

print("-" * 70)
print(f"{'TỔNG ĐIỂM':<30} {'?/30':>10} {'?/30':>12} {'?/30':>10}")
print()

print("=" * 70)
print("📝 GHI CHÚ THÊM")  
print("=" * 70)
print("""
Sau khi chấm điểm, trả lời các câu hỏi:

1. Framework nào em thấy DỄ HIỂU nhất?
   → Trả lời: _______________

2. Framework nào cho KẾT QUẢ TỐT nhất?
   → Trả lời: _______________

3. Framework nào em MUỐN DÙNG cho dự án?
   → Trả lời: _______________

4. Lý do chọn:
   → _______________________________________________
   → _______________________________________________

═══════════════════════════════════════════════════

GỢI Ý CỦA MÌNH:

🏆 Nếu team muốn KIỂM SOÁT CHI TIẾT → chọn LangGraph
   - Phù hợp khi cần: vòng lặp (retry), nhánh (if/else), 
     custom flow phức tạp
   - Cần: kiến thức Python trung bình+

🏆 Nếu team muốn LÀM NHANH, ÍT CODE → chọn CrewAI
   - Phù hợp khi cần: triển khai nhanh, logic đơn giản
   - Cần: kiến thức Python cơ bản

🏆 Nếu team muốn HIỂU SÂU, TỰ CHỦ → chọn Custom
   - Phù hợp khi: muốn hiểu 100% code, không phụ thuộc framework
   - Cần: kiến thức Python tốt + hiểu API

💡 Khuyến nghị cho dự án này: LangGraph
   Lý do: Hệ thống cần xử lý phức tạp (retry khi QC fail, 
   nhiều nhánh, dễ mở rộng), LangGraph cho phép kiểm soát tốt nhất.
""")
