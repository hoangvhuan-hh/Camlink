package vn.vinalite.camlink

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView

/** Xem trực tiếp toàn màn hình — dùng CÙNG bộ phát libVLC với màn giám sát (ExoPlayer cũ không phát được cam Oryza). */
class XemLiveActivity : Activity() {
    private val boPhat by lazy { BoPhat(this) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        var url = intent.getStringExtra("url") ?: ""
        var tieu = intent.getStringExtra("tieu_de") ?: "Xem trực tiếp"
        // 2.14.0 — mở từ mã QR trong hồ sơ: camlink://xem?d=<base64url(JSON)>; khoá do camlink_hoso.ma_xem() ghi:
        // l = link video có sẵn tài khoản, da = tên dự án, t = tên cam. Chỉ nhận link rtsp. Không cần dự án, không cần thiết lập.
        val du = intent.data
        if (du != null && du.scheme == "camlink" && du.host == "xem") {
            url = ""
            try {
                val tho = du.getQueryParameter("d") ?: ""
                val co = android.util.Base64.URL_SAFE or android.util.Base64.NO_PADDING or android.util.Base64.NO_WRAP
                val j = org.json.JSONObject(String(android.util.Base64.decode(tho, co), Charsets.UTF_8))
                val l = j.optString("l")
                if (l.startsWith("rtsp://")) url = l
                val ten = listOf(j.optString("da"), j.optString("t")).filter { it.isNotEmpty() }.joinToString(" · ")
                if (ten.isNotEmpty()) tieu = ten
            } catch (_: Exception) { }
        }
        val goc = LinearLayout(this)
        goc.orientation = LinearLayout.VERTICAL
        goc.setBackgroundColor(Color.BLACK)
        val tieuDe = TextView(this).apply {
            text = tieu
            textSize = 16f; setTextColor(Color.WHITE); setPadding(24, 24, 24, 8)
        }
        val tt = TextView(this).apply { textSize = 13f; setTextColor(Color.parseColor("#9AA8B5")); setPadding(24, 8, 24, 8) }
        val khung = FrameLayout(this)
        goc.addView(tieuDe)
        goc.addView(khung, LinearLayout.LayoutParams(-1, 0, 1f))
        goc.addView(tt)
        setContentView(goc)
        val caoDp = (resources.displayMetrics.heightPixels / resources.displayMetrics.density).toInt() - 140
        if (url.isEmpty()) { tt.text = "Mã này không có link xem trực tiếp. Hãy quét lại mã QR trong hồ sơ."; return }
        khung.post { boPhat.phat(khung, url, tt, caoDp) }
    }

    override fun onPause() { boPhat.tamDung(); super.onPause() }
    override fun onResume() { boPhat.tiepTuc(); super.onResume() }
    override fun onDestroy() { boPhat.dungHet(); super.onDestroy() }
}
