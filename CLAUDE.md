# CamLink — quy tắc làm việc cho Claude

App Android cài và kiểm tra camera cho bên thi công (VINA LITE). Lõi Python ở `app/src/main/python/camlink_*.py`,
màn hình Kotlin ở `app/src/main/java/vn/vinalite/camlink/`, bài thử ở `tools/thu_*.py`.
Mọi nội dung trả cho anh Huan: 100% tiếng Việt, ngắn, mở đầu bằng bằng chứng.

## QUY TẮC BẮT BUỘC

Lý do: từ 08/11 đến 25/11/2026 kho này ra 61 bản trong 18 ngày vì giao bản chưa thử tới nơi. Không lặp lại.

1. **Hỏi "đạt khi…" trước khi làm việc mới.** Nêu cách hiểu + tiêu chí đạt kiểm được, chờ anh Huan chốt rồi mới code.
   Thứ gì tự tra được (code, tài liệu hãng, dữ liệu cũ) thì tự tra, không hỏi.
2. **Test trước, code sau.** Không viết code sản phẩm khi chưa có bài thử đang ĐỎ cho đúng việc đó.
   Chạy bài thử để thấy nó đỏ, rồi mới sửa cho xanh. Không sửa bài thử cho khớp với code sai.
3. **Lỗi đã sửa phải có bài thử giữ lại.** Thêm mục vào `tools/thu_hoiquy.py` (hoặc bài thử riêng) và ghi vào bảng đầu file đó.
4. **Không build, không phát hành khi bộ test chưa xanh đủ.** Lệnh: `sudo python3 tools/chay_test.py --du`.
   CI (`.github/workflows/build.yml`) tự chạy lệnh này trước; đỏ thì không ra APK. Không được gỡ hay nới bước này.
5. **Không báo "xong" khi chưa có bằng chứng.** Chạy lại lệnh kiểm ngay trước khi báo và dán dòng KẾT QUẢ thật.
   Phần nào chưa thử trên thiết bị thật thì nói rõ là chưa thử trên thiết bị thật.
6. **Gỡ lỗi tận gốc.** Tái hiện → tìm nguyên nhân gốc → một giả thuyết → sửa tại gốc → chạy lại cả bộ.
   Thủ công chạy được mà app tự động không chạy thì lỗi nằm ở code app, mở code ra kiểm, không đổ cho bên ngoài.
7. **Mỗi việc để lại một bài học.** Cuối việc, thêm đúng một dòng vào mục BÀI HỌC bên dưới.
8. **Code xong phải ĐI THỬ NHƯ NGƯỜI DÙNG trước khi phát hành.** Dựng dữ liệu giống máy anh Huan (Tân Triều chưa cài · Phú Lý đã xong · Tà Lài mở rộng),
   in ra đúng những gì từng màn hình sẽ hiện rồi soát: (a) thứ KHÔNG đủ điều kiện có bị hiện ra không (nút, dự án, câu hỏi);
   (b) có thêm thứ anh Huan KHÔNG yêu cầu làm màn hình rối hơn không — có thì bỏ. Giữ thành mục trong `tools/thu_nguoidung.py`.
   Code đúng mà logic sai / gây rối thì vẫn là hỏng: app để phục vụ người dùng, không phải để họ phải nghĩ thay nó.

Quy trình chi tiết: bộ skill Superpowers trong `.claude/skills/` (brainstorming → writing-plans → test-driven-development →
systematic-debugging → verification-before-completion). Dùng chúng cho mọi việc code trong kho này.

## Chạy bài thử

```
pip install requests openpyxl rsa pillow reportlab==4.2.5 cryptography
sudo python3 tools/chay_test.py --du      # đủ mọi bài (cần root: cam giả ở 127.0.4.x + iptables giả mất mạng)
python3 tools/chay_test.py --nhanh        # bỏ 4 bài cần mạng giả
python3 tools/chay_test.py thu_hoiquy     # một bài
```

- `tools/gialap_onvif.py`: cam giả lập ONVIF + RTSP dùng chung cho các bài thử.
- Bài thử mới: đặt tên `tools/thu_<ten>.py`, tự thoát mã khác 0 khi hỏng, không dùng đường dẫn cứng (dùng `tempfile`).
- Bài thử KHÔNG được gọi ra tên miền hay IP thật của công trình: mọi lời gọi mạng phải vào cam giả hoặc được thay bằng hàm giả.

## Phát hành

- Đẩy lên `main` → CI chạy test → xanh mới build → ghi đè APK ở nhánh `apk` (link tải của người dùng).
- Nhánh khác: CI chỉ chạy test, không build.
- Đổi `versionName` trong `app/build.gradle.kts` khi có thay đổi người dùng thấy được; tên file gửi anh Huan phải kèm số phiên bản.

## BÀI HỌC

