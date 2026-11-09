"""Kiểm tra từ xa cả dự án theo 5 tầng + sửa từ xa.
Tầng: 1 tên miền · 2 IP trỏ về · 3 đường truyền điểm · 4 port từng cam · 5 hình ảnh.
Chỉ ĐỌC, trừ khi người dùng bấm nút Sửa."""
import errno, ipaddress, json, os, re, socket, time
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
        if c["t_rtsp"] == "mo" and c.get("live"):
            try:
                duong = re.sub(r"^rtsp://[^/]*", "", c["live"]) or "/"
                c["rtsp_ma"], c["codec"], c["rtsp_ghi"] = rtsp_describe(dom, c["rtsp"], duong, cu, cp)
            except Exception:
                pass
        if c["t_rtsp"] != "mo":
            if rtsp_cam and rtsp_cam != c["rtsp"]:
                _ket(c, VANG, f"Có hình nhưng cam đang dùng RTSP {rtsp_cam} thay vì {c['rtsp']} → IOC không xem được video",
                     [f"Bấm Sửa từ xa để đặt lại RTSP {c['rtsp']} cho cam."], ["dat_port_rtsp"], "Cam đổi port RTSP")
            else:
                _ket(c, VANG, f"Có hình nhưng port RTSP {c['rtsp']} chưa mở trên modem → IOC không xem được video",
                     [f"Bấm Sửa từ xa để thêm luật NAT {c['rtsp']} (cần vào được web modem)."], ["them_nat"], "Thiếu NAT RTSP")
            continue
        if c.get("them"):
            mac_hs = {x.get("mac", "").upper() for x in (ho_so or {}).get("cam", []) if x.get("mac")}
            cua_minh = bool(c.get("mac")) and c["mac"].upper() in mac_hs
            _ket(c, VANG, f"CAM LẠ: đang dùng tên miền {dom} ở port {c['http']} nhưng KHÔNG có trong hồ sơ điểm này"
                 + (f" ({c['hang']} {c['model']}, MAC {c.get('mac', '')})" if c.get("model") else "")
                 + (" — MAC trùng cam mình đã lắp (có thể bị đổi port)" if cua_minh else " — thiết bị không do mình lắp"),
                 ["Hệ thống có thêm thiết bị mà hồ sơ không có: hoặc đơn vị khác nâng cấp/lắp thêm không báo, hoặc có người biết pass modem/cam đã thêm hoặc can thiệp.",
                  "Xác minh với đơn vị quản lý điểm: ai lắp, khi nào. Nếu không ai nhận → đổi pass modem và pass cam cả điểm.",
                  "Nếu là cam hợp lệ: bổ sung vào file khảo sát để lần sau không báo lạ."], [], "CAM LẠ (ngoài hồ sơ)")
            continue
        if c.get("loi_cau_hinh"):
            _ket(c, VANG, "Cam đang chạy (có hình) nhưng cấu hình trong cam chưa đúng: " + c["loi_cau_hinh"][0],
                 ["Cam đang chạy nên app KHÔNG tự sửa, chỉ báo cáo."] + c["loi_cau_hinh"] +
                 ["Muốn sửa: bấm nút Sửa từ xa bên dưới hoặc ra điểm chạy lại CamLink."],
                 (["nhap_lai_ddns"] if c.get("ddns_sai") else []) + (["khoi_phuc_mang"] if c.get("mang_sai") else []),
                 "Cấu hình trong cam chưa đúng")
            continue
        _ket(c, XANH, "Xem được từ ngoài: có ảnh chụp qua tên miền, port web + video mở, cấu hình trong cam đúng", [], nhan="Đạt")
    # Cùng điểm: số cam quét được = số theo file, có vị trí "không thấy" và có "cam lạ" → cam ĐỔI PORT,
    # không phải cam lạ, cũng không phải cam mất
    thieu = [c for c in cams if c.get("khong_thay")]
    la = [c for c in cams if c.get("them")]
    if thieu and la and len(cam_port) == so:
        for ct, cl in zip(thieu, la):
            cl.pop("them", None)
            cl["doi_port"], cl["so"] = ct["http"], ct["so"]
            cl["nhan"] = "Đạt (cam đang ở port khác cấu hình)"
            if cl.get("anh"):
                cl["muc"] = XANH
            cl["nguyen_nhan"] = (f"Cam {ct['so']} đang chạy ở port {cl['http']} thay vì {ct['http']} như cấu hình "
                                 f"(đổi port hoặc file ghi sai) — vẫn xem được; IOC phải dùng đúng port {cl['http']}")
            cl["viec"] = [f"Xác nhận IOC đang dùng port {cl['http']} cho cam này; nếu IOC dùng {ct['http']}: bấm Sửa từ xa để đặt lại."]
            cl["sua"] = ["dat_port_http"]
            cams.remove(ct)
        cams.sort(key=lambda x: x["so"])
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


