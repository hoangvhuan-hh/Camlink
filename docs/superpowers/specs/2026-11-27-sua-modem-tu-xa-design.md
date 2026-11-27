# Sửa modem từ xa — thiết kế (anh Huan chốt 27/11/2026, bản 2.13.0)

## Vì sao
App làm cho THỢ tự sửa hệ thống của họ từ xa. Công trình cách hàng trăm km; "đã nhờ được người tới đó dùng CamLink thì đâu gọi là sửa từ xa".
Trước 2.13.0 Sửa từ xa chỉ đi qua cửa của CAM (5 việc: khởi động lại cam, port RTSP, port web, gateway/DNS, nhập lại DDNS). Hai việc trên MODEM
(thêm luật mở port, khởi động lại modem) không bao giờ chạy: `CHAY_DUOC` không chứa chúng, và chỉ có trình cho modem nền Broadcom.
Đúng trường hợp phải đi xa — điểm còn điện, tên miền vào được, cam không ra vì modem mất / sai luật — app lại bảo "ra điểm".

## Ràng buộc anh Huan nêu
- Giao diện GIỮ NGUYÊN: mọi thứ nằm trong lượt cài và nút "Sửa từ xa" hiện có; chỉ thêm dòng trong báo cáo.
- Không đặt thêm thiết bị trong tủ (không được phép, không kinh phí). Không "nhờ người tại điểm chạy app" — đó không phải sửa từ xa.
- Hai IP (IP WAN trên modem, IP nhìn từ ngoài): ghi lại cả hai, KHÔNG bắt trùng, không cảnh báo; DDNS bám theo IP ngoài.
- Lỗi của nhà mạng / điện lực (mất mạng, mất điện) thì nhà mạng sửa; app phải nói đúng nguyên nhân và lỗi thuộc ai.
- Mật khẩu: chỉ dùng tài khoản modem người dùng đã nhập; không đoán; modem VNPT sai 3 lần khoá 3 phút → mỗi lượt thử đúng MỘT lần.

## 7 ý đã chốt → cách làm
1. **Mở cửa vào modem lúc cài** — `camlink_dt.mo_cua_modem()`: port ngoài 8098 → trang quản trị của chính modem (đúng cổng web modem đang phục vụ).
   UPnP trước; không được thì thêm luật qua trang modem (`them_nat(..., port_trong)`). Mật khẩu modem yếu → không mở (giữ chốt cũ).
2. **Thử cửa từ ngoài ngay tại điểm** — trong `camlink_core.bang_chung()` (đoạn này Kotlin đã ép chạy qua 4G): `camlink_modem.vao_tu_xa()` đăng nhập 1 lần,
   đọc bảng mở port, đăng xuất → ghi `sua_tu_xa {duoc, ly_do}` vào kết quả + hồ sơ điểm, cập nhật dòng báo cáo cài "Sửa modem từ xa".
3. **Hai IP** — `wan_modem` (modem tự báo) và `ip_ngoai` (Internet nhìn thấy) lưu vào hồ sơ điểm; chỉ đem ra giải thích khi bước 2 không qua và hai IP lệch nhau.
4. **Nối modem vào Sửa từ xa** — `camlink_tuxa.sua_modem()` cho mọi kiểu modem app biết (VNPT AX3000, OpenWrt, Broadcom) qua `vao_tu_xa()`.
5. **Biết cam còn trên mạng hay không** — chưa có lệnh đọc danh sách thiết bị của AX3000 (chưa có mẫu). Thay bằng SOÁT bảng mở port:
   luật thiếu → thêm lại; luật trỏ sai → báo đúng luật sai; luật đúng mà cam không trả lời → "cam không còn trên mạng: mất nguồn / lỏng dây → cần người tại điểm".
6. **Điểm còn sống, cam không ra** — chẩn đoán "từ chối port", "cam im lặng" (khi điểm có cửa), "không cam nào trả lời (IP còn sống)" (khi cửa còn thông)
   đều gắn việc sửa `them_nat`; `sua_tat_ca` chạy việc đó cho từng cam rồi kiểm lại.
7. **Lỗi thuộc ai** — `ai_xu_ly()`: Nhà mạng / điện lực · Sửa từ xa được · Cần người tại điểm · Người giữ tài khoản. Hiện ở dòng đầu "Ai xử lý: …" của báo cáo sửa.

## Chưa làm được (thiếu mẫu lệnh của modem AX3000 — không đoán)
- Khởi động lại modem AX3000 từ xa; xoá luật mở port sai; đọc danh sách thiết bị đang cắm vào modem.
- Đã mở rộng "Thu mẫu thiết bị": lấy thêm mã (JS) các trang còn lại của modem (bỏ trang WAN / WiFi / tài khoản) để lần sau bổ sung 3 lệnh này.
- Ý 8 (CamLink bản máy tính chạy qua UltraViewer): chờ anh Huan quyết — không nằm được trong giao diện hiện có.

## Giới hạn nói trước
- Modem reset về xuất xưởng → cửa mất theo; mất điện / đứt cáp; nhà mạng đổi mật khẩu modem; nhà mạng cấp IP dùng chung → không vào được từ ngoài.
- Điểm cài tay (Phú Lý, Tà Lài) chưa có cửa: báo cáo nói rõ "chưa có cửa vào modem từ xa".

## Bài thử
`tools/thu_suamodem.py` (điểm giả 3 lớp: IP ngoài → modem AX3000 giả có bảng mở port CÓ TÁC DỤNG THẬT → 2 cam giả), `tools/thu_caitron.py` (L1–L4),
`tools/thu_nguoidung.py` (N12).

## Chưa thử trên thiết bị thật
Modem AX3000 có nhận luật mở port trỏ vào chính nó hay không; đăng nhập trang modem từ ngoài qua https cổng 8098; toàn bộ đường sửa trên modem thật.
