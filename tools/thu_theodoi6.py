# Tái hiện báo cáo Huan gửi 10/11 14:06: theo dõi cam 2 điểm 2 từ 10:58 → 14:05, dịch vụ đo bị dừng (chỉ 3 lượt), màn xem ghi 20 lần ngắt
import sys, os, shutil, time, json
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import camlink_theodoi as T
G = "/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/td6"; shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
T.khoi_tao(G); T._chup = lambda m, ten: ""
p = {"stt": "2", "ten": "Ngã ba chùa Pháp Bảo", "domain": "phuly-chuaphapbao.ddns.net", "du_an": "Camera Xa Phu Ly",
     "cam": [{"so": 1, "http": 8080}, {"so": 2, "http": 8081, "live": "rtsp://a:b@phuly-chuaphapbao.ddns.net:5541/snl/live/1/1"}]}
tid = T.bat("pl", p, 2, 120, {"cam_user": "a", "cam_pw": "b"})
m = T._doc(T._thu_muc(tid, "meta.json"))
d = lambda hm: time.mktime(time.strptime("2026-11-10 " + hm, "%Y-%m-%d %H:%M:%S"))
m["bat_dau"], m["het"] = d("10:58:09"), d("14:05:02")
for t in (d("10:58:20"), d("10:58:50"), d("10:59:20")):
    T._xu_ly_mau(m, {"t": t, "net": True, "ip": "113.188.130.14", "cam": "mo", "ms": 186, "ban": {"8080": "mo"}})
T._ghi(T._thu_muc(tid, "meta.json"), m)
gio = ["11:10:57", "11:39:31", "11:40:13", "11:40:53", "11:41:33", "13:11:26", "13:14:23", "13:18:44", "13:19:45", "13:20:21",
       "13:23:10", "13:30:02", "13:31:40", "13:35:11", "13:40:20", "13:44:05", "13:50:30", "13:55:12", "14:01:40", "14:04:33"]
lau = [34, 21, 20, 20, 16, 13, 11, 12, 17, 22, 25, 18, 14, 30, 12, 19, 21, 15, 16, 0]
lv = [{"ngat": d(g), **({"len": d(g) + s} if s else {})} for g, s in zip(gio, lau)]
T._ghi(T._thu_muc(tid, "live.json"), lv)
m = T._doc(T._thu_muc(tid, "meta.json")); T._ket_thuc(m)
a = T.phan_tich(tid)
print("phủ:", round(100 * a["phu"]), "% | thiếu dữ liệu:", a["thieu"], "| số lần rớt:", len(a["su_kien"]), "| kết luận:", a["ket_luan"])
assert a["thieu"] and len(a["su_kien"]) == 20 and "KHÔNG ĐỦ DỮ LIỆU" in a["ket_luan"]
print("PDF:", T._doc(T._thu_muc(tid, "meta.json"))["pdf"])
print("✓ báo cáo không còn ghi 'ổn định 100%' khi gần như không đo; 20 lần ngắt từ màn xem được tính")
