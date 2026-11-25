"""Điều khiển modem qua trang quản trị web — có 2 trình: Bcm (iGate VNPT nền Broadcom) và Owrt (VNPT AX3000 GPON ONT nền OpenWrt/LuCI, qua ubus).
Trình Bcm cho modem iGate VNPT (GW020-H / GW040-H / GW240-H…),
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


class Owrt:
    """Modem nền OpenWrt / LuCI — vd VNPT "AX3000 Wireless Dual-Band GPON ONT" (mẫu điểm 4 Tà Lài mở rộng, 25/11/2026:
    trang chủ là trang Login riêng của VNPT, phía sau có /cgi-bin/luci và /ubus/).
    Điều khiển qua ubus JSON-RPC chuẩn OpenWrt: session.login → uci (firewall, kiểu 'redirect' = mở port).
    AN TOÀN: chỉ thêm luật khi tường lửa của modem ĐÚNG kiểu OpenWrt (có vùng wan + lan); thêm xong đọc lại để kiểm;
    không đổi mật khẩu, không đụng cấu hình khác. CHƯA kiểm trên modem thật — bước nào không qua thì báo rõ bước đó."""

    def __init__(self, host, user, pw, port=80, cho=8):
        self.goc = f"http://{host}:{port}" if int(port) != 80 else f"http://{host}"
        self.user, self.pw, self.cho = user or "admin", pw or "", cho
        self.sid, self.buoc = "", ""      # buoc: câu mô tả chỗ đang kẹt (ghi nhật ký)
        # Mẫu thật 25/11: modem tự chuyển http → https (cổng 443) với chứng chỉ TỰ KÝ → phải bỏ kiểm chứng chỉ (thiết bị trong mạng LAN)
        self.s = requests.Session()
        self.s.verify = False
        try:
            requests.packages.urllib3.disable_warnings()
        except Exception:
            pass

    def nhan_ra(self):
        try:
            r = self.s.get(f"{self.goc}/cgi-bin/luci", timeout=self.cho)      # theo chuyển hướng sang https
            la = "x-luci-login-required" in {k.lower() for k in r.headers} or "luci" in r.text[:3000].lower()
            if la:
                m = re.match(r"(https?://[^/]+)", r.url)
                if m:
                    self.goc = m.group(1)      # từ đây gọi thẳng địa chỉ modem thật sự trả lời (https)
            return la
        except requests.RequestException:
            return False

    def _ubus(self, doi_tuong, lenh, ts=None, sid=None):
        """Trả (mã ubus: 0 = đạt, dữ liệu). Mã -1 = modem không trả lời kiểu ubus."""
        than = {"jsonrpc": "2.0", "id": 1, "method": "call", "params": [sid or self.sid or "0" * 32, doi_tuong, lenh, ts or {}]}
        for duong in ("/ubus/", "/ubus", "/cgi-bin/luci/admin/ubus"):
            try:
                r = self.s.post(self.goc + duong, json=than, timeout=self.cho)
                j = r.json()
            except (requests.RequestException, ValueError):
                continue
            if isinstance(j, dict) and "error" in j:
                return int((j["error"] or {}).get("code", -2)), j["error"]
            kq = j.get("result") if isinstance(j, dict) else None
            if isinstance(kq, list) and kq:
                return int(kq[0]), (kq[1] if len(kq) > 1 else {})
        return -1, None

    def dang_nhap(self, pw=None):
        pw = self.pw if pw is None else pw
        ung = []
        for u in (self.user, "admin", "root"):
            if u and u not in ung:
                ung.append(u)
        for u in ung:      # 1) đăng nhập thẳng ubus
            ma, d = self._ubus("session", "login", {"username": u, "password": pw, "timeout": 600}, sid="0" * 32)
            if ma == 0 and isinstance(d, dict) and d.get("ubus_rpc_session"):
                self.sid, self.user = d["ubus_rpc_session"], u
                return True
            if ma == -1:
                break
        for u in ung:      # 2) đăng nhập form LuCI → cookie sysauth chính là mã phiên ubus
            try:
                r = self.s.post(f"{self.goc}/cgi-bin/luci", data={"luci_username": u, "luci_password": pw}, timeout=self.cho, allow_redirects=False)
            except requests.RequestException:
                break
            ck = next((v for k, v in r.cookies.items() if k.startswith("sysauth")), "")
            if ck:
                self.sid, self.user = ck, u
                return True
        self.buoc = "modem kiểu OpenWrt/LuCI nhưng không nhận user/pass modem đã lưu (hoặc cách đăng nhập khác chuẩn)"
        return False

    def vao_duoc(self, pw=None):
        return self.nhan_ra() and self.dang_nhap(pw)

    def tuong_lua(self):
        ma, d = self._ubus("uci", "get", {"config": "firewall"})
        if ma != 0 or not isinstance(d, dict):
            raise RuntimeError(f"tài khoản modem không được đọc cấu hình tường lửa (mã {ma})")
        return d.get("values") or {}

    def luat(self):
        out = []
        for v in self.tuong_lua().values():
            if v.get(".type") == "redirect" and str(v.get("enabled", "1")) != "0":
                try:
                    out.append((int(str(v.get("src_dport", "0")).split("-")[0].split(":")[0]), str(v.get("dest_ip", ""))))
                except ValueError:
                    pass
        return out

    def them_nat(self, ten, port, ip):
        fw = self.tuong_lua()
        vung = {str(v.get("name")) for v in fw.values() if v.get(".type") == "zone"}
        if not {"wan", "lan"} <= vung:
            return False, f"tường lửa modem không theo kiểu OpenWrt chuẩn (vùng có: {', '.join(sorted(vung)) or 'không có'}) → chưa mở port tự động được"
        co = self.luat()
        if (int(port), ip) in co:
            return True, f"modem đã có luật {port} → {ip}"
        if any(p == int(port) for p, _ in co):
            return False, f"port {port} trên modem đang trỏ về IP khác — kiểm tra lại bằng tay, app không ghi đè"
        ma, d = self._ubus("uci", "add", {"config": "firewall", "type": "redirect", "values": {
            "name": "camlink_" + re.sub(r"[^A-Za-z0-9_]", "_", ten), "target": "DNAT", "src": "wan", "dest": "lan", "proto": "tcp",
            "src_dport": str(port), "dest_ip": ip, "dest_port": str(port)}})
        if ma != 0:
            return False, f"modem không cho thêm luật mở port (mã {ma}) — tài khoản không đủ quyền"
        ma, _ = self._ubus("uci", "commit", {"config": "firewall"})
        if ma != 0:
            return False, f"modem không lưu được luật mở port (mã {ma})"
        ok = (int(port), ip) in self.luat()
        return ok, (f"đã thêm luật mở port {port} → {ip}" if ok else f"đã gửi luật {port} → {ip} nhưng đọc lại không thấy")


def chuan_bi(gw, user, pw, log=print, yeu=None):
    """Lúc cài điểm: modem còn mật khẩu xuất xưởng thì đổi sang mật khẩu của hệ thống. Trả đối tượng modem đã đăng nhập, hoặc None.
    yeu(user, pw) → True nếu mật khẩu hệ thống còn yếu (khi đó không đổi)."""
    m = Bcm(gw, user, pw)
    if m.vao_duoc():
        log("   ✔ Đăng nhập trang quản trị modem bằng mật khẩu đã lưu")
        return m
    o = Owrt(gw, user, pw)
    if o.nhan_ra():      # modem nền OpenWrt/LuCI (VNPT AX3000 GPON ONT…): chỉ đăng nhập bằng mật khẩu đã lưu, không đổi mật khẩu
        if o.dang_nhap():
            log(f"   ✔ Đăng nhập modem (kiểu OpenWrt/LuCI) bằng user «{o.user}» và mật khẩu đã lưu")
            return o
        log(f"   ✖ Modem kiểu OpenWrt/LuCI (VNPT AX3000…): {o.buoc} → nhập đúng user/pass modem ở 'User/pass riêng điểm này' rồi cài lại.")
        return None
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
