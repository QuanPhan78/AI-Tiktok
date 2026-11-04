# Mẫu tin nhắn gửi nhóm

Sau khi nhánh được đẩy lên GitHub, gửi nội dung dưới đây qua nhóm Zalo và đính kèm ZIP SEJOY xuất từ Bước 7. Đây là mẫu để người dùng gửi, không phải thông báo đã được gửi tự động.

---

Mình đã đưa bài hướng dẫn và source Content Studio v2 lên GitHub:

https://github.com/QuanPhan78/AI-Tiktok/blob/docs/content-studio-v2-handoff/docs/HANDOFF_CONTENT_STUDIO_V2.md

Trong bài có cách chạy web, luồng 7 bước, phần bàn giao dữ liệu và source automation v2. PR để xem thay đổi sẽ được gửi kèm link sau khi tạo.

- Bảo: nhận ZIP SEJOY mình đính kèm riêng, kiểm tra ảnh rồi dùng nguyên prompt Cảnh 2 cùng hai ảnh để tạo thử clip 8 giây. Gửi lại clip gốc và lỗi cần sửa, kèm mã phiên/bản nội dung.
- Long: xem phần `integrations/long-v2`, thử trên database Notion riêng, import workflow callback v2 rồi kiểm tra biên nhận và JSON đọc lại. Có thể chạy Docker trên cùng máy để thử trước, chưa cần URL HTTPS nếu cùng máy.

SEJOY đã xuất được bộ prompt bốn cảnh, QC AI 9/10. Lần gửi gần nhất lỗi kết nối nên chưa xác nhận hệ thống automation nhận đủ dữ liệu. Đợt này chưa tích hợp Telegram hoặc đăng TikTok; mình cần hai bạn xác nhận clip thử và dữ liệu nhận được để hoàn tất nghiệm thu.

---

ZIP thật nằm trên máy tạo phiên, không có trong repo clone mới. Không gửi `.env`, token hoặc database phiên vào nhóm. Các ví dụ trong repo dùng dữ liệu tổng hợp và ảnh minh họa kiểm thử.
