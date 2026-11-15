"""Giao tiếp web API cam Oryza (POST /action/WEB_JsonAjax, XML CommandHead, xác thực XDigest SHA-256).
Giao thức đọc từ JS giao diện web của chính cam (xem camlink/oryza/GIAO_THUC.md)."""
import base64, hashlib, random, re
import xml.etree.ElementTree as ET
import requests
import rsa

DUONG = "/action/WEB_JsonAjax"


def _h(s):
    return hashlib.sha256(s.encode()).hexdigest()


def _esc(v):
    s = str(v).lower() if isinstance(v, bool) else str(v)
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&apos;")


def _phan_tu(ten, o):
    """Giống hàm N của cam: thuộc tính nguyên thuỷ -> attribute, object/list -> phần tử con."""
    if isinstance(o, list):
        if "List" in ten:
            ben_trong = "".join(_phan_tu(k, v) for it in o for k, v in it.items())
            return f"<{ten}>{ben_trong}</{ten}>"
        return "".join(_phan_tu(ten, it) for it in o)
    at = "".join(f' {k}="{_esc(v)}"' for k, v in o.items() if not isinstance(v, (dict, list)))
    con = "".join(_phan_tu(k, v) for k, v in o.items() if isinstance(v, (dict, list)))
    return f"<{ten}{at}>{con}</{ten}>" if con else f"<{ten}{at}/>"


def tao_xml(cmd, than, sid=""):
    s = f' SessionId="{sid}"' if sid else ""
    n = "".join(_phan_tu(k, v) for k, v in (than or {}).items())
    return (f'<?xml version="1.0" encoding="UTF-8"?><CommandHead Command="{cmd}"{s}>'
            f'<Parameters Version="1">{n}</Parameters></CommandHead>')


def _sang_dict(e):
    d = dict(e.attrib)
    for c in e:
        v = _sang_dict(c)
        if c.tag in d:
            if not isinstance(d[c.tag], list):
                d[c.tag] = [d[c.tag]]
            d[c.tag].append(v)
        else:
            d[c.tag] = v
    return d


def doc_xml(t):
    goc = ET.fromstring(re.sub(r"^\s*<\?xml[^>]*\?>", "", t.strip()))
    p = goc.find("Parameters")
    return _sang_dict(p if p is not None else goc)


def ma_kq(d):
    try:
        return int((d.get("Result") or {}).get("Code", -1))
    except (TypeError, ValueError):
        return -1


def la_oryza(ip, port, cho=4):
    try:
        r = requests.post(f"http://{ip}:{port}{DUONG}", data=tao_xml(11027, {"DigestAuthentication": {"OperatorType": 2}}),
                          timeout=cho, headers={"Content-Type": "application/xml"})
        return r.status_code == 401 and "xdigest" in r.headers.get("WWW-Authenticate", "").lower()
    except requests.RequestException:
        return False


def ma_hoa_rsa(khoa, chu):
    k = (khoa or "").strip()
    if "BEGIN" not in k:
        k = "-----BEGIN PUBLIC KEY-----\n" + "\n".join(k[i:i + 64] for i in range(0, len(k), 64)) + "\n-----END PUBLIC KEY-----"
    if "BEGIN RSA PUBLIC KEY" in k:
        pub = rsa.PublicKey.load_pkcs1(k.encode())
    else:
        try:
            pub = rsa.PublicKey.load_pkcs1_openssl_pem(k.encode())
        except Exception:
            pub = rsa.PublicKey.load_pkcs1(k.replace("PUBLIC KEY", "RSA PUBLIC KEY").encode())
    return base64.b64encode(rsa.encrypt(chu.encode(), pub)).decode()


LOI_DANG_NHAP = {-507: "sai user/pass cam", -508: "sai user/pass cam", -511: "cam đã đủ số người đăng nhập",
                 -520: "cam đã đủ số người đăng nhập", -515: "cam đang bị khoá do nhập sai nhiều lần"}


