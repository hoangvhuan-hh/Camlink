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


def link_diem(ma, stt, da=None):
    lk = lien_ket(ma)
    if not lk.get("id"):
        return ""
    lm_stt = (da or {}).get("diem", {}).get(str(stt), {}).get("lm_stt") or stt
    return f"{MAY_CHU}/ct/{lk['id']}/diem/{lm_stt}"


def ghep_ghim(da, ghim):
    """Ghép điểm CamLink ↔ ghim LiteMark THEO VỊ TRÍ (số thứ tự hai bên KHÔNG trùng nhau: LiteMark đánh số lại theo tuyến).
    Ghép 1-1 theo khoảng cách tăng dần (toạ độ Excel của CamLink so với ghim); điểm đã ghép tay (lm_tay) giữ nguyên.
    Trả về {stt_camlink: {"lm_stt", "kc", "chac"}} và danh sách ghi chú."""
    goc = da.get("toa_do_goc") or da.get("toa_do") or {}
    ket, ghi_chu = {}, []
    da_dung = set()
    for stt, d in da["diem"].items():
        if d.get("lm_tay") and str(d["lm_tay"]) in ghim:
            ket[stt] = {"lm_stt": str(d["lm_tay"]), "kc": 0, "chac": True, "tay": True}
            da_dung.add(str(d["lm_tay"]))
    cap = []
    for stt, d in da["diem"].items():
        if stt in ket or stt not in goc:
            continue
        for g_stt, g in ghim.items():
            cap.append((_khoang_cach(goc[stt][0], goc[stt][1], float(g["lat"]), float(g["lng"])), stt, g_stt))
    cap.sort()
    for kc, stt, g_stt in cap:
        if stt in ket or g_stt in da_dung:
            continue
        ket[stt] = {"lm_stt": g_stt, "kc": int(kc), "chac": kc <= 300}
        da_dung.add(g_stt)
    con_lai = [g for g in ghim if g not in da_dung]
    for stt in da["diem"]:
        if stt not in ket:   # không có toạ độ Excel hoặc ghim đã hết: lấy ghim còn trống đầu tiên, đánh dấu chưa chắc
            if con_lai:
                ket[stt] = {"lm_stt": con_lai.pop(0), "kc": -1, "chac": False}
            else:
                ghi_chu.append(f"Điểm {stt} ({da['diem'][stt].get('ten', '')}): không còn ghim LiteMark nào để ghép")
    for stt, k in ket.items():
        if k.get("tay"):
            continue
        if not k["chac"]:
            ghi_chu.append(f"Điểm {stt} ({da['diem'][stt].get('ten', '')}) ↔ ghim LiteMark {k['lm_stt']}: "
                           + (f"cách {k['kc']} m — CHƯA CHẮC" if k["kc"] >= 0 else "không có toạ độ Excel — CHƯA CHẮC")
                           + " → mở điểm trong màn giám sát, so ảnh khảo sát LiteMark với hình live rồi bấm 'Sai ghim? chọn lại' nếu cần")
    for g in con_lai:
        ghi_chu.append(f"Ghim LiteMark {g} ({ghim[g].get('ten', '')}) không ghép với điểm CamLink nào")
    return ket, ghi_chu


