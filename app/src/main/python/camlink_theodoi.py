"""THEO DÕI ỔN ĐỊNH CAMERA THEO ĐIỂM (Huan chốt 10/11/2026; 1.9.6: theo dõi cả điểm, hỏi web thay gõ cửa TCP, báo ngay khi rớt).

Bật theo dõi một điểm = theo dõi mọi cam của điểm trong thời gian t, đo CHUNG một lượt (không hỏi cam 2 lần). Mỗi 30 giây đo:
  1. mạng điện thoại (1.1.1.1 / 8.8.8.8)   → điện thoại mất mạng thì KHÔNG tính là cam rớt
  2. tên miền đang trỏ IP nào               → IP đổi = modem mất kết nối rồi lên lại
  3. port web của cam: HỎI 1 trang web (không đăng nhập, ~0,5 KB) → lên / TREO (nhận kết nối nhưng không trả lời) / im lặng / từ chối
  4. port các cam khác cùng điểm            → cam khác vẫn lên = lỗi riêng cam này; cùng im = lỗi cả điểm
  5. luồng video RTSP (mỗi 2 phút khi port lên) → web lên mà video không ra = cam treo / băng thông yếu
Chỉ chụp ảnh ngay trước và ngay sau mỗi lần rớt (giữ 1 ảnh "mới nhất" ghi đè) → ~1 MB/ngày.
Hết t (hoặc bấm dừng) → báo cáo PDF 1–3 trang A4: tóm tắt, nguyên nhân gom nhóm, danh sách lần rớt, đề xuất khắc phục.
"""
import json, os, socket, threading, time

NHIP = 30            # giây giữa 2 lần đo
RTSP_MOI = 4         # hỏi luồng video mỗi 4 nhịp = 2 phút (Huan 10/11: nhẹ cho cam); đang hỏng video thì hỏi mỗi nhịp tới khi lên
ANH_MOI = 3600       # làm mới ảnh "trước khi rớt" mỗi 1 giờ (chụp bắt cam nén JPEG — hạn chế)
BAO_SAU = 300        # rớt liên tục 5 phút → báo ngay lên điện thoại + đẩy cảnh báo lên ghim LiteMark
KHI_BAO = None       # lõi gắn hàm đẩy LiteMark vào đây: KHI_BAO(m, "rot"/"len", thông tin)
_MANG = ""           # loại mạng điện thoại lúc đo (wifi / di_dong / khong) — dịch vụ chạy nền báo vào
TRA_LOI = 10         # chờ cam trả lời trang web tối đa 10 giây mới tính là TREO (cam Oryza đo thật có lúc 3 giây)
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
def bat_diem(ma, p, phut, cd):
    """Theo dõi CẢ ĐIỂM: mọi cam của điểm, chung một lượt đo, chung một báo cáo. Trả mã nhóm."""
    for m in ds():
        if m["trang_thai"] == "dang" and m["domain"] == p["domain"]:
            return m.get("nhom") or m["id"]      # điểm này đang được theo dõi rồi
    nhom = "N" + time.strftime("%Y%m%d_%H%M%S") + f"_{p.get('stt')}"
    so_cam = 0
    for c in p.get("cam", []):
        if c.get("http"):
            bat(ma, p, c.get("so"), phut, cd, nhom)
            so_cam += 1
    if not so_cam:
        raise RuntimeError(f"Điểm {p.get('stt')} không có cam nào để theo dõi")
    return nhom


def bat(ma, p, so, phut, cd, nhom=""):
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
            "trang_thai": "dang", "lan_do": 0, "lan_toi": 0, "dang_rot": None, "lien_tiep_hong": 0, "ip_dau": "", "pdf": "", "nhom": nhom}
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


def _cung_nhom(nhom):
    return sorted([m for m in ds() if m.get("nhom") == nhom], key=lambda m: m["so"])


def dung(tid):
    """Dừng sớm → ra báo cáo luôn. tid là mã nhóm (cả điểm) hoặc mã một cam (dừng luôn cả điểm của nó)."""
    with _KHOA:
        m = None if tid.startswith("N") else _doc(_thu_muc(tid, "meta.json"))
        nhom = tid if tid.startswith("N") else (m or {}).get("nhom", "")
        ms = _cung_nhom(nhom) if nhom else ([m] if m else [])
        if not ms:
            raise RuntimeError("Không thấy lần theo dõi này")
        for x in ms:
            if x["trang_thai"] == "dang":
                x["het"] = time.time()
                _ket_thuc(x)
        return _pdf_nhom(nhom) if nhom else (_doc(_thu_muc(ms[0]["id"], "meta.json")) or {}).get("pdf", "")


def _pdf_nhom(nhom):
    """Cả nhóm đã xong → 1 báo cáo chung cho cả điểm (ghi đường dẫn vào mọi cam của nhóm)."""
    ms = _cung_nhom(nhom)
    if not ms or any(x["trang_thai"] != "xong" for x in ms):
        return ""
    if ms[0].get("pdf"):
        return ms[0]["pdf"]
    try:
        f = bao_cao_pdf(ms[0]["id"])
    except Exception as e:
        f = ""
        for x in ms:
            x["loi_pdf"] = str(e)[:200]
    for x in ms:
        x["pdf"] = f
        _ghi(_thu_muc(x["id"], "meta.json"), x)
    return f


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


def _hoi_web(host, port, cho=4):
    """Hỏi 1 trang web của cam (không đăng nhập, đọc 16 byte rồi đóng). Phân biệt được CAM TREO:
    port vẫn nhận kết nối (modem/cam còn sống phần mạng) nhưng phần mềm cam không trả lời."""
    import errno
    t0 = time.time()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(cho)
    try:
        try:
            s.connect((host, port))
        except ConnectionRefusedError:
            return "tu_choi", 0
        except OSError as e:
            return ("tu_choi" if getattr(e, "errno", None) == errno.ECONNREFUSED else "im_lang"), 0
        try:
            s.settimeout(TRA_LOI)    # đo thật cam Oryza Phú Lý 10/11: trang web trả lời 0,4–3 giây, có lần > 10 giây
            s.sendall(f"GET / HTTP/1.0\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n".encode())
            b = s.recv(16)
        except OSError:
            b = b""
        return ("mo" if b else "treo"), int((time.time() - t0) * 1000)
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
    return do_nhom([m])[m["id"]]


