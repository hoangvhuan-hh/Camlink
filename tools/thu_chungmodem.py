# 2.12.19 — GHIM · MODEM · CAM: cam nằm ở ghim KHÁC ghim đặt modem (Tà Lài mở rộng: 1 modem, 2 cam, 2 ghim cách ~100 m).
# Ba kiểu công trình thật anh Huan nêu 26/11/2026 phải đúng cả ba:
#   Tà Lài mở rộng: 6 định vị, 6 cam, 5 modem · Phú Lý: 1 ghim 3 cam cùng toạ độ · Tân Triều: 1 ghim 4 cam.
# Thiết kế: docs/superpowers/specs/2026-11-26-ghim-modem-cam-design.md. Chạy: python3 tools/thu_chungmodem.py
import os, sys, json, shutil, tempfile, copy
os.environ["CAMLINK_THU_NOI_BO"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python"))
G = os.path.join(tempfile.gettempdir(), "camlink_thu", "chungmodem"); shutil.rmtree(G, True); os.makedirs(G + "/ketqua")

import camlink_core as K, camlink_dt as C, camlink_litemark as L
K.khoi_tao(G)
cd = C.doc_cai_dat(); cd.update(cam_user="admin", cam_pw="MatKhau@1"); C.ghi_cai_dat(cd)

dat = 0
def kt(ten, dk):
    global dat
    assert dk, "HỎNG: " + ten
    dat += 1; print("✓", ten)

def diem(ten, dom, so=0):
    return {"ten": ten, "domain": dom, "u": "u" if dom else "", "p": "p" if dom else "", "so": so}

def hs(n):
    return {"luc": "25/11/2026 11:09", "cam": [{"so": i + 1, "ip": f"192.168.1.{200 + i}"} for i in range(n)]}

def tao(ten, da):
    """Ghi dự án giả với đúng mã app tự tính từ tên; trả mã."""
    ma = K._ma(K._ten_tu_file(ten + ".xlsx"))
    da["ten"] = ten
    K._ghi_du_an(ma, da)
    return ma

def tt(ma):
    return next(x for x in json.loads(K.tom_tat_du_an())["du_an"] if x["ma"] == ma)

# ---- kiểu Tà Lài mở rộng: ghim 1 đặt modem + cam 1; ghim 6 cách ghim 1 ~100 m mang cam thứ 2 của modem đó
TL = {"kho_ddns": [],
      "diem": {"1": diem("Ngã 3 Tư Gia 1", "d1.ddns.net"), "2": diem("Điểm 2", "d2.ddns.net"), "3": diem("Điểm 3", "d3.ddns.net"),
               "4": diem("Điểm 4", "d4.ddns.net"), "5": diem("Điểm 5", "d5.ddns.net"), "6": diem("Ngã 3 Tư Gia 2", "")},
      "toa_do": {"1": [11.3000, 107.3000], "6": [11.3009, 107.3000], "2": [11.3200, 107.3000], "3": [11.3400, 107.3000],
                 "4": [11.3600, 107.3000], "5": [11.3800, 107.3000]},
      "da_xong": {k: "25/11/2026" for k in "12345"}, "ho_so": {"1": hs(2), "2": hs(1), "3": hs(1), "4": hs(1), "5": hs(1)}}
talai = tao("Ta Lai kieu", copy.deepcopy(TL))
# ---- kiểu Phú Lý (1 ghim 3 cam cùng toạ độ) và kiểu Tân Triều (1 ghim 4 cam)
phuly = tao("Phu Ly kieu", {"diem": {"1": diem("Cột 3 cam", "pl.ddns.net", 3)}, "toa_do": {"1": [12.0, 108.0]},
                       "da_xong": {"1": "x"}, "ho_so": {"1": hs(3)}})
tantrieu = tao("Tan Trieu kieu", {"diem": {"1": diem("Cột 4 cam", "tt.ddns.net", 4)}, "toa_do": {"1": [13.0, 109.0]},
                          "da_xong": {"1": "x"}, "ho_so": {"1": hs(4)}})
truoc = {m: tt(m) for m in (phuly, tantrieu)}

# ================= T1: gợi ý đúng cặp, KHÔNG tự ghi
gy = json.loads(K.goi_y_chung(talai))
kt("T1a: gợi ý đúng một cặp — ghim 6 dùng chung modem điểm 1, cam số 2", len(gy) == 1 and (gy[0]["a"], gy[0]["b"], gy[0]["cam"]) == ("1", "6", 2))
kt("T1b: gợi ý ghi khoảng cách thật giữa hai ghim (~100 m)", 80 <= gy[0]["m"] <= 120)
kt("T1c: gợi ý KHÔNG tự ghi gì vào dự án (app không tự đoán)", "chung" not in K._doc_du_an(talai)["diem"]["6"])
kt("T1d: Phú Lý / Tân Triều không có gợi ý nào", json.loads(K.goi_y_chung(phuly)) == [] and json.loads(K.goi_y_chung(tantrieu)) == [])
x = tt(talai)
kt("T1e: trước khi xác nhận, số liệu giữ như cũ (6 modem, thiếu 1 tên miền)", x["modem"] == 6 and x["ten_mien"] == 5 and not x["hoan_thanh"])

# ================= T2: người dùng xác nhận → báo đúng sự thật
kt("T2a: ghi nhận ghim 6 dùng chung modem điểm 1", K.dat_chung(talai, "6", "1", 2) == "")
x = tt(talai)
kt("T2b: 6 định vị · 6 cam · 5 modem", (x["diem"], x["cam"], x["modem"]) == (6, 6, 5))
kt("T2c: tên miền 5/5 modem, user/pass DDNS 5/5 — không còn thiếu", x["ten_mien"] == 5 and x["tk_ddns"] == 5)
kt("T2d: đã cài 6/6 và dự án là HOÀN THÀNH", x["da_xong"] == 6 and x["hoan_thanh"] is True)
kt("T2e: xác nhận rồi thì không gợi ý lại", json.loads(K.goi_y_chung(talai)) == [])

# ================= T3: Phú Lý / Tân Triều không đổi
for m in (phuly, tantrieu):
    sau = tt(m)
    kt(f"T3: {m} — số liệu cũ giữ nguyên, modem = số ghim", all(sau[k] == truoc[m][k] for k in truoc[m] if k != "modem") and sau["modem"] == sau["diem"])
kt("T3c: Phú Lý 1 ghim 3 cam · Tân Triều 1 ghim 4 cam", (tt(phuly)["cam"], tt(tantrieu)["cam"]) == (3, 4))

# ================= T4: GPS
r = json.loads(K.tu_dong_xet(11.3009, 107.3000))
kt("T4a: đứng tại ghim 6 → không tự cài, lý do nói rõ dùng chung modem điểm 1, không đòi tên miền",
   not r["ok"] and "dùng chung modem" in r["ly_do"] and "tên miền" not in r["ly_do"])
talai2 = tao("Ta Lai chua cai", {"diem": {"1": diem("A", "e1.ddns.net"), "2": diem("B", "")},
                        "toa_do": {"1": [14.0000, 110.0000], "2": [14.0009, 110.0000]}, "da_xong": {}, "ho_so": {}})
r0 = json.loads(K.tu_dong_xet(14.0000, 110.0000))
kt("T4b: (chưa gắn chung) đứng tại A bị chặn vì ghim B sát bên — đúng như cũ", not r0["ok"] and "sát bên" in r0["ly_do"])
kt("T4c: gắn chung khi A chưa cài vẫn được", K.dat_chung(talai2, "2", "1", 2) == "")
r1 = json.loads(K.tu_dong_xet(14.0000, 110.0000))
kt("T4d: gắn chung rồi → đứng tại A tự cài được (ghim B không còn là 'điểm khác sát bên')", r1["ok"] and r1["stt"] == "1")
x2 = tt(talai2)
kt("T4e: A chưa cài → ghim B cũng CHƯA cài (0/2), 1 modem, 2 cam dự kiến", x2["da_xong"] == 0 and x2["modem"] == 1 and x2["cam"] == 2)

d_a = K._doc_du_an(talai2)["diem"]["1"]
kt("T4f: điểm A được ghi đủ 2 cam để lượt kiểm tra từ xa quét cả cam của ghim B; số gốc của file vẫn giữ để đối chiếu",
   int(d_a["so"]) == 2 and d_a.get("goc", {}).get("so") == 0)

# ================= T5: kiểm tra từ xa / Giám sát — cam mang tên ghim của nó
da = K._doc_du_an(talai)
kq = {"diem": [{"stt": "1", "ten": "Ngã 3 Tư Gia 1", "cam": [{"so": 1}, {"so": 2}]}, {"stt": "2", "ten": "Điểm 2", "cam": [{"so": 1}]}]}
K.gan_ghim_cam(da, kq)
c1, c2 = kq["diem"][0]["cam"]
kt("T5a: cam số 2 của điểm 1 mang ghim 6 + tên ghim 6", c2.get("ghim") == "6" and c2.get("ten_ghim") == "Ngã 3 Tư Gia 2")
kt("T5b: cam số 1 và cam các điểm khác không bị gắn gì", "ghim" not in c1 and "ghim" not in kq["diem"][1]["cam"][0])

# ================= T6: LiteMark — cam thứ 2 lỗi thì tô đỏ đúng ghim 6
da_gui = []
L.lien_ket = lambda ma: {"id": "ct-thu", "ten": "Công trình thử"}
L._goi = lambda duong, than=None: (da_gui.append(than), {"ok": True})[1]
cam = lambda so, muc: {"so": so, "http": 8079 + so, "muc": muc, "nhan": "", "nguyen_nhan": "", "viec": []}
kq = {"dat": 5, "tong_cam": 6, "diem": [
    {"stt": "1", "ten": "Ngã 3 Tư Gia 1", "muc": "do", "tong": "1/2 cam đạt", "domain": "d1.ddns.net", "cam": [cam(1, "xanh"), cam(2, "do")]},
    {"stt": "2", "ten": "Điểm 2", "muc": "xanh", "tong": "ĐẠT", "domain": "d2.ddns.net", "cam": [cam(1, "xanh")]}]}
K.gan_ghim_cam(da, kq)
L.goi_canh_bao(talai, kq, "thu", log=lambda s: None, da=da)
b = da_gui[-1]
kt("T6a: bản tin tô đỏ ghim 6 (mang đúng cam số 2), KHÔNG tô ghim 1", [d["stt"] for d in b["diem"]] == ["6"] and [c["so"] for c in b["diem"][0]["cam"]] == [2] and b["diem"][0]["muc"] == "do")
kt("T6b: ghim 1 (cam 1 đang lên) và ghim 2 nằm trong danh sách đạt", sorted(b["diem_dat"]) == ["1", "2"])
kq["diem"][0]["cam"] = [cam(1, "do"), cam(2, "xanh")]
K.gan_ghim_cam(da, kq)
L.goi_canh_bao(talai, kq, "thu", log=lambda s: None, da=da)
b = da_gui[-1]
kt("T6c: ngược lại — cam 1 lỗi thì đỏ ghim 1, ghim 6 đạt", [d["stt"] for d in b["diem"]] == ["1"] and sorted(b["diem_dat"]) == ["2", "6"])
kq_pl = {"dat": 2, "tong_cam": 3, "diem": [{"stt": "1", "ten": "Cột 3 cam", "muc": "vang", "tong": "2/3 cam đạt", "domain": "pl.ddns.net",
                                           "cam": [cam(1, "xanh"), cam(2, "do"), cam(3, "xanh")]}]}
da_pl = K._doc_du_an(phuly)
K.gan_ghim_cam(da_pl, kq_pl)
L.goi_canh_bao(phuly, kq_pl, "thu", log=lambda s: None, da=da_pl)
b = da_gui[-1]
kt("T6d: Phú Lý (không ghim dùng chung) — bản tin như cũ: 1 điểm, đủ 3 cam, không thêm khoá lạ",
   [d["stt"] for d in b["diem"]] == ["1"] and len(b["diem"][0]["cam"]) == 3 and b["diem_dat"] == []
   and set(b["diem"][0]) == {"stt", "stt_camlink", "ten", "domain", "muc", "tong", "chua_chac_ghim", "cam"})

# ================= T7: các ca dễ vấp
kt("T7a: gắn chung về điểm không tồn tại → báo lỗi, không ghi", K.dat_chung(talai, "6", "99", 2) != "" and K._doc_du_an(talai)["diem"]["6"]["chung"]["stt"] == "1")
kt("T7b: không cho gắn ghim vào chính nó / vào một ghim cũng đang dùng chung", K.dat_chung(talai, "1", "1", 2) != "" and K.dat_chung(talai, "5", "6", 2) != "")
thieu = tao("Thieu cam", {"diem": {"1": diem("A", "f1.ddns.net"), "2": diem("B", "")}, "toa_do": {},
                       "da_xong": {"1": "x"}, "ho_so": {"1": hs(1)}})
kt("T7c: dự án không có toạ độ, điểm A chỉ quét được 1 cam → không gợi ý (không đoán)", json.loads(K.goi_y_chung(thieu)) == [])
K.dat_chung(thieu, "2", "1", 2)
x = tt(thieu)
kt("T7d: đã gắn chung nhưng điểm A mới quét được 1 cam → ghim B CHƯA tính là đã cài (1/2), chưa hoàn thành", x["da_xong"] == 1 and not x["hoan_thanh"] and x["modem"] == 1)
kt("T7e: gỡ gắn chung → trở lại như cũ (2 modem, thiếu 1 tên miền)", K.bo_chung(thieu, "2") == "" and tt(thieu)["modem"] == 2 and tt(thieu)["ten_mien"] == 1)
tuchoi = tao("Tu choi", copy.deepcopy(TL))
kt("T7f: bấm 'Không phải' → không hỏi lại", len(json.loads(K.goi_y_chung(tuchoi))) == 1 and K.tu_choi_chung(tuchoi, "6") == "" and json.loads(K.goi_y_chung(tuchoi)) == [])
print(f"\n✓ 2.12.19 ghim · modem · cam: {dat}/{dat} đạt")
