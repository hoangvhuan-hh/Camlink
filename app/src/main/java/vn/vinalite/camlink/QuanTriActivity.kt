package vn.vinalite.camlink

import android.app.Activity
import android.app.AlertDialog
import android.graphics.Color
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import com.chaquo.python.Python
import org.json.JSONArray
import org.json.JSONObject

/**
 * MÀN QUẢN TRỊ & KHÔI PHỤC (Huan 15/11) — để test tròn mọi vai trên một máy.
 *  - Chủ: máy tin cậy, mở bằng PIN, toàn quyền (nạp két, cấp mã thợ, thu hồi, xoay mật khẩu, tạo Xem, khôi phục, nhật ký).
 *  - Thợ: bật "🧪 Đóng vai thợ" để giả lập máy lạ — nhập mã, chỉ làm việc hẹp, KHÔNG xem được mật khẩu; chủ thu hồi là mất quyền.
 * Chưa đưa lên chợ; chỉ thêm, không đụng logic cũ và liên kết LiteMark.
 */
class QuanTriActivity : Activity() {
    private val core by lazy { Python.getInstance().getModule("camlink_core") }
    private lateinit var goc: LinearLayout
    private var pin: String? = null                 // PIN chủ, giữ trong phiên màn hình
    private var vaiTho = false                       // đang đóng vai thợ (test)
    private val mayThat by lazy { "may-" + (Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID) ?: "x") }
    private val mayTho = "may-tho-test"
    private fun may() = if (vaiTho) mayTho else mayThat

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        goc = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16), dp(16), dp(16), dp(16)) }
        setContentView(ScrollView(this).apply { addView(goc) })
        ve()
    }

    private fun chu(t: String, sz: Float = 15f, dam: Boolean = false, mau: String = "#20303A"): TextView {
        val tv = TextView(this); tv.text = t; tv.textSize = sz; tv.setTextColor(Color.parseColor(mau))
        if (dam) tv.setTypeface(tv.typeface, android.graphics.Typeface.BOLD)
        tv.setPadding(0, dp(4), 0, dp(4)); return tv
    }

    private fun nut(t: String, bam: () -> Unit) = Button(this).apply {
        text = t; isAllCaps = false; textSize = 15f
        setOnClickListener { bam() }
        goc.addView(this, LinearLayout.LayoutParams(-1, -2).apply { topMargin = dp(4) })
    }

    private fun hoi(tieu: String, goi: String, matKhau: Boolean, xong: (String) -> Unit) {
        val o = EditText(this); o.hint = goi
        if (matKhau) o.inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
        AlertDialog.Builder(this).setTitle(tieu).setView(o)
            .setPositiveButton("OK") { _, _ -> xong(o.text.toString()) }
            .setNegativeButton("Huỷ", null).show()
    }

    private fun bao(t: String) = AlertDialog.Builder(this).setMessage(t).setPositiveButton("OK", null).show()

    // ------------------------------------------------------------------ vẽ theo vai
    private fun ve() {
        goc.removeAllViews()
        goc.addView(chu("🔐 Quản trị & Khôi phục", 20f, true))
        val daTao = core.callAttr("qt_da_tao").toBoolean()
        if (!daTao) {
            goc.addView(chu("Chưa có tài khoản chủ. Tạo để quản lý mật khẩu mọi công trình, cấp quyền cho thợ, khôi phục khi quên."))
            nut("➕ Tạo tài khoản chủ") { taoTaiKhoan() }
            return
        }
        val vai = core.callAttr("qt_quyen", may(), "").toString()
        goc.addView(chu("Máy này: " + (if (vaiTho) "🧪 ĐANG ĐÓNG VAI THỢ (test)" else "máy của bạn") + " · vai hiện tại: " +
            when (vai) { "chu" -> "CHỦ"; "tho" -> "THỢ (có phiên)"; else -> "CHƯA CÓ QUYỀN" }, 13f, false, "#5B6776"))

        if (vaiTho) veTho(vai) else veChu(vai)

        goc.addView(chu(" ", 8f))
        nut(if (vaiTho) "⬅ Thoát vai thợ (về máy chủ)" else "🧪 Đóng vai thợ (test trên máy này)") {
            vaiTho = !vaiTho; ve()
        }
    }

    // ------------------------------------------------------------------ CHỦ
    private fun veChu(vai: String) {
        if (vai != "chu") {
            goc.addView(chu("Máy này chưa phải máy tin cậy. Mở bằng PIN để thêm làm máy chủ, hoặc dùng mã khôi phục.", 13f, false, "#B42318"))
            nut("Thêm máy này làm máy chủ (nhập PIN)") {
                hoi("PIN chủ", "PIN", true) { p ->
                    try { core.callAttr("qt_them_thiet_bi", p, mayThat, android.os.Build.MODEL ?: "Máy"); pin = p; ve() }
                    catch (e: Exception) { bao("Sai PIN hoặc lỗi: ${e.message?.take(80)}") }
                }
            }
            return
        }
        if (pin == null) {
            nut("🔓 Mở khoá (nhập PIN)") { hoi("PIN chủ", "PIN", true) { p ->
                val kq = try { core.callAttr("qt_kiem_pin", p).toString() } catch (e: Exception) { "Không kiểm được PIN: ${e.message?.take(80)}" }
                if (kq.isNotEmpty()) { bao(kq); return@hoi }      // PIN sai thì KHÔNG mở khoá
                pin = p; Toast.makeText(this, "Đã mở khoá", Toast.LENGTH_SHORT).show(); ve() } }
            return
        }
        nut("📥 Nạp mật khẩu dự án vào két") { chonDuAn { ma -> try {
            val n = core.callAttr("qt_nap_tu_cai_dat", pin, ma).toInt(); bao("Đã nạp $n điểm vào két.") } catch (e: Exception) { bao(loi(e)) } } }
        nut("👁 Xem két (chỉ chủ)") { chonDuAn { ma -> chonDiem(ma) { stt ->
            try { val d = JSONObject(core.callAttr("qt_xem_mat_khau", may(), ma, stt, pin).toString())
                bao("Điểm $stt:\nCam user: ${d.optString("cam_user")}\nCam pass: ${d.optString("cam_pw")}\n" +
                    "Modem: ${d.optString("modem_user")} / ${d.optString("modem_pw")}\n" +
                    "Tài khoản Xem: ${d.optJSONArray("xem")?.length() ?: 0}") } catch (e: Exception) { bao(loi(e)) } } } }
        nut("🎟 Cấp mã một lần cho thợ") { chonDuAn { ma -> chonDiem(ma, true) { stt ->
            val pv = if (stt == "*") ma else "$ma:$stt"
            hoi("Số giờ hiệu lực", "VD 24", false) { g -> try {
                val code = core.callAttr("qt_cap_ma_mot_lan", pin, pv, g.toIntOrNull() ?: 24).toString()
                bao("Mã cho thợ (phạm vi $pv, $g giờ):\n\n   $code\n\nGửi thợ. Hết giờ hoặc bạn thu hồi là mã vô dụng.") } catch (e: Exception) { bao(loi(e)) } } } } }
        nut("📋 Phiên thợ đang hoạt động / thu hồi") { phienList() }
        nut("🔄 Xoay mật khẩu (không đụng tài khoản Xem)") { chonDuAn { ma -> chonDiem(ma) { stt ->
            hoi("Mật khẩu admin MỚI", "mật khẩu mới", false) { mk -> try {
                val tb = core.callAttr("qt_xoay_mat_khau", pin, may(), ma, stt, mk, false).toString(); bao(tb) } catch (e: Exception) { bao(loi(e)) } } } } }
        nut("➕ Tạo tài khoản Xem cho khách") { chonDuAn { ma -> chonDiem(ma) { stt ->
            hoi("Tên tài khoản Xem", "vd khach", false) { u -> hoi("Mật khẩu Xem", "mật khẩu", false) { p -> try {
                val tb = core.callAttr("qt_tao_tai_khoan_xem", pin, may(), ma, stt, u, p).toString(); bao(tb) } catch (e: Exception) { bao(loi(e)) } } } } } }
        nut("🧹 Gỡ tài khoản \"chỉ xem\" khỏi cam") { chonDuAn { ma -> Thread {
            val r = try { JSONObject(core.callAttr("go_tai_khoan_xem", ma).toString()) } catch (e: Exception) { JSONObject().put("tom_tat", loi(e)) }
            val ds = r.optJSONArray("loi"); val sb = StringBuilder(r.optString("tom_tat"))
            if (ds != null && ds.length() > 0) { sb.append("\n\nChưa xử lý được:"); for (i in 0 until ds.length()) sb.append("\n• ").append(ds.optString(i)) }
            runOnUiThread { bao(sb.toString()) } }.start() } }
        nut("🆘 Khôi phục khi quên mật khẩu") { chonDuAn { ma -> chonDiem(ma) { stt ->
            hoi("Tên miền cam", "vd phuly-chuaphapbao.ddns.net", false) { dom -> hoi("Port web cam", "vd 8080", false) { ht -> Thread {
                val r = try { JSONObject(core.callAttr("qt_khoi_phuc_doc_ma", ma, stt, dom, ht.toIntOrNull() ?: 8080).toString()) } catch (e: Exception) { JSONObject().put("loi", loi(e)) }
                runOnUiThread { bao(if (r.optBoolean("ok")) "Khôi phục điểm $stt:\n" + r.optString("ghi_chu") else "Chưa khôi phục được: " + r.optString("loi")) } }.start() } } } } }
        nut("🔎 Nhận diện hãng cam (ONVIF)") { chonDuAn { ma -> chonDiem(ma) { stt -> Thread {
            val r = try { JSONObject(core.callAttr("qt_nhan_dien_hang", ma, stt, pin).toString()) } catch (e: Exception) { JSONObject().put("loi", loi(e)) }
            runOnUiThread { bao(if (r.optBoolean("ok")) "Điểm $stt:\nHãng: ${r.optString("hang")}\nModel: ${r.optString("model")}\nFirmware: ${r.optString("firmware")}\nSerial: ${r.optString("serial")}" else "Không đọc được: " + r.optString("loi")) } }.start() } } }
        nut("➕ Thêm máy tin cậy khác") { bao("Mở app trên máy kia → Quản trị → \"Thêm máy này làm máy chủ\" → nhập PIN.\nMã máy này: $mayThat") }
        nut("📜 Nhật ký") { nhatKy() }
        nut("🔑 Đổi PIN") { hoi("PIN cũ", "PIN cũ", true) { c -> hoi("PIN mới", "PIN mới", true) { m -> try {
            core.callAttr("qt_doi_pin", c, m); bao("Đã đổi PIN.") } catch (e: Exception) { bao(loi(e)) } } } }
    }

    // ------------------------------------------------------------------ THỢ
    private fun veTho(vai: String) {
        if (vai != "tho") {
            goc.addView(chu("Máy thợ chưa có quyền. Nhập mã chủ cấp để xin phiên.", 13f, false, "#B42318"))
            nut("Nhập mã của chủ") { hoi("Mã một lần", "6 số", false) { ma ->
                if (core.callAttr("qt_tho_dung_ma", ma, mayTho).toBoolean()) { Toast.makeText(this, "Đã có phiên thợ", Toast.LENGTH_SHORT).show(); ve() }
                else bao("Mã sai, hết hạn, hoặc đã bị thu hồi.") } }
            return
        }
        goc.addView(chu("Thợ làm được việc hẹp; KHÔNG xem được mật khẩu; chủ thu hồi là mất quyền.", 13f, false, "#1D7A46"))
        nut("🔁 Khởi động lại cam (thử)") { thoThu("khoi_dong_cam") }
        nut("📷 Chụp ảnh (thử)") { thoThu("chup_anh") }
        nut("👁 Thử XEM mật khẩu (phải bị chặn)") {
            try { core.callAttr("qt_xem_mat_khau", mayTho, "pl", "2", pin ?: ""); bao("LỖI: lẽ ra phải bị chặn!") }
            catch (e: Exception) { bao("✓ Đúng: thợ bị chặn xem mật khẩu.\n(${e.message?.take(60)})") }
        }
        nut("🔄 Thử xoay mật khẩu (phải bị chặn)") {
            try { core.callAttr("qt_xoay_mat_khau", pin ?: "", mayTho, "pl", "2", "x", false); bao("LỖI: lẽ ra phải bị chặn!") }
            catch (e: Exception) { bao("✓ Đúng: thợ không xoay được mật khẩu.") }
        }
    }

    private fun thoThu(viec: String) {
        // mô phỏng thao tác thợ qua cổng kiểm vai (app tự chạy, thợ không thấy mật khẩu)
        try {
            val r = core.callAttr("qt_quyen", mayTho, "pl:2").toString()
            bao(if (r == "tho") "✓ Thợ được phép '$viec' trong phạm vi được cấp — app sẽ tự chạy bằng mật khẩu trong két (thợ không thấy)."
                else "Thợ không có quyền ở phạm vi này.")
        } catch (e: Exception) { bao(loi(e)) }
    }

    // ------------------------------------------------------------------ phụ trợ
    private fun taoTaiKhoan() {
        hoi("Đặt PIN chủ", "PIN (4-6 số)", true) { p1 -> hoi("Nhập lại PIN", "PIN", true) { p2 ->
            if (p1 != p2 || p1.length < 4) { bao("PIN không khớp hoặc quá ngắn."); return@hoi }
            try {
                val maKp = core.callAttr("qt_tao_tai_khoan", p1, mayThat, android.os.Build.MODEL ?: "Máy chủ").toString()
                pin = p1
                AlertDialog.Builder(this).setTitle("GHI LẠI MÃ KHÔI PHỤC").setCancelable(false)
                    .setMessage("Mất hết máy thì mở lại bằng mã này. GHI RA GIẤY, cất nơi an toàn. Không ai lấy lại được nếu mất:\n\n$maKp")
                    .setPositiveButton("Đã ghi") { _, _ -> ve() }.show()
            } catch (e: Exception) { bao(loi(e)) }
        } }
    }

    private fun chonDuAn(xong: (String) -> Unit) {
        val ds = JSONArray(core.callAttr("ds_du_an").toString())
        if (ds.length() == 0) { bao("Chưa có dự án nào. Nạp file khảo sát ở màn chính trước."); return }
        if (ds.length() == 1) { xong(ds.getJSONArray(0).getString(0)); return }
        val ten = (0 until ds.length()).map { ds.getJSONArray(it).getString(1) }.toTypedArray()
        AlertDialog.Builder(this).setTitle("Chọn dự án").setItems(ten) { _, i -> xong(ds.getJSONArray(i).getString(0)) }.show()
    }

    private fun chonDiem(ma: String, themCaDuAn: Boolean = false, xong: (String) -> Unit) {
        val ds = JSONArray(core.callAttr("qt_ds_diem", ma).toString())
        val nhan = ArrayList<String>(); val stt = ArrayList<String>()
        if (themCaDuAn) { nhan.add("★ Cả dự án"); stt.add("*") }
        for (i in 0 until ds.length()) { nhan.add("Điểm ${ds.getJSONArray(i).getString(0)} · ${ds.getJSONArray(i).getString(1)}"); stt.add(ds.getJSONArray(i).getString(0)) }
        if (nhan.isEmpty()) { bao("Dự án chưa có điểm."); return }
        AlertDialog.Builder(this).setTitle("Chọn điểm").setItems(nhan.toTypedArray()) { _, i -> xong(stt[i]) }.show()
    }

    private fun phienList() {
        val ds = JSONArray(core.callAttr("qt_phien_dang_song").toString())
        if (ds.length() == 0) { bao("Không có phiên thợ nào đang hoạt động."); return }
        val nhan = (0 until ds.length()).map { val p = ds.getJSONObject(it)
            "Phạm vi ${p.optString("pham_vi")} · máy ${p.optString("thiet_bi", "chưa gắn")} · ${(p.optDouble("gio")).toInt()}h" }.toTypedArray()
        AlertDialog.Builder(this).setTitle("Phiên thợ — chạm để thu hồi").setItems(nhan) { _, i ->
            val cs = ds.getJSONObject(i).optInt("chi_so")
            hoi("PIN để thu hồi", "PIN", true) { p -> try { core.callAttr("qt_thu_hoi_phien", p, cs, null); bao("Đã thu hồi phiên.") } catch (e: Exception) { bao(loi(e)) } }
        }.setNeutralButton("Thu hồi TẤT CẢ") { _, _ -> hoi("PIN", "PIN", true) { p ->
            try { core.callAttr("qt_thu_hoi_phien", p, null, null); bao("Đã thu hồi tất cả phiên thợ.") } catch (e: Exception) { bao(loi(e)) } } }
            .setNegativeButton("Đóng", null).show()
    }

    private fun nhatKy() {
        val ds = JSONArray(core.callAttr("qt_nhat_ky", 60).toString())
        val sb = StringBuilder()
        val f = java.text.SimpleDateFormat("dd/MM HH:mm")
        for (i in ds.length() - 1 downTo maxOf(0, ds.length() - 40)) { val x = ds.getJSONObject(i)
            sb.append(f.format(java.util.Date((x.optDouble("luc") * 1000).toLong()))).append(" · ")
                .append(x.optString("vai")).append(" · ").append(x.optString("viec")).append(" ").append(x.optString("muc")).append("\n") }
        AlertDialog.Builder(this).setTitle("Nhật ký").setMessage(if (sb.isEmpty()) "Trống" else sb.toString()).setPositiveButton("OK", null).show()
    }

    private fun loi(e: Exception) = e.message?.substringAfterLast("Error: ")?.take(120) ?: "lỗi"
}