def do_nhom(ms):
    """MỘT lượt đo chung cho mọi cam đang theo dõi của một điểm: mỗi port chỉ hỏi 1 lần. Trả {id: mẫu}."""
    m0 = ms[0]
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
    chay("ip", _ip, m0["domain"])
    for x in th:
        x.join(12)
    th.clear()
    ip = kq.get("ip") or ""
    dich = ip or m0["domain"]
    cong = sorted({int(m["http"]) for m in ms} | {int(b) for m in ms for b in m["ban"]})
    for pt in cong:
        chay(f"p{pt}", _hoi_web, dich, pt)
    for x in th:
        x.join(16)
    st = {pt: (kq.get(f"p{pt}") or ("im_lang", 0)) for pt in cong}
    ra = {}
    for m in ms:
        cam = st[int(m["http"])]
        mau = {"t": round(kq["t"], 1), "net": bool(kq.get("net")), "ip": ip, "cam": cam[0], "ms": cam[1],
               "ban": {str(b): st[int(b)][0] for b in m["ban"]}}
        if _MANG:
            mau["mang"] = _MANG
        xem = dang_xem(m, ip)
        if cam[0] == "mo" and xem is not None:
            # Huan đang mở xem đúng cam này → lấy chính màn xem làm số đo, KHÔNG hỏi cam thêm
            mau["rtsp"] = "loi_xem" if xem == "ngat" else "ok_xem"
        elif cam[0] == "mo" and m.get("rtsp") and (m["lan_do"] % RTSP_MOI == 0 or str(m.get("rtsp_cuoi", "")).startswith("loi")):
            try:
                from camlink_tuxa import rtsp_describe
                ma_rtsp = rtsp_describe(dich, m["rtsp"], m.get("rtsp_path", "/"), m["user"], m["pass"])[0]
                # 401/403/404 = sai user/pass hoặc sai đường dẫn → không phải cam chập chờn, không tính rớt (ghi riêng)
                mau["rtsp"] = "ok" if ma_rtsp == 200 else ("xac_thuc" if ma_rtsp in (401, 403, 404) else f"loi_{ma_rtsp}")
            except Exception:
                mau["rtsp"] = "loi"
        ra[m["id"]] = mau
    return ra


# ------------------------------------------------------------------ vòng chạy (gọi mỗi 30 giây từ dịch vụ chạy nền)
def _ten(m):
    return f"Điểm {m['stt']} · cam {m['so']}"


def _su_tam(m, r, t):
    """Lần rớt đang diễn ra → đoán nguyên nhân tạm (để báo ngay)."""
    su = {"ip_truoc": r["ip_truoc"], "ip_sau": r.get("ip_moi", ""), "ban_co": bool(m["ban"]), "dur": t - r["bd"], "chua_len": True,
          "ti_le_ban_len": (r["ban_len"] / r["ban_do"]) if r["ban_do"] else None, "tu_choi": r["tu_choi"] / max(1, r["mau"]),
          "video": r.get("video", 0) / max(1, r["mau"]), "treo": r.get("treo", 0) / max(1, r["mau"])}
    return phan_loai(su)


def vong(loai_mang=""):
    """Đo mọi lần theo dõi tới hạn — cam cùng điểm đo CHUNG một lượt. Trả tóm tắt + báo cáo mới + tin báo ngay."""
    global _MANG
    _MANG = loai_mang or ""
    xong_moi, bao, dong_moi = [], [], []
    with _KHOA:
        dang = [m for m in ds() if m["trang_thai"] == "dang" and time.time() >= m.get("toi", 0)]
    nhom_do = {}
    for m in dang:
        nhom_do.setdefault(m.get("nhom") or m["id"], []).append(m)
    for _, ms in nhom_do.items():
        try:
            maus = do_nhom(ms)
        except Exception as e:
            maus = {m["id"]: {"t": time.time(), "net": False, "ip": "", "cam": "loi_do", "ms": 0, "ban": {}, "loi": str(e)[:80]} for m in ms}
        for m in ms:
            mau = maus[m["id"]]
            with _KHOA:
                m2 = _doc(_thu_muc(m["id"], "meta.json")) or m
                if m2["trang_thai"] != "dang":
                    continue
                r0 = m2.get("dang_rot") or {}
                _xu_ly_mau(m2, mau)
                r = m2.get("dang_rot")
                if r and not r.get("da_bao") and mau["t"] - r["bd"] >= BAO_SAU:
                    r["da_bao"] = True
                    tam = _su_tam(m2, r, mau["t"])
                    import camlink_chandoan as D
                    pd = D.tinh(D.tu_su_kien({**tam, "ip_truoc": r["ip_truoc"], "ip_sau": r.get("ip_moi", ""), "ban_co": bool(m2["ban"]),
                                             "ti_le_ban_len": (r["ban_len"] / r["ban_do"]) if r["ban_do"] else None,
                                             "treo": r.get("treo", 0) / max(1, r["mau"]), "tu_choi": r["tu_choi"] / max(1, r["mau"])}),
                                m2["ma"], "dang_mat")
                    bao.append({"kieu": "rot", "id": m2["id"], "ten": _ten(m2), "bd": r["bd"], "ma": m2["ma"], "stt": m2["stt"], "so": m2["so"],
                                "http": m2["http"], **tam, "nguyen_nhan": "Khả năng: " + D.dong_mot_dong(pd)})
                elif r0 and not r:
                    dong_moi.append((m2["id"], bool(r0.get("da_bao"))))
                m2["toi"] = mau["t"] + m2["nhip"]
                if time.time() >= m2["het"]:
                    _ket_thuc(m2)
                    xong_moi.append(m2)
                else:
                    _ghi(_thu_muc(m2["id"], "meta.json"), m2)
    # lần rớt vừa kết thúc → đọc nhật ký các cam của điểm: cam có khởi động lại không (tách MẤT ĐIỆN với MODEM/VNPT)
    for tid, da_bao in dong_moi:
        try:
            x = doc_khoi_dong_su_kien(tid)
        except Exception:
            x = None
        if da_bao:
            m2 = _doc(_thu_muc(tid, "meta.json")) or {}
            x = x or (_doc(_thu_muc(tid, "su_kien.json"), []) or [{}])[-1]
            import camlink_chandoan as D
            pd = D.tinh(D.tu_su_kien(x), m2.get("ma", ""), "sau_khi_len")
            bao.append({"kieu": "len", "id": tid, "ten": _ten(m2), "bd": x.get("bd", 0), "dur": x.get("dur", 0), "ma": m2.get("ma", ""),
                        "stt": m2.get("stt"), "so": m2.get("so"), "http": m2.get("http"), "loai": x.get("loai", ""),
                        "nguyen_nhan": "Khả năng: " + D.dong_mot_dong(pd)})
    # cả điểm cùng rớt / cùng lên → gộp thành 1 tin cho điểm (không báo từng cam trùng nội dung)
    gop = {}
    for b in bao:
        mb = _doc(_thu_muc(b["id"], "meta.json")) or {}
        k = (mb.get("nhom") or b["id"], b["kieu"], b.get("nguyen_nhan", ""))
        if k in gop:
            gop[k]["ten"] += f", {b.get('so')}"
            gop[k].setdefault("ds", []).append(b)
        else:
            gop[k] = dict(b, ds=[b])
    bao_tin = list(gop.values())
    for b in bao:
        if KHI_BAO:
            try:
                KHI_BAO(b)
            except Exception:
                pass
    pdf_moi = []
    with _KHOA:
        for m in xong_moi:
            f = _pdf_nhom(m["nhom"]) if m.get("nhom") else (_doc(_thu_muc(m["id"], "meta.json")) or {}).get("pdf", "")
            if f and f not in pdf_moi:
                pdf_moi.append(f)
    try:
        don_cu()
    except Exception:
        pass
    return {"dang": [x for x in ds_hien() if x["trang_thai"] == "dang"], "xong_moi": [m["id"] for m in xong_moi], "pdf_moi": pdf_moi,
            "bao": [{k: v for k, v in b.items() if k != "ds"} for b in bao_tin]}


