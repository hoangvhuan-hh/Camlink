"""HỒ SƠ HỆ THỐNG CAMERA HIỆN TẠI — tự động, có bằng chứng (2.12.20; đổi tên 2.12.21 theo anh Huan: hợp mọi thời điểm, không chỉ lúc nghiệm thu).

Ghép những thứ app ĐÃ CÓ thành một file PDF: ảnh từng cam chụp qua tên miền (như chủ đầu tư / IOC nhìn từ ngoài), giờ chụp,
toạ độ ghim, tên miền + port, kết quả ĐẠT / CHƯA ĐẠT kèm lý do.
2.12.22 (anh Huan 26/11 23:17): mỗi cam có QR = link http kèm user/mật khẩu CAM để quét là vào xem, và in link + user + mật khẩu ra chữ.
Lý do: đây là giai đoạn cài đặt, file chia trong nhóm cài đặt; bên quản lý tiếp quản rồi tự đổi mật khẩu. Bỏ QR LiteMark (người không dùng LiteMark không xem được).
KHÔNG in mật khẩu modem, user/mật khẩu DDNS, đường RTSP; link luôn là http (https qua DDNS thất thường).
2.13.1 (anh Huan 27/11 16:39): QR mở TRANG XEM TRỰC TIẾP của cam (không mở link ảnh chụp — một tấm ảnh không chứng minh cam đang chạy);
ảnh chụp trong báo cáo vẫn giữ; user/mật khẩu cam chỉ nằm trong QR để đăng nhập, KHÔNG in ra chữ (là thứ bên giao cấp cho mình).
Lõi tự gọi sau mỗi lượt kiểm tra từ xa và sau khi cài xong một điểm — người dùng không phải bấm tạo.

du_lieu() là hàm thuần (kiểm được bằng bài thử); ve_pdf() chỉ vẽ đúng những gì du_lieu() trả.
Thiết kế: docs/superpowers/specs/2026-11-26-ho-so-nghiem-thu-design.md
"""
import os
import json
import time
from urllib.parse import quote


TIEU_DE = "HỒ SƠ HỆ THỐNG CAMERA HIỆN TẠI"
THUC_HIEN = "Báo cáo được thực hiện bằng app CamLink"      # anh Huan 27/11: hồ sơ gửi đi đâu cũng mang tên app


def _chi_duong(td):
    """Link chỉ đường Google Maps tới toạ độ ghim (bấm trong PDF hoặc copy dán đều mở chỉ đường). '' nếu ghim chưa có toạ độ.
    Bên nhận hồ sơ không dùng LiteMark vẫn tìm được đường tới điểm."""
    try:
        return f"https://www.google.com/maps/dir/?api=1&destination={float(td[0]):.6f},{float(td[1]):.6f}"
    except (TypeError, ValueError, IndexError):
        return ""


def _so(x):
    return int(x) if str(x).isdigit() else 0


def _gio_tep(f):
    try:
        return time.strftime("%H:%M %d/%m/%Y", time.localtime(os.path.getmtime(f)))
    except OSError:
        return ""


def _link_cam(dom, http, user, pw):
    """(link để đọc, QR để quét) của một cam. Luôn http, luôn theo tên miền + port của cam = trang XEM TRỰC TIẾP của cam.
    Link để đọc không kèm tài khoản; QR kèm user/pass (đã mã hoá ký tự lạ như @ # :) để quét là vào, không phải gõ."""
    if not dom or not http:
        return "", ""
    tk = f"{quote(str(user), safe='')}:{quote(str(pw), safe='')}@" if user else ""
    return f"http://{dom}:{http}/", f"http://{tk}{dom}:{http}/"


