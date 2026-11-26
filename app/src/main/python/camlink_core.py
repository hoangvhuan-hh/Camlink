# -*- coding: utf-8 -*-
"""Cầu nối giữa giao diện Android và lõi camlink_dt.py — hỗ trợ nhiều dự án.

Mỗi file khảo sát Excel = 1 dự án, lưu riêng ở <app>/duan/<mã>.json:
  {"ten": tên dự án, "diem": {stt: {...}}, "toa_do": {stt: [lat, lng]}, "da_xong": {stt: "dd/mm hh:mm"}}
User/pass cam + modem dùng chung cho mọi dự án (camlink_caidat.json).
GPS tìm điểm gần nhất trên TẤT CẢ dự án → tự chọn đúng dự án + điểm.
"""
import json, os, re, time, unicodedata
import camlink_dt as C

from camlink_phien_ban import PHIEN_BAN as PHIEN_BAN_LOI  # phiên bản lõi ở camlink_phien_ban.py
KENH_CAP_NHAT = "https://claude.ai/artifact/D5udnnkXEqbKMRBmsMhjGy"   # kênh cập nhật (đổi được bằng gói zip, không cần APK)   # phiên bản phần logic Python (cập nhật đè được, vài trăm KB)

GOC = None


def _cb(x):
    """Nhận hàm ghi nhật ký từ Android (đối tượng có .ghi) hoặc hàm Python; None → bỏ qua."""
    if x is None:
        return lambda *_: None
    return getattr(x, "ghi", x)


def _thu_muc_du_an():
    return os.path.join(GOC, "duan")


def khoi_tao(thu_muc):
    import camlink_litemark as L
    L.khoi_tao(thu_muc)
    import camlink_theodoi as TD
    TD.khoi_tao(thu_muc)
    TD.KHI_BAO = _theodoi_bao_lm
    import camlink_chandoan as CD
    CD.khoi_tao(thu_muc)
    import camlink_quantri as QT
    QT.khoi_tao(thu_muc)
    global GOC
    GOC = thu_muc
    os.makedirs(os.path.join(GOC, "ketqua"), exist_ok=True)
    os.makedirs(_thu_muc_du_an(), exist_ok=True)
    C.thu_muc_ra = lambda: os.path.join(GOC, "ketqua")
    _chuyen_du_lieu_cu()


def _chuyen_du_lieu_cu():
    """Bản 1.0 chỉ có 1 dự án (diem.json) → chuyển thành dự án riêng, không mất gì."""
    cu = os.path.join(GOC, "diem.json")
    if not os.path.exists(cu) or _cac_du_an():
        return
    try:
        with open(cu, encoding="utf-8") as f:
            diem = json.load(f)
    except (OSError, ValueError):
        return
    cd = C.doc_cai_dat()
    _ghi_du_an("du-an-1", {"ten": "Dự án 1", "diem": diem, "toa_do": cd.get("toa_do", {}),
                           "da_xong": cd.get("da_xong", {})})


def _ma(ten):
    s = unicodedata.normalize("NFD", ten.lower()).replace("đ", "d")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "du-an"


def _ten_tu_file(ten_file):
    t = os.path.splitext(os.path.basename(ten_file or "Dự án"))[0]
    t = re.sub(r"^(ks|khao[ _-]?sat)[ _-]*", "", t, flags=re.I)
    t = re.sub(r"[_]+", " ", t).strip()
    t = re.sub(r"\s*[\(\[]\d+[\)\]]$|\s*-\s*(copy|bản sao)(\s*\d+)?$", "", t, flags=re.I).strip()  # "(1)", "(2)", "- Copy" do tải trùng
    return t or "Dự án"


def _cac_du_an():
    out = {}
    for f in sorted(os.listdir(_thu_muc_du_an())):
        if f.endswith(".json"):
            try:
                with open(os.path.join(_thu_muc_du_an(), f), encoding="utf-8") as fh:
                    out[f[:-5]] = json.load(fh)
            except (OSError, ValueError):
                pass
    return out


def _doc_du_an(ma):
    with open(os.path.join(_thu_muc_du_an(), ma + ".json"), encoding="utf-8") as f:
        da = json.load(f)
    _so_cam_theo_ho_so(da)
    return da


def _so_cam_theo_ho_so(da):
    """Số cam của điểm không được ÍT hơn số cam app đã tự tay cài tại điểm đó (hồ sơ lúc cài). Dự án lấy từ ghim LiteMark ghi "0 cam"
    → lưới Giám sát chỉ vẽ 1 ô dù điểm có 2 cam. Chỉ nâng lên, không giảm; giá trị gốc của file giữ ở "goc"."""
    try:
        for stt, hs in (da.get("ho_so") or {}).items():
            d = (da.get("diem") or {}).get(stt)
            n = len((hs or {}).get("cam") or [])
            if d is None or n <= int(d.get("so") or 0):
                continue
            cu = int(d.get("so") or 0)
            d.setdefault("goc", {"so": d.get("so"), "bs": d.get("bs")})
            d["so"], d["so_thuc"] = n, n
            ds = d.setdefault("hieu_chinh", [])
            if not any(h.get("ly_do") == "theo hồ sơ lúc cài tại chỗ" and h.get("moi") == n for h in ds):
                ds.append({"luc": str((hs or {}).get("luc", "")), "ly_do": "theo hồ sơ lúc cài tại chỗ", "cu": cu, "moi": n})
    except Exception:
        pass


def _ghi_du_an(ma, da):
    with open(os.path.join(_thu_muc_du_an(), ma + ".json"), "w", encoding="utf-8") as f:
        json.dump(da, f, ensure_ascii=False)