class Oryza:
    def __init__(self, ip, port, user, pw, cho=10):
        self.ip, self.port, self.user, self.pw, self.cho = ip, port, user, pw, cho
        self.url = f"http://{ip}:{port}{DUONG}"
        self.sid = ""
        self.nc = 2
        self.cnonce = base64.b64encode("".join(random.choice("abcdef0123456789") for _ in range(16)).encode()).decode()
        self.realm = self.nonce = ""
        self.qop, self.alg = "auth", "SHA-256"
        self.ivd = ""
        self.mat_khau_mac_dinh = False

    def _post(self, cmd, than, auth=None):
        hd = {"Content-Type": "application/xml"}
        if auth:
            hd["Authorization"] = auth
        return requests.post(self.url, data=tao_xml(cmd, than, self.sid).encode(), headers=hd, timeout=self.cho)

    def _thach(self, r):
        a = r.headers.get("WWW-Authenticate", "")
        for k, v in re.findall(r'(\w+)\s*=\s*"?([^",]*)"?', a.replace("XDigest", "")):
            if k == "realm": self.realm = v
            elif k == "nonce": self.nonce = v
            elif k == "qop": self.qop = v
            elif k == "algorithm": self.alg = v

    def _auth(self, cmd, mk, nc):
        uri = f"active/base/{cmd}"
        ncs = format(nc, "08x")
        resp = _h(f"{_h(f'{self.user}:{self.realm}:{mk}')}:{self.nonce}:{ncs}:{self.cnonce}:{self.qop}:{_h('POST:' + uri)}")
        return (f'XDigest username="{self.user}",realm="{self.realm}",nonce="{self.nonce}",uri="{uri}",'
                f'algorithm="{self.alg}",qop="{self.qop}",nc="{ncs}",cnonce="{self.cnonce}",response="{resp}"')

    def dang_nhap(self):
        r = self._post(11027, {"DigestAuthentication": {"OperatorType": 2}})
        if r.status_code != 401:
            raise RuntimeError(f"cam Oryza không trả lời đăng nhập (mã {r.status_code})")
        self._thach(r)
        self.nc = 2
        r = self._post(11027, {"DigestAuthentication": {"OperatorType": 2}}, self._auth(11027, self.pw, self.nc))
        d = doc_xml(r.text)
        c = ma_kq(d)
        if c != 0:
            raise RuntimeError(LOI_DANG_NHAP.get(c, f"đăng nhập cam lỗi mã {c}"))
        da = d.get("DigestAuthentication") or {}
        self.sid = da.get("SessionId", "")
        if str(da.get("Response")) == "100":
            self.mat_khau_mac_dinh = True
            self.ivd = self.pw
        else:
            self.ivd = _h(f"{self.pw}:{self.sid}")
        return self

    def lenh(self, cmd, than, lan=0):
        self.nc += 1
        r = self._post(cmd, than, self._auth(cmd, self.ivd, self.nc))
        if r.status_code in (401, 413):
            d = {}
            try:
                d = doc_xml(r.text)
            except Exception:
                pass
            if ma_kq(d) in (-512, -669) or lan:
                raise RuntimeError("phiên đăng nhập cam hết hạn")
            self._thach(r)
            self.nc = 1
            return self.lenh(cmd, than, 1)
        if r.status_code != 200:
            raise RuntimeError(f"lệnh {cmd} lỗi HTTP {r.status_code}")
        return doc_xml(r.text)

    def dang_xuat(self):
        try:
            uri_nc = self.nc + 1
            ncs = format(uri_nc, "08x")
            uri = "active/base/11027"
            resp = _h(f"{_h(f'{self.user}:{self.realm}:{self.ivd}')}:{self.nonce}:{ncs}:{self.cnonce}:{self.qop}:{_h('POST:' + uri)}")
            self._post(11027, {"DigestAuthentication": {"User": self.user, "Realm": self.realm, "Cnonce": self.cnonce,
                                                        "Qop": self.qop, "Nonce": self.nonce, "Uri": uri, "Nc": ncs,
                                                        "Algorithm": self.alg, "Response": resp, "OperatorType": 3}},
                       self._auth(11027, self.ivd, uri_nc))
        except Exception:
            pass

    # ---------------------------------------------------------------- DDNS
    def nha_cung_cap(self):
        d = self.lenh(32706, {"ChannelId": {"Id": -1}})
        ds = ((d.get("DDNSProviderList") or {}).get("DDNSProvider")) or []
        return ds if isinstance(ds, list) else [ds]

    def doc_ddns(self):
        d = self.lenh(32701, {"ChannelId": {"Id": -1}, "EncodeVerParam": {"EncodeVer": 1}})
        if ma_kq(d) != 0:
            raise RuntimeError(f"đọc DDNS lỗi mã {ma_kq(d)}")
        return d.get("DDNSParam") or {}

    def khoa_cong_khai(self):
        d = self.lenh(11011, {"WebAuthInfo": {"OperatorType": 1}})
        return (d.get("WebAuthInfo") or {}).get("PublicKey", "")


