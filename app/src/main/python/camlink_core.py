# -*- coding: utf-8 -*-
"""Cầu nối giữa giao diện Android và lõi camlink_dt.py."""
import json, os, re, time
import camlink_dt as C

GOC = None


def _cb(x):
    """Nhận hàm ghi nhật ký từ Android (đối tượng có .ghi) hoặc hàm Python."""
    return getattr(x, "ghi", x)


def khoi_tao(thu_muc):
    global GOC
    GOC = thu_muc
    os.makedirs(os.path.join(GOC, "ketqua"), exist_ok=True)
    C.thu_muc_ra = lambda: os.path.join(GOC, "ketqua")
    _nap_diem()


def _file_diem():
    return os.path.join(GOC, "diem.json")


def _nap_diem():
    try:
        with open(_file_diem(), encoding="utf-8") as f:
            C.PHU_LY.clear()
            C.PHU_LY.update(json.load(f))
    except (OSError, ValueError):
        pass


def _chuan(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def nhap_excel(duong_dan, log):
    """Đọc file khảo sát (cột No, Tên, Map, Camera, Camera BS, Domain, USER, PW)."""
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
                     "so": int(g(c_cam) or 0) + int(g(c_bs) or 0), "map": str(g(c_map) or "")}
        if not ds:
            continue
        with open(_file_diem(), "w", encoding="utf-8") as f:
            json.dump(ds, f, ensure_ascii=False)
        _nap_diem()
        cd = C.doc_cai_dat()
        cd["toa_do"] = {}
        log(f"Đọc được {len(ds)} điểm, {sum(v['so'] for v in ds.values())} cam. Đang lấy toạ độ từ link bản đồ ...")
        for k, v in ds.items():
            td = C.toa_do_tu_link(v["map"]) if v["map"].startswith("http") else None
            if td:
                cd["toa_do"][k] = td
            log(f"  {k}. {v['ten']}: {'%.5f, %.5f' % tuple(td) if td else 'không có toạ độ'}")
        C.ghi_cai_dat(cd)
        return f"{len(ds)} điểm"
    raise ValueError("Không thấy bảng có cột 'Domain' trong file.")


def co_du_lieu():
    return bool(C.PHU_LY)


def co_cai_dat():
    return "cam_pw" in C.doc_cai_dat()


def lay_cai_dat():
    cd = C.doc_cai_dat()
    return [cd.get("cam_user", "admin"), cd.get("cam_pw", ""), cd.get("modem_user", "admin"), cd.get("modem_pw", "admin")]


def luu_cai_dat(cu, cp, mu, mp):
    cd = C.doc_cai_dat()
    cd.update(cam_user=cu or "admin", cam_pw=cp, modem_user=mu or "admin", modem_pw=mp or "admin")
    C.ghi_cai_dat(cd)


def danh_sach():
    xong = C.doc_cai_dat().get("da_xong", {})
    return [f"{k}. {v['ten']} ({v['so']} cam)" + (f"  ✔ {xong[k]}" if k in xong else "") for k, v in C.PHU_LY.items()]


def khoa_theo_so_thu_tu(i):
    return list(C.PHU_LY.keys())[i]


def diem_gan(lat, lng):
    td = C.doc_cai_dat().get("toa_do", {})
    if not td:
        return None
    m, k = min((C.khoang_cach((lat, lng), v), k) for k, v in td.items())
    return [k, C.PHU_LY[k]["ten"], int(m)]


def chay(stt, may_ip, gw, log):
    log = _cb(log)
    C.LOG_CB, C.GW = log, gw or None
    if may_ip:
        os.environ["CAMLINK_MAY"] = may_ip
    C.NHAT_KY.clear()
    C.CAN_MAU.clear()
    cd = C.doc_cai_dat()
    C.chay(stt, cd["cam_user"], cd["cam_pw"], cd["modem_user"], cd["modem_pw"])
    if any("ĐẠT" in l for l in C.NHAT_KY):
        cd.setdefault("da_xong", {})[stt] = time.strftime("%d/%m %H:%M")
        C.ghi_cai_dat(cd)


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
    return out
