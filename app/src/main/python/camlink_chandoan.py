"""CHẨN ĐOÁN THEO % KHẢ NĂNG LỖI (Huan chốt 10/11/2026 19:08).

Không khẳng định — đưa ra KHẢ NĂNG từng nguyên nhân (%) kèm BẰNG CHỨNG.
  %  = mức nền (kinh nghiệm thi công, chỉnh dần theo xác nhận thực tế của từng dự án) × hệ số của từng bằng chứng đo được → chia lại cho đủ 100.
Nút "🔧 Sửa từ xa" chỉ sáng khi tổng % các nguyên nhân SỬA ĐƯỢC TỪ XA ≥ 60%.
Mất điện + modem/VNPT ≥ 50% → ẩn nút sửa, hướng dẫn kiểm tra nguồn điện / modem tại điểm (tránh cái gì cũng bấm sửa).
Hai giai đoạn: ĐANG MẤT (chỉ có bằng chứng mạng + câu trả lời của người tại điểm) → SAU KHI LÊN (đọc nhật ký cam, IP có đổi không).
"""
import json
import os
import time

NGUONG_SUA = 0.60
NGUONG_HIEN_TRUONG = 0.50

# mã: (tên, sửa từ xa được?, việc cần làm, ai xử lý)
NGUYEN_NHAN = {
    "mat_dien": ("Mất điện lưới tại điểm", False,
                 "Kiểm tra nguồn điện tại điểm (CB, ổ cắm, điện lưới khu vực); nên gắn bộ lưu điện cho modem + nguồn cam",
                 "Thợ điện / đơn vị quản lý điện tại điểm"),
    "modem_vnpt": ("Modem hoặc đường truyền VNPT bị đứt", False,
                   "Kiểm tra modem (nguồn, đèn tín hiệu quang, nhiệt); báo VNPT kiểm tra đường cáp",
                   "Kỹ thuật VNPT / thợ mạng"),
    "cau_hinh": ("Cấu hình sai (NAT / DDNS / mật khẩu)", True,
                 "Sửa cấu hình từ xa bằng CamLink",
                 "Người cấu hình (CamLink)"),
    "cam_treo": ("Cam treo (nhận kết nối nhưng không trả lời)", True,
                 "Khởi động lại cam từ xa; không được thì cắt nguồn cam tại điểm",
                 "CamLink từ xa → thợ cam nếu không được"),
    "cau_hinh_nang": ("Cấu hình cam quá nặng (khung hình/AI/bitrate)", True,
                      "Hạ cấu hình luồng video từ xa",
                      "Người cấu hình (CamLink)"),
    "nguon_day_cam": ("Nguồn rời hoặc dây mạng của riêng cam này", False,
                      "Kiểm tra adaptor, ổ cắm, dây mạng, đầu RJ45 của cam",
                      "Thợ cam tại điểm"),
    "bang_thong": ("Nghẽn băng thông đường lên / quá số người xem", False,
                   "Giảm số nơi xem, IOC kéo luồng phụ, giảm bitrate; nâng gói VNPT nếu cần",
                   "Quản trị IOC / VNPT"),
}

# Mức nền theo kinh nghiệm (chưa có số liệu đo) — được chỉnh theo xác nhận thực tế của dự án
NEN = {"mat_dien": 0.30, "modem_vnpt": 0.25, "cau_hinh": 0.15, "cam_treo": 0.15, "cau_hinh_nang": 0.05,
       "nguon_day_cam": 0.10, "bang_thong": 0.05}

