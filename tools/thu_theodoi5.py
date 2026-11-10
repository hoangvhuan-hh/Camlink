# 1.9.6: cam rớt ≥5 phút → sửa đúng cam trong kết quả gần nhất, đẩy CẢ ẢNH CHỤP DỰ ÁN lên LiteMark (điểm khác giữ nguyên); lên lại → gỡ
import sys, os, shutil, json, time
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
G = "/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/td5"; shutil.rmtree(G, True); os.makedirs(G)
import camlink_core as K, camlink_litemark as L, camlink_tuxa as T
K.khoi_tao(G)
gui = []
L.lien_ket = lambda ma: {"id": "abc", "ten": "Phú Lý"}
L._goi = lambda duong, than: gui.append(json.loads(json.dumps(than)))
K._doc_du_an = lambda ma: {"diem": {"2": {"lm_stt": "10", "lm_chac": True}, "4": {"lm_stt": "4"}}}
kq = {"dat": 4, "tong_cam": 4, "diem": [
    {"stt": "2", "ten": "Chùa Pháp Bảo", "domain": "pl.ddns.net", "muc": "xanh", "tong": "ĐẠT", "cam": [{"so": 1, "http": 8080, "muc": "xanh", "nhan": "Đạt"}, {"so": 2, "http": 8081, "muc": "xanh", "nhan": "Đạt"}]},
    {"stt": "4", "ten": "Điểm 4", "domain": "p4.ddns.net", "muc": "do", "tong": "0/2", "cam": [{"so": 1, "http": 8080, "muc": "do", "nhan": "Cam không trả lời"}, {"so": 2, "http": 8081, "muc": "do", "nhan": "x"}]}]}
json.dump(kq, open(T._f_lich_su(G, "pl"), "w"))
b = {"kieu": "rot", "ma": "pl", "stt": "2", "so": 1, "http": 8080, "bd": time.time() - 320, "loai": "cam_treo", "nguyen_nhan": "Cam treo"}
assert K._theodoi_bao_lm(b)
t = gui[-1]
d2 = next(x for x in t["diem"] if x["stt"] == "10")
print("rớt → gửi:", [(x["stt"], x["muc"], [(c["so"], c["muc"], c["nhan"]) for c in x["cam"]]) for x in t["diem"]], "| điểm đạt:", t["diem_dat"])
assert d2["muc"] == "do" and d2["cam"][0]["muc"] == "do" and d2["cam"][1]["muc"] == "xanh"
assert any(x["stt"] == "4" for x in t["diem"])                 # điểm 4 vẫn còn cảnh báo cũ
assert K._theodoi_bao_lm({**b, "kieu": "len", "dur": 400})
t = gui[-1]
print("lên → gửi:", [x["stt"] for x in t["diem"]], "| điểm đạt:", t["diem_dat"])
assert "10" in t["diem_dat"] and all(x["stt"] != "10" for x in t["diem"])
ls = json.load(open(T._f_lich_su(G, "pl")))
assert ls["diem"][0]["cam"][0]["muc"] == "xanh"
print("✓ đẩy LiteMark đúng ghim 10 khi rớt/lên, điểm khác giữ nguyên")
