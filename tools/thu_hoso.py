# 2.12.20 — HỒ SƠ HỆ THỐNG CAMERA HIỆN TẠI tự động, có bằng chứng (anh Huan chốt 26/11/2026). Thiết kế: docs/superpowers/specs/2026-11-26-ho-so-nghiem-thu-design.md
# Chạy: python3 tools/thu_hoso.py
import os, sys, json, shutil, tempfile, re, time
os.environ["CAMLINK_THU_NOI_BO"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python"))
G = os.path.join(tempfile.gettempdir(), "camlink_thu", "hoso"); shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
import camlink_core as K, camlink_dt as C, camlink_tuxa as T, camlink_hoso as H
from PIL import Image
K.khoi_tao(G)
cd = C.doc_cai_dat(); cd.update(cam_user="admin", cam_pw="PassCam@BiMat1", modem_user="admin", modem_pw="PassModem@BiMat2"); C.ghi_cai_dat(cd)

dat = 0
def kt(ten, dk, them=""):
    global dat
    assert dk, "HỎNG: " + ten
    dat += 1; print("✓", ten)

def tao(ten, da):
    ma = K._ma(K._ten_tu_file(ten + ".xlsx")); da["ten"] = ten; K._ghi_du_an(ma, da); return ma

def anh(ten):
    f = os.path.join(G, "ketqua", ten); Image.new("RGB", (320, 180), (40, 90, 60)).save(f, "JPEG"); return f

def cam(ma, stt, so, len_=True, dom=None):
    c = {"so": so, "http": 8079 + so, "rtsp": 554 if so == 1 else 5540 + so - 1, "muc": "xanh" if len_ else "do",
         "nhan": "ĐẠT" if len_ else "Mất kết nối", "nguyen_nhan": "" if len_ else "Cam không trả lời — nghi mất điện tại cột",
         "live": f"rtsp://admin:PassCam@BiMat1@{dom or 'pl' + str(stt) + '.ddns.net'}:{554 if so == 1 else 5540 + so - 1}/", "user": "admin", "pass": "PassCam@BiMat1", "anh": anh(f"tuxa_{ma}_{stt}_p{8079 + so}.jpg") if len_ else "",
         "anh_url": f"http://{dom or 'pl' + str(stt) + '.ddns.net'}:{8079 + so}/anh.jpg" if len_ else ""}
    return c

# ---- kiểu Phú Lý: 11 điểm, 23 cam (điểm 8 có 3 cam); điểm 6 đang rớt cả 2 cam
dd = {str(i): {"ten": f"Cột {i}", "domain": f"pl{i}.ddns.net", "u": "ddnsuser", "p": "PassDdns@BiMat3", "so": 3 if i == 8 else 2} for i in range(1, 12)}
pl = tao("Camera Xa Phu Ly", {"diem": dd, "toa_do": {str(i): [11.2 + i * 0.01, 107.4] for i in range(1, 12)}, "da_xong": {str(i): "x" for i in range(1, 12)}, "ho_so": {}})
ds = [{"stt": str(i), "ten": f"Cột {i}", "domain": f"pl{i}.ddns.net", "noip_user": "ddnsuser", "noip_pass": "PassDdns@BiMat3", "muc": "do" if i == 6 else "xanh",
       "tong": "0/2 cam đạt" if i == 6 else "ĐẠT", "cam": [cam(pl, str(i), n + 1, i != 6) for n in range(3 if i == 8 else 2)]} for i in range(1, 12)]
with open(T._f_lich_su(G, pl), "w", encoding="utf-8") as fh:
    json.dump({"luc": "15:33:10 26/11/2026", "diem": ds}, fh, ensure_ascii=False)
# sổ tài khoản CHỈ XEM (camlink_xem) — mọi cam Phú Lý đã có, TRỪ điểm 3 (cam không cho tạo)
import camlink_xem as X
XEM_PW = "Xem-Ab3dEf7h"
with open(X._f(G + "/ketqua", pl), "w", encoding="utf-8") as fh:
    json.dump({f"pl{i}.ddns.net:{8080 + n}": {"u": X.TEN, "p": XEM_PW} for i in range(1, 12) if i != 3 for n in range(3)}, fh)
tt = tao("Cam an ninh tan trieu 2", {"diem": {str(i): {"ten": f"Ghim {i}", "domain": "", "so": 0} for i in range(1, 4)}, "toa_do": {}, "da_xong": {}, "ho_so": {}})

# ================= H1: dữ liệu hồ sơ (thuần) — đúng sự thật, không làm đẹp số
m = H.du_lieu(G, pl)
kt("H1a: trang tổng khớp màn Dự án — 11 định vị · 23 cam · 11 modem", (m["tong"]["dinh_vi"], m["tong"]["cam"], m["tong"]["modem"]) == (11, 23, 11))
kt("H1b: 21/23 cam ĐẠT (điểm 6 rớt 2 cam) — không làm đẹp số", m["tong"]["dat"] == 21 and m["tong"]["chua"] == 2)
kt("H1c: đủ 11 trang điểm, đúng thứ tự 1..11", [d["stt"] for d in m["diem"]] == [str(i) for i in range(1, 12)])
d6 = next(d for d in m["diem"] if d["stt"] == "6"); d8 = next(d for d in m["diem"] if d["stt"] == "8")
kt("H1d: cam không lên ghi rõ CHƯA ĐẠT + lý do, không bỏ trống", [c["dat"] for c in d6["cam"]] == [False, False] and all("mất điện" in c["ly_do"] for c in d6["cam"]) and all(not c["anh"] for c in d6["cam"]))
kt("H1e: cam lên có ảnh thật + giờ chụp; điểm 8 đủ 3 cam", len(d8["cam"]) == 3 and all(c["dat"] and os.path.exists(c["anh"]) and c["gio"] for c in d8["cam"]))
kt("H1f: có toạ độ và tên miền, port của từng cam", d8["toa_do"] == [11.28, 107.4] and d8["domain"] == "pl8.ddns.net" and [c["http"] for c in d8["cam"]] == [8080, 8081, 8082])
chuoi = json.dumps(m, ensure_ascii=False)
chuoi_cam = chuoi.replace("https://www.google.com/maps/", "")      # link chỉ đường Google Maps (https) là thứ duy nhất được phép https
kt("H1g: KHÔNG có mật khẩu modem / DDNS, không user DDNS, không đường RTSP, không link https, không link LiteMark, không còn trang trung gian xem.html trong dữ liệu hồ sơ",
   all(x not in chuoi_cam for x in ("PassModem@BiMat2", "PassDdns@BiMat3", "ddnsuser", "rtsp://", "https://", "litemark", "xem.html", "github")))
# 2.14.2 — anh Huan chốt 27/11 20:40: QR mở thẳng ẢNH CAM CHỤP NGAY LÚC QUÉT (http, không cần app), dùng tài khoản CHỈ XEM;
# hồ sơ không còn mật khẩu quản trị; không còn chỗ tải CamLink trên đường quét. Ảnh trong báo cáo vẫn giữ.
kt("H1h: cạnh mã in tài khoản CHỈ XEM (không phải admin) + link trang cam http không kèm tài khoản",
   [(c["link"], c["user"], c["pass"], c["tk_xem"]) for c in d8["cam"]] == [(f"http://pl8.ddns.net:{p}/", "xemhoso", XEM_PW, True) for p in (8080, 8081, 8082)], d8["cam"])
kt("H1i: QR mỗi cam = đường ảnh của chính cam đó qua tên miền, http, kèm tài khoản chỉ xem → quét là cam chụp và trả ảnh ngay lúc đó",
   [c["qr"] for c in d8["cam"]] == [f"http://xemhoso:{XEM_PW}@pl8.ddns.net:{p}/anh.jpg" for p in (8080, 8081, 8082)] and all(c["qr_anh"] for c in d8["cam"]), [c["qr"] for c in d8["cam"]])
co_xem = json.dumps([d for d in m["diem"] if d["stt"] not in ("3", "6")], ensure_ascii=False)
kt("H1i2: điểm đã có tài khoản chỉ xem → KHÔNG còn mật khẩu quản trị ở bất kỳ chỗ nào của điểm đó (chữ in lẫn QR, kể cả dạng đã đổi ký tự)",
   "PassCam" not in co_xem and '"admin"' not in co_xem)
d3 = next(d for d in m["diem"] if d["stt"] == "3")
kt("H1i3: điểm 3 — cam không cho tạo tài khoản chỉ xem → QR vẫn ra ảnh bằng tài khoản đang có, và hồ sơ ĐÁNH DẤU rõ (tk_xem = False) để in cảnh báo",
   [(c["qr"], c["user"], c["tk_xem"], c["qr_anh"]) for c in d3["cam"]] == [(f"http://admin:PassCam%40BiMat1@pl3.ddns.net:{p}/anh.jpg", "admin", False, True) for p in (8080, 8081)], d3["cam"])
kt("H1j: ảnh chụp trong báo cáo VẪN có đủ cho cam đạt", all(c["anh"] and os.path.exists(c["anh"]) for c in d8["cam"]))
kt("H1k: không còn QR chung của điểm (trước trỏ sang LiteMark — người không dùng LiteMark không xem được)", all("qr" not in d and "qr_litemark" not in d for d in m["diem"]))
kt("H1l: cam đang rớt mà app vẫn nhớ tài khoản chỉ xem của nó → QR mở trang cam (chưa có ảnh để chụp), in tài khoản chỉ xem; tuyệt đối không in tài khoản quản trị",
   all(c["qr"] == c["link"] == f"http://pl6.ddns.net:{c['http']}/" and not c["qr_anh"] and (c["user"], c["pass"]) == ("xemhoso", XEM_PW) for c in d6["cam"]), d6["cam"])
import camlink_litemark as L
L.noi(pl, {"id": "ct123", "ten": "Phú Lý"})
ds[7]["cam"][0]["anh_url"] = "https://pl8.ddns.net:8080/LAPI/V1.0/Channels/0/Media/Video/Streams/0/Snapshot?a=1&b=2"
ds[2]["muc"], ds[2]["cam"][1] = "do", cam(pl, "3", 2, False)      # điểm 3 cam 2 vừa rớt: không có ảnh, không có tài khoản chỉ xem
with open(T._f_lich_su(G, pl), "w", encoding="utf-8") as fh:
    json.dump({"luc": "15:33:10 26/11/2026", "diem": ds}, fh, ensure_ascii=False)
m2 = H.du_lieu(G, pl); e8 = next(d for d in m2["diem"] if d["stt"] == "8"); e3 = next(d for d in m2["diem"] if d["stt"] == "3")
kt("H1m: dự án ĐÃ nối LiteMark thì QR vẫn là link cam, không có chữ litemark / https nào", "litemark" not in json.dumps(m2).lower() and "https://" not in json.dumps(m2).replace("https://www.google.com/maps/", ""))
kt("H1n: QR dùng ĐÚNG đường ảnh cam đã trả ở lượt kiểm (giữ nguyên phần sau dấu ?), ép về http; không có đường video nào trong hồ sơ",
   e8["cam"][0]["qr"] == f"http://xemhoso:{XEM_PW}@pl8.ddns.net:8080/LAPI/V1.0/Channels/0/Media/Video/Streams/0/Snapshot?a=1&b=2" and "rtsp://" not in json.dumps(m2) and "anh_url" not in json.dumps(m2), e8["cam"][0]["qr"])
kt("H1o: cam rớt, không có tài khoản chỉ xem → QR chỉ mở trang cam, KHÔNG in user / mật khẩu quản trị ra hồ sơ",
   (e3["cam"][1]["qr"], e3["cam"][1]["user"], e3["cam"][1]["pass"]) == ("http://pl3.ddns.net:8081/", "", "") and "PassCam" not in json.dumps(e3["cam"][1]), e3["cam"][1])
ds[2]["muc"], ds[2]["cam"][1] = "xanh", cam(pl, "3", 2)
with open(T._f_lich_su(G, pl), "w", encoding="utf-8") as fh:
    json.dump({"luc": "15:33:10 26/11/2026", "diem": ds}, fh, ensure_ascii=False)

# 2.13.2 — anh Huan 27/11 16:51: thêm CHỈ ĐƯỜNG (bên nhận không dùng LiteMark là mù đường) + dòng "thực hiện bằng app CamLink"
kt("H1p: điểm có toạ độ → có link chỉ đường Google Maps tới đúng toạ độ ghim (bấm hoặc copy là đi)",
   d8["chi_duong"] == "https://www.google.com/maps/dir/?api=1&destination=11.280000,107.400000", d8.get("chi_duong"))
kt("H1r: hồ sơ ghi rõ được thực hiện bằng app CamLink", m["thuc_hien"] == "Báo cáo được thực hiện bằng app CamLink")
# ================= H2: file PDF thật
f = K.ho_so_tao(pl)
raw = open(f, "rb").read()
so_trang = len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", raw))
kt("H2a: ra đúng MỘT file PDF, tên có mã dự án", f.endswith(".pdf") and os.path.basename(f) == f"HoSo_HeThongCamera_{pl}.pdf" and raw[:5] == b"%PDF-")
kt("H2d: tiêu đề là 'HỒ SƠ HỆ THỐNG CAMERA HIỆN TẠI' (anh Huan 26/11: hợp với mọi thời điểm, không chỉ lúc nghiệm thu) — không còn chữ 'nghiệm thu'",
   m["tieu_de"] == "HỒ SƠ HỆ THỐNG CAMERA HIỆN TẠI" and "nghiệm thu" not in json.dumps(m, ensure_ascii=False).lower())
kt(f"H2b: 1 trang tổng + 11 trang điểm = 12 trang (đếm được {so_trang})", so_trang == 12)
kt("H2c: file có nhúng ảnh thật của cam (21 ảnh)", len(re.findall(rb"/Subtype\s*/Image", raw)) >= 21)

# ================= H3: TỰ ĐỘNG — cam lên thì hồ sơ tự cập nhật, người dùng không bấm tạo
os.remove(f)
ds[5]["muc"], ds[5]["tong"], ds[5]["cam"] = "xanh", "ĐẠT", [cam(pl, "6", 1), cam(pl, "6", 2)]      # điểm 6 lên lại
with open(T._f_lich_su(G, pl), "w", encoding="utf-8") as fh:
    json.dump({"luc": "16:40:00 26/11/2026", "diem": ds}, fh, ensure_ascii=False)
K.ho_so_tu_dong(pl)
l = {x["ma"]: x for x in json.loads(K.ho_so_ds())}
kt("H3a: sau lượt kiểm, hồ sơ tự có lại và tự cập nhật: 23/23 cam đạt", os.path.exists(f) and l[pl]["dat"] == 23 and l[pl]["cam"] == 23 and l[pl]["tep"] == f)
kt("H3b: mục Hồ sơ chỉ có dự án đã cài cam — Tân Triều chưa cài KHÔNG hiện", tt not in l and list(l) == [pl])
kt("H3c: tự động không bao giờ làm hỏng lượt kiểm — dự án lạ / lỗi thì im lặng bỏ qua", K.ho_so_tu_dong("khong-co") in ("", None))
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python/camlink_core.py"), encoding="utf-8").read()
kt("H3d: lõi tự gọi xuất hồ sơ sau kiểm tra từ xa (cả dự án, một điểm) và sau bằng chứng lúc cài", src.count("ho_so_tu_dong(ma)") >= 3)

# ================= H4: kiểu Tà Lài — cam nằm ở ghim khác ghim đặt modem hiện ở trang của ghim nó; điểm mới cài (chưa kiểm từ xa) lấy bằng chứng lúc cài
tl = tao("Ta Lai mo rong", {"diem": {"1": {"ten": "Ngã 3 Tư Gia 1", "domain": "t1.ddns.net", "u": "u", "p": "p", "so": 2}, "2": {"ten": "Điểm 2", "domain": "t2.ddns.net", "u": "u", "p": "p", "so": 1},
                                     "6": {"ten": "Ngã 3 Tư Gia 2", "domain": "", "so": 0, "chung": {"stt": "1", "cam": [2]}}},
                            "toa_do": {"1": [11.3, 107.3], "6": [11.3009, 107.3]}, "da_xong": {"1": "x", "2": "x"}, "ho_so": {"1": {"cam": [{"so": 1}, {"so": 2}]}, "2": {"cam": [{"so": 1}]}}})
with open(T._f_lich_su(G, tl), "w", encoding="utf-8") as fh:
    json.dump({"luc": "11:42:00 25/11/2026", "diem": [{"stt": "1", "ten": "Ngã 3 Tư Gia 1", "domain": "t1.ddns.net", "muc": "xanh", "tong": "ĐẠT", "cam": [cam(tl, "1", 1, dom="t1.ddns.net"), cam(tl, "1", 2, dom="t1.ddns.net")]}]}, fh, ensure_ascii=False)
with open(K._file_so_do(tl, "2"), "w", encoding="utf-8") as fh:      # điểm 2 vừa cài xong, chưa có trong lượt kiểm từ xa
    json.dump({"stt": "2", "luc": "26/11/2026 09:10", "domain": "t2.ddns.net", "cam": [{"so": 1, "http": 8080, "rtsp": 554, "ok": True, "ngoai": True, "anh": anh("bc_tl_2.jpg"), "anh_url": "http://t2.ddns.net:8080/anh.jpg", "loi_ngoai": ""}]}, fh)
m = H.du_lieu(G, tl)
p = {d["stt"]: d for d in m["diem"]}
kt("H4a: Tà Lài — 3 định vị · 3 cam · 2 modem, 3/3 đạt", (m["tong"]["dinh_vi"], m["tong"]["cam"], m["tong"]["modem"], m["tong"]["dat"]) == (3, 3, 2, 3))
kt("H4b: trang ghim 1 chỉ có cam 1; cam 2 nằm ở trang ghim 6 (ghi rõ dùng modem điểm 1)", [c["so"] for c in p["1"]["cam"]] == [1] and [c["so"] for c in p["6"]["cam"]] == [2] and "điểm 1" in p["6"]["ghi_chu"])
kt("H4c: điểm 2 chưa có trong lượt kiểm từ xa → lấy bằng chứng lúc cài (ảnh + giờ)", p["2"]["cam"][0]["dat"] and os.path.exists(p["2"]["cam"][0]["anh"]) and "26/11/2026" in p["2"]["cam"][0]["gio"])
kt("H4e: cam 2 ở ghim 6 (dùng modem điểm 1) → link + QR theo tên miền điểm 1, port cam 2", p["6"]["cam"][0]["link"] == "http://t1.ddns.net:8081/" and p["6"]["cam"][0]["qr"] == "http://admin:PassCam%40BiMat1@t1.ddns.net:8081/anh.jpg", p["6"]["cam"][0]["qr"])
kt("H4g: điểm KHÔNG có toạ độ → không bịa link chỉ đường; ghim 6 có toạ độ riêng → chỉ đường tới đúng ghim 6 (không phải ghim đặt modem)",
   p["2"]["chi_duong"] == "" and p["6"]["chi_duong"].endswith("destination=11.300900,107.300000") and p["1"]["chi_duong"].endswith("destination=11.300000,107.300000"), (p["2"]["chi_duong"], p["6"]["chi_duong"]))
da_tl = K._doc_du_an(tl); da_tl["diem"]["2"]["rieng"] = {"cam_pw": "Rieng#Diem2"}; K._ghi_du_an(tl, da_tl)
p2 = {d["stt"]: d for d in H.du_lieu(G, tl)["diem"]}["2"]["cam"][0]
kt("H4f: điểm có mật khẩu cam RIÊNG, chưa có tài khoản chỉ xem → QR và chữ in dùng đúng mật khẩu riêng của điểm đó (ký tự lạ được đổi đúng chuẩn link)", p2["qr"] == "http://admin:Rieng%23Diem2@t2.ddns.net:8080/anh.jpg" and p2["pass"] == "Rieng#Diem2" and not p2["tk_xem"], p2)
f2 = K.ho_so_tao(tl)
kt("H4d: PDF Tà Lài: 1 + 3 = 4 trang", len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", open(f2, "rb").read())) == 4)
src_hs = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python/camlink_hoso.py"), encoding="utf-8").read()
kt("H5a: PDF vẽ QR cho TỪNG CAM (trong vòng lặp cam), không còn câu chữ LiteMark", "QrCodeWidget(c[\"qr\"]" in src_hs and "LiteMark" not in src_hs.split("def ve_pdf")[1])
kt("H5c: PDF in cạnh mã: 'xem ảnh cam chụp ngay lúc quét' + user + mật khẩu + link trang cam; có dòng cảnh báo khi phải dùng tài khoản quản trị; không còn lời mời cài app",
   all(x in src_hs.split("def ve_pdf")[1] for x in ("xem ảnh cam chụp ngay lúc quét", "User:", "Mật khẩu:", "Trang cam:", "chưa có tài khoản chỉ xem")) and "bằng app <font" not in src_hs.split("def ve_pdf")[1])
kt("H5b: lõi lưu đường ảnh của cam sau kiểm tra từ xa và sau bằng chứng lúc cài", "anh_url" in src and "anh_url" in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python/camlink_tuxa.py"), encoding="utf-8").read())
pdf = open(K.ho_so_tao(pl), "rb").read()
kt("H5d: trong PDF link chỉ đường BẤM ĐƯỢC (mở Google Maps) cho điểm có toạ độ", pdf.count(b"google.com/maps/dir/") >= 1, pdf.count(b"google.com/maps"))
kt("H5e: PDF in dòng 'thực hiện bằng app CamLink' ở trang đầu và chân mọi trang; link chỉ đường cũng in ra chữ để copy",
   "m[\"thuc_hien\"]" in src_hs.split("def ve_pdf")[1] and "onFirstPage" in src_hs and "onLaterPages" in src_hs and "p[\"chi_duong\"]" in src_hs.split("def ve_pdf")[1])
# 2.13.4 — anh Huan 27/11 17:50: cập nhật app xong mở Hồ sơ trên điện thoại vẫn ra bản CŨ (app chỉ tạo file khi chưa có) → mở là phải ra bản mới
import camlink_phien_ban as PB
fp = H.tep(G, pl)
open(fp, "wb").write(b"%PDF-BAN-CU do ban app truoc ve"); open(fp + ".ban", "w").write("2.12.22")      # giả: file do bản app cũ vẽ
ds_ = json.loads(K.ho_so_ds()); moi = open(fp, "rb").read()
kt("H6a: file hồ sơ do bản app CŨ vẽ → mở mục Hồ sơ là app vẽ lại bằng bản hiện tại (có link chỉ đường, không còn file cũ)",
   b"BAN-CU" not in moi and b"google.com/maps/dir/" in moi and open(fp + ".ban").read().strip() == PB.PHIEN_BAN, moi[:40])
t0 = os.path.getmtime(fp); time.sleep(1.1); K.ho_so_ds()
kt("H6b: cùng bản app, dữ liệu không đổi → mở lại KHÔNG vẽ lại (không bắt người dùng chờ vô ích)", os.path.getmtime(fp) == t0)
time.sleep(1.1); da_pl = K._doc_du_an(pl); da_pl["toa_do"]["8"] = [11.5, 107.9]; K._ghi_du_an(pl, da_pl); K.ho_so_ds()
kt("H6c: dữ liệu dự án vừa đổi (sửa toạ độ ghim 8) → mở Hồ sơ là thấy toạ độ mới, không phải chờ lượt kiểm tra từ xa", b"destination=11.500000,107.900000" in open(fp, "rb").read())
os.remove(fp + ".ban"); open(fp, "wb").write(b"%PDF-BAN-CU"); K.ho_so_ds()
kt("H6d: file cũ không có dấu phiên bản (do bản 2.13.3 trở về trước vẽ) → cũng vẽ lại", b"BAN-CU" not in open(fp, "rb").read())

# 2.13.3 — anh Huan 27/11 17:14: chữ CamLink đang bị mờ, phải nhấn cho nổi
vp = src_hs.split("def ve_pdf")[1]
kt("H5f: chữ CamLink được NHẤN (chữ đậm, màu riêng, to hơn chữ thường) ở trang đầu và ở chân trang — không in chung màu xám mờ với cả dòng",
   "MAU_APP" in src_hs and vp.count("MAU_APP") >= 2 and 'P(m["thuc_hien"], 9.5, mau=MO' not in vp and "cv.setFont(dam" in vp)
print(f"\n✓ 2.12.20 hồ sơ hệ thống camera: {dat}/{dat} đạt")
