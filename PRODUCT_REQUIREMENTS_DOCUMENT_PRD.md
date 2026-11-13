# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## QUAN4 CULINARY TOURISM

> Bản chuyển đổi từ PDF sang Markdown (UTF-8) để xem và chia sẻ trong Visual Studio Code.
> Nội dung được trích xuất theo từng trang; bố cục bảng trong PDF có thể được chuyển thành văn bản tuyến tính.

---

<!-- Trang 1 -->
**PRODUCT REQUIREMENTS**
**DOCUMENT (PRD)**

QUAN4 CULINARY TOURISM

## 1. GIỚI THIỆU

### 1.1. Mục đích tài liệu

Tài liệu Product Requirements Document (PRD) mô tả các yêu cầu sản phẩm của
hệ thống Quan4 Culinary Tourism – nền tảng hỗ trợ khám phá du lịch ẩm thực
tại Quận 4, TP. Hồ Chí Minh.

PRD được xây dựng nhằm:

● Xác định mục tiêu, định hướng và phạm vi của sản phẩm.
● Xác định các nhóm người dùng và quyền hạn tương ứng.
● Mô tả các chức năng nghiệp vụ của Visitor Portal, Owner Portal và Admin
Portal.
● Đặc tả cách hệ thống quản lý địa điểm ẩm thực (POI), nội dung đa ngôn ngữ
và Audio Guide.
● Mô tả cơ chế GPS, Geofence, Audio Narration và Background Prefetch.
● Xác định khả năng hoạt động Offline của Visitor PWA.
● Đưa ra yêu cầu phi chức năng và các ràng buộc kỹ thuật.
● Xây dựng tiêu chí nghiệm thu để nhóm phát triển và kiểm thử có cùng cơ sở
đánh giá.
● Làm cơ sở cập nhật Use Case Diagram, Activity Diagram, Sequence
Diagram, thiết kế cơ sở dữ liệu và API.

---

<!-- Trang 2 -->
### 1.2. Tổng quan sản phẩm

Quan4 Culinary Tourism là một nền tảng PWA hỗ trợ người dùng khám phá các
địa điểm ẩm thực tại Quận 4 thông qua bản đồ tương tác và hướng dẫn âm thanh đa
ngôn ngữ.

Hệ thống cho phép Owner đăng ký, quản lý thông tin địa điểm ẩm thực thuộc
quyền sở hữu và gửi nội dung để Admin kiểm duyệt. Admin chịu trách nhiệm quản
trị tài khoản, phân quyền, quản lý POI, kiểm duyệt nội dung và giám sát hoạt động
hệ thống.

Đối với Visitor, hệ thống cung cấp bản đồ các địa điểm ẩm thực, thông tin chi tiết
về từng POI và Audio Guide. Khi Visitor di chuyển đến gần một POI, hệ thống sử
dụng GPS và Geofence để xác định vị trí, lựa chọn nội dung phù hợp và đưa ra lời
mời nghe thuyết minh.

Hệ thống hỗ trợ nội dung đa ngôn ngữ thông qua dịch thuật tự động và chuyển văn
bản thành giọng nói (Text-to-Speech). Ngoài ra, Visitor có thể sử dụng một phần
chức năng khi Offline nếu các tài nguyên cần thiết đã được lưu trên thiết bị.

### 1.3. Vấn đề cần giải quyết

Việc khám phá các địa điểm ẩm thực thường phụ thuộc vào thông tin tìm kiếm từ
nhiều nguồn khác nhau. Người dùng có thể gặp khó khăn khi:

● Không biết những địa điểm ẩm thực đáng chú ý ở khu vực đang tham quan.
● Phải tự tìm kiếm thông tin về từng địa điểm.
● Gặp rào cản ngôn ngữ khi tiếp cận thông tin.
● Không có trải nghiệm thuyết minh theo vị trí khi di chuyển.
● Phụ thuộc vào kết nối Internet để xem bản đồ và nội dung.
● Không có một nền tảng tập trung để chủ địa điểm quản lý thông tin và nội
dung giới thiệu.

Quan4 Culinary Tourism hướng đến giải quyết các vấn đề này bằng cách kết hợp
bản đồ, POI, GPS, Geofence, dịch thuật, TTS và PWA.

### 1.4. Giá trị sản phẩm

---

<!-- Trang 3 -->
Đối tượng Giá trị mang lại

Visitor Khám phá địa điểm ẩm thực, xem thông tin và nghe Audio Guide
bằng ngôn ngữ phù hợp.

Owner Quản lý thông tin địa điểm thuộc quyền sở hữu, cập nhật nội dung và
gửi yêu cầu kiểm duyệt.

Admin Quản lý dữ liệu, tài khoản, quyền truy cập, kiểm duyệt nội dung và
theo dõi hoạt động hệ thống.

Hệ thống Tự động hóa quy trình dịch thuật, tạo Audio và chuẩn bị tài nguyên
để nâng cao trải nghiệm người dùng.

### 1.5. Thuật ngữ và định nghĩa

Thuật ngữ Định nghĩa

POI Point of Interest – địa điểm ẩm thực được quản lý và
hiển thị trên bản đồ.

Geofence Vùng địa lý được xác định quanh tọa độ POI để phát
hiện Visitor đi vào hoặc ra khỏi vùng.

Trigger Radius Bán kính kích hoạt Geofence của POI.

---

<!-- Trang 4 -->
Audio Guide Nội dung thuyết minh được chuyển thành âm thanh để
Visitor nghe.

TTS Text-to-Speech – chuyển đổi văn bản thành giọng nói.

Translation Dịch nội dung POI từ ngôn ngữ nguồn sang ngôn ngữ
đích.

AI Advisor Chức năng sử dụng AI để hỗ trợ cải thiện nội dung mô tả
POI.

Prefetch Chuẩn bị trước tài nguyên hoặc nội dung để giảm thời
gian chờ khi người dùng cần sử dụng.

Audio Queue Hàng đợi xử lý các yêu cầu phát Audio Guide.

PWA Progressive Web Application – ứng dụng web có khả
năng cài đặt và sử dụng một phần chức năng Offline.

Offline Pack Gói tài nguyên được tải trước, bao gồm bản đồ, dữ liệu
POI, hình ảnh và Audio.

Owner Submission Nội dung tạo mới hoặc cập nhật POI do Owner gửi lên
chờ Admin kiểm duyệt.

---

<!-- Trang 5 -->
RBAC Role-Based Access Control – cơ chế kiểm soát quyền
truy cập theo vai trò.

Localization Quá trình cung cấp nội dung POI theo ngôn ngữ được
lựa chọn.

UI Bundle Bộ dữ liệu ngôn ngữ dùng để hiển thị giao diện ứng
dụng.

## 2. PHÂN LOẠI NGUỒN YÊU CẦU VÀ
QUYẾT ĐỊNH SẢN PHẨM

Để tránh nhầm lẫn giữa thiết kế hiện tại và yêu cầu sản phẩm, PRD sử dụng ba
nhãn:

● [HTML]: Thông tin được mô tả trong tài liệu HTML nguồn.
● [MVP]: Quyết định điều chỉnh hoặc lựa chọn triển khai của nhóm cho phiên
bản MVP.
● [TBD]: Nội dung chưa đủ căn cứ hoặc cần xác nhận trước khi triển khai
chính thức.

Một số quyết định quan trọng:

Nội dung Quyết định

Tên sản phẩm Quan4 Culinary Tourism [MVP]

---

<!-- Trang 6 -->
Venue và POI Chỉ sử dụng POI làm thực thể địa điểm chính [MVP]

Geofence Là vùng bán kính quanh tọa độ POI, không phải thực thể
POI [HTML]

Exhibit Không sử dụng thực thể Exhibit [MVP]

Hình ảnh Là tài nguyên thuộc POI [HTML]

Owner và Content Editor Gộp thành một actor Owner [MVP]

Visitor Account Không yêu cầu Visitor đăng nhập trong luồng khám phá
công khai [HTML/Diagram Review]

AI Advisor Tách biệt với dịch vụ Translation [HTML]

Translation Dịch nội dung POI sang ngôn ngữ khác [HTML]

TTS Tạo Audio từ nội dung văn bản [HTML]

Audio Prompt Visitor xác nhận nghe trước khi phát trong MVP [MVP]

Background Prefetch Chuẩn bị bản dịch cho POI gần đó, độc lập với Audio
Queue [HTML]

---

<!-- Trang 7 -->
Offline Chỉ áp dụng cho Visitor PWA và tài nguyên đã cache
[HTML]

## 3. MỤC TIÊU VÀ CHỈ SỐ ĐÁNH GIÁ

### 3.1. Mục tiêu sản phẩm

OBJ-01 – Khám phá địa điểm ẩm thực

Cung cấp bản đồ tương tác để Visitor tìm kiếm, xem và khám phá các địa điểm ẩm
thực tại Quận 4.

OBJ-02 – Hướng dẫn theo vị trí

Sử dụng GPS và Geofence để nhận biết Visitor đang ở gần POI và đề xuất Audio
Guide phù hợp.

OBJ-03 – Hỗ trợ đa ngôn ngữ

Cung cấp nội dung POI và Audio Guide theo ngôn ngữ mà Visitor lựa chọn.

OBJ-04 – Quản lý nội dung tập trung

Cho phép Owner quản lý POI thuộc quyền sở hữu và Admin kiểm duyệt trước khi
công khai.

OBJ-05 – Tự động hóa xử lý nội dung

Sử dụng Translation, TTS và AI Advisor để giảm công việc xử lý nội dung thủ
công.

OBJ-06 – Hỗ trợ sử dụng khi Offline

---

<!-- Trang 8 -->
Cho phép Visitor truy cập các tài nguyên đã được lưu trên thiết bị khi mất kết nối
Internet.

### 3.2. Chỉ số đánh giá đề xuất

Các chỉ số dưới đây là KPI định hướng để nhóm có thể đánh giá sản phẩm. Chúng
không phải số liệu hiệu năng đã được chứng minh trong HTML.

KPI Ý nghĩa Cách đánh giá

POI Coverage Số lượng POI có dữ liệu Đếm POI được Admin kích hoạt
hợp lệ

Localization Mức độ bao phủ ngôn ngữ Tỷ lệ POI có nội dung bản địa hóa
Coverage sẵn sàng

Audio Coverage Mức độ bao phủ Audio Tỷ lệ POI/ngôn ngữ có Audio hợp lệ

