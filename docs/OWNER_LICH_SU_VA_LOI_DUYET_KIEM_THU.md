# Sửa lịch sử Owner trống và duyệt POI thất bại không có lý do

Ngày kiểm tra: **24/11/2026** — Asia/Saigon.

**Cập nhật theo yêu cầu mới:** Admin có quyền `poi:approve` được duyệt cả đề xuất POI do chính mình gửi. Không cần đổi sang tài khoản Admin khác. Điều kiện này áp dụng đồng nhất cho nút Duyệt và API thực hiện duyệt.

## 1. Nguyên nhân thực tế trong hai ảnh

### Lịch sử trống là lỗi giao diện, dữ liệu vẫn còn

Tài khoản trong ảnh là `demo.admin@quan4.local`, dùng cả cổng Admin và cổng Owner. Khi kiểm tra database, tài khoản này có **5 submission**:

| Tên | Trạng thái khi kiểm tra |
| --- | --- |
| 2632 | pending — đang chờ |
| Cơm Sài Gòn Xưa | rejected — đã từ chối |
| Bếp Nhà Quận 4 (Chi nhánh 2) | rejected — đã từ chối |
| Ốc Tô | approved — đã duyệt |
| Phá Lấu Bò Cô Thảo | approved — đã duyệt |

Lỗi nằm ở `OwnerApp.tsx`:

1. Tài khoản Admin không có đơn đăng ký Owner nhận 404 ở API trạng thái. Frontend gắn nhãn “Tài khoản nội bộ” rồi thoát hàm, không tải lịch sử.
2. Các nhánh tải dữ liệu chỉ cho trạng thái `approved`, trong khi biểu mẫu lại cho cả `approved` và `admin` gửi đề xuất.
3. Sau khi gửi thành công, frontend chỉ xóa biểu mẫu và báo thành công, chưa cập nhật lịch sử.
4. Chuyển sang trang lịch sử hoặc quay lại tab chưa gọi tải lại lịch sử.
5. Lịch sử và danh sách POI cùng nằm trong một `Promise.all`: lỗi tải POI có thể ngăn kết quả lịch sử được đưa lên giao diện.
6. Lỗi tải dữ liệu chỉ hiện ở biểu mẫu gửi quán, không hiện tại trang lịch sử. Vì vậy trang dễ trông giống “chưa gửi nội dung nào” dù thực tế tải lỗi.

### Vì sao Admin bị chặn và đã sửa ra sao?

**2632** (`ec7692aa-7945-4918-b569-4a798ee531de`): người gửi là `demo.admin@quan4.local`. Điều kiện trước đây chặn mọi trường hợp người duyệt trùng người gửi, chưa phân biệt Admin với Owner. Vì vậy tài khoản Admin cũng bị trả **403**, rồi nút Duyệt bị khóa khi giao diện hiển thị lý do. Đây là điều kiện chặn quá rộng so với yêu cầu của bạn.

Đã đổi cả `duyet_submission` và `submission_cho_duyet` trong `backend/app/routers/owner.py`: chỉ chặn tự duyệt nếu người dùng **không phải Admin**. API vẫn bắt buộc quyền `poi:approve`, lấy từ phiên đăng nhập đã xác thực ở backend. Role Admin không tự vượt qua bước kiểm tra quyền. Frontend dùng `can_approve` do API trả về nên tự mở nút khi tải lại danh sách.

Đọc lại dữ liệu thật bằng mã mới với vai trò Admin: **2632 có `can_approve=true`, `approval_blockers=[]`**, trạng thái vẫn `pending` để bạn tự bấm duyệt.

**Quán Bún Demo** (`10000000-0000-4000-8000-000000000321`): snapshot dữ liệu demo thiếu cả `lat` và `lng`. Luồng duyệt cũ đưa snapshot này thẳng vào câu SQL tạo POI nên thất bại do thiếu tham số. Nay kiểm tra dữ liệu trước khi ghi, trả **409** cùng lý do thiếu vĩ độ/kinh độ.

Từ chối vẫn hoạt động vì không cần tạo POI từ tọa độ và không đi qua bước kiểm tra tự duyệt của thao tác approve. Bản sửa giữ nguyên việc từ chối phải có ghi chú.

## 2. Đã thay đổi gì?