# Bằng chứng → hệ số nhân cho từng nguyên nhân (không có mặt = 1)
BANG_CHUNG = {
    "ca_diem_mat": ("Mọi cam của điểm cùng không trả lời",
                    {"mat_dien": 5, "modem_vnpt": 5, "cau_hinh": 0.1, "cam_treo": 0.1, "cau_hinh_nang": 0.1, "nguon_day_cam": 0.1, "bang_thong": 0.2}),
    "mot_cam_mat": ("Chỉ cam này mất, cam khác cùng điểm vẫn lên",
                    {"mat_dien": 0.05, "modem_vnpt": 0.05, "nguon_day_cam": 6, "cam_treo": 2, "cau_hinh": 1.5}),
    "ip_doi": ("Lên lại với IP mới (modem nối WAN lại)", {"modem_vnpt": 6, "mat_dien": 1.5, "cau_hinh": 0.3}),
    "cam_khoi_dong_ca_diem": ("Nhật ký cam: mọi cam cùng khởi động lại", {"mat_dien": 8, "modem_vnpt": 0.15}),
    "cam_khong_khoi_dong": ("Nhật ký cam: cam KHÔNG khởi động lại trong lúc mất", {"mat_dien": 0.08, "modem_vnpt": 4, "nguon_day_cam": 0.3}),
    "cam_khoi_dong_rieng": ("Nhật ký cam: riêng cam này khởi động lại", {"nguon_day_cam": 6, "cam_treo": 1.5, "mat_dien": 0.2}),
    "treo": ("Cổng nhận kết nối nhưng cam không trả lời", {"cam_treo": 8, "cau_hinh_nang": 2, "mat_dien": 0.05, "modem_vnpt": 0.05}),
    "tu_choi": ("Modem từ chối đúng cổng của cam (thiếu NAT)", {"cau_hinh": 10, "mat_dien": 0.05, "modem_vnpt": 0.1}),
    "sai_mat_khau": ("Cam từ chối user/pass", {"cau_hinh": 20}),
    "dns_sai": ("Tên miền không phân giải / trỏ IP cũ", {"cau_hinh": 3, "modem_vnpt": 2}),
    "phan_hoi_cham": ("Cam trả lời chậm (> 1 giây)", {"cau_hinh_nang": 3, "cam_treo": 1.5, "bang_thong": 1.5}),
    "video_ngat_web_con": ("Web cam còn lên nhưng luồng video đứt", {"bang_thong": 5, "cau_hinh_nang": 3, "cam_treo": 1.5, "mat_dien": 0.05, "modem_vnpt": 0.3, "cau_hinh": 0.3, "nguon_day_cam": 0.3}),
    "rot_ngan_lap": ("Rớt ngắn 0,5–3 phút rồi tự lên (kiểu cam tự khởi động lại)", {"nguon_day_cam": 2, "cam_treo": 1.5, "modem_vnpt": 1.2}),
    "tu_len": ("Tự lên lại không cần sửa", {"cau_hinh": 0.1}),
    "nhieu_diem_cung_luc": ("Nhiều điểm của dự án rớt cùng lúc", {"mat_dien": 3, "modem_vnpt": 3, "cau_hinh": 0.2, "cam_treo": 0.2, "nguon_day_cam": 0.1}),
    # câu trả lời của người tại điểm
    "hien_truong_nguon_cam_tat": ("Người tại điểm: đèn nguồn cam TẮT", {"mat_dien": 10, "nguon_day_cam": 4, "modem_vnpt": 0.1, "cam_treo": 0.1}),
    "hien_truong_nguon_cam_sang": ("Người tại điểm: đèn nguồn cam SÁNG", {"mat_dien": 0.05, "modem_vnpt": 2, "cam_treo": 2}),
    "hien_truong_modem_do": ("Người tại điểm: đèn tín hiệu quang modem ĐỎ / nháy", {"modem_vnpt": 12, "mat_dien": 0.1}),
    "hien_truong_modem_tat": ("Người tại điểm: modem TẮT hẳn", {"mat_dien": 6, "modem_vnpt": 4}),
    "hien_truong_modem_xanh": ("Người tại điểm: modem đèn bình thường", {"modem_vnpt": 0.2, "cau_hinh": 2, "cam_treo": 2, "nguon_day_cam": 2}),
}

CAU_HOI = [  # hỏi người tại điểm khi cả điểm đang mất (2 câu đủ tách điện hay VNPT)
    {"id": "nguon_cam", "hoi": "Đèn nguồn trên cam / adaptor có sáng không?",
     "tra_loi": [["Sáng", "hien_truong_nguon_cam_sang"], ["Tắt", "hien_truong_nguon_cam_tat"], ["Không biết", ""]]},
    {"id": "modem", "hoi": "Đèn trên modem thế nào?",
     "tra_loi": [["Bình thường (xanh)", "hien_truong_modem_xanh"], ["Đèn quang ĐỎ / nháy", "hien_truong_modem_do"],
                 ["Modem tắt hẳn", "hien_truong_modem_tat"], ["Không biết", ""]]},
]