def _chuan(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def nhap_excel(duong_dan, ten_file, log):
    """Đọc file khảo sát (cột No, Tên, link bản đồ, Camera, Camera BS, Domain, USER, PW) thành 1 dự án.
    Nhập lại file cùng tên = cập nhật dự án đó (giữ dấu điểm đã xong)."""
    import openpyxl
    log = _cb(log)
    C.LOG_CB = log
    wb = openpyxl.load_workbook(duong_dan, data_only=True)
    for ws in wb.worksheets:
        for r in range(1, min(ws.max_row, 15) + 1):
            cot = {_chuan(ws.cell(r, c).value): c for c in range(1, ws.max_column + 1) if ws.cell(r, c).value is not None}
            if "domain" in cot:
                break
        else:
            continue

        def tim(*ten):
            for t in ten:
                for k, v in cot.items():
                    if k == t or k.startswith(t):
                        return v
        c_no, c_ten = tim("no", "stt"), tim("tên", "vị trí")
        c_map = next((c for c in range(1, ws.max_column + 1)
                      if any(re.search(r"goo\.gl|google\.[a-z.]+/maps|maps\.app", str(ws.cell(x, c).value or ""))
                             for x in range(r + 1, min(ws.max_row, r + 15) + 1))), None)
        c_cam, c_bs, c_dom = tim("camera"), tim("camera bs"), tim("domain")
        c_u, c_p = tim("user"), tim("pw", "pass")
        ds = {}
        for rr in range(r + 1, ws.max_row + 1):
            g = lambda c: ws.cell(rr, c).value if c else None
            dom = g(c_dom)
            if not dom or "." not in str(dom):
                continue
            k = str(g(c_no) or len(ds) + 1).strip()
            ds[k] = {"ten": str(g(c_ten) or "").strip(), "domain": str(dom).strip().lower(),
                     "u": str(g(c_u) or ""), "p": str(g(c_p) or ""),
                     "so": int(g(c_cam) or 0) + int(g(c_bs) or 0), "bs": int(g(c_bs) or 0), "map": str(g(c_map) or "")}
        if not ds:
            continue
        ten = _ten_tu_file(ten_file)
        ma = _ma(ten)
        # dự án cũ nạp từ bản tải trùng "(1)" → gộp làm MỘT dự án
        for ma_cu, da_cu in _cac_du_an().items():
            if ma_cu != ma and _ma(_ten_tu_file(da_cu.get("ten", "") + ".xlsx")) == ma:
                os.replace(os.path.join(_thu_muc_du_an(), ma_cu + ".json"), os.path.join(_thu_muc_du_an(), ma + ".json"))
                break
        cu = {}
        try:
            cu = _doc_du_an(ma)
        except (OSError, ValueError):
            pass
        log(f"Dự án: {ten} — {len(ds)} điểm, {sum(v['so'] for v in ds.values())} cam"
            + (" (cập nhật dự án đã có)" if cu else ""))
        log("Đang lấy toạ độ từ link bản đồ ...")
        toa_do = {}
        for k, v in ds.items():
            td = C.toa_do_tu_link(v["map"]) if v["map"].startswith("http") else None
            if td:
                toa_do[k] = td
            log(f"  {k}. {v['ten']}: {'%.5f, %.5f' % tuple(td) if td else 'không có toạ độ'}")
        for k, v in ds.items():   # giữ hiệu chỉnh theo thực tế đã ghi trong app
            dc = (cu.get("diem") or {}).get(k, {})
            if dc.get("so_thuc"):
                v["so_thuc"] = dc["so_thuc"]
                v["goc"] = {"so": v.get("so"), "bs": v.get("bs")}
                v["so"], v["bs"] = dc.get("so", v.get("so")), dc.get("bs", v.get("bs"))
                v["hieu_chinh"] = dc.get("hieu_chinh", [])
            if dc.get("rieng"):      # nạp lại file không làm mất user/pass riêng đã nhập cho điểm
                v["rieng"] = dc["rieng"]
        _ghi_du_an(ma, {"ten": ten, "diem": ds, "toa_do": toa_do, "da_xong": cu.get("da_xong", {}),
                        "ho_so": cu.get("ho_so", {})})
        canh = _diem_trung_vi_tri(ma, toa_do)
        for c in canh:
            log("⚠ " + c)
        return f"{ten} ({len(ds)} điểm)"
    raise ValueError("Không thấy bảng có cột 'Domain' trong file.")


def _diem_trung_vi_tri(ma_moi, toa_do_moi):
    """Cảnh báo khi điểm của dự án mới nằm sát (< 400 m) điểm của dự án khác → GPS có thể nhầm."""
    out = []
    for ma, da in _cac_du_an().items():
        if ma == ma_moi:
            continue
        for k1, a in toa_do_moi.items():
            for k2, b in da.get("toa_do", {}).items():
                m = C.khoang_cach(a, b)
                if m < 400:
                    out.append(f"Điểm {k1} gần điểm {k2} của dự án {da['ten']} ({int(m)} m) — tới đó app sẽ hỏi chọn.")
    return out


def co_du_lieu():
    return bool(_cac_du_an())


def so_du_an():
    return len(_cac_du_an())


def _chum_khoa(cd, cd0, loai):
    """Khoá thử thêm cho cam / modem của một điểm, sau mật khẩu đang dùng cho điểm: [(user, pass, nhãn)].
    Chỉ có khi điểm được nhập mật khẩu RIÊNG khác mặc định → thử thêm mật khẩu mặc định của hệ thống.
    (Mật khẩu xuất xưởng của hãng do trình từng hãng tự thử. Không có danh sách mật khẩu nào khác — Huan chốt 25/11.)"""
    u, p = cd.get(loai + "_user") or "admin", cd.get(loai + "_pw") or ""
    u0, p0 = cd0.get(loai + "_user") or "admin", cd0.get(loai + "_pw") or ""
    if p0 and (u0, p0) != (u, p):
        return [(u0, p0, f"mật khẩu {'cam' if loai == 'cam' else 'modem'} mặc định của hệ thống")]
    return []


def viec_con(ma, stt):
    """Sau lượt cài: các việc app chưa làm được (mỗi dòng một việc). Rỗng = app làm trọn."""
    if C.KQ_CUOI.get("stt") != stt:
        return ""
    return "\n".join(f"{i}. {v}" for i, v in enumerate(C.KQ_CUOI.get("viec_con") or [], 1))


def co_cai_dat():
    return "cam_pw" in C.doc_cai_dat()


def lay_cai_dat():
    cd = C.doc_cai_dat()
    return [cd.get("cam_user", "admin"), cd.get("cam_pw", ""), cd.get("modem_user", "admin"), cd.get("modem_pw", "admin")]


def luu_cai_dat(cu, cp, mu, mp):
    cd = C.doc_cai_dat()
    cd.update(cam_user=cu or "admin", cam_pw=cp, modem_user=mu or "admin", modem_pw=mp or "admin")
    C.ghi_cai_dat(cd)


def _cac_diem():
    """[(mã dự án, tên dự án, stt, điểm, đã xong)] theo thứ tự dự án → điểm."""
    out = []
    for ma, da in _cac_du_an().items():
        for k, v in da["diem"].items():
            out.append((ma, da["ten"], k, v, da.get("da_xong", {}).get(k)))
    return out


def danh_sach():
    nhieu = so_du_an() > 1
    return [(f"[{ten}] " if nhieu else "") + f"{k}. {v['ten']} ({v['so']} cam)" + (f"  ✔ {xong}" if xong else "")
            for ma, ten, k, v, xong in _cac_diem()]


def khoa_theo_so_thu_tu(i):
    ma, _, k, _, _ = _cac_diem()[i]
    return [ma, k]


def diem_gan(lat, lng):
    """Trả [mã dự án, stt, tên dự án, tên điểm, mét, có_điểm_khác_sát_bên] hoặc None."""
    ung = []
    for ma, da in _cac_du_an().items():
        for k, td in da.get("toa_do", {}).items():
            ung.append((C.khoang_cach((lat, lng), td), ma, k, da))
    if not ung:
        return None
    ung.sort(key=lambda x: x[0])
    m, ma, k, da = ung[0]
    # ghim dùng chung modem (không có modem riêng) không phải là một điểm để cài → không tính là "điểm khác sát bên"
    khac = [u for u in ung[1:] if not _chung(u[3]["diem"].get(u[2])) and not (_chung(da["diem"].get(k)) and u[1] == ma
                                                                               and str(_chung(da["diem"][k])["stt"]) == str(u[2]))]
    sat = bool(khac) and khac[0][0] - m < 150 and khac[0][0] <= 400
    return [ma, k, da["ten"], da["diem"][k]["ten"], int(m), sat]


def chay(ma, stt, may_ip, gw, log):
    log = _cb(log)
    C.LOG_CB, C.GW = log, gw or None
    if may_ip:
        os.environ["CAMLINK_MAY"] = may_ip
    da = _doc_du_an(ma)
    C.PHU_LY.clear()
    C.PHU_LY.update(da["diem"])
    C.NHAT_KY.clear()
    C.CAN_MAU.clear()
    log(f"Dự án: {da['ten']}")
    cd = C.cd_diem(da["diem"][stt], C.doc_cai_dat())      # user/pass nhập riêng cho điểm được ưu tiên hơn mặc định
    if da["diem"][stt].get("rieng"):
        log("Điểm này dùng user/pass RIÊNG do người dùng nhập (mặc định của hệ thống giữ nguyên).")
    cd0 = C.doc_cai_dat()
    C.CHUM["cam"], C.CHUM["modem"] = _chum_khoa(cd, cd0, "cam"), _chum_khoa(cd, cd0, "modem")
    do = [b for b in (da.get("ho_so", {}).get(stt, {}).get("bao_cao") or []) if not b.get("xong")]
    if do:      # Huan chốt 25/11: lần cài kế tiếp chỉ đi sửa việc CHƯA xong; việc đã xong kiểm nhanh thấy còn đúng thì giữ nguyên
        log(f"Lần trước còn dở {len(do)} việc: " + ", ".join(b.get("ngan") or b.get("viec", "") for b in do)
            + " → lần này chỉ xử lý các việc đó; việc đã xong giữ nguyên.")
    C.chay(stt, cd["cam_user"], cd["cam_pw"], cd.get("modem_user", "admin"), cd.get("modem_pw", "admin"))
    for loai, kd in list(C.KHOA_DUNG.items()):      # thiết bị vào được bằng khoá dự phòng → ghi nhớ RIÊNG cho điểm (mặc định giữ nguyên)
        r = da["diem"][stt].setdefault("rieng", {})
        r[loai + "_user"], r[loai + "_pw"] = kd[0], kd[1]
        log(f"✎ Điểm {stt}: {loai} vào được bằng mật khẩu mặc định của hệ thống (mật khẩu riêng của điểm không đúng) → đã sửa lại phần riêng của điểm (kiểm tra / sửa từ xa sau này dùng đúng mật khẩu đó).")
    if any("ĐẠT" in l for l in C.NHAT_KY):
        da.setdefault("da_xong", {})[stt] = time.strftime("%d/%m %H:%M")
    if C.KQ_CUOI.get("stt") == stt:   # hồ sơ điểm: để sau này kiểm tra / sửa từ xa
        k = C.KQ_CUOI
        da.setdefault("ho_so", {})[stt] = {"luc": time.strftime("%d/%m/%Y %H:%M"), "wan": k.get("wan", ""),
                                           "gw": k.get("gw", ""), "upnp": k.get("upnp"), "luat": k.get("luat", []),
                                           "web_modem": k.get("web_modem", 0), "viec_con": k.get("viec_con", []), "bao_cao": k.get("bao_cao", []),
                                           "cam": [{"so": c["so"], "ip": c["ip"], "mac": c.get("mac", ""),
                                                    "model": c.get("model", "")} for c in k.get("cam", [])]}
        # Số cam của điểm theo SỰ THẬT vừa đếm tại chỗ: file/ghim ghi ít hơn (vd "0 cam") thì nâng lên, để Giám sát / Kiểm tra từ xa
        # hiện đủ cam. Không tự GIẢM (cam có thể đang mất điện) — giảm thì người dùng sửa tay.
        x_d = da["diem"][stt]
        n_that = len(k.get("cam", []))
        if n_that > int(x_d.get("so") or 0):
            x_d.setdefault("goc", {"so": x_d.get("so"), "bs": x_d.get("bs")})
            cu_so = int(x_d.get("so") or 0)
            x_d["so"], x_d["so_thuc"] = n_that, n_that
            x_d.setdefault("hieu_chinh", []).append({"luc": time.strftime("%d/%m/%Y %H:%M"), "ly_do": "đếm thực tế lúc cài tại chỗ", "cu": cu_so, "moi": n_that})
            log(f"✎ Điểm {stt}: ghi nhận {n_that} cam thực tế (trước ghi {cu_so}) → Giám sát và Kiểm tra từ xa sẽ hiện đủ {n_that} cam.")
    _ghi_du_an(ma, da)
    try:   # ghi ngược tên miền + MAC về ghim LiteMark (lúc này đang trong WiFi modem: chỉ xếp hàng, gửi khi có 4G)
        import camlink_litemark as L
        if L.lien_ket(ma).get("id") and stt in da.get("ho_so", {}):
            cho = L._doc(f"gan_{ma}.json", {})
            x = da["diem"].get(str(stt), {})
            hs = da["ho_so"][stt]
            cho[str(x.get("lm_stt") or stt)] = {"domain": x.get("domain", ""), "mac": [c.get("mac", "") for c in hs.get("cam", []) if c.get("mac")],
                                                "ip": hs.get("wan", ""), "so_cam_thuc": len(hs.get("cam", [])),
                                                "luc": time.strftime("%Y-%m-%dT%H:%M:%S%z")[:-2] + ":" + time.strftime("%z")[-2:], "nguon": "camlink"}
            L._ghi(f"gan_{ma}.json", cho)
    except Exception as e:
        log(f"⚠ xếp hàng ghi ngược LiteMark: {e}")
    # đổi tên nhật ký cho có tên dự án, tránh lẫn giữa các dự án
    d = os.path.join(GOC, "ketqua")
    for f in sorted(os.listdir(d), key=lambda x: os.path.getmtime(os.path.join(d, x)), reverse=True)[:3]:
        if f.startswith(f"camlink_diem{stt}_") and f.endswith(".txt"):
            os.replace(os.path.join(d, f), os.path.join(d, f"camlink_{ma}_{f[len('camlink_'):]}"))
            break


def thu_mau(may_ip, gw, log):
    log = _cb(log)
    C.LOG_CB, C.GW = log, gw or None
    if may_ip:
        os.environ["CAMLINK_MAY"] = may_ip
    cd = C.doc_cai_dat()
    return C.thu(cd.get("cam_user", ""), cd.get("cam_pw", "")) or ""


def file_ket_qua_moi_nhat():
    d = os.path.join(GOC, "ketqua")
    fs = sorted((os.path.join(d, f) for f in os.listdir(d)), key=os.path.getmtime, reverse=True)
    out, co_txt, co_zip = [], False, False
    for f in fs:
        if f.endswith(".txt") and not co_txt:
            out.append(f); co_txt = True
        if f.endswith(".zip") and not co_zip and time.time() - os.path.getmtime(f) < 1800:
            out.append(f); co_zip = True
        if f.endswith(".jpg") and os.path.basename(f).startswith("anh_") and time.time() - os.path.getmtime(f) < 1800:
            out.append(f)
    return out


# ------------------------------------------------------------------ 1.2: kiểm tra từ xa + tóm tắt kết quả
def khoang_cach_den(ma, stt, lat, lng):
    """Mét từ vị trí hiện tại tới điểm; -1 nếu điểm không có toạ độ."""
    try:
        td = _doc_du_an(ma).get("toa_do", {}).get(stt)
    except (OSError, ValueError):
        td = None
    return int(C.khoang_cach((lat, lng), td)) if td else -1


def ten_diem(ma, stt):
    da = _doc_du_an(ma)
    d = da["diem"][stt]
    return f"[{da['ten']}] điểm {stt}: {d['ten']} ({d['so']} cam)"


def tom_tat():
    """Đọc nhật ký lượt vừa chạy → [trạng thái 'DAT'|'CHUA'|'LOI', nội dung ngắn]."""
    nk = C.NHAT_KY
    cam = [l for l in nk if re.match(r"^ Cam \d+:", l)]
    dat = [l for l in cam if "ĐẠT" in l]
    luat = next((l.strip() for l in nk if "luật" in l and ("Mở" in l or "UPnP" in l)), "")
    loi = [l.strip() for l in nk if l.strip().startswith("✖")]
    canh = [l.strip() for l in nk if l.strip().startswith("⚠") and "DDNS có thể mất" not in l]
    dong = []
    if cam:
        dong.append(f"Cam đạt: {len(dat)}/{len(cam)}")
    if luat:
        dong.append(luat.lstrip("✔⚠ "))
    dong += loi + canh
    if loi or not cam:
        tt = "LOI"
    elif len(dat) < len(cam) or canh:
        tt = "CHUA"
    else:
        tt = "DAT"
    return [tt, "\n".join(dong) or "Không có kết quả."]


def kiem_tra_tu_xa(ma, stt, log):
    """Chỉ ĐỌC qua Internet (tên miền + port), không thay đổi gì trên thiết bị."""
    import ipaddress, socket
    log = _cb(log)
    C.LOG_CB = log
    C.NHAT_KY.clear()
    global _TUXA
    _TUXA = (ma, stt)
    da = _doc_du_an(ma)
    d = da["diem"][stt]
    dom = d["domain"]
    C.log(f"KIỂM TRA TỪ XA — [{da['ten']}] điểm {stt}: {d['ten']}")
    C.log("Chỉ đọc qua Internet, không thay đổi gì trên cam hay modem.")
    if not dom:
        C.log("✖ Điểm này chưa có tên miền DDNS → chưa kiểm tra từ xa được. Nạp file tên miền hoặc nhập tên miền khi cài điểm.")
        return tom_tat_tu_xa(0, d["so"])
    try:
        ip = socket.gethostbyname(dom)
    except OSError:
        ip = None
    if not ip:
        C.log(f"✖ {dom} không phân giải được → tên miền chưa tạo / hết hạn No-IP, hoặc điện thoại chưa có Internet")
        return tom_tat_tu_xa(0, d["so"])
    a = ipaddress.ip_address(ip)
    if (a.is_private or a in ipaddress.ip_network("100.64.0.0/10")) and not os.environ.get("CAMLINK_THU_NOI_BO"):
        C.log(f"✖ {dom} đang trỏ IP nội bộ {ip} → DDNS trên cam 1 cập nhật sai")
        return tom_tat_tu_xa(0, d["so"])
    C.log(f"✔ {dom} → {ip}")
    cd = C.doc_cai_dat()
    tot = sai_pass = 0
    for i in range(d["so"]):
        http, rtsp = C.HTTP[i], C.RTSP[i]
        mh, mr = C.mo(dom, http, 4), C.mo(dom, rtsp, 4)
        ghi = ""
        if mh:
            ov = C.Onvif(dom, http, cd.get("cam_user", "admin"), cd.get("cam_pw", ""))
            if ov.co():
                try:
                    tt = ov.thong_tin()
                    ghi = f" — {tt['hang']} {tt['model']}".rstrip()
                except Exception:
                    ghi = " — port mở nhưng user/pass cam trong app SAI"
                    sai_pass += 1
        ok = mh and mr and "SAI" not in ghi
        tot += ok
        C.log(f" Cam {i + 1}: HTTP {http} {'mở' if mh else 'ĐÓNG'} · RTSP {rtsp} {'mở' if mr else 'ĐÓNG'}{ghi}  {'ĐẠT' if ok else 'CHƯA'}")
    if tot < d["so"]:
        C.log("⚠ Port ĐÓNG: modem chưa mở port đó, cam đổi IP, hoặc cam mất điện/mất mạng")
    if sai_pass:
        C.log("⚠ User/pass cam lưu trong app không đúng với cam → không chụp được ảnh; sửa ở nút \"User / pass cam và modem\"")
    return tom_tat_tu_xa(tot, d["so"])


_TUXA = ("du-an", "0")


def tom_tat_tu_xa(tot, so):
    try:
        f = os.path.join(GOC, "ketqua", f"camlink_{_TUXA[0]}_tuxa_diem{_TUXA[1]}_{time.strftime('%H%M')}.txt")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("\n".join(C.NHAT_KY))
    except OSError:
        pass
    loi = [l.strip() for l in C.NHAT_KY if l.strip().startswith(("✖", "⚠"))]
    tt = "DAT" if tot == so and so else ("LOI" if tot == 0 else "CHUA")
    return [tt, "\n".join([f"Cam xem được từ ngoài: {tot}/{so}"] + loi)]


# ------------------------------------------------------------------ 1.3: bằng chứng qua tên miền + dữ liệu sơ đồ
def _file_so_do(ma, stt):
    return os.path.join(GOC, "ketqua", f"sodo_{ma}_{stt}.json")


def bang_chung(ma, stt, log):
    """Gọi vào TÊN MIỀN:port như IOC: đăng nhập cam, chụp ảnh, lấy luồng RTSP.
    Kotlin chạy hàm này qua mạng di động (4G) để là kiểm tra từ ngoài thật."""
    import socket
    log = _cb(log)
    C.LOG_CB = log
    da = _doc_du_an(ma)
    try:   # đang ở 4G: gửi bù tên miền/MAC vừa cài về ghim LiteMark
        import camlink_litemark as L
        L.gui_bu_gan(ma, log)
    except Exception:
        pass
    d = da["diem"][stt]
    dom = d["domain"]
    cd = C.doc_cai_dat()
    kq = dict(C.KQ_CUOI) if C.KQ_CUOI.get("stt") == stt and C.KQ_CUOI.get("domain") == dom else {}
    kq.setdefault("domain", dom)
    kq.setdefault("ten", d["ten"])
    kq.setdefault("stt", stt)
    kq["du_an"] = da["ten"]
    if getattr(C, "LY_DO_0CAM", {}).get("stt") == stt:      # lượt cài vừa rồi không vào được cam nào → nói rõ vì sao
        kq["ly_do"] = C.LY_DO_0CAM.get("ly_do", [])
    kq.setdefault("cam", [{"so": i + 1, "ip": f"…{C.IP_TU + i}", "http": C.HTTP[i], "rtsp": C.RTSP[i],
                           "model": "", "mac": "", "ok": None, "ghi": ""} for i in range(d["so"])])
    C.log("")
    C.log(f"BẰNG CHỨNG TỪ NGOÀI — gọi {dom} như IOC")
    try:
        ip = socket.gethostbyname(dom)
    except OSError:
        ip = ""
    # Tên miền phải trỏ ĐÚNG IP công cộng của điểm thì mới xem được từ ngoài. Vừa nhập DDNS xong, cam cần 1–5 phút báo IP lên No-IP
    # → chờ và kiểm lại, không kết luận vội "modem chặn" khi tên miền còn trỏ IP cũ.
    wan = str(kq.get("wan") or "")
    chua_tro = False
    if dom and wan and re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", wan) and ip != wan:
        C.log(f"   {dom} đang trỏ {ip or '(chưa có IP)'}, IP của điểm là {wan} → chờ cam báo IP lên No-IP (tối đa 3 phút) …")
        het = time.time() + 180
        while time.time() < het and ip != wan:
            time.sleep(15)
            try:
                ip = socket.gethostbyname(dom)
            except OSError:
                ip = ""
            C.log(f"   chờ tên miền cập nhật: {dom} → {ip or '(chưa có IP)'} (cần {wan}, còn {max(0, int(het - time.time()))} giây)")
        chua_tro = ip != wan
        if chua_tro:
            C.log(f"   ✖ Sau 3 phút {dom} vẫn trỏ {ip or '(chưa có IP)'}, chưa về IP của điểm {wan} → DDNS trên cam chưa cập nhật được")
        else:
            C.log(f"   ✔ {dom} đã trỏ đúng IP của điểm {wan}")
    kq["ip_ten_mien"] = ip
    kq["ten_mien_chua_tro"] = chua_tro
    C.log(f"   {dom} → {ip or 'không phân giải được'}")
    anh_dir = os.path.join(GOC, "ketqua")
    for c in kq["cam"]:
        c["ngoai"] = False
        c["anh"] = ""
        c["live"] = ""
        c["loi_ngoai"] = ""
        if not ip:
            c["loi_ngoai"] = "tên miền không phân giải được"
            continue
        if chua_tro:
            c["loi_ngoai"] = (f"tên miền đang trỏ IP cũ {ip}, chưa về IP của điểm {wan} → KHÔNG phải do modem chặn. DDNS trên cam chưa báo được lên No-IP: "
                              "chờ thêm 5–10 phút rồi bấm Kiểm tra từ xa; vẫn vậy thì user/pass No-IP của tên miền này sai hoặc tên miền bị khoá")
            C.log(f"   ✖ Cam {c['so']}: {c['loi_ngoai']}")
            continue
        ov = C.Onvif(dom, c["http"], cd.get("cam_user", "admin"), cd.get("cam_pw", ""))
        try:
            if not ov.co():
                raise RuntimeError(f"không vào được {dom}:{c['http']} (port chưa mở / modem chặn)")
            tt = ov.thong_tin()
            c["model"] = c.get("model") or tt.get("model", "")
            c["hang"] = tt.get("hang", "")
            um = ov.url_media()
            tk = ov.profile_dau(um)
            try:
                jpg = ov.anh_chup(um, tk)
                f = os.path.join(anh_dir, f"anh_{ma}_{stt}_cam{c['so']}.jpg")
                with open(f, "wb") as fh:
                    fh.write(jpg)
                c["anh"] = f
            except Exception as e:
                c["loi_ngoai"] = f"không lấy được ảnh: {e}"
            try:
                c["live"] = ov.luong_video(um, tk, c["rtsp"])
            except Exception as e:
                c["loi_ngoai"] = (c["loi_ngoai"] + "; " if c["loi_ngoai"] else "") + f"không lấy được RTSP: {e}"
            c["ngoai"] = bool(c["anh"]) or (bool(c["live"]) and C.mo(dom, c["rtsp"], 4))
            C.log(f"   {'✔' if c['ngoai'] else '⚠'} Cam {c['so']} qua {dom}:{c['http']}"
                  + (" — có ảnh chụp" if c["anh"] else "") + (f" — {c['loi_ngoai']}" if c["loi_ngoai"] else ""))
        except Exception as e:
            m = str(e)
            if "not authorized" in m.lower() or "401" in m or "NotAuthorized" in m:
                m = "port vẫn mở nhưng user/pass cam trong app SAI → sửa ở nút User / pass"
            c["loi_ngoai"] = m[:160]
            C.log(f"   ✖ Cam {c['so']}: {c['loi_ngoai']}")
    kq["luc"] = time.strftime("%d/%m/%Y %H:%M")
    with open(_file_so_do(ma, stt), "w", encoding="utf-8") as fh:
        json.dump(kq, fh, ensure_ascii=False)
    n = sum(1 for c in kq["cam"] if c["ngoai"])
    C.log(f"   → Xem được từ ngoài: {n}/{len(kq['cam'])} cam")
    ho_so_tu_dong(ma)      # cam lên → hồ sơ nghiệm thu tự cập nhật
    return json.dumps(kq, ensure_ascii=False)


def so_do_gan_nhat():
    d = os.path.join(GOC, "ketqua")
    fs = sorted((os.path.join(d, f) for f in os.listdir(d) if f.startswith("sodo_")), key=os.path.getmtime, reverse=True)
    if not fs:
        return ""
    with open(fs[0], encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------ 1.5: kiểm tra từ xa cả dự án + sửa từ xa
def ds_du_an():
    # gộp các dự án trùng do tải file nhiều lần ("ten (1)") — giữ bản cập nhật gần nhất
    nhom = {}
    for ma, da in _cac_du_an().items():
        nhom.setdefault(_ma(_ten_tu_file(da.get("ten", "") + ".xlsx")), []).append(ma)
    for goc_ma, ds in nhom.items():
        ds.sort(key=lambda m: os.path.getmtime(os.path.join(_thu_muc_du_an(), m + ".json")), reverse=True)
        moi = ds[0]
        for cu in ds[1:]:
            os.replace(os.path.join(_thu_muc_du_an(), cu + ".json"), os.path.join(_thu_muc_du_an(), cu + ".json.cu"))
        if moi != goc_ma:
            da = _doc_du_an(moi)
            da["ten"] = _ten_tu_file(da["ten"] + ".xlsx")
            _ghi_du_an(goc_ma, da)
            os.replace(os.path.join(_thu_muc_du_an(), moi + ".json"), os.path.join(_thu_muc_du_an(), moi + ".json.cu"))
    return [[ma, da["ten"], str(len(da["diem"])), str(sum(int(v.get("so") or 0) for v in da["diem"].values()))]
            for ma, da in _cac_du_an().items()]


def tuxa_kiem(ma, log, nhanh=True):
    """nhanh=True: điểm lần trước toàn ĐẠT lấy lại từ lịch sử (live xác minh), chỉ quét lại điểm có sự cố. nhanh=False: quét hết."""
    import camlink_tuxa as T
    log = _cb(log)
    da = _doc_du_an(ma)
    kq = T.kiem_du_an(GOC, da, ma, C.doc_cai_dat(), log, nhanh=bool(nhanh))
    # tự ghi hiệu chỉnh vào hồ sơ dự án (giữ giá trị gốc của file để đối chiếu)
    doi = False
    for h in kq.get("hieu_chinh", []):
        d = da["diem"].get(h["stt"])
        if d and (d.get("so") != h["moi"] or d.get("bs") != h["bs_moi"]):
            d.setdefault("goc", {"so": d.get("so"), "bs": d.get("bs")})
            d["so"], d["bs"], d["so_thuc"] = h["moi"], h["bs_moi"], h["moi"]
            d.setdefault("hieu_chinh", []).append({"luc": kq["luc"], "ly_do": h["ly_do"], "cu": h["cu"], "moi": h["moi"]})
            doi = True
            log(f"✎ Đã tự hiệu chỉnh điểm {h['stt']}: {h['cu']} → {h['moi']} cam ({h['ly_do'][:80]})")
    if doi:
        _ghi_du_an(ma, da)
    import camlink_litemark as L
    # nhận diện điểm theo MAC → IP → tên miền (tên miền chỉ là nhãn), rồi ghi dấu vết lần này
    try:
        L.doi_chieu_vet(da, kq, log)
        L.cap_nhat_vet(da, kq)
        _ghi_du_an(ma, da)
    except Exception as e:
        log(f"⚠ dấu vết điểm: {e}")
    lk = L.lien_ket(ma)
    if lk.get("id"):
        try:
            L.gui_bu_gan(ma, log)
        except Exception:
            pass
        kq["litemark"] = {"id": lk["id"], "ten": lk.get("ten", "")}
        for p in kq.get("diem", []):
            d = da["diem"].get(p["stt"], {})
            p["lm_link"] = L.link_diem(ma, p["stt"], da)
            p["lm_stt"], p["lm_chac"], p["lm_anh"], p["lm_kc"] = d.get("lm_stt", ""), d.get("lm_chac", True), d.get("lm_anh", ""), d.get("lm_kc", 0)
            p["lm_ghim"] = [[g, v.get("ten", "")] for g, v in sorted(da.get("litemark", {}).get("ghim", {}).items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0)]
        try:
            kq["litemark"]["da_gui"] = L.goi_canh_bao(ma, kq, PHIEN_BAN_LOI, log, da)
        except Exception as e:
            log(f"⚠ LiteMark: {e}")
    ho_so_tu_dong(ma)      # sau mỗi lượt kiểm tra từ xa: hồ sơ nghiệm thu tự cập nhật (người dùng không phải bấm tạo)
    return json.dumps(kq, ensure_ascii=False)


# ---------------- LiteMark ----------------
def lm_trang_thai(ma):
    """[có khoá?, tên công trình đã nối, lúc đồng bộ ghim, số ghim, ghi chú đối chiếu]"""
    import camlink_litemark as L
    lk = L.lien_ket(ma) if ma else {}
    da = _doc_du_an(ma) if ma else {}
    lm = da.get("litemark", {}) if da else {}
    return json.dumps({"co_khoa": bool(L.khoa()), "ten": lk.get("ten", ""), "id": lk.get("id", ""),
                       "luc_dong_bo": lm.get("luc_dong_bo", ""), "so_ghim": lm.get("so_ghim", 0),
                       "ghi_chu": lm.get("ghi_chu", []), "may_chu": L.MAY_CHU}, ensure_ascii=False)


def lm_luu_khoa(k):
    import camlink_litemark as L
    return L.luu_khoa(k)


def lm_xoa_khoa():
    import camlink_litemark as L
    L.xoa_khoa()


def lm_ds_cong_trinh(ma):
    """Danh sách công trình LiteMark, gợi ý khớp dự án `ma` lên đầu (JSON)."""
    import camlink_litemark as L
    ds = L.ds_cong_trinh()
    da = _doc_du_an(ma) if ma else {}
    return json.dumps(L.goi_y(da.get("ten", ""), len(da.get("diem", {})), ds) if da else ds, ensure_ascii=False)


def lm_noi(ma, id_ct, ten_ct, log):
    """Nối dự án với công trình LiteMark rồi đồng bộ ghim ngay."""
    import camlink_litemark as L
    log = _cb(log)
    L.noi(ma, {"id": id_ct, "ten": ten_ct})
    return lm_dong_bo(ma, log)


def lm_dong_bo(ma, log):
    import camlink_litemark as L
    log = _cb(log)
    da = _doc_du_an(ma)
    da, ghi_chu = L.dong_bo_ghim(ma, da, log)
    _ghi_du_an(ma, da)
    L.gui_bu(ma, log)
    return json.dumps({"ok": True, "ten": da["litemark"]["ten"], "so_ghim": da["litemark"]["so_ghim"], "ghi_chu": ghi_chu,
                       "bang_ghep": da["litemark"].get("bang_ghep", [])}, ensure_ascii=False)


def lm_xac_minh(ma):
    """Dữ liệu màn Xác minh vị trí: ảnh cam vừa chụp + ghim ứng viên kèm ảnh khảo sát (JSON)."""
    import camlink_litemark as L
    kq = None
    try:
        kq = json.loads(tuxa_gan_nhat(ma) or "null")
    except ValueError:
        pass
    return json.dumps(L.xac_minh(ma, _doc_du_an(ma), kq), ensure_ascii=False)


def lm_dung_tai_day(ma, stt, lat, lng, log):
    import camlink_litemark as L
    da = _doc_du_an(ma)
    g, kc = L.dung_tai_day(ma, da, stt, float(lat), float(lng))
    _ghi_du_an(ma, da)
    r = json.loads(lm_dong_bo(ma, log))
    r["ghim"], r["kc"] = g, kc
    return json.dumps(r, ensure_ascii=False)


def lm_thu_canh_bao(ma, stt, bat, log):
    import camlink_litemark as L
    return L.thu_canh_bao(ma, _doc_du_an(ma), stt, bool(bat), PHIEN_BAN_LOI, _cb(log))


def lm_ds_diem(ma):
    da = _doc_du_an(ma)
    return json.dumps([[s, d.get("ten", ""), d.get("domain", ""), str(d.get("lm_stt", ""))] for s, d in sorted(da["diem"].items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0)], ensure_ascii=False)


# ---- dự án tạo từ LiteMark ----
def lm_cho_nhan():
    """Công trình LiteMark đã 'Chuyển sang CamLink' mà máy này chưa nhận (JSON)."""
    import camlink_litemark as L
    if not L.khoa():
        return "[]"
    return json.dumps(L.ds_cho_nhan(list(_cac_du_an().keys())), ensure_ascii=False)


def lm_nhan_du_an(id_ct, ten_ct, log):
    """Tạo dự án từ công trình LiteMark; đã nhận rồi thì trả dự án cũ (không tạo trùng). Trả mã dự án."""
    import camlink_litemark as L
    log = _cb(log)
    cu = L.ma_da_noi_voi(id_ct, list(_cac_du_an().keys()))
    if cu:
        log(f"Công trình này đã có trong CamLink: {_doc_du_an(cu)['ten']}")
        return cu
    da = L.tao_du_an_tu_lm(id_ct, ten_ct, log)
    ma = _ma(da["ten"])
    while os.path.exists(os.path.join(_thu_muc_du_an(), ma + ".json")):
        ma += "-lm"
    _ghi_du_an(ma, da)
    L.noi(ma, {"id": id_ct, "ten": da["ten"]})
    for c in _diem_trung_vi_tri(ma, da["toa_do"]):
        log("⚠ " + c)
    return ma


def lm_nap_ddns(ma, duong_dan, log):
    """Nạp file tên miền của bên cấp vào dự án (tạo từ LiteMark), ghép theo toạ độ. Trả báo cáo ghép (JSON)."""
    import camlink_litemark as L
    log = _cb(log)
    C.LOG_CB = log
    da = _doc_du_an(ma)
    dong = L.doc_file_ddns(duong_dan, C.toa_do_tu_link, log)
    da, bc = L.ghep_ddns(da, dong, log)
    _ghi_du_an(ma, da)
    return json.dumps(bc, ensure_ascii=False)


def can_chon_ten_mien(ma, stt):
    """Điểm chưa có tên miền mà dự án có kho tên miền → app phải cho chọn trước khi cài."""
    da = _doc_du_an(ma)
    if _dong_bo_kho(da):
        _ghi_du_an(ma, da)
    return (not da["diem"][str(stt)].get("domain")) and bool(da.get("kho_ddns"))


def _dong_bo_kho(da):
    """Dấu "đã dùng" của từng tên miền trong kho phải theo SỰ THẬT: điểm nào đang mang tên miền đó.
    (Dấu cũ có thể sót lại sau khi đổi / nhập tay / lấy theo cam → kho báo "dùng hết" trong khi vẫn còn tên miền trống.)
    Trả True nếu có sửa."""
    giu = {str(d.get("domain") or "").lower(): s for s, d in da["diem"].items() if d.get("domain")}
    doi = False
    for k in da.get("kho_ddns", []):
        dung = giu.get(str(k.get("domain") or "").lower(), "")
        if str(k.get("dung") or "") != dung:
            k["dung"] = dung
            doi = True
    return doi


def ung_vien_ten_mien(ma, stt):
    import camlink_litemark as L
    da = _doc_du_an(ma)
    if _dong_bo_kho(da):
        _ghi_du_an(ma, da)
    return json.dumps(L.ung_vien_ten_mien(da, stt), ensure_ascii=False)


def tat_ca_ten_mien(ma, stt):
    """MỌI tên miền trong kho của dự án, kể cả đã dùng: tên miền nào đang ở điểm nào (để người dùng tự chọn / chuyển, không bị kẹt)."""
    da = _doc_du_an(ma)
    if _dong_bo_kho(da):
        _ghi_du_an(ma, da)
    out = []
    for i, k in enumerate(da.get("kho_ddns", [])):
        giu = str(k.get("dung") or "")
        da_cai = ""
        if giu and giu != str(stt):
            try:
                da_cai = diem_da_cai(da, giu) or ""
            except Exception:
                da_cai = ""
        out.append({"i": i, "domain": k.get("domain", ""), "giu": giu, "ten_giu": (da["diem"].get(giu) or {}).get("ten", "") if giu else "",
                    "da_cai": bool(da_cai), "co_pass": bool(k.get("u") and k.get("p"))})
    return json.dumps(out, ensure_ascii=False)


def chuyen_ten_mien(ma, stt, i):
    """Người dùng chọn một tên miền trong kho cho điểm này, kể cả khi đang gán cho điểm khác (điểm kia sẽ thành 'chưa có tên miền').
    Trả tên miền."""
    import camlink_litemark as L
    da = _doc_du_an(ma)
    _dong_bo_kho(da)
    k = da["kho_ddns"][int(i)]
    giu = str(k.get("dung") or "")
    if giu and giu != str(stt):
        x = da["diem"][giu]
        x.update(domain="", u="", p="", dom_nguon=f"tên miền {k.get('domain')} đã chuyển sang điểm {stt} lúc {time.strftime('%d/%m %H:%M')}")
        k["dung"] = ""
    dom = L.gan_ten_mien(da, stt, int(i), "người dùng chọn")
    _ghi_du_an(ma, da)
    return dom


def gan_ten_mien(ma, stt, i):
    import camlink_litemark as L
    da = _doc_du_an(ma)
    d = L.gan_ten_mien(da, stt, i)
    _ghi_du_an(ma, da)
    return d


def lm_dat_ghim(ma, stt, lm_stt, log):
    """Người dùng chốt điểm CamLink `stt` = ghim LiteMark `lm_stt`, rồi đồng bộ lại."""
    import camlink_litemark as L
    da = L.dat_ghim_tay(ma, _doc_du_an(ma), str(stt), str(lm_stt))
    _ghi_du_an(ma, da)
    return lm_dong_bo(ma, log)


def lm_ngat(ma):
    import camlink_litemark as L
    L.ngat(ma)
    da = _doc_du_an(ma)
    if da.get("toa_do_goc"):
        da["toa_do"] = da.pop("toa_do_goc")
    da.pop("litemark", None)
    _ghi_du_an(ma, da)


def tuxa_khao_sat(ma, json_kq):
    import camlink_tuxa as T
    return T.xuat_khao_sat_hieu_chinh(GOC, _doc_du_an(ma), json.loads(json_kq))


def tuxa_kiem_diem(ma, stt, log):
    import camlink_tuxa as T
    log = _cb(log)
    kq = T.kiem_du_an(GOC, _doc_du_an(ma), ma, C.doc_cai_dat(), log, chi_diem=[stt], tu_sua=False)
    p = kq["diem"][0]
    # cập nhật điểm này vào lịch sử để lần kiểm nhanh sau không lấy lại kết quả cũ sai
    try:
        f = T._f_lich_su(GOC, ma)
        with open(f, encoding="utf-8") as fh:
            ls = json.load(fh)
        ls["diem"] = [p if x["stt"] == p["stt"] else x for x in ls.get("diem", [])]
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(ls, fh, ensure_ascii=False)
    except (OSError, ValueError, KeyError):
        pass
    ho_so_tu_dong(ma)
    return json.dumps(p, ensure_ascii=False)


def tuxa_gan_nhat(ma):
    import camlink_tuxa as T
    try:
        with open(T._f_lich_su(GOC, ma), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def tuxa_sua(ma, stt, so, viec, log):
    import camlink_tuxa as T
    log = _cb(log)
    da_ = _doc_du_an(ma)
    d = dict(da_["diem"][stt])
    d["_hs"] = (da_.get("ho_so") or {}).get(stt) or {}      # hồ sơ lúc cài: port quản trị modem, IP trong của cam
    if viec == "nhap_lai_ddns":      # lần kiểm gần nhất thấy điểm sống qua IP dự phòng → vào cam bằng IP đó
        try:
            with open(T._f_lich_su(GOC, ma), encoding="utf-8") as fh:
                pp = next((x for x in json.load(fh).get("diem", []) if str(x.get("stt")) == str(stt)), {})
            if pp.get("du_phong"):
                d["_host"] = pp["du_phong"]["ip"]
                log(f"Tên miền đang hỏng → vào cam qua IP dự phòng {d['_host']}")
        except (OSError, ValueError):
            pass
    ok, tb = T.sua(d, int(so), viec, C.doc_cai_dat(), log)
    return ["OK" if ok else "KHONG", tb]


def tuxa_excel(json_kq):
    import camlink_tuxa as T
    return T.xuat_excel(GOC, json.loads(json_kq))


def ten_sua(viec):
    import camlink_tuxa as T
    return T.TEN_SUA.get(viec, viec)


def sua_so_cam(ma, stt, n):
    da = _doc_du_an(ma)
    da["diem"][stt]["so_thuc"] = int(n)
    _ghi_du_an(ma, da)
    return f"Điểm {stt}: đã ghi {n} cam thực tế"


def tuxa_sua_tat_ca(ma, json_kq, log):
    import camlink_tuxa as T
    log = _cb(log)
    kq = T.sua_tat_ca(GOC, _doc_du_an(ma), ma, json.loads(json_kq), C.doc_cai_dat(), log)
    return json.dumps(kq, ensure_ascii=False)


def tuxa_sua_diem(ma, json_kq, stt, log):
    """Sửa từ xa ĐÚNG MỘT điểm (bấm 'điểm lỗi' ở Trang chủ → vào thẳng điểm → tự sửa). Báo cáo như 'Sửa tất cả'."""
    import camlink_tuxa as T
    log = _cb(log)
    kq = T.sua_tat_ca(GOC, _doc_du_an(ma), ma, json.loads(json_kq), C.doc_cai_dat(), log, chi_diem=[str(stt)])
    return json.dumps(kq, ensure_ascii=False)


# ------------------------------------------------------------------ 2.12.20: HỒ SƠ NGHIỆM THU tự động (camlink_hoso.py)
def ho_so_tao(ma):
    import camlink_hoso as H
    return H.tao(GOC, ma)


def ho_so_tu_dong(ma):
    """Lõi tự gọi sau lượt kiểm tra từ xa / sau bằng chứng lúc cài. KHÔNG BAO GIỜ ném lỗi ra ngoài (không được làm hỏng lượt kiểm)."""
    try:
        da = _doc_du_an(ma)
        if not any(diem_da_cai(da, k, _lich_su_kiem(ma)) for k in da.get("diem", {})):
            return ""      # dự án chưa cài cam nào: chưa có gì để nghiệm thu
        return ho_so_tao(ma)
    except Exception:
        return ""


def ho_so_ds():
    """Mục 'Hồ sơ nghiệm thu': mỗi dự án ĐÃ CÀI cam một dòng {ma, ten, cam, dat, chua, luc, tep}. Thiếu file thì tự tạo."""
    import camlink_hoso as H
    out = []
    for r in ds_du_an_kiem():
        ma = str(r[0])
        try:
            m = H.du_lieu(GOC, ma)
            f = H.tep(GOC, ma)
            if not os.path.exists(f):
                f = H.ve_pdf(m, f)
            out.append({"ma": ma, "ten": m["du_an"], "cam": m["tong"]["cam"], "dat": m["tong"]["dat"], "chua": m["tong"]["chua"],
                        "luc": time.strftime("%H:%M %d/%m/%Y", time.localtime(os.path.getmtime(f))), "tep": f})
        except Exception as e:
            out.append({"ma": ma, "ten": str(r[1]), "cam": 0, "dat": 0, "chua": 0, "luc": "", "tep": "", "loi": str(e)[:120]})
    return json.dumps(out, ensure_ascii=False)


def diem_loi_tat_ca():
    """Các ĐIỂM đang lỗi theo kết quả kiểm gần nhất đã lưu của mọi dự án (không chạm mạng) — đỏ trước, vàng sau.
    JSON [{ma, du_an, stt, ten, muc, tong, luc}]. Số phần tử khớp con số 'điểm lỗi' ở Trang chủ."""
    import camlink_tuxa as T
    out = []
    for r in ds_du_an():
        ma, ten = str(r[0]), str(r[1])
        try:
            with open(T._f_lich_su(GOC, ma), encoding="utf-8") as fh:
                kq = json.load(fh)
        except (OSError, ValueError):
            continue
        for p in kq.get("diem") or []:
            if p.get("muc") != "xanh":
                out.append({"ma": ma, "du_an": ten, "stt": str(p.get("stt")), "ten": p.get("ten", ""), "muc": p.get("muc", ""),
                            "tong": p.get("tong", ""), "luc": str(kq.get("luc", ""))})
    out.sort(key=lambda x: 0 if x["muc"] == "do" else 1)
    return json.dumps(out, ensure_ascii=False)


def ds_du_an_kiem():
    """Dự án để KIỂM TRA TỪ XA: chỉ dự án đã có ít nhất một điểm cài cam. Dự án chưa cài cam nào thì không có gì để kiểm."""
    out = []
    for r in ds_du_an():
        da = _doc_du_an(str(r[0]))
        ls = _lich_su_kiem(str(r[0]))
        if any(diem_da_cai(da, k, ls) for k in da.get("diem", {})):
            out.append(r)
    return out


def tuxa_ban_do(json_kq):
    import camlink_tuxa as T
    return T.ban_do_html(json.loads(json_kq), GOC)


def tuxa_phieu(ma, json_kq, stt):
    import camlink_tuxa as T
    kq = json.loads(json_kq)
    p = next(x for x in kq["diem"] if x["stt"] == stt)
    return T.phieu_bao_mang(kq, p, (_doc_du_an(ma).get("ho_so") or {}).get(stt))


# ------------------------------------------------------------------ cập nhật đè phần logic (không cần cài lại APK)
TEP_LOI = {"camlink_phien_ban.py", "camlink_core.py", "camlink_dt.py", "camlink_tuxa.py", "camlink_oryza.py", "camlink_litemark.py"}


def phien_ban_loi():
    return PHIEN_BAN_LOI


def nap_cap_nhat_zip(duong_zip):
    """Nạp gói cập nhật: .zip HOẶC gói một tệp .camlink (JSON, không bị điện thoại tự giải nén) → áp dụng khi mở lại app."""
    import base64, hashlib, zipfile

    def _moi_hon(pb):
        a = [int(x) for x in re.findall(r"\d+", str(pb))]
        b = [int(x) for x in re.findall(r"\d+", PHIEN_BAN_LOI)]
        if a <= b:
            raise RuntimeError(f"Gói này là lõi {pb}, app đang chạy lõi {PHIEN_BAN_LOI} (bằng hoặc mới hơn) → không cần nạp.")
    th = os.path.join(GOC, "capnhat")
    os.makedirs(th, exist_ok=True)
    with open(duong_zip, "rb") as fh:
        dau = fh.read(4)
    if dau[:1] == b"{":   # gói một tệp .camlink
        with open(duong_zip, encoding="utf-8") as fh:
            goi = json.load(fh)
        if goi.get("loai") != "camlink-loi":
            raise RuntimeError("Đây không phải gói cập nhật CamLink")
        _moi_hon(goi.get("phien_ban", "0"))
        for f, nd in goi["tep"].items():
            if f not in TEP_LOI:
                raise RuntimeError(f"Gói chứa tệp lạ: {f}")
            d = base64.b64decode(nd["b64"])
            if hashlib.sha256(d).hexdigest() != nd["sha256"]:
                raise RuntimeError(f"Tệp {f} sai chữ ký — gói hỏng")
            with open(os.path.join(th, f), "wb") as fh:
                fh.write(d)
        with open(os.path.join(th, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"phien_ban": goi["phien_ban"], "tep": {f: nd["sha256"] for f, nd in goi["tep"].items()}}, fh)
        return f"Đã nạp lõi {goi['phien_ban']} ({len(goi['tep'])} tệp). Mở lại app để dùng."
    if dau[:2] != b"PK":
        ten = os.path.basename(duong_zip)
        raise RuntimeError("Tệp đã chọn không phải gói cập nhật (có thể điện thoại đã tự giải nén và bạn chọn nhầm tệp bên trong). "
                           "Hãy chọn đúng tệp CamLink-loi-x.y.z.camlink hoặc .zip còn nguyên.")
    with zipfile.ZipFile(duong_zip) as z:
        ten = z.namelist()
        if "manifest.json" not in ten:
            raise RuntimeError("Gói không có manifest.json")
        mf = json.loads(z.read("manifest.json").decode("utf-8"))
        _moi_hon(mf.get("phien_ban", "0"))
        for f, sha in mf["tep"].items():
            if f not in TEP_LOI:
                raise RuntimeError(f"Gói chứa tệp lạ: {f}")
            d = z.read(f)
            if hashlib.sha256(d).hexdigest() != sha:
                raise RuntimeError(f"Tệp {f} sai chữ ký — gói hỏng")
        for f in mf["tep"]:
            with open(os.path.join(th, f), "wb") as fh:
                fh.write(z.read(f))
        with open(os.path.join(th, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump(mf, fh, ensure_ascii=False)
    return f"Đã nạp lõi {mf.get('phien_ban')} ({len(mf['tep'])} tệp, {sum(os.path.getsize(os.path.join(th, f)) for f in mf['tep']) // 1024} KB). Mở lại app để dùng."


def kiem_cap_nhat(url_goc, phien_ban_apk_code):
    """Hỏi kênh cập nhật: có lõi mới (tải vài trăm KB) hay APK mới (chỉ khi phần Android đổi)."""
    import hashlib
    import requests
    url_goc = KENH_CAP_NHAT or url_goc
    try:
        r = requests.get(url_goc.rstrip("/") + "/phien_ban.json", timeout=15, headers={"Accept": "application/json"})
        r.raise_for_status()
        pb = r.json()
    except Exception as e:
        return json.dumps({"loi_moi": None, "apk_moi": None,
                           "ghi_chu": f"Kênh cập nhật tự động chưa mở được ({type(e).__name__}). Đang chạy lõi {PHIEN_BAN_LOI} — là bản mới nhất đã cài. "
                                      "Khi Claude gửi gói .zip, dùng 'Từ file .zip'."}, ensure_ascii=False)
    kq = {"loi_moi": None, "apk_moi": None}
    if pb.get("loi") and pb["loi"] != PHIEN_BAN_LOI:
        th = os.path.join(GOC, "capnhat")
        os.makedirs(th, exist_ok=True)
        for f, sha in pb["tep"].items():
            if f not in TEP_LOI:
                continue
            duong = (pb.get("url_tep") or {}).get(f, "py/" + f)
            d = requests.get(duong if duong.startswith("http") else url_goc.rstrip("/") + "/" + duong, timeout=30).content
            if hashlib.sha256(d).hexdigest() != sha:
                raise RuntimeError(f"{f} tải về sai chữ ký")
            with open(os.path.join(th, f), "wb") as fh:
                fh.write(d)
        with open(os.path.join(th, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"phien_ban": pb["loi"], "tep": pb["tep"]}, fh)
        kq["loi_moi"] = pb["loi"]
    if int(pb.get("apk_code") or 0) > int(phien_ban_apk_code):
        kq["apk_moi"] = {"ten": pb.get("apk_ten"), "url": pb.get("apk_url"), "mb": pb.get("apk_mb"), "ly_do": pb.get("apk_ly_do", "")}
    return json.dumps(kq, ensure_ascii=False)


def tuxa_hanh_dong(ma, stt, so, http, id_hd, json_kq, log):
    """Hành động do lõi định nghĩa (nút sinh từ JSON) → trả kết quả điểm đã kiểm lại."""
    import camlink_tuxa as T
    log = _cb(log)
    da = _doc_du_an(ma)
    d = da["diem"][stt]
    if id_hd == "khong_co_cam":
        so_quet = 0
        try:
            kq = json.loads(json_kq)
            so_quet = next((p.get("so_quet", 0) for p in kq["diem"] if p["stt"] == stt), 0)
        except Exception:
            pass
        moi = max(1, so_quet or (int(d.get("so") or 1) - 1))
        d.setdefault("goc", {"so": d.get("so"), "bs": d.get("bs")})
        d["so_thuc"] = moi
        d["so"] = moi
        if int(d.get("bs") or 0) > moi:
            d["bs"] = moi
        d.setdefault("hieu_chinh", []).append({"luc": time.strftime("%d/%m/%Y %H:%M"), "cu": d["goc"]["so"], "moi": moi,
                                               "ly_do": f"Người dùng xác nhận tại chỗ: không có cam {so} (port {http})"})
        log(f"✎ Điểm {stt}: xác nhận không có cam {so} → hồ sơ {moi} cam")
    elif id_hd == "cam_co_that":
        d.setdefault("cam_that", [])
        if int(http) not in d["cam_that"]:
            d["cam_that"].append(int(http))
        log(f"✎ Điểm {stt}: xác nhận cam {so} (port {http}) có thật — từ nay báo là cam hỏng, không nghi file")
    _ghi_du_an(ma, da)
    kq = T.kiem_du_an(GOC, _doc_du_an(ma), ma, C.doc_cai_dat(), log, chi_diem=[stt], tu_sua=False)
    return json.dumps(kq["diem"][0], ensure_ascii=False)


# ---------------- THEO DÕI ỔN ĐỊNH MỘT CAM ----------------
def theodoi_bat(ma, json_p, so, phut, ten_du_an=""):
    """Bật theo dõi cam `so` của điểm (lấy từ kết quả kiểm tra từ xa) trong `phut` phút. Trả id."""
    import camlink_theodoi as TD
    p = json.loads(json_p)
    if ten_du_an:
        p["du_an"] = ten_du_an
    return TD.bat(ma, p, int(so), float(phut), C.doc_cai_dat())


def theodoi_bat_diem(ma, json_p, phut, ten_du_an=""):
    """Theo dõi CẢ ĐIỂM (mọi cam, chung một lượt đo, chung một báo cáo). Trả mã nhóm."""
    import camlink_theodoi as TD
    p = json.loads(json_p)
    if ten_du_an:
        p["du_an"] = ten_du_an
    return TD.bat_diem(ma, p, float(phut), C.doc_cai_dat())


def theodoi_vong(loai_mang=""):
    """Gọi mỗi 10 giây từ dịch vụ chạy nền. JSON {dang:[…], xong_moi:[id], pdf_moi:[đường dẫn], bao:[tin báo ngay]}."""
    import camlink_theodoi as TD
    return json.dumps(TD.vong(loai_mang or ""), ensure_ascii=False)


def theodoi_ds():
    import camlink_theodoi as TD
    return json.dumps(TD.ds_hien(), ensure_ascii=False)


def _theodoi_bao_lm(b):
    """Theo dõi: cam rớt ≥ 5 phút / lên lại → sửa đúng cam đó trong kết quả kiểm gần nhất rồi đẩy lên ghim LiteMark
    (gửi cả ảnh chụp toàn dự án như mọi lần kiểm, nên điểm khác không bị mất cảnh báo). Chưa nối LiteMark thì thôi."""
    import camlink_tuxa as T
    import camlink_litemark as L
    ma = b.get("ma", "")
    if not ma or not L.lien_ket(ma).get("id"):
        return False
    f = T._f_lich_su(GOC, ma)
    try:
        with open(f, encoding="utf-8") as fh:
            kq = json.load(fh)
    except (OSError, ValueError):
        return False
    p = next((x for x in kq.get("diem", []) if str(x.get("stt")) == str(b.get("stt"))), None)
    if not p:
        return False
    c = next((x for x in p.get("cam", []) if int(x.get("http") or 0) == int(b.get("http") or 0)), None)
    if not c:
        return False
    if b["kieu"] == "rot":
        c.update({"muc": "do", "nhan": f"Rớt từ {time.strftime('%H:%M', time.localtime(b['bd']))} (theo dõi)",
                  "nguyen_nhan": b.get("nguyen_nhan", ""), "theo_doi_rot": b["bd"]})
    elif c.get("theo_doi_rot"):
        c.update({"muc": "xanh", "nhan": "Đạt", "nguyen_nhan": f"Đã lên lại sau {round(b.get('dur', 0) / 60)} phút rớt (theo dõi)"})
        c.pop("theo_doi_rot", None)
    else:
        return False
    dat = sum(1 for x in p["cam"] if x.get("muc") == "xanh")
    p["muc"] = "xanh" if dat == len(p["cam"]) else "do"
    p["tong"] = "ĐẠT" if p["muc"] == "xanh" else f"{dat}/{len(p['cam'])} cam đạt"
    kq["dat"] = sum(1 for x in kq["diem"] for y in x.get("cam", []) if y.get("muc") == "xanh")
    with open(f, "w", encoding="utf-8") as fh:      # lần kiểm nhanh sau sẽ quét lại đúng cam đang rớt
        json.dump(kq, fh, ensure_ascii=False)
    return L.goi_canh_bao(ma, kq, PHIEN_BAN_LOI, lambda *_: None, _doc_du_an(ma))


def theodoi_dung(tid):
    import camlink_theodoi as TD
    return TD.dung(tid)


def theodoi_ghi_live(domain, port_rtsp, luc_ngat, luc_len):
    """Màn xem trực tiếp báo ngắt/lên lại (luc_len=0 là ngắt)."""
    import camlink_theodoi as TD
    return TD.ghi_live(domain, int(port_rtsp), float(luc_ngat), float(luc_len))


def theodoi_dang_xem(host, port_rtsp, trang_thai):
    """Màn xem trực tiếp báo đang xem cam (trang_thai "len" có hình / "ngat" đang rớt) — theo dõi dùng thay cho việc hỏi cam."""
    import camlink_theodoi as TD
    TD.bao_dang_xem(host, int(port_rtsp), trang_thai)


def tuxa_luong_phu(ma, stt, http):
    """Màn giám sát: cam chưa có luồng phụ trong lịch sử → hỏi cam 1 lần, lưu lại. Trả đường dẫn ("" = cam không có luồng phụ)."""
    import camlink_tuxa as T
    f = T._f_lich_su(GOC, ma)
    with open(f, encoding="utf-8") as fh:
        kq = json.load(fh)
    p = next(x for x in kq["diem"] if str(x["stt"]) == str(stt))
    c = next(x for x in p["cam"] if int(x.get("http") or 0) == int(http))
    if c.get("live_phu") or c.get("live_phu_da_hoi"):
        return c.get("live_phu", "")
    cd = C.doc_cai_dat()
    try:
        url = T.luong_phu(p["domain"], int(http), int(c.get("rtsp") or 554), c.get("user") or cd.get("cam_user", "admin"), c.get("pass") or cd.get("cam_pw", ""))
    except Exception:
        return ""                       # cam bận/chậm: lần mở sau hỏi lại
    c["live_phu"], c["live_phu_da_hoi"] = url, True
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(kq, fh, ensure_ascii=False)
    return url


def truc_tiep_bao(ma, json_b):
    """Màn giám sát trực tiếp: cam rớt ≥ 5 phút / lên lại → ghi vào kết quả gần nhất + đẩy ghim LiteMark (như Theo dõi)."""
    b = json.loads(json_b)
    b["ma"] = ma
    return bool(_theodoi_bao_lm(b))


def theodoi_lam_lai(tid):
    import camlink_theodoi as TD
    return TD.lam_lai_pdf(tid)


def chandoan_tinh(ma, json_bang_chung, giai_doan="dang_mat"):
    """Phiếu chẩn đoán theo % khả năng lỗi cho màn hình (bằng chứng do app thu được: cả điểm mất / 1 cam / treo / từ chối / video đứt / câu trả lời hiện trường)."""
    import camlink_chandoan as CD
    return json.dumps(CD.tinh(json.loads(json_bang_chung), ma, giai_doan), ensure_ascii=False)


def chandoan_viec_sua(json_pd, json_sua_co_san):
    import camlink_chandoan as CD
    return json.dumps(CD.viec_sua(json.loads(json_pd), json.loads(json_sua_co_san)), ensure_ascii=False)


def chandoan_xac_nhan(ma, su_co, nguyen_nhan, ghi_chu=""):
    import camlink_chandoan as CD
    return CD.xac_nhan(ma, su_co, nguyen_nhan, ghi_chu)


def chandoan_ds_nguyen_nhan():
    import camlink_chandoan as CD
    return json.dumps([[k, v[0]] for k, v in CD.NGUYEN_NHAN.items()], ensure_ascii=False)


# ===================== Quản trị & Khôi phục (chưa gắn nút — sẵn để nối app) =====================
def qt_da_tao():
    import camlink_quantri as QT
    return QT.da_tao()


def qt_tao_tai_khoan(pin, thiet_bi_id, ten_may="Máy chủ"):
    import camlink_quantri as QT
    return QT.tao_tai_khoan(pin, thiet_bi_id, ten_may)


def qt_kiem_pin(pin):
    import camlink_quantri as QT
    return QT.kiem_pin(pin)


def qt_quyen(thiet_bi_id, pham_vi=""):
    import camlink_quantri as QT
    return QT.quyen(thiet_bi_id, pham_vi)


def qt_nap_tu_cai_dat(pin, ma, thiet_bi_id=""):
    import camlink_quantri as QT
    diem = _doc_du_an(ma).get("diem", {})
    ds = list(diem.values()) if isinstance(diem, dict) else diem
    return QT.nap_tu_cai_dat(pin, ma, ds, C.doc_cai_dat())


def qt_ds_diem(ma):
    diem = _doc_du_an(ma).get("diem", {})
    ds = list(diem.values()) if isinstance(diem, dict) else diem
    return json.dumps([[str(p.get("stt")), p.get("ten", "")] for p in ds], ensure_ascii=False)


def qt_cap_ma_mot_lan(pin, pham_vi, gio=24):
    import camlink_quantri as QT
    return QT.cap_ma_mot_lan(pin, pham_vi, gio)


def qt_tho_dung_ma(ma, thiet_bi_id):
    import camlink_quantri as QT
    return QT.tho_dung_ma(ma, thiet_bi_id)


def qt_thu_hoi_phien(pin, chi_so=None, thiet_bi_id=None):
    import camlink_quantri as QT
    return QT.thu_hoi_phien(pin, chi_so, thiet_bi_id)


def qt_xem_mat_khau(thiet_bi_id, ma, stt, pin=None):
    import camlink_quantri as QT
    return json.dumps(QT.xem_mat_khau(thiet_bi_id, ma, stt, pin), ensure_ascii=False)


def qt_nhat_ky(n=200):
    import camlink_quantri as QT
    return json.dumps(QT.nhat_ky(n), ensure_ascii=False)


def qt_phien_dang_song():
    import camlink_quantri as QT
    return json.dumps(QT.phien_dang_song(), ensure_ascii=False)


def _qt_dong_bo_litemark(ma, stt, cam_user, cam_pw):
    """Ghi mật khẩu mới vào đúng chỗ CamLink dùng để kiểm/đẩy LiteMark → liên kết không đứt.
    Cập nhật: (1) user/pass của điểm trong kết quả kiểm gần nhất, (2) doc_cai_dat mặc định."""
    import camlink_tuxa as T
    try:
        f = T._f_lich_su(GOC, ma)
        with open(f, encoding="utf-8") as fh:
            kq = json.load(fh)
        for p in kq.get("diem", []):
            if str(p.get("stt")) == str(stt):
                for c in p.get("cam", []):
                    c["user"], c["pass"] = cam_user, cam_pw
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(kq, fh, ensure_ascii=False)
    except (OSError, ValueError):
        pass
    cd = C.doc_cai_dat()
    cd["cam_user"], cd["cam_pw"] = cam_user, cam_pw
    C.ghi_cai_dat(cd)



def _qt_diem(ma, stt):
    diem = _doc_du_an(ma).get("diem", {})
    ds = list(diem.values()) if isinstance(diem, dict) else diem
    p = next((x for x in ds if str(x.get("stt")) == str(stt)), None)
    if not p:
        raise RuntimeError(f"Không thấy điểm {stt}")
    so = int(p.get("so") or 1)
    cong = [(i + 1, C.HTTP[i]) for i in range(min(so, len(C.HTTP)))]
    return p.get("domain", ""), cong


def qt_nhan_dien_hang(ma, stt, pin):
    """Nhận diện HÃNG/model qua ONVIF chuẩn (GetDeviceInformation) — để chọn trình cắm hãng khi cần. Đa hãng."""
    import camlink_quantri as QT
    dom, cong = _qt_diem(ma, stt)
    d = QT.xem_mat_khau("_chu_noi_bo_", ma, stt, pin) if False else None  # không dùng; đọc creds nội bộ bên dưới
    creds = QT._doc_ket(QT._lay_khoa_dl(pin=pin))["diem"].get(f"{ma}:{stt}", {})
    u, pw = creds.get("cam_user", "admin"), creds.get("cam_pw", "")
    for _so, ht in cong:
        try:
            ov = C.Onvif(dom, ht, u, pw)
            ov.co()
            return json.dumps({"ok": True, **ov.thong_tin(), "cong": ht}, ensure_ascii=False)
        except Exception:
            continue
    return json.dumps({"ok": False, "loi": "Không đọc được thông tin cam (sai mật khẩu hoặc không tới được)."}, ensure_ascii=False)


def qt_them_thiet_bi(pin, thiet_bi_id, ten_may):
    import camlink_quantri as QT
    return QT.them_thiet_bi(pin, thiet_bi_id, ten_may)


def qt_luu_mat_khau(pin, ma, stt, cam_user, cam_pw, modem_user="", modem_pw=""):
    import camlink_quantri as QT
    return QT.luu_mat_khau(pin, ma, stt, cam_user, cam_pw, modem_user, modem_pw)


def qt_xoay_mat_khau(pin, thiet_bi_id, ma, stt, mat_khau_moi, gom_modem=False):
    """Đổi mật khẩu admin TRÊN CAM bằng ONVIF chuẩn (SetUser) cho MỌI hãng, + cập nhật két + đồng bộ LiteMark.
    Không đụng tài khoản Xem. Modem đổi riêng theo model (chưa qua ONVIF)."""
    import camlink_quantri as QT
    dom, cong = _qt_diem(ma, stt)
    kq_cam = []

    def doi_tren_cam(creds_cu, loai, mk):
        if loai != "cam":
            kq_cam.append("Modem: đổi theo model modem (không qua ONVIF) — để lại.")
            return
        u, pw = creds_cu.get("cam_user", "admin"), creds_cu.get("cam_pw", "")
        for so, ht in cong:
            try:
                ov = C.Onvif(dom, ht, u, pw)
                ov.co()
                ov.doi_mat_khau(u, mk, "Administrator")
                kq_cam.append(f"Cam {so} (:{ht}): ✓ đã đổi")
            except Exception as e:
                kq_cam.append(f"Cam {so} (:{ht}): ✖ {str(e)[:60]}")

    gom = ("cam", "modem") if gom_modem else ("cam",)
    QT.xoay_mat_khau(pin, thiet_bi_id, ma, stt, mat_khau_moi, doi_tren_cam=doi_tren_cam,
                     dong_bo_litemark=lambda st, uu, pp: _qt_dong_bo_litemark(ma, st, uu, pp), gom=gom)
    return "Đổi mật khẩu admin (ONVIF, đa hãng):\n" + "\n".join(kq_cam) + \
           "\n→ Đã cập nhật két và đồng bộ sang đường kiểm/đẩy LiteMark."


def qt_tao_tai_khoan_xem(pin, thiet_bi_id, ma, stt, user, pw):
    """Tạo tài khoản CHỈ XEM cho khách bằng ONVIF chuẩn (CreateUsers, mức 'User') trên mọi cam của điểm — đa hãng."""
    import camlink_quantri as QT
    dom, cong = _qt_diem(ma, stt)
    kq_cam = []

    def tao_tren_cam(creds, u, p):
        au, ap = creds.get("cam_user", "admin"), creds.get("cam_pw", "")
        for so, ht in cong:
            try:
                ov = C.Onvif(dom, ht, au, ap)
                ov.co()
                ov.tao_user(u, p, "User")
                kq_cam.append(f"Cam {so} (:{ht}): ✓")
            except Exception as e:
                kq_cam.append(f"Cam {so} (:{ht}): ✖ {str(e)[:60]}")

    QT.tao_tai_khoan_xem(pin, thiet_bi_id, ma, stt, user, pw, tao_tren_cam)
    return "Tạo tài khoản Xem (ONVIF mức User, chỉ xem) cho khách:\n" + "\n".join(kq_cam) + "\n→ Đã lưu vào két."


def qt_khoi_phuc_doc_ma(ma, stt, domain, http):
    """Khôi phục khi quên sạch mật khẩu — ĐA HÃNG. Bước 1: kiểm cam còn tới được (ONVIF, trước đăng nhập).
    Reset-không-mật-khẩu KHÔNG có chuẩn chung → tuỳ hãng (mã thử–mã mở, nút vật lý). App chọn trình cắm theo hãng;
    hãng chưa có trình cắm thì chỉ ra đúng đường của hãng đó. Trả JSON {ok, toi_duoc, ghi_chu}."""
    toi = False
    try:
        toi = C.Onvif(domain, int(http), "", "").co()      # co() không cần mật khẩu
    except Exception as e:
        return json.dumps({"ok": False, "loi": str(e)[:120]}, ensure_ascii=False)
    if not toi:
        return json.dumps({"ok": False, "loi": "Cam không trả lời qua mạng (kiểm tên miền/cổng/đường truyền)."}, ensure_ascii=False)
    return json.dumps({"ok": True, "toi_duoc": True,
                       "ghi_chu": "Cam còn tới được qua mạng. Khôi phục khi quên mật khẩu tuỳ HÃNG: nếu hãng này đã có "
                                  "trình cắm reset từ xa thì app chạy; chưa có thì lấy mã thử/serial gửi hãng–đại lý để lấy mã mở. "
                                  "Sau khi mở, app đặt lại admin và nạp lại cấu hình từ hồ sơ điểm."},
                      ensure_ascii=False)


def qt_doi_pin(pin_cu, pin_moi):
    import camlink_quantri as QT
    return QT.doi_pin(pin_cu, pin_moi)


# ------------------------------------------------------------------ 2.4: tổng quan cho màn hình chính đồ hoạ
def tong_quan():
    """Số liệu cho thẻ trạng thái ở trang chủ đồ hoạ — CHỈ đọc kết quả kiểm gần nhất đã lưu, không chạm mạng."""
    import camlink_tuxa as T
    out = {"du_an": 0, "tong_cam": 0, "dat": 0, "diem_loi": 0, "gan_nhat": "", "gan_nhat_ma": "", "theo_doi": 0, "ds": []}
    moi = 0
    for r in ds_du_an():
        ma, ten = str(r[0]), str(r[1])
        out["du_an"] += 1
        d = {"ma": ma, "ten": ten, "co_kq": False, "tong_cam": 0, "dat": 0, "diem_loi": 0, "luc": ""}
        f = T._f_lich_su(GOC, ma)
        try:
            with open(f, encoding="utf-8") as fh:
                kq = json.load(fh)
            ds = kq.get("diem") or []
            if ds:
                d["co_kq"] = True
                d["tong_cam"] = sum(len(p.get("cam") or []) for p in ds)
                d["dat"] = sum(1 for p in ds for c in (p.get("cam") or []) if c.get("muc") == "xanh")
                d["diem_loi"] = sum(1 for p in ds if p.get("muc") != "xanh")
                d["luc"] = str(kq.get("luc", ""))
                out["tong_cam"] += d["tong_cam"]
                out["dat"] += d["dat"]
                out["diem_loi"] += d["diem_loi"]
                t = os.path.getmtime(f)
                if t > moi:
                    moi, out["gan_nhat"], out["gan_nhat_ma"] = t, f"{ten} · {d['luc']}", ma
        except (OSError, ValueError):
            pass
        out["ds"].append(d)
    try:
        import camlink_theodoi as TD
        out["theo_doi"] = sum(1 for x in TD.ds_hien() if x.get("trang_thai") == "dang")
    except Exception:
        pass
    return json.dumps(out, ensure_ascii=False)


# ------------------------------------------------------------------ 2.4.1: điểm chưa có tên miền DDNS
def ten_mien_diem(ma, stt):
    """Tên miền DDNS của điểm ('' nếu chưa có) — app hỏi trước khi cài để không cài mù."""
    return str(_doc_du_an(ma)["diem"][str(stt)].get("domain") or "")


def dat_ten_mien_tay(ma, stt, domain, u="", p=""):
    """Nhập tay tên miền tại cột (chưa có file của bên cấp). Trả '' nếu xong, hoặc câu báo lỗi để hiện cho thợ."""
    dom = str(domain or "").strip().lower()
    dom = re.sub(r"^[a-z]+://", "", dom).split("/")[0].split(":")[0]
    if not re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+", dom):
        return "Tên miền không hợp lệ — ví dụ đúng: tencongtrinh-01.ddns.net"
    da = _doc_du_an(ma)
    for k, d in da["diem"].items():
        if k != str(stt) and str(d.get("domain") or "").lower() == dom:
            return f"Tên miền này đã gán cho điểm {k}. {d.get('ten', '')} — mỗi điểm một tên miền."
    x = da["diem"][str(stt)]
    for k in da.get("kho_ddns", []):          # trùng dòng trong kho của bên cấp thì đánh dấu đã dùng
        if str(k.get("domain") or "").lower() == dom and not k.get("dung"):
            k["dung"] = str(stt)
    x.update(domain=dom, u=str(u or "").strip(), p=str(p or "").strip(), dom_nguon=f"nhập tay tại cột {time.strftime('%d/%m %H:%M')}")
    _ghi_du_an(ma, da)
    return ""


def tach_tin_nhan_ddns(van_ban):
    """Tách tin nhắn bên cấp gửi (Zalo…) thành các bộ [tên miền, user, pass, vị trí]. Mỗi bộ: 1 dòng tên miền, 2 dòng kế là user và pass
    (hoặc cùng một dòng, cách nhau bằng khoảng trắng / dấu phẩy). Dòng toạ độ (10.123456, 107.123456) hoặc link Google Maps nằm
    trong bộ nào thì là vị trí của tên miền đó. Bỏ qua tên người gửi, giờ gửi. vị trí = "" | "lat,lng" | link."""
    mau_toa_do = r"(-?\d{1,2}\.\d{3,})\s*[,; ]\s*(-?\d{2,3}\.\d{3,})"
    mau_link = r"https?://\S*(?:goo\.gl|google\.[a-z.]+/maps|maps\.app|maps\.google)\S*"
    la_mien = lambda t: re.fullmatch(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+", t) and re.search(r"\.[a-z]{2,}$", t)
    sach = lambda x: re.sub(r"^[a-z]+://", "", x.lower()).split("/")[0]
    bo = []
    for dong in str(van_ban or "").replace("\r", "\n").split("\n"):
        dong = dong.strip()
        if not dong:
            continue
        vi_tri = ""
        m = re.search(mau_link, dong)
        if m:
            vi_tri, dong = m.group(0), dong.replace(m.group(0), " ").strip()
        else:
            m = re.search(mau_toa_do, dong)
            if m:
                vi_tri, dong = f"{m.group(1)},{m.group(2)}", dong.replace(m.group(0), " ").strip()
        if vi_tri and bo and not bo[-1][3]:
            bo[-1][3] = vi_tri
        if not dong:
            continue
        cac = [x for x in re.split(r"[\s,;|]+", dong) if x]
        co_mien = any(la_mien(sach(x)) for x in cac)
        if not co_mien and (len(cac) > 1 or re.fullmatch(r"\d{1,2}[:h]\d{2}", dong)):
            continue      # dòng có khoảng trắng mà không có tên miền = tên người gửi / lời nhắn; dòng giờ gửi
        for x in cac:
            if la_mien(sach(x)):
                bo.append([sach(x), "", "", ""])
            elif bo and not bo[-1][1]:
                bo[-1][1] = x
            elif bo and not bo[-1][2]:
                bo[-1][2] = x
    return bo


def dan_ten_mien(ma, van_ban):
    """Dán tin nhắn tên miền (không có file) → đưa vào KHO tên miền của dự án, giữ nguyên các dòng kho đã có.
    Dòng có toạ độ thì tự ghép với ghim của điểm (chỉ khi chắc: ≤ 50 m). Trả JSON báo cáo."""
    import camlink_litemark as L
    bo = tach_tin_nhan_ddns(van_ban)
    if not bo:
        return json.dumps({"them": 0, "trung": 0, "loi": "Không thấy tên miền nào trong nội dung dán (ví dụ đúng: ten-diem.ddns.net, dòng dưới là user, dòng dưới nữa là pass)."}, ensure_ascii=False)
    da = _doc_du_an(ma)
    kho = da.setdefault("kho_ddns", [])
    da_co = {str(k.get("domain") or "").lower(): k for k in kho}
    gan = {str(d.get("domain") or "").lower(): s for s, d in da["diem"].items() if d.get("domain")}
    them, trung, thieu, co_td = [], 0, [], 0
    for dom, u, p, vi_tri in bo:
        td = None
        m = re.fullmatch(r"(-?\d+\.\d+),(-?\d+\.\d+)", vi_tri or "")
        if m:
            td = [float(m.group(1)), float(m.group(2))]
        elif vi_tri.startswith("http"):
            try:
                td = C.toa_do_tu_link(vi_tri)
            except Exception:
                td = None
        if dom in da_co:      # đã có trong kho: chỉ bổ sung phần trước đó trống
            k = da_co[dom]
            if u and not k.get("u"):
                k["u"] = u
            if p and not k.get("p"):
                k["p"] = p
            if td and not k.get("toa_do"):
                k["toa_do"], k["map"] = td, vi_tri
            trung += 1
            continue
        dong = {"no": str(len(kho) + 1), "ten": dom.split(".")[0].replace("-", " "), "domain": dom, "u": u, "p": p, "so": 0, "bs": 0,
                "map": vi_tri, "toa_do": td, "dung": gan.get(dom, ""), "nguon": f"dán tin nhắn {time.strftime('%d/%m %H:%M')}"}
        kho.append(dong)
        da_co[dom] = dong
        them.append(dom)
        co_td += 1 if td else 0
        if not (u and p):
            thieu.append(dom)
    tu_gan = 0
    if any(k.get("toa_do") for k in kho) and da.get("toa_do"):
        truoc = sum(1 for d in da["diem"].values() if d.get("domain"))
        da, _ = L.ghep_ddns(da, kho, lambda *_: None)
        tu_gan = sum(1 for d in da["diem"].values() if d.get("domain")) - truoc
    _ghi_du_an(ma, da)
    return json.dumps({"them": len(them), "trung": trung, "ds": them, "thieu_pass": thieu, "co_toa_do": co_td, "tu_gan": tu_gan, "loi": ""}, ensure_ascii=False)


def thong_tin_ten_mien(ma, stt):
    """Tên miền của điểm + nguồn gốc (để người dùng XÁC NHẬN trước khi cài) + số tên miền còn trống trong kho."""
    da = _doc_du_an(ma)
    d = da["diem"][str(stt)]
    con = sum(1 for k in da.get("kho_ddns", []) if not k.get("dung"))
    return json.dumps({"domain": d.get("domain", ""), "nguon": d.get("dom_nguon", ""), "con_trong": con}, ensure_ascii=False)


def ten_mien_lech(ma, stt):
    """Sau lượt cài: cam đang dùng tên miền khác tên miền app lưu cho điểm? Trả JSON {"cam", "app"} hoặc ''."""
    k = getattr(C, "TM_LECH", {})
    if str(k.get("stt")) != str(stt):
        return ""
    return json.dumps({"cam": k.get("cam", ""), "app": k.get("app", "")}, ensure_ascii=False)


def nhan_ten_mien_cam(ma, stt):
    """Người dùng chọn: lấy tên miền ĐANG CÓ TRÊN CAM làm tên miền của điểm (cam không bị đổi gì). Trả '' nếu xong, hoặc câu báo lỗi."""
    k = getattr(C, "TM_LECH", {})
    if str(k.get("stt")) != str(stt) or not k.get("cam"):
        return "Không còn thông tin tên miền trên cam — cài lại điểm này để app đọc lại."
    dom = k["cam"]
    da = _doc_du_an(ma)
    for s2, d2 in da["diem"].items():
        if s2 != str(stt) and str(d2.get("domain") or "").lower() == dom:
            return f"Tên miền {dom} đang gán cho điểm {s2}. {d2.get('ten', '')} trong app — hai điểm không thể chung một tên miền. Kiểm tra lại điểm {s2}."
    x = da["diem"][str(stt)]
    cu = str(x.get("domain") or "").lower()
    u = p = ""
    for dong in da.get("kho_ddns", []):
        dm = str(dong.get("domain") or "").lower()
        if dm == cu and str(dong.get("dung")) == str(stt):
            dong["dung"] = ""                     # trả tên miền cũ về kho cho điểm khác dùng
        if dm == dom:
            dong["dung"] = str(stt)               # tên miền trên cam: đánh dấu đã dùng → loại khỏi các điểm khác
            u, p = dong.get("u", ""), dong.get("p", "")
    x.update(domain=dom, u=u, p=p, dom_nguon=f"lấy theo tên miền đang có trên cam {time.strftime('%d/%m %H:%M')}")
    _ghi_du_an(ma, da)
    C.TM_LECH = {}
    return ""


def dat_ghi_de_ddns():
    """Người dùng chọn: ghi tên miền của điểm LÊN CAM (đè tên miền cam đang dùng) — áp dụng cho đúng lượt cài kế tiếp."""
    C.GHI_DE_DDNS = True


def bao_mat_modem():
    """Màn hình canh modem: mất kết nối quá 2 phút → các vòng chờ trong lõi dừng sớm."""
    C.DUNG_VI_MAT_MODEM = True


# ------------------------------------------------------------------ 2.12: "ĐÃ CÀI" tính theo SỰ THẬT, không chỉ theo lần cài bằng app này
def _lich_su_kiem(ma):
    import camlink_tuxa as T
    try:
        with open(T._f_lich_su(GOC, ma), encoding="utf-8") as fh:
            kq = json.load(fh)
        out = {str(p.get("stt")): p for p in kq.get("diem", [])}
        out["_luc"] = {"luc": str(kq.get("luc", "")), "cam": []}      # giờ của lần kiểm (khoá riêng, không trùng số điểm)
        return out
    except (OSError, ValueError):
        return {}


def diem_da_cai(da, stt, ls=None):
    """Điểm coi là ĐÃ CÀI khi: app cài đạt (da_xong) · hoặc có hồ sơ lúc cài · hoặc từng thấy cam của điểm (dấu vết MAC) ·
    hoặc lần kiểm tra từ xa gần nhất có cam của điểm đang lên. Trả câu mô tả ('' nếu chưa cài)."""
    stt = str(stt)
    c = _chung((da.get("diem") or {}).get(stt))
    if c:      # ghim dùng chung modem: đã cài khi điểm đặt modem đã cài VÀ thật sự thấy cam mang số của ghim này trên modem đó
        a = str(c["stt"])
        if a == stt or not diem_da_cai(da, a, ls) or _so_cam_that(da, a, ls) < max([int(n) for n in c.get("cam") or [1]]):
            return ""
        return f"đã cài (cam số {', '.join(str(n) for n in c.get('cam') or [])} trên modem điểm {a})"
    x = (da.get("da_xong") or {}).get(stt)
    if x:
        return f"đã cài lúc {x}"
    if ((da.get("ho_so") or {}).get(stt) or {}).get("cam"):
        return "đã cài (có hồ sơ lúc cài)"
    p = (ls or {}).get(stt) or {}
    if any(c.get("muc") == "xanh" for c in p.get("cam", [])):
        return f"đang chạy (kiểm tra từ xa {p.get('luc', '')[:8].strip()})".replace(" ()", "")
    if ((da.get("vet") or {}).get(stt) or {}).get("mac"):
        return "đã cài (từng thấy cam của điểm khi kiểm tra từ xa)"
    return ""


# ------------------------------------------------------------------ 2.4.2: trang "Dự án & cấu hình" — cho thấy file đã nạp đủ gì
def tom_tat_du_an():
    """Mỗi dự án: số điểm, bao nhiêu điểm có toạ độ (để GPS tự dò), có tên miền, có user/pass DDNS kèm. Không trả mật khẩu."""
    out = []
    for r in ds_du_an():
        da = _doc_du_an(str(r[0]))
        diem = da.get("diem", {})
        td = da.get("toa_do", {})
        ls = _lich_su_kiem(str(r[0]))
        da_cai = sum(1 for k in diem if diem_da_cai(da, k, ls))
        modem = [k for k in diem if not _chung(diem[k])]      # ghim có modem riêng; ghim dùng chung modem điểm khác không tính
        out.append({"ma": str(r[0]), "ten": da.get("ten", ""), "diem": len(diem),
                    "hoan_thanh": bool(diem) and da_cai == len(diem),
                    "cam_kiem": sum(len(ls[k].get("cam", [])) for k in diem if k in ls),
                    "cam_len": sum(1 for k in diem if k in ls for c in ls[k].get("cam", []) if c.get("muc") == "xanh"),
                    "luc_kiem": (ls.get("_luc") or {}).get("luc", ""),
                    "tu_litemark": "kho_ddns" in da,
                    "modem": len(modem),
                    # nút "Ghim dùng chung modem…" chỉ hiện khi ĐỦ ĐIỀU KIỆN: dự án đã có modem (điểm có tên miền) VÀ có ghim trống để gắn hoặc ghim đang gắn để gỡ.
                    # Dự án chưa có modem nào (Tân Triều chưa cài) hay đã đủ tên miền (Phú Lý) thì không hiện — tránh gây rối.
                    "chon_chung": any(diem[k].get("domain") for k in modem) and (len(modem) != len(diem) or any(
                        not diem[k].get("domain") and not _cam_chung(da, k) for k in modem)),
                    "cam": sum(max([int(diem[k].get("so") or 0)] + list(_cam_chung(da, k))) for k in modem),
                    "toa_do": sum(1 for k in diem if td.get(k)),
                    "ten_mien": sum(1 for k in modem if diem[k].get("domain")),
                    "tk_ddns": sum(1 for k in modem if diem[k].get("domain") and diem[k].get("u") and diem[k].get("p")),
                    "da_xong": da_cai,
                    "rieng": sum(1 for v in diem.values() if v.get("rieng")),
                    "litemark": bool(da.get("kho_ddns") is not None and "kho_ddns" in da)})
    cd = C.doc_cai_dat()
    return json.dumps({"du_an": out, "cam_user": cd.get("cam_user", "admin"), "co_cam_pw": bool(cd.get("cam_pw")),
                       "wifi_ten": cd.get("wifi_ten", ""),
                       "modem_user": cd.get("modem_user", "admin"),
                       "modem_mac_dinh": cd.get("modem_user", "admin") == "admin" and cd.get("modem_pw", "admin") == "admin"}, ensure_ascii=False)


def thong_tin_cai(ma, stt):
    """Dòng tóm tắt cho bảng xác nhận trước khi cài: tài khoản nào sẽ dùng, lấy từ đâu. Không trả mật khẩu."""
    d = _doc_du_an(ma)["diem"][str(stt)]
    cd = C.doc_cai_dat()
    mac_dinh = cd.get("modem_user", "admin") == "admin" and cd.get("modem_pw", "admin") == "admin"
    return json.dumps({"domain": d.get("domain", ""), "u_ddns": d.get("u", ""), "co_p_ddns": bool(d.get("p")),
                       "cam_user": cd.get("cam_user", "admin"), "modem_user": cd.get("modem_user", "admin"), "modem_mac_dinh": mac_dinh,
                       "so": int(d.get("so") or 0)}, ensure_ascii=False)


# ------------------------------------------------------------------ 2.12.19: GHIM · MODEM · CAM
# Sự thật ngoài công trình: một modem (một tên miền) gánh 1..6 cam; cam có thể nằm ở ghim KHÁC ghim đặt modem
# (Tà Lài mở rộng: 1 modem, 2 cam, 2 ghim cách ~100 m). Ghim không có modem riêng ghi: chung = {"stt": <điểm đặt modem>, "cam": [số cam]}.
# App KHÔNG tự đoán: chỉ ghi khi người dùng xác nhận (dat_chung). Thiết kế: docs/superpowers/specs/2026-11-26-ghim-modem-cam-design.md
def _chung(d):
    c = (d or {}).get("chung")
    return c if isinstance(c, dict) and c.get("stt") else None


def _cam_chung(da, a):
    import camlink_tuxa as T
    return T.cam_chung(da, a)


def _so_cam_that(da, stt, ls=None):
    """Số cam THẬT SỰ thấy trên modem của điểm: lúc cài tại chỗ (hồ sơ) hoặc đang lên ở lần kiểm tra từ xa gần nhất."""
    n = len(((da.get("ho_so") or {}).get(str(stt)) or {}).get("cam") or [])
    return max(n, sum(1 for c in ((ls or {}).get(str(stt)) or {}).get("cam", []) if c.get("muc") == "xanh"))


def _so_cam_ke_hoach(d):
    """Số cam theo file / ghim khảo sát (giá trị gốc trước khi app hiệu chỉnh); 0 coi là 1."""
    g = d.get("goc") or {}
    return max(1, int((g.get("so") if "so" in g else d.get("so")) or 0))


def goi_y_chung(ma):
    """GỢI Ý (không ghi): điểm A thấy nhiều cam hơn kế hoạch VÀ có ghim B chưa có tên miền, chưa cài → hỏi người dùng
    "ghim B dùng chung modem điểm A, cam số n?". Trả JSON [{a, ten_a, b, ten_b, cam, m}] (m: mét giữa hai ghim, -1 nếu thiếu toạ độ)."""
    try:
        da = _doc_du_an(ma)
    except (OSError, ValueError):
        return "[]"
    diem, td, ls = da.get("diem", {}), da.get("toa_do", {}), _lich_su_kiem(ma)
    trong = [k for k, d in diem.items() if not d.get("domain") and not _chung(d) and not d.get("chung_khong")
             and not diem_da_cai(da, k, ls) and not _cam_chung(da, k)]
    out = []
    for a, d in sorted(diem.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        if _chung(d) or not d.get("domain") or not trong:
            continue
        da_gan = _cam_chung(da, a)
        du = [n for n in range(_so_cam_ke_hoach(d) + 1, _so_cam_that(da, a, ls) + 1) if n not in da_gan]
        for n in du:
            if not trong:
                break
            def xa(b):
                return C.khoang_cach(td[a], td[b]) if td.get(a) and td.get(b) else 10 ** 9
            b = min(trong, key=xa)
            m = int(xa(b)) if xa(b) < 10 ** 9 else -1
            if m > 1000:      # hai ghim cách nhau quá 1 km thì không thể chung một modem → không hỏi
                continue
            trong.remove(b)
            out.append({"a": a, "ten_a": d.get("ten", ""), "b": b, "ten_b": diem[b].get("ten", ""), "cam": n, "m": m})
    return json.dumps(out, ensure_ascii=False)


def dat_chung(ma, b, a, cam):
    """Người dùng xác nhận: ghim `b` không có modem riêng, cam của nó là cam số `cam` trên modem điểm `a`. '' nếu ghi được, câu lỗi nếu không."""
    da = _doc_du_an(ma)
    diem, a, b = da.get("diem", {}), str(a), str(b)
    try:
        cam = int(cam)
    except (TypeError, ValueError):
        return "Số cam không hợp lệ."
    if a not in diem or b not in diem:
        return "Không tìm thấy điểm."
    if a == b:
        return "Một ghim không thể dùng chung modem với chính nó."
    if _chung(diem[a]):
        return f"Điểm {a} cũng đang dùng chung modem của điểm khác — chọn điểm đặt modem."
    if _cam_chung(da, b):
        return f"Điểm {b} đang là điểm đặt modem cho ghim khác."
    if diem[b].get("domain"):
        return f"Điểm {b} đã có tên miền riêng ({diem[b]['domain']}) — tức là có modem riêng."
    if not 1 <= cam <= len(C.HTTP):
        return f"Số cam phải từ 1 đến {len(C.HTTP)}."
    if _cam_chung(da, a).get(cam) not in (None, b):
        return f"Cam số {cam} của điểm {a} đã gắn cho ghim khác."
    diem[b]["chung"] = {"stt": a, "cam": [cam]}
    diem[b].pop("chung_khong", None)
    if int(diem[a].get("so") or 0) < cam:      # điểm đặt modem phải mang đủ số cam để lượt kiểm tra từ xa quét cả cam của ghim này
        diem[a].setdefault("goc", {"so": diem[a].get("so"), "bs": diem[a].get("bs")})
        diem[a].setdefault("hieu_chinh", []).append({"luc": time.strftime("%d/%m/%Y %H:%M"), "ly_do": f"ghim {b} dùng chung modem (cam số {cam})",
                                                    "cu": int(diem[a].get("so") or 0), "moi": cam})
        diem[a]["so"] = cam
        if diem[a].get("so_thuc"):
            diem[a]["so_thuc"] = max(int(diem[a]["so_thuc"]), cam)
    _ghi_du_an(ma, da)
    _gan_ghim_lich_su(ma, da)
    return ""


def bo_chung(ma, b):
    da = _doc_du_an(ma)
    da["diem"][str(b)].pop("chung", None)
    _ghi_du_an(ma, da)
    _gan_ghim_lich_su(ma, da)
    return ""


def _gan_ghim_lich_su(ma, da):
    """Gắn / gỡ tên ghim cho cam ngay trong kết quả kiểm tra đang lưu → Giám sát, Kiểm tra từ xa đổi liền, không chờ lượt kiểm sau."""
    import camlink_tuxa as T
    try:
        f = T._f_lich_su(GOC, ma)
        with open(f, encoding="utf-8") as fh:
            kq = json.load(fh)
        T.gan_ghim(da, kq.get("diem", []))
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(kq, fh, ensure_ascii=False)
    except (OSError, ValueError):
        pass


def ds_chon_chung(ma):
    """Cho hộp CHỌN TAY 'ghim dùng chung modem': b = ghim chưa có tên miền (chưa gắn); a = điểm đặt modem kèm số cam kế tiếp;
    go = ghim đang gắn chung (để gỡ khi bấm nhầm). JSON."""
    da = _doc_du_an(ma)
    diem, ls = da.get("diem", {}), _lich_su_kiem(ma)
    thu_tu = sorted(diem, key=lambda x: int(x) if x.isdigit() else 0)
    b = [{"stt": k, "ten": diem[k].get("ten", "")} for k in thu_tu
         if not diem[k].get("domain") and not _chung(diem[k]) and not _cam_chung(da, k)]
    a = []
    for k in thu_tu:
        if _chung(diem[k]) or not diem[k].get("domain"):
            continue
        da_co = max([int(diem[k].get("so") or 0), _so_cam_that(da, k, ls), 1] + list(_cam_chung(da, k)))
        tiep = next((n for n in range(2, len(C.HTTP) + 1) if n > _so_cam_ke_hoach(diem[k]) and n not in _cam_chung(da, k)
                     and (n <= da_co or n == da_co + 1)), da_co + 1)
        a.append({"stt": k, "ten": diem[k].get("ten", ""), "cam": tiep})
    go = [{"stt": k, "ten": diem[k].get("ten", ""), "a": str(_chung(diem[k])["stt"])} for k in thu_tu if _chung(diem[k])]
    return json.dumps({"a": a, "b": b, "go": go}, ensure_ascii=False)


def tu_choi_chung(ma, b):
    """Người dùng bấm 'Không phải' → không hỏi lại cho ghim này."""
    da = _doc_du_an(ma)
    da["diem"][str(b)]["chung_khong"] = True
    _ghi_du_an(ma, da)
    return ""


def chung_cua(ma, stt):
    """Bấm tay 'Cài điểm này' ở một ghim dùng chung modem → câu nói rõ phải cài ở đâu ('' nếu là điểm thường)."""
    da = _doc_du_an(ma)
    c = _chung(da.get("diem", {}).get(str(stt)))
    if not c:
        return ""
    a = str(c["stt"])
    return (f"Ghim này không có modem riêng: nó dùng chung modem với điểm {a}. {da['diem'].get(a, {}).get('ten', '')} "
            f"(cam số {', '.join(str(n) for n in c.get('cam') or [])}).\n\nCài tại điểm {a} — app cài luôn cam của ghim này.")


def gan_ghim_cam(da, kq):
    import camlink_tuxa as T
    T.gan_ghim(da, kq.get("diem", []))
    return kq


# ------------------------------------------------------------------ 2.5: TỰ CÀI khi điện thoại vào WiFi modem của điểm
TU_DONG_MET = 150      # GPS phải cách điểm trong file không quá chừng này mới tự cài


def tu_dong_xet(lat, lng):
    """Điện thoại vừa vào một WiFi: có điểm nào ĐỦ CHẮC để tự cài không bấm nút không?
    Chỉ 'ok' khi: gần đúng 1 điểm (≤150 m, không có điểm khác sát bên), điểm có tên miền, chưa cài xong, đã có pass cam.
    Trả JSON {ok, ma, stt, ten, m, ly_do}. Không chắc thì ok=False kèm lý do — app đứng yên, thợ bấm tay."""
    r = {"ok": False, "ma": "", "stt": "", "ten": "", "m": -1, "ly_do": ""}
    if not _cac_du_an():
        r["ly_do"] = "chưa có file cấu hình dự án"
        return json.dumps(r, ensure_ascii=False)
    if "cam_pw" not in C.doc_cai_dat():
        r["ly_do"] = "chưa nhập user/pass cam"
        return json.dumps(r, ensure_ascii=False)
    g = diem_gan(lat, lng)
    if not g:
        r["ly_do"] = "file dự án không có toạ độ điểm"
        return json.dumps(r, ensure_ascii=False)
    ma, stt, _, ten, m, sat = g
    da = _doc_du_an(ma)
    r.update(ma=ma, stt=stt, ten=f"{stt}. {ten}", m=int(m))
    c = _chung(da["diem"][stt])
    if c and m <= TU_DONG_MET:      # ghim này không có modem riêng → không cài riêng, không đòi tên miền
        a = str(c["stt"])
        r["ly_do"] = (f"điểm này dùng chung modem với điểm {a}. {da['diem'].get(a, {}).get('ten', '')} "
                      f"(cam số {', '.join(str(n) for n in c.get('cam') or [])}) — cài tại điểm {a}")
    elif m > TU_DONG_MET:
        r["ly_do"] = f"điểm gần nhất cách {int(m)} m (quá {TU_DONG_MET} m)"
    elif sat:
        r["ly_do"] = "có điểm khác ở sát bên — cần người chọn đúng điểm"
    elif not da["diem"][stt].get("domain"):
        r["ly_do"] = "điểm chưa có tên miền DDNS"
    elif diem_da_cai(da, stt, _lich_su_kiem(ma)):      # đã cài theo sự thật (kể cả điểm cài từ trước / bằng máy khác) → KHÔNG tự cài lại
        mo_ta = diem_da_cai(da, stt, _lich_su_kiem(ma))
        r["ly_do"] = f"điểm {mo_ta}"
        r["da_cai"] = da.get("da_xong", {}).get(stt) or mo_ta      # app báo "đã cài" rồi tự mở hình, không cài lại
    else:
        r["ok"] = True
    return json.dumps(r, ensure_ascii=False)


# ------------------------------------------------------------------ 2.6: WiFi modem dùng chung — app tự vào WiFi tại điểm
def lay_wifi():
    """[tên WiFi (kết thúc bằng * = mỗi modem khác phần đuôi), mật khẩu] — nhập một lần cho cả hệ thống."""
    cd = C.doc_cai_dat()
    return [cd.get("wifi_ten", ""), cd.get("wifi_mk", "")]


def luu_wifi(ten, mk):
    ten, mk = str(ten or "").strip(), str(mk or "")
    if ten and mk and len(mk) < 8:
        return "Mật khẩu WiFi phải từ 8 ký tự (để trống nếu WiFi không đặt mật khẩu)."
    if ten.rstrip("*") == "" and ten:
        return "Nhập ít nhất phần đầu của tên WiFi trước dấu *."
    cd = C.doc_cai_dat()
    cd.update(wifi_ten=ten, wifi_mk=mk)
    C.ghi_cai_dat(cd)
    return ""


def wifi_khop(ssid, ten=None):
    """Tên WiFi điện thoại đang vào có phải WiFi modem (mặc định, hoặc tên truyền vào) không."""
    ten = C.doc_cai_dat().get("wifi_ten", "") if ten is None else str(ten)
    ssid = str(ssid or "").strip('"')
    if not ten or not ssid:
        return False
    return ssid.startswith(ten[:-1]) if ten.endswith("*") else ssid == ten


# ------------------------------------------------------------------ 2.7: user/pass RIÊNG theo điểm — ưu tiên hơn mặc định, không đổi mặc định
def lay_tat_ca_mac_dinh():
    """6 ô mặc định cả hệ thống: user cam, pass cam, user modem, pass modem, tên WiFi, mật khẩu WiFi."""
    return lay_cai_dat() + lay_wifi()


def luu_tat_ca_mac_dinh(cu, cp, mu, mp, wt, wm):
    loi = luu_wifi(wt, wm)
    if loi:
        return loi
    luu_cai_dat(cu, cp, mu, mp)
    return ""


def lay_rieng(ma, stt):
    """Giá trị ĐANG DÙNG cho điểm (riêng nếu có, không thì mặc định), cùng thứ tự 6 ô, + ô thứ 7 = '1' nếu điểm có nhập riêng."""
    d = _doc_du_an(ma)["diem"][str(stt)]
    cd = C.cd_diem(d, C.doc_cai_dat())
    return [cd.get("cam_user", "admin"), cd.get("cam_pw", ""), cd.get("modem_user", "admin"), cd.get("modem_pw", "admin"),
            cd.get("wifi_ten", ""), cd.get("wifi_mk", ""), "1" if d.get("rieng") else ""]


def luu_rieng(ma, stt, cu, cp, mu, mp, wt, wm):
    """Lưu user/pass người dùng nhập cho RIÊNG điểm này. Ô nào trùng mặc định thì không lưu (điểm tiếp tục theo mặc định).
    Mặc định của cả hệ thống KHÔNG bị đổi. Trả '' nếu xong, hoặc câu báo lỗi."""
    wt, wm = str(wt or "").strip(), str(wm or "")
    if wt and wm and len(wm) < 8:
        return "Mật khẩu WiFi phải từ 8 ký tự (để trống nếu WiFi không đặt mật khẩu)."
    da = _doc_du_an(ma)
    d = da["diem"][str(stt)]
    cd = C.doc_cai_dat()
    mac = {"cam_user": cd.get("cam_user", "admin"), "cam_pw": cd.get("cam_pw", ""), "modem_user": cd.get("modem_user", "admin"),
           "modem_pw": cd.get("modem_pw", "admin"), "wifi_ten": cd.get("wifi_ten", ""), "wifi_mk": cd.get("wifi_mk", "")}
    moi = {"cam_user": str(cu or "").strip(), "cam_pw": str(cp or ""), "modem_user": str(mu or "").strip(), "modem_pw": str(mp or ""),
           "wifi_ten": wt, "wifi_mk": wm}
    rieng = {k: v for k, v in moi.items() if v != "" and v != mac[k]}
    if rieng:
        d["rieng"] = rieng
    else:
        d.pop("rieng", None)
    _ghi_du_an(ma, da)
    return ""


def xoa_rieng(ma, stt):
    da = _doc_du_an(ma)
    da["diem"][str(stt)].pop("rieng", None)
    _ghi_du_an(ma, da)
    return ""


# ------------------------------------------------------------------ 2.10: màn rada của Kiểm tra từ xa
def tuxa_rada(ma):
    """Dựng trang rada (bản đồ toàn tuyến, màu theo lần kiểm trước). Trả đường dẫn file HTML."""
    import camlink_tuxa as T
    ls = {}
    try:
        with open(T._f_lich_su(GOC, ma), encoding="utf-8") as fh:
            ls = json.load(fh)
    except (OSError, ValueError):
        pass
    return T.rada_html(_doc_du_an(ma), ma, ls, GOC)


# ------------------------------------------------------------------ 2.11: chẩn đoán theo % ngay trong thẻ điểm lỗi của Kiểm tra từ xa
def chandoan_diem(ma, json_p):
    """Kết quả quét một điểm → phiếu chẩn đoán theo % (gộp bằng chứng của các cam lỗi). Điểm không lỗi trả '{}'."""
    import camlink_chandoan as CD
    b = CD.tu_ket_qua_diem(json.loads(json_p))
    gop = []
    for ds in b.values():
        for x in ds:
            if x not in gop:
                gop.append(x)
    if not b:
        return "{}"
    pd = CD.tinh(gop, ma, "dang_mat")
    pd["mot_dong"] = CD.dong_mot_dong(pd)
    return json.dumps(pd, ensure_ascii=False)
