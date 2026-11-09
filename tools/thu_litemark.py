# Backtest nối LiteMark với máy chủ giả: khoá sai → 401; danh sách; gợi ý; đồng bộ ghim; cảnh báo + hàng đợi khi rớt mạng
import os, sys, json, threading, shutil, time
from http.server import BaseHTTPRequestHandler, HTTPServer
os.environ["CAMLINK_LITEMARK"] = "http://127.0.0.1:18765"
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
G = "/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/lm"; shutil.rmtree(G, True); os.makedirs(G)
NHAN = []
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _tra(self, ma, du):
        b = json.dumps(du, ensure_ascii=False).encode(); self.send_response(ma); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.headers.get("Authorization") != "Bearer KHOA_DUNG_1234567890abcdef": return self._tra(401, {"error": "sai khoá"})
        if self.path == "/api/camlink/cong-trinh":
            return self._tra(200, {"cong_trinh": [{"id": "ct9", "ten": "Cổng chào Ayun", "so_diem": 1, "trang_thai": "xong", "cap_nhat": "2026-10-01"},
                                                 {"id": "ct1", "ten": "Công trình camera an ninh xã Phú Lý", "so_diem": 11, "so_camera": 23, "trang_thai": "da_khoa", "cap_nhat": "2026-11-03"},
                                                 {"id": "ct2", "ten": "Camera Tân Triều", "so_diem": 50, "trang_thai": "dang_thi_cong", "cap_nhat": "2026-11-08"}]})
        if self.path == "/api/camlink/cong-trinh/ct1/diem":
            return self._tra(200, {"id": "ct1", "ten": "Công trình camera an ninh xã Phú Lý",
                                   "diem": [{"stt": i, "ten": f"VT{i}", "lat": 11.0 + i * 0.001, "lng": 107.0, "so_camera": 3 if i == 8 else 2} for i in range(1, 12)]})
        return self._tra(404, {"error": "Không có"})
    def do_POST(self):
        if self.headers.get("Authorization") != "Bearer KHOA_DUNG_1234567890abcdef": return self._tra(401, {})
        n = int(self.headers.get("Content-Length", 0)); NHAN.append(json.loads(self.rfile.read(n))); self._tra(200, {"ok": True, "luc_nhan": "x"})
sv = HTTPServer(("127.0.0.1", 18765), H); threading.Thread(target=sv.serve_forever, daemon=True).start()
import camlink_litemark as L
L.khoi_tao(G)
# 1. khoá sai → thông báo rõ
L.luu_khoa("https://litemark.vn/camlink?khoa=SAI")
try: L.ds_cong_trinh(); print("✖ phải 401")
except RuntimeError as e: print("1 ✓ khoá sai →", str(e)[:60])
# 2. khoá đúng (dán dạng link) → danh sách + gợi ý
assert L.luu_khoa("litemark://camlink?khoa=KHOA_DUNG_1234567890abcdef") == "KHOA_DUNG_1234567890abcdef"
ds = L.ds_cong_trinh(); assert ds[0]["id"] == "ct2", "đang thi công phải lên đầu"
gy = L.goi_y("camera-xa-phu-ly", 11, ds); assert gy[0]["id"] == "ct1" and gy[0]["diem_khop"] >= 3, gy[0]
print("2 ✓ gợi ý đúng Phú Lý (điểm khớp", gy[0]["diem_khop"], ")")
# 3. nối + đồng bộ ghim: điểm 4 có toạ độ Excel lệch 300 m, LiteMark ghi 3 cam ở điểm 8 (file 2)
da = {"ten": "camera-xa-phu-ly", "diem": {str(i): {"ten": f"Điểm {i}", "domain": f"pl{i}.ddns.net", "so": 2} for i in range(1, 12)},
      "toa_do": {"4": [11.004 + 0.0027, 107.0], "1": [11.001, 107.0]}}
L.noi("pl", gy[0]); da, gc = L.dong_bo_ghim("pl", da, lambda s: None)
# ghép theo VỊ TRÍ: điểm 1 → ghim 1 (0 m); điểm 4 (Excel 11.0067) → ghim 7 (gần nhất, 33 m); điểm khác không có toạ độ → chưa chắc
assert da["diem"]["1"]["lm_stt"] == "1" and da["diem"]["4"]["lm_stt"] == "7" and da["diem"]["4"]["lm_chac"]
assert da["toa_do"]["4"] == [11.007, 107.0] and len(da["toa_do"]) == 11 and da["toa_do_goc"]["4"][0] > 11.006
assert sum(1 for g in gc if "CHƯA CHẮC" in g) == 9 and any("3 camera" in g for g in gc), gc
print("3 ✓ ghép theo vị trí, ghim LiteMark thay toạ độ Excel; ghi chú:", len(gc))
assert L.link_diem("pl", 4, da) == "http://127.0.0.1:18765/ct/ct1/diem/7"
# 4. cảnh báo: rớt mạng → xếp hàng; mạng lại → gửi bù
kq = {"dat": 20, "tong_cam": 23, "diem": [{"stt": "2", "ten": "x", "muc": "do", "tong": "1/2", "cam": [{"so": 1, "http": 8080, "muc": "do", "nhan": "Không lên", "nguyen_nhan": "im", "viec": ["a"]}]}]}
sv.shutdown(); sv.server_close()
assert L.goi_canh_bao("pl", kq, "1.7.0", lambda s: None, da) is False and os.path.exists(L._f("cho_pl.json"))
print("4 ✓ rớt mạng → xếp hàng")
sv = HTTPServer(("127.0.0.1", 18765), H); threading.Thread(target=sv.serve_forever, daemon=True).start()
assert L.gui_bu("pl", lambda s: None) and NHAN[-1]["tong"] == {"dat": 20, "tong": 23} and NHAN[-1]["diem"][0]["cam"][0]["http"] == 8080
assert NHAN[-1]["diem"][0]["stt"] == da["diem"]["2"]["lm_stt"] and NHAN[-1]["diem"][0]["stt_camlink"] == "2" and NHAN[-1]["chi_bao_loi"]
assert not os.path.exists(L._f("cho_pl.json"))
print("5 ✓ gửi bù xong, hàng đợi trống")
