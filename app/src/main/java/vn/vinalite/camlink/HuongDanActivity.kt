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
        "A2. DỰ ÁN MỚI TỪ LITEMARK (không cần file khảo sát)" to listOf(
            "Trên LiteMark: kết thúc khảo sát công trình camera → bấm \"📹 Chuyển sang CamLink\". CamLink mở ra và nhận dự án: đủ điểm, đúng số ghim, đúng toạ độ.",
            "Máy khác: mở CamLink → Kiểm tra từ xa → hiện \"Có dự án mới từ LiteMark\" → bấm để nhận.",
            "Bấm \"📥 Nạp file tên miền\" → chọn file DDNS của bên cấp. App tự ghép tên miền vào ghim (theo mã TT và toạ độ) và báo điểm nào chưa ghép chắc.",
            "Điểm chưa có tên miền: lúc cài tại cột app hiện danh sách tên miền gần nhất để chọn; tên miền đã dùng không chọn lại được.",
            "Cài xong, tên miền + MAC cam tự ghi về ghim LiteMark; kiểm tra từ xa thì cam lỗi tự hiện trên bản đồ LiteMark."
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
        "D. KIỂM TRA TỪ XA + SỬA TỪ XA (ở đâu cũng được)" to listOf(
            "Bấm \"Kiểm tra từ xa cả dự án\" → chọn dự án (hoặc nạp file Excel cấu hình cũ: tên miền, user/pass No-IP).",
            "Kiểm xong app mở MÀN HÌNH GIÁM SÁT: mỗi điểm một khung thu nhỏ (lên/tổng, ảnh từng cam). Bấm khung → phóng to: bấy nhiêu cam bấy nhiêu ô, cam lên phát TRỰC TIẾP ngay, cam lỗi ghi lý do trong ô. ‹ Lưới để quay lại; 📋 Chi tiết/sửa để xem bằng chứng, link, user/pass và nút sửa.",
            "App kiểm tra TẤT CẢ điểm cùng lúc qua 4G (khoảng 1–2 phút), mỗi điểm QUÉT chính tên miền (hơn 40 port) để đếm số cam THẬT đang gắn, không tin số trong file; mỗi cam qua 5 tầng: tên miền → IP → đường truyền → port → ảnh. App tự đối chiếu chéo: cùng một cam ở 2 tên miền, cam khác lần trước, nhiều tên miền trỏ cùng IP, cam lạ ngoài cấu hình → báo ⚠.",
            "Đọc bảng: 🟢 đạt · 🟡 lỗi cấu hình (thường sửa từ xa được) · 🔴 lỗi phần cứng/mạng (phải có người tại điểm). Điểm lỗi nằm trên cùng. \"⬇ VỪA RỚT\" = cam mới hỏng so với lần kiểm trước.",
            "Bấm vào cam: xem nguyên nhân, việc tiếp theo, ảnh chụp, link web, link xem trực tiếp, user/pass cam và No-IP. Có nút Mở web, ▶ Xem, Copy.",
            "Cam đang chạy tốt: app CHỈ ĐỌC (kể cả cấu hình bên trong: DDNS cam 1, gateway, DNS, giờ) và báo cáo, không thay đổi gì. Cam có vấn đề (treo, đổi port…): app TỰ SỬA, sửa xong kiểm tra lại cấu hình, mất/sai thì khôi phục, rồi ghi \"ĐÃ TỰ SỬA\" vào bằng chứng.",
            "Cam có nút \"🔧 Sửa từ xa\" (khởi động lại cam, đặt lại port RTSP…): bấm → LÀM. App tự sửa rồi tự kiểm tra lại điểm đó và báo kết quả.",
            "Không sửa từ xa được: làm theo \"Việc tiếp theo\" (gọi người tại điểm / gọi VNPT / cử thợ).",
            "Bấm \"📤 Xuất Excel + gửi\" để gửi bảng kết quả qua Zalo/Gmail.",
            "🔗 LiteMark (một lần cho mỗi dự án): bấm \"🔗 LiteMark\" → dán khoá kết nối (lấy trong LiteMark → Tài khoản → Kết nối CamLink) → chọn đúng công trình trong danh sách (⭐ = khớp tên/số điểm). Từ đó vị trí điểm lấy theo ghim thực tế của LiteMark; mỗi lần kiểm xong, cam lỗi tự hiện đỏ/vàng trên bản đồ công trình LiteMark; ở màn giám sát có nút \"🔗 LiteMark\" mở thẳng điểm đó."
        ),
        "D2. THEO DÕI ỔN ĐỊNH MỘT CAM (cam chập chờn)" to listOf(
            "Dưới ô cam (màn Kiểm tra từ xa hoặc màn giám sát) bấm \"📈 Theo dõi\" → chọn 2 giờ / 6 giờ / 24 giờ / tuỳ chọn. Bật cam nào thì chỉ theo dõi cam đó; bật nhiều cam được.",
            "App chạy nền (có thông báo trên điện thoại), mỗi 30 giây đo: mạng điện thoại, tên miền → IP, port cam, cam khác cùng điểm, luồng video. Điện thoại mất mạng thì không tính là cam rớt.",
            "Hết giờ (hoặc bấm Dừng & lấy báo cáo) → báo cáo PDF 1–3 trang: tóm tắt, nguyên nhân các lần rớt, danh sách lần rớt, đề xuất khắc phục, ảnh trước/sau. Chạm thông báo để mở, có nút gửi Zalo.",
            "Nút \"📈 Theo dõi\" trên cùng màn Kiểm tra từ xa: xem các cam đang theo dõi và mở lại báo cáo cũ.",
            "Để điện thoại cắm sạc, có sóng ổn định. Dữ liệu khoảng 1 MB/ngày mỗi cam, tự xoá sau 7 ngày (PDF giữ lại)."
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
