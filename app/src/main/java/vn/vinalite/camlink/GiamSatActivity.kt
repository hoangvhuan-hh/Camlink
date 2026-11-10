package vn.vinalite.camlink

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.FrameLayout
import android.widget.GridLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * MÀN HÌNH GIÁM SÁT: mỗi điểm một khung, bấy nhiêu cam bấy nhiêu ô.
 * Lưới tổng: khung thu nhỏ (ảnh chụp lúc kiểm + lên/tổng). Bấm khung → phóng to, cam lên phát trực tiếp, cam lỗi báo ngay trong ô.
 */
class GiamSatActivity : Activity() {
    private lateinit var kq: JSONObject
    private var ma = ""
    private lateinit var goc: LinearLayout
    private lateinit var duoi: LinearLayout          // thanh nút cố định dưới đáy (chỉ khi mở một điểm)
    private val boPhat by lazy { BoPhat(this) }
    private var dangMo: String? = null
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
    private val mauVien = mapOf("xanh" to "#1D7A46", "vang" to "#C88A00", "do" to "#B42318")
    private val mauNen = mapOf("xanh" to "#EAF6EF", "vang" to "#FFF7E0", "do" to "#FDECEA")

    private fun chu(s: String, co: Float = 13f, dam: Boolean = false, mau: String = "#17202B") = TextView(this).apply {
        text = s; textSize = co; setTextColor(Color.parseColor(mau)); if (dam) setTypeface(null, Typeface.BOLD)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val f = intent.getStringExtra("file") ?: return finish()
        ma = intent.getStringExtra("ma") ?: ""
        kq = JSONObject(File(f).readText())
        goc = LinearLayout(this)
        goc.orientation = LinearLayout.VERTICAL
        goc.setBackgroundColor(Color.parseColor("#0F161C"))
        goc.setPadding(dp(8), dp(12), dp(8), dp(16))
        duoi = LinearLayout(this)
        duoi.orientation = LinearLayout.VERTICAL
        duoi.setBackgroundColor(Color.parseColor("#172029"))
        duoi.setPadding(dp(6), dp(6), dp(6), dp(6))
        val nen = LinearLayout(this)
        nen.orientation = LinearLayout.VERTICAL
        nen.setBackgroundColor(Color.parseColor("#0F161C"))
        nen.addView(ScrollView(this).apply { isFillViewport = true; setBackgroundColor(Color.parseColor("#0F161C")); addView(goc) }, LinearLayout.LayoutParams(-1, 0, 1f))
        nen.addView(duoi, LinearLayout.LayoutParams(-1, -2))
        setContentView(nen)
        veLuoi()
    }

    private fun diemList(): List<JSONObject> {
        val ds = kq.optJSONArray("diem") ?: JSONArray()
        return (0 until ds.length()).map { ds.getJSONObject(it) }
            .sortedBy { mapOf("do" to 0, "vang" to 1, "xanh" to 2)[it.optString("muc")] ?: 3 }
    }

    private fun camLen(p: JSONObject) = (p.optJSONArray("cam") ?: JSONArray()).let { cs ->
        (0 until cs.length()).count { cs.getJSONObject(it).optString("muc") == "xanh" } to cs.length()
    }

    // ---------------- LƯỚI TỔNG ----------------
    private fun veLuoi() {
        boPhat.dungHet(); dangMo = null
        goc.removeAllViews()
        duoi.removeAllViews(); duoi.visibility = View.GONE
        val (dat, tong) = diemList().fold(0 to 0) { a, p -> val (l, t) = camLen(p); (a.first + l) to (a.second + t) }
        goc.addView(chu("${kq.optString("du_an")} · $dat/$tong cam lên · ${kq.optString("luc")}", 15f, true, "#E7EDF2").apply { setPadding(dp(4), 0, dp(4), dp(8)) })
        val luoi = GridLayout(this)
        luoi.columnCount = 2
        for (p in diemList()) luoi.addView(khungNho(p), GridLayout.LayoutParams(GridLayout.spec(GridLayout.UNDEFINED, 1f), GridLayout.spec(GridLayout.UNDEFINED, 1f)).apply { width = 0; setMargins(dp(4), dp(4), dp(4), dp(4)) })
        goc.addView(luoi)
    }

