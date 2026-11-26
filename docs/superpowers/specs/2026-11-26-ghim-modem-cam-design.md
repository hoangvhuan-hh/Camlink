# Tách GHIM · MODEM · CAM — thiết kế ngắn (anh Huan chốt 26/11/2026 21:00)

## Vì sao
Màn Dự án báo Tà Lài mở rộng "Thiếu tên miền 1/6 · đã cài 5/6 · 5 cam" trong khi sự thật là 6 định vị, 6 cam, 5 modem, đã cài đủ.
Gốc: code coi **1 ghim = 1 modem = 1 tên miền**. Sai đúng một kiểu công trình: cam nằm ở ghim KHÁC ghim đặt modem.

Ba kiểu công trình thật phải đúng cả ba:
- Tà Lài mở rộng: 1 modem, 2 cam, 2 ghim cách nhau gần 100 m.
- Phú Lý: 1 ghim 2 cam, có ghim 3 cam, cùng toạ độ.
- Tân Triều: có ghim 4 cam.

## Mục tiêu (đạt khi)
1. Tà Lài: "6 định vị · 6 cam · 5 modem", đã cài 6/6, tự xuống nhóm Hoàn thành, không còn "Thiếu tên miền".
2. Phú Lý, Tân Triều: số liệu không đổi.
3. Đứng ở ghim dùng chung: app báo "dùng chung modem điểm A", không đòi tên miền; đứng ở điểm A không bị chặn vì "có điểm khác sát bên".
4. Giám sát + Kiểm tra từ xa: cam thứ 2 mang tên ghim B.
5. Cam thứ 2 lỗi → LiteMark tô đỏ đúng ghim B (không phải ghim A).
6. Bài thử đỏ trước cho cả 3 kiểu, sửa xong xanh, cả bộ vẫn xanh.

Không làm (ngoài phạm vi lần này): file Excel báo cáo vẫn đếm theo điểm; không đổi cách cài tại chỗ (modem vẫn tối đa 6 cam theo bảng port).
Tuyệt đối không: app tự đoán ghim nào dùng chung. Chỉ ghi nhận khi người dùng xác nhận.

## Các cách đã cân nhắc
- A. Gộp ghim B vào điểm A (xoá B): mất vị trí thật của cam thứ 2 trên bản đồ, LiteMark không còn ghim để báo lỗi → loại.
- B. Coi B là một điểm riêng có cùng tên miền với A: hai điểm cùng tên miền làm lượt cài/kiểm tra quét trùng, đếm 2 modem → loại.
- C (chọn). Giữ nguyên ghim B, ghi trên B: `chung = {"stt": "<A>", "cam": [2]}` = "ghim này không có modem riêng; cam của nó là cam số 2 trên modem điểm A". Mọi chỗ đếm/quét hỏi qua một nhóm hàm chung.

## Thiết kế
- Dữ liệu: `da["diem"][B]["chung"] = {"stt": A, "cam": [số cam trên modem A]}`; từ chối gợi ý: `da["diem"][B]["chung_khong"] = True`.
- Gợi ý (không tự ghi): điểm A có số cam cài thật (hồ sơ lúc cài) > số cam theo kế hoạch (file/ghim, 0 coi là 1) VÀ có ghim B chưa có tên miền, chưa cài, chưa gắn chung, chưa bị từ chối → đề xuất ghim B gần A nhất, cam số = kế hoạch + 1. Người dùng bấm "Đúng" mới ghi.
- Đếm: định vị = số ghim; modem = số ghim không gắn chung; tên miền / user-pass DDNS tính trên modem; cam = tổng cam của các modem (modem A tính cả cam của ghim gắn chung); ghim gắn chung "đã cài" khi điểm A đã cài và hồ sơ của A có cam mang số đó.
- GPS: ghim gắn chung không bao giờ là điểm để tự cài, không tính là "điểm khác sát bên"; đứng tại đó → lý do "dùng chung modem điểm A (cam số n)".
- Kiểm tra từ xa: ghim gắn chung không quét riêng, không báo "chưa có tên miền"; cam của điểm A mang thêm `ghim`, `ten_ghim` khi thuộc ghim khác.
- LiteMark: điểm có cam thuộc ghim khác thì tách bản tin theo ghim (mỗi ghim chỉ mang cam của mình, mức = mức xấu nhất của các cam đó). Điểm không có ghim gắn chung: bản tin giữ nguyên từng byte.
- Màn hình: dòng dự án "n định vị · c cam · m modem" (chỉ thêm "m modem" khi m ≠ n); "Thiếu tên miền" tính trên modem; hộp hỏi xác nhận một lần khi mở trang Dự án; ô cam ở Giám sát / Kiểm tra từ xa thêm tên ghim.
