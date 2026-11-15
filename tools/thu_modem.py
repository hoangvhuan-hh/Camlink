# 2.9.0 — trình điều khiển modem iGate VNPT (nền Broadcom): modem giả có đăng nhập Basic + sessionKey đổi mỗi lần
import sys, os, re, base64, threading, random
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../app/src/main/python"))
import camlink_modem as M
import camlink_dt as C
dat = 0
def kt(ten, dk):
    global dat
    assert dk, ten
    dat += 1; print("✓", ten)

class Md:
    user, pw, khoa, luat, khoi_dong, kieu_khac = "admin", "admin", "0", [], 0, False
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _g(self, ma, t=""):
        b = t.encode(); self.send_response(ma)
        if ma == 401: self.send_header("WWW-Authenticate", 'Basic realm="Broadband Router"')
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        a = self.headers.get("Authorization", "")
        if a != "Basic " + base64.b64encode(f"{Md.user}:{Md.pw}".encode()).decode(): return self._g(401)
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        def trang(than):
            Md.khoa = str(random.randint(100000, 999999))
            return self._g(200, f"<html><script>var sessionKey='{Md.khoa}';</script>{than}</html>")
        if Md.kieu_khac: return self._g(200, "<html>modem kiểu khác</html>")
        bang = "".join(f"<tr><td>{t}</td><td>{p}</td><td>{p}</td><td>TCP</td><td>{p}</td><td>{p}</td><td>{ip}</td><td>ppp0.1</td></tr>" for t, p, ip in Md.luat)
        if u.path == "/scvrtsrv.html": return trang(f"<select name='dstWanIf'><option value='ppp0.1'>pppoe_0_1</option></select><table>{bang}</table>")
        if u.path in ("/password.html", "/resetrouter.html"): return trang("")
        if q.get("sessionKey") != Md.khoa: return self._g(200, "<html>sessionKey sai</html>")
        if u.path == "/scvrtsrv.cmd" and q.get("action") == "add":
            Md.luat.append((q["srvName"], int(q["eStart"].strip(",")), q["srvAddr"])); return trang("ok")
        if u.path == "/password.cgi" and q.get("inOrgPassword") == Md.pw and q.get("inUserName") == Md.user:
            Md.pw = q["inPassword"]; return self._g(200, "ok")
        if u.path == "/rebootinfo.cgi": Md.khoi_dong += 1; return self._g(200, "rebooting")
        self._g(404)
sv = HTTPServer(("127.0.0.1", 0), H); port = sv.server_address[1]
threading.Thread(target=sv.serve_forever, daemon=True).start()
goc_Bcm = M.Bcm
M.Bcm = lambda host, user, pw, p=port, cho=8: goc_Bcm(host, user, pw, p, cho)      # modem giả nghe ở cổng khác 80

nk = []
m = M.chuan_bi("127.0.0.1", "admin", "Vn@Lite#2026", nk.append, C.pass_modem_yeu)
kt("modem còn mật khẩu xuất xưởng → tự đổi sang mật khẩu hệ thống", Md.pw == "Vn@Lite#2026" and m is not None and any("đã đổi mật khẩu modem" in x for x in nk))
kt("nhật ký không in mật khẩu", not any("Vn@Lite#2026" in x for x in nk))
nk.clear()
m = M.chuan_bi("127.0.0.1", "admin", "Vn@Lite#2026", nk.append, C.pass_modem_yeu)
kt("lần sau: đăng nhập thẳng bằng mật khẩu đã lưu, không đổi gì", m is not None and len(nk) == 1 and "đã lưu" in nk[0])
ok, tb = m.them_nat("cam1", 8080, "192.168.1.200")
kt("thêm luật mở port qua trang modem + kiểm lại trong bảng", ok and Md.luat == [("cam1", 8080, "192.168.1.200")])
ok, tb = m.them_nat("cam1", 8080, "192.168.1.200")
kt("luật đã có → không thêm trùng", ok and len(Md.luat) == 1 and "đã có" in tb)
kt("khởi động lại modem", m.khoi_dong()[0] and Md.khoi_dong == 1)
Md.pw = "admin"; nk.clear()
m = M.chuan_bi("127.0.0.1", "admin", "admin123", nk.append, C.pass_modem_yeu)
kt("mật khẩu hệ thống còn yếu → KHÔNG đổi, báo rõ", Md.pw == "admin" and any("còn yếu" in x for x in nk))
Md.pw = "TemModem#77"
kt("mật khẩu trên tem khác cả hai → không vào, không đoán mò", M.chuan_bi("127.0.0.1", "admin", "Vn@Lite#2026", nk.append, C.pass_modem_yeu) is None)
Md.pw, Md.kieu_khac = "admin", True
kt("modem khác kiểu → đứng yên, không ra lệnh nào", M.chuan_bi("127.0.0.1", "admin", "Vn@Lite#2026", nk.append, C.pass_modem_yeu) is None and Md.pw == "admin")
print(f"\n✓ 2.9.0 modem iGate VNPT (giả lập): {dat}/{dat} đạt")
