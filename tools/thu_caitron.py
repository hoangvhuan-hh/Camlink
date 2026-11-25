# 2.12.16 — BÀI THỬ TRỌN CHUỖI một lượt cài điểm (C.chay) với thiết bị GIẢ nhưng có trạng thái thật:
#   2 cam Uniview (LAPI + ONVIF; đổi port/IP thì cổng nghe đổi theo; RTSP chỉ đổi sau khi khởi động lại) + modem VNPT AX3000 (đăng nhập, khoá, NAT).
# Mục đích: không còn chuyện "từng khâu chạy được mà cả chuỗi chưa chạy lần nào" trước khi đem ra công trình.
# Chạy: python3 tools/thu_caitron.py   (cần quyền mở cổng 80/554 trên 127.0.7.x)
import sys, os, re, json, time, base64, hashlib, socket, threading, http.server
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python"))
import rsa
pub, priv = rsa.newkeys(1024)
md5 = lambda x: hashlib.md5(x.encode()).hexdigest()
HE_THONG = "HeThong@2026"       # mật khẩu cam / modem người dùng nhập trong app
GW = "127.0.7.1"


class Cam:
    """Cam UNV giả: nghe ở (ip, http) và (ip, rtsp); đổi cấu hình thì đóng cổng cũ, mở cổng mới như cam thật."""
    def __init__(self, ten, ip, pw):
        self.ten, self.ip, self.http, self.rtsp, self.rtsp_cho = ten, ip, 80, 554, None
        self.pw = {"admin": pw}
        self.ddns = {"Enable": 0, "UsedType": 0, "Number": 2, "DDNSs": [
            {"Type": 0, "TypeName": "DynDNS", "ServerName": "members.dyndns.org", "UserName": "", "DeviceDomain": ""},
            {"Type": 1, "TypeName": "NO-IP", "ServerName": "dynupdate.no-ip.com", "UserName": "", "DeviceDomain": ""}]}
        self.ddns_pw, self.sv, self.rs, self.gw, self.ddns_ghi = None, None, None, "", 0
        self.mo()

    def mo(self):
        cam = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self): cam.xu(self, "GET")
            def do_PUT(self): cam.xu(self, "PUT")
            def do_POST(self): cam.xu(self, "POST")
        self.sv = http.server.ThreadingHTTPServer((self.ip, self.http), H)
        threading.Thread(target=self.sv.serve_forever, daemon=True).start()
        self.rs = socket.socket(); self.rs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.rs.bind((self.ip, self.rtsp)); self.rs.listen(8)

    def doi(self, ip=None, http=None, khoi_dong=False):
        """Áp cấu hình mới sau 0,4 giây (để kịp trả lời lệnh đang xử lý)."""
        def lam():
            time.sleep(0.4)
            sv, rs = self.sv, self.rs
            threading.Thread(target=sv.shutdown, daemon=True).start(); time.sleep(0.2); sv.server_close(); rs.close()
            if ip: self.ip = ip
            if http: self.http = http
            if khoi_dong and self.rtsp_cho: self.rtsp, self.rtsp_cho = self.rtsp_cho, None
            if khoi_dong: time.sleep(1.5)
            self.mo()
        threading.Thread(target=lam, daemon=True).start()

    def tra(self, h, ma, than, kieu="application/json", hd=None):
        b = than.encode() if isinstance(than, str) else json.dumps(than).encode()
        h.send_response(ma)
        for k, v in (hd or {}).items(): h.send_header(k, v)
        h.send_header("Content-Type", kieu); h.send_header("Content-Length", str(len(b))); h.end_headers(); h.wfile.write(b)

    def digest_ok(self, h, cach):
        m = dict(re.findall(r'(\w+)="?([^",]+)"?', h.headers.get("Authorization", "")))
        pw = self.pw.get(m.get("username"))
        if not pw: return False
        ha1, ha2 = md5(f"{m['username']}:unv:{pw}"), md5(f"{cach}:{m.get('uri')}")
        dung = md5(f"{ha1}:{m.get('nonce')}:{m.get('nc')}:{m.get('cnonce')}:{m.get('qop')}:{ha2}") if m.get("qop") else md5(f"{ha1}:{m.get('nonce')}:{ha2}")
        return dung == m.get("response")

    def onvif_ok(self, than):
        u = re.search(r"<Username>(.*?)</Username>", than); dg = re.search(r"PasswordDigest\">(.*?)<", than)
        nonce = re.search(r"Base64Binary\">(.*?)<", than); cr = re.search(r"<Created[^>]*>(.*?)<", than)
        if not (u and dg and nonce and cr and u.group(1) in self.pw): return False
        return base64.b64encode(hashlib.sha1(base64.b64decode(nonce.group(1)) + cr.group(1).encode() + self.pw[u.group(1)].encode()).digest()).decode() == dg.group(1)

    def xu(self, h, cach):
        p = h.path.split("?")[0]
        n = int(h.headers.get("Content-Length") or 0); tho = h.rfile.read(n).decode("utf-8", "replace") if n else ""
        if p.startswith("/onvif/"):
            bao = lambda x: self.tra(h, 200, f'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"><s:Body>{x}</s:Body></s:Envelope>', "application/soap+xml")
            if "GetSystemDateAndTime" in tho:
                t = time.gmtime()
                return bao(f"<UTCDateTime><Time><Hour>{t.tm_hour}</Hour><Minute>{t.tm_min}</Minute><Second>{t.tm_sec}</Second></Time>"
                           f"<Date><Year>{t.tm_year}</Year><Month>{t.tm_mon}</Month><Day>{t.tm_mday}</Day></Date></UTCDateTime>")
            if not self.onvif_ok(tho):
                return self.tra(h, 400, '<s:Envelope><s:Body><s:Fault><s:Reason><s:Text>Sender not Authorized</s:Text></s:Reason></s:Fault></s:Body></s:Envelope>', "application/soap+xml")
            if "GetDeviceInformation" in tho: return bao("<Manufacturer>UNIVIEW</Manufacturer><Model>IPC2B25SS-ADZK-I1</Model><SerialNumber>S1</SerialNumber><FirmwareVersion>1</FirmwareVersion>")
            if "GetNetworkInterfaces" in tho: return bao(f'<NetworkInterfaces token="eth0"><Info><HwAddress>48:ea:63:00:00:{self.ten[-1]}0</HwAddress></Info></NetworkInterfaces>')
            if "SetNetworkDefaultGateway" in tho: self.gw = re.search(r"IPv4Address>([\d.]+)", tho).group(1); return bao("<ok/>")
            if "SetNetworkProtocols" in tho:      # như cam thật: HTTP đổi ngay, RTSP chờ khởi động lại
                c = dict(re.findall(r"Name>(\w+)</.*?Port>(\d+)<", tho, re.S))
                if int(c["RTSP"]) != self.rtsp: self.rtsp_cho = int(c["RTSP"])
                bao("<ok/>")
                if int(c["HTTP"]) != self.http: self.doi(http=int(c["HTTP"]))
                return
            if "SetNetworkInterfaces" in tho:
                bao("<RebootNeeded>false</RebootNeeded>"); return self.doi(ip=re.search(r"Address>([\d.]+)<", tho).group(1))
            if "SystemReboot" in tho: bao("<Message>Rebooting</Message>"); return self.doi(khoi_dong=True)
            return bao("<ok/>")
        if not p.startswith("/LAPI/"): return self.tra(h, 404, "nf", "text/html")
        body = json.loads(tho) if tho else {}
        dat = lambda d=None: self.tra(h, 200, {"Response": {"ResponseURL": p, "CreatedID": -1, "ResponseCode": 0, "ResponseString": "Succeed", "StatusCode": 0, "Data": d if d is not None else "null"}})
        if not self.digest_ok(h, cach):
            return self.tra(h, 401, {"Response": {"ResponseURL": p, "ResponseCode": 3, "ResponseString": "Not Authorized"}}, hd={"WWW-Authenticate": 'Digest realm="unv", qop="auth", nonce="abc123", algorithm=MD5'})
        if p == "/LAPI/V1.0/System/Security/RSA": return dat({"RSAPublicKeyE": format(pub.e, "x"), "RSAPublicKeyN": format(pub.n, "x")})
        if p == "/LAPI/V1.0/NetWork/Port":
            if cach == "PUT":      # như cam thật: đổi RTSP qua LAPI thì cam tự khởi động lại
                dat({"HttpPort": body["HttpPort"], "HttpsPort": 443, "RtspPort": body["RtspPort"]})
                if int(body["RtspPort"]) != self.rtsp: self.rtsp_cho = int(body["RtspPort"])
                if int(body["HttpPort"]) != self.http or self.rtsp_cho: self.doi(http=int(body["HttpPort"]), khoi_dong=True)
                return
            return dat({"HttpPort": self.http, "HttpsPort": 443, "RtspPort": self.rtsp})
        if p == "/LAPI/V1.0/Channel/0/System/Users": return dat({"Users": [{"ID": 1, "Name": "admin", "Level": 0}]})
        if p == "/LAPI/V1.0/Channel/0/System/Users/Users/1" and cach == "PUT":
            self.pw["admin"] = rsa.decrypt(base64.b64decode(body["Passwd"]), priv).decode(); return dat()
        if p == "/LAPI/V1.0/NetWork/DDNS":
            if cach == "PUT":
                self.ddns_ghi += 1
                for x in body["DDNSs"]:
                    if "PassWord" in x: self.ddns_pw = rsa.decrypt(base64.b64decode(x.pop("PassWord")), priv).decode()
                body.pop("RSAPublicKey", None); self.ddns = body
            return dat(self.ddns)
        self.tra(h, 404, {"Response": {"ResponseURL": p, "ResponseCode": 1}})


