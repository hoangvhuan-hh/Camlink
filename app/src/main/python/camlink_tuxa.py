"""Kiểm tra từ xa cả dự án theo 5 tầng + sửa từ xa.
Tầng: 1 tên miền · 2 IP trỏ về · 3 đường truyền điểm · 4 port từng cam · 5 hình ảnh.
Chỉ ĐỌC, trừ khi người dùng bấm nút Sửa."""
import errno, ipaddress, json, os, socket, time
from concurrent.futures import ThreadPoolExecutor
import camlink_dt as C
import camlink_oryza

PORT_QUET = [80, 81, 82, 85, 88, 443, 7547, 8888] + list(range(8000, 8011)) + list(range(8080, 8100))  # cổng web cam/modem hay dùng
RTSP_CHUNG = [554, 5541, 5542, 5543]

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

    # Tầng 3 — QUÉT chính tên miền: tìm mọi cam thật đang gắn sau tên miền (không tin số cam trong file)
    rtsp_du_kien = [c["rtsp"] for c in cams]
    cong = sorted(set(PORT_QUET) | {c["http"] for c in cams} | set(rtsp_du_kien))
    with ThreadPoolExecutor(16) as ex:
        ket = dict(zip(cong, ex.map(lambda x: cham_tg(dom, x), cong)))
    mo = [x for x in cong if ket[x][0] == "mo" and x not in rtsp_du_kien and x not in RTSP_CHUNG]
    cam_port, web_khac = [], []
    for x in mo:
        ov = C.Onvif(dom, x, cu, cp)
        if ov.co() or camlink_oryza.la_oryza(dom, x, 4):
            cam_port.append(x)
        else:
            web_khac.append(x)
    if web_khac:
        x = web_khac[0]
        kq["web_modem"] = f"{'https' if x == 443 else 'http'}://{dom}:{x}"
    kq["quet"] = {"cam_port": cam_port, "web_khac": web_khac, "so_quet": len(cam_port)}
    kq["so_quet"] = len(cam_port)
    song = any(r[0] != "im_lang" for r in ket.values())
    if not song:
        viec = ["Gọi người tại điểm kiểm tra đèn nguồn tủ điện và modem.",
                "Modem sáng đèn LOS đỏ → gọi VNPT 18001166 báo đứt cáp quang.",
                "Chỉ cử thợ ra khi 2 bước trên không xử lý được."]
        if ho_so and ho_so.get("wan") and ho_so["wan"] != ip:
            viec.insert(0, f"Lưu ý: tên miền đang trỏ {ip}, lúc cài là {ho_so['wan']} → có thể cam 1 mất nguồn nên DDNS không cập nhật IP mới.")
        for c in cams:
            c["t_http"], c["ms_http"] = ket[c["http"]]
            c["t_rtsp"], c["ms_rtsp"] = ket[c["rtsp"]]
        return ca_diem(DO, "MẤT ĐIỆN / MẤT MẠNG CẢ ĐIỂM",
                       f"quét {len(cong)} port trên {dom}: modem và mọi cam đều không trả lời", viec)

    # cam phát hiện thêm ở port không có trong cấu hình
    du_kien = {c["http"] for c in cams}
    for x in cam_port:
        if x not in du_kien:
            cams.append({"so": len(cams) + 1, "http": x, "rtsp": 0, "web": f"http://{dom}:{x}", "live": "",
                         "user": cu, "pass": cp, "anh": "", "hang": "", "model": "", "t_http": "", "t_rtsp": "",
                         "ms_http": 0, "ms_rtsp": 0, "onvif": "", "bang_chung": [], "them": True})
    ghi_quet = (f"Quét {dom}: thấy {len(cam_port)} cam (port {', '.join(map(str, cam_port)) or 'không có'})"
                f"; cấu hình {so} cam ({nguon_so})")

    # Tầng 4–5 — từng cam
    for c in cams:
        c["t_http"], c["ms_http"] = ket.get(c["http"], cham_tg(dom, c["http"]))
        if c["http"] not in cam_port:
            c["khong_thay"] = True   # vị trí file ghi có cam nhưng quét tên miền không thấy
            goi_y = [f"Thực tế quét {dom} thấy {len(cam_port)} cam, file ghi {so_file} cam."]
            if c["t_http"] == "tu_choi":
                _ket(c, VANG, f"Modem có mạng nhưng từ chối port {c['http']} → chưa có luật mở port (NAT) cho cam {c['so']}, hoặc không có cam {c['so']}",
                     goi_y + [f"Bấm Sửa từ xa để thêm luật NAT {c['http']}/{c['rtsp']} → 192.168.1.{C.IP_TU + c['so'] - 1} (cần vào được web modem).",
                              "Không vào được web modem: ra điểm chạy lại CamLink."], ["them_nat"], "Không thấy cam / thiếu NAT")
            elif c["t_http"] == "im_lang":
                _ket(c, DO, f"Modem có mạng nhưng cam {c['so']} (port {c['http']}) không trả lời → cam mất nguồn, lỏng dây mạng, hoặc bị đổi IP",
                     goi_y + [f"Gọi người tại điểm kiểm tra đèn nguồn cam {c['so']} và dây mạng/PoE.",
                              "Nếu cam vẫn sáng: có thể cam bị reset về IP mặc định → ra điểm chạy lại CamLink.",
                              "Có web modem: bấm Sửa từ xa để khởi động lại modem."], ["khoi_dong_modem"], "Cam mất nguồn / lỏng dây")
            else:
                _ket(c, VANG, f"Port {c['http']} mở nhưng không phải cam trả lời (ONVIF tắt hoặc cam treo)",
                     [f"Mở web {c['web']} xem có vào được không.", "Bấm Sửa từ xa để khởi động lại modem; còn lỗi thì ra điểm khởi động lại cam."],
                     ["khoi_dong_modem"], "Port mở nhưng cam không trả lời")
            if c["rtsp"]:
                c["t_rtsp"], c["ms_rtsp"] = ket.get(c["rtsp"], ("im_lang", 0))
            continue
        ov = C.Onvif(dom, c["http"], cu, cp)
        c["onvif"] = "trả lời (chưa đăng nhập)"
        try:
            ov.co()
            tt = ov.thong_tin()
            c["hang"], c["model"], c["serial"] = tt.get("hang", ""), tt.get("model", ""), tt.get("serial", "")
            try:
                c["mac"] = ov.token_mang()[1]
            except Exception:
                c["mac"] = ""
            c["onvif"] = "đăng nhập được"
            doc_cau_hinh(c, ov, dom, d, cu, cp, ho_so, c["http"] == min(cam_port))
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
            f = os.path.join(anh_dir, f"tuxa_{ma}_{stt}_p{c['http']}.jpg")
            with open(f, "wb") as fh:
                fh.write(jpg)
            c["anh"] = f
        except Exception as e:
            _ket(c, VANG, f"Cam trả lời nhưng không ra hình ({str(e)[:60]}) → cam treo",
                 ["Bấm Sửa từ xa để khởi động lại cam, chờ 2 phút rồi kiểm tra lại."], ["khoi_dong_cam"], "Cam treo")
            continue
        # cổng video THẬT của cam (đọc từ cam), không đoán theo quy ước
        rtsp_cam = 0
        try:
            rtsp_cam = ov.doc_port().get("RTSP") or 0
        except Exception:
            pass
        if not c["rtsp"]:
            c["rtsp"] = rtsp_cam or 554
        try:
            c["live"] = ov.luong_video(um, tk, c["rtsp"])
        except Exception:
            c["live"] = f"rtsp://{cu}:{cp}@{dom}:{c['rtsp']}/"
        c["t_rtsp"], c["ms_rtsp"] = ket[c["rtsp"]] if c["rtsp"] in ket else cham_tg(dom, c["rtsp"])
        if c["t_rtsp"] != "mo":
            if rtsp_cam and rtsp_cam != c["rtsp"]:
                _ket(c, VANG, f"Có hình nhưng cam đang dùng RTSP {rtsp_cam} thay vì {c['rtsp']} → IOC không xem được video",
                     [f"Bấm Sửa từ xa để đặt lại RTSP {c['rtsp']} cho cam."], ["dat_port_rtsp"], "Cam đổi port RTSP")
            else:
                _ket(c, VANG, f"Có hình nhưng port RTSP {c['rtsp']} chưa mở trên modem → IOC không xem được video",
                     [f"Bấm Sửa từ xa để thêm luật NAT {c['rtsp']} (cần vào được web modem)."], ["them_nat"], "Thiếu NAT RTSP")
            continue
        if c.get("them"):
            _ket(c, VANG, f"Cam chạy tốt nhưng ở port {c['http']} — KHÔNG có trong cấu hình điểm này",
                 ["Kiểm tra cam này có phải của điểm này không (có thể tên miền bị đổi/gộp giữa các điểm).",
                  "Đúng là của điểm này: cập nhật lại file khảo sát."], [], "Cam lạ ngoài cấu hình")
            continue
        if c.get("loi_cau_hinh"):
            _ket(c, VANG, "Cam đang chạy (có hình) nhưng cấu hình trong cam chưa đúng: " + c["loi_cau_hinh"][0],
                 ["Cam đang chạy nên app KHÔNG tự sửa, chỉ báo cáo."] + c["loi_cau_hinh"] +
                 ["Muốn sửa: bấm nút Sửa từ xa bên dưới hoặc ra điểm chạy lại CamLink."],
                 (["nhap_lai_ddns"] if c.get("ddns_sai") else []) + (["khoi_phuc_mang"] if c.get("mang_sai") else []),
                 "Cấu hình trong cam chưa đúng")
            continue
        _ket(c, XANH, "Xem được từ ngoài: có ảnh chụp qua tên miền, port web + video mở, cấu hình trong cam đúng", [], nhan="Đạt")
    hong = [c for c in cams if c["muc"] != XANH]
    kq["muc"] = DO if any(c["muc"] == DO for c in cams) else (VANG if hong else XANH)
    kq["tong"] = "ĐẠT" if not hong else f"{len(cams) - len(hong)}/{len(cams)} cam đạt"
    kq["ghi_quet"] = ghi_quet
    return _xong(kq)


