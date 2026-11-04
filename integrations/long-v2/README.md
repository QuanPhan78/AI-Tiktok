# Gói automation Content Studio v2 cho Long

Gói này gồm service Docker tối thiểu và workflow n8n để nhận nguyên đầu ra web 7 bước. Source nền từ [LongVu-AI/AI_Content_Automation](https://github.com/LongVu-AI/AI_Content_Automation), kèm thay đổi v2 đã chuẩn bị trong workspace. Đây là bản bàn giao để Long review/tích hợp, chưa phải thay đổi đã merge vào repo của Long.

Không có `.env` thật, database hoặc workflow Telegram trong gói. Các endpoint v1 có trong API vẫn được giữ; workflow n8n v1 tiếp tục lấy từ repo hiện có của Long.

## 1. Chuẩn bị cấu hình và Notion thử

Từ gốc repo AI-Tiktok, cài dependency theo [bài chính](../../docs/HANDOFF_CONTENT_STUDIO_V2.md), mở Docker Desktop rồi:

```powershell
cd integrations/long-v2
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Trong `.env` tại thư mục này, điền `NOTION_TOKEN` của integration, `NOTION_DATABASE_ID` của database v1/cấu trúc gốc và `NOTION_V2_DATABASE_ID` của **database thử khác**. Cho integration truy cập database thử. Có thể nhân cấu trúc database hiện có nhưng không sao chép các dòng dữ liệu.

Schema database thử phải có các cột dưới đây, đúng tên và kiểu; `status` cần lựa chọn `DRAFT`:

| Cột | Kiểu Notion |
|---|---|
| `request_id` | Title |
| `product_name`, `hook_text`, `voice_over_text`, `text_on_screen`, `image_prompt_en` | Rich text |
| `post_caption`, `hashtags`, `qc_feedback` | Rich text |
| `product_link` | URL |
| `qc_score` | Number |
| `status` | Select, gồm `DRAFT` |

Chạy preflight từ gốc repo; lệnh chỉ đọc schema, không tạo trang:

```powershell
cd ../..
.\.venv\Scripts\python.exe scripts/acceptance.py --env-file integrations/long-v2/.env preflight --side long
```

Nếu có lỗi, sửa cấu hình/schema trước khi gửi. Source dùng `notion-client==2.2.1`; giữ phiên bản đó cho đợt nghiệm thu, không tự nâng SDK trong lúc kiểm tra.

## 2. Chạy stack thử

```powershell
cd integrations/long-v2
docker compose -f docker-compose.yml -f docker-compose.acceptance.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.acceptance.yml up -d --build
```

- API: [health cổng 8000](http://127.0.0.1:8000/health), [tài liệu API](http://127.0.0.1:8000/docs).
- n8n: [cổng 5678](http://127.0.0.1:5678), hoàn tất thiết lập tài khoản local nếu chạy lần đầu.
- Override bật `CONTENT_V2_ACCEPTANCE_MODE=1`, từ chối ghi khi database thử thiếu/trùng database v1.
- Gateway tùy chọn cổng 5679 chỉ phục vụ webhook v2, để dùng khi cần kết nối hai máy. Chạy local không cần tunnel.

Stack dùng volume cho n8n và dữ liệu bàn giao. Không dùng `docker compose down -v` nếu cần giữ dữ liệu. Nếu máy đã chạy các container/cổng 8000 hoặc 5678, chọn cập nhật stack hiện có hoặc dừng đúng stack cũ trước; không chạy hai bản trên cùng cổng. Gói dùng tên container tương ứng source Long để thuận tiện đối chiếu.

## 3. Import workflow và Header Auth

1. Import [Content Studio - AI Agent Callback v2.json](n8n/Content%20Studio%20-%20AI%20Agent%20Callback%20v2.json).
2. Tạo credential **Header Auth**, tên `Content Studio v2 - X-Content-Token`, header `X-Content-Token`. Giá trị là token bí mật tự đặt, trùng `WEBHOOK_V2_TOKEN` trong `.env` của web.
3. Chọn credential đó ở node Webhook v2. Workflow import để **inactive**; bật workflow khi đã cấu hình đúng.
4. Web cùng máy dùng URL production `http://127.0.0.1:5678/webhook/ai-agent-callback-v2`. Sau khi đổi `.env`, khởi động lại web để nạp cấu hình.
5. Thiếu/sai Header Auth phải bị từ chối, không tạo trang Notion. Workflow tắt lưu execution data chứa header; không bật lại để chụp token.

Node HTTP gọi `http://python-service:8000/api/v2/content/ai-output` trong mạng Docker. Không thay nó bằng `127.0.0.1:8000` trong container n8n. Biên nhận được trả nguyên về web; chỉ trả thành công sau khi Notion đã ghi đủ.

Nếu chạy khác máy, cung cấp URL HTTPS v2 có Header Auth cho máy web. Gateway trong override chỉ mở đường dẫn callback; chỉ mở tunnel sau khi xác thực đã hoạt động, không mở giao diện n8n ra ngoài. `.env` và credential được trao đổi qua kênh riêng, không đặt vào URL hoặc Git.

## 4. Đọc lại và đối chiếu

Từ API, lấy `GET /api/v2/content/{request_id}/revisions/{revision}`. Dùng revision **trong bundle**, lưu nguyên JSON thành `readback.json`; nhận biên nhận từ web hoặc response n8n. Từ gốc repo:

```powershell
.\.venv\Scripts\python.exe scripts/acceptance.py compare --bundle handoff.json --receipt receipt.json --readback readback.json --database-id ID_DATABASE_THU --zip goi-da-duyet.zip
```

`session.handoff` là phần `data` của biên nhận; nếu lấy từ API phiên, bọc nó thành `{"success":true,"data":...}` trước khi lưu `receipt.json`. Công cụ so request/revision, database, SHA-256, toàn bộ payload, prompt Markdown và hash hai ảnh trong ZIP. Kết quả kỹ thuật đạt vẫn cần Bảo xác nhận clip và Long kiểm tra lưu trữ sau restart.

JSON đầy đủ và receipt SQLite nằm ở `/data`, mount volume `handoff_data`. Gửi lại cùng bản không tạo trùng; bản đã sang trạng thái ngoài `DRAFT`/`FAILED` không được ghi đè bằng revision mới. Lỗi 502 có thể đã lưu một phần; gửi lại **nguyên bản** để tiếp tục, không sửa payload cùng revision.

## 5. Áp dụng vào repo hiện có của Long

Review diff của `python-service/app/main.py`, hai module v2, Compose, workflow và script trước khi áp dụng. `main.py` cần import/include router v2; không chép đè file nếu repo Long đã có thay đổi mới. Giữ `.env`, workflow v1 và volume hiện tại; bổ sung volume `handoff_data`, các biến v2 cùng database thử. `SOURCE_MANIFEST.json` liệt kê hash các file đóng gói để đối chiếu.

Từ gốc AI-Tiktok, kiểm thử mặc định dùng gói này. Muốn kiểm tra một checkout khác của Long, đặt `LONG_AUTOMATION_ROOT` bằng đường dẫn tới thư mục có `python-service/` và `n8n/`, rồi chạy lại suite. Hai bản contract phải giống nguyên vẹn.

Xem [runbook SEJOY](../../docs/SEJOY_ACCEPTANCE_RUNBOOK.md) và [API web](../../docs/CONTENT_STUDIO_V2.md). Bot Telegram, tạo video và đăng TikTok chưa nằm trong gói này.
