"""GỠ tài khoản chỉ xem khỏi cam (anh Huan chốt 28/11/2026 07:42).

Bản 2.14.2/2.14.3 từng cho app TỰ TẠO trên cam một tài khoản 'xemhoso' (mức User) cho QR hồ sơ. Anh Huan (thầu phụ) bỏ hướng đó
vì tự thêm tài khoản trên cam của chủ đầu tư khi chưa được phép chẳng khác backdoor. Từ 2.14.4 app không tạo nữa; file này để DỌN
những cam đã lỡ bị tạo: dùng tài khoản admin vào cam, xoá 'xemhoso' nếu có, rồi ĐỌC LẠI danh sách xác nhận đã sạch.
"""
TEN = "xemhoso"


def con_tren_cam(ov):
    """True nếu cam (đang nối bằng ov) còn tài khoản xemhoso."""
    try:
        return any(x.get("ten") == TEN for x in ov.ds_user())
    except Exception:
        return False


def go(ov, dom="", http=0):
    """Xoá tài khoản chỉ xem khỏi MỘT cam (ov nối bằng admin), rồi đọc lại xác nhận. → (xong, ghi).
    (True, "")             : đã xoá và cam không còn.
    (True, "không có")     : cam vốn không có tài khoản này.
    (False, lý do)         : xoá hụt (cam vẫn còn / lỗi)."""
    try:
        if not con_tren_cam(ov):
            return True, "không có"
        ov.xoa_user(TEN)
        if con_tren_cam(ov):
            return False, "đã gửi lệnh xoá nhưng cam vẫn còn tài khoản"
        return True, ""
    except Exception as e:
        return False, f"lỗi khi xoá ({str(e)[:60]})"