Geofence Khả năng phát hiện Visitor Kiểm thử các kịch bản GPS và
Detection vào vùng Geofence

Audio Prompt Tỷ lệ Visitor đồng ý nghe Số lần đồng ý / số Audio Prompt
Conversion Audio

Offline Khả năng truy cập dữ liệu Kiểm thử Offline Pack và tài nguyên
Availability đã tải cache

---

<!-- Trang 9 -->
Owner Khả năng gửi POI thành Số submission hợp lệ được tiếp nhận
Submission công
Success

Admin Review Khả năng xử lý submission Tỷ lệ submission được xử lý
Completion

## 4. PHẠM VI SẢN PHẨM

### 4.1. Trong phạm vi sản phẩm

#### 4.1.1. Visitor Portal

● Truy cập Visitor PWA.
● Chọn ngôn ngữ giao diện và nội dung.
● Xem bản đồ và danh sách POI.
● Xem thông tin chi tiết POI.
● Xem hình ảnh POI nếu có.
● Yêu cầu quyền truy cập vị trí.
● Phát hiện POI gần Visitor bằng GPS và Geofence.
● Nhận Audio Prompt khi vào vùng POI phù hợp.
● Xác nhận hoặc từ chối nghe Audio.
● Phát Audio Guide.
● Chọn ngôn ngữ Audio Guide.
● Sử dụng nội dung và Audio đã cache khi Offline.
● Tải và sử dụng Offline Pack.

#### 4.1.2. Owner Portal

● Đăng ký tài khoản Owner.

---

<!-- Trang 10 -->
● Chờ Admin xác minh và phê duyệt.
● Đăng nhập vào Owner Portal.
● Xem và cập nhật thông tin tài khoản trong phạm vi được phép.
● Xem POI thuộc quyền sở hữu.
● Tạo POI submission.
● Gửi yêu cầu cập nhật POI.
● Quản lý nội dung POI trong phạm vi quyền được cấp.
● Quản lý phiên bản ngôn ngữ.
● Yêu cầu dịch nội dung.
● Tạo Audio bằng TTS.
● Xem trước nội dung và Audio.
● Sử dụng AI Advisor để cải thiện mô tả POI.
● Theo dõi trạng thái kiểm duyệt.
● Nhận và xem thông báo từ Admin.

#### 4.1.3. Admin Portal

● Đăng nhập và xác thực Admin.
● Quản lý tài khoản.
● Quản lý vai trò và quyền truy cập.
● Quản lý POI.
● Quản lý Menu và MenuItem.
● Tiếp nhận và duyệt đăng ký Owner.
● Duyệt hoặc từ chối POI submission.
● Quản lý nội dung và trạng thái công khai POI.
● Quản lý nội dung đa ngôn ngữ.
● Sử dụng Translation và TTS.
● Theo dõi và quản lý Audio Tasks.
● Sử dụng AI Advisor.
● Xem Analytics.
● Xem Audit Logs.
● Theo dõi Runtime Observability.

### 4.2. Ngoài phạm vi MVP

---

<!-- Trang 11 -->
Các chức năng sau không được xem là yêu cầu MVP nếu chưa có quyết định bổ
sung:

● Thanh toán trực tuyến.
● Đặt bàn hoặc đặt món.
● Giao hàng.
● Đặt tour và quản lý lịch trình tour.
● Đánh giá, xếp hạng và bình luận POI.
● QR Code và QR Scanning.
● Quản lý Exhibit riêng biệt.
● Quản lý Venue như một thực thể độc lập.
● Visitor Account và hồ sơ cá nhân dành cho Visitor.
● Social Network hoặc chia sẻ bài viết.
● Tự động phát Audio không cần xác nhận Visitor trong MVP.
● Chức năng nghiệp vụ Offline cho Owner Portal và Admin Portal.

## 5. ACTOR VÀ QUYỀN HẠN

### 5.1. Danh sách Actor

Actor ID Actor Mô tả

ACT-01 Visitor Người sử dụng ứng dụng để khám phá địa điểm ẩm
thực.

ACT-02 Owner Chủ địa điểm ẩm thực, quản lý POI thuộc quyền sở
hữu.

---

<!-- Trang 12 -->
ACT-03 Admin Người quản trị hệ thống, kiểm duyệt và quản lý dữ
liệu.

EXT-01 GPS / Geolocation Cung cấp thông tin vị trí của thiết bị.
Provider

EXT-02 Translation Hỗ trợ dịch nội dung POI.
Provider

EXT-03 TTS Provider Chuyển nội dung văn bản thành Audio.

EXT-04 AI Provider Hỗ trợ AI Advisor cải thiện nội dung.

EXT-05 Map Service Cung cấp bản đồ và tài nguyên bản đồ trực tuyến.

### 5.2. Quyền hạn theo Actor

Chức năng Visitor Owner Admin

Xem bản đồ công khai ✓ ✓ ✓

Xem POI công khai ✓ ✓ ✓

Nghe Audio Guide ✓ ✓ ✓

---

<!-- Trang 13 -->
Sử dụng Offline Pack ✓ Không thuộc phạm Không thuộc phạm
vi nghiệp vụ vi nghiệp vụ

Đăng ký Owner — ✓ —

Quản lý POI sở hữu — ✓ ✓

Gửi POI Submission — ✓ —

Duyệt POI Submission — — ✓

Quản lý tài khoản — Thông tin tài khoản ✓
của mình

Quản lý — — ✓
Role/Permission

Quản lý Menu — Theo quyền được ✓
cấp nếu có

Dịch nội dung — ✓ ✓

Tạo Audio bằng TTS — ✓ ✓

---

<!-- Trang 14 -->
AI Advisor — ✓ ✓

Xem Analytics quản — — ✓
trị

Xem Audit Logs — — ✓

Runtime Observability — — ✓

Lưu ý: Owner và Admin có thể sử dụng một số chức năng nội dung chung nhưng
quyền thao tác phải được kiểm tra bằng RBAC và quyền sở hữu POI.

### 5.3. Quy tắc xác thực và phân quyền

● Visitor có thể sử dụng các chức năng khám phá công khai mà không cần
đăng nhập.
● Owner phải đăng ký tài khoản và được Admin phê duyệt trước khi có quyền
quản lý POI.
● Admin phải được xác thực trước khi truy cập các chức năng quản trị.
● Quyền truy cập được xác định theo vai trò và permission.
● Owner chỉ được thao tác trên POI thuộc quyền sở hữu.
● Owner không được tự phê duyệt POI submission của mình.
● Admin có quyền xử lý các yêu cầu kiểm duyệt.
● Các thao tác quản trị quan trọng cần được ghi nhận trong Audit Logs.

## 6. KIẾN TRÚC SẢN PHẨM VÀ THÀNH
PHẦN HỆ THỐNG

---

<!-- Trang 15 -->
### 6.1. Kiến trúc tổng quan

Theo HTML, hệ thống được tổ chức theo hướng Modular Monolith: các module
nghiệp vụ được tách theo router/service/store nhưng dùng chung backend runtime
và các tài nguyên hạ tầng.

Không xem đây là kiến trúc Microservices độc lập.

Các thành phần chính:

## 1. Visitor PWA.
## 2. Owner Portal.
## 3. Admin Portal.
## 4. Backend API.
## 5. PostgreSQL + PostGIS.
## 6. Trạng thái tạm thời trong tiến trình.
## 7. Static/Runtime Storage.
## 8. Translation Provider.
## 9. TTS Provider.
10.AI Provider.
11.Map Service.

### 6.2. Các module Backend

Module Trách nhiệm

content Quản lý POI, MenuItem, đồng bộ dữ liệu và điều kiện
kích hoạt nội dung.

audio Xử lý TTS, Audio Tasks, Audio URL, Audio Queue liên
quan đến nội dung.

---

<!-- Trang 16 -->
admin Quản trị tài khoản, vai trò, quyền, POI và kiểm duyệt.

owner Đăng ký Owner, quản lý POI sở hữu, submission và
notification.

ai_advisor Cung cấp chức năng hỗ trợ cải thiện mô tả POI.

analytics Thu thập và tổng hợp dữ liệu Analytics có sự đồng ý của
người dùng.

localization Dịch và quản lý nội dung POI theo ngôn ngữ.

maps Quản lý Map Manifest, bản đồ tĩnh, PMTiles và tài
nguyên bản đồ.

runtime_observability Theo dõi thông tin vị trí/runtime phục vụ quản trị.

ui_i18n Quản lý UI Translation Bundles theo locale và
namespace.

### 6.3. Các thành phần dữ liệu chính

Collection / Entity Mục đích

---

<!-- Trang 17 -->
POI Lưu dữ liệu địa điểm ẩm thực gốc, tọa độ, hình ảnh và
trigger radius.

poi_localizations Lưu bản dịch và Audio URL theo POI và ngôn ngữ.

audio_tasks Lưu trạng thái và thông tin các tác vụ tạo Audio.

content_dataset_versions Quản lý phiên bản dữ liệu và đồng bộ POI.

admin_users Lưu tài khoản Admin/Owner và thông tin xác thực.

roles Quản lý vai trò và permission.

audit_logs Lưu nhật ký hoạt động.

poi_owner_registrations Lưu yêu cầu đăng ký Owner.

poi_submissions Lưu yêu cầu tạo mới hoặc cập nhật POI chờ duyệt.

owner_notifications Lưu thông báo dành cho Owner.

ai_usage_limits Theo dõi giới hạn sử dụng AI Advisor.

---

<!-- Trang 18 -->
analytics_* Lưu dữ liệu và read models phục vụ Analytics.

localization_rate_limits Theo dõi giới hạn yêu cầu Translation/TTS.

ui_translation_bundles Lưu các UI Translation Bundles.

runtime_location_hourly Lưu read model vị trí theo cửa sổ thời gian.

MenuItem Lưu các món ăn thuộc POI.

#### 6.3.1. Mô hình POI

POI là thực thể địa điểm trung tâm của hệ thống.

Một POI có thể bao gồm:

● ID.
● Tên địa điểm.
● Mô tả.
● Danh mục.
● Địa chỉ.
● Tọa độ địa lý.
● Hình ảnh.
● Trigger Radius.
● Trạng thái hoạt động.
● Chủ sở hữu.
● Thời gian tạo/cập nhật.
● Dữ liệu MenuItem liên quan nếu có.

POI không phải là một vùng địa lý. Geofence là vùng bán kính được tính toán xung
quanh tọa độ POI.

---

