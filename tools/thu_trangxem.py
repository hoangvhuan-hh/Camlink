# 2.14.0 — TRANG XEM (web/xem.html) + phần app mở từ mã QR. Anh Huan chốt 27/11/2026 18:11.
# Máy có CamLink: quét là vào thẳng hình live. Máy chưa có: trang gợi ý dùng CamLink miễn phí, hoặc tự nhập user/mật khẩu.
# Chạy: python3 tools/thu_trangxem.py
import os, sys, re, json, base64
GOC = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(GOC, "../app/src/main/python"))
import camlink_hoso as H
dat = 0


def kt(ten, dk, them=""):
    global dat
    assert dk, "HỎNG: " + ten + (" — " + str(them) if them else "")
    dat += 1; print("✓", ten)


doc = lambda *p: open(os.path.join(GOC, "..", *p), encoding="utf-8").read()
LIVE = "rtsp://admin:Mk@1:#x@pl8.ddns.net:5541/media/video1"      # mật khẩu có cả @ : # để thử chỗ tách
ma = H.ma_xem("Camera xã Phú Lý", "Cột 8 · Cam 2", LIVE, 8081)
kt("X1: mã cam chỉ gồm ký tự an toàn cho link và mã QR (không + / = hay dấu cách)", re.fullmatch(r"[A-Za-z0-9_-]+", ma) is not None, ma)
g = json.loads(base64.urlsafe_b64decode(ma + "=" * (-len(ma) % 4)).decode("utf-8"))
kt("X2: giải bằng base64url + JSON chuẩn (đúng cách trang web và app giải) ra nguyên vẹn tiếng Việt; mã chỉ mang link video + cổng web (ngắn cho QR dễ quét)",
   g == {"v": 1, "da": "Camera xã Phú Lý", "t": "Cột 8 · Cam 2", "l": LIVE, "wp": 8081}, g)
kt("X2b: từ link video tách đúng user / mật khẩu (mật khẩu chứa @ : #) / link trang cam cho lối 'không cài, tự nhập'",
   H.giai_ma_xem(ma) == {"v": 1, "da": "Camera xã Phú Lý", "t": "Cột 8 · Cam 2", "l": LIVE, "u": "admin", "p": "Mk@1:#x", "w": "http://pl8.ddns.net:8081/"}, H.giai_ma_xem(ma))
kt("X2d: link video dạng cam trả về (mật khẩu đã đổi @ thành %40) → tách ra mật khẩu THẬT", H.tach_link_video("rtsp://admin:Aa1122%40@pl8.ddns.net:554/a") == ("admin", "Aa1122@", "pl8.ddns.net"))
me = H.ma_xem("DA", "C1", "rtsp://admin:Tien%4150@a.ddns.net:554/", 8080, "a.ddns.net", "admin", "Tien%4150")
kt("X2e: mật khẩu thật có chứa dấu % (tách từ link sẽ ra sai) → mã ghi thẳng user / mật khẩu thật, trang không bao giờ hiện sai", H.giai_ma_xem(me)["p"] == "Tien%4150", H.giai_ma_xem(me))
ma0 = H.ma_xem("DA", "Cột 1 · Cam 3", "", 8082, "a.ddns.net", "admin", "Abc@1")
kt("X2c: cam chưa có link video → mã vẫn đủ cho lối tự nhập (tên miền, user, mật khẩu ghi riêng)", H.giai_ma_xem(ma0) == {"v": 1, "da": "DA", "t": "Cột 1 · Cam 3", "l": "", "u": "admin", "p": "Abc@1", "w": "http://a.ddns.net:8082/"}, H.giai_ma_xem(ma0))
kt("X3: link trong QR đủ ngắn để mã in gần 4 cm quét dễ (dưới 260 ký tự với tên dự án, tên cam, link video cỡ thật)", len(H.TRANG_XEM + "#" + ma) < 260, len(H.TRANG_XEM + "#" + ma))

t = doc("web", "xem.html")
kt("X4: trang tự chứa — không tải mã / phông / ảnh từ nơi khác, không gửi dữ liệu đi đâu (mã cam chỉ nằm sau dấu #)",
   not re.search(r"<script[^>]+src=|<link[^>]+href=|fetch\(|XMLHttpRequest|sendBeacon|<img[^>]+src=[\"']http", t))
kt("X5: nút 'Xem live ngay' mở đúng app CamLink (tên gói + kiểu link camlink://xem), có đường lui khi máy chưa cài",
   all(x in t for x in ("scheme=camlink", "package=vn.vinalite.camlink", "intent://xem?d=", "browser_fallback_url")) and "Xem live ngay" in t)
kt("X6: khối kêu gọi dùng CamLink MIỄN PHÍ: nút tải + 4 lợi ích đã chốt", all(x in t for x in (
    "Dùng miễn phí", "Tải CamLink miễn phí", "Quét mã là thấy hình trực tiếp", "Không cần đăng ký, không cần tài khoản", "Tự kiểm tra cả hệ thống cam từ xa", "Tự xuất hồ sơ kèm ảnh và chỉ đường")))
