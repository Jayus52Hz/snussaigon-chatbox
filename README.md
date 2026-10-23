# Snus Sài Gòn Chatbox

Chatbox tách từ `Jayus52Hz/snussaigon-shopnex-public`: Python server, widget và KB. Không cần Next.js, Payload, database, Node.js hoặc cài thêm package Python.

## Chạy local

Yêu cầu Python 3.10+.

```powershell
git clone https://github.com/Jayus52Hz/snussaigon-chatbox.git
cd snussaigon-chatbox
Copy-Item .env.example .env
python server/app.py
```

Mở **http://127.0.0.1:8788**. Nếu không tạo `.env`, cổng mặc định là 8787.

Không có key, server trả phản hồi mẫu để test mở/đóng chat, gửi tin, lịch sử và reset. Đây không phải câu trả lời AI.

Để dùng Anthropic, sửa `.env` rồi khởi động lại server:

```dotenv
ANTHROPIC_API_KEY=your-api-key
MODEL=your-enabled-anthropic-model-id
```

Điền model ID mà tài khoản Anthropic của bạn có quyền sử dụng. API key chỉ ở server; `.env` đã được bỏ qua bởi Git. Biến môi trường của terminal được ưu tiên hơn `.env`.

## Thành phần

- `server/app.py`: server standard library, trang test và endpoint `/chat/api/message` (SSE `message` + `done`). Câu trả lời được tạo xong rồi gửi một lần; chưa stream từng token.
- `server/static/widget.js`: widget, lịch sử hội thoại trong bộ nhớ tab, reset, timeout và thông báo lỗi.
- `server/static/demo.html`: trang test riêng, hiển thị chế độ demo/AI.
- `bot/system_prompt.md`, `kb/`: prompt và kiến thức snapshot ngày 22/10/2026. Giá/tồn kho không cập nhật trực tiếp.

Repo chỉ lấy source cần thiết và KB Markdown; không kèm raw payments, dữ liệu tài khoản ngân hàng, `.env` hay lịch sử Git của repo gốc. Không cần chạy scanner để thử chatbox.

Widget dùng endpoint cùng origin. Để nhúng trên trang khác, phục vụ `/chat/*` qua reverse proxy cùng origin và thêm `<script src="/chat/widget.js"></script>`. Có thể gọi `window.SnusChat.open()`.

Đây là bản test local, mặc định chỉ bind loopback. Chưa có xác thực, rate limit hoặc quản lý ngân sách để mở public. Chưa xác minh câu trả lời bằng API thật nếu chưa cấu hình key/model.

## Kiểm tra

```powershell
python -m unittest discover -s tests -v
```