<!-- Trang 19 -->
Ví dụ:

● POI: Quán ăn A.
● Tọa độ POI: Latitude/Longitude.
● Trigger Radius: 30 mét.
● Geofence: vùng bán kính 30 mét xung quanh tọa độ POI.

#### 6.3.2. Hình ảnh POI

Hình ảnh là tài nguyên thuộc POI, không phải một thực thể Exhibit độc lập.

Owner có thể gửi hình ảnh cùng dữ liệu POI submission. Admin kiểm duyệt dữ
liệu trước khi POI được công khai.

HTML ghi nhận giới hạn tối đa 8 hình ảnh cho một POI và kích thước tối đa 5 MB
cho mỗi hình ảnh.

## 7. YÊU CẦU CHỨC NĂNG

### 7.1. Nhóm A – Visitor Portal

FR-VIS-001: Truy cập Visitor PWA

Mô tả: Visitor có thể mở ứng dụng thông qua trình duyệt hoặc PWA đã cài đặt.

Luồng chính:

## 1. Visitor truy cập ứng dụng.
## 2. Frontend khởi động Service Worker.
## 3. Hệ thống hiển thị Splash Screen.
## 4. Visitor lựa chọn ngôn ngữ.
## 5. Hệ thống tải các tài nguyên cần thiết.
## 6. Hệ thống hiển thị Visitor Portal.

Tiêu chí nghiệm thu:

---

<!-- Trang 20 -->
● Ứng dụng có thể khởi động ở trạng thái Online.
● Ứng dụng có thể sử dụng snapshot đã cache khi backend chưa phản hồi,
trong giới hạn dữ liệu có sẵn.
● Nếu không có dữ liệu cache và không thể kết nối backend, hệ thống phải
hiển thị trạng thái phù hợp thay vì giả định dữ liệu đã sẵn sàng.

FR-VIS-002: Lựa chọn ngôn ngữ

Visitor có thể chọn ngôn ngữ sử dụng.

Hệ thống cần phân biệt:

● Ngôn ngữ giao diện (UI Locale).
● Ngôn ngữ nội dung POI (Content Locale).
● Ngôn ngữ Audio Guide.

Việc thay đổi ngôn ngữ nội dung không được mặc định đồng nghĩa với việc UI
Bundle đã sẵn sàng.

Tiêu chí nghiệm thu:

● Visitor có thể chọn ngôn ngữ được hệ thống hỗ trợ.
● Hệ thống tải UI Bundle và nội dung POI tương ứng.
● Khi một trong hai luồng chưa sẵn sàng, giao diện cần thể hiện trạng thái chờ
hoặc trạng thái fallback phù hợp.

FR-VIS-003: Xem bản đồ và POI

Visitor có thể xem bản đồ khu vực Quận 4 và các POI công khai.

Hệ thống phải:

● Tải dữ liệu POI từ Backend hoặc cache.
● Hiển thị POI trên bản đồ.
● Cho phép Visitor lựa chọn POI.
● Đồng bộ dữ liệu khi có phiên bản mới.
● Hỗ trợ bản đồ trực tuyến và bản đồ Offline nếu đã có Map Pack.

Tiêu chí nghiệm thu:

---

<!-- Trang 21 -->
● Chỉ POI được phép công khai mới được hiển thị.
● POI phải có tọa độ hợp lệ.
● Khi dữ liệu đã cache, Visitor vẫn có thể xem POI khi Offline.

FR-VIS-004: Xem thông tin chi tiết POI

Visitor có thể chọn một POI để xem thông tin chi tiết.

Thông tin có thể bao gồm:

● Tên.
● Mô tả.
● Danh mục.
● Địa chỉ.
● Hình ảnh.
● Nội dung theo ngôn ngữ lựa chọn.
● Thông tin Audio Guide nếu có.

Tiêu chí nghiệm thu:

● Hệ thống hiển thị thông tin tương ứng với POI được chọn.
● Nếu bản dịch không tồn tại, áp dụng quy tắc fallback.
● Nếu hình ảnh không có hoặc chưa tải được, giao diện không bị lỗi.

FR-VIS-005: Yêu cầu quyền truy cập vị trí

Visitor có thể cho phép hoặc từ chối quyền truy cập GPS.

Luồng chính:

## 1. Visitor mở chức năng sử dụng vị trí.
## 2. Trình duyệt yêu cầu quyền Geolocation.
## 3. Nếu Visitor đồng ý, hệ thống nhận Latitude, Longitude và Accuracy.
## 4. Hệ thống cập nhật vị trí.
## 5. Nếu Visitor từ chối, hệ thống tiếp tục cho phép xem bản đồ và POI thủ công.

Tiêu chí nghiệm thu:

● Không được giả định người dùng đã cấp quyền GPS.

---

<!-- Trang 22 -->
● Nếu GPS không khả dụng, hệ thống không được làm hỏng chức năng bản
đồ.
● Thông báo rõ khi không thể lấy vị trí.

FR-VIS-006: Phát hiện POI gần Visitor

Hệ thống sử dụng vị trí GPS để xác định Visitor có đi vào Geofence của POI hay
không.

Quy tắc kỹ thuật theo HTML:

● GPS throttle mặc định: 5 giây.
● Geofence debounce: 3 giây.
● Trigger Radius mặc định: 30 mét.
● Cooldown mặc định: 5 phút.
● Thời gian reconcile: 5 giây.

Luồng xử lý:

## 1. Nhận vị trí Visitor.
## 2. Tính khoảng cách từ Visitor đến các POI phù hợp.
## 3. So sánh khoảng cách với Trigger Radius.
## 4. Kiểm tra debounce.
## 5. Xác nhận trạng thái ENTER.
## 6. Kiểm tra cooldown và trạng thái phát Audio.
## 7. Chuyển POI phù hợp sang NarrationEngine.

Tiêu chí nghiệm thu:

● Không kích hoạt Audio Prompt chỉ vì một lần đo GPS bất thường.
● Không phát lặp liên tục cùng một POI trong thời gian cooldown.
● Có thể xử lý nhiều POI nằm gần nhau theo quy tắc ưu tiên.
● Nếu GPS không chính xác hoặc không có dữ liệu, không tự ý kích hoạt
Geofence.

FR-VIS-007: Nhận Audio Prompt

---

<!-- Trang 23 -->
Mô tả: Trong MVP, khi Geofence xác nhận Visitor đã đi vào vùng POI phù hợp,
hệ thống hiển thị Audio Prompt.

Audio Prompt cung cấp thông tin về POI và đề nghị Visitor nghe Audio Guide.

Đây là quyết định điều chỉnh sản phẩm của nhóm. HTML mô tả cơ chế tự động
đưa POI vào NarrationEngine và xử lý phát Audio; PRD MVP bổ sung bước xác
nhận để hạn chế việc phát ngoài ý muốn.

Tiêu chí nghiệm thu:

● Prompt chỉ xuất hiện khi POI được xác nhận hợp lệ.
● Prompt hiển thị thông tin nhận diện POI.
● Visitor có thể chọn nghe hoặc từ chối.
● Từ chối không làm gián đoạn việc xem bản đồ.
● Prompt không được hiển thị lặp liên tục trong thời gian cooldown.

FR-VIS-008: Phát Audio Guide

Visitor có thể phát Audio Guide cho POI đã chọn hoặc đồng ý nghe từ Audio
Prompt.

Hệ thống sử dụng Audio URL tương ứng với ngôn ngữ được chọn.

Quy trình:

## 1. Kiểm tra Audio có sẵn hay không.
## 2. Nếu có Audio hợp lệ, tải hoặc sử dụng cache.
## 3. Đưa yêu cầu vào Audio Queue.
## 4. Phát Audio.
## 5. Theo dõi trạng thái phát.
## 6. Nếu Audio không khả dụng, hiển thị nội dung văn bản thay thế.

Tiêu chí nghiệm thu:

● Không phát Audio không thuộc POI được lựa chọn.
● Không phát đồng thời nhiều Audio ngoài quy tắc Audio Queue.
● Nếu Audio lỗi, hệ thống có thể chuyển sang nội dung văn bản.

---

<!-- Trang 24 -->
● Visitor có thể tiếp tục xem POI khi Audio không khả dụng.

FR-VIS-009: Lựa chọn ngôn ngữ Audio

Visitor có thể chọn ngôn ngữ Audio Guide.

Hệ thống tìm Audio theo ngôn ngữ mục tiêu. Nếu không có dữ liệu, áp dụng
Content Fallback:

## 1. Ngôn ngữ mục tiêu.
## 2. English.
## 3. Vietnamese.

Hệ thống cần phân biệt nội dung fallback với nội dung bản dịch thực sự của ngôn
ngữ mục tiêu.

FR-VIS-010: Background Prefetch bản dịch

Mô tả: Hệ thống tự động chuẩn bị bản dịch cho các POI gần Visitor để giảm thời
gian chờ khi Visitor mở nội dung.

Quy tắc theo HTML:

● Lọc POI có is_fallback=true.
● Xét các POI trong bán kính 500 mét.
● Tối đa 3 POI mỗi đợt.
● Xử lý tuần tự.
● Khoảng cách tối thiểu giữa hai đợt là 30 giây.
● Nếu nhận HTTP 429, sử dụng cơ chế backoff.

Lưu ý quan trọng:

Background Prefetch là hàng đợi dịch nội dung, không phải hàng đợi phát Audio.

Nó không có nghĩa hệ thống sẽ dịch tất cả ba POI gần nhất trong mọi trường hợp,
cũng không đồng nghĩa ba POI đó sẽ tự động được phát Audio.

Tiêu chí nghiệm thu:

---

<!-- Trang 25 -->
● Không đưa POI đã có bản dịch hợp lệ vào hàng đợi dịch lại nếu không cần
thiết.
● Không vượt quá giới hạn số POI mỗi đợt.
● Có cơ chế xử lý khi Provider từ chối yêu cầu.
● Lỗi Prefetch không được làm gián đoạn chức năng xem POI.

FR-VIS-011: Sử dụng nội dung Offline

Visitor có thể sử dụng dữ liệu đã lưu trong cache hoặc Offline Pack khi không có
Internet.

Các tài nguyên có thể sử dụng:

● Bản đồ đã tải.
● POI đã cache.
● Hình ảnh đã cache.
● Nội dung bản địa hóa đã cache.
● Audio đã cache.
● UI Bundles đã cache.

Nếu tài nguyên chưa được cache, hệ thống không được giả định có thể truy cập tài
nguyên đó Offline.