kt("X7: link tải app nằm ở MỘT chỗ (sau này lên CH Play chỉ đổi một dòng, mã QR đã phát không phải in lại)", t.count("github.com/hoangvhuan-hh/camlink/raw/apk/CamLink.apk") == 1 and "var TAI =" in t)
kt("X8: lối 'không cài': hiện user + mật khẩu (có nút sao chép) và nút mở trang cam", all(x in t for x in ("Không muốn cài", "Mở trang cam", "Sao chép", "j.u", "j.p", "j.w")))

# ---- CHẠY THẬT đoạn mã của trang (node) với trang giả tối thiểu: 5 tình huống người quét gặp
import shutil, subprocess
js = re.search(r"<script>(.*)</script>", t, re.S).group(1)
GIA = """
var els = {}; function el(i) { if (!els[i]) els[i] = {textContent: "", className: "", style: {}, href: "", bam: null, getAttribute: function () { return "u"; }, addEventListener: function (k, f) { if (k === "click") this.bam = f; }}; return els[i]; }
globalThis.document = {getElementById: el, querySelectorAll: function () { return []; }, title: "", hidden: false, addEventListener: function () {}};
globalThis.window = {addEventListener: function () {}};
var di = [];
globalThis.location = {hash: "#%s", search: "%s", origin: "https://hhaico.com", host: "hhaico.com", pathname: "/Camlink/xem.html", replace: function (u) { di.push("thay:" + u); }};
Object.defineProperty(globalThis.location, "href", {get: function () { return di.length ? di[di.length - 1] : ""; }, set: function (u) { di.push(u); }});
Object.defineProperty(globalThis, "navigator", {value: {userAgent: "%s"}, configurable: true});
globalThis.sessionStorage = {getItem: function () { return null; }, setItem: function () {}};
globalThis.setTimeout = function (f) { f(); };
"""
RA = """
var tuMo = location.href;      // trang tự chuyển đi đâu ngay khi vừa mở (chưa ai bấm gì)
if (el("nut-web").bam) el("nut-web").bam({preventDefault: function () {}});
console.log(JSON.stringify({di: di, goi_y_ios: el("goi-y-ios").style.display || "", cam: el("cam").textContent, da: el("da").textContent, u: el("u").textContent, p: el("p").textContent, web: el("nut-web").href, live: el("nut-live").href,
  tai: el("nut-tai").href, tu_mo: tuMo, bao: el("bao").textContent, an_live: el("khoi-live").className, an_tai: el("khoi-tai").className, an_tu: el("khoi-tu").className}));
"""
AND = "Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36"
IOS = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Version/17.5 Mobile/15E148 Safari/604.1"
MAY = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"


