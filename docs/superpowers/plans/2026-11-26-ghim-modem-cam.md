# Tách ghim · modem · cam — kế hoạch làm

**Goal:** App báo đúng sự thật khi cam nằm ở ghim khác ghim đặt modem (Tà Lài mở rộng), không đổi gì với Phú Lý / Tân Triều.
**Architecture:** Một trường `chung` trên ghim không có modem riêng + nhóm hàm trong `camlink_core.py`; mọi nơi đếm/quét/gửi hỏi qua nhóm hàm đó.
**Tech Stack:** Python lõi (Chaquopy), Kotlin màn hình, bài thử `tools/thu_*.py`, CI GitHub Actions.
**Spec:** `docs/superpowers/specs/2026-11-26-ghim-modem-cam-design.md`
**Cách chạy:** làm tại chỗ trong một phiên (anh Huan bảo "làm đi", không dùng phiên phụ).

## Global Constraints
- Test đỏ trước, code sau; không sửa bài thử cho khớp code sai. Cả bộ `sudo python3 tools/chay_test.py --du` phải xanh trước khi gộp.
- Đẩy nhánh `ghim-modem-cam` cho CI chạy trước, xanh mới gộp `main`. Đổi versionName → 2.12.19.
- App không tự đoán ghim dùng chung; không xoá dữ liệu; điểm không có ghim gắn chung thì kết quả cũ giữ nguyên.

## Review Focus
1. Ghim B trỏ về điểm A không tồn tại / A chưa cài → B "chưa cài", không lỗi.
2. A chưa quét được cam số 2 (hồ sơ chỉ 1 cam) → B chưa tính là đã cài.
3. Người dùng bấm "Không phải" → không hỏi lại.
4. Dự án không có toạ độ → gợi ý vẫn chạy (chọn ghim đầu tiên đủ điều kiện), không lỗi.
5. Bản tin LiteMark của dự án không có ghim gắn chung không đổi một byte.

## Task 1 — bài thử đỏ `tools/thu_chungmodem.py`
- [ ] Dựng 3 dự án giả (kiểu Tà Lài 6 ghim/5 tên miền/điểm 1 hồ sơ 2 cam; kiểu Phú Lý 1 ghim 3 cam; kiểu Tân Triều 1 ghim 4 cam) trong thư mục tạm.
- [ ] Các mục: T1 gợi ý đúng cặp (A=1, B=6, cam 2) và KHÔNG tự ghi · T2 sau `dat_chung`: tom_tat → diem 6, modem 5, cam 6, ten_mien 5, tk_ddns 5, da_xong 6, hoan_thanh True · T3 Phú Lý/Tân Triều trước = sau · T4 GPS tại B: ok False + lý do có "dùng chung modem"; GPS tại A không dính "sát bên" · T5 `gan_ghim_cam` gắn `ghim`/`ten_ghim` cho cam số 2 · T6 LiteMark: cam 2 đỏ → bản tin có ghim B đỏ, ghim A nằm trong `diem_dat`; dự án không gắn chung → bản tin y nguyên · T7 các ca Review Focus 1–4.
- [ ] Chạy: phải ĐỎ (thiếu hàm). Commit.

## Task 2 — lõi `camlink_core.py`
Produces:
- `goi_y_chung(ma) -> str` JSON `[{"a","ten_a","b","ten_b","cam","m"}]`
- `dat_chung(ma, b, a, cam) -> str` ('' nếu được, câu lỗi nếu không) · `bo_chung(ma, b)` · `tu_choi_chung(ma, b)`
- `_cam_chung(da, a) -> {số cam: stt ghim}` · `gan_ghim_cam(da, kq)` (ghi `ghim`, `ten_ghim` vào từng cam của `kq["diem"]`)
- `tom_tat_du_an()` thêm khoá `"modem"`; `diem_da_cai`, `diem_gan`, `tu_dong_xet` theo spec.
- [ ] Viết → chạy `python3 tools/thu_chungmodem.py` tới T5 xanh. Commit.

## Task 3 — kiểm tra từ xa + LiteMark
- `camlink_tuxa.kiem_du_an`: bỏ ghim gắn chung khỏi danh sách "chưa có tên miền"; trước khi lưu lịch sử gọi gắn ghim cho cam (hàm thuần trong tuxa: `gan_ghim(da, ds_diem)`; core.gan_ghim_cam gọi lại nó).
- `camlink_litemark.gui_canh_bao`: tách theo ghim khi cam có `ghim`.
- [ ] T6 xanh, cả `thu_chungmodem.py` xanh. Commit.

## Task 4 — màn hình Kotlin
- `MainActivity.dongDuAn`: dùng `modem`; chữ "n định vị · c cam · m modem"; các dòng Tên miền / User-pass tính trên modem.
- Trang Dự án: gọi `goi_y_chung(ma)` cho từng dự án, mỗi gợi ý hỏi MỘT hộp: "Đúng" → `dat_chung`, "Không phải" → `tu_choi_chung`; vẽ lại.
- `GiamSatActivity`, `TuXaActivity`: nhãn cam thêm tên ghim khi có `ten_ghim`.
- [ ] Không thử được trên máy này (không có bộ dựng Android) → CI biên dịch; ghi rõ "chưa xem trên điện thoại".

## Task 5 — ra bản
- [ ] `sudo python3 tools/chay_test.py --du` xanh đủ → đẩy nhánh → CI xanh → gộp main → CI build `CamLink-2.12.19.apk`.
- [ ] Thêm 1 dòng BÀI HỌC vào CLAUDE.md; thêm mục vào bảng `thu_hoiquy.py`; cập nhật sổ CamLink.
