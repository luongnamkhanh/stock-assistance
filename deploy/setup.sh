#!/usr/bin/env bash
# Chay tren VPS (Ubuntu/Debian), trong thu muc chua cac file da rsync len:
#   sudo bash setup.sh
set -e
mkdir -p /opt/stock-bot
rsync -a --delete --exclude __pycache__ src tests telegram.json /opt/stock-bot/
[ -f flows.db ] && cp -n flows.db /opt/stock-bot/ || true   # giu lich su neu co, khong ghi de
cp stock-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now stock-bot
sleep 2
systemctl status stock-bot --no-pager -l | head -15
echo "---"
echo "Xem log: journalctl -u stock-bot -f"
