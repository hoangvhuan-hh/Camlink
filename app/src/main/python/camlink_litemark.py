"""Nối CamLink ↔ LiteMark (litemark.vn): lấy ghim thực tế của công trình, đẩy cảnh báo cam lỗi lên bản đồ LiteMark.

Hợp đồng API (phía LiteMark làm theo đúng tên trường):
  GET  /api/camlink/cong-trinh                 → {"cong_trinh":[{id, ten, dia_chi, so_diem, so_camera, trang_thai, cap_nhat}]}
  GET  /api/camlink/cong-trinh/{id}/diem       → {"id","ten","diem":[{stt, ten, lat, lng, so_camera, so_camera_bs, ghi_chu}]}
  POST /api/camlink/cong-trinh/{id}/canh-bao   ← {"luc","nguon":"camlink","phien_ban","khong_tin_cay","tong":{dat,tong},"diem":[...]}
  Header: Authorization: Bearer <khoá kết nối lấy trong Tài khoản LiteMark>
"""
import json, os, re, time, unicodedata, urllib.request, urllib.error

MAY_CHU = os.environ.get("CAMLINK_LITEMARK", "https://litemark.vn")
GOC = None


def khoi_tao(goc):
    global GOC
    GOC = goc
    os.makedirs(os.path.join(goc, "litemark"), exist_ok=True)


def _f(ten):
    return os.path.join(GOC, "litemark", ten)


