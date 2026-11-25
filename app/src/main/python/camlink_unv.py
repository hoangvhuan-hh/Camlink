"""Trình cắm cam Uniview (UNV) — giao thức LAPI (JSON qua HTTP, xác thực Digest).

NGUỒN (25/11/2026): tài liệu LightAPI của Uniview + mã giao diện web Uniview công khai
(ComScript: Port_Cfg = /LAPI/V1.0/NetWork/Port, DDNS_Cfg = /LAPI/V1.0/NetWork/DDNS,
Users_Cfg = /LAPI/V1.0/Channel/0/System/Users, SecurityRSA = /LAPI/V1.0/System/Security/RSA).
CHƯA kiểm trên cam UNV thật của Huan (IPC2B25SS-ADZK-I1) → mọi bước đều thử vài biến thể đường dẫn,
ghi nhật ký rõ từng bước; sai thì báo đúng chỗ để sửa theo mẫu thật, không âm thầm bỏ qua.

Mật khẩu (user cam, DDNS) gửi lên cam: RSA PKCS#1 v1.5 bằng khoá công khai của cam, rồi base64 —
đúng như hàm Utils.encrypting của web Uniview (encryptedString có đệm 00 02 … 00).
"""
import base64
import json
import time

import requests
import rsa
from requests.auth import HTTPDigestAuth

USER_MAC_DINH, PASS_MAC_DINH = "admin", "123456"      # tài khoản xuất xưởng của Uniview


def _url(ip, port, duong):
    return f"http://{ip}{'' if int(port) == 80 else ':' + str(port)}{duong}"


def la_unv(ip, port):
    """Nhận ra cam Uniview mà KHÔNG cần mật khẩu. Chỉ đọc."""
    try:
        r = requests.get(_url(ip, port, "/LAPI/V1.0/System/DeviceBasicInfo"), timeout=4)
    except requests.RequestException:
        return False
    if "/LAPI/" in r.text or '"ResponseCode"' in r.text:
        return True
    if r.status_code == 401:      # cam bắt đăng nhập cho /LAPI/… nhưng đường dẫn lạ thì không → đúng là có dịch vụ LAPI
        try:
            la = requests.get(_url(ip, port, "/khong-co-trang-nay-camlink"), timeout=4)
            if la.status_code != 401:
                return True
        except requests.RequestException:
            pass
    return False


class Lapi:
    def __init__(self, ip, port, user, pw):
        self.ip, self.port, self.user = ip, port, user
        self.s = requests.Session()
        self.s.auth = HTTPDigestAuth(user, pw)

    def goi(self, cach, duong, du_lieu=None, cho=8):
        """Trả (mã HTTP, mã LAPI (0 = đạt, None = không đọc được), Data, chữ thô)."""
        try:
            r = self.s.request(cach, _url(self.ip, self.port, duong), timeout=cho,
                               data=None if du_lieu is None else (json.dumps(du_lieu) + "\r\n").encode(),
                               headers={"Content-Type": "application/json; charset=UTF-8"})
        except requests.RequestException as e:
            return 0, None, None, str(e)[:120]
        try:
            j = r.json()
            tra = j.get("Response", j) if isinstance(j, dict) else {}
            ma = tra.get("ResponseCode", tra.get("StatusCode"))
            return r.status_code, ma, tra.get("Data"), r.text[:300]
        except ValueError:
            return r.status_code, None, None, r.text[:300]

    def doc(self, *cac_duong):
        """GET lần lượt các biến thể đường dẫn; trả (đường dẫn dùng được, Data) hoặc (None, lý do)."""
        ly_do = ""
        for d in cac_duong:
            http, ma, data, tho = self.goi("GET", d)
            if http == 200 and ma == 0 and data is not None:
                return d, data
            ly_do = f"{d} → HTTP {http}, mã {ma}"
            if http == 401:
                break
        return None, ly_do

    def vao_duoc(self):
        """Thử ĐÚNG MỘT lệnh (cam UNV khoá tài khoản khi nhập sai nhiều lần — mẫu thật 25/11: StatusString "UserLocked").
        True = đăng nhập đúng · False = cam từ chối user/pass · "khoa" = cam đang khoá đăng nhập · None = không rõ."""
        http, ma, data, tho = self.goi("GET", "/LAPI/V1.0/NetWork/Port")
        if "lock" in tho.lower():
            return "khoa"
        if http == 200 and ma == 0:
            return True
        if http == 401 or any(x in tho.lower() for x in ("unauthor", "not authorized", "password", "passwd", "auth")):
            return False
        return None

    def khoa_rsa(self):
        d, data = self.doc("/LAPI/V1.0/System/Security/RSA")
        if not d:
            raise RuntimeError(f"không lấy được khoá RSA của cam ({data})")
        return data["RSAPublicKeyE"], data["RSAPublicKeyN"]

    def ma_hoa(self, chu):
        e, n = self.khoa_rsa()
        ban_ma = rsa.encrypt(chu.encode(), rsa.PublicKey(int(n, 16), int(e, 16)))
        return base64.b64encode(ban_ma).decode(), {"RSAPublicKeyE": e, "RSAPublicKeyN": n}


