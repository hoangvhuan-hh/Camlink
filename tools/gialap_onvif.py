# Cam giả lập ONVIF + RTSP cho các bài thử (thu_tuxa9, thu_tuxa10, thu_theodoi2, thu_chandoan).
# Dựng lại 26/11/2026: bản gốc chỉ nằm trong phiên đã viết ra nó, không có trong kho → 4 bài thử kia không chạy được.
# Chỉ trả lời đúng những lệnh mà lõi CamLink (camlink_dt.Onvif, camlink_tuxa.rtsp_describe) thật sự gọi.
import base64, hashlib, io, os, re, socket, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_DANG_CHAY = []      # [(cam, http_server, rtsp_socket)]
_KHOA = threading.Lock()


class Cam:
    def __init__(self, ip, isapi=False, stt=1):
        self.ip, self.isapi, self.stt = ip, isapi, stt
        self.http, self.rtsp = 80, 554
        self.gw, self.dns = "192.168.1.1", "8.8.8.8"
        self.model, self.mac = "OR-IPC", "78:CE:A5:00:00:01"
        self.user, self.pw = "admin", "Abc@12345"
        self.hang, self.firmware = "ORYZA", "V1.0.0"
        self._serial = ""
        self.khoi_dong = []          # các thời điểm (epoch) cam khởi động lại — bài thử tự gán
        self.users = [("admin", "Administrator")]
        self.mk = {}                 # mật khẩu của các tài khoản tạo thêm qua ONVIF (CreateUsers / SetUser) — ảnh chụp chỉ trả cho đúng tài khoản
        self.so_lan_tao_user = 0
        self.cho_tao_user = True     # False: cam từ chối tạo tài khoản (giả hãng không hỗ trợ)
        self.anh_chi_quan_tri = False  # True: cam chỉ cho tài khoản quản trị lấy ảnh
        self.so_lan_reboot = 0


def _serial(cam):
    """Mỗi cam một số máy riêng (theo IP + port web) — nhiều cam chung một IP WAN vẫn phân biệt được."""
    return cam._serial or "SN%s%05d" % (cam.ip.replace(".", ""), cam.http)


def _anh_jpg(chu):
    try:
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (320, 180), (40, 60, 90))
        ImageDraw.Draw(im).text((10, 10), chu + " " + time.strftime("%H:%M:%S"), fill=(255, 255, 255))
        b = io.BytesIO(); im.save(b, "JPEG", quality=70)
        return b.getvalue()
    except Exception:
        return b"\xff\xd8\xff\xe0" + b"\x00" * 600 + b"\xff\xd9"


def _xac_thuc_ok(cam, than):
    """WS-Security UsernameToken PasswordDigest = base64(sha1(nonce + created + mật khẩu))."""
    u = re.search(r"<Username>(.*?)</Username>", than)
    p = re.search(r"<Password[^>]*>(.*?)</Password>", than)
    n = re.search(r"<Nonce[^>]*>(.*?)</Nonce>", than)
    c = re.search(r"<Created[^>]*>(.*?)</Created>", than)
    if not (u and p and n and c) or u.group(1) != cam.user:
        return False
    dg = base64.b64encode(hashlib.sha1(base64.b64decode(n.group(1)) + c.group(1).encode() + cam.pw.encode()).digest()).decode()
    return dg == p.group(1)


def _boc(than):
    return ('<?xml version="1.0" encoding="UTF-8"?><s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
            'xmlns:tds="http://www.onvif.org/ver10/device/wsdl" xmlns:trt="http://www.onvif.org/ver10/media/wsdl" '
            'xmlns:tt="http://www.onvif.org/ver10/schema"><s:Body>' + than + '</s:Body></s:Envelope>')


def _loi(chu):
    return _boc('<s:Fault><s:Code><s:Value>s:Sender</s:Value></s:Code><s:Reason><s:Text xml:lang="en">' + chu +
                '</s:Text></s:Reason></s:Fault>')


