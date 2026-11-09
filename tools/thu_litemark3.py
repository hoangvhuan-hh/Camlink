import sys, json
sys.path.insert(0, '/home/claude/camlink-repo/app/src/main/python')
import camlink_litemark as L
da = {"ten": "PL", "diem": {"2": {"ten": "Chùa Pháp Bảo", "domain": "a.ddns.net", "lm_stt": "7"},
                           "6": {"ten": "Rừng Lý Lịch", "domain": "b.ddns.net", "lm_stt": "2"},
                           "10": {"ten": "Hết 322A", "domain": "c.ddns.net", "lm_stt": "10"}}}
def kq(a_mac, b_mac, c_mac, a_ip, b_ip, c_ip):
    return {"diem": [{"stt": "2", "domain": "a.ddns.net", "ip": a_ip, "muc": "xanh", "tong": "ĐẠT", "cam": [{"so": 1, "http": 8080, "muc": "xanh", "mac": a_mac}]},
                     {"stt": "6", "domain": "b.ddns.net", "ip": b_ip, "muc": "xanh", "tong": "ĐẠT", "cam": [{"so": 1, "http": 8080, "muc": "xanh", "mac": b_mac}]},
                     {"stt": "10", "domain": "c.ddns.net", "ip": c_ip, "muc": "xanh", "tong": "ĐẠT", "cam": [{"so": 1, "http": 8080, "muc": "xanh", "mac": c_mac}]}]}
# lần 1: ghi dấu vết
k1 = kq("AA", "BB", "CC", "1.1.1.1", "2.2.2.2", "3.3.3.3")
assert L.doi_chieu_vet(da, k1) == []
L.cap_nhat_vet(da, k1)
assert da["vet"]["6"]["mac"] == ["BB"] and da["vet"]["10"]["ip"][0]["ip"] == "3.3.3.3"
# lần 2: quản lý đổi tên — b.ddns.net nay trỏ về cam CC (điểm 10), c.ddns.net trỏ về BB; điểm 2 cam hỏng (không MAC) nhưng IP là của điểm 10 cũ
k2 = kq("", "CC", "BB", "3.3.3.3", "9.9.9.9", "2.2.2.2")
k2["diem"][0]["cam"][0]["muc"] = "do"; k2["diem"][0]["muc"] = "do"
doi = L.doi_chieu_vet(da, k2, lambda s: None)
assert ("6", "10", "MAC cam") in doi and ("10", "6", "MAC cam") in doi, doi
assert any(x[0] == "2" and x[1] == "10" and "IP" in x[2] for x in doi), doi
assert k2["diem"][1]["lm_stt_that"] == "10" and "ĐIỂM 10" in k2["diem"][1]["canh_bao"][0]
print("✓ nhận diện theo MAC trước, IP sau, tên miền cuối:", [(a, "→", b, c[:3]) for a, b, c in doi])
