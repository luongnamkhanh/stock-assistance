"""Dong thuan quy mo (Fmarket): chup danh muc 1 lan/thang + tong hop cho /fund va anh."""
from src.adapters import chart, presenters
from src.config import now_vn
from src.infrastructure import fmarket_api


def pull_holdings(repo, month):
    """Keo chi tiet moi quy co phieu (top 10 khoan + phan bo + NAV + AUM), luu tron goi 4 bang."""
    holdings, assets, industries, snaps = [], [], [], []
    funds = fmarket_api.stock_funds()
    for _, name, owner in funds:
        d = fmarket_api.fund_detail(name)
        holdings += [(name, *h) for h in d["holdings"]]
        assets += [(name, *a) for a in d["assets"]]
        industries += [(name, *i) for i in d["industries"]]
        snaps.append((name, owner, d["report_month"], d["nav"], *d["nav_chg"], d["aum"]))
    repo.save_fund_month(month, holdings, assets, industries, snaps)
    return len(funds), len(holdings)


def fund_data(repo):
    """Top ma theo so quy nam + bien dong vs thang truoc. None neu chua co du lieu.
    delta=None: thang dau tien, chua co gi de so."""
    months = repo.fund_months()
    if not months:
        return None
    cur, prev = months[-1], (months[-2] if len(months) > 1 else None)
    con = repo.fund_consensus(cur)
    before = {s: n for s, n, _ in repo.fund_consensus(prev)} if prev else {}
    syms = {s for s, _, _ in con}
    return {"month": cur,
            "rows": [(s, n, (n - before.get(s, 0)) if prev else None) for s, n, _ in con[:10]],
            "new": [s for s, _, _ in con if prev and s not in before][:6],
            "out": [s for s in before if s not in syms][:6]}


def holders_of(repo, sym):
    """So quy mo dang nam sym trong thang chup moi nhat (0 neu chua co du lieu)."""
    months = repo.fund_months()
    return len(repo.funds_holding(sym, months[-1])) if months else 0


def fund_summary_text(repo):
    """2 dong data quy cho script video (ngay + tuan). "" neu chua co du lieu."""
    fd = fund_data(repo)
    if not fd:
        return ""
    out = ("\nQuỹ mở đang nắm nhiều nhất (nguồn Fmarket, top 10 khoản/quỹ): "
           + ", ".join(f"{s} {n} quỹ" for s, n, _ in fd["rows"][:5]))
    if fd["new"]:
        out += "\nMã mới vào top danh mục quỹ tháng này: " + ", ".join(fd["new"])
    return out


def fund_stock_message(sym, repo):
    months = repo.fund_months()
    if not months:
        return "Chưa có dữ liệu quỹ (bot chụp danh mục Fmarket từ ngày 15 hàng tháng)."
    m = months[-1]
    prev_n = len(repo.funds_holding(sym, months[-2])) if len(months) > 1 else None
    return presenters.fund_stock_text(sym, m, repo.funds_holding(sym, m),
                                      prev_n, repo.fund_report_month(m))


def maybe_pull_funds(repo, tg):
    """Goi moi vong lap main. Chup danh muc 1 lan/thang: tu ngay 15 (quy da cap nhat bao cao),
    toi da 1 lan thu/ngay. Chay duoc ca trong gio GD — 34 call x timeout 10s, block toi da
    vai phut 1 lan/thang, doi lai data co ngay khong phai doi het phien."""
    now = now_vn()
    month, today = now.strftime("%Y-%m"), now.date().isoformat()
    if (now.day < 15
            or repo.has_fund_month(month) or repo.get_meta("fund_try") == today):
        return
    repo.set_meta("fund_try", today)
    try:
        n_funds, n_rows = pull_holdings(repo, month)
        print(f"[{now.isoformat(timespec='seconds')}] fund holdings {month}: {n_funds} quy, {n_rows} dong")
        data = fund_data(repo)
        if data and tg.cfg.get("chat_ids"):  # chi gui kenh duyet — bro tu forward neu ung
            tg.send_photo(tg.cfg["chat_ids"][0], chart.fund_png(data),
                          f"🏦 Quỹ mở đồng thuận tháng {month[5:]}/{month[:4]}")
    except Exception as e:
        print(f"[{now.isoformat(timespec='seconds')}] fund pull failed: {e}")