### 7.2. Nhóm B – Owner Portal

FR-OWN-001: Đăng ký Owner

Owner có thể gửi yêu cầu đăng ký tài khoản.

Dữ liệu đăng ký có thể bao gồm thông tin cá nhân và thông tin xác minh cần thiết.

Theo HTML:

● Đăng ký thông qua /admin/auth/register-owner.
● Thông tin nhạy cảm như CCCD được mã hóa bằng Fernet.
● Đơn đăng ký được lưu với trạng thái chờ xử lý.

---

<!-- Trang 26 -->
● Admin thực hiện phê duyệt hoặc từ chối.

Tiêu chí nghiệm thu:

● Tài khoản mới chưa được xác minh không có quyền quản lý POI.
● Thông tin nhạy cảm không được lưu dưới dạng plaintext.
● Owner nhận được kết quả xử lý đăng ký.

FR-OWN-002: Đăng nhập Owner

Owner đăng nhập bằng thông tin xác thực hợp lệ.

Hệ thống:

● Kiểm tra tài khoản.
● Kiểm tra mật khẩu.
● Kiểm tra trạng thái xác minh.
● Thiết lập phiên xác thực.
● Kiểm tra permission.
● Chuyển Owner đến giao diện phù hợp.

Owner chưa được phê duyệt không được sử dụng các chức năng quản lý POI.

FR-OWN-003: Xem POI sở hữu

Owner có thể xem danh sách POI thuộc quyền sở hữu.

Hệ thống chỉ trả về dữ liệu mà Owner có quyền truy cập.

FR-OWN-004: Tạo POI Submission

Owner có thể gửi thông tin một POI mới.

Dữ liệu có thể gồm:

● Tên.
● Mô tả.
● Danh mục.
● Địa chỉ.

---

<!-- Trang 27 -->
● Tọa độ.
● Hình ảnh.

Theo HTML, POI submission phải được Admin kiểm duyệt trước khi xuất hiện
công khai.

FR-OWN-005: Cập nhật POI

Owner có thể gửi yêu cầu cập nhật thông tin POI thuộc quyền sở hữu.

Owner không được cập nhật trực tiếp POI của người khác.

Các thay đổi cần qua quy trình submission/review theo thiết kế HTML.

FR-OWN-006: Quản lý nội dung POI

Owner có thể tạo và chỉnh sửa nội dung nguồn của POI theo quyền được cấp.

Hệ thống phải kiểm tra:

● POI có thuộc Owner hay không.
● Nội dung có hợp lệ hay không.
● Nội dung có đáp ứng điều kiện lưu hay không.
● Ngôn ngữ nguồn có được hỗ trợ hay không.

FR-OWN-007: Quản lý Language Version

Owner có thể xem và quản lý các phiên bản ngôn ngữ của nội dung POI.

Mỗi phiên bản ngôn ngữ cần gắn với POI tương ứng.

FR-OWN-008: Translation

Owner có thể yêu cầu hệ thống dịch nội dung POI.

Quy trình:

## 1. Owner chọn POI và ngôn ngữ đích.
## 2. Hệ thống lấy nội dung nguồn.
## 3. Translation Provider xử lý.

---

<!-- Trang 28 -->
## 4. Hệ thống nhận kết quả.
## 5. Kết quả được lưu thành phiên bản ngôn ngữ tương ứng.
## 6. Owner có thể xem lại và chỉnh sửa nội dung nếu được phép.

Nếu Translation thất bại, nội dung nguồn không được ghi đè hoặc mất dữ liệu.

FR-OWN-009: Generate Audio bằng TTS

Owner có thể yêu cầu tạo Audio từ nội dung văn bản đã có.

Hệ thống:

● Kiểm tra nội dung đầu vào.
● Kiểm tra ngôn ngữ và giọng đọc hỗ trợ.
● Tạo Audio Task.
● Gọi TTS Provider.
● Lưu Audio URL khi thành công.
● Cập nhật trạng thái tác vụ.

Nếu tạo Audio thất bại, nội dung văn bản vẫn được giữ nguyên.

FR-OWN-010: Preview Content & Audio

Owner có thể xem trước nội dung và nghe Audio đã tạo trước khi gửi hoặc hoàn tất
quy trình nội dung.

FR-OWN-011: Sử dụng AI Advisor

Owner có thể gửi nội dung mô tả POI đến AI Advisor để nhận gợi ý cải thiện.

Theo HTML:

● Provider: Gemini 2.5 Flash / ProxyPal.
● Giới hạn Owner: 10 lượt mỗi ngày.
● Thời gian chờ: 30 giây.
● Có thông tin Provider/Fallback khi xảy ra lỗi.
● AI không được tự tạo thông tin thực tế không có căn cứ.
● Nội dung gợi ý có độ dài mục tiêu khoảng 200–300 từ.

---

<!-- Trang 29 -->
Kết quả AI Advisor là bản gợi ý; Owner cần kiểm tra trước khi sử dụng.

FR-OWN-012: Theo dõi trạng thái Submission

Owner có thể xem trạng thái các yêu cầu đã gửi.

Các trạng thái nghiệp vụ cần hỗ trợ tối thiểu:

● Pending.
● Approved.
● Rejected.

Nếu bị từ chối, Owner có thể xem admin_note hoặc lý do kiểm duyệt tương
ứng.

FR-OWN-013: Owner Notifications

Owner có thể xem thông báo từ hệ thống.

Thông báo được tạo khi có kết quả xử lý đăng ký hoặc POI submission.

Owner có thể:

● Xem danh sách thông báo.
● Xem chi tiết.
● Đánh dấu đã đọc/chưa đọc theo chức năng được cung cấp.

### 7.3. Nhóm C – Admin Portal

FR-ADM-001: Admin Authentication

Admin đăng nhập vào Admin Portal.

Hệ thống kiểm tra thông tin xác thực và quyền truy cập trước khi cho phép sử dụng
chức năng quản trị.

FR-ADM-002: User Management

---

<!-- Trang 30 -->
Admin có thể:

● Xem danh sách tài khoản.
● Xem thông tin tài khoản.
● Quản lý trạng thái tài khoản.
● Thực hiện thao tác quản trị được permission cho phép.

FR-ADM-003: Role Management

Admin có thể quản lý vai trò và quyền.

Theo HTML, hệ thống có 32 RBAC permissions và hỗ trợ dynamic roles được lưu
trong database.

Quyền thực tế phải được kiểm tra ở Backend, không chỉ ẩn/hiện nút ở Frontend.

FR-ADM-004: POI Management

Admin có thể:

● Xem danh sách POI.
● Tạo POI.
● Chỉnh sửa POI.
● Xóa hoặc xử lý trạng thái POI theo quyền.
● Quản lý tọa độ.
● Quản lý hình ảnh.
● Quản lý trạng thái công khai.

FR-ADM-005: Menu Management

Admin có thể quản lý Menu và MenuItem thuộc POI.

Các thao tác CRUD phải tuân thủ kiểm tra permission và quan hệ dữ liệu.

FR-ADM-006: Owner Registration Review

Admin có thể xem các yêu cầu đăng ký Owner.

Admin có thể:

---

<!-- Trang 31 -->
● Xem thông tin đăng ký.
● Phê duyệt.
● Từ chối.
● Ghi chú lý do.
● Cập nhật trạng thái xác minh.

Khi được phê duyệt, hệ thống cập nhật trạng thái xác minh Owner theo quy tắc
trong HTML, bao gồm is_verified=true và
is_poi_owner_verified=true.

FR-ADM-007: POI Submission Review

Admin có thể tiếp nhận các yêu cầu tạo mới hoặc cập nhật POI.

Quy trình:

## 1. Admin mở danh sách submission.
## 2. Chọn submission cần xử lý.
## 3. Kiểm tra nội dung.
## 4. Chấp nhận hoặc từ chối.
## 5. Nếu chấp nhận, cập nhật POI chính thức.
## 6. Nếu từ chối, lưu ghi chú.
## 7. Tạo Owner Notification.

FR-ADM-008: Publish / Unpublish POI

Admin có thể bật hoặc tắt trạng thái công khai của POI.

Hệ thống phải kiểm tra điều kiện sẵn sàng trước khi Publish.

Theo HTML, readiness gate có liên quan đến trạng thái nội dung English và trạng
thái Audio.

Nếu chưa đạt điều kiện, hệ thống không được kích hoạt POI công khai.

FR-ADM-009: Localization Management

Admin có thể quản lý nội dung bản địa hóa và kiểm tra trạng thái dịch của POI.

---

<!-- Trang 32 -->
FR-ADM-010: Audio Task Monitoring

Admin có thể theo dõi Audio Tasks.

Theo HTML:

● Có tiến trình qua Server-Sent Events (SSE).
● Có heartbeat định kỳ.
● Có cơ chế phát hiện tác vụ stale.
● Có khả năng recovery sau khi Backend restart.
● Hỗ trợ điều khiển Pause/Resume/Cancel theo các thao tác được cung cấp.

FR-ADM-011: AI Advisor

Admin có thể sử dụng AI Advisor để cải thiện nội dung.

Theo HTML, Admin không áp dụng giới hạn 10 lượt/ngày như Owner.

FR-ADM-012: Analytics Dashboard

Admin có thể xem các dữ liệu tổng hợp phục vụ quản trị.

Analytics chỉ thu thập dữ liệu người dùng sau khi người dùng đã đồng ý.

tracked_online_users biểu thị các thiết bị ẩn danh đã đồng ý theo dõi và
hiện hoạt động trong cửa sổ thời gian, không phải tổng lượt truy cập hoặc số tab
trình duyệt.

FR-ADM-013: Audit Logs

Admin có thể xem nhật ký hoạt động của hệ thống.

Thông tin log có thể gồm:

● Action.
● User ID.
● Resource.
● Timestamp.

FR-ADM-014: Runtime Observability

---

<!-- Trang 33 -->
Admin có thể theo dõi các thông tin vận hành runtime được hệ thống cung cấp.

Dữ liệu vị trí phục vụ Runtime Observability là một luồng riêng, không được đồng
nhất với Analytics có sự đồng ý của người dùng.

### 7.4. Nhóm D – Localization, Translation và TTS

FR-AUD-001: Quản lý phiên bản ngôn ngữ

Mỗi POI có thể có nhiều phiên bản nội dung theo ngôn ngữ.

Dữ liệu bản địa hóa được liên kết với POI và ngôn ngữ tương ứng.