def chon_noip(ds):
    for p in ds:
        n = str(p.get("ProviderName", "")).lower().replace("-", "").replace(" ", "")
        if "noip" in n:
            return p
    return None


def dat_ddns(ip, port, user, pw, dom, du, dp, thu=True):
    """Đăng nhập cam Oryza, bật DDNS No-IP với tên miền/tài khoản của điểm. Trả về chuỗi mô tả kết quả."""
    cam = Oryza(ip, port, user, pw).dang_nhap()
    try:
        ncc = cam.nha_cung_cap()
        p = chon_noip(ncc)
        if not p:
            raise RuntimeError("cam không có nhà cung cấp No-IP (có: " + ", ".join(str(x.get("ProviderName")) for x in ncc) + ")")
        cu = cam.doc_ddns()
        if (str(cu.get("DDNSEnableFlag")).lower() in ("true", "1") and str(cu.get("DDNSProviderId")) == str(p.get("ProviderId"))
                and cu.get("DDNSDomainName") == dom and cu.get("DDNSAccounts") == du):
            return "DDNS đã đúng sẵn (No-IP " + dom + ")"
        moi = {k: v for k, v in cu.items() if not isinstance(v, (dict, list))}
        moi.update({"DDNSEnableFlag": True, "DDNSProviderId": p.get("ProviderId"), "DDNSDomainName": dom,
                    "DDNSAccounts": du, "DDNSPassword": ma_hoa_rsa(cam.khoa_cong_khai(), dp)})
        moi["EncodeVerParam"] = {"EncodeVer": 1}
        than = {"ChannelId": {"Id": -1}, "DDNSParam": moi, "EncodeVerParam": {"EncodeVer": 1}}
        d = cam.lenh(32703, than)
        if ma_kq(d) != 0:
            raise RuntimeError(f"cam từ chối lưu DDNS (mã {ma_kq(d)})")
        sau = cam.doc_ddns()
        if sau.get("DDNSDomainName") != dom:
            raise RuntimeError("đã lưu nhưng đọc lại tên miền không khớp")
        kq = "DDNS đã nhập (No-IP " + dom + ")"
        if thu:
            try:
                t = cam.lenh(32705, than, 0)
                ok = ma_kq(t) == 0 and str((t.get("State") or {}).get("State", "1")) in ("0", "false", "False")
                kq += " · thử kết nối No-IP: " + ("ĐẠT" if ok else "chưa đạt (kiểm tra user/pass No-IP)")
            except Exception as e:
                kq += f" · không thử được ({e})"
        return kq
    finally:
        cam.dang_xuat()


def doc_ddns_cam(ip, port, user, pw):
    """Chỉ đọc cấu hình DDNS trong cam Oryza. Trả dict hoặc ném lỗi."""
    cam = Oryza(ip, port, user, pw).dang_nhap()
    try:
        ncc = {str(p.get("ProviderId")): str(p.get("ProviderName")) for p in cam.nha_cung_cap()}
        d = cam.doc_ddns()
        return {"bat": str(d.get("DDNSEnableFlag")).lower() in ("true", "1"), "ten_mien": d.get("DDNSDomainName", ""),
                "tai_khoan": d.get("DDNSAccounts", ""), "nha_cung_cap": ncc.get(str(d.get("DDNSProviderId")), str(d.get("DDNSProviderId")))}
    finally:
        cam.dang_xuat()


