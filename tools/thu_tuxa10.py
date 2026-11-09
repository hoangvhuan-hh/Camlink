import os, sys, json, shutil, time
os.environ["CAMLINK_THU_NOI_BO"] = "1"
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import gialap_onvif as S, camlink_tuxa as T
G = "/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/pl10"; shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
cd = {"cam_user": "admin", "cam_pw": "Abc@12345"}
def cam(ip, h, r):
    c = S.Cam(ip, isapi=False, stt=1); c.http, c.rtsp = h, r; c.gw, c.dns = "192.168.1.1", "8.8.8.8"; c.model = "OR-IPC-B4"; c.mac = "78:CE:A5:%02X:%02X:%02X" % (int(ip.split(".")[3]), h // 256, h % 256); S.bat(c); return c
c4a = cam("127.0.4.4", 8080, 554); cam("127.0.4.4", 8081, 5541)
cam("127.0.4.8", 8081, 5541)                                  # điểm 8: cam 1 hỏng
diem = {"4": {"ten": "Bình Chánh 761", "domain": "pl4.ddns.net", "so": 2, "bs": 0, "u": "", "p": ""},
        "8": {"ten": "Lý Lịch 2 BC", "domain": "pl8.ddns.net", "so": 2, "bs": 0, "u": "", "p": ""}}
da = {"ten": "PL", "diem": diem}
r1 = T.kiem_du_an(G, da, "pl", cd, log=lambda s: None, tu_sua=False)
assert r1["che_do"] == "day_du" and r1["dat"] == 3
t0 = time.time(); logs = []
r2 = T.kiem_du_an(G, da, "pl", cd, log=logs.append, tu_sua=False, nhanh=True)
assert r2["che_do"] == "nhanh" and r2["so_tai_su_dung"] == 1 and r2["so_quet_lai"] == 1, (r2["che_do"], r2["so_tai_su_dung"])
p4 = [p for p in r2["diem"] if p["stt"] == "4"][0]
assert p4["tu_lich_su"] and all(c["muc"] == "xanh" and c["tu_lich_su"] for c in p4["cam"]) and r2["dat"] == 3
print("1 ✓ nhanh: điểm 4 lấy từ lịch sử, chỉ quét điểm 8 ·", round(time.time() - t0, 1), "giây ·", logs[0][:90])
# cam 1 điểm 4 hỏng sau đó → live không lên → kiểm điểm lẻ phải thấy và ghi vào lịch sử
S.tat(c4a) if hasattr(S, "tat") else None
import camlink_core as K
K.GOC = G; K._doc_du_an = lambda ma: da
p = json.loads(K.tuxa_kiem_diem("pl", "4", None))
assert p["cam"][0]["muc"] != "xanh"
ls = json.load(open(T._f_lich_su(G, "pl"), encoding="utf-8"))
assert [c["muc"] for x in ls["diem"] if x["stt"] == "4" for c in x["cam"]][0] != "xanh"
r3 = T.kiem_du_an(G, da, "pl", cd, log=lambda s: None, tu_sua=False, nhanh=True)
assert r3["so_tai_su_dung"] == 0, "điểm 4 đã có sự cố thì lần nhanh sau phải quét lại"
print("2 ✓ cam lịch sử hỏng → kiểm điểm lẻ phát hiện, lịch sử cập nhật, lần nhanh sau quét lại điểm đó")
S.tat_het()
