# 2.13.0 — SỬA MODEM TỪ XA (anh Huan chốt 27/11/2026, 7 ý). Thiết kế: docs/superpowers/specs/2026-11-27-sua-modem-tu-xa-design.md
# Dựng một ĐIỂM GIẢ có đủ 3 lớp như thật: IP ngoài (tên miền) → modem VNPT AX3000 giả (bảng mở port CÓ TÁC DỤNG THẬT: có luật thì cổng ngoài
# mới thông vào cam) → 2 cam giả trong mạng. Mất luật thì từ ngoài không thấy cam, đúng như ngoài công trình.
# Chạy: sudo python3 tools/thu_suamodem.py   (cần mở cổng 80/554 ở 127.0.9.x)
import os, sys, json, shutil, socket, tempfile, threading, zipfile, io, http.server
os.environ["CAMLINK_THU_NOI_BO"] = "1"
GOC_TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(GOC_TOOLS, "../app/src/main/python")); sys.path.insert(0, GOC_TOOLS)
G = os.path.join(tempfile.gettempdir(), "camlink_thu", "suamodem"); shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
import gialap_onvif as S, camlink_core as K, camlink_dt as C, camlink_tuxa as T, camlink_modem as M
K.khoi_tao(G)
NGOAI, GW, PW_MODEM, PW_CAM = "127.0.9.1", "127.0.9.254", "ModemHeThong@27", "Abc@12345"      # NGOAI đóng vai tên miền của điểm
cd = C.doc_cai_dat(); cd.update(cam_user="admin", cam_pw=PW_CAM, modem_user="admin", modem_pw=PW_MODEM); C.ghi_cai_dat(cd)
dat = 0


def kt(ten, dk, them=""):
    global dat
    assert dk, "HỎNG: " + ten + (" — " + str(them) if them else "")
    dat += 1; print("✓", ten)


# ------------------------------------------------------------------ modem AX3000 giả: bảng mở port có tác dụng thật
class Modem:
    pw, nat, lenh, vao, ra, chuyen = PW_MODEM, [], [], 0, 0, {}      # nat: [(tên, cổng ngoài, cổng trong, IP)]; chuyen: {cổng ngoài: socket nghe}


def _ong(a, b):
    try:
        while True:
            d = a.recv(65536)
            if not d:
                break
            b.sendall(d)
    except OSError:
        pass
    for s in (a, b):
        try:
            s.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


def _nghe(sk, ip, cong):
    while True:
        try:
            k, _ = sk.accept()
        except OSError:
            return
        try:
            t = socket.create_connection((ip, cong), 3)
        except OSError:
            k.close(); continue
        threading.Thread(target=_ong, args=(k, t), daemon=True).start(); threading.Thread(target=_ong, args=(t, k), daemon=True).start()


def dong_bo():
    """Bảng mở port → cổng ngoài nào có luật VÀ máy trong còn sống thì thông; còn lại đóng (từ ngoài bị từ chối)."""
    can = {}
    for _, ngoai, trong, ip in Modem.nat:
        try:
            socket.create_connection((ip, trong), 1).close(); can[ngoai] = (ip, trong)
        except OSError:
            pass
    for p in [p for p in Modem.chuyen if p not in can or Modem.chuyen[p][1] != can[p]]:
        sk = Modem.chuyen.pop(p)[0]
        try:
            sk.shutdown(socket.SHUT_RDWR)      # đánh thức luồng đang chờ accept, không thì cổng vẫn còn nghe
        except OSError:
            pass
        sk.close()
    for p, (ip, trong) in can.items():
        if p not in Modem.chuyen:
            sk = socket.socket(); sk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); sk.bind((NGOAI, p)); sk.listen(32)
            Modem.chuyen[p] = (sk, (ip, trong)); threading.Thread(target=_nghe, args=(sk, ip, trong), daemon=True).start()


