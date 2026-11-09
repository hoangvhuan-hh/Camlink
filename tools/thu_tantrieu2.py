import sys, re
exec(open('thu_tantrieu.py', encoding='utf-8').read().split("dong = L.doc_file_ddns")[0])
da = L.tao_du_an_tu_lm("f7ee", "", lambda s: None)
dong = L.doc_file_ddns(f, lambda u: None, lambda s: None)
for d in dong: d["ten"] = "Vị trí " + d["no"] if d["no"] != "51" else "Cột cao"; d["no"] = str(100 + int(d["no"]))   # bỏ hết mã TT
da, bc = L.ghep_ddns(da, dong, print)
sai = [(s, d["lm_ten"], d["domain"]) for s, d in da["diem"].items() if d.get("domain") and d["lm_ten"].startswith("TT") and d["domain"] != f"tantrieu-{int(d['lm_ten'][2:]):02d}.ddns.net"]
print("trùng:", bc["trung"], "| chưa chắc:", [x[0] for x in bc["chua_chac"]], "| sai:", sai)
assert not sai, sai
print(f"✓ chỉ toạ độ: tự gán {bc['tu_gan']}/{bc['tong_diem']}, sai 0, còn {len(bc['diem_thieu'])} điểm chốt tại cột")
