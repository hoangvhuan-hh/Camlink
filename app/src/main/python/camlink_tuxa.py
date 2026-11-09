"""Kiểm tra từ xa cả dự án theo 5 tầng + sửa từ xa.
Tầng: 1 tên miền · 2 IP trỏ về · 3 đường truyền điểm · 4 port từng cam · 5 hình ảnh.
Chỉ ĐỌC, trừ khi người dùng bấm nút Sửa."""
import errno, ipaddress, json, os, socket, time
from concurrent.futures import ThreadPoolExecutor
import camlink_dt as C
import camlink_oryza

PORT_MODEM = [8888, 8000, 443, 80, 7547]   # cổng quản trị modem có thể mở ra Internet

XANH, VANG, DO = "xanh", "vang", "do"


TEN_CHAM = {"mo": "MỞ (có thiết bị trả lời)", "tu_choi": "BỊ TỪ CHỐI (modem trả lời nhưng không có gì ở port này)",
            "im_lang": "KHÔNG TRẢ LỜI"}


def cham_tg(host, port, cho=4):
    t0 = time.time()
    r = cham(host, port, cho)
    return r, int((time.time() - t0) * 1000)


def cham(host, port, cho=4):
    """'mo' | 'tu_choi' (máy có trả lời nhưng không có gì ở port) | 'im_lang' (không trả lời)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(cho)
    try:
        s.connect((host, port))
        return "mo"
    except ConnectionRefusedError:
        return "tu_choi"
    except OSError as e:
        return "tu_choi" if getattr(e, "errno", None) in (errno.ECONNREFUSED,) else "im_lang"
    finally:
        s.close()


def _ip_noi_bo(ip):
    if os.environ.get("CAMLINK_THU_NOI_BO"):
        return False
    a = ipaddress.ip_address(ip)
    return a.is_private or a in ipaddress.ip_network("100.64.0.0/10")


def _ket(cam, muc, nguyen_nhan, viec, sua=None, nhan=""):
    cam.update(muc=muc, nguyen_nhan=nguyen_nhan, viec=viec, sua=sua or [], nhan=nhan)
    return cam


def kiem_diem(stt, d, cd, anh_dir, ma, ho_so=None):
    dom = d["domain"]
    cu, cp = cd.get("cam_user", "admin"), cd.get("cam_pw", "")
    so_file = max(int(d.get("so") or 0), 1)
    if d.get("so_thuc"):
        so, nguon_so = int(d["so_thuc"]), "số cam thực tế đã sửa trong app"
    elif ho_so and ho_so.get("cam"):
        so, nguon_so = len(ho_so["cam"]), "số cam tìm thấy lúc cài"
    else:
        so, nguon_so = so_file, "số cam theo file khảo sát (Camera + Camera BS)"
    luc = time.strftime("%H:%M:%S %d/%m/%Y")
    kq = {"stt": stt, "ten": d["ten"], "domain": dom, "noip_user": d.get("u", ""), "noip_pass": d.get("p", ""),
          "ip": "", "tong": "", "muc": XANH, "viec": [], "web_modem": "", "cam": [], "luc": luc,
          "so": so, "so_file": so_file, "nguon_so": nguon_so}
    cams = [{"so": i + 1, "http": C.HTTP[i], "rtsp": C.RTSP[i], "web": f"http://{dom}:{C.HTTP[i]}",
             "live": f"rtsp://{cu}:{cp}@{dom}:{C.RTSP[i]}/", "user": cu, "pass": cp, "anh": "", "hang": "", "model": "",
             "t_http": "", "t_rtsp": "", "ms_http": 0, "ms_rtsp": 0, "onvif": "", "bang_chung": []} for i in range(so)]
    kq["cam"] = cams

    def ca_diem(muc, tong, nguyen, viec):
        kq.update(muc=muc, tong=tong, viec=viec)
        for c in cams:
            _ket(c, muc, nguyen, viec, nhan=tong)
        return _xong(kq)

    # Tầng 1 — tên miền
    try:
        ip = socket.gethostbyname(dom)
    except OSError:
        return ca_diem(DO, "TÊN MIỀN KHÔNG HOẠT ĐỘNG", f"{dom} không phân giải được",
                       ["Đăng nhập noip.com bằng tài khoản No-IP của điểm (bấm cam để xem user/pass) → kiểm tra tên miền còn không, bấm Confirm gia hạn (gói miễn phí hết hạn sau 30 ngày nếu không xác nhận).",
                        "Nếu tên miền còn: kiểm tra điện thoại có Internet rồi kiểm tra lại."])
    kq["ip"] = ip
    # Tầng 2 — IP trỏ về
    if _ip_noi_bo(ip):
        return ca_diem(DO, "TÊN MIỀN TRỎ IP NỘI BỘ", f"{dom} → {ip} (IP nội bộ, Internet không vào được)",
                       ["DDNS trên cam 1 đang gửi sai IP: ra điểm chạy lại CamLink để nhập lại DDNS.",
                        "Nếu IP dạng 100.64–100.127.x.x: nhà mạng đang cấp IP nội bộ (CGNAT) → gọi VNPT 18001166 xin IP public cho đường truyền.",
                        "Nhà mạng không cấp IP public: lắp router có VPN dự phòng tại điểm (khoảng 0,5–1,5 triệu) để vẫn xem và sửa từ xa được."])

    # Tầng 3–4 — đường truyền + port từng cam (chạm song song)
    viec_cham = [(c, "t_http", c["http"]) for c in cams] + [(c, "t_rtsp", c["rtsp"]) for c in cams]
    with ThreadPoolExecutor(8) as ex:
        for (c, k, _), (r, ms) in zip(viec_cham, ex.map(lambda x: cham_tg(dom, x[2]), viec_cham)):
            c[k] = r
            c["ms" + k[1:]] = ms
    cong_cam = {c["http"] for c in cams} | {c["rtsp"] for c in cams}
    for p in PORT_MODEM:
        if p not in cong_cam and cham(dom, p, 3) == "mo":
            kq["web_modem"] = f"{'https' if p == 443 else 'http'}://{dom}:{p}"
            break
    song = kq["web_modem"] or any(c["t_http"] != "im_lang" or c["t_rtsp"] != "im_lang" for c in cams)
    if not song:
        viec = ["Gọi người tại điểm kiểm tra đèn nguồn tủ điện và modem.",
                "Modem sáng đèn LOS đỏ → gọi VNPT 18001166 báo đứt cáp quang.",
                "Chỉ cử thợ ra khi 2 bước trên không xử lý được."]
        if ho_so and ho_so.get("wan") and ho_so["wan"] != ip:
            viec.insert(0, f"Lưu ý: tên miền đang trỏ {ip}, lúc cài là {ho_so['wan']} → có thể cam 1 mất nguồn nên DDNS không cập nhật IP mới.")
        return ca_diem(DO, "MẤT ĐIỆN / MẤT MẠNG CẢ ĐIỂM", "modem và mọi cam đều không trả lời", viec)

    # Tầng 4–5 — từng cam
    for c in cams:
        if c["t_http"] == "tu_choi":
            _ket(c, VANG, f"Modem có mạng nhưng từ chối port {c['http']} → chưa có luật mở port (NAT) cho cam {c['so']}",
                 [f"Bấm Sửa từ xa để thêm luật NAT {c['http']}/{c['rtsp']} → 192.168.1.{C.IP_TU + c['so'] - 1} (cần vào được web modem).",
                  "Không vào được web modem: ra điểm chạy lại CamLink."], ["them_nat"], "Thiếu luật mở port (NAT)")
            continue
        if c["t_http"] == "im_lang":
            _ket(c, DO, f"Modem có mạng nhưng cam {c['so']} không trả lời → cam mất nguồn, lỏng dây mạng, hoặc bị đổi IP",
                 [f"Gọi người tại điểm kiểm tra đèn nguồn cam {c['so']} và dây mạng/PoE.",
                  "Nếu cam vẫn sáng: có thể cam bị reset về IP mặc định → ra điểm chạy lại CamLink.",
                  "Có web modem: bấm Sửa từ xa để khởi động lại modem."], ["khoi_dong_modem"], "Cam mất nguồn / lỏng dây")
            continue
        ov = C.Onvif(dom, c["http"], cu, cp)
        c["onvif"] = "không trả lời"
        if not ov.co():
            _ket(c, VANG, f"Port {c['http']} mở nhưng không phải cam trả lời (ONVIF tắt hoặc cam treo)",
                 [f"Mở web {c['web']} xem có vào được không.", "Bấm Sửa từ xa để khởi động lại modem; còn lỗi thì ra điểm khởi động lại cam."],
                 ["khoi_dong_modem"], "Port mở nhưng cam không trả lời")
            continue
        try:
            tt = ov.thong_tin()
            c["hang"], c["model"] = tt.get("hang", ""), tt.get("model", "")
            c["onvif"] = "đăng nhập được"
        except Exception:
            c["onvif"] = "trả lời nhưng TỪ CHỐI user/pass"
            _ket(c, VANG, "Cam có mạng nhưng user/pass cam lưu trong app SAI",
                 ["Sửa user/pass cam ở nút \"User / pass cam và modem\" rồi kiểm tra lại.",
                  "Nếu pass đúng mà vẫn báo: có người đã đổi pass cam → hỏi đơn vị quản lý."], nhan="Sai user/pass cam")
            continue
        try:
            um = ov.url_media()
            tk = ov.profile_dau(um)
            jpg = ov.anh_chup(um, tk)
            f = os.path.join(anh_dir, f"tuxa_{ma}_{stt}_cam{c['so']}.jpg")
            with open(f, "wb") as fh:
                fh.write(jpg)
            c["anh"] = f
            try:
                c["live"] = ov.luong_video(um, tk, c["rtsp"])
            except Exception:
                pass
        except Exception as e:
            _ket(c, VANG, f"Cam trả lời nhưng không ra hình ({str(e)[:60]}) → cam treo",
                 ["Bấm Sửa từ xa để khởi động lại cam, chờ 2 phút rồi kiểm tra lại."], ["khoi_dong_cam"], "Cam treo")
            continue
        if c["t_rtsp"] != "mo":
            sua = ["dat_port_rtsp"]
            try:
                p = ov.doc_port().get("RTSP")
                lech = p and p != c["rtsp"]
            except Exception:
                lech = False
            if lech:
                _ket(c, VANG, f"Có hình nhưng cam đang dùng RTSP {p} thay vì {c['rtsp']} → IOC không xem được video",
                     [f"Bấm Sửa từ xa để đặt lại RTSP {c['rtsp']} cho cam."], sua, "Cam đổi port RTSP")
            else:
                _ket(c, VANG, f"Có hình nhưng port RTSP {c['rtsp']} chưa mở trên modem → IOC không xem được video",
                     [f"Bấm Sửa từ xa để thêm luật NAT {c['rtsp']} (cần vào được web modem)."], ["them_nat"], "Thiếu NAT RTSP")
            continue
        _ket(c, XANH, "Xem được từ ngoài: có ảnh chụp qua tên miền, port HTTP + RTSP mở", [], nhan="Đạt")
    hong = [c for c in cams if c["muc"] != XANH]
    kq["muc"] = DO if any(c["muc"] == DO for c in cams) else (VANG if hong else XANH)
    kq["tong"] = "ĐẠT" if not hong else f"{len(cams) - len(hong)}/{len(cams)} cam đạt"
    return _xong(kq)


def _xong(kq):
    """Ghi bằng chứng cho từng cam: vào được hay không vào được đều có dữ kiện cụ thể."""
    for c in kq["cam"]:
        b = [f"Kiểm lúc {kq['luc']} qua Internet",
             f"Tên miền {kq['domain']} → " + (kq["ip"] or "KHÔNG PHÂN GIẢI ĐƯỢC")]
        if c.get("t_http"):
            b.append(f"Port web {c['http']}: {TEN_CHAM[c['t_http']]} — {c['ms_http']} ms")
            b.append(f"Port video RTSP {c['rtsp']}: {TEN_CHAM[c['t_rtsp']]} — {c['ms_rtsp']} ms")
        if c.get("onvif"):
            b.append(f"ONVIF: {c['onvif']}" + (f" — {c['hang']} {c['model']}".rstrip() if c.get("model") else ""))
        if c.get("anh") and os.path.exists(c["anh"]):
            b.append(f"ẢNH CHỤP qua {kq['domain']}:{c['http']} — {os.path.getsize(c['anh']) // 1024} KB")
        elif c["muc"] != XANH:
            b.append("KHÔNG lấy được ảnh")
        c["bang_chung"] = b
    if kq.get("so") != kq.get("so_file"):
        kq["ghi_so"] = f"File khảo sát ghi {kq['so_file']} cam, đang kiểm {kq['so']} cam ({kq['nguon_so']})"
    else:
        kq["ghi_so"] = f"Kiểm {kq['so']} cam ({kq['nguon_so']})"
    return kq


# ------------------------------------------------------------------ cả dự án
def _f_lich_su(goc, ma):
    return os.path.join(goc, "ketqua", f"tuxa_{ma}.json")


def kiem_du_an(goc, da, ma, cd, log=print, chi_diem=None):
    anh_dir = os.path.join(goc, "ketqua")
    os.makedirs(anh_dir, exist_ok=True)
    diem = da["diem"]
    ds = [k for k in diem if not chi_diem or k in chi_diem]
    ho_so = da.get("ho_so", {})
    log(f"KIỂM TRA TỪ XA — {da['ten']}: {len(ds)} điểm (chỉ đọc, qua Internet)")
    t0 = time.time()

    def mot(k):
        try:
            r = kiem_diem(k, diem[k], cd, anh_dir, ma, ho_so.get(k))
        except Exception as e:
            r = {"stt": k, "ten": diem[k]["ten"], "domain": diem[k]["domain"], "muc": DO, "tong": f"LỖI KIỂM TRA: {e}",
                 "viec": ["Kiểm tra lại."], "cam": [], "ip": "", "web_modem": "", "noip_user": "", "noip_pass": ""}
        bieu = {"xanh": "🟢", "vang": "🟡", "do": "🔴"}[r["muc"]]
        log(f" {bieu} {k}. {r['ten']} — {r['tong']}")
        return r

    with ThreadPoolExecutor(6) as ex:
        kqs = list(ex.map(mot, ds))
    # so với lần trước
    f = _f_lich_su(goc, ma)
    truoc = {}
    try:
        with open(f, encoding="utf-8") as fh:
            truoc = json.load(fh)
    except (OSError, ValueError):
        pass
    tr_cam = {(p["stt"], c["so"]): c.get("muc") for p in truoc.get("diem", []) for c in p.get("cam", [])}
    for p in kqs:
        for c in p["cam"]:
            cu_m = tr_cam.get((p["stt"], c["so"]))
            c["vua_rot"] = cu_m == XANH and c["muc"] != XANH
            c["vua_len"] = cu_m is not None and cu_m != XANH and c["muc"] == XANH
    tong_cam = sum(len(p["cam"]) for p in kqs)
    dat = sum(1 for p in kqs for c in p["cam"] if c["muc"] == XANH)
    dem = {}
    for p in kqs:
        if p["muc"] == DO and not any(c["muc"] == XANH for c in p["cam"]) and p["tong"].isupper():
            dem[p["tong"]] = dem.get(p["tong"], 0) + 1   # lỗi cả điểm: đếm theo điểm
        else:
            for c in p["cam"]:
                if c["muc"] != XANH:
                    dem[c["nhan"]] = dem.get(c["nhan"], 0) + 1
    out = {"du_an": da["ten"], "ma": ma, "luc": time.strftime("%d/%m/%Y %H:%M"), "giay": round(time.time() - t0),
           "tong_cam": tong_cam, "dat": dat, "rot": sum(1 for p in kqs for c in p["cam"] if c.get("vua_rot")),
           "nhom_loi": dem, "diem": sorted(kqs, key=lambda p: (int(p["stt"]) if str(p["stt"]).isdigit() else 0))}
    if not chi_diem:
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False)
    log(f"→ {dat}/{tong_cam} cam đạt · {out['rot']} cam vừa rớt so với lần trước · {out['giay']} giây")
    return out


def xuat_excel(goc, ket_qua):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Kiem tra tu xa"
    ws.append([f"KIỂM TRA TỪ XA — {ket_qua['du_an']} — {ket_qua['luc']} — {ket_qua['dat']}/{ket_qua['tong_cam']} cam đạt"])
    ws["A1"].font = Font(bold=True, size=13)
    tieu = ["No", "Tên điểm", "Domain", "Cam", "Trạng thái", "Ảnh chụp (bằng chứng)", "Bằng chứng kết nối", "Nguyên nhân",
            "Việc tiếp theo", "Link web", "Link xem trực tiếp", "User cam", "Pass cam", "User No-IP", "Pass No-IP",
            "Web modem", "Vừa rớt", "Số cam"]
    ws.append(tieu)
    for c in ws[2]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="0F5D8C")
    mau = {"xanh": "D9F2E3", "vang": "FFF1C7", "do": "FBD9D5"}
    chu = {"xanh": "ĐẠT", "vang": "LỖI CẤU HÌNH", "do": "LỖI PHẦN CỨNG / MẠNG"}
    try:
        from openpyxl.drawing.image import Image as XImg
        from PIL import Image as PImg
    except Exception:
        XImg = None
    for p in ket_qua["diem"]:
        for c in p["cam"]:
            ws.append([p["stt"], p["ten"], p["domain"], c["so"], chu[c["muc"]], "" if c.get("anh") else "KHÔNG CÓ ẢNH",
                       "\n".join(c.get("bang_chung", [])), c.get("nguyen_nhan", ""),
                       "\n".join(f"{i + 1}) {v}" for i, v in enumerate(c.get("viec", []))), c["web"], c["live"],
                       c["user"], c["pass"], p.get("noip_user", ""), p.get("noip_pass", ""), p.get("web_modem", ""),
                       "CÓ" if c.get("vua_rot") else "", p.get("ghi_so", "")])
            dong = ws.max_row
            for cell in ws[dong]:
                cell.fill = PatternFill("solid", fgColor=mau[c["muc"]])
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            ws.row_dimensions[dong].height = 125
            ws.cell(dong, 10).hyperlink = c["web"]
            ws.cell(dong, 10).font = Font(color="0B57D0", underline="single")
            if p.get("web_modem"):
                ws.cell(dong, 16).hyperlink = p["web_modem"]
                ws.cell(dong, 16).font = Font(color="0B57D0", underline="single")
            a = c.get("anh")
            if XImg and a and os.path.exists(a):
                try:
                    nho = a[:-4] + "_nho.png"
                    im = PImg.open(a)
                    im.thumbnail((210, 160))
                    im.save(nho)
                    ws.add_image(XImg(nho), f"F{dong}")
                except Exception:
                    ws.cell(dong, 6, "có ảnh (không nhúng được)")
    for col, w in zip("ABCDEFGHIJKLMNOPQR", [5, 24, 26, 5, 13, 31, 52, 40, 56, 28, 38, 10, 12, 12, 14, 24, 8, 30]):
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A3"
    f = os.path.join(goc, "ketqua", f"KiemTraTuXa_{ket_qua['ma']}_{time.strftime('%Y%m%d_%H%M')}.xlsx")
    wb.save(f)
    return f


# ------------------------------------------------------------------ sửa từ xa
TEN_SUA = {"khoi_dong_cam": "Khởi động lại cam", "dat_port_rtsp": "Đặt lại port RTSP cho cam",
           "them_nat": "Thêm luật mở port trên modem", "khoi_dong_modem": "Khởi động lại modem",
           "nhap_lai_ddns": "Nhập lại DDNS trên cam 1"}


def sua(d, so, viec, cd, log=print):
    """Trả (ok, thông báo). Modem: cần lệnh theo model modem (chờ mẫu VNPT)."""
    dom = d["domain"]
    i = int(so) - 1
    http, rtsp = C.HTTP[i], C.RTSP[i]
    ov = C.Onvif(dom, http, cd.get("cam_user", "admin"), cd.get("cam_pw", ""))
    try:
        if viec == "khoi_dong_cam":
            ov.co()
            ov.khoi_dong()
            log(f"Đã gửi lệnh khởi động lại cam {so} qua {dom}:{http}. Chờ khoảng 2 phút …")
            if C.cho_len(dom, http, 180):
                return True, f"Cam {so} đã lên lại sau khởi động — bấm Kiểm tra lại để xem hình."
            return False, f"Cam {so} chưa lên lại sau 3 phút → ra điểm kiểm tra nguồn cam."
        if viec == "dat_port_rtsp":
            ov.co()
            ov.dat_port(http, rtsp)
            log(f"Đã đặt HTTP {http} / RTSP {rtsp} cho cam {so}. Chờ cam áp dụng …")
            for _ in range(20):
                if C.mo(dom, rtsp, 3):
                    return True, f"RTSP {rtsp} của cam {so} đã mở."
                time.sleep(3)
            return False, f"Đã đặt lại nhưng RTSP {rtsp} vẫn chưa mở từ ngoài → modem thiếu luật NAT {rtsp}."
        if viec == "nhap_lai_ddns":
            if not camlink_oryza.la_oryza(dom, http):
                return False, "Cam 1 không phải Oryza hoặc không vào được — chưa hỗ trợ nhập DDNS từ xa cho hãng này."
            return True, camlink_oryza.dat_ddns(dom, http, cd.get("cam_user", "admin"), cd.get("cam_pw", ""),
                                                dom, d.get("u", ""), d.get("p", ""))
        if viec in ("them_nat", "khoi_dong_modem"):
            return False, ("App chưa có lệnh điều khiển modem VNPT từ xa (đang chờ mẫu modem). Tạm thời: "
                           + ("ra điểm chạy lại CamLink để mở port." if viec == "them_nat"
                              else "nhờ người tại điểm rút điện modem 10 giây rồi cắm lại."))
        return False, f"Không có thao tác {viec}"
    except Exception as e:
        return False, f"{TEN_SUA.get(viec, viec)} lỗi: {str(e)[:120]}"
