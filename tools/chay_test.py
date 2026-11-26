#!/usr/bin/env python3
# CỔNG TEST của CamLink — một lệnh chạy toàn bộ bài thử tools/thu_*.py. Có bài đỏ → thoát mã 1 → CI KHÔNG build, KHÔNG phát hành APK.
#
#   python3 tools/chay_test.py            chạy hết; bài cần mạng giả mà máy không đủ quyền thì báo BỎ QUA (vẫn tính là chưa đạt đủ)
#   python3 tools/chay_test.py --nhanh    bỏ các bài cần mạng giả (dùng cho hook trước khi commit)
#   sudo python3 tools/chay_test.py --du  bắt buộc chạy ĐỦ mọi bài (CI dùng lệnh này); thiếu quyền → đỏ
#   python3 tools/chay_test.py thu_hoiquy thu_modem     chỉ chạy các bài nêu tên
#
# Cần: pip install requests openpyxl rsa pillow reportlab==4.2.5 (đúng các gói app dùng, xem app/build.gradle.kts).
# Bài cần mạng giả (cam giả lập ở 127.0.4.x + iptables để giả mất mạng) phải chạy bằng root trên Linux.
import glob, os, shutil, subprocess, sys, time

GOC = os.path.dirname(os.path.abspath(__file__))
CAN_MANG_GIA = {"thu_tuxa9", "thu_tuxa10", "thu_theodoi2", "thu_chandoan"}
GIOI_HAN = 420      # giây cho mỗi bài
TEN_MIEN_GIA = [(f"127.0.4.{i}", f"pl{i}.ddns.net") for i in (2, 4, 6, 8)]


def du_quyen_mang_gia():
    if os.name != "posix" or not hasattr(os, "geteuid") or os.geteuid() != 0 or not shutil.which("iptables"):
        return False
    try:
        with open("/etc/hosts", encoding="utf-8") as f:
            co = f.read()
        thieu = [f"{ip} {ten}\n" for ip, ten in TEN_MIEN_GIA if ten not in co]
        if thieu:
            with open("/etc/hosts", "a", encoding="utf-8") as f:
                f.write("".join(thieu))
        return subprocess.run(["iptables", "-S"], capture_output=True).returncode == 0
    except OSError:
        return False


def don_chan_mang():
    """Bài thử chết giữa chừng có thể để sót luật chặn 127.0.4.x → gỡ hết, không ảnh hưởng bài sau."""
    for chuoi in ("INPUT", "OUTPUT"):
        ra = subprocess.run(["iptables", "-S", chuoi], capture_output=True, text=True).stdout
        for dong in ra.splitlines():
            if "127.0.4." in dong and dong.startswith("-A "):
                subprocess.run(["iptables"] + ("-D " + dong[3:]).split(), capture_output=True)


def main():
    doi = [a for a in sys.argv[1:] if not a.startswith("--")]
    nhanh, du = "--nhanh" in sys.argv, "--du" in sys.argv
    ds = sorted(os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(GOC, "thu_*.py")))
    if doi:
        ds = [n for n in ds if n in doi]
    mang_gia = du_quyen_mang_gia()
    mt = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    xanh, do, bo = [], [], []
    bd = time.time()
    for n in ds:
        if n in CAN_MANG_GIA and (nhanh or not mang_gia):
            bo.append(n)
            print(f"⏭  {n} — bỏ qua (cần root + iptables để giả mất mạng)", flush=True)
            continue
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, os.path.join(GOC, n + ".py")], cwd=GOC, env=mt, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=GIOI_HAN)
            ma, ra = r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired as e:
            ma, ra = -1, f"{e.stdout or ''}\nQUÁ {GIOI_HAN} GIÂY — coi là hỏng"
        if n in CAN_MANG_GIA and mang_gia:
            don_chan_mang()
        giay = round(time.time() - t0, 1)
        if ma == 0:
            xanh.append(n)
            print(f"✅ {n} ({giay} giây)", flush=True)
        else:
            do.append(n)
            print(f"❌ {n} ({giay} giây) — 25 dòng cuối:", flush=True)
            print("\n".join("      " + d for d in str(ra).strip().splitlines()[-25:]), flush=True)
    print(f"\nKẾT QUẢ: {len(xanh)} xanh · {len(do)} đỏ · {len(bo)} bỏ qua / {len(ds)} bài · {round(time.time() - bd)} giây")
    if do:
        print("ĐỎ:", ", ".join(do), "→ KHÔNG được build / phát hành. Sửa tận gốc rồi chạy lại.")
        return 1
    if bo and du:
        print("THIẾU:", ", ".join(bo), "→ chế độ --du đòi chạy đủ mọi bài (chạy bằng root trên Linux).")
        return 1
    if not ds:
        print("Không có bài thử nào được chạy → coi là hỏng.")
        return 1
    print("XANH" + (" (chưa đủ — còn bài bỏ qua, CI sẽ chạy đủ)" if bo else " ĐỦ — được phép build."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