| File | Hành vi sau sửa |
| --- | --- |
| `backend/app/routers/owner.py` | Trả trạng thái `admin` rõ ràng cho Admin không có đơn đăng ký Owner; không dùng 404 để suy ra quyền nội bộ. |
| API lịch sử | Trả thêm `submission_type`, giữ lọc theo người đang đăng nhập. Quán mới đã được duyệt có `poi_id` vẫn hiển thị đúng loại “Quán mới”. |
| API danh sách chờ | Trả `can_approve` và `approval_blockers`: Admin có quyền được tự duyệt; dữ liệu thiếu/sai vẫn hiện lý do và khóa nút. |
| API approve | Admin có quyền được duyệt đề xuất của mình hoặc người khác. Owner không được tự duyệt. Xác thực snapshot bằng schema trước khi ghi POI/menu; lỗi dữ liệu cũ trả 409 kèm trường cần bổ sung. |
| `frontend/src/admin/OwnerApp.tsx` | Tải lịch sử cho cả Owner đã duyệt và tài khoản nội bộ; tách lỗi danh sách POI khỏi lịch sử; cập nhật sau gửi, khi vào lịch sử và khi quay lại tab. |
| Trang lịch sử | Có nút **Tải lại lịch sử**, phân biệt đang tải/lỗi/danh sách trống. Hiện lỗi ngay tại trang đang xem; response lịch sử cũ đến muộn không ghi đè kết quả mới. |
| Biểu mẫu gửi | Khóa nút Gửi khi request đang chạy; hiển thị lý do backend nếu bị từ chối và lỗi kết nối nếu mất mạng. |
| `frontend/src/admin/OwnerApprovals.tsx` | Hiển thị lý do chặn ngay cạnh từng đơn và khóa nút Duyệt khi đã biết không hợp lệ; nút Từ chối vẫn dùng được. Hiển thị lý do backend cho 403/409, mã HTTP khi lỗi không có JSON, và thông báo mất kết nối. |
| `frontend/src/admin/apiErrors.ts` | Đọc thông báo `detail` và lỗi validation; không đưa trang HTML lỗi máy chủ lên giao diện. |

Các thao tác duyệt/từ chối tài khoản và quán đều kiểm tra phản hồi HTTP. Khi đã duyệt thành công nhưng tải lại danh sách POI lỗi, giao diện nói rõ phần duyệt đã thành công để tránh người dùng tưởng cần duyệt lại.

## 3. Có thay đổi các đơn thật hay không?

Không duyệt, từ chối, xóa hoặc tạo lại bất kỳ đơn thật nào trong lần sửa này. Script chẩn đoán chỉ đọc. Đơn **2632 vẫn đang chờ**; dữ liệu lịch sử của người dùng được giữ nguyên.

Không tự điền tọa độ cho Quán Bún Demo vì chưa có vị trí thực tế để xác minh. Thay đổi quy tắc cho phép Admin tự duyệt không tự chuyển trạng thái các đơn đang chờ.

Để duyệt 2632, dùng **chính tài khoản `demo.admin@quan4.local`** có quyền duyệt POI. Bạn cũng có thể dùng Admin khác. Khi thử luồng Owner riêng gửi và Admin duyệt, dùng hai hồ sơ trình duyệt hoặc cửa sổ thường/ẩn danh để tránh hai tab dùng chung phiên đăng nhập.

| Trường hợp | Kết quả |
| --- | --- |
| Admin + `poi:approve`, duyệt đơn của mình, dữ liệu hợp lệ | Được duyệt. |
| Admin + `poi:approve`, duyệt đơn người khác | Được duyệt. |
| Admin thiếu `poi:approve` | API trả 403. |
| Owner tự duyệt, kể cả được gán quyền duyệt nhầm | API trả 403. |
| Admin duyệt đơn thiếu/sai tọa độ | Khóa nút kèm lý do; gọi trực tiếp API trả 409. |
| Duyệt lại đơn đã xử lý | API trả 404, không tạo POI lần hai. |

## 4. Kiểm thử đã chạy

**Lần sửa quyền Admin mới nhất:**

- **71 test backend đạt**, gồm 3 trường hợp PostgreSQL thật: Admin tự duyệt, Admin khác duyệt và luồng publication. Dữ liệu thử được rollback.
- **16 test giao diện đạt**, gồm lịch sử Owner và duyệt quán; xác nhận nút được mở khi backend cho phép, thông báo thành công nhắc bước công khai và các lỗi vẫn hiện rõ.
- **Ruff đạt** trên các file Python sửa trong lần này.
- Script chỉ đọc xác nhận 2632 được phép duyệt bằng mã mới; Quán Bún Demo vẫn báo thiếu tọa độ.

**Kết quả toàn bộ dự án ở lần sửa lịch sử trước đó** (không phải lần chạy lại sau thay đổi quyền Admin):

- **Frontend: 117 passed / 21 file test**.
- **ESLint: đạt**.
- **TypeScript + production build + service worker: đạt**.
- **Ruff trên các file Python thay đổi: đạt**.
- **Backend toàn bộ: 222 passed, 1 failed, 4 skipped**.
- **PostgreSQL thật: 2 passed**, gồm bài Owner mới và bài luồng publication trước đó. Dữ liệu test tổng hợp dùng transaction/savepoint rồi rollback; không duyệt đơn thật trong quá trình test.

