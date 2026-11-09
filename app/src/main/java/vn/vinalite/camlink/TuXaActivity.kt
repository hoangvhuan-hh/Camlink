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
    private val TOI_DA_LIVE = 4

    /** Phát trực tiếp RTSP ngay trong thẻ cam. Quá TOI_DA_LIVE thì dừng cái cũ nhất. */
    private fun phatLive(khungAnh: FrameLayout, url: String, trangThai: TextView) {
        if (url.isEmpty()) { trangThai.text = "Không có link video"; return }
        dangPhat.remove(url)?.release()
        while (dangPhat.size >= TOI_DA_LIVE) { val k = dangPhat.keys.first(); dangPhat.remove(k)?.release() }
        khungAnh.removeAllViews()
        val pv = PlayerView(this)
        pv.useController = false
        khungAnh.addView(pv, FrameLayout.LayoutParams(-1, dp(200)))
        val p = ExoPlayer.Builder(this).build()
        pv.player = p
        p.setMediaSource(RtspMediaSource.Factory().setForceUseRtpTcp(true).createMediaSource(MediaItem.fromUri(url)))
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
                trangThai.text = "✖ KHÔNG XEM TRỰC TIẾP ĐƯỢC: ${error.errorCodeName} — port video chưa mở hoặc cam không phát"
                trangThai.setTextColor(Color.parseColor("#B42318"))
            }
        })
        p.prepare(); p.playWhenReady = true
        dangPhat[url] = p
    }

    override fun onDestroy() { dangPhat.values.forEach { it.release() }; dangPhat.clear(); super.onDestroy() }
    override fun onPause() { dangPhat.values.forEach { it.pause() }; super.onPause() }
    override fun onResume() { dangPhat.values.forEach { it.play() }; super.onResume() }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    inner class NhatKy {
        fun ghi(s: String) { ui.post { tienDo.text = s.trim() } }
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
        goc.addView(chu("Kiểm tra từ xa", 22f, true))
        val hang = LinearLayout(this)
        hang.orientation = LinearLayout.HORIZONTAL
        hang.addView(nut("🔄 Kiểm tra lại") { kiem() }, LinearLayout.LayoutParams(0, -2, 1f))
        hang.addView(nut("📤 Xuất Excel + gửi") { xuat() }, LinearLayout.LayoutParams(0, -2, 1f))
        goc.addView(hang)
        goc.addView(nut("📁 Chọn dự án / nạp file cấu hình") { chonDuAn() })
        val hang2 = LinearLayout(this)
        hang2.orientation = LinearLayout.HORIZONTAL
        hang2.addView(nut("🗺 Bản đồ điểm lỗi") { moBanDo() }, LinearLayout.LayoutParams(0, -2, 1f))
        hang2.addView(nut("🔴 Live tất cả") { liveTatCa() }, LinearLayout.LayoutParams(0, -2, 1f))
        goc.addView(hang2)
        tienDo = chu("", 13f, mau = "#0F5D8C")
        tienDo.setPadding(dp(4), dp(4), dp(4), dp(4))
        goc.addView(tienDo)
        khung = LinearLayout(this)
        khung.orientation = LinearLayout.VERTICAL
        val cuon = ScrollView(this)
        cuon.addView(khung)
        goc.addView(cuon, LinearLayout.LayoutParams(-1, 0, 1f))
        setContentView(goc)
        chonDuAn()
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
        val uri: Uri = data?.data ?: return
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
    private fun gan4G(bat: Boolean): Boolean {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        if (!bat) { cm.bindProcessToNetwork(null); return true }
        val dd = cm.allNetworks.firstOrNull { n ->
            val nc = cm.getNetworkCapabilities(n)
            nc?.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) == true && nc.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
        } ?: return false
        return cm.bindProcessToNetwork(dd)
    }

    // ---------------- kiểm tra ----------------
    private fun kiem() {
        if (ma.isEmpty() || dangChay) return
        dangChay = true
        ketQua = null
        khung.removeAllViews()   // xoá sạch kết quả cũ trước khi kiểm tra lại
        khung.addView(chu("⏳ Đang kiểm tra $tenDuAn…\nCam đang chạy tốt: chỉ đọc và báo cáo.\nCam có vấn đề: app tự sửa rồi kiểm tra lại cấu hình.", 15f, mau = "#0F5D8C"))
        nk.ghi("⏳ Đang kiểm tra $tenDuAn qua Internet…")
        thread {
            val co4G = gan4G(true)
            try {
                val j = core.callAttr("tuxa_kiem", ma, nk).toString()
                ui.post {
                    ketQua = JSONObject(j)
                    veBang(if (co4G) "Đã kiểm tra qua 4G (như IOC gọi từ ngoài)" else "⚠ Không bật được 4G — đã kiểm tra qua WiFi; nếu đang ở trong WiFi của chính điểm, kết quả có thể sai")
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
        tt.addView(chu("File khảo sát ghi: $tongFile cam\nQuét thực tế trên các tên miền: $tongQuet cam" +
            (if (camLa > 0) "\n  = theo file $tongFile cam + $camLa CAM LẠ ngoài hồ sơ" else "") +
            (if (k.optInt("khong_thay") > 0) "\nFile ghi nhưng không thấy cam: ${k.optInt("khong_thay")} vị trí" else ""), 14f))
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
        for (i in 0 until cams.length()) t.addView(dongCam(p, cams.getJSONObject(i)))
        return t
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
        ct.visibility = View.VISIBLE   // luôn mở: cam lên được phải thấy ảnh ngay
        dau.setOnClickListener { ct.visibility = if (ct.visibility == View.VISIBLE) View.GONE else View.VISIBLE }

        ct.addView(chu("Nguyên nhân: ${c.optString("nguyen_nhan")}", 14f))
        val viec = c.optJSONArray("viec")
        if (viec != null && viec.length() > 0) {
            ct.addView(chu("Việc tiếp theo:", 14f, true, "#0F5D8C"))
            for (i in 0 until viec.length()) ct.addView(chu("${i + 1}) ${viec.getString(i)}", 14f))
        }
        // Khung hình: LIVE trực tiếp (bấm là phát tại chỗ); ảnh chụp chỉ là bằng chứng lúc kiểm
        val anh = c.optString("anh")
        val live = c.optString("live")
        if (live.isNotEmpty() || (anh.isNotEmpty() && File(anh).exists())) {
            val khungAnh = FrameLayout(this)
            val tt = chu("", 13f, true, "#1D7A46")
            if (anh.isNotEmpty() && File(anh).exists()) {
                val iv = ImageView(this)
                iv.setImageBitmap(BitmapFactory.decodeFile(anh))
                iv.adjustViewBounds = true
                khungAnh.addView(iv, FrameLayout.LayoutParams(-1, -2))
                tt.text = "Ảnh chụp lúc kiểm · bấm ▶ để xem TRỰC TIẾP"
            }
            val nutLive = Button(this)
            nutLive.text = "▶ XEM TRỰC TIẾP"
            nutLive.isAllCaps = false
            nutLive.setOnClickListener { phatLive(khungAnh, live, tt) }
            khungAnh.addView(nutLive, FrameLayout.LayoutParams(-2, -2, android.view.Gravity.CENTER))
            ct.addView(khungAnh, LinearLayout.LayoutParams(-1, -2))
            ct.addView(tt)
            if (muc == "xanh") khungAnh.tag = Triple(khungAnh, live, tt)   // để nút "Live tất cả" bật lên
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

    private fun moBanDo() {
        val k = ketQua ?: run { Toast.makeText(this, "Kiểm tra trước đã", Toast.LENGTH_SHORT).show(); return }
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
                ui.post {
                    val i = Intent(Intent.ACTION_SEND_MULTIPLE)
                    i.type = "*/*"
                    i.putParcelableArrayListExtra(Intent.EXTRA_STREAM, arrayListOf(
                        FileProvider.getUriForFile(this, "vn.vinalite.camlink.files", f),
                        FileProvider.getUriForFile(this, "vn.vinalite.camlink.files", fm)))
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
