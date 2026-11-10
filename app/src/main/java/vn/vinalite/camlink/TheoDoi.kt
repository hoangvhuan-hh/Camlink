package vn.vinalite.camlink

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.widget.EditText
import android.widget.Toast
import androidx.core.content.FileProvider
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import kotlin.concurrent.thread

/** THEO DÕI ỔN ĐỊNH THEO ĐIỂM — giao diện dùng chung (màn Kiểm tra từ xa + màn giám sát). */
object TheoDoi {
    private fun core() = Python.getInstance().getModule("camlink_core")

    fun ds(): JSONArray = try { JSONArray(core().callAttr("theodoi_ds").toString()) } catch (_: Exception) { JSONArray() }

    private fun dangTheoDoiDiem(domain: String): JSONObject? {
        val d = ds()
        for (i in 0 until d.length()) {
            val m = d.getJSONObject(i)
            if (m.optString("trang_thai") == "dang" && m.optString("domain") == domain) return m
        }
        return null
    }

    /** Nút "📈 Theo dõi": theo dõi CẢ ĐIỂM (mọi cam, chung một lượt đo, chung một báo cáo). Đang theo dõi → xem / dừng lấy báo cáo. */
    fun diem(act: Activity, ma: String, p: JSONObject, tenDuAn: String) {
        val dang = dangTheoDoiDiem(p.optString("domain"))
        if (dang != null) {
            val ct = dang.optJSONArray("chi_tiet") ?: JSONArray()
            val tung = (0 until ct.length()).joinToString("\n") { i -> val x = ct.getJSONObject(i)
                "• Cam ${x.optInt("so")}: rớt ${x.optInt("so_rot")} lần" + if (x.optBoolean("dang_rot")) " — ĐANG RỚT" else "" }
            AlertDialog.Builder(act).setTitle("Đang theo dõi điểm ${p.optString("stt")}")
                .setMessage("$tung\n\nTổng rớt ${dang.optDouble("phut_rot")} phút. Còn ${dang.optInt("con_phut")} phút thì tự ra báo cáo PDF.")
                .setPositiveButton("Dừng & lấy báo cáo") { _, _ -> dung(act, dang.optString("id")) }
                .setNegativeButton("Đóng", null).show()
            return
        }
        val so = (p.optJSONArray("cam") ?: JSONArray()).length()
        chonThoiGian(act, "Theo dõi điểm ${p.optString("stt")} · cả $so cam (${p.optString("domain")})") { phut -> batDiem(act, ma, p, phut, tenDuAn) }
    }

    private fun chonThoiGian(act: Activity, tieuDe: String, xong: (Double) -> Unit) {
        val chon = arrayOf("2 giờ", "6 giờ", "24 giờ", "Tuỳ chọn (nhập số giờ)")
        AlertDialog.Builder(act).setTitle(tieuDe).setItems(chon) { _, i ->
            when (i) {
                0 -> xong(120.0); 1 -> xong(360.0); 2 -> xong(1440.0)
                else -> {
                    val o = EditText(act); o.hint = "Số giờ, vd 12"; o.inputType = android.text.InputType.TYPE_CLASS_NUMBER or android.text.InputType.TYPE_NUMBER_FLAG_DECIMAL
                    AlertDialog.Builder(act).setTitle("Theo dõi bao nhiêu giờ?").setView(o)
                        .setPositiveButton("Bắt đầu") { _, _ -> o.text.toString().replace(",", ".").toDoubleOrNull()?.let { if (it > 0) xong(it * 60) } }
                        .setNegativeButton("Huỷ", null).show()
                }
            }
        }.setNegativeButton("Huỷ", null).show()
    }

    private fun batDiem(act: Activity, ma: String, p: JSONObject, phut: Double, tenDuAn: String) {
        try {
            core().callAttr("theodoi_bat_diem", ma, p.toString(), phut, tenDuAn)
            val i = Intent(act, TheoDoiService::class.java)
            if (Build.VERSION.SDK_INT >= 26) act.startForegroundService(i) else act.startService(i)
            val gio = (phut / 60).let { if (it % 1.0 == 0.0) it.toInt().toString() else "%.1f".format(it) }
            Toast.makeText(act, "Đã bật theo dõi điểm ${p.optString("stt")} (mọi cam) trong $gio giờ. Rớt quá 5 phút app báo ngay. Để điện thoại có mạng, nên cắm sạc.", Toast.LENGTH_LONG).show()
        } catch (e: Exception) {
            Toast.makeText(act, "Không bật được: ${e.message?.substringAfterLast("Error: ")?.take(120)}", Toast.LENGTH_LONG).show(); return
        }
        xinChayNen(act)
    }

