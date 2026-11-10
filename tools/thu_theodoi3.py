# 1.9.2: video làm chuẩn — web còn nhưng video ngắt = rớt; hỏng 1 lần = chập chờn ngắn; 401 không tính; ghi lần ngắt từ màn xem
import sys, os, shutil, time
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import camlink_theodoi as T
G = "/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/td3"; shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
T.khoi_tao(G)
T._chup = lambda m, ten: None
p = {"stt": "2", "ten": "Ngã ba chùa Pháp Bảo", "domain": "phuly-chuaphapbao.ddns.net", "du_an": "Camera Xa Phu Ly",
     "cam": [{"so": 1, "http": 8080, "live": "rtsp://admin:x@phuly-chuaphapbao.ddns.net:554/snl/live/1/1"}, {"so": 2, "http": 8081}]}
tid = T.bat("pl", p, 1, 120, {"cam_user": "admin", "cam_pw": "x"})
m = T._doc(T._thu_muc(tid, "meta.json"))
t0 = time.mktime(time.strptime("2026-11-09 10:00", "%Y-%m-%d %H:%M")); m["bat_dau"], m["het"] = t0, t0 + 7200
def mau(i, cam="mo", rtsp="ok"):
    return {"t": t0 + i * 30, "net": True, "ip": "113.166.223.36", "cam": cam, "ms": 200 if cam == "mo" else 0, "ban": {"8081": "mo"}, "rtsp": rtsp if cam == "mo" else None}
k = {}
for i in range(240):
    if 20 <= i < 26: s = mau(i, rtsp="loi_0")          # 3 phút web còn, video ngắt → RỚT video_ngat
    elif i == 40: s = mau(i, rtsp="loi_0")             # video ngắt 1 lần → chập chờn ngắn
    elif i == 60: s = mau(i, cam="im_lang")            # mất hẳn 1 lần → chập chờn ngắn
    elif 80 <= i < 90: s = mau(i, rtsp="xac_thuc")     # 401 → không tính rớt
    elif 120 <= i < 124: s = mau(i, cam="im_lang")     # mất hẳn 2 phút → rớt (cam khác vẫn lên)
    else: s = mau(i)
    T._xu_ly_mau(m, s)
T._ghi(T._thu_muc(tid, "meta.json"), m)
# màn xem báo ngắt lúc 10:10:05 và lên lại 10:13:10 (IP thay cho tên miền cũng phải khớp)
assert T.ghi_live("113.166.223.36", 554, t0 + 605, 0)
assert T.ghi_live("phuly-chuaphapbao.ddns.net", 554, t0 + 605, t0 + 790)
assert not T.ghi_live("phuly-chuaphapbao.ddns.net", 5541, t0 + 605, 0)   # cam khác port → không ghi
m = T._doc(T._thu_muc(tid, "meta.json"))
T._ket_thuc(m)
a = T.phan_tich(tid)
for x in a["su_kien"]: print(f"  #{x['n']} {T._gio(x['bd'])} {T._thoi_luong(x['dur'])} → {x['loai']}")
print("chập chờn:", [(T._gio(x['t']), x['kieu']) for x in a["chap_chon"]], "| live:", a["live"], "| 401:", a["rtsp_xac_thuc"])
print("kết luận:", a["ket_luan"])
assert [x["loai"] for x in a["su_kien"]] == ["video_ngat", "cam_khoi_dong_lai"], [x["loai"] for x in a["su_kien"]]
assert abs(a["su_kien"][0]["bd"] - (t0 + 600)) < 1          # giờ rớt = lần hỏng ĐẦU TIÊN (khớp màn xem 10:10)
assert [x["kieu"] for x in a["chap_chon"]] == ["video", "mat"]
assert a["rtsp_xac_thuc"] == 10 and len(a["live"]) == 1 and a["live"][0]["len"] == t0 + 790
m = T._doc(T._thu_muc(tid, "meta.json")); print("PDF:", m.get("pdf"), m.get("loi_pdf", ""))
assert m.get("pdf")
print("✓ 1.9.2 theo dõi lấy video làm chuẩn")
