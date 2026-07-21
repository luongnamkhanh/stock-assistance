"""Telegram bot implementation."""
import json
import subprocess
import urllib.request

from src.adapters.gateways import Telegram


class TelegramBot(Telegram):
    """Telegram bot that sends alerts to configured chat IDs."""

    def __init__(self, cfg: dict):
        """Initialize with config dict containing 'token' and 'chat_ids'."""
        self.cfg = cfg

    def send_to(self, chat_id, text, silent=False, reply_markup=None):
        """Send text message to a single chat_id (cap 4000 — Telegram limit 4096).
        silent=True: gui khong am thanh/rung (disable_notification) — tin van den day du, chi khong keu.
        reply_markup: inline keyboard (dict) — nut bam duoi tin (vd nut 'Luu' cho note)."""
        body = {"chat_id": chat_id, "text": text[:4000], "disable_notification": silent}
        if reply_markup:
            body["reply_markup"] = reply_markup
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.cfg['token']}/sendMessage",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)

    def answer_callback(self, callback_id, text=""):
        """Tra loi 1 cu bam nut inline — tat trang thai loading + hien toast ngan."""
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.cfg['token']}/answerCallbackQuery",
            data=json.dumps({"callback_query_id": callback_id, "text": text}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)

    def _send_file(self, method, field, filename, mime, data, chat_id, caption):
        """Multipart tu dung bang stdlib (curl khong chac co tren Railway)."""
        b = "----tg-file-boundary"
        body = b"".join([
            f'--{b}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{chat_id}\r\n'.encode(),
            f'--{b}\r\nContent-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'.encode(),
            (f'--{b}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
             f'Content-Type: {mime}\r\n\r\n').encode(),
            data, f"\r\n--{b}--\r\n".encode()])
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.cfg['token']}/{method}", data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        urllib.request.urlopen(req, timeout=60)

    def send_photo(self, chat_id, png, caption=""):
        """Gui anh PNG (bytes)."""
        self._send_file("sendPhoto", "photo", "daily.png", "image/png", png, chat_id, caption)

    def send_document(self, chat_id, data, filename, caption=""):
        """Gui file dinh kem (bytes) — vd dashboard.html."""
        self._send_file("sendDocument", "document", filename, "text/html", data, chat_id, caption)

    def broadcast_photo(self, png, caption=""):
        """Gui anh den moi chat_id da cau hinh. False neu chua config."""
        if not (self.cfg.get("token") and self.cfg.get("chat_ids")):
            return False
        for cid in self.cfg["chat_ids"]:
            self.send_photo(cid, png, caption)
        return True

    def send_video(self, chat_id, path, caption=""):
        """Gui video len 1 chat — curl -F vi urllib khong co multipart san."""
        subprocess.run(["curl", "-s", "-F", f"chat_id={chat_id}", "-F", f"video=@{path}",
                        "-F", f"caption={caption}",
                        f"https://api.telegram.org/bot{self.cfg['token']}/sendVideo"],
                       check=True, capture_output=True)

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
