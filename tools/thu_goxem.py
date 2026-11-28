# GỠ tài khoản chỉ xem — anh Huan chốt 28/11/2026 07:42: bấm một nút, app vào từng cam của dự án xoá 'xemhoso', đọc lại xác nhận sạch.
# Cam giả có tác dụng thật (tạo được / xoá được / đọc lại được tài khoản). Chạy: python3 tools/thu_goxem.py
import os, sys, json, shutil, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gialap_onvif as S, camlink_dt as C, camlink_tuxa as T, camlink_core as K, camlink_xem as X
G = os.path.join(tempfile.gettempdir(), "camlink_thu", "goxem"); shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
K.khoi_tao(G)
dat = 0
def kt(ten, dk, them=""):
    global dat
    assert dk, f"HỎNG: {ten} {them}"
    dat += 1; print("✓", ten)

PW = "AdminCam@9"
C.ghi_cai_dat({"cam_user": "admin", "cam_pw": PW, "modem_user": "admin", "modem_pw": "m"})
# 2 điểm: điểm 1 có 2 cam (đều đã bị tạo xemhoso), điểm 2 có 1 cam (KHÔNG có xemhoso) + 1 cam TẮT (không vào được)
cams = {}
for p, ip, ports in ((1, "127.0.5.1", (8080, 8081)), (2, "127.0.5.2", (8080,))):
    for pt in ports:
        c = S.Cam(ip); c.http, c.rtsp, c.pw = pt, 554 + pt, PW; S.bat(c); cams[(ip, pt)] = c

# tạo sẵn xemhoso trên 2 cam điểm 1 (giả cảnh bản 2.14.2 đã lỡ tạo)
for ip, pt in (("127.0.5.1", 8080), ("127.0.5.1", 8081)):
    C.Onvif(ip, pt, "admin", PW).co(); C.Onvif(ip, pt, "admin", PW).tao_user(X.TEN, "Xem-abc12345", "User")
kt("G0: cam giả nhận và GIỮ tài khoản vừa tạo (có tác dụng thật)", X.con_tren_cam(C.Onvif("127.0.5.1", 8080, "admin", PW)) and not X.con_tren_cam(C.Onvif("127.0.5.2", 8080, "admin", PW)))

da = {"ten": "Gỡ xem", "diem": {
        "1": {"ten": "Điểm 1", "domain": "127.0.5.1", "so": 2},
        "2": {"ten": "Điểm 2", "domain": "127.0.5.2", "so": 2}}}      # điểm 2 khai 2 cam nhưng cam cổng 8081 tắt
ma = K._ma(K._ten_tu_file("goxem.xlsx")); K._ghi_du_an(ma, da)
with open(T._f_lich_su(G, ma), "w", encoding="utf-8") as fh:
    json.dump({"luc": "08:00 28/11/2026", "diem": [
        {"stt": "1", "domain": "127.0.5.1", "muc": "xanh", "cam": [{"so": 1, "http": 8080, "rtsp": 8634, "muc": "xanh"}, {"so": 2, "http": 8081, "rtsp": 8635, "muc": "xanh"}]},
        {"stt": "2", "domain": "127.0.5.2", "muc": "xanh", "cam": [{"so": 1, "http": 8080, "rtsp": 8634, "muc": "xanh"}, {"so": 2, "http": 8081, "rtsp": 8635, "muc": "do"}]}]}, fh, ensure_ascii=False)

kq = K.go_tai_khoan_xem(ma)
print("   kết quả:", kq)
kt("G1: 2 cam điểm 1 đã bị gỡ sạch tài khoản xemhoso (đọc lại TỪ CAM để xác nhận)",
   not X.con_tren_cam(C.Onvif("127.0.5.1", 8080, "admin", PW)) and not X.con_tren_cam(C.Onvif("127.0.5.1", 8081, "admin", PW)))
kt("G2: báo đúng số cam đã gỡ = 2", kq["xong"] == 2, kq)
kt("G3: cam vốn không có tài khoản (điểm 2 cam 1) KHÔNG tính là gỡ, cũng không báo lỗi", kq["khong_co"] == 1, kq)
kt("G4: cam không vào được (điểm 2 cam 2, đang tắt) → báo rõ để xoá tay, không nói đã sạch", any("8081" in x or "Điểm 2" in x for x in kq["loi"]) and kq["loi"], kq)

# bấm lại lần nữa: không còn gì để gỡ, không vỡ
kq2 = K.go_tai_khoan_xem(ma)
kt("G5: bấm lại → không còn cam nào bị gỡ (0), không lỗi mới trên cam còn sống", kq2["xong"] == 0, kq2)

S.tat_het()
print(f"\nKẾT QUẢ: {dat} mục đạt")
