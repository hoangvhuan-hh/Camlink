# 2.1.0 — chẩn đoán theo % khả năng, đo thật với cam giả lập: (A) cả điểm mất, cam KHÔNG khởi động lại, IP đổi → Modem/VNPT cao nhất
#                                                         (B) cả điểm mất, nhật ký cam CÓ khởi động lại → Mất điện cao nhất
import sys, os, shutil, time, subprocess, json
os.environ["CAMLINK_THU_NOI_BO"] = "1"
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import gialap_onvif as S, camlink_theodoi as T, camlink_chandoan as D
def cam(ip, h, r):
    c = S.Cam(ip, isapi=False, stt=1); c.http, c.rtsp = h, r; c.gw, c.dns = "192.168.1.1", "8.8.8.8"; c.model = "OR-IPC"; c.mac = f"78:CE:A5:00:{h-8000:02X}:01"; S.bat(c); return c
c1 = cam("127.0.4.2", 8080, 554); c2 = cam("127.0.4.2", 8081, 5541)
p = {"stt": "2", "ten": "Chùa Pháp Bảo", "domain": "pl2.ddns.net", "cam": [{"so": 1, "http": 8080, "live": "rtsp://admin:Abc@12345@pl2.ddns.net:554/"}, {"so": 2, "http": 8081, "live": "rtsp://admin:Abc@12345@pl2.ddns.net:5541/"}]}
def chay(ten, khoi_dong):
    G = f"/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/cd_{ten}"; shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
    T.khoi_tao(G); D.khoi_tao(G); T.NHIP = 1; T.ANH_MOI = 10 ** 9; T.BAO_SAU = 3; T._NK_CACHE.clear()
    c1.khoi_dong = c2.khoi_dong = []
    ip_that = {"v": "127.0.4.2"}; T._ip = lambda d: ip_that["v"]
    gid = T.bat_diem("pl", p, 0.5, {"cam_user": "admin", "cam_pw": "Abc@12345"})
    bd = time.time(); chan = False; bao = []
    while True:
        r = T.vong("wifi"); bao += r["bao"]
        el = time.time() - bd
        if 6 < el and not chan:
            for pt in (8080, 8081): subprocess.run(f"iptables -I INPUT -p tcp -d 127.0.4.2 --dport {pt} -j DROP", shell=True)
            chan = True
        if el > 16 and chan is True:
            for pt in (8080, 8081): subprocess.run(f"iptables -D INPUT -p tcp -d 127.0.4.2 --dport {pt} -j DROP", shell=True)
            chan = None
            if khoi_dong: c1.khoi_dong = c2.khoi_dong = [time.time() - 2]     # nguồn về → cả 2 cam vừa khởi động
            else: ip_that["v"] = "127.0.4.2"                                  # (IP đổi giả lập ở dưới)
        if r["xong_moi"]: break
        time.sleep(0.5)
    ms = T._cung_nhom(gid)
    sk = T._doc(T._thu_muc(ms[0]["id"], "su_kien.json"))
    a = T.phan_tich(ms[0]["id"])
    x = a["su_kien"][0]
    print(f"[{ten}] nhật ký cam: {x.get('cam_khoi_dong')} {x.get('cam_khoi_dong_luc', '')} | khả năng: {D.dong_mot_dong(x['chan_doan'])} | nút sửa: {x['chan_doan']['nut_sua']}")
    print("   báo ngay:", [(b["kieu"], b["nguyen_nhan"][:70]) for b in bao])
    print("   PDF:", ms[0].get("pdf") or T._doc(T._thu_muc(ms[0]["id"], "meta.json")).get("pdf"))
    return x
xa = chay("A_modem", False)
# A: IP đổi — ghi thẳng vào lần rớt (iptables không đổi được IP thật) rồi tính lại
xa["ip_truoc"], xa["ip_sau"] = "113.188.130.14", "123.31.122.115"
pa = D.tinh(D.tu_su_kien(xa), "pl", "sau_khi_len")
print("   + IP đổi:", D.dong_mot_dong(pa))
assert xa["cam_khoi_dong"] == "khong" and pa["kha_nang"][0]["ma"] == "modem_vnpt" and pa["nut_sua"] == "an"
xb = chay("B_mat_dien", True)
assert xb["cam_khoi_dong"] == "ca_diem" and xb["chan_doan"]["kha_nang"][0]["ma"] == "mat_dien" and xb["chan_doan"]["nut_sua"] == "an"
# không khẳng định: không nguyên nhân nào vượt 95%
assert all(k["pt"] <= 95 for k in xb["chan_doan"]["kha_nang"])
# xác nhận nguyên nhân thật → mức nền dự án thay đổi
n0 = D.nen_du_an("pl")[0]["mat_dien"]; D.xac_nhan("pl", "2:8080:test", "mat_dien"); n1 = D.nen_du_an("pl")[0]["mat_dien"]
print(f"   mức nền 'mất điện' của dự án: {n0:.2f} → {n1:.2f} sau 1 xác nhận")
assert n1 > n0
# nút sửa: cam treo + có thao tác khởi động lại → sáng và chỉ chạy đúng thao tác đó
pt = D.tinh(["mot_cam_mat", "treo"], "", "dang_mat")
print("   cam treo:", D.dong_mot_dong(pt), "| nút:", pt["nut_sua"], "| sẽ chạy:", D.viec_sua(pt, ["khoi_dong_cam", "khoi_dong_modem", "them_nat"]))
assert pt["nut_sua"] == "sang" and D.viec_sua(pt, ["khoi_dong_cam", "khoi_dong_modem", "them_nat"]) == ["khoi_dong_cam"]
print("✓ 2.1.0: chẩn đoán theo % — modem/VNPT vs mất điện tách được nhờ nhật ký cam; nút sửa có điều kiện; học từ xác nhận")
S.tat_het()
