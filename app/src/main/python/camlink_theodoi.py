"""THEO DÕI ỔN ĐỊNH MỘT CAM (Huan chốt 10/11/2026).

Bật cam nào thì theo dõi cam đó trong thời gian t. Mỗi 30 giây đo:
  1. mạng điện thoại (1.1.1.1 / 8.8.8.8)   → điện thoại mất mạng thì KHÔNG tính là cam rớt
  2. tên miền đang trỏ IP nào               → IP đổi = modem mất kết nối rồi lên lại
  3. port web của cam                       → lên / im lặng / bị từ chối, thời gian phản hồi
  4. port các cam khác cùng điểm            → cam khác vẫn lên = lỗi riêng cam này; cùng im = lỗi cả điểm
  5. luồng video RTSP (mỗi 2 phút khi port lên) → web lên mà video không ra = cam treo / băng thông yếu
Chỉ chụp ảnh ngay trước và ngay sau mỗi lần rớt (giữ 1 ảnh "mới nhất" ghi đè) → ~1 MB/ngày.
Hết t (hoặc bấm dừng) → báo cáo PDF 1–3 trang A4: tóm tắt, nguyên nhân gom nhóm, danh sách lần rớt, đề xuất khắc phục.
"""
import json, os, socket, threading, time

NHIP = 30            # giây giữa 2 lần đo
RTSP_MOI = 4         # đo RTSP mỗi 4 nhịp (~2 phút) khi port lên
ANH_MOI = 600        # làm mới ảnh "trước khi rớt" mỗi 10 phút
ROT_SAU = 2          # cần 2 lần đo liên tiếp không vào được mới tính là rớt (tránh rớt 1 gói lẻ)
GIU_NGAY = 7         # dữ liệu một lần theo dõi tự xoá sau 7 ngày (PDF đã xuất giữ ở ketqua/)

GOC = None
_KHOA = threading.Lock()


def khoi_tao(goc):
    global GOC
    GOC = goc
    os.makedirs(_thu_muc(), exist_ok=True)


def _thu_muc(*p):
    return os.path.join(GOC, "ketqua", "theodoi", *p)


def _doc(f, md=None):
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return md


def _ghi(f, d):
    tmp = f + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
    os.replace(tmp, f)


def _gio(t):
    return time.strftime("%H:%M:%S %d/%m", time.localtime(t))


def _thoi_luong(s):
    s = int(round(s))
    if s < 60:
        return f"{s} giây"
    if s < 3600:
        return f"{s // 60} phút {s % 60:02d} giây" if s % 60 else f"{s // 60} phút"
    return f"{s // 3600} giờ {s % 3600 // 60:02d} phút"


# ------------------------------------------------------------------ bật / dừng / danh sách
def bat(ma, p, so, phut, cd):
    """p = điểm trong kết quả kiểm tra từ xa (có domain, cam[]); so = số cam cần theo dõi; phut = thời gian t."""
    cams = p.get("cam", [])
    c = next((x for x in cams if int(x.get("so", 0)) == int(so)), None)
    if not c:
        raise RuntimeError(f"Không thấy cam {so} ở điểm {p.get('stt')}")
    for m in ds():
        if m["trang_thai"] == "dang" and m["domain"] == p["domain"] and int(m["http"]) == int(c["http"]):
            return m["id"]   # đang theo dõi rồi
    tid = time.strftime("%Y%m%d_%H%M%S") + f"_{p.get('stt')}_{so}"
    os.makedirs(_thu_muc(tid), exist_ok=True)
    rtsp_port, rtsp_path = 0, "/"
    live = c.get("live", "")
    if live.startswith("rtsp://"):
        import re
        mm = re.match(r"rtsp://(?:[^@/]*@)?[^/:]+(?::(\d+))?(/.*)?$", live)
        if mm:
            rtsp_port, rtsp_path = int(mm.group(1) or 554), mm.group(2) or "/"
    meta = {"id": tid, "ma": ma, "stt": str(p.get("stt")), "so": int(so), "ten_diem": p.get("ten", ""), "du_an": p.get("du_an", ""),
            "domain": p["domain"], "http": int(c["http"]), "rtsp": rtsp_port or int(c.get("rtsp") or 0), "rtsp_path": rtsp_path,
            "ban": [int(x["http"]) for x in cams if x is not c and x.get("http")],
            "user": c.get("user") or cd.get("cam_user", "admin"), "pass": c.get("pass") or cd.get("cam_pw", ""),
            "bat_dau": time.time(), "het": time.time() + float(phut) * 60, "phut": float(phut), "nhip": NHIP,
            "trang_thai": "dang", "lan_do": 0, "lan_toi": 0, "dang_rot": None, "lien_tiep_hong": 0, "ip_dau": "", "pdf": ""}
    _ghi(_thu_muc(tid, "meta.json"), meta)
    _ghi(_thu_muc(tid, "su_kien.json"), [])
    return tid


