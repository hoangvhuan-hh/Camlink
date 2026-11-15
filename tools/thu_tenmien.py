# 2.4.1 — điểm chưa có tên miền DDNS: hỏi trước khi cài, nhập tay tại cột, không cài mù
import sys, tempfile, json, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../app/src/main/python"))
import camlink_core as K
K.khoi_tao(tempfile.mkdtemp())
da = {"ten": "Thử", "diem": {"1": {"ten": "Cột 1", "domain": "", "u": "", "p": "", "so": 2, "bs": 0, "map": ""},
                             "2": {"ten": "Cột 2", "domain": "thu-02.ddns.net", "u": "a", "p": "b", "so": 1, "bs": 0, "map": ""}},
      "toa_do": {}, "kho_ddns": []}
K._ghi_du_an("thu", da)
dat = 0
def kt(ten, dk):
    global dat
    assert dk, ten
    dat += 1; print("✓", ten)
kt("điểm 1 báo chưa có tên miền", K.ten_mien_diem("thu", "1") == "")
kt("điểm 2 có tên miền", K.ten_mien_diem("thu", "2") == "thu-02.ddns.net")
kt("không có kho → không bật chọn từ kho", not K.can_chon_ten_mien("thu", "1"))
kt("từ chối tên miền sai dạng", K.dat_ten_mien_tay("thu", "1", "khong hop le") != "")
kt("từ chối tên miền trống", K.dat_ten_mien_tay("thu", "1", "") != "")
kt("từ chối trùng điểm khác", "điểm 2" in K.dat_ten_mien_tay("thu", "1", "THU-02.ddns.net"))
kt("nhận tên miền đúng (dán cả http:// và port)", K.dat_ten_mien_tay("thu", "1", " http://Thu-01.DDNS.net:8080/ ", "u1", "p1") == "")
d = K._doc_du_an("thu")["diem"]["1"]
kt("lưu chuẩn hoá + tài khoản DDNS", d["domain"] == "thu-01.ddns.net" and d["u"] == "u1" and d["p"] == "p1" and "nhập tay" in d["dom_nguon"])
kt("điểm 2 không bị đụng", K._doc_du_an("thu")["diem"]["2"]["domain"] == "thu-02.ddns.net")
print(f"\n✓ 2.4.1 tên miền tại cột: {dat}/{dat} đạt")
