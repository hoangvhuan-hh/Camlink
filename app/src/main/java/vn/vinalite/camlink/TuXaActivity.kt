package vn.vinalite.camlink

import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import android.view.View
import android.widget.Button
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.FileProvider
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.rtsp.RtspMediaSource
import androidx.media3.ui.PlayerView
import android.widget.FrameLayout
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import kotlin.concurrent.thread

/** Kiểm tra từ xa CẢ DỰ ÁN theo 5 tầng → bảng kết quả từng cam, link + user/pass, nút Sửa từ xa. */
class TuXaActivity : Activity() {
    private lateinit var core: PyObject
    private lateinit var khung: LinearLayout
    private lateinit var tienDo: TextView
    private val ui = Handler(Looper.getMainLooper())
    private var ma = ""
    private var tenDuAn = ""
    private var ketQua: JSONObject? = null
    private var dangChay = false
    private val maFile = 21
    private val dangPhat = java.util.LinkedHashMap<String, ExoPlayer>()   // url → player đang chạy
    private val cauRtsp = HashMap<String, RtspCau>()                      // url → cầu RTSP cục bộ
    private var mang4G: android.net.Network? = null
    private val vlcPlayers = java.util.LinkedHashMap<String, org.videolan.libvlc.MediaPlayer>()
    private var libVlc: org.videolan.libvlc.LibVLC? = null

    /** ĐỘNG CƠ 1 — libVLC (cùng lõi với VLC/IOC): chịu được SDP khai 127.0.0.1, Digest, H.264/H.265. */
    private fun phatVlc(khungAnh: FrameLayout, url: String, trangThai: TextView): Boolean {
        return try {
            val lib = libVlc ?: org.videolan.libvlc.LibVLC(this, arrayListOf("--rtsp-tcp", "--network-caching=600", "--no-drop-late-frames", "--no-skip-frames", "-vvv")).also { libVlc = it }
            vlcPlayers.remove(url)?.let { it.stop(); it.detachViews(); it.release() }
            while (vlcPlayers.size >= TOI_DA_LIVE) { val k = vlcPlayers.keys.first(); vlcPlayers.remove(k)?.let { it.stop(); it.detachViews(); it.release() } }
            khungAnh.removeAllViews()
            val layout = org.videolan.libvlc.util.VLCVideoLayout(this)
            khungAnh.addView(layout, FrameLayout.LayoutParams(-1, dp(220)))
            val mp = org.videolan.libvlc.MediaPlayer(lib)
            mp.attachViews(layout, null, false, false)
            val media = org.videolan.libvlc.Media(lib, Uri.parse(url))
            media.setHWDecoderEnabled(true, false)
            media.addOption(":rtsp-tcp")
            media.addOption(":network-caching=600")
            mp.media = media; media.release()
            val t0 = System.currentTimeMillis()
            mp.setEventListener { ev ->
                when (ev.type) {
                    org.videolan.libvlc.MediaPlayer.Event.Opening -> trangThai.text = "⏳ libVLC đang kết nối…"
                    org.videolan.libvlc.MediaPlayer.Event.Buffering -> if (ev.buffering < 100f) trangThai.text = "⏳ libVLC đang tải ${ev.buffering.toInt()}%"
                    org.videolan.libvlc.MediaPlayer.Event.Vout -> { trangThai.text = "🔴 TRỰC TIẾP (libVLC) — ${java.text.SimpleDateFormat("HH:mm:ss").format(java.util.Date())} — sau ${(System.currentTimeMillis() - t0) / 1000}s"; trangThai.setTextColor(Color.parseColor("#1D7A46")) }
                    org.videolan.libvlc.MediaPlayer.Event.EncounteredError -> {
                        trangThai.text = "libVLC không phát được → chuyển sang động cơ 2 (ExoPlayer qua cầu)…"
                        ui.postDelayed({ phatLive(khungAnh, url, trangThai, tcp = true, dungVlc = false) }, 300)
                    }
                    org.videolan.libvlc.MediaPlayer.Event.EndReached -> trangThai.text = "Luồng kết thúc"
                }
            }
            mp.play()
            vlcPlayers[url] = mp
            true
        } catch (e: Throwable) {
            trangThai.text = "libVLC không khởi động được (${e.javaClass.simpleName}) → dùng động cơ 2…"
            false
        }
    }
    private val TOI_DA_LIVE = 4
    private val boPhat by lazy { BoPhat(this) }   // CÙNG bộ phát với màn giám sát (đã xem được thật)

