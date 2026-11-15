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
    private lateinit var dhChamGS: android.view.View
    private val dhTab = mutableListOf<TextView>()
    private var doHoa = false
    private val maGiamSatDH = 42
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
        AlertDialog.Builder(this)
            .setTitle("$nhan\n$viec")
            .setMessage(kq[1])
            .setPositiveButton("Gửi kết quả") { _, _ -> guiKetQua() }
            .setNegativeButton("Đóng", null)
            .show()
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
            if (resultCode == RESULT_OK && data != null) moKiemTra()
            return
        }
        val uri: Uri = data?.data ?: return
        if (requestCode == maZip && resultCode == RESULT_OK) { napZip(uri); return }
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
    private fun hopCaiDat() {
        val cu = core.callAttr("lay_cai_dat").asList().map { it.toString() }
        val hop = LinearLayout(this)
        hop.orientation = LinearLayout.VERTICAL
        hop.setPadding(dp(20), dp(8), dp(20), 0)
        val nhan = listOf("User cam", "Pass cam", "User modem", "Pass modem")
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
            e.hint = "Nhập $n"
            e.setText(cu.getOrElse(i) { "" })
            e.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
            dong.addView(e, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f))
            hop.addView(dong)
            e
        }
        AlertDialog.Builder(this)
            .setTitle("Nhập một lần, app nhớ cho mọi dự án")
            .setView(hop)
            .setPositiveButton("Lưu") { _, _ ->
                core.callAttr("luu_cai_dat", o[0].text.toString(), o[1].text.toString(),
                    o[2].text.toString(), o[3].text.toString())
                nhatKy.ghi("✔ Đã lưu user/pass.")
                capNhatTieuDe()
            }
            .setNegativeButton("Huỷ", null)
            .show()
    }

    // ---------------- Chạy ----------------
    private fun sanSang(): Boolean {
        if (!core.callAttr("co_du_lieu").toBoolean()) { moFile(); return false }
        if (!core.callAttr("co_cai_dat").toBoolean()) { hopCaiDat(); return false }
        return true
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
        if (!can) { xacNhanCaiThat(ma, stt, m, canhBao); return }
        val ds = org.json.JSONArray(core.callAttr("ung_vien_ten_mien", ma, stt).toString())
        if (ds.length() == 0) {
            AlertDialog.Builder(this).setTitle("Điểm này chưa có tên miền")
                .setMessage("Kho tên miền của bên cấp đã dùng hết. Vẫn cài cam, mở port; DDNS để trống chờ bên cấp tên miền.")
                .setPositiveButton("Tiếp tục cài") { _, _ -> xacNhanCaiThat(ma, stt, m, canhBao) }.setNegativeButton("Huỷ", null).show()
            return
        }
        val ten = core.callAttr("ten_diem", ma, stt).toString()
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

    /** Bảng kiểm tra trước khi cài: chế độ, điểm, mạng WiFi, việc sẽ làm. */
    private fun xacNhanCaiThat(ma: String, stt: String, m: Int, canhBao: String?) {
        val (may, gw) = mangWifi()
        val ten = core.callAttr("ten_diem", ma, stt).toString()
        val viTri = when {
            m >= 0 -> "Cách điểm: $m m"
            else -> "Vị trí: không rõ (không có GPS)"
        }
        val mang = if (may.isEmpty()) "WiFi: CHƯA VÀO WiFi nào" else "WiFi: máy $may · modem $gw"
        val noiDung = StringBuilder()
            .append("CHẾ ĐỘ: CÀI TẠI CHỖ\n").append(ten).append("\n").append(viTri).append("\n").append(mang).append("\n\n")
            .append("App sẽ: tìm cam trong mạng này → đặt port, IP, DDNS (cam nào đã đúng thì giữ nguyên) → mở port trên modem → kiểm tra tên miền.\n")
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
        val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val d = wm.dhcpInfo
        fun ip(v: Int) = if (v == 0) "" else "${v and 255}.${v shr 8 and 255}.${v shr 16 and 255}.${v shr 24 and 255}"
        return Pair(ip(d.ipAddress), ip(d.gateway))
    }

    /** Ép mọi kết nối của app đi qua WiFi modem (kể cả khi modem chưa có Internet). */
    private fun ganWifi(bat: Boolean) {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        if (!bat) { cm.bindProcessToNetwork(null); return }
        val wifi = cm.allNetworks.firstOrNull { n ->
            cm.getNetworkCapabilities(n)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
        }
        cm.bindProcessToNetwork(wifi)
    }

    private fun chayDiem(ma: String, stt: String, ten: String) {
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

    private fun thuMau() {
        val (may, gw) = mangWifi()
        if (may.isEmpty()) {
            nhatKy.ghi("✖ Điện thoại chưa vào WiFi của modem.")
            return
        }
        log.text = ""
        chayNen("Thu mẫu thiết bị trong WiFi $gw (chỉ đọc)", coTomTat = false) {
            ganWifi(true)
            val zp = try {
                core.callAttr("thu_mau", may, gw, nhatKy)?.toString() ?: ""
            } finally {
                ganWifi(false)
            }
            if (zp.isNotEmpty() && File(zp).exists()) ui.post { guiFile(File(zp), "Gửi file mẫu thiết bị cho Claude") }
            null
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
        them("📁", "Thêm / cập nhật dự án", "File khảo sát Excel") { moFile() }
        them("🔑", "User / pass cam và modem", "Nhập một lần cho mọi dự án") { hopCaiDat() }
        them("⬆️", "Cập nhật", "Lõi vài trăm KB; APK chỉ khi cần") { capNhat() }
        them("📘", "Hướng dẫn sử dụng", "", khoaKhiChay = false) { startActivity(Intent(this, HuongDanActivity::class.java)) }
        them("☰", "Đổi sang giao diện chữ", "Giao diện cũ, đủ mọi nút", khoaKhiChay = false) { datGiaoDien(false) }
        dhThem = ScrollView(this)
        dhThem.addView(t)
        dhThem.visibility = android.view.View.GONE
        dhTrang.addView(dhThem)

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

    /** Giám sát trực tiếp dùng kết quả kiểm gần nhất của dự án (đúng như nút trong màn Kiểm tra từ xa). */
    private fun moGiamSatDH() {
        if (ban() || !sanSang()) return
        val ds = core.callAttr("ds_du_an").asList().map { r -> r.asList().map { it.toString() } }
        val co = ds.map { Pair(it, core.callAttr("tuxa_gan_nhat", it[0]).toString()) }.filter { it.second.isNotEmpty() }
        fun mo(ma: String, kq: String) {
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

    override fun onResume() {
        super.onResume()
        if (::dhThe.isInitialized && doHoa) lamMoiTrangChu()
    }

    @Deprecated("")
    override fun onBackPressed() {
        if (doHoa && ::dhThem.isInitialized && dhThem.visibility == android.view.View.VISIBLE) { chonTrang(0); return }
        @Suppress("DEPRECATION") super.onBackPressed()
    }
}
