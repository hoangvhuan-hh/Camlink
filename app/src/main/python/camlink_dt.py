# -*- coding: utf-8 -*-
"""CamLink điện thoại — chạy trên Android (Termux) hoặc laptop. Chỉ cần Python + requests.

  python camlink_dt.py          → hỏi: số điểm, user/pass cam, user/pass modem → tự làm hết
  python camlink_dt.py thu      → thu mẫu thiết bị (không đổi gì), lưu zip vào thư mục Download

Tự làm: tìm cam trong mạng → DDNS (cam 1) → port HTTP/RTSP → gateway, DNS → IP tĩnh
→ mở port trên modem (UPnP) → kiểm tra IP WAN, CGNAT, tên miền.
Quy ước VINA LITE: cam1 .200 8080/554 · cam2 .201 8081/5541 · cam3 .202 8082/5542.
"""
import base64, datetime, hashlib, ipaddress, json, os, re, socket, sys, time, zipfile
from concurrent.futures import ThreadPoolExecutor

try:
    import requests
    from requests.auth import HTTPDigestAuth
except ImportError:
    sys.exit("Thiếu thư viện: chạy  pip install requests  rồi chạy lại.")
requests.packages.urllib3.disable_warnings()
import camlink_oryza

HTTP = [8080, 8081, 8082, 8083, 8084, 8085]
RTSP = [554, 5541, 5542, 5543, 5544, 5545]
IP_TU = 200
PORT_QUET = [80, 8080, 8081, 8082, 8083, 8084, 8085]
PORT_WEB_MODEM = 8098      # port ngoài dẫn vào trang quản trị modem (để sửa modem từ xa)
PASS_MODEM_YEU = ("", "admin", "password", "user", "root", "1234", "12345", "123456", "1234567", "12345678", "123456789", "admin123", "vnpt", "megavnn")


def pass_modem_yeu(user, pw):
    """Mật khẩu modem còn mặc định / dễ đoán → KHÔNG được mở trang quản trị ra Internet."""
    pw = str(pw or "")
    return len(pw) < 8 or pw.lower() in PASS_MODEM_YEU or pw.lower() == str(user or "").lower()

# Dữ liệu file ks_Camera_Xa_Phu_Ly.xlsx (số điểm: tên, tên miền, user/pass DDNS, số cam)
PHU_LY = {}  # app Android nạp từ file khảo sát người dùng chọn (không nhúng mật khẩu vào APK)


def thu_muc_ra():
    for p in ("/sdcard/Download", os.path.expanduser("~/storage/downloads"), os.path.expanduser("~/Downloads")):
        if os.path.isdir(p):
            return p
    return os.getcwd()


NHAT_KY = []
CAN_MAU = []
KQ_CUOI = {}   # thiết bị app chưa biết cách điều khiển → tự thu mẫu cuối lượt
TM_LECH = {}          # cam đang dùng tên miền KHÁC tên miền app lưu cho điểm: {"stt", "cam", "app"} → app hỏi người dùng, không tự ghi đè
GHI_DE_DDNS = False   # người dùng đã chọn "ghi tên miền của điểm lên cam" → lượt chạy kế ghi đè (dùng một lần)
DUNG_VI_MAT_MODEM = False   # màn hình báo: mất kết nối modem quá 2 phút → dừng các vòng chờ
LY_DO_0CAM = {}   # lượt cài ra 0 cam: {"stt", "ly_do": [câu lý do + việc cần làm]} — màn sơ đồ hiện ra


def ten_file(s):
    return re.sub(r"[^\w.-]", "_", s) or "goc"


LOG_CB = None   # app Android gắn hàm nhận nhật ký vào đây
GW = None       # app Android truyền gateway thật (từ WiFi)


def log(s=""):
    if LOG_CB:
        LOG_CB(str(s))
    else:
        print(s, flush=True)
    NHAT_KY.append(s)


# ------------------------------------------------------------------ mạng
def ip_may():
    if os.environ.get("CAMLINK_MAY"):
        return os.environ["CAMLINK_MAY"]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "192.168.1.100"
    finally:
        s.close()


def mo(host, port, cho=0.7):
    try:
        with socket.create_connection((host, port), timeout=cho):
            return True
    except OSError:
        return False


def quet(mang, bo_qua):
    hosts = [str(h) for h in ipaddress.ip_network(mang, strict=False).hosts() if str(h) not in bo_qua]
    viec = [(h, p) for h in hosts for p in PORT_QUET]
    with ThreadPoolExecutor(128) as ex:
        kq = list(ex.map(lambda hp: hp if mo(*hp, 0.5) else None, viec))
    tim = {}
    for hp in kq:
        if hp:
            tim.setdefault(hp[0], hp[1])
    return tim


def cho_len(ip, port, giay=120):
    het = time.time() + giay
    while time.time() < het:
        if mo(ip, port, 1):
            return True
        if DUNG_VI_MAT_MODEM:
            return False
        time.sleep(3)
    return False


def ten_mien_tren_cam(nt, ip, port, user, pw):
    """Chỉ ĐỌC: tên miền DDNS đang bật trên cam ('' nếu không có / hãng chưa đọc được)."""
    try:
        if nt == "unv":
            import camlink_unv
            return camlink_unv.doc_ddns(ip, port, user, pw)
        if nt == "oryza":
            d = camlink_oryza.doc_ddns_cam(ip, port, user, pw)
            return str(d.get("ten_mien") or "").strip().lower() if d.get("bat") else ""
    except Exception:
        pass
    return ""


# ------------------------------------------------------------------ ONVIF (chuẩn chung camera IP)
NS = ('xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:tds="http://www.onvif.org/ver10/device/wsdl" '
      'xmlns:tt="http://www.onvif.org/ver10/schema" xmlns:trt="http://www.onvif.org/ver10/media/wsdl"')