    private fun khungNho(p: JSONObject): View {
        val muc = p.optString("muc")
        val (len, tong) = camLen(p)
        val k = LinearLayout(this)
        k.orientation = LinearLayout.VERTICAL
        k.background = GradientDrawable().apply { setColor(Color.parseColor("#172029")); cornerRadius = dp(8).toFloat(); setStroke(dp(2), Color.parseColor(mauVien[muc] ?: "#5B6776")) }
        k.setPadding(dp(6), dp(6), dp(6), dp(6))
        k.addView(chu("Điểm ${p.optString("stt")} · $len/$tong lên", 13f, true, mauVien[muc]?.let { if (muc == "xanh") "#7ED6A0" else if (muc == "vang") "#FFD166" else "#FF8A80" } ?: "#E7EDF2"))
        k.addView(chu(p.optString("ten"), 11f, false, "#C6D0DA").apply { maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END })
        val cs = p.optJSONArray("cam") ?: JSONArray()
        val o = GridLayout(this)
        o.columnCount = if (cs.length() <= 1) 1 else 2
        for (i in 0 until cs.length()) {
            val c = cs.getJSONObject(i)
            val fr = FrameLayout(this)
            fr.setBackgroundColor(Color.parseColor(if (c.optString("muc") == "xanh") "#000000" else "#5A1F1A"))
            val anh = c.optString("anh")
            if (anh.isNotEmpty() && File(anh).exists()) {
                val iv = ImageView(this)
                iv.setImageBitmap(BitmapFactory.decodeFile(anh, BitmapFactory.Options().apply { inSampleSize = 4 }))
                iv.scaleType = ImageView.ScaleType.CENTER_CROP
                fr.addView(iv, FrameLayout.LayoutParams(-1, -1))
            }
            fr.addView(chu(if (c.optString("muc") == "xanh") "C${c.optInt("so")}" else "C${c.optInt("so")} ✖", 11f, true, "#FFFFFF").apply {
                setBackgroundColor(Color.parseColor("#80000000")); setPadding(dp(3), 0, dp(3), 0)
            }, FrameLayout.LayoutParams(-2, -2, Gravity.TOP or Gravity.START))
            o.addView(fr, GridLayout.LayoutParams(GridLayout.spec(GridLayout.UNDEFINED, 1f), GridLayout.spec(GridLayout.UNDEFINED, 1f)).apply { width = 0; height = dp(if (cs.length() <= 1) 90 else 52); setMargins(dp(1), dp(1), dp(1), dp(1)) })
        }
        k.addView(o)
        k.setOnClickListener { moDiem(p) }
        return k
    }

