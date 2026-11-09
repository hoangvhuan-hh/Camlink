# -*- coding: utf-8 -*-
"""Cầu nối giữa giao diện Android và lõi camlink_dt.py — hỗ trợ nhiều dự án.

Mỗi file khảo sát Excel = 1 dự án, lưu riêng ở <app>/duan/<mã>.json:
  {"ten": tên dự án, "diem": {stt: {...}}, "toa_do": {stt: [lat, lng]}, "da_xong": {stt: "dd/mm hh:mm"}}
User/pass cam + modem dùng chung cho mọi dự án (camlink_caidat.json).
GPS tìm điểm gần nhất trên TẤT CẢ dự án → tự chọn đúng dự án + điểm.
"""
import json, os, re, time, unicodedata
import camlink_dt as C

PHIEN_BAN_LOI = "1.6"
KENH_CAP_NHAT = "https://claude.ai/artifact/D5udnnkXEqbKMRBmsMhjGy"   # kênh cập nhật (đổi được bằng gói zip, không cần APK)   # phiên bản phần logic Python (cập nhật đè được, vài trăm KB)

GOC = None


def _cb(x):
    """Nhận hàm ghi nhật ký từ Android (đối tượng có .ghi) hoặc hàm Python."""
    return getattr(x, "ghi", x)


def _thu_muc_du_an():
    return os.path.join(GOC, "duan")


def khoi_tao(thu_muc):
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
        return json.load(f)


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
    sat = len(ung) > 1 and ung[1][0] - m < 150 and ung[1][0] <= 400
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
    cd = C.doc_cai_dat()
    C.chay(stt, cd["cam_user"], cd["cam_pw"], cd["modem_user"], cd["modem_pw"])
    if any("ĐẠT" in l for l in C.NHAT_KY):
        da.setdefault("da_xong", {})[stt] = time.strftime("%d/%m %H:%M")
    if C.KQ_CUOI.get("stt") == stt:   # hồ sơ điểm: để sau này kiểm tra / sửa từ xa
        k = C.KQ_CUOI
        da.setdefault("ho_so", {})[stt] = {"luc": time.strftime("%d/%m/%Y %H:%M"), "wan": k.get("wan", ""),
                                           "gw": k.get("gw", ""), "upnp": k.get("upnp"), "luat": k.get("luat", []),
                                           "cam": [{"so": c["so"], "ip": c["ip"], "mac": c.get("mac", ""),
                                                    "model": c.get("model", "")} for c in k.get("cam", [])]}
    _ghi_du_an(ma, da)
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
    return C.thu(cd.get("cam_user", ""), cd.get("cam_pw", ""))


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
    d = da["diem"][stt]
    dom = d["domain"]
    cd = C.doc_cai_dat()
    kq = dict(C.KQ_CUOI) if C.KQ_CUOI.get("stt") == stt and C.KQ_CUOI.get("domain") == dom else {}
    kq.setdefault("domain", dom)
    kq.setdefault("ten", d["ten"])
    kq.setdefault("stt", stt)
    kq["du_an"] = da["ten"]
    kq.setdefault("cam", [{"so": i + 1, "ip": f"…{C.IP_TU + i}", "http": C.HTTP[i], "rtsp": C.RTSP[i],
                           "model": "", "mac": "", "ok": None, "ghi": ""} for i in range(d["so"])])
    C.log("")
    C.log(f"BẰNG CHỨNG TỪ NGOÀI — gọi {dom} như IOC")
    try:
        ip = socket.gethostbyname(dom)
    except OSError:
        ip = ""
    kq["ip_ten_mien"] = ip
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


def tuxa_kiem(ma, log):
    import camlink_tuxa as T
    log = _cb(log)
    da = _doc_du_an(ma)
    kq = T.kiem_du_an(GOC, da, ma, C.doc_cai_dat(), log)
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
    return json.dumps(kq, ensure_ascii=False)


def tuxa_khao_sat(ma, json_kq):
    import camlink_tuxa as T
    return T.xuat_khao_sat_hieu_chinh(GOC, _doc_du_an(ma), json.loads(json_kq))


def tuxa_kiem_diem(ma, stt, log):
    import camlink_tuxa as T
    log = _cb(log)
    kq = T.kiem_du_an(GOC, _doc_du_an(ma), ma, C.doc_cai_dat(), log, chi_diem=[stt], tu_sua=False)
    return json.dumps(kq["diem"][0], ensure_ascii=False)


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
    ok, tb = T.sua(_doc_du_an(ma)["diem"][stt], int(so), viec, C.doc_cai_dat(), log)
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


def tuxa_ban_do(json_kq):
    import camlink_tuxa as T
    return T.ban_do_html(json.loads(json_kq), GOC)


def tuxa_phieu(ma, json_kq, stt):
    import camlink_tuxa as T
    kq = json.loads(json_kq)
    p = next(x for x in kq["diem"] if x["stt"] == stt)
    return T.phieu_bao_mang(kq, p, (_doc_du_an(ma).get("ho_so") or {}).get(stt))


# ------------------------------------------------------------------ cập nhật đè phần logic (không cần cài lại APK)
TEP_LOI = ["camlink_core.py", "camlink_dt.py", "camlink_tuxa.py", "camlink_oryza.py"]


def phien_ban_loi():
    return PHIEN_BAN_LOI


def nap_cap_nhat_zip(duong_zip):
    """Nạp gói cập nhật: .zip HOẶC gói một tệp .camlink (JSON, không bị điện thoại tự giải nén) → áp dụng khi mở lại app."""
    import base64, hashlib, zipfile
    th = os.path.join(GOC, "capnhat")
    os.makedirs(th, exist_ok=True)
    with open(duong_zip, "rb") as fh:
        dau = fh.read(4)
    if dau[:1] == b"{":   # gói một tệp .camlink
        with open(duong_zip, encoding="utf-8") as fh:
            goi = json.load(fh)
        if goi.get("loai") != "camlink-loi":
            raise RuntimeError("Đây không phải gói cập nhật CamLink")
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