GOC = ""


def khoi_tao(goc):
    global GOC
    GOC = goc


def _f_nen(ma):
    return os.path.join(GOC, "ketqua", f"chandoan_{ma}.json")


def nen_du_an(ma):
    """Mức nền đã chỉnh theo các lần thợ xác nhận nguyên nhân thật của dự án (mỗi xác nhận như 1 lần quan sát, trọng số kinh nghiệm = 10)."""
    nen = dict(NEN)
    try:
        with open(_f_nen(ma), encoding="utf-8") as fh:
            xn = json.load(fh).get("xac_nhan", [])
    except (OSError, ValueError):
        xn = []
    if xn:
        dem = {k: 0 for k in NEN}
        for x in xn:
            if x.get("nguyen_nhan") in dem:
                dem[x["nguyen_nhan"]] += 1
        tong = 10 + len(xn)
        nen = {k: (NEN[k] * 10 + dem[k]) / tong for k in NEN}
    return nen, len(xn)


def xac_nhan(ma, ma_su_co, nguyen_nhan, ghi_chu=""):
    """Thợ xử lý xong bấm "nguyên nhân thật là…" → lưu để chỉnh mức nền của dự án."""
    if nguyen_nhan not in NGUYEN_NHAN:
        raise ValueError("nguyên nhân không hợp lệ")
    f = _f_nen(ma)
    try:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        d = {"xac_nhan": []}
    d["xac_nhan"] = [x for x in d["xac_nhan"] if x.get("su_co") != ma_su_co] + \
        [{"su_co": ma_su_co, "nguyen_nhan": nguyen_nhan, "ghi_chu": ghi_chu, "luc": time.time()}]
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False)
    return len(d["xac_nhan"])


def tinh(bang_chung, ma="", giai_doan="dang_mat"):
    """bang_chung: danh sách mã bằng chứng (có thể kèm chi tiết: [("ip_doi", "113.x → 123.x"), "treo", ...]).
    Trả phiếu chẩn đoán: khả năng từng nguyên nhân (%), bằng chứng, trạng thái nút sửa, việc cần làm, câu hỏi hiện trường."""
    nen, so_xn = nen_du_an(ma) if ma else (dict(NEN), 0)
    diem = dict(nen)
    dung = []
    for b in bang_chung:
        k, ct = (b if isinstance(b, (list, tuple)) else (b, ""))
        if k not in BANG_CHUNG:
            continue
        ten, hs = BANG_CHUNG[k]
        dung.append({"ma": k, "ten": ten, "chi_tiet": ct})
        for nn, h in hs.items():
            diem[nn] *= h
    tong = sum(diem.values()) or 1
    # KHÔNG KHẲNG ĐỊNH (Huan 19:06): một nguyên nhân tối đa 95%, 5% còn lại chia cho các khả năng khác theo tỷ lệ
    top = max(diem, key=diem.get)
    if diem[top] / tong > 0.95:
        con = tong - diem[top]
        if con > 0:
            diem = {k: (0.95 * tong if k == top else v * 0.05 * tong / con) for k, v in diem.items()}
        else:
            diem = {k: (0.95 * tong if k == top else 0.05 * tong / (len(diem) - 1)) for k in diem}
    kn = sorted(({"ma": k, "ten": NGUYEN_NHAN[k][0], "pt": round(100 * v / tong), "tu_xa": NGUYEN_NHAN[k][1],
                  "viec": NGUYEN_NHAN[k][2], "ai": NGUYEN_NHAN[k][3]} for k, v in diem.items()), key=lambda x: -x["pt"])
    # gộp phần nhỏ thành "khác" cho gọn
    chinh = [x for x in kn if x["pt"] >= 5][:4]
    khac = 100 - sum(x["pt"] for x in chinh)
    p_tu_xa = sum(v for k, v in diem.items() if NGUYEN_NHAN[k][1]) / tong
    p_ht = (diem["mat_dien"] + diem["modem_vnpt"]) / tong
    if p_ht >= NGUONG_HIEN_TRUONG:
        nut, loi_nut = "an", "Kiểm tra nguồn điện / modem tại điểm trước — chưa nên sửa từ xa"
    elif p_tu_xa >= NGUONG_SUA:
        nut, loi_nut = "sang", "Khả năng cao sửa được từ xa"
    else:
        nut, loi_nut = "mo", f"Khả năng sửa được từ xa chỉ {round(100 * p_tu_xa)}% — có thể thử nhưng nhiều khả năng phải ra hiện trường"
    co_cam = {b if isinstance(b, str) else b[0] for b in bang_chung}
    hoi = []
    if giai_doan == "dang_mat" and ("ca_diem_mat" in co_cam or "nhieu_diem_cung_luc" in co_cam):
        da_tra_loi = {k for k in co_cam if k.startswith("hien_truong_")}
        hoi = [q for q in CAU_HOI if not any(t[1] in da_tra_loi for t in q["tra_loi"] if t[1])]
    viec_sua = [x["ma"] for x in kn if x["tu_xa"] and x["pt"] >= 10]
    return {"giai_doan": giai_doan, "kha_nang": chinh, "khac": max(0, khac), "bang_chung": dung,
            "p_tu_xa": round(100 * p_tu_xa), "p_hien_truong": round(100 * p_ht), "nut_sua": nut, "loi_nut": loi_nut,
            "viec_sua": viec_sua, "cau_hoi": hoi, "so_xac_nhan": so_xn,
            "ghi_chu": ("Khả năng ước tính từ mức nền kinh nghiệm × bằng chứng đo được" +
                        (f", đã chỉnh theo {so_xn} lần xác nhận thực tế của dự án." if so_xn else "; chưa có xác nhận thực tế nào — bấm \"Nguyên nhân thật là…\" sau khi xử lý để app chính xác dần."))}