def dong_bo_ghim(ma, da, log=print):
    """Lấy ghim LiteMark về: ghép theo vị trí, dùng toạ độ ghim làm toạ độ chính; giữ toạ độ Excel ở toa_do_goc để đối chiếu."""
    lk = lien_ket(ma)
    if not lk.get("id"):
        raise RuntimeError("Dự án chưa nối với công trình LiteMark")
    kq = _goi(f"/api/camlink/cong-trinh/{lk['id']}/diem")
    ghim = {str(d.get("stt")): d for d in kq.get("diem", []) if d.get("lat") and d.get("lng")}
    if not ghim:
        raise RuntimeError("Công trình LiteMark chưa có ghim nào")
    da.setdefault("toa_do_goc", dict(da.get("toa_do", {})))
    ket, ghi_chu = ghep_ghim(da, ghim)
    toa_do = {}
    bang = []
    for stt, d in da["diem"].items():
        k = ket.get(stt)
        if not k:
            if stt in da["toa_do_goc"]:
                toa_do[stt] = da["toa_do_goc"][stt]
            continue
        g = ghim[k["lm_stt"]]
        toa_do[stt] = [float(g["lat"]), float(g["lng"])]
        d["lm_stt"], d["lm_kc"], d["lm_chac"] = k["lm_stt"], k["kc"], k["chac"]
        d["lm_ten"], d["lm_anh"] = g.get("ten", ""), g.get("anh_dai_dien", "")
        so_lm = g.get("so_camera")
        if so_lm not in (None, ""):
            d["lm_so"] = int(so_lm)
            if int(so_lm) != int(d.get("so") or 0):
                ghi_chu.append(f"Điểm {stt} (ghim LM {k['lm_stt']}): LiteMark ghi {so_lm} camera, hồ sơ CamLink {d.get('so')} → đối chiếu khi kiểm")
        bang.append(f"CamLink {stt} «{d.get('ten', '')[:28]}» ↔ ghim LM {k['lm_stt']}" + ("" if k["kc"] <= 0 else f" ({k['kc']} m)") + ("" if k["chac"] else " ⚠ chưa chắc"))
    da["toa_do"] = toa_do
    da["litemark"] = {"id": lk["id"], "ten": kq.get("ten", lk.get("ten", "")), "luc_dong_bo": time.strftime("%d/%m/%Y %H:%M"),
                      "so_ghim": len(ghim), "ghi_chu": ghi_chu, "bang_ghep": bang,
                      "ghim": {g: {"ten": v.get("ten", ""), "lat": v["lat"], "lng": v["lng"]} for g, v in ghim.items()}}
    log(f"🔗 LiteMark «{da['litemark']['ten']}»: {len(ghim)} ghim, ghép theo vị trí {len(ket)} điểm" + (f"; {len(ghi_chu)} ghi chú" if ghi_chu else ""))
    for b in bang:
        log("   · " + b)
    for g in ghi_chu:
        log("   ⚠ " + g)
    return da, ghi_chu


def dat_ghim_tay(ma, da, stt, lm_stt):
    """Người dùng chốt: điểm CamLink `stt` chính là ghim LiteMark `lm_stt` (sau khi so ảnh khảo sát với live)."""
    da["diem"][stt]["lm_tay"] = str(lm_stt)
    return da


def _khoang_cach(a1, o1, a2, o2):
    import math
    r = 6371000.0
    p1, p2 = math.radians(a1), math.radians(a2)
    dp, dl = math.radians(a2 - a1), math.radians(o2 - o1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def goi_canh_bao(ma, kq, phien_ban, log=print, da=None):
    """Đẩy kết quả kiểm lên LiteMark theo SỐ GHIM LITEMARK (đã ghép theo vị trí). Chỉ gửi điểm có vấn đề + danh sách điểm đạt
    để LiteMark xoá cảnh báo cũ; điểm đạt không tô màu (trạng thái hoàn thành của LiteMark đã nói đủ).
    Không gửi được → xếp hàng, lần sau gửi bù (bản mới nhất thắng)."""
    lk = lien_ket(ma)
    if not lk.get("id"):
        return False
    dm = (da or {}).get("diem", {})
    def lm(p):
        return str(dm.get(str(p["stt"]), {}).get("lm_stt") or p["stt"])
    than = {"luc": time.strftime("%Y-%m-%dT%H:%M:%S"), "nguon": "camlink", "phien_ban": phien_ban,
            "khong_tin_cay": kq.get("khong_tin_cay", ""), "tong": {"dat": kq.get("dat", 0), "tong": kq.get("tong_cam", 0)},
            "chi_bao_loi": True, "diem_dat": [lm(p) for p in kq.get("diem", []) if p["muc"] == "xanh"],
            "diem": [{"stt": lm(p), "stt_camlink": p["stt"], "ten": p["ten"], "domain": p.get("domain", ""), "muc": p["muc"], "tong": p["tong"],
                      "chua_chac_ghim": not dm.get(str(p["stt"]), {}).get("lm_chac", True),
                      "cam": [{"so": c["so"], "http": c["http"], "muc": c["muc"], "nhan": c.get("nhan", ""),
                               "nguyen_nhan": c.get("nguyen_nhan", ""), "viec": c.get("viec", [])[:3]} for c in p["cam"]]}
                     for p in kq.get("diem", []) if p["muc"] != "xanh"]}
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
