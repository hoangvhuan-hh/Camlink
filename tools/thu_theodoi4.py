# 1.9.6: theo dõi CẢ ĐIỂM (đo chung 1 lượt) · cam TREO (nhận kết nối mà câm) · báo ngay khi rớt ≥ BAO_SAU · 1 báo cáo chung · khoảng trống do app bị dừng
import sys, os, shutil, time, json
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import camlink_theodoi as T
G = "/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/td4"; shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
T.khoi_tao(G); T.NHIP = 1; T.BAO_SAU = 3; T.ANH_MOI = 10 ** 9
T._chup = lambda m, ten: ""
T._mang_ok = lambda: True
T._ip = lambda d: "113.188.130.14"
hoi = []
bd = None
def hoi_web(h, p, cho=4):
    hoi.append(p)
    el = time.time() - bd
    if p == 8080 and 4 < el < 11:
        return ("treo", 3000)           # cam 1 treo ~7 giây
    return ("mo", 120)
T._hoi_web = hoi_web
import camlink_tuxa; camlink_tuxa.rtsp_describe = lambda *a, **k: (200, "", "")
bao = []
T.KHI_BAO = lambda b: bao.append(b)
p = {"stt": "2", "ten": "Ngã ba chùa Pháp Bảo", "domain": "phuly-chuaphapbao.ddns.net", "du_an": "Camera Xa Phu Ly",
     "cam": [{"so": 1, "http": 8080, "live": "rtsp://a:b@phuly-chuaphapbao.ddns.net:554/snl/live/1/1"},
             {"so": 2, "http": 8081, "live": "rtsp://a:b@phuly-chuaphapbao.ddns.net:5541/snl/live/1/1"}]}
gid = T.bat_diem("pl", p, 0.3, {"cam_user": "a", "cam_pw": "b"})
assert T.bat_diem("pl", p, 0.3, {}) == gid                    # bật lại → không tạo trùng
bd = time.time(); pdf = []; luot = 0
while True:
    r = T.vong("di_dong" if time.time() - bd < 8 else "wifi")
    luot += 1 if r["dang"] else 0
    pdf += r["pdf_moi"]
    if r["xong_moi"]: break
    time.sleep(1)
h = T.ds_hien()
print("danh sách:", [(x["ten"], x["trang_thai"], x["so_rot"], x["cams"]) for x in h])
assert len(h) == 1 and h[0]["cams"] == [8080, 8081]
n = len([x for x in hoi])
mau1 = [json.loads(x) for x in open(T._thu_muc(T._cung_nhom(gid)[0]["id"], "mau.jsonl"))]
print("số lượt đo:", len(mau1), "| số lần hỏi web:", n, "→ mỗi lượt hỏi", round(n / len(mau1), 2), "port (2 cam, không hỏi trùng)")
assert abs(n / len(mau1) - 2) < 0.3
sk1 = T._doc(T._thu_muc(T._cung_nhom(gid)[0]["id"], "su_kien.json"))
sk2 = T._doc(T._thu_muc(T._cung_nhom(gid)[1]["id"], "su_kien.json"))
print("cam 1:", [(x["loai"], round(x["dur"])) for x in sk1], "| cam 2:", sk2)
assert len(sk1) == 1 and sk1[0]["loai"] == "cam_treo" and not sk2
print("báo ngay:", [(b["kieu"], b["ten"], b.get("loai")) for b in bao])
assert [b["kieu"] for b in bao] == ["rot", "len"] and bao[0]["loai"] == "cam_treo"
assert len(pdf) == 1 and "2cam" in pdf[0], pdf
a = T.phan_tich(T._cung_nhom(gid)[0]["id"])
print("đổi mạng:", a["doi_mang"])
assert len(a["doi_mang"]) == 1
# khoảng trống: app bị dừng 10 phút giữa chừng → không tính là lên
m = T._doc(T._thu_muc(T._cung_nhom(gid)[0]["id"], "meta.json"))
f = T._thu_muc(m["id"], "mau.jsonl")
ls = [json.loads(x) for x in open(f)]
for x in ls[len(ls) // 2:]: x["t"] += 600
m["het"] += 600; T._ghi(T._thu_muc(m["id"], "meta.json"), m)
open(f, "w").write("\n".join(json.dumps(x) for x in ls))
a = T.phan_tich(m["id"])
print("khoảng trống:", len(a["trong"]), "lần,", round(a["ngu"]), "giây không đo")
assert len(a["trong"]) == 1 and a["ngu"] > 590
print("PDF:", pdf[0])
print("✓ 1.9.6: theo dõi cả điểm, phát hiện treo, báo ngay, 1 báo cáo chung, khoảng trống")