def dong_mot_dong(pd):
    """1 dòng gọn cho thông báo / bảng: 'Modem/VNPT 48% · Mất điện 47% · khác 5%'."""
    return " · ".join(f"{x['ten'].split('(')[0].strip()} {x['pt']}%" for x in pd["kha_nang"]) + (f" · khác {pd['khac']}%" if pd["khac"] else "")


# ------------------------------------------------------------------ bằng chứng từ một lần rớt của Theo dõi
def tu_su_kien(su, cung_luc_diem_khac=0):
    """Một lần rớt (theo dõi) → danh sách bằng chứng."""
    b = []
    if su.get("loai") in ("ca_diem", "modem_doi_ip") or (su.get("ti_le_ban_len") is not None and su["ti_le_ban_len"] < 0.3 and su.get("ban_co")):
        b.append("ca_diem_mat")
    elif su.get("ti_le_ban_len") is not None and su["ti_le_ban_len"] >= 0.7:
        b.append("mot_cam_mat")
    if su.get("ip_sau") and su.get("ip_truoc") and su["ip_sau"] != su["ip_truoc"]:
        b.append(("ip_doi", f"{su['ip_truoc']} → {su['ip_sau']}"))
    if su.get("treo", 0) >= 0.5:
        b.append("treo")
    if su.get("tu_choi", 0) >= 0.5:
        b.append("tu_choi")
    if su.get("dns_loi"):
        b.append("dns_sai")
    if su.get("loai") in ("video_ngat", "man_xem_ngat"):
        b.append("video_ngat_web_con")
    kd = su.get("cam_khoi_dong")      # điền bởi đọc nhật ký cam sau khi lên: "ca_diem" / "rieng" / "khong" / None
    if kd == "ca_diem_chua_ro":       # điểm chỉ 1 cam: có khởi động lại nhưng không có cam khác để so
        kd = "ca_diem" if "ca_diem_mat" in b else "rieng"
    if kd == "ca_diem":
        b.append(("cam_khoi_dong_ca_diem", su.get("cam_khoi_dong_luc", "")))
    elif kd == "rieng":
        b.append(("cam_khoi_dong_rieng", su.get("cam_khoi_dong_luc", "")))
    elif kd == "khong":
        b.append("cam_khong_khoi_dong")
    if not su.get("chua_len"):
        b.append("tu_len")                       # lỗi cấu hình không tự hết → giảm mạnh khả năng cấu hình
        if 30 <= su.get("dur", 0) <= 200 and "mot_cam_mat" in b:
            b.append("rot_ngan_lap")
    if cung_luc_diem_khac >= 2:
        b.append(("nhieu_diem_cung_luc", f"{cung_luc_diem_khac} điểm khác"))
    return b