def ds():
    out = []
    try:
        for d in sorted(os.listdir(_thu_muc()), reverse=True):
            m = _doc(_thu_muc(d, "meta.json"))
            if m:
                out.append(m)
    except OSError:
        pass
    return out


def dung(tid):
    """Dừng sớm → ra báo cáo luôn."""
    with _KHOA:
        m = _doc(_thu_muc(tid, "meta.json"))
        if not m:
            raise RuntimeError("Không thấy lần theo dõi này")
        if m["trang_thai"] == "dang":
            m["het"] = time.time()
            _ket_thuc(m)
        return m.get("pdf", "")


def don_cu():
    """Xoá dữ liệu theo dõi đã xong quá 7 ngày (PDF ở ketqua/ giữ nguyên)."""
    import shutil
    for m in ds():
        if m["trang_thai"] == "xong" and time.time() - m.get("het", 0) > GIU_NGAY * 86400:
            shutil.rmtree(_thu_muc(m["id"]), ignore_errors=True)


# ------------------------------------------------------------------ đo
def _cham(host, port, cho=4):
    t0 = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(cho)
    try:
        s.connect((host, port))
        return "mo", int((time.time() - t0) * 1000)
    except ConnectionRefusedError:
        return "tu_choi", 0
    except OSError as e:
        import errno
        return ("tu_choi" if getattr(e, "errno", None) == errno.ECONNREFUSED else "im_lang"), 0
    finally:
        s.close()


def _mang_ok():
    if os.environ.get("CAMLINK_THU_NOI_BO"):
        return True
    for h, pt in (("1.1.1.1", 443), ("8.8.8.8", 443), ("1.0.0.1", 443)):
        if _cham(h, pt, 3)[0] == "mo":
            return True
    return False


def _ip(dom):
    try:
        return socket.getaddrinfo(dom, None, socket.AF_INET)[0][4][0]
    except OSError:
        return ""


def _chup(m, ten):
    """Chụp ảnh cam qua ONVIF; lỗi thì bỏ qua (ảnh chỉ là bằng chứng phụ)."""
    try:
        import camlink_dt as C
        ov = C.Onvif(m["domain"], m["http"], m["user"], m["pass"])
        um = ov.url_media()
        jpg = ov.anh_chup(um, ov.profile_dau(um))
        f = _thu_muc(m["id"], ten)
        with open(f, "wb") as fh:
            fh.write(jpg)
        return f
    except Exception:
        return ""


def do_mot_lan(m):
    """Một lần đo (song song). Trả về bản ghi mẫu."""
    kq = {"t": time.time()}
    th = []

    def chay(k, f, *a):
        def g():
            try:
                kq[k] = f(*a)
            except Exception:
                kq[k] = None
        x = threading.Thread(target=g, daemon=True)
        x.start()
        th.append(x)
    chay("net", _mang_ok)
    chay("ip", _ip, m["domain"])
    for x in th:
        x.join(12)
    th.clear()
    ip = kq.get("ip") or ""
    dich = ip or m["domain"]
    chay("cam", _cham, dich, m["http"])
    for b in m["ban"]:
        chay(f"b{b}", _cham, dich, b)
    for x in th:
        x.join(12)
    cam = kq.get("cam") or ("im_lang", 0)
    mau = {"t": round(kq["t"], 1), "net": bool(kq.get("net")), "ip": ip, "cam": cam[0], "ms": cam[1],
           "ban": {str(b): (kq.get(f"b{b}") or ("im_lang", 0))[0] for b in m["ban"]}}
    if cam[0] == "mo" and m.get("rtsp") and m["lan_do"] % RTSP_MOI == 0:
        try:
            from camlink_tuxa import rtsp_describe
            ma_rtsp = rtsp_describe(dich, m["rtsp"], m.get("rtsp_path", "/"), m["user"], m["pass"])[0]
            mau["rtsp"] = "ok" if ma_rtsp == 200 else f"loi_{ma_rtsp}"
        except Exception:
            mau["rtsp"] = "loi"
    return mau


