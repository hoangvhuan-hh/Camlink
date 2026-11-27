# 2.14.2 — anh Huan chốt 27/11/2026 20:40: QR hồ sơ mở ẢNH CAM CHỤP NGAY LÚC QUÉT bằng tài khoản CHỈ XEM (không dùng tài khoản quản trị).
# Bài này thử phần tạo / giữ tài khoản chỉ xem trên cam giả có tác dụng thật (ảnh chỉ trả cho đúng tài khoản). Chạy: python3 tools/thu_xem.py
import os, sys, json, shutil, tempfile, re
import requests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gialap_onvif as S, camlink_dt as C, camlink_xem as X, camlink_hoso as H
G = os.path.join(tempfile.gettempdir(), "camlink_thu", "xem"); shutil.rmtree(G, True); os.makedirs(G)
dat = 0
def kt(ten, dk, them=""):
    global dat
    assert dk, f"HỎNG: {ten} {them}"
    dat += 1; print("✓", ten)

IP, QT = "127.0.4.31", "QuanTri@BiMat9"
cam = S.Cam(IP); cam.http, cam.rtsp, cam.pw = 8080, 5549, QT; S.bat(cam)
def ov_moi():
    o = C.Onvif(IP, 8080, "admin", QT); o.co(); return o
def lay_anh(u, p):
    return requests.get(f"http://{IP}:8080/anh.jpg", auth=(u, p), timeout=5)
URL = f"http://{IP}:8080/anh.jpg"

kt("X0: cam giả chỉ trả ảnh cho đúng tài khoản (người lạ bị từ chối)", lay_anh("admin", QT).status_code == 200 and lay_anh("xemhoso", "doan-mo").status_code == 401)
u, p, ghi = X.dam_bao(G, "da1", ov_moi(), IP, 8080, URL)
kt("X1: app tạo tài khoản chỉ xem trên cam (mức User, không phải Administrator)", (u, ghi) == (X.TEN, "") and (X.TEN, "User") in cam.users, (u, p, ghi, cam.users))
kt("X2: tài khoản chỉ xem LẤY ĐƯỢC ẢNH thật từ cam; mật khẩu khác mật khẩu quản trị", lay_anh(u, p).status_code == 200 and lay_anh(u, p).content[:2] == b"\xff\xd8" and p != QT)
kt("X3: mật khẩu chỉ gồm chữ, số, dấu gạch (gắn vào link không bị đổi ký tự), đủ hoa + thường + số", re.fullmatch(r"[A-Za-z0-9\-]{10,}", p) and re.search("[A-Z]", p) and re.search("[a-z]", p) and re.search("[0-9]", p), p)
kt("X4: app nhớ tài khoản này theo dự án + tên miền + cổng", X.cua_cam(G, "da1", IP, 8080) == (u, p) and X.cua_cam(G, "da1", IP, 8081) == ("", ""))
n0 = cam.so_lan_tao_user
u2, p2, _ = X.dam_bao(G, "da1", ov_moi(), IP, 8080, URL)
kt("X5: lượt kiểm sau KHÔNG tạo lại, không đổi mật khẩu (QR đã in vẫn dùng được)", (u2, p2) == (u, p) and cam.so_lan_tao_user == n0)
cam.users = [x for x in cam.users if x[0] != X.TEN]; cam.mk.pop(X.TEN, None)
kt("X6a: tài khoản bị xoá trên cam → QR cũ hết dùng được (cam giả có tác dụng thật)", lay_anh(u, p).status_code == 401)
u3, p3, _ = X.dam_bao(G, "da1", ov_moi(), IP, 8080, URL)
kt("X6: tài khoản bị xoá trên cam → lượt kiểm sau tạo lại với ĐÚNG mật khẩu cũ (QR đã in sống lại)", (u3, p3) == (u, p) and lay_anh(u, p).status_code == 200)
os.remove(X._f(G, "da1"))
u4, p4, _ = X.dam_bao(G, "da1", ov_moi(), IP, 8080, URL)
kt("X7: app mất sổ (cài lại app) mà cam còn tài khoản → đặt lại mật khẩu, vẫn mức User, lấy được ảnh", u4 == X.TEN and p4 != p and lay_anh(u4, p4).status_code == 200 and (X.TEN, "User") in cam.users)
cam2 = S.Cam("127.0.4.32"); cam2.http, cam2.rtsp, cam2.pw, cam2.cho_tao_user = 8080, 5549, QT, False; S.bat(cam2)
o2 = C.Onvif("127.0.4.32", 8080, "admin", QT); o2.co()
u5, p5, ghi5 = X.dam_bao(G, "da1", o2, "127.0.4.32", 8080, "http://127.0.4.32:8080/anh.jpg")
kt("X8: cam KHÔNG cho tạo tài khoản → không vỡ, trả rỗng kèm lý do, không ghi sổ", (u5, p5) == ("", "") and ghi5 and X.cua_cam(G, "da1", "127.0.4.32", 8080) == ("", ""), ghi5)
cam3 = S.Cam("127.0.4.33"); cam3.http, cam3.rtsp, cam3.pw, cam3.anh_chi_quan_tri = 8080, 5549, QT, True; S.bat(cam3)
o3 = C.Onvif("127.0.4.33", 8080, "admin", QT); o3.co()
u6, p6, ghi6 = X.dam_bao(G, "da1", o3, "127.0.4.33", 8080, "http://127.0.4.33:8080/anh.jpg")
kt("X9: cam tạo được tài khoản nhưng KHÔNG cho tài khoản đó lấy ảnh → coi như không dùng được (không in QR hỏng), không ghi sổ", (u6, p6) == ("", "") and "ảnh" in ghi6 and X.cua_cam(G, "da1", "127.0.4.33", 8080) == ("", ""), ghi6)
kt("X10: sổ tài khoản chỉ xem KHÔNG chứa mật khẩu quản trị", QT not in open(X._f(G, "da1"), encoding="utf-8").read())
l = H.link_anh(URL + "?a=1&b=2", u4, p4)
kt("X11: link trong QR = http://user:mật-khẩu@máy:cổng/đường-ảnh, giữ nguyên phần sau dấu ?, không https", l == f"http://{u4}:{p4}@{IP}:8080/anh.jpg?a=1&b=2", l)
kt("X12: mở đúng link trong QR (như điện thoại quét) → ra ảnh cam", requests.get(l, timeout=5).content[:2] == b"\xff\xd8")
kt("X13: link ảnh https do cam trả cũng bị ép về http; mật khẩu có ký tự lạ được đổi đúng chuẩn link", H.link_anh("https://a.b:8080/x.jpg", "admin", "Aa@1:2") == "http://admin:Aa%401%3A2@a.b:8080/x.jpg" and H.link_anh("", "a", "b") == "")
S.tat_het()
print(f"\nKẾT QUẢ: {dat} mục đạt")
