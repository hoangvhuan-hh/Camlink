# Mạng chập chờn: điểm 8 bị chặn (DROP) trong 12 giây đầu rồi mở lại → lượt 2 phải cứu được, không báo rớt
import os, sys, json, shutil, subprocess, threading, time
os.environ["CAMLINK_THU_NOI_BO"] = "1"
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import gialap_onvif as S, camlink_tuxa as T
G = "/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/pl9"; shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
cd = {"cam_user": "admin", "cam_pw": "Abc@12345"}
def cam(ip, h, r, model="OR-IPC-B4"):
    c = S.Cam(ip, isapi=False, stt=1); c.http, c.rtsp = h, r; c.gw, c.dns = "192.168.1.1", "8.8.8.8"; c.model = model; c.mac = "78:CE:A5:%02X:%02X:%02X" % (int(ip.split(".")[3]), h // 256, h % 256); S.bat(c); return c
cam("127.0.4.4", 8080, 554); cam("127.0.4.4", 8081, 5541)
cam("127.0.4.8", 8080, 554); cam("127.0.4.8", 8081, 5541)
diem = {"4": {"ten": "Bình Chánh 761", "domain": "pl4.ddns.net", "so": 2, "bs": 0, "u": "", "p": ""},
        "8": {"ten": "Lý Lịch 2 BC", "domain": "pl8.ddns.net", "so": 2, "bs": 0, "u": "", "p": ""}}
subprocess.run("iptables -I OUTPUT -d 127.0.4.8 -j DROP", shell=True)
threading.Timer(12, lambda: subprocess.run("iptables -D OUTPUT -d 127.0.4.8 -j DROP", shell=True)).start()
r = T.kiem_du_an(G, {"ten": "PL", "diem": diem}, "pl", cd, tu_sua=False)
for p in r["diem"]:
    print(f"[{p['stt']}] {p['tong']}")
print("không tin cậy:", r.get("khong_tin_cay") or "không", "| đạt", r["dat"], "/", r["tong_cam"])
assert r["dat"] == 4, "lượt 2 không cứu được điểm bị chặn tạm"
S.tat_het()
