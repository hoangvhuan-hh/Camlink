# Giao thức DDNS cam Oryza (đọc từ baseSetting.203f4cd0.js, cam điểm 7, 08/11/2026)
- b(cmd, body) = ui.js export "w"; X(pwd) = ui.js export "aw" -> trả {Response: <mật khẩu mã hoá>}
- 32706 body {ChannelId:{Id:-1}} -> data.DDNSProviderList.DDNSProvider[] = {ProviderName, ProviderId}
- 32701 body {ChannelId:{Id:-1},EncodeVerParam:{EncodeVer:1}} -> data.Result.Code (0=ok), data.DDNSParam = {DDNSEnableFlag, DDNSProviderId, DDNSNetworkCardName, DDNSDomainName, DDNSAccounts, DDNSPassword, DDNSProtocolType(1 HTTP/2 HTTPS), ...}
- 32703 ghi body:
  {ChannelId:{Id:-1}, DDNSParam:{...DDNSInfoData (từ 32701), EncodeVerParam:{EncodeVer:1}, DDNSEnableFlag:bool,
     DDNSProviderId:<ProviderId số>, DDNSAccounts:str, DDNSPassword:<X(pwd).Response hoặc "">}, EncodeVerParam:{EncodeVer:1}}
  -> data.Result.Code != 0 là lỗi
- 32705 = Test DDNS (cùng body 32703) -> ok khi !Result.Code && !State.State
- Tên miền tối đa 63 ký tự; account/pass tối đa 32

## Mã hoá mật khẩu DDNS = Es (ui.js 178145)
- B(11011,{WebAuthInfo:{OperatorType:1}}) -> data.WebAuthInfo.PublicKey ; JSEncrypt RSA PKCS#1 v1.5, base64 -> Response. KHÔNG có AES.

## Gửi lệnh B(cmd, body) (ui.js ~139400)
- POST /action/WEB_JsonAjax, body XML:
  <?xml version="1.0" encoding="UTF-8"?><CommandHead Command="CMD" SessionId="SID"><Parameters Version="1">...</Parameters></CommandHead>
  (SessionId chỉ khi có)
- Object -> phần tử: thuộc tính nguyên thuỷ thành attribute k="Na(v)"; con object/array thành phần tử con. Mảng: tên chứa "List" -> <XList><Item .../></XList> (mỗi phần tử là {TênCon:{...}}), không thì lặp <Tên .../>.
- Trả về XML -> ObjTree attr_prefix '' -> data = CommandHead.Parameters (attribute thành key)
- Header khi loginInit: Authorization: XDigest username="U",realm="R",nonce="N",uri="active/base/CMD",algorithm="SHA-256",qop="auth",nc="%08x",cnonce="C",response="RESP"
- 401 -> đọc www-authenticate (XDigest realm, nonce, opaque, qop, algorithm), Nc=1, tính lại và gửi lại
- Code -512 / -669 = phiên hết hạn ; -508 = khoá/sai ; -243
## getNewResponse (ui.js 2494)
- Nc += 1 trước mỗi lệnh ; nc = hex 8 ký tự
- HA1 = ee(user:realm:Ivd) ; HA2 = ee("POST:active/base/CMD") ; resp = ee(HA1:nonce:nc:cnonce:qop:HA2) ; ee = SHA-256 hex (Algorithm mặc định SHA-256)
- Ivd = ee(password + ":" + sessionId)  (setEncryptPassword t=false) hoặc = password thô khi t=true
- dataValue = sid[-8:]+sid[:8]+sid[4:-4] (chỉ dùng nội bộ trình duyệt)

## Đăng nhập (loginIndex F + ui.js ar) — operatorType 2
1. (tuỳ) B(11011,{WebAuthInfo:{OperatorType:1}}) -> WebAuthInfo.Nonce (xa), PublicKey (Ka)
2. vt = 16 ký tự ngẫu nhiên [a-f0-9]; Ea = vt[:16]; Cnonce Ye = base64(vt)   (Tt = base64, ĐÃ KIỂM: Tt.encode('0123456789abcdef') = btoa)
3. POST 11027 {DigestAuthentication:{OperatorType:2}} không auth -> 401, header WWW-Authenticate: XDigest realm,nonce,opaque,algorithm,qop
4. Nc ban đầu = 2 -> nc="00000002"; Response = ee(ee(user:realm:PASS_THÔ):nonce:nc:Ye:qop:ee("POST:active/base/11027"))
   ee = SHA-256 hex — ĐÃ KIỂM: vendor.s('abc') = ba7816bf...15ad
5. POST lại 11027 {DigestAuthentication:{OperatorType:2}} kèm Authorization XDigest (uri active/base/11027, nc 00000002, cnonce Ye)
   -> Result.Code 0 ; DigestAuthentication.SessionId ; DigestAuthentication.Response==100 => mật khẩu mặc định, phải đổi (khi đó Ivd = pass thô)
   lỗi: -507 sai user/pass ; -508 sai, RemainCount ; -511/-520 quá số user ; -515 bị khoá (RemainingLockingMin/Sec)
6. Sau đăng nhập: Ivd = ee(PASS + ":" + SessionId) ; mỗi lệnh Nc+=1 (lệnh đầu = 3) ; CommandHead có SessionId="SID"
7. Đăng xuất: 11027 {DigestAuthentication:{User,Realm,Cnonce,Qop,Nonce,Uri,Nc,Algorithm,Response,OperatorType:3}} (Response tính như lệnh thường, getNewResponse(11027,false) = Nc+1 không tăng)

## Kích hoạt cam mới (tạo mật khẩu lần đầu) — operatorType 3
- 11011 {WebAuthInfo:{OperatorType:1}} -> Nonce xa, PublicKey Ka
- key = utf8(sha256hex(xa + Ye)[:32]) ; iv = utf8(vt[:16]) ; L = AES-CBC-PKCS7(pass) base64 ; Response = RSA_PKCS1(L) base64
- POST 11011 {WebAuthInfo:{OperatorType:3, User, Cnonce:Ye, Response}} -> Result.Code 0
