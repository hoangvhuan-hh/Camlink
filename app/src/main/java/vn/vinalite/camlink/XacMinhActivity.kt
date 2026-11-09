package vn.vinalite.camlink

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.HorizontalScrollView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import com.chaquo.python.Python
import org.json.JSONArray
import org.json.JSONObject
import kotlin.concurrent.thread

/**
 * XÁC MINH VỊ TRÍ THEO SỰ THẬT: tên miền chỉ là cái nhãn. Với mỗi điểm, đặt ảnh cam vừa chụp cạnh ảnh khảo sát của các ghim
 * LiteMark gần đó — người nhìn hình chốt cam thật sự đứng ở ghim nào; hoặc đứng tại cột bấm "Đang đứng tại đây" (GPS).
 * Chốt xong: cảnh báo, dẫn đường, bản đồ đều theo ghim thật.
 */
class XacMinhActivity : Activity() {
    private val ui = Handler(Looper.getMainLooper())
    private lateinit var ma: String
    private lateinit var khung: LinearLayout
    private val core by lazy { Python.getInstance().getModule("camlink_core") }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private fun chu(s: String, co: Float = 13f, dam: Boolean = false, mau: String = "#17202B") = TextView(this).apply {
        text = s; textSize = co; setTextColor(Color.parseColor(mau)); if (dam) setTypeface(null, Typeface.BOLD)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ma = intent.getStringExtra("ma") ?: return finish()
        val goc = LinearLayout(this)
        goc.orientation = LinearLayout.VERTICAL
        goc.setPadding(dp(12), dp(14), dp(12), dp(12))
        goc.setBackgroundColor(Color.parseColor("#EEF1F4"))
        goc.addView(chu("Xác minh vị trí cam theo thực tế", 20f, true))
        goc.addView(chu("Tên miền chỉ là nhãn. Nhìn ẢNH CAM (trái) rồi bấm ảnh khảo sát LiteMark giống cảnh nhất (phải) để chốt cam đứng ở ghim nào. Đứng tại cột thì bấm 📍. \"Giống\" chỉ là gợi ý của máy.", 12f, false, "#5B6776").apply { setPadding(0, dp(4), 0, dp(8)) })
        khung = LinearLayout(this)
        khung.orientation = LinearLayout.VERTICAL
        goc.addView(ScrollView(this).apply { addView(khung) }, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(goc)
        nap()
    }

    private fun nap() {
        khung.removeAllViews()
        khung.addView(chu("⏳ Đang lấy ảnh khảo sát từ LiteMark…", 14f, false, "#0F5D8C"))
        thread {
            try {
                val ds = JSONArray(core.callAttr("lm_xac_minh", ma).toString())
                ui.post { ve(ds) }
            } catch (e: Exception) {
                ui.post { khung.removeAllViews(); khung.addView(chu("✖ ${e.message?.substringAfterLast("RuntimeError: ")?.take(200)}", 14f, false, "#B42318")) }
            }
        }
    }

    private fun ve(ds: JSONArray) {
        khung.removeAllViews()
        for (i in 0 until ds.length()) {
            val p = ds.getJSONObject(i)
            val the = LinearLayout(this)
            the.orientation = LinearLayout.VERTICAL
            the.setPadding(dp(10), dp(10), dp(10), dp(10))
            val chac = p.optBoolean("lm_chac") || p.optString("lm_tay").isNotEmpty()
            the.background = GradientDrawable().apply { setColor(Color.WHITE); cornerRadius = dp(10).toFloat(); setStroke(dp(2), Color.parseColor(if (chac) "#1D7A46" else "#C88A00")) }
            val trangThai = if (p.optString("lm_tay").isNotEmpty()) "✔ đã chốt tay = ghim ${p.optString("lm_tay")}"
                else if (p.optBoolean("lm_chac")) "ghép theo toạ độ Excel = ghim ${p.optString("lm_stt")} (chưa ai xác nhận)"
                else "⚠ CHƯA CHẮC — máy đoán ghim ${p.optString("lm_stt")}"
            the.addView(chu("Điểm ${p.optString("stt")}. ${p.optString("ten")}", 15f, true))
            the.addView(chu("${p.optString("domain")} · ${p.optString("tong")} · $trangThai", 12f, false, "#5B6776"))
            val hang = LinearLayout(this)
            hang.orientation = LinearLayout.HORIZONTAL
            // trái: ảnh cam vừa chụp
            val trai = LinearLayout(this)
            trai.orientation = LinearLayout.VERTICAL
            val ivCam = ImageView(this)
            ivCam.scaleType = ImageView.ScaleType.CENTER_CROP
            ivCam.setBackgroundColor(Color.parseColor("#172029"))
            trai.addView(ivCam, LinearLayout.LayoutParams(dp(150), dp(100)))
            trai.addView(chu("ẢNH CAM đang nhìn", 11f, true, "#0F5D8C"))
            val anh = p.optString("anh")
            if (anh.isNotEmpty()) thread { val bm = BitmapFactory.decodeFile(anh); ui.post { ivCam.setImageBitmap(bm) } }
            else trai.addView(chu("(cam không lên — chưa có ảnh)", 10f, false, "#B42318"))
            hang.addView(trai)
            // phải: các ghim ứng viên, cuộn ngang
            val cuon = HorizontalScrollView(this)
            val dsGhim = LinearLayout(this)
            dsGhim.orientation = LinearLayout.HORIZONTAL
            val uv = p.optJSONArray("ung_vien") ?: JSONArray()
            for (j in 0 until minOf(uv.length(), 6)) {
                val g = uv.getJSONObject(j)
                val o = LinearLayout(this)
                o.orientation = LinearLayout.VERTICAL
                o.setPadding(dp(6), 0, 0, 0)
                val iv = ImageView(this)
                iv.scaleType = ImageView.ScaleType.CENTER_CROP
                iv.setBackgroundColor(Color.parseColor("#D7DEE5"))
                o.addView(iv, LinearLayout.LayoutParams(dp(130), dp(100)))
                val anhG = g.optString("anh")
                if (anhG.isNotEmpty()) thread { val bm = BitmapFactory.decodeFile(anhG); ui.post { iv.setImageBitmap(bm) } }
                val giong = g.optInt("giong", -1)
                val kc = g.optInt("kc", -1)
                val daGhep = g.optString("da_ghep_voi")
                o.addView(chu("Ghim ${g.optString("lm_stt")}" + (if (kc >= 0) " · ${kc} m" else "") + (if (giong >= 0) " · giống $giong%" else "") +
                    (if (daGhep.isNotEmpty()) "\n(đang là điểm $daGhep)" else ""), 10f, g.optString("lm_stt") == p.optString("lm_stt"), "#17202B"))
                val chot = { chotGhim(p, g.optString("lm_stt")) }
                iv.setOnClickListener { chot() }
                o.addView(Button(this).apply { text = "Đúng ghim này"; isAllCaps = false; textSize = 11f; setOnClickListener { chot() } })
                dsGhim.addView(o)
            }
            cuon.addView(dsGhim)
            hang.addView(cuon, LinearLayout.LayoutParams(0, -2, 1f))
            the.addView(hang)
            the.addView(Button(this).apply { text = "📍 Tôi đang đứng tại cột cam này (GPS)"; isAllCaps = false; textSize = 12f; setOnClickListener { dungTaiDay(p) } })
            khung.addView(the, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(10) })
        }
        if (ds.length() == 0) khung.addView(chu("Chưa có điểm nào", 14f))
    }

