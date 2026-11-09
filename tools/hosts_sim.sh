for i in 2 4 6 8; do grep -q "pl$i.ddns.net" /etc/hosts || echo "127.0.4.$i pl$i.ddns.net" >> /etc/hosts; done
bash /home/claude/camlink/sim/moi_truong.sh >/dev/null 2>&1 || true
