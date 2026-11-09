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
        val ten = ds.map { "${it[1]}  (${it[2]} điểm · ${it[3]} cam)" } + "＋ Nạp file Excel cấu hình (DNS, user/pass…)"
        AlertDialog.Builder(this)
            .setTitle("Kiểm tra dự án nào?")
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

    private fun batDau() {
        val cu = core.callAttr("tuxa_gan_nhat", ma).toString()
        if (cu.isNotEmpty()) { ketQua = JSONObject(cu); veBang("Kết quả lần trước — đang kiểm tra mới…") }
        kiem()
    }

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
        nk.ghi("⏳ Đang kiểm tra $tenDuAn qua Internet (chỉ đọc)…")
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
        tt.addView(chu("$dat/$tong cam ĐẠT", 20f, true, if (dat == tong) "#1D7A46" else "#B42318"))
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
        val wm = p.optString("web_modem")
        if (wm.isNotEmpty()) t.addView(link("🌐 Web modem: $wm") { moLink(wm) })
        t.addView(chu(p.optString("ghi_so"), 12f, mau = "#5B6776"))
        t.addView(nut("Sửa số cam thực tế (đang ${p.optInt("so")})") { suaSoCam(p) })
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
        ct.visibility = if (muc == "xanh") View.GONE else View.VISIBLE
        dau.setOnClickListener { ct.visibility = if (ct.visibility == View.VISIBLE) View.GONE else View.VISIBLE }

        ct.addView(chu("Nguyên nhân: ${c.optString("nguyen_nhan")}", 14f))
        val viec = c.optJSONArray("viec")
        if (viec != null && viec.length() > 0) {
            ct.addView(chu("Việc tiếp theo:", 14f, true, "#0F5D8C"))
            for (i in 0 until viec.length()) ct.addView(chu("${i + 1}) ${viec.getString(i)}", 14f))
        }
        val anh = c.optString("anh")
        if (anh.isNotEmpty() && File(anh).exists()) {
            val iv = ImageView(this)
            iv.setImageBitmap(BitmapFactory.decodeFile(anh))
            iv.adjustViewBounds = true
            ct.addView(iv, LinearLayout.LayoutParams(-1, -2))
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
                ui.post {
                    val i = Intent(Intent.ACTION_SEND)
                    i.type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    i.putExtra(Intent.EXTRA_STREAM, FileProvider.getUriForFile(this, "vn.vinalite.camlink.files", f))
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