def khai_bao_lan_dau(ip, port, cam_user, cam_pw, log=print):
    """Cam UNV còn mật khẩu xuất xưởng (admin/123456) → đổi sang mật khẩu cam của hệ thống.
    Trả (trạng thái, user dùng được, câu báo). Trạng thái: 'san' đã vào được bằng user/pass đã lưu ·
    'moi' vừa đổi mật khẩu xuất xưởng xong · 'sai' cam từ chối · 'khoa' cam đang khoá đăng nhập · 'loi' việc khác.
    Mỗi cặp user/pass chỉ thử MỘT lần (tối đa 3 lần sai) để không làm cam khoá tài khoản."""
    CAU_KHOA = ("cam UNV đang KHOÁ đăng nhập vì bị nhập sai mật khẩu nhiều lần → chờ khoảng 10 phút hoặc tắt/bật nguồn cam rồi cài lại; "
                "nếu cam này đã đặt mật khẩu riêng thì nhập đúng ở 'User/pass riêng điểm này'")
    vao = Lapi(ip, port, cam_user, cam_pw).vao_duoc()
    if vao is True:
        return "san", cam_user, "user/pass cam đã lưu vào được"
    if vao == "khoa":
        return "khoa", cam_user, CAU_KHOA
    if vao is None:
        return "loi", cam_user, ("cam UNV không trả lời lệnh LAPI app biết (đời cam/firmware khác) → "
                                 "bấm 'Thu mẫu thiết bị' gửi Claude; trước mắt đặt mật khẩu và DDNS bằng tay trên web cam")
    md = Lapi(ip, port, USER_MAC_DINH, PASS_MAC_DINH)
    vao = md.vao_duoc() if (cam_user, cam_pw) != (USER_MAC_DINH, PASS_MAC_DINH) else False
    if vao == "khoa":
        return "khoa", cam_user, CAU_KHOA
    if vao is not True:
        if cam_user != USER_MAC_DINH and Lapi(ip, port, USER_MAC_DINH, cam_pw).vao_duoc() is True:
            return "san", USER_MAC_DINH, f"cam vào được bằng user «{USER_MAC_DINH}» với mật khẩu đã lưu"
        return "sai", cam_user, ("cam UNV từ chối cả user/pass đã lưu lẫn mật khẩu xuất xưởng (admin/123456) → cam đã bị đặt mật khẩu khác: "
                                  "nhập đúng user/pass cam cho điểm này, hoặc reset cam về xuất xưởng rồi cài lại")
    if cam_pw == PASS_MAC_DINH:
        return "san", USER_MAC_DINH, "cam đang dùng mật khẩu xuất xưởng, trùng mật khẩu đã lưu"
    try:
        d, data = md.doc("/LAPI/V1.0/Channel/0/System/Users", "/LAPI/V1.0/Channels/0/System/Users", "/LAPI/V1.0/System/Users")
        if not d:
            return "loi", USER_MAC_DINH, f"không đọc được danh sách user của cam ({data})"
        nguoi = next((u for u in data.get("Users", []) if str(u.get("Name")) == USER_MAC_DINH), None)
        if nguoi is None:
            return "loi", USER_MAC_DINH, "cam không có user admin trong danh sách"
        ban_ma, khoa = md.ma_hoa(cam_pw)
        moi = dict(nguoi)
        moi.update(Passwd=ban_ma, RSAPublicKey=khoa)
        http, ma, _, tho = md.goi("PUT", f"{d}/Users/{nguoi.get('ID')}", moi)
        if not (http == 200 and ma == 0):
            return "loi", USER_MAC_DINH, f"cam không nhận mật khẩu mới (HTTP {http}, mã {ma}: {tho[:100]}) — mật khẩu có thể chưa đủ mạnh theo yêu cầu của cam"
        time.sleep(2)
        if Lapi(ip, port, USER_MAC_DINH, cam_pw).vao_duoc() is True:
            return "moi", USER_MAC_DINH, "cam UNV còn mật khẩu xuất xưởng → đã đổi sang mật khẩu cam của hệ thống"
        return "loi", USER_MAC_DINH, "đã gửi mật khẩu mới nhưng đăng nhập lại chưa được"
    except Exception as e:
        return "loi", USER_MAC_DINH, f"đổi mật khẩu lần đầu lỗi: {str(e)[:120]}"


