# ĐI THỬ NHƯ NGƯỜI DÙNG (anh Huan 26/11/2026: "code không sai nhưng sai logic, show những thứ không đủ điều kiện, làm rắc rối thứ không yêu cầu").
# Dựng đúng 3 dự án như máy anh Huan rồi kiểm NHỮNG GÌ MÀN HÌNH SẼ HIỆN: thứ không đủ điều kiện thì không được hiện.
# Chạy: python3 tools/thu_nguoidung.py
import os, sys, json, shutil, tempfile
os.environ["CAMLINK_THU_NOI_BO"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python"))
G = os.path.join(tempfile.gettempdir(), "camlink_thu", "nguoidung"); shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
import camlink_core as K, camlink_dt as C, camlink_tuxa as T
K.khoi_tao(G)
cd = C.doc_cai_dat(); cd.update(cam_user="admin", cam_pw="x@1"); C.ghi_cai_dat(cd)
def tao(ten, da):
    ma = K._ma(K._ten_tu_file(ten + ".xlsx")); da["ten"] = ten; K._ghi_du_an(ma, da); return ma
hs = lambda n: {"luc": "25/11/2026", "cam": [{"so": i + 1} for i in range(n)]}
cam = lambda so, muc: {"so": so, "http": 8079 + so, "muc": muc, "nhan": "", "sua": []}
# Tân Triều: 49 ghim từ LiteMark, CHƯA cài, chưa có tên miền
tt = tao("Cam an ninh tân triều 2", {"kho_ddns": [], "diem": {str(i): {"ten": f"Ghim {i}", "domain": "", "so": 2 if i <= 36 else 1} for i in range(1, 50)},
                                     "toa_do": {str(i): [11.0 + i * 0.01, 107.0] for i in range(1, 50)}, "da_xong": {}, "ho_so": {}})
# Phú Lý: 11 điểm, 23 cam (điểm 8 có 3 cam), đã cài hết, file Excel (không từ LiteMark); điểm 6 đang lỗi
pl_d = {str(i): {"ten": f"Cột {i}", "domain": f"pl{i}.ddns.net", "u": "u", "p": "p", "so": 3 if i == 8 else 2} for i in range(1, 12)}
pl = tao("Camera Xa Phu Ly", {"diem": pl_d, "toa_do": {str(i): [12.0 + i * 0.01, 108.0] for i in range(1, 12)}, "da_xong": {str(i): "x" for i in range(1, 12)},
                              "ho_so": {str(i): hs(3 if i == 8 else 2) for i in range(1, 12)}})
with open(T._f_lich_su(G, pl), "w") as fh:
    json.dump({"luc": "15:33 26/11/2026", "diem": [{"stt": str(i), "ten": f"Cột {i}", "domain": f"pl{i}.ddns.net", "muc": "do" if i == 6 else "xanh", "tong": "0/2 cam đạt" if i == 6 else "ĐẠT",
               "cam": [cam(n + 1, "do" if i == 6 else "xanh") for n in range(3 if i == 8 else 2)]} for i in range(1, 12)]}, fh)
# Tà Lài mở rộng: 6 ghim từ LiteMark, 5 tên miền; cài TAY nên app có thể KHÔNG có hồ sơ 2 cam ở điểm 1 (đúng như máy anh Huan đang hiện "5 cam")
def talai(co_ho_so_2cam):
    d = {str(i): {"ten": f"Điểm {i}", "domain": f"tl{i}.ddns.net", "u": "u", "p": "p", "so": 1} for i in range(1, 6)}
    d["6"] = {"ten": "Ngã 3 Tư Gia 2", "domain": "", "so": 0}
    return tao("Dự án cam an ninh Tà Lài mở rộng", {"kho_ddns": [], "diem": d, "toa_do": {"1": [13.0, 109.0], "6": [13.0009, 109.0], **{str(i): [13.0 + i * 0.02, 109.0] for i in range(2, 6)}},
               "da_xong": {str(i): "x" for i in range(1, 6)}, "ho_so": {"1": hs(2 if co_ho_so_2cam else 1), **{str(i): hs(1) for i in range(2, 6)}}})

dat = 0
def kt(ten, dk):
    global dat
    assert dk, "HỎNG: " + ten
    dat += 1; print("✓", ten)

def dong(ma):
    """Đúng những gì một dòng dự án hiện ra (theo công thức của màn Dự án)."""
    d = next(x for x in json.loads(K.tom_tat_du_an())["du_an"] if x["ma"] == ma)
    n, modem = d["diem"], d.get("modem", d["diem"]); thieu = modem - d["ten_mien"]
    return {"hoan_thanh": d["hoan_thanh"], "thieu": thieu, "dong2": f"{n} định vị · {d['cam']} cam · {modem} modem" if modem != n else f"{n} điểm · {d['cam']} cam",
            "nut_chung": bool(d.get("chon_chung")), "hoi": json.loads(K.goi_y_chung(ma))}

# ---- máy anh Huan lúc này: Tà Lài cài TAY nên app chưa có hồ sơ 2 cam ở điểm 1
tl = talai(False)
x = dong(tt)
kt("N1: Tân Triều (chưa cài, chưa có modem nào) — KHÔNG hiện nút 'Ghim dùng chung modem', không hỏi gì", not x["nut_chung"] and x["hoi"] == [] and x["dong2"] == "49 điểm · 85 cam")
x = dong(pl)
kt("N2: Phú Lý (đủ tên miền, hoàn thành) — không hiện nút ghim chung, không hỏi gì, vẫn '11 điểm · 23 cam'", x["hoan_thanh"] and not x["nut_chung"] and x["hoi"] == [] and x["dong2"] == "11 điểm · 23 cam")
x = dong(tl)
kt("N3: Tà Lài cài tay (app chưa thấy 2 cam ở điểm 1) — app KHÔNG tự hỏi (không đoán), nhưng CÓ nút chọn tay vì đủ điều kiện (có modem + có ghim trống)",
   x["hoi"] == [] and x["nut_chung"] and x["thieu"] == 1)
# ---- app đã thấy 2 cam ở điểm 1 → hỏi đúng một câu
tl = talai(True)
x = dong(tl)
kt("N4: app thấy 2 cam ở điểm 1 → hỏi đúng MỘT câu: ghim 6 chung modem điểm 1, cam 2", [(g["a"], g["b"], g["cam"]) for g in x["hoi"]] == [("1", "6", 2)])
K.dat_chung(tl, "6", "1", 2)
x = dong(tl)
kt("N5: bấm Đúng → 'Hoàn thành', '6 định vị · 6 cam · 5 modem', hết thiếu tên miền, không hỏi lại; nút chọn tay còn để gỡ khi bấm nhầm",
   x["hoan_thanh"] and x["dong2"] == "6 định vị · 6 cam · 5 modem" and x["thieu"] == 0 and x["hoi"] == [] and x["nut_chung"])
kt("N6: Tân Triều và Phú Lý không bị ảnh hưởng gì sau khi Tà Lài gắn chung", not dong(tt)["nut_chung"] and dong(pl)["dong2"] == "11 điểm · 23 cam")
# ---- Trang chủ
tq = json.loads(K.tong_quan()); dl = json.loads(K.diem_loi_tat_ca())
kt("N7: Trang chủ 1 điểm lỗi → bấm là tới thẳng Phú Lý điểm 6 (không hỏi dự án)", tq["diem_loi"] == 1 and [(d["du_an"], d["stt"]) for d in dl] == [("Camera Xa Phu Ly", "6")])
kt("N8: hộp chọn dự án kiểm tra chỉ có Phú Lý + Tà Lài; Tân Triều chưa cài không hiện", sorted(r[1] for r in K.ds_du_an_kiem()) == ["Camera Xa Phu Ly", "Dự án cam an ninh Tà Lài mở rộng"])
# ---- mục Hồ sơ nghiệm thu (một dòng trong tab Thêm)
hs_ = json.loads(K.ho_so_ds())
kt("N9: mục Hồ sơ nghiệm thu chỉ có Phú Lý + Tà Lài (đã cài); Tân Triều chưa cài không hiện; mỗi dòng có file sẵn, không cần bấm tạo",
   sorted(x["ten"] for x in hs_) == ["Camera Xa Phu Ly", "Dự án cam an ninh Tà Lài mở rộng"] and all(x["tep"] and os.path.exists(x["tep"]) for x in hs_))
x = next(x for x in hs_ if x["ten"] == "Camera Xa Phu Ly")
kt("N10: dòng Phú Lý nói đúng sự thật: 21/23 cam đạt (điểm 6 đang rớt) — khớp Trang chủ", (x["dat"], x["cam"]) == (21, 23) and tq["dat"] - 0 >= 21)
print(f"\n✓ đi thử như người dùng: {dat}/{dat} đạt")