- 26/11/2026 — 24/24 bài thử cũ không chạy được ở đâu ngoài phiên đã viết ra chúng (đường dẫn cứng, thiếu cam giả, thiếu thư viện),
  nên không bài nào canh cho 61 bản đã ra. Bài thử chỉ có giá trị khi CI chạy nó ở mỗi lần đẩy.
- 26/11/2026 — Lỗi gửi cảnh báo trống 0/0 lên LiteMark được ghi nhận từ 11/11 nhưng vẫn còn nguyên ở bản 2.12.18:
  lỗi đã biết mà không có bài thử thì sẽ nằm đó. Ghi lỗi nào là viết bài thử đỏ cho lỗi đó ngay.
- 26/11/2026 — `thu_theodoi4` xanh trên máy không có Internet nhưng đỏ trên CI: nó còn gọi ONVIF ra một IP thật rồi chờ hết giờ.
  Bài thử phải chạy thử trên CI (đẩy nhánh trước) rồi mới gộp `main`; "xanh trên máy mình" chưa phải bằng chứng.
- 26/11/2026 — Code đếm mọi thứ theo ghim vì ngầm coi "1 ghim = 1 modem = 1 tên miền"; Tà Lài mở rộng (1 modem, 2 cam, 2 ghim cách 100 m)
  làm lộ ra. Trước khi viết chỗ đếm / quét nào, dựng dữ liệu giả cho ĐỦ các kiểu công trình thật (Tà Lài, Phú Lý 3 cam một ghim, Tân Triều 4 cam).
- 26/11/2026 — Trang chủ báo "1 điểm lỗi" nhưng bấm vào lại hỏi chọn dự án: màn hình đã có dữ liệu mà không truyền sang bước sau.
  Thứ app đã biết thì không hỏi lại người dùng — mỗi con số hiện ra phải bấm được tới đúng thứ nó đếm.
- 26/11/2026 — 2.12.19 qua đủ 26 bài thử nhưng đi thử như người dùng mới lộ: nút "Ghim dùng chung modem" hiện cả ở Tân Triều (chưa có modem nào),
  và trên máy anh Huan app không tự hỏi vì Tà Lài cài tay (app chưa thấy 2 cam). Bài thử từng hàm không thay được việc soát cả màn hình.
- 26/11/2026 — Hồ sơ nghiệm thu: tách `du_lieu()` (thuần, bài thử soát được từng con số, soát không lộ mật khẩu) khỏi `ve_pdf()`, rồi dựng ảnh
  từng trang PDF ra NHÌN bằng mắt trước khi giao (lộ ngay cột "Cam" bị xuống dòng). Thứ để người đọc thì phải mở ra xem, bài thử không thấy bố cục.
- 26/11/2026 — Đặt tên "Hồ sơ nghiệm thu" là bó nó vào một thời điểm; anh Huan đổi thành "Hồ sơ hệ thống camera hiện tại" vì file tự cập nhật, dùng lúc nào cũng đúng.
  Đặt tên theo thứ nó LÀ (trạng thái hiện tại), không theo một dịp dùng nó.
- 26/11/2026 — QR hồ sơ trỏ sang LiteMark: người không dùng LiteMark quét ra không xem được gì; anh Huan đổi thành QR từng cam = link http kèm user/mật khẩu cam.
  Thứ đưa cho người ngoài (file, QR, link) phải dùng được mà KHÔNG cần cài app nào của mình; và mức bảo mật theo giai đoạn do anh Huan quyết, không tự siết.
- 27/11/2026 — "Sửa từ xa" có sẵn 2 việc trên modem nhưng danh sách việc-được-chạy không chứa chúng → chưa từng chạy lần nào, và tôi còn đề xuất "nhờ người tại điểm" cho app sửa TỪ XA.
  Tính năng nào cũng phải có bài thử đi TRỌN đường (hỏng thật → bấm nút → hết hỏng) trên thiết bị giả có tác dụng thật; và đề xuất phải đứng ở vai người dùng của app (thợ ở xa), không phải vai người viết code.
- 27/11/2026 — Tôi tự cho QR mở link ẢNH chụp ("vào thẳng, khỏi đăng nhập") và in cả user/mật khẩu ra chữ: anh Huan cần QR mở trang XEM TRỰC TIẾP (ảnh không chứng minh cam đang chạy),
  còn tài khoản đã nằm trong QR thì không in ra. Đừng đổi thứ người dùng yêu cầu ("xem cam") thành thứ dễ làm hơn ("xem ảnh"); thông tin của bên khác giao thì chỉ dùng, không phô ra.
- 27/11/2026 — Hồ sơ có toạ độ nhưng không có đường đi: bên nhận không dùng LiteMark là "mù đường". Mỗi thông tin in ra phải kèm cách DÙNG nó ngay
  (toạ độ → link chỉ đường bấm được, cam → QR xem trực tiếp); và hồ sơ gửi ra ngoài phải mang tên app làm ra nó.