FR-AUD-002: Translation Provider

Hệ thống sử dụng dịch vụ Translation được mô tả trong HTML để tạo bản dịch.

Lỗi từ Provider không được làm mất nội dung nguồn.

FR-AUD-003: TTS Provider

Hệ thống sử dụng Edge-TTS theo công nghệ được mô tả trong HTML để chuyển
văn bản thành giọng nói.

FR-AUD-004: Audio Generation Tiers

HTML mô tả bốn tầng xử lý Audio:

## 1. Pre-generated Audio.
## 2. On-demand Audio.
## 3. Cloud TTS.
## 4. Local TTS.

Mục tiêu là ưu tiên Audio đã có, giảm thời gian chờ và có phương án dự phòng khi
một tầng không khả dụng.

Việc sử dụng từng tầng phải tuân theo khả năng thực tế của implementation.

---

<!-- Trang 34 -->
FR-AUD-005: Audio Task Lifecycle

Audio Task cần có trạng thái và thông tin phục vụ:

● Theo dõi tiến trình.
● Khôi phục sau restart.
● Heartbeat.
● Xác định tác vụ stale.
● Lưu trữ kết quả.
● Quản lý thời gian lưu trữ.

FR-AUD-006: Content Fallback

Khi không tìm được nội dung ở ngôn ngữ mục tiêu, hệ thống áp dụng thứ tự:

## 1. Target Language.
## 2. English.
## 3. Vietnamese.

Không được đánh dấu nội dung fallback là bản dịch hoàn chỉnh của ngôn ngữ mục
tiêu.

FR-AUD-007: Localization và UI i18n

Hệ thống quản lý hai luồng ngôn ngữ độc lập:

● POI Content Localization.
● UI Translation Bundles.

Việc chuyển ngôn ngữ hoàn tất khi các dữ liệu cần thiết của cả hai luồng đã sẵn
sàng hoặc hệ thống đã xác định trạng thái fallback phù hợp.

### 7.5. Nhóm E – GPS, Geofence và Audio Narration

FR-GPS-001: Lấy vị trí Visitor

---

<!-- Trang 35 -->
Hệ thống lấy vị trí thiết bị thông qua Geolocation API sau khi được người dùng
cho phép.

Thông tin cần có:

● Latitude.
● Longitude.
● Accuracy.
● Timestamp.

FR-GPS-002: GPS Throttle

Theo HTML, chu kỳ throttle mặc định là 5 giây.

Mục tiêu là hạn chế việc xử lý vị trí quá thường xuyên.

FR-GPS-003: Geofence Detection

Hệ thống tính khoảng cách từ Visitor đến POI và so sánh với Trigger Radius.

Trigger Radius mặc định là 30 mét.

FR-GPS-004: Debounce

Hệ thống sử dụng debounce 3 giây để tránh kích hoạt Geofence do dao động GPS
nhất thời.

FR-GPS-005: POI Selection

Khi có nhiều POI phù hợp, hệ thống lựa chọn theo:

## 1. audio_priority.
## 2. Khoảng cách.

Không được giả định mọi POI trong vùng đều phải được phát Audio cùng lúc.

FR-GPS-006: Cooldown

Theo HTML, thời gian cooldown mặc định là 5 phút.

---

<!-- Trang 36 -->
Mục tiêu là tránh tạo Audio Prompt lặp liên tục.

FR-GPS-007: Narration Engine

NarrationEngine nhận POI đã được Geofence xác nhận và chuẩn bị yêu cầu Audio.

Trong MVP, NarrationEngine phải phối hợp với Audio Prompt để Visitor quyết
định nghe trước khi phát.

FR-GPS-008: Audio Queue Manager

AudioQueueManager quản lý các yêu cầu Audio theo thứ tự và trạng thái xử lý.

Cần tránh phát trùng lặp hoặc phát nhiều Audio không kiểm soát.

FR-GPS-009: Audio Fallback

Nếu Audio không có sẵn hoặc lỗi, hệ thống có thể sử dụng các phương án dự
phòng được hỗ trợ.

Nếu không có Audio khả dụng, Visitor vẫn cần truy cập được nội dung văn bản
tương ứng.

### 7.6. Nhóm F – PWA và Offline

FR-OFF-001: Service Worker

Visitor PWA sử dụng Service Worker và Workbox để quản lý tài nguyên cache.

FR-OFF-002: Runtime Cache

Hệ thống có thể lưu các tài nguyên được truy cập thường xuyên.

Theo HTML:

● POI sử dụng NetworkFirst với timeout 8 giây.
● POI cache TTL mặc định 15 phút.
● Audio sử dụng CacheFirst theo từng ngôn ngữ.

---

<!-- Trang 37 -->
FR-OFF-003: IndexedDB

Hệ thống sử dụng IndexedDB với database Quan4DB v2 để lưu dữ liệu Offline.

FR-OFF-004: Offline Pack

Visitor có thể tải Offline Pack.

Offline Pack có thể bao gồm:

● Map.
● POI.
● Images.
● Audio.

FR-OFF-005: Offline Pack Installation

Quy trình cài đặt:

## 1. Lấy Manifest.
## 2. Xác định phiên bản và tài nguyên cần tải.
## 3. Tải Map.
## 4. Tải POI.
## 5. Tải Images.
## 6. Tải Audio.
## 7. Kiểm tra SHA-256 từng tài nguyên.
## 8. Chỉ kích hoạt Pack sau khi kiểm tra hợp lệ.

FR-OFF-006: Cache Management

Theo HTML:

● Audio cache tối đa 300 file cho mỗi ngôn ngữ.
● Tối đa 3 ngôn ngữ được giữ đồng thời.
● Sử dụng LRU để loại bỏ dữ liệu cũ.
● Nếu dung lượng lưu trữ đầy, runtime cache có thể được dọn để ưu tiên
Offline Pack.

FR-OFF-007: Offline Map

---

<!-- Trang 38 -->
Hệ thống hỗ trợ PMTiles và tài nguyên bản đồ cục bộ.

Các chế độ bản đồ được mô tả:

● Cloud.
● Offline.
● Hybrid.

FR-OFF-008: Offline Content Fallback

Khi Offline, hệ thống chỉ sử dụng tài nguyên đã được cache.

Thứ tự fallback:

## 1. Ngôn ngữ mục tiêu.
## 2. English.
## 3. Vietnamese.

Trong target lane, cần bỏ qua nội dung được đánh dấu is_fallback=true.

FR-OFF-009: Offline Limitation

Các thao tác cần Backend hoặc Provider trực tuyến không được xem là có thể hoạt
động đầy đủ khi Offline.

Bao gồm:

● Translation mới.
● TTS mới.
● AI Advisor.
● Các thao tác quản trị và Owner Portal.
● Các thao tác đồng bộ dữ liệu cần Backend.

Nếu không có tài nguyên đã tải, hệ thống hiển thị thông báo phù hợp.

## 8. QUY TẮC NGHIỆP VỤ

---

<!-- Trang 39 -->
Rule ID Quy tắc

BR-001 Visitor có thể sử dụng chức năng khám phá công khai mà không cần đăng nhập.

BR-002 Owner phải được Admin phê duyệt trước khi quản lý POI.

BR-003 Owner chỉ được thao tác trên POI thuộc quyền sở hữu.

BR-004 POI submission của Owner phải qua kiểm duyệt trước khi công khai.

BR-005 Admin có quyền phê duyệt hoặc từ chối Owner Registration và POI
Submission.

BR-006 POI là thực thể địa điểm chính; Geofence là vùng bán kính quanh tọa độ POI.

BR-007 Hình ảnh là tài nguyên thuộc POI, không phải Exhibit độc lập.

BR-008 POI không đạt điều kiện readiness không được Publish.

BR-009 AI Advisor không được tự bịa thông tin thực tế về POI.

BR-010 Owner có giới hạn 10 lượt AI Advisor mỗi ngày theo HTML.

---

<!-- Trang 40 -->
BR-011 Admin không áp dụng giới hạn AI Advisor 10 lượt/ngày như Owner.

BR-012 Translation thất bại không được làm mất nội dung nguồn.

BR-013 TTS thất bại không được làm mất nội dung văn bản.

BR-014 Content Fallback theo Target → English → Vietnamese.

BR-015 UI Bundle và POI Localization là hai luồng dữ liệu độc lập.

BR-016 Geofence sử dụng debounce để tránh kích hoạt do dao động GPS.

BR-017 POI được lựa chọn theo audio_priority và khoảng cách.

BR-018 Cooldown được sử dụng để tránh Audio Prompt lặp liên tục.

BR-019 MVP yêu cầu Visitor xác nhận nghe Audio trước khi phát.

BR-020 Background Prefetch dịch nội dung độc lập với Audio Queue.

BR-021 Background Prefetch xử lý tối đa 3 POI mỗi đợt.

BR-022 Offline chỉ sử dụng tài nguyên đã cache hoặc tải trước.

---

<!-- Trang 41 -->
BR-023 Offline Pack chỉ được kích hoạt sau khi xác minh tài nguyên.

BR-024 Analytics chỉ thu thập dữ liệu sau khi có sự đồng ý của người dùng.

BR-025 Runtime Observability và Analytics là hai luồng dữ liệu riêng.

BR-026 Quyền truy cập phải được xác minh ở Backend.

## 9. YÊU CẦU PHI CHỨC NĂNG

### 9.1. Security

NFR-SEC-001: Các tài khoản Admin và Owner phải được xác thực trước khi truy
cập chức năng riêng tư.

NFR-SEC-002: Access Token và Refresh Token phải được quản lý theo cơ chế
bảo mật trong HTML.

Thông số được mô tả:

● Access Token: 30 phút.
● Refresh Token: 7 ngày.

NFR-SEC-003: Cookie xác thực sử dụng HttpOnly và SameSite=Lax theo cấu
hình HTML.

NFR-SEC-004: Hệ thống có CSRF Protection.

NFR-SEC-005: Mật khẩu phải được lưu dưới dạng hash, không lưu plaintext.

---

<!-- Trang 42 -->
NFR-SEC-006: Thông tin nhạy cảm như CCCD phải được mã hóa.

NFR-SEC-007: Backend phải kiểm tra RBAC và quyền sở hữu dữ liệu.

NFR-SEC-008: Các thao tác quan trọng cần có Audit Logs.

### 9.2. Performance và Resource Management

Các thông số sau là giá trị cấu hình được ghi trong HTML, không phải SLA đã
được kiểm chứng.