_NK_CACHE = {}


def _nhat_ky_khoi_dong(m, dich):
    """Các lần khởi động của cam (đọc nhật ký ONVIF). None = cam không cho đọc. Lưu đệm 2 phút để các cam cùng điểm không hỏi lại."""
    k = (m["domain"], m["http"])
    if k in _NK_CACHE and time.time() - _NK_CACHE[k][0] < 120:
        return _NK_CACHE[k][1]
    import camlink_chandoan as D
    import camlink_dt as C
    try:
        ov = C.Onvif(dich, m["http"], m["user"], m["pass"])
        ov.co()
        ds_kd = D.lan_khoi_dong(ov.nhat_ky())
    except Exception:
        ds_kd = None
    _NK_CACHE[k] = (time.time(), ds_kd)
    return ds_kd


def doc_khoi_dong_su_kien(tid):
    """Lần rớt cuối của cam tid vừa kết thúc → đọc nhật ký mọi cam cùng điểm → ghi 'cam_khoi_dong' vào lần rớt đó."""
    import camlink_chandoan as D
    m = _doc(_thu_muc(tid, "meta.json"))
    sk = _doc(_thu_muc(tid, "su_kien.json"), [])
    if not m or not sk or sk[-1].get("chua_len"):
        return None
    x = sk[-1]
    dich = _ip(m["domain"]) or m["domain"]
    cung = _cung_nhom(m["nhom"]) if m.get("nhom") else [m]
    cua = _nhat_ky_khoi_dong(m, dich)
    khac = [_nhat_ky_khoi_dong(y, dich) for y in cung if y["id"] != tid]
    kq, luc = D.xep_khoi_dong(x["bd"], x.get("kt", x["bd"] + x["dur"]), cua, khac)
    with _KHOA:
        sk = _doc(_thu_muc(tid, "su_kien.json"), [])
        sk[-1]["cam_khoi_dong"], sk[-1]["cam_khoi_dong_luc"] = kq, luc
        _ghi(_thu_muc(tid, "su_kien.json"), sk)
    return sk[-1]


def lam_lai_pdf(tid):
    """Làm lại báo cáo từ dữ liệu đo đã lưu (khi cách phân tích được sửa) — không đo lại."""
    with _KHOA:
        m = None if tid.startswith("N") else _doc(_thu_muc(tid, "meta.json"))
        nhom = tid if tid.startswith("N") else (m or {}).get("nhom", "")
        ms = _cung_nhom(nhom) if nhom else [m]
        f = bao_cao_pdf(ms[0]["id"])
        for x in ms:
            x["pdf"] = f
            _ghi(_thu_muc(x["id"], "meta.json"), x)
        return f


def ds_hien():
    """Danh sách cho màn hình: mỗi ĐIỂM đang/đã theo dõi một dòng (cam lẻ đời cũ vẫn hiện riêng)."""
    out, da = [], set()
    for m in ds():
        k = m.get("nhom") or m["id"]
        if k in da:
            continue
        da.add(k)
        ms = _cung_nhom(k) if m.get("nhom") else [m]
        tt = [tom_tat(x) for x in ms]
        out.append({"id": k, "ten": f"Điểm {m['stt']}. {m.get('ten_diem', '')} · {len(ms)} cam ({m['domain']})",
                    "trang_thai": "dang" if any(x["trang_thai"] == "dang" for x in ms) else "xong",
                    "so_rot": sum(x["so_rot"] for x in tt), "phut_rot": round(sum(x["phut_rot"] for x in tt), 1),
                    "con_phut": max(x["con_phut"] for x in tt), "dang_rot": any(x["dang_rot"] for x in tt),
                    "pdf": next((x["pdf"] for x in tt if x["pdf"]), ""), "domain": m["domain"], "stt": m["stt"],
                    "cams": [x["http"] for x in tt], "http": m["http"],
                    "chi_tiet": [{"so": x["so"], "so_rot": x["so_rot"], "dang_rot": x["dang_rot"]} for x in tt]})
    return out


def tom_tat(m):
    sk = _doc(_thu_muc(m["id"], "su_kien.json"), [])
    return {"id": m["id"], "ten": f"Điểm {m['stt']} · cam {m['so']} ({m['domain']}:{m['http']})", "trang_thai": m["trang_thai"],
            "so_rot": len(sk) + (1 if m.get("dang_rot") else 0), "phut_rot": round(sum(x["dur"] for x in sk) / 60, 1),
            "con_phut": max(0, round((m["het"] - time.time()) / 60)), "dang_rot": bool(m.get("dang_rot")), "pdf": m.get("pdf", ""),
            "domain": m["domain"], "http": m["http"], "stt": m["stt"], "so": m["so"]}


def _video_hong(mau):
    return str(mau.get("rtsp", "")).startswith("loi")


