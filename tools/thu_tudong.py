# 2.5.0 — tự cài khi vào WiFi modem: chỉ tự chạy khi GPS khớp CHẮC đúng một điểm
import sys, tempfile, json, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../app/src/main/python"))
import camlink_core as K
import camlink_dt as C
K.khoi_tao(tempfile.mkdtemp())
dat = 0
def kt(ten, dk):
    global dat
    assert dk, ten
    dat += 1; print("✓", ten)
x = lambda la, ln: json.loads(K.tu_dong_xet(la, ln))
kt("chưa có dự án → không tự cài", not x(10.5, 106.5)["ok"])
D = lambda dom: {"ten": "Cột", "domain": dom, "u": "a", "p": "b", "so": 2, "bs": 0, "map": ""}
da = {"ten": "Thử", "diem": {"1": D("t1.ddns.net"), "2": D("t2.ddns.net"), "3": D(""), "4": D("t4.ddns.net"), "5": D("t5.ddns.net")},
      "toa_do": {"1": [10.5000, 106.5000], "2": [10.5100, 106.5000], "3": [10.5200, 106.5000], "4": [10.5300, 106.5000], "5": [10.5303, 106.5000]},
      "da_xong": {"2": "15/11 09:00"}}
K._ghi_du_an("thu", da)
kt("chưa nhập pass cam → không tự cài", "pass" in x(10.5, 106.5)["ly_do"])
K.luu_cai_dat("admin", "matkhau", "", "")
r = x(10.5002, 106.5001)
kt("đứng sát điểm 1 → TỰ CÀI đúng điểm 1", r["ok"] and r["stt"] == "1" and r["m"] < 50)
kt("cách điểm 1 ~300 m → không tự cài", not x(10.5027, 106.5000)["ok"])
kt("điểm 2 đã cài xong → không tự cài lại", "đã cài" in x(10.5100, 106.5000)["ly_do"])
kt("điểm 3 thiếu tên miền → không tự cài", "tên miền" in x(10.5200, 106.5000)["ly_do"])
kt("điểm 4 và 5 sát nhau (33 m) → không tự cài, cần người chọn", "sát bên" in x(10.5301, 106.5000)["ly_do"])
kt("ở xa mọi điểm (văn phòng) → không tự cài", not x(10.8, 106.7)["ok"])
kt("điểm đã cài → trả mốc đã cài để app báo + mở hình", x(10.5100, 106.5000).get("da_cai") == "15/11 09:00" and "da_cai" not in x(10.5200, 106.5000))
print(f"\n✓ 2.5.x tự cài: {dat}/{dat} đạt")