    /** Xin quyền thông báo + cho CamLink chạy nền KHÔNG bị tối ưu pin (Samsung hay dừng app nền → báo cáo bị thủng). */
    private fun xinChayNen(act: Activity) {
        if (Build.VERSION.SDK_INT >= 33 && act.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            act.requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 77)
        if (Build.VERSION.SDK_INT >= 23) {
            val pm = act.getSystemService(Context.POWER_SERVICE) as PowerManager
            if (!pm.isIgnoringBatteryOptimizations(act.packageName)) try {
                @Suppress("BatteryLife")
                act.startActivity(Intent(android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${act.packageName}")))
            } catch (_: Exception) {}
        }
    }

    fun dung(act: Activity, id: String) {
        Toast.makeText(act, "Đang dừng và làm báo cáo…", Toast.LENGTH_SHORT).show()
        thread {
            try {
                val f = core().callAttr("theodoi_dung", id).toString()
                act.runOnUiThread { if (f.isNotEmpty()) moPdf(act, f) else Toast.makeText(act, "Không tạo được PDF", Toast.LENGTH_LONG).show() }
            } catch (e: Exception) { act.runOnUiThread { Toast.makeText(act, "Lỗi: ${e.message?.take(120)}", Toast.LENGTH_LONG).show() } }
        }
    }

    fun uriPdf(ctx: Context, f: String): Uri = FileProvider.getUriForFile(ctx, "vn.vinalite.camlink.files", File(f))

    fun moPdf(act: Activity, f: String) {
        val u = uriPdf(act, f)
        AlertDialog.Builder(act).setTitle("Báo cáo theo dõi").setMessage(File(f).name)
            .setPositiveButton("Mở PDF") { _, _ ->
                try { act.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(u, "application/pdf").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)) }
                catch (_: Exception) { Toast.makeText(act, "Máy chưa có app đọc PDF — bấm Gửi để mở bằng Zalo", Toast.LENGTH_LONG).show() }
            }
            .setNeutralButton("Gửi Zalo / Gmail") { _, _ ->
                act.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("application/pdf").putExtra(Intent.EXTRA_STREAM, u)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), "Gửi báo cáo theo dõi"))
            }.setNegativeButton("Đóng", null).show()
    }

    /** Danh sách mọi lần theo dõi (đang chạy / đã xong) — nút "📈 Theo dõi" ở màn Kiểm tra từ xa. */
    fun danhSach(act: Activity) {
        val d = ds()
        if (d.length() == 0) {
            AlertDialog.Builder(act).setTitle("Theo dõi ổn định")
                .setMessage("Chưa theo dõi điểm nào.\n\nMở một điểm → bấm \"📈 Theo dõi\" → chọn thời gian. App theo dõi mọi cam của điểm, rớt quá 5 phút báo ngay, hết giờ ra báo cáo PDF.")
                .setPositiveButton("OK", null).show(); return
        }
        val nhan = (0 until d.length()).map { i ->
            val m = d.getJSONObject(i)
            (if (m.optString("trang_thai") == "dang") "⏳ " else "📄 ") + m.optString("ten") + " · rớt ${m.optInt("so_rot")} lần" +
                (if (m.optString("trang_thai") == "dang") " · còn ${m.optInt("con_phut")} phút" else "")
        }
        AlertDialog.Builder(act).setTitle("Theo dõi ổn định").setItems(nhan.toTypedArray()) { _, i ->
            val m = d.getJSONObject(i)
            if (m.optString("trang_thai") == "dang")
                AlertDialog.Builder(act).setTitle(m.optString("ten")).setMessage("Đang theo dõi, còn ${m.optInt("con_phut")} phút.")
                    .setPositiveButton("Dừng & lấy báo cáo") { _, _ -> dung(act, m.optString("id")) }.setNegativeButton("Đóng", null).show()
            else if (m.optString("pdf").isNotEmpty()) moPdf(act, m.optString("pdf"))
        }.setNegativeButton("Đóng", null).show()
    }
}

/** Chạy nền: mỗi 10 giây gọi lõi (lõi tự đo đúng nhịp 30 giây cho từng cam); không còn cam nào thì tự tắt. */
class TheoDoiService : Service() {
    @Volatile private var chay = false
    private var khoa: PowerManager.WakeLock? = null
    private val KENH = "theodoi"
    private val KENH_BAO = "theodoi_bao"

    /** Loại mạng điện thoại lúc đo — ghi vào báo cáo để biết lần rớt nào trùng lúc điện thoại đổi mạng. */
    private fun loaiMang(): String = try {
        val cm = getSystemService(android.net.ConnectivityManager::class.java)
        val nc = cm.getNetworkCapabilities(cm.activeNetwork)
        when {
            nc == null -> "khong"
            nc.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
            nc.hasTransport(android.net.NetworkCapabilities.TRANSPORT_CELLULAR) -> "di_dong"
            else -> "khac"
        }
    } catch (_: Exception) { "" }

    override fun onBind(i: Intent?): IBinder? = null