def _xu_ly_mau(m, mau):
    """Ghi mẫu + máy trạng thái. HỎNG = port web không vào được HOẶC luồng video lỗi (web vẫn lên)."""
    with open(_thu_muc(m["id"], "mau.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(mau, ensure_ascii=False) + "\n")
    m["lan_do"] += 1
    if not m["ip_dau"] and mau["ip"]:
        m["ip_dau"] = mau["ip"]
    if not mau["net"]:                      # điện thoại không có mạng → không kết luận gì
        m["khong_do"] = m.get("khong_do", 0) + 1
        return
    web = mau["cam"] == "mo"
    if mau.get("rtsp"):
        m["rtsp_cuoi"] = mau["rtsp"]
    elif not web:
        m["rtsp_cuoi"] = ""                 # web mất → lần lên sau phải đo lại video từ đầu
    vid_hong = web and _video_hong({"rtsp": mau.get("rtsp") or m.get("rtsp_cuoi", "")})
    if mau.get("rtsp") == "xac_thuc":
        m["rtsp_xac_thuc"] = m.get("rtsp_xac_thuc", 0) + 1
    if web:
        m["lan_toi"] = m.get("lan_toi", 0) + 1
        m["ms_tong"] = m.get("ms_tong", 0) + mau["ms"]
        m["ms_max"] = max(m.get("ms_max", 0), mau["ms"])
        if vid_hong:
            m["video_loi"] = m.get("video_loi", 0) + 1
    hong = (not web) or vid_hong
    if not hong:
        if m.get("dang_rot"):
            _dong_su_kien(m, mau)
        elif m.get("lien_tiep_hong", 0) == 1 and m.get("hong_dau"):     # hỏng đúng 1 lần đo rồi lên → chập chờn ngắn
            cc = _doc(_thu_muc(m["id"], "chap_chon.json"), [])
            cc.append(m["hong_dau"])
            _ghi(_thu_muc(m["id"], "chap_chon.json"), cc)
        m["lien_tiep_hong"] = 0
        m["hong_dau"] = None
        if time.time() - m.get("anh_luc", 0) > ANH_MOI:   # ảnh "trước khi rớt" (ghi đè, chỉ 1 file)
            if _chup(m, "moi_nhat.jpg"):
                m["anh_luc"] = time.time()
        m["ip_cuoi_len"] = mau["ip"] or m.get("ip_cuoi_len", "")
        return
    m["lien_tiep_hong"] = m.get("lien_tiep_hong", 0) + 1
    kieu = "video" if vid_hong else ("treo" if mau["cam"] == "treo" else "mat")
    if m["lien_tiep_hong"] == 1:
        m["hong_dau"] = {"t": mau["t"], "kieu": kieu, "ban_len": any(v == "mo" for v in mau["ban"].values())}
    if m.get("dang_rot"):
        r = m["dang_rot"]
        r["mau"] += 1
        r["video"] += 1 if vid_hong else 0
        r["treo"] = r.get("treo", 0) + (1 if mau["cam"] == "treo" else 0)
        r["ban_len"] += sum(1 for v in mau["ban"].values() if v == "mo")
        r["ban_do"] += len(mau["ban"])
        r["tu_choi"] += 1 if mau["cam"] == "tu_choi" else 0
        if mau["ip"] and mau["ip"] != r["ip_truoc"]:
            r["ip_moi"] = mau["ip"]
        if not mau["ip"]:
            r["dns_loi"] += 1
    elif m["lien_tiep_hong"] >= ROT_SAU:
        bd = (m.get("hong_dau") or {}).get("t", mau["t"] - m["nhip"] * (ROT_SAU - 1))
        dau_video = (m.get("hong_dau") or {}).get("kieu") == "video"
        m["dang_rot"] = {"bd": bd, "ip_truoc": m.get("ip_cuoi_len") or m["ip_dau"], "ip_moi": "", "mau": ROT_SAU,
                         "video": (1 if vid_hong else 0) + (1 if dau_video else 0),
                         "treo": (1 if mau["cam"] == "treo" else 0) + (1 if (m.get("hong_dau") or {}).get("kieu") == "treo" else 0),
                         "ban_len": sum(1 for v in mau["ban"].values() if v == "mo") + (1 if (m.get("hong_dau") or {}).get("ban_len") else 0),
                         "ban_do": len(mau["ban"]) * ROT_SAU,
                         "tu_choi": 1 if mau["cam"] == "tu_choi" else 0, "dns_loi": 0 if mau["ip"] else 1, "n": 0}
        sk = _doc(_thu_muc(m["id"], "su_kien.json"), [])
        n = len(sk) + 1
        m["dang_rot"]["n"] = n
        anh = _thu_muc(m["id"], "moi_nhat.jpg")
        if os.path.exists(anh):
            import shutil
            shutil.copy(anh, _thu_muc(m["id"], f"truoc_{n}.jpg"))
            m["dang_rot"]["anh_truoc"] = _thu_muc(m["id"], f"truoc_{n}.jpg")


_DANG_XEM = {}      # (tên/IP, port rtsp) → (lúc báo, "len"/"ngat") — màn xem trực tiếp báo mỗi ~30 giây


def bao_dang_xem(host, port_rtsp, trang_thai):
    _DANG_XEM[(str(host).lower(), int(port_rtsp))] = (time.time(), trang_thai)


def dang_xem(m, ip=""):
    """Cam này đang được mở xem trực tiếp (báo trong 60 giây qua)? → "len"/"ngat", không xem → None."""
    ten = {str(m["domain"]).lower(), str(m.get("ip_dau") or ""), str(m.get("ip_cuoi_len") or ""), str(ip or "")} - {""}
    hop = [(t, tt) for (h, pt), (t, tt) in list(_DANG_XEM.items())
           if h in ten and pt == int(m.get("rtsp") or 0) and time.time() - t < 60]
    return max(hop)[1] if hop else None       # báo mới nhất thắng


def ghi_live(domain, port_rtsp, luc_ngat, luc_len=0.0):
    """Màn xem trực tiếp báo luồng bị ngắt / lên lại → ghi vào lần theo dõi đang chạy của đúng cam đó (hai màn luôn khớp)."""
    with _KHOA:
        for m in ds():
            ten = {str(m["domain"]).lower(), str(m.get("ip_dau") or ""), str(m.get("ip_cuoi_len") or "")}
            if m["trang_thai"] != "dang" or str(domain).lower() not in ten or int(m.get("rtsp") or 0) != int(port_rtsp):
                continue
            lv = _doc(_thu_muc(m["id"], "live.json"), [])
            if luc_len and lv and not lv[-1].get("len"):
                lv[-1]["len"] = float(luc_len)
            elif not luc_len:
                lv.append({"ngat": float(luc_ngat)})
            _ghi(_thu_muc(m["id"], "live.json"), lv)
            return True
    return False


def _dong_su_kien(m, mau, ket_thuc_theo_doi=False):
    r = m.pop("dang_rot")
    m["dang_rot"] = None
    kt = mau["t"] if mau else min(time.time(), m["het"])
    su = {"n": r["n"], "bd": r["bd"], "kt": kt, "dur": max(0, kt - r["bd"]), "chua_len": ket_thuc_theo_doi,
          "ip_truoc": r["ip_truoc"], "ip_sau": (mau or {}).get("ip") or r.get("ip_moi", ""),
          "ban_co": bool(m["ban"]), "ti_le_ban_len": (r["ban_len"] / r["ban_do"]) if r["ban_do"] else None,
          "tu_choi": r["tu_choi"] / max(1, r["mau"]), "dns_loi": r["dns_loi"], "anh_truoc": r.get("anh_truoc", ""),
          "video": r.get("video", 0) / max(1, r["mau"]), "treo": r.get("treo", 0) / max(1, r["mau"]), "da_bao": bool(r.get("da_bao"))}
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
    "man_xem_ngat": ("Luồng video bị ngắt (ghi từ chính màn xem trực tiếp)",
                     ["Kiểm tra số người xem cùng lúc: IOC/đầu ghi, app CamLink, điện thoại… — cam Oryza giới hạn số luồng, vượt thì ngắt bớt.",
                      "Đầu ghi/IOC nên kéo luồng PHỤ; giảm độ phân giải/bitrate luồng chính nếu đường truyền upload của điểm yếu.",
                      "Nếu vẫn ngắt khi chỉ còn 1 nơi xem: khởi động lại cam, kiểm tra nguồn/PoE và dây mạng."]),
    "cam_treo": ("Cam treo: port vẫn nhận kết nối nhưng cam không trả lời (phần mềm cam bị đơ)",
                 ["Khởi động lại cam: rút nguồn/PoE 10 giây rồi cắm lại (cam treo không nhận lệnh khởi động lại qua mạng).",
                  "Treo lặp lại: kiểm tra nguồn (adaptor yếu, PoE quá tải), nhiệt độ hộp cam; cập nhật firmware.",
                  "Điểm hay treo: gắn ổ cắm/rơ-le điều khiển từ xa (~200–300 nghìn đồng) để tự cắt nguồn cam từ xa."]),
    "video_ngat": ("Web cam vẫn lên nhưng luồng video bị ngắt",
                   ["Kiểm tra số người xem cùng lúc: IOC/đầu ghi, app CamLink, điện thoại… — cam Oryza giới hạn số luồng, vượt thì ngắt bớt. Tắt bớt nơi xem trùng.",
                    "Đầu ghi/IOC nên kéo luồng PHỤ cho xem nhiều nơi; giảm độ phân giải/bitrate luồng chính nếu đường truyền upload yếu.",
                    "Nếu vẫn lặp lại khi chỉ có 1 nơi xem: khởi động lại cam (Sửa từ xa), cập nhật firmware."]),
    "mat_mo_port": ("Modem từ chối port của cam (luật mở port mất hoặc cam đổi IP trong mạng)",
                    ["Đặt IP tĩnh cho cam (vd .200) và kiểm tra lại luật mở port trên modem — dùng CÀI ĐIỂM NÀY khi tới điểm.",
                     "Tắt UPnP tự động trên modem nếu luật port hay bị xoá sau khi modem khởi động lại."]),
}


def phan_loai(su):
    if su.get("treo", 0) >= 0.5:
        k = "cam_treo"
    elif su.get("video", 0) >= 0.5:
        k = "video_ngat"
    elif su.get("tu_choi", 0) >= 0.5:
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
    if m.get("nhom"):          # theo dõi cả điểm: báo cáo chung làm khi cả nhóm xong (_pdf_nhom)
        return
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
    mat_mang = sum(1 for x in mau if not x["net"]) * m["nhip"]
    # khoảng trống: điện thoại dừng app (tiết kiệm pin/ngủ sâu) → không có số đo, không được tính là cam lên
    moc = [m["bat_dau"]] + [x["t"] for x in mau] + [m["het"]]
    trong = [(moc[i], moc[i + 1]) for i in range(len(moc) - 1) if moc[i + 1] - moc[i] > 3 * m["nhip"]]
    ngu = sum(b - a - m["nhip"] for a, b in trong)
    khong_do = mat_mang + ngu
    doi_mang, mg = [], ""
    for x in mau:
        if x.get("mang") and x["mang"] != mg:
            if mg:
                doi_mang.append((x["t"], mg, x["mang"]))
            mg = x["mang"]
    # Lần ngắt ghi từ MÀN XEM là sự thật → tính vào số lần rớt (bỏ lần trùng với lần rớt đo được), kể cả khi dịch vụ đo bị dừng
    lv = _doc(_thu_muc(tid, "live.json"), [])
    them_do = 0
    sk_do = list(sk)                 # chỉ bỏ lần ngắt TRÙNG với lần rớt đo được (không gộp các lần ngắt liền nhau của màn xem)
    for i, x in enumerate(lv):
        bd = x["ngat"]
        if any(y["bd"] - 30 <= bd <= y.get("kt", y["bd"] + y["dur"]) + 30 for y in sk_do):
            continue
        dur = (x["len"] - bd) if x.get("len") else 0
        sk.append({"n": 0, "bd": bd, "kt": x.get("len") or bd, "dur": dur, "loai": "man_xem_ngat", "nguyen_nhan": NGUYEN_NHAN["man_xem_ngat"][0],
                   "ip_truoc": "", "ip_sau": "", "chua_ro_len": not x.get("len"), "tu_man_xem": True})
        if any(a <= bd <= b for a, b in trong):
            them_do += dur          # lúc đó app không đo nhưng màn xem đang chạy → đoạn này coi như có số đo
    sk.sort(key=lambda y: y["bd"])
    for i, y in enumerate(sk, 1):
        y["n"] = i
    # CHẨN ĐOÁN theo % khả năng (không khẳng định) — có đối chiếu điểm khác của dự án rớt cùng lúc
    import camlink_chandoan as D
    khac = {}
    for y in ds():
        if y.get("ma") == m.get("ma") and y["domain"] != m["domain"]:
            khac.setdefault(y["domain"], []).extend(z["bd"] for z in _doc(_thu_muc(y["id"], "su_kien.json"), []))
    for y in sk:
        cung = sum(1 for _, ds_bd in khac.items() if any(abs(t - y["bd"]) <= 180 for t in ds_bd))
        y["chan_doan"] = D.tinh(D.tu_su_kien(y, cung), m.get("ma", ""), "dang_mat" if y.get("chua_len") else "sau_khi_len")
    rot = sum(x["dur"] for x in sk)
    tg_do = max(1, tong_tg - khong_do + them_do)
    phu = min(1.0, tg_do / tong_tg)
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
    cc = _doc(_thu_muc(tid, "chap_chon.json"), [])
    if not sk:
        cc0 = _doc(_thu_muc(tid, "chap_chon.json"), [])
        ket = ("Không có lần rớt kéo dài, nhưng có " + str(len(cc0)) + " lần chập chờn ngắn (< 1 phút)." if cc0
               else "Cam ổn định trong suốt thời gian theo dõi — không có lần rớt nào.")
    else:
        tl = {}
        for y in sk:
            k = y["chan_doan"]["kha_nang"][0]
            g = tl.setdefault(k["ma"], {"ten": k["ten"], "so": 0, "pt": []})
            g["so"] += 1
            g["pt"].append(k["pt"])
        xep = sorted(tl.values(), key=lambda g: -g["so"])
        ket = f"Rớt {len(sk)} lần — khả năng cao nhất: " + "; ".join(
            f"{g['ten'].split('(')[0].strip().lower()} ({g['so']} lần, trung bình {round(sum(g['pt']) / len(g['pt']))}%)" for g in xep[:2]) + "."
    thieu = phu < 0.5
    if thieu:      # đo được quá ít → KHÔNG được kết luận ổn định (trước đây ghi "ổn định 100%" dù chỉ đo 3 lượt trong 3 giờ)
        ket = (f"KHÔNG ĐỦ DỮ LIỆU để kết luận — chỉ đo được {round(100 * phu)}% thời gian ({_thoi_luong(tg_do)} / {_thoi_luong(tong_tg)}). "
               + (f"Trong lúc đo được đã ghi {len(sk)} lần rớt/ngắt. " if sk else "")
               + "Cần theo dõi lại.")
    elif phu < 0.8:
        ket += f" (Lưu ý: chỉ đo được {round(100 * phu)}% thời gian.)"
    return {"m": m, "su_kien": sk, "nhom": nhom, "tong_tg": tong_tg, "khong_do": khong_do, "rot": rot,
            "len_pt": round(100 * max(0, tg_do - rot) / tg_do, 2), "dai_nhat": max([x["dur"] for x in sk], default=0),
            "phu": phu, "thieu": thieu, "tg_do": tg_do,
            "gio": gio, "ms_tb": ms_tb, "ms_max": m.get("ms_max", 0), "video_loi": m.get("video_loi", 0),
            "so_mau": len(mau), "ket_luan": ket, "mau": mau, "chap_chon": cc, "live": lv,
            "rtsp_xac_thuc": m.get("rtsp_xac_thuc", 0), "trong": trong, "ngu": ngu, "mat_mang": mat_mang, "doi_mang": doi_mang}


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
    """Báo cáo 1–3 trang A4. Theo dõi cả điểm → MỘT báo cáo cho mọi cam của điểm (bảng so sánh, dải thời gian từng cam)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.graphics.shapes import Drawing, Rect, String

    m0 = _doc(_thu_muc(tid, "meta.json"))
    ids = [x["id"] for x in _cung_nhom(m0["nhom"])] if m0.get("nhom") else [tid]
    A = [phan_tich(i) for i in ids]
    m = A[0]["m"]
    nhieu = len(A) > 1
    F, FB = _font()
    s = lambda **k: ParagraphStyle("x", fontName=k.pop("f", F), fontSize=k.pop("c", 9.5), leading=k.pop("l", 12.5), **k)
    H1, H2, P, NHO = s(f=FB, c=15, l=19, spaceAfter=2), s(f=FB, c=11.5, l=15, spaceBefore=7, spaceAfter=3, textColor=colors.HexColor("#0F5D8C")), s(), s(c=8, l=10, textColor=colors.HexColor("#5B6776"))
    XANH, DO, VANG, XAM, TIM = colors.HexColor("#1D7A46"), colors.HexColor("#C0392B"), colors.HexColor("#C88A00"), colors.HexColor("#D7DEE5"), colors.HexColor("#7D3C98")
    ngay = time.strftime('%Y%m%d_%H%M', time.localtime(m['bat_dau']))
    ten_file = f"TheoDoi_diem{m['stt']}_{len(A)}cam_{ngay}.pdf" if nhieu else f"TheoDoi_diem{m['stt']}_cam{m['so']}_{ngay}.pdf"
    f = os.path.join(GOC, "ketqua", ten_file)
    doc = SimpleDocTemplate(f, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f"Theo dõi ổn định camera — điểm {m['stt']}", author="CamLink")
    W = A4[0] - 28 * mm
    el = []
    cam_txt = ", ".join(f"cam {a['m']['so']} (:{a['m']['http']})" for a in A)
    el.append(Paragraph("BÁO CÁO THEO DÕI ỔN ĐỊNH CAMERA", H1))
    el.append(Paragraph((f"{m['du_an']} · " if m.get('du_an') else "") + f"Điểm {m['stt']}. {m['ten_diem']} · <b>{m['domain']}</b> · {cam_txt}", P))
    tong_tg = A[0]["tong_tg"]
    el.append(Paragraph(f"Theo dõi từ {_gio(m['bat_dau'])} đến {_gio(m['het'])} ({_thoi_luong(tong_tg)}), đo {A[0]['so_mau']} lượt, "
                        f"mỗi {m['nhip']} giây (hỏi trang web từng cam, luồng video 2 phút/lần) · CamLink", NHO))
    el.append(Spacer(1, 5))
    # ---- 1. bảng tóm tắt từng cam
    rows = [["Cam", "Thời gian lên", "Số lần rớt", "Tổng rớt", "Dài nhất", "Chập chờn", "Phản hồi"]]
    for a in A:
        rows.append([f"Cam {a['m']['so']} (:{a['m']['http']})", (Paragraph(f"không đủ dữ liệu<br/>(đo được {round(100 * a['phu'])}%)", s(c=8, l=10)) if a["thieu"] else f"{a['len_pt']} %"), str(len(a["su_kien"])), _thoi_luong(a["rot"]) if a["rot"] else "0",
                     _thoi_luong(a["dai_nhat"]) if a["su_kien"] else "—", str(len(a["chap_chon"])), f"{a['ms_tb']} ms"])
    tb = Table(rows, colWidths=[W * .2, W * .14, W * .11, W * .14, W * .13, W * .14, W * .14])
    stl = [("FONT", (0, 0), (-1, -1), F, 9), ("FONT", (0, 0), (-1, 0), FB, 8.5), ("GRID", (0, 0), (-1, -1), .4, XAM),
           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EEF5")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    for i, a in enumerate(A, 1):
        stl.append(("TEXTCOLOR", (1, i), (1, i), colors.HexColor("#5B6776") if a["thieu"] else (XANH if not a["su_kien"] else (DO if a["len_pt"] < 97 else VANG))))
        stl.append(("FONT", (1, i), (1, i), FB, 9))
    tb.setStyle(TableStyle(stl))
    el.append(tb)
    kd = A[0]
    if kd["khong_do"]:
        ly = []
        if kd["mat_mang"]:
            ly.append(f"điện thoại mất mạng {_thoi_luong(kd['mat_mang'])}")
        if kd["ngu"]:
            ly.append(f"điện thoại dừng app {len(kd['trong'])} lần, {_thoi_luong(kd['ngu'])}")
        el.append(Paragraph(f"Không đo được (không tính vào kết quả): {_thoi_luong(kd['khong_do'])} — " + "; ".join(ly) + ".", NHO))
    if kd["doi_mang"]:
        el.append(Paragraph(f"Điện thoại đổi mạng {len(kd['doi_mang'])} lần (" + ", ".join(
            f"{time.strftime('%H:%M', time.localtime(t))} {a.replace('di_dong', '4G')}→{b.replace('di_dong', '4G')}" for t, a, b in kd["doi_mang"][:6])
            + ") — lần rớt trùng giờ đổi mạng nên xem lại.", NHO))
    el.append(Spacer(1, 3))
    # kết luận
    ca_diem = sum(1 for a in A for x in a["su_kien"] if x["loai"] in ("ca_diem", "modem_doi_ip"))
    for a in A:
        kl = a["ket_luan"].replace("Cam ổn định", "Ổn định")
        el.append(Paragraph(f"<b>{'Cam ' + str(a['m']['so']) + ': ' if nhieu else 'Kết luận: '}</b>{kl}",
                            s(c=10, l=13.5, textColor=VANG if a["thieu"] else (XANH if not a["su_kien"] else (DO if a["len_pt"] < 97 else VANG)))))
    if nhieu and ca_diem:
        el.append(Paragraph(f"<b>Cả điểm:</b> {ca_diem} lần mọi cam cùng mất → không phải lỗi từng cam; khả năng điện hay modem/VNPT xem mục 1.", s(c=10, l=13.5, textColor=DO)))
    # ---- dải thời gian từng cam
    nhan_w = 42 if nhieu else 0
    BW = W - nhan_w
    d = Drawing(W, 16 + 16 * len(A))
    t0, t1 = m["bat_dau"], max(m["het"], m["bat_dau"] + 1)
    X = lambda t: nhan_w + BW * (t - t0) / (t1 - t0)
    for i, a in enumerate(A):
        y = 12 + 16 * (len(A) - 1 - i)
        if nhieu:
            d.add(String(0, y + 3, f"Cam {a['m']['so']}", fontName=FB, fontSize=8))
        d.add(Rect(nhan_w, y, BW, 11, fillColor=colors.HexColor("#CFE8D8"), strokeColor=None))
        for x in a["mau"]:
            if not x["net"]:
                d.add(Rect(X(x["t"]), y, max(1, BW * m["nhip"] / (t1 - t0)), 11, fillColor=XAM, strokeColor=None))
        for g0, g1 in a["trong"]:
            d.add(Rect(X(g0), y, max(1, X(g1) - X(g0)), 11, fillColor=XAM, strokeColor=None))
        for x in a["chap_chon"]:
            d.add(Rect(X(x["t"]), y, 1, 11, fillColor=VANG, strokeColor=None))
        for x in a["su_kien"]:
            d.add(Rect(X(x["bd"]), y, max(1.5, BW * x["dur"] / (t1 - t0)), 11, fillColor=TIM if x["loai"] == "cam_treo" else DO, strokeColor=None))
    for i in range(5):
        tx = t0 + (t1 - t0) * i / 4
        d.add(String(nhan_w + BW * i / 4 - (0 if i == 0 else (24 if i == 4 else 12)), 2, time.strftime("%H:%M", time.localtime(tx)), fontName=F, fontSize=7))
    el.append(Paragraph("Dải thời gian: xanh = lên · đỏ = rớt · tím = cam treo · vàng = chập chờn ngắn · xám = không đo được", NHO))
    el.append(d)
    # ---- 2. nguyên nhân
    el.append(Paragraph("1. Chẩn đoán các lần rớt — khả năng lỗi (không khẳng định)", H2))
    co_rot = False
    import camlink_chandoan as D
    for a in A:
        tien = f"Cam {a['m']['so']} — " if nhieu else ""
        gop = {}
        for x in a["su_kien"]:
            pd = x.get("chan_doan")
            if not pd:
                continue
            k = pd["kha_nang"][0]
            g = gop.setdefault(k["ma"], {"ten": k["ten"], "so": 0, "giay": 0, "pt": []})
            g["so"] += 1
            g["giay"] += x["dur"]
            g["pt"].append(k["pt"])
        for k, g in sorted(gop.items(), key=lambda y: -y[1]["so"]):
            co_rot = True
            el.append(Paragraph(f"• {tien}Khả năng cao nhất <b>{g['ten']}</b> (trung bình {round(sum(g['pt']) / len(g['pt']))}%): "
                                f"{g['so']} lần, tổng {_thoi_luong(g['giay'])}", P))
        if a["gio"] and len(a["su_kien"]) >= 3:
            h, n = max(a["gio"].items(), key=lambda x: x[1])
            if n >= 2:
                el.append(Paragraph(f"• {tien}Rớt dồn nhiều nhất khung giờ {h:02d}:00–{(h + 1) % 24:02d}:00 ({n} lần)"
                                    + (" — giờ cao điểm điện tối, nghi nguồn điện yếu." if 17 <= h <= 21 else "."), P))
        if a["chap_chon"]:
            cc = a["chap_chon"]
            loai = {"video": "web còn nhưng video ngắt", "treo": "treo", "mat": "mất hẳn"}
            dem = {}
            for x in cc:
                dem[x["kieu"]] = dem.get(x["kieu"], 0) + 1
            el.append(Paragraph(f"• {tien}<b>Chập chờn ngắn (&lt; 1 phút)</b>: {len(cc)} lần ("
                                + ", ".join(f"{n} lần {loai.get(k, k)}" for k, n in dem.items()) + "). Giờ: "
                                + ", ".join(time.strftime("%H:%M", time.localtime(x["t"])) for x in cc[:16]) + (" …" if len(cc) > 16 else ""), P))
        if a["live"] and False:
            lv = a["live"]
            el.append(Paragraph(f"• {tien}<b>Màn xem trực tiếp bị ngắt</b> (ghi từ chính màn xem): {len(lv)} lần — "
                                + ", ".join(time.strftime("%H:%M:%S", time.localtime(x["ngat"])) + (f" (lên lại sau {_thoi_luong(x['len'] - x['ngat'])})" if x.get("len") else "")
                                            for x in lv[:10]) + (" …" if len(lv) > 10 else ""), P))
        if a["rtsp_xac_thuc"]:
            el.append(Paragraph(f"• {tien}Luồng video từ chối user/pass {a['rtsp_xac_thuc']} lần — không tính là rớt; kiểm tra user/pass cam lưu trong CamLink.", NHO))
    if not co_rot:
        el.append(Paragraph("Không đủ dữ liệu để biết có rớt hay không." if any(a["thieu"] for a in A) else "Không có lần rớt kéo dài nào trong thời gian theo dõi.", P))
    # ---- 3. danh sách (gộp mọi cam, tối đa 18 lần dài nhất)
    tat = [(a["m"]["so"], x) for a in A for x in a["su_kien"]]
    if tat:
        el.append(Paragraph("2. Danh sách các lần rớt", H2))
        hien = sorted(sorted(tat, key=lambda y: -y[1]["dur"])[:18], key=lambda y: y[1]["bd"])
        rows = [(["Cam"] if nhieu else []) + ["Bắt đầu", "Lên lại", "Kéo dài", "Khả năng lỗi · dấu hiệu"]]
        for so, x in hien:
            dh = []
            if x.get("ti_le_ban_len") is not None:
                dh.append(f"cam khác cùng điểm lên {round(100 * x['ti_le_ban_len'])}%")
            if x.get("ip_sau") and x["ip_sau"] != x["ip_truoc"]:
                dh.append(f"IP {x['ip_truoc']} → {x['ip_sau']}")
            if x.get("dns_loi"):
                dh.append("tên miền không phân giải")
            kdc = x.get("cam_khoi_dong")
            if kdc in ("ca_diem", "rieng", "ca_diem_chua_ro"):
                dh.append(f"nhật ký cam: khởi động lại {x.get('cam_khoi_dong_luc', '')}")
            elif kdc == "khong":
                dh.append("nhật ký cam: không khởi động lại")
            rows.append(([str(so)] if nhieu else []) + [_gio(x["bd"])[:8], (Paragraph("chưa lên<br/>(hết giờ theo dõi)", s(c=8, l=10)) if x.get("chua_len")
                        else Paragraph("không ghi được<br/>(rời màn xem)", s(c=8, l=10)) if x.get("chua_ro_len") else _gio(x["kt"])[:8]),
                        _thoi_luong(x["dur"]), Paragraph(("<b>" + D.dong_mot_dong(x["chan_doan"]).replace("Modem hoặc đường truyền VNPT bị đứt", "Modem/VNPT").replace("Mất điện lưới tại điểm", "Mất điện")
                                                           .replace("Nguồn rời hoặc dây mạng của riêng cam này", "Nguồn/dây cam") + "</b>" if x.get("chan_doan") else x["nguyen_nhan"])
                                                          + (f"<br/><font color='#5B6776'>{'; '.join(dh)}</font>" if dh else ""), s(c=8, l=10.5))])
        cw = ([W * .06] if nhieu else []) + [W * .13, W * .16, W * .14] + [W * (.51 - (.06 if nhieu else 0) + .06 * (0 if nhieu else 0))]
        cw[-1] = W - sum(cw[:-1])
        t = Table(rows, colWidths=cw, repeatRows=1)
        t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), F, 8.5), ("FONT", (0, 0), (-1, 0), FB, 8.5), ("GRID", (0, 0), (-1, -1), .3, XAM),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EEF5")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        el.append(t)
        if len(tat) > len(hien):
            con = [x for y in tat if y not in hien for x in [y[1]]]
            el.append(Paragraph(f"Còn {len(con)} lần rớt ngắn khác, tổng {_thoi_luong(sum(x['dur'] for x in con))} (không liệt kê).", NHO))
    # ---- 4. đề xuất (gộp mọi cam, nhóm nhiều lần nhất lên trước, không lặp)
    el.append(Paragraph("3. Đề xuất khắc phục — theo khả năng lỗi", H2))
    gop_dx = {}
    for a in A:
        for x in a["su_kien"]:
            pd = x.get("chan_doan")
            if pd:
                for k in pd["kha_nang"][:2]:
                    if k["pt"] >= 20:
                        g = gop_dx.setdefault(k["ma"], {**k, "so": 0})
                        g["so"] += 1
    for i, (k, g) in enumerate(sorted(gop_dx.items(), key=lambda y: -y[1]["so"]), 1):
        el.append(Paragraph(f"<b>{i}. {g['ten']}</b> ({g['so']} lần có khả năng ≥ 20%) — "
                            + ("<font color='#1D7A46'>sửa được từ xa bằng CamLink</font>" if g["tu_xa"] else "<font color='#B42318'>phải xử lý tại hiện trường</font>"), P))
        el.append(Paragraph(f"   – Việc cần làm: {g['viec']}", P))
        el.append(Paragraph(f"   – Ai xử lý: {g['ai']}", P))
    gom = {}
    for a in A:
        for g in a["nhom"]:
            x = gom.setdefault(g["loai"], {"ten": g["ten"], "so": 0, "cam": []})
            x["so"] += g["so"]
            x["cam"].append(str(a["m"]["so"]))
    if any(a["thieu"] for a in A):
        el.append(Paragraph("<b>Theo dõi lại</b>: lần này điện thoại dừng CamLink nên gần như không đo được. Lần sau: cắm sạc, cho CamLink chạy nền "
                            "không tối ưu pin (app tự hỏi khi bật theo dõi), không cài bản app mới giữa chừng.", P))
    elif not gom:
        el.append(Paragraph("Không cần xử lý. Nếu trước đây cam từng chập chờn, nên theo dõi thêm một lần vào khung giờ hay rớt.", P))
    if gop_dx:
        gom = {}
    ngan_video = any(x["kieu"] == "video" for a in A for x in a["chap_chon"]) or any(a["live"] for a in A)
    if ngan_video and "video_ngat" not in gom and "man_xem_ngat" not in gom:
        el.append(Paragraph("<b>Cho các lần video ngắt ngắn:</b>", P))
        for v in NGUYEN_NHAN["video_ngat"][1]:
            el.append(Paragraph(f"   – {v}", P))
    if kd["khong_do"] > 0.2 * tong_tg:
        el.append(Paragraph("<b>Lưu ý:</b> hơn 20% thời gian không đo được — để điện thoại cắm sạc, sóng ổn định, và cho CamLink chạy nền không tối ưu pin.", P))
    # ---- 5. ảnh tiêu biểu (2 lần dài nhất có ảnh)
    cap = [(so, x) for so, x in sorted(tat, key=lambda y: -y[1]["dur"]) if x.get("anh_truoc") or x.get("anh_sau")][:2]
    if cap:
        el.append(Paragraph("4. Ảnh trước / sau lần rớt tiêu biểu", H2))
        for so, x in cap:
            o = []
            for f_anh, nhan in ((x.get("anh_truoc"), "Trước khi rớt"), (x.get("anh_sau"), "Sau khi lên lại")):
                if f_anh and os.path.exists(f_anh):
                    o.append([Image(f_anh, width=W * .40, height=W * .40 * 9 / 16), Paragraph(nhan, NHO)])
                else:
                    o.append([Paragraph("(không có ảnh)", NHO), Paragraph(nhan, NHO)])
            tbl = Table([[o[0][0], o[1][0]], [o[0][1], o[1][1]]], colWidths=[W * .5, W * .5])
            el.append(KeepTogether([Paragraph((f"Cam {so} · " if nhieu else "") + f"lần {x['n']} lúc {_gio(x['bd'])}, kéo dài {_thoi_luong(x['dur'])}", P), tbl]))
    el.append(Spacer(1, 6))
    el.append(Paragraph("Cách đọc: \"rớt\" = 2 lượt đo liên tiếp (≥ 1 phút) cam không trả lời trang web, bị treo, hoặc luồng video lỗi, trong khi điện thoại vẫn có mạng; "
                        "hỏng 1 lượt rồi lên = \"chập chờn ngắn\"; lần ngắt ghi từ màn xem trực tiếp cũng tính là rớt. "
                        "Khả năng lỗi (%) = mức nền kinh nghiệm × bằng chứng đo được (nhật ký cam, IP, cam khác cùng điểm, điểm khác cùng lúc), không phải khẳng định; "
                        "sau khi xử lý bấm \"Nguyên nhân thật là…\" trong app để app chính xác dần. \"Treo\" = port vẫn nhận kết nối nhưng cam không trả lời. "
                        "Nguyên nhân suy ra từ cam khác cùng điểm, IP công cộng của modem và thời gian rớt; \"khởi động lại\" là suy luận "
                        "từ rớt ngắn 0,5–3 phút khi cam khác vẫn lên.", NHO))
    doc.build(el)
    return f