# ------------------------------------------------------------------ KHAI BÁO LẦN ĐẦU (cam mới chưa có mật khẩu)
# Học từ chính giao diện web của cam (loginIndex + index.js, cam Phú Lý firmware v5.2.1629, 15/11/2026):
#  - 30541 (không cần đăng nhập) → DeviceSummaryInfo.ActivateFlag: "true" = đã khai báo, "false" = cam mới → trang tạo mật khẩu
#  - 11015 (không cần đăng nhập) → Result.Code -532: tự đặt tên user quản trị; còn lại: SNString.String = tên user bắt buộc
#  - 11011 {WebAuthInfo:{OperatorType:1}} → Nonce, PublicKey
#  - vt = 16 ký tự [a-f0-9]; Cnonce = base64(vt); khoá AES = utf8(sha256hex(Nonce + Cnonce)[:32]); iv = utf8(vt)
#    L = base64(AES-256-CBC-PKCS7(mật khẩu)); Response = base64(RSA_PKCS1(L))
#  - 11011 {WebAuthInfo:{OperatorType:3, User, Cnonce, Response}} → Result.Code 0 là xong; sau đó đăng nhập như thường
_SB = None


def _sbox():
    global _SB
    if _SB is None:
        p = q = 1
        sb = [0] * 256
        while True:
            p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
            q ^= q << 1
            q ^= q << 2
            q ^= q << 4
            q &= 0xFF
            if q & 0x80:
                q ^= 0x09
            x = q ^ ((q << 1 | q >> 7) & 0xFF) ^ ((q << 2 | q >> 6) & 0xFF) ^ ((q << 3 | q >> 5) & 0xFF) ^ ((q << 4 | q >> 4) & 0xFF)
            sb[p] = (x ^ 0x63) & 0xFF
            if p == 1:
                break
        sb[0] = 0x63
        _SB = sb
    return _SB


def _xt(a):
    return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else a << 1


def _aes_khoa(khoa):
    sb = _sbox()
    nk = len(khoa) // 4
    nr = nk + 6
    w = [list(khoa[4 * i:4 * i + 4]) for i in range(nk)]
    rc = 1
    for i in range(nk, 4 * (nr + 1)):
        t = list(w[i - 1])
        if i % nk == 0:
            t = [sb[t[1]] ^ rc, sb[t[2]], sb[t[3]], sb[t[0]]]
            rc = _xt(rc)
        elif nk > 6 and i % nk == 4:
            t = [sb[x] for x in t]
        w.append([w[i - nk][j] ^ t[j] for j in range(4)])
    return [sum(w[4 * r:4 * r + 4], []) for r in range(nr + 1)], nr


def _aes_khoi(b, ks, nr):
    sb = _sbox()
    st = [b[i] ^ ks[0][i] for i in range(16)]
    for r in range(1, nr + 1):
        st = [sb[x] for x in st]
        st = [st[(i + 4 * (i % 4)) % 16] for i in range(16)]      # ShiftRows (trạng thái xếp theo cột)
        if r != nr:
            m = []
            for c in range(4):
                a = st[4 * c:4 * c + 4]
                x = a[0] ^ a[1] ^ a[2] ^ a[3]
                m += [a[i] ^ x ^ _xt(a[i] ^ a[(i + 1) % 4]) for i in range(4)]
            st = m
        st = [st[i] ^ ks[r][i] for i in range(16)]
    return bytes(st)


