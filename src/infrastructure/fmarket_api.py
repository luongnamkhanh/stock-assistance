"""Fmarket public API: danh muc quy mo co phieu (top 10 khoan/quy, quy cap nhat ~giua thang).
Nguon cong khai, khong can auth — ~35 request/lan chup, 1 lan/thang."""
from src.infrastructure.http import http_json

API = "https://api.fmarket.vn/res/products"
_FILTER = {"types": ["NEW_FUND", "TRADING_FUND"], "issuerIds": [], "sortOrder": "DESC",
           "sortField": "navTo6Months", "page": 1, "pageSize": 100, "isIpo": False,
           "fundAssetTypes": ["STOCK"], "bondRemainPeriods": [], "searchField": "",
           "isBuyByReward": False, "thirdAppIds": []}


def stock_funds():
    """[(id, shortName, ten_cty_quan_ly)] cac quy co phieu dang giao dich tren Fmarket."""
    rows = http_json(f"{API}/filter", timeout=30, body=_FILTER)["data"]["rows"]
    return [(r["id"], r["shortName"], (r.get("owner") or {}).get("name") or "") for r in rows]


def fund_detail(fund_id):
    return _parse(http_json(f"{API}/{fund_id}", timeout=30)["data"])


def _parse(d):
    """Detail JSON -> dict: holdings/assets/industries + report_month + nav + nav_chg.
    Tach rieng de test khong can mang."""
    nc = d.get("productNavChange") or {}
    rp = (d.get("productFund") or {}).get("updateAssetHoldingTime") or ""  # "06/2026"
    return {
        "holdings": [(h["stockCode"], h.get("netAssetPercent") or 0, h.get("industry") or "")
                     for h in d.get("productTopHoldingList") or [] if h.get("stockCode")],
        "assets": [(((a.get("assetType") or {}).get("name") or "?"), a.get("assetPercent") or 0)
                   for a in d.get("productAssetHoldingList") or []],
        "industries": [((i.get("industry") or "?"), i.get("assetPercent") or 0)
                       for i in d.get("productIndustriesHoldingList") or []],
        "report_month": "-".join(reversed(rp.split("/"))) if "/" in rp else None,  # -> "2026-06"
        "nav": d.get("nav"),
        "nav_chg": tuple(nc.get(f"navTo{m}Months") for m in (1, 3, 6, 12, 36)),
    }