def du_lieu(goc, ma):
    """Nội dung hồ sơ của một dự án: {du_an, lap_luc, kiem_luc, tong{dinh_vi, modem, cam, dat, chua}, diem[...]}.
    Mỗi GHIM một mục; cam nằm ở ghim khác ghim đặt modem thì hiện ở mục của ghim nó."""
    import camlink_core as K
    import camlink_tuxa as T
    import camlink_dt as C
    da = K._doc_du_an(ma)
    diem, td = da.get("diem", {}), da.get("toa_do", {})
    try:
        with open(T._f_lich_su(goc, ma), encoding="utf-8") as fh:
            kq = json.load(fh)
    except (OSError, ValueError):
        kq = {}
    ls = {str(p.get("stt")): p for p in kq.get("diem") or []}

    def cam_cua_modem(a):
        """Mọi cam trên modem của điểm a, theo bằng chứng mới nhất: lượt kiểm tra từ xa → bằng chứng lúc cài → chưa có gì."""
        out = {}
        p = ls.get(a)
        if p:
            for c in p.get("cam") or []:
                dat_ = c.get("muc") == "xanh"
                f = c.get("anh") or ""
                f = f if f and os.path.exists(f) else ""
                out[_so(c.get("so"))] = {"so": _so(c.get("so")), "http": c.get("http"), "rtsp": c.get("rtsp"), "dat": dat_,
                                         "ly_do": "" if dat_ else (c.get("nguyen_nhan") or c.get("nhan") or p.get("tong") or "chưa xem được"),
                                         "anh": f, "gio": (_gio_tep(f) if f else "") or str(kq.get("luc", "")),
                                         "_tk": (c.get("user") or "", c.get("pass") or "")}
        else:
            try:
                with open(K._file_so_do(ma, a), encoding="utf-8") as fh:
                    sd = json.load(fh)
            except (OSError, ValueError):
                sd = {}
            for c in sd.get("cam") or []:
                f = c.get("anh") or ""
                f = f if f and os.path.exists(f) else ""
                dat_ = bool(c.get("ngoai"))
                out[_so(c.get("so"))] = {"so": _so(c.get("so")), "http": c.get("http"), "rtsp": c.get("rtsp"), "dat": dat_,
                                         "ly_do": "" if dat_ else (c.get("loi_ngoai") or "chưa xem được qua tên miền"),
                                         "anh": f, "gio": str(sd.get("luc", ""))}
        can = max([_so(diem[a].get("so"))] + list(T.cam_chung(da, a)) + [0])      # số cam phải có trên modem này
        for n in range(1, can + 1):
            if n not in out:
                out[n] = {"so": n, "http": C_HTTP(n), "rtsp": C_RTSP(n), "dat": False,
                          "ly_do": "chưa cài" if not K.diem_da_cai(da, a, K._lich_su_kiem(ma)) else "chưa có lượt kiểm tra nào thấy cam này",
                          "anh": "", "gio": ""}
        cd = C.cd_diem(diem[a], C.doc_cai_dat())          # user/pass cam của điểm này (riêng của điểm nếu có, không thì của hệ thống)
        dom = diem[a].get("domain", "")
        for c in out.values():
            u, p = c.pop("_tk", ("", ""))      # tài khoản cam chỉ đi vào QR, không giữ trong dữ liệu để khỏi bị in ra chữ
            c["link"], c["qr"] = _link_cam(dom, c.get("http"), u or cd.get("cam_user", "admin"), p or cd.get("cam_pw", ""))
        return out

    ds = []
    for k in sorted(diem, key=_so):
        d = diem[k]
        c = K._chung(d)
        a = str(c["stt"]) if c else k
        tat_ca = cam_cua_modem(a) if a in diem else {}
        cua_ghim_khac = T.cam_chung(da, a)
        if c:
            cams = [tat_ca[n] for n in sorted(tat_ca) if cua_ghim_khac.get(n) == k]
            ghi = f"Dùng chung modem với điểm {a}. {diem.get(a, {}).get('ten', '')}"
        else:
            cams = [tat_ca[n] for n in sorted(tat_ca) if n not in cua_ghim_khac]
            ghi = ""
        dom = diem.get(a, {}).get("domain", "")
        ds.append({"stt": k, "ten": d.get("ten", ""), "toa_do": td.get(k) or [], "chi_duong": _chi_duong(td.get(k) or []), "domain": dom, "ghi_chu": ghi, "cam": cams})
    modem = [k for k in diem if not K._chung(diem[k])]
    tat = [c for p in ds for c in p["cam"]]
    return {"tieu_de": TIEU_DE, "thuc_hien": THUC_HIEN, "ma": ma, "du_an": da.get("ten", ""), "lap_luc": time.strftime("%H:%M %d/%m/%Y"), "kiem_luc": str(kq.get("luc", "")),
            "tong": {"dinh_vi": len(diem), "modem": len(modem), "cam": len(tat), "dat": sum(1 for c in tat if c["dat"]),
                     "chua": sum(1 for c in tat if not c["dat"])},
            "diem": ds}


def C_HTTP(n):
    import camlink_dt as C
    return C.HTTP[n - 1] if 1 <= n <= len(C.HTTP) else None


def C_RTSP(n):
    import camlink_dt as C
    return C.RTSP[n - 1] if 1 <= n <= len(C.RTSP) else None


def tep(goc, ma):
    return os.path.join(goc, "ketqua", f"HoSo_HeThongCamera_{ma}.pdf")


