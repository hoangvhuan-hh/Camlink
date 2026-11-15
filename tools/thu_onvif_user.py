# 2.3.0 — quản trị ĐA HÃNG qua ONVIF chuẩn: xoay mật khẩu (SetUser), tạo tài khoản Xem (CreateUsers mức User),
# nhận diện hãng (GetDeviceInformation). Giả lập cam ONVIF bất kỳ (không dính hãng nào), kiểm bản tin SOAP + két + LiteMark.
import sys, os, shutil, json
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import camlink_core as K, camlink_dt as C, camlink_quantri as Q, camlink_tuxa as TX

G = "/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/onvif"
shutil.rmtree(G, True); os.makedirs(G + "/duan"); os.makedirs(G + "/ketqua")
K.khoi_tao(G)

# dự án giả: điểm 2, tên miền bất kỳ, 2 cam
duan = {"ten": "Thi cong X", "diem": {"2": {"stt": "2", "ten": "Ngã ba A", "domain": "diem2.ddns.net", "so": 2}}}
json.dump(duan, open(G + "/duan/tc.json", "w", encoding="utf-8"), ensure_ascii=False)
# kết quả kiểm gần nhất (để kiểm đồng bộ LiteMark)
json.dump({"diem": [{"stt": "2", "domain": "diem2.ddns.net", "cam": [{"so": 1, "http": 8080, "user": "admin", "pass": "cu"},
                                                                     {"so": 2, "http": 8081, "user": "admin", "pass": "cu"}]}]},
          open(TX._f_lich_su(G, "tc"), "w", encoding="utf-8"), ensure_ascii=False)

# tài khoản chủ + két
MAY = "may-chu"
Q.tao_tai_khoan("1234", MAY, "Máy chủ")
Q.luu_mat_khau("1234", "tc", "2", "admin", "cu", "admin", "modempw")

# ===== giả lập MỘT cam ONVIF bất kỳ (không hãng cụ thể) =====
goi_log = []
def gia_goi(self, than, xac_thuc=True, cho=8, url=None):
    goi_log.append(than)
    if "GetSystemDateAndTime" in than:
        return "<UTCDateTime><Date><Year>2026</Year><Month>11</Month><Day>15</Day></Date><Time><Hour>5</Hour><Minute>0</Minute><Second>0</Second></Time></UTCDateTime>"
    if "GetDeviceInformation" in than:
        return "<Manufacturer>ACME-IPC</Manufacturer><Model>MX-500</Model><SerialNumber>SN999</SerialNumber><FirmwareVersion>1.0</FirmwareVersion>"
    if "GetUsers" in than:
        return "<User><Username>admin</Username><UserLevel>Administrator</UserLevel></User>"
    return "<Response/>"   # CreateUsers / SetUser / DeleteUsers OK
C.Onvif.goi = gia_goi

dat = 0
def ok(dk, c):
    global dat
    assert c, "SAI: " + dk
    dat += 1; print("  ✓", dk)

# 1. Nhận diện hãng qua ONVIF chuẩn (đa hãng)
r = json.loads(K.qt_nhan_dien_hang("tc", "2", "1234"))
ok("nhận diện hãng qua ONVIF GetDeviceInformation", r["ok"] and r["hang"] == "ACME-IPC" and r["model"] == "MX-500")

# 2. Xoay mật khẩu admin qua ONVIF SetUser trên CẢ 2 cam
goi_log.clear()
tb = K.qt_xoay_mat_khau("1234", MAY, "tc", "2", "MoiPass@9")
soap = " ".join(goi_log)
ok("xoay: gửi lệnh ONVIF SetUser", "SetUser" in soap)
ok("xoay: đặt mức Administrator + mật khẩu mới", "Administrator" in soap and "MoiPass@9" in soap)
ok("xoay: áp cho cả 2 cam (2 lần SetUser)", soap.count("<tds:SetUser>") == 2)
ok("xoay: két cập nhật mật khẩu mới", Q.xem_mat_khau(MAY, "tc", "2", pin="1234")["cam_pw"] == "MoiPass@9")
ls = json.load(open(TX._f_lich_su(G, "tc"), encoding="utf-8"))
ok("xoay: đồng bộ LiteMark (kết quả kiểm có pass mới)", all(c["pass"] == "MoiPass@9" for c in ls["diem"][0]["cam"]))
ok("xoay: doc_cai_dat có pass mới (đường đẩy LiteMark)", C.doc_cai_dat().get("cam_pw") == "MoiPass@9")

# 3. Tạo tài khoản Xem qua ONVIF CreateUsers mức User (chỉ xem)
goi_log.clear()
tb = K.qt_tao_tai_khoan_xem("1234", MAY, "tc", "2", "khach", "Xem@123")
soap = " ".join(goi_log)
ok("tạo Xem: gửi lệnh ONVIF CreateUsers", "CreateUsers" in soap)
ok("tạo Xem: mức 'User' (chỉ xem), không phải Administrator", "<tt:UserLevel>User</tt:UserLevel>" in soap)
ok("tạo Xem: áp cả 2 cam", soap.count("<tds:CreateUsers>") == 2)
ok("tạo Xem: lưu vào két", Q.xem_mat_khau(MAY, "tc", "2", pin="1234")["xem"][0]["user"] == "khach")

# 4. Không dính hãng: đổi 'hãng' cam giả lập, mọi thứ vẫn chạy y hệt
def gia_goi2(self, than, xac_thuc=True, cho=8, url=None):
    goi_log.append(than)
    if "GetSystemDateAndTime" in than:
        return "<UTCDateTime><Date><Year>2026</Year><Month>11</Month><Day>15</Day></Date><Time><Hour>5</Hour><Minute>0</Minute><Second>0</Second></Time></UTCDateTime>"
    if "GetDeviceInformation" in than:
        return "<Manufacturer>Hikvision</Manufacturer><Model>DS-2CD</Model><SerialNumber>HK1</SerialNumber>"
    return "<Response/>"
C.Onvif.goi = gia_goi2
r = json.loads(K.qt_nhan_dien_hang("tc", "2", "1234"))
ok("hãng khác (Hikvision) vẫn nhận diện + chạy chung một đường ONVIF", r["ok"] and r["hang"] == "Hikvision")

print(f"\n✓ 2.3.0 ONVIF đa hãng: {dat}/{dat} đạt — quản trị chạy bằng chuẩn chung, không phụ thuộc Oryza")
