package vn.vinalite.camlink

import android.app.Activity
import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject
import java.io.File

/** Sơ đồ sau khi cài: Internet → tên miền → modem → từng cam (ảnh chụp qua tên miền + nút xem trực tiếp). */
class SoDoActivity : Activity() {
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun the(mauVien: String): LinearLayout {
        val l = LinearLayout(this)
        l.orientation = LinearLayout.VERTICAL
        l.setPadding(dp(12), dp(10), dp(12), dp(12))
        val nen = GradientDrawable()
        nen.setColor(Color.WHITE)
        nen.cornerRadius = dp(10).toFloat()
        nen.setStroke(dp(2), Color.parseColor(mauVien))
        l.background = nen
        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.topMargin = dp(4)
        l.layoutParams = lp
        return l
    }

    private fun chu(s: String, co: Float = 14f, dam: Boolean = false, mau: String = "#17202B"): TextView {
        val t = TextView(this)
        t.text = s
        t.textSize = co
        t.setTextColor(Color.parseColor(mau))
        if (dam) t.setTypeface(null, Typeface.BOLD)
        return t
    }

    private fun mui(): TextView {
        val t = chu("│\n▼", 14f, mau = "#5B6776")
        t.gravity = Gravity.CENTER
        return t
    }

    private fun nhan(ok: Boolean?, chuOk: String, chuKhong: String): TextView {
        val t = chu(if (ok == true) "✔ $chuOk" else "✖ $chuKhong", 13f, true, "#FFFFFF")
        t.setPadding(dp(8), dp(3), dp(8), dp(3))
        val nen = GradientDrawable()
        nen.cornerRadius = dp(6).toFloat()
        nen.setColor(Color.parseColor(if (ok == true) "#1D7A46" else "#B42318"))
        t.background = nen
        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.rightMargin = dp(6)
        t.layoutParams = lp
        return t
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val j = JSONObject(intent.getStringExtra("du_lieu") ?: "{}")
        val goc = LinearLayout(this)
        goc.orientation = LinearLayout.VERTICAL
        goc.setPadding(dp(14), dp(18), dp(14), dp(24))
        goc.setBackgroundColor(Color.parseColor("#EEF1F4"))

        val cams = j.optJSONArray("cam")
        var nNgoai = 0
        var nTaiCho = 0
        val tong = cams?.length() ?: 0
        for (i in 0 until tong) {
            val c = cams!!.getJSONObject(i)
            if (c.optBoolean("ngoai")) nNgoai++
            if (c.optBoolean("ok")) nTaiCho++
        }
        goc.addView(chu("[${j.optString("du_an")}] điểm ${j.optString("stt")}", 20f, true))
        goc.addView(chu(j.optString("ten"), 15f))
        goc.addView(chu("Kiểm lúc ${j.optString("luc")} · cài tại chỗ $nTaiCho/$tong · xem được từ ngoài $nNgoai/$tong", 13f, mau = "#5B6776"))

        // Internet / tên miền
        val tm = the("#0F5D8C")
        tm.addView(chu("🌐 INTERNET — tên miền", 13f, true, "#0F5D8C"))
        tm.addView(chu(j.optString("domain"), 16f, true))
        val ipTm = j.optString("ip_ten_mien")
        tm.addView(chu(if (ipTm.isNotEmpty()) "trỏ về IP $ipTm" else "không phân giải được", 13f,
            mau = if (ipTm.isNotEmpty()) "#1D7A46" else "#B42318"))
        goc.addView(tm)
        goc.addView(mui())

        // Modem
        val md = the("#5B6776")
        md.addView(chu("📶 MODEM", 13f, true, "#5B6776"))
        md.addView(chu("IP WAN: ${j.optString("wan").ifEmpty { "chưa đọc được" }}", 14f))
        md.addView(chu("IP LAN: ${j.optString("gw")}", 14f))
        val luat = j.optJSONArray("luat")
        if (luat != null && luat.length() > 0) {
            md.addView(chu("Luật mở port (ngoài = trong, TCP):", 13f, true))
            for (i in 0 until luat.length()) {
                val r = luat.getJSONObject(i)
                md.addView(chu("  ${r.optString("ten").padEnd(10)}  ${r.optInt("port").toString().padEnd(5)} → ${r.optString("ip")}", 13f).apply { typeface = Typeface.MONOSPACE })
            }
        }
        goc.addView(md)
        goc.addView(mui())

        // Cam
        for (i in 0 until tong) {
            val c = cams!!.getJSONObject(i)
            val ct = the(if (c.optBoolean("ngoai")) "#1D7A46" else "#B42318")
            ct.addView(chu("📷 CAM ${c.optInt("so")}  ${c.optString("hang")} ${c.optString("model")}".trim(), 15f, true))
            val hang = LinearLayout(this)
            hang.orientation = LinearLayout.HORIZONTAL
            hang.setPadding(0, dp(4), 0, dp(6))
            hang.addView(nhan(c.optBoolean("ok"), "Cài tại chỗ", "Cài tại chỗ"))
            hang.addView(nhan(c.optBoolean("ngoai"), "Xem được từ ngoài", "Chưa xem được từ ngoài"))
            ct.addView(hang)
            val anh = c.optString("anh")
            if (anh.isNotEmpty() && File(anh).exists()) {
                val iv = ImageView(this)
                iv.setImageBitmap(BitmapFactory.decodeFile(anh))
                iv.adjustViewBounds = true
                ct.addView(iv, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
                ct.addView(chu("Ảnh chụp lấy qua ${j.optString("domain")}:${c.optInt("http")}", 12f, mau = "#5B6776"))
            }
            ct.addView(chu("IP LAN ${c.optString("ip")} · HTTP ${c.optInt("http")} · RTSP ${c.optInt("rtsp")}", 13f))
            if (c.optString("mac").isNotEmpty()) ct.addView(chu("MAC ${c.optString("mac")}", 13f))
            ct.addView(chu("Xem web: http://${j.optString("domain")}:${c.optInt("http")}", 13f, mau = "#0F5D8C").apply { setTextIsSelectable(true) })
            val ghiCai = c.optString("ghi")
            if (ghiCai.isNotEmpty()) ct.addView(chu("Lúc cài: $ghiCai", 13f, mau = if (ghiCai.contains("CHƯA") || ghiCai.contains("LỖI")) "#9A5B00" else "#1D7A46"))
            val loi = c.optString("loi_ngoai")
            if (loi.isNotEmpty()) ct.addView(chu("⚠ $loi", 13f, mau = "#9A5B00"))
            val live = c.optString("live")
            if (live.isNotEmpty()) {
                val b = Button(this)
                b.text = "▶ Xem trực tiếp qua tên miền"
                b.isAllCaps = false
                b.setOnClickListener {
                    startActivity(Intent(this, XemLiveActivity::class.java)
                        .putExtra("url", live)
                        .putExtra("tieu_de", "Cam ${c.optInt("so")} · ${j.optString("domain")}:${c.optInt("rtsp")}"))
                }
                ct.addView(b)
            }
            goc.addView(ct)
        }
        setContentView(ScrollView(this).apply { addView(goc) })
    }
}