def _tra_loi_onvif(cam, than):
    """→ (mã HTTP, thân trả lời)."""
    co = lambda k: re.search(r"<(?:\w+:)?" + k + r"\b", than) is not None
    if co("GetSystemDateAndTime"):
        g = time.gmtime()
        return 200, _boc("<tds:GetSystemDateAndTimeResponse><tds:SystemDateAndTime><tt:UTCDateTime><tt:Time>"
                         f"<tt:Hour>{g.tm_hour}</tt:Hour><tt:Minute>{g.tm_min}</tt:Minute><tt:Second>{g.tm_sec}</tt:Second></tt:Time>"
                         f"<tt:Date><tt:Year>{g.tm_year}</tt:Year><tt:Month>{g.tm_mon}</tt:Month><tt:Day>{g.tm_mday}</tt:Day></tt:Date>"
                         "</tt:UTCDateTime></tds:SystemDateAndTime></tds:GetSystemDateAndTimeResponse>")
    if not _xac_thuc_ok(cam, than):
        return 400, _loi("Sender not Authorized")
    goc = f"http://{cam.ip}:{cam.http}"
    if co("GetDeviceInformation"):
        return 200, _boc(f"<tds:GetDeviceInformationResponse><tds:Manufacturer>{cam.hang}</tds:Manufacturer>"
                         f"<tds:Model>{cam.model}</tds:Model><tds:FirmwareVersion>{cam.firmware}</tds:FirmwareVersion>"
                         f"<tds:SerialNumber>{_serial(cam)}</tds:SerialNumber><tds:HardwareId>1</tds:HardwareId>"
                         "</tds:GetDeviceInformationResponse>")
    if co("SetNetworkInterfaces"):
        m = re.search(r"<tt:Address>([\d.]+)<", than)
        if m:
            cam.ip_lan = m.group(1)
        return 200, _boc("<tds:SetNetworkInterfacesResponse><tds:RebootNeeded>false</tds:RebootNeeded></tds:SetNetworkInterfacesResponse>")
    if co("GetNetworkInterfaces"):
        return 200, _boc('<tds:GetNetworkInterfacesResponse><tds:NetworkInterfaces token="eth0"><tt:Enabled>true</tt:Enabled>'
                         f"<tt:Info><tt:Name>eth0</tt:Name><tt:HwAddress>{cam.mac}</tt:HwAddress></tt:Info>"
                         "</tds:NetworkInterfaces></tds:GetNetworkInterfacesResponse>")
    if co("GetCapabilities"):
        return 200, _boc(f"<tds:GetCapabilitiesResponse><tds:Capabilities><tt:Media><tt:XAddr>{goc}/onvif/media_service</tt:XAddr>"
                         "</tt:Media></tds:Capabilities></tds:GetCapabilitiesResponse>")
    if co("GetProfiles"):
        return 200, _boc('<trt:GetProfilesResponse><trt:Profiles token="Profile_1" fixed="true"><tt:Name>chinh</tt:Name></trt:Profiles>'
                         '<trt:Profiles token="Profile_2" fixed="true"><tt:Name>phu</tt:Name></trt:Profiles></trt:GetProfilesResponse>')
    if co("GetSnapshotUri"):
        return 200, _boc(f"<trt:GetSnapshotUriResponse><trt:MediaUri><tt:Uri>{goc}/anh.jpg</tt:Uri></trt:MediaUri></trt:GetSnapshotUriResponse>")
    if co("GetStreamUri"):
        tk = (re.search(r"ProfileToken>(.*?)<", than) or [None, "Profile_1"])[1]
        duong = "/Streaming/Channels/102" if tk.endswith("2") else "/Streaming/Channels/101"
        return 200, _boc(f"<trt:GetStreamUriResponse><trt:MediaUri><tt:Uri>rtsp://{cam.ip}:{cam.rtsp}{duong}</tt:Uri></trt:MediaUri></trt:GetStreamUriResponse>")
    if co("SetNetworkProtocols"):
        for ten, port in re.findall(r"<tt:Name>\s*(\w+)\s*</tt:Name>.*?<tt:Port>\s*(\d+)", than, re.S):
            if ten.upper() == "RTSP":
                cam.rtsp_khai = int(port)
            if ten.upper() == "HTTP":
                cam.http_khai = int(port)
        return 200, _boc("<tds:SetNetworkProtocolsResponse/>")
    if co("GetNetworkProtocols"):
        return 200, _boc("<tds:GetNetworkProtocolsResponse>"
                         f"<tds:NetworkProtocols><tt:Name>HTTP</tt:Name><tt:Enabled>true</tt:Enabled><tt:Port>{getattr(cam, 'http_khai', cam.http)}</tt:Port></tds:NetworkProtocols>"
                         f"<tds:NetworkProtocols><tt:Name>RTSP</tt:Name><tt:Enabled>true</tt:Enabled><tt:Port>{getattr(cam, 'rtsp_khai', cam.rtsp)}</tt:Port></tds:NetworkProtocols>"
                         "</tds:GetNetworkProtocolsResponse>")
    if co("SetNetworkDefaultGateway"):
        m = re.search(r"IPv4Address>([\d.]+)<", than)
        if m:
            cam.gw = m.group(1)
        return 200, _boc("<tds:SetNetworkDefaultGatewayResponse/>")
    if co("GetNetworkDefaultGateway"):
        return 200, _boc(f"<tds:GetNetworkDefaultGatewayResponse><tds:NetworkGateway><tt:IPv4Address>{cam.gw}</tt:IPv4Address>"
                         "</tds:NetworkGateway></tds:GetNetworkDefaultGatewayResponse>")
    if co("SetDNS"):
        m = re.search(r"IPv4Address>([\d.]+)<", than)
        if m:
            cam.dns = m.group(1)
        return 200, _boc("<tds:SetDNSResponse/>")
    if co("GetDNS"):
        return 200, _boc("<tds:GetDNSResponse><tds:DNSInformation><tt:FromDHCP>false</tt:FromDHCP><tt:DNSManual><tt:Type>IPv4</tt:Type>"
                         f"<tt:IPv4Address>{cam.dns}</tt:IPv4Address></tt:DNSManual></tds:DNSInformation></tds:GetDNSResponse>")
    if co("GetSystemLog"):
        dong = ["%s system running" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 86400 * 3))]
        dong += ["%s System startup" % time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) for t in (cam.khoi_dong or [])]
        return 200, _boc("<tds:GetSystemLogResponse><tds:SystemLog><tt:String>" + "\n".join(dong) +
                         "</tt:String></tds:SystemLog></tds:GetSystemLogResponse>")
    if co("SystemReboot"):
        cam.so_lan_reboot += 1
        cam.khoi_dong = list(cam.khoi_dong or []) + [time.time()]
        return 200, _boc("<tds:SystemRebootResponse><tds:Message>Rebooting</tds:Message></tds:SystemRebootResponse>")
    if co("GetUsers"):
        return 200, _boc("<tds:GetUsersResponse>" + "".join(
            f"<tds:User><tt:Username>{t}</tt:Username><tt:UserLevel>{m}</tt:UserLevel></tds:User>" for t, m in cam.users) +
            "</tds:GetUsersResponse>")
    if co("CreateUsers") or co("SetUser"):
        t = (re.search(r"Username>(.*?)<", than.split("Body", 1)[-1]) or [None, ""])[1]
        m = (re.search(r"UserLevel>(.*?)<", than) or [None, "User"])[1]
        if not cam.cho_tao_user:
            return 400, _loi("Action not supported")
        mk = re.search(r"Password>(.*?)<", than.split("Body", 1)[-1])
        cam.users = [x for x in cam.users if x[0] != t] + [(t, m)]
        if mk and t != cam.user:
            cam.mk[t] = mk.group(1).replace("&amp;", "&")
        cam.so_lan_tao_user += 1
        return 200, _boc("<tds:CreateUsersResponse/>")
    if co("DeleteUsers"):
        t = (re.search(r"Username>(.*?)<", than.split("Body", 1)[-1]) or [None, ""])[1]
        cam.users = [x for x in cam.users if x[0] != t]
        return 200, _boc("<tds:DeleteUsersResponse/>")
    return 400, _loi("Action not supported")


