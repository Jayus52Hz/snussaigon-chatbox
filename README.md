# Snus Sài Gòn Chatbox

Chatbox tách từ `Jayus52Hz/snussaigon-shopnex-public`: Python server và giao diện chat; dữ liệu cửa hàng lấy live qua CMS MCP. Bản local dùng **GPT 5.6 Luna qua Codex CLI đã đăng nhập ChatGPT**, không cần API key riêng. Không cần Next.js, Payload, database hoặc package Python ngoài standard library.

## Chạy local

Yêu cầu Python 3.10+ và Codex CLI mới có hỗ trợ `gpt-5.6-luna`.

```powershell
git clone https://github.com/Jayus52Hz/snussaigon-chatbox.git
cd snussaigon-chatbox
Copy-Item .env.example .env
codex login
# Dien SNUSSAIGON_MCP_TOKEN vao .env truoc khi chay
python server/app.py
```

Mở **http://127.0.0.1:8788**. Nếu không tạo `.env`, cổng mặc định là 8787.

Đăng nhập bằng tài khoản ChatGPT trong `codex login`. Máy đã đăng nhập thì không cần đăng nhập lại. Model mặc định là `gpt-5.6-luna`; quyền truy cập và hạn mức phụ thuộc tài khoản. Yêu cầu được xử lý trên dịch vụ OpenAI qua Codex, không chạy model offline trên máy.

Thiết lập mặc định trong `.env`:

```dotenv
AI_PROVIDER=codex
MODEL=gpt-5.6-luna
SNUSSAIGON_MCP_URL=https://snussaigon.com/api/mcp
SNUSSAIGON_MCP_TOKEN=your-local-cms-token
```

Nếu PATH trỏ đến Codex CLI cũ, đặt `CODEX_BIN` trong `.env` bằng đường dẫn đầy đủ tới bản mới. Các thiết lập này chỉ áp dụng cho tiến trình chatbox; không thay đổi model của ứng dụng Codex đang mở.

Chatbox giữ 8 tin nhắn gần nhất trong bộ nhớ tab và gửi lại ngữ cảnh mỗi lượt. Backend gọi `codex exec --ephemeral` cho từng lượt, dùng lại **phiên đăng nhập**; không tạo một chat bền vững trong giao diện ChatGPT/Codex. Reset hoặc tải lại trang bắt đầu cuộc chat mới; bản lưu hỗ trợ khách hàng vẫn còn trong SQLite local và không tự đưa vào ngữ cảnh của cuộc chat mới.

Backend không đọc/copy token đăng nhập: Codex CLI tự dùng thông tin đăng nhập của nó. Lệnh chạy trong thư mục tạm, sandbox chỉ đọc, tắt shell tool/apps/multi-agent và bỏ qua config người dùng. Không đưa lỗi chi tiết hay token về trình duyệt. `.env` đã được bỏ qua bởi Git; biến môi trường terminal được ưu tiên hơn `.env`.

Chế độ `AI_PROVIDER=demo` chỉ trả phản hồi mẫu và không gọi AI. Transport Anthropic cũ chưa hỗ trợ vòng gọi MCP; chế độ tra cứu live dùng `AI_PROVIDER=codex`.

## Dữ liệu live qua MCP

Luồng: câu hỏi và lịch sử → GPT 5.6 Luna chọn công cụ → CMS MCP trả dữ liệu mới → AI trả lời. Không còn hàm khớp từ khóa với catalog Markdown, không có bảng map câu hỏi cố định. Chào hỏi không cần gọi CMS.

- `find_products`: AI tách tên/brand/flavor/strength từ câu hỏi để tìm sản phẩm.
- `get_products`: đọc chi tiết theo ID, hỗ trợ nhiều ID trong một lần gọi.
- `get_shop_info`: FAQ, chính sách, vận chuyển, khuyến mãi và thông tin cửa hàng. Do MCP upstream chỉ có `raw_get` theo ID, cầu nối dùng REST public để liệt kê **ID**, sau đó đọc **nội dung từng tài liệu qua MCP**.