def rtsp_describe(host, port, path, user, pw, cho=6):
    """DESCRIBE RTSP (Basic/Digest) → (mã, codec, ghi chú). Chỉ đọc — bằng chứng luồng video thật."""
    import base64, hashlib
    url = f"rtsp://{host}:{port}{path or '/'}"

    def goi(hd):
        sk = socket.create_connection((host, port), cho)
        sk.settimeout(cho)
        try:
            sk.sendall((f"DESCRIBE {url} RTSP/1.0\r\nCSeq: 2\r\nAccept: application/sdp\r\n{hd}\r\n").encode())
            d = b""
            while b"\r\n\r\n" not in d:
                x = sk.recv(4096)
                if not x:
                    break
                d += x
            hdr, _, body = d.partition(b"\r\n\r\n")
            n = re.search(rb"Content-Length:\s*(\d+)", hdr, re.I)
            while n and len(body) < int(n.group(1)):
                x = sk.recv(4096)
                if not x:
                    break
                body += x
            return hdr.decode(errors="ignore"), body.decode(errors="ignore")
        finally:
            sk.close()
    try:
        h, b = goi("")
        m = re.match(r"RTSP/1\.\d (\d+)", h)
        ma = int(m.group(1)) if m else 0
        if ma == 401:
            if "Digest" in h:
                f = dict(re.findall(r'(\w+)="([^"]*)"', h.split("Digest", 1)[1]))
                ha1 = hashlib.md5(f"{user}:{f.get('realm', '')}:{pw}".encode()).hexdigest()
                ha2 = hashlib.md5(f"DESCRIBE:{url}".encode()).hexdigest()
                rs = hashlib.md5(f"{ha1}:{f.get('nonce', '')}:{ha2}".encode()).hexdigest()
                au = (f'Authorization: Digest username="{user}", realm="{f.get("realm", "")}", nonce="{f.get("nonce", "")}", '
                      f'uri="{url}", response="{rs}"\r\n')
            else:
                au = "Authorization: Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode() + "\r\n"
            h, b = goi(au)
            m = re.match(r"RTSP/1\.\d (\d+)", h)
            ma = int(m.group(1)) if m else 0
        codec = ", ".join(sorted(set(re.findall(r"a=rtpmap:\d+ ([\w-]+)", b)))) or "?"
        if ma == 200:
            return ma, codec, f"Luồng video RTSP: DESCRIBE 200, codec {codec}"
        if ma == 401:
            return ma, codec, "Luồng video RTSP: 401 — cam từ chối user/pass cho video"
        if ma == 404:
            return ma, codec, "Luồng video RTSP: 404 — đường dẫn luồng không đúng"
        return ma, codec, f"Luồng video RTSP trả mã {ma}"
    except Exception as e:
        return 0, "?", f"Luồng video RTSP: không kết nối được ({str(e)[:50]})"


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
        if c.get("rtsp_ghi"):
            b.append(c["rtsp_ghi"] + (" — H.265: một số điện thoại không phát được trong app, IOC/VLC vẫn xem bình thường"
                                      if "H265" in c.get("codec", "").upper() else ""))
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
    toa_do = da.get("toa_do", {})
    log(f"KIỂM TRA TỪ XA — {da['ten']}: {len(ds)} điểm (chỉ đọc, qua Internet)")
    t0 = time.time()

    def mot(k):
        try:
            r = kiem_diem(k, diem[k], cd, anh_dir, ma, ho_so.get(k))
        except Exception as e:
            r = {"stt": k, "ten": diem[k]["ten"], "domain": diem[k]["domain"], "muc": DO, "tong": f"LỖI KIỂM TRA: {e}",
                 "viec": ["Kiểm tra lại."], "cam": [], "ip": "", "web_modem": "", "noip_user": "", "noip_pass": ""}
        td = toa_do.get(k)
        if td:
            r["lat"], r["lng"] = td[0], td[1]
            r["map"] = f"https://maps.google.com/?q={td[0]:.6f},{td[1]:.6f}"
        r["map_goc"] = diem[k].get("map", "")
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
    cu_la = {(x["domain"], x["http"]): x for x in truoc.get("cam_la", [])}
    ds_la = []
    for p in kqs:
        for c in p["cam"]:
            if c.get("them"):
                k = (p["domain"], c["http"])
                ds_la.append({"stt": p["stt"], "ten": p["ten"], "domain": p["domain"], "http": c["http"], "web": c["web"],
                              "hang": c.get("hang", ""), "model": c.get("model", ""), "mac": c.get("mac", ""),
                              "serial": c.get("serial", ""), "anh": c.get("anh", ""),
                              "lan_dau": cu_la[k]["lan_dau"] if k in cu_la else time.strftime("%d/%m/%Y %H:%M"),
                              "moi": k not in cu_la})
                c["cam_la_moi"] = k not in cu_la
    tong_cam = sum(len(p["cam"]) for p in kqs)
    dat = sum(1 for p in kqs for c in p["cam"] if c["muc"] == XANH)
    tong_file = sum(int(diem[p["stt"]].get("so") or 0) for p in kqs)
    tong_quet = sum(p.get("so_quet", 0) for p in kqs)
    khong_thay = sum(1 for p in kqs for c in p["cam"] if c.get("khong_thay"))
    # tách: "cam KHÔNG LÊN" (có cam, không xem được) ≠ "file ghi dư" (quét đủ cam nhưng file ghi nhiều hơn)
    file_du = sum(1 for p in kqs for c in p["cam"] if c.get("khong_thay") and c.get("t_http") == "tu_choi")
    khong_len = sum(1 for p in kqs for c in p["cam"] if c["muc"] != XANH and not c.get("anh") and not (c.get("khong_thay") and c.get("t_http") == "tu_choi"))
    dem = {}
    for p in kqs:
        if p["muc"] == DO and not any(c["muc"] == XANH for c in p["cam"]) and p["tong"].isupper():
            dem[p["tong"]] = dem.get(p["tong"], 0) + 1   # lỗi cả điểm: đếm theo điểm
        else:
            for c in p["cam"]:
                if c["muc"] != XANH:
                    dem[c["nhan"]] = dem.get(c["nhan"], 0) + 1
    out = {"du_an": da["ten"], "ma": ma, "luc": time.strftime("%d/%m/%Y %H:%M"), "giay": round(time.time() - t0),
           "tong_cam": tong_cam, "dat": dat, "tong_file": tong_file, "tong_quet": tong_quet, "khong_thay": khong_thay, "file_du": file_du, "khong_len": khong_len, "cam_la": ds_la, "so_cam_la": len(ds_la), "da_sua": sum(1 for p in kqs for c in p["cam"] if c.get("da_sua")),
           "sua_xong": sum(1 for p in kqs for c in p["cam"] if c.get("da_sua") and c["muc"] == XANH), "rot": sum(1 for p in kqs for c in p["cam"] if c.get("vua_rot")),
           "nhom_loi": dem, "ho_so": ho_so, "diem": sorted(kqs, key=lambda p: (int(p["stt"]) if str(p["stt"]).isdigit() else 0))}
    if not chi_diem:
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False)
    if ds_la:
        log(f"⚠ CAM LẠ: theo file {tong_file} cam + {len(ds_la)} cam lạ scan thấy ở "
            + "; ".join(f"điểm {x['stt']} ({x['domain']}:{x['http']}{', MỚI' if x['moi'] else ''})" for x in ds_la))
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
    th.append(["No", "Tên điểm", "Domain", "Cam theo file", "Cam quét thực tế", "Port cam thấy", "Cam đạt", "Kết luận", "Cảnh báo", "Toạ độ", "Dẫn đường (bấm)", "IP hiện tại", "IP lúc lắp"])
    for c in th[3]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="0F5D8C")
    for p in ket_qua["diem"]:
        q = p.get("quet") or {}
        th.append([p["stt"], p["ten"], p["domain"], p.get("so_file", ""), q.get("so_quet", "—"),
                   ", ".join(map(str, q.get("cam_port", []))), sum(1 for c in p["cam"] if c["muc"] == XANH),
                   p["tong"], "\n".join(p.get("canh_bao", [])),
                   (f"{p['lat']:.6f}, {p['lng']:.6f}" if p.get("lat") else "chưa có"), p.get("map", ""), p.get("ip", ""),
                   ((ket_qua.get("ho_so") or {}).get(p["stt"]) or {}).get("wan", "")])
        if p.get("map"):
            th.cell(th.max_row, 11).hyperlink = p["map"]
            th.cell(th.max_row, 11).font = Font(color="0B57D0", underline="single")
        for cell in th[th.max_row]:
            cell.fill = PatternFill("solid", fgColor=mau[p["muc"]])
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        if p.get("so_file") != q.get("so_quet"):
            th.cell(th.max_row, 5).font = Font(bold=True, color="B42318")
    for col, w in zip("ABCDEFGHIJKLM", [5, 30, 30, 12, 14, 18, 9, 22, 50, 22, 40, 16, 16]):
        th.column_dimensions[col].width = w
    # ---- Cam lạ
    if ket_qua.get("cam_la"):
        cl = wb.create_sheet("Cam la", 1)
        cl.append([f"CAM LẠ — theo file {ket_qua.get('tong_file', '')} cam + {len(ket_qua['cam_la'])} cam lạ scan thấy — có thể nâng cấp không báo hoặc bị can thiệp"])
        cl["A1"].font = Font(bold=True, size=13, color="B42318")
        cl.append(["Điểm", "Tên điểm", "Domain", "Port", "Link web", "Hãng/Model", "MAC", "Serial", "Thấy lần đầu", "Mới phát hiện"])
        for c in cl[2]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="7A1FA2")
        for x in ket_qua["cam_la"]:
            cl.append([x["stt"], x["ten"], x["domain"], x["http"], x["web"], f"{x['hang']} {x['model']}".strip(), x["mac"], x["serial"], x["lan_dau"], "MỚI" if x["moi"] else ""])
            cl.cell(cl.max_row, 5).hyperlink = x["web"]
        for col, w in zip("ABCDEFGHIJ", [6, 28, 30, 6, 34, 22, 20, 22, 18, 12]):
            cl.column_dimensions[col].width = w
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
TEN_SUA = {"dat_port_http": "Đặt lại port web/video đúng cấu hình", "khoi_phuc_mang": "Khôi phục gateway + DNS trong cam", "khoi_dong_cam": "Khởi động lại cam", "dat_port_rtsp": "Đặt lại port RTSP cho cam",
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
        if viec == "dat_port_http":
            for pth in [http] + list(range(8080, 8100)) + [80, 81, 82, 85, 88, 8000, 8001, 8002]:
                o2 = C.Onvif(dom, pth, cd.get("cam_user", "admin"), cd.get("cam_pw", ""))
                if C.mo(dom, pth, 2) and o2.co():
                    o2.dat_port(http, rtsp)
                    break
            else:
                return False, "Không tìm thấy cam để đặt lại port."
            for _ in range(20):
                if C.mo(dom, http, 3):
                    return True, f"Cam đã về port web {http} / video {rtsp}."
                time.sleep(3)
            return False, f"Đã gửi lệnh nhưng port {http} chưa mở từ ngoài → modem thiếu luật NAT {http}."
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
CHAY_DUOC = ("khoi_dong_cam", "dat_port_rtsp", "dat_port_http", "khoi_phuc_mang", "nhap_lai_ddns")


def _bo_dong_bam(viec):
    return [v for v in viec if not v.startswith("Bấm Sửa") and "bấm nút Sửa" not in v and not v.startswith("App đã tự thử")]


def _tinh_lai(kq, diem):
    ds = kq["diem"]
    kq["tong_cam"] = sum(len(p["cam"]) for p in ds)
    kq["dat"] = sum(1 for p in ds for c in p["cam"] if c["muc"] == XANH)
    kq["tong_quet"] = sum(p.get("so_quet", 0) for p in ds)
    kq["khong_thay"] = sum(1 for p in ds for c in p["cam"] if c.get("khong_thay"))
    kq["so_cam_la"] = sum(1 for p in ds for c in p["cam"] if c.get("them"))
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


# ------------------------------------------------------------------ BẢN ĐỒ + PHIẾU BÁO MẠNG
MAU_MAP = {"xanh": "#1D7A46", "vang": "#C88A00", "do": "#B42318"}


def phieu_bao_mang(kq, p, ho_so=None):
    """Phiếu gửi bên nhà mạng/người không nắm địa bàn: vị trí dẫn đường được + dữ liệu để tra đường truyền."""
    hs = ho_so or {}
    cam_hong = [c for c in p["cam"] if c["muc"] != XANH]
    dong = [f"PHIẾU BÁO SỰ CỐ ĐIỂM CAMERA — {kq['du_an']}",
            f"Điểm {p['stt']}: {p['ten']}",
            f"Vị trí (bấm để dẫn đường): {p.get('map') or p.get('map_goc') or 'chưa có toạ độ'}",
            (f"Toạ độ: {p['lat']:.6f}, {p['lng']:.6f}" if p.get("lat") else "Toạ độ: chưa có"),
            f"Tên miền: {p['domain']} → IP hiện tại: {p.get('ip') or 'không phân giải'}",
            f"IP WAN lúc lắp đặt: {hs.get('wan') or 'chưa ghi'}" + (f" ({hs.get('luc')})" if hs.get("luc") else ""),
            f"Hiện tượng: {p['tong']}",
            f"Phát hiện lúc: {p.get('luc') or kq['luc']}"]
    if p.get("canh_bao"):
        dong += ["Cảnh báo: " + " | ".join(p["canh_bao"])]
    for c in cam_hong:
        dong.append(f"  - Cam {c['so']} (port {c['http']}): {c.get('nguyen_nhan', '')}")
    viec = (p.get("viec") or (cam_hong[0].get("viec") if cam_hong else [])) or []
    if viec:
        dong.append("Đề nghị kiểm tra: " + " ".join(f"({i + 1}) {v}" for i, v in enumerate(viec[:3])))
    dong.append("Khi tới điểm: gọi lại số trên phiếu, chụp đèn modem (PON/LOS/LAN) gửi về.")
    return "\n".join(dong)


LEAFLET = os.environ.get("CAMLINK_LEAFLET", "file:///android_asset/")   # thư viện bản đồ đóng gói sẵn trong app


def ban_do_html(kq, goc):
    """Bản đồ các điểm (Leaflet/OpenStreetMap) tô màu theo tình trạng — mở offline-first trong WebView, tải tile khi có mạng."""
    import html as H
    ds = []
    for p in kq["diem"]:
        if not p.get("lat"):
            continue
        hong = [c for c in p["cam"] if c["muc"] != XANH]
        nd = f"<b>Điểm {p['stt']}. {H.escape(p['ten'])}</b><br>{H.escape(p['tong'])}<br>{H.escape(p['domain'])}"
        for c in hong[:3]:
            nd += f"<br>• Cam {c['so']}: {H.escape(c.get('nhan', ''))}"
        nd += f"<br><a href='{p['map']}'>Dẫn đường</a> · <a href='camlink://phieu/{p['stt']}'>Phiếu báo mạng</a>"
        ds.append({"lat": p["lat"], "lng": p["lng"], "mau": MAU_MAP[p["muc"]], "stt": p["stt"], "nd": nd, "muc": p["muc"]})
    thieu = [p["stt"] for p in kq["diem"] if not p.get("lat")]
    data = json.dumps(ds, ensure_ascii=False)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="{LEAFLET}leaflet.css"><script src="{LEAFLET}leaflet.js"></script>
<style>html,body,#m{{height:100%;margin:0}}.l{{position:absolute;top:8px;left:50px;z-index:1000;background:#fff;padding:6px 10px;border-radius:8px;font:13px sans-serif;box-shadow:0 1px 4px #0004}}
.n{{color:#fff;font:bold 12px sans-serif;text-align:center;line-height:26px}}</style></head><body><div id="m"></div>
<div class="l"><b>{H.escape(kq['du_an'])}</b> · {kq['luc']}<br>🟢 đạt · 🟡 lỗi cấu hình · 🔴 mất điện/mạng{'<br>Chưa có toạ độ: điểm ' + ', '.join(thieu) if thieu else ''}</div>
<script>var D={data};var m=L.map('m');L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{maxZoom:19,attribution:'© OpenStreetMap'}}).addTo(m);
m.on('tileerror',function(){{document.querySelector('.l').insertAdjacentHTML('beforeend','<br><span style=color:#B42318>Không tải được nền bản đồ (không có mạng) — vẫn hiện vị trí tương đối các điểm</span>')}});var g=L.featureGroup();D.forEach(function(d){{var ic=L.divIcon({{className:'',html:'<div class="n" style="background:'+d.mau+';width:26px;height:26px;border-radius:13px;border:2px solid #fff;box-shadow:0 0 4px #0008">'+d.stt+'</div>',iconSize:[26,26],iconAnchor:[13,13]}});
L.marker([d.lat,d.lng],{{icon:ic,zIndexOffset:d.muc=='do'?1000:(d.muc=='vang'?500:0)}}).bindPopup(d.nd).addTo(g)}});g.addTo(m);
if(D.length)m.fitBounds(g.getBounds().pad(0.2));else m.setView([16,107],6);</script></body></html>"""
    f = os.path.join(goc, "ketqua", f"BanDo_{kq['ma']}.html")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(page)
    return f
