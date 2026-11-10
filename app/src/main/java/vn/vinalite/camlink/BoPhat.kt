package vn.vinalite.camlink

import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.widget.Button
import android.widget.FrameLayout
import android.widget.TextView
import org.videolan.libvlc.LibVLC
import org.videolan.libvlc.Media
import org.videolan.libvlc.MediaPlayer
import org.videolan.libvlc.util.VLCVideoLayout

/** Bộ phát trực tiếp dùng chung (libVLC — cùng lõi với VLC/IOC). Mỗi ô hình một MediaPlayer. */
class BoPhat(private val act: Activity) {
    private val ui = Handler(Looper.getMainLooper())
    private val lib: LibVLC by lazy {
        LibVLC(act, arrayListOf("--rtsp-tcp", "--network-caching=600", "--no-drop-late-frames", "--no-skip-frames", "--no-audio"))
    }
    private val dang = HashMap<String, MediaPlayer>()
    val coHinhLuc = HashMap<String, Long>()              // url → lần cuối thấy hình (video là sự thật)
    private val ngatLuc = HashMap<String, Long>()        // url → lúc luồng bắt đầu rớt (giữ tới khi có hình lại)
    private val canh = HashMap<String, Runnable>()       // url → vòng gõ cửa / canh hình đứng
    @Volatile private var dungHan = false
    @Volatile private var tamNghi = 0L                   // >0 = app đang tạm nghỉ (hộp xin quyền, chuyển app) — không được coi là cam rớt
    private val gio = java.text.SimpleDateFormat("HH:mm:ss")
    private fun dp(v: Int) = (v * act.resources.displayMetrics.density).toInt()

    /** Phát url vào khung; trangThai nhận dòng trạng thái. Lỗi → hiện lý do + nút mở VLC ngoài. */
    fun phat(khung: FrameLayout, url: String, trangThai: TextView, chieuCao: Int = 200, khiLoi: (() -> Unit)? = null) {
        dungHan = false
        canh.remove(url)?.let { ui.removeCallbacks(it) }
        dung(url)
        khung.removeAllViews()
        if (url.isEmpty()) { trangThai.text = "Không có luồng video"; return }
        val layout = VLCVideoLayout(act)
        khung.addView(layout, FrameLayout.LayoutParams(-1, dp(chieuCao)))
        val mp = MediaPlayer(lib)
        mp.attachViews(layout, null, false, false)
        val media = Media(lib, Uri.parse(url))
        media.setHWDecoderEnabled(true, false)
        media.addOption(":rtsp-tcp")
        media.addOption(":network-caching=600")
        mp.media = media
        media.release()
        val t0 = System.currentTimeMillis()
        trangThai.setTextColor(Color.parseColor("#5B6776"))
        trangThai.text = "⏳ Đang kết nối…"
        mp.setEventListener { ev ->
            when (ev.type) {
                MediaPlayer.Event.Buffering -> if (ev.buffering < 100f) trangThai.text = "⏳ Đang tải ${ev.buffering.toInt()}%"
                MediaPlayer.Event.Vout -> if (ev.voutCount > 0) {
                    coHinhLuc[url] = System.currentTimeMillis()
                    val nl = ngatLuc.remove(url)
                    val them = if (nl != null) " · lên lại sau rớt ${(System.currentTimeMillis() - nl) / 1000}s" else ""
                    trangThai.text = "🔴 TRỰC TIẾP · ${gio.format(java.util.Date())}$them"
                    trangThai.setTextColor(Color.parseColor("#1D7A46"))
                    khung.setBackgroundColor(Color.TRANSPARENT)
                    if (nl != null) ghiLoi(url, nl, System.currentTimeMillis())
                    canhHinhDung(khung, url, trangThai, chieuCao, mp, khiLoi)
                }
                MediaPlayer.Event.EncounteredError -> ui.post { loi(khung, url, trangThai, "libVLC báo lỗi luồng (sau ${(System.currentTimeMillis() - t0) / 1000}s)", chieuCao); khiLoi?.invoke() }
                MediaPlayer.Event.EndReached -> ui.post { loi(khung, url, trangThai, "Luồng kết thúc sớm — cam ngắt kết nối", chieuCao); khiLoi?.invoke() }
            }
        }
        ui.postDelayed({
            if (dang[url] === mp && !mp.isPlaying && mp.vlcVout?.areViewsAttached() == true && trangThai.text.startsWith("⏳")) {
                loi(khung, url, trangThai, "Không nhận được hình sau 20 giây", chieuCao); khiLoi?.invoke()
            }
        }, 20000)
        mp.play()
        dang[url] = mp
    }