Một test backend thất bại vẫn là lỗi đã có: `tests/test_sec_007.py::test_khong_render_duong_dan_dong_vao_href`, quét chuỗi `src={`/`href={` ở ảnh QR và link dashboard. Không phải lỗi nghiệp vụ mới. Bốn test DB thật mặc định skip để không tự kết nối dịch vụ ngoài; hai bài liên quan đã chạy riêng với cờ bật.

### Các tình huống được xác nhận

1. Owner đã duyệt và tài khoản nội bộ đều nhìn thấy lịch sử đang chờ.
2. Lỗi tải POI không làm mất lịch sử; lỗi lịch sử không bị trình bày thành “Bạn chưa gửi nội dung nào”.
3. Gửi thành công rồi mở lịch sử ngay, không cần tải lại trang/đăng nhập lại.
4. Quay lại tab lấy được trạng thái từ chối và ghi chú mới.
5. Response cũ đến muộn không ghi đè trạng thái mới.
6. Quán mới đã được duyệt vẫn mang loại “Quán mới”.
7. Backend trả lý do cho thiếu tọa độ, tọa độ ngoài khoảng, menu sai hoặc snapshot lỗi trước khi ghi dữ liệu.
8. Admin có quyền được tự duyệt cả ở thông tin danh sách và endpoint; Owner tự duyệt vẫn bị chặn. Admin thiếu quyền không được duyệt.
9. Admin tự duyệt hoặc Admin khác duyệt đều thành công: tạo POI và menu, giữ đúng chủ sở hữu, cập nhật lịch sử và thông báo; POI vẫn chưa công khai cho tới bước publish. Duyệt lại không tạo thêm POI.
10. Từ chối vẫn lưu ghi chú và cập nhật lịch sử.
11. UI hiển thị đúng lỗi 403/409, HTTP 500 không có JSON và lỗi mạng; không báo duyệt thành công khi request thất bại.

Giới hạn: đã kiểm thử component React, HTTP và SQL thật; chưa thao tác phiên trình duyệt đang đăng nhập của người dùng. Mã được sửa tại workspace, chưa triển khai lên hosting/production.

## 5. Cách tự kiểm tra đúng hai ảnh

1. **Nạp mã mới:** khởi động lại backend hoặc chờ `--reload` hoàn tất; tại frontend nhấn **Ctrl+F5**.
2. Đăng nhập `demo.admin@quan4.local`, mở `/owner/history`. Phải thấy các đơn của tài khoản, trong đó **2632 — Đang chờ duyệt**. Số mục có thể tăng nếu bạn đã gửi thêm.
3. Mở `/admin/approvals` bằng chính tài khoản đó, bấm **Tải lại danh sách** nếu cần. Dòng **2632** phải có nút **Duyệt quán** hoạt động và không còn cảnh báo yêu cầu Admin khác. Bấm Duyệt: hiện thành công, đơn biến mất khỏi hàng chờ. Mở `/owner/history`: đơn chuyển **Đã được duyệt**; tại Quản lý quán có POI ở trạng thái chưa công khai.
4. Dòng **Quán Bún Demo** phải ghi rõ thiếu vĩ độ và kinh độ. Từ chối kèm ghi chú để Owner bổ sung/gửi lại khi phù hợp với nghiệp vụ; bản sửa không tự quyết định từ chối thay bạn.
5. Dùng tài khoản Owner riêng, gửi một quán thử có tên, địa chỉ, tọa độ hợp lệ và tùy chọn menu. Bấm **Trạng thái gửi duyệt**: quán mới phải xuất hiện ngay.
6. Dùng Admin có quyền duyệt quán thử; nếu Admin tự gửi thì dùng luôn tài khoản đó. Quay lại tab Owner hoặc bấm **Tải lại lịch sử**: trạng thái phải là **Đã được duyệt**; xem Địa điểm của tôi và Thông báo để kiểm tra POI và thông báo.
7. Tạo một đơn thử khác, Admin từ chối kèm ghi chú. Owner phải thấy **Cần chỉnh sửa** và đúng ghi chú.

## 6. Lệnh chạy lại trên PowerShell

Từ thư mục gốc repository:

```powershell
Set-Location backend

# Chỉ đọc trạng thái đơn của tài khoản trong ảnh, không sửa dữ liệu.
.\.venv\Scripts\python.exe scripts\diagnose_owner_submissions.py demo.admin@quan4.local

# Chạy lại đúng 71 test: logic, HTTP + SQL thật; dữ liệu test được rollback.
.\.venv\Scripts\python.exe -m pytest -q tests_postgres/test_owner_submission_errors.py tests_postgres/test_publication.py tests_postgres/test_poi_write_workflows.py tests_postgres/test_owner_submission_database.py tests_postgres/test_publication_database.py --run-publication-db

Set-Location ../frontend
npm.cmd test -- src/admin/OwnerApp.test.tsx src/admin/OwnerApprovals.test.tsx
npm.cmd run lint
npm.cmd run build
```