TRANG = {"home.html": '<a href="nat.html">NAT</a><a href="wan.html">WAN</a><a href="wifi.html">WiFi</a><a href="reboot.html">Reboot</a><a href="device_info.html">Thiết bị</a>',
         "nat.html": '<script src="js/nat.js"></script>', "wan.html": '<script src="js/wan.js"></script>PPPOE_BI_MAT', "wifi.html": '<script src="js/wifi.js"></script>WIFI_BI_MAT',
         "reboot.html": '<script src="js/reboot.js"></script>', "device_info.html": '<script src="js/device_info.js"></script>',
         "js/nat.js": 'send_http_request("natvirtualserver.json")', "js/wan.js": "PPPOE_BI_MAT", "js/wifi.js": "WIFI_BI_MAT",
         "js/reboot.js": 'send_http_request("reboot.cmd")', "js/device_info.js": 'send_http_request("lanhost.json")'}


class HM(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def tra(self, b, ma=200):
        b = b.encode(); self.send_response(ma); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        d = self.path.lstrip("/").split("?")[0]
        if d in TRANG: return self.tra(TRANG[d])
        if d == "": return self.tra('<p>AX3000 Wireless Dual-Band GPON ONT</p><script src="login.js"></script>')
        self.tra("khong co", 404)

    def do_POST(self):
        than = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("latin-1"); ten = self.path.split("/cgi-bin/luci/")[-1]
        q = dict(x.split("=", 1) for x in than.split("&") if "=" in x)
        Modem.lenh.append(ten + ":" + q.get("action", ""))
        if ten == "login.cmd":
            Modem.vao += 1
            if q.get("pass") == Modem.pw: return self.tra('{"status":"OK","sessionKey":"777","firstlog":"0"}')
            return self.tra('{"status":"fail","numberLogin":"1","timeoutLogin":"0"}')
        if ten == "logout.cmd":
            Modem.ra += 1; return self.tra('{"status":"OK"}')
        if q.get("sessionKey") != "777": return self.tra('{"status":"fail authen"}')
        if ten == "natvirtualserver.json":
            st = {}
            if q.get("action") == "add":
                Modem.nat.append((q["serviceName"], int(q["eStart"].rstrip(",")), int(q["iStart"].rstrip(",")), q["srvAddr"])); dong_bo(); st = {"status": "OK"}
            return self.tra(json.dumps(json.dumps({**st, "enblNat": "1", "scVrtSrv": [f"{t}|{e}|{e}|TCP|{i}|{i}|{ip}|veip0.11" for t, e, i, ip in Modem.nat],
                                                   "wanInterfaceInfoRoute": "tr069_veip0.2/veip0.2|internet_veip0.11/veip0.11", "glbEntryCt": len(Modem.nat)})))
        self.tra('{"status":"OK"}')


http.server.ThreadingHTTPServer.allow_reuse_address = True
threading.Thread(target=http.server.ThreadingHTTPServer((GW, 80), HM).serve_forever, daemon=True).start()


def cam(ip, h, r):
    c = S.Cam(ip, isapi=False, stt=1); c.http, c.rtsp = h, r; c.gw = GW; c.model = "OR-IPC-B4"; c.mac = "78:CE:A5:09:%02X:%02X" % (int(ip.split(".")[3]), h % 256); S.bat(c); return c


c1, c2 = cam("127.0.9.200", 8080, 554), cam("127.0.9.201", 8081, 5541)
LUAT_DUNG = [("cam1", 8080, 8080, "127.0.9.200"), ("cam1_rtsp", 554, 554, "127.0.9.200"), ("cam2", 8081, 8081, "127.0.9.201"), ("cam2_rtsp", 5541, 5541, "127.0.9.201")]
CUA = ("camlink_modem", 8098, 80, GW)


def dat_luat(ds):
    Modem.nat = list(ds); dong_bo()


def hs(web=8098):
    return {"luc": "27/11/2026 08:00", "wan": NGOAI, "gw": GW, "web_modem": web, "modem_kieu": "vnpt_ax3000" if web else "",
            "luat": [{"ten": t, "port": e, "ip": ip} for t, e, _, ip in LUAT_DUNG],
            "cam": [{"so": 1, "ip": "127.0.9.200", "mac": c1.mac, "model": "OR-IPC-B4"}, {"so": 2, "ip": "127.0.9.201", "mac": c2.mac, "model": "OR-IPC-B4"}]}


def du_an(web=8098):
    da = {"ten": "Diem gia sua modem", "diem": {"1": {"ten": "Cột 1", "domain": NGOAI, "so": 2, "u": "", "p": ""}}, "toa_do": {}, "da_xong": {"1": "x"}, "ho_so": {"1": hs(web)}}
    ma = K._ma(K._ten_tu_file(da["ten"] + ".xlsx")); K._ghi_du_an(ma, da); return ma, da


def kiem(da, ma):
    return T.kiem_du_an(G, da, ma, cd, log=lambda s: None, tu_sua=False)


def muc(r):
    return [c["muc"] for c in r["diem"][0]["cam"]]


ma, da = du_an()
dat_luat(LUAT_DUNG + [CUA])
r = kiem(da, ma)
kt("M0: điểm giả đủ luật mở port → kiểm tra từ xa thấy 2/2 cam xanh (nền để so)", muc(r) == ["xanh", "xanh"], [(c["nhan"], c["nguyen_nhan"]) for c in r["diem"][0]["cam"]])

# ================= ý 4 + 6: điểm còn sống, tên miền vào được, cam KHÔNG ra vì modem mất luật mở port → Sửa từ xa phải tự mở lại
dat_luat([x for x in LUAT_DUNG if x[0] not in ("cam2", "cam2_rtsp")] + [CUA])
r = kiem(da, ma)
kt("M1a: modem mất luật của cam 2 → chẩn đoán đúng: cam 1 xanh, cam 2 không ra, có việc sửa trên modem", muc(r)[0] == "xanh" and muc(r)[1] != "xanh" and "them_nat" in r["diem"][0]["cam"][1]["sua"])
Modem.vao = Modem.ra = 0; del Modem.lenh[:]
r2 = T.sua_tat_ca(G, da, ma, r, cd, log=lambda s: None)
bc = r2["bao_cao_sua"]
kt("M1b: bấm Sửa từ xa → app vào modem qua cửa từ xa, tự thêm lại 2 luật của cam 2 (đúng port, đúng IP cam)",
   sorted(Modem.nat) == sorted(LUAT_DUNG + [CUA]), Modem.nat)
kt("M1c: kiểm lại ra xanh 2/2 và báo cáo ghi HOÀN THÀNH", muc(r2) == ["xanh", "xanh"] and [b["ket_qua"] for b in bc] == ["HOÀN THÀNH"], bc)
kt("M1d: modem chỉ cho một nơi đăng nhập → mỗi lần vào app đều đăng xuất (số lần vào = số lần ra, không thừa)", Modem.vao == Modem.ra == 1, (Modem.vao, Modem.ra))

# ================= cả điểm: mất HẾT luật của cam, cửa modem còn → sửa được hết từ xa
dat_luat([CUA])
r = kiem(da, ma)
kt("M2a: mất hết luật cam (IP điểm còn sống) → 0/2 cam, vẫn có việc sửa trên modem cho cả 2 cam", muc(r).count("xanh") == 0 and all("them_nat" in c["sua"] for c in r["diem"][0]["cam"]), [(c["nhan"], c["sua"]) for c in r["diem"][0]["cam"]])
r2 = T.sua_tat_ca(G, da, ma, r, cd, log=lambda s: None)
kt("M2b: Sửa từ xa mở lại đủ 4 luật, 2/2 cam xanh, mọi dòng báo cáo HOÀN THÀNH", sorted(Modem.nat) == sorted(LUAT_DUNG + [CUA]) and muc(r2) == ["xanh", "xanh"] and all(b["ket_qua"] == "HOÀN THÀNH" for b in r2["bao_cao_sua"]), r2["bao_cao_sua"])

# ================= ý 5 + 7: luật trên modem ĐÚNG mà cam không trả lời → cam không còn trên mạng → nói rõ cần người tại điểm, không báo chung chung
S.tat(c2); dong_bo()
r = kiem(da, ma)
so_luat = len(Modem.nat)
r2 = T.sua_tat_ca(G, da, ma, r, cd, log=lambda s: None)
b = r2["bao_cao_sua"][0]; chu = json.dumps(b, ensure_ascii=False)
kt("M3a: cam 2 rút nguồn → app soát modem thấy luật đúng, KHÔNG thêm luật thừa", len(Modem.nat) == so_luat and b["ket_qua"] == "CHƯA", chu)
kt("M3b: báo cáo nói đúng: luật mở port trên modem đúng → cam không còn trên mạng (mất nguồn / lỏng dây)", b["nguyen_nhan"].startswith("Luật mở port trên modem ĐÚNG") and "mất nguồn" in b["nguyen_nhan"], chu)
kt("M3c: báo cáo ghi rõ AI xử lý: cần người tại điểm (không phải nhà mạng, không phải sửa từ xa)", b.get("ai") == "Cần người tại điểm" and any(g.startswith("Ai xử lý: Cần người tại điểm") for g in b["giai_phap"]), chu)
c2 = cam("127.0.9.201", 8081, 5541); dong_bo()

# ================= luật SAI IP: modem AX3000 app chưa có lệnh xoá → không ghi đè bừa, báo đúng luật nào sai
dat_luat([x for x in LUAT_DUNG if x[0] != "cam2"] + [("cam2", 8081, 8081, "127.0.9.250"), CUA])
r = kiem(da, ma)
r2 = T.sua_tat_ca(G, da, ma, r, cd, log=lambda s: None)
chu = json.dumps(r2["bao_cao_sua"], ensure_ascii=False)
kt("M4: luật 8081 trỏ SAI IP → app không ghi đè, báo rõ 'port 8081 đang trỏ về 127.0.9.250', kết quả CHƯA",
   ("cam2", 8081, 8081, "127.0.9.250") in Modem.nat and "8081" in chu and "127.0.9.250" in chu and r2["bao_cao_sua"][0]["ket_qua"] == "CHƯA", chu)

# ================= điểm CHƯA có cửa modem (cài tay / modem không cho) → nói thật, không thử đăng nhập mò
ma0, da0 = du_an(web=0)
dat_luat([x for x in LUAT_DUNG if x[0] not in ("cam2", "cam2_rtsp")] + [CUA])
r = kiem(da0, ma0); Modem.vao = 0
r2 = T.sua_tat_ca(G, da0, ma0, r, cd, log=lambda s: None)
chu = json.dumps(r2["bao_cao_sua"], ensure_ascii=False)
kt("M5: điểm chưa mở cửa modem lúc cài → báo 'chưa có cửa vào modem từ xa', KHÔNG đăng nhập modem lần nào, không còn câu 'chờ mẫu modem'",
   Modem.vao == 0 and "chưa có cửa vào modem từ xa" in chu and "chờ mẫu" not in chu and r2["bao_cao_sua"][0]["ket_qua"] == "CHƯA", chu)

# ================= sai mật khẩu modem: đúng MỘT lần thử (sai 3 lần modem khoá 3 phút)
ma, da = du_an()
Modem.pw = "NhaMangDoiRoi#1"; Modem.vao = 0
d1 = dict(da["diem"]["1"], _hs=da["ho_so"]["1"])
ok, tb = T.sua(d1, 2, "them_nat", cd, lambda s: None)
kt("M6: nhà mạng đổi mật khẩu modem → app thử đúng 1 lần rồi dừng, báo không vào được modem qua cửa từ xa", not ok and Modem.vao == 1 and "Không vào được modem" in tb, (Modem.vao, tb))
Modem.pw = PW_MODEM

# ================= khởi động lại modem AX3000: app chưa có lệnh → nói thật, không gửi lệnh đoán
del Modem.lenh[:]
ok, tb = T.sua(d1, 1, "khoi_dong_modem", cd, lambda s: None)
kt("M7: khởi động lại modem AX3000 từ xa: app chưa có lệnh (cần mẫu trang modem) → báo rõ, KHÔNG gửi lệnh nào tới modem", not ok and "chưa có lệnh khởi động lại" in tb and Modem.lenh == [], (tb, Modem.lenh))

# ================= kiểm tra từ xa: cam im lặng (modem VNPT thật không báo từ chối) → có cửa thì việc sửa là soát modem; không cửa thì giữ như cũ
goc_cham = T.cham_tg
T.cham_tg = lambda h, p, *a, **k: ("im_lang", 0) if p in (8081, 5541) else goc_cham(h, p, *a, **k)
dat_luat([x for x in LUAT_DUNG if x[0] not in ("cam2", "cam2_rtsp")] + [CUA])
co = kiem(da, ma)["diem"][0]["cam"][1]; khong = kiem(da0, ma0)["diem"][0]["cam"][1]
T.cham_tg = goc_cham
kt("M8: cam im lặng + điểm có cửa modem → việc sửa là soát luật trên modem; điểm không có cửa → giữ nguyên như trước", co["sua"] == ["them_nat"] and khong["sua"] == ["khoi_dong_modem"], (co["sua"], khong["sua"]))

# ================= ý 1: lúc cài — mở cửa vào modem (UPnP không được thì qua trang modem), không mở khi mật khẩu modem yếu
dat_luat(LUAT_DUNG)
v = M.VnptLuci(GW, "admin", PW_MODEM); assert v.nhan_ra() and v.dang_nhap()
kt("C1a: modem AX3000 đang phục vụ trang ở cổng 80 → app biết cổng web của modem để trỏ cửa vào", v.cong_web() == 80)
web, ly = C.mo_cua_modem(v, None, GW, "admin", PW_MODEM, log=lambda s: None)
kt("C1b: UPnP tắt → app mở cửa qua trang modem: luật 8098 → modem (cổng web của modem)", web == 8098 and ly == "" and CUA in Modem.nat, (web, ly, Modem.nat))
dat_luat(LUAT_DUNG)
web, ly = C.mo_cua_modem(v, None, GW, "admin", "admin", log=lambda s: None)
kt("C1c: mật khẩu modem còn yếu → KHÔNG mở cửa ra Internet, ghi rõ lý do", web == 0 and "yếu" in ly and len(Modem.nat) == 4, (web, ly))
web, ly = C.mo_cua_modem(None, None, GW, "admin", PW_MODEM, log=lambda s: None)
kt("C1d: chưa đăng nhập được modem và UPnP tắt → chưa mở được cửa, ghi rõ lý do", web == 0 and ly != "", (web, ly))
v.dang_xuat()

# ================= ý 2 + 3: thử cửa TỪ NGOÀI ngay lúc cài, ghi "Sửa modem từ xa: ĐƯỢC / CHƯA + lý do" vào hồ sơ điểm; hai IP chỉ ghi lại
dat_luat(LUAT_DUNG + [CUA])
da["ho_so"]["1"].update(bao_cao=[{"ngan": "Sửa modem từ xa", "viec": "x", "xong": True, "ly_do": ""}], wan_modem="100.70.1.2", ip_ngoai="14.1.2.3"); K._ghi_du_an(ma, da)
C.KQ_CUOI = {}; Modem.vao = Modem.ra = 0
kq = json.loads(K.bang_chung(ma, "1", None))
luu = K._doc_du_an(ma)["ho_so"]["1"]
kt("C2a: cửa thông → thử từ ngoài vào được modem → 'Sửa modem từ xa: ĐƯỢC', lưu vào hồ sơ điểm; vào 1 lần, ra 1 lần",
   kq["sua_tu_xa"]["duoc"] is True and luu["sua_tu_xa"]["duoc"] is True and Modem.vao == Modem.ra == 1, (kq.get("sua_tu_xa"), Modem.vao, Modem.ra))
kt("C2b: hai IP lệch nhau nhưng vào được → KHÔNG cảnh báo gì về IP (không bắt trùng)", "IP" not in kq["sua_tu_xa"].get("ly_do", ""), kq["sua_tu_xa"])
dat_luat(LUAT_DUNG)      # cửa không thông (modem không nhận luật trỏ vào chính nó / nhà mạng chặn)
kq = json.loads(K.bang_chung(ma, "1", None))
luu = K._doc_du_an(ma)["ho_so"]["1"]; b = next(x for x in luu["bao_cao"] if x["ngan"] == "Sửa modem từ xa")
kt("C2c: cửa không thông → 'Sửa modem từ xa: CHƯA' + lý do; dòng báo cáo cài chuyển sang chưa xong kèm lý do",
   kq["sua_tu_xa"]["duoc"] is False and kq["sua_tu_xa"]["ly_do"] and b["xong"] is False and b["ly_do"], (kq["sua_tu_xa"], b))
kt("C2d: thử không qua VÀ hai IP lệch nhau → lúc này mới dùng hai IP đã ghi để nói lý do (nhà mạng cấp IP dùng chung)",
   "100.70.1.2" in kq["sua_tu_xa"]["ly_do"] and "14.1.2.3" in kq["sua_tu_xa"]["ly_do"] and "nhà mạng" in kq["sua_tu_xa"]["ly_do"], kq["sua_tu_xa"])
src = open(os.path.join(GOC_TOOLS, "../app/src/main/python/camlink_dt.py"), encoding="utf-8").read()
kt("C3: lượt cài chỉ GHI hai IP (IP WAN trên modem, IP nhìn từ ngoài), không còn câu bắt gọi nhà mạng xin IP", "xin IP public" not in src and '"wan_modem"' in src and '"ip_ngoai"' in src)

# ================= thu mẫu để bổ sung lệnh còn thiếu (khởi động lại, danh sách thiết bị): chỉ ĐỌC mã trang, không lấy trang có mật khẩu
dat_luat(LUAT_DUNG); del Modem.lenh[:]
bo = io.BytesIO()
with zipfile.ZipFile(bo, "w") as z:
    C._thu_modem(z, "mau", f"http://{GW}", ("admin", PW_MODEM))
with zipfile.ZipFile(io.BytesIO(bo.getvalue())) as z:
    ten = z.namelist(); tat_ca = "".join(z.read(n).decode("utf-8", "replace") for n in ten)
kt("C4a: mẫu modem có mã các trang khởi động lại + danh sách thiết bị (để lần sau bổ sung lệnh)", "reboot.cmd" in tat_ca and "lanhost.json" in tat_ca, ten)
kt("C4b: mẫu KHÔNG lấy trang WAN / WiFi (có mật khẩu PPPoE, WiFi)", "PPPOE_BI_MAT" not in tat_ca and "WIFI_BI_MAT" not in tat_ca)
kt("C4c: thu mẫu chỉ ĐỌC: không gửi lệnh khởi động lại / thêm / xoá nào tới modem", all(l.split(":")[0] in ("login.cmd", "logout.cmd") or l.endswith(":get") for l in Modem.lenh), Modem.lenh)
print(f"\n✓ 2.13.0 sửa modem từ xa: {dat}/{dat} đạt")
