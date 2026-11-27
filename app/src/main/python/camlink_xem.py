"""TÀI KHOẢN CHỈ XEM cho QR hồ sơ (2.14.2 — anh Huan chốt 27/11/2026 20:40).

QR trong "Hồ sơ hệ thống camera hiện tại" mở thẳng ẢNH CAM CHỤP NGAY LÚC QUÉT (link http của tên miền, không cần app).
Hồ sơ là thứ gửi ra ngoài → QR không được mang tài khoản quản trị của cam: app tự tạo trên cam một tài khoản mức 'User' (chỉ xem)
bằng ONVIF chuẩn và chỉ đưa tài khoản đó vào QR. Cam không cho tạo thì trả rỗng kèm lý do — nơi gọi dùng tài khoản đang có và ghi rõ.

Sổ nhớ: <ketqua>/xem_<mã dự án>.json  {"tên-miền:cổng": {"u", "p"}}. Mật khẩu chỉ gồm chữ, số, dấu gạch để gắn vào link không bị đổi ký tự.
Chưa thử trên cam Oryza thật: cam có nhận tài khoản trong link ảnh không, có cho tạo tài khoản mức User không.
"""
import os
import json
import secrets
import threading

import requests
from requests.auth import HTTPDigestAuth

TEN = "xemhoso"
_KHOA = threading.Lock()
_CHU = "abcdefghijkmnpqrstuvwxyz", "ABCDEFGHJKLMNPQRSTUVWXYZ", "23456789"      # bỏ ký tự dễ nhầm khi phải gõ tay (l/1, O/0)


def _f(thu_muc, ma):
    return os.path.join(thu_muc, f"xem_{ma}.json")


def _doc(thu_muc, ma):
    try:
        with open(_f(thu_muc, ma), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def cua_cam(thu_muc, ma, dom, http):
    """(user, mật khẩu) chỉ xem đã tạo cho cam ở dom:http; ('', '') nếu chưa có."""
    x = _doc(thu_muc, ma).get(f"{dom}:{http}") or {}
    return (x.get("u") or "", x.get("p") or "") if x.get("u") and x.get("p") else ("", "")


def mat_khau_moi():
    """Xem-XXXXXXXX: có hoa, thường, số, dấu gạch (đủ cho cam đòi mật khẩu mạnh), không có ký tự phải đổi khi nằm trong link."""
    while True:
        s = "".join(secrets.choice("".join(_CHU)) for _ in range(8))
        if all(any(c in nhom for c in s) for nhom in _CHU):
            return "Xem-" + s


def _lay_duoc_anh(anh_url, u, p):
    for au in (HTTPDigestAuth(u, p), (u, p)):
        try:
            r = requests.get(anh_url, auth=au, timeout=12)
        except requests.RequestException:
            continue
        if r.status_code == 200 and r.content[:2] == b"\xff\xd8":
            return True
    return False


def dam_bao(thu_muc, ma, ov, dom, http, anh_url):
    """Bảo đảm cam (đang nối bằng ov — tài khoản quản trị) có tài khoản chỉ xem dùng được cho QR. → (user, mật khẩu, ghi_chú).
    Đã có và còn trên cam → giữ nguyên (QR đã in vẫn dùng được). Bị xoá trên cam → tạo lại ĐÚNG mật khẩu cũ. App mất sổ → đặt mật khẩu mới.
    Không tạo được / tài khoản mới không lấy được ảnh → ('', '', lý do), không ghi sổ. Không bao giờ làm hỏng lượt kiểm đang chạy."""
    if not anh_url:
        return "", "", "cam chưa cho đường ảnh"
    khoa = f"{dom}:{http}"
    try:
        u, p = cua_cam(thu_muc, ma, dom, http)
        co = any(x["ten"] == TEN for x in ov.ds_user())
        if u and co:
            return u, p, ""
        p = p if u else mat_khau_moi()
        if co:
            ov.doi_mat_khau(TEN, p, "User")
        else:
            ov.tao_user(TEN, p, "User")
        if not any(x["ten"] == TEN and x["muc"] == "User" for x in ov.ds_user()):
            return "", "", "cam không tạo được tài khoản chỉ xem"
        if not _lay_duoc_anh(anh_url, TEN, p):
            return "", "", "cam không cho tài khoản chỉ xem lấy ảnh"
        with _KHOA:
            d = _doc(thu_muc, ma)
            d[khoa] = {"u": TEN, "p": p}
            tam = _f(thu_muc, ma) + ".tam"
            with open(tam, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False)
            os.replace(tam, _f(thu_muc, ma))
        return TEN, p, ""
    except Exception as e:
        return "", "", f"cam không cho tạo tài khoản chỉ xem ({str(e)[:60]})"