# ------------------------------------------------------------------ bằng chứng từ kết quả Kiểm tra từ xa (một điểm)
def tu_ket_qua_diem(p):
    """Kết quả quét một điểm → {so_cam: bằng chứng} cho từng cam lỗi + bằng chứng chung của điểm."""
    cams = p.get("cam", [])
    hong = [c for c in cams if c.get("muc") != "xanh"]
    if not hong:
        return {}
    ca_diem = len(hong) == len(cams) and all(c.get("t_http") in ("im_lang", "", None) for c in hong)
    ra = {}
    for c in hong:
        b = ["ca_diem_mat"] if ca_diem else (["mot_cam_mat"] if len(hong) < len(cams) else [])
        t = c.get("t_http")
        nhan = (c.get("nhan") or "").lower()
        if t == "tu_choi":
            b.append("tu_choi")
        if "treo" in nhan or "không trả lời" in nhan and t == "mo":
            b.append("treo")
        if "user/pass" in nhan:
            b.append("sai_mat_khau")
        if c.get("ms_http", 0) > 1000:
            b.append("phan_hoi_cham")
        if not p.get("ip"):
            b.append("dns_sai")
        ra[c.get("so")] = b
    return ra


# ------------------------------------------------------------------ sửa từ xa: chỉ đúng thao tác của nguyên nhân có khả năng
VIEC_THEO_NN = {"cau_hinh": ("them_nat", "dat_port_http", "dat_port_rtsp", "khoi_phuc_mang"),
                "cam_treo": ("khoi_dong_cam",)}


def viec_sua(pd, sua_co_san):
    """Từ phiếu chẩn đoán + các thao tác sửa từ xa app có cho cam này → danh sách thao tác sẽ chạy khi bấm "Sửa từ xa"."""
    if pd["nut_sua"] == "an":
        return []
    ra = []
    for nn in pd["viec_sua"]:
        for v in VIEC_THEO_NN.get(nn, ()):
            if v in sua_co_san and v not in ra:
                ra.append(v)
    return ra


# ------------------------------------------------------------------ nhật ký khởi động của cam (ONVIF GetSystemLog)
import re as _re
_TU_KHOA = _re.compile(r"(boot|start ?up|startupdevice|reboot|restart|power ?on|system start|khởi động)", _re.I)
_NGAY = _re.compile(r"(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})[ T_]+(\d{1,2}):(\d{2}):(\d{2})")


def lan_khoi_dong(van_ban):
    """Đọc nhật ký hệ thống của cam → các thời điểm cam khởi động (epoch). Dòng nào có chữ khởi động + ngày giờ thì lấy."""
    ra = []
    for dong in str(van_ban or "").splitlines():
        if not _TU_KHOA.search(dong):
            continue
        m = _NGAY.search(dong)
        if m:
            try:
                ra.append(time.mktime(tuple(int(x) for x in m.groups()) + (0, 0, -1)))
            except (OverflowError, ValueError):
                pass
    return sorted(set(ra))


def xep_khoi_dong(bd, kt, cua_cam, cua_cam_khac):
    """cua_cam: list thời điểm khởi động của cam này (None = không đọc được); cua_cam_khac: list các list của cam khác cùng điểm.
    → "ca_diem" / "rieng" / "khong" / None (không đủ dữ liệu)."""
    if cua_cam is None:
        return None, ""
    cua = [t for t in cua_cam if bd - 120 <= t <= kt + 300]
    khac_doc = [x for x in cua_cam_khac if x is not None]
    khac_kd = [any(bd - 120 <= t <= kt + 300 for t in x) for x in khac_doc]
    if cua:
        luc = time.strftime("%H:%M:%S", time.localtime(cua[0]))
        if khac_doc and all(khac_kd):
            return "ca_diem", luc
        return ("rieng" if khac_doc else "ca_diem_chua_ro"), luc
    return "khong", ""