def doc_cau_hinh(c, ov, dom, d, cu, cp, ho_so, cam_dau):
    """CHỈ ĐỌC cấu hình trong cam: gateway, DNS, giờ, và DDNS trên cam đầu tiên. Không ghi gì."""
    loi = []
    ch = {}
    gw, dns = ov.doc_gw_dns()
    ch["gateway"], ch["dns"] = gw or "(trống)", dns or "(trống)"
    gw_dung = (ho_so or {}).get("gw") or ""
    if not gw:
        loi.append("Gateway trong cam đang TRỐNG → cam không ra được Internet.")
        c["mang_sai"] = True
    elif gw_dung and gw != gw_dung:
        loi.append(f"Gateway trong cam là {gw}, lúc cài là {gw_dung}.")
        c["mang_sai"] = True
    if not dns:
        loi.append("DNS trong cam đang TRỐNG → cam không cập nhật được No-IP, tên miền sẽ trỏ IP cũ.")
        c["mang_sai"] = True
    c["gw_dung"] = gw_dung or gw
    lech = getattr(ov, "lech", None)
    if lech is not None:
        phut = int(abs(lech.total_seconds()) // 60)
        ch["gio_lech_phut"] = phut
        if phut >= 30:   # lệch vài phút: chỉ ghi vào bằng chứng, không tính là lỗi
            loi.append(f"Giờ của cam lệch {phut} phút → ảnh và dữ liệu lưu sai giờ.")
    if cam_dau:
        try:
            if camlink_oryza.la_oryza(dom, c["http"], 4):
                dd = camlink_oryza.doc_ddns_cam(dom, c["http"], cu, cp)
                ch["ddns"] = dd
                if not dd["bat"]:
                    loi.append("DDNS trong cam 1 đang TẮT → tên miền không tự cập nhật IP mới.")
                    c["ddns_sai"] = True
                elif dd["ten_mien"].lower() != dom.lower():
                    loi.append(f"DDNS trong cam 1 đang gửi IP cho tên miền {dd['ten_mien']}, KHÔNG phải {dom} → tên miền bị đổi/nhầm điểm.")
                    c["ddns_sai"] = True
                elif d.get("u") and dd["tai_khoan"] and dd["tai_khoan"] != d["u"]:
                    loi.append(f"DDNS trong cam 1 dùng tài khoản No-IP {dd['tai_khoan']}, file ghi {d['u']}.")
                    c["ddns_sai"] = True
            else:
                ch["ddns"] = "chưa đọc được DDNS với hãng cam này"
        except Exception as e:
            ch["ddns"] = f"không đọc được ({str(e)[:60]})"
    c["cau_hinh"] = ch
    c["loi_cau_hinh"] = loi


def _xong(kq):
    """Ghi bằng chứng cho từng cam: vào được hay không vào được đều có dữ kiện cụ thể."""
    for c in kq["cam"]:
        b = [f"Kiểm lúc {kq['luc']} qua Internet",
             f"Tên miền {kq['domain']} → " + (kq["ip"] or "KHÔNG PHÂN GIẢI ĐƯỢC")]
        if c.get("t_http"):
            b.append(f"Port web {c['http']}: {TEN_CHAM.get(c['t_http'], c['t_http'])} — {c['ms_http']} ms")
        if c.get("t_rtsp"):
            b.append(f"Port video RTSP {c['rtsp']}: {TEN_CHAM.get(c['t_rtsp'], c['t_rtsp'])} — {c['ms_rtsp']} ms")
        if c.get("onvif"):
            b.append(f"ONVIF: {c['onvif']}" + (f" — {c['hang']} {c['model']}".rstrip() if c.get("model") else ""))
        ch = c.get("cau_hinh")
        if ch:
            dd = ch.get("ddns")
            txt = f"Cấu hình trong cam: gateway {ch.get('gateway')}, DNS {ch.get('dns')}"
            if "gio_lech_phut" in ch:
                txt += f", giờ lệch {ch['gio_lech_phut']} phút"
            if isinstance(dd, dict):
                txt += f", DDNS {'BẬT' if dd['bat'] else 'TẮT'} {dd['nha_cung_cap']} → {dd['ten_mien']} (tài khoản {dd['tai_khoan']})"
            elif dd:
                txt += f", DDNS: {dd}"
            b.append(txt)
        for x in c.get("da_sua", []):
            b.append("ĐÃ TỰ SỬA: " + x)
        if c.get("anh") and os.path.exists(c["anh"]):
            b.append(f"ẢNH CHỤP qua {kq['domain']}:{c['http']} — {os.path.getsize(c['anh']) // 1024} KB")
        elif c["muc"] != XANH:
            b.append("KHÔNG lấy được ảnh")
        if kq.get("quet"):
            q = kq["quet"]
            b.insert(2, f"Quét tên miền: thấy {q['so_quet']} cam ở port {', '.join(map(str, q['cam_port'])) or '—'}")
        c["bang_chung"] = b
    if kq.get("so") != kq.get("so_file"):
        kq["ghi_so"] = f"File khảo sát ghi {kq['so_file']} cam, đang kiểm {kq['so']} cam ({kq['nguon_so']})"
    else:
        kq["ghi_so"] = f"Kiểm {kq['so']} cam ({kq['nguon_so']})"
    if kq.get("ghi_quet"):
        kq["ghi_so"] = kq["ghi_quet"]
    return kq


# ------------------------------------------------------------------ cả dự án
def _f_lich_su(goc, ma):
    return os.path.join(goc, "ketqua", f"tuxa_{ma}.json")


TU_SUA_DUOC = ("khoi_dong_cam", "dat_port_rtsp")


def tu_sua_diem(p, d, cd, anh_dir, ma, ho_so, log):
    """Chỉ đụng tới cam ĐANG CÓ VẤN ĐỀ: chạy sửa lỗi; sửa xong vào kiểm tra lại cấu hình,
    mất/sai cấu hình thì khôi phục. Cam đang chạy tốt: không đụng tới."""
    nhat_ky = {}
    can = [c for c in p["cam"] if c["muc"] != XANH and any(v in TU_SUA_DUOC for v in c.get("sua", []))]
    if not can:
        return p
    for c in can:
        for v in [v for v in c["sua"] if v in TU_SUA_DUOC]:
            log(f"   🔧 Điểm {p['stt']} cam {c['so']}: {TEN_SUA[v]} …")
            ok, tb = sua(d, c["so"], v, cd, log)
            nhat_ky.setdefault(c["http"], []).append(f"{TEN_SUA[v]} → {'XONG' if ok else 'CHƯA ĐƯỢC'}: {tb}")
    moi = kiem_diem(p["stt"], d, cd, anh_dir, ma, ho_so)
    cu, cp = cd.get("cam_user", "admin"), cd.get("cam_pw", "")
    sua_cau_hinh = False
    for c in moi["cam"]:
        if c["http"] not in nhat_ky or not c.get("cau_hinh"):
            continue
        ov = C.Onvif(moi["domain"], c["http"], cu, cp)
        ch = c["cau_hinh"]
        try:
            gw_dung = (ho_so or {}).get("gw") or (ch["gateway"] if ch["gateway"] != "(trống)" else "")
            if gw_dung and (ch["gateway"] != gw_dung or ch["dns"] == "(trống)"):
                ov.dat_gw_dns(gw_dung)
                nhat_ky[c["http"]].append(f"Khôi phục gateway {gw_dung} + DNS 8.8.8.8")
                sua_cau_hinh = True
            if c.get("ddns_sai"):
                kq = camlink_oryza.dat_ddns(moi["domain"], c["http"], cu, cp, moi["domain"], d.get("u", ""), d.get("p", ""))
                nhat_ky[c["http"]].append("Khôi phục DDNS: " + kq)
                sua_cau_hinh = True
        except Exception as e:
            nhat_ky[c["http"]].append(f"Khôi phục cấu hình lỗi: {str(e)[:80]}")
    if sua_cau_hinh:
        moi = kiem_diem(p["stt"], d, cd, anh_dir, ma, ho_so)
    for c in moi["cam"]:
        if c["http"] in nhat_ky:
            c["da_sua"] = nhat_ky[c["http"]]
            if c["muc"] != XANH:
                c["viec"] = [f"App đã tự thử: {'; '.join(nhat_ky[c['http']])} — vẫn chưa được."] + c.get("viec", [])
    log(f"   → Điểm {p['stt']} sau khi tự sửa: {moi['tong']}")
    return _xong(moi)


def kiem_du_an(goc, da, ma, cd, log=print, chi_diem=None, tu_sua=True):
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
    if tu_sua:
        sua_n = [p for p in kqs if any(c["muc"] != XANH and any(v in TU_SUA_DUOC for v in c.get("sua", [])) for c in p["cam"])]
        if sua_n:
            log(f"TỰ SỬA {sum(1 for p in sua_n for c in p['cam'] if c['muc'] != XANH)} cam có vấn đề (cam đang chạy tốt không đụng tới):")
        for i, p in enumerate(kqs):
            if p in sua_n:
                try:
                    kqs[i] = tu_sua_diem(p, diem[p["stt"]], cd, anh_dir, ma, ho_so.get(p["stt"]), log)
                except Exception as e:
                    log(f"   ✖ Tự sửa điểm {p['stt']} lỗi: {e}")
    # so với lần trước
    f = _f_lich_su(goc, ma)
    truoc = {}
    try:
        with open(f, encoding="utf-8") as fh:
            truoc = json.load(fh)
    except (OSError, ValueError):
        pass
    tr_cam = {(p["stt"], c["so"]): c.get("muc") for p in truoc.get("diem", []) for c in p.get("cam", [])}
    # ---- đối chiếu chéo: phát hiện tên miền bị đổi / gộp / trỏ nhầm điểm
    tr_fp = {(p["domain"], c["http"]): (c.get("serial") or c.get("mac")) for p in truoc.get("diem", []) for c in p.get("cam", [])}
    tr_so = {p["domain"]: (p.get("quet") or {}).get("so_quet") for p in truoc.get("diem", [])}
    vet = {}
    for p in kqs:
        for c in p["cam"]:
            k = c.get("serial") or c.get("mac")
            if k:
                vet.setdefault(k, []).append(f"điểm {p['stt']} ({p['domain']}:{c['http']})")
    theo_ip = {}
    for p in kqs:
        if p.get("ip"):
            theo_ip.setdefault(p["ip"], []).append(f"điểm {p['stt']} ({p['domain']})")
    for p in kqs:
        p["canh_bao"] = []
        if len(theo_ip.get(p.get("ip"), [])) > 1:
            p["canh_bao"].append(f"Nhiều tên miền cùng trỏ về IP {p['ip']}: " + ", ".join(theo_ip[p["ip"]]) + " → kiểm tra có bị đổi/gộp tên miền giữa các điểm không.")
        so_cu, so_moi = tr_so.get(p["domain"]), (p.get("quet") or {}).get("so_quet")
        if so_cu is not None and so_moi is not None and so_cu != so_moi:
            p["canh_bao"].append(f"Lần kiểm trước quét thấy {so_cu} cam trên {p['domain']}, nay {so_moi} cam.")
        mac_hs = {x.get("mac", "").upper() for x in (ho_so.get(p["stt"]) or {}).get("cam", []) if x.get("mac")}
        for c in p["cam"]:
            k = c.get("serial") or c.get("mac")
            cb = []
            if k and len(vet.get(k, [])) > 1:
                cb.append("Cùng một cam xuất hiện ở " + ", ".join(vet[k]) + " → tên miền đang trỏ trùng.")
            k_cu = tr_fp.get((p["domain"], c["http"]))
            if k and k_cu and k != k_cu:
                cb.append(f"Cam ở {p['domain']}:{c['http']} KHÁC lần kiểm trước (mã {k_cu} → {k}) → tên miền có thể đã bị đổi sang điểm khác.")
            if mac_hs and c.get("mac") and c["mac"].upper() not in mac_hs:
                cb.append(f"MAC {c['mac']} không có trong hồ sơ lúc cài điểm {p['stt']} → cam này không phải cam đã cài ở điểm này.")
            if cb:
                c["canh_bao"] = cb
                c.setdefault("viec", [])
                c["viec"] = cb + c["viec"]
                if c["muc"] == XANH:
                    c["muc"], c["nhan"] = VANG, "Tên miền trỏ nhầm / đổi điểm"
                    c["nguyen_nhan"] = "Cam xem được nhưng không khớp đối chiếu: " + cb[0]
        hong = [c for c in p["cam"] if c["muc"] != XANH]
        if p["cam"] and not (p["muc"] == DO and p["tong"].isupper()):
            p["muc"] = DO if any(c["muc"] == DO for c in p["cam"]) else (VANG if hong else XANH)
            p["tong"] = "ĐẠT" if not hong else f"{len(p['cam']) - len(hong)}/{len(p['cam'])} cam đạt"
    for p in kqs:
        for c in p["cam"]:
            cu_m = tr_cam.get((p["stt"], c["so"]))
            c["vua_rot"] = cu_m == XANH and c["muc"] != XANH
            c["vua_len"] = cu_m is not None and cu_m != XANH and c["muc"] == XANH
    tong_cam = sum(len(p["cam"]) for p in kqs)
    dat = sum(1 for p in kqs for c in p["cam"] if c["muc"] == XANH)
    tong_file = sum(int(diem[p["stt"]].get("so") or 0) for p in kqs)
    tong_quet = sum(p.get("so_quet", 0) for p in kqs)
    khong_thay = sum(1 for p in kqs for c in p["cam"] if c.get("khong_thay"))
    cam_la = sum(1 for p in kqs for c in p["cam"] if c.get("them"))
    dem = {}
    for p in kqs:
        if p["muc"] == DO and not any(c["muc"] == XANH for c in p["cam"]) and p["tong"].isupper():
            dem[p["tong"]] = dem.get(p["tong"], 0) + 1   # lỗi cả điểm: đếm theo điểm
        else:
            for c in p["cam"]:
                if c["muc"] != XANH:
                    dem[c["nhan"]] = dem.get(c["nhan"], 0) + 1
    out = {"du_an": da["ten"], "ma": ma, "luc": time.strftime("%d/%m/%Y %H:%M"), "giay": round(time.time() - t0),
           "tong_cam": tong_cam, "dat": dat, "tong_file": tong_file, "tong_quet": tong_quet, "khong_thay": khong_thay, "cam_la": cam_la, "da_sua": sum(1 for p in kqs for c in p["cam"] if c.get("da_sua")),
           "sua_xong": sum(1 for p in kqs for c in p["cam"] if c.get("da_sua") and c["muc"] == XANH), "rot": sum(1 for p in kqs for c in p["cam"] if c.get("vua_rot")),
           "nhom_loi": dem, "diem": sorted(kqs, key=lambda p: (int(p["stt"]) if str(p["stt"]).isdigit() else 0))}
    if not chi_diem:
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False)
    log(f"→ File ghi {tong_file} cam · quét thực tế thấy {tong_quet} cam · {dat} cam đạt · {out['rot']} cam vừa rớt so với lần trước · {out['giay']} giây")
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
                       "CÓ" if c.get("vua_rot") else "", "\n".join([p.get("ghi_so", "")] + p.get("canh_bao", []))])
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
    # ---- Tổng hợp: số cam theo file vs thực tế quét
    th = wb.create_sheet("Tong hop", 0)
    th.append([f"TỔNG HỢP — {ket_qua['du_an']} — {ket_qua['luc']}"])
    th["A1"].font = Font(bold=True, size=13)
    th.append([f"File ghi {ket_qua.get('tong_file', '')} cam · quét thực tế thấy {ket_qua.get('tong_quet', '')} cam · "
               f"{ket_qua['dat']} cam đạt (có ảnh) · {ket_qua.get('khong_thay', 0)} vị trí file ghi nhưng không thấy cam"])
    th.append(["No", "Tên điểm", "Domain", "Cam theo file", "Cam quét thực tế", "Port cam thấy", "Cam đạt", "Kết luận", "Cảnh báo"])
    for c in th[3]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="0F5D8C")
    for p in ket_qua["diem"]:
        q = p.get("quet") or {}
        th.append([p["stt"], p["ten"], p["domain"], p.get("so_file", ""), q.get("so_quet", "—"),
                   ", ".join(map(str, q.get("cam_port", []))), sum(1 for c in p["cam"] if c["muc"] == XANH),
                   p["tong"], "\n".join(p.get("canh_bao", []))])
        for cell in th[th.max_row]:
            cell.fill = PatternFill("solid", fgColor=mau[p["muc"]])
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        if p.get("so_file") != q.get("so_quet"):
            th.cell(th.max_row, 5).font = Font(bold=True, color="B42318")
    for col, w in zip("ABCDEFGHI", [5, 30, 30, 12, 14, 18, 9, 22, 50]):
        th.column_dimensions[col].width = w
    # ---- Báo cáo sửa tất cả
    if ket_qua.get("bao_cao_sua"):
        bs = wb.create_sheet("Bao cao sua", 1)
        xong = sum(1 for b in ket_qua["bao_cao_sua"] if b["ket_qua"] == "HOÀN THÀNH")
        bs.append([f"BÁO CÁO SỬA TẤT CẢ — {ket_qua.get('luc_sua', '')} — {xong}/{len(ket_qua['bao_cao_sua'])} vấn đề hoàn thành"])
        bs["A1"].font = Font(bold=True, size=13)
        bs.append(["Điểm", "Cam", "Vấn đề", "App đã làm", "Kết quả", "Nguyên nhân (nếu chưa)", "Giải pháp đề xuất"])
        for c in bs[2]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="0F5D8C")
        for b in ket_qua["bao_cao_sua"]:
            bs.append([b["diem"], b["cam"], b["van_de"], "\n".join(b["da_lam"]), b["ket_qua"], b.get("nguyen_nhan", ""),
                       "\n".join(f"{i + 1}) {g}" for i, g in enumerate(b.get("giai_phap", [])))])
            for cell in bs[bs.max_row]:
                cell.fill = PatternFill("solid", fgColor="D9F2E3" if b["ket_qua"] == "HOÀN THÀNH" else "FBD9D5")
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for col, w in zip("ABCDEFG", [28, 18, 26, 50, 13, 45, 60]):
            bs.column_dimensions[col].width = w
    f = os.path.join(goc, "ketqua", f"KiemTraTuXa_{ket_qua['ma']}_{time.strftime('%Y%m%d_%H%M')}.xlsx")
    wb.save(f)
    return f


