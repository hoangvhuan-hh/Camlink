# Test LOCAL nhiều vai cho module Quản trị & Khôi phục (Huan 15/11).
# Mục tiêu chứng minh: thợ rút là KHÔNG can thiệp được; chỉ CHỦ xem/đổi được; liên kết LiteMark không đứt khi xoay pass.
import sys, os, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../app/src/main/python')); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import camlink_quantri as Q

G = os.path.join(__import__("tempfile").gettempdir(), "camlink_thu", "qt")
shutil.rmtree(G, True); os.makedirs(G)
Q.khoi_tao(G)
MAY_CHU, MAY_THO, MAY_THO2 = "may-chu-huan", "may-tho-A", "may-tho-B"
dat = 0
def ok(dk, cond):
    global dat
    assert cond, "SAI: " + dk
    dat += 1; print("  ✓", dk)

# 1. Tạo tài khoản — máy chủ thành tin cậy, có mã khôi phục
ma_kp = Q.tao_tai_khoan("1234", MAY_CHU, "Điện thoại Huan")
ok("tạo tài khoản, sinh mã khôi phục", "-" in ma_kp and Q.da_tao())
ok("máy chủ là thiết bị tin cậy", Q.thiet_bi_tin_cay(MAY_CHU) and Q.quyen(MAY_CHU) == Q.CHU)
ok("máy thợ chưa có quyền", Q.quyen(MAY_THO) == Q.KHONG)

# 2. Chủ lưu mật khẩu điểm; đọc lại được
Q.luu_mat_khau("1234", "pl", "2", "admin", "Aa112233@", "admin", "modempass", {"host": "phuly-chuaphapbao"})
Q.luu_mat_khau("1234", "pl", "10", "admin", "Cam10pass!", "admin", "modempass")
ok("chủ đọc được mật khẩu", Q.xem_mat_khau(MAY_CHU, "pl", "2", pin="1234")["cam_pw"] == "Aa112233@")

# 3. Sai PIN bị từ chối; mở lại bằng mã khôi phục (mô phỏng mất máy)
try:
    Q.xem_mat_khau(MAY_CHU, "pl", "2", pin="0000"); ok("sai PIN phải lỗi", False)
except ValueError:
    ok("sai PIN → từ chối", True)
ok("mở lại bằng mã khôi phục", Q._doc_ket(Q._lay_khoa_dl(ma_khoi_phuc=ma_kp))["diem"]["pl:2"]["cam_pw"] == "Aa112233@")

# 4. CHỐT CHẶN: máy thợ KHÔNG đọc được mật khẩu dù có phiên
ma1 = Q.cap_ma_mot_lan("1234", "pl:2", gio=24)
ok("thợ nhập mã một lần → có phiên", Q.tho_dung_ma(ma1, MAY_THO) and Q.quyen(MAY_THO, "pl:2") == Q.THO)
try:
    Q.xem_mat_khau(MAY_THO, "pl", "2", pin="1234"); ok("thợ đọc mật khẩu phải bị chặn", False)
except PermissionError:
    ok("thợ KHÔNG đọc được mật khẩu (dù có phiên)", True)

# 5. Thợ làm được việc hẹp (app tự chạy bằng creds, thợ không thấy pass)
thay_pass = {}
def gia_khoi_dong(creds):
    thay_pass["co"] = creds.get("cam_pw"); return "đã khởi động lại cam"
r = Q.thao_tac(MAY_THO, "pl", "2", "khoi_dong_cam", gia_khoi_dong, pin="1234")
ok("thợ khởi động lại cam được", r["ok"] and r["ket_qua"] == "đã khởi động lại cam")

# 6. Thợ KHÔNG làm được việc ngoài phạm vi (xoay/đổi admin)
r = Q.thao_tac(MAY_THO, "pl", "2", "xoay_mat_khau", lambda c: "x", pin="1234")
ok("thợ không xoay được mật khẩu", not r["ok"])

# 7. Phạm vi: mã cấp cho điểm 2, thợ thao tác điểm 10 → từ chối
r = Q.thao_tac(MAY_THO, "pl", "10", "khoi_dong_cam", lambda c: "x", pin="1234")
ok("thợ ngoài phạm vi điểm → từ chối", not r["ok"])

# 8. CHỐT CHẶN: thợ RÚT (thu hồi phiên) → KHÔNG can thiệp được gì nữa
Q.thu_hoi_phien("1234", thiet_bi_id=MAY_THO)
ok("sau thu hồi, thợ hết quyền", Q.quyen(MAY_THO, "pl:2") == Q.KHONG)
r = Q.thao_tac(MAY_THO, "pl", "2", "khoi_dong_cam", lambda c: "x", pin="1234")
ok("sau thu hồi, thợ không thao tác được", not r["ok"])