    /** Phát trực tiếp RTSP ngay trong thẻ cam. Quá TOI_DA_LIVE thì dừng cái cũ nhất. */
    private fun phatLive(khungAnh: FrameLayout, url: String, trangThai: TextView, tcp: Boolean = true, dungVlc: Boolean = true) {
        if (url.isEmpty()) { trangThai.text = "Không có link video"; return }
        if (dungVlc) { boPhat.phat(khungAnh, url, trangThai, if (khungAnh.height > dp(60)) (khungAnh.height / resources.displayMetrics.density).toInt() else 200); return }
        dangPhat.remove(url)?.release()
        cauRtsp.remove(url)?.tat()
        while (dangPhat.size >= TOI_DA_LIVE) { val k = dangPhat.keys.first(); dangPhat.remove(k)?.release(); cauRtsp.remove(k)?.tat() }
        // cầu RTSP: tránh cam quảng bá 127.0.0.1/IP LAN trong luồng, và ép đi 4G nếu có
        val u = Uri.parse(url)
        val cau = RtspCau(u.host ?: "", if (u.port > 0) u.port else 554, mang4G)
        cau.bat()
        cauRtsp[url] = cau
        val urlPhat = cau.doiUrl(url)
        khungAnh.removeAllViews()
        val pv = PlayerView(this)
        pv.useController = false
        khungAnh.addView(pv, FrameLayout.LayoutParams(-1, dp(200)))
        val p = ExoPlayer.Builder(this).build()
        pv.player = p
        p.setMediaSource(RtspMediaSource.Factory().setForceUseRtpTcp(true).setDebugLoggingEnabled(true).createMediaSource(MediaItem.fromUri(urlPhat)))
        p.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                trangThai.text = when (state) {
                    Player.STATE_BUFFERING -> "⏳ Đang tải hình trực tiếp…"
                    Player.STATE_READY -> "🔴 TRỰC TIẾP qua tên miền — ${java.text.SimpleDateFormat("HH:mm:ss").format(java.util.Date())}"
                    Player.STATE_ENDED -> "Luồng đã dừng"
                    else -> trangThai.text
                }
            }
            override fun onPlayerError(error: PlaybackException) {
                var ng: Throwable? = error
                val chuoi = StringBuilder()
                while (ng != null) { chuoi.append(ng.javaClass.simpleName).append(": ").append(ng.message ?: "").append(" ← "); ng = ng.cause }
                val ct = chuoi.toString().trimEnd(' ', '←')
                if (tcp) {
                    trangThai.text = "⏳ Lần 1 lỗi ($ct) — thử lại…"
                    ui.postDelayed({ phatLive(khungAnh, url, trangThai, tcp = false) }, 800)
                    return
                }
                val cauHienTai = cauRtsp[url]
                val nk = cauHienTai?.nhatKy?.toString()?.take(1500) ?: ""
                trangThai.text = "✖ Cả 2 động cơ đều không phát được.\nChi tiết ExoPlayer: $ct\n" +
                    "CHẨN ĐOÁN: URL đưa vào ExoPlayer = ${urlPhat.replace(Regex("//[^@/]*@"), "//")} · cầu nghe cổng ${cauHienTai?.cong} · " +
                    "kết nối vào cầu: ${cauHienTai?.soKetNoi ?: 0} · 4G: ${if (mang4G != null) "có" else "không"}\n" +
                    (if (nk.isNotEmpty()) "Hội thoại với cam:\n$nk\n" else "Trình phát KHÔNG nối vào cầu.\n") +
                    "Bấm nút để mở bằng VLC/app khác."
                trangThai.setTextIsSelectable(true)
                trangThai.setTextColor(Color.parseColor("#B42318"))
                khungAnh.removeAllViews()
                val b = Button(this@TuXaActivity)
                b.text = "▶ Mở bằng VLC / app khác"
                b.isAllCaps = false
                b.setOnClickListener {
                    try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).setDataAndType(Uri.parse(url), "video/*")) }
                    catch (e: Exception) { copy(url); Toast.makeText(this@TuXaActivity, "Chưa có app phát RTSP (cài VLC). Đã copy link.", Toast.LENGTH_LONG).show() }
                }
                khungAnh.addView(b, FrameLayout.LayoutParams(-2, -2, android.view.Gravity.CENTER))
            }
        })
        p.prepare(); p.playWhenReady = true
        dangPhat[url] = p
    }

    override fun onDestroy() {
        boPhat.dungHet()
        dangPhat.values.forEach { it.release() }; dangPhat.clear(); cauRtsp.values.forEach { it.tat() }; cauRtsp.clear()
        vlcPlayers.values.forEach { it.stop(); it.detachViews(); it.release() }; vlcPlayers.clear(); libVlc?.release(); libVlc = null
        super.onDestroy()
    }
    override fun onPause() { boPhat.tamDung(); dangPhat.values.forEach { it.pause() }; vlcPlayers.values.forEach { it.pause() }; super.onPause() }
    override fun onResume() { boPhat.tiepTuc(); dangPhat.values.forEach { it.play() }; vlcPlayers.values.forEach { it.play() }; super.onResume() }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private lateinit var thanhTienDo: android.widget.ProgressBar
    private lateinit var chuTienDo: TextView

    inner class NhatKy {
        fun ghi(s: String) {
            if (s.startsWith("TIEN_DO ")) {   // "TIEN_DO 27|Lượt 1: xong 3/11 điểm"
                val pct = s.substring(8).substringBefore("|").trim().toIntOrNull() ?: return
                val chu = s.substringAfter("|", "")
                ui.post {
                    thanhTienDo.visibility = if (pct >= 100) View.GONE else View.VISIBLE
                    chuTienDo.visibility = thanhTienDo.visibility
                    thanhTienDo.progress = pct
                    chuTienDo.text = "$pct% · $chu"
                }
                return
            }
            ui.post { tienDo.text = s.trim() }
        }
    }

    private val nk = NhatKy()

    private fun chu(s: String, co: Float = 14f, dam: Boolean = false, mau: String = "#17202B"): TextView {
        val t = TextView(this)
        t.text = s
        t.textSize = co
        t.setTextColor(Color.parseColor(mau))
        if (dam) t.setTypeface(null, Typeface.BOLD)
        return t
    }

    private fun the(vien: String, nen: String = "#FFFFFF"): LinearLayout {
        val l = LinearLayout(this)
        l.orientation = LinearLayout.VERTICAL
        l.setPadding(dp(12), dp(10), dp(12), dp(10))
        l.background = GradientDrawable().apply {
            setColor(Color.parseColor(nen)); cornerRadius = dp(10).toFloat(); setStroke(dp(2), Color.parseColor(vien))
        }
        val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
        lp.topMargin = dp(10)
        l.layoutParams = lp
        return l
    }

    private fun link(s: String, bam: () -> Unit): TextView {
        val t = TextView(this)
        t.text = android.text.SpannableString(s).apply { setSpan(android.text.style.UnderlineSpan(), 0, s.length, 0) }
        t.textSize = 15f
        t.setTextColor(Color.parseColor("#0B57D0"))
        t.setPadding(0, dp(6), 0, dp(6))
        t.setOnClickListener { bam() }
        return t
    }

    // ---------------- LiteMark: lấy ghim thực tế, đẩy cảnh báo lên bản đồ công trình ----------------
    private fun liteMark() {
        if (ma.isEmpty()) { Toast.makeText(this, "Chọn dự án trước", Toast.LENGTH_SHORT).show(); return }
        val tt = JSONObject(core.callAttr("lm_trang_thai", ma).toString())
        if (!tt.optBoolean("co_khoa")) { nhapKhoa(); return }
        val daNoi = tt.optString("ten").isNotEmpty()
        val dong = ArrayList<String>()
        dong.add(if (daNoi) "🔄 Đồng bộ lại ghim từ LiteMark" else "🔗 Chọn công trình LiteMark để nối")
        if (daNoi) { dong.add("🧭 Xác minh vị trí cam theo thực tế (ảnh / GPS)"); dong.add("🔁 Đổi sang công trình khác"); dong.add("🌐 Mở công trình trên LiteMark"); dong.add("✂ Ngắt nối (về toạ độ Excel)") }
        dong.add("📥 Nạp file tên miền (DDNS) của bên cấp")
        dong.add("🔑 Đổi khoá kết nối")
        val ghiChu = tt.optJSONArray("ghi_chu")?.let { a -> (0 until a.length()).joinToString("\n") { "· " + a.getString(it) } } ?: ""
        AlertDialog.Builder(this)
            .setTitle(if (daNoi) "LiteMark: «${tt.optString("ten")}»" else "LiteMark: dự án chưa nối")
            .setMessage(if (daNoi) "${tt.optInt("so_ghim")} ghim · đồng bộ ${tt.optString("luc_dong_bo")}\nBản đồ, dẫn đường, phiếu báo mạng đang dùng ghim LiteMark.\n$ghiChu".trim()
                        else "Chọn đúng công trình đã khảo sát/thi công trên LiteMark; CamLink sẽ dùng ghim của công trình đó làm vị trí điểm và đẩy cam lỗi lên bản đồ LiteMark.")
            .setItems(dong.toTypedArray()) { _, i ->
                when (dong[i]) {
                    "🔗 Chọn công trình LiteMark để nối", "🔁 Đổi sang công trình khác" -> chonCongTrinh()
                    "🔄 Đồng bộ lại ghim từ LiteMark" -> thread { goiLm("lm_dong_bo", ma, nk) }
                    "🧭 Xác minh vị trí cam theo thực tế (ảnh / GPS)" -> startActivity(Intent(this, XacMinhActivity::class.java).putExtra("ma", ma))
                    "🌐 Mở công trình trên LiteMark" -> startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("${tt.optString("may_chu")}/ct/${tt.optString("id")}")))
                    "✂ Ngắt nối (về toạ độ Excel)" -> { core.callAttr("lm_ngat", ma); nk.ghi("Đã ngắt nối LiteMark, dùng lại toạ độ Excel") }
                    "🔑 Đổi khoá kết nối" -> nhapKhoa()
                    "📥 Nạp file tên miền (DDNS) của bên cấp" -> moFileDdns()
                }
            }
            .setNegativeButton("Đóng", null).show()
    }

    private fun nhapKhoa(sau: (() -> Unit)? = null) {
        val o = android.widget.EditText(this)
        o.hint = "Dán khoá kết nối (LiteMark → Tài khoản → Kết nối CamLink)"
        o.setPadding(dp(16), dp(12), dp(16), dp(12))
        AlertDialog.Builder(this).setTitle("Khoá kết nối LiteMark")
            .setMessage("Mở LiteMark → Tài khoản → Kết nối CamLink → Sao chép khoá, rồi dán vào đây. Khoá chỉ cho phép đọc công trình và ghi cảnh báo camera.")
            .setView(o)
            .setPositiveButton("Lưu") { _, _ ->
                val k = core.callAttr("lm_luu_khoa", o.text.toString()).toString()
                if (k.length < 16) { Toast.makeText(this, "Khoá quá ngắn — dán lại", Toast.LENGTH_LONG).show(); return@setPositiveButton }
                if (sau != null) sau() else chonCongTrinh()
            }
            .setNegativeButton("Huỷ", null).show()
    }

    private fun chonCongTrinh() {
        nk.ghi("Đang lấy danh sách công trình từ LiteMark…")
        thread {
            try {
                val ds = JSONArray(core.callAttr("lm_ds_cong_trinh", ma).toString())
                ui.post {
                    if (ds.length() == 0) { nk.ghi("LiteMark: tài khoản chưa có công trình nào"); return@post }
                    val tenTT = mapOf("dang_thi_cong" to "đang thi công", "dang_khao_sat" to "đang khảo sát", "da_khoa" to "đã khoá KS", "xong" to "xong")
                    val nhan = (0 until ds.length()).map { i ->
                        val c = ds.getJSONObject(i)
                        (if (c.optInt("diem_khop") >= 3) "⭐ " else "") + "${c.optString("ten")} — ${c.optInt("so_diem")} điểm · ${tenTT[c.optString("trang_thai")] ?: c.optString("trang_thai")}"
                    }
                    AlertDialog.Builder(this).setTitle("Nối «$tenDuAn» với công trình LiteMark nào? (⭐ = khớp tên/số điểm)")
                        .setItems(nhan.toTypedArray()) { _, i ->
                            val c = ds.getJSONObject(i)
                            thread { goiLm("lm_noi", ma, c.optString("id"), c.optString("ten"), nk) }
                        }
                        .setNegativeButton("Huỷ", null).show()
                }
            } catch (e: Exception) { ui.post { nk.ghi("✖ LiteMark: ${e.message?.substringAfterLast("RuntimeError: ")?.take(160)}") } }
        }
    }

    private fun goiLm(ham: String, vararg thamSo: Any) {
        try {
            val r = JSONObject(core.callAttr(ham, *thamSo).toString())
            ui.post {
                val gc = r.optJSONArray("ghi_chu")
                val bg = r.optJSONArray("bang_ghep")
                val bang = if (bg != null && bg.length() > 0) "\n\nGhép theo VỊ TRÍ (số điểm hai bên khác nhau):\n" + (0 until bg.length()).joinToString("\n") { bg.getString(it) } else ""
                val chuoi = if (gc != null && gc.length() > 0) "\n\n" + (0 until gc.length()).joinToString("\n") { "⚠ " + gc.getString(it) } else ""
                AlertDialog.Builder(this).setTitle("Đã nối LiteMark «${r.optString("ten")}»")
                    .setMessage("${r.optInt("so_ghim")} ghim đã dùng làm vị trí điểm. Kết quả kiểm tra từ nay tự đẩy lên bản đồ LiteMark theo số ghim LiteMark.$bang$chuoi")
                    .setPositiveButton("Kiểm tra lại ngay") { _, _ -> kiem() }
                    .setNeutralButton("🧭 Xác minh vị trí") { _, _ -> startActivity(Intent(this, XacMinhActivity::class.java).putExtra("ma", ma)) }
                    .setNegativeButton("Đóng", null).show()
            }
        } catch (e: Exception) { ui.post { nk.ghi("✖ LiteMark: ${e.message?.substringAfterLast("RuntimeError: ")?.take(160)}") } }
    }

    private fun nut(s: String, bam: () -> Unit): Button {
        val b = Button(this)
        b.text = s
        b.isAllCaps = false
        b.setOnClickListener { bam() }
        return b
    }

    private val mauVien = mapOf("xanh" to "#1D7A46", "vang" to "#C88A00", "do" to "#B42318")
    private val mauNen = mapOf("xanh" to "#EAF6EF", "vang" to "#FFF7E0", "do" to "#FDECEA")
    private val bieu = mapOf("xanh" to "🟢", "vang" to "🟡", "do" to "🔴")

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        core = Python.getInstance().getModule("camlink_core")
        val goc = LinearLayout(this)
        goc.orientation = LinearLayout.VERTICAL
        goc.setPadding(dp(14), dp(18), dp(14), dp(10))
        goc.setBackgroundColor(Color.parseColor("#EEF1F4"))
        goc.addView(chu("Kiểm tra từ xa  ·  CamLink ${packageManager.getPackageInfo(packageName, 0).versionName}", 22f, true))
        val hang = LinearLayout(this)
        hang.orientation = LinearLayout.HORIZONTAL
        hang.addView(nut("🔄 Kiểm tra lại") { kiem() }.apply { setOnLongClickListener { kiem(false); true } }, LinearLayout.LayoutParams(0, -2, 1f))
        hang.addView(nut("📤 Xuất Excel + gửi") { xuat() }, LinearLayout.LayoutParams(0, -2, 1f))
        hang.addView(nut("📈 Theo dõi") { TheoDoi.danhSach(this) }, LinearLayout.LayoutParams(0, -2, 1f))
        goc.addView(hang)
        goc.addView(nut("📁 Chọn dự án / nạp file cấu hình") { chonDuAn() })
        val hang2 = LinearLayout(this)
        hang2.orientation = LinearLayout.HORIZONTAL
        hang2.addView(nut("🖥 Màn hình giám sát") { moGiamSat() }, LinearLayout.LayoutParams(0, -2, 1f))
        hang2.addView(nut("🗺 Bản đồ") { moBanDo() }, LinearLayout.LayoutParams(0, -2, 1f))
        hang2.addView(nut("🔗 LiteMark") { liteMark() }, LinearLayout.LayoutParams(0, -2, 1f))
        goc.addView(hang2)
        thanhTienDo = android.widget.ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal)
        thanhTienDo.max = 100
        thanhTienDo.visibility = View.GONE
        goc.addView(thanhTienDo, LinearLayout.LayoutParams(-1, dp(10)).apply { topMargin = dp(4) })
        chuTienDo = chu("", 13f, true, "#0F5D8C")
        chuTienDo.visibility = View.GONE
        goc.addView(chuTienDo)
        tienDo = chu("", 13f, mau = "#0F5D8C")
        tienDo.setPadding(dp(4), dp(4), dp(4), dp(4))
        goc.addView(tienDo)
        khung = LinearLayout(this)
        khung.orientation = LinearLayout.VERTICAL
        val cuon = ScrollView(this)
        cuon.addView(khung)
        goc.addView(cuon, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(goc)
        if (intent.getBooleanExtra("mo_theo_doi", false)) ui.postDelayed({ TheoDoi.danhSach(this) }, 400)
        val nhanCt = intent.getStringExtra("nhan_ct")
        if (nhanCt != null) nhanDuAn(nhanCt, intent.getStringExtra("nhan_ten") ?: "")
        else { chonDuAn(); kiemChoNhan() }
    }

    // ---------------- nhận dự án từ LiteMark (sau khi bấm "Chuyển sang CamLink") ----------------
    private val maFileDdns = 22

    /** Có công trình LiteMark đã bấm "Chuyển sang CamLink" mà máy này chưa nhận → mời nhận. */
    private fun kiemChoNhan() {
        thread {
            try {
                val ds = JSONArray(core.callAttr("lm_cho_nhan").toString())
                if (ds.length() == 0) return@thread
                ui.post {
                    val nhan = (0 until ds.length()).map { i -> val c = ds.getJSONObject(i); "📥 ${c.optString("ten")} — ${c.optInt("so_diem")} điểm, ${c.optInt("so_camera")} cam" }
                    AlertDialog.Builder(this).setTitle("Có dự án mới từ LiteMark")
                        .setItems(nhan.toTypedArray()) { _, i -> val c = ds.getJSONObject(i); nhanDuAn(c.optString("id"), c.optString("ten")) }
                        .setNegativeButton("Để sau", null).show()
                }
            } catch (_: Exception) {}
        }
    }

    private fun nhanDuAn(idCt: String, tenCt: String) {
        val tt = JSONObject(core.callAttr("lm_trang_thai", "").toString())
        if (!tt.optBoolean("co_khoa")) { nhapKhoa { nhanDuAn(idCt, tenCt) }; return }
        nk.ghi("Đang nhận dự án từ LiteMark…")
        thread {
            try {
                val m = core.callAttr("lm_nhan_du_an", idCt, tenCt, nk).toString()
                val ds = core.callAttr("ds_du_an").asList().map { r -> r.asList().map { it.toString() } }
                val d = ds.firstOrNull { it[0] == m }
                ui.post {
                    ma = m; tenDuAn = d?.get(1) ?: tenCt
                    AlertDialog.Builder(this).setTitle("Đã nhận «$tenDuAn»")
                        .setMessage("${d?.get(2) ?: "?"} điểm, vị trí lấy đúng ghim LiteMark (số điểm hai bên trùng nhau).\n\nBước tiếp: nạp file tên miền (DDNS) của bên cấp để app tự ghép tên miền vào từng ghim. Điểm nào không ghép chắc được sẽ chọn tại cột lúc cài.")
                        .setPositiveButton("📥 Nạp file tên miền") { _, _ -> moFileDdns() }
                        .setNegativeButton("Để sau", null).show()
                }
            } catch (e: Exception) { ui.post { nk.ghi("✖ Nhận dự án: ${e.message?.substringAfterLast("RuntimeError: ")?.take(160)}") } }
        }
    }

    private fun moFileDdns() {
        if (ma.isEmpty()) { Toast.makeText(this, "Chọn dự án trước", Toast.LENGTH_SHORT).show(); return }
        val i = Intent(Intent.ACTION_OPEN_DOCUMENT)
        i.addCategory(Intent.CATEGORY_OPENABLE)
        i.type = "*/*"
        startActivityForResult(i, maFileDdns)
    }

    private fun napDdns(uri: Uri) {
        val dich = File(cacheDir, "ddns.xlsx")
        contentResolver.openInputStream(uri)?.use { vao -> dich.outputStream().use { vao.copyTo(it) } }
        nk.ghi("Đang ghép tên miền vào ghim…")
        thread {
            try {
                val bc = JSONObject(core.callAttr("lm_nap_ddns", ma, dich.absolutePath, nk).toString())
                val sb = StringBuilder()
                sb.append("File: ${bc.optInt("tong_dong")} tên miền · dự án: ${bc.optInt("tong_diem")} điểm\n")
                sb.append("✔ Tự ghép chắc: ${bc.optInt("tu_gan")} điểm\n")
                val tr = bc.optJSONArray("trung"); if (tr != null && tr.length() > 0) sb.append("⚠ Trùng (2 dòng cùng sát 1 ghim): ${(0 until tr.length()).joinToString { "ghim " + tr.getJSONArray(it).getString(0) }}\n")
                val cc = bc.optJSONArray("chua_chac"); if (cc != null && cc.length() > 0) sb.append("⚠ Chưa chắc: ${(0 until cc.length()).joinToString { "ghim " + cc.getJSONArray(it).getString(0) }}\n")
                val th = bc.optJSONArray("diem_thieu"); if (th != null && th.length() > 0) sb.append("→ ${th.length()} điểm chọn tên miền TẠI CỘT lúc cài: ${(0 until th.length()).joinToString { th.getString(it) }}\n")
                val kt = bc.optJSONArray("dong_khong_toa_do"); if (kt != null && kt.length() > 0) sb.append("· Dòng file không có toạ độ / không có ghim: ${(0 until kt.length()).joinToString { kt.getString(it) }}\n")
                val ch = bc.optJSONArray("chenh_cam"); if (ch != null && ch.length() > 0) sb.append("· Số cam file ≠ LiteMark: ${(0 until ch.length()).joinToString { val r = ch.getJSONArray(it); "ghim ${r.getString(0)} (${r.getInt(1)}↔${r.getInt(2)})" }} — lúc cài theo số quét thực tế\n")
                ui.post { AlertDialog.Builder(this).setTitle("Ghép tên miền — $tenDuAn").setMessage(sb.toString()).setPositiveButton("OK", null).show() }
            } catch (e: Exception) { ui.post { nk.ghi("✖ File tên miền: ${e.message?.substringAfterLast("Error: ")?.take(160)}") } }
        }
    }

    // ---------------- dự án ----------------
    private fun chonDuAn() {
        if (dangChay) return
        val ds = core.callAttr("ds_du_an").asList().map { r -> r.asList().map { it.toString() } }
        val ten = ds.map { "📂 ${it[1]} — ${it[2]} điểm (đã nạp sẵn trong app, bấm để kiểm tra)" } +
            "＋ Nạp file Excel khác / cập nhật file mới"
        AlertDialog.Builder(this)
            .setTitle(if (ds.isEmpty()) "Chưa có dự án — nạp file Excel cấu hình" else "Chọn dự án để kiểm tra")
            .setItems(ten.toTypedArray()) { _, i ->
                if (i == ds.size) moFile() else { ma = ds[i][0]; tenDuAn = ds[i][1]; batDau() }
            }
            .setNegativeButton("Đóng") { _, _ -> if (ma.isEmpty()) finish() }
            .show()
    }

    private fun moFile() {
        val i = Intent(Intent.ACTION_OPEN_DOCUMENT)
        i.addCategory(Intent.CATEGORY_OPENABLE)
        i.type = "*/*"
        startActivityForResult(i, maFile)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == maGiamSat) {
            val stt = data?.getStringExtra("stt") ?: return
            val v = khung.findViewWithTag<View>("diem_$stt") ?: return
            (khung.parent as? ScrollView)?.post { (khung.parent as ScrollView).smoothScrollTo(0, v.top) }
            return
        }
        val uri: Uri = data?.data ?: return
        if (requestCode == maFileDdns && resultCode == RESULT_OK) { napDdns(uri); return }
        if (requestCode != maFile || resultCode != RESULT_OK) return
        var tenFile = "khao_sat.xlsx"
        contentResolver.query(uri, null, null, null, null)?.use { c ->
            val cot = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (cot >= 0 && c.moveToFirst()) tenFile = c.getString(cot) ?: tenFile
        }
        val dich = File(cacheDir, "khao_sat.xlsx")
        contentResolver.openInputStream(uri)?.use { vao -> dich.outputStream().use { vao.copyTo(it) } }
        nk.ghi("Đang nạp $tenFile …")
        thread {
            try {
                core.callAttr("nhap_excel", dich.absolutePath, tenFile, nk)
                val ds = core.callAttr("ds_du_an").asList().map { r -> r.asList().map { it.toString() } }
                val moi = ds.maxByOrNull { File(filesDir, "duan/${it[0]}.json").lastModified() }
                ui.post { if (moi != null) { ma = moi[0]; tenDuAn = moi[1]; batDau() } }
            } catch (e: Exception) {
                ui.post { nk.ghi("✖ Không đọc được file: ${e.message}") }
            }
        }
    }

    private fun batDau() { kiem() }

    // ---------------- mạng 4G ----------------
    private var yeuCau4G: ConnectivityManager.NetworkCallback? = null

    private fun gan4G(bat: Boolean): Boolean {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        if (!bat) {
            cm.bindProcessToNetwork(null)   // giữ yêu cầu 4G để cầu RTSP còn dùng được
            return true
        }
        fun tim() = cm.allNetworks.firstOrNull { n ->
            val nc = cm.getNetworkCapabilities(n)
            nc?.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) == true && nc.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
        }
        var dd = tim()
        if (dd == null) {
            // đang có WiFi → Android tắt 4G; phải yêu cầu rõ thì hệ thống mới bật lại
            val khoa = java.util.concurrent.CountDownLatch(1)
            val cb = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(n: android.net.Network) { dd = n; khoa.countDown() }
            }
            try {
                cm.requestNetwork(android.net.NetworkRequest.Builder()
                    .addTransportType(NetworkCapabilities.TRANSPORT_CELLULAR)
                    .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET).build(), cb)
                yeuCau4G = cb
                khoa.await(8, java.util.concurrent.TimeUnit.SECONDS)
            } catch (_: Exception) {}
        }
        val n = dd ?: return false
        mang4G = n
        return cm.bindProcessToNetwork(n)
    }

    // ---------------- kiểm tra ----------------
    /** nhanh=true (mặc định): điểm lần trước toàn ĐẠT lấy từ lịch sử, phát live xác minh; chỉ quét lại điểm có sự cố. Giữ lâu nút = quét đầy đủ. */
    private fun kiem(nhanh: Boolean = true) {
        if (ma.isEmpty() || dangChay) return
        dangChay = true
        ketQua = null
        khung.removeAllViews()   // xoá sạch kết quả cũ trước khi kiểm tra lại
        khung.addView(chu(if (nhanh) "⏳ Kiểm tra nhanh $tenDuAn…\nĐiểm lần trước toàn đạt: lấy lại, phát live để xác minh.\nĐiểm có sự cố: quét lại đầy đủ, tự sửa nếu được.\n(Giữ lâu nút Kiểm tra lại = quét đầy đủ mọi điểm)"
                          else "⏳ Đang quét ĐẦY ĐỦ $tenDuAn…\nCam đang chạy tốt: chỉ đọc và báo cáo.\nCam có vấn đề: app tự sửa rồi kiểm tra lại cấu hình.", 15f, mau = "#0F5D8C"))
        nk.ghi("⏳ Đang kiểm tra $tenDuAn qua Internet…")
        thread {
            val co4G = gan4G(true)
            try {
                val j = core.callAttr("tuxa_kiem", ma, nk, nhanh).toString()
                ui.post {
                    ketQua = JSONObject(j)
                    veBang(if (co4G) "Đã kiểm tra qua 4G (như IOC gọi từ ngoài)" else "⚠ Không bật được 4G — đã kiểm tra qua WiFi; nếu đang ở trong WiFi của chính điểm, kết quả có thể sai")
                    moGiamSat()
                }
            } catch (e: Exception) {
                ui.post { nk.ghi("✖ Lỗi kiểm tra: ${e.message}") }
            } finally {
                gan4G(false)
                dangChay = false
            }
        }
    }

    private fun veBang(ghiChu: String) {
        val k = ketQua ?: return
        khung.removeAllViews()
        tienDo.text = ghiChu
        // tổng
        val tong = k.optInt("tong_cam")
        val dat = k.optInt("dat")
        val tt = the(if (dat == tong) "#1D7A46" else "#B42318")
        tt.addView(chu(k.optString("du_an"), 17f, true))
        tt.addView(chu("Kiểm lúc ${k.optString("luc")} · ${k.optInt("giay")} giây", 12f, mau = "#5B6776"))
        val tongFile = k.optInt("tong_file")
        val tongQuet = k.optInt("tong_quet")
        val camLa = k.optInt("so_cam_la")
        tt.addView(chu("$dat cam ĐẠT (có ảnh)", 20f, true, if (dat >= tongFile && dat > 0) "#1D7A46" else "#B42318"))
        val tongHc = k.optInt("tong_hc", tongFile)
        tt.addView(chu("File khảo sát ghi: $tongFile cam" + (if (tongHc != tongFile) "  →  hồ sơ đã hiệu chỉnh theo thực tế: $tongHc cam" else "") +
            "\nQuét thực tế trên các tên miền: $tongQuet cam" +
            (if (camLa > 0) "\n  trong đó $camLa CAM LẠ ngoài hồ sơ (xem khung tím)" else "") +
            "\nCam KHÔNG LÊN (có cam, không xem được): ${k.optInt("khong_len")}" +
            (if (k.optInt("file_du") > 0) "\nTrong đó ${k.optInt("file_du")} vị trí nhiều khả năng là file ghi NHẦM ĐIỂM (cam lạ ở điểm khác bù vào) — xem cảnh báo ⚠ ở điểm có cam lạ" else ""), 14f))
        val hc = k.optJSONArray("hieu_chinh")
        if (hc != null && hc.length() > 0) {
            val h = the("#0F5D8C", "#EAF2FA")
            h.addView(chu("✎ Đã tự hiệu chỉnh hồ sơ theo thực tế (file khảo sát gốc vẫn giữ để đối chiếu)", 15f, true, "#0F5D8C"))
            for (i in 0 until hc.length()) {
                val x = hc.getJSONObject(i)
                h.addView(chu("• Điểm ${x.optString("stt")}. ${x.optString("ten")}: ${x.optInt("cu")} → ${x.optInt("moi")} cam (BS ${x.optInt("bs_cu")} → ${x.optInt("bs_moi")})\n  ${x.optString("ly_do")}", 13f))
            }
            h.addView(chu("Bấm \"Xuất Excel + gửi\" để nhận kèm file khảo sát đã hiệu chỉnh.", 12f, mau = "#5B6776"))
            tt.addView(h)
        }
        val dsLa = k.optJSONArray("cam_la")
        if (dsLa != null && dsLa.length() > 0) {
            val la = the("#7A1FA2", "#F3E8FA")
            la.addView(chu("⚠ CAM LẠ — hệ thống có thêm thiết bị ngoài hồ sơ", 16f, true, "#7A1FA2"))
            la.addView(chu("Theo file $tongFile cam + ${dsLa.length()} cam lạ scan thấy. Có thể đơn vị khác nâng cấp/lắp thêm không báo, hoặc có người biết pass đã thêm/can thiệp.", 14f))
            for (i in 0 until dsLa.length()) {
                val x = dsLa.getJSONObject(i)
                la.addView(chu("• Điểm ${x.optString("stt")}. ${x.optString("ten")} — ${x.optString("domain")}:${x.optInt("http")}" +
                    (if (x.optString("model").isNotEmpty()) " — ${x.optString("hang")} ${x.optString("model")}" else "") +
                    (if (x.optString("mac").isNotEmpty()) " — MAC ${x.optString("mac")}" else "") +
                    "\n  thấy lần đầu ${x.optString("lan_dau")}" + (if (x.optBoolean("moi")) "   🆕 MỚI PHÁT HIỆN" else ""), 14f, x.optBoolean("moi"), "#17202B"))
                la.addView(link("🌐 ${x.optString("web")}") { moLink(x.optString("web")) })
            }
            la.addView(chu("Việc cần làm: xác minh với đơn vị quản lý điểm ai lắp, khi nào. Không ai nhận → đổi pass modem + pass cam cả điểm. Hợp lệ → bổ sung file khảo sát.", 13f, true, "#7A1FA2"))
            tt.addView(la)
        }
        val bcs = k.optJSONArray("bao_cao_sua")
        if (bcs != null) {
            var xong = 0
            for (i in 0 until bcs.length()) if (bcs.getJSONObject(i).optString("ket_qua") == "HOÀN THÀNH") xong++
            tt.addView(chu("🔧 Sửa tất cả lúc ${k.optString("luc_sua")}: $xong/${bcs.length()} vấn đề HOÀN THÀNH", 15f, true, if (xong == bcs.length()) "#1D7A46" else "#9A5B00"))
            tt.addView(nut("Xem báo cáo sửa (từng vấn đề)") { xemBaoCaoSua(bcs) })
        }
        if (tong - dat > 0 && bcs == null) tt.addView(nut("🔧 SỬA TẤT CẢ ${tong - dat} VẤN ĐỀ (rồi báo cáo)") { suaTatCa() })
        val daSua = k.optInt("da_sua")
        if (daSua > 0) tt.addView(chu("🔧 App đã tự sửa $daSua cam có vấn đề → ${k.optInt("sua_xong")} cam đã chạy lại", 14f, true, "#0F5D8C"))
        tt.addView(chu("Cam đang chạy tốt: chỉ đọc, không thay đổi gì", 12f, mau = "#5B6776"))
        val rot = k.optInt("rot")
        if (rot > 0) tt.addView(chu("⬇ $rot cam vừa rớt so với lần trước", 14f, true, "#B42318"))
        val nhom = k.optJSONObject("nhom_loi")
        if (nhom != null && nhom.length() > 0) {
            val sb = StringBuilder()
            nhom.keys().forEach { n -> sb.append("• ").append(n).append(": ").append(nhom.optInt(n)).append("\n") }
            tt.addView(chu(sb.toString().trim(), 14f))
        }
        khung.addView(tt)
        // từng điểm
        val diem = k.optJSONArray("diem") ?: JSONArray()
        val thuTu = (0 until diem.length()).map { diem.getJSONObject(it) }
            .sortedBy { mapOf("do" to 0, "vang" to 1, "xanh" to 2)[it.optString("muc")] ?: 3 }
        for (p in thuTu) khung.addView(theDiem(p))
    }

    private fun theDiem(p: JSONObject): LinearLayout {
        val muc = p.optString("muc")
        val t = the(mauVien[muc] ?: "#5B6776", mauNen[muc] ?: "#FFFFFF")
        t.tag = "diem_${p.optString("stt")}"
        t.addView(chu("${bieu[muc]} Điểm ${p.optString("stt")}. ${p.optString("ten")}", 16f, true))
        t.addView(chu("${p.optString("tong")}  ·  ${p.optString("domain")}${if (p.optString("ip").isNotEmpty()) " → " + p.optString("ip") else ""}", 13f, mau = "#3B4654"))
        val mapUrl = p.optString("map")
        if (mapUrl.isNotEmpty()) t.addView(link("📍 Dẫn đường tới điểm (Google Maps)") { moLink(mapUrl) })
        else t.addView(chu("📍 Chưa có toạ độ — bổ sung link bản đồ vào cột Vị trí của file khảo sát", 12f, mau = "#9A5B00"))
        if (muc != "xanh") t.addView(nut("📨 Phiếu báo mạng (gửi người không nắm địa bàn)") { phieu(p.optString("stt")) })
        val wm = p.optString("web_modem")
        if (wm.isNotEmpty()) t.addView(link("🌐 Web modem: $wm") { moLink(wm) })
        t.addView(chu(p.optString("ghi_so"), 12f, mau = "#5B6776"))
        val cb = p.optJSONArray("canh_bao")
        if (cb != null) for (i in 0 until cb.length()) t.addView(chu("⚠ ${cb.getString(i)}", 13f, true, "#B42318"))
        val cams = p.optJSONArray("cam") ?: JSONArray()
        t.addView(luoiCam(p, cams))
        for (i in 0 until cams.length()) t.addView(dongCam(p, cams.getJSONObject(i)))
        return t
    }

    /** Lưới ô hình: mỗi cam một ô. Ô cam lên: ảnh chụp, bấm là phát trực tiếp ngay tại ô. Ô cam lỗi: ghi lý do ngay trong ô. */
    private fun luoiCam(p: JSONObject, cams: JSONArray): android.widget.GridLayout {
        val n = cams.length()
        val o = android.widget.GridLayout(this)
        o.columnCount = if (n <= 1) 1 else 2
        o.setPadding(0, dp(6), 0, dp(2))
        val cao = if (n <= 1) 210 else 120
        for (i in 0 until n) {
            val c = cams.getJSONObject(i)
            val muc = c.optString("muc")
            val oCam = LinearLayout(this)
            oCam.orientation = LinearLayout.VERTICAL
            val khung = FrameLayout(this)
            khung.setBackgroundColor(Color.parseColor(if (muc == "xanh") "#172029" else "#5A1E1E"))
            val tt = chu("", 11f, true, mauVien[muc] ?: "#17202B")
            val anh = c.optString("anh")
            val live = c.optString("live")
            if (muc == "xanh" && anh.isNotEmpty() && File(anh).exists()) {
                val iv = ImageView(this)
                iv.scaleType = ImageView.ScaleType.CENTER_CROP
                thread { val bm = BitmapFactory.decodeFile(anh); ui.post { iv.setImageBitmap(bm) } }
                khung.addView(iv, FrameLayout.LayoutParams(-1, -1))
                khung.addView(chu("▶", 30f, true, "#FFFFFF"), FrameLayout.LayoutParams(-2, -2, android.view.Gravity.CENTER))
                tt.text = "Bấm ô để xem trực tiếp"
            } else if (muc != "xanh") {
                khung.addView(chu(c.optString("nhan"), 12f, true, "#FFD7D2").apply { setPadding(dp(8), dp(22), dp(8), dp(4)) }, FrameLayout.LayoutParams(-1, -2))
            }
            khung.addView(chu(" C${c.optInt("so")} ${if (muc == "xanh") "✓" else "✖"} ", 12f, true, "#FFFFFF").apply { setBackgroundColor(Color.parseColor("#99000000")) },
                FrameLayout.LayoutParams(-2, -2, android.view.Gravity.TOP or android.view.Gravity.START))
            if (live.isNotEmpty() && muc == "xanh") {
                khung.setOnClickListener { boPhat.phat(khung, live, tt, cao) }
                khung.tag = Triple(khung, live, tt)          // cho nút "Live tất cả"
            }
            oCam.addView(khung, LinearLayout.LayoutParams(-1, dp(cao)))
            oCam.addView(tt)
            oCam.addView(Button(this).apply {
                text = "📈 Theo dõi"; isAllCaps = false; textSize = 12f
                setOnClickListener { TheoDoi.bam(this@TuXaActivity, ma, p, c, tenDuAn) }
            }, LinearLayout.LayoutParams(-2, -2))
            o.addView(oCam, android.widget.GridLayout.LayoutParams(android.widget.GridLayout.spec(android.widget.GridLayout.UNDEFINED, 1f),
                android.widget.GridLayout.spec(android.widget.GridLayout.UNDEFINED, 1f)).apply { width = 0; setMargins(dp(2), dp(2), dp(2), dp(2)) })
        }
        return o
    }

    private fun dongCam(p: JSONObject, c: JSONObject): LinearLayout {
        val muc = c.optString("muc")
        val hop = LinearLayout(this)
        hop.orientation = LinearLayout.VERTICAL
        hop.setPadding(0, dp(8), 0, 0)
        val dau = chu("${bieu[muc]} Cam ${c.optInt("so")}: ${c.optString("nhan")}" +
            (if (c.optBoolean("vua_rot")) "   ⬇ VỪA RỚT" else "") + (if (c.optBoolean("vua_len")) "   ⬆ đã lên lại" else "") + "   ▸ chi tiết",
            15f, true, mauVien[muc] ?: "#17202B")
        hop.addView(dau)
        val ct = LinearLayout(this)
        ct.orientation = LinearLayout.VERTICAL
        ct.setPadding(dp(10), dp(4), 0, dp(4))
        ct.visibility = View.GONE      // gọn: hình đã ở lưới ô phía trên; bấm "▸ chi tiết" để xem nguyên nhân, link, user/pass, sửa
        dau.setOnClickListener { ct.visibility = if (ct.visibility == View.VISIBLE) View.GONE else View.VISIBLE }

        ct.addView(chu("Nguyên nhân: ${c.optString("nguyen_nhan")}", 14f))
        val viec = c.optJSONArray("viec")
        if (viec != null && viec.length() > 0) {
            ct.addView(chu("Việc tiếp theo:", 14f, true, "#0F5D8C"))
            for (i in 0 until viec.length()) ct.addView(chu("${i + 1}) ${viec.getString(i)}", 14f))
        }
        val thongTin = "Web: ${c.optString("web")}\nXem trực tiếp: ${c.optString("live")}\n" +
            "User cam: ${c.optString("user")}   Pass cam: ${c.optString("pass")}\n" +
            "User No-IP: ${p.optString("noip_user")}   Pass No-IP: ${p.optString("noip_pass")}" +
            (if (c.optString("model").isNotEmpty()) "\nCam: ${c.optString("hang")} ${c.optString("model")}" else "")
        // link bấm vào là mở luôn
        ct.addView(link("🌐 ${c.optString("web")}") { moLink(c.optString("web")) })
        ct.addView(link("▶ ${c.optString("live").replace(Regex("//[^@/]*@"), "//")}") {
            startActivity(Intent(this, XemLiveActivity::class.java).putExtra("url", c.optString("live"))
                .putExtra("tieu_de", "Điểm ${p.optString("stt")} · cam ${c.optInt("so")}"))
        })
        ct.addView(chu("User cam: ${c.optString("user")}   Pass cam: ${c.optString("pass")}\n" +
            "User No-IP: ${p.optString("noip_user")}   Pass No-IP: ${p.optString("noip_pass")}" +
            (if (c.optString("model").isNotEmpty()) "\nCam: ${c.optString("hang")} ${c.optString("model")}" else ""),
            13f).apply { setTextIsSelectable(true); typeface = Typeface.MONOSPACE })
        val bc = c.optJSONArray("bang_chung")
        if (bc != null && bc.length() > 0) {
            ct.addView(chu("Bằng chứng:", 14f, true, "#0F5D8C"))
            for (i in 0 until bc.length()) ct.addView(chu("• ${bc.getString(i)}", 13f, mau = "#3B4654"))
        }
        val h1 = LinearLayout(this)
        h1.orientation = LinearLayout.HORIZONTAL
        h1.addView(nut("Mở web") { moLink(c.optString("web")) }, LinearLayout.LayoutParams(0, -2, 1f))
        h1.addView(nut("▶ Xem") {
            startActivity(Intent(this, XemLiveActivity::class.java).putExtra("url", c.optString("live"))
                .putExtra("tieu_de", "Điểm ${p.optString("stt")} · cam ${c.optInt("so")}"))
        }, LinearLayout.LayoutParams(0, -2, 1f))
        h1.addView(nut("Copy") { copy(thongTin) }, LinearLayout.LayoutParams(0, -2, 1f))
        ct.addView(h1)
        val sua = c.optJSONArray("sua")
        if (sua != null) for (i in 0 until sua.length()) {
            val v = sua.getString(i)
            ct.addView(nut("🔧 Sửa từ xa: ${core.callAttr("ten_sua", v)}") { xacNhanSua(p, c, v) })
        }
        hop.addView(ct)
        return hop
    }

    private val maGiamSat = 41
    private fun moGiamSat() {
        val k = ketQua ?: run { Toast.makeText(this, "Kiểm tra trước đã", Toast.LENGTH_SHORT).show(); return }
        val f = File(cacheDir, "giamsat.json")
        f.writeText(k.toString())
        startActivityForResult(Intent(this, GiamSatActivity::class.java).putExtra("file", f.absolutePath).putExtra("ma", ma), maGiamSat)
    }

    private fun moBanDo() {
        val k = ketQua ?: run { Toast.makeText(this, "Kiểm tra trước đã", Toast.LENGTH_SHORT).show(); return }
        // Đã nối LiteMark → bản đồ là bản đồ công trình LiteMark (một nguồn dữ liệu); bản đồ riêng của CamLink chỉ khi chưa nối
        val lm = k.optJSONObject("litemark")
        if (lm != null && lm.optString("id").isNotEmpty()) {
            val tt = JSONObject(core.callAttr("lm_trang_thai", ma).toString())
            AlertDialog.Builder(this).setTitle("Bản đồ")
                .setItems(arrayOf("🌐 Bản đồ công trình trên LiteMark (ghim thật, cảnh báo cam lỗi)", "🗺 Bản đồ riêng của CamLink (đối chiếu)")) { _, i ->
                    if (i == 0) startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("${tt.optString("may_chu")}/ct/${lm.optString("id")}")))
                    else moBanDoRieng(k)
                }.show()
            return
        }
        moBanDoRieng(k)
    }

    private fun moBanDoRieng(k: JSONObject) {
        thread {
            try {
                val f = core.callAttr("tuxa_ban_do", k.toString()).toString()
                ui.post { startActivity(Intent(this, BanDoActivity::class.java).putExtra("file", f).putExtra("ma", ma).putExtra("kq", k.toString())) }
            } catch (e: Exception) { ui.post { nk.ghi("✖ Bản đồ: ${e.message}") } }
        }
    }

    private fun phieu(stt: String) {
        val k = ketQua ?: return
        val txt = core.callAttr("tuxa_phieu", ma, k.toString(), stt).toString()
        AlertDialog.Builder(this).setTitle("Phiếu báo mạng — điểm $stt").setMessage(txt)
            .setPositiveButton("Gửi Zalo/SMS") { _, _ ->
                startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply { type = "text/plain"; putExtra(Intent.EXTRA_TEXT, txt) }, "Gửi phiếu báo mạng"))
            }
            .setNeutralButton("Copy") { _, _ -> copy(txt) }
            .setNegativeButton("Đóng", null).show()
    }

    private fun liveTatCa() {
        val ds = ArrayList<Triple<FrameLayout, String, TextView>>()
        fun quet(v: View) {
            (v.tag as? Triple<*, *, *>)?.let { ds.add(it as Triple<FrameLayout, String, TextView>) }
            if (v is android.view.ViewGroup) for (i in 0 until v.childCount) quet(v.getChildAt(i))
        }
        quet(khung)
        if (ds.isEmpty()) { Toast.makeText(this, "Chưa có cam nào lên để xem", Toast.LENGTH_SHORT).show(); return }
        for (t in ds.take(TOI_DA_LIVE)) phatLive(t.first, t.second, t.third)
        if (ds.size > TOI_DA_LIVE) Toast.makeText(this, "Đang phát $TOI_DA_LIVE cam đầu; bấm ▶ ở cam khác để đổi", Toast.LENGTH_LONG).show()
    }

    private fun suaTatCa() {
        val k = ketQua ?: return
        if (dangChay) return
        AlertDialog.Builder(this)
            .setTitle("Sửa tất cả vấn đề?")
            .setMessage("App chỉ đụng tới cam ĐANG CÓ VẤN ĐỀ (khởi động lại, đặt lại port, khôi phục gateway/DNS/DDNS). Cam đang chạy tốt không thay đổi gì. Xong app kiểm tra lại và báo cáo từng vấn đề: hoàn thành hay chưa, nguyên nhân, giải pháp.")
            .setPositiveButton("SỬA TẤT CẢ") { _, _ ->
                dangChay = true
                khung.removeAllViews()
                khung.addView(chu("🔧 Đang sửa tất cả… (vài phút, cam khởi động lại mất ~2 phút)", 15f, mau = "#0F5D8C"))
                thread {
                    gan4G(true)
                    try {
                        val j = core.callAttr("tuxa_sua_tat_ca", ma, k.toString(), nk).toString()
                        ui.post { ketQua = JSONObject(j); veBang("Đã sửa tất cả và kiểm tra lại"); xemBaoCaoSua(ketQua!!.optJSONArray("bao_cao_sua") ?: JSONArray()) }
                    } catch (e: Exception) { ui.post { nk.ghi("✖ ${e.message}"); veBang("Sửa tất cả bị lỗi: ${e.message}") } }
                    finally { gan4G(false); dangChay = false }
                }
            }
            .setNegativeButton("Huỷ", null)
            .show()
    }

    private fun xemBaoCaoSua(bcs: JSONArray) {
        val sb = StringBuilder()
        for (i in 0 until bcs.length()) {
            val b = bcs.getJSONObject(i)
            sb.append(if (b.optString("ket_qua") == "HOÀN THÀNH") "✅ " else "❌ ").append(b.optString("diem")).append(" — ").append(b.optString("cam")).append("\n")
            sb.append("Vấn đề: ").append(b.optString("van_de")).append("\n")
            val dl = b.optJSONArray("da_lam"); if (dl != null) for (j in 0 until dl.length()) sb.append("• ").append(dl.getString(j)).append("\n")
            if (b.optString("ket_qua") != "HOÀN THÀNH") {
                sb.append("Nguyên nhân: ").append(b.optString("nguyen_nhan")).append("\n")
                val gp = b.optJSONArray("giai_phap"); if (gp != null) for (j in 0 until gp.length()) sb.append("→ ").append(gp.getString(j)).append("\n")
            }
            sb.append("\n")
        }
        AlertDialog.Builder(this).setTitle("Báo cáo sửa tất cả").setMessage(sb.toString().trim()).setPositiveButton("Đóng", null).show()
    }

    private fun suaSoCam(p: JSONObject) {
        val stt = p.optString("stt")
        val chon = arrayOf("1 cam", "2 cam", "3 cam", "4 cam")
        AlertDialog.Builder(this)
            .setTitle("Điểm $stt thực tế có mấy cam?")
            .setItems(chon) { _, i ->
                core.callAttr("sua_so_cam", ma, stt, i + 1)
                if (dangChay) return@setItems
                dangChay = true
                thread {
                    gan4G(true)
                    try {
                        val moi = JSONObject(core.callAttr("tuxa_kiem_diem", ma, stt, nk).toString())
                        ui.post { thayDiem(moi) }
                    } catch (e: Exception) { ui.post { nk.ghi("✖ ${e.message}") } } finally { gan4G(false); dangChay = false }
                }
            }
            .setNegativeButton("Huỷ", null)
            .show()
    }

    // ---------------- sửa từ xa ----------------
    private fun xacNhanSua(p: JSONObject, c: JSONObject, viec: String) {
        val ten = core.callAttr("ten_sua", viec).toString()
        AlertDialog.Builder(this)
            .setTitle("$ten?")
            .setMessage("Điểm ${p.optString("stt")}. ${p.optString("ten")} — cam ${c.optInt("so")}\n\nApp sẽ đăng nhập qua ${p.optString("domain")} để làm việc này. Xong tự kiểm tra lại điểm.")
            .setPositiveButton("LÀM") { _, _ -> sua(p, c, viec) }
            .setNegativeButton("Huỷ", null)
            .show()
    }

    private fun sua(p: JSONObject, c: JSONObject, viec: String) {
        if (dangChay) return
        dangChay = true
        val stt = p.optString("stt")
        nk.ghi("⏳ ${core.callAttr("ten_sua", viec)} — điểm $stt cam ${c.optInt("so")}…")
        thread {
            gan4G(true)
            try {
                val r = core.callAttr("tuxa_sua", ma, stt, c.optInt("so"), viec, nk).asList().map { it.toString() }
                nk.ghi("Kiểm tra lại điểm $stt…")
                val moi = JSONObject(core.callAttr("tuxa_kiem_diem", ma, stt, nk).toString())
                ui.post {
                    thayDiem(moi)
                    AlertDialog.Builder(this)
                        .setTitle(if (r[0] == "OK") "✔ Đã sửa" else "✖ Chưa sửa được")
                        .setMessage(r[1] + "\n\nSau khi kiểm tra lại: điểm $stt ${moi.optString("tong")}")
                        .setPositiveButton("Đóng", null)
                        .show()
                }
            } catch (e: Exception) {
                ui.post { nk.ghi("✖ ${e.message}") }
            } finally {
                gan4G(false)
                dangChay = false
            }
        }
    }

    private fun thayDiem(moi: JSONObject) {
        val k = ketQua ?: return
        val ds = k.optJSONArray("diem") ?: return
        for (i in 0 until ds.length()) if (ds.getJSONObject(i).optString("stt") == moi.optString("stt")) ds.put(i, moi)
        var tong = 0; var dat = 0
        for (i in 0 until ds.length()) {
            val cs = ds.getJSONObject(i).optJSONArray("cam") ?: continue
            for (j in 0 until cs.length()) { tong++; if (cs.getJSONObject(j).optString("muc") == "xanh") dat++ }
        }
        k.put("tong_cam", tong); k.put("dat", dat)
        veBang("Đã cập nhật điểm ${moi.optString("stt")} sau khi sửa")
    }

    // ---------------- tiện ích ----------------
    private fun moLink(u: String) {
        try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(u))) } catch (e: Exception) { copy(u) }
    }

    private fun copy(s: String) {
        (getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("CamLink", s))
        Toast.makeText(this, "Đã copy", Toast.LENGTH_SHORT).show()
    }

    private fun xuat() {
        val k = ketQua ?: return
        thread {
            try {
                val f = File(core.callAttr("tuxa_excel", k.toString()).toString())
                val fm = File(core.callAttr("tuxa_ban_do", k.toString()).toString())
                val fk = File(core.callAttr("tuxa_khao_sat", ma, k.toString()).toString())
                ui.post {
                    val i = Intent(Intent.ACTION_SEND_MULTIPLE)
                    i.type = "*/*"
                    i.putParcelableArrayListExtra(Intent.EXTRA_STREAM, arrayListOf(
                        FileProvider.getUriForFile(this, "vn.vinalite.camlink.files", f),
                        FileProvider.getUriForFile(this, "vn.vinalite.camlink.files", fm),
                        FileProvider.getUriForFile(this, "vn.vinalite.camlink.files", fk)))
                    i.putExtra(Intent.EXTRA_TEXT, "Kiểm tra từ xa ${k.optString("du_an")} ${k.optString("luc")}: ${k.optInt("dat")}/${k.optInt("tong_cam")} cam đạt")
                    i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    startActivity(Intent.createChooser(i, "Gửi kết quả kiểm tra từ xa"))
                }
            } catch (e: Exception) {
                ui.post { nk.ghi("✖ Không xuất được Excel: ${e.message}") }
            }
        }
    }

}