# ------------------------------------------------------------------ sửa từ xa
TEN_SUA = {"khoi_phuc_mang": "Khôi phục gateway + DNS trong cam", "khoi_dong_cam": "Khởi động lại cam", "dat_port_rtsp": "Đặt lại port RTSP cho cam",
           "them_nat": "Thêm luật mở port trên modem", "khoi_dong_modem": "Khởi động lại modem",
           "nhap_lai_ddns": "Nhập lại DDNS trên cam 1"}


def sua(d, so, viec, cd, log=print, gw_dung=""):
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
        if viec == "khoi_phuc_mang":
            gw, dns = ov.doc_gw_dns()
            gw = gw or gw_dung
            if not gw:
                return False, "Không biết gateway đúng của điểm (cam trống gateway, chưa có hồ sơ lúc cài) → ra điểm chạy lại CamLink."
            ov.dat_gw_dns(gw)
            gw2, dns2 = ov.doc_gw_dns()
            return bool(gw2 and dns2), f"Gateway {gw2 or '(trống)'}, DNS {dns2 or '(trống)'} sau khi đặt lại."
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


# ------------------------------------------------------------------ SỬA TẤT CẢ (người dùng bấm)
CHAY_DUOC = ("khoi_dong_cam", "dat_port_rtsp", "khoi_phuc_mang", "nhap_lai_ddns")


