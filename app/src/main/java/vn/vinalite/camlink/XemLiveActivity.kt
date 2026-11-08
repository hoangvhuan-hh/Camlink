package vn.vinalite.camlink

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.widget.LinearLayout
import android.widget.TextView
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.rtsp.RtspMediaSource
import androidx.media3.ui.PlayerView

/** Xem hình trực tiếp qua rtsp://tên-miền:port — đúng đường IOC sẽ dùng. */
class XemLiveActivity : Activity() {
    private var player: ExoPlayer? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val url = intent.getStringExtra("url") ?: return finish()
        val goc = LinearLayout(this)
        goc.orientation = LinearLayout.VERTICAL
        goc.setBackgroundColor(Color.BLACK)
        val tieuDe = TextView(this)
        tieuDe.text = intent.getStringExtra("tieu_de") ?: "Xem trực tiếp"
        tieuDe.setTextColor(Color.WHITE)
        tieuDe.textSize = 15f
        tieuDe.setPadding(24, 36, 24, 12)
        goc.addView(tieuDe)
        val trangThai = TextView(this)
        trangThai.text = "Đang kết nối…"
        trangThai.setTextColor(Color.parseColor("#CFE3F1"))
        trangThai.setPadding(24, 0, 24, 12)
        goc.addView(trangThai)
        val pv = PlayerView(this)
        goc.addView(pv, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        setContentView(goc)

        val p = ExoPlayer.Builder(this).build()
        player = p
        pv.player = p
        val nguon = RtspMediaSource.Factory().setForceUseRtpTcp(true).createMediaSource(MediaItem.fromUri(url))
        p.setMediaSource(nguon)
        p.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                trangThai.text = when (state) {
                    Player.STATE_BUFFERING -> "Đang tải hình…"
                    Player.STATE_READY -> "✔ Đang xem trực tiếp qua tên miền"
                    Player.STATE_ENDED -> "Luồng đã dừng"
                    else -> trangThai.text
                }
            }
            override fun onPlayerError(error: PlaybackException) {
                trangThai.text = "✖ Không xem được: ${error.errorCodeName}. Kiểm tra port RTSP đã mở và user/pass cam."
            }
        })
        p.prepare()
        p.playWhenReady = true
    }

    override fun onDestroy() {
        player?.release()
        super.onDestroy()
    }
}