def dat_ddns(ip, port, user, pw, domain, ddns_user, ddns_pw):
    """Bật DDNS No-IP trên cam UNV và nhập tên miền + user/pass. Trả câu kết quả; lỗi thì raise RuntimeError."""
    c = Lapi(ip, port, user, pw)
    d, cfg = c.doc("/LAPI/V1.0/NetWork/DDNS", "/LAPI/V1.0/Network/DDNS", "/LAPI/V1.0/Channel/0/NetWork/DDNS")
    if not d:
        raise RuntimeError(f"UNV: không đọc được cấu hình DDNS ({cfg}) — bấm 'Thu mẫu thiết bị' gửi Claude")
    ds = cfg.get("DDNSs") or []
    def la_noip(x):
        t = (str(x.get("TypeName", "")) + " " + str(x.get("ServerName", ""))).lower().replace("-", "").replace(" ", "")
        return "noip" in t
    muc = next((x for x in ds if la_noip(x)), None)
    if muc is None:
        ten = ", ".join(str(x.get("TypeName", x.get("Type"))) for x in ds) or "không có loại nào"
        raise RuntimeError(f"UNV: cam không có loại DDNS No-IP (cam có: {ten})")
    da_dung = (str(cfg.get("UsedType")) == str(muc.get("Type")) and str(muc.get("DeviceDomain", "")).lower() == domain.lower()
               and str(muc.get("UserName", "")) == ddns_user and int(cfg.get("Enable", cfg.get("Enabled", 0)) or 0) == 1)
    khoa_bat = "Enabled" if ("Enabled" in cfg and "Enable" not in cfg) else "Enable"
    cfg[khoa_bat] = 1
    cfg["UsedType"] = muc.get("Type")
    muc["DeviceDomain"] = domain
    muc["UserName"] = ddns_user
    if not str(muc.get("ServerName", "")).strip():
        muc["ServerName"] = "dynupdate.no-ip.com"
    if ddns_pw:
        muc["PassWord"], cfg["RSAPublicKey"] = c.ma_hoa(ddns_pw)
    http, ma, _, tho = c.goi("PUT", d, cfg)
    if not (http == 200 and ma == 0):
        raise RuntimeError(f"UNV: cam không nhận cấu hình DDNS (HTTP {http}, mã {ma}: {tho[:100]})")
    _, sau = c.doc(d)
    if isinstance(sau, dict):
        m2 = next((x for x in (sau.get("DDNSs") or []) if str(x.get("Type")) == str(muc.get("Type"))), {})
        if str(m2.get("DeviceDomain", "")).lower() != domain.lower() or str(sau.get("UsedType")) != str(muc.get("Type")):
            raise RuntimeError("UNV: đã gửi DDNS nhưng đọc lại không thấy tên miền trên cam")
    return f"DDNS No-IP đã nhập trên cam UNV: {domain}" + (" (trước đó đã đúng, nhập lại mật khẩu)" if da_dung else "")


def dat_port(ip, port, user, pw, http_moi, rtsp_moi):
    """Dự phòng khi ONVIF không đổi được port: đặt port HTTP/RTSP qua LAPI. Cam tự khởi động lại nếu đổi RTSP."""
    c = Lapi(ip, port, user, pw)
    d, cfg = c.doc("/LAPI/V1.0/NetWork/Port", "/LAPI/V1.0/Network/Port")
    if not d:
        raise RuntimeError(f"UNV: không đọc được cấu hình port ({cfg})")
    cfg["HttpPort"], cfg["RtspPort"] = int(http_moi), int(rtsp_moi)
    http, ma, _, tho = c.goi("PUT", d, cfg)
    if not (http in (200, 0) and ma in (0, None)):      # cam có thể cắt kết nối ngay khi đổi port → HTTP 0 vẫn có thể là đã nhận
        raise RuntimeError(f"UNV: cam không nhận port mới (HTTP {http}, mã {ma}: {tho[:100]})")
