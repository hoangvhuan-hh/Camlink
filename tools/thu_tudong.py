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
kt("WiFi: chưa nhập → không khớp gì", not K.wifi_khop("CAMERA_XA"))
kt("WiFi: từ chối mật khẩu dưới 8 ký tự", K.luu_wifi("CAMERA_XA", "123") != "")
kt("WiFi: lưu tên đúng + khớp chính xác", K.luu_wifi("CAMERA_XA", "12345678") == "" and K.wifi_khop('"CAMERA_XA"') and not K.wifi_khop("CAMERA_XA_2"))
kt("WiFi: tên có * khớp theo phần đầu", K.luu_wifi("VNPT_*", "") == "" and K.wifi_khop("VNPT_AB12") and not K.wifi_khop("Viettel_1"))
kt("WiFi: trang Dự án hiện tên, không lộ mật khẩu", json.loads(K.tom_tat_du_an())["wifi_ten"] == "VNPT_*" and "wifi_mk" not in K.tom_tat_du_an())
print(f"\n✓ 2.6 tự vào WiFi + tự cài: {dat}/{dat} đạt")

# ---- 2.12: "đã cài" theo sự thật — điểm đang chạy (cài từ trước) không bị tự cài lại, dự án tính đúng hoàn thành
import camlink_tuxa as T
d0 = K._doc_du_an("thu")
kt("trước khi có kết quả kiểm: điểm 1 chưa cài → được tự cài", x(10.5002, 106.5001)["ok"])
os.makedirs(os.path.dirname(T._f_lich_su(K.GOC, "thu")), exist_ok=True)
json.dump({"luc": "15/11/2026 17:00", "diem": [{"stt": "1", "luc": "17:00:01 15/11/2026", "cam": [{"so": 1, "muc": "xanh"}, {"so": 2, "muc": "do"}]},
                                              {"stt": "4", "cam": [{"so": 1, "muc": "do"}]}]}, open(T._f_lich_su(K.GOC, "thu"), "w"))
r = x(10.5002, 106.5001)
kt("điểm 1 đang chạy theo kiểm tra từ xa → KHÔNG tự cài lại, báo đã cài", not r["ok"] and r.get("da_cai") and "đang chạy" in r["ly_do"])
d0.setdefault("vet", {})["5"] = {"mac": ["AA:05"], "ip": [], "domain": []}; K._ghi_du_an("thu", d0)
q = [p for p in json.loads(K.tom_tat_du_an())["du_an"] if p["ma"] == "thu"][0]
kt("đếm đã cài: 1 (đang chạy) + 2 (app cài) + 5 (từng thấy cam) = 3/5, chưa hoàn thành", q["da_xong"] == 3 and not q["hoan_thanh"])
D2 = lambda dom: {"ten": "Cột", "domain": dom, "u": "a", "p": "b", "so": 1, "bs": 0, "map": ""}
K._ghi_du_an("xong", {"ten": "Đã xong", "diem": {"1": D2("x1.ddns.net"), "2": D2("x2.ddns.net")}, "toa_do": {}, "da_xong": {}})
ma_x = [r[0] for r in K.ds_du_an() if r[1] == "Đã xong"][0]      # app chuẩn hoá mã dự án theo tên
json.dump({"luc": "x", "diem": [{"stt": "1", "cam": [{"so": 1, "muc": "xanh"}]}, {"stt": "2", "cam": [{"so": 1, "muc": "xanh"}]}]}, open(T._f_lich_su(K.GOC, ma_x), "w"))
q = [p for p in json.loads(K.tom_tat_du_an())["du_an"] if p["ma"] == ma_x][0]
kt("dự án cài từ trước, cam đang lên đủ → HOÀN THÀNH 2/2 (trước đây báo 0/2)", q["hoan_thanh"] and q["da_xong"] == 2)
print(f"✓ 2.12 đã cài theo sự thật: {dat}/{dat} đạt")