def _lop_xu_ly(cam):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _gui(self, ma, than, kieu="text/html", dau=None):
            _tre = float(os.environ.get("CAMLINK_GIA_TRE") or 0)      # độ trễ mạng giả (giây/lượt) để đo tốc độ quét; 0 = tắt
            if _tre:
                time.sleep(_tre)
            if isinstance(than, str):
                than = than.encode()
            self.send_response(ma)
            self.send_header("Content-Type", kieu)
            self.send_header("Content-Length", str(len(than)))
            self.send_header("Connection", "close")
            for k, v in (dau or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(than)

        def do_GET(self):
            if self.path.startswith("/anh.jpg"):
                au = self.headers.get("Authorization", "")
                if not au:
                    return self._gui(401, "", dau={"WWW-Authenticate": 'Basic realm="cam"'})
                if au.startswith("Basic "):
                    tu, _, tp = base64.b64decode(au[6:]).decode(errors="ignore").partition(":")
                    them = (not cam.anh_chi_quan_tri) and tu in cam.mk and cam.mk[tu] == tp and any(x[0] == tu for x in cam.users)
                    if (tu, tp) != (cam.user, cam.pw) and not them:
                        return self._gui(401, "", dau={"WWW-Authenticate": 'Basic realm="cam"'})
                return self._gui(200, _anh_jpg(f"cam {cam.ip}:{cam.http}"), "image/jpeg")
            if cam.isapi and self.path.startswith("/ISAPI/System/deviceInfo"):
                return self._gui(401, "", dau={"WWW-Authenticate": 'Digest realm="isapi", nonce="abc", qop="auth"'})
            if self.path in ("/", "/index.html"):
                return self._gui(200, "<html><title>IP Camera</title></html>")
            self._gui(404, "khong co")

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            than = self.rfile.read(n).decode(errors="ignore") if n else ""
            if self.path.startswith("/onvif/"):
                ma, ra = _tra_loi_onvif(cam, than)
                return self._gui(ma, ra, "application/soap+xml; charset=utf-8")
            self._gui(404, "khong co")
    return H


def _rtsp_phuc_vu(cam, sk):
    realm, nonce = "cam", "0123456789abcdef"
    while True:
        try:
            k, _ = sk.accept()
        except OSError:
            return
        try:
            k.settimeout(5)
            d = b""
            while b"\r\n\r\n" not in d:
                x = k.recv(4096)
                if not x:
                    break
                d += x
            y = d.decode(errors="ignore")
            cseq = (re.search(r"CSeq:\s*(\d+)", y) or [None, "1"])[1]
            url = (re.match(r"\w+ (\S+)", y) or [None, ""])[1]
            m = re.search(r'response="([0-9a-f]+)"', y)
            ha1 = hashlib.md5(f"{cam.user}:{realm}:{cam.pw}".encode()).hexdigest()
            ha2 = hashlib.md5(f"DESCRIBE:{url}".encode()).hexdigest()
            dung = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
            if not m or m.group(1) != dung:
                tl = f'RTSP/1.0 401 Unauthorized\r\nCSeq: {cseq}\r\nWWW-Authenticate: Digest realm="{realm}", nonce="{nonce}"\r\n\r\n'
            else:
                sdp = ("v=0\r\no=- 0 0 IN IP4 0.0.0.0\r\ns=cam\r\nt=0 0\r\nm=video 0 RTP/AVP 96\r\n"
                       "a=rtpmap:96 H264/90000\r\na=control:trackID=0\r\n")
                tl = (f"RTSP/1.0 200 OK\r\nCSeq: {cseq}\r\nContent-Base: {url}/\r\nContent-Type: application/sdp\r\n"
                      f"Content-Length: {len(sdp)}\r\n\r\n{sdp}")
            k.sendall(tl.encode())
        except OSError:
            pass
        finally:
            try:
                k.close()
            except OSError:
                pass


def bat(cam):
    """Mở web (ONVIF + ảnh chụp) ở cam.ip:cam.http và RTSP ở cam.ip:cam.rtsp."""
    ThreadingHTTPServer.allow_reuse_address = True
    web = ThreadingHTTPServer((cam.ip, cam.http), _lop_xu_ly(cam))
    web.daemon_threads = True
    threading.Thread(target=web.serve_forever, daemon=True).start()
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sk.bind((cam.ip, cam.rtsp)); sk.listen(16)
    threading.Thread(target=_rtsp_phuc_vu, args=(cam, sk), daemon=True).start()
    with _KHOA:
        _DANG_CHAY.append((cam, web, sk))
    return cam


def tat(cam):
    with _KHOA:
        cua = [x for x in _DANG_CHAY if x[0] is cam]
        for x in cua:
            _DANG_CHAY.remove(x)
    for _, web, sk in cua:
        try:
            web.shutdown(); web.server_close()
        except OSError:
            pass
        try:
            sk.close()
        except OSError:
            pass


def tat_het():
    with _KHOA:
        ds = [x[0] for x in _DANG_CHAY]
    for c in ds:
        tat(c)
