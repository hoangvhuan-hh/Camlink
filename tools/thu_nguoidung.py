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
cam = lambda so, muc, dom="": {"so": so, "http": 8079 + so, "muc": muc, "nhan": "", "sua": [], "anh_url": f"http://{dom}:{8079 + so}/anh.jpg" if muc == "xanh" and dom else ""}
# Tân Triều: 49 ghim từ LiteMark, CHƯA cài, chưa có tên miền
tt = tao("Cam an ninh tân triều 2", {"kho_ddns": [], "diem": {str(i): {"ten": f"Ghim {i}", "domain": "", "so": 2 if i <= 36 else 1} for i in range(1, 50)},
                                     "toa_do": {str(i): [11.0 + i * 0.01, 107.0] for i in range(1, 50)}, "da_xong": {}, "ho_so": {}})
# Phú Lý: 11 điểm, 23 cam (điểm 8 có 3 cam), đã cài hết, file Excel (không từ LiteMark); điểm 6 đang lỗi
pl_d = {str(i): {"ten": f"Cột {i}", "domain": f"pl{i}.ddns.net", "u": "u", "p": "p", "so": 3 if i == 8 else 2} for i in range(1, 12)}
pl = tao("Camera Xa Phu Ly", {"diem": pl_d, "toa_do": {str(i): [12.0 + i * 0.01, 108.0] for i in range(1, 12)}, "da_xong": {str(i): "x" for i in range(1, 12)},
                              "ho_so": {str(i): hs(3 if i == 8 else 2) for i in range(1, 12)}})
with open(T._f_lich_su(G, pl), "w") as fh:
    json.dump({"luc": "15:33 26/11/2026", "diem": [{"stt": str(i), "ten": f"Cột {i}", "domain": f"pl{i}.ddns.net", "muc": "do" if i == 6 else "xanh", "tong": "0/2 cam đạt" if i == 6 else "ĐẠT",
               "cam": [cam(n + 1, "do" if i == 6 else "xanh", f"pl{i}.ddns.net") for n in range(3 if i == 8 else 2)]} for i in range(1, 12)]}, fh)
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
# ---- mục Hồ sơ hệ thống camera hiện tại (một dòng trong tab Thêm)
hs_ = json.loads(K.ho_so_ds())
kt("N9: mục Hồ sơ hệ thống camera hiện tại chỉ có Phú Lý + Tà Lài (đã cài); Tân Triều chưa cài không hiện; mỗi dòng có file sẵn, không cần bấm tạo",
   sorted(x["ten"] for x in hs_) == ["Camera Xa Phu Ly", "Dự án cam an ninh Tà Lài mở rộng"] and all(x["tep"] and os.path.exists(x["tep"]) for x in hs_))
x = next(x for x in hs_ if x["ten"] == "Camera Xa Phu Ly")
kt("N10: dòng Phú Lý nói đúng sự thật: 21/23 cam đạt (điểm 6 đang rớt) — khớp Trang chủ", (x["dat"], x["cam"]) == (21, 23) and tq["dat"] - 0 >= 21)
# ---- 2.12.22: mở hồ sơ ra, người cầm file (không có LiteMark, không có CamLink) phải vào xem được từng cam
import camlink_hoso as H
for ten_da in ("Camera Xa Phu Ly", "Dự án cam an ninh Tà Lài mở rộng"):
    mh = H.du_lieu(K.GOC, next(x["ma"] for x in hs_ if x["ten"] == ten_da))
    cams = [c for d in mh["diem"] for c in d["cam"]]
    print(f"   {ten_da}: {len(cams)} cam trong hồ sơ, ví dụ: {cams[0]['link']}")
    c0 = cams[0]
    print(f"      cạnh mã của cam đầu: QR → {c0['qr']} | User: {c0['user']} | Mật khẩu: {c0['pass']}")
    kt(f"N11 ({ten_da}) — 2.14.4: QR dùng ĐÚNG tài khoản admin khách cấp; cam đang lên → QR ra ảnh lúc quét, cam chưa có ảnh → QR mở trang cam; "
       "mọi link là http; app KHÔNG tạo tài khoản nào (không có xemhoso); không còn trang trung gian / lời mời tải app / LiteMark; không có thứ gì ngoài cam (modem, DDNS)",
       all(c["link"].startswith("http://") and c["qr"].startswith("http://") for c in cams if c["link"]) and all(c["link"] for d in mh["diem"] if d["domain"] for c in d["cam"])
       and all((c["qr"].endswith("/anh.jpg") and c["user"] == "admin") if c["qr_anh"] else (c["qr"] == c["link"] and c["user"] == "admin") for c in cams if c["link"])
       and not any(x in json.dumps(mh).lower().replace("https://www.google.com/maps/", "") for x in ("litemark", "https://", "xem.html", ".apk", "rtsp://", "xemhoso"))
       and all("qr" not in d for d in mh["diem"]))
    co_td = [d for d in mh["diem"] if d["toa_do"]]
    print(f"      chỉ đường: {len(co_td)}/{len(mh['diem'])} điểm có link, ví dụ: {co_td[0]['chi_duong'] if co_td else '(dự án chưa có toạ độ)'}")
    kt(f"N11b ({ten_da}): điểm nào có toạ độ thì có link chỉ đường Google Maps, điểm không có toạ độ thì không hiện dòng chỉ đường",
       all(d["chi_duong"].startswith("https://www.google.com/maps/dir/") for d in co_td) and all(d["chi_duong"] == "" for d in mh["diem"] if not d["toa_do"]))
