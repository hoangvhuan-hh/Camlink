# 2.8.0 — đường dự phòng bằng IP khi tên miền hỏng + điều kiện mở quản trị modem từ xa (mạng giả lập)
import sys, tempfile, json, os, socket
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../app/src/main/python"))
import camlink_core as K
import camlink_dt as C
import camlink_tuxa as T
import camlink_oryza as O
K.khoi_tao(tempfile.mkdtemp())
dat = 0
def kt(ten, dk):
    global dat
    assert dk, ten
    dat += 1; print("✓", ten)

# ---- mạng giả: IP nào đang có cam nào (port → MAC)
MANG = {}                 # ip → {port: mac}
TEN_MIEN = {}             # domain → ip (không có = không phân giải)
DDNS_DA_NHAP = []
T.cham_tg = lambda host, port, cho=4: (("mo", 30) if port in MANG.get(TEN_MIEN.get(host, host), {}) else ("im_lang", 4000))
class OnvifGia:
    def __init__(self, host, port, u, p): self.ip, self.port = TEN_MIEN.get(host, host), port
    def co(self): return self.port in MANG.get(self.ip, {})
    def token_mang(self): return ("eth0", MANG[self.ip][self.port])
    def thong_tin(self): return {"serial": "SER-" + MANG[self.ip][self.port]}
C.Onvif = OnvifGia
O.la_oryza = lambda host, port, cho=4: True
O.dat_ddns = lambda host, port, u, p, dom, du, dp: (DDNS_DA_NHAP.append((host, port, dom)), "DDNS đã nhập")[1]
T.CHO_DDNS = 0

D = {"ten": "Cột 1", "domain": "t1.ddns.net", "u": "a", "p": "b", "so": 2, "bs": 0, "map": ""}
da = {"ten": "Thử", "diem": {"1": D},
      "ho_so": {"1": {"wan": "14.0.0.1", "gw": "192.168.1.1", "web_modem": 8098, "cam": [{"so": 1, "mac": "AA:01"}, {"so": 2, "mac": "AA:02"}]}},
      "vet": {"1": {"mac": ["AA:01", "AA:02"], "ip": [{"ip": "14.0.0.1", "luc": "x"}, {"ip": "14.0.0.9", "luc": "y"}], "domain": []}}}
T._DP.clear(); T._DP.update(T.gom_du_phong(da))
kt("gom IP dự phòng: mới nhất trước, kèm MAC của điểm", T._DP["1"]["ip"] == ["14.0.0.9", "14.0.0.1"] and T._DP["1"]["mac"] == {"AA:01", "AA:02"})

def hong(ip_ten_mien=""):
    cams = [{"so": i + 1, "http": C.HTTP[i], "rtsp": C.RTSP[i], "muc": "do", "web": "", "live": "", "bang_chung": []} for i in range(2)]
    return {"stt": "1", "ten": "Cột 1", "domain": "t1.ddns.net", "ip": ip_ten_mien, "tong": "TÊN MIỀN KHÔNG HOẠT ĐỘNG" if not ip_ten_mien else "MẤT ĐIỆN / MẤT MẠNG CẢ ĐIỂM",
            "muc": "do", "viec": [], "web_modem": "", "cam": cams, "luc": "bây giờ", "so": 2, "so_file": 2, "nguon_so": "thử"}

# 1) tên miền hỏng, điểm thật đang ở IP mới nhất từng thấy
MANG.clear(); MANG["14.0.0.9"] = {8080: "AA:01", 8081: "AA:02", 8098: "MODEM"}
r = T._thu_ip_du_phong(hong(), D, {"cam_user": "admin", "cam_pw": "x"})
kt("tên miền hỏng → tìm thấy điểm qua IP dự phòng", r.get("du_phong", {}).get("ip") == "14.0.0.9" and r["muc"] == "vang")
kt("cả 2 cam được xác minh bằng MAC, có link xem tạm qua IP", all(c.get("qua_ip") == "14.0.0.9" and "14.0.0.9" in c["web"] for c in r["cam"]))
kt("chỉ cam đầu mang việc nhập lại DDNS", [c.get("sua") for c in r["cam"]] == [["nhap_lai_ddns"], []])
kt("link quản trị modem đi theo IP dự phòng", r["web_modem"] == "http://14.0.0.9:8098")