Thông số Giá trị

GPS throttle 5 giây

Best-effort locate budget 15 giây

Cached location max age 30 giây

Geofence debounce 3 giây

Trigger Radius mặc định 30 mét

Geofence cooldown 5 phút

Geofence reconcile 5 giây

---

<!-- Trang 43 -->
Prefetch bán kính 500 mét

Prefetch tối đa mỗi đợt 3 POI

Prefetch interval tối thiểu 30 giây

POI cache TTL 15 phút

POI NetworkFirst timeout 8 giây

Audio cache CacheFirst theo ngôn ngữ

Audio cache tối đa 300 file/ngôn ngữ

Số ngôn ngữ Audio cache Tối đa 3

TTS concurrency Tối đa 3

Audio Task heartbeat 5 giây

Audio Task stale threshold 5 phút

Audio Task retention 14 ngày

---

<!-- Trang 44 -->
Owner AI quota 10 lượt/ngày

AI timeout 30 giây

AI description target 200–300 từ

Localization on-demand rate limit 30 request/10 phút

POI images Tối đa 8 ảnh/POI

Kích thước ảnh Tối đa 5 MB/ảnh

Hotset nearby 1.500 mét

Hotset tối đa 10 POI ID

### 9.3. Reliability

NFR-REL-001: Hệ thống phải xử lý được trường hợp Translation Provider không
phản hồi.

NFR-REL-002: Hệ thống phải xử lý được trường hợp TTS Provider không phản
hồi.

NFR-REL-003: Lỗi một dịch vụ không được làm mất dữ liệu nguồn.

NFR-REL-004: Audio Tasks cần có khả năng recovery sau Backend restart theo
cơ chế HTML mô tả.

---

<!-- Trang 45 -->
NFR-REL-005: Geofence phải có debounce và cooldown.

NFR-REL-006: Offline Pack chỉ được kích hoạt khi tài nguyên đã vượt qua bước
xác minh.

### 9.4. Usability

NFR-USE-001: Visitor phải có thể khám phá POI mà không cần tạo tài khoản.

NFR-USE-002: Audio Prompt phải thể hiện rõ POI và lựa chọn nghe/từ chối.

NFR-USE-003: Nếu GPS bị từ chối, Visitor vẫn có thể sử dụng bản đồ thủ công.

NFR-USE-004: Owner phải có thể theo dõi trạng thái submission.

NFR-USE-005: Admin phải có thể nhận biết trạng thái tác vụ Audio và trạng thái
kiểm duyệt.

### 9.5. Compatibility và PWA

NFR-PWA-001: Visitor Portal phải hỗ trợ trải nghiệm PWA.

NFR-PWA-002: Service Worker phải quản lý cache theo chiến lược được cấu
hình.

NFR-PWA-003: Ứng dụng phải có phương án fallback khi không có Internet.

NFR-PWA-004: Bản đồ Offline phải sử dụng các tài nguyên PMTiles và
style/glyph/sprite cần thiết đã tải.

NFR-PWA-005: Các chức năng cần Backend phải thông báo trạng thái khi
Offline.

### 9.6. Maintainability

NFR-MNT-001: Backend được tổ chức theo module nghiệp vụ.

NFR-MNT-002: Các module phải có boundary tương đối rõ ràng.

---

<!-- Trang 46 -->
NFR-MNT-003: Frontend và Backend phải có thể kiểm thử độc lập theo chức
năng.

NFR-MNT-004: Các thông số như Trigger Radius, cooldown, cache TTL và quota
cần được quản lý tập trung thay vì rải rác trong code.

## 10. LUỒNG NGHIỆP VỤ CHÍNH

### 10.1. Luồng Visitor khám phá POI

## 1. Visitor mở Visitor PWA.
## 2. Hệ thống khởi tạo Service Worker.
## 3. Visitor lựa chọn ngôn ngữ.
## 4. Hệ thống tải UI Bundle và POI Localization.
## 5. Hệ thống tải dữ liệu POI.
## 6. Visitor xem bản đồ.
## 7. Visitor chọn một POI.
## 8. Hệ thống hiển thị thông tin chi tiết.
## 9. Visitor có thể nghe Audio Guide thủ công.

### 10.2. Luồng GPS và Audio Prompt MVP

## 1. Visitor cấp quyền GPS.
## 2. Hệ thống nhận vị trí.
## 3. GPS cập nhật theo throttle.
## 4. Geofence Engine tính khoảng cách tới POI.
## 5. Hệ thống kiểm tra Trigger Radius.
## 6. Debounce xác nhận Visitor thực sự đi vào vùng.
## 7. Hệ thống kiểm tra cooldown.
## 8. Hệ thống lựa chọn POI phù hợp.
## 9. NarrationEngine chuẩn bị Audio.
10.Hệ thống hiển thị Audio Prompt.
11.Visitor chọn nghe hoặc từ chối.

---

<!-- Trang 47 -->
12.Nếu đồng ý, AudioQueueManager xử lý phát Audio.
13.Nếu không đồng ý, hệ thống tiếp tục hoạt động bình thường.

### 10.3. Luồng Background Translation Prefetch

## 1. Hệ thống có dữ liệu vị trí Visitor và danh sách POI.
## 2. Prefetch Manager xác định POI trong phạm vi 500 mét.
## 3. Lọc các POI có is_fallback=true.
## 4. Chọn tối đa 3 POI cho một đợt.
## 5. Gửi yêu cầu Translation tuần tự.
## 6. Lưu kết quả thành Localization.
## 7. Nếu gặp HTTP 429, áp dụng backoff.
## 8. Chờ ít nhất 30 giây trước khi xử lý đợt tiếp theo.

Luồng này chạy độc lập với luồng phát Audio.

### 10.4. Luồng Owner đăng ký và quản lý POI

## 1. Owner gửi đăng ký.
## 2. Hệ thống lưu đăng ký ở trạng thái Pending.
## 3. Admin kiểm tra thông tin.
## 4. Admin phê duyệt hoặc từ chối.
## 5. Nếu được duyệt, Owner được xác minh.
## 6. Owner đăng nhập.
## 7. Owner tạo hoặc cập nhật POI Submission.
## 8. Admin kiểm duyệt.
## 9. Nếu Approved, dữ liệu POI chính thức được cập nhật.
10.Nếu Rejected, lưu lý do và gửi Notification.
11.Owner theo dõi kết quả.

### 10.5. Luồng Translation và TTS

## 1. Owner/Admin chọn POI.
## 2. Chọn ngôn ngữ đích.
## 3. Yêu cầu Translation.

---

<!-- Trang 48 -->
## 4. Hệ thống gọi Translation Provider.
## 5. Lưu bản dịch.
## 6. Người quản lý nội dung kiểm tra nội dung.
## 7. Yêu cầu TTS.
## 8. Hệ thống tạo Audio Task.
## 9. TTS Provider xử lý.
10.Hệ thống lưu Audio URL.
11.Người quản lý nội dung Preview Audio.
12.Nội dung được sử dụng trong Visitor Portal khi đủ điều kiện công khai.

### 10.6. Luồng Offline Pack

## 1. Hệ thống kiểm tra version UI bundle, POI data.
## 2. Hệ thống lấy Manifest.
## 3. Tải bản đồ.
## 4. Tải dữ liệu POI.
## 5. Tải hình ảnh.
## 6. Tải Audio.
## 7. Xác minh SHA-256.
## 8. Nếu hợp lệ, kích hoạt Pack.
## 9. Khi Offline, Visitor sử dụng dữ liệu đã lưu.
10.Nếu thiếu tài nguyên, hệ thống hiển thị nội dung fallback hoặc thông báo
không khả dụng.

## 11. USE CASE BASELINE

Bảng dưới đây là danh sách Use Case đề xuất đã điều chỉnh để phù hợp với HTML
và các quyết định MVP.

### 11.1. Visitor Use Cases

---

<!-- Trang 49 -->
UC ID Use Case Actor

UC-VIS-01 Access Visitor PWA Visitor

UC-VIS-02 Select Language Visitor

UC-VIS-03 View Map & POI Visitor

UC-VIS-04 View POI Information Visitor

UC-VIS-05 Get Current Location Visitor, GPS Provider

UC-VIS-06 Detect Nearby POI / Geofence GPS Provider

UC-VIS-07 Receive Audio Prompt Visitor

UC-VIS-08 Play Audio Guide Visitor, TTS/Audio Service

UC-VIS-09 Access Cached Content Offline Visitor

### 11.2. Owner Use Cases

UC ID Use Case Actor

---

<!-- Trang 50 -->
UC-OWN-01 Register Owner Owner

UC-OWN-02 Authenticate Owner Owner

UC-OWN-03 View Owned POIs Owner

UC-OWN-04 Manage POI Content Owner

UC-OWN-05 Translate Content Translation Provider

UC-OWN-06 Generate Audio TTS Provider

UC-OWN-07 Preview Content & Audio Owner

UC-OWN-08 Use AI Advisor Owner, AI Provider

UC-OWN-09 View Submission Status Owner

UC-OWN-10 View Notifications Owner

### 11.3. Admin Use Cases

UC ID Use Case Actor

---

<!-- Trang 51 -->
UC-ADM-01 Authenticate Admin Admin

UC-ADM-02 Manage Users Admin

UC-ADM-03 Manage Roles & Permissions Admin

UC-ADM-04 Manage POI Admin

UC-ADM-05 Manage Menu & MenuItem Admin

UC-ADM-06 Review Owner Registration Admin

UC-ADM-07 Review POI Submission Admin

UC-ADM-08 Analytic Localization Admin

UC-ADM-09 Monitor Audio Tasks Admin

UC-ADM-10 Use AI Advisor Admin, AI Provider

UC-ADM-11 View Analytics Admin

UC-ADM-12 View Audit Logs Admin

---

<!-- Trang 52 -->
UC-ADM-13 Monitor Runtime Observability Admin

### 11.4. Quan hệ Use Case cần lưu ý

● Access Visitor PWA bao gồm tải dữ liệu POI và UI Bundle.
● View Map & POI bao gồm Get Current Location khi Visitor cấp quyền.
● Detect Nearby POI / Geofence kích hoạt Receive Audio Prompt khi điều
kiện phù hợp.
● Confirm or Decline Audio quyết định có tiếp tục luồng phát Audio hay
không.
● Play Audio Guide sử dụng Audio Queue và các cơ chế fallback.
● Translate Content sử dụng Translation Provider.
● Generate Audio sử dụng TTS Provider.
● Use AI Advisor sử dụng AI Provider.
● Publish POI phải kiểm tra POI đã có english localization chưa.
● Review POI Submission tạo Owner Notification.
● Access Cached Content Offline phụ thuộc dữ liệu đã cache hoặc Offline
Pack.

