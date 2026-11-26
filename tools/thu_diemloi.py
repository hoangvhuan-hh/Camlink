# 2.12.20 — Bấm "điểm lỗi" ở Trang chủ phải vào THẲNG điểm lỗi và sửa từ xa, không hỏi lại dự án (anh Huan 26/11/2026).
# Thiết kế: docs/superpowers/specs/2026-11-26-diem-loi-vao-thang-design.md. Chạy: python3 tools/thu_diemloi.py
import os, sys, json, shutil, tempfile
os.environ["CAMLINK_THU_NOI_BO"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python"))
G = os.path.join(tempfile.gettempdir(), "camlink_thu", "diemloi"); shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
import camlink_core as K, camlink_dt as C, camlink_tuxa as T
K.khoi_tao(G)

dat = 0
def kt(ten, dk):
    global dat
    assert dk, "HỎNG: " + ten
    dat += 1; print("✓", ten)

def tao(ten, da):
    ma = K._ma(K._ten_tu_file(ten + ".xlsx")); da["ten"] = ten; K._ghi_du_an(ma, da); return ma

def diem(ten, dom, so=1):
    return {"ten": ten, "domain": dom, "u": "u", "p": "p", "so": so}

def cam(so, muc, sua=()):
    return {"so": so, "http": 8079 + so, "rtsp": 554, "muc": muc, "nhan": "Mất kết nối" if muc != "xanh" else "ĐẠT", "nguyen_nhan": "thử", "viec": ["Ra điểm"], "sua": list(sua)}

def lich_su(ma, luc, ds):
    with open(T._f_lich_su(G, ma), "w", encoding="utf-8") as fh:
        json.dump({"luc": luc, "diem": ds}, fh, ensure_ascii=False)

# 3 dự án như máy anh Huan: Phú Lý đã cài (1 điểm lỗi), Tà Lài đã cài (đạt hết), Tân Triều CHƯA cài cam nào
pl = tao("Camera Xa Phu Ly", {"diem": {"1": diem("Cột 1", "p1.ddns.net"), "6": diem("Ngã tư vô rừng", "p6.ddns.net", 2)}, "toa_do": {}, "da_xong": {"1": "x", "6": "x"}, "ho_so": {}})
tl = tao("Ta Lai mo rong", {"diem": {"1": diem("Điểm 1", "t1.ddns.net")}, "toa_do": {}, "da_xong": {"1": "x"}, "ho_so": {}})
tt = tao("Cam an ninh tan trieu 2", {"diem": {str(i): {"ten": f"Ghim {i}", "domain": "", "so": 0} for i in range(1, 4)}, "toa_do": {}, "da_xong": {}, "ho_so": {}})
lich_su(tl, "10:00 26/11/2026", [{"stt": "1", "ten": "Điểm 1", "domain": "t1.ddns.net", "muc": "xanh", "tong": "ĐẠT", "cam": [cam(1, "xanh")]}])
os.utime(T._f_lich_su(G, tl), (1_000_000, 1_000_000))
lich_su(pl, "15:33 26/11/2026", [
    {"stt": "1", "ten": "Cột 1", "domain": "p1.ddns.net", "muc": "xanh", "tong": "ĐẠT", "cam": [cam(1, "xanh")]},
    {"stt": "6", "ten": "Ngã tư vô rừng", "domain": "p6.ddns.net", "muc": "do", "tong": "0/2 cam đạt", "cam": [cam(1, "do", ["khoi_dong_cam"]), cam(2, "do")]}])

# ---- Đ1: danh sách điểm lỗi
dl = json.loads(K.diem_loi_tat_ca())
tq = json.loads(K.tong_quan())
kt("Đ1a: đúng 1 điểm lỗi — Phú Lý điểm 6, kèm tên dự án + tên điểm", len(dl) == 1 and (dl[0]["ma"], dl[0]["stt"]) == (pl, "6") and dl[0]["du_an"] == "Camera Xa Phu Ly" and dl[0]["ten"] == "Ngã tư vô rừng")
kt("Đ1b: số điểm lỗi khớp con số Trang chủ đang hiện", len(dl) == tq["diem_loi"] == 1)
kt("Đ1c: Trang chủ biết dự án vừa kiểm gần nhất (để mở thẳng khi không có lỗi)", tq.get("gan_nhat_ma") == pl)

# ---- Đ2: hộp chọn dự án kiểm tra không còn dự án chưa cài cam nào
ds = [r[0] for r in K.ds_du_an_kiem()]
kt("Đ2a: Tân Triều (chưa cài cam nào) KHÔNG có trong danh sách dự án để kiểm tra", tt not in ds)
kt("Đ2b: Phú Lý và Tà Lài (đã cài) vẫn có", pl in ds and tl in ds)
kt("Đ2c: danh sách dự án đầy đủ (trang Dự án) không đổi — vẫn đủ 3", len(K.ds_du_an()) == 3)

# ---- Đ3: nhiều điểm lỗi → đỏ trước vàng
lich_su(tl, "16:00 26/11/2026", [{"stt": "1", "ten": "Điểm 1", "domain": "t1.ddns.net", "muc": "vang", "tong": "1/1 cam chập chờn", "cam": [cam(1, "vang")]}])
dl = json.loads(K.diem_loi_tat_ca())
kt("Đ3: 2 điểm lỗi ở 2 dự án → liệt kê cả hai, điểm ĐỎ đứng trước điểm vàng", [(x["ma"], x["stt"], x["muc"]) for x in dl] == [(pl, "6", "do"), (tl, "1", "vang")])

# ---- Đ4: tự sửa ĐÚNG MỘT điểm (không đụng điểm khác), báo cáo từng vấn đề
da_goi = []
T.sua = lambda d, so, viec, cd, log, gw="": (da_goi.append((d["ten"], so, viec)), (True, "đã gửi lệnh"))[1]
def kiem_gia(goc, da, ma, cd, log=print, chi_diem=None, tu_sua=True, nhanh=False):
    return {"diem": [{"stt": "6", "ten": "Ngã tư vô rừng", "domain": "p6.ddns.net", "muc": "vang", "tong": "1/2 cam đạt", "cam": [cam(1, "xanh"), cam(2, "do")]}]}
T.kiem_du_an = kiem_gia
kq = {"luc": "15:33", "diem": [
    {"stt": "1", "ten": "Cột 1", "domain": "p1.ddns.net", "muc": "do", "tong": "0/1 cam đạt", "cam": [cam(1, "do", ["khoi_dong_cam"])]},
    {"stt": "6", "ten": "Ngã tư vô rừng", "domain": "p6.ddns.net", "muc": "do", "tong": "0/2 cam đạt", "cam": [cam(1, "do", ["khoi_dong_cam"]), cam(2, "do")]}]}
moi = json.loads(K.tuxa_sua_diem(pl, json.dumps(kq), "6", lambda s: None))
bc = moi["bao_cao_sua"]
kt("Đ4a: chỉ chạy lệnh sửa cho điểm 6 — điểm 1 (cũng đang lỗi) không bị đụng", da_goi == [("Ngã tư vô rừng", 1, "khoi_dong_cam")])
kt("Đ4b: báo cáo đủ 2 vấn đề của điểm 6: cam 1 HOÀN THÀNH; cam 2 CHƯA kèm nguyên nhân + việc cần làm",
   [b["ket_qua"] for b in bc] == ["HOÀN THÀNH", "CHƯA"] and all(b["diem"].startswith("6.") for b in bc) and bc[1]["nguyen_nhan"] and bc[1]["giai_phap"])
kt("Đ4c: lỗi app không có cách sửa từ xa → không chạy lệnh nào, ghi rõ", bc[1]["da_lam"] == ["App không có cách sửa từ xa cho lỗi này"])
print(f"\n✓ 2.12.20 điểm lỗi vào thẳng: {dat}/{dat} đạt")