# 8b. Phiên HẾT HẠN cũng mất quyền (thợ cài xong, hôm sau không vào được)
ma2 = Q.cap_ma_mot_lan("1234", "pl:2", gio=24); Q.tho_dung_ma(ma2, MAY_THO2)
ph = Q._doc("phien.json"); ph["ds"][-1]["het_luc"] = 1  # ép hết hạn
Q._ghi("phien.json", ph)
ok("phiên hết hạn → thợ hết quyền", Q.quyen(MAY_THO2, "pl:2") == Q.KHONG)

# 9. Tài khoản XEM cho khách
tao_xem = {}
Q.tao_tai_khoan_xem("1234", MAY_CHU, "pl", "2", "khach", "Xem@123", lambda creds, u, p: tao_xem.update(u=u, p=p))
ok("tạo tài khoản Xem trên cam (callback chạy)", tao_xem == {"u": "khach", "p": "Xem@123"})

# 10. XOAY mật khẩu admin — vault đổi, LiteMark được đồng bộ pass mới, tài khoản Xem KHÔNG đụng
lm = {}; doi = []
Q.xoay_mat_khau("1234", MAY_CHU, "pl", "2", "MoiAa999@",
                doi_tren_cam=lambda c, loai, mk: doi.append((loai, c.get("cam_pw"), mk)),
                dong_bo_litemark=lambda stt, u, p: lm.update(stt=stt, user=u, pw=p), gom=("cam", "modem"))
d = Q.xem_mat_khau(MAY_CHU, "pl", "2", pin="1234")
ok("xoay: vault có mật khẩu mới", d["cam_pw"] == "MoiAa999@")
ok("xoay: dùng pass CŨ để đổi trên cam", doi[0][1] == "Aa112233@" and doi[0][2] == "MoiAa999@")
ok("xoay: LiteMark nhận pass MỚI (liên kết không đứt)", lm == {"stt": "2", "user": "admin", "pw": "MoiAa999@"})
ok("xoay: tài khoản Xem của khách KHÔNG đổi", d["xem"][0]["pw"] == "Xem@123")

# 11. KHÔI PHỤC khi quên — chạy 2 lần liên tiếp (khách đổi pass nhiều lần), không cần reset vật lý
def lay_ma_thu(): return ("CHALLENGE-7788", "78CEA5008532")
def tinh_ma_mo(mt, sr): return "UNLOCK-" + sr[-4:]          # mô phỏng công thức hãng
reset = []; nap = []; lm2 = {}
for lan in range(2):
    r = Q.khoi_phuc_quen("1234", MAY_CHU, "pl", "2", lay_ma_thu, tinh_ma_mo,
                         dat_lai_admin=lambda mo, mk: reset.append((mo, mk)),
                         nap_lai_cau_hinh=lambda creds: nap.append(creds.get("cam_pw")),
                         dong_bo_litemark=lambda stt, u, p: lm2.update(pw=p), mat_khau_moi=f"KhoiPhuc{lan}@")
    ok(f"khôi phục lần {lan+1} thành công", r["ok"] and reset[-1][0] == "UNLOCK-8532")
ok("khôi phục: nạp lại cấu hình cả 2 lần", len(nap) == 2 and lm2["pw"] == "KhoiPhuc1@")

# 11b. Khôi phục khi CHƯA có mã mở → trả mã thử để gửi đại lý
r = Q.khoi_phuc_quen("1234", MAY_CHU, "pl", "2", lay_ma_thu, lambda mt, sr: "",
                     lambda mo, mk: None, lambda c: None, lambda s, u, p: None, "x")
ok("chưa có mã mở → đưa mã thử cho đại lý", not r["ok"] and r["ma_thu"] == "CHALLENGE-7788")

# 12. Máy thợ KHÔNG khôi phục / KHÔNG tạo tài khoản Xem được
try:
    Q.cap_ma_mot_lan("1234", "pl:2"); Q.tho_dung_ma(Q.cap_ma_mot_lan("1234", "pl:2"), MAY_THO)
    Q.tao_tai_khoan_xem("1234", MAY_THO, "pl", "2", "x", "y", lambda c, u, p: None); ok("thợ tạo Xem phải bị chặn", False)
except PermissionError:
    ok("thợ KHÔNG tạo được tài khoản Xem", True)

# 13. Nhật ký ghi lại các mốc (gồm cả lần thợ bị từ chối)
nk = Q.nhat_ky()
viec = {x["viec"] for x in nk}
ok("nhật ký có: thợ bị từ chối đọc mật khẩu", any("xem_mat_khau_tu_choi" in v for v in viec))
ok("nhật ký có: xoay mật khẩu", "xoay_mat_khau" in viec)
ok("nhật ký có: khôi phục", "khoi_phuc_quen" in viec)

print(f"\n✓ Quản trị & Khôi phục: {dat}/{dat} kịch bản nhiều vai ĐẠT — thợ rút không can thiệp được, chỉ chủ xem/đổi, LiteMark không đứt")