    // ---------------- MỘT ĐIỂM: bấy nhiêu cam, bấy nhiêu ô phát trực tiếp ----------------
    private fun moDiem(p: JSONObject) {
        boPhat.dungHet(); dangMo = p.optString("stt")
        goc.removeAllViews()
        val muc = p.optString("muc")
        val (len, tong) = camLen(p)
        val dau = LinearLayout(this)
        dau.orientation = LinearLayout.HORIZONTAL
        dau.gravity = Gravity.CENTER_VERTICAL
        dau.addView(Button(this).apply { text = "‹ Lưới"; isAllCaps = false; setOnClickListener { veLuoi() } })
        dau.addView(chu("Điểm ${p.optString("stt")}. ${p.optString("ten")} · lên $len/$tong", 15f, true, "#E7EDF2").apply { setPadding(dp(8), 0, 0, 0) }, LinearLayout.LayoutParams(0, -2, 1f))
        goc.addView(dau)
        goc.addView(chu("${p.optString("domain")} → ${p.optString("ip")} · ${p.optString("tong")}", 12f, false, "#9AA8B5").apply { setPadding(dp(4), 0, dp(4), dp(6)) })
        val diemThat = p.optString("diem_that")
        if (diemThat.isNotEmpty()) goc.addView(chu("🔁 " + (p.optJSONArray("canh_bao")?.optString(0) ?: "Tên miền này hiện trỏ về thiết bị của điểm $diemThat"), 12f, true, "#FFD27A").apply { setPadding(dp(4), 0, dp(4), dp(6)) })
        val lmStt = p.optString("lm_stt")
        if (lmStt.isNotEmpty()) {
            val chac = p.optBoolean("lm_chac", true)
            val hangLm = LinearLayout(this)
            hangLm.orientation = LinearLayout.HORIZONTAL
            hangLm.gravity = Gravity.CENTER_VERTICAL
            hangLm.addView(chu((if (chac) "📍 Ghim LiteMark $lmStt" else "⚠ Ghim LiteMark $lmStt — CHƯA CHẮC (cách toạ độ Excel ${p.optInt("lm_kc")} m)") +
                "\nSo hình live với ảnh khảo sát LiteMark: đúng chỗ thì thôi, sai thì chọn lại ghim.", 11f, false, if (chac) "#9AA8B5" else "#FFD27A").apply { setPadding(dp(4), 0, dp(4), dp(4)) }, LinearLayout.LayoutParams(0, -2, 1f))
            hangLm.addView(Button(this).apply { text = "🧭 Xác minh"; isAllCaps = false; textSize = 12f; setOnClickListener { startActivity(Intent(this@GiamSatActivity, XacMinhActivity::class.java).putExtra("ma", ma)) } })
            goc.addView(hangLm)
            val anhLm = p.optString("lm_anh")
            if (anhLm.isNotEmpty()) {
                val iv = android.widget.ImageView(this)
                iv.scaleType = android.widget.ImageView.ScaleType.CENTER_CROP
                goc.addView(iv, LinearLayout.LayoutParams(-1, dp(110)).apply { setMargins(dp(4), 0, dp(4), dp(4)) })
                Thread { try { val bm = android.graphics.BitmapFactory.decodeStream(java.net.URL(anhLm).openStream()); runOnUiThread { iv.setImageBitmap(bm) } } catch (_: Exception) {} }.start()
                goc.addView(chu("↑ ảnh khảo sát LiteMark tại ghim $lmStt", 10f, false, "#9AA8B5").apply { setPadding(dp(4), 0, dp(4), dp(6)) })
            }
        }
        val cs = p.optJSONArray("cam") ?: JSONArray()
        val o = GridLayout(this)
        // 1–2 cam: mỗi cam một hàng, khung rộng hết màn (16:9); 3 cam trở lên: 2 cột. Chiều cao chia theo phần màn còn trống.
        val cot = if (cs.length() <= 2) 1 else 2
        val hangSo = (cs.length() + cot - 1) / cot
        o.columnCount = cot
        val dm = resources.displayMetrics
        val rongDp = (dm.widthPixels / dm.density).toInt() - 16 - cot * 14
        val caoTrong = (dm.heightPixels / dm.density).toInt() - 300 - (if (lmStt.isNotEmpty()) 60 else 0)
        val cao = minOf(rongDp / cot * 9 / 16, maxOf(120, caoTrong / maxOf(1, hangSo) - 48)).coerceAtLeast(110)
        var soPhat = 0
        for (i in 0 until cs.length()) {
            val c = cs.getJSONObject(i)
            val oCam = LinearLayout(this)
            oCam.orientation = LinearLayout.VERTICAL
            oCam.background = GradientDrawable().apply { setColor(Color.parseColor("#172029")); cornerRadius = dp(6).toFloat(); setStroke(dp(1), Color.parseColor(mauVien[c.optString("muc")] ?: "#5B6776")) }
            oCam.setPadding(dp(4), dp(4), dp(4), dp(4))
            oCam.addView(chu("Cam ${c.optInt("so")} · port ${c.optInt("http")} · ${c.optString("nhan")}", 12f, true, "#E7EDF2").apply { maxLines = 2 })
            val khung = FrameLayout(this)
            khung.setBackgroundColor(Color.BLACK)
            oCam.addView(khung, LinearLayout.LayoutParams(-1, dp(cao)))
            val tt = chu("", 11f, false, "#9AA8B5")
            oCam.addView(tt)
            if (c.optString("muc") == "xanh" && c.optString("live").isNotEmpty() && soPhat < 4) {
                soPhat++
                val lichSu = c.optString("tu_lich_su")
                if (lichSu.isNotEmpty()) oCam.addView(chu("↺ lấy từ lần kiểm $lichSu — live lên = còn tốt; không lên thì bấm Chi tiết / sửa → kiểm lại", 10f, false, "#9AA8B5"), 1)
                // Không tự quét lại cả điểm khi hình rớt (dồn việc lên cam đúng lúc cam yếu) — bộ phát tự gõ cửa nhẹ tới khi cam lên
                boPhat.phat(khung, c.optString("live"), tt, cao)
            } else {
                khung.setBackgroundColor(Color.parseColor("#5A1F1A"))
                val ly = c.optString("nguyen_nhan").take(140)
                khung.addView(chu("✖ ${c.optString("nhan")}\n$ly", 12f, true, "#FFFFFF").apply { gravity = Gravity.CENTER; setPadding(dp(8), dp(8), dp(8), dp(8)) }, FrameLayout.LayoutParams(-1, -1))
                val v = c.optJSONArray("viec")
                tt.text = if (v != null && v.length() > 0) "→ ${v.getString(0)}" else ""
                tt.setTextColor(Color.parseColor("#FFB4A8"))
                val hd = c.optJSONArray("hanh_dong")
                if (hd != null) for (j in 0 until hd.length()) {
                    val h = hd.getJSONObject(j)
                    oCam.addView(Button(this).apply {
                        text = h.optString("ten"); isAllCaps = false; textSize = 12f
                        setOnClickListener { hanhDong(p, c, h.optString("id")) }
                    })
                }
            }
            o.addView(oCam, GridLayout.LayoutParams(GridLayout.spec(GridLayout.UNDEFINED, 1f), GridLayout.spec(GridLayout.UNDEFINED, 1f)).apply { width = 0; setMargins(dp(3), dp(3), dp(3), dp(3)) })
        }
        goc.addView(o)
        // ---- thanh nút dưới đáy: luôn trong tầm ngón tay, không trôi theo nội dung
        duoi.removeAllViews(); duoi.visibility = View.VISIBLE
        fun nutDuoi(t: String, chinh: Boolean = false, bam: () -> Unit) = Button(this).apply {
            text = t; isAllCaps = false; textSize = 14f; minHeight = dp(48); setPadding(dp(4), 0, dp(4), 0)
            background = GradientDrawable().apply { setColor(Color.parseColor(if (chinh) "#1D7A46" else "#2A3642")); cornerRadius = dp(8).toFloat() }
            setTextColor(Color.WHITE)
            setOnClickListener { bam() }
        }
        fun lp() = LinearLayout.LayoutParams(0, -2, 1f).apply { setMargins(dp(3), dp(3), dp(3), dp(3)) }
        val h1 = LinearLayout(this); h1.orientation = LinearLayout.HORIZONTAL
        val h2 = LinearLayout(this); h2.orientation = LinearLayout.HORIZONTAL
        h1.addView(nutDuoi("📈 Theo dõi", true) { chonCamTheoDoi(p) }, lp())
        val mapUrl = p.optString("map")
        val lmLink = p.optString("lm_link")
        if (mapUrl.isNotEmpty()) h1.addView(nutDuoi("📍 Dẫn đường") { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(mapUrl))) }, lp())
        if (lmLink.isNotEmpty()) h1.addView(nutDuoi("🔗 LiteMark") { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(lmLink))) }, lp())
        h2.addView(nutDuoi("📋 Chi tiết / sửa") { setResult(RESULT_OK, Intent().putExtra("stt", p.optString("stt"))); finish() }, lp())
        h2.addView(nutDuoi("✕ Đóng") { veLuoi() }, lp())
        duoi.addView(h1); duoi.addView(h2)
    }

    /** Theo dõi: 1 cam thì vào thẳng; nhiều cam thì chọn cam (ghi rõ cam nào đang được theo dõi). */
    private fun chonCamTheoDoi(p: JSONObject) {
        val cs = p.optJSONArray("cam") ?: JSONArray()
        if (cs.length() == 0) return
        if (cs.length() == 1) { TheoDoi.bam(this, ma, p, cs.getJSONObject(0), kq.optString("du_an")); return }
        val dang = TheoDoi.ds().let { a -> (0 until a.length()).map { a.getJSONObject(it) }
            .filter { it.optString("trang_thai") == "dang" && it.optString("domain") == p.optString("domain") }.map { it.optInt("http") }.toSet() }
        val nhan = (0 until cs.length()).map { i -> val c = cs.getJSONObject(i)
            "Cam ${c.optInt("so")} · port ${c.optInt("http")} · ${c.optString("nhan")}" + if (c.optInt("http") in dang) "  — đang theo dõi" else "" }
        AlertDialog.Builder(this).setTitle("Theo dõi cam nào?")
            .setItems(nhan.toTypedArray()) { _, i -> TheoDoi.bam(this, ma, p, cs.getJSONObject(i), kq.optString("du_an")) }
            .setNegativeButton("Huỷ", null).show()
    }

    private val daXacMinh = HashSet<String>()

    /** Đọc trạng thái bộ phát (chạy trên luồng giao diện) từ luồng nền. */
    private fun runOnUiThreadKq(f: () -> Boolean): Boolean {
        val q = java.util.concurrent.ArrayBlockingQueue<Boolean>(1)
        runOnUiThread { q.offer(try { f() } catch (_: Exception) { false }) }
        return q.poll(3, java.util.concurrent.TimeUnit.SECONDS) ?: false
    }

    /** Người dùng chốt điểm này là ghim LiteMark nào (sau khi so live với ảnh khảo sát). */
    private fun chonGhim(p: JSONObject) {
        val ds = p.optJSONArray("lm_ghim") ?: return
        val nhan = (0 until ds.length()).map { i -> val g = ds.getJSONArray(i); "Ghim ${g.getString(0)} — ${g.getString(1)}" }
        AlertDialog.Builder(this).setTitle("Điểm ${p.optString("stt")} «${p.optString("ten")}» thực tế là ghim LiteMark nào?")
            .setItems(nhan.toTypedArray()) { _, i ->
                val lm = ds.getJSONArray(i).getString(0)
                Thread {
                    try {
                        val core = com.chaquo.python.Python.getInstance().getModule("camlink_core")
                        core.callAttr("lm_dat_ghim", ma, p.optString("stt"), lm, null)
                        p.put("lm_stt", lm); p.put("lm_chac", true)
                        runOnUiThread { Toast.makeText(this, "Đã chốt: điểm ${p.optString("stt")} = ghim LiteMark $lm. Kiểm tra lại để LiteMark nhận đúng điểm.", Toast.LENGTH_LONG).show(); moDiem(p) }
                    } catch (e: Exception) { runOnUiThread { Toast.makeText(this, "Lỗi: ${e.message?.take(100)}", Toast.LENGTH_LONG).show() } }
                }.start()
            }.setNegativeButton("Huỷ", null).show()
    }

    /** Cam lấy từ lịch sử mà live không lên → kiểm đầy đủ lại điểm đó ngay (một lần), cập nhật ô. */
    private fun xacMinhDiem(p: JSONObject) {
        val stt = p.optString("stt")
        if (!daXacMinh.add(stt)) return
        Toast.makeText(this, "Điểm $stt: live không lên → đang kiểm lại điểm này…", Toast.LENGTH_SHORT).show()
        Thread {
            try {
                val core = com.chaquo.python.Python.getInstance().getModule("camlink_core")
                val moi = JSONObject(core.callAttr("tuxa_kiem_diem", ma, stt, null).toString())
                // Video là sự thật: cam vừa có hình trong 90 giây thì giữ "lên", không để kết quả quét (vd báo sai user/pass lúc cam bận) đè lên
                val cu = p.optJSONArray("cam") ?: JSONArray()
                val csMoi = moi.optJSONArray("cam") ?: JSONArray()
                for (i in 0 until csMoi.length()) {
                    val c = csMoi.getJSONObject(i)
                    val ccu = (0 until cu.length()).map { cu.getJSONObject(it) }.firstOrNull { it.optInt("http") == c.optInt("http") } ?: continue
                    if (c.optString("muc") != "xanh" && ccu.optString("live").isNotEmpty() && runOnUiThreadKq { boPhat.vuaCoHinh(ccu.optString("live")) })
                        csMoi.put(i, ccu.put("ghi_chu_quet", c.optString("nhan")))
                }
                val ds = kq.optJSONArray("diem")!!
                for (i in 0 until ds.length()) if (ds.getJSONObject(i).optString("stt") == stt) ds.put(i, moi)
                File(intent.getStringExtra("file")!!).writeText(kq.toString())
                runOnUiThread { if (dangMo == stt) moDiem(moi) }
            } catch (e: Exception) { runOnUiThread { Toast.makeText(this, "Kiểm lại điểm $stt lỗi: ${e.message?.take(80)}", Toast.LENGTH_LONG).show() } }
        }.start()
    }

    private fun hanhDong(p: JSONObject, c: JSONObject, id: String) {
        val core = com.chaquo.python.Python.getInstance().getModule("camlink_core")
        val stt = p.optString("stt")
        AlertDialog.Builder(this).setTitle("Xác nhận").setMessage("Điểm $stt, cam ${c.optInt("so")} (port ${c.optInt("http")}): ${(c.optJSONArray("hanh_dong")?.let { a -> (0 until a.length()).map { a.getJSONObject(it) }.firstOrNull { it.optString("id") == id }?.optString("ten") }) ?: id}?\nApp sẽ ghi vào hồ sơ và kiểm lại điểm này.")
            .setPositiveButton("Đúng") { _, _ ->
                Thread {
                    try {
                        val moi = JSONObject(core.callAttr("tuxa_hanh_dong", ma, stt, c.optInt("so"), c.optInt("http"), id, kq.toString(), null).toString())
                        val ds = kq.optJSONArray("diem")!!
                        for (i in 0 until ds.length()) if (ds.getJSONObject(i).optString("stt") == stt) ds.put(i, moi)
                        File(intent.getStringExtra("file")!!).writeText(kq.toString())
                        runOnUiThread { moDiem(moi) }
                    } catch (e: Exception) { runOnUiThread { AlertDialog.Builder(this).setMessage("Lỗi: ${e.message}").setPositiveButton("Đóng", null).show() } }
                }.start()
            }.setNegativeButton("Huỷ", null).show()
    }

    override fun onBackPressed() { if (dangMo != null) veLuoi() else super.onBackPressed() }
    override fun onPause() { boPhat.tamDung(); super.onPause() }
    override fun onResume() { boPhat.tiepTuc(); super.onResume() }
    override fun onDestroy() { boPhat.dungHet(); super.onDestroy() }
}
