# 2.7.0 — user/pass RIÊNG theo điểm: ưu tiên hơn mặc định, KHÔNG đổi mặc định cả hệ thống
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
D = lambda dom: {"ten": "Cột", "domain": dom, "u": "a", "p": "b", "so": 2, "bs": 0, "map": ""}
K._ghi_du_an("thu", {"ten": "Thử", "diem": {"1": D("t1.ddns.net"), "2": D("t2.ddns.net")}, "toa_do": {}, "da_xong": {}})
kt("lưu 6 ô mặc định một chỗ", K.luu_tat_ca_mac_dinh("admin", "CamChung1", "admin", "ModemChung1", "CAM_XA", "WifiChung1") == "")
kt("đọc lại đủ 6 ô", K.lay_tat_ca_mac_dinh() == ["admin", "CamChung1", "admin", "ModemChung1", "CAM_XA", "WifiChung1"])
kt("mật khẩu WiFi mặc định <8 ký tự bị từ chối, không lưu gì", K.luu_tat_ca_mac_dinh("x", "y", "z", "t", "CAM_XA", "123") != "" and K.lay_cai_dat()[1] == "CamChung1")
kt("điểm chưa nhập riêng → dùng mặc định", K.lay_rieng("thu", "1") == ["admin", "CamChung1", "admin", "ModemChung1", "CAM_XA", "WifiChung1", ""])
kt("nhập WiFi riêng điểm 1", K.luu_rieng("thu", "1", "admin", "CamChung1", "admin", "ModemChung1", "NHA_VAN_HOA", "WifiRieng9") == "")
r = K.lay_rieng("thu", "1")
kt("điểm 1 ưu tiên WiFi riêng, cam/modem vẫn theo mặc định", r[4:] == ["NHA_VAN_HOA", "WifiRieng9", "1"] and r[:4] == ["admin", "CamChung1", "admin", "ModemChung1"])
kt("chỉ lưu ô KHÁC mặc định", K._doc_du_an("thu")["diem"]["1"]["rieng"] == {"wifi_ten": "NHA_VAN_HOA", "wifi_mk": "WifiRieng9"})
kt("MẶC ĐỊNH cả hệ thống không đổi", K.lay_tat_ca_mac_dinh() == ["admin", "CamChung1", "admin", "ModemChung1", "CAM_XA", "WifiChung1"])
kt("điểm 2 không bị ảnh hưởng", K.lay_rieng("thu", "2")[4:] == ["CAM_XA", "WifiChung1", ""])
kt("nhập pass cam + modem riêng điểm 2", K.luu_rieng("thu", "2", "admin", "CamRieng2", "root", "ModemRieng2", "CAM_XA", "WifiChung1") == "")
cd2 = C.cd_diem(K._doc_du_an("thu")["diem"]["2"], C.doc_cai_dat())
kt("lúc cài điểm 2 dùng user/pass riêng", (cd2["cam_pw"], cd2["modem_user"], cd2["modem_pw"], cd2["wifi_ten"]) == ("CamRieng2", "root", "ModemRieng2", "CAM_XA"))
kt("đổi mặc định sau đó: điểm theo mặc định đổi theo, điểm riêng giữ riêng", K.luu_tat_ca_mac_dinh("admin", "CamMoi", "admin", "ModemChung1", "CAM_XA", "WifiChung1") == "" and K.lay_rieng("thu", "1")[1] == "CamMoi" and K.lay_rieng("thu", "2")[1] == "CamRieng2")
kt("nhập lại trùng mặc định → bỏ chế độ riêng", K.luu_rieng("thu", "1", "admin", "CamMoi", "admin", "ModemChung1", "CAM_XA", "WifiChung1") == "" and "rieng" not in K._doc_du_an("thu")["diem"]["1"])
kt("WiFi khớp theo tên riêng của điểm", K.wifi_khop("NHA_VAN_HOA", "NHA_VAN_HOA") and not K.wifi_khop("CAM_XA", "NHA_VAN_HOA") and K.wifi_khop("CAM_XA"))
kt("trang Dự án đếm điểm dùng riêng", json.loads(K.tom_tat_du_an())["du_an"][0]["rieng"] == 1)
kt("xoá riêng → về mặc định", K.xoa_rieng("thu", "2") == "" and K.lay_rieng("thu", "2")[6] == "")
print(f"\n✓ 2.7.0 user/pass riêng theo điểm: {dat}/{dat} đạt")
