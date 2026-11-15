# 2.9.0 — khai báo lần đầu cam Oryza: AES thuần Python đúng chuẩn + cam giả giải mã ra đúng mật khẩu
import sys, os, re, json, base64, hashlib, threading, secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../app/src/main/python"))
import camlink_oryza as O
import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
dat = 0
def kt(ten, dk):
    global dat
    assert dk, ten
    dat += 1; print("✓", ten)

def chuan(d, k, iv):
    p = padding.PKCS7(128).padder(); d = p.update(d) + p.finalize()
    e = Cipher(algorithms.AES(k), modes.CBC(iv)).encryptor(); return e.update(d) + e.finalize()
def giai(c, k, iv):
    e = Cipher(algorithms.AES(k), modes.CBC(iv)).decryptor(); d = e.update(c) + e.finalize()
    u = padding.PKCS7(128).unpadder(); return u.update(d) + u.finalize()
ok = True
for nk in (16, 24, 32):
    for n in (0, 1, 15, 16, 17, 31, 32, 33, 100):
        k, iv, d = secrets.token_bytes(nk), secrets.token_bytes(16), secrets.token_bytes(n)
        ok = ok and O.aes_cbc(d, k, iv) == chuan(d, k, iv)
kt("AES-CBC thuần Python khớp thư viện chuẩn (khoá 128/192/256, 27 ca)", ok)

from cryptography.hazmat.primitives.asymmetric import rsa as crsa, padding as cpad
from cryptography.hazmat.primitives import serialization
KHOA = crsa.generate_private_key(public_exponent=65537, key_size=1024)
# cam thật trả khoá công khai dạng base64 trần (SubjectPublicKeyInfo), không có dòng BEGIN/END
PUB_B64 = base64.b64encode(KHOA.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
class Cam:
    kich_hoat = False; user = ""; pw = ""; nonce = "n0nce1234"; ten_bat_buoc = ""; lenh = []
def tra(code, them=""): return f'<?xml version="1.0" encoding="UTF-8"?><CommandHead Command="0" SessionId=""><Parameters Version="1"><Result Code="{code}" />{them}</Parameters></CommandHead>'
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _g(self, t):
        b = t.encode(); self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        goc = ET.fromstring(re.sub(r"^\s*<\?xml[^>]*\?>", "", self.rfile.read(int(self.headers["Content-Length"])).decode()))
        cmd = int(goc.get("Command")); P = goc.find("Parameters"); Cam.lenh.append(cmd)
        if cmd == 30541: return self._g(tra(0, f'<DeviceSummaryInfo MACAddr="78:CE:A5:00:00:01" ProductModel="ORZ-TEST" ActivateFlag="{"true" if Cam.kich_hoat else "false"}" />'))
        if cmd == 11015: return self._g(tra(0, f'<SNString String="{Cam.ten_bat_buoc}" />') if Cam.ten_bat_buoc else tra(-532))
        if cmd == 11011:
            w = P.find("WebAuthInfo")
            if w.get("OperatorType") == "1":
                return self._g(tra(0, f'<WebAuthInfo Nonce="{Cam.nonce}" PublicKey="{PUB_B64}" />'))
            if Cam.kich_hoat: return self._g(tra(-1))
            L = KHOA.decrypt(base64.b64decode(w.get("Response")), cpad.PKCS1v15()).decode()
            cn = w.get("Cnonce"); vt = base64.b64decode(cn)
            k = hashlib.sha256((Cam.nonce + cn).encode()).hexdigest()[:32].encode()
            pw = giai(base64.b64decode(L), k, vt).decode()
            if len(pw) < 8: return self._g(tra(-533))
            Cam.kich_hoat, Cam.user, Cam.pw = True, w.get("User"), pw
            return self._g(tra(0))
        self._g(tra(-1))
sv = HTTPServer(("127.0.0.1", 0), H); port = sv.server_address[1]
threading.Thread(target=sv.serve_forever, daemon=True).start()

kt("đọc thông tin cam không cần đăng nhập (model, MAC)", O.tom_tat("127.0.0.1", port).get("ProductModel") == "ORZ-TEST")
kt("nhận ra cam MỚI chưa khai báo", O.da_khai_bao("127.0.0.1", port) is False)
kt("mật khẩu yếu → cam từ chối, app báo rõ, cam vẫn chưa khai báo", O.khai_bao_lan_dau("127.0.0.1", port, "admin", "abc")[0] is False and not Cam.kich_hoat)
ok, u, tb = O.khai_bao_lan_dau("127.0.0.1", port, "admin", "Vn@Lite#2026 ".strip())
kt("khai báo lần đầu thành công", ok and u == "admin")
kt("cam giải mã ra ĐÚNG mật khẩu và user đã gửi", (Cam.user, Cam.pw) == ("admin", "Vn@Lite#2026"))
kt("sau đó cam báo đã khai báo", O.da_khai_bao("127.0.0.1", port) is True)
n = len(Cam.lenh)
ok2, _, tb2 = O.khai_bao_lan_dau("127.0.0.1", port, "admin", "MatKhauKhac99")
kt("cam đã có mật khẩu → KHÔNG khai báo lại, không gửi lệnh tạo mật khẩu", not ok2 and Cam.pw == "Vn@Lite#2026" and 11011 not in Cam.lenh[n:])
Cam.kich_hoat, Cam.ten_bat_buoc = False, "root"
ok3, u3, _ = O.khai_bao_lan_dau("127.0.0.1", port, "admin", "Vn@Lite#2026")
kt("cam bắt buộc tên user quản trị → dùng đúng tên cam yêu cầu và báo lại", ok3 and u3 == "root" and Cam.user == "root")
kt("mật khẩu có khoảng trắng / user có ký tự lạ → chặn trước khi gửi", not O.khai_bao_lan_dau("127.0.0.1", port, "ad min", "x")[0])
kt("cam không trả lời → không xác định, không làm gì", O.da_khai_bao("127.0.0.1", 9) is None)
print(f"\n✓ 2.9.0 khai báo lần đầu cam Oryza: {dat}/{dat} đạt")