# 2) IP cũ nay thuộc ĐIỂM KHÁC (cam khác MAC, cùng port) → không được nhận nhầm
MANG.clear(); MANG["14.0.0.9"] = {8080: "BB:01", 8081: "BB:02"}
r = T._thu_ip_du_phong(hong(), D, {})
kt("IP cũ đã cấp cho điểm khác (MAC lạ) → KHÔNG nhận nhầm", "du_phong" not in r and r["muc"] == "do")

# 3) chỉ 1 trong 2 cam còn sống ở IP lúc cài
MANG.clear(); MANG["14.0.0.1"] = {8081: "AA:02"}
r = T._thu_ip_du_phong(hong("14.0.0.50"), D, {})
kt("1/2 cam sống qua IP lúc cài → điểm vẫn ĐỎ, cam sống VÀNG", r["du_phong"]["ip"] == "14.0.0.1" and r["muc"] == "do" and [c["muc"] for c in r["cam"]] == ["do", "vang"])

# 4) điểm không có MAC trong hồ sơ → không dám kết luận
T._DP["1"]["mac"] = set()
MANG.clear(); MANG["14.0.0.9"] = {8080: "AA:01"}
kt("hồ sơ không có MAC → không dùng IP dự phòng", "du_phong" not in T._thu_ip_du_phong(hong(), D, {}))
T._DP["1"]["mac"] = {"AA:01", "AA:02"}

# 4b) hồ sơ chỉ lưu số serial (không có MAC) vẫn nhận ra đúng cam
T._DP["1"]["mac"] = {"SER-AA:01"}
kt("hồ sơ lưu serial → vẫn đối chiếu được", T._thu_ip_du_phong(hong(), D, {}).get("du_phong", {}).get("cam") == [8080])
T._DP["1"]["mac"] = {"AA:01", "AA:02"}

# 5) lỗi khác (không phải hỏng tên miền) → không đụng
x = hong(); x["tong"] = "1/2 cam đạt"
kt("lỗi không phải do tên miền → bỏ qua dự phòng", "du_phong" not in T._thu_ip_du_phong(x, D, {}))

# 6) tự sửa: vào cam qua IP dự phòng, nhập lại DDNS đúng tên miền của điểm
MANG.clear(); MANG["14.0.0.9"] = {8080: "AA:01", 8081: "AA:02"}
p = T._thu_ip_du_phong(hong(), D, {})
T._kiem_diem_goc = lambda *a, **k: hong()
moi = T.tu_sua_diem(p, D, {"cam_user": "admin", "cam_pw": "x"}, "", "thu", da["ho_so"]["1"], lambda *a: None)
kt("tự sửa: nhập lại DDNS qua IP dự phòng, đúng cam đầu, đúng tên miền", DDNS_DA_NHAP == [("14.0.0.9", 8080, "t1.ddns.net")])
kt("kết quả ghi rõ đã sửa + dặn chờ tên miền cập nhật", any("DDNS" in v for v in moi["viec"]) and any(c.get("da_sua") for c in moi["cam"]))

# 7) sửa tay "nhập lại DDNS" cũng đi qua IP dự phòng
DDNS_DA_NHAP.clear()
ok, tb = T.sua({**D, "_host": "14.0.0.9"}, 1, "nhap_lai_ddns", {"cam_user": "admin", "cam_pw": "x"})
kt("sửa tay đi vào cam bằng IP, DDNS vẫn nhập tên miền gốc", ok and DDNS_DA_NHAP == [("14.0.0.9", 8080, "t1.ddns.net")])

# 8) điều kiện mở quản trị modem từ xa
kt("mật khẩu modem mặc định/yếu → KHÔNG mở ra Internet", all(C.pass_modem_yeu("admin", x) for x in ["admin", "", "12345678", "Admin", "vnpt", "abc123"]))
kt("mật khẩu modem mạnh → được mở", not C.pass_modem_yeu("admin", "Vn@Lite#2026"))
print(f"\n✓ 2.8.0 dự phòng IP + quản trị modem từ xa: {dat}/{dat} đạt")