    private fun thongBao(chu: String): Notification {
        val nm = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26 && nm.getNotificationChannel(KENH) == null)
            nm.createNotificationChannel(NotificationChannel(KENH, "Theo dõi camera", NotificationManager.IMPORTANCE_LOW))
        if (Build.VERSION.SDK_INT >= 26 && nm.getNotificationChannel(KENH_BAO) == null)
            nm.createNotificationChannel(NotificationChannel(KENH_BAO, "Cảnh báo cam rớt", NotificationManager.IMPORTANCE_HIGH))
        val mo = PendingIntent.getActivity(this, 0, Intent(this, TuXaActivity::class.java).putExtra("mo_theo_doi", true), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val b = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, KENH) else @Suppress("DEPRECATION") Notification.Builder(this)
        return b.setSmallIcon(android.R.drawable.ic_menu_camera).setContentTitle("CamLink đang theo dõi camera").setContentText(chu)
            .setStyle(Notification.BigTextStyle().bigText(chu)).setOngoing(true).setContentIntent(mo).build()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Android tự khởi động lại dịch vụ khi app nằm nền có thể không cho chạy foreground → không được làm đổ app, chỉ dừng dịch vụ
        try {
            val n = thongBao("Đang bắt đầu…")
            if (Build.VERSION.SDK_INT >= 29) startForeground(9, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC) else startForeground(9, n)
        } catch (_: Exception) { stopSelf(); return START_NOT_STICKY }
        if (chay) return START_STICKY
        chay = true
        khoa = (getSystemService(Context.POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "camlink:theodoi").apply { acquire(26 * 3600 * 1000L) }
        thread { try {
            Loi.khoiDong(this)
            val core = Python.getInstance().getModule("camlink_core")
            val nm = getSystemService(NotificationManager::class.java)
            while (chay) {
                try {
                    val r = JSONObject(core.callAttr("theodoi_vong", loaiMang()).toString())
                    val bao = r.optJSONArray("bao") ?: JSONArray()
                    for (i in 0 until bao.length()) {
                        val x = bao.getJSONObject(i)
                        val gio = java.text.SimpleDateFormat("HH:mm").format(java.util.Date((x.optDouble("bd") * 1000).toLong()))
                        val (tieu, noi) = if (x.optString("kieu") == "rot")
                            "⚠ ${x.optString("ten")} RỚT từ $gio" to "Đã rớt hơn 5 phút. Nghi: ${x.optString("nguyen_nhan")}. Đã báo lên ghim LiteMark (nếu dự án đã nối)."
                        else "✓ ${x.optString("ten")} đã lên lại" to "Rớt từ $gio, kéo dài ${(x.optDouble("dur") / 60).toInt()} phút. ${x.optString("nguyen_nhan")}"
                        val b = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, KENH_BAO) else @Suppress("DEPRECATION") Notification.Builder(this)
                        nm.notify(("bao" + x.optString("id")).hashCode(), b.setSmallIcon(android.R.drawable.stat_notify_error).setContentTitle(tieu).setContentText(noi)
                            .setStyle(Notification.BigTextStyle().bigText(noi)).setAutoCancel(true)
                            .setContentIntent(PendingIntent.getActivity(this, 1, Intent(this, TuXaActivity::class.java).putExtra("mo_theo_doi", true), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)).build())
                    }
                    val dang = r.optJSONArray("dang") ?: JSONArray()
                    val pdf = r.optJSONArray("pdf_moi") ?: JSONArray()
                    for (i in 0 until pdf.length()) {
                        val f = pdf.optString(i); if (f.isEmpty()) continue
                        val u = TheoDoi.uriPdf(this, f)
                        val pi = PendingIntent.getActivity(this, f.hashCode(), Intent(Intent.ACTION_VIEW).setDataAndType(u, "application/pdf")
                            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE)
                        val b = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, KENH) else @Suppress("DEPRECATION") Notification.Builder(this)
                        nm.notify(f.hashCode(), b.setSmallIcon(android.R.drawable.ic_menu_camera).setContentTitle("Báo cáo theo dõi camera đã xong")
                            .setContentText(File(f).name + " — chạm để mở").setAutoCancel(true).setContentIntent(pi).build())
                    }
                    if (dang.length() == 0) break
                    val chu = (0 until dang.length()).joinToString("\n") { i ->
                        val m = dang.getJSONObject(i)
                        "${m.optString("ten")}: rớt ${m.optInt("so_rot")} lần (${m.optDouble("phut_rot")} phút)" + (if (m.optBoolean("dang_rot")) " · ĐANG RỚT" else "") + " · còn ${m.optInt("con_phut")} phút"
                    }
                    nm.notify(9, thongBao(chu))
                } catch (_: Exception) {}
                Thread.sleep(10_000)
            }
        } catch (_: Throwable) {} finally {
            chay = false
            try { khoa?.release() } catch (_: Exception) {}
            try { stopForeground(true); stopSelf() } catch (_: Exception) {}
        } }
        return START_STICKY
    }

    override fun onDestroy() { chay = false; try { khoa?.release() } catch (_: Exception) {}; super.onDestroy() }
}
