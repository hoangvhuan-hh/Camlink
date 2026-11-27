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

## Sửa 2.12.22 — QR từng cam (anh Huan quyết 26/11/2026 23:17)

- Bỏ QR chung của điểm trỏ sang LiteMark (người không dùng LiteMark không xem được).
- Mỗi cam một QR đặt cạnh ảnh cam: link **http** (không https) theo tên miền + port của cam, kèm user/mật khẩu **cam** trong link (ký tự lạ được mã hoá).
  App đã biết đường ảnh của cam (lưu lúc kiểm tra từ xa / lúc cài) thì QR mở thẳng ảnh cam; chưa biết thì mở trang cam.
- In ra chữ cạnh QR: link, user, mật khẩu cam. KHÔNG in mật khẩu modem, user/mật khẩu DDNS, đường RTSP.
- Lý do anh Huan nêu: giai đoạn cài đặt, file chia trong nhóm cài đặt; bên quản lý tiếp quản sẽ tự đổi mật khẩu.
- Chưa thử trên thiết bị thật: trình duyệt / app quét QR trên điện thoại có nhận user/mật khẩu trong link hay không (một số app quét bỏ phần này → khi đó gõ user/mật khẩu in bên cạnh).
- Bài thử: `tools/thu_hoso.py` H1g–H1n, H4e–H4f, H5; `tools/thu_tuxa10.py` (lưu đường ảnh); `tools/thu_nguoidung.py` N11.

## Sửa 2.13.1 — QR xem trực tiếp (anh Huan 27/11/2026 16:39)

