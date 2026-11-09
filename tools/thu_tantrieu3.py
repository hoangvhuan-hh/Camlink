# Qua đúng các hàm lõi app gọi: nhận dự án → nạp file → điểm cần chọn tại cột → gán → kiểm từ xa bỏ qua điểm chưa cài
import sys, json, os, shutil
exec(open('thu_tantrieu.py', encoding='utf-8').read().split("dong = L.doc_file_ddns")[0])
import camlink_core as K
G2 = G + "/app"; shutil.rmtree(G2, True); os.makedirs(G2)
K.khoi_tao(G2)
L.khoa = lambda: "x"
api = {"/api/camlink/cong-trinh": {"cong_trinh": [{"id": "f7ee", "ten": "Cam an ninh tân triều 2", "so_diem": 49, "so_camera": 84, "san_sang_camlink": True}]}}
goc_goi = L._goi
L._goi = lambda duong, du=None, cho=15: api.get(duong) or goc_goi(duong, du, cho)
cho = json.loads(K.lm_cho_nhan()); assert len(cho) == 1, cho
ma = K.lm_nhan_du_an("f7ee", "Cam an ninh tân triều 2", None)
assert K.lm_nhan_du_an("f7ee", "x", None) == ma, "không được tạo trùng"
assert json.loads(K.lm_cho_nhan()) == [], "đã nhận thì không mời nữa"
bc = json.loads(K.lm_nap_ddns(ma, f, None))
assert bc["tu_gan"] == 48 and bc["diem_thieu"] == ["35"]
assert K.can_chon_ten_mien(ma, "35") and not K.can_chon_ten_mien(ma, "1")
uv = json.loads(K.ung_vien_ten_mien(ma, "35")); K.gan_ten_mien(ma, "35", uv[0]["i"])
assert not K.can_chon_ten_mien(ma, "35")
print("✓ nhận 1 lần (không trùng) · ghép 48/49 · điểm 35 chọn tại cột · danh sách mời nhận tự hết")
