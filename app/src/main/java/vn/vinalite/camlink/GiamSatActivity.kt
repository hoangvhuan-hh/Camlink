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
 * MÀN HÌNH GIÁM SÁT TRỰC TIẾP (2.0 — Huan 10/11): MỘT màn cho mọi cam.
 *  - Mọi ô có TRẠNG THÁI ĐO TRỰC TIẾP: hỏi nhẹ trang web từng cam mỗi 30 giây (~0,5 KB) → xanh / vàng (chập chờn) / đỏ + "đo Xs trước".
 *  - Video LUỒNG PHỤ tự phát ở các ô đang hiện trên màn (tối đa 4 khi Wi-Fi, 2 khi 4G); cuộn khuất là tắt → nhẹ app, nhẹ cam.
 *  - Rớt ≥ 5 phút → ghi vào kết quả + đẩy ghim LiteMark; lên lại → gỡ. Chạm ô → phóng to. Kiểm tra sâu là bước sau.
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
        cuon = ScrollView(this).apply { isFillViewport = true; setBackgroundColor(Color.parseColor("#0F161C")); addView(goc) }
        cuon.viewTreeObserver.addOnScrollChangedListener { ui.removeCallbacks(chonVideoR); ui.postDelayed(chonVideoR, 400) }
        nen.addView(cuon, LinearLayout.LayoutParams(-1, 0, 1f))
        nen.addView(duoi, LinearLayout.LayoutParams(-1, -2))
        setContentView(nen)
        veLuoi()
    }

    private lateinit var cuon: ScrollView
    private val ui = android.os.Handler(android.os.Looper.getMainLooper())

    private fun diemList(): List<JSONObject> {
        val ds = kq.optJSONArray("diem") ?: JSONArray()
        return (0 until ds.length()).map { ds.getJSONObject(it) }.sortedBy { it.optString("stt").toIntOrNull() ?: 9999 }
    }

    private fun camLen(p: JSONObject) = (p.optJSONArray("cam") ?: JSONArray()).let { cs ->
        (0 until cs.length()).count { cs.getJSONObject(it).optString("muc") == "xanh" } to cs.length()
    }

    // ---------------- TRẠNG THÁI TRỰC TIẾP (nguồn sự thật của màn này) ----------------
    private class TT { var tt = ""; var luc = 0L; var hong = 0; var rotTu = 0L; var daBao = false; var ly = ""; var videoHong = 0; var thuVideoSau = 0L }
    private class O(val khung: FrameLayout, val nhan: TextView, val bm: android.graphics.Bitmap?, val p: JSONObject, val c: JSONObject)
    private val ttCam = HashMap<String, TT>()                 // "stt:http"
    private val oLuoi = LinkedHashMap<String, O>()
    private val theDiem = HashMap<String, Pair<LinearLayout, TextView>>()
    private val dangPhatO = HashSet<String>()
    private val dangHoiPhu = HashSet<String>()
    private var tieuDe: TextView? = null
    @Volatile private var dangDo = false
    private var dangMoMan = false
    private fun khoa(p: JSONObject, c: JSONObject) = "${p.optString("stt")}:${c.optInt("http")}"
    private val nhipDo = object : Runnable { override fun run() { doTatCa(); ui.postDelayed(this, 30_000) } }
    private val chonVideoR = Runnable { chonVideo() }
    private val dongHo = object : Runnable { override fun run() { if (dangMo == null) capNhatLuoi(); ui.postDelayed(this, 5_000) } }

    /** Hỏi 1 trang web của cam (không đăng nhập): trả lời = lên; nhận kết nối mà câm 10 giây = treo. */
    private fun hoiWeb(host: String, port: Int): String = try {
        java.net.Socket().use { sk ->
            try { sk.connect(java.net.InetSocketAddress(host, port), 4000) }
            catch (e: java.net.ConnectException) { return "tu_choi" }
            sk.soTimeout = 10_000
            sk.getOutputStream().write("GET / HTTP/1.0\r\nHost: $host:$port\r\nConnection: close\r\n\r\n".toByteArray())
            if (sk.getInputStream().read(ByteArray(16)) > 0) "mo" else "treo"
        }
    } catch (_: java.net.SocketTimeoutException) { "treo_hoac_im" } catch (_: Exception) { "im_lang" }

    private fun moTa(k: String) = when (k) {
        "treo", "treo_hoac_im" -> "cam treo / không trả lời"
        "tu_choi" -> "port bị từ chối (thiếu NAT / sai IP)"
        else -> "không trả lời (mất mạng / mất nguồn)"
    }

    private fun mangWifi(): Boolean = try {
        val cm = getSystemService(android.net.ConnectivityManager::class.java)
        cm.getNetworkCapabilities(cm.activeNetwork)?.hasTransport(android.net.NetworkCapabilities.TRANSPORT_WIFI) == true
    } catch (_: Exception) { false }

    private fun doTatCa() {
        if (dangDo || !dangMoMan) return
        dangDo = true
        val viec = oLuoi.map { (k, o) -> Triple(k, o.p.optString("domain"), o.c.optInt("http")) }
        val coHinh = oLuoi.filter { (_, o) -> boPhat.dangPhat(o.khung) }.keys
        Thread {
            val kqDo = java.util.concurrent.ConcurrentHashMap<String, String>()
            val pool = java.util.concurrent.Executors.newFixedThreadPool(6)
            for ((k, host, port) in viec) {
                if (k in coHinh) { kqDo[k] = "xem"; continue }     // đang có hình = sự thật, không hỏi cam thêm
                pool.execute { kqDo[k] = hoiWeb(host, port) }
            }
            pool.shutdown(); pool.awaitTermination(40, java.util.concurrent.TimeUnit.SECONDS)
            ui.post { apDung(kqDo); dangDo = false }
        }.start()
    }

    private fun apDung(kqDo: Map<String, String>) {
        val now = System.currentTimeMillis()
        for ((k, r) in kqDo) {
            val o = oLuoi[k] ?: continue
            val t = ttCam.getOrPut(k) { TT() }
            t.luc = now
            if (r == "mo" || r == "xem") {
                if (t.daBao) baoLm(o, "len", t)
                t.hong = 0; t.rotTu = 0; t.daBao = false
                if (t.videoHong == 0) { t.tt = "xanh"; t.ly = "" }
            } else {
                t.hong++
                if (t.hong == 1) { t.rotTu = now; t.tt = "vang"; t.ly = "chập chờn — ${moTa(r)}" }
                else { t.tt = "do"; t.ly = moTa(r) }
                if (t.tt == "do" && !t.daBao && now - t.rotTu >= 5 * 60_000) { t.daBao = true; baoLm(o, "rot", t) }
                if (dangPhatO.remove(k)) tatO(o)
            }
        }
        if (dangMo == null) { capNhatLuoi(); chonVideo() }
    }

    /** Rớt ≥ 5 phút / lên lại → ghi kết quả + đẩy ghim LiteMark (chung đường với Theo dõi). */
    private fun baoLm(o: O, kieu: String, t: TT) {
        val b = JSONObject().put("kieu", kieu).put("stt", o.p.optString("stt")).put("so", o.c.optInt("so")).put("http", o.c.optInt("http"))
            .put("bd", t.rotTu / 1000.0).put("nguyen_nhan", t.ly).put("dur", (System.currentTimeMillis() - t.rotTu) / 1000.0)
        Thread { try { com.chaquo.python.Python.getInstance().getModule("camlink_core").callAttr("truc_tiep_bao", ma, b.toString()) } catch (_: Exception) {} }.start()
    }

    private fun capNhatLuoi() {
        val now = System.currentTimeMillis()
        var len = 0; var tong = 0; var cuNhat = 0L
        val mauDiem = HashMap<String, String>()
        for ((k, o) in oLuoi) {
            tong++
            val t = ttCam[k]
            val stt = o.p.optString("stt")
            val tt = t?.tt ?: ""
            if (tt == "xanh") len++
            if (t != null) cuNhat = if (cuNhat == 0L) t.luc else minOf(cuNhat, t.luc)
            val tuoi = t?.let { ((now - it.luc) / 1000).toInt() }
            val dangHinh = k in dangPhatO && boPhat.dangPhat(o.khung)
            o.nhan.text = "C${o.c.optInt("so")} " + when (tt) {
                "xanh" -> if (dangHinh) "🔴 trực tiếp" else "● ${tuoi}s"
                "vang" -> "◐ ${t?.ly}"
                "do" -> "✖ ${t?.ly} · từ ${java.text.SimpleDateFormat("HH:mm").format(java.util.Date(t!!.rotTu))}"
                else -> "· đang đo…"
            }
            o.nhan.setBackgroundColor(Color.parseColor(when (tt) { "xanh" -> "#B01D7A46"; "vang" -> "#B0A86F00"; "do" -> "#C0B42318"; else -> "#80000000" }))
            val m = mauDiem[stt]
            mauDiem[stt] = when { tt == "do" || m == "do" -> "do"; tt == "vang" || m == "vang" -> "vang"; tt == "" || m == "" -> ""; else -> "xanh" }
        }
        for ((stt, the) in theDiem) {
            val muc = mauDiem[stt] ?: ""
            the.first.background = GradientDrawable().apply { setColor(Color.parseColor("#172029")); cornerRadius = dp(8).toFloat(); setStroke(dp(2), Color.parseColor(mauVien[muc] ?: "#5B6776")) }
            val cs = oLuoi.filter { it.value.p.optString("stt") == stt }
            val l = cs.keys.count { ttCam[it]?.tt == "xanh" }
            the.second.text = "Điểm $stt · $l/${cs.size} lên · ${cs.values.first().p.optString("ten")}"
            the.second.setTextColor(Color.parseColor(when (muc) { "xanh" -> "#7ED6A0"; "vang" -> "#FFD166"; "do" -> "#FF8A80"; else -> "#E7EDF2" }))
        }
        tieuDe?.text = "${kq.optString("du_an")} · $len/$tong cam lên · TRỰC TIẾP" +
            (if (cuNhat > 0) " (đo ${((now - cuNhat) / 1000)}s trước)" else " (đang đo…)")
    }

    /** Video luồng phụ cho các ô ĐANG HIỆN trên màn, tối đa 4 (Wi-Fi) / 2 (4G). Ô khuất tắt ngay. */
    private fun chonVideo() {
        if (!dangMoMan || dangMo != null) return
        val toiDa = if (mangWifi()) 4 else 2
        val r = android.graphics.Rect()
        val hien = oLuoi.filter { (_, o) -> o.khung.getLocalVisibleRect(r) && r.height() >= o.khung.height / 2 }.keys
        for (k in dangPhatO.toList()) if (k !in hien) { dangPhatO.remove(k); oLuoi[k]?.let { tatO(it) } }
        val now = System.currentTimeMillis()
        for (k in hien) {
            if (dangPhatO.size >= toiDa) break
            if (k in dangPhatO) continue
            val o = oLuoi[k] ?: continue
            val t = ttCam[k] ?: continue
            if (t.tt == "do" || t.hong > 0 || now < t.thuVideoSau) continue
            val phu = o.c.optString("live_phu")
            if (phu.isEmpty()) {
                if (o.c.optBoolean("live_phu_da_hoi")) continue          // cam không có luồng phụ → chỉ ảnh, chạm để xem
                if (dangHoiPhu.add(k)) Thread {
                    val u = try { com.chaquo.python.Python.getInstance().getModule("camlink_core").callAttr("tuxa_luong_phu", ma, o.p.optString("stt"), o.c.optInt("http")).toString() } catch (_: Exception) { "" }
                    ui.post { if (u.isNotEmpty()) o.c.put("live_phu", u) else o.c.put("live_phu_da_hoi", true); dangHoiPhu.remove(k); chonVideo() }
                }.start()
                continue
            }
            dangPhatO.add(k)
            val caoDp = (o.khung.height / resources.displayMetrics.density).toInt().coerceAtLeast(60)
            boPhat.phat(o.khung, phu, TextView(this), caoDp, khiLoi = {
                // cam còn trả lời trang web mà không đẩy được video → nghẽn luồng/băng thông: thử thưa dần 30 s → 60 s → 120 s
                dangPhatO.remove(k); tatO(o)
                t.videoHong++
                t.thuVideoSau = System.currentTimeMillis() + 30_000L * (1 shl minOf(2, t.videoHong - 1))
                if (t.tt == "xanh") { t.tt = "vang"; t.ly = "còn sống nhưng không đẩy được video (nghẽn luồng/băng thông?)" }
                capNhatLuoi()
            }, tuGoCua = false)
            ui.postDelayed({ if (boPhat.dangPhat(o.khung)) { t.videoHong = 0; if (t.tt == "vang" && t.hong == 0) { t.tt = "xanh"; t.ly = "" }; capNhatLuoi() } }, 8000)
        }
        capNhatLuoi()
    }

    private fun tatO(o: O) {
        boPhat.tat(o.khung)
        o.khung.removeAllViews()
        if (o.bm != null) o.khung.addView(ImageView(this).apply { setImageBitmap(o.bm); scaleType = ImageView.ScaleType.CENTER_CROP }, FrameLayout.LayoutParams(-1, -1))
        o.khung.addView(o.nhan.also { (it.parent as? android.view.ViewGroup)?.removeView(it) }, FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM or Gravity.START))
    }

    // ---------------- LƯỚI TỔNG (trực tiếp) ----------------
    private fun veLuoi() {
        boPhat.dungHet(); dangMo = null
        dangPhatO.clear(); oLuoi.clear(); theDiem.clear()
        goc.removeAllViews()
        duoi.removeAllViews(); duoi.visibility = View.VISIBLE
        tieuDe = chu("", 15f, true, "#E7EDF2").apply { setPadding(dp(4), 0, dp(4), dp(2)) }
        goc.addView(tieuDe)
        goc.addView(chu("Xanh = trả lời trong lần đo gần nhất (30 giây/lần) · video luồng phụ ở ô đang hiện · chạm ô để phóng to", 10f, false, "#9AA8B5").apply { setPadding(dp(4), 0, dp(4), dp(6)) })
        val rong = (resources.displayMetrics.widthPixels / resources.displayMetrics.density).toInt() - 16
        for (p in diemList()) {
            val k = LinearLayout(this)
            k.orientation = LinearLayout.VERTICAL
            k.setPadding(dp(6), dp(6), dp(6), dp(6))
            val dau = chu("Điểm ${p.optString("stt")} · ${p.optString("ten")}", 13f, true, "#E7EDF2").apply { maxLines = 1; ellipsize = android.text.TextUtils.TruncateAt.END }
            k.addView(dau)
            theDiem[p.optString("stt")] = k to dau
            val cs = p.optJSONArray("cam") ?: JSONArray()
            val g = GridLayout(this)
            val cot = if (cs.length() <= 1) 1 else 2
            g.columnCount = cot
            val caoO = (rong - 12) / cot * 9 / 16
            for (i in 0 until cs.length()) {
                val c = cs.getJSONObject(i)
                val fr = FrameLayout(this)
                fr.setBackgroundColor(Color.BLACK)
                val anh = c.optString("anh")
                val bm = if (anh.isNotEmpty() && File(anh).exists()) try { BitmapFactory.decodeFile(anh, BitmapFactory.Options().apply { inSampleSize = 4 }) } catch (_: Exception) { null } else null
                val nhan = chu("C${c.optInt("so")} · đang đo…", 10f, true, "#FFFFFF").apply { setPadding(dp(4), dp(1), dp(4), dp(1)); maxLines = 2 }
                val o = O(fr, nhan, bm, p, c)
                oLuoi[khoa(p, c)] = o
                tatO(o)
                fr.setOnClickListener { moDiem(p) }
                g.addView(fr, GridLayout.LayoutParams(GridLayout.spec(GridLayout.UNDEFINED, 1f), GridLayout.spec(GridLayout.UNDEFINED, 1f)).apply { width = 0; height = dp(caoO); setMargins(dp(2), dp(2), dp(2), dp(2)) })
            }
            k.addView(g)
            k.setOnClickListener { moDiem(p) }
            goc.addView(k, LinearLayout.LayoutParams(-1, -2).apply { setMargins(0, dp(4), 0, dp(4)) })
        }
        // thanh dưới: kiểm tra sâu là BƯỚC SAU
        fun nut(t: String, bam: () -> Unit) = Button(this).apply {
            text = t; isAllCaps = false; textSize = 14f; minHeight = dp(46); setTextColor(Color.WHITE)
            background = GradientDrawable().apply { setColor(Color.parseColor("#2A3642")); cornerRadius = dp(8).toFloat() }
            setOnClickListener { bam() }
        }
        val h = LinearLayout(this); h.orientation = LinearLayout.HORIZONTAL
        val lp = { LinearLayout.LayoutParams(0, -2, 1f).apply { setMargins(dp(3), dp(3), dp(3), dp(3)) } }
        h.addView(nut("🔍 Kiểm tra sâu cả dự án") { setResult(RESULT_OK, Intent().putExtra("kiem_sau", true)); finish() }, lp())
        h.addView(nut("📈 Theo dõi") { TheoDoi.danhSach(this) }, lp())
        duoi.addView(h)
        capNhatLuoi()
        ui.removeCallbacks(nhipDo); ui.post(nhipDo)
        ui.postDelayed(chonVideoR, 600)
    }

    // ---------------- MỘT ĐIỂM: bấy nhiêu cam, bấy nhiêu ô phát trực tiếp ----------------
    private fun moDiem(p: JSONObject) {
        boPhat.dungHet(); dangMo = p.optString("stt"); dangPhatO.clear()
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
                val stt0 = p.optString("stt")
                ui.postDelayed({ if (dangMo == stt0) phatO(khung, c, tt, cao) }, 3000L * (soPhat - 1))   // mở lần lượt, không dồn luồng vào điểm
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
        h2.addView(nutDuoi("🔍 Kiểm tra sâu") { xacMinhDiem(p, true) }, lp())
        h2.addView(nutDuoi("📋 Chi tiết / sửa") { setResult(RESULT_OK, Intent().putExtra("stt", p.optString("stt"))); finish() }, lp())
        h2.addView(nutDuoi("✕ Đóng") { veLuoi() }, lp())
        duoi.addView(h1); duoi.addView(h2)
    }

    /** Theo dõi CẢ ĐIỂM: mọi cam đo chung một lượt, chung một báo cáo. */
    private fun chonCamTheoDoi(p: JSONObject) = TheoDoi.diem(this, ma, p, kq.optString("du_an"))

    private val daXacMinh = HashSet<String>()
    private val xemHd = HashSet<String>()     // cam người dùng chọn xem HD (luồng chính)

    /** Mặc định xem LUỒNG PHỤ (nhẹ 6–8 lần, không tranh băng thông với IOC); chạm khung để đổi HD ↔ luồng phụ. */
    private fun phatO(khung: FrameLayout, c: JSONObject, tt: TextView, cao: Int) {
        val chinh = c.optString("live"); val phu = c.optString("live_phu")
        val khoa = chinh
        fun chay() {
            val hd = phu.isEmpty() || xemHd.contains(khoa)
            boPhat.phat(khung, if (hd) chinh else phu, tt, cao,
                ghiChu = if (phu.isEmpty()) "" else if (hd) " · HD (chạm để xem nhẹ)" else " · luồng phụ (chạm để xem HD)")
        }
        if (phu.isNotEmpty()) khung.setOnClickListener { if (!xemHd.add(khoa)) xemHd.remove(khoa); chay() }
        chay()
    }

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
    private fun xacMinhDiem(p: JSONObject, chuDong: Boolean = false) {
        val stt = p.optString("stt")
        if (!daXacMinh.add(stt) && !chuDong) return
        Toast.makeText(this, "Điểm $stt: đang kiểm tra sâu (ONVIF, cấu hình)…", Toast.LENGTH_SHORT).show()
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
    override fun onPause() { dangMoMan = false; ui.removeCallbacks(nhipDo); ui.removeCallbacks(dongHo); boPhat.tamDung(); super.onPause() }
    override fun onResume() {
        TheoDoi.damBaoChay(this)
        super.onResume(); dangMoMan = true; boPhat.tiepTuc()
        ui.removeCallbacks(nhipDo); ui.post(nhipDo); ui.removeCallbacks(dongHo); ui.postDelayed(dongHo, 5_000)
    }
    override fun onDestroy() { ui.removeCallbacksAndMessages(null); boPhat.dungHet(); super.onDestroy() }
}
