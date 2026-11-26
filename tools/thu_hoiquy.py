# Bài thử HỒI QUY — mỗi lỗi đã từng lọt ra bản phát hành có ít nhất một mục giữ ở đây, để không tái phát.
# Lỗi mới sửa xong thì THÊM mục vào file này (hoặc bài thử riêng) trước khi phát hành. Chạy: python3 tools/thu_hoiquy.py
#
# Bảng 10 lỗi cũ (ghi nhận tới 26/11/2026) và nơi canh:
#   1  PIN Quản trị nhập số nào cũng vào ........................ HQ1 (file này)
#   2  Gửi cảnh báo trống 0/0 lên LiteMark ...................... HQ2 (file này)
#   3  Nút Thu mẫu thiết bị không chạy .......................... HQ3 (file này)
#   4  Tên miền không phân giải → lượt kiểm dừng/không nói rõ ... HQ4 (file này)
#   5  Cam UNV (trang Accept + mật khẩu mạnh) chưa hỗ trợ ....... thu_caitron.py (L1, L3, L4)
#   6  Không báo tiến trình % khi cài ........................... thu_caitron.py (L1: % tiến độ)
#   7  Chọn tên miền xong lại quay về hộp thoại chọn (vòng lặp) . HQ7 (file này)
#   8  Tên miền còn trỏ IP cũ mà báo nhầm "modem chặn" .......... HQ8 (file này)
#   9  Chỉ thử 1 mật khẩu rồi ngưng ............................. HQ9 (file này) + thu_caitron.py (L3, L4) + thu_modem.py
#   10 Bấm cài khi chưa có tên miền thì cài mù .................. HQ10 (file này) + thu_tenmien.py
#   11 Cam nằm ở ghim khác ghim đặt modem → báo "thiếu tên miền" . thu_chungmodem.py (Tà Lài 6 định vị · 6 cam · 5 modem)
import os, sys, json, shutil, tempfile, time, socket
os.environ["CAMLINK_THU_NOI_BO"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
G = os.path.join(tempfile.gettempdir(), "camlink_thu", "hoiquy"); shutil.rmtree(G, True); os.makedirs(G + "/ketqua")

import camlink_core as K, camlink_dt as C, camlink_quantri as Q, camlink_litemark as L, camlink_modem as M, camlink_tuxa as T
K.khoi_tao(G)

dat = 0
def kt(ten, dk):
    global dat
    assert dk, "HỎNG: " + ten
    dat += 1; print("✓", ten)


# ---------------------------------------------------------------- HQ1: PIN Quản trị
Q.tao_tai_khoan("4826", "may-chu", "Máy chủ")
kt("HQ1a: PIN sai bị từ chối", Q.kiem_pin("0000") != "")
kt("HQ1b: PIN trống bị từ chối", Q.kiem_pin("") != "")
kt("HQ1c: PIN đúng vào được", Q.kiem_pin("4826") == "")
for _ in range(Q.SAI_TOI_DA):
    Q.kiem_pin("1111")
kt("HQ1d: sai đủ số lần → khoá, kể cả khi sau đó nhập đúng", Q.kiem_pin("4826") != "")
Q._ghi("mo_khoa.json", {"sai": 0, "khoa_den": 0})
kt("HQ1e: hết khoá thì PIN đúng vào lại được", Q.kiem_pin("4826") == "")

# ---------------------------------------------------------------- HQ2: cảnh báo trống 0/0 lên LiteMark
da_gui = []
L.lien_ket = lambda ma: {"id": "ct-thu", "ten": "Công trình thử"}
L._goi = lambda duong, than=None: (da_gui.append((duong, than)), {"ok": True})[1]
r = L.goi_canh_bao("hq", {"dat": 0, "tong_cam": 0, "diem": []}, "thu", log=lambda s: None)
kt("HQ2a: chưa kiểm cam nào (0/0) → KHÔNG gửi lên LiteMark", not da_gui and not r)
kt("HQ2b: bản trống không nằm lại trong hàng đợi gửi bù", not os.path.exists(L._f("cho_hq.json")))
kq1 = {"dat": 1, "tong_cam": 2, "diem": [
    {"stt": "1", "ten": "Cột 1", "muc": "xanh", "tong": "ĐẠT", "cam": []},
    {"stt": "2", "ten": "Cột 2", "muc": "do", "tong": "0/1 cam đạt", "domain": "x.ddns.net",
     "cam": [{"so": 1, "http": 8080, "muc": "do", "nhan": "Mất kết nối", "nguyen_nhan": "thử", "viec": ["a"]}]}]}
L.goi_canh_bao("hq", kq1, "thu", log=lambda s: None)
kt("HQ2c: có cam đã kiểm → gửi đúng 1 lần, đúng tổng 1/2", len(da_gui) == 1 and da_gui[0][1]["tong"] == {"dat": 1, "tong": 2})
kt("HQ2d: bản gửi chỉ mang điểm lỗi + danh sách điểm đạt", [d["stt"] for d in da_gui[0][1]["diem"]] == ["2"] and da_gui[0][1]["diem_dat"] == ["1"])

# ---------------------------------------------------------------- HQ3: nút Thu mẫu thiết bị
nk = []
_quet, _ip_may = C.quet, C.ip_may
C.quet = lambda mang, bo=None: []
C.ip_may = lambda: "192.168.1.50"
try:
    ra = K.thu_mau("192.168.1.50", "192.168.1.1", nk.append)
finally:
    C.quet, C.ip_may = _quet, _ip_may
kt("HQ3a: bấm Thu mẫu chạy được tới cùng (không văng lỗi), mạng trống → trả rỗng", ra == "")
kt("HQ3b: mạng không có thiết bị → báo rõ cho người dùng, không im lặng", any("Không thấy thiết bị" in s for s in nk))

# ---------------------------------------------------------------- HQ4: tên miền không phân giải được
nk4 = []
r4 = T.kiem_du_an(G, {"ten": "HQ", "diem": {"5": {"ten": "Bến phà 5", "domain": "ten-mien-khong-ton-tai-camlink.invalid", "so": 1, "bs": 0, "u": "", "p": ""}}},
                  "hq4", {"cam_user": "admin", "cam_pw": "x"}, log=nk4.append, tu_sua=False)
p5 = r4["diem"][0]
van = json.dumps(p5, ensure_ascii=False)
kt("HQ4a: lượt kiểm chạy tới cùng, điểm bị đánh dấu ĐỎ (không dừng giữa chừng)", p5["muc"] == "do")
kt("HQ4b: nói rõ nguyên nhân 'không phân giải được'", "không phân giải" in van)
kt("HQ4c: chỉ việc tiếp theo là kiểm tên miền trên No-IP", "No-IP" in van or "noip" in van.lower())
kt("HQ4d: không tính là cam đạt", r4["dat"] == 0)

# ---------------------------------------------------------------- HQ7: chọn tên miền không lặp lại
K._ghi_du_an("hq7", {"ten": "HQ7", "toa_do": {}, "diem": {
    "1": {"ten": "Cột 1", "domain": "", "u": "", "p": "", "so": 1, "bs": 0, "map": ""},
    "2": {"ten": "Cột 2", "domain": "", "u": "", "p": "", "so": 1, "bs": 0, "map": ""}},
    "kho_ddns": [{"no": "1", "ten": "hq 01", "domain": "hq-01.ddns.net", "u": "u1", "p": "p1", "so": 0, "bs": 0},
                 {"no": "2", "ten": "hq 02", "domain": "hq-02.ddns.net", "u": "u2", "p": "p2", "so": 0, "bs": 0}]})
kt("HQ7a: điểm chưa có tên miền + có kho → phải cho chọn", K.can_chon_ten_mien("hq7", "1"))
dom = K.gan_ten_mien("hq7", "1", 0)
kt("HQ7b: chọn xong thì điểm mang đúng tên miền đã chọn", dom == "hq-01.ddns.net" and K.ten_mien_diem("hq7", "1") == "hq-01.ddns.net")
kt("HQ7c: chọn xong KHÔNG hỏi chọn lại (hết vòng lặp) → đi tiếp vào cài", not K.can_chon_ten_mien("hq7", "1"))
tat_ca = json.loads(K.tat_ca_ten_mien("hq7", "2"))
kt("HQ7d: tên miền đã dùng được đánh dấu đang ở điểm 1, điểm 2 không lấy trùng",
   [x["giu"] for x in tat_ca] == ["1", ""] and K.can_chon_ten_mien("hq7", "2"))

# ---------------------------------------------------------------- HQ8: tên miền trỏ IP cũ ≠ modem chặn
K._ghi_du_an("hq8", {"ten": "HQ8", "toa_do": {}, "kho_ddns": [], "diem": {
    "1": {"ten": "Cột 1", "domain": "hq8.ddns.net", "u": "u", "p": "p", "so": 1, "bs": 0, "map": ""}}})
C.KQ_CUOI = {"stt": "1", "ten": "Cột 1", "domain": "hq8.ddns.net", "wan": "113.0.0.9",
             "cam": [{"so": 1, "ip": "192.168.1.200", "http": 8080, "rtsp": 554, "model": "", "mac": "", "ok": True, "ghi": ""}]}
_ghbn, _sleep, _time = socket.gethostbyname, time.sleep, time.time
gio = [_time()]
socket.gethostbyname = lambda h: "14.0.0.1" if h == "hq8.ddns.net" else _ghbn(h)      # tên miền còn trỏ IP cũ
time.sleep = lambda s: gio.__setitem__(0, gio[0] + s)                                   # tua nhanh 3 phút chờ
time.time = lambda: gio[0]
nk8 = []
try:
    kq8 = json.loads(K.bang_chung("hq8", "1", nk8.append))
finally:
    socket.gethostbyname, time.sleep, time.time = _ghbn, _sleep, _time
c8 = kq8["cam"][0]
kt("HQ8a: tên miền trỏ IP cũ → ghi nhận 'tên miền chưa trỏ', không tính xem được từ ngoài", kq8["ten_mien_chua_tro"] and not c8["ngoai"])
kt("HQ8b: lý do nói rõ KHÔNG phải do modem chặn", "KHÔNG phải do modem chặn" in c8["loi_ngoai"])
kt("HQ8c: có chờ tên miền cập nhật rồi mới kết luận (không kết luận vội)", any("chờ tên miền cập nhật" in s for s in nk8))

# ---------------------------------------------------------------- HQ9: thử đủ 2 mật khẩu, không đoán thêm
ds = M._chum("admin", "MatKhauHeThong@1", [], [("admin", "admin")])
kt("HQ9a: thử mật khẩu đã lưu TRƯỚC, rồi tới mật khẩu xuất xưởng được cấp", [(u, p) for u, p, _ in ds] == [("admin", "MatKhauHeThong@1"), ("admin", "admin")])
kt("HQ9b: không được cấp mật khẩu xuất xưởng → chỉ thử đúng 1 mật khẩu, không đoán mò", len(M._chum("admin", "MatKhauHeThong@1", [], None)) == 1)
kt("HQ9c: hai mật khẩu trùng nhau → chỉ thử 1 lần (không phí lượt, tránh khoá thiết bị)", len(M._chum("admin", "admin", [], [("admin", "admin")])) == 1)
kt("HQ9d: mật khẩu trống bị bỏ qua", len(M._chum("admin", "", [], [("admin", "admin")])) == 1)

# ---------------------------------------------------------------- HQ10: không cài mù khi chưa có tên miền
K._ghi_du_an("hq10", {"ten": "HQ10", "toa_do": {}, "kho_ddns": [], "diem": {
    "1": {"ten": "Cột 1", "domain": "", "u": "", "p": "", "so": 2, "bs": 0, "map": ""}}})
kt("HQ10a: điểm chưa có tên miền được nhận ra (rỗng)", K.ten_mien_diem("hq10", "1") == "")
kt("HQ10b: tên miền nhập sai dạng bị từ chối, không lưu bừa", K.dat_ten_mien_tay("hq10", "1", "abc xyz") != "" and K.ten_mien_diem("hq10", "1") == "")
kt("HQ10c: nhập đúng thì lưu và điểm sẵn sàng cài", K.dat_ten_mien_tay("hq10", "1", "hq10-01.ddns.net", "u", "p") == "" and K.ten_mien_diem("hq10", "1") == "hq10-01.ddns.net")

print(f"\n✓ HỒI QUY: {dat}/{dat} mục đạt — 10 lỗi cũ đều có nơi canh (xem bảng đầu file)")
