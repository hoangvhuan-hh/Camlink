"""QUẢN TRỊ & KHÔI PHỤC (Huan chốt 15/11/2026).

Mục tiêu: thợ rút là KHÔNG can thiệp được vào hệ thống; chỉ CHỦ mới xem/đổi; tránh "ai cài thì ôm luôn điểm".

Ba vai trong MỘT tài khoản:
  - CHỦ  : toàn quyền trên hệ của mình. Máy tin cậy mở két bằng PIN/vân tay, không xin ai, offline cũng được.
  - THỢ  : máy lạ, phải có PHIÊN do chủ cấp (mã một lần hoặc cấp cho máy), quyền hẹp, TỰ HẾT HẠN, chủ thu hồi một chạm.
           Thợ bấm nút cho app tự thao tác — KHÔNG đọc được mật khẩu, không sửa cấu hình ngoài phạm vi.
  - XEM  : khách/IOC, chỉ xem. Đổi mật khẩu admin / thu hồi thợ KHÔNG đụng tài khoản Xem → khách không gián đoạn.

Két mã hoá ĐẦU-CUỐI (chủ giữ khoá): chủ app không đọc được. Khoá dữ liệu bọc hai lần — bằng PIN và bằng MÃ KHÔI PHỤC
(chủ ghi ra giấy). Mất hết máy thì mở lại bằng mã khôi phục; mất cả hai thì không ai mở được (đó là ý nghĩa "kín").

Mã hoá chỉ dùng thư viện chuẩn (hashlib/hmac/secrets) — KHÔNG thêm phụ thuộc cho APK:
  khoá = PBKDF2-HMAC-SHA256(200k); mã dòng = HMAC-SHA256 chế độ đếm (CTR); mã hoá-rồi-ký (encrypt-then-MAC).

Module này CHỈ THÊM, không sửa/bỏ logic cũ. Khi xoay mật khẩu, nó ghi mật khẩu mới vào đúng chỗ CamLink đang dùng để
kiểm tra từ xa và đẩy cảnh báo lên LiteMark (doc_cai_dat + user/pass từng điểm) → liên kết LiteMark KHÔNG đứt.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

GOC = ""
_PBKDF = 200_000

# ------- vai & quyền -------
CHU, THO, XEM, KHONG = "chu", "tho", "xem", "khong"
# thao tác thợ được phép (quyền hẹp) — admin/xoá/đổi cấu hình KHÔNG nằm ở đây
THO_DUOC = {"kiem_tra", "khoi_dong_cam", "chup_anh", "xem_live", "theo_doi", "dat_port_rtsp"}


def khoi_tao(goc):
    global GOC
    GOC = goc
    os.makedirs(os.path.join(goc, "quantri"), exist_ok=True)


def _f(ten):
    return os.path.join(GOC, "quantri", ten)


def _doc(ten, md=None):
    try:
        with open(_f(ten), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {} if md is None else md


def _ghi(ten, d):
    os.makedirs(os.path.join(GOC, "quantri"), exist_ok=True)
    with open(_f(ten), "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)


# ===================================================================== mã hoá (stdlib)
def _khoa(mat_khau, muoi):
    return hashlib.pbkdf2_hmac("sha256", mat_khau.encode("utf-8"), muoi, _PBKDF, dklen=32)


def _dong_ma(khoa, nonce, n):
    out = b""
    i = 0
    while len(out) < n:
        out += hmac.new(khoa, nonce + i.to_bytes(4, "big"), hashlib.sha256).digest()
        i += 1
    return out[:n]


def _boc(khoa, du_lieu):
    """encrypt-then-MAC → b64(nonce16 + ct + tag32)."""
    nonce = secrets.token_bytes(16)
    ct = bytes(a ^ b for a, b in zip(du_lieu, _dong_ma(khoa, nonce, len(du_lieu))))
    tag = hmac.new(khoa, b"MAC" + nonce + ct, hashlib.sha256).digest()
    return base64.b64encode(nonce + ct + tag).decode()


def _mo_boc(khoa, chuoi):
    raw = base64.b64decode(chuoi)
    nonce, ct, tag = raw[:16], raw[16:-32], raw[-32:]
    if not hmac.compare_digest(tag, hmac.new(khoa, b"MAC" + nonce + ct, hashlib.sha256).digest()):
        raise ValueError("Sai PIN / mã khôi phục, hoặc dữ liệu hỏng")
    return bytes(a ^ b for a, b in zip(ct, _dong_ma(khoa, nonce, len(ct))))


# ===================================================================== tài khoản chủ + két
def da_tao():
    return bool(_doc("taikhoan.json"))


def tao_tai_khoan(pin, thiet_bi_id, ten_may="Máy chủ"):
    """Lần đầu: tạo tài khoản chủ. Trả MÃ KHÔI PHỤC (hiện 1 lần, chủ ghi ra giấy). Máy này thành máy tin cậy."""
    if da_tao():
        raise RuntimeError("Tài khoản đã tạo")
    khoa_dl = secrets.token_bytes(32)                 # khoá dữ liệu thật của két
    ma_khoi_phuc = "-".join(secrets.token_hex(2).upper() for _ in range(6))   # VD AB12-... (12 nhóm hex)
    m_pin, m_rec = secrets.token_bytes(16), secrets.token_bytes(16)
    tk = {"salt_pin": base64.b64encode(m_pin).decode(), "salt_rec": base64.b64encode(m_rec).decode(),
          "boc_pin": _boc(_khoa(pin, m_pin), khoa_dl), "boc_rec": _boc(_khoa(ma_khoi_phuc, m_rec), khoa_dl),
          "tao_luc": time.time()}
    _ghi("taikhoan.json", tk)
    _ghi("ket.enc", {"blob": _boc(khoa_dl, json.dumps({"diem": {}}).encode())})
    _ghi("thietbi.json", {"ds": [{"id": thiet_bi_id, "ten": ten_may, "luc": time.time()}]})
    _nhat_ky(thiet_bi_id, CHU, "tao_tai_khoan", "")
    return ma_khoi_phuc


def _lay_khoa_dl(pin=None, ma_khoi_phuc=None):
    tk = _doc("taikhoan.json")
    if not tk:
        raise RuntimeError("Chưa tạo tài khoản")
    if pin is not None:
        return _mo_boc(_khoa(pin, base64.b64decode(tk["salt_pin"])), tk["boc_pin"])
    if ma_khoi_phuc is not None:
        return _mo_boc(_khoa(ma_khoi_phuc.strip().upper(), base64.b64decode(tk["salt_rec"])), tk["boc_rec"])
    raise ValueError("Cần PIN hoặc mã khôi phục")


def doi_pin(pin_cu, pin_moi):
    khoa_dl = _lay_khoa_dl(pin=pin_cu)
    tk = _doc("taikhoan.json")
    m = secrets.token_bytes(16)
    tk["salt_pin"], tk["boc_pin"] = base64.b64encode(m).decode(), _boc(_khoa(pin_moi, m), khoa_dl)
    _ghi("taikhoan.json", tk)
    return True


def _doc_ket(khoa_dl):
    return json.loads(_mo_boc(khoa_dl, _doc("ket.enc")["blob"]).decode())


def _ghi_ket(khoa_dl, ket):
    _ghi("ket.enc", {"blob": _boc(khoa_dl, json.dumps(ket, ensure_ascii=False).encode())})


# ===================================================================== thiết bị tin cậy (máy của chủ)
def thiet_bi_tin_cay(thiet_bi_id):
    return any(x["id"] == thiet_bi_id for x in _doc("thietbi.json", {"ds": []})["ds"])


def them_thiet_bi(pin, thiet_bi_id, ten_may):
    """Chủ thêm máy của mình (điện thoại phụ, máy văn phòng). Phải mở được bằng PIN để xác là chủ."""
    _lay_khoa_dl(pin=pin)
    tb = _doc("thietbi.json", {"ds": []})
    if not thiet_bi_tin_cay(thiet_bi_id):
        tb["ds"].append({"id": thiet_bi_id, "ten": ten_may, "luc": time.time()})
        _ghi("thietbi.json", tb)
    _nhat_ky(thiet_bi_id, CHU, "them_thiet_bi", ten_may)
    return True


def go_thiet_bi(pin, thiet_bi_id):
    _lay_khoa_dl(pin=pin)
    tb = _doc("thietbi.json", {"ds": []})
    tb["ds"] = [x for x in tb["ds"] if x["id"] != thiet_bi_id]
    _ghi("thietbi.json", tb)
    _nhat_ky(thiet_bi_id, CHU, "go_thiet_bi", thiet_bi_id)
    return True


# ===================================================================== phiên thợ
def _bam(s):
    return hashlib.sha256(s.encode()).hexdigest()


def cap_ma_mot_lan(pin, pham_vi, gio=24):
    """Chủ sinh MÃ MỘT LẦN cho thợ (6 số). pham_vi: 'ma_du_an' hoặc 'ma_du_an:stt'. Thợ nhập mã để xin phiên."""
    _lay_khoa_dl(pin=pin)
    ma = f"{secrets.randbelow(1000000):06d}"
    ph = _doc("phien.json", {"ds": []})
    ph["ds"].append({"loai": "ma", "bam": _bam(ma), "pham_vi": pham_vi, "gio": gio,
                     "het_luc": time.time() + gio * 3600, "da_dung": False, "thu_hoi": False, "cap_luc": time.time()})
    _ghi("phien.json", ph)
    _nhat_ky("chu", CHU, "cap_ma_mot_lan", pham_vi)
    return ma


def cap_phien_may(pin, thiet_bi_id, pham_vi, gio=24):
    """Chủ cấp phiên thẳng cho một máy thợ đã biết id."""
    _lay_khoa_dl(pin=pin)
    ph = _doc("phien.json", {"ds": []})
    ph["ds"].append({"loai": "may", "thiet_bi": thiet_bi_id, "pham_vi": pham_vi, "gio": gio,
                     "het_luc": time.time() + gio * 3600, "thu_hoi": False, "cap_luc": time.time()})
    _ghi("phien.json", ph)
    _nhat_ky(thiet_bi_id, CHU, "cap_phien_may", pham_vi)
    return True


def tho_dung_ma(ma, thiet_bi_id):
    """Máy thợ nhập mã một lần → gắn máy vào phiên."""
    ph = _doc("phien.json", {"ds": []})
    for p in ph["ds"]:
        if p.get("loai") == "ma" and not p["da_dung"] and not p["thu_hoi"] and time.time() < p["het_luc"] \
                and hmac.compare_digest(p["bam"], _bam(ma)):
            p["da_dung"] = True
            p["thiet_bi"] = thiet_bi_id
            _ghi("phien.json", ph)
            _nhat_ky(thiet_bi_id, THO, "tho_dung_ma", p["pham_vi"])
            return True
    _nhat_ky(thiet_bi_id, THO, "tho_dung_ma_that_bai", "")
    return False


def thu_hoi_phien(pin, chi_so=None, thiet_bi_id=None):
    """Chủ thu hồi: một phiên (chi_so), hoặc mọi phiên của một máy, hoặc TẤT CẢ."""
    _lay_khoa_dl(pin=pin)
    ph = _doc("phien.json", {"ds": []})
    for i, p in enumerate(ph["ds"]):
        if chi_so is not None and i == chi_so:
            p["thu_hoi"] = True
        elif thiet_bi_id is not None and p.get("thiet_bi") == thiet_bi_id:
            p["thu_hoi"] = True
        elif chi_so is None and thiet_bi_id is None:
            p["thu_hoi"] = True
    _ghi("phien.json", ph)
    _nhat_ky(thiet_bi_id or "chu", CHU, "thu_hoi_phien", str(chi_so if chi_so is not None else thiet_bi_id or "tat_ca"))
    return True


def _phien_hop_le(thiet_bi_id, pham_vi):
    """Máy thợ còn phiên sống cho phạm vi này? (pham_vi của phiên là tiền tố của pham_vi yêu cầu)."""
    for p in _doc("phien.json", {"ds": []})["ds"]:
        if p.get("thiet_bi") != thiet_bi_id or p.get("thu_hoi") or time.time() >= p.get("het_luc", 0):
            continue
        pv = p.get("pham_vi", "")
        if pham_vi == pv or pham_vi.startswith(pv + ":") or pv == "*":
            return True
    return False


def quyen(thiet_bi_id, pham_vi=""):
    """Vai hiện tại của MÁY này với một điểm/dự án. Máy chủ = CHỦ; máy có phiên sống = THỢ; còn lại = KHÔNG."""
    if thiet_bi_tin_cay(thiet_bi_id):
        return CHU
    if _phien_hop_le(thiet_bi_id, pham_vi):
        return THO
    return KHONG


# ===================================================================== két mật khẩu (chỉ chủ đọc được)
def _diem_khoa(ma, stt):
    return f"{ma}:{stt}"


def luu_mat_khau(pin, ma, stt, cam_user, cam_pw, modem_user="", modem_pw="", ddns=None):
    """Chủ lưu user/pass của một điểm vào két (mã hoá)."""
    khoa_dl = _lay_khoa_dl(pin=pin)
    ket = _doc_ket(khoa_dl)
    d = ket["diem"].setdefault(_diem_khoa(ma, stt), {})
    d.update({"cam_user": cam_user, "cam_pw": cam_pw})
    if modem_pw:
        d.update({"modem_user": modem_user, "modem_pw": modem_pw})
    if ddns is not None:
        d["ddns"] = ddns
    _ghi_ket(khoa_dl, ket)
    _nhat_ky("chu", CHU, "luu_mat_khau", _diem_khoa(ma, stt))
    return True


def nap_tu_cai_dat(pin, ma, ds_diem, cd):
    """Gom user/pass sẵn có (doc_cai_dat + từng điểm) vào két — không bắt nhập lại."""
    khoa_dl = _lay_khoa_dl(pin=pin)
    ket = _doc_ket(khoa_dl)
    for p in ds_diem:
        d = ket["diem"].setdefault(_diem_khoa(ma, str(p.get("stt"))), {})
        d.setdefault("cam_user", p.get("user") or cd.get("cam_user", "admin"))
        d.setdefault("cam_pw", p.get("pass") or cd.get("cam_pw", ""))
        d.setdefault("modem_user", cd.get("modem_user", "admin"))
        d.setdefault("modem_pw", cd.get("modem_pw", ""))
    _ghi_ket(khoa_dl, ket)
    _nhat_ky("chu", CHU, "nap_tu_cai_dat", f"{len(ds_diem)} điểm")
    return len(ds_diem)


def xem_mat_khau(thiet_bi_id, ma, stt, pin=None):
    """ĐỌC mật khẩu: CHỈ CHỦ. Thợ gọi hàm này luôn bị từ chối (đây là chốt chặn 'thợ ôm điểm')."""
    if quyen(thiet_bi_id) != CHU:
        _nhat_ky(thiet_bi_id, quyen(thiet_bi_id), "xem_mat_khau_tu_choi", _diem_khoa(ma, stt))
        raise PermissionError("Chỉ chủ tài khoản mới xem được mật khẩu")
    khoa_dl = _lay_khoa_dl(pin=pin)
    _nhat_ky(thiet_bi_id, CHU, "xem_mat_khau", _diem_khoa(ma, stt))
    return _doc_ket(khoa_dl)["diem"].get(_diem_khoa(ma, stt), {})


def _creds_noi_bo(ma, stt, pin):
    """Lấy creds để app TỰ thao tác (không trả cho người gọi là thợ). Dùng nội bộ bởi thao_tac()."""
    return _doc_ket(_lay_khoa_dl(pin=pin))["diem"].get(_diem_khoa(ma, stt), {})


# ===================================================================== thao tác có kiểm soát vai
def thao_tac(thiet_bi_id, ma, stt, viec, chay, pin=None):
    """Cổng thực thi: kiểm vai + phạm vi + phiên rồi mới chạy. 'chay' là callback nhận creds, app tự làm.
    Thợ: chỉ các viec trong THO_DUOC, và app tự lấy creds trong két để chạy — thợ KHÔNG thấy mật khẩu.
    Trả: {"ok":bool, "ket_qua" / "loi"}."""
    pham_vi = _diem_khoa(ma, stt)
    vai = quyen(thiet_bi_id, pham_vi)
    if vai == KHONG:
        _nhat_ky(thiet_bi_id, KHONG, "thao_tac_tu_choi", f"{viec}@{pham_vi}")
        return {"ok": False, "loi": "Máy chưa được cấp quyền. Xin chủ cấp phiên hoặc mã."}
    if vai == THO and viec not in THO_DUOC:
        _nhat_ky(thiet_bi_id, THO, "thao_tac_ngoai_pham_vi", f"{viec}@{pham_vi}")
        return {"ok": False, "loi": f"Thợ không có quyền '{viec}'. Việc này chỉ chủ làm được."}
    # creds: chủ mở bằng PIN; thợ → app dùng creds đã được chủ phát cho phiên (trong thực tế máy chủ phát;
    # ở local test truyền pin để mô phỏng việc app tự lấy creds, KHÔNG trả creds ra cho lớp gọi).
    try:
        creds = _creds_noi_bo(ma, stt, pin) if pin is not None else {}
    except Exception as e:
        return {"ok": False, "loi": f"Không mở được két: {e}"}
    try:
        kq = chay(creds)
    except Exception as e:
        _nhat_ky(thiet_bi_id, vai, "thao_tac_loi", f"{viec}@{pham_vi}: {e}")
        return {"ok": False, "loi": str(e)}
    _nhat_ky(thiet_bi_id, vai, f"thao_tac:{viec}", pham_vi)
    return {"ok": True, "ket_qua": kq}


# ===================================================================== tài khoản Xem (khách/IOC)
def tao_tai_khoan_xem(pin, thiet_bi_id, ma, stt, user, pw, tao_tren_cam):
    """Tạo tài khoản CHỈ XEM cho khách trên cam (callback tao_tren_cam(creds, user, pw)). Lưu vào két riêng vai XEM."""
    if quyen(thiet_bi_id) != CHU:
        raise PermissionError("Chỉ chủ tạo được tài khoản Xem")
    creds = _creds_noi_bo(ma, stt, pin)
    tao_tren_cam(creds, user, pw)
    khoa_dl = _lay_khoa_dl(pin=pin)
    ket = _doc_ket(khoa_dl)
    ket["diem"].setdefault(_diem_khoa(ma, stt), {}).setdefault("xem", []).append({"user": user, "pw": pw, "luc": time.time()})
    _ghi_ket(khoa_dl, ket)
    _nhat_ky(thiet_bi_id, CHU, "tao_tai_khoan_xem", f"{_diem_khoa(ma, stt)} user={user}")
    return True


# ===================================================================== xoay mật khẩu (không đụng tài khoản Xem)
def xoay_mat_khau(pin, thiet_bi_id, ma, stt, mat_khau_moi, doi_tren_cam, dong_bo_litemark, gom=("cam",)):
    """Đổi mật khẩu ADMIN cam (và/hoặc modem) sang giá trị mới chỉ chủ giữ.
    doi_tren_cam(creds_cu, loai, mk_moi): thực đổi trên thiết bị (loai='cam'/'modem').
    dong_bo_litemark(stt, cam_user, cam_pw): ghi mật khẩu mới vào chỗ CamLink dùng kiểm/đẩy LiteMark → KHÔNG đứt liên kết.
    KHÔNG đụng mục 'xem' trong két → khách vẫn xem bình thường."""
    if quyen(thiet_bi_id) != CHU:
        raise PermissionError("Chỉ chủ xoay được mật khẩu")
    khoa_dl = _lay_khoa_dl(pin=pin)
    ket = _doc_ket(khoa_dl)
    d = ket["diem"].setdefault(_diem_khoa(ma, stt), {})
    creds_cu = dict(d)
    for loai in gom:
        doi_tren_cam(creds_cu, loai, mat_khau_moi)
        if loai == "cam":
            d["cam_pw"] = mat_khau_moi
        elif loai == "modem":
            d["modem_pw"] = mat_khau_moi
    _ghi_ket(khoa_dl, ket)
    if "cam" in gom:
        dong_bo_litemark(stt, d.get("cam_user", "admin"), mat_khau_moi)   # giữ liên kết LiteMark
    _nhat_ky(thiet_bi_id, CHU, "xoay_mat_khau", f"{_diem_khoa(ma, stt)} gồm {'+'.join(gom)}")
    return True


# ===================================================================== khôi phục khi quên (từ xa, không reset vật lý)
def khoi_phuc_quen(pin, thiet_bi_id, ma, stt, lay_ma_thu, tinh_ma_mo, dat_lai_admin, nap_lai_cau_hinh, dong_bo_litemark,
                   mat_khau_moi):
    """Cam quên hết mật khẩu → khôi phục qua đường chính hãng, KHÔNG cần nút reset vật lý:
      lay_ma_thu()               → đọc mã thử (challenge) + serial từ cam qua mạng (trước đăng nhập).
      tinh_ma_mo(ma_thu, serial) → mã mở trong ngày (app tự tính nếu hãng cho công thức, hoặc chủ nhập mã từ đại lý).
      dat_lai_admin(ma_mo, mk)   → dùng mã mở đặt lại mật khẩu admin.
      nap_lai_cau_hinh(creds)    → nạp lại IP/port/NAT/DDNS từ hồ sơ điểm.
    Chạy lặp lại bao nhiêu lần cũng được (mã mở không dính mật khẩu khách đặt)."""
    if quyen(thiet_bi_id) != CHU:
        raise PermissionError("Chỉ chủ khôi phục được")
    ma_thu, serial = lay_ma_thu()
    ma_mo = tinh_ma_mo(ma_thu, serial)
    if not ma_mo:
        return {"ok": False, "loi": "Chưa có mã mở. Gửi mã thử cho đại lý Oryza lấy mã mở trong ngày.",
                "ma_thu": ma_thu, "serial": serial}
    dat_lai_admin(ma_mo, mat_khau_moi)
    khoa_dl = _lay_khoa_dl(pin=pin)
    ket = _doc_ket(khoa_dl)
    d = ket["diem"].setdefault(_diem_khoa(ma, stt), {})
    d["cam_pw"] = mat_khau_moi
    _ghi_ket(khoa_dl, ket)
    nap_lai_cau_hinh(dict(d))
    dong_bo_litemark(stt, d.get("cam_user", "admin"), mat_khau_moi)
    _nhat_ky(thiet_bi_id, CHU, "khoi_phuc_quen", _diem_khoa(ma, stt))
    return {"ok": True, "ma_thu": ma_thu, "serial": serial}


# ===================================================================== nhật ký (ai-làm-gì-lúc-nào)
def _nhat_ky(thiet_bi_id, vai, viec, muc_tieu):
    try:
        with open(_f("nhatky.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"luc": time.time(), "may": thiet_bi_id, "vai": vai, "viec": viec, "muc": muc_tieu},
                                ensure_ascii=False) + "\n")
    except OSError:
        pass


def nhat_ky(n=200):
    try:
        with open(_f("nhatky.jsonl"), encoding="utf-8") as fh:
            dong = fh.readlines()[-n:]
        return [json.loads(x) for x in dong]
    except OSError:
        return []


def phien_dang_song():
    return [dict(p, chi_so=i) for i, p in enumerate(_doc("phien.json", {"ds": []})["ds"])
            if not p.get("thu_hoi") and time.time() < p.get("het_luc", 0)]