    /** Đang có hình mà khung hình đứng im > 15 s (cam ngắt luồng nhưng không báo lỗi) → coi là rớt, đúng như mắt thấy. */
    private fun canhHinhDung(khung: FrameLayout, url: String, trangThai: TextView, chieuCao: Int, mp: MediaPlayer, khiLoi: (() -> Unit)?) {
        canh.remove(url)?.let { ui.removeCallbacks(it) }
        var tCu = -1L; var dungTu = 0L
        val r = object : Runnable { override fun run() {
            if (dungHan || dang[url] !== mp || !khung.isAttachedToWindow) return
            val t = try { mp.time } catch (_: Exception) { -1L }
            val now = System.currentTimeMillis()
            if (tamNghi > 0L || now - tiepLuc < 8000) { tCu = t; dungTu = now; ui.postDelayed(this, 5000); return }
            if (t != tCu || !mp.isPlaying && t < 0) { tCu = t; dungTu = now; if (t > 0) coHinhLuc[url] = now }
            else if (now - dungTu > 15000) { loi(khung, url, trangThai, "Hình đứng im — cam ngắt luồng video", chieuCao); khiLoi?.invoke(); return }
            ui.postDelayed(this, 5000)
        } }
        canh[url] = r
        ui.postDelayed(r, 5000)
    }

    /** Rớt → báo GIỜ RỚT, rồi gõ cửa cam 10 giây/lần (1 kết nối TCP, không kéo video). Cam trả lời là tự phát lại — không cần bấm. */
    private fun loi(khung: FrameLayout, url: String, trangThai: TextView, ly: String, chieuCao: Int = 200) {
        dung(url)
        khung.removeAllViews()
        val dau = ngatLuc[url] == null
        if (dau) { ngatLuc[url] = System.currentTimeMillis(); ghiLoi(url, ngatLuc[url]!!, 0L) }
        val luc = gio.format(java.util.Date(ngatLuc[url]!!))
        trangThai.text = "✖ Cam rớt lúc $luc — đang chờ cam lên (kiểm 10 giây/lần)\n$ly"
        trangThai.setTextColor(Color.parseColor("#B42318"))
        khung.setBackgroundColor(Color.parseColor("#FDECEA"))
        val b2 = Button(act)
        b2.text = "Mở VLC"
        b2.isAllCaps = false
        b2.setOnClickListener {
            try { act.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(Uri.parse(url), "video/*")) } catch (_: Exception) {}
        }
        khung.addView(b2, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))
        val u = try { Uri.parse(url) } catch (_: Exception) { null }
        val host = u?.host ?: return
        val port = if ((u.port) > 0) u.port else 554
        var lan = 0
        val r = object : Runnable { override fun run() {
            if (dungHan || !khung.isAttachedToWindow) return
            lan++
            Thread {
                val mo = try { java.net.Socket().use { it.connect(java.net.InetSocketAddress(host, port), 4000) }; true } catch (_: Exception) { false }
                ui.post {
                    if (dungHan || !khung.isAttachedToWindow || canh[url] !== this) return@post
                    if (mo) { trangThai.text = "⏳ Cam đã trả lời (rớt từ $luc) — đang lấy hình…"; phat(khung, url, trangThai, chieuCao) }
                    else {
                        trangThai.text = "✖ Cam rớt lúc $luc — vẫn chưa lên (đã kiểm $lan lần, lần cuối ${gio.format(java.util.Date())})\n$ly"
                        ui.postDelayed(this, 10000)
                    }
                }
            }.start()
        } }
        canh[url] = r
        ui.postDelayed(r, 10000)
    }

    /** Ghi lần ngắt/lên lại sang lõi — nếu cam này đang được Theo dõi thì báo cáo có luôn (hai màn khớp nhau). */
    private fun ghiLoi(url: String, ngat: Long, len: Long) {
        val u = try { Uri.parse(url) } catch (_: Exception) { return }
        val host = u.host ?: return
        val port = if (u.port > 0) u.port else 554
        Thread {
            try {
                com.chaquo.python.Python.getInstance().getModule("camlink_core")
                    .callAttr("theodoi_ghi_live", host, port, ngat / 1000.0, len / 1000.0)
            } catch (_: Exception) {}
        }.start()
    }

    fun dung(url: String) {
        dang.remove(url)?.let { try { it.stop(); it.detachViews(); it.release() } catch (_: Exception) {} }
    }

    fun dungHet() { dungHan = true; canh.values.forEach { ui.removeCallbacks(it) }; canh.clear(); ArrayList(dang.keys).forEach { dung(it) } }
    /** Cam này vừa có hình trong 90 giây qua (hoặc đang phát)? */
    fun vuaCoHinh(url: String) = System.currentTimeMillis() - (coHinhLuc[url] ?: 0L) < 90_000
    @Volatile private var tiepLuc = 0L
    fun tamDung() { tamNghi = System.currentTimeMillis(); dang.values.forEach { try { it.pause() } catch (_: Exception) {} } }
    fun tiepTuc() { tamNghi = 0L; tiepLuc = System.currentTimeMillis(); dang.values.forEach { try { it.play() } catch (_: Exception) {} } }
}