def _x(v):
    return (str(v).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", '&apos;'))


class Onvif:
    def __init__(self, ip, port, user, pw):
        self.ip, self.port, self.user, self.pw = ip, port, user, pw
        self.lech = datetime.timedelta(0)

    @property
    def url(self):
        return f"http://{self.ip}:{self.port}/onvif/device_service"

    def _bao_mat(self):
        nonce = os.urandom(16)
        created = (datetime.datetime.utcnow() + self.lech).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        dg = base64.b64encode(hashlib.sha1(nonce + created.encode() + self.pw.encode()).digest()).decode()
        return ('<s:Header><Security s:mustUnderstand="1" xmlns="http://docs.oasis-open.org/wss/2004/01/'
                'oasis-200401-wss-wssecurity-secext-1.0.xsd"><UsernameToken><Username>' + self.user +
                '</Username><Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-'
                'token-profile-1.0#PasswordDigest">' + dg + '</Password><Nonce EncodingType="http://docs.oasis-'
                'open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">' +
                base64.b64encode(nonce).decode() + '</Nonce><Created xmlns="http://docs.oasis-open.org/wss/2004/'
                '01/oasis-200401-wss-wssecurity-utility-1.0.xsd">' + created + '</Created></UsernameToken>'
                '</Security></s:Header>')

    def goi(self, than, xac_thuc=True, cho=8, url=None):
        env = f'<?xml version="1.0" encoding="UTF-8"?><s:Envelope {NS}>' + \
              (self._bao_mat() if xac_thuc else "") + f"<s:Body>{than}</s:Body></s:Envelope>"
        r = requests.post(url or self.url, data=env.encode(), timeout=cho,
                          headers={"Content-Type": "application/soap+xml; charset=utf-8"})
        if r.status_code != 200 or "Fault" in r.text[:3000]:
            ly_do = re.search(r"<[^>]*Text[^>]*>(.*?)</", r.text)
            raise RuntimeError(f"ONVIF {r.status_code}: {ly_do.group(1) if ly_do else r.text[:120]}")
        return r.text

    def co(self):
        try:
            t = self.goi("<tds:GetSystemDateAndTime/>", xac_thuc=False, cho=8)   # cam Oryza đo thật có lúc trả lời 3 giây
        except Exception:
            return False
        if "DateTime" not in t:   # trả 200 nhưng không phải cam ONVIF (vd web modem)
            return False
        try:
            g = lambda k: int(re.search(rf"<[^>]*{k}>(\d+)<", t.split("UTCDateTime")[1]).group(1))
            cam = datetime.datetime(g("Year"), g("Month"), g("Day"), g("Hour"), g("Minute"), g("Second"))
            self.lech = cam - datetime.datetime.utcnow()
        except Exception:
            pass
        return True


    # ---- Quản lý tài khoản theo ONVIF CHUẨN (đa hãng) ----
    def ds_user(self):
        """GetUsers → [{ten, muc}] (muc: Administrator/Operator/User)."""
        t = self.goi("<tds:GetUsers/>")
        ra = []
        for kh in re.findall(r"<[^>]*User>(.*?)</[^>]*User>", t, re.S):
            ten = (re.search(r"<[^>]*Username>(.*?)<", kh) or [None, ""])[1]
            muc = (re.search(r"<[^>]*UserLevel>(.*?)<", kh) or [None, ""])[1]
            if ten:
                ra.append({"ten": ten, "muc": muc})
        return ra

    def _than_user(self, lenh, ten, pw=None, muc=None):
        u = f"<tt:Username>{_x(ten)}</tt:Username>"
        if pw is not None:
            u += f"<tt:Password>{_x(pw)}</tt:Password>"
        if muc is not None:
            u += f"<tt:UserLevel>{muc}</tt:UserLevel>"
        return f"<tds:{lenh}><tds:User>{u}</tds:User></tds:{lenh}>"

    def tao_user(self, ten, pw, muc="User"):
        """CreateUsers — tài khoản Xem cho khách = muc 'User' (chỉ xem)."""
        self.goi(self._than_user("CreateUsers", ten, pw, muc))
        return True

    def doi_mat_khau(self, ten, pw, muc="Administrator"):
        """SetUser — đổi mật khẩu tài khoản đã có (xoay mật khẩu admin)."""
        self.goi(self._than_user("SetUser", ten, pw, muc))
        return True

    def xoa_user(self, ten):
        self.goi(f"<tds:DeleteUsers><tds:Username>{_x(ten)}</tds:Username></tds:DeleteUsers>")
        return True

    def thong_tin(self):
        t = self.goi("<tds:GetDeviceInformation/>")
        g = lambda k: (re.search(rf"<[^>]*{k}>(.*?)<", t) or [None, ""])[1]
        return {"hang": g("Manufacturer"), "model": g("Model"), "serial": g("SerialNumber"), "firmware": g("FirmwareVersion")}

    def token_mang(self):
        t = self.goi("<tds:GetNetworkInterfaces/>")
        m = re.search(r'NetworkInterfaces[^>]*token="([^"]+)"', t)
        mac = re.search(r"<[^>]*HwAddress>(.*?)<", t)
        return (m.group(1) if m else "eth0"), (mac.group(1) if mac else "")

    # ---- Media: ảnh chụp + luồng video (dùng để CHỨNG MINH cam xem được qua tên miền) ----
    def _doi_host(self, u, port):
        """Cam trả địa chỉ LAN (192.168.x.x) → thay bằng host/port mình đang gọi (tên miền)."""
        return re.sub(r"^(\w+://)(?:[^@/]*@)?[^/:]+(?::\d+)?", lambda m: f"{m.group(1)}{self.ip}:{port}", u, count=1)

    def url_media(self):
        try:
            t = self.goi('<tds:GetCapabilities><tds:Category>Media</tds:Category></tds:GetCapabilities>')
            m = re.search(r"<[^>]*Media[^>]*>.*?<[^>]*XAddr>(.*?)<", t, re.S)
            if m:
                return self._doi_host(m.group(1).strip(), self.port)
        except Exception:
            pass
        return f"http://{self.ip}:{self.port}/onvif/media_service"

    def profile_dau(self, url_media):
        return self.ds_profile(url_media)[0]

    def nhat_ky(self):
        """Nhật ký hệ thống của cam (ONVIF GetSystemLog) — để biết cam có khởi động lại không. Cam không hỗ trợ → lỗi."""
        t = self.goi('<tds:GetSystemLog><tds:LogType>System</tds:LogType></tds:GetSystemLog>', cho=10)
        m = re.search(r"<(?:\w+:)?String>(.*?)</(?:\w+:)?String>", t, re.S)
        if m:
            import html
            return html.unescape(m.group(1))
        m = re.search(r"<(?:\w+:)?Include[^>]*>|<(?:\w+:)?Binary>(.*?)</", t, re.S)
        raise RuntimeError("cam không trả nhật ký dạng chữ")

    def ds_profile(self, url_media):
        """Mọi profile video (profile 1 = luồng chính, profile 2 thường = luồng phụ). Lưu lại để lấy luồng phụ không phải hỏi cam lần nữa."""
        t = self.goi("<trt:GetProfiles/>", url=url_media)
        ds = re.findall(r'Profiles[^>]*token="([^"]+)"', t)
        if not ds:
            raise RuntimeError("cam không có profile video")
        self.profiles = ds
        return ds

    def anh_chup(self, url_media, token):
        t = self.goi(f"<trt:GetSnapshotUri><trt:ProfileToken>{token}</trt:ProfileToken></trt:GetSnapshotUri>", url=url_media)
        m = re.search(r"<(?:\w+:)?Uri>\s*(.*?)\s*<", t)
        if not m:
            raise RuntimeError("cam không cho lấy ảnh chụp")
        u = self._doi_host(m.group(1).replace("&amp;", "&"), self.port)
        for au in (HTTPDigestAuth(self.user, self.pw), (self.user, self.pw)):
            r = requests.get(u, auth=au, timeout=12)
            if r.status_code == 200 and r.content[:2] == b"\xff\xd8":
                return r.content
        raise RuntimeError(f"lấy ảnh lỗi {r.status_code}")

    def luong_video(self, url_media, token, rtsp_port):
        t = self.goi(f"<trt:GetStreamUri><trt:StreamSetup><tt:Stream>RTP-Unicast</tt:Stream><tt:Transport>"
                     f"<tt:Protocol>RTSP</tt:Protocol></tt:Transport></trt:StreamSetup><trt:ProfileToken>{token}"
                     f"</trt:ProfileToken></trt:GetStreamUri>", url=url_media)
        m = re.search(r"<(?:\w+:)?Uri>\s*(.*?)\s*<", t)
        if not m:
            raise RuntimeError("cam không trả luồng RTSP")
        u = self._doi_host(m.group(1).replace("&amp;", "&"), rtsp_port)
        return u.replace("rtsp://", f"rtsp://{requests.utils.quote(self.user)}:{requests.utils.quote(self.pw)}@", 1)

    def dat_port(self, http, rtsp):
        self.goi("<tds:SetNetworkProtocols>"
                 f"<tds:NetworkProtocols><tt:Name>HTTP</tt:Name><tt:Enabled>true</tt:Enabled><tt:Port>{http}</tt:Port></tds:NetworkProtocols>"
                 f"<tds:NetworkProtocols><tt:Name>RTSP</tt:Name><tt:Enabled>true</tt:Enabled><tt:Port>{rtsp}</tt:Port></tds:NetworkProtocols>"
                 "</tds:SetNetworkProtocols>")

    def doc_port(self):
        t = self.goi("<tds:GetNetworkProtocols/>")
        kq = {}
        for ten, port in re.findall(r"<(?:\w+:)?Name>\s*(\w+)\s*</(?:\w+:)?Name>.*?<(?:\w+:)?Port>\s*(\d+)", t, re.S):
            kq.setdefault(ten.upper(), int(port))
        return kq

    def doc_gw_dns(self):
        """Đọc gateway + DNS đang đặt trong cam (chỉ đọc)."""
        gw = dns = ""
        try:
            t = self.goi("<tds:GetNetworkDefaultGateway/>")
            m = re.search(r"<(?:\w+:)?IPv4Address>\s*([\d.]+)", t)
            gw = m.group(1) if m else ""
        except Exception:
            pass
        try:
            t = self.goi("<tds:GetDNS/>")
            dns = ", ".join(re.findall(r"<(?:\w+:)?IPv4Address>\s*([\d.]+)", t))
        except Exception:
            pass
        return gw, dns

    def khoi_dong(self):
        try:
            self.goi("<tds:SystemReboot/>", cho=6)
        except requests.RequestException:
            pass   # cam khởi động lại ngay, có thể cắt kết nối trước khi trả lời

    def dat_gw_dns(self, gw, dns="8.8.8.8"):
        self.goi(f"<tds:SetNetworkDefaultGateway><tds:IPv4Address>{gw}</tds:IPv4Address></tds:SetNetworkDefaultGateway>")
        self.goi("<tds:SetDNS><tds:FromDHCP>false</tds:FromDHCP><tds:DNSManual><tt:Type>IPv4</tt:Type>"
                 f"<tt:IPv4Address>{dns}</tt:IPv4Address></tds:DNSManual></tds:SetDNS>")

    def dat_ip(self, token, ip):
        t = self.goi(f"<tds:SetNetworkInterfaces><tds:InterfaceToken>{token}</tds:InterfaceToken><tds:NetworkInterface>"
                     "<tt:Enabled>true</tt:Enabled><tt:IPv4><tt:Enabled>true</tt:Enabled><tt:Manual>"
                     f"<tt:Address>{ip}</tt:Address><tt:PrefixLength>24</tt:PrefixLength></tt:Manual>"
                     "<tt:DHCP>false</tt:DHCP></tt:IPv4></tds:NetworkInterface></tds:SetNetworkInterfaces>")
        if re.search(r"RebootNeeded>\s*true", t):
            try:
                self.goi("<tds:SystemReboot/>", cho=4)
            except Exception:
                pass


# ------------------------------------------------------------------ DDNS theo nền tảng cam
def ddns_isapi(ip, port, user, pw, dom, du, dp):
    a, url = HTTPDigestAuth(user, pw), f"http://{ip}:{port}/ISAPI/System/Network/DDNS/1"
    r = requests.get(url, auth=a, timeout=8)
    if r.status_code != 200:
        raise RuntimeError(f"ISAPI DDNS đọc lỗi {r.status_code}")
    x = r.text

    def dat(x, the, gia_tri):
        if re.search(rf"<{the}>.*?</{the}>", x, re.S):
            return re.sub(rf"<{the}>.*?</{the}>", f"<{the}>{gia_tri}</{the}>", x, count=1, flags=re.S)
        return x.replace("</DDNS>", f"<{the}>{gia_tri}</{the}></DDNS>")
    for the, g in (("enabled", "true"), ("provider", "NO-IP"), ("deviceDomainName", dom),
                   ("userName", du), ("password", dp)):
        x = dat(x, the, g)
    r = requests.put(url, data=x.encode(), auth=a, timeout=8, headers={"Content-Type": "application/xml"})
    if r.status_code != 200:
        raise RuntimeError(f"ISAPI DDNS ghi lỗi {r.status_code}: {r.text[:120]}")


def ddns_dahua(ip, port, user, pw, dom, du, dp):
    q = {"action": "setConfig", "DDNS[0].Enable": "true", "DDNS[0].Protocol": "NO-IP DDNS",
         "DDNS[0].HostName": dom, "DDNS[0].UserName": du, "DDNS[0].Password": dp}
    r = requests.get(f"http://{ip}:{port}/cgi-bin/configManager.cgi", params=q,
                     auth=HTTPDigestAuth(user, pw), timeout=8)
    if r.status_code != 200 or "OK" not in r.text:
        raise RuntimeError(f"Dahua DDNS lỗi {r.status_code}: {r.text[:120]}")


def nen_tang(ip, port):
    """Nhận nền tảng thật của cam (nhiều hãng VN dán nhãn lại Hikvision/Dahua)."""
    if camlink_oryza.la_oryza(ip, port):
        return "oryza"
    def lay(p):
        try:
            r = requests.get(f"http://{ip}:{port}{p}", timeout=4)
            return r.status_code, r.headers.get("WWW-Authenticate", ""), r.text[:500]
        except requests.RequestException:
            return None, "", ""
    ma, au, t = lay("/ISAPI/System/deviceInfo")
    if (ma == 401 and "digest" in au.lower()) or "<DeviceInfo" in t:
        return "isapi"
    ma, au, t = lay("/cgi-bin/magicBox.cgi?action=getDeviceType")
    if (ma == 401 and au) or t.startswith("type="):
        return "dahua"
    import camlink_unv
    if camlink_unv.la_unv(ip, port):
        return "unv"      # Uniview (LAPI) — xem camlink_unv.py
    return "khac"


# ------------------------------------------------------------------ UPnP modem
def upnp_tim():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(3)
    loc = os.environ.get("CAMLINK_UPNP")
    try:
        if not loc:
            s.sendto(b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\n'
                 b'ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n', ("239.255.255.250", 1900))
        while not loc:
            d, _ = s.recvfrom(4096)
            m = re.search(rb"LOCATION:\s*(\S+)", d, re.I)
            loc = m and m.group(1).decode()
    except OSError:
        return None
    finally:
        s.close()
    try:
        xml = requests.get(loc, timeout=5).text
    except requests.RequestException:
        return None
    for st in ("urn:schemas-upnp-org:service:WANIPConnection:1", "urn:schemas-upnp-org:service:WANPPPConnection:1"):
        m = re.search(r"<serviceType>" + re.escape(st) + r"</serviceType>.*?<controlURL>(.*?)</controlURL>", xml, re.S)
        if m:
            return requests.compat.urljoin(loc, m.group(1).strip()), st
    return None


def upnp_goi(igd, hd, ts):
    url, st = igd
    b = "".join(f"<{k}>{v}</{k}>" for k, v in ts.items())
    env = (f'<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle='
           f'"http://schemas.xmlsoap.org/soap/encoding/"><s:Body><u:{hd} xmlns:u="{st}">{b}</u:{hd}></s:Body></s:Envelope>')
    r = requests.post(url, data=env, timeout=6, headers={"Content-Type": 'text/xml; charset="utf-8"',
                                                         "SOAPAction": f'"{st}#{hd}"'})
    return r.status_code, r.text


# ------------------------------------------------------------------ quy trình một điểm
def chay(stt, cam_user, cam_pw, modem_user, modem_pw, ds_ip=None):
    d = PHU_LY[str(stt)]
    log(f"=== Điểm {stt}: {d['ten']} — {d['domain']} — {d['so']} cam ===")
    may = ip_may()
    gw = GW or ".".join(may.split(".")[:3]) + ".1"
    log(f"Máy này {may}, modem {gw}")
    if ds_ip:
        tim = {}
        for ip in ds_ip:
            p = next((p for p in PORT_QUET if mo(ip, p)), None)
            if p:
                tim[ip] = p
            else:
                log(f"  {ip}: không vào được")
    else:
        log("Quét mạng tìm cam ...")
        tim = quet(gw.rsplit(".", 1)[0] + ".0/24", {gw, may})
    cams = []
    global LY_DO_0CAM, TM_LECH, GHI_DE_DDNS, DUNG_VI_MAT_MODEM
    LY_DO_0CAM = {}
    TM_LECH = {}
    DUNG_VI_MAT_MODEM = False
    ghi_de_ddns, GHI_DE_DDNS = GHI_DE_DDNS, False
    sai_pass, khong_onvif = [], []      # để khi ra 0 cam thì nói được VÌ SAO
    unv_tt = {}                         # ip → (trạng thái, câu báo) của bước khai báo cam Uniview
    for ip in sorted(tim, key=lambda x: int(x.split(".")[-1])):
        if camlink_oryza.da_khai_bao(ip, tim[ip]) is False:      # cam MỚI chưa có mật khẩu → tự khai báo lần đầu bằng user/pass của hệ thống
            log(f"  Cam {ip}:{tim[ip]} còn MỚI (chưa khai báo lần đầu) → tự tạo mật khẩu quản trị theo user/pass cam đã lưu …")
            ok_kb, u_kb, tb_kb = camlink_oryza.khai_bao_lan_dau(ip, tim[ip], cam_user, cam_pw)
            log(f"  {'✔' if ok_kb else '✖'} {ip}: {tb_kb}")
            if ok_kb:
                if u_kb != cam_user:
                    log(f"  ⚠ Cam bắt buộc tên user quản trị là «{u_kb}» (khác «{cam_user}» đang lưu) → lần chạy này dùng «{u_kb}»; sửa User cam trong app cho khớp.")
                    cam_user = u_kb
                time.sleep(3)
        try:      # cam Uniview: còn mật khẩu xuất xưởng thì tự đổi sang mật khẩu cam của hệ thống (như khai báo lần đầu)
            import camlink_unv
            if ip != gw and camlink_unv.la_unv(ip, tim[ip]):
                tt_u, u_u, tb_u = camlink_unv.khai_bao_lan_dau(ip, tim[ip], cam_user, cam_pw)
                unv_tt[ip] = (tt_u, tb_u)
                log(f"  {'✔' if tt_u in ('san', 'moi') else '✖'} Cam UNV {ip}:{tim[ip]}: {tb_u}")
                if tt_u in ("san", "moi") and u_u != cam_user:
                    log(f"  ⚠ Cam UNV dùng user quản trị «{u_u}» (khác «{cam_user}» đang lưu) → lần chạy này dùng «{u_u}»; sửa User cam trong app cho khớp.")
                    cam_user = u_u
                if tt_u == "moi":
                    time.sleep(3)
                if tt_u not in ("san", "moi"):      # chưa có user/pass đúng → KHÔNG thử tiếp qua ONVIF (mỗi lần sai làm cam khoá lâu hơn)
                    sai_pass.append((ip, tim[ip]))
                    continue
        except Exception as e:
            log(f"  · UNV {ip}: {str(e)[:100]}")
        ov = Onvif(ip, tim[ip], cam_user, cam_pw)
        if ov.co():
            try:
                tt = ov.thong_tin()
            except Exception as e:
                log(f"  {ip}:{tim[ip]} có ONVIF nhưng không đăng nhập được ({e}) → kiểm tra user/pass cam")
                sai_pass.append((ip, tim[ip]))
                continue
            cams.append((ip, tim[ip], ov, tt))
            log(f"  Cam {ip}:{tim[ip]} — {tt['hang']} {tt['model']}")
        else:
            khong_onvif.append((ip, tim[ip]))
    if not cams:
        CAN_MAU.append("cam")
        ly_do = []
        if not tim:
            ly_do.append(f"Không thấy thiết bị nào trong mạng {gw.rsplit('.', 1)[0]}.x ngoài modem → cam chưa lên mạng. "
                         "Kiểm nguồn cam, dây mạng cam–modem; điện thoại phải ở đúng WiFi modem của điểm.")
        for ip, port in list(sai_pass) + list(khong_onvif):      # cam Uniview: nói đúng theo kết quả bước khai báo
            if ip in unv_tt:
                tt_u, tb_u = unv_tt[ip]
                if tt_u in ("sai", "loi", "khoa"):
                    ly_do.append(f"Cam UNV {ip}:{port} — {tb_u}.")
                elif (ip, port) in khong_onvif:
                    ly_do.append(f"Cam UNV {ip}:{port} đăng nhập được nhưng ONVIF không trả lời → mở web cam http://{ip}{'' if port == 80 else ':' + str(port)}, "
                                 "vào Setup → Network → Port (hoặc mục ONVIF) bật ONVIF, rồi cài lại. Bấm 'Thu mẫu thiết bị' gửi Claude để app tự làm bước này.")
                else:
                    ly_do.append(f"Cam UNV {ip}:{port} đăng nhập trang web được nhưng ONVIF từ chối user «{cam_user}» → trên web cam vào mục ONVIF/User kiểm tra tài khoản ONVIF, rồi cài lại.")
        sai_pass = [x for x in sai_pass if x[0] not in unv_tt]
        khong_onvif = [x for x in khong_onvif if x[0] not in unv_tt]
        for ip, port in sai_pass:
            ly_do.append(f"Cam {ip}:{port} có trả lời nhưng TỪ CHỐI user «{cam_user}» / mật khẩu cam đã lưu → "
                         "sửa user/pass cam trong Cài đặt chung (hoặc nhập riêng cho điểm này) rồi cài lại.")
        for ip, port in khong_onvif:
            try:
                nt = nen_tang(ip, port)
            except Exception:
                nt = "khac"
            if nt == "unv":
                ly_do.append(f"{ip}:{port} là cam UNV nhưng chưa cho app vào (ONVIF không trả lời) → cam mới chưa đặt mật khẩu lần đầu, hoặc ONVIF đang tắt. "
                             f"App chưa tự kích hoạt được UNV: mở http://{ip}{'' if port == 80 else ':' + str(port)} bằng Chrome, đặt mật khẩu TRÙNG mật khẩu cam đã lưu trong app, rồi cài lại.")
            else:
                ly_do.append(f"{ip}:{port} có trong mạng nhưng app không nhận ra là cam (ONVIF không trả lời) → nếu đây là cam: bật ONVIF / kích hoạt cam trên web cam, hoặc bấm 'Thu mẫu thiết bị' gửi Claude.")
        for l in ly_do:
            log("✖ " + l)
        LY_DO_0CAM = {"stt": stt, "ly_do": ly_do}
        tu_thu_mau(cam_user, cam_pw)
        return
    if len(cams) != d["so"]:
        log(f"⚠ Tìm thấy {len(cams)} cam, file ghi {d['so']} cam")

    ket_qua, luat = [], []
    for i, (ip, port, ov, tt) in enumerate(cams):
        if DUNG_VI_MAT_MODEM:
            log("✖ Dừng cài các cam còn lại: mất kết nối modem quá 2 phút (modem khởi động lại / rớt WiFi). Vào lại WiFi modem rồi cài lại điểm này.")
            break
        ip_moi, http, rtsp = f"{gw.rsplit('.', 1)[0]}.{IP_TU + i}", HTTP[i], RTSP[i]
        log(f"-- Cam {i + 1}: {ip}:{port} → {ip_moi}  HTTP {http}  RTSP {rtsp}")
        kq = {"so": i + 1, "ip": ip_moi, "http": http, "rtsp": rtsp, "model": tt["model"], "ghi": []}
        try:
            token, mac = ov.token_mang()
            kq["mac"] = mac
            nt = nen_tang(ip, port)
            if i == 0:
                tm_cam = ten_mien_tren_cam(nt, ip, port, cam_user, cam_pw)
                tm_app = str(d.get("domain") or "").strip().lower()
                try:
                    if tm_cam and tm_cam != tm_app and not ghi_de_ddns:
                        # cam (cài tay / cài trước) đang dùng tên miền khác → KHÔNG tự ghi đè, để người dùng chọn sau lượt chạy
                        TM_LECH = {"stt": stt, "cam": tm_cam, "app": tm_app}
                        kq["ghi"].append(f"Cam đang dùng tên miền {tm_cam}, khác {tm_app or '(chưa có)'} của điểm — CHƯA ghi đè, chờ bạn chọn")
                        log(f"   ⚠ {kq['ghi'][-1]}")
                    elif not tm_app:
                        kq["ghi"].append("DDNS bỏ trống (điểm chưa có tên miền)")
                    elif nt == "oryza":
                        kq["ghi"].append(camlink_oryza.dat_ddns(ip, port, cam_user, cam_pw, d["domain"], d["u"], d["p"]))
                        log(f"   ✔ {kq['ghi'][-1]}")
                    elif ip == ip_moi and port == http:
                        pass  # Hik/Dahua đã đúng sẵn: giữ nguyên DDNS
                    elif nt == "isapi":
                        ddns_isapi(ip, port, cam_user, cam_pw, d["domain"], d["u"], d["p"])
                        kq["ghi"].append("DDNS đã nhập")
                    elif nt == "dahua":
                        ddns_dahua(ip, port, cam_user, cam_pw, d["domain"], d["u"], d["p"])
                        kq["ghi"].append("DDNS đã nhập")
                    elif nt == "unv":
                        import camlink_unv
                        kq["ghi"].append(camlink_unv.dat_ddns(ip, port, cam_user, cam_pw, d["domain"], d["u"], d["p"]))
                        log(f"   ✔ {kq['ghi'][-1]}")
                    else:
                        raise RuntimeError("hãng này chưa có lệnh DDNS — bấm 'Thu mẫu thiết bị' gửi Claude")
                except Exception as e:
                    kq["ghi"].append(f"DDNS CHƯA nhập: {e}")
                    CAN_MAU.append("cam")
                    log(f"   ⚠ DDNS: {e}")
            if ip == ip_moi and port == http and mo(ip, rtsp, 1):
                kq["ok"] = True
                kq["ghi"].append("Đã đúng sẵn — giữ nguyên, không đổi gì")
                luat += [(f"cam{i + 1}", http, ip_moi), (f"cam{i + 1}_rtsp", rtsp, ip_moi)]
                log(f"   ✔ Cam {i + 1} đã đúng sẵn (IP {ip_moi}, HTTP {http}, RTSP {rtsp}) — giữ nguyên")
                ket_qua.append(kq)
                continue
            ov.dat_gw_dns(gw)
            try:
                ov.dat_port(http, rtsp)
            except Exception as e_port:
                if nt != "unv":
                    raise
                import camlink_unv      # cam Uniview: ONVIF không đổi được port → đổi qua LAPI
                log(f"   · ONVIF không đổi được port ({str(e_port)[:60]}) → đổi qua LAPI của UNV")
                camlink_unv.dat_port(ip, port, cam_user, cam_pw, http, rtsp)
            log(f"   port xong, chờ cam mở {ip}:{http} ...")
            if not cho_len(ip, http, 150 if nt == "unv" else 60):
                raise RuntimeError("cam không mở port HTTP mới")
            ov.port = http
            ov.dat_ip(token, ip_moi)
            log(f"   đặt IP xong, chờ cam lên {ip_moi}:{http} ...")
            if not cho_len(ip_moi, http, 120):
                raise RuntimeError(f"cam không lên lại ở {ip_moi}:{http}")
            kq["ok"] = mo(ip_moi, rtsp, 3)
            kq["ghi"].append("RTSP mở" if kq["ok"] else f"RTSP {rtsp} chưa mở")
            luat += [(f"cam{i + 1}", http, ip_moi), (f"cam{i + 1}_rtsp", rtsp, ip_moi)]
            log(f"   ✔ Cam {i + 1} xong")
        except Exception as e:
            kq["ok"] = False
            kq["ghi"].append(f"LỖI: {e}")
            log(f"   ✖ Cam {i + 1}: {e}")
        ket_qua.append(kq)

    log("-- Modem: mở port")
    wan = None
    web_modem = 0
    mdm = None
    try:      # modem mới còn mật khẩu xuất xưởng → đổi sang mật khẩu của hệ thống (chỉ khi nhận ra đúng kiểu modem)
        import camlink_modem
        log("   đăng nhập trang quản trị modem …")
        mdm = camlink_modem.chuan_bi(gw, modem_user, modem_pw, log, pass_modem_yeu)
        if mdm is None:
            log("   · Chưa vào được trang quản trị modem (khác kiểu, hoặc mật khẩu trên tem modem khác mật khẩu đã lưu) → mở port bằng UPnP; "
                "muốn app quản modem thì nhập đúng mật khẩu modem ở 'User/pass riêng điểm này'.")
            CAN_MAU.append("modem")
    except Exception as e:
        log(f"   · Trang quản trị modem: {str(e)[:80]}")
    log("   dò UPnP trên modem …")
    igd = upnp_tim()
    if igd:
        dem = co_san = 0
        for ten, p, ip in luat:
            ma, t = upnp_goi(igd, "AddPortMapping", {"NewRemoteHost": "", "NewExternalPort": p, "NewProtocol": "TCP",
                             "NewInternalPort": p, "NewInternalClient": ip, "NewEnabled": 1,
                             "NewPortMappingDescription": ten, "NewLeaseDuration": 0})
            if ma == 200:
                dem += 1
            elif "718" in t or "Conflict" in t:
                co_san += 1   # modem đã có luật cho port này (vd tạo tay) → giữ nguyên
        tong = dem + co_san
        log(f"   {'✔' if tong == len(luat) else '⚠'} Mở {tong}/{len(luat)} luật"
            + (f" ({co_san} luật modem đã có sẵn, giữ nguyên)" if co_san else "") + " qua UPnP")
        ma, t = upnp_goi(igd, "GetExternalIPAddress", {})
        m = re.search(r"<NewExternalIPAddress>(.*?)<", t)
        wan = m and m.group(1)
        # 2.8 — mở quản trị modem từ xa: chỉ khi mật khẩu modem KHÔNG còn mặc định/yếu
        if pass_modem_yeu(modem_user, modem_pw):
            log("   ⚠ CHƯA mở quản trị modem từ xa: mật khẩu modem còn mặc định/yếu — mở ra Internet là bị chiếm modem. "
                "Đổi mật khẩu modem (từ 8 ký tự), nhập mật khẩu mới vào app rồi chạy lại điểm này.")
        else:
            try:
                ma, t = upnp_goi(igd, "AddPortMapping", {"NewRemoteHost": "", "NewExternalPort": PORT_WEB_MODEM, "NewProtocol": "TCP",
                                 "NewInternalPort": 80, "NewInternalClient": gw, "NewEnabled": 1,
                                 "NewPortMappingDescription": "camlink_modem", "NewLeaseDuration": 0})
                if ma == 200 or "718" in t or "Conflict" in t:
                    web_modem = PORT_WEB_MODEM
                    log(f"   ✔ Mở quản trị modem từ xa: {d['domain']}:{PORT_WEB_MODEM} → trang modem {gw} (đăng nhập bằng mật khẩu modem)")
                else:
                    log("   ⚠ Modem không cho mở port vào chính nó qua UPnP → muốn quản trị modem từ xa phải bật 'Remote management' "
                        "trong trang modem (app cần mẫu modem này để tự bật).")
                    CAN_MAU.append("modem")
            except Exception as e:
                log(f"   ⚠ Mở quản trị modem từ xa lỗi: {str(e)[:80]}")
    else:
        if mdm is not None:
            dem = 0
            for ten, p, ip in luat:
                log(f"   thêm luật mở port {p} → {ip} trên modem …")
                try:
                    ok_n, tb_n = mdm.them_nat(ten, p, ip)
                except Exception as e:
                    ok_n, tb_n = False, str(e)[:80]
                dem += 1 if ok_n else 0
                if not ok_n:
                    log(f"   ✖ {tb_n}")
            log(f"   {'✔' if dem == len(luat) else '⚠'} Modem tắt UPnP → mở {dem}/{len(luat)} luật qua trang quản trị modem")
        else:
            log("   ⚠ Modem tắt UPnP → tạm mở port tay theo bảng dưới (Virtual Servers)")
            CAN_MAU.append("modem")
    if not igd and pass_modem_yeu(modem_user, modem_pw):      # không in mật khẩu ra nhật ký (nhật ký được gửi qua Zalo/Gmail)
        log("   ⚠ Mật khẩu modem đang lưu trong app còn mặc định/yếu — nếu modem đã đặt mật khẩu riêng thì nhập đúng vào app.")

    log("-- Kiểm tra")
    if wan:
        a = ipaddress.ip_address(wan)
        if a.is_private or a in ipaddress.ip_network("100.64.0.0/10"):
            log(f"   ✖ CGNAT: IP WAN {wan} là IP nội bộ nhà mạng → gọi nhà mạng xin IP public")
        else:
            log(f"   IP WAN {wan}")
            try:
                ip_dom = socket.gethostbyname(d["domain"])
            except OSError:
                ip_dom = None
            log(f"   {'✔' if ip_dom == wan else '⚠'} {d['domain']} → {ip_dom} (cần {wan}; DDNS có thể mất 1–5 phút)")
    global KQ_CUOI
    KQ_CUOI = {"stt": stt, "ten": d["ten"], "domain": d["domain"], "gw": gw, "wan": wan or "", "web_modem": web_modem,
               "upnp": bool(igd), "luat": [{"ten": t, "port": p, "ip": ip} for t, p, ip in luat],
               "cam": [{"so": k["so"], "ip": k["ip"], "http": k["http"], "rtsp": k["rtsp"], "model": k.get("model", ""),
                        "mac": k.get("mac", ""), "ok": bool(k.get("ok")), "ghi": "; ".join(k["ghi"])} for k in ket_qua]}
    log("")
    log(f"BẢNG KẾT QUẢ ĐIỂM {stt} — {d['domain']}")
    for k in ket_qua:
        log(f" Cam {k['so']}: {k['ip']}  HTTP {k['http']}  RTSP {k['rtsp']}  {'ĐẠT' if k.get('ok') else 'CHƯA'}  ({'; '.join(k['ghi'])})")
    log(" Bảng mở port modem (ngoài = trong, TCP):")
    for ten, p, ip in luat:
        log(f"   {ten:<10} {p:<6} → {ip}")
    log(f" Kiểm tra port: {d['domain']}  " + ", ".join(str(p) for _, p, _ in luat))
    f = os.path.join(thu_muc_ra(), f"camlink_diem{stt}_{time.strftime('%H%M')}.txt")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write("\n".join(NHAT_KY))
    log(f"Đã lưu nhật ký: {f}")
    tu_thu_mau(cam_user, cam_pw)


def tu_thu_mau(cam_user, cam_pw):
    if CAN_MAU:
        log("")
        log(f"Gặp thiết bị app chưa biết ({', '.join(sorted(set(CAN_MAU)))}) → tự lưu mẫu để Claude bổ sung lệnh ...")
        thu(cam_user, cam_pw)


def _thu_modem(z, thu_muc, goc, tk):
    """Chỉ ĐỌC: tệp JS của trang đăng nhập modem, thử đăng nhập ubus/LuCI bằng user/pass modem đã lưu, đọc cấu hình mở port."""
    def ghi(ten, noi_dung):
        t = noi_dung if isinstance(noi_dung, str) else json.dumps(noi_dung, ensure_ascii=False, indent=1)
        if tk[1] and len(tk[1]) >= 4:
            t = t.replace(tk[1], "***")
        z.writestr(f"{thu_muc}/modem/{ten}", t[:400000])
    hd = {"User-Agent": "Mozilla/5.0", "Referer": goc + "/"}
    for f in ("login.js", "main.js", "index.js", "common.js", "menu.js", "home.html", "index.html", "main.html", "luci-static/resources/luci.js",
              "cgi-bin/luci/admin/menu", "ubus"):
        try:
            r = requests.get(f"{goc}/{f}", timeout=8, headers=hd, verify=False)
            ghi(ten_file(f) + ".txt", f"{r.status_code}\n{dict(r.headers)}\n\n{r.text}")
        except Exception as e:
            ghi(ten_file(f) + ".LOI.txt", str(e)[:300])
    import camlink_modem
    o = camlink_modem.Owrt(goc.split("//")[1].split(":")[0], tk[0], tk[1], int(goc.rsplit(":", 1)[1]) if goc.count(":") > 1 else 80)
    bc = {"nhan_ra_luci": o.nhan_ra()}
    ma0, d0 = o._ubus("session", "login", {"username": tk[0], "password": tk[1], "timeout": 300}, sid="0" * 32)
    bc["ubus_login_ma"] = ma0
    bc["ubus_login_tra"] = ("có phiên" if isinstance(d0, dict) and d0.get("ubus_rpc_session") else d0)
    bc["dang_nhap"] = o.dang_nhap()
    bc["user_dung"] = o.user if bc["dang_nhap"] else ""
    bc["buoc_ket"] = o.buoc
    ghi("ubus_bao_cao.json", bc)
    if bc["dang_nhap"]:
        for ten, dt, lenh, ts in (("acl", "session", "access", {}), ("uci_cac_goi", "uci", "configs", {}), ("uci_firewall", "uci", "get", {"config": "firewall"}),
                                  ("uci_network", "uci", "get", {"config": "network"}), ("uci_upnpd", "uci", "get", {"config": "upnpd"}),
                                  ("board", "system", "board", {})):
            ma, d = o._ubus(dt, lenh, ts)
            ghi(f"ubus_{ten}.json", {"ma": ma, "du_lieu": d})
        try:
            r = o.s.post(o.goc + "/ubus/", json={"jsonrpc": "2.0", "id": 1, "method": "list", "params": [o.sid, "*"]}, timeout=8)
            ghi("ubus_list.json", r.text)
        except Exception as e:
            ghi("ubus_list.LOI.txt", str(e)[:300])


# ------------------------------------------------------------------ thu mẫu
# Trang riêng của cam Uniview (UNV) — giao thức LAPI, chỉ ĐỌC (GET). Hãng khác trả 404, không ảnh hưởng.
TRANG_UNV = ["/LAPI/V1.0/System/DeviceBasicInfo", "/LAPI/V1.0/System/DeviceInfo", "/LAPI/V1.0/System/Security/Activation",
             "/LAPI/V1.0/Network/Interfaces", "/LAPI/V1.0/NetWork/Interfaces", "/LAPI/V1.0/Network/Ports", "/LAPI/V1.0/NetWork/Ports",
             "/LAPI/V1.0/NetWork/Port", "/LAPI/V1.0/Network/Interfaces/1", "/LAPI/V1.0/System/Security/RSA", "/LAPI/V1.0/NetWork/HttpAuth",
             "/LAPI/V1.0/Network/DDNS", "/LAPI/V1.0/NetWork/DDNS", "/LAPI/V1.0/Network/DDNS/Capabilities", "/LAPI/V1.0/NetWork/DDNS/Capabilities",
             "/LAPI/V1.0/Network/UPnP", "/LAPI/V1.0/NetWork/UPnP", "/LAPI/V1.0/System/Capabilities",
             "/LAPI/V1.0/Channels/0/Media/Video/Streams/0/LiveStreamURL", "/index.htm", "/cgi-bin/main-cgi"]


def thu(cam_user="", cam_pw=""):
    may = ip_may()
    gw = GW or ".".join(may.split(".")[:3]) + ".1"
    log(f"Quét mạng {gw} ...")
    tim = quet(gw.rsplit(".", 1)[0] + ".0/24", {may})
    if not tim:
        log(f"✖ Không thấy thiết bị nào trong mạng {gw.rsplit('.', 1)[0]}.x (đã thử port {', '.join(str(x) for x in PORT_QUET)}).")
        log("  Kiểm tra: cam đã cấp nguồn và cắm dây vào modem chưa; điện thoại có đang ở đúng WiFi của modem đó không.")
        return ""
    log(f"Tìm thấy {len(tim)} thiết bị. Đang đọc từng thiết bị ...")
    zp = os.path.join(thu_muc_ra(), f"camlink_mau_{time.strftime('%Y%m%d_%H%M%S')}.zip")
    _cd = doc_cai_dat()
    tk_modem = (_cd.get("modem_user", "admin"), _cd.get("modem_pw", "admin"))
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for ip, port in tim.items():
            goc = f"http://{ip}:{port}"
            log(f"  {goc}")
            trang_modem = (["/info.html", "/main.html", "/menu.html", "/scvrtsrv.html", "/password.html", "/resetrouter.html", "/scacccntr.html",
                            "/upnpcfg.html", "/wancfg.html", "/login.html", "/login.asp", "/cgi-bin/login.asp", "/status.htm", "/index.asp",
                            "/cgi-bin/luci", "/html/index.html", "/js/main.js", "/getpage.gch?pid=1002"] if ip == gw else [])
            kem_pass_cam = bool(cam_user) and ip != gw
            if kem_pass_cam:
                try:
                    import camlink_unv
                    if camlink_unv.la_unv(ip, port) and camlink_unv.Lapi(ip, port, cam_user, cam_pw).vao_duoc() is not True:
                        kem_pass_cam = False      # cam UNV chưa nhận mật khẩu đã lưu → đọc không kèm mật khẩu, không gây khoá tài khoản
                        z.writestr(f"{ip}_{port}/ghi_chu.txt", "Cam UNV không nhận user/pass cam đã lưu (hoặc đang khoá) → mẫu này đọc KHÔNG kèm mật khẩu.")
                except Exception:
                    pass
            for p in ["/", "/ISAPI/System/deviceInfo", "/cgi-bin/magicBox.cgi?action=getDeviceType",
                      "/onvif/device_service", "/doc/page/login.asp", "/rootDesc.xml", "/igd.xml"] + (TRANG_UNV if ip != gw else []) + trang_modem:
                try:
                    r = requests.get(goc + p, timeout=5, verify=False,
                                     auth=HTTPDigestAuth(cam_user, cam_pw) if kem_pass_cam else (tk_modem if ip == gw and p in trang_modem else None))
                    than = r.text[:200000]
                    for bi_mat in (cam_pw, tk_modem[1]):      # file mẫu được gửi đi → che mật khẩu nếu trang có nhúng
                        if bi_mat and len(bi_mat) >= 4:
                            than = than.replace(bi_mat, "***")
                    z.writestr(f"{ip}_{port}/{ten_file(p)}.txt", f"{r.status_code}\n{dict(r.headers)}\n\n{than}")
                    if p == "/":
                        for src in re.findall(r'(?:src|href)=["\']([^"\']+\.(?:js|asp|html?|htm))', r.text, re.I)[:40]:
                            try:
                                r2 = requests.get(requests.compat.urljoin(r.url, src), timeout=8, verify=False, headers={"User-Agent": "Mozilla/5.0", "Referer": r.url})
                                z.writestr(f"{ip}_{port}/tai/{ten_file(src)}", r2.text[:500000])
                            except Exception as e_tai:      # ghi lại lỗi để biết vì sao thiếu tệp
                                z.writestr(f"{ip}_{port}/tai/{ten_file(src)}.LOI.txt", str(e_tai)[:300])
                except requests.RequestException:
                    pass
            if ip == gw:      # modem: thu thêm phần đăng nhập + mở port (chỉ ĐỌC) để Claude viết lệnh cho đúng kiểu modem
                try:
                    _thu_modem(z, f"{ip}_{port}", goc, tk_modem)
                except Exception as e_md:
                    z.writestr(f"{ip}_{port}/modem_LOI.txt", str(e_md)[:300])
            ov = Onvif(ip, port, cam_user, cam_pw)
            if ov.co():
                z.writestr(f"{ip}_{port}/onvif.txt", "ONVIF: có")
                if cam_user and (kem_pass_cam or ip == gw):
                    try:
                        z.writestr(f"{ip}_{port}/onvif_info.txt", json.dumps(ov.thong_tin(), ensure_ascii=False))
                    except Exception as e:
                        z.writestr(f"{ip}_{port}/onvif_info.txt", str(e))
    log("Xong. Đã lưu file mẫu (chỉ đọc, không thay đổi gì). App sẽ mở bảng chia sẻ → chọn Zalo/Gmail gửi cho Claude.")
    log("Mục đích: Claude đọc file này để dạy app điều khiển cam/modem loại mới.")
    return zp


# ------------------------------------------------------------------ cài đặt một lần + tự nhận điểm
KHOA_RIENG = ("wifi_ten", "wifi_mk", "cam_user", "cam_pw", "modem_user", "modem_pw")


def cd_diem(d, cd):
    """User/pass dùng cho MỘT điểm: thứ người dùng nhập riêng cho điểm (d['rieng']) được ưu tiên, còn lại lấy mặc định. Không sửa mặc định."""
    out = dict(cd or {})
    out.update({k: v for k, v in ((d or {}).get("rieng") or {}).items() if k in KHOA_RIENG and v not in ("", None)})
    return out


def file_cai_dat():
    return os.path.join(thu_muc_ra(), "camlink_caidat.json")


def doc_cai_dat():
    try:
        with open(file_cai_dat(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ghi_cai_dat(cd):
    with open(file_cai_dat(), "w", encoding="utf-8") as f:
        json.dump(cd, f, ensure_ascii=False, indent=1)


def toa_do_tu_link(url):
    """Mở link Google Maps rút gọn, lấy toạ độ trong địa chỉ đích."""
    try:
        r = requests.get(url, timeout=10, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        dich = r.url + " " + r.text[:3000]
    except requests.RequestException:
        return None
    for mau in (r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)", r"@(-?\d+\.\d+),(-?\d+\.\d+)",
                r"[?&](?:q|ll|query)=(-?\d+\.\d+)(?:,|%2C)\+?(-?\d+\.\d+)"):
        m = re.search(mau, dich)
        if m:
            return [float(m.group(1)), float(m.group(2))]
    return None


def vi_tri_hien_tai(cho=25):
    """GPS điện thoại qua Termux:API. Không có thì trả None."""
    import shutil, subprocess
    lenh = os.environ.get("CAMLINK_GPS_CMD") or (shutil.which("termux-location") and "termux-location -p gps -r once")
    if not lenh:
        return None
    for nguon in (lenh, lenh.replace("-p gps", "-p network")):
        try:
            out = subprocess.run(nguon, shell=True, capture_output=True, text=True, timeout=cho).stdout
            j = json.loads(out)
            return j["latitude"], j["longitude"]
        except Exception:
            continue
    return None


def khoang_cach(a, b):
    import math
    R = 6371000
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def tao_nut_widget():
    """Tạo nút 'CamLink' cho widget Termux trên màn hình chính."""
    tm = os.path.expanduser("~/.shortcuts")
    try:
        os.makedirs(tm, exist_ok=True)
        f = os.path.join(tm, "CamLink")
        with open(f, "w") as fh:
            fh.write(f"#!/data/data/com.termux/files/usr/bin/bash\ncd \"{os.path.dirname(os.path.abspath(__file__))}\"\n"
                     f"python \"{os.path.abspath(__file__)}\"\necho\nread -p 'Xong. Enter để đóng...'\n")
        os.chmod(f, 0o755)
    except OSError:
        pass


def cai_lan_dau(cd):
    print("CÀI ĐẶT LẦN ĐẦU (chỉ hỏi một lần, lưu lại cho các điểm sau)")
    cd["cam_user"] = input("User cam [admin]: ").strip() or "admin"
    cd["cam_pw"] = input("Pass cam: ").strip()
    cd["modem_user"] = input("User modem [admin]: ").strip() or "admin"
    cd["modem_pw"] = input("Pass modem [admin]: ").strip() or "admin"
    print("Đang lấy toạ độ các điểm từ link bản đồ trong file khảo sát ...")
    cd["toa_do"] = {}
    for k, v in PHU_LY.items():
        td = toa_do_tu_link(v.get("map", ""))
        if td:
            cd["toa_do"][k] = td
        print(f"  {k:>2}. {v['ten']}: {td or 'không lấy được'}")
    ghi_cai_dat(cd)
    tao_nut_widget()
    print(f"Đã lưu: {file_cai_dat()}\n")


def chon_diem(cd):
    td = cd.get("toa_do", {})
    if td:
        print("Đang lấy vị trí GPS ...")
        vt = vi_tri_hien_tai()
        if vt:
            gan = sorted((khoang_cach(vt, v), k) for k, v in td.items())
            m, k = gan[0]
            if m <= 400:
                print(f"→ Đang ở điểm {k}: {PHU_LY[k]['ten']} (cách {m:.0f} m)")
                return k
            print(f"Điểm gần nhất là {k} nhưng cách {m:.0f} m — chọn tay.")
        else:
            print("Không lấy được GPS — chọn tay.")
    xong = cd.get("da_xong", {})
    for k, v in PHU_LY.items():
        print(f"  {k:>2}. {v['ten']} ({v['so']} cam){'  ✔ đã làm ' + xong[k] if k in xong else ''}")
    k = input("Số điểm: ").strip()
    if k not in PHU_LY:
        sys.exit("Số điểm không có trong danh sách.")
    return k


def main():
    cd = doc_cai_dat()
    if len(sys.argv) > 1 and sys.argv[1] == "thu":
        return thu(cd.get("cam_user", ""), cd.get("cam_pw", ""))
    if len(sys.argv) > 1 and sys.argv[1] == "caidat" or "cam_pw" not in cd:
        cai_lan_dau(cd)
    k = chon_diem(cd)
    chay(k, cd["cam_user"], cd["cam_pw"], cd["modem_user"], cd["modem_pw"])
    if any("ĐẠT" in l for l in NHAT_KY):
        cd.setdefault("da_xong", {})[k] = time.strftime("%d/%m %H:%M")
        ghi_cai_dat(cd)


if __name__ == "__main__":
    main()