Các quan hệ include và extend trong UML cần được thể hiện theo ý nghĩa bắt
buộc/tùy chọn của từng luồng, không chỉ dựa vào việc hai chức năng có liên quan
nhau.

## 12. ACCEPTANCE CRITERIA – TIÊU CHÍ
NGHIỆM THU

### 12.1. Visitor

---

<!-- Trang 53 -->
AC ID Điều kiện nghiệm thu

AC-VIS-01 Visitor mở được PWA và truy cập Visitor Portal.

AC-VIS-02 Visitor chọn được ngôn ngữ được hỗ trợ.

AC-VIS-03 Visitor xem được bản đồ và POI công khai.

AC-VIS-04 Visitor xem được thông tin chi tiết POI.

AC-VIS-05 Visitor từ chối GPS vẫn xem được bản đồ.

AC-VIS-06 Geofence chỉ kích hoạt sau khi thỏa mãn điều kiện xác nhận.

AC-VIS-07 Audio Prompt xuất hiện cho POI phù hợp.

AC-VIS-08 Visitor có thể từ chối nghe mà không làm gián đoạn ứng dụng.

AC-VIS-09 Visitor đồng ý nghe thì Audio Queue xử lý phát Audio.

AC-VIS-10 Audio lỗi thì nội dung văn bản vẫn truy cập được.

AC-VIS-11 Background Prefetch không vượt quá 3 POI mỗi đợt.

---

<!-- Trang 54 -->
AC-VIS-12 Prefetch không làm gián đoạn luồng Audio.

AC-VIS-13 Offline Pack chỉ được kích hoạt sau khi kiểm tra checksum thành công.

### 12.2. Owner

AC ID Điều kiện nghiệm thu

AC-OWN-01 Owner gửi được yêu cầu đăng ký.

AC-OWN-02 Owner chưa được duyệt không thể quản lý POI.

AC-OWN-03 Owner được duyệt có thể đăng nhập.

AC-OWN-04 Owner chỉ xem và thao tác trên POI được phép.

AC-OWN-05 Owner gửi được POI Submission hợp lệ.

AC-OWN-06 Owner xem được trạng thái submission.

AC-OWN-07 Owner nhận được thông báo khi submission được xử lý.

AC-OWN-08 Owner yêu cầu Translation được.

---

<!-- Trang 55 -->
AC-OWN-09 Translation lỗi không làm mất nội dung nguồn.

AC-OWN-10 Owner tạo Audio Task được.

AC-OWN-11 TTS lỗi không làm mất nội dung văn bản.

AC-OWN-12 Owner Preview được nội dung và Audio.

AC-OWN-13 Owner AI Advisor không vượt quá quota được cấu hình.

### 12.3. Admin

AC ID Điều kiện nghiệm thu

AC-ADM-01 Admin đăng nhập được bằng tài khoản hợp lệ.

AC-ADM-02 Admin quản lý được User theo permission.

AC-ADM-03 Admin quản lý được Role/Permission.

AC-ADM-04 Admin CRUD POI theo quyền.

AC-ADM-05 Admin quản lý được Menu/MenuItem.

---

<!-- Trang 56 -->
AC-ADM-06 Admin phê duyệt hoặc từ chối Owner
Registration.

AC-ADM-07 Admin phê duyệt hoặc từ chối POI Submission.

AC-ADM-08 Owner nhận được Notification sau khi submission
được xử lý.

AC-ADM-09 POI không đạt readiness không được Publish.

AC-ADM-10 Admin xem được trạng thái Audio Tasks.

AC-ADM-11 Admin xem được Analytics có consent.

AC-ADM-12 Admin xem được Audit Logs.

AC-ADM-13 Admin xem được Runtime Observability.

### 12.4. Security và Offline

AC ID Điều kiện nghiệm thu

AC-SEC-01 Backend từ chối request không có quyền.

---

<!-- Trang 57 -->
AC-SEC-02 Owner không truy cập được POI của
Owner khác.

AC-SEC-03 Dữ liệu nhạy cảm được mã hóa theo thiết
kế.

AC-SEC-04 Cookie và CSRF được cấu hình theo
HTML.

AC-OFF-01 Visitor truy cập được POI đã cache khi
Offline.

AC-OFF-02 Visitor phát được Audio đã cache khi
Offline.

AC-OFF-03 Visitor xem được bản đồ nếu Map Pack đã
tải đầy đủ.

AC-OFF-04 Tài nguyên chưa cache không được giả
định là khả dụng.

AC-OFF-05 Translation/TTS/AI Advisor mới không
được mô tả là chức năng Offline.

---

<!-- Trang 58 -->
## 13. UI/UX REQUIREMENTS

### 13.1. Visitor Portal

Giao diện cần ưu tiên trải nghiệm khám phá:

● Bản đồ là khu vực hiển thị chính.
● POI có dấu hiệu nhận biết rõ.
● Có thể mở thông tin chi tiết POI.
● Có lựa chọn ngôn ngữ dễ tiếp cận.
● Có trạng thái GPS rõ ràng.
● Audio Prompt không che khuất các thao tác quan trọng.
● Audio Player hiển thị trạng thái đang phát.
● Có thông báo khi nội dung chỉ có thể truy cập Online.
● Có khu vực quản lý Offline Pack.

### 13.2. Owner Portal

Giao diện cần hỗ trợ:

● Đăng ký và theo dõi trạng thái xác minh.
● Danh sách POI sở hữu.
● Form tạo/cập nhật POI.
● Quản lý hình ảnh POI.
● Quản lý nội dung và phiên bản ngôn ngữ.
● Translation và TTS.
● Preview.
● AI Advisor.
● Submission Status.
● Notifications.

### 13.3. Admin Portal

Giao diện cần hỗ trợ:

---

<!-- Trang 59 -->
● Dashboard.
● User Management.
● Role & Permission Management.
● POI Management.
● Menu Management.
● Owner Registration Review.
● POI Submission Review.
● Localization.
● Audio Task Monitoring.
● AI Advisor.
● Analytics.
● Audit Logs.
● Runtime Observability.

### 13.4. Responsive Design

● Visitor Portal phải thích ứng với màn hình điện thoại và desktop.
● Owner Portal và Admin Portal phải có bố cục phù hợp cho màn hình
desktop.
● Các chức năng quản lý nội dung phải sử dụng form có validation rõ ràng.
● Các trạng thái Pending, Approved, Rejected, Processing, Failed phải dễ nhận
biết.

## 14. DATA REQUIREMENTS

### 14.1. POI

POI là dữ liệu trung tâm của sản phẩm.

Các nhóm trường dữ liệu dự kiến:

---

<!-- Trang 60 -->
Nhóm Trường dữ liệu

Identity id

Basic Information name, description, category

Address address

Location latitude, longitude

Media images

Geofence trigger_radius

Ownership owner_id

Publication is_active

Content source content, language versions

Audio audio_url, audio status

Audit created_at, updated_at

---

<!-- Trang 61 -->
Tên trường là định hướng logic; cấu trúc vật lý cần tuân theo schema thực tế của
HTML/backend.

### 14.2. POI Localization

Dữ liệu bản địa hóa được quản lý theo POI và ngôn ngữ.

Các thông tin chính:

● poi_id.
● lang.
● Translated content.
● Audio URL.
● Fallback status.
● Trạng thái sẵn sàng.

### 14.3. Audio Task

Audio Task cần có dữ liệu để:

● Nhận diện tác vụ.
● Theo dõi trạng thái.
● Theo dõi tiến trình.
● Ghi nhận heartbeat.
● Phục hồi sau restart.
● Liên kết kết quả Audio.

### 14.4. Owner Registration và POI Submission

Các yêu cầu đăng ký và submission cần lưu:

● Người gửi.
● Nội dung yêu cầu.
● Trạng thái.
● Thời gian gửi.
● Người xử lý.

---

<!-- Trang 62 -->
● Ghi chú kiểm duyệt.
● Thời gian xử lý.

### 14.5. Data Retention

HTML ghi nhận:

● Audio Task retention: 14 ngày.
● PII retention: 180 ngày.

Đây là thông số lưu trữ hiện được mô tả trong HTML. Cần xác nhận lại chính sách
lưu trữ cuối cùng trước khi triển khai thực tế, đặc biệt với dữ liệu định danh và dữ
liệu vị trí.

## 15. API VÀ TÍCH HỢP HỆ THỐNG

### 15.1. API Modules

HTML mô tả 10 mounted FastAPI routers:

## 1. content
## 2. audio
## 3. admin
## 4. owner
## 5. ai_advisor
## 6. analytics
## 7. localization
## 8. maps
## 9. runtime_observability
10.ui_i18n

### 15.2. Các API Flow quan trọng

---

<!-- Trang 63 -->
Nghiệp vụ Endpoint/nhóm API được HTML đề cập

Owner Registration POST
/admin/auth/register-owner

Owner POI Update PUT /owner/pois/{id}

Owner POI Submission POST /owner/submissions

Owner Notifications /owner/notifications*

POI Load /poi/load-all

