package vn.vinalite.camlink

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import android.text.InputType
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.content.FileProvider
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import kotlin.concurrent.thread

/**
 * CamLink 1.2 — 3 chế độ, app tự nhận và báo rõ trước khi làm:
 *  TẠI CHỖ  : GPS cách điểm ≤ 400 m + đang vào WiFi modem → cài đầy đủ.
 *  TỪ XA    : cách điểm > 1 km → chỉ KIỂM TRA qua tên miền (không thay đổi gì).
 *  CHƯA RÕ  : không có GPS / 400 m–1 km → hỏi xác nhận trước khi cài.
 */
class MainActivity : Activity() {
    private lateinit var core: PyObject
    private lateinit var log: TextView
    private lateinit var cuon: ScrollView
    private lateinit var tieuDe: TextView
    private lateinit var trangThai: TextView
    // 2.4 — giao diện đồ hoạ (tuỳ chọn): dựng song song, đổi qua lại, không đụng giao diện chữ
    private lateinit var gocChu: LinearLayout
    private lateinit var gocDH: LinearLayout
    private lateinit var dhTrangThai: TextView
    private lateinit var dhThe: LinearLayout
    private lateinit var dhTrang: android.widget.FrameLayout
    private lateinit var dhChu: ScrollView
    private lateinit var dhThem: ScrollView
    private lateinit var dhDuAn: LinearLayout
    private lateinit var dhCaiDat: ScrollView
    private lateinit var dhChamGS: android.view.View
    private lateinit var dhMoTaDuAn: TextView
    private val dhTab = mutableListOf<TextView>()
    private var doHoa = false
    private val maGiamSatDH = 42
    private var maGiamSatDangMo = ""
    private val maViTriTuDong = 14
    private var daXinViTri = false
    private val cacNut = mutableListOf<Button>()
    private val ui = Handler(Looper.getMainLooper())
    private val maFile = 11
    private val maViTri = 12
    private var viTriCuoi: Location? = null
    private var dangChay = ""

    private val XANH = "#1D7A46"
    private val DO = "#B42318"
    private val VANG = "#9A5B00"
    private val LAM = "#0F5D8C"
    private val XAM = "#5B6776"

    /** Python gọi nhatKy.ghi("...") để in nhật ký; dòng bước lớn đổi luôn thanh trạng thái. */
    inner class NhatKy {
        fun ghi(s: String) {
            ui.post {
                log.append(s + "\n")
                tvThuMau?.let { tv -> tv.append(s + "\n"); (tv.parent as? ScrollView)?.let { c -> c.post { c.fullScroll(ScrollView.FOCUS_DOWN) } } }
                cuon.post { cuon.fullScroll(ScrollView.FOCUS_DOWN) }
                val t = s.trim()
                val buoc = when {
                    t.startsWith("Quét mạng") -> "quét mạng tìm cam"
                    t.startsWith("-- Cam") -> t.removePrefix("-- ").substringBefore(":") + ": đặt port, IP, DDNS"
                    t.startsWith("-- Modem") -> "mở port trên modem"
                    t.startsWith("-- Kiểm tra") -> "kiểm tra tên miền"
                    t.startsWith("Gặp thiết bị") -> "lưu mẫu thiết bị lạ"
                    t.startsWith("Đang lấy toạ độ") -> "lấy toạ độ các điểm"
                    else -> null
                }
                if (buoc != null && dangChay.isNotEmpty()) datTrangThai("⏳ $dangChay\nĐang: $buoc", LAM)
            }
        }
    }

    private val nhatKy = NhatKy()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Loi.khoiDong(this)
        core = Python.getInstance().getModule("camlink_core")
        dungGiaoDien()
        capNhatTieuDe()
        Loi.baoLoiCu(this)
        TheoDoi.damBaoChay(this)
        ngheWifi()
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    /** So "1.7.2" với "1.6.3" theo từng số: >0 nếu a mới hơn b. */
    private fun soSanhPhienBan(a: String, b: String): Int {
        val x = a.split(".").map { it.filter { c -> c.isDigit() }.toIntOrNull() ?: 0 }
        val y = b.split(".").map { it.filter { c -> c.isDigit() }.toIntOrNull() ?: 0 }
        for (i in 0 until maxOf(x.size, y.size)) {
            val d = (x.getOrNull(i) ?: 0) - (y.getOrNull(i) ?: 0)
            if (d != 0) return d
        }
        return 0
    }

    private fun nut(chu: String, chinh: Boolean = false, bam: () -> Unit): Button {
        val b = Button(this)
        b.text = chu
        b.isAllCaps = false
        b.textSize = if (chinh) 20f else 16f
        if (chinh) {
            b.setBackgroundColor(Color.parseColor(LAM))
            b.setTextColor(Color.WHITE)
            b.setPadding(dp(8), dp(18), dp(8), dp(18))
        }
        b.setOnClickListener { bam() }
        cacNut.add(b)
        return b
    }

