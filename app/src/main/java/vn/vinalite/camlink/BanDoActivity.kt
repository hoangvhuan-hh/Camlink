package vn.vinalite.camlink

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import com.chaquo.python.Python

/** Bản đồ các điểm tô màu theo tình trạng; bấm điểm → dẫn đường / phiếu báo mạng. */
class BanDoActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val duong = intent.getStringExtra("file") ?: return finish()
        val ma = intent.getStringExtra("ma") ?: ""
        val kq = intent.getStringExtra("kq") ?: "{}"
        val core = Python.getInstance().getModule("camlink_core")
        val wv = WebView(this)
        wv.settings.javaScriptEnabled = true
        wv.settings.domStorageEnabled = true
        wv.settings.allowFileAccess = true
        wv.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, req: WebResourceRequest): Boolean {
                val u = req.url
                if (u.scheme == "camlink" && u.host == "phieu") {
                    val stt = u.lastPathSegment ?: return true
                    val phieu = core.callAttr("tuxa_phieu", ma, kq, stt).toString()
                    AlertDialog.Builder(this@BanDoActivity)
                        .setTitle("Phiếu báo mạng — điểm $stt")
                        .setMessage(phieu)
                        .setPositiveButton("Gửi Zalo/SMS") { _, _ ->
                            startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply {
                                type = "text/plain"; putExtra(Intent.EXTRA_TEXT, phieu)
                            }, "Gửi phiếu báo mạng"))
                        }
                        .setNegativeButton("Đóng", null).show()
                    return true
                }
                if (u.host?.contains("google") == true || u.scheme == "geo") {
                    startActivity(Intent(Intent.ACTION_VIEW, u)); return true
                }
                return false
            }
        }
        setContentView(wv)
        wv.loadUrl(Uri.fromFile(java.io.File(duong)).toString())
    }
}