    private fun chotGhim(p: JSONObject, lm: String) {
        AlertDialog.Builder(this).setTitle("Chốt vị trí")
            .setMessage("Điểm ${p.optString("stt")} «${p.optString("ten")}» (${p.optString("domain")}) thực tế đứng ở GHIM LiteMark $lm?\nTừ nay cảnh báo, dẫn đường, bản đồ theo ghim này.")
            .setPositiveButton("Đúng") { _, _ ->
                thread {
                    try {
                        core.callAttr("lm_dat_ghim", ma, p.optString("stt"), lm, null)
                        ui.post { Toast.makeText(this, "Đã chốt điểm ${p.optString("stt")} = ghim $lm", Toast.LENGTH_SHORT).show(); nap() }
                    } catch (e: Exception) { ui.post { Toast.makeText(this, "Lỗi: ${e.message?.take(120)}", Toast.LENGTH_LONG).show() } }
                }
            }.setNegativeButton("Huỷ", null).show()
    }

    @Suppress("MissingPermission", "DEPRECATION")
    private fun dungTaiDay(p: JSONObject) {
        Toast.makeText(this, "Đang lấy GPS…", Toast.LENGTH_SHORT).show()
        val lm = getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val xong: (Location?) -> Unit = { l ->
            if (l == null) Toast.makeText(this, "Không lấy được GPS — ra chỗ thoáng rồi bấm lại", Toast.LENGTH_LONG).show()
            else thread {
                try {
                    val r = JSONObject(core.callAttr("lm_dung_tai_day", ma, p.optString("stt"), l.latitude, l.longitude, null).toString())
                    ui.post { Toast.makeText(this, "Đã chốt: điểm ${p.optString("stt")} = ghim ${r.optString("ghim")} (cách ${r.optInt("kc")} m)", Toast.LENGTH_LONG).show(); nap() }
                } catch (e: Exception) { ui.post { AlertDialog.Builder(this).setMessage(e.message?.substringAfterLast("RuntimeError: ")?.take(200)).setPositiveButton("Đóng", null).show() } }
            }
        }
        val cu = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
            .mapNotNull { runCatching { lm.getLastKnownLocation(it) }.getOrNull() }
            .filter { System.currentTimeMillis() - it.time < 60_000 }.maxByOrNull { it.time }
        if (cu != null) { xong(cu); return }
        var daTra = false
        val nghe = object : LocationListener {
            override fun onLocationChanged(l: Location) { if (!daTra) { daTra = true; lm.removeUpdates(this); xong(l) } }
            @Deprecated("") override fun onStatusChanged(p: String?, s: Int, b: Bundle?) {}
            override fun onProviderEnabled(p: String) {}
            override fun onProviderDisabled(p: String) {}
        }
        for (pr in listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)) runCatching { lm.requestLocationUpdates(pr, 0L, 0f, nghe, Looper.getMainLooper()) }
        ui.postDelayed({ if (!daTra) { daTra = true; lm.removeUpdates(nghe); xong(null) } }, 25_000)
    }
}