    private fun dungGiaoDien() {
        val goc = LinearLayout(this)
        goc.orientation = LinearLayout.VERTICAL
        goc.setPadding(dp(16), dp(20), dp(16), dp(12))

        val ten = TextView(this)
        ten.text = "CamLink " + packageManager.getPackageInfo(packageName, 0).versionName + " · lõi " + core.callAttr("phien_ban_loi").toString()
        ten.textSize = 26f
        ten.setTypeface(null, Typeface.BOLD)
        goc.addView(ten)

        val doi = TextView(this)      // 2.4: lối sang giao diện đồ hoạ — giao diện chữ này giữ nguyên
        doi.text = "🎨 Đổi sang giao diện đồ hoạ ›"
        doi.textSize = 14f
        doi.setTextColor(Color.parseColor(LAM))
        doi.setPadding(0, dp(4), 0, dp(4))
        doi.setOnClickListener { datGiaoDien(true) }
        goc.addView(doi)

        tieuDe = TextView(this)
        tieuDe.textSize = 14f
        tieuDe.setPadding(0, dp(2), 0, dp(8))
        goc.addView(tieuDe)

        trangThai = TextView(this)
        trangThai.textSize = 16f
        trangThai.setTypeface(null, Typeface.BOLD)
        trangThai.setTextColor(Color.WHITE)
        trangThai.setPadding(dp(12), dp(10), dp(12), dp(10))
        val lpTt = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
        lpTt.bottomMargin = dp(10)
        goc.addView(trangThai, lpTt)
        datTrangThai("Chưa chạy", XAM)

        goc.addView(nut("CHẠY CÀI ĐIỂM NÀY", chinh = true) { batDauChay() })
        goc.addView(nut("📘 Hướng dẫn sử dụng") { startActivity(Intent(this, HuongDanActivity::class.java)) })
        goc.addView(nut("⬆ Cập nhật (lõi vài trăm KB; APK chỉ khi cần)") { capNhat() })
        goc.addView(nut("Kiểm tra từ xa cả dự án (xem lỗi + sửa từ xa)") { if (sanSang()) startActivity(Intent(this, TuXaActivity::class.java)) })
        goc.addView(nut("Chọn điểm bằng tay") { chonDiem(chiKiemTra = false) })
        goc.addView(nut("Xem sơ đồ + ảnh lần chạy gần nhất") { moSoDoGanNhat() })
        goc.addView(nut("Gửi kết quả (Zalo, Gmail…)") { guiKetQua() })
        goc.addView(nut("Thêm / cập nhật dự án (file Excel)") { moFile() })
        goc.addView(nut("User / pass cam và modem") { hopCaiDat() })
        goc.addView(nut("Thu mẫu thiết bị") { thuMau() })
        goc.addView(nut("🔐 Quản trị & khôi phục (mật khẩu, thợ, khách)") { startActivity(Intent(this, QuanTriActivity::class.java)) })

        cuon = ScrollView(this)
        log = TextView(this)
        log.typeface = Typeface.MONOSPACE
        log.textSize = 12f
        log.setTextColor(Color.parseColor("#CFE3F1"))
        log.setBackgroundColor(Color.parseColor("#0E1720"))
        log.setPadding(dp(10), dp(10), dp(10), dp(10))
        log.setTextIsSelectable(true)
        cuon.addView(log)
        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f)
        lp.topMargin = dp(10)
        goc.addView(cuon, lp)
        gocChu = goc
        dungDoHoa()
        datGiaoDien(getSharedPreferences("camlink", MODE_PRIVATE).getBoolean("do_hoa", true), luu = false)
        xuLyLink(intent)
    }

    private fun datTrangThai(chu: String, mau: String) {
        trangThai.text = chu
        trangThai.setBackgroundColor(Color.parseColor(mau))
        if (::dhTrangThai.isInitialized) {
            dhTrangThai.text = chu
            dhTrangThai.background = bo(mau, 14)
            dhTrangThai.visibility = if (chu == "Chưa chạy") android.view.View.GONE else android.view.View.VISIBLE
        }
    }

    private fun capNhatTieuDe() {
        val coFile = core.callAttr("co_du_lieu").toBoolean()
        val coPass = core.callAttr("co_cai_dat").toBoolean()
        tieuDe.text = when {
            !coFile -> "Bước 1: bấm \"Thêm / cập nhật dự án (file Excel)\"."
            !coPass -> "Bước 2: bấm \"User / pass cam và modem\" (nhập một lần)."
            else -> "Sẵn sàng · ${core.callAttr("so_du_an").toInt()} dự án. Tới điểm: vào WiFi modem rồi bấm CHẠY."
        }
        lamMoiTrangChu()
    }

    private fun khoaNut(khoa: Boolean) = ui.post { cacNut.forEach { it.isEnabled = !khoa } }

    /** Chạy việc nặng ở luồng nền; xong thì hiện HỘP KẾT QUẢ rõ ràng (đạt / chưa / lỗi). */
    private fun chayNen(viec: String, coTomTat: Boolean, lam: () -> List<String>?) {
        dangChay = viec
        datTrangThai("⏳ $viec\nĐang bắt đầu…", LAM)
        khoaNut(true)
        thread {
            var kq: List<String>? = null
            try {
                kq = lam()
            } catch (e: Exception) {
                kq = listOf("LOI", "Lỗi: " + (e.message ?: e.toString()))
                nhatKy.ghi("✖ " + kq[1])
            } finally {
                khoaNut(false)
                val ketQua = kq
                ui.post {
                    dangChay = ""
                    capNhatTieuDe()
                    if (coTomTat && ketQua != null) hienKetQua(viec, ketQua)
                    else datTrangThai("✔ Xong: $viec", XANH)
                }
            }
        }
    }

    private fun hienKetQua(viec: String, kq: List<String>) {
        val (nhan, mau) = when (kq[0]) {
            "DAT" -> Pair("✔ ĐẠT", XANH)
            "CHUA" -> Pair("⚠ CHƯA XONG HẾT", VANG)
            else -> Pair("✖ LỖI", DO)
        }
        datTrangThai("$nhan — $viec", mau)
        val b = AlertDialog.Builder(this)
            .setTitle("$nhan\n$viec")
            .setMessage(kq[1])
            .setPositiveButton("Gửi kết quả") { _, _ -> guiKetQua() }
            .setNegativeButton("Đóng", null)
        val dc = diemCuoi
        if (kq[0] != "DAT" && dc != null && viec.startsWith("CÀI TẠI CHỖ"))      // điểm này user/pass thực tế khác mặc định → nhập riêng rồi cài lại
            b.setNeutralButton("User/pass riêng điểm này") { _, _ -> hopUserPass(dc.first, dc.second) { caiLai(dc.first, dc.second) } }
        b.show()
    }

    // ---------------- Nhập file khảo sát ----------------
    private fun moFile() {
        nhatKy.ghi("Chọn file khảo sát Excel của dự án (mỗi file = 1 dự án; nhập lại file cùng tên = cập nhật).")
        val i = Intent(Intent.ACTION_OPEN_DOCUMENT)
        i.addCategory(Intent.CATEGORY_OPENABLE)
        i.type = "*/*"
        startActivityForResult(i, maFile)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == maGiamSatDH) {      // từ màn trực tiếp bấm "Kiểm tra sâu" / "Chi tiết, sửa" → sang màn Kiểm tra từ xa
            if (resultCode == RESULT_OK && data != null && !ban() && sanSang()) {
                val i = Intent(this, TuXaActivity::class.java).putExtra("ma", maGiamSatDangMo)
                data.getStringExtra("stt")?.let { i.putExtra("toi_diem", it) }      // "Chi tiết / sửa" ở một điểm → nhảy thẳng tới thẻ điểm đó
                startActivity(i)
            }
            return
        }
        val uri: Uri = data?.data ?: return
        if (requestCode == maZip && resultCode == RESULT_OK) { napZip(uri); return }
        if (requestCode == maFileDdns && resultCode == RESULT_OK) { napDdns(uri); return }
        if (requestCode != maFile || resultCode != RESULT_OK) return
        var tenFile = "khao_sat.xlsx"
        contentResolver.query(uri, null, null, null, null)?.use { c ->
            val cot = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (cot >= 0 && c.moveToFirst()) tenFile = c.getString(cot) ?: tenFile
        }
        val dich = File(cacheDir, "khao_sat.xlsx")
        contentResolver.openInputStream(uri)?.use { vao -> dich.outputStream().use { vao.copyTo(it) } }
        log.text = ""
        chayNen("Nhập dự án từ $tenFile", coTomTat = false) {
            val kq = core.callAttr("nhap_excel", dich.absolutePath, tenFile, nhatKy).toString()
            nhatKy.ghi("✔ Đã lưu dự án: $kq")
            null
        }
    }

    // ---------------- User / pass ----------------
    private fun hopCaiDat() = hopUserPass(null, null)

    /** Một hộp duy nhất cho user/pass cam, modem và WiFi modem.
     *  ma == null: MẶC ĐỊNH cả hệ thống. Có ma/stt: nhập RIÊNG cho điểm đó — được ưu tiên, mặc định giữ nguyên. */
    private fun hopUserPass(ma: String?, stt: String?, loi: String = "", nhap: List<String>? = null, xong: (() -> Unit)? = null) {
        val rieng = ma != null && stt != null
        val cu = nhap ?: try {
            (if (rieng) core.callAttr("lay_rieng", ma, stt) else core.callAttr("lay_tat_ca_mac_dinh")).asList().map { it.toString() }
        } catch (_: Exception) { core.callAttr("lay_cai_dat").asList().map { it.toString() } + listOf("", "") }
        val hop = LinearLayout(this)
        hop.orientation = LinearLayout.VERTICAL
        hop.setPadding(dp(20), dp(8), dp(20), 0)
        val nhan = listOf("User cam", "Pass cam", "User modem", "Pass modem", "Tên WiFi", "Pass WiFi")
        val o = nhan.mapIndexed { i, n ->
            val dong = LinearLayout(this)
            dong.orientation = LinearLayout.HORIZONTAL
            dong.gravity = android.view.Gravity.CENTER_VERTICAL
            val tieuDeO = TextView(this)
            tieuDeO.text = "$n:"
            tieuDeO.textSize = 15f
            tieuDeO.setTypeface(null, Typeface.BOLD)
            tieuDeO.setTextColor(Color.parseColor("#0F5D8C"))
            dong.addView(tieuDeO, LinearLayout.LayoutParams(dp(112), LinearLayout.LayoutParams.WRAP_CONTENT))
            val e = EditText(this)
            e.hint = if (i == 4) "WiFi của modem" else "Nhập $n"
            e.setText(cu.getOrElse(i) { "" })
            e.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
            dong.addView(e, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            hop.addView(dong)
            e
        }
        val tenDiem = if (rieng) core.callAttr("ten_diem", ma, stt).toString() else ""
        val b = AlertDialog.Builder(this)
            .setTitle(if (rieng) "Riêng cho điểm: $tenDiem" else "Mặc định cho cả hệ thống")
            .setMessage(if (loi.isNotEmpty()) "⚠ $loi"
                else if (rieng) "Chỉ áp dụng cho điểm này và được ưu tiên khi cài. Mặc định của cả hệ thống giữ nguyên."
                else "Nhập một lần, dùng cho mọi điểm. Điểm nào thực tế khác thì tới nơi app sẽ hỏi nhập riêng cho điểm đó.")
            .setView(hop)
            .setPositiveButton(if (rieng) "Lưu cho điểm này" else "Lưu") { _, _ ->
                val v = o.map { it.text.toString() }
                val kq = try {
                    (if (rieng) core.callAttr("luu_rieng", ma, stt, v[0], v[1], v[2], v[3], v[4], v[5])
                    else core.callAttr("luu_tat_ca_mac_dinh", v[0], v[1], v[2], v[3], v[4], v[5])).toString()
                } catch (e: Exception) { e.message ?: "Không lưu được" }
                if (kq.isNotEmpty()) { hopUserPass(ma, stt, kq, v, xong); return@setPositiveButton }
                nhatKy.ghi(if (rieng) "✔ Đã lưu user/pass RIÊNG cho $tenDiem (mặc định giữ nguyên)." else "✔ Đã lưu user/pass mặc định.")
                daXinWifi.clear()
                capNhatTieuDe()
                if (xong != null) { xong() } else { if (!rieng) xetTuDong() }
            }
            .setNegativeButton("Huỷ", null)
        if (rieng && cu.getOrElse(6) { "" } == "1") b.setNeutralButton("Về mặc định") { _, _ ->
            core.callAttr("xoa_rieng", ma, stt)
            nhatKy.ghi("Điểm $tenDiem trở về dùng user/pass mặc định.")
            capNhatTieuDe()
        }
        b.show()
    }

    // ---------------- Chạy ----------------
    private fun sanSang(): Boolean {
        if (!core.callAttr("co_du_lieu").toBoolean()) { hoiFileCauHinh(); return false }
        if (!core.callAttr("co_cai_dat").toBoolean()) { hopCaiDat(); return false }
        return true
    }

    /** Chưa có dự án nào = app chưa biết điểm nào, tên miền DDNS nào → nói rõ rồi mới mở chọn file (không mở mù). */
    private fun hoiFileCauHinh() {
        AlertDialog.Builder(this)
            .setTitle("Chưa có file cấu hình dự án")
            .setMessage("App cài theo file cấu hình: danh sách điểm, số cam và TÊN MIỀN DDNS của từng điểm. Máy này chưa có dự án nào nên chưa cài được.\n\n" +
                "• Có file Excel khảo sát (cột Domain, User, PW): chọn file.\n" +
                "• Dự án tạo bên LiteMark: nhận dự án về, tên miền nạp sau hoặc nhập tại cột.")
            .setPositiveButton("Chọn file Excel") { _, _ -> moFile() }
            .setNeutralButton("Nhận từ LiteMark") { _, _ -> startActivity(Intent(this, TuXaActivity::class.java)) }
            .setNegativeButton("Đóng", null)
            .show()
    }

    // ================================================================= 2.5: TỰ CÀI khi vào WiFi modem của điểm
    // Điện thoại vừa vào một WiFi (hoặc vừa mở app khi đang ở WiFi đó) → lấy GPS → dò điểm trong file.
    // Đủ chắc (≤150 m, đúng 1 điểm, có tên miền, chưa cài) thì đếm ngược 8 giây rồi TỰ CÀI, không cần bấm "Cài điểm này".
    // Không chắc thì đứng yên, chỉ ghi một dòng lý do — nút bấm tay vẫn còn nguyên.
    private val daXetTuDong = mutableSetOf<String>()      // mỗi WiFi (theo IP modem + IP máy) chỉ xét một lần mỗi lượt mở app
    private var dangXetTuDong = false
    private var hopTuDong: AlertDialog? = null
    private var dangHien = false

    private fun batTuDong() = getSharedPreferences("camlink", MODE_PRIVATE).getBoolean("tu_dong", true)

    private fun ngheWifi() {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val yc = android.net.NetworkRequest.Builder().addTransportType(NetworkCapabilities.TRANSPORT_WIFI).build()
        runCatching {
            cm.registerNetworkCallback(yc, object : ConnectivityManager.NetworkCallback() {
                override fun onLinkPropertiesChanged(network: android.net.Network, lp: android.net.LinkProperties) {
                    ui.postDelayed({ xetTuDong() }, 1500)      // chờ DHCP cấp IP xong
                }
            })
        }
    }

    private var mangRieng: android.net.Network? = null      // WiFi modem app tự vào (chỉ app dùng, điện thoại vẫn giữ 4G)
    private var cbRieng: ConnectivityManager.NetworkCallback? = null
    private val daXinWifi = mutableSetOf<String>()
    private var choWifiTay: String? = null      // đã báo "Vui lòng kết nối WiFi": ghi IP modem lúc báo ("" nếu chưa ở WiFi nào) để nhận ra khi thợ vào WiFi khác

    private fun wifiChung(): Pair<String, String> = try {
        val w = core.callAttr("lay_wifi").asList().map { it.toString() }
        Pair(w[0], w[1])
    } catch (_: Exception) { Pair("", "") }

    @Suppress("DEPRECATION")
    private fun ssidDangVao(): String {
        val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        return runCatching { wm.connectionInfo?.ssid?.trim('"') ?: "" }.getOrDefault("")
    }

    private fun thaWifiRieng() {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        cbRieng?.let { runCatching { cm.unregisterNetworkCallback(it) } }
        cbRieng = null
        mangRieng = null
    }

    /** WiFi dùng cho điểm: phần nhập riêng của điểm được ưu tiên, không có thì lấy mặc định. */
    private fun wifiDiem(ma: String, stt: String): Pair<String, String> = try {
        val r = core.callAttr("lay_rieng", ma, stt).asList().map { it.toString() }
        Pair(r[4], r[5])
    } catch (_: Exception) { wifiChung() }

    private fun xetTuDong() {
        if (!dangHien || !batTuDong() || dangChay.isNotEmpty() || dangXetTuDong || hopTuDong != null || cbRieng != null) return
        if (!coQuyenViTri()) return
        if (!core.callAttr("co_du_lieu").toBoolean()) return
        val (may, gw) = mangWifi()
        val coWifi = may.isNotEmpty() && gw.isNotEmpty()
        if (!coWifi && wifiChung().first.isEmpty()) return      // không ở WiFi nào và chưa nhập WiFi mặc định → chờ thợ vào WiFi
        dangXetTuDong = true
        layViTri { vt ->
            dangXetTuDong = false
            if (vt == null) return@layViTri
            viTriCuoi = vt
            val r = try { org.json.JSONObject(core.callAttr("tu_dong_xet", vt.latitude, vt.longitude).toString()) } catch (_: Exception) { return@layViTri }
            val ma = r.optString("ma"); val stt = r.optString("stt")
            if (ma.isEmpty() || dangChay.isNotEmpty() || !dangHien) return@layViTri
            val diem = "$ma|$stt"
            if (!r.optBoolean("ok")) {
                val daCai = r.optString("da_cai")
                if (daCai.isNotEmpty()) {      // tới điểm đã cài: báo đã cài + tự mở hình các cam, không cài lại
                    if (!daXetTuDong.add("da-cai|$diem")) return@layViTri
                    val ten = core.callAttr("ten_diem", ma, stt).toString()
                    log.text = ""
                    nhatKy.ghi("✔ $ten — ĐÃ CÀI lúc $daCai. Đang lấy hình các cam qua tên miền…")
                    chayNen("ĐÃ CÀI $daCai · $ten — đang lấy hình", coTomTat = false) { bangChung(ma, stt, thuLai = false); null }
                    return@layViTri
                }
                if (r.optInt("m", 9999) <= 400 && daXetTuDong.add("ly-do|$diem"))
                    datTrangThai("Tới gần điểm nhưng chưa tự cài: ${r.optString("ly_do")}", XAM)
                return@layViTri
            }
            val ten = core.callAttr("ten_diem", ma, stt).toString()
            val (tenWifi, _) = wifiDiem(ma, stt)
            val vuaVaoTay = choWifiTay != null && coWifi && gw != choWifiTay      // thợ vừa tự vào WiFi sau khi app báo
            val dungWifi = coWifi && (tenWifi.isEmpty() || vuaVaoTay ||
                try { core.callAttr("wifi_khop", ssidDangVao(), tenWifi).toBoolean() } catch (_: Exception) { false })
            when {
                dungWifi -> {
                    if (vuaVaoTay) choWifiTay = null
                    if (daXetTuDong.add("$gw|$may|$diem")) demNguocCai(ma, stt, ten, r.optInt("m"), gw)
                }
                tenWifi.isNotEmpty() && android.os.Build.VERSION.SDK_INT >= 29 -> {
                    if (daXinWifi.add(diem)) vaoWifiRoiCai(ma, stt, ten, r.optInt("m"))      // mỗi điểm tự thử MỘT lần; thử lại chỉ khi người dùng nhập lại
                }
                else -> if (daXetTuDong.add("can-wifi|$diem")) datTrangThai("⚠ Vui lòng kết nối WiFi\n$ten — chưa cài", VANG)
            }
        }
    }

    /** Tự vào WiFi modem (tên + mật khẩu dùng chung đã lưu) rồi cài. Kết nối này chỉ app dùng; cài xong tự nhả. */
    private fun vaoWifiRoiCai(ma: String, stt: String, ten: String, m: Int) {
        if (android.os.Build.VERSION.SDK_INT < 29) return
        val (tenWifi, mk) = wifiDiem(ma, stt)
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val b = android.net.wifi.WifiNetworkSpecifier.Builder()
        if (tenWifi.endsWith("*")) b.setSsidPattern(android.os.PatternMatcher(tenWifi.dropLast(1), android.os.PatternMatcher.PATTERN_PREFIX))
        else b.setSsid(tenWifi)
        if (mk.isNotEmpty()) b.setWpa2Passphrase(mk)
        val yc = android.net.NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .setNetworkSpecifier(b.build()).build()
        datTrangThai("📶 Đang vào WiFi modem «$tenWifi»\n$ten", LAM)
        nhatKy.ghi("Tới $ten → tự vào WiFi modem «$tenWifi» (thử 30 giây)…")
        val cb = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: android.net.Network) {
                ui.postDelayed({
                    if (cbRieng !== this) return@postDelayed
                    mangRieng = network
                    val (_, gw) = mangWifi()
                    nhatKy.ghi("✔ Đã vào WiFi modem $gw")
                    demNguocCai(ma, stt, ten, m, gw)
                }, 1500)
            }
            override fun onUnavailable() {
                ui.post {
                    if (cbRieng !== this) return@post
                    thaWifiRieng()
                    baoWifiKhac(ma, stt, ten, m, tenWifi)
                }
            }
            override fun onLost(network: android.net.Network) {
                ui.post { if (mangRieng == network && dangChay.isEmpty()) thaWifiRieng() }
            }
        }
        cbRieng = cb
        try { cm.requestNetwork(yc, cb, 30_000) } catch (e: Exception) {
            thaWifiRieng()
            baoWifiKhac(ma, stt, ten, m, tenWifi)
        }
    }

    /** Thử WiFi 30 giây không vào được → DỪNG (không tự thử lại), cảnh báo, để người dùng nhập lại riêng cho điểm hoặc tự vào WiFi. */
    private fun baoWifiKhac(ma: String, stt: String, ten: String, m: Int, tenWifi: String) {
        choWifiTay = mangWifi().second
        datTrangThai("⚠ Vui lòng kết nối WiFi\n$ten — chưa cài", VANG)
        nhatKy.ghi("⚠ Sau 30 giây không vào được WiFi «$tenWifi» ở $ten (khác tên hoặc khác mật khẩu). Đã dừng, chờ người dùng.")
        AlertDialog.Builder(this)
            .setTitle("Vui lòng kết nối WiFi")
            .setMessage("$ten\n\nApp không vào được WiFi «$tenWifi» sau 30 giây — điểm này WiFi khác tên hoặc khác mật khẩu.\n\n• Nhập lại WiFi cho riêng điểm này: app vào WiFi đó và cài tiếp. Mặc định của cả hệ thống giữ nguyên.\n• Hoặc tự kết nối WiFi modem bằng tay rồi quay lại app, app tự cài tiếp.")
            .setPositiveButton("Nhập lại cho điểm này") { _, _ ->
                hopUserPass(ma, stt) { choWifiTay = null; vaoWifiRoiCai(ma, stt, ten, m) }
            }
            .setNeutralButton("Mở cài đặt WiFi") { _, _ -> runCatching { startActivity(Intent(android.provider.Settings.ACTION_WIFI_SETTINGS)) } }
            .setNegativeButton("Đóng", null)
            .show()
    }

    /** Cài lại điểm sau khi người dùng nhập user/pass riêng: chưa ở WiFi thì app tự vào WiFi của điểm trước. */
    private fun caiLai(ma: String, stt: String) {
        val ten = core.callAttr("ten_diem", ma, stt).toString()
        if (mangWifi().first.isEmpty() && wifiDiem(ma, stt).first.isNotEmpty() && android.os.Build.VERSION.SDK_INT >= 29 && cbRieng == null)
            vaoWifiRoiCai(ma, stt, ten, -1)
        else chayDiem(ma, stt, ten)
    }

    private fun demNguocCai(ma: String, stt: String, ten: String, m: Int, gw: String) {
        var con = 8
        val hop = AlertDialog.Builder(this)
            .setTitle("Tự cài sau $con giây")
            .setMessage("$ten\n" + (if (m >= 0) "Cách điểm $m m · " else "") + "WiFi modem $gw\n\nApp tự tìm cam, đặt port, IP, DDNS và mở port modem theo file dự án.")
            .setPositiveButton("Cài ngay", null)
            .setNegativeButton("Huỷ", null)
            .setCancelable(false)
            .create()
        hopTuDong = hop
        val chay = { if (hopTuDong === hop) { hopTuDong = null; hop.dismiss(); nhatKy.ghi("Tự cài: $ten (GPS cách $m m, WiFi $gw)"); chayDiem(ma, stt, ten) } }
        val dem = object : Runnable {
            override fun run() {
                if (hopTuDong !== hop) return
                con -= 1
                if (con <= 0) chay() else { hop.setTitle("Tự cài sau $con giây"); ui.postDelayed(this, 1000) }
            }
        }
        hop.setOnShowListener {
            hop.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener { chay() }
            hop.getButton(AlertDialog.BUTTON_NEGATIVE).setOnClickListener {
                hopTuDong = null; hop.dismiss(); thaWifiRieng(); datTrangThai("Đã huỷ tự cài — bấm Cài điểm này khi cần", XAM)
            }
        }
        hop.show()
        ui.postDelayed(dem, 1000)
    }

    private fun coQuyenViTri() =
        checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    private fun batDauChay() {
        if (!sanSang()) return
        if (!coQuyenViTri()) {
            requestPermissions(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION), maViTri)
            return
        }
        log.text = ""
        datTrangThai("⏳ Đang lấy vị trí GPS…", LAM)
        nhatKy.ghi("Đang lấy vị trí GPS ...")
        layViTri { vt ->
            viTriCuoi = vt
            if (vt == null) {
                datTrangThai("Không lấy được GPS — chọn điểm", VANG)
                nhatKy.ghi("Không lấy được GPS — chọn điểm bằng tay.")
                chonDiem(chiKiemTra = false)
                return@layViTri
            }
            val gan = core.callAttr("diem_gan", vt.latitude, vt.longitude)
            if (gan == null || gan.toString() == "None") {
                nhatKy.ghi("Dự án không có toạ độ — chọn điểm bằng tay.")
                chonDiem(chiKiemTra = false)
                return@layViTri
            }
            val g = gan.asList()
            val ma = g[0].toString()
            val stt = g[1].toString()
            val m = g[4].toInt()
            val sat = g[5].toBoolean()
            when {
                m > 1000 -> {
                    datTrangThai("📍 TỪ XA — cách điểm gần nhất ${m / 1000} km", VANG)
                    nhatKy.ghi("Đang cách điểm gần nhất ${m / 1000} km → không cài được, chỉ kiểm tra từ xa.")
                    AlertDialog.Builder(this)
                        .setTitle("Bạn đang ở XA điểm lắp")
                        .setMessage("Điểm gần nhất: ${core.callAttr("ten_diem", ma, stt)}\ncách ${m / 1000} km.\n\n" +
                            "Ở xa thì app KHÔNG cài được (chỉ cài được khi đứng tại điểm và vào WiFi modem của điểm).\n\n" +
                            "Có thể KIỂM TRA TỪ XA: xem tên miền và từng camera có xem được từ Internet không. Không thay đổi gì.")
                        .setPositiveButton("Kiểm tra từ xa") { _, _ -> chonDiem(chiKiemTra = true) }
                        .setNegativeButton("Đóng", null)
                        .show()
                }
                m > 400 || sat -> xacNhanCai(ma, stt, m, if (sat) "Có điểm khác ở sát bên — kiểm tra đúng điểm." else "Cách hơi xa (${m} m).")
                else -> xacNhanCai(ma, stt, m, null)
            }
        }
    }

    /** Link từ LiteMark: camlink://nhan?ct=<id>&ten=<tên> → mở màn Kiểm tra từ xa và nhận dự án. */
    private fun xuLyLink(i: Intent?) {
        val u = i?.data ?: return
        if (u.scheme != "camlink" || u.host != "nhan") return
        val ct = u.getQueryParameter("ct") ?: return
        startActivity(Intent(this, TuXaActivity::class.java).putExtra("nhan_ct", ct).putExtra("nhan_ten", u.getQueryParameter("ten") ?: ""))
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); xuLyLink(intent) }

    /** Điểm (dự án nhận từ LiteMark) chưa có tên miền → chọn tên miền TẠI CỘT trước khi cài. */
    private fun xacNhanCai(ma: String, stt: String, m: Int, canhBao: String?) {
        val can = try { core.callAttr("can_chon_ten_mien", ma, stt).toBoolean() } catch (_: Exception) { false }
        val thieu = try { core.callAttr("ten_mien_diem", ma, stt).toString().isEmpty() } catch (_: Exception) { false }
        if (!can && !thieu) { xacNhanCaiThat(ma, stt, m, canhBao); return }
        val ten = core.callAttr("ten_diem", ma, stt).toString()
        val ds = if (can) org.json.JSONArray(core.callAttr("ung_vien_ten_mien", ma, stt).toString()) else org.json.JSONArray()
        if (ds.length() == 0) {      // chưa nạp file tên miền, hoặc kho của bên cấp đã dùng hết
            val hop = AlertDialog.Builder(this).setTitle("Điểm này chưa có tên miền DDNS")
                .setMessage("$ten\n\n" + (if (can) "Kho tên miền của bên cấp đã dùng hết." else "Dự án chưa nạp file tên miền của bên cấp.") +
                    " Không có tên miền thì app không đặt được DDNS lên cam và không kiểm tra từ xa được điểm này.\n\nChọn một cách:")
                .setPositiveButton("Nhập tên miền") { _, _ -> nhapTenMien(ma, stt, m, canhBao, ten) }
                .setNeutralButton("Nạp file tên miền") { _, _ -> choDdns = arrayOf(ma, stt, m.toString(), canhBao ?: ""); moFileDdns() }
                .setNegativeButton("Cài không DDNS") { _, _ ->
                    xacNhanCaiThat(ma, stt, m, listOfNotNull(canhBao, "Điểm chưa có tên miền: chỉ đặt port, IP cam và mở port modem. DDNS bỏ trống — có tên miền thì chạy lại điểm này.").joinToString("\n⚠ "))
                }
            hop.show()
            return
        }
        val nhan = (0 until minOf(ds.length(), 8)).map { i ->
            val d = ds.getJSONObject(i); val kc = d.optInt("kc", -1)
            "${d.optString("domain")}  ·  dòng ${d.optString("no")} ${d.optString("ten")}" + (if (kc >= 0) "  ·  cách ghim $kc m" else "  ·  (file không có toạ độ)") + (if (kc > 100) "  ⚠ XA" else "")
        }
        AlertDialog.Builder(this).setTitle("Chọn tên miền cho: $ten")
            .setItems(nhan.toTypedArray()) { _, i ->
                val d = ds.getJSONObject(i)
                val chot = {
                    core.callAttr("gan_ten_mien", ma, stt, d.optInt("i"))
                    nhatKy.ghi("Đã chốt tên miền ${d.optString("domain")} cho $ten (chọn tại cột)")
                    xacNhanCaiThat(ma, stt, m, canhBao)
                }
                if (d.optInt("kc", -1) > 100) AlertDialog.Builder(this).setTitle("Tên miền này ở XA ghim (${d.optInt("kc")} m)")
                    .setMessage("Dòng ${d.optString("no")} «${d.optString("ten")}» trong file cách ghim ${d.optInt("kc")} m. Chắc chắn đúng cột này?")
                    .setPositiveButton("Đúng, gán") { _, _ -> chot() }.setNegativeButton("Chọn lại") { _, _ -> xacNhanCai(ma, stt, m, canhBao) }.show()
                else chot()
            }
            .setNeutralButton("Cài không DDNS") { _, _ -> xacNhanCaiThat(ma, stt, m, canhBao) }
            .setNegativeButton("Huỷ", null).show()
    }

    private var choDdns: Array<String>? = null      // điểm đang chờ nạp file tên miền: mã, stt, mét, cảnh báo
    private val maFileDdns = 13

    private fun moFileDdns() {
        val i = Intent(Intent.ACTION_OPEN_DOCUMENT)
        i.addCategory(Intent.CATEGORY_OPENABLE)
        i.type = "*/*"
        startActivityForResult(i, maFileDdns)
    }

    /** Nạp file tên miền của bên cấp ngay tại cột, ghép theo toạ độ rồi quay lại đúng bước chọn tên miền cho điểm đang cài. */
    private fun napDdns(uri: Uri) {
        val cho = choDdns ?: return
        choDdns = null
        val dich = File(cacheDir, "ddns.xlsx")
        contentResolver.openInputStream(uri)?.use { vao -> dich.outputStream().use { vao.copyTo(it) } }
        datTrangThai("⏳ Đang ghép tên miền vào các điểm…", LAM)
        thread {
            try {
                val bc = org.json.JSONObject(core.callAttr("lm_nap_ddns", cho[0], dich.absolutePath, nhatKy).toString())
                ui.post {
                    datTrangThai("✔ Đã nạp ${bc.optInt("tong_dong")} tên miền · tự ghép ${bc.optInt("tu_gan")} điểm", XANH)
                    if (cho[1].isEmpty()) {      // nạp từ trang Dự án (không gắn với điểm nào): báo kết quả ghép rồi vẽ lại danh sách
                        val th = bc.optJSONArray("diem_thieu")
                        AlertDialog.Builder(this).setTitle("Đã nạp file tên miền")
                            .setMessage("File có ${bc.optInt("tong_dong")} tên miền · dự án ${bc.optInt("tong_diem")} điểm\n✔ Tự ghép chắc theo toạ độ: ${bc.optInt("tu_gan")} điểm" +
                                (if (th != null && th.length() > 0) "\n→ ${th.length()} điểm còn lại chọn tên miền tại cột lúc cài" else ""))
                            .setPositiveButton("OK", null).show()
                        capNhatTieuDe()
                    } else xacNhanCai(cho[0], cho[1], cho[2].toInt(), cho[3].ifEmpty { null })
                }
            } catch (e: Exception) {
                val loi = e.message?.substringAfterLast("Error: ")?.take(200) ?: e.toString()
                ui.post {
                    datTrangThai("✖ File tên miền không đọc được", DO)
                    nhatKy.ghi("✖ File tên miền: $loi")
                    AlertDialog.Builder(this).setTitle("File tên miền không đọc được").setMessage(loi)
                        .setPositiveButton("Chọn lại") { _, _ -> if (cho[1].isEmpty()) { choDdns = cho; moFileDdns() } else xacNhanCai(cho[0], cho[1], cho[2].toInt(), cho[3].ifEmpty { null }) }
                        .setNegativeButton("Đóng", null).show()
                }
            }
        }
    }

    /** Nhập tay tên miền (và tài khoản DDNS nếu có) cho điểm đang đứng. */
    private fun nhapTenMien(ma: String, stt: String, m: Int, canhBao: String?, ten: String, loi: String = "", cu: List<String> = listOf("", "", "")) {
        val hop = LinearLayout(this)
        hop.orientation = LinearLayout.VERTICAL
        hop.setPadding(dp(20), dp(8), dp(20), 0)
        val goiY = listOf("Tên miền, vd: congtrinh-01.ddns.net", "User DDNS (bỏ trống nếu không có)", "Pass DDNS (bỏ trống nếu không có)")
        val o = goiY.mapIndexed { i, g ->
            val e = EditText(this)
            e.hint = g
            e.setText(cu[i])
            e.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
            hop.addView(e)
            e
        }
        AlertDialog.Builder(this)
            .setTitle("Tên miền cho: $ten")
            .setMessage(if (loi.isEmpty()) "Nhập đúng tên miền bên cấp giao cho điểm này." else "⚠ $loi")
            .setView(hop)
            .setPositiveButton("Lưu và cài") { _, _ ->
                val v = o.map { it.text.toString().trim() }
                val kq = core.callAttr("dat_ten_mien_tay", ma, stt, v[0], v[1], v[2]).toString()
                if (kq.isNotEmpty()) { nhapTenMien(ma, stt, m, canhBao, ten, kq, v); return@setPositiveButton }
                nhatKy.ghi("Đã nhập tên miền ${v[0].lowercase()} cho $ten (nhập tay tại cột)")
                xacNhanCaiThat(ma, stt, m, canhBao)
            }
            .setNegativeButton("Quay lại") { _, _ -> xacNhanCai(ma, stt, m, canhBao) }
            .show()
    }

    /** Bảng kiểm tra trước khi cài: chế độ, điểm, mạng WiFi, việc sẽ làm. */
    private fun xacNhanCaiThat(ma: String, stt: String, m: Int, canhBao: String?) {
        val (may, gw) = mangWifi()
        val ten = core.callAttr("ten_diem", ma, stt).toString()
        val viTri = when {
            m >= 0 -> "Cách điểm: $m m"
            else -> "Vị trí: không rõ (không có GPS)"
        }
        val mang = if (may.isEmpty()) "WiFi: CHƯA VÀO WiFi nào" else "WiFi: máy $may · modem $gw"
        val tenMien = try { core.callAttr("ten_mien_diem", ma, stt).toString() } catch (_: Exception) { "?" }
        val noiDung = StringBuilder()
            .append("CHẾ ĐỘ: CÀI TẠI CHỖ\n").append(ten).append("\n").append(viTri).append("\n").append(mang).append("\n")
            .append(if (tenMien.isEmpty()) "Tên miền: CHƯA CÓ — cài không DDNS" else if (tenMien == "?") "" else "Tên miền: $tenMien").append("\n")
            .append(try {
                val tt = org.json.JSONObject(core.callAttr("thong_tin_cai", ma, stt).toString())
                (if (tenMien.isEmpty() || tenMien == "?") "" else "Tài khoản DDNS: " + (if (tt.optString("u_ddns").isEmpty()) "file KHÔNG có user/pass cho tên miền này" else tt.optString("u_ddns") + " (theo file)") + "\n") +
                    "Cam: ${tt.optString("cam_user")} · Modem: ${tt.optString("modem_user")}" + (if (tt.optBoolean("modem_mac_dinh")) " (mặc định)" else "") + "\n"
            } catch (_: Exception) { "" }).append("\n")
            .append(if (tenMien.isEmpty()) "App sẽ: tìm cam trong mạng này → đặt port, IP (cam nào đã đúng thì giữ nguyên) → mở port trên modem. DDNS bỏ trống.\n"
                    else "App sẽ: tìm cam trong mạng này → đặt port, IP, DDNS (cam nào đã đúng thì giữ nguyên) → mở port trên modem → kiểm tra tên miền.\n")
        if (canhBao != null) noiDung.append("\n⚠ ").append(canhBao).append("\n")
        noiDung.append("\nChỉ bấm BẮT ĐẦU khi đang đứng tại điểm này và điện thoại đã vào WiFi modem của điểm.")
        datTrangThai("📍 TẠI CHỖ — $ten", LAM)
        AlertDialog.Builder(this)
            .setTitle("Kiểm tra trước khi cài")
            .setMessage(noiDung.toString())
            .setPositiveButton("BẮT ĐẦU CÀI") { _, _ -> chayDiem(ma, stt, ten) }
            .setNeutralButton("Chỉ kiểm tra từ xa") { _, _ -> kiemTraTuXa(ma, stt, ten) }
            .setNegativeButton("Huỷ") { _, _ -> datTrangThai("Đã huỷ", XAM) }
            .show()
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == maViTriTuDong) { xetTuDong(); return }
        if (requestCode == maViTri) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) batDauChay()
            else chonDiem(chiKiemTra = false)
        }
    }

    @Suppress("MissingPermission", "DEPRECATION")
    private fun layViTri(xong: (Location?) -> Unit) {
        val lm = getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val moi = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
            .mapNotNull { runCatching { lm.getLastKnownLocation(it) }.getOrNull() }
            .filter { System.currentTimeMillis() - it.time < 120_000 }
            .maxByOrNull { it.time }
        if (moi != null) { xong(moi); return }
        var daTra = false
        val nghe = object : LocationListener {
            override fun onLocationChanged(l: Location) {
                if (!daTra) { daTra = true; lm.removeUpdates(this); xong(l) }
            }
            @Deprecated("") override fun onStatusChanged(p: String?, s: Int, b: Bundle?) {}
            override fun onProviderEnabled(p: String) {}
            override fun onProviderDisabled(p: String) {}
        }
        for (p in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) {
            runCatching { lm.requestLocationUpdates(p, 0L, 0f, nghe, Looper.getMainLooper()) }
        }
        ui.postDelayed({ if (!daTra) { daTra = true; lm.removeUpdates(nghe); xong(null) } }, 25_000)
    }

    private fun chonDiem(chiKiemTra: Boolean) {
        if (!sanSang()) return
        val ds = core.callAttr("danh_sach").asList().map { it.toString() }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle(if (chiKiemTra) "Kiểm tra từ xa điểm nào?" else "Đang đứng ở điểm nào?")
            .setItems(ds) { _, i ->
                val k = core.callAttr("khoa_theo_so_thu_tu", i).asList()
                val ma = k[0].toString()
                val stt = k[1].toString()
                val ten = core.callAttr("ten_diem", ma, stt).toString()
                if (chiKiemTra) { kiemTraTuXa(ma, stt, ten); return@setItems }
                val vt = viTriCuoi
                val m = if (vt != null) core.callAttr("khoang_cach_den", ma, stt, vt.latitude, vt.longitude).toInt() else -1
                if (m > 1000) {
                    AlertDialog.Builder(this)
                        .setTitle("Không cài được từ xa")
                        .setMessage("$ten\nĐang cách ${m / 1000} km.\n\nChỉ cài được khi đứng tại điểm và vào WiFi modem của điểm. Muốn kiểm tra từ xa điểm này?")
                        .setPositiveButton("Kiểm tra từ xa") { _, _ -> kiemTraTuXa(ma, stt, ten) }
                        .setNegativeButton("Đóng", null)
                        .show()
                } else {
                    xacNhanCai(ma, stt, m, if (m < 0) "Không có GPS: app không tự xác nhận được bạn đang ở điểm này." else null)
                }
            }
            .show()
    }

    @Suppress("DEPRECATION")
    private fun mangWifi(): Pair<String, String> {
        mangRieng?.let { n ->      // WiFi modem app tự vào: lấy IP máy + IP modem từ chính kết nối đó
            val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val lp = cm.getLinkProperties(n)
            val may = lp?.linkAddresses?.firstOrNull { it.address is java.net.Inet4Address }?.address?.hostAddress ?: ""
            val gw = lp?.routes?.firstOrNull { it.isDefaultRoute && it.gateway is java.net.Inet4Address }?.gateway?.hostAddress
                ?: (if (may.isNotEmpty()) may.substringBeforeLast(".") + ".1" else "")
            if (may.isNotEmpty()) return Pair(may, gw)
        }
        val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val d = wm.dhcpInfo
        fun ip(v: Int) = if (v == 0) "" else "${v and 255}.${v shr 8 and 255}.${v shr 16 and 255}.${v shr 24 and 255}"
        return Pair(ip(d.ipAddress), ip(d.gateway))
    }

    /** Ép mọi kết nối của app đi qua WiFi modem (kể cả khi modem chưa có Internet). */
    private fun ganWifi(bat: Boolean) {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        if (!bat) { cm.bindProcessToNetwork(null); return }
        val wifi = mangRieng ?: cm.allNetworks.firstOrNull { n ->
            cm.getNetworkCapabilities(n)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
        }
        cm.bindProcessToNetwork(wifi)
    }

    private var diemCuoi: Pair<String, String>? = null      // điểm vừa cài — để nhập user/pass riêng rồi cài lại khi chưa đạt

    private fun chayDiem(ma: String, stt: String, ten: String) {
        diemCuoi = Pair(ma, stt)
        val (may, gw) = mangWifi()
        if (may.isEmpty()) {
            datTrangThai("✖ Chưa vào WiFi modem", DO)
            nhatKy.ghi("✖ Điện thoại chưa vào WiFi của modem. Vào WiFi modem ở điểm này rồi bấm lại.")
            return
        }
        log.text = ""
        val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val khoa = wm.createMulticastLock("camlink")
        chayNen("CÀI TẠI CHỖ · $ten", coTomTat = true) {
            khoa.acquire()
            ganWifi(true)
            val kq: List<String>
            try {
                core.callAttr("chay", ma, stt, may, gw, nhatKy)
                kq = core.callAttr("tom_tat").asList().map { it.toString() }
            } finally {
                ganWifi(false)
                khoa.release()
            }
            ui.post { datTrangThai("⏳ $dangChay\nĐang: chứng minh qua tên miền (4G)", LAM) }
            ui.post { thaWifiRieng() }      // cài xong: nhả WiFi modem app tự vào, điện thoại về mạng thường
            bangChung(ma, stt)
            kq
        }
    }

    /** Gọi tên miền qua 4G như IOC: chụp ảnh từng cam + lấy luồng live, rồi mở màn hình sơ đồ. */
    private fun bangChung(ma: String, stt: String, thuLai: Boolean = true) {
        val di_dong = ganDiDong(true)
        if (!di_dong) nhatKy.ghi("⚠ Không bật được 4G — thử qua WiFi (một số modem không cho gọi tên miền của chính nó từ bên trong).")
        try {
            var j = ""
            for (lan in 1..(if (thuLai) 3 else 1)) {   // vừa cài xong: DDNS có thể chậm 1–2 phút
                j = core.callAttr("bang_chung", ma, stt, nhatKy).toString()
                if (j.contains("\"ngoai\": true")) break
                if (thuLai && lan < 3) { nhatKy.ghi("   chờ 40 giây cho tên miền cập nhật rồi thử lại…"); Thread.sleep(40_000) }
            }
            val du = j
            ui.post { startActivity(Intent(this, SoDoActivity::class.java).putExtra("du_lieu", du)) }
        } finally {
            ganDiDong(false)
        }
    }

    /** Ép app đi đường 4G (để kiểm tra từ ngoài thật). Trả false nếu máy không có / không bật dữ liệu di động. */
    private fun ganDiDong(bat: Boolean): Boolean {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        if (!bat) { cm.bindProcessToNetwork(null); return true }
        val dd = cm.allNetworks.firstOrNull { n ->
            val nc = cm.getNetworkCapabilities(n)
            nc?.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) == true &&
                nc.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
        } ?: return false
        return cm.bindProcessToNetwork(dd)
    }

    private fun moSoDoGanNhat() {
        val j = core.callAttr("so_do_gan_nhat").toString()
        if (j.isEmpty()) { nhatKy.ghi("Chưa có lần chạy nào có sơ đồ."); return }
        startActivity(Intent(this, SoDoActivity::class.java).putExtra("du_lieu", j))
    }

    private fun kiemTraTuXa(ma: String, stt: String, ten: String) {
        log.text = ""
        chayNen("KIỂM TRA TỪ XA · $ten", coTomTat = true) {
            // đi đường 4G như IOC; đứng trong WiFi của chính điểm đó thì modem có thể chặn gọi tên miền của nó
            if (!ganDiDong(true)) nhatKy.ghi("⚠ Không bật được 4G — đang kiểm tra qua WiFi. Nếu đang vào WiFi của chính điểm này, kết quả có thể báo ĐÓNG sai.")
            val kq = try {
                core.callAttr("kiem_tra_tu_xa", ma, stt, nhatKy).asList().map { it.toString() }
            } finally { ganDiDong(false) }
            if (kq[0] != "LOI") bangChung(ma, stt, thuLai = false)
            kq
        }
    }

    private var tvThuMau: TextView? = null      // hộp tiến độ của "Thu mẫu thiết bị" — hiện ngay tại chỗ bấm (cả giao diện đồ hoạ lẫn chữ)

    private fun thuMau() {
        val (may, gw) = mangWifi()
        if (may.isEmpty()) {
            datTrangThai("✖ Chưa vào WiFi modem", DO)
            nhatKy.ghi("✖ Điện thoại chưa vào WiFi của modem.")
            AlertDialog.Builder(this).setTitle("Chưa vào WiFi modem")
                .setMessage("Thu mẫu cần điện thoại ở cùng mạng với cam.\n\nVào WiFi của modem đang cắm cam, rồi bấm lại \"Thu mẫu thiết bị\".")
                .setPositiveButton("Mở cài đặt WiFi") { _, _ -> try { startActivity(Intent(android.provider.Settings.ACTION_WIFI_SETTINGS)) } catch (e: Exception) {} }
                .setNegativeButton("Đóng", null).show()
            return
        }
        log.text = ""
        val tv = TextView(this)
        tv.typeface = Typeface.MONOSPACE
        tv.textSize = 12f
        tv.setPadding(dp(16), dp(12), dp(16), dp(12))
        tv.text = "Đang quét mạng $gw …\n"
        val sv = ScrollView(this)
        sv.addView(tv)
        val hop = AlertDialog.Builder(this).setTitle("⏳ Đang thu mẫu thiết bị (chỉ đọc)").setView(sv)
            .setPositiveButton("Ẩn (vẫn chạy)", null).setCancelable(false).show()
        tvThuMau = tv
        chayNen("Thu mẫu thiết bị trong WiFi $gw (chỉ đọc)", coTomTat = true) {
            ganWifi(true)
            val zp = try {
                core.callAttr("thu_mau", may, gw, nhatKy)?.toString() ?: ""
            } finally {
                ganWifi(false)
                ui.post { tvThuMau = null; try { hop.dismiss() } catch (e: Exception) {} }
            }
            if (zp.isNotEmpty() && File(zp).exists()) {
                ui.post { guiFile(File(zp), "Gửi file mẫu thiết bị cho Claude") }
                listOf("DAT", "Đã thu xong file mẫu.\nBảng chia sẻ vừa mở → chọn Zalo/Gmail gửi cho Claude.\n(Lỡ đóng bảng chia sẻ thì bấm \"Gửi kết quả\".)")
            } else
                listOf("LOI", "Không thu được mẫu: không thấy thiết bị nào trong mạng $gw.\nKiểm tra cam đã cấp nguồn, đã cắm dây vào modem, và điện thoại đang ở đúng WiFi modem đó.")
        }
    }

    // ---------------- Gửi kết quả ----------------
    // ---------------- cập nhật đè ----------------
    private val maZip = 31
    private val kenhCapNhat = "https://raw.githubusercontent.com/hoangvhuan-hh/camlink-capnhat/main"

    private fun capNhat() {
        AlertDialog.Builder(this).setTitle("Cập nhật CamLink")
            .setMessage("• Tự động: tải phần logic mới (vài trăm KB) từ kênh cập nhật; chỉ tải APK khi phần Android thay đổi.\n• Từ file: nạp gói .zip Claude gửi (vài trăm KB).")
            .setPositiveButton("Tự động") { _, _ ->
                thread {
                    try {
                        val pc = packageManager.getPackageInfo(packageName, 0).longVersionCode
                        val j = org.json.JSONObject(core.callAttr("kiem_cap_nhat", kenhCapNhat, pc).toString())
                        ui.post {
                            val loi = j.optString("loi_moi", "")
                            val apk = j.optJSONObject("apk_moi")
                            val sb = StringBuilder()
                            if (loi.isNotEmpty() && loi != "null") sb.append("✔ Đã tải lõi $loi — mở lại app để dùng.\n")
                            if (apk != null) sb.append("Có APK mới ${apk.optString("ten")} (${apk.optString("mb")} MB): ${apk.optString("ly_do")}\n")
                            val gc = j.optString("ghi_chu", "")
                            if (sb.isEmpty()) sb.append(if (gc.isNotEmpty() && gc != "null") gc else "Đang là bản mới nhất.")
                            val d = AlertDialog.Builder(this).setTitle("Cập nhật").setMessage(sb.toString())
                            if (apk != null) d.setPositiveButton("Tải APK") { _, _ -> startActivity(Intent(Intent.ACTION_VIEW, android.net.Uri.parse(apk.optString("url")))) }
                            if (loi.isNotEmpty() && loi != "null") d.setNeutralButton("Mở lại app") { _, _ -> khoiDongLai() }
                            d.setNegativeButton("Đóng", null).show()
                        }
                    } catch (e: Exception) {
                        ui.post { AlertDialog.Builder(this).setTitle("Cập nhật").setMessage("Không nối được kênh cập nhật: ${e.message}\nDùng 'Từ file' nếu Claude đã gửi gói .zip.").setPositiveButton("Đóng", null).show() }
                    }
                }
            }
            .setNeutralButton("Từ file .zip") { _, _ ->
                val i = Intent(Intent.ACTION_OPEN_DOCUMENT); i.addCategory(Intent.CATEGORY_OPENABLE); i.type = "*/*"
                startActivityForResult(i, maZip)
            }
            .setNegativeButton("Đóng", null).show()
    }

    private fun napZip(uri: android.net.Uri) {
        val dich = File(cacheDir, "capnhat.zip")
        contentResolver.openInputStream(uri)?.use { vao -> dich.outputStream().use { vao.copyTo(it) } }
        try {
            val tb = core.callAttr("nap_cap_nhat_zip", dich.absolutePath).toString()
            AlertDialog.Builder(this).setTitle("Cập nhật").setMessage(tb).setPositiveButton("Mở lại app") { _, _ -> khoiDongLai() }.setNegativeButton("Để sau", null).show()
        } catch (e: Exception) {
            AlertDialog.Builder(this).setTitle("Cập nhật").setMessage("Không nạp được: ${e.message}").setPositiveButton("Đóng", null).show()
        }
    }

    private fun khoiDongLai() {
        val i = packageManager.getLaunchIntentForPackage(packageName)!!
        i.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(i)
        finishAffinity()
        android.os.Process.killProcess(android.os.Process.myPid())
    }

    private fun guiFile(f: File, tieuDe: String) {
        val i = Intent(Intent.ACTION_SEND)
        i.type = "application/zip"
        i.putExtra(Intent.EXTRA_STREAM, FileProvider.getUriForFile(this, "vn.vinalite.camlink.files", f))
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        startActivity(Intent.createChooser(i, tieuDe))
    }

    private fun guiKetQua() {
        val fs = core.callAttr("file_ket_qua_moi_nhat").asList().map { File(it.toString()) }
        if (fs.isEmpty()) {
            nhatKy.ghi("Chưa có kết quả nào để gửi.")
            return
        }
        val uris = ArrayList<Uri>(fs.map { FileProvider.getUriForFile(this, "vn.vinalite.camlink.files", it) })
        val i = Intent(Intent.ACTION_SEND_MULTIPLE)
        i.type = "*/*"
        i.putParcelableArrayListExtra(Intent.EXTRA_STREAM, uris)
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        startActivity(Intent.createChooser(i, "Gửi kết quả CamLink"))
    }

    // ================================================================= 2.4: GIAO DIỆN ĐỒ HOẠ (tuỳ chọn)
    // Trang chủ = thẻ trạng thái + 1 nút chính + 2 lối tắt; thanh tab dưới; việc ít dùng nằm ở tab "Thêm".
    // Mọi nút gọi lại ĐÚNG các hàm của giao diện chữ nên logic cài điểm / kiểm tra / LiteMark không đổi.
    private val M_NEN = "#F4F6F9"; private val M_THE = "#FFFFFF"; private val M_VIEN = "#E7ECF1"
    private val M_CHU = "#121C26"; private val M_MO = "#6A7885"; private val M_MO2 = "#9AA7B3"
    private val M_XANH = "#0D8F6F"; private val M_XANH_NEN = "#E5F4EF"; private val M_LAM = "#1667B8"; private val M_DO = "#D14343"

    private fun bo(mau: String, r: Int, vien: String? = null): android.graphics.drawable.GradientDrawable {
        val g = android.graphics.drawable.GradientDrawable()
        g.setColor(Color.parseColor(mau))
        g.cornerRadius = dp(r).toFloat()
        if (vien != null) g.setStroke(dp(1), Color.parseColor(vien))
        return g
    }

    private fun chu(s: CharSequence, co: Float, mau: String, dam: Boolean = false): TextView {
        val t = TextView(this)
        t.text = s
        t.textSize = co
        t.setTextColor(Color.parseColor(mau))
        if (dam) t.setTypeface(null, Typeface.BOLD)
        return t
    }

    private fun lpDoc(tren: Int = 0, duoi: Int = 0): LinearLayout.LayoutParams {
        val lp = LinearLayout.LayoutParams(-1, -2)
        lp.topMargin = dp(tren); lp.bottomMargin = dp(duoi)
        return lp
    }

    /** Đang chạy cài điểm / nhập file thì không cho bấm việc khác (giao diện chữ khoá nút, ở đây báo nhẹ). */
    private fun ban(): Boolean {
        if (dangChay.isEmpty()) return false
        android.widget.Toast.makeText(this, "Đang chạy: $dangChay — chờ xong đã", android.widget.Toast.LENGTH_SHORT).show()
        return true
    }

    /** Một hàng lớn: ô biểu tượng + tên + mô tả + mũi tên. Trả về (hàng, chấm đỏ). */
    private fun hang(bieu: String, ten: String, moTa: String, bam: () -> Unit): Pair<LinearLayout, android.view.View> {
        val h = LinearLayout(this)
        h.orientation = LinearLayout.HORIZONTAL
        h.gravity = android.view.Gravity.CENTER_VERTICAL
        h.background = bo(M_THE, 15, M_VIEN)
        h.setPadding(dp(14), dp(13), dp(14), dp(13))
        val ic = chu(bieu, 20f, M_CHU)
        ic.gravity = android.view.Gravity.CENTER
        ic.background = bo(M_XANH_NEN, 12)
        h.addView(ic, LinearLayout.LayoutParams(dp(42), dp(42)))
        val tx = LinearLayout(this)
        tx.orientation = LinearLayout.VERTICAL
        tx.addView(chu(ten, 15.5f, M_CHU, dam = true))
        if (moTa.isNotEmpty()) tx.addView(chu(moTa, 12.5f, M_MO))
        val lpTx = LinearLayout.LayoutParams(0, -2, 1f)
        lpTx.leftMargin = dp(13)
        h.addView(tx, lpTx)
        val cham = android.view.View(this)
        cham.background = bo(M_DO, 5)
        cham.visibility = android.view.View.GONE
        val lpC = LinearLayout.LayoutParams(dp(9), dp(9))
        lpC.rightMargin = dp(8)
        h.addView(cham, lpC)
        h.addView(chu("›", 22f, M_MO2))
        h.isClickable = true
        h.setOnClickListener { bam() }
        return Pair(h, cham)
    }

    private fun nhan(s: String): TextView {
        val t = chu(s.uppercase(), 11.5f, M_MO2, dam = true)
        t.letterSpacing = 0.06f
        t.setPadding(dp(2), dp(20), 0, dp(9))
        return t
    }

    private fun dauTrang(tieu: String, phu: String): LinearLayout {
        val hd = LinearLayout(this)
        hd.orientation = LinearLayout.HORIZONTAL
        hd.gravity = android.view.Gravity.CENTER_VERTICAL
        val mk = chu("📹", 19f, "#FFFFFF")
        mk.gravity = android.view.Gravity.CENTER
        val g = android.graphics.drawable.GradientDrawable(android.graphics.drawable.GradientDrawable.Orientation.TL_BR,
            intArrayOf(Color.parseColor(M_LAM), Color.parseColor(M_XANH)))
        g.cornerRadius = dp(11).toFloat()
        mk.background = g
        hd.addView(mk, LinearLayout.LayoutParams(dp(40), dp(40)))
        val c = LinearLayout(this)
        c.orientation = LinearLayout.VERTICAL
        c.addView(chu(tieu, 17f, M_CHU, dam = true))
        c.addView(chu(phu, 11.5f, M_MO2))
        val lp = LinearLayout.LayoutParams(0, -2, 1f)
        lp.leftMargin = dp(11)
        hd.addView(c, lp)
        return hd
    }

    private fun dungDoHoa() {
        val pb = packageManager.getPackageInfo(packageName, 0).versionName + " · lõi " + core.callAttr("phien_ban_loi").toString()
        gocDH = LinearLayout(this)
        gocDH.orientation = LinearLayout.VERTICAL
        gocDH.setBackgroundColor(Color.parseColor(M_NEN))
        dhTrang = android.widget.FrameLayout(this)
        gocDH.addView(dhTrang, LinearLayout.LayoutParams(-1, 0, 1f))

        // ---------- Trang chủ
        val c = LinearLayout(this)
        c.orientation = LinearLayout.VERTICAL
        c.setPadding(dp(18), dp(22), dp(18), dp(18))
        c.addView(dauTrang("CamLink", pb), lpDoc(duoi = 18))
        dhThe = LinearLayout(this)
        dhThe.orientation = LinearLayout.VERTICAL
        dhThe.background = bo(M_XANH_NEN, 18, M_VIEN)
        dhThe.setPadding(dp(18), dp(16), dp(18), dp(16))
        c.addView(dhThe, lpDoc(duoi = 14))
        dhTrangThai = chu("", 14.5f, "#FFFFFF", dam = true)
        dhTrangThai.setPadding(dp(14), dp(11), dp(14), dp(11))
        dhTrangThai.visibility = android.view.View.GONE
        dhTrangThai.setOnClickListener { xemNhatKy() }
        c.addView(dhTrangThai, lpDoc(duoi = 14))
        val chinh = chu("▶  Cài điểm này", 18f, "#FFFFFF", dam = true)
        chinh.gravity = android.view.Gravity.CENTER
        chinh.background = bo(M_LAM, 16)
        chinh.setPadding(dp(12), dp(17), dp(12), dp(17))
        chinh.elevation = dp(4).toFloat()
        chinh.setOnClickListener { if (!ban()) batDauChay() }
        c.addView(chinh, lpDoc())
        c.addView(nhan("Chuẩn bị trước khi cài"))
        val da = hang("📁", "Dự án & cấu hình", "") { chonTrang(5) }
        dhMoTaDuAn = (da.first.getChildAt(1) as LinearLayout).let { tx -> val m = chu("", 12.5f, M_MO); tx.addView(m); m }
        c.addView(da.first, lpDoc())
        c.addView(nhan("Việc thường dùng"))
        c.addView(hang("🔍", "Kiểm tra từ xa", "Soát cả dự án · sửa từ xa") { moKiemTra() }.first, lpDoc(duoi = 10))
        val gs = hang("🖥️", "Giám sát trực tiếp", "Xem hình mọi cam") { moGiamSatDH() }
        dhChamGS = gs.second
        c.addView(gs.first, lpDoc(duoi = 10))
        dhChu = ScrollView(this)
        dhChu.addView(c)
        dhTrang.addView(dhChu)

        // ---------- Trang "Thêm"
        val t = LinearLayout(this)
        t.orientation = LinearLayout.VERTICAL
        t.setPadding(dp(18), dp(22), dp(18), dp(18))
        t.addView(dauTrang("Thêm", "Việc ít dùng hơn"), lpDoc())
        fun them(bieu: String, ten: String, moTa: String, khoaKhiChay: Boolean = true, bam: () -> Unit) =
            t.addView(hang(bieu, ten, moTa) { if (!khoaKhiChay || !ban()) bam() }.first, lpDoc(duoi = 10))
        t.addView(nhan("Theo dõi & kết quả"))
        them("📈", "Theo dõi ổn định", "Cam rớt lúc nào, bao lâu", khoaKhiChay = false) { TheoDoi.danhSach(this) }
        them("🧩", "Sơ đồ + ảnh lần gần nhất", "Kết quả lần cài điểm vừa rồi", khoaKhiChay = false) { moSoDoGanNhat() }
        them("📤", "Gửi kết quả", "Zalo, Gmail…", khoaKhiChay = false) { guiKetQua() }
        them("📜", "Nhật ký lần chạy", "Từng bước app đã làm", khoaKhiChay = false) { xemNhatKy() }
        t.addView(nhan("Cài điểm"))
        them("📍", "Chọn điểm bằng tay", "Khi GPS không nhận đúng điểm") { chonDiem(chiKiemTra = false) }
        them("📡", "Thu mẫu thiết bị", "Gặp modem / cam lạ") { thuMau() }
        t.addView(nhan("Dự án & cài đặt"))
        them("📁", "Dự án", "File cấu hình từng dự án", khoaKhiChay = false) { chonTrang(5) }
        them("⚙️", "Cài đặt chung", "User/pass mặc định · tự cài", khoaKhiChay = false) { chonTrang(6) }
        them("⬆️", "Cập nhật", "Lõi vài trăm KB; APK chỉ khi cần") { capNhat() }
        them("📘", "Hướng dẫn sử dụng", "", khoaKhiChay = false) { startActivity(Intent(this, HuongDanActivity::class.java)) }
        them("☰", "Đổi sang giao diện chữ", "Giao diện cũ, đủ mọi nút", khoaKhiChay = false) { datGiaoDien(false) }
        dhThem = ScrollView(this)
        dhThem.addView(t)
        dhThem.visibility = android.view.View.GONE
        dhTrang.addView(dhThem)
        dhDuAn = LinearLayout(this)
        dhDuAn.orientation = LinearLayout.VERTICAL
        dhDuAn.visibility = android.view.View.GONE
        dhTrang.addView(dhDuAn)
        dhCaiDat = ScrollView(this)
        dhCaiDat.visibility = android.view.View.GONE
        dhTrang.addView(dhCaiDat)

        // ---------- Thanh tab dưới
        val vach = android.view.View(this)
        vach.setBackgroundColor(Color.parseColor(M_VIEN))
        gocDH.addView(vach, LinearLayout.LayoutParams(-1, dp(1)))
        val nav = LinearLayout(this)
        nav.orientation = LinearLayout.HORIZONTAL
        nav.setBackgroundColor(Color.parseColor(M_THE))
        fun tab(bieu: String, ten: String, bam: () -> Unit) {
            val b = chu("$bieu\n$ten", 11.5f, M_MO2, dam = true)
            b.gravity = android.view.Gravity.CENTER
            b.setLineSpacing(dp(3).toFloat(), 1f)
            b.setPadding(dp(2), dp(9), dp(2), dp(11))
            b.setOnClickListener { bam() }
            dhTab.add(b)
            nav.addView(b, LinearLayout.LayoutParams(0, -2, 1f))
        }
        tab("🏠", "Trang chủ") { chonTrang(0) }
        tab("🔍", "Kiểm tra") { moKiemTra() }
        tab("🖥️", "Giám sát") { moGiamSatDH() }
        tab("🔐", "Quản trị") { startActivity(Intent(this, QuanTriActivity::class.java)) }
        tab("⋯", "Thêm") { chonTrang(4) }
        gocDH.addView(nav, LinearLayout.LayoutParams(-1, -2))
        chonTrang(0)
    }

    private fun chonTrang(i: Int) {
        dhChu.visibility = if (i == 0) android.view.View.VISIBLE else android.view.View.GONE
        dhThem.visibility = if (i == 4) android.view.View.VISIBLE else android.view.View.GONE
        dhDuAn.visibility = if (i == 5) android.view.View.VISIBLE else android.view.View.GONE
        dhCaiDat.visibility = if (i == 6) android.view.View.VISIBLE else android.view.View.GONE
        if (i == 5) dungTrangDuAn()
        if (i == 6) dungTrangCaiDat()
        dhTab.forEachIndexed { k, b -> b.setTextColor(Color.parseColor(if (k == i) M_XANH else M_MO2)) }
        if (i == 0) lamMoiTrangChu()
    }

    private fun datGiaoDien(dh: Boolean, luu: Boolean = true) {
        doHoa = dh
        if (luu) getSharedPreferences("camlink", MODE_PRIVATE).edit().putBoolean("do_hoa", dh).apply()
        if (dh) { chonTrang(0); setContentView(gocDH) } else setContentView(gocChu)
    }

    private fun moKiemTra() {
        if (ban()) return
        if (sanSang()) startActivity(Intent(this, TuXaActivity::class.java))
    }

    /** Thẻ trạng thái: đọc kết quả kiểm gần nhất đã lưu (không chạm mạng). Chưa có dữ liệu thì chỉ đúng bước cần làm. */
    private fun lamMoiTrangChu() {
        if (!::dhThe.isInitialized) return
        if (dhDuAn.visibility == android.view.View.VISIBLE) dungTrangDuAn()
        if (dhCaiDat.visibility == android.view.View.VISIBLE) dungTrangCaiDat()
        dhMoTaDuAn.text = try {
            val q = org.json.JSONObject(core.callAttr("tom_tat_du_an").toString())
            val n = q.getJSONArray("du_an").length()
            if (n == 0) "Chưa có file cấu hình — bấm để nạp" else "$n dự án · " + (if (q.optBoolean("co_cam_pw")) "user/pass đã lưu" else "chưa nhập pass cam")
        } catch (_: Exception) { "File cấu hình · user/pass mặc định" }
        dhThe.removeAllViews()
        dhThe.setOnClickListener(null)
        dhThe.isClickable = false
        dhChamGS.visibility = android.view.View.GONE
        val coFile = core.callAttr("co_du_lieu").toBoolean()
        val coPass = core.callAttr("co_cai_dat").toBoolean()
        fun buoc(so: String, ten: String, moTa: String, nhanNut: String, bam: () -> Unit) {
            dhThe.addView(chu(so, 12f, M_XANH, dam = true))
            dhThe.addView(chu(ten, 21f, M_CHU, dam = true))
            dhThe.addView(chu(moTa, 13f, M_MO), lpDoc(tren = 2, duoi = 12))
            val n = chu(nhanNut, 14.5f, "#FFFFFF", dam = true)
            n.gravity = android.view.Gravity.CENTER
            n.background = bo(M_XANH, 12)
            n.setPadding(dp(12), dp(11), dp(12), dp(11))
            n.setOnClickListener { if (!ban()) bam() }
            dhThe.addView(n, lpDoc())
        }
        if (!coFile) { buoc("BƯỚC 1 / 2", "Thêm dự án", "Chọn file khảo sát Excel của dự án.", "📁  Chọn file Excel") { moFile() }; return }
        if (!coPass) { buoc("BƯỚC 2 / 2", "Nhập user / pass", "Của cam và modem — nhập một lần, app nhớ.", "🔑  Nhập user / pass") { hopCaiDat() }; return }
        val j = try { org.json.JSONObject(core.callAttr("tong_quan").toString()) } catch (e: Exception) { org.json.JSONObject() }
        val soDa = j.optInt("du_an", core.callAttr("so_du_an").toInt())
        val tong = j.optInt("tong_cam"); val dat = j.optInt("dat"); val loi = j.optInt("diem_loi")
        if (tong == 0) {
            dhThe.addView(chu("Sẵn sàng", 30f, M_XANH, dam = true))
            dhThe.addView(chu("$soDa dự án đang quản lý · chưa kiểm từ xa lần nào", 13f, M_MO), lpDoc(tren = 2))
            dhThe.addView(chu("Tới điểm: vào WiFi modem rồi bấm Cài điểm này.", 13f, M_MO), lpDoc(tren = 8))
            return
        }
        val lon = android.text.SpannableString("$dat/$tong cam đang lên")
        lon.setSpan(android.text.style.ForegroundColorSpan(Color.parseColor(if (dat == tong) M_XANH else M_DO)), 0, dat.toString().length, 0)
        lon.setSpan(android.text.style.RelativeSizeSpan(0.62f), "$dat/$tong".length, lon.length, 0)
        dhThe.addView(chu(lon, 34f, M_CHU, dam = true))
        dhThe.addView(chu("$soDa dự án đang quản lý", 13f, M_MO), lpDoc(tren = 2))
        val h = LinearLayout(this)
        h.orientation = LinearLayout.HORIZONTAL
        fun o(so: String, ten: String, mau: String, nang: Float) {
            val v = LinearLayout(this)
            v.orientation = LinearLayout.VERTICAL
            val s = chu(so, 17f, mau, dam = true)
            s.maxLines = 1; s.ellipsize = android.text.TextUtils.TruncateAt.END
            v.addView(s)
            v.addView(chu(ten, 12f, M_MO))
            h.addView(v, LinearLayout.LayoutParams(0, -2, nang))
        }
        o(loi.toString(), "điểm lỗi", if (loi > 0) M_DO else M_CHU, 1f)
        o(j.optString("gan_nhat").ifEmpty { "—" }, "lần kiểm gần nhất", M_CHU, 3f)
        val dangTd = j.optInt("theo_doi")
        if (dangTd > 0) o(dangTd.toString(), "đang theo dõi", M_CHU, 1.4f)
        dhThe.addView(h, lpDoc(tren = 14))
        dhThe.setOnClickListener { moKiemTra() }
        if (loi > 0) dhChamGS.visibility = android.view.View.VISIBLE
    }

    // ---------------- 2.12: trang Dự án — đầu trang cố định (nút thêm, cài đặt chung, lọc, tìm), danh sách từng dòng gọn
    private var dhLoc = "dang"                          // dang = đang thi công · xong = hoàn thành · tat = tất cả
    private var dhTim = ""
    private val dhMo = mutableSetOf<String>()           // dự án đang bung chi tiết
    private var dhDs: LinearLayout? = null
    private var dhDuLieu = org.json.JSONObject()

    private fun theTrang(): LinearLayout {
        val v = LinearLayout(this)
        v.orientation = LinearLayout.VERTICAL
        v.background = bo(M_THE, 15, M_VIEN)
        v.setPadding(dp(15), dp(13), dp(15), dp(13))
        return v
    }

    private fun dongTrang(v: LinearLayout, ten: String, gia: String, mau: String = M_CHU) {
        val h = LinearLayout(this)
        h.orientation = LinearLayout.HORIZONTAL
        h.addView(chu(ten, 13f, M_MO), LinearLayout.LayoutParams(0, -2, 1f))
        h.addView(chu(gia, 13f, mau, dam = true))
        v.addView(h, lpDoc(tren = 5))
    }

    private fun nutTrang(s: String, mau: String = M_LAM, bam: () -> Unit): TextView {
        val n = chu(s, 14.5f, "#FFFFFF", dam = true)
        n.gravity = android.view.Gravity.CENTER
        n.background = bo(mau, 12)
        n.setPadding(dp(12), dp(12), dp(12), dp(12))
        n.setOnClickListener { if (!ban()) bam() }
        return n
    }

    /** Trang Dự án: phần trên CỐ ĐỊNH không cuộn (＋ Dự án mới · Cài đặt chung · nhãn lọc · ô tìm); bên dưới là danh sách cuộn. */
    private fun dungTrangDuAn() {
        dhDuAn.removeAllViews()
        dhDuLieu = try { org.json.JSONObject(core.callAttr("tom_tat_du_an").toString()) } catch (_: Exception) { org.json.JSONObject() }
        val ds = dhDuLieu.optJSONArray("du_an") ?: org.json.JSONArray()
        var soDang = 0; var soXong = 0
        for (i in 0 until ds.length()) if (ds.getJSONObject(i).optBoolean("hoan_thanh")) soXong++ else soDang++
        val nhieu = ds.length() > 8      // ít dự án: một danh sách hai nhóm, không cần nhãn lọc / ô tìm
        if (!nhieu || (dhLoc == "dang" && soDang == 0 && soXong > 0)) dhLoc = "tat"

        val dau = LinearLayout(this)
        dau.orientation = LinearLayout.VERTICAL
        dau.setPadding(dp(18), dp(22), dp(18), dp(6))
        // tiêu đề + nút thêm dự án (luôn thấy, không bị danh sách đẩy đi)
        val h = LinearLayout(this)
        h.orientation = LinearLayout.HORIZONTAL
        h.gravity = android.view.Gravity.CENTER_VERTICAL
        val tieu = LinearLayout(this); tieu.orientation = LinearLayout.VERTICAL
        tieu.addView(chu("Dự án", 20f, M_CHU, dam = true))
        tieu.addView(chu("${ds.length()} dự án · $soDang đang làm · $soXong hoàn thành", 12f, M_MO2))
        h.addView(tieu, LinearLayout.LayoutParams(0, -2, 1f))
        val them = chu("＋ Thêm dự án", 14f, "#FFFFFF", dam = true)
        them.background = bo(M_LAM, 20)
        them.setPadding(dp(14), dp(10), dp(14), dp(10))
        them.setOnClickListener {
            if (!ban()) AlertDialog.Builder(this).setTitle("Thêm dự án từ đâu?")
                .setItems(arrayOf("📁  Từ file Excel khảo sát", "🔗  Nhận từ LiteMark")) { _, i ->
                    if (i == 0) moFile() else startActivity(Intent(this, TuXaActivity::class.java))
                }.setNegativeButton("Đóng", null).show()
        }
        h.addView(them)
        dau.addView(h, lpDoc(duoi = 10))
        // cài đặt chung: user/pass mặc định + tự cài (tách khỏi danh sách)
        val cd = hang("⚙️", "Cài đặt chung",
            "Cam ${dhDuLieu.optString("cam_user", "admin")}" + (if (dhDuLieu.optBoolean("co_cam_pw")) "" else " (CHƯA có pass)") +
            " · WiFi ${dhDuLieu.optString("wifi_ten").ifEmpty { "chưa nhập" }} · Tự cài ${if (batTuDong()) "bật" else "tắt"}") { chonTrang(6) }
        if (!dhDuLieu.optBoolean("co_cam_pw")) cd.second.visibility = android.view.View.VISIBLE
        dau.addView(cd.first, lpDoc(duoi = 10))
        if (nhieu) {      // nhiều dự án mới cần nhãn lọc + ô tìm
            val loc = LinearLayout(this)
            loc.orientation = LinearLayout.HORIZONTAL
            fun nhanLoc(ma: String, ten: String) {
                val chon = dhLoc == ma
                val t = chu(ten, 13f, if (chon) "#FFFFFF" else M_MO, dam = true)
                t.gravity = android.view.Gravity.CENTER
                t.background = bo(if (chon) M_XANH else M_THE, 18, if (chon) null else M_VIEN)
                t.setPadding(dp(10), dp(8), dp(10), dp(8))
                t.setOnClickListener { dhLoc = ma; dungTrangDuAn() }
                val lp = LinearLayout.LayoutParams(0, -2, 1f); lp.rightMargin = dp(6)
                loc.addView(t, lp)
            }
            nhanLoc("tat", "Tất cả · ${ds.length()}")
            nhanLoc("dang", "Đang làm · $soDang")
            nhanLoc("xong", "Hoàn thành · $soXong")
            dau.addView(loc, lpDoc(duoi = 8))
            val o = EditText(this)
            o.hint = "🔎 Tìm theo tên dự án"
            o.setText(dhTim)
            o.textSize = 14f
            o.setSingleLine(true)
            o.background = bo(M_THE, 12, M_VIEN)
            o.setPadding(dp(12), dp(9), dp(12), dp(9))
            o.addTextChangedListener(object : android.text.TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
                override fun afterTextChanged(s: android.text.Editable?) { dhTim = s?.toString() ?: ""; veDsDuAn() }      // chỉ vẽ lại danh sách, giữ con trỏ ô tìm
            })
            dau.addView(o, lpDoc(duoi = 6))
        } else dhTim = ""
        dhDuAn.addView(dau)

        val cuon = ScrollView(this)
        val l = LinearLayout(this)
        l.orientation = LinearLayout.VERTICAL
        l.setPadding(dp(18), dp(2), dp(18), dp(18))
        cuon.addView(l)
        dhDs = l
        dhDuAn.addView(cuon, LinearLayout.LayoutParams(-1, 0, 1f))
        veDsDuAn()
    }

    private fun khongDau(x: String) = java.text.Normalizer.normalize(x.lowercase(), java.text.Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "").replace('đ', 'd')

    /** Danh sách dự án: hai nhóm (Đang làm · Hoàn thành); mỗi dự án MỘT DÒNG ghi trạng thái theo VIỆC CẦN LÀM; bấm dòng bung chi tiết + nút việc tiếp theo. */
    private fun veDsDuAn() {
        val l = dhDs ?: return
        l.removeAllViews()
        val ds = dhDuLieu.optJSONArray("du_an") ?: org.json.JSONArray()
        if (ds.length() == 0) {
            val v = theTrang()
            v.addView(chu("Chưa có dự án nào", 15.5f, M_CHU, dam = true))
            v.addView(chu("Bấm ＋ Thêm dự án: nạp file Excel khảo sát (mỗi dòng một điểm, gồm các cột No · Tên điểm · link bản đồ · Camera · Domain · USER · PW), hoặc nhận dự án từ LiteMark.", 13f, M_MO), lpDoc(tren = 4))
            l.addView(v)
            return
        }
        val tim = khongDau(dhTim.trim())
        val dang = ArrayList<org.json.JSONObject>(); val xongDs = ArrayList<org.json.JSONObject>()
        for (i in 0 until ds.length()) {
            val d = ds.getJSONObject(i)
            if (tim.isNotEmpty() && !khongDau(d.optString("ten")).contains(tim)) continue
            if (d.optBoolean("hoan_thanh")) xongDs.add(d) else dang.add(d)
        }
        var dem = 0
        if (dhLoc != "xong" && dang.isNotEmpty()) { l.addView(nhan("Đang làm · ${dang.size}")); dang.forEach { l.addView(dongDuAn(it), lpDoc(duoi = 8)); dem++ } }
        if (dhLoc != "dang" && xongDs.isNotEmpty()) { l.addView(nhan("Hoàn thành · ${xongDs.size}")); xongDs.forEach { l.addView(dongDuAn(it), lpDoc(duoi = 8)); dem++ } }
        if (dem == 0) l.addView(chu(when {
            tim.isNotEmpty() -> "Không có dự án nào khớp «${dhTim.trim()}»."
            dhLoc == "dang" -> "Không có dự án nào đang làm."
            else -> "Chưa có dự án nào hoàn thành."
        }, 13.5f, M_MO), lpDoc(tren = 10))
    }

    private fun dongDuAn(d: org.json.JSONObject): LinearLayout {
        val ma = d.optString("ma"); val n = d.optInt("diem")
        val xong = d.optBoolean("hoan_thanh")
        val daCai = d.optInt("da_xong")
        val thieuTM = n - d.optInt("ten_mien")
        val camKiem = d.optInt("cam_kiem"); val camLen = d.optInt("cam_len")
        val luc = d.optString("luc_kiem").substringAfter(" ", "").ifEmpty { d.optString("luc_kiem") }      // chỉ lấy giờ
        // trạng thái = việc cần làm
        val (tt, mauTt) = when {
            xong && camKiem > 0 && camLen == camKiem -> Pair("✔ Hoàn thành · $camLen/$camKiem cam đang lên (kiểm $luc)", M_XANH)
            xong && camKiem > 0 -> Pair("Hoàn thành · ${camKiem - camLen} cam lỗi (kiểm $luc)", M_DO)
            xong -> Pair("✔ Hoàn thành · chưa kiểm tra từ xa", M_XANH)
            thieuTM > 0 -> Pair("Thiếu tên miền $thieuTM/$n điểm" + (if (daCai > 0) " · đã cài $daCai/$n" else ""), M_DO)
            daCai == 0 -> Pair("Sẵn sàng cài · 0/$n điểm", M_LAM)
            else -> Pair("Đang cài · $daCai/$n điểm", M_LAM)
        }
        val soCam = if (d.optInt("cam") > 0) "${d.optInt("cam")} cam" else "chưa có số cam"
        val mo = ma in dhMo
        val v = LinearLayout(this)
        v.orientation = LinearLayout.VERTICAL
        v.background = bo(M_THE, 13, M_VIEN)
        v.setPadding(dp(14), dp(11), dp(12), dp(11))
        val h = LinearLayout(this)
        h.orientation = LinearLayout.HORIZONTAL
        h.gravity = android.view.Gravity.CENTER_VERTICAL
        val tx = LinearLayout(this); tx.orientation = LinearLayout.VERTICAL
        val ten = chu(d.optString("ten"), 15f, M_CHU, dam = true)
        ten.maxLines = 1; ten.ellipsize = android.text.TextUtils.TruncateAt.END
        tx.addView(ten)
        tx.addView(chu(tt, 13f, mauTt, dam = true))
        tx.addView(chu("$n điểm · $soCam", 12f, M_MO2))
        h.addView(tx, LinearLayout.LayoutParams(0, -2, 1f))
        h.addView(chu(if (mo) "▾" else "›", 20f, M_MO2))
        v.addView(h)
        if (mo) {
            fun du(k: String) = "${d.optInt(k)}/$n"
            fun mau(k: String) = if (d.optInt(k) == n) M_XANH else M_DO
            dongTrang(v, "Đã cài", "$daCai/$n", if (daCai == n) M_XANH else M_CHU)
            dongTrang(v, "Toạ độ (GPS tự dò điểm)", du("toa_do"), mau("toa_do"))
            dongTrang(v, "Tên miền DDNS", du("ten_mien"), mau("ten_mien"))
            dongTrang(v, "User/pass DDNS kèm tên miền", du("tk_ddns"), mau("tk_ddns"))
            if (d.optInt("toa_do") < n) v.addView(chu("Điểm thiếu toạ độ: tới nơi app sẽ hỏi chọn điểm bằng tay.", 12f, M_MO), lpDoc(tren = 6))
            if (d.optInt("rieng") > 0) v.addView(chu("${d.optInt("rieng")} điểm đang dùng user/pass riêng (khác mặc định).", 12f, M_MO), lpDoc(tren = 4))
            // nút đúng việc tiếp theo
            fun viec(s: String, mau: String, bam: () -> Unit) {
                val b = chu(s, 14f, "#FFFFFF", dam = true)
                b.gravity = android.view.Gravity.CENTER
                b.background = bo(mau, 11)
                b.setPadding(dp(10), dp(10), dp(10), dp(10))
                b.setOnClickListener { if (!ban()) bam() }
                v.addView(b, lpDoc(tren = 8))
            }
            val tuLm = d.optBoolean("tu_litemark")
            if (thieuTM > 0 && tuLm) viec("📄  Nạp file tên miền của bên cấp", M_LAM) { choDdns = arrayOf(ma, "", "-1", ""); moFileDdns() }
            if (!tuLm) viec("📁  Cập nhật file Excel của dự án", if (xong) M_MO else M_LAM) { moFile() }
            if (daCai > 0) viec("🔍  Mở kiểm tra từ xa dự án này", M_XANH) { startActivity(Intent(this, TuXaActivity::class.java).putExtra("ma", ma)) }
            if (thieuTM > 0 && !tuLm) v.addView(chu("Điểm thiếu tên miền: bổ sung cột Domain trong file Excel rồi cập nhật.", 12f, M_MO), lpDoc(tren = 6))
        }
        v.isClickable = true
        v.setOnClickListener { if (mo) dhMo.remove(ma) else dhMo.add(ma); veDsDuAn() }
        return v
    }

    /** Trang Cài đặt chung: user/pass mặc định + tự cài (tách khỏi danh sách dự án). */
    private fun dungTrangCaiDat() {
        dhCaiDat.removeAllViews()
        val q = try { org.json.JSONObject(core.callAttr("tom_tat_du_an").toString()) } catch (_: Exception) { org.json.JSONObject() }
        val t = LinearLayout(this)
        t.orientation = LinearLayout.VERTICAL
        t.setPadding(dp(18), dp(22), dp(18), dp(18))
        val ve = chu("‹ Dự án", 14f, M_LAM, dam = true)
        ve.setPadding(0, 0, 0, dp(10))
        ve.setOnClickListener { chonTrang(5) }
        t.addView(ve)
        t.addView(dauTrang("Cài đặt chung", "Dùng cho mọi dự án, nhập một lần"), lpDoc())
        t.addView(nhan("User / pass mặc định"))
        val v = theTrang()
        dongTrang(v, "Cam", q.optString("cam_user", "admin") + " / " + (if (q.optBoolean("co_cam_pw")) "••••••" else "CHƯA NHẬP"), if (q.optBoolean("co_cam_pw")) M_CHU else M_DO)
        dongTrang(v, "Modem", q.optString("modem_user", "admin") + " / " + (if (q.optBoolean("modem_mac_dinh", true)) "admin (mặc định)" else "••••••"))
        dongTrang(v, "DDNS", "theo từng dòng trong file")
        dongTrang(v, "WiFi modem", q.optString("wifi_ten").ifEmpty { "chưa nhập — vào WiFi bằng tay" }, if (q.optString("wifi_ten").isEmpty()) M_MO else M_CHU)
        v.addView(chu("Điểm nào thực tế khác thì nhập riêng tại điểm — app ưu tiên phần nhập riêng, mặc định giữ nguyên.", 12f, M_MO), lpDoc(tren = 6))
        v.isClickable = true
        v.setOnClickListener { if (!ban()) hopCaiDat() }
        t.addView(v, lpDoc(duoi = 10))
        t.addView(nutTrang("🔑  Sửa user / pass cam · modem · WiFi") { hopCaiDat() }, lpDoc())
        t.addView(nhan("Tới điểm"))
        val c = theTrang()
        val bat = batTuDong()
        c.addView(chu(if (bat) "Tự cài khi vào WiFi modem: ĐANG BẬT" else "Tự cài khi vào WiFi modem: ĐANG TẮT", 14f, if (bat) M_XANH else M_MO, dam = true))
        c.addView(chu(if (bat) (if (q.optString("wifi_ten").isEmpty()) "" else "Đã nhập WiFi dùng chung: tới điểm chỉ cần mở app, app tự vào WiFi modem. ") +
                "App lấy GPS, dò điểm trong file, đếm ngược 8 giây rồi tự cài cam và mở port modem. Điểm đã cài hoặc đang chạy thì KHÔNG cài lại, chỉ báo đã cài và mở hình. Không khớp chắc một điểm (xa quá 150 m, hai điểm sát nhau, thiếu tên miền) thì app đứng yên, bấm Cài điểm này."
            else "Vào WiFi modem của điểm → về Trang chủ bấm Cài điểm này. App lấy GPS, dò điểm trong file rồi cài.", 13f, M_MO), lpDoc(tren = 4))
        t.addView(c, lpDoc(duoi = 10))
        t.addView(nutTrang(if (bat) "Tắt tự cài" else "Bật tự cài", if (bat) M_MO else M_XANH) {
            getSharedPreferences("camlink", MODE_PRIVATE).edit().putBoolean("tu_dong", !bat).apply()
            dungTrangCaiDat()
        }, lpDoc())
        dhCaiDat.addView(t)
    }

    /** Giám sát trực tiếp dùng kết quả kiểm gần nhất của dự án (đúng như nút trong màn Kiểm tra từ xa). */
    private fun moGiamSatDH() {
        if (ban() || !sanSang()) return
        val ds = core.callAttr("ds_du_an").asList().map { r -> r.asList().map { it.toString() } }
        val co = ds.map { Pair(it, core.callAttr("tuxa_gan_nhat", it[0]).toString()) }.filter { it.second.isNotEmpty() }
        fun mo(ma: String, kq: String) {
            maGiamSatDangMo = ma
            val f = File(cacheDir, "giamsat.json")
            f.writeText(kq)
            startActivityForResult(Intent(this, GiamSatActivity::class.java).putExtra("file", f.absolutePath).putExtra("ma", ma), maGiamSatDH)
        }
        when {
            co.isEmpty() -> AlertDialog.Builder(this)
                .setTitle("Chưa có kết quả kiểm")
                .setMessage("Giám sát trực tiếp cần danh sách cam từ một lần Kiểm tra từ xa. Kiểm một lần rồi vào lại.")
                .setPositiveButton("Kiểm tra từ xa") { _, _ -> moKiemTra() }
                .setNegativeButton("Đóng", null).show()
            co.size == 1 -> mo(co[0].first[0], co[0].second)
            else -> AlertDialog.Builder(this)
                .setTitle("Giám sát dự án nào?")
                .setItems(co.map { it.first[1] }.toTypedArray()) { _, i -> mo(co[i].first[0], co[i].second) }
                .show()
        }
    }

    private fun xemNhatKy() {
        val tv = TextView(this)
        tv.text = if (log.text.isEmpty()) "Chưa có gì — nhật ký hiện khi chạy cài điểm, nhập dự án, cập nhật…" else log.text
        tv.typeface = Typeface.MONOSPACE
        tv.textSize = 12f
        tv.setTextIsSelectable(true)
        tv.setPadding(dp(16), dp(12), dp(16), dp(12))
        val sv = ScrollView(this)
        sv.addView(tv)
        AlertDialog.Builder(this).setTitle("Nhật ký").setView(sv).setPositiveButton("Đóng", null).show()
        sv.post { sv.fullScroll(ScrollView.FOCUS_DOWN) }
    }

    override fun onPause() {
        super.onPause()
        dangHien = false
    }

    override fun onResume() {
        super.onResume()
        dangHien = true
        if (!coQuyenViTri() && batTuDong() && core.callAttr("co_du_lieu").toBoolean() && !daXinViTri) {
            daXinViTri = true      // xin quyền vị trí một lần để tự dò điểm; từ chối thì vẫn bấm tay được
            requestPermissions(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION), maViTriTuDong)
        }
        ui.postDelayed({ xetTuDong() }, 800)
        if (::dhThe.isInitialized && doHoa) lamMoiTrangChu()
    }

    @Deprecated("")
    override fun onBackPressed() {
        if (doHoa && ::dhCaiDat.isInitialized && dhCaiDat.visibility == android.view.View.VISIBLE) { chonTrang(5); return }
        if (doHoa && ::dhThem.isInitialized && (dhThem.visibility == android.view.View.VISIBLE || dhDuAn.visibility == android.view.View.VISIBLE)) { chonTrang(0); return }
        @Suppress("DEPRECATION") super.onBackPressed()
    }
}
