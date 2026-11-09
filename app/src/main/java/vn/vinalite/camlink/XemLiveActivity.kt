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
        val url = intent.getStringExtra("url") ?: ""
        val goc = LinearLayout(this)
        goc.orientation = LinearLayout.VERTICAL
        goc.setBackgroundColor(Color.BLACK)
        val tieuDe = TextView(this).apply {
            text = intent.getStringExtra("tieu_de") ?: "Xem trực tiếp"
            textSize = 16f; setTextColor(Color.WHITE); setPadding(24, 24, 24, 8)
        }
        val tt = TextView(this).apply { textSize = 13f; setTextColor(Color.parseColor("#9AA8B5")); setPadding(24, 8, 24, 8) }
        val khung = FrameLayout(this)
        goc.addView(tieuDe)
        goc.addView(khung, LinearLayout.LayoutParams(-1, 0, 1f))
        goc.addView(tt)
        setContentView(goc)
        val caoDp = (resources.displayMetrics.heightPixels / resources.displayMetrics.density).toInt() - 140
        khung.post { boPhat.phat(khung, url, tt, caoDp) }
    }

    override fun onPause() { boPhat.tamDung(); super.onPause() }
    override fun onResume() { boPhat.tiepTuc(); super.onResume() }
    override fun onDestroy() { boPhat.dungHet(); super.onDestroy() }
}