def _doc(ten, mac_dinh):
    try:
        with open(_f(ten), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return mac_dinh


def _ghi(ten, du_lieu):
    with open(_f(ten), "w", encoding="utf-8") as fh:
        json.dump(du_lieu, fh, ensure_ascii=False)


def khoa():
    return _doc("khoa.json", {}).get("khoa", "")


def luu_khoa(k):
    k = (k or "").strip()
    # cho phép dán cả link/QR dạng  litemark://camlink?khoa=XYZ  hoặc  https://litemark.vn/camlink?khoa=XYZ
    m = re.search(r"[?&]khoa=([A-Za-z0-9_\-]+)", k)
    if m:
        k = m.group(1)
    _ghi("khoa.json", {"khoa": k, "luc": time.strftime("%d/%m/%Y %H:%M")})
    return k


def xoa_khoa():
    try:
        os.remove(_f("khoa.json"))
    except OSError:
        pass


def _goi(duong, du_lieu=None, cho=15):
    if not khoa():
        raise RuntimeError("Chưa có khoá kết nối LiteMark (lấy trong LiteMark → Tài khoản → Kết nối CamLink)")
    than = json.dumps(du_lieu, ensure_ascii=False).encode("utf-8") if du_lieu is not None else None
    req = urllib.request.Request(MAY_CHU + duong, data=than, method="POST" if than else "GET",
                                 headers={"Authorization": "Bearer " + khoa(), "Content-Type": "application/json",
                                          "User-Agent": "CamLink"})
    try:
        with urllib.request.urlopen(req, timeout=cho) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RuntimeError("LiteMark từ chối khoá kết nối (sai hoặc đã thu hồi) → tạo khoá mới trong LiteMark rồi dán lại")
        if e.code == 403:
            raise RuntimeError("Tài khoản LiteMark này không có quyền xem công trình đó")
        if e.code == 404:
            raise RuntimeError("LiteMark chưa có API kết nối CamLink (máy chủ chưa cập nhật) hoặc công trình không tồn tại")
        raise RuntimeError(f"LiteMark trả lỗi {e.code}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Không nối được litemark.vn ({getattr(e, 'reason', e)}) — kiểm tra 4G/WiFi")


def ds_cong_trinh():
    """Danh sách công trình tài khoản được xem — người dùng CHỌN để nối, không nhập tay."""
    kq = _goi("/api/camlink/cong-trinh")
    ds = kq.get("cong_trinh", [])
    thu_tu = {"dang_thi_cong": 0, "dang_khao_sat": 1, "da_khoa": 2, "xong": 3}
    ds.sort(key=lambda c: (thu_tu.get(c.get("trang_thai", ""), 9), -(len(c.get("cap_nhat") or ""))))
    _ghi("cong_trinh.json", {"luc": time.time(), "ds": ds})
    return ds


def _chuan(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def goi_y(ten_du_an, so_diem, ds=None):
    """Chấm điểm công trình LiteMark khớp với dự án CamLink (tên + số điểm) để gợi ý lên đầu."""
    ds = ds if ds is not None else _doc("cong_trinh.json", {}).get("ds", [])
    tu_da = set(_chuan(ten_du_an).split())
    out = []
    for c in ds:
        tu_ct = set(_chuan(c.get("ten")).split())
        chung = len(tu_da & tu_ct - {"camera", "cam", "cong", "trinh", "du", "an", "xa", "he", "thong"})
        diem = chung * 2 + (3 if int(c.get("so_diem") or 0) == int(so_diem) else 0)
        out.append((diem, c))
    out.sort(key=lambda x: -x[0])
    return [{"diem_khop": d, **c} for d, c in out]


def lien_ket(ma):
    return _doc(f"lk_{ma}.json", {})


def noi(ma, cong_trinh):
    """Gắn dự án CamLink `ma` với công trình LiteMark (dict có id, ten)."""
    lk = {"id": cong_trinh["id"], "ten": cong_trinh.get("ten", ""), "luc_noi": time.strftime("%d/%m/%Y %H:%M")}
    _ghi(f"lk_{ma}.json", lk)
    return lk


def ngat(ma):
    try:
        os.remove(_f(f"lk_{ma}.json"))
    except OSError:
        pass


def link_diem(ma, stt):
    lk = lien_ket(ma)
    return f"{MAY_CHU}/ct/{lk['id']}/diem/{stt}" if lk.get("id") else ""


def dong_bo_ghim(ma, da, log=print):
    """Lấy ghim LiteMark về làm toạ độ chính của dự án; giữ toạ độ Excel ở toa_do_goc để đối chiếu.
    Trả về (da đã cập nhật, ghi chú đối chiếu)."""
    lk = lien_ket(ma)
    if not lk.get("id"):
        raise RuntimeError("Dự án chưa nối với công trình LiteMark")
    kq = _goi(f"/api/camlink/cong-trinh/{lk['id']}/diem")
    ghim = {str(d.get("stt")): d for d in kq.get("diem", []) if d.get("lat") and d.get("lng")}
    if not ghim:
        raise RuntimeError("Công trình LiteMark chưa có ghim nào")
    da.setdefault("toa_do_goc", dict(da.get("toa_do", {})))
    toa_do = {}
    ghi_chu = []
    for stt, d in da["diem"].items():
        g = ghim.get(str(stt))
        if not g:
            ghi_chu.append(f"Điểm {stt} ({d.get('ten', '')}): LiteMark không có ghim số {stt} → giữ toạ độ Excel")
            if stt in da.get("toa_do_goc", {}):
                toa_do[stt] = da["toa_do_goc"][stt]
            continue
        toa_do[stt] = [float(g["lat"]), float(g["lng"])]
        d["lm_ten"] = g.get("ten", "")
        goc = da.get("toa_do_goc", {}).get(stt)
        if goc:
            lech = _khoang_cach(goc[0], goc[1], toa_do[stt][0], toa_do[stt][1])
            if lech > 150:
                ghi_chu.append(f"Điểm {stt}: ghim LiteMark cách toạ độ Excel {int(lech)} m → dùng ghim LiteMark (thực tế thi công)")
        so_lm = g.get("so_camera")
        if so_lm not in (None, "") and int(so_lm) != int(d.get("so") or 0):
            ghi_chu.append(f"Điểm {stt}: LiteMark ghi {so_lm} camera, hồ sơ CamLink {d.get('so')} → đối chiếu khi kiểm")
            d["lm_so"] = int(so_lm)
    for stt in ghim:
        if stt not in da["diem"]:
            ghi_chu.append(f"LiteMark có ghim số {stt} ({ghim[stt].get('ten', '')}) nhưng dự án CamLink không có điểm này")
    da["toa_do"] = toa_do
    da["litemark"] = {"id": lk["id"], "ten": kq.get("ten", lk.get("ten", "")), "luc_dong_bo": time.strftime("%d/%m/%Y %H:%M"),
                      "so_ghim": len(ghim), "ghi_chu": ghi_chu}
    log(f"🔗 LiteMark «{da['litemark']['ten']}»: {len(ghim)} ghim → đã dùng làm toạ độ {len(toa_do)} điểm" + (f"; {len(ghi_chu)} ghi chú" if ghi_chu else ""))
    for g in ghi_chu:
        log("   · " + g)
    return da, ghi_chu


def _khoang_cach(a1, o1, a2, o2):
    import math
    r = 6371000.0
    p1, p2 = math.radians(a1), math.radians(a2)
    dp, dl = math.radians(a2 - a1), math.radians(o2 - o1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def goi_canh_bao(ma, kq, phien_ban, log=print):
    """Đẩy kết quả kiểm lên LiteMark. Không gửi được → xếp hàng, lần sau gửi bù (bản mới nhất thắng)."""
    lk = lien_ket(ma)
    if not lk.get("id"):
        return False
    than = {"luc": time.strftime("%Y-%m-%dT%H:%M:%S"), "nguon": "camlink", "phien_ban": phien_ban,
            "khong_tin_cay": kq.get("khong_tin_cay", ""), "tong": {"dat": kq.get("dat", 0), "tong": kq.get("tong_cam", 0)},
            "diem": [{"stt": p["stt"], "ten": p["ten"], "muc": p["muc"], "tong": p["tong"],
                      "cam": [{"so": c["so"], "http": c["http"], "muc": c["muc"], "nhan": c.get("nhan", ""),
                               "nguyen_nhan": c.get("nguyen_nhan", ""), "viec": c.get("viec", [])[:3]} for c in p["cam"]]}
                     for p in kq.get("diem", [])]}
    _ghi(f"cho_{ma}.json", than)   # hàng đợi: luôn ghi bản mới nhất
    return gui_bu(ma, log)


def gui_bu(ma, log=print):
    lk = lien_ket(ma)
    than = _doc(f"cho_{ma}.json", None)
    if not lk.get("id") or not than:
        return False
    try:
        _goi(f"/api/camlink/cong-trinh/{lk['id']}/canh-bao", than)
        os.remove(_f(f"cho_{ma}.json"))
        log(f"🔗 Đã đẩy cảnh báo {than['tong']['dat']}/{than['tong']['tong']} cam lên bản đồ LiteMark «{lk.get('ten', '')}»")
        return True
    except Exception as e:
        log(f"⚠ Chưa đẩy được lên LiteMark ({str(e)[:90]}) — sẽ gửi bù ở lần kiểm sau")
        return False
