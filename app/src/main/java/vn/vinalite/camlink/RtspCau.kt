package vn.vinalite.camlink

import android.net.Network
import java.io.BufferedInputStream
import java.io.InputStream
import java.io.OutputStream
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import kotlin.concurrent.thread

/**
 * Cầu RTSP cục bộ: trình phát nối vào 127.0.0.1:<cổng cầu>, cầu nối ra cam qua tên miền (có thể qua mạng 4G chỉ định).
 * Lý do: nhiều cam (Oryza…) ghi trong SDP "a=control:rtsp://127.0.0.1:554/..." hoặc IP LAN → trình phát đi nối
 * vào localhost rồi báo ECONNREFUSED. Cầu viết lại mọi địa chỉ rtsp:// trong trả lời của cam về địa chỉ cầu,
 * và trong yêu cầu của trình phát về địa chỉ cam. Dữ liệu RTP xen kẽ ('$') đi qua nguyên vẹn.
 */
class RtspCau(private val host: String, private val port: Int, private val mang: Network? = null) {
    private var sv: ServerSocket? = null
    val cong: Int get() = sv?.localPort ?: 0

    fun bat(): Int {
        val s = ServerSocket(0, 4, InetAddress.getLoopbackAddress())
        sv = s
        thread(isDaemon = true) {
            while (!s.isClosed) {
                try {
                    val kh = s.accept()
                    thread(isDaemon = true) { phucVu(kh) }
                } catch (_: Exception) { break }
            }
        }
        return s.localPort
    }

    fun tat() { try { sv?.close() } catch (_: Exception) {} }

    /** rtsp://user:pass@host:port/duong → rtsp://user:pass@127.0.0.1:cong/duong */
    fun doiUrl(url: String): String =
        url.replaceFirst(Regex("^(rtsp://(?:[^@/]*@)?)[^/:]+(?::\\d+)?"), "$1" + "127.0.0.1:$cong")

    private fun phucVu(kh: Socket) {
        val cam = Socket()
        try {
            mang?.bindSocket(cam)
            cam.connect(InetSocketAddress(host, port), 8000)
            cam.soTimeout = 0
            kh.soTimeout = 0
            val diaChiCau = "rtsp://127.0.0.1:$cong"
            val diaChiCam = "rtsp://$host:$port"
            val t1 = thread(isDaemon = true) {
                chuyen(BufferedInputStream(kh.getInputStream()), cam.getOutputStream()) { s ->
                    s.replace(Regex("rtsp://127\\.0\\.0\\.1:$cong"), diaChiCam)
                }
            }
            chuyen(BufferedInputStream(cam.getInputStream()), kh.getOutputStream()) { s ->
                // mọi địa chỉ rtsp cam quảng bá (localhost, IP LAN, tên miền) → về cầu
                s.replace(Regex("rtsp://[^/\\s\"]+"), diaChiCau)
            }
            t1.join(500)
        } catch (_: Exception) {
        } finally {
            try { kh.close() } catch (_: Exception) {}
            try { cam.close() } catch (_: Exception) {}
        }
    }

    /** Đọc từng bản tin RTSP (hoặc gói '$' xen kẽ) từ vao, viết lại phần chữ, ghi ra ra. */
    private fun chuyen(vao: InputStream, ra: OutputStream, vietLai: (String) -> String) {
        while (true) {
            vao.mark(1)
            val b = vao.read()
            if (b < 0) return
            if (b == '$'.code) {                       // gói RTP/RTCP xen kẽ: $ + kênh + độ dài(2) + dữ liệu
                val dau = ByteArray(3)
                docDu(vao, dau)
                val n = ((dau[1].toInt() and 0xff) shl 8) or (dau[2].toInt() and 0xff)
                val du = ByteArray(n)
                docDu(vao, du)
                synchronized(ra) { ra.write('$'.code); ra.write(dau); ra.write(du); ra.flush() }
                continue
            }
            vao.reset()
            val dauMuc = StringBuilder()
            var truoc = 0
            while (true) {                             // đọc tới dòng trống
                val c = vao.read()
                if (c < 0) return
                dauMuc.append(c.toChar())
                if (dauMuc.endsWith("\r\n\r\n")) break
                truoc = c
            }
            var than = ByteArray(0)
            val m = Regex("Content-Length:\\s*(\\d+)", RegexOption.IGNORE_CASE).find(dauMuc)
            if (m != null) { than = ByteArray(m.groupValues[1].toInt()); docDu(vao, than) }
            val thanMoi = vietLai(String(than, Charsets.ISO_8859_1)).toByteArray(Charsets.ISO_8859_1)
            var dauMoi = vietLai(dauMuc.toString())
            if (m != null) dauMoi = dauMoi.replace(Regex("Content-Length:\\s*\\d+", RegexOption.IGNORE_CASE), "Content-Length: ${thanMoi.size}")
            synchronized(ra) { ra.write(dauMoi.toByteArray(Charsets.ISO_8859_1)); ra.write(thanMoi); ra.flush() }
        }
    }

    private fun docDu(vao: InputStream, b: ByteArray) {
        var o = 0
        while (o < b.size) {
            val k = vao.read(b, o, b.size - o)
            if (k < 0) throw java.io.EOFException()
            o += k
        }
    }
}