def aes_cbc(du_lieu, khoa, iv):
    """AES-CBC + đệm PKCS7, thuần Python (APK không có thư viện AES). Khoá 16/24/32 byte."""
    ks, nr = _aes_khoa(bytes(khoa))
    n = 16 - len(du_lieu) % 16
    du_lieu = bytes(du_lieu) + bytes([n]) * n
    out, truoc = b"", bytes(iv)
    for i in range(0, len(du_lieu), 16):
        truoc = _aes_khoi(bytes(a ^ b for a, b in zip(du_lieu[i:i + 16], truoc)), ks, nr)
        out += truoc
    return out


def _goi_tho(ip, port, cmd, than=None, cho=8):
    r = requests.post(f"http://{ip}:{port}{DUONG}", data=tao_xml(cmd, than).encode(), timeout=cho, headers={"Content-Type": "application/xml"})
    return doc_xml(r.text)


def tom_tat(ip, port, cho=6):
    """Thông tin cam KHÔNG cần đăng nhập (lệnh 30541): model, MAC, firmware, và đã khai báo lần đầu chưa. {} nếu không đọc được."""
    try:
        d = _goi_tho(ip, port, 30541, None, cho)
        return (d.get("DeviceSummaryInfo") or {}) if ma_kq(d) == 0 else {}
    except Exception:
        return {}


def da_khai_bao(ip, port):
    """True = cam đã có mật khẩu; False = cam MỚI chưa khai báo lần đầu; None = không xác định được."""
    f = str(tom_tat(ip, port).get("ActivateFlag", "")).lower()
    return True if f == "true" else False if f == "false" else None


def khai_bao_lan_dau(ip, port, user, pw):
    """Khai báo lần đầu cho cam mới: tạo mật khẩu quản trị. Trả (ok, tên user thực tế, thông báo).
    Chỉ chạy khi cam báo CHƯA khai báo — cam đã có mật khẩu thì không đụng."""
    kb = da_khai_bao(ip, port)
    if kb is True:
        return False, user, "cam đã khai báo từ trước (đã có mật khẩu) — không khai báo lại"
    if kb is None:
        return False, user, "không đọc được trạng thái khai báo của cam"
    if not re.fullmatch(r"[a-zA-Z0-9]{1,20}", user or ""):
        return False, user, "tên user cam chỉ gồm chữ và số, tối đa 20 ký tự"
    if not pw or re.search(r"\s", pw):
        return False, user, "mật khẩu cam trống hoặc có khoảng trắng"
    try:
        d = _goi_tho(ip, port, 11015, None)      # cam có bắt buộc tên user quản trị không
        sn = d.get("SNString") or {}
        sn = sn[0] if isinstance(sn, list) and sn else sn
        ten = str((sn or {}).get("String", "")) if ma_kq(d) == 0 else ""
        if ten and re.fullmatch(r"[a-zA-Z0-9]{1,20}", ten):
            user = ten
    except Exception:
        pass
    try:
        d = _goi_tho(ip, port, 11011, {"WebAuthInfo": {"OperatorType": 1}})
        w = d.get("WebAuthInfo") or {}
        if ma_kq(d) != 0 or not w.get("PublicKey"):
            return False, user, f"cam không cấp khoá mã hoá (mã {ma_kq(d)})"
        vt = "".join(random.choice("abcdef0123456789") for _ in range(16))
        cn = base64.b64encode(vt.encode()).decode()
        khoa = _h(str(w.get("Nonce", "")) + cn)[:32].encode()
        ma = base64.b64encode(aes_cbc(pw.encode(), khoa, vt.encode())).decode()
        d = _goi_tho(ip, port, 11011, {"WebAuthInfo": {"OperatorType": 3, "User": user, "Cnonce": cn, "Response": ma_hoa_rsa(w["PublicKey"], ma)}})
        c = ma_kq(d)
        if c != 0:
            return False, user, f"cam từ chối tạo mật khẩu (mã {c}) — thường do mật khẩu chưa đủ mạnh theo yêu cầu của cam"
        return True, user, f"đã khai báo lần đầu, user quản trị «{user}»"
    except Exception as e:
        return False, user, f"khai báo lần đầu lỗi: {str(e)[:100]}"
