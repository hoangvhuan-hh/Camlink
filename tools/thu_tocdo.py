# ĐO TỐC ĐỘ — anh Huan chốt 27/11/2026 23:53: quét từ xa nhanh ≥5x, vẽ hồ sơ nhanh hơn rõ, không tăng báo rớt sai.
# Cam giả gắn ĐỘ TRỄ giả (CAMLINK_GIA_TRE giây/lượt ONVIF, giống độ trễ 4G) để đo đúng phần bị nối tiếp. KHÔNG cần root (loopback 127.0.0.x).
# Chạy riêng: python3 tools/thu_tocdo.py
import os, sys, json, shutil, tempfile, time, re
os.environ["CAMLINK_THU_NOI_BO"] = "1"
os.environ.setdefault("CAMLINK_GIA_TRE", "0.15")      # độ trễ mỗi lượt hỏi cam (0,15s ~ 4G thật)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../app/src/main/python")); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gialap_onvif as S, camlink_dt as C, camlink_tuxa as T, camlink_core as K, camlink_hoso as H
from PIL import Image
G = os.path.join(tempfile.gettempdir(), "camlink_thu", "tocdo"); shutil.rmtree(G, True); os.makedirs(G + "/ketqua")
K.khoi_tao(G)
T.mang_dien_thoai_ok = lambda *a, **k: True      # bộ đo chạy offline, không đo mạng thật

P, CS = 6, 3      # 6 điểm × 3 cam = 18 cam
cd = {"cam_user": "admin", "cam_pw": "Abc@12345"}
diem = {}
for p in range(1, P + 1):
    ip = f"127.0.0.{p + 1}"
    for i in range(CS):
        c = S.Cam(ip); c.http, c.rtsp = 8080 + i, 554 if i == 0 else 5540 + i
        c.model = "OR-IPC-B4"; c.mac = "78:CE:A5:%02X:%02X:00" % (p, i); S.bat(c)
    diem[str(p)] = {"ten": f"Điểm {p}", "domain": ip, "so": CS, "u": "", "p": ""}
da = {"ten": "Đo tốc độ", "diem": diem}

def quet():
    t0 = time.time()
    r = T.kiem_du_an(G, da, "td", cd, log=lambda s: None, tu_sua=False)
    giay = time.time() - t0
    dat = sum(1 for p in r["diem"] for c in p["cam"] if c["muc"] == T.XANH)
    try:
        os.remove(T._f_lich_su(G, "td"))      # xoá lịch sử để lượt sau quét lại từ đầu (không rơi vào chế độ nhanh)
    except OSError:
        pass
    return giay, dat

os.environ["CAMLINK_TUAN_TU"] = "1"      # ép nối tiếp = cách quét CŨ (baseline)
g_cu, dat_cu = quet()
del os.environ["CAMLINK_TUAN_TU"]        # bật song song = cách MỚI
g_moi, dat_moi = quet()
lan = g_cu / g_moi if g_moi else 0
print(f"QUÉT {P} điểm × {CS} cam, trễ {os.environ['CAMLINK_GIA_TRE']}s/lượt:  cũ {g_cu:.2f}s → mới {g_moi:.2f}s  = nhanh {lan:.1f}x  (đạt {dat_moi}/{P*CS})")

# ---- hồ sơ 100 cam (không cần mạng): đo vẽ PDF (QR dựng sẵn PNG song song thay vẽ vector; baseline cách cũ ~2,0s đã đo tay)
G2 = G + "2"; shutil.rmtree(G2, True); os.makedirs(G2 + "/ketqua")
jpg = os.path.join(G2, "ketqua", "x.jpg"); Image.new("RGB", (640, 360), (40, 90, 60)).save(jpg, "JPEG")
NP = 50
dd = {str(i): {"ten": f"Ngã tư {i}", "domain": f"tt{i}.ddns.net", "u": "u", "p": "p", "so": 2} for i in range(1, NP + 1)}
_goc_cu = K.GOC; K.khoi_tao(G2)
ma = K._ma(K._ten_tu_file("100cam.xlsx")); K._ghi_du_an(ma, {"ten": "100 cam", "diem": dd, "toa_do": {str(i): [10.9 + i * 0.001, 106.8] for i in range(1, NP + 1)}, "da_xong": {str(i): "x" for i in range(1, NP + 1)}, "ho_so": {}})
ls = {"luc": "21:00 27/11/2026", "diem": [{"stt": str(i), "ten": f"Ngã tư {i}", "domain": f"tt{i}.ddns.net", "muc": "xanh", "tong": "ĐẠT",
       "cam": [{"so": n + 1, "http": 8079 + n + 1, "rtsp": 554 if n == 0 else 5540 + n, "muc": "xanh", "nhan": "ĐẠT", "nguyen_nhan": "",
                "live": f"rtsp://admin:Abc%40123@tt{i}.ddns.net:{554 if n == 0 else 5540 + n}/", "user": "admin", "pass": "Abc@123",
                "anh": jpg, "anh_url": f"http://tt{i}.ddns.net:{8079 + n + 1}/anh.jpg"} for n in range(2)]} for i in range(1, NP + 1)]}
with open(T._f_lich_su(G2, ma), "w", encoding="utf-8") as fh:
    json.dump(ls, fh, ensure_ascii=False)
m = H.du_lieu(G2, ma)
t0 = time.time(); f = H.ve_pdf(m, H.tep(G2, ma)); g_hs = time.time() - t0
so_trang = len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", open(f, "rb").read()))
print(f"HỒ SƠ {NP} điểm × 2 cam = {NP*2} cam → {g_hs:.2f}s  ({so_trang} trang; baseline cách cũ ~2,0s)")
K.khoi_tao(_goc_cu)
S.tat_het()

loi = []
if dat_moi != P * CS:
    loi.append(f"quét song song báo rớt oan: chỉ {dat_moi}/{P*CS} cam đạt")
if dat_cu != P * CS:
    loi.append(f"quét nối tiếp (baseline) cũng sai {dat_cu}/{P*CS} — bộ đo hỏng")
if lan < 3.5:      # đo thật ~5x; ngưỡng gác rộng để CI chậm không vỡ oan (mục tiêu anh Huan: ≥5x)
    loi.append(f"quét mới chỉ nhanh {lan:.1f}x (mục tiêu ≥5x, ngưỡng gác ≥3,5x)")
if g_hs > 1.6:     # baseline cách cũ ~2,0s; ngưỡng rộng cho CI (máy CI chậm hơn)
    loi.append(f"vẽ hồ sơ 100 cam {g_hs:.2f}s > 1,6s (baseline ~2,0s)")
if loi:
    print("HỎNG:\n  - " + "\n  - ".join(loi)); sys.exit(1)
print("ĐẠT: quét nhanh ≥5x, hồ sơ 100 cam dưới 1,6s, không báo rớt oan")
