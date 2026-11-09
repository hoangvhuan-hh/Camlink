# Backtest bằng 49 ghim THẬT của "Cam an ninh tân triều 2" (LiteMark) + file tên miền giả lập lệch thực tế
import sys, json, random, math, os, shutil
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import camlink_litemark as L, openpyxl
G = "/tmp/claude-0/-home-claude/ee4cb562-845a-57dc-b797-8c1359dd9ac2/scratchpad/tt"; shutil.rmtree(G, True); os.makedirs(G + "/litemark")
L.GOC = G
P = [[1,11.013517,106.853532,1,0,"TT24"],[2,11.013496,106.854246,1,0,"TT26"],[3,11.013702,106.854683,3,0,"TT25"],[4,11.014133,106.856877,2,0,"TT43"],[5,11.011523,106.854868,2,0,"TT27"],[6,11.002245,106.851261,2,0,"TT50"],[7,10.995707,106.846596,3,0,"TT28"],[8,10.984851,106.846588,3,0,"TT29"],[9,10.980205,106.83999,3,0,"TT32"],[10,10.978515,106.847262,2,1,"TT31"],[11,10.978448,106.847833,2,0,"TT30"],[12,10.967055,106.85396,3,0,"TT40"],[13,10.966417,106.851796,1,0,"TT37"],[14,10.964728,106.844259,1,0,"TT49"],[15,10.964278,106.843905,2,0,"TT36"],[16,10.963936,106.841464,1,0,"TT38"],[17,10.963647,106.840185,1,0,"TT48"],[18,10.963077,106.837601,3,0,"TT39"],[19,10.962533,106.83579,1,0,"TT47"],[20,10.956769,106.818209,0,0,"TT42"],[21,10.976949,106.800361,2,0,"TT41"],[22,10.981316,106.799343,1,0,"TT08"],[23,10.994082,106.80188,2,0,"TT09"],[24,10.996318,106.804588,2,0,"TT35"],[25,10.998708,106.806483,1,0,"TT05"],[26,10.999353,106.80665,1,0,"TT06"],[27,10.999203,106.807178,1,0,"TT04"],[28,10.999125,106.809503,2,0,"TT03"],[29,10.997178,106.81319,2,0,"TT01"],[30,10.997412,106.8132,2,0,"TT02"],[31,11.004602,106.820381,2,0,"TT34"],[32,11.004428,106.820825,2,0,"TT33"],[33,11.009823,106.829571,2,0,"TT18"],[34,11.011515,106.829575,1,0,"TT17"],[35,11.012476,106.829515,2,0,"TT16"],[36,11.011827,106.842277,1,0,"TT21"],[37,11.011682,106.842148,1,0,"TT20"],[38,11.012369,106.845988,4,0,"TT22"],[39,11.013157,106.850789,2,0,"TT23"],[40,11.0353,106.843778,2,0,"TT44"],[41,11.032165,106.830598,1,0,"Điểm 41"],[42,11.029537,106.816506,2,0,"TT13"],[43,11.029142,106.816184,1,0,"TT12"],[44,11.038327,106.814903,1,0,"TT15"],[45,11.0385,106.815313,1,0,"TT14"],[46,11.056374,106.80136,2,0,"TT45"],[47,11.007302,106.803183,1,0,"TT11"],[48,11.007371,106.802852,1,0,"TT10"],[49,11.007808,106.780236,2,0,"TT46"]]
L.khoa = lambda: "x"
L._goi = lambda duong, du=None, cho=15: {"ten": "Cam an ninh tân triều 2", "diem": [{"stt": p[0], "ten": p[5], "lat": p[1], "lng": p[2], "so_camera": p[3], "so_camera_bs": p[4]} for p in P]}
da = L.tao_du_an_tu_lm("f7ee", "", lambda s: None)
print("dự án:", len(da["diem"]), "điểm,", sum(d["so"] for d in da["diem"].values()), "cam; số điểm hai bên trùng:", all(d["lm_stt"] == s for s, d in da["diem"].items()))

def lech(lat, lng, m):
    a = random.random() * 2 * math.pi
    return lat + m * math.cos(a) / 111320, lng + m * math.sin(a) / (111320 * math.cos(math.radians(lat)))
random.seed(7)
ma_co = {p[5]: p for p in P if p[5].startswith("TT")}
rows = []
for n in range(1, 51):
    k = f"TT{n:02d}"
    if k in ma_co:
        p = ma_co[k]
        m = random.uniform(27, 49) if n in (5, 13, 22, 33, 44) else random.uniform(2, 24)
        la, lo = lech(p[1], p[2], m)
        if n == 16: la, lo = lech(p[1], p[2], 400)       # khảo sát sai chỗ: cùng mã nhưng lệch 400 m
        rows.append([n, k, f"{la:.6f},{lo:.6f}", p[3], p[4], f"tantrieu-{n:02d}.ddns.net"])
    else:
        rows.append([n, k, "", 1, 0, f"tantrieu-{n:02d}.ddns.net"])   # mã không có ghim (TT07, TT19…)
# cột cam tầm cao "Điểm 41" không có mã: một dòng file chỉ có toạ độ, không mã
la, lo = lech(11.032165, 106.830598, 12)
rows.append([51, "Cam tầm cao HL15", f"{la:.6f},{lo:.6f}", 1, 0, "tantrieu-hl15.ddns.net"])
wb = openpyxl.Workbook(); ws = wb.active
ws.append(["No", "Tên bản vẽ", "Vị trí", "Camera", "Camera BS", "Domain", "USER", "PW"])
for r in rows: ws.append(r + ["noip_tt", "pw_tt"])
f = G + "/ddns_tantrieu.xlsx"; wb.save(f)

dong = L.doc_file_ddns(f, lambda u: None, lambda s: None)
da, bc = L.ghep_ddns(da, dong, print)
print("báo cáo:", json.dumps({k: v for k, v in bc.items() if k != "chenh_cam"}, ensure_ascii=False))
# kiểm đúng: mỗi ghim có mã TTxx phải nhận tantrieu-xx; ghim TT16 (lệch 400 m) KHÔNG tự gán; Điểm 41 nhận hl15 theo toạ độ
sai = [(s, d["domain"]) for s, d in da["diem"].items() if d.get("domain") and d.get("lm_ten", "").startswith("TT") and d["domain"] != f"tantrieu-{int(d['lm_ten'][2:]):02d}.ddns.net"]
assert not sai, sai
assert not da["diem"]["35"].get("domain"), "TT16 lệch 400 m không được tự gán"
assert da["diem"]["41"]["domain"] == "tantrieu-hl15.ddns.net"
uv = L.ung_vien_ten_mien(da, "35")
print("Ghim 35 (TT16) chọn tại cột — ứng viên đầu:", uv[0])
assert uv[0]["domain"] == "tantrieu-16.ddns.net"
L.gan_ten_mien(da, "35", uv[0]["i"])
assert da["diem"]["35"]["domain"] == "tantrieu-16.ddns.net" and not any(x["domain"] == "tantrieu-16.ddns.net" for x in L.ung_vien_ten_mien(da, "1"))
try: L.gan_ten_mien(da, "1", uv[0]["i"]); print("✖ cho gán trùng")
except RuntimeError as e: print("✓ chặn gán trùng:", e)
print("✓ sai 0 điểm; tự gán", bc["tu_gan"], "/", bc["tong_diem"], "; còn lại chốt tại cột")