# ------------------------------------------------------------------ vòng chạy (gọi mỗi 30 giây từ dịch vụ chạy nền)
def vong():
    """Đo mọi lần theo dõi đang chạy tới hạn. Trả danh sách tóm tắt + lần nào vừa xong (để báo thông báo)."""
    xong_moi = []
    with _KHOA:
        dang = [m for m in ds() if m["trang_thai"] == "dang"]
    for m in dang:
        if time.time() < m.get("toi", 0):
            continue
        try:
            mau = do_mot_lan(m)
        except Exception as e:
            mau = {"t": time.time(), "net": False, "ip": "", "cam": "loi_do", "ms": 0, "ban": {}, "loi": str(e)[:80]}
        with _KHOA:
            m2 = _doc(_thu_muc(m["id"], "meta.json")) or m
            if m2["trang_thai"] != "dang":
                continue
            _xu_ly_mau(m2, mau)
            m2["toi"] = mau["t"] + m2["nhip"]
            if time.time() >= m2["het"]:
                _ket_thuc(m2)
                xong_moi.append(m2["id"])
            else:
                _ghi(_thu_muc(m2["id"], "meta.json"), m2)
    try:
        don_cu()
    except Exception:
        pass
    return {"dang": [tom_tat(m) for m in ds() if m["trang_thai"] == "dang"], "xong_moi": xong_moi,
            "pdf_moi": [(_doc(_thu_muc(i, "meta.json")) or {}).get("pdf", "") for i in xong_moi]}


def tom_tat(m):
    sk = _doc(_thu_muc(m["id"], "su_kien.json"), [])
    return {"id": m["id"], "ten": f"Điểm {m['stt']} · cam {m['so']} ({m['domain']}:{m['http']})", "trang_thai": m["trang_thai"],
            "so_rot": len(sk) + (1 if m.get("dang_rot") else 0), "phut_rot": round(sum(x["dur"] for x in sk) / 60, 1),
            "con_phut": max(0, round((m["het"] - time.time()) / 60)), "dang_rot": bool(m.get("dang_rot")), "pdf": m.get("pdf", ""),
            "domain": m["domain"], "http": m["http"], "stt": m["stt"], "so": m["so"]}