- QR mỗi cam mở TRANG XEM TRỰC TIẾP của cam (http://tên miền:port/, kèm user/mật khẩu cam trong link) — không mở link ảnh chụp nữa.
- Ảnh chụp trong báo cáo vẫn giữ (bằng chứng lúc kiểm).
- KHÔNG in user / mật khẩu cam ra chữ; chỉ in link không kèm tài khoản. Dữ liệu `du_lieu()` không còn trường user / pass.
- Chưa thử trên thiết bị thật: trang cam Oryza / UNV trên trình duyệt điện thoại có tự đăng nhập bằng tài khoản trong link và có phát được hình trực tiếp hay không.

## Sửa 2.13.2 — chỉ đường + tên app (anh Huan 27/11/2026 16:51, 16:53)

- Mỗi điểm có toạ độ: dòng "Chỉ đường (Google Maps)" bấm được + in link ra chữ để copy (`https://www.google.com/maps/dir/?api=1&destination=lat,lng`).
  Ghim dùng chung modem chỉ đường tới toạ độ của chính ghim đó. Điểm chưa có toạ độ thì không hiện dòng này.
- Dòng "Báo cáo được thực hiện bằng app CamLink" dưới tên dự án ở trang đầu và ở chân mọi trang (kèm số trang).
- Link Google Maps là link https duy nhất trong hồ sơ; link cam vẫn http.

## Sửa 2.14.0 — QR mở live bằng CamLink + trang gợi ý (anh Huan chốt 27/11/2026 18:05–18:11)

Vì sao: bản 2.13.x QR mở trang web của cam kèm tài khoản trong link → cam Oryza vẫn hiện ô đăng nhập ("QR làm cái gì"). Trang web của cam đăng nhập
bằng chuỗi trao đổi mã hoá nên không link nào tự điền được; chỉ LINK VIDEO (rtsp) nhận tài khoản ngay trong link.

Anh Huan chốt:
- Dùng CamLink để xem (không dùng VLC) — "một tên bắn hai nhạn"; xem không cần bản trả phí, cài đơn giản.
- Máy chưa có CamLink: gợi ý "muốn xem live thì cài, không thì tự nhập user và mật khẩu". Lời kêu gọi phải đủ hấp dẫn để khách dùng miễn phí trước; đưa lên CH Play làm sau.
- Phương án (a): in lại user + mật khẩu cạnh mã QR trong hồ sơ.
- Mở mục Hồ sơ là ra bản mới, không phải quét lại (2.13.4 gộp vào đây).

Cách làm:
- QR = `https://hoangvhuan-hh.github.io/Camlink/xem.html#<mã cam>`; mã = base64url(JSON {v, da, t, l, wp}) nằm sau dấu # nên không gửi lên máy chủ.
  `l` là đúng link video app đang phát ở tab Giám sát. User / mật khẩu / tên miền cho lối tự nhập tách từ `l` (giữ mã ngắn, QR dễ quét).
- `web/xem.html` (trang tĩnh, tự chứa): Android → tự thử mở `camlink://xem?d=<mã>` (qua intent, có đường lui về chính trang kèm `?chua=1`);
  khối "Chưa có CamLink? Dùng miễn phí" (4 lợi ích + nút tải); lối "Không muốn cài" (user, mật khẩu có nút sao chép, nút mở trang cam). iPhone / máy tính: chỉ lối tự nhập.
  Link tải app nằm ở MỘT biến `TAI` — lên CH Play chỉ đổi một dòng, QR đã phát không phải in lại.
- App: `XemLiveActivity` nhận `camlink://xem` (exported, BROWSABLE), tự giải mã, phát bằng bộ phát sẵn có; không gọi lõi Python, không cần dự án / PIN.
- CI đưa `web/xem.html` lên nhánh `gh-pages` mỗi lần phát hành. GitHub Pages phải được BẬT một lần trong Settings của kho (API bật Pages bị chặn ở phiên này).

Chưa thử trên thiết bị thật: quét trên điện thoại (trình duyệt có cho tự mở app hay phải bấm nút "Xem live ngay"; app quét trong Zalo); hình live trong CamLink khi mở từ mã.

## Sửa 2.14.1 — sau khi anh Huan thử thật (27/11/2026 19:31)

Kết quả thử thật: Android có CamLink quét mã → xem live ĐƯỢC. iPhone (không có CamLink): (1) mật khẩu hiện `…%40`; (2) bấm "Mở trang cam" bị trắng trang
trong trình duyệt nhúng của app quét mã, trong khi trước đó quét QR http thẳng trên iPhone thì vào được trang cam; trên Android nút này chạy bình thường.
- (1) Gốc: link video app lấy từ cam (`Onvif.luong_video`) đã đổi ký tự lạ thành %xx; trang tách mật khẩu từ link mà không đổi ngược. Sửa ở cả `tach_link_video` và `web/xem.html`;
  `ma_xem` ghi thẳng user / mật khẩu thật khi tách ra không khớp.
- (2) Chưa xác định chắc nguyên nhân (trang cam Oryza nặng ~2,7 MB, tải được tiêu đề rồi trắng). Làm: trên iPhone nút "Mở trang cam" thử chuyển sang Safari
  (`x-safari-https://…/xem.html?web=1#mã` → trang tự vào thẳng trang cam), sau 1,5 giây không đi được thì mở thẳng như cũ; thêm dòng "Nếu trang cam trắng: bấm ··· rồi chọn Mở bằng Safari".
  Kiểu link `x-safari-https` không phải cách chính thức của Apple (được báo chạy trên iOS 15/17/18, không chạy iOS 16) → CHƯA thử trên iPhone thật.

## 2.14.2 — QR mở ảnh cam chụp ngay lúc quét, bằng tài khoản chỉ xem (anh Huan chốt 27/11/2026 20:40)

Lý do đổi hướng (anh Huan 20:27): người đã có CamLink thì mở app xem, không cần quét; QR là cho người cầm hồ sơ, không cài gì. Ảnh phải là ảnh chụp tại lúc quét.
- **QR** = đường ảnh của chính cam (ONVIF GetSnapshotUri, đã lưu `anh_url` từ 2.12.22) qua tên miền, `http://user:mật-khẩu@tên-miền:cổng/đường` (`camlink_hoso.link_anh`).
  Mỗi lần mở link là cam chụp và trả ảnh mới. Không qua trang trung gian, không cần app. Ảnh in trong hồ sơ giữ nguyên.
- **Tài khoản chỉ xem** (`camlink_xem.py`): trong lượt kiểm tra từ xa và lúc cài, app tự tạo trên cam tài khoản `xemhoso` mức ONVIF `User`, mật khẩu ngẫu nhiên `Xem-XXXXXXXX`,
  thử lấy ảnh bằng tài khoản đó rồi mới ghi sổ `ketqua/xem_<mã>.json`. Đã có thì giữ nguyên (QR đã in còn dùng được); bị xoá trên cam thì tạo lại đúng mật khẩu cũ.
- **Không tạo được** (cam từ chối / tài khoản mới không lấy được ảnh): QR dùng tài khoản đang có, hồ sơ in dòng đỏ "Tài khoản quản trị — cam chưa có tài khoản chỉ xem".
  Cam đang rớt và chưa có tài khoản chỉ xem: QR chỉ mở trang cam, KHÔNG in tài khoản nào.
- **Bỏ**: QR trỏ `web/xem.html`, lời mời cài app, nút tải APK (trang `xem.html` vẫn để cho mã QR của hồ sơ 2.14.0 / 2.14.1 đã phát, đã gỡ nút tải). Đồng hồ đếm ngược: không làm.
- **Để sau** (cùng đợt cấp phép): máy chủ đứng giữa cho link ngắn không chứa mật khẩu, thu hồi được.
- **CHƯA thử trên cam Oryza thật**: (1) trình duyệt điện thoại + cam có nhận tài khoản trong link ảnh không — không nhận thì máy hiện ô hỏi user / mật khẩu (đã in cạnh QR);
  (2) cam có cho tạo tài khoản mức User qua ONVIF không; (3) tài khoản mức User trên Oryza có thật sự không sửa được cấu hình không. Cam giả trong bộ thử không chứng minh được ba điều này.


## 2.14.3 — dồn hồ sơ cho ngắn (anh Huan 27/11/2026 21:48, 21:51)

"Đủ mà không thiếu, không quá dài; có điểm cả trăm cam … ảnh nhỏ hơn tí, QR nhỏ lại; 3–4 cam một trang, không cần trình bày lại, chỉ cần dồn lên."
- Trang đầu giữ nguyên; các điểm nối liền ngay sau chỗ ký (không ngắt trang sau trang đầu, không còn mỗi ghim một trang).
- Mỗi điểm: 1 dòng tên + kết quả, 1 dòng toạ độ · chỉ đường · tên miền, 1 dòng link chỉ đường in chữ. Mỗi cam một hàng: ảnh 44 mm | QR 27 mm | kết quả + giờ chụp, port web · port video · link trang cam, dòng quét mã, user · mật khẩu.
- Bỏ bảng cam riêng của từng điểm (lặp lại đúng những thứ đã nằm trên hàng cam). Điểm từ 4 cam trở xuống không bị tách sang hai trang.
- Đo: Phú Lý 11 điểm · 23 cam 12 → 5 trang; 50 điểm · 100 cam 51 → 19 trang (khoảng 5–6 cam một trang). QR 27 mm: máy đọc được 22/23 mã ở 150 dpi (QR 22 mm chỉ đọc được 2/10 nên không dùng).
- Chưa thử: quét mã 27 mm trên giấy in thật / trên màn hình điện thoại của anh Huan.
