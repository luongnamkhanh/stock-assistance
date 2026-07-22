"""HoseFeed: gia + dong tien khoi ngoai HOSE — uu tien SSI iBoard, fallback VPS
khi bi chan IP datacenter."""
from src.adapters.gateways import MarketFeed
from src.infrastructure.http import http_json
from src.infrastructure.vps_api import fetch_vps

API = "https://iboard-query.ssi.com.vn/stock/exchange/hose"
HEADERS = {"User-Agent": "Mozilla/5.0", "Origin": "https://iboard.ssi.com.vn"}


class HoseFeed(MarketFeed):
    def fetch_hose(self):
        try:
            data = http_json(API, HEADERS, timeout=15)["data"]
            return [
                (x["stockSymbol"], x.get("buyForeignValue") or 0, x.get("sellForeignValue") or 0,
                 x.get("buyForeignQtty") or 0, x.get("sellForeignQtty") or 0,
                 x.get("remainForeignQtty") or 0, x.get("matchedPrice") or 0,
                 x.get("nmTotalTradedValue") or 0, x.get("priceChangePercent") or 0)
                for x in data
                if x.get("stockType") == "s" and x.get("stockSymbol") and len(x["stockSymbol"]) == 3
            ]
        except Exception:
            return fetch_vps()  # iBoard chan IP datacenter -> fallback VPS