def _xu_ly_mau(m, mau):
    """Ghi mẫu + máy trạng thái sự kiện rớt."""
    with open(_thu_muc(m["id"], "mau.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(mau, ensure_ascii=False) + "\n")
    m["lan_do"] += 1
    if not m["ip_dau"] and mau["ip"]:
        m["ip_dau"] = mau["ip"]
    if not mau["net"]:                      # điện thoại không có mạng → không kết luận gì
        m["khong_do"] = m.get("khong_do", 0) + 1
        return
    len_ = mau["cam"] == "mo"
    if len_:
        m["lan_toi"] = m.get("lan_toi", 0) + 1
        m["ms_tong"] = m.get("ms_tong", 0) + mau["ms"]
        m["ms_max"] = max(m.get("ms_max", 0), mau["ms"])
        if mau.get("rtsp") and mau["rtsp"] != "ok":
            m["video_loi"] = m.get("video_loi", 0) + 1
        if m.get("dang_rot"):
            _dong_su_kien(m, mau)
        m["lien_tiep_hong"] = 0
        if time.time() - m.get("anh_luc", 0) > ANH_MOI:   # ảnh "trước khi rớt" (ghi đè, chỉ 1 file)
            if _chup(m, "moi_nhat.jpg"):
                m["anh_luc"] = time.time()
        m["ip_cuoi_len"] = mau["ip"] or m.get("ip_cuoi_len", "")
        return
    m["lien_tiep_hong"] = m.get("lien_tiep_hong", 0) + 1
    if m.get("dang_rot"):
        r = m["dang_rot"]
        r["mau"] += 1
        r["ban_len"] += sum(1 for v in mau["ban"].values() if v == "mo")
        r["ban_do"] += len(mau["ban"])
        r["tu_choi"] += 1 if mau["cam"] == "tu_choi" else 0
        if mau["ip"] and mau["ip"] != r["ip_truoc"]:
            r["ip_moi"] = mau["ip"]
        if not mau["ip"]:
            r["dns_loi"] += 1
    elif m["lien_tiep_hong"] >= ROT_SAU:
        bd = mau["t"] - m["nhip"] * (ROT_SAU - 1)
        m["dang_rot"] = {"bd": bd, "ip_truoc": m.get("ip_cuoi_len") or m["ip_dau"], "ip_moi": "", "mau": ROT_SAU,
                         "ban_len": sum(1 for v in mau["ban"].values() if v == "mo"), "ban_do": len(mau["ban"]),
                         "tu_choi": 1 if mau["cam"] == "tu_choi" else 0, "dns_loi": 0 if mau["ip"] else 1, "n": 0}
        sk = _doc(_thu_muc(m["id"], "su_kien.json"), [])
        n = len(sk) + 1
        m["dang_rot"]["n"] = n
        anh = _thu_muc(m["id"], "moi_nhat.jpg")
        if os.path.exists(anh):
            import shutil
            shutil.copy(anh, _thu_muc(m["id"], f"truoc_{n}.jpg"))
            m["dang_rot"]["anh_truoc"] = _thu_muc(m["id"], f"truoc_{n}.jpg")


def _dong_su_kien(m, mau, ket_thuc_theo_doi=False):
    r = m.pop("dang_rot")
    m["dang_rot"] = None
    kt = mau["t"] if mau else min(time.time(), m["het"])
    su = {"n": r["n"], "bd": r["bd"], "kt": kt, "dur": max(0, kt - r["bd"]), "chua_len": ket_thuc_theo_doi,
          "ip_truoc": r["ip_truoc"], "ip_sau": (mau or {}).get("ip") or r.get("ip_moi", ""),
          "ban_co": bool(m["ban"]), "ti_le_ban_len": (r["ban_len"] / r["ban_do"]) if r["ban_do"] else None,
          "tu_choi": r["tu_choi"] / max(1, r["mau"]), "dns_loi": r["dns_loi"], "anh_truoc": r.get("anh_truoc", "")}
    if mau and not ket_thuc_theo_doi:
        su["anh_sau"] = _chup(m, f"sau_{r['n']}.jpg")
    su.update(phan_loai(su))
    sk = _doc(_thu_muc(m["id"], "su_kien.json"), [])
    sk.append(su)
    _ghi(_thu_muc(m["id"], "su_kien.json"), sk)


# ------------------------------------------------------------------ nguyên nhân
NGUYEN_NHAN = {
    "modem_doi_ip": ("Modem rớt mạng rồi tự kết nối lại (IP công cộng đổi)",
                     ["Gọi VNPT kiểm tra đường truyền điểm này (suy hao cáp quang, đầu nối, ONT) — dùng nút Phiếu báo mạng trong CamLink.",
                      "Kiểm tra nguồn điện cấp cho modem (ổ cắm lỏng, chung nguồn với thiết bị công suất lớn); lắp UPS mini cho modem.",
                      "Xin VNPT IP tĩnh để không phụ thuộc thời gian cập nhật tên miền DDNS."]),
    "ca_diem": ("Cả điểm mất mạng hoặc mất điện (mọi cam cùng im, IP không đổi)",
                ["Kiểm tra điện tại tủ/cột: aptomat, ổ cắm, nguồn chung cho modem và cam; lắp UPS mini cho modem + nguồn PoE.",
                 "Nếu điện ổn: gọi VNPT kiểm tra đường truyền (rớt mà IP không đổi thường do đường cáp chập chờn)."]),
    "cam_khoi_dong_lai": ("Riêng cam này khởi động lại (cam khác cùng điểm vẫn lên, mất 0,5–3 phút rồi tự lên)",
                          ["Thay adaptor/nguồn PoE của cam này (nguồn yếu hoặc chập chờn làm cam tự khởi động lại).",
                           "Kiểm tra đầu nối nguồn, dây nguồn ngoài trời bị ẩm/oxy hoá.",
                           "Nếu nguồn ổn: cập nhật firmware cam hoặc đổi cam (cam tự treo rồi tự khởi động)."]),
    "cam_mat_ket_noi": ("Riêng cam này mất kết nối (cam khác cùng điểm vẫn lên)",
                        ["Kiểm tra dây mạng từ cam về modem/switch: bấm lại đầu RJ45, thay đoạn dây ngoài trời, đổi cổng modem/switch.",
                         "Kiểm tra nguồn PoE/adaptor của cam (mất nguồn lâu cũng cho dấu hiệu này)."]),
    "mot_cam_khong_phan_biet": ("Cam không vào được (điểm chỉ có 1 cam nên không phân biệt được lỗi cam hay lỗi cả điểm)",
                                ["Kiểm tra nguồn và dây mạng của cam, đồng thời nguồn modem tại điểm.",
                                 "Theo dõi thêm lần sau khi điểm có thêm thiết bị để so sánh."]),
    "mat_mo_port": ("Modem từ chối port của cam (luật mở port mất hoặc cam đổi IP trong mạng)",
                    ["Đặt IP tĩnh cho cam (vd .200) và kiểm tra lại luật mở port trên modem — dùng CÀI ĐIỂM NÀY khi tới điểm.",
                     "Tắt UPnP tự động trên modem nếu luật port hay bị xoá sau khi modem khởi động lại."]),
}


def phan_loai(su):
    if su.get("tu_choi", 0) >= 0.5:
        k = "mat_mo_port"
    elif su["ip_truoc"] and su.get("ip_sau") and su["ip_sau"] != su["ip_truoc"]:
        k = "modem_doi_ip"
    elif not su["ban_co"]:
        k = "mot_cam_khong_phan_biet"
    elif (su["ti_le_ban_len"] or 0) >= 0.5:
        k = "cam_khoi_dong_lai" if 30 <= su["dur"] <= 200 and not su.get("chua_len") else "cam_mat_ket_noi"
    else:
        k = "ca_diem"
    return {"loai": k, "nguyen_nhan": NGUYEN_NHAN[k][0]}


# ------------------------------------------------------------------ kết thúc + báo cáo
def _ket_thuc(m):
    m["het"] = min(m["het"], time.time())
    if m.get("dang_rot"):
        _dong_su_kien(m, None, ket_thuc_theo_doi=True)
    m["trang_thai"] = "xong"
    _ghi(_thu_muc(m["id"], "meta.json"), m)
    try:
        m["pdf"] = bao_cao_pdf(m["id"])
    except Exception as e:
        m["loi_pdf"] = str(e)[:200]
    _ghi(_thu_muc(m["id"], "meta.json"), m)


def phan_tich(tid):
    m = _doc(_thu_muc(tid, "meta.json"))
    sk = _doc(_thu_muc(tid, "su_kien.json"), [])
    mau = []
    try:
        with open(_thu_muc(tid, "mau.jsonl"), encoding="utf-8") as fh:
            mau = [json.loads(x) for x in fh if x.strip()]
    except OSError:
        pass
    tong_tg = max(1, m["het"] - m["bat_dau"])
    khong_do = sum(1 for x in mau if not x["net"]) * m["nhip"]
    rot = sum(x["dur"] for x in sk)
    tg_do = max(1, tong_tg - khong_do)
    nhom = {}
    for x in sk:
        g = nhom.setdefault(x["loai"], {"loai": x["loai"], "ten": NGUYEN_NHAN[x["loai"]][0], "so": 0, "giay": 0})
        g["so"] += 1
        g["giay"] += x["dur"]
    nhom = sorted(nhom.values(), key=lambda g: (-g["so"], -g["giay"]))
    gio = {}
    for x in sk:
        h = time.localtime(x["bd"]).tm_hour
        gio[h] = gio.get(h, 0) + 1
    ms_tb = round(m.get("ms_tong", 0) / max(1, m.get("lan_toi", 0)))
    if not sk:
        ket = "Cam ổn định trong suốt thời gian theo dõi — không có lần rớt nào."
    else:
        ket = f"Rớt {len(sk)} lần, nhiều lần nhất do: {nhom[0]['ten'].split('(')[0].strip().lower()} ({nhom[0]['so']} lần)"
        lau = max(nhom, key=lambda g: g["giay"])
        ket += (f"; mất nhiều thời gian nhất do: {lau['ten'].split('(')[0].strip().lower()} ({_thoi_luong(lau['giay'])})." if lau is not nhom[0] else ".")
    return {"m": m, "su_kien": sk, "nhom": nhom, "tong_tg": tong_tg, "khong_do": khong_do, "rot": rot,
            "len_pt": round(100 * max(0, tg_do - rot) / tg_do, 2), "dai_nhat": max([x["dur"] for x in sk], default=0),
            "gio": gio, "ms_tb": ms_tb, "ms_max": m.get("ms_max", 0), "video_loi": m.get("video_loi", 0),
            "so_mau": len(mau), "ket_luan": ket, "mau": mau}


def _font():
    """Font tiếng Việt CÓ SẴN trong máy (Android: Roboto/Noto) — không nhúng font vào app."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    cap = [("/system/fonts/Roboto-Regular.ttf", "/system/fonts/Roboto-Bold.ttf"),
           ("/system/fonts/NotoSans-Regular.ttf", "/system/fonts/NotoSans-Bold.ttf"),
           ("/system/fonts/DroidSans.ttf", "/system/fonts/DroidSans-Bold.ttf"),
           ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
    for r, b in cap:
        if os.path.exists(r):
            try:
                pdfmetrics.registerFont(TTFont("VN", r))
                pdfmetrics.registerFont(TTFont("VNB", b if os.path.exists(b) else r))
                return "VN", "VNB"
            except Exception:
                continue
    # Android 12+: Roboto là font biến thiên — thử font bất kỳ trong /system/fonts có dấu tiếng Việt
    for f in sorted(os.listdir("/system/fonts")) if os.path.isdir("/system/fonts") else []:
        if f.endswith(".ttf") and ("Noto" in f or "Roboto" in f) and "Serif" not in f:
            try:
                pdfmetrics.registerFont(TTFont("VN", "/system/fonts/" + f))
                pdfmetrics.registerFont(TTFont("VNB", "/system/fonts/" + f))
                return "VN", "VNB"
            except Exception:
                continue
    raise RuntimeError("Không tìm thấy font tiếng Việt trong máy")


def bao_cao_pdf(tid):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.graphics.shapes import Drawing, Rect, String, Line

    a = phan_tich(tid)
    m = a["m"]
    F, FB = _font()
    s = lambda **k: ParagraphStyle("x", fontName=k.pop("f", F), fontSize=k.pop("c", 9.5), leading=k.pop("l", 12.5), **k)
    H1, H2, P, NHO = s(f=FB, c=15, l=19, spaceAfter=2), s(f=FB, c=11.5, l=15, spaceBefore=7, spaceAfter=3, textColor=colors.HexColor("#0F5D8C")), s(), s(c=8, l=10, textColor=colors.HexColor("#5B6776"))
    XANH, DO, VANG, XAM = colors.HexColor("#1D7A46"), colors.HexColor("#C0392B"), colors.HexColor("#C88A00"), colors.HexColor("#D7DEE5")
    ten_file = f"TheoDoi_diem{m['stt']}_cam{m['so']}_{time.strftime('%Y%m%d_%H%M', time.localtime(m['bat_dau']))}.pdf"
    f = os.path.join(GOC, "ketqua", ten_file)
    doc = SimpleDocTemplate(f, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f"Theo dõi ổn định camera — điểm {m['stt']} cam {m['so']}", author="CamLink")
    W = A4[0] - 28 * mm
    el = []
    el.append(Paragraph("BÁO CÁO THEO DÕI ỔN ĐỊNH CAMERA", H1))
    el.append(Paragraph(f"{m.get('du_an') or ''} · Điểm {m['stt']}. {m['ten_diem']} · Cam {m['so']} · "
                        f"<b>{m['domain']}:{m['http']}</b>", P))
    el.append(Paragraph(f"Theo dõi từ {_gio(m['bat_dau'])} đến {_gio(m['het'])} ({_thoi_luong(a['tong_tg'])}), đo {a['so_mau']} lần, "
                        f"mỗi {m['nhip']} giây · CamLink", NHO))
    el.append(Spacer(1, 5))
    # ---- 1. tóm tắt
    mau_kl = XANH if not a["su_kien"] else (DO if a["len_pt"] < 97 else VANG)
    tt = [["Thời gian cam lên", f"{a['len_pt']} %", "Số lần rớt", str(len(a["su_kien"]))],
          ["Tổng thời gian rớt", _thoi_luong(a["rot"]), "Lần rớt dài nhất", _thoi_luong(a["dai_nhat"]) if a["su_kien"] else "—"],
          ["Phản hồi trung bình", f"{a['ms_tb']} ms (chậm nhất {a['ms_max']} ms)", "Video lỗi khi web vẫn lên", f"{a['video_loi']} lần"]]
    if a["khong_do"]:
        tt.append(["Điện thoại mất mạng (không tính)", _thoi_luong(a["khong_do"]), "", ""])
    tb = Table([[Paragraph(str(x), P if i % 2 == 0 else s(f=FB)) for i, x in enumerate(r)] for r in tt], colWidths=[W * .27, W * .23, W * .27, W * .23])
    tb.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .4, XAM), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F5F8")),
                            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F2F5F8")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    el.append(tb)
    el.append(Spacer(1, 4))
    el.append(Paragraph(f"<b>Kết luận:</b> {a['ket_luan']}", s(f=F, c=10.5, l=14, textColor=mau_kl)))
    # ---- dải thời gian lên/rớt
    d = Drawing(W, 34)
    d.add(Rect(0, 12, W, 12, fillColor=colors.HexColor("#CFE8D8"), strokeColor=None))
    t0, t1 = m["bat_dau"], max(m["het"], m["bat_dau"] + 1)
    for x in a["mau"]:
        if not x["net"]:
            d.add(Rect(W * (x["t"] - t0) / (t1 - t0), 12, max(1, W * m["nhip"] / (t1 - t0)), 12, fillColor=XAM, strokeColor=None))
    for x in a["su_kien"]:
        d.add(Rect(W * (x["bd"] - t0) / (t1 - t0), 12, max(1.5, W * x["dur"] / (t1 - t0)), 12, fillColor=DO, strokeColor=None))
    for i in range(5):
        tx = t0 + (t1 - t0) * i / 4
        d.add(String(W * i / 4 - (0 if i == 0 else (24 if i == 4 else 12)), 2, time.strftime("%H:%M", time.localtime(tx)), fontName=F, fontSize=7))
    d.add(String(0, 27, "Dải thời gian: xanh = cam lên · đỏ = rớt · xám = điện thoại mất mạng", fontName=F, fontSize=7, fillColor=colors.HexColor("#5B6776")))
    el.append(d)
    # ---- 2. nguyên nhân
    el.append(Paragraph("1. Nguyên nhân các lần rớt", H2))
    if not a["nhom"]:
        el.append(Paragraph("Không có lần rớt nào trong thời gian theo dõi.", P))
    for g in a["nhom"]:
        el.append(Paragraph(f"• <b>{g['ten']}</b>: {g['so']} lần, tổng {_thoi_luong(g['giay'])} "
                            f"({round(100 * g['giay'] / max(1, a['rot']))}% thời gian rớt)", P))
    if a["gio"] and len(a["su_kien"]) >= 3:
        h, n = max(a["gio"].items(), key=lambda x: x[1])
        if n >= 2:
            el.append(Paragraph(f"• Rớt dồn nhiều nhất khung giờ {h:02d}:00–{(h + 1) % 24:02d}:00 ({n} lần)"
                                + (" — giờ cao điểm điện tối, nghi nguồn điện yếu." if 17 <= h <= 21 else "."), P))
    # ---- 3. danh sách
    sk = a["su_kien"]
    if sk:
        el.append(Paragraph("2. Danh sách các lần rớt", H2))
        hien = sorted(sk, key=lambda x: -x["dur"])[:15] if len(sk) > 15 else sk
        hien = sorted(hien, key=lambda x: x["bd"])
        rows = [["#", "Bắt đầu", "Lên lại", "Kéo dài", "Nguyên nhân · dấu hiệu"]]
        for x in hien:
            dh = []
            if x.get("ti_le_ban_len") is not None:
                dh.append(f"cam khác cùng điểm lên {round(100 * x['ti_le_ban_len'])}%")
            if x.get("ip_sau") and x["ip_sau"] != x["ip_truoc"]:
                dh.append(f"IP {x['ip_truoc']} → {x['ip_sau']}")
            if x.get("dns_loi"):
                dh.append("tên miền không phân giải")
            rows.append([str(x["n"]), _gio(x["bd"])[:8], (Paragraph("chưa lên<br/>(hết giờ theo dõi)", s(c=8, l=10)) if x.get("chua_len") else _gio(x["kt"])[:8]),
                         _thoi_luong(x["dur"]), Paragraph(f"{x['nguyen_nhan'].split('(')[0].strip()}" + (f" · <font color='#5B6776'>{'; '.join(dh)}</font>" if dh else ""), s(c=8.5, l=11))])
        t = Table(rows, colWidths=[W * .05, W * .13, W * .17, W * .14, W * .51], repeatRows=1)
        t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), F, 8.5), ("FONT", (0, 0), (-1, 0), FB, 8.5), ("GRID", (0, 0), (-1, -1), .3, XAM),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EEF5")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        el.append(t)
        if len(sk) > len(hien):
            con = [x for x in sk if x not in hien]
            el.append(Paragraph(f"Còn {len(con)} lần rớt ngắn khác, tổng {_thoi_luong(sum(x['dur'] for x in con))} (không liệt kê).", NHO))
    # ---- 4. đề xuất
    el.append(Paragraph("3. Đề xuất khắc phục", H2))
    if not a["nhom"]:
        el.append(Paragraph("Không cần xử lý. Nếu trước đây cam từng chập chờn, nên theo dõi thêm một lần vào khung giờ hay rớt.", P))
    da = set()
    for i, g in enumerate(a["nhom"], 1):
        el.append(Paragraph(f"<b>{i}. Cho nhóm \"{g['ten'].split('(')[0].strip()}\" ({g['so']} lần):</b>", P))
        for v in NGUYEN_NHAN[g["loai"]][1]:
            if v in da:
                continue
            da.add(v)
            el.append(Paragraph(f"   – {v}", P))
    if a["video_loi"]:
        el.append(Paragraph(f"<b>Thêm:</b> {a['video_loi']} lần web cam vẫn lên nhưng luồng video không ra → giảm độ phân giải/bitrate luồng phụ, "
                            "kiểm tra băng thông upload của đường truyền; nếu lặp lại thì khởi động lại cam.", P))
    if a["khong_do"] > 0.2 * a["tong_tg"]:
        el.append(Paragraph("<b>Lưu ý:</b> điện thoại theo dõi mất mạng hơn 20% thời gian — nên theo dõi lại bằng máy cắm sạc, sóng ổn định.", P))
    # ---- 5. ảnh tiêu biểu
    cap = [(x.get("anh_truoc"), x.get("anh_sau"), x) for x in sorted(sk, key=lambda x: -x["dur"]) if x.get("anh_truoc") or x.get("anh_sau")][:2]
    if cap:
        el.append(Paragraph("4. Ảnh trước / sau lần rớt tiêu biểu", H2))
        for tr, sa, x in cap:
            o = []
            for f_anh, nhan in ((tr, "Trước khi rớt"), (sa, "Sau khi lên lại")):
                if f_anh and os.path.exists(f_anh):
                    o.append([Image(f_anh, width=W * .40, height=W * .40 * 9 / 16), Paragraph(nhan, NHO)])
                else:
                    o.append([Paragraph("(không có ảnh)", NHO), Paragraph(nhan, NHO)])
            tbl = Table([[o[0][0], o[1][0]], [o[0][1], o[1][1]]], colWidths=[W * .5, W * .5])
            el.append(KeepTogether([Paragraph(f"Lần {x['n']} lúc {_gio(x['bd'])}, kéo dài {_thoi_luong(x['dur'])}", P), tbl]))
    el.append(Spacer(1, 6))
    el.append(Paragraph("Cách đọc: \"rớt\" = 2 lần đo liên tiếp (≥ 1 phút) không vào được port cam trong khi điện thoại vẫn có mạng. "
                        "Nguyên nhân suy ra từ cam khác cùng điểm, IP công cộng của modem và thời gian rớt; \"khởi động lại\" là suy luận "
                        "từ rớt ngắn 0,5–3 phút khi cam khác vẫn lên.", NHO))
    doc.build(el)
    return f
