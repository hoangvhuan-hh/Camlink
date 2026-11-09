import os, sys, json
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import camlink_litemark as L
CL = {"1": (11.3108,107.1574,"Ngã ba gần trạm y tế"), "2": (11.3069,107.1450,"Ngã ba chùa Pháp Bảo"), "3": (11.2938,107.1372,"Ngã ba 761 Bàu điền"),
      "4": (11.2998,107.1394,"Ngã ba Bình Chánh 761"), "5": (11.2784,107.1523,"Ngã tư bầu phụng"), "6": (11.2802,107.1645,"Ngã tư vô rừng lý lịch"),
      "7": (11.2798,107.1589,"Lý lịch 2 cây cầu"), "8": (11.2845,107.1652,"Lý lịch 2 bình chánh"), "9": (11.3162,107.1596,"Đầu 322A mũi tàu"),
      "10": (11.3293,107.1674,"Hết 322A"), "11": (11.3260,107.1639,"Đường 322a")}
LM = {1:(11.2846,107.1652),2:(11.2803,107.1645),3:(11.2799,107.1589),4:(11.2784,107.1537),5:(11.2783,107.1523),6:(11.2998,107.1393),7:(11.3074,107.1450),8:(11.3107,107.1574),9:(11.3158,107.1596),10:(11.3293,107.1675),11:(11.3325,107.1561)}
da = {"ten": "camera-xa-phu-ly", "diem": {k: {"ten": v[2], "so": 2} for k, v in CL.items()}, "toa_do": {k: [v[0], v[1]] for k, v in CL.items()}}
ghim = {str(k): {"stt": k, "ten": f"Điểm {k}", "lat": v[0], "lng": v[1], "so_camera": 2} for k, v in LM.items()}
ket, gc = L.ghep_ghim(da, ghim)
for k in sorted(ket, key=int): print(f"CamLink {k:>2} {CL[k][2]:26} → ghim LM {ket[k]['lm_stt']:>2}  {ket[k]['kc']:>5} m  {'' if ket[k]['chac'] else '⚠ chưa chắc'}")
print("ghi chú:", *gc, sep="\n  ")
assert ket["2"]["lm_stt"] == "7" and ket["6"]["lm_stt"] == "2" and ket["8"]["lm_stt"] == "1" and ket["10"]["lm_stt"] == "10"
assert len({v["lm_stt"] for v in ket.values()}) == 11
# ghép tay: Huan chốt CamLink 11 = ghim 11
da["diem"]["11"]["lm_tay"] = "11"
ket2, _ = L.ghep_ghim(da, ghim); assert ket2["11"]["lm_stt"] == "11" and ket2["11"]["tay"] and ket2["3"]["lm_stt"] == "4"
print("✓ ghép 1-1 đủ 11, ghép tay giữ nguyên")
