"""Telegram bot implementation."""
import json
import urllib.request

from src.adapters.gateways import Telegram


class TelegramBot(Telegram):
    """Telegram bot that sends alerts to configured chat IDs."""

    def __init__(self, cfg: dict):
        """Initialize with config dict containing 'token' and 'chat_ids'."""
        self.cfg = cfg

    def send_to(self, chat_id, text):
        """Send text message to a single chat_id."""
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.cfg['token']}/sendMessage",
            data=json.dumps({"chat_id": chat_id, "text": text}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)

    def broadcast(self, text):
        """Broadcast text to all configured chat_ids. Return False if not configured."""
        if not (self.cfg.get("token") and self.cfg.get("chat_ids")):
            return False
        for cid in self.cfg["chat_ids"]:
            self.send_to(cid, text)
        return True

    def get_updates(self, offset, wait):
        """Get updates from Telegram API. Return list of update dicts."""
        url = f"https://api.telegram.org/bot{self.cfg['token']}/getUpdates?offset={offset + 1}&timeout={wait}"
        with urllib.request.urlopen(urllib.request.Request(url), timeout=wait + 10) as r:
            return json.load(r)["result"]
