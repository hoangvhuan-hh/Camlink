"""Điều khiển modem qua trang quản trị web — hiện có trình cho modem iGate VNPT (GW020-H / GW040-H / GW240-H…),
giao diện "Advanced Setup → NAT → Virtual Servers" = nền firmware Broadcom CPE:
  - đăng nhập HTTP Basic; mỗi trang cấu hình nhúng `sessionKey` phải gửi kèm lệnh
  - mở port:      scvrtsrv.cmd?action=add&srvName=&dstWanIf=&srvAddr=&proto=1,&eStart=&eEnd=&iStart=&iEnd=&sessionKey=
  - đổi mật khẩu: password.cgi?inUserName=&inPassword=&inOrgPassword=&sessionKey=
  - khởi động lại: rebootinfo.cgi?sessionKey=
NGUYÊN TẮC AN TOÀN: chỉ ra lệnh khi trang của modem ĐÚNG dấu hiệu nền này; việc nào cũng kiểm lại kết quả; không đúng kiểu thì đứng yên
(app vẫn mở port bằng UPnP như cũ). Chưa có modem thật để kiểm — lần chạy đầu ở hiện trường app tự thu mẫu nếu modem khác kiểu."""
import re
import requests

MAT_KHAU_XUAT_XUONG = [("admin", "admin")]      # thử tối đa vài cặp để không làm modem khoá đăng nhập


class Bcm:
    def __init__(self, host, user, pw, port=80, cho=8):
        self.goc = f"http://{host}:{port}" if int(port) != 80 else f"http://{host}"
        self.user, self.pw, self.cho = user or "admin", pw or "", cho

    def _lay(self, duong, pw=None):
        return requests.get(f"{self.goc}/{duong}", auth=(self.user, self.pw if pw is None else pw), timeout=self.cho)

    def vao_duoc(self, pw=None):
        """Đăng nhập được và ĐÚNG kiểu modem này (trang mở port có sessionKey / lệnh scvrtsrv)."""
        try:
            r = self._lay("scvrtsrv.html", pw)
            return r.status_code == 200 and ("sessionKey" in r.text or "scvrtsrv" in r.text)
        except requests.RequestException:
            return False

    def _khoa(self, trang):
        t = self._lay(trang).text
        m = re.search(r"sessionKey\s*=\s*'?\"?(\d+)", t)
        if not m:
            raise RuntimeError(f"trang {trang} của modem không có sessionKey — modem khác kiểu")
        return m.group(1), t

    def cong_wan(self, t):
        ds = re.findall(r"<option[^>]*value=['\"]([^'\"]+)['\"]", t)
        ds = [x for x in ds if re.match(r"(ppp|ipoe|veip|eth|atm|ptm|epon|gpon|wan)", x, re.I)]
        return ds[0] if ds else ""

    def luat(self):
        """[(cổng ngoài, IP trong)] các luật mở port đang có."""
        t = self._lay("scvrtsrv.html").text
        out = []
        for hang in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S | re.I):
            o = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", hang, re.S | re.I)]
            ip = next((x for x in o if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", x)), "")
            so = [int(x) for x in o if x.isdigit()]
            if ip and so:
                out.append((so[0], ip))
        return out

    def them_nat(self, ten, port, ip):
        if (int(port), ip) in self.luat():
            return True, f"modem đã có luật {port} → {ip}"
        k, t = self._khoa("scvrtsrv.html")
        r = self._lay("scvrtsrv.cmd?action=add&srvName=" + requests.utils.quote(ten) + f"&dstWanIf={self.cong_wan(t)}&srvAddr={ip}"
                      f"&proto=1,&eStart={port},&eEnd={port},&iStart={port},&iEnd={port},&sessionKey={k}")
        ok = (int(port), ip) in self.luat()
        return ok, (f"đã thêm luật mở port {port} → {ip}" if ok else f"modem không nhận luật {port} → {ip} (mã {r.status_code})")

    def doi_mat_khau(self, moi):
        """Đổi mật khẩu quản trị rồi KIỂM: mật khẩu mới vào được mới báo xong."""
        k, _ = self._khoa("password.html")
        self._lay("password.cgi?inUserName=" + requests.utils.quote(self.user) + "&inPassword=" + requests.utils.quote(moi)
                  + "&inOrgPassword=" + requests.utils.quote(self.pw) + f"&sessionKey={k}")
        if self.vao_duoc(moi):
            self.pw = moi
            return True, "đã đổi mật khẩu modem sang mật khẩu của hệ thống (đã đăng nhập thử bằng mật khẩu mới)"
        if self.vao_duoc():
            return False, "modem không nhận lệnh đổi mật khẩu — mật khẩu cũ vẫn dùng được, chưa đổi gì"
        return False, "ĐÃ GỬI lệnh đổi mật khẩu nhưng cả mật khẩu cũ lẫn mới đều chưa vào được — thử lại sau 1 phút; vẫn không được thì reset modem"

    def khoi_dong(self):
        k, _ = self._khoa("resetrouter.html")
        self._lay(f"rebootinfo.cgi?sessionKey={k}")
        return True, "đã gửi lệnh khởi động lại modem — chờ khoảng 2 phút"


def chuan_bi(gw, user, pw, log=print, yeu=None):
    """Lúc cài điểm: modem còn mật khẩu xuất xưởng thì đổi sang mật khẩu của hệ thống. Trả đối tượng modem đã đăng nhập, hoặc None.
    yeu(user, pw) → True nếu mật khẩu hệ thống còn yếu (khi đó không đổi)."""
    m = Bcm(gw, user, pw)
    if m.vao_duoc():
        log("   ✔ Đăng nhập trang quản trị modem bằng mật khẩu đã lưu")
        return m
    for u0, p0 in MAT_KHAU_XUAT_XUONG:
        if (u0, p0) == (user, pw):
            continue
        m0 = Bcm(gw, u0, p0)
        if not m0.vao_duoc():
            continue
        if yeu and yeu(user, pw):
            log("   ⚠ Modem còn mật khẩu xuất xưởng; mật khẩu modem đang lưu trong app còn yếu nên CHƯA đổi — nhập mật khẩu mạnh rồi chạy lại.")
            return m0
        if u0 != user:
            log(f"   ⚠ Modem dùng user «{u0}», app đang lưu «{user}» → giữ user «{u0}», chỉ đổi mật khẩu; sửa User modem trong app cho khớp.")
        try:
            ok, tb = m0.doi_mat_khau(pw)
        except Exception as e:
            ok, tb = False, f"đổi mật khẩu modem lỗi: {str(e)[:80]}"
        log(f"   {'✔' if ok else '✖'} Modem còn mật khẩu xuất xưởng → {tb}")
        return m0
    return None