def chay(ua, hash_, search=""):
    r = subprocess.run(["node", "-e", GIA % (hash_, search, ua) + js + RA], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr[-400:]
    return json.loads(r.stdout.strip().splitlines()[-1])


if shutil.which("node"):
    a = chay(AND, ma)
    kt("X20: Android: trang hiện đúng tên dự án + tên cam, nút 'Xem live ngay' mở app CamLink kèm đúng mã cam, và TỰ thử mở app ngay khi vào trang",
       a["da"] == "Camera xã Phú Lý" and a["cam"] == "Cột 8 · Cam 2" and a["live"].startswith("intent://xem?d=" + ma + "#Intent;scheme=camlink;package=vn.vinalite.camlink;") and a["tu_mo"] == a["live"] and a["bao"] == "", a)
    kt("X21: Android: lối tự nhập có đúng user, mật khẩu (chứa @ : #) và link trang cam, tách từ link video", (a["u"], a["p"], a["web"]) == ("admin", "Mk@1:#x", "http://pl8.ddns.net:8081/"), a)
    kt("X22: máy chưa cài CamLink → đường lui quay về chính trang này kèm đúng mã cam (không ra trang lỗi)",
       "S.browser_fallback_url=" + __import__("urllib.parse").parse.quote("https://hhaico.com/Camlink/xem.html?chua=1#" + ma, safe="") + ";end" in a["live"], a["live"][-200:])
    c = chay(AND, ma, "?chua=1")
    kt("X23: quay về vì chưa cài → báo 'chưa có CamLink, tải miễn phí', KHÔNG tự thử mở app lần nữa (không lặp vô hạn), nút tải thành nút chính",
       "chưa có CamLink" in c["bao"] and c["tu_mo"] == "" and c["tai"].endswith("CamLink.apk"), c)
    i = chay(IOS, ma)
    kt("X24: iPhone → ẩn nút xem live và khối tải (không có bản iPhone), nói rõ, vẫn đủ user / mật khẩu / link trang cam",
       i["an_live"] == "an" and i["an_tai"] == "an" and "iPhone" in i["bao"] and i["tu_mo"] == "" and (i["u"], i["p"], i["web"]) == ("admin", "Mk@1:#x", "http://pl8.ddns.net:8081/"), i)
    w = chay(MAY, ma)
    kt("X25: máy tính → không tự mở app, nói rõ xem live chạy trên Android, vẫn có lối tự nhập", w["tu_mo"] == "" and "Android" in w["bao"] and w["web"] == "http://pl8.ddns.net:8081/", w)
    h = chay(AND, "@@@")
    kt("X26: mã hỏng → báo 'Mã không hợp lệ', ẩn nút xem live và lối tự nhập, không lỗi", "Mã không hợp lệ" in h["bao"] and h["an_live"] == "an" and h["an_tu"] == "an" and h["tu_mo"] == "", h)
    k = chay(AND, ma0)
    kt("X27: cam chưa có link video → ẩn nút xem live, vẫn cho tự nhập với đúng user / mật khẩu / link", k["an_live"] == "an" and k["tu_mo"] == "" and (k["u"], k["p"], k["web"]) == ("admin", "Abc@1", "http://a.ddns.net:8082/"), k)
    # ---- 2.14.1: anh Huan thử thật 27/11 19:31 trên iPhone
    LIVE_Q = "rtsp://admin:Aa1122%40@pl8.ddns.net:554/media/video1"      # ĐÚNG dạng app lấy từ cam: ký tự @ trong mật khẩu đã thành %40
    maq = H.ma_xem("Camera Xa Phu Ly", "Ngã ba gần trạm y tế · Cam 1", LIVE_Q, 8080, "pl8.ddns.net", "admin", "Aa1122@")
    q = chay(IOS, maq)
    kt("X28: link video từ cam có mật khẩu dạng %40 → trang hiện ĐÚNG mật khẩu thật (kết thúc bằng @), không hiện %40", (q["u"], q["p"]) == ("admin", "Aa1122@") and "%" not in q["p"], q)
    kt("X29: iPhone bấm 'Mở trang cam' → thử mở bằng SAFARI trước (thoát trình duyệt nhúng của app quét mã), không được thì mở thẳng trang cam như cũ",
       q["di"] == ["x-safari-https://hhaico.com/Camlink/xem.html?web=1#" + maq, "http://pl8.ddns.net:8080/"] and q["goi_y_ios"] == "block", q["di"])
    q2 = chay(IOS, maq, "?web=1")
    kt("X30: đã sang Safari (link có web=1) → vào THẲNG trang cam qua tên miền, không dừng ở trang gợi ý", q2["di"][:1] == ["thay:http://pl8.ddns.net:8080/"], q2["di"])
    kt("X31: Android: nút 'Mở trang cam' vẫn là link http thẳng tới tên miền của cam (không đổi)", a["web"] == "http://pl8.ddns.net:8081/" and a["di"] == [a["live"]], a["di"])      # Android: chỉ có lần tự mở app; nút web là link thường, không bị chặn lại
else:
    print("· (máy này không có node → bỏ qua phần chạy thật đoạn mã của trang; CI có node)")
kt("X9: trang giải mã đúng cách (base64url → UTF-8 → JSON) và không vỡ khi mã hỏng / thiếu", all(x in t for x in ("atob(", "TextDecoder", "JSON.parse", "catch")) and "Mã không hợp lệ" in t)
kt("X10: iPhone không có CamLink → trang nói rõ và chỉ đưa lối tự nhập", "iPhone" in t and "Android" in t)

mf = doc("app", "src", "main", "AndroidManifest.xml"); kx = doc("app", "src", "main", "java", "vn", "vinalite", "camlink", "XemLiveActivity.kt")
khoi = mf[mf.index('android:name=".XemLiveActivity"'):]; khoi = khoi[:khoi.index("</activity>")]
kt("X11: app nhận link camlink://xem ở màn Xem trực tiếp (mở được từ trình duyệt)", 'android:exported="true"' in khoi and 'android:scheme="camlink"' in khoi and 'android:host="xem"' in khoi and "BROWSABLE" in khoi)
kt("X12: màn Xem trực tiếp đọc đúng các khoá mà lõi ghi vào mã (l = link video, da + t = tiêu đề), chỉ nhận link rtsp",
   all(x in kx for x in ('getQueryParameter("d")', 'optString("l")', 'optString("da")', 'optString("t")', 'startsWith("rtsp://")', "URL_SAFE")))
kt("X13: người chỉ cài để XEM không phải thiết lập gì: màn Xem trực tiếp không gọi lõi Python, không đòi dự án / mã PIN", "callAttr" not in kx and "QuanTri" not in kx)
ci = doc(".github", "workflows", "build.yml")
kt("X14: CI tự đưa trang xem lên nhánh gh-pages mỗi lần phát hành (trang và app luôn khớp nhau)", "gh-pages" in ci and "web/xem.html" in ci)
print(f"\n✓ 2.14.0 trang xem + mở app từ mã QR: {dat}/{dat} đạt")
