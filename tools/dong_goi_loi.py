"""Đóng gói lõi Python thành gói cập nhật .zip (manifest + sha256) + thư mục kênh cập nhật."""
import hashlib, json, os, re, shutil, sys, zipfile
G = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(G, "app/src/main/python")
TEP = ["camlink_phien_ban.py", "camlink_core.py", "camlink_dt.py", "camlink_tuxa.py", "camlink_oryza.py", "camlink_litemark.py"]
src = open(os.path.join(PY, "camlink_phien_ban.py"), encoding="utf-8").read()
pb = re.search(r'PHIEN_BAN = "([^"]+)"', src).group(1)
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(G, "kenh")
os.makedirs(os.path.join(out, "py"), exist_ok=True)
tep = {}
for f in TEP:
    d = open(os.path.join(PY, f), "rb").read()
    tep[f] = hashlib.sha256(d).hexdigest()
    shutil.copy(os.path.join(PY, f), os.path.join(out, "py", f))
mf = {"phien_ban": pb, "tep": tep}
zp = os.path.join(out, f"CamLink-loi-{pb}.zip")
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for f in TEP:
        z.write(os.path.join(PY, f), f)
    z.writestr("manifest.json", json.dumps(mf, ensure_ascii=False))
# gói một tệp .camlink (JSON) — điện thoại không tự giải nén như .zip
import base64
goi = {"loai": "camlink-loi", "phien_ban": pb, "tep": {f: {"sha256": tep[f], "b64": base64.b64encode(open(os.path.join(PY, f), "rb").read()).decode()} for f in TEP}}
cl = os.path.join(out, f"CamLink-loi-{pb}.camlink")
json.dump(goi, open(cl, "w"), ensure_ascii=False)
print(cl, os.path.getsize(cl) // 1024, "KB")
gr = os.path.join(G, "app/build.gradle.kts")
code = int(re.search(r"versionCode = (\d+)", open(gr).read()).group(1)); ten = re.search(r'versionName = "([^"]+)"', open(gr).read()).group(1)
cu = {}
try:
    cu = json.load(open(os.path.join(out, "phien_ban.json")))
except Exception:
    pass
json.dump({"loi": pb, "tep": tep, "apk_code": cu.get("apk_code", code), "apk_ten": cu.get("apk_ten", ten),
           "apk_url": cu.get("apk_url", ""), "apk_mb": cu.get("apk_mb", ""), "apk_ly_do": cu.get("apk_ly_do", "")},
          open(os.path.join(out, "phien_ban.json"), "w"), ensure_ascii=False, indent=1)
print(zp, os.path.getsize(zp) // 1024, "KB")
