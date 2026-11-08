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

class MainActivity : Activity() {
    private lateinit var core: PyObject
    private lateinit var log: TextView
    private lateinit var cuon: ScrollView
    private lateinit var tieuDe: TextView
    private val cacNut = mutableListOf<Button>()
    private val ui = Handler(Looper.getMainLooper())
    private val maFile = 11
    private val maViTri = 12

    /** Python gọi nhatKy.ghi("...") để in nhật ký lên màn hình. */
    inner class NhatKy {
        fun ghi(s: String) {
            ui.post {
                log.append(s + "\n")
                cuon.post { cuon.fullScroll(ScrollView.FOCUS_DOWN) }
            }
        }
    }

    private val nhatKy = NhatKy()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        core = Python.getInstance().getModule("camlink_core")
        core.callAttr("khoi_tao", filesDir.absolutePath)
        dungGiaoDien()
        capNhatTieuDe()
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun nut(chu: String, chinh: Boolean = false, bam: () -> Unit): Button {
        val b = Button(this)
        b.text = chu
        b.isAllCaps = false
        b.textSize = if (chinh) 20f else 16f
        if (chinh) {
            b.setBackgroundColor(Color.parseColor("#0F5D8C"))
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
        goc.setPadding(dp(16), dp(24), dp(16), dp(16))

        val ten = TextView(this)
        ten.text = "CamLink"
        ten.textSize = 26f
        ten.setTypeface(null, Typeface.BOLD)
        goc.addView(ten)

        tieuDe = TextView(this)
        tieuDe.textSize = 14f
        tieuDe.setPadding(0, dp(4), 0, dp(12))
        goc.addView(tieuDe)

        goc.addView(nut("CHẠY CÀI ĐIỂM NÀY", chinh = true) { batDauChay() })
        goc.addView(nut("Chọn điểm bằng tay") { chonDiemTay() })
        goc.addView(nut("Gửi kết quả (Zalo, Gmail…)") { guiKetQua() })
        goc.addView(nut("Nhập file khảo sát (Excel)") { moFile() })
        goc.addView(nut("User / pass cam và modem") { hopCaiDat() })
        goc.addView(nut("Thu mẫu thiết bị") { thuMau() })

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
        lp.topMargin = dp(12)
        goc.addView(cuon, lp)
        setContentView(goc)
    }

    private fun capNhatTieuDe() {
        val coFile = core.callAttr("co_du_lieu").toBoolean()
        val coPass = core.callAttr("co_cai_dat").toBoolean()
        tieuDe.text = when {
            !coFile -> "Bước 1: bấm \"Nhập file khảo sát (Excel)\"."
            !coPass -> "Bước 2: bấm \"User / pass cam và modem\" (nhập một lần)."
            else -> "Sẵn sàng. Tới điểm: vào WiFi modem rồi bấm CHẠY."
        }
    }

    private fun khoaNut(khoa: Boolean) = ui.post { cacNut.forEach { it.isEnabled = !khoa } }

    private fun chayNen(viec: () -> Unit) {
        khoaNut(true)
        thread {
            try {
                viec()
            } catch (e: Exception) {
                nhatKy.ghi("LỖI: " + (e.message ?: e.toString()))
            } finally {
                khoaNut(false)
                ui.post { capNhatTieuDe() }
            }
        }
    }

    // ---------------- Nhập file khảo sát ----------------
    private fun moFile() {
        val i = Intent(Intent.ACTION_OPEN_DOCUMENT)
        i.addCategory(Intent.CATEGORY_OPENABLE)
        i.type = "*/*"
        startActivityForResult(i, maFile)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        val uri: Uri = data?.data ?: return
        if (requestCode != maFile || resultCode != RESULT_OK) return
        val dich = File(cacheDir, "khao_sat.xlsx")
        contentResolver.openInputStream(uri)?.use { vao -> dich.outputStream().use { vao.copyTo(it) } }
        log.text = ""
        chayNen {
            val kq = core.callAttr("nhap_excel", dich.absolutePath, nhatKy).toString()
            nhatKy.ghi("Đã nhập file khảo sát: $kq")
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
            val e = EditText(this)
            e.hint = n
            e.setText(cu.getOrElse(i) { "" })
            e.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
            hop.addView(e)
            e
        }
        AlertDialog.Builder(this)
            .setTitle("Nhập một lần, app nhớ cho các điểm sau")
            .setView(hop)
            .setPositiveButton("Lưu") { _, _ ->
                core.callAttr("luu_cai_dat", o[0].text.toString(), o[1].text.toString(),
                    o[2].text.toString(), o[3].text.toString())
                nhatKy.ghi("Đã lưu user/pass.")
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

    private fun batDauChay() {
        if (!sanSang()) return
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION), maViTri)
            return
        }
        log.text = ""
        nhatKy.ghi("Đang lấy vị trí GPS ...")
        layViTri { vt ->
            if (vt == null) {
                nhatKy.ghi("Không lấy được GPS — chọn điểm bằng tay.")
                chonDiemTay()
                return@layViTri
            }
            val gan = core.callAttr("diem_gan", vt.latitude, vt.longitude)
            if (gan == null || gan.toString() == "None") {
                nhatKy.ghi("File khảo sát không có toạ độ — chọn điểm bằng tay.")
                chonDiemTay()
                return@layViTri
            }
            val g = gan.asList()
            val m = g[2].toInt()
            if (m > 400) {
                nhatKy.ghi("Điểm gần nhất (${g[0]}) cách $m m — chọn điểm bằng tay.")
                chonDiemTay()
            } else {
                nhatKy.ghi("→ Đang ở điểm ${g[0]}: ${g[1]} (cách $m m)")
                chayDiem(g[0].toString())
            }
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == maViTri) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) batDauChay() else chonDiemTay()
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

    private fun chonDiemTay() {
        if (!sanSang()) return
        val ds = core.callAttr("danh_sach").asList().map { it.toString() }.toTypedArray()
        AlertDialog.Builder(this)
            .setTitle("Đang ở điểm nào?")
            .setItems(ds) { _, i -> chayDiem(core.callAttr("khoa_theo_so_thu_tu", i).toString()) }
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
    private fun gan_wifi(bat: Boolean) {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        if (!bat) { cm.bindProcessToNetwork(null); return }
        val wifi = cm.allNetworks.firstOrNull { n ->
            cm.getNetworkCapabilities(n)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
        }
        cm.bindProcessToNetwork(wifi)
    }

    private fun chayDiem(stt: String) {
        val (may, gw) = mangWifi()
        if (may.isEmpty()) {
            nhatKy.ghi("✖ Điện thoại chưa vào WiFi của modem. Vào WiFi modem ở điểm này rồi bấm lại.")
            return
        }
        val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val khoa = wm.createMulticastLock("camlink")
        chayNen {
            khoa.acquire()
            gan_wifi(true)
            try {
                core.callAttr("chay", stt, may, gw, nhatKy)
            } finally {
                gan_wifi(false)
                khoa.release()
            }
        }
    }

    private fun thuMau() {
        val (may, gw) = mangWifi()
        if (may.isEmpty()) {
            nhatKy.ghi("✖ Điện thoại chưa vào WiFi của modem.")
            return
        }
        log.text = ""
        chayNen {
            gan_wifi(true)
            try {
                core.callAttr("thu_mau", may, gw, nhatKy)
            } finally {
                gan_wifi(false)
            }
        }
    }

    // ---------------- Gửi kết quả ----------------
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
}