Không cache giá/tồn kho giữa các lượt. AI được yêu cầu tra lại kể cả khi lịch sử có giá/tồn kho cũ. Khi MCP lỗi, không dùng snapshot để giả làm dữ liệu hiện tại. Cầu nối không cung cấp công cụ ghi, orders, users, payments hoặc `raw_get` tùy ý cho chatbot. Key chỉ ở biến môi trường của backend/MCP process; không đi vào prompt, HTML hoặc Git.

`/chat/health` báo nguồn dữ liệu và việc có cấu hình token; đó không phải phép kiểm tra kết nối CMS tức thời.

## Thành phần

- `server/app.py`: server standard library, trang test và endpoint `/chat/api/message` (SSE `message` + `done`). Câu trả lời được tạo xong rồi gửi một lần; chưa stream từng token.
- `server/static/widget.js`: widget, lịch sử hội thoại trong bộ nhớ tab, reset, timeout và thông báo lỗi.
- `server/static/demo.html`: trang chat tối giản, mở trực tiếp hội thoại.
- `server/cms_mcp.py`: cầu nối MCP chỉ đọc, phục vụ công cụ live cho AI.
- `bot/system_prompt.md`, `kb/service_guide.md`: hướng dẫn trả lời. Các file catalog/FAQ/chính sách Markdown cũ không được nạp làm dữ liệu trả lời.

Repo chỉ lấy source cần thiết và KB Markdown; không kèm raw payments, dữ liệu tài khoản ngân hàng, `.env` hay lịch sử Git của repo gốc. Không cần chạy scanner để thử chatbox.

Widget dùng endpoint cùng origin. Để nhúng trên trang khác, phục vụ `/chat/*` qua reverse proxy cùng origin và thêm `<script src="/chat/widget.js"></script>`. Có thể gọi `window.SnusChat.open()`.

Đây là bản test local, mặc định chỉ bind loopback. Chưa có xác thực, rate limit hoặc quản lý ngân sách để mở public. Người khác clone repo cần đăng nhập Codex bằng tài khoản của họ.

## Kiểm tra

```powershell
python -m unittest discover -s tests -v
```

## Lưu hội thoại để hỗ trợ khách hàng

Backend tự lưu các tin nhắn được chấp nhận kể từ khi bật module vào `data/chat-history.sqlite3`. Mỗi lượt có mã hội thoại, mã yêu cầu, tin khách gửi, câu trả lời bot, thời gian UTC, model/provider, thời gian xử lý và trạng thái. Tin khách được ghi trước khi gọi AI; lỗi AI vẫn giữ được tin khách, chỉ ghi mã lỗi chung. Câu trả lời được lưu trước khi gửi về trình duyệt, nên đóng tab/reset khi đang chờ không xóa bản lưu trên server.

Không lưu lại toàn bộ mảng lịch sử gửi kèm, không lưu prompt, token, stdout/stderr Codex hay toàn bộ dữ liệu MCP. Gửi lại cùng request ID đã hoàn tất sẽ trả câu trả lời đã lưu mà không tạo thêm lượt/gọi AI lần nữa. Gửi lại nội dung bằng một request ID mới được xem là lượt mới.

Tra cứu bằng terminal tại thư mục repo:

```powershell
python server/chat_store.py list
python server/chat_store.py show MA_HOI_THOAI
python server/chat_store.py export MA_HOI_THOAI --output support-exports/chat.json
```

Module chỉ cung cấp CLI local; không có API tải danh sách hoặc nội dung hội thoại cho trình duyệt khách. Database và `support-exports/` được Git bỏ qua. Muốn chuyển vị trí lưu, đặt `CHAT_DB_PATH` trong môi trường khi chạy server/CLI, hoặc dùng `--db DUONG_DAN` với CLI. Nếu đặt đường dẫn riêng trong `.env` của server, truyền cùng đường dẫn bằng `--db` khi dùng CLI.

Hội thoại được lưu cho đến khi người vận hành quản lý file database; chưa có tự xóa theo kỳ hạn hoặc khôi phục các cuộc chat trước khi module được bật. Giao diện khách vẫn chỉ có chat, không thêm bảng log hay ghi chú kỹ thuật.
