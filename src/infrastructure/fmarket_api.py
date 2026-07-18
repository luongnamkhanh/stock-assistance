"""Fmarket public API: danh muc quy mo co phieu (top 10 khoan/quy, quy cap nhat ~giua thang).
Nguon cong khai, khong can auth — ~35 request/lan chup, 1 lan/thang."""
from src.infrastructure.http import http_json

API = "https://api.fmarket.vn/res/products"
_FILTER = {"types": ["NEW_FUND", "TRADING_FUND"], "issuerIds": [], "sortOrder": "DESC",
           "sortField": "navTo6Months", "page": 1, "pageSize": 100, "isIpo": False,
           "fundAssetTypes": ["STOCK"], "bondRemainPeriods": [], "searchField": "",
           "isBuyByReward": False, "thirdAppIds": []}


def stock_funds():
    """[(id, shortName)] cac quy co phieu dang giao dich tren Fmarket."""
    rows = http_json(f"{API}/filter", timeout=30, body=_FILTER)["data"]["rows"]
    return [(r["id"], r["shortName"]) for r in rows]


def fund_holdings(fund_id):
    """[(symbol, pct_nav, industry)] top 10 khoan nam giu cua 1 quy."""
    d = http_json(f"{API}/{fund_id}", timeout=30)["data"]
    return [(h["stockCode"], h.get("netAssetPercent") or 0, h.get("industry") or "")
            for h in d.get("productTopHoldingList") or [] if h.get("stockCode")]
