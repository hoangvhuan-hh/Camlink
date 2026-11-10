import sys, os, shutil, time, subprocess, json
os.environ["CAMLINK_THU_NOI_BO"] = "1"
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import gialap_onvif as S, camlink_theodoi as T
G = "/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/td2"; shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
T.khoi_tao(G); T.NHIP = 1; T.ANH_MOI = 2
def cam(ip, h, r):
    c = S.Cam(ip, isapi=False, stt=1); c.http, c.rtsp = h, r; c.gw, c.dns = "192.168.1.1", "8.8.8.8"; c.model = "OR-IPC"; c.mac = f"78:CE:A5:00:{h-8000:02X}:01"; S.bat(c); return c
cam("127.0.4.2", 8080, 554); cam("127.0.4.2", 8081, 5541)
p = {"stt": "2", "ten": "Chùa Pháp Bảo", "domain": "pl2.ddns.net", "cam": [{"so": 1, "http": 8080, "live": "rtsp://admin:Abc@12345@pl2.ddns.net:554/"}, {"so": 2, "http": 8081}]}
tid = T.bat("pl", p, 1, 0.6, {"cam_user": "admin", "cam_pw": "Abc@12345"})
bd = time.time(); chan = False
while True:
    r = T.vong()
    el = time.time() - bd
    if 8 < el and not chan:
        subprocess.run("iptables -I INPUT -p tcp -d 127.0.4.2 --dport 8080 -j DROP", shell=True); chan = True
    if el > 20 and chan:
        subprocess.run("iptables -D INPUT -p tcp -d 127.0.4.2 --dport 8080 -j DROP", shell=True); chan = None
    if r["xong_moi"]: break
    time.sleep(0.5)
m = T._doc(T._thu_muc(tid, "meta.json")); sk = T._doc(T._thu_muc(tid, "su_kien.json"))
mau = [json.loads(x) for x in open(T._thu_muc(tid, "mau.jsonl"))]
print("số lần đo:", len(mau), "| trạng thái cam:", sorted({x["cam"] for x in mau}), "| rtsp:", sorted({x.get("rtsp") for x in mau if x.get("rtsp")}), "| IP:", {x["ip"] for x in mau})
print("sự kiện:", [(x["loai"], round(x["dur"]), x.get("ti_le_ban_len")) for x in sk], "| PDF:", os.path.basename(m.get("pdf", "")), m.get("loi_pdf", ""))
assert len(sk) == 1 and sk[0]["loai"] in ("cam_mat_ket_noi",) and sk[0]["ti_le_ban_len"] == 1.0 and m["pdf"]
assert "ok" in {x.get("rtsp") for x in mau}
print("✓ đo thật: cam 1 bị chặn, cam 2 vẫn lên → 1 lần rớt 'lỗi riêng cam này'; RTSP đọc được; PDF ra")
S.tat_het()