# ---- 2.14.4: sau lượt kiểm, app KHÔNG để lại tài khoản nào trên cam; hồ sơ gửi ra ngoài chỉ nhắc lại tài khoản admin khách đã cấp
mh = H.du_lieu(K.GOC, pl); cams = [c for d in mh["diem"] for c in d["cam"]]; chuoi_pl = json.dumps(mh, ensure_ascii=False)
print(f"   Phú Lý: QR cam đầu → {cams[0]['qr']} | User: {cams[0]['user']} | Mật khẩu: {cams[0]['pass']}")
kt("N13: app không tạo tài khoản nào trên cam (không có sổ xem_<mã>.json, không có tên xemhoso trong hồ sơ)",
   not os.path.exists(os.path.join(G, "ketqua", f"xem_{pl}.json")) and "xemhoso" not in chuoi_pl)
kt("N13b: 21 cam đang lên → QR ra ảnh lúc quét bằng tài khoản admin khách cấp (admin/x@1); 2 cam rớt ở điểm 6 → QR mở trang cam, vẫn in tài khoản admin",
   sum(1 for c in cams if c["qr"].startswith("http://admin:x%401@") and c["qr_anh"]) == 21
   and [(c["qr"], c["user"], c["pass"]) for d in mh["diem"] if d["stt"] == "6" for c in d["cam"]] == [("http://pl6.ddns.net:8080/", "admin", "x@1"), ("http://pl6.ddns.net:8081/", "admin", "x@1")])
# ---- 2.13.0: trên máy anh Huan Phú Lý cài TAY (chưa có cửa vào modem). Bấm Sửa từ xa ở điểm mất luật mở port → màn báo cáo hiện gì?
import camlink_tuxa as T
kq_gia = {"du_an": "Camera Xa Phu Ly", "diem": [{"stt": "6", "ten": "Cột 6", "domain": "pl6.ddns.net", "muc": "vang", "tong": "1/2 cam đạt", "viec": [], "cam": [
    {"so": 1, "http": 8080, "rtsp": 554, "muc": "xanh", "nhan": "Đạt", "nguyen_nhan": "", "viec": [], "sua": []},
    {"so": 2, "http": 8081, "rtsp": 5541, "muc": "vang", "nhan": "Không thấy cam / thiếu NAT", "nguyen_nhan": "Modem có mạng nhưng từ chối port 8081", "viec": ["Không vào được web modem: ra điểm chạy lại CamLink."], "sua": ["them_nat"]}]}]}
quet_lai = []
goc_kiem = T.kiem_du_an; T.kiem_du_an = lambda *a, **k: quet_lai.append(1) or goc_kiem(*a, **k)
bc = T.sua_tat_ca(K.GOC, K._doc_du_an(pl), pl, kq_gia, C.doc_cai_dat(), log=lambda s: None)["bao_cao_sua"]
T.kiem_du_an = goc_kiem
for b in bc:
    print("   BÁO CÁO SỬA:", b["diem"], "·", b["cam"], "·", b["ket_qua"]); [print("      →", g) for g in b["giai_phap"]]
chu = json.dumps(bc, ensure_ascii=False)
kt("N12: điểm cài tay chưa có cửa modem → báo cáo nói thật 'chưa có cửa vào modem từ xa' + 'Ai xử lý: Cần người tại điểm'; không còn câu 'chờ mẫu modem'; app không quét lại vô ích",
   len(bc) == 1 and bc[0]["ket_qua"] == "CHƯA" and bc[0]["giai_phap"][0] == "Ai xử lý: Cần người tại điểm" and "chưa có cửa vào modem từ xa" in chu and "chờ mẫu" not in chu and quet_lai == [])
print(f"\n✓ đi thử như người dùng: {dat}/{dat} đạt")
