# Snus Sài Gòn Chatbox

Chatbox tách từ `Jayus52Hz/snussaigon-shopnex-public`: Python server, widget và KB. Bản local dùng **GPT 5.6 Luna qua Codex CLI đã đăng nhập ChatGPT**, không cần API key riêng. Không cần Next.js, Payload, database hoặc package Python ngoài standard library.

## Chạy local

Yêu cầu Python 3.10+ và Codex CLI mới có hỗ trợ `gpt-5.6-luna`.

```powershell
git clone https://github.com/Jayus52Hz/snussaigon-chatbox.git
cd snussaigon-chatbox
Copy-Item .env.example .env
codex login
python server/app.py
```

Mở **http://127.0.0.1:8788**. Nếu không tạo `.env`, cổng mặc định là 8787.

Đăng nhập bằng tài khoản ChatGPT trong `codex login`. Máy đã đăng nhập thì không cần đăng nhập lại. Model mặc định là `gpt-5.6-luna`; quyền truy cập và hạn mức phụ thuộc tài khoản. Yêu cầu được xử lý trên dịch vụ OpenAI qua Codex, không chạy model offline trên máy.

Thiết lập mặc định trong `.env`:

```dotenv
AI_PROVIDER=codex
MODEL=gpt-5.6-luna
```

Nếu PATH trỏ đến Codex CLI cũ, đặt `CODEX_BIN` trong `.env` bằng đường dẫn đầy đủ tới bản mới. Các thiết lập này chỉ áp dụng cho tiến trình chatbox; không thay đổi model của ứng dụng Codex đang mở.

Chatbox giữ 8 tin nhắn gần nhất trong bộ nhớ tab và gửi lại ngữ cảnh mỗi lượt. Backend gọi `codex exec --ephemeral` cho từng lượt, dùng lại **phiên đăng nhập**; không tạo một chat bền vững trong giao diện ChatGPT/Codex. Reset hoặc tải lại trang sẽ xóa lịch sử. Cách này phù hợp test local, chưa phải tích hợp app-server cho hội thoại lưu lâu dài.

Backend không đọc/copy token đăng nhập: Codex CLI tự dùng thông tin đăng nhập của nó. Lệnh chạy trong thư mục tạm, sandbox chỉ đọc, tắt shell tool/apps/multi-agent và bỏ qua config người dùng. Không đưa lỗi chi tiết hay token về trình duyệt. `.env` đã được bỏ qua bởi Git; biến môi trường terminal được ưu tiên hơn `.env`.

Chế độ `AI_PROVIDER=demo` chỉ trả phản hồi mẫu và không gọi AI. Giữ tùy chọn cũ `AI_PROVIDER=anthropic` nếu muốn dùng `ANTHROPIC_API_KEY` cùng `MODEL` Anthropic phù hợp.

## Thành phần

- `server/app.py`: server standard library, trang test và endpoint `/chat/api/message` (SSE `message` + `done`). Câu trả lời được tạo xong rồi gửi một lần; chưa stream từng token.
- `server/static/widget.js`: widget, lịch sử hội thoại trong bộ nhớ tab, reset, timeout và thông báo lỗi.
- `server/static/demo.html`: trang chat tối giản, mở trực tiếp hội thoại.
- `bot/system_prompt.md`, `kb/`: prompt và kiến thức snapshot ngày 22/10/2026. Giá/tồn kho không cập nhật trực tiếp.

Repo chỉ lấy source cần thiết và KB Markdown; không kèm raw payments, dữ liệu tài khoản ngân hàng, `.env` hay lịch sử Git của repo gốc. Không cần chạy scanner để thử chatbox.

Widget dùng endpoint cùng origin. Để nhúng trên trang khác, phục vụ `/chat/*` qua reverse proxy cùng origin và thêm `<script src="/chat/widget.js"></script>`. Có thể gọi `window.SnusChat.open()`.

Đây là bản test local, mặc định chỉ bind loopback. Chưa có xác thực, rate limit hoặc quản lý ngân sách để mở public. Người khác clone repo cần đăng nhập Codex bằng tài khoản của họ.

## Kiểm tra

```powershell
python -m unittest discover -s tests -v
```