class Modem:
    pw, sai, khoa, nat, lan = HE_THONG, 0, False, [], 0


class HM(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def tra(self, b):
        b = b.encode(); self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self.tra('<p>AX3000 Wireless Dual-Band GPON ONT</p><script src="login.js"></script>')
    def do_POST(self):
        than = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("latin-1"); ten = self.path.split("/cgi-bin/luci/")[-1]
        q = dict(x.split("=", 1) for x in than.split("&") if "=" in x)
        if ten == "login.cmd":
            Modem.lan += 1
            if Modem.khoa: return self.tra('{"status":"fail","numberLogin":"3","timeoutLogin":"180"}')
            if q.get("pass") == Modem.pw: Modem.sai = 0; return self.tra('{"status":"OK","sessionKey":"777","firstlog":"0"}')
            Modem.sai += 1
            if Modem.sai >= 3: Modem.khoa = True
            return self.tra('{"status":"fail","numberLogin":"%d","timeoutLogin":"%d"}' % (Modem.sai, 180 if Modem.khoa else 0))
        if ten == "logout.cmd": return self.tra('{"status":"OK"}')
        if q.get("sessionKey") != "777": return self.tra('{"status":"fail authen"}')
        if ten == "natvirtualserver.json":
            st = {}
            if q.get("action") == "add":
                e = q["eStart"].rstrip(","); Modem.nat.append(f'{q["serviceName"]}|{e}|{e}|TCP|{e}|{e}|{q["srvAddr"]}|{q["dstWanIf"]}'); st = {"status": "OK"}
            return self.tra(json.dumps(json.dumps({**st, "enblNat": "1", "scVrtSrv": Modem.nat, "wanInterfaceInfoRoute": "tr069_veip0.2/veip0.2|internet_veip0.11/veip0.11",
                                                   "ethIpAddress": GW, "ethSubnetMask": "255.255.255.0", "glbEntryCt": len(Modem.nat)})))
        self.tra('{"status":"OK"}')


threading.Thread(target=http.server.ThreadingHTTPServer((GW, 80), HM).serve_forever, daemon=True).start()
import camlink_dt as C
RA = "/tmp/camlink_thu_caitron"; os.makedirs(RA, exist_ok=True)
C.thu_muc_ra = lambda: RA
C.tu_thu_mau = lambda *a: None
C.upnp_tim = lambda: None                      # modem VNPT AX3000 thật: UPnP tắt
C.pass_modem_yeu = lambda u, p: False
os.environ["CAMLINK_MAY"] = "127.0.7.9"; C.GW = GW
C.PHU_LY.clear(); C.PHU_LY["1"] = {"ten": "Điểm thử", "domain": "diem-thu.ddns.net", "u": "ddnsuser", "p": "ddnspass", "so": 2}
nk, PT = [], []
C.LOG_CB = lambda x: PT.append(int(x[8:].split("|")[0])) if x.startswith("TIEN_DO ") else nk.append(x)
dat = 0


def kt(ten, dk):
    global dat
    if not dk:
        print("\n".join(nk[-60:])); raise SystemExit("✖ TRƯỢT: " + ten)
    dat += 1; print("✓", ten)


def luat_modem():
    return sorted((int(x.split("|")[1]), x.split("|")[6]) for x in Modem.nat)


# ---------- Lượt 1: 2 cam MỚI (mật khẩu xuất xưởng) + modem đúng mật khẩu hệ thống → app phải làm TRỌN, không còn việc tay
c1, c2 = Cam("cam1", "127.0.7.50", "123456"), Cam("cam2", "127.0.7.51", "123456")
C.CHUM["cam"], C.CHUM["modem"] = [], []
t0 = time.time(); C.chay("1", "admin", HE_THONG, "admin", HE_THONG)
k = C.KQ_CUOI
print(f"   (lượt 1 chạy {time.time() - t0:.0f} giây)")
kt("L1: thấy đủ 2 cam, cả 2 ĐẠT", len(k.get("cam", [])) == 2 and all(c["ok"] for c in k["cam"]))
kt("L1: cả 2 cam được đổi từ mật khẩu xuất xưởng sang mật khẩu hệ thống", c1.pw["admin"] == HE_THONG and c2.pw["admin"] == HE_THONG)
kt("L1: cam 1 → .200 HTTP 8080 RTSP 554; cam 2 → .201 HTTP 8081 RTSP 5541", (c1.ip, c1.http, c1.rtsp, c2.ip, c2.http, c2.rtsp) == ("127.0.7.200", 8080, 554, "127.0.7.201", 8081, 5541))
kt("L1: DDNS No-IP nhập lên cam 1 (đúng tên miền, user, pass)", c1.ddns["Enable"] == 1 and c1.ddns["DDNSs"][1]["DeviceDomain"] == "diem-thu.ddns.net" and c1.ddns["DDNSs"][1]["UserName"] == "ddnsuser" and c1.ddns_pw == "ddnspass")
kt("L1: modem có đủ 4 luật mở port đúng IP", luat_modem() == [(554, "127.0.7.200"), (5541, "127.0.7.201"), (8080, "127.0.7.200"), (8081, "127.0.7.201")])
kt("L1: modem chỉ nhận 1 lần đăng nhập (không thử thừa)", Modem.lan == 1)
kt("L1: % tiến độ tăng dần 5 → 92, đủ mốc quét / từng cam / modem / kiểm tra, không lẫn vào nhật ký",
   PT == sorted(PT) and PT[0] == 5 and PT[-1] == 92 and len(PT) >= 12 and not any("TIEN_DO" in str(l) for l in C.NHAT_KY))
kt("L1: báo cáo từng việc: tất cả ĐÃ HOÀN TẤT", k.get("viec_con") == [] and len(k["bao_cao"]) == 5 and all(b["xong"] for b in k["bao_cao"]))

# ---------- Lượt 2: cài LẠI điểm đã cài đúng → nhận ra đã đúng, giữ nguyên, không thêm luật trùng
del nk[:]; Modem.lan = 0
C.chay("1", "admin", HE_THONG, "admin", HE_THONG); k = C.KQ_CUOI
kt("L2: 2 cam báo 'đã đúng sẵn — giữ nguyên'", sum("đã đúng sẵn (IP" in l for l in nk) == 2 and all(c["ok"] for c in k["cam"]))
kt("L2: modem vẫn đúng 4 luật (không thêm trùng), không còn việc tay", len(Modem.nat) == 4 and k.get("viec_con") == [])
kt("L2: việc đã xong không làm lại — DDNS trên cam 1 chỉ ghi đúng 1 lần (ở lượt 1)", c1.ddns_ghi == 1 and any("DDNS đã đúng sẵn" in c["ghi"] for c in k["cam"]))

# ---------- Lượt 3: cam 2 bị đặt mật khẩu LẠ + modem mật khẩu LẠ → cam 1 vẫn xong, báo đúng 2 việc còn lại
del nk[:]; Modem.lan, Modem.pw, Modem.nat = 0, "TemModem#99", []
c2.pw["admin"] = "MatKhauLa!1"
C.chay("1", "admin", HE_THONG, "admin", HE_THONG); k = C.KQ_CUOI
vc = k.get("viec_con") or []
kt("L3: cam 1 vẫn được xử lý xong dù cam 2 và modem hỏng", len(k["cam"]) == 1 and k["cam"][0]["ok"])
kt("L3: cam 2 — đã thử cả mật khẩu hệ thống lẫn xuất xưởng rồi mới kết luận", any("mật khẩu cam đã lưu ✖" in l and "mật khẩu xuất xưởng ✖" in l for l in nk))
kt("L3: modem — chưa được cấp mật khẩu xuất xưởng nên chỉ thử mật khẩu hệ thống (không đoán), không làm modem khoá", Modem.lan == 1 and not Modem.khoa)
bc = {b["viec"].split(":")[0].split(" (")[0]: b for b in k["bao_cao"]}
kt("L3: báo cáo từng việc — cam 1 + DDNS hoàn tất; cam 2, đăng nhập modem, mở port CHƯA kèm lý do",
   bc["Cam 1"]["xong"] and not bc["Đăng nhập trang quản trị modem"]["xong"] and bc["Đăng nhập trang quản trị modem"]["ly_do"]
   and sum(1 for b in k["bao_cao"] if not b["xong"] and b["ly_do"]) == 3)
kt("L3: báo đúng 2 việc còn phải làm tay (cam 2 + mở port modem, kèm bảng port)", len(vc) == 2 and any("127.0.7.201" in v for v in vc) and any("MỞ PORT TRÊN MODEM" in v and "8080 → 127.0.7.200" in v for v in vc))

# ---------- Lượt 4: Huan cấp mật khẩu xuất xưởng của modem (nạp vào bảng) → modem còn xuất xưởng thì vào bằng khoá thứ 2, mở đủ port
import camlink_modem as M
M.XUAT_XUONG_DA_BIET["vnpt_ax3000"] = [("admin", "XuatXuong#1")]
del nk[:]; Modem.lan, Modem.pw, Modem.nat, Modem.sai = 0, "XuatXuong#1", [], 0
c2.pw["admin"] = HE_THONG
C.chay("1", "admin", HE_THONG, "admin", HE_THONG); k = C.KQ_CUOI
kt("L4: modem xuất xưởng (mật khẩu được cấp) → vào được ở lần thử thứ 2, mở đủ 4 luật", Modem.lan == 2 and len(Modem.nat) == 4)
kt("L4: 2 cam đạt, báo cáo: tất cả việc đã hoàn tất", len(k["cam"]) == 2 and all(c["ok"] for c in k["cam"]) and k.get("viec_con") == [] and all(b["xong"] for b in k["bao_cao"]))

# ---------- Lượt 5: lần trước DỞ đúng một việc (DDNS trên cam 1 chưa nhập) → lần này chỉ làm việc đó, cam/port/modem giữ nguyên
del nk[:]; del PT[:]; Modem.lan = 0
c1.ddns["Enable"] = 0; c1.ddns_ghi = 0; so_luat = len(Modem.nat)
C.chay("1", "admin", HE_THONG, "admin", HE_THONG); k = C.KQ_CUOI
kt("L5: chỉ làm việc còn dở — DDNS được nhập lại đúng 1 lần", c1.ddns_ghi == 1 and c1.ddns["Enable"] == 1)
kt("L5: việc đã xong giữ nguyên — 2 cam 'đã đúng sẵn', không thêm luật modem, báo cáo tất cả hoàn tất",
   sum("đã đúng sẵn (IP" in l for l in nk) == 2 and len(Modem.nat) == so_luat and all(b["xong"] for b in k["bao_cao"]))
print(f"\n✓ 2.12.18 cài trọn chuỗi (cam UNV + modem VNPT AX3000 giả lập): {dat}/{dat} đạt")
