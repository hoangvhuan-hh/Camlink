# Backtest máy trạng thái + phân loại + PDF bằng 24 giờ mẫu giả lập (nhịp 30 giây) có đủ các kiểu rớt
import sys, os, json, shutil, time
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import camlink_theodoi as T
G = "/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/td"; shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
T.khoi_tao(G)
from PIL import Image, ImageDraw
anh_mau = G + "/mau.jpg"
im = Image.new("RGB", (640, 360), (90, 110, 90)); ImageDraw.Draw(im).rectangle((0, 250, 640, 360), fill=(70, 70, 70)); im.save(anh_mau)
T._chup = lambda m, ten: (shutil.copy(anh_mau, T._thu_muc(m["id"], ten)) and T._thu_muc(m["id"], ten))
p = {"stt": "2", "ten": "Ngã ba chùa Pháp Bảo", "domain": "phuly-chuaphapbao.ddns.net", "du_an": "Camera Xa Phu Ly",
     "cam": [{"so": 1, "http": 8080, "live": "rtsp://admin:x@phuly-chuaphapbao.ddns.net:554/snl/live/1/1"}, {"so": 2, "http": 8081}]}
tid = T.bat("pl", p, 1, 24 * 60, {"cam_user": "admin", "cam_pw": "x"})
m = T._doc(T._thu_muc(tid, "meta.json"))
t0 = time.mktime(time.strptime("2026-11-08 00:00", "%Y-%m-%d %H:%M"))
m["bat_dau"], m["het"] = t0, t0 + 86400
H = lambda hm: t0 + int(hm[:2]) * 3600 + int(hm[3:]) * 60
# (bắt đầu, giây, cam1, cam2, ip, net)
kich_ban = [("03:00", 600, "x", "x", "A", False),          # điện thoại mất mạng → không tính
            ("05:00", 30, "im", "mo", "A", True),           # 1 lần đo lẻ → không tính
            ("08:10", 90, "im", "mo", "A", True),           # cam khởi động lại
            ("12:00", 360, "im", "im", "A", True),          # cả điểm
            ("18:20", 120, "im", "mo", "A", True), ("18:45", 120, "im", "mo", "A", True), ("18:55", 90, "im", "mo", "A", True),
            ("20:00", 240, "im", "im", "B", True),          # modem đổi IP
            ("22:00", 900, "im", "mo", "B", True),          # cam mất kết nối lâu
            ("23:50", 1200, "im", "mo", "B", True)]         # rớt tới hết giờ theo dõi
ip_hien = "113.166.223.36"
IP = {"A": "113.166.223.36", "B": "14.231.10.77"}
for i in range(2880):
    t = t0 + i * 30
    s = {"t": t, "net": True, "ip": ip_hien, "cam": "mo", "ms": 180 + (i % 7) * 20, "ban": {"8081": "mo"}}
    for bd, dur, c1, c2, ipk, net in kich_ban:
        if H(bd) <= t < H(bd) + dur:
            s["net"] = net
            if net:
                s["cam"] = "im_lang"; s["ban"] = {"8081": "mo" if c2 == "mo" else "im_lang"}; s["ms"] = 0
            ip_hien = IP[ipk] if ipk == "B" and c1 == "im" and c2 == "im" else ip_hien
            s["ip"] = ip_hien if not (c1 == "im" and c2 == "im" and ipk == "B") else IP["A"]
    if s["net"] and s["cam"] == "mo" and i % 4 == 0:
        s["rtsp"] = "loi_0" if i in (400, 404, 1200) else "ok"
    if t >= H("20:04"): s["ip"] = s["ip"] if s["cam"] != "mo" else IP["B"]
    T._xu_ly_mau(m, s)
m["het"] = t0 + 86400
T._ket_thuc(m)
a = T.phan_tich(tid)
for x in a["su_kien"]: print(f"  #{x['n']} {T._gio(x['bd'])} {T._thoi_luong(x['dur'])} → {x['loai']}")
print("nhóm:", [(g["loai"], g["so"]) for g in a["nhom"]], "| lên", a["len_pt"], "% | không đo", a["khong_do"], "s")
k = [x["loai"] for x in a["su_kien"]]
assert k == ["cam_khoi_dong_lai", "ca_diem", "cam_khoi_dong_lai", "cam_khoi_dong_lai", "cam_khoi_dong_lai", "modem_doi_ip", "cam_mat_ket_noi", "cam_mat_ket_noi"], k
assert a["khong_do"] == 600 and a["video_loi"] == 3
m = T._doc(T._thu_muc(tid, "meta.json"))
print("PDF:", m.get("pdf"), m.get("loi_pdf", ""))