def _bo_dong_bam(viec):
    return [v for v in viec if not v.startswith("Bấm Sửa") and "bấm nút Sửa" not in v and not v.startswith("App đã tự thử")]


def _tinh_lai(kq, diem):
    ds = kq["diem"]
    kq["tong_cam"] = sum(len(p["cam"]) for p in ds)
    kq["dat"] = sum(1 for p in ds for c in p["cam"] if c["muc"] == XANH)
    kq["tong_quet"] = sum(p.get("so_quet", 0) for p in ds)
    kq["khong_thay"] = sum(1 for p in ds for c in p["cam"] if c.get("khong_thay"))
    kq["cam_la"] = sum(1 for p in ds for c in p["cam"] if c.get("them"))
    dem = {}
    for p in ds:
        if p["muc"] == DO and not any(c["muc"] == XANH for c in p["cam"]) and p["tong"].isupper():
            dem[p["tong"]] = dem.get(p["tong"], 0) + 1
        else:
            for c in p["cam"]:
                if c["muc"] != XANH:
                    dem[c.get("nhan", "")] = dem.get(c.get("nhan", ""), 0) + 1
    kq["nhom_loi"] = dem
    return kq


def sua_tat_ca(goc, da, ma, kq, cd, log=print):
    """Gom MỌI vấn đề trong kết quả kiểm tra → chạy hết các cách sửa app làm được → kiểm tra lại →
    báo cáo từng vấn đề: HOÀN THÀNH, hoặc CHƯA kèm nguyên nhân + giải pháp."""
    diem = da["diem"]
    muc_sua, dong_diem = [], set()
    for p in kq["diem"]:
        ca_diem = p["muc"] == DO and p["tong"].isupper() and not any(c["muc"] == XANH for c in p["cam"])
        cams = [c for c in p["cam"] if c["muc"] != XANH]
        if ca_diem and cams:
            cams = cams[:1]
        for c in cams:
            chay = [v for v in c.get("sua", []) if v in CHAY_DUOC]
            muc_sua.append({"stt": p["stt"], "ten": p["ten"], "domain": p["domain"], "so": c["so"], "http": c["http"],
                            "ca_diem": ca_diem, "van_de": p["tong"] if ca_diem else c.get("nhan", ""),
                            "nguyen_nhan_truoc": c.get("nguyen_nhan", ""), "chay": chay, "da_lam": [],
                            "gw_dung": c.get("gw_dung", ""),
                            "trung": any("Cùng một cam" in x for x in c.get("canh_bao", []))})
    log(f"SỬA TẤT CẢ: {len(muc_sua)} vấn đề")
    for vong in range(3):   # sửa → kiểm lại → còn việc sửa được (vd mất cấu hình sau khởi động) thì làm tiếp
        dong_diem = set()
        for m in muc_sua:
            for v in m["chay"]:
                if v in m.setdefault("da_chay", []):
                    continue
                m["da_chay"].append(v)
                if v == "nhap_lai_ddns" and m.get("trung"):
                    m["da_lam"].append("Không nhập lại DDNS: cam này đang xuất hiện ở nhiều tên miền, phải xác định cam thuộc điểm nào trước (tránh ghi đè DDNS của điểm khác).")
                    continue
                log(f"🔧 Điểm {m['stt']} cam {m['so']}: {TEN_SUA[v]} …")
                ok, tb = sua(diem[m["stt"]], m["so"], v, cd, log, m.get("gw_dung", ""))
                m["da_lam"].append(f"{TEN_SUA[v]}: {'xong' if ok else 'chưa được'} — {tb}")
                dong_diem.add(m["stt"])
        if not dong_diem:
            break
        log("Kiểm tra lại các điểm vừa sửa …")
        moi = kiem_du_an(goc, da, ma, cd, log, chi_diem=sorted(dong_diem), tu_sua=False)
        theo = {p["stt"]: p for p in moi["diem"]}
        kq["diem"] = [theo.get(p["stt"], p) for p in kq["diem"]]
        theo = {p["stt"]: p for p in kq["diem"]}
        for m in muc_sua:   # việc sửa mới lộ ra sau vòng trước
            c = next((x for x in theo[m["stt"]]["cam"] if x["http"] == m["http"]), None)
            if c and c["muc"] != XANH:
                m["chay"] = [v for v in c.get("sua", []) if v in CHAY_DUOC]
                m["gw_dung"] = c.get("gw_dung", "")
    theo = {p["stt"]: p for p in kq["diem"]}
    bao_cao = []
    for m in muc_sua:
        p = theo[m["stt"]]
        c = next((x for x in p["cam"] if x["http"] == m["http"]), None)
        xong = c is not None and c["muc"] == XANH and bool(m.get("da_chay"))
        dong = {"diem": f"{m['stt']}. {m['ten']}", "cam": "cả điểm" if m["ca_diem"] else f"cam {m['so']} (port {m['http']})",
                "van_de": m["van_de"], "da_lam": m["da_lam"] or ["App không có cách sửa từ xa cho lỗi này"],
                "ket_qua": "HOÀN THÀNH" if xong else "CHƯA"}
        if not xong:
            dong["nguyen_nhan"] = (c or {}).get("nguyen_nhan") or m["nguyen_nhan_truoc"]
            gp = _bo_dong_bam((c or {}).get("viec") or (p.get("viec") or []))
            if any(v in ("them_nat", "khoi_dong_modem") for v in (c or {}).get("sua", [])):
                dau = [g for g in gp if g.startswith("Thực tế quét")]
                gp = dau + ["App chưa điều khiển được modem VNPT từ xa (đang chờ mẫu modem) → ra điểm chạy lại CamLink, hoặc nhờ người tại điểm rút điện modem 10 giây."] + [g for g in gp if g not in dau]
            dong["giai_phap"] = gp or ["Ra điểm kiểm tra trực tiếp."]
        bao_cao.append(dong)
    kq["bao_cao_sua"] = bao_cao
    kq["luc_sua"] = time.strftime("%d/%m/%Y %H:%M")
    _tinh_lai(kq, diem)
    xong = sum(1 for b in bao_cao if b["ket_qua"] == "HOÀN THÀNH")
    log(f"→ Sửa tất cả: {xong}/{len(bao_cao)} vấn đề HOÀN THÀNH")
    try:
        with open(_f_lich_su(goc, ma), "w", encoding="utf-8") as fh:
            json.dump(kq, fh, ensure_ascii=False)
    except OSError:
        pass
    return kq