Map Manifest /static/maps/*, /api/v1/maps/*

Các endpoint còn lại cần lấy theo API implementation thực tế. PRD không tự đặt
endpoint mới nếu HTML chưa cung cấp.

### 15.3. External Integrations

Integration Mục đích

GPS / Browser Geolocation Lấy vị trí Visitor

---

<!-- Trang 64 -->
Translation Provider Dịch nội dung POI

Edge-TTS Chuyển văn bản thành Audio

Gemini 2.5 Flash / ProxyPal AI Advisor

MapLibre Hiển thị bản đồ

PMTiles Cung cấp dữ liệu bản đồ Offline

MapTiler Tài nguyên bản đồ trực tuyến theo cấu hình

Trạng thái tạm thời trong tiến trình; dữ liệu bền được lưu trong PostgreSQL

PostgreSQL + PostGIS Lưu dữ liệu nghiệp vụ và truy vấn không gian

## 16. TECHNOLOGY CONSTRAINTS

Theo HTML, công nghệ được mô tả gồm:

Layer Technology

---

<!-- Trang 65 -->
Frontend React 19.2

Build Tool Vite 7

PWA Service Worker, Workbox

Map MapLibre

Offline Map PMTiles

Backend FastAPI

Database PostgreSQL + PostGIS

Cache / Runtime State Trạng thái trong tiến trình

Translation deep-translator / Google Translate

TTS Edge-TTS

AI Advisor Gemini 2.5 Flash / ProxyPal

Offline Storage IndexedDB

---

<!-- Trang 66 -->
Streaming Task Progress Server-Sent Events

Map Assets PMTiles, local style, glyphs, sprites

Các công nghệ trên là technology baseline theo HTML. Thay đổi công nghệ cần
được thống nhất và cập nhật lại tài liệu kiến trúc.

## 17. RISKS VÀ MITIGATION

Risk ID Rủi ro Ảnh hưởng Hướng giảm thiểu

R-01 GPS không chính Geofence kích Debounce, accuracy check,
xác hoạt sai cooldown

R-02 Nhiều POI gần Audio Prompt Priority và distance selection
nhau trùng lặp

R-03 Audio phát không Trải nghiệm MVP yêu cầu Visitor xác
đúng thời điểm kém nhận

R-04 Translation Không có bản Fallback và giữ nội dung
Provider lỗi dịch nguồn

---

<!-- Trang 67 -->
R-05 TTS Provider lỗi Không tạo được Giữ văn bản, sử dụng Audio
Audio fallback nếu có

R-06 AI trả về nội dung Sai thông tin Owner/Admin kiểm tra kết
không chính xác POI quả AI

R-07 Offline cache thiếu Không truy cập Offline Pack, checksum,
dữ liệu được nội fallback
dung

R-08 Dung lượng thiết bị Không tải được LRU, giới hạn cache
hạn chế Offline Pack

R-09 Owner sửa POI Vi phạm dữ liệu Backend ownership
không thuộc sở validation
hữu

R-10 Admin cấu hình sai Rủi ro bảo mật RBAC validation và Audit
quyền Logs

R-11 Analytics thiếu Rủi ro quyền Consent-gated collection
consent riêng tư

R-12 Audio Task bị treo Tác vụ không Heartbeat, stale detection,
hoàn tất recovery

---

<!-- Trang 68 -->
## 18. OPEN ISSUES – CÁC ĐIỂM CẦN XÁC
NHẬN KHI TRIỂN KHAI

Các điểm sau chưa đủ căn cứ để PRD quy định thành hành vi bắt buộc:

ID Vấn đề Nội dung cần xác nhận

OI-01 Danh sách ngôn Những ngôn ngữ nào được hỗ trợ chính thức trong
ngữ MVP?

OI-02 POI readiness Điều kiện chính xác để Publish ngoài English
readiness và Audio status?

OI-03 Audio Priority Admin có thể chỉnh audio_priority hay hệ
thống tự xác định?

OI-04 Audio Prompt Một Prompt có thể chờ bao lâu trước khi tự hết hạn?

OI-05 Audio Queue Nếu Visitor đi vào POI mới trong khi Audio cũ đang
phát thì xử lý thế nào?

OI-06 Visitor Settings Visitor có thể tùy chỉnh bán kính Geofence không?

OI-07 Offline Pack Visitor được tải bao nhiêu Pack và có giới hạn dung
lượng không?

---

<!-- Trang 69 -->
OI-08 Owner Bộ thông tin xác minh Owner chính thức gồm những
Registration gì?

OI-09 POI Submission Owner có thể sửa submission đang Pending hay phải
tạo submission mới?

OI-10 MenuItem Phạm vi CRUD và các trường dữ liệu MenuItem cần
xác nhận theo schema thực tế.

OI-11 Analytics Consent Cơ chế hiển thị và lưu trạng thái đồng ý cần được
xác nhận.

OI-12 Runtime Phạm vi dữ liệu vị trí được thu thập và thời hạn lưu
Observability trữ cần xác nhận.

OI-13 Visitor Account Có bổ sung tài khoản Visitor trong phiên bản sau hay
không?

OI-14 AI Advisor Owner/Admin được phép sử dụng AI trên những
trường nội dung nào?

OI-15 Media Storage Backend lưu hình ảnh và Audio trên local storage
hay S3-compatible storage theo môi trường?

Các Open Issues không làm mất đi phạm vi chức năng đã xác định; chúng là những
điểm cần quyết định trước khi hoàn thiện thiết kế chi tiết hoặc triển khai phần liên
quan.

---

<!-- Trang 70 -->
## 19. TRACEABILITY MATRIX – TRUY
VẾT YÊU CẦU

Requirement Group Use Case liên quan Activity Diagram liên quan

Authentication & UC-OWN-02, AD-01 Staff Authentication
RBAC UC-ADM-01,
UC-ADM-02,
UC-ADM-03

POI Management UC-OWN-03, AD-02 POI / Location & Owner
UC-OWN-04, Management
UC-OWN-05,
UC-ADM-04

Content Management UC-OWN-06, AD-03 Content Creation &
UC-OWN-07, Management
UC-ADM-09

Translation & TTS UC-OWN-08, AD-04 Translation & Audio
UC-OWN-09, Generation
UC-OWN-10,
UC-ADM-10

Publish / Unpublish UC-ADM-08 AD-05 Publish / Unpublish

---

<!-- Trang 71 -->
Visitor Map & POI UC-VIS-01, AD-06 Visitor Map & POI
UC-VIS-02, Discovery
UC-VIS-03,
UC-VIS-04

GPS / Geofence UC-VIS-05, AD-07 GPS / Geofence &
UC-VIS-06, Audio
UC-VIS-07,
UC-VIS-08,
UC-VIS-09

Offline / PWA UC-VIS-10, AD-08 PWA & Offline
UC-VIS-11

Owner Registration UC-OWN-01, AD-02
UC-ADM-06

Submission Review UC-ADM-07, AD-02
UC-OWN-12,
UC-OWN-13

AI Advisor UC-OWN-11, AD-03 / AD-04 (cần bổ sung
UC-ADM-11 nhánh AI Advisor riêng nếu
mô hình hóa chi tiết)

Analytics UC-ADM-12 Chưa có Activity Diagram riêng

---

<!-- Trang 72 -->
Audit Logs UC-ADM-13 Chưa có Activity Diagram riêng

Runtime Observability UC-ADM-14 Chưa có Activity Diagram riêng

Menu Management UC-ADM-05 Chưa có Activity Diagram riêng

## 20. KẾ HOẠCH TRIỂN KHAI ĐỀ XUẤT

Đề xuất chia thành các giai đoạn để hạn chế phụ thuộc và tránh triển khai quá
nhiều chức năng cùng lúc.

Phase 1 – Foundation

● Khởi tạo Frontend và Backend.
● Thiết lập Database.
● Thiết lập Authentication.
● Thiết lập RBAC.
● Xây dựng cấu trúc POI.
● Thiết lập môi trường phát triển và CI/CD.

Phase 2 – POI & Management

● Owner Registration.
● Admin Review Owner.
● POI CRUD.
● Owner POI Submission.
● Admin Submission Review.
● Owner Notification.
● Menu/MenuItem Management.

---

<!-- Trang 73 -->
Phase 3 – Localization & Audio

● Quản lý nội dung POI.
● Language Version.
● Translation.
● TTS.
● Audio Task.
● Audio Preview.
● AI Advisor.
● Publish Readiness.

Phase 4 – Visitor Experience

● Visitor PWA.
● Map & POI.
● POI Detail.
● GPS.
● Geofence.
● Audio Prompt.
● Audio Queue.
● Audio Playback.

Phase 5 – Offline & Admin Advanced

● Service Worker.
● IndexedDB.
● Offline Pack.
● PMTiles.
● Offline Audio.
● Analytics.
● Audit Logs.
● Runtime Observability.
● Audio Task Monitoring.

Phase 6 – Testing & Release

---

<!-- Trang 74 -->
● Functional Testing.
● Integration Testing.
● Security Testing.
● GPS/Geofence Testing.
● Offline Testing.
● Responsive Testing.
● UAT.
● Deployment.

Thứ tự trên là đề xuất phụ thuộc kỹ thuật, không phải cam kết thời gian cố định.

## 21. DEFINITION OF DONE

Một chức năng được xem là hoàn thành khi đáp ứng các điều kiện:

## 1. Đáp ứng yêu cầu chức năng tương ứng trong PRD.
## 2. Có kiểm tra dữ liệu đầu vào.
## 3. Có xử lý lỗi và trạng thái ngoại lệ.
## 4. Có kiểm tra quyền truy cập nếu là chức năng riêng tư.
## 5. Có kiểm thử chức năng chính.
## 6. Có kiểm thử các trường hợp thất bại quan trọng.
## 7. Không làm hỏng các chức năng hiện có.
## 8. Có giao diện phản hồi trạng thái phù hợp.
## 9. API và dữ liệu được cập nhật đúng.
10.Tài liệu liên quan được cập nhật.
11.Thay đổi được quản lý qua Git.
12.CI/CD và quy trình triển khai không phát sinh lỗi chưa được xử lý.

## 22. KẾT LUẬN

---

<!-- Trang 75 -->
Quan4 Culinary Tourism là nền tảng khám phá du lịch ẩm thực tập trung vào POI,
bản đồ tương tác, GPS/Geofence và Audio Guide đa ngôn ngữ.

Sản phẩm được tổ chức thành ba khu vực sử dụng chính:

● Visitor Portal: Khám phá POI, sử dụng GPS, nhận Audio Prompt, nghe
Audio Guide và truy cập nội dung đã cache khi Offline.
● Owner Portal: Đăng ký, quản lý POI thuộc quyền sở hữu, tạo nội dung đa
ngôn ngữ và gửi yêu cầu kiểm duyệt.
● Admin Portal: Quản trị hệ thống, quản lý tài khoản và quyền, kiểm duyệt
POI, giám sát Audio, Analytics, Audit Logs và Runtime Observability.

Các thành phần kỹ thuật như Translation, TTS, AI Advisor, Geofence, Audio
Queue, PWA và Offline Pack đóng vai trò hỗ trợ các luồng nghiệp vụ chính.

PRD này là baseline để nhóm tiếp tục hoàn thiện Use Case Specification, Activity
Diagram, Sequence Diagram, ERD, API Specification và thiết kế UI/UX.

Nguyên tắc phát triển: Ưu tiên các luồng nghiệp vụ cốt lõi, bảo đảm tính đúng
đắn và khả năng kiểm thử trước khi mở rộng các tính năng nâng cao.

---
