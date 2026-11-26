# Bấm "điểm lỗi" ở Trang chủ → vào thẳng điểm lỗi + tự sửa từ xa (anh Huan chốt 26/11/2026 21:53)

## Vì sao
Trang chủ báo "27/29 cam · 1 điểm lỗi" nhưng bấm vào lại bật hộp "Chọn dự án để kiểm tra", liệt kê cả Tân Triều chưa cài cam nào.
App đã biết điểm nào lỗi (kết quả kiểm gần nhất) mà còn hỏi lại → sai. Gốc: thẻ trạng thái gọi mở màn Kiểm tra từ xa không kèm dự án / điểm.

## Đạt khi
1. Trang chủ báo 1 điểm lỗi: bấm thẻ → vào thẳng thẻ điểm lỗi, không qua hộp chọn dự án.
2. App tự chạy sửa từ xa cho điểm đó và báo kết quả: đã sửa xong, hoặc chưa kèm lý do (lỗi không sửa từ xa được thì không bấm bừa, báo nguyên nhân + việc cần làm).
3. Từ 2 điểm lỗi: hiện danh sách ĐIỂM LỖI (kèm tên dự án), bấm là vào đúng điểm.
4. Không có điểm lỗi: bấm thẻ → mở dự án vừa kiểm gần nhất.
5. Dự án chưa cài cam nào không xuất hiện trong hộp chọn dự án kiểm tra.
6. Bài thử đỏ trước; cả bộ vẫn xanh.

## Các cách đã cân nhắc
- A. Chỉ lọc hộp chọn dự án: vẫn phải bấm thêm 2 lần mới tới điểm lỗi → không đúng ý "nhảy luôn".
- B (chọn). Lõi trả danh sách điểm lỗi từ kết quả đã lưu; màn hình đi thẳng theo danh sách đó, dùng lại đường "ma + toi_diem" đã có của màn Kiểm tra từ xa, thêm cờ `tu_sua` để quét lại xong thì tự sửa đúng điểm đó bằng chính hàm "Sửa tất cả" (giới hạn một điểm).

## Thiết kế
- `camlink_core.diem_loi_tat_ca() -> JSON [{ma, du_an, stt, ten, muc, tong, luc}]` — đọc file lịch sử từng dự án, không chạm mạng; đỏ trước vàng; số phần tử = `tong_quan()["diem_loi"]`.
- `camlink_core.tong_quan()` thêm `gan_nhat_ma`.
- `camlink_core.ds_du_an_kiem()` — như `ds_du_an()` nhưng chỉ dự án có ít nhất một điểm đã cài (`diem_da_cai`).
- `camlink_tuxa.sua_tat_ca(..., chi_diem=None)` + `camlink_core.tuxa_sua_diem(ma, json_kq, stt, log)` — sửa đúng một điểm, báo cáo như "Sửa tất cả".
- Kotlin: thẻ trạng thái → `moDiemLoi()`; `TuXaActivity` nhận `tu_sua`: quét xong, điểm còn lỗi thì tự sửa và mở báo cáo; điểm đã lên lại thì báo "đã lên lại, không cần sửa". Hộp chọn dự án dùng `ds_du_an_kiem`.
- Kế hoạch: test đỏ `tools/thu_diemloi.py` → lõi → màn hình (CI biên dịch) → cả bộ xanh → đẩy nhánh → CI xanh → gộp main → 2.12.20.
