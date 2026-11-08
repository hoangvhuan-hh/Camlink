package vn.vinalite.camlink

import android.app.Activity
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView

/** Hướng dẫn sử dụng ngay trong app — chỉ các bước cần làm. */
class HuongDanActivity : Activity() {
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private val muc = listOf(
        "A. LÀM MỘT LẦN (ở nhà)" to listOf(
            "Bấm \"Thêm / cập nhật dự án (file Excel)\" → chọn file khảo sát của dự án. Mỗi file = 1 dự án; có dự án mới thì thêm file mới, dự án cũ giữ nguyên.",
            "Bấm \"User / pass cam và modem\" → nhập user/pass cam, user/pass modem → Lưu. App nhớ cho mọi dự án.",
            "Cho phép app dùng Vị trí khi điện thoại hỏi."
        ),
        "B. CÀI MỘT ĐIỂM (đứng tại điểm)" to listOf(
            "Cấp nguồn cam, cắm cam vào modem của điểm.",
            "Điện thoại vào WiFi của modem điểm đó. Bật luôn 4G (dữ liệu di động).",
            "Bấm \"CHẠY CÀI ĐIỂM NÀY\". App tự tìm điểm gần nhất theo GPS.",
            "Xem bảng \"Kiểm tra trước khi cài\": đúng tên điểm, có dòng WiFi máy/modem → bấm \"BẮT ĐẦU CÀI\".",
            "Chờ thanh trạng thái chạy xong (vài phút). App tự: tìm cam → DDNS cam 1 → đặt port, IP (.200, .201…) → mở port modem → gọi tên miền qua 4G.",
            "App tự mở màn hình SƠ ĐỒ: mỗi cam có ảnh chụp lấy qua tên miền và nút \"▶ Xem trực tiếp\". Thấy ảnh = cài đạt.",
            "Bấm \"Gửi kết quả\" → chọn Zalo/Gmail để gửi file kết quả."
        ),
        "C. ĐỌC KẾT QUẢ" to listOf(
            "Khung xanh \"Xem được từ ngoài\" = đạt, IOC xem được.",
            "Khung đỏ: đọc dòng ⚠ ngay dưới cam đó. Hay gặp: \"port chưa mở\" → modem tắt UPnP, mở port tay theo bảng trong kết quả; \"tên miền không phân giải\" → chờ 2–5 phút rồi bấm \"Kiểm tra từ xa\".",
            "Dòng \"Lúc cài: DDNS CHƯA nhập …\" → xem lý do ghi ở đó (sai user/pass No-IP, hãng cam chưa hỗ trợ…).",
            "\"CGNAT\" trong nhật ký → gọi nhà mạng xin IP public cho đường truyền đó."
        ),
        "D. KIỂM TRA TỪ XA (ở đâu cũng được)" to listOf(
            "Bấm \"Kiểm tra từ xa (không thay đổi gì)\" → chọn điểm trong danh sách (nhiều dự án thì đầu dòng ghi [tên dự án]; điểm đã cài có dấu ✔).",
            "App gọi tên miền của điểm, chụp ảnh từng cam và mở sơ đồ. Không thay đổi gì trên cam/modem."
        ),
        "E. NÚT KHÁC" to listOf(
            "\"Chọn điểm bằng tay\": dùng khi GPS yếu hoặc dự án chưa có toạ độ.",
            "\"Xem sơ đồ + ảnh lần chạy gần nhất\": mở lại kết quả lần trước.",
            "\"Thu mẫu thiết bị\": khi app báo gặp cam/modem lạ — đứng tại điểm, vào WiFi modem, bấm nút này. Xong app tự mở bảng chia sẻ → chọn Zalo/Gmail gửi cho Claude (lỡ tắt thì bấm \"Gửi kết quả\", file mẫu có kèm trong đó). Mục đích: Claude đọc mẫu để dạy app điều khiển cam/modem loại mới. Chỉ đọc, không thay đổi gì."
        ),
        "F. LƯU Ý" to listOf(
            "Ở xa điểm hơn 1 km app không cho cài, chỉ cho kiểm tra từ xa.",
            "Cam đã đúng sẵn thì app giữ nguyên; chạy lại nhiều lần không sao.",
            "Đổi pass modem hiện vẫn làm tay (chờ bổ sung theo model modem VNPT)."
        )
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val goc = LinearLayout(this)
        goc.orientation = LinearLayout.VERTICAL
        goc.setPadding(dp(16), dp(20), dp(16), dp(28))
        goc.setBackgroundColor(Color.parseColor("#EEF1F4"))
        goc.addView(TextView(this).apply {
            text = "Hướng dẫn sử dụng CamLink"
            textSize = 22f
            setTypeface(null, Typeface.BOLD)
            setTextColor(Color.parseColor("#17202B"))
        })
        for ((tieuDe, buoc) in muc) {
            val the = LinearLayout(this)
            the.orientation = LinearLayout.VERTICAL
            the.setPadding(dp(14), dp(12), dp(14), dp(12))
            the.background = GradientDrawable().apply {
                setColor(Color.WHITE)
                cornerRadius = dp(10).toFloat()
            }
            val lp = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT)
            lp.topMargin = dp(12)
            the.addView(TextView(this).apply {
                text = tieuDe
                textSize = 16f
                setTypeface(null, Typeface.BOLD)
                setTextColor(Color.parseColor("#0F5D8C"))
            })
            buoc.forEachIndexed { i, s ->
                the.addView(TextView(this).apply {
                    text = "${i + 1}. $s"
                    textSize = 15f
                    setTextColor(Color.parseColor("#17202B"))
                    setPadding(0, dp(6), 0, 0)
                    setLineSpacing(0f, 1.15f)
                })
            }
            goc.addView(the, lp)
        }
        setContentView(ScrollView(this).apply { addView(goc) })
    }
}
