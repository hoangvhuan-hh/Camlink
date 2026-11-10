package vn.vinalite.camlink

import android.app.Activity
import android.app.ActivityManager
import android.app.AlertDialog
import android.app.Application
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.content.FileProvider
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date

/**
 * Khởi động lõi Python NGAY KHI tiến trình app mở — bất kể màn nào được mở trước.
 * (Android hay dọn app khi chuyển sang Zalo/chụp màn hình; lúc quay lại nó dựng thẳng màn đang xem
 *  — Kiểm tra từ xa, Giám sát — chứ không qua màn chính, trước đây lõi chưa chạy → app bị đóng.)
 * Kèm bộ ghi lỗi: app bị đóng vì lỗi thì lần mở sau báo lại + gửi được cho kỹ thuật.
 */
class CamLinkApp : Application() {
    override fun onCreate() {
        super.onCreate()
        val cu = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            try {
                val sw = java.io.StringWriter(); e.printStackTrace(java.io.PrintWriter(sw))
                File(filesDir, "loi_cuoi.txt").writeText("CamLink ${try { packageManager.getPackageInfo(packageName, 0).versionName } catch (_: Exception) { "?" }} · Android ${Build.VERSION.RELEASE} · ${Build.MODEL}\n" +
                    "Lúc: ${SimpleDateFormat("dd/MM/yyyy HH:mm:ss").format(Date())} · luồng ${t.name}\n\n$sw")
            } catch (_: Exception) {}
            cu?.uncaughtException(t, e)
        }
        try { Loi.khoiDong(this) } catch (e: Exception) {
            try { File(filesDir, "loi_cuoi.txt").writeText("Khởi động lõi lỗi: $e") } catch (_: Exception) {}
        }
    }
}

object Loi {
    @Volatile private var xong = false

    /** Gọi bao nhiêu lần cũng được: chỉ chạy một lần mỗi tiến trình. */
    @Synchronized fun khoiDong(ctx: Context) {
        if (xong) return
        val app = ctx.applicationContext
        if (!Python.isStarted()) Python.start(AndroidPlatform(app))
        val py = Python.getInstance()
        val th = File(app.filesDir, "capnhat")
        val mf = File(th, "manifest.json")
        if (mf.exists()) {
            // Chỉ dùng lõi cập nhật đè khi nó MỚI HƠN lõi trong APK; APK mới hơn thì bỏ thư mục capnhat cũ
            val pbApk = try { py.getModule("camlink_phien_ban")["PHIEN_BAN"].toString() } catch (_: Exception) { "0" }
            val pbCapNhat = try { org.json.JSONObject(mf.readText()).optString("phien_ban", "0") } catch (_: Exception) { "0" }
            if (soSanh(pbCapNhat, pbApk) > 0) py.getModule("sys")["path"]!!.callAttr("insert", 0, th.absolutePath)
            else th.deleteRecursively()
        }
        py.getModule("camlink_core").callAttr("khoi_tao", app.filesDir.absolutePath)
        xong = true
    }

    fun soSanh(a: String, b: String): Int {
        val x = a.split(".").map { it.filter { c -> c.isDigit() }.toIntOrNull() ?: 0 }
        val y = b.split(".").map { it.filter { c -> c.isDigit() }.toIntOrNull() ?: 0 }
        for (i in 0 until maxOf(x.size, y.size)) {
            val d = (x.getOrNull(i) ?: 0) - (y.getOrNull(i) ?: 0)
            if (d != 0) return d
        }
        return 0
    }

    /** Màn chính gọi khi mở: lần trước app bị đóng vì lỗi → báo + nút gửi kỹ thuật (Zalo/Gmail). */
    fun baoLoiCu(act: Activity) {
        val f = File(act.filesDir, "loi_cuoi.txt")
        var noiDung = if (f.exists()) f.readText() else ""
        // Android 11+: hỏi hệ thống lý do lần đóng trước (bắt được cả lỗi tầng thấp của bộ phát video và treo máy)
        if (Build.VERSION.SDK_INT >= 30) try {
            val sp = act.getSharedPreferences("loi", Context.MODE_PRIVATE)
            val daXem = sp.getLong("da_xem", 0L)
            val am = act.getSystemService(ActivityManager::class.java)
            val r = am.getHistoricalProcessExitReasons(act.packageName, 0, 5).firstOrNull {
                it.timestamp > daXem && it.reason in listOf(android.app.ApplicationExitInfo.REASON_CRASH, android.app.ApplicationExitInfo.REASON_CRASH_NATIVE, android.app.ApplicationExitInfo.REASON_ANR)
            }
            if (r != null) {
                sp.edit().putLong("da_xem", r.timestamp).apply()
                val loai = when (r.reason) { android.app.ApplicationExitInfo.REASON_CRASH_NATIVE -> "lỗi tầng thấp (bộ phát video/thư viện)"; android.app.ApplicationExitInfo.REASON_ANR -> "app treo không phản hồi"; else -> "lỗi chương trình" }
                val vet = try { r.traceInputStream?.bufferedReader()?.use { it.readText().take(8000) } ?: "" } catch (_: Exception) { "" }
                noiDung += "\n\n--- Hệ thống Android ghi nhận ---\nLúc: ${SimpleDateFormat("dd/MM/yyyy HH:mm:ss").format(Date(r.timestamp))} · $loai\n${r.description ?: ""}\n$vet"
            }
        } catch (_: Exception) {}
        if (noiDung.isBlank()) return
        val ra = File(act.filesDir, "ketqua").apply { mkdirs() }.let { File(it, "BaoLoi_CamLink.txt") }
        ra.writeText(noiDung)
        f.delete()
        AlertDialog.Builder(act).setTitle("Lần trước CamLink bị đóng do lỗi")
            .setMessage("App đã ghi lại lỗi. Bấm Gửi để chuyển cho kỹ thuật sửa.\n\n" + noiDung.lines().take(6).joinToString("\n"))
            .setPositiveButton("Gửi Zalo / Gmail") { _, _ ->
                val u = FileProvider.getUriForFile(act, "vn.vinalite.camlink.files", ra)
                act.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_STREAM, u)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION), "Gửi báo lỗi CamLink"))
            }.setNegativeButton("Đóng", null).show()
    }
}
