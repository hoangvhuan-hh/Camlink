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
MODEM_PASS_MOI = "Aa112233@"

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
        time.sleep(3)
    return False


# ------------------------------------------------------------------ ONVIF (chuẩn chung camera IP)
NS = ('xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:tds="http://www.onvif.org/ver10/device/wsdl" '
      'xmlns:tt="http://www.onvif.org/ver10/schema" xmlns:trt="http://www.onvif.org/ver10/media/wsdl"')


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
            t = self.goi("<tds:GetSystemDateAndTime/>", xac_thuc=False, cho=4)
        except Exception:
            return False
        try:
            g = lambda k: int(re.search(rf"<[^>]*{k}>(\d+)<", t.split("UTCDateTime")[1]).group(1))
            cam = datetime.datetime(g("Year"), g("Month"), g("Day"), g("Hour"), g("Minute"), g("Second"))
            self.lech = cam - datetime.datetime.utcnow()
        except Exception:
            pass
        return True

    def thong_tin(self):
        t = self.goi("<tds:GetDeviceInformation/>")
        g = lambda k: (re.search(rf"<[^>]*{k}>(.*?)<", t) or [None, ""])[1]
        return {"hang": g("Manufacturer"), "model": g("Model"), "serial": g("SerialNumber")}

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
        t = self.goi("<trt:GetProfiles/>", url=url_media)
        m = re.search(r'Profiles[^>]*token="([^"]+)"', t)
        if not m:
            raise RuntimeError("cam không có profile video")
        return m.group(1)

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
    for ip in sorted(tim, key=lambda x: int(x.split(".")[-1])):
        ov = Onvif(ip, tim[ip], cam_user, cam_pw)
        if ov.co():
            try:
                tt = ov.thong_tin()
            except Exception as e:
                log(f"  {ip}:{tim[ip]} có ONVIF nhưng không đăng nhập được ({e}) → kiểm tra user/pass cam")
                continue
            cams.append((ip, tim[ip], ov, tt))
            log(f"  Cam {ip}:{tim[ip]} — {tt['hang']} {tt['model']}")
    if not cams:
        CAN_MAU.append("cam")
        log("✖ Không cam nào vào được. Nếu dòng trên báo 'không đăng nhập được' → sai user/pass cam, chạy lại. "
            "Nếu không thấy cam nào → app tự lưu mẫu, gửi file zip cho Claude.")
        tu_thu_mau(cam_user, cam_pw)
        return
    if len(cams) != d["so"]:
        log(f"⚠ Tìm thấy {len(cams)} cam, file ghi {d['so']} cam")

    ket_qua, luat = [], []
    for i, (ip, port, ov, tt) in enumerate(cams):
        ip_moi, http, rtsp = f"{gw.rsplit('.', 1)[0]}.{IP_TU + i}", HTTP[i], RTSP[i]
        log(f"-- Cam {i + 1}: {ip}:{port} → {ip_moi}  HTTP {http}  RTSP {rtsp}")
        kq = {"so": i + 1, "ip": ip_moi, "http": http, "rtsp": rtsp, "model": tt["model"], "ghi": []}
        try:
            token, mac = ov.token_mang()
            kq["mac"] = mac
            nt = nen_tang(ip, port)
            if i == 0:
                try:
                    if nt == "oryza":
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
            ov.dat_port(http, rtsp)
            log(f"   port xong, chờ cam mở {ip}:{http} ...")
            if not cho_len(ip, http, 60):
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
    else:
        log("   ⚠ Modem tắt UPnP → tạm mở port tay theo bảng dưới (Virtual Servers)")
        CAN_MAU.append("modem")
    log(f"   ⚠ Đổi pass modem ({modem_user}/{modem_pw} → {MODEM_PASS_MOI}): app chưa có lệnh cho model modem này, làm tay")

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
    KQ_CUOI = {"stt": stt, "ten": d["ten"], "domain": d["domain"], "gw": gw, "wan": wan or "",
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


# ------------------------------------------------------------------ thu mẫu
def thu(cam_user="", cam_pw=""):
    may = ip_may()
    gw = GW or ".".join(may.split(".")[:3]) + ".1"
    log(f"Quét mạng {gw} ...")
    tim = quet(gw.rsplit(".", 1)[0] + ".0/24", {may})
    zp = os.path.join(thu_muc_ra(), f"camlink_mau_{time.strftime('%Y%m%d_%H%M%S')}.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for ip, port in tim.items():
            goc = f"http://{ip}:{port}"
            log(f"  {goc}")
            for p in ["/", "/ISAPI/System/deviceInfo", "/cgi-bin/magicBox.cgi?action=getDeviceType",
                      "/onvif/device_service", "/doc/page/login.asp", "/rootDesc.xml", "/igd.xml"]:
                try:
                    r = requests.get(goc + p, timeout=5, verify=False,
                                     auth=HTTPDigestAuth(cam_user, cam_pw) if cam_user and ip != gw else None)
                    z.writestr(f"{ip}_{port}/{ten_file(p)}.txt",
                               f"{r.status_code}\n{dict(r.headers)}\n\n{r.text[:200000]}")
                    if p == "/":
                        for src in re.findall(r'(?:src|href)=["\']([^"\']+\.(?:js|asp|html?|htm))', r.text, re.I)[:40]:
                            try:
                                r2 = requests.get(requests.compat.urljoin(goc + "/", src), timeout=5)
                                z.writestr(f"{ip}_{port}/tai/{ten_file(src)}", r2.text[:500000])
                            except requests.RequestException:
                                pass
                except requests.RequestException:
                    pass
            ov = Onvif(ip, port, cam_user, cam_pw)
            if ov.co():
                z.writestr(f"{ip}_{port}/onvif.txt", "ONVIF: có")
                if cam_user:
                    try:
                        z.writestr(f"{ip}_{port}/onvif_info.txt", json.dumps(ov.thong_tin(), ensure_ascii=False))
                    except Exception as e:
                        z.writestr(f"{ip}_{port}/onvif_info.txt", str(e))
    log("Xong. Đã lưu file mẫu (chỉ đọc, không thay đổi gì). App sẽ mở bảng chia sẻ → chọn Zalo/Gmail gửi cho Claude.")
    log("Mục đích: Claude đọc file này để dạy app điều khiển cam/modem loại mới.")
    return zp


# ------------------------------------------------------------------ cài đặt một lần + tự nhận điểm
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
