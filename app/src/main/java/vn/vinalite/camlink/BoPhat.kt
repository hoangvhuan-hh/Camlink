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
    private fun dp(v: Int) = (v * act.resources.displayMetrics.density).toInt()

    /** Phát url vào khung; trangThai nhận dòng trạng thái. Lỗi → hiện lý do + nút mở VLC ngoài. */
    fun phat(khung: FrameLayout, url: String, trangThai: TextView, chieuCao: Int = 200, khiLoi: (() -> Unit)? = null) {
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
                MediaPlayer.Event.Vout -> {
                    trangThai.text = "🔴 TRỰC TIẾP · ${java.text.SimpleDateFormat("HH:mm:ss").format(java.util.Date())} · ${(System.currentTimeMillis() - t0) / 1000}s"
                    trangThai.setTextColor(Color.parseColor("#1D7A46"))
                }
                MediaPlayer.Event.EncounteredError -> ui.post { loi(khung, url, trangThai, "libVLC báo lỗi luồng (sau ${(System.currentTimeMillis() - t0) / 1000}s)"); khiLoi?.invoke() }
                MediaPlayer.Event.EndReached -> ui.post { loi(khung, url, trangThai, "Luồng kết thúc sớm — cam ngắt kết nối"); khiLoi?.invoke() }
            }
        }
        ui.postDelayed({
            if (dang[url] === mp && !mp.isPlaying && mp.vlcVout?.areViewsAttached() == true && trangThai.text.startsWith("⏳")) {
                loi(khung, url, trangThai, "Không nhận được hình sau 20 giây"); khiLoi?.invoke()
            }
        }, 20000)
        mp.play()
        dang[url] = mp
    }

    private fun loi(khung: FrameLayout, url: String, trangThai: TextView, ly: String) {
        dung(url)
        khung.removeAllViews()
        val an = url.replace(Regex("//[^@/]*@"), "//")
        trangThai.text = "✖ $ly\n$an"
        trangThai.setTextColor(Color.parseColor("#B42318"))
        val b = Button(act)
        b.text = "Thử lại"
        b.isAllCaps = false
        b.setOnClickListener { phat(khung, url, trangThai) }
        val b2 = Button(act)
        b2.text = "Mở VLC"
        b2.isAllCaps = false
        b2.setOnClickListener {
            try { act.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(Uri.parse(url), "video/*")) } catch (_: Exception) {}
        }
        val hang = android.widget.LinearLayout(act)
        hang.orientation = android.widget.LinearLayout.HORIZONTAL
        hang.addView(b); hang.addView(b2)
        khung.setBackgroundColor(Color.parseColor("#FDECEA"))
        khung.addView(hang, FrameLayout.LayoutParams(-2, -2, Gravity.CENTER))
    }

    fun dung(url: String) {
        dang.remove(url)?.let { try { it.stop(); it.detachViews(); it.release() } catch (_: Exception) {} }
    }

    fun dungHet() { ArrayList(dang.keys).forEach { dung(it) } }
    fun tamDung() { dang.values.forEach { try { it.pause() } catch (_: Exception) {} } }
    fun tiepTuc() { dang.values.forEach { try { it.play() } catch (_: Exception) {} } }
}
