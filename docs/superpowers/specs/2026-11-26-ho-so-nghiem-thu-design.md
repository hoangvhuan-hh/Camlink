# Hồ sơ nghiệm thu tự động, có bằng chứng (anh Huan chốt 26/11/2026 22:25)

## Vì sao
Nhà thầu nào cũng phải nghiệm thu mới được thanh toán; hiện chụp màn hình từng cam rồi dán vào Word. App đã có sẵn bằng chứng
(ảnh chụp qua tên miền bằng 4G, toạ độ ghim, bảng thông số) — chỉ thiếu việc ghép thành hồ sơ. Đứng trên phần app đã chạy thật (kiểm tra từ xa),
không phụ thuộc phần tự cài.

## Anh Huan chốt thêm
- Phải nằm trong MỘT mục "Hồ sơ" — không thêm gì lên Trang chủ, giao diện không rối.
- Cam lên thì hệ thống TỰ chụp, TỰ xuất hồ sơ — người dùng không phải bấm tạo.

## Đạt khi
1. Kiểu Phú Lý (11 điểm, 23 cam) ra MỘT file PDF: 1 trang tổng + 11 trang điểm, mở được trên điện thoại.
2. Mỗi cam có ảnh thật kèm giờ chụp; cam không lên ghi rõ "CHƯA ĐẠT" + lý do — không bỏ trống, không làm đẹp số.
3. Số liệu trang tổng khớp màn Dự án (định vị · cam · modem).
4. Mật khẩu cam / modem / DDNS không xuất hiện trong hồ sơ.
5. Tự động: sau mỗi lượt kiểm tra từ xa và sau khi cài xong một điểm, hồ sơ của dự án tự cập nhật; mở mục Hồ sơ là có sẵn.
6. Mục Hồ sơ chỉ liệt kê dự án đã cài cam (Tân Triều chưa cài không hiện).
7. Anh Huan mở file thật ra xem rồi mới tính là xong.

## Các cách đã cân nhắc
- A. Nút "Xuất hồ sơ" ở từng màn: thêm nút ở nhiều nơi, phải nhớ bấm → trái ý "tự xuất, không rối".
- B (chọn). Một mô-đun `camlink_hoso.py`: `du_lieu()` (thuần, kiểm được) → `ve_pdf()`. Lõi tự gọi sau lượt kiểm tra từ xa / sau bằng chứng lúc cài.
  Màn hình chỉ thêm MỘT dòng "Hồ sơ nghiệm thu" trong tab Thêm → danh sách dự án đã cài → Mở / Gửi file.

## Thiết kế
- Nguồn: kết quả kiểm tra từ xa đã lưu (ưu tiên, mới nhất) + bằng chứng lúc cài của từng điểm (`sodo_<ma>_<stt>.json`) cho điểm chưa có trong lượt kiểm.
- Trang theo GHIM: cam nằm ở ghim khác ghim đặt modem (Tà Lài) hiện ở trang của ghim nó.
- Không in: mật khẩu, user DDNS, đường RTSP (có kèm mật khẩu). Có in: tên miền, port, số cam, toạ độ, giờ chụp.
- QR mỗi điểm: trang ghim trên LiteMark nếu dự án đã nối LiteMark; chưa nối thì trang web của cam 1 (`http://tên-miền:port`, khách tự đăng nhập bằng tài khoản xem của họ).
- Tệp: `ketqua/HoSo_NghiemThu_<ma>.pdf` (ghi đè bản mới nhất).
- API lõi: `ho_so_tu_dong(ma)` (không ném lỗi), `ho_so_ds()` JSON, `ho_so_tao(ma)` → đường dẫn.