def ve_pdf(m, duong):
    """Vẽ đúng những gì du_lieu() trả: 1 trang tổng + mỗi ghim một trang."""
    import camlink_theodoi as TD
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.barcode.qr import QrCodeWidget
    thuong, dam = TD._font()
    XANH, DO, MO, VIEN = colors.HexColor("#067647"), colors.HexColor("#B42318"), colors.HexColor("#5B6776"), colors.HexColor("#C9D1DA")
    st = lambda co, f=thuong, mau=colors.black, giua=0: ParagraphStyle("x", fontName=f, fontSize=co, leading=co * 1.35, textColor=mau, alignment=giua)
    P = lambda s, co=10, f=thuong, mau=colors.black, giua=0: Paragraph(str(s).replace("&", "&amp;").replace("<", "&lt;"), st(co, f, mau, giua))
    khung = lambda cot_dam=True: TableStyle([("GRID", (0, 0), (-1, -1), 0.5, VIEN), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF1F4")),
                                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)])
    t, e = m["tong"], []
    R_ANH, R_QR = 74 * mm, 30 * mm
    # ---------------- trang tổng
    e += [P(m.get("tieu_de") or TIEU_DE, 16, dam, giua=1), Spacer(1, 2 * mm), P(m["du_an"], 13, dam, giua=1), Spacer(1, 1.5 * mm),
          P(m["thuc_hien"], 9.5, mau=MO, giua=1), Spacer(1, 3 * mm),
          P(f"Lập lúc {m['lap_luc']}" + (f"   ·   Lượt kiểm tra gần nhất: {m['kiem_luc']}" if m["kiem_luc"] else ""), 9.5, mau=MO, giua=1), Spacer(1, 5 * mm)]
    du = t["chua"] == 0 and t["cam"] > 0
    e += [P(f"{t['dinh_vi']} định vị   ·   {t['cam']} cam   ·   {t['modem']} modem", 12, dam, giua=1), Spacer(1, 1.5 * mm),
          P(f"ĐẠT {t['dat']}/{t['cam']} cam" + ("" if du else f"   ·   CHƯA ĐẠT {t['chua']} cam"), 13, dam, XANH if du else DO, giua=1), Spacer(1, 2 * mm),
          P("Ảnh trong hồ sơ được chụp qua tên miền của từng điểm, từ ngoài mạng (4G) — đúng như đơn vị sử dụng nhìn từ xa.", 9, mau=MO, giua=1), Spacer(1, 1 * mm),
          P("Quét mã QR cạnh từng cam để vào xem trực tiếp cam đó. Mỗi điểm có link chỉ đường Google Maps. Tài liệu dành cho nhóm cài đặt.", 9, mau=MO, giua=1), Spacer(1, 5 * mm)]
    dong = [[P(x, 9, dam) for x in ("STT", "Vị trí", "Tên miền", "Cam", "Kết quả")]]
    for p in m["diem"]:
        n, ok = len(p["cam"]), sum(1 for c in p["cam"] if c["dat"])
        dong.append([P(p["stt"], 9), P(p["ten"] + (f" ({p['ghi_chu'].lower()})" if p["ghi_chu"] else ""), 9), P(p["domain"] or "—", 9), P(n, 9),
                     P(f"ĐẠT {ok}/{n}" if n and ok == n else (f"CHƯA ĐẠT {n - ok}/{n}" if n else "chưa có cam"), 9, dam, XANH if n and ok == n else DO)])
    b = Table(dong, colWidths=[12 * mm, 58 * mm, 56 * mm, 16 * mm, 36 * mm], repeatRows=1)
    b.setStyle(khung())
    e += [b, Spacer(1, 10 * mm)]
    ky = Table([[P("BÊN GIAO (đơn vị thi công)", 10, dam, giua=1), P("BÊN NHẬN", 10, dam, giua=1)],
                [P("(ký, ghi rõ họ tên)", 8.5, mau=MO, giua=1), P("(ký, ghi rõ họ tên)", 8.5, mau=MO, giua=1)]], colWidths=[89 * mm, 89 * mm])
    e.append(ky)
    # ---------------- mỗi ghim một trang
    for p in m["diem"]:
        e.append(PageBreak())
        n, ok = len(p["cam"]), sum(1 for c in p["cam"] if c["dat"])
        e += [P(f"Điểm {p['stt']}. {p['ten']}", 14, dam), Spacer(1, 1.5 * mm),
              P(f"ĐẠT {ok}/{n} cam" if n and ok == n else (f"CHƯA ĐẠT {n - ok}/{n} cam" if n else "Chưa có cam"), 11, dam, XANH if n and ok == n else DO), Spacer(1, 2 * mm)]
        dong_tt = []
        if p["toa_do"]:
            dong_tt.append(f"Toạ độ: {p['toa_do'][0]:.6f}, {p['toa_do'][1]:.6f}")
        if p["chi_duong"]:      # bấm được trong PDF; in cả link ra chữ để copy
            e.append(Paragraph(f'Toạ độ: {p["toa_do"][0]:.6f}, {p["toa_do"][1]:.6f}   ·   <a href="{p["chi_duong"].replace("&", "&amp;")}" color="#175CD3"><u>Chỉ đường (Google Maps)</u></a>', st(10)))
            e.append(Paragraph(f'<a href="{p["chi_duong"].replace("&", "&amp;")}" color="#175CD3">{p["chi_duong"].replace("&", "&amp;")}</a>', st(8.5)))
            dong_tt.pop()
        if p["domain"]:
            dong_tt.append(f"Tên miền: {p['domain']}")
        if p["ghi_chu"]:
            dong_tt.append(p["ghi_chu"])
        for s in dong_tt:
            e.append(P(s, 10))
        e.append(Spacer(1, 3 * mm))
        if p["cam"]:
            dc = [[P(x, 9, dam) for x in ("Cam", "Port web", "Port video", "Kết quả", "Giờ chụp / lý do")]]
            for c in p["cam"]:
                dc.append([P(f"Cam {c['so']}", 9), P(c["http"] or "—", 9), P(c["rtsp"] or "—", 9),
                           P("ĐẠT" if c["dat"] else "CHƯA ĐẠT", 9, dam, XANH if c["dat"] else DO), P(c["gio"] if c["dat"] else c["ly_do"], 9)])
            bc = Table(dc, colWidths=[18 * mm, 24 * mm, 26 * mm, 28 * mm, 82 * mm], repeatRows=1)
            bc.setStyle(khung())
            e += [bc, Spacer(1, 4 * mm)]
        # mỗi cam một hàng: ảnh chụp | QR xem trực tiếp | link (chữ, không kèm tài khoản)
        hang = []
        for c in p["cam"]:
            if not (c["anh"] or c.get("qr")):
                continue
            o_anh = P("(chưa có ảnh)", 8.5, mau=MO)
            if c["anh"]:
                try:
                    im = Image(c["anh"])
                    ti = im.imageHeight / float(im.imageWidth or 1)
                    im.drawWidth, im.drawHeight = R_ANH, min(R_ANH * ti, 42 * mm)
                    o_anh = im
                except Exception:
                    o_anh = P("không đọc được ảnh", 8.5, mau=DO)
            o_qr = ""
            if c.get("qr"):
                w = QrCodeWidget(c["qr"])
                x0, y0, x1, y1 = w.getBounds()
                o_qr = Drawing(R_QR, R_QR, transform=[R_QR / (x1 - x0), 0, 0, R_QR / (y1 - y0), 0, 0])
                o_qr.add(w)
            chu = [P(f"Cam {c['so']}" + (f" — chụp {c['gio']}" if c["anh"] and c["gio"] else ""), 9.5, dam)]
            if c.get("link"):
                chu += [P("Quét mã để xem trực tiếp cam này", 8.5, mau=MO), P(c["link"], 9)]
            hang.append([o_anh, o_qr, chu])
        if hang:
            e.append(Table(hang, colWidths=[R_ANH + 4 * mm, R_QR + 4 * mm, 178 * mm - R_ANH - R_QR - 8 * mm],
                           style=TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -2), 0.5, VIEN),
                                             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)])))
    os.makedirs(os.path.dirname(duong), exist_ok=True)
    tam = duong + ".tam"
    def chan(cv, doc):      # chân mọi trang: tên app + số trang
        cv.saveState()
        cv.setFont(thuong, 8)
        cv.setFillColor(MO)
        cv.drawString(16 * mm, 8 * mm, m["thuc_hien"])
        cv.drawRightString(A4[0] - 16 * mm, 8 * mm, f"Trang {doc.page}")
        cv.restoreState()

    SimpleDocTemplate(tam, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=14 * mm,
                      title=f"Hồ sơ hệ thống camera hiện tại — {m['du_an']}", author="CamLink").build(e, onFirstPage=chan, onLaterPages=chan)
    os.replace(tam, duong)
    return duong


def tao(goc, ma):
    return ve_pdf(du_lieu(goc, ma), tep(goc, ma))
