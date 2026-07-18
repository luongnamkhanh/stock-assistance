"""Sinh dashboard quy mo — 1 file HTML tu chua (khong server, khong CDN) tu flows.db.

Usage: python -m src.dashboard    # ghi export/dashboard.html + mo trinh duyet
Chay lai moi thang sau khi bot chup danh muc. Spec metric: docs/metrics/Metrics-Palantir-Fmarket.md.
Style theo skill dataviz: bar 1 series slot-1, delta tokens, dark mode chon rieng — khong co
chart >=2 series nen khong can palette categorical.
"""
import json
import sqlite3
import webbrowser
from pathlib import Path

from src.config import DB, now_vn

TABLES = ["fund_holdings", "fund_assets", "fund_industries", "fund_snapshot"]


def _rows(db, table):
    cur = db.execute(f"SELECT * FROM {table}")
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def build_html(db_path=None):
    db = sqlite3.connect(str(db_path or DB))
    data = {t: _rows(db, t) for t in TABLES}
    data["generated"] = now_vn().isoformat(timespec="seconds")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return _TEMPLATE.replace("__DATA__", payload)


def main(db_path=None, out=None):
    out = Path(out or "export/dashboard.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(build_html(db_path), encoding="utf-8")
    print("dashboard:", out)
    return out


_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quỹ mở đồng thuận — dashboard</title>
<style>
:root {
  color-scheme: light;
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --border:rgba(11,11,11,.10);
  --s1:#2a78d6; --track:#cde2fb; --up:#006300; --down:#d03b3b;
  --wash:rgba(42,120,214,.07);
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --border:rgba(255,255,255,.10);
  --s1:#3987e5; --track:#184f95; --up:#0ca30c; --down:#d03b3b;
  --wash:rgba(57,135,229,.12);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --ink2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --border:rgba(255,255,255,.10);
    --s1:#3987e5; --track:#184f95; --up:#0ca30c; --down:#d03b3b;
    --wash:rgba(57,135,229,.12);
  }
}
* { box-sizing:border-box; margin:0; }
body { background:var(--page); color:var(--ink);
  font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;
  max-width:1080px; margin:0 auto; padding:20px 16px 40px; }
h1 { font-size:20px; font-weight:650; }
.sub { color:var(--ink2); font-size:13px; }
.mut { color:var(--muted); font-size:12px; }
.row { display:flex; gap:12px; align-items:center; flex-wrap:wrap; }
.filters { margin:14px 0 18px; }
select,button { font:inherit; color:var(--ink); background:var(--surface);
  border:1px solid var(--border); border-radius:8px; padding:6px 10px; }
button { cursor:pointer; }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:16px 18px; }
.kpi .lbl { font-size:13px; color:var(--ink2); }
.kpi .val { font-size:28px; font-weight:600; margin-top:2px; }
.kpi .note { font-size:12px; color:var(--muted); margin-top:2px; }
section.card { margin-top:14px; }
section h2 { font-size:15px; font-weight:650; }
section .cap { font-size:12px; color:var(--muted); margin:2px 0 12px; }
/* bar rows: 1 series -> slot-1; value at the tip; khong vien quanh mark */
.brow { display:grid; grid-template-columns:64px 1fr 76px; gap:10px; align-items:center;
  padding:4px 6px; border-radius:8px; }
.brow.click { cursor:pointer; }
.brow.click:hover { background:var(--wash); }
.brow .sym { font-weight:650; font-size:14px; }
.barwrap { display:flex; align-items:center; gap:8px; min-width:0; }
.bar { height:18px; background:var(--s1); border-radius:0 4px 4px 0; flex:none; }
.bval { color:var(--ink2); font-size:13px; white-space:nowrap; }
.delta { font-size:13px; text-align:right; font-variant-numeric:tabular-nums; }
.delta.up { color:var(--up); } .delta.down { color:var(--down); }
.chips { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
.chip { font-size:12px; padding:3px 10px; border-radius:99px; border:1px solid var(--border); }
.chip.up { color:var(--up); } .chip.down { color:var(--down); }
table { border-collapse:collapse; width:100%; font-size:13px; }
th { text-align:left; color:var(--ink2); font-weight:600; padding:6px 8px;
  border-bottom:1px solid var(--grid); cursor:pointer; white-space:nowrap; user-select:none; }
td { padding:6px 8px; border-bottom:1px solid var(--grid); }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
tr:hover td { background:var(--wash); }
.meter { display:inline-flex; align-items:center; gap:8px; }
.meter .track { width:110px; height:8px; border-radius:4px; background:var(--track); overflow:hidden; }
.meter .fill { height:100%; background:var(--s1); border-radius:0 4px 4px 0; }
.pos { color:var(--up); } .neg { color:var(--down); }
#drill { display:none; }
#drill.show { display:block; }
#drill .brow { grid-template-columns:92px 1fr 8px; }
#drill .head { display:flex; justify-content:space-between; align-items:baseline; }
footer { margin-top:22px; font-size:12px; color:var(--muted); text-align:center; }
</style>
</head>
<body>
<div class="row" style="justify-content:space-between">
  <div>
    <h1>Quỹ mở đồng thuận</h1>
    <div class="sub">Nguồn công khai Fmarket — mỗi quỹ chỉ công bố top 10 khoản: <b>không thấy ≠ không nắm</b></div>
  </div>
  <button id="theme" title="Đổi giao diện sáng/tối">◐</button>
</div>

<div class="row filters">
  <label class="sub" for="month">Tháng chụp:</label>
  <select id="month"></select>
  <span class="mut" id="freshness"></span>
</div>

<div class="cards" id="kpis"></div>

<section class="card">
  <h2>Mã được nhiều quỹ nắm nhất</h2>
  <div class="cap">Số quỹ có mã trong top 10 danh mục · cột phải: thay đổi so với tháng chụp trước · bấm vào mã để xem quỹ nào nắm</div>
  <div id="consensus"></div>
  <div class="chips" id="moves"></div>
</section>

<section class="card" id="drill">
  <div class="head"><h2 id="drillTitle"></h2><button id="drillClose">Đóng</button></div>
  <div class="cap" id="drillCap"></div>
  <div id="drillRows"></div>
</section>

<section class="card">
  <h2>Phân bổ ngành</h2>
  <div class="cap">Trung bình không trọng số trên các quỹ có khai ngành đó (không có AUM để tính trọng số)</div>
  <div id="industries"></div>
</section>

<section class="card">
  <h2>Từng quỹ: coverage &amp; hiệu suất NAV</h2>
  <div class="cap">Coverage = tổng % top 10 ÷ tỷ trọng cổ phiếu — quỹ công bố được bao nhiêu phần danh mục cổ phiếu. Bấm tiêu đề cột để sắp xếp.</div>
  <table id="funds"><thead></thead><tbody></tbody></table>
</section>

<footer>Thông tin tham khảo — không phải khuyến nghị đầu tư · sinh lúc <span id="gen"></span> bởi src/dashboard.py</footer>

<script>
const DATA = __DATA__;
const $ = s => document.querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag);
  if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
const months = [...new Set(DATA.fund_snapshot.map(r => r.month))].sort();
let month = months[months.length - 1];
let sortKey = "nav_12m", sortDir = -1, selStock = null;

const of = (t, m) => DATA[t].filter(r => r.month === m);
const fmt = (v, d=1) => v == null ? "—" : v.toLocaleString("vi-VN", {minimumFractionDigits:d, maximumFractionDigits:d});

function consensus(m) {
  const map = new Map();
  for (const h of of("fund_holdings", m)) {
    const e = map.get(h.symbol) || { n:0, sum:0, funds:[] };
    e.n++; e.sum += h.pct || 0; e.funds.push(h); map.set(h.symbol, e);
  }
  return [...map.entries()].map(([symbol, e]) => ({ symbol, ...e }))
    .sort((a, b) => b.n - a.n || b.sum - a.sum);
}
const prevMonth = () => months[months.indexOf(month) - 1] || null;
const shortOwner = s => (s || "").replace(/^CÔNG TY (CỔ PHẦN|TNHH)( MTV)?( QUẢN LÝ (QUỸ|Q\\.?))?( ĐẦU TƯ)?( CHỨNG KHOÁN)?\\s*/u, "") || s;

function fundRows(m) {
  const cons = consensus(m), snap = of("fund_snapshot", m);
  const top10 = {}, stockPct = {}, cash = {};
  for (const c of cons) for (const h of c.funds) top10[h.fund] = (top10[h.fund] || 0) + (h.pct || 0);
  for (const a of of("fund_assets", m)) {
    if (a.asset === "Cổ phiếu") stockPct[a.fund] = a.pct;
    if (/^Tiền/u.test(a.asset)) cash[a.fund] = (cash[a.fund] || 0) + (a.pct || 0);
  }
  return snap.map(s => ({ ...s, owner_s: shortOwner(s.owner), stock_pct: stockPct[s.fund],
    cash_pct: cash[s.fund],
    coverage: stockPct[s.fund] ? (top10[s.fund] || 0) / stockPct[s.fund] * 100 : null }));
}

function render() {
  const cons = consensus(month), prev = prevMonth();
  const before = prev ? new Map(consensus(prev).map(c => [c.symbol, c.n])) : null;
  const rows = fundRows(month);

  // freshness
  const rms = [...new Set(of("fund_snapshot", month).map(r => r.report_month))].sort();
  $("#freshness").textContent = rms.length ? ("kỳ báo cáo danh mục: " + rms.join(" – ")
    + (rms.length > 1 ? " (các quỹ lệch kỳ)" : "")) : "";

  // KPI
  const kp = $("#kpis"); kp.replaceChildren();
  const cashVals = rows.map(r => r.cash_pct).filter(v => v != null);
  const kpis = [
    ["Số quỹ trong bản chụp", rows.length, ""],
    ["Số mã trong top 10", cons.length, ""],
    ["Tiền mặt trung bình", fmt(cashVals.reduce((a,b)=>a+b,0) / (cashVals.length||1)) + "%", "TB không trọng số"],
    ["Đồng thuận cao nhất", cons[0] ? cons[0].symbol + " · " + cons[0].n + " quỹ" : "—", ""],
  ];
  for (const [l, v, n] of kpis) {
    const c = el("div", "card kpi"); c.append(el("div", "lbl", l), el("div", "val", String(v)));
    if (n) c.append(el("div", "note", n)); kp.append(c);
  }

  // consensus bars (1 series, slot-1; value at tip; delta = token tang/giam)
  const box = $("#consensus"); box.replaceChildren();
  const top = cons.slice(0, 15), peak = top[0] ? top[0].n : 1;
  for (const c of top) {
    const r = el("div", "brow click");
    r.append(el("div", "sym", c.symbol));
    const w = el("div", "barwrap"), bar = el("div", "bar");
    bar.style.width = (c.n / peak * 100 * 0.82) + "%";
    w.append(bar, el("span", "bval", c.n + " quỹ"));
    r.append(w);
    const d = before ? c.n - (before.get(c.symbol) || 0) : null;
    r.append(el("div", "delta" + (d > 0 ? " up" : d < 0 ? " down" : ""),
      d == null ? "" : d > 0 ? "▲" + d : d < 0 ? "▼" + (-d) : "＝"));
    r.title = c.symbol + ": " + c.n + " quỹ nắm, tổng tỷ trọng " + fmt(c.sum) + "%";
    r.addEventListener("click", () => { selStock = c.symbol; render(); });
    box.append(r);
  }

  // moi vao / roi top
  const mv = $("#moves"); mv.replaceChildren();
  if (before) {
    const cur = new Set(cons.map(c => c.symbol));
    for (const c of cons) if (!before.has(c.symbol)) mv.append(el("span", "chip up", "mới vào top: " + c.symbol));
    for (const s of before.keys()) if (!cur.has(s)) mv.append(el("span", "chip down", "rời top: " + s));
    if (!mv.children.length) mv.append(el("span", "mut", "Không có mã vào/rời top so với tháng trước."));
  } else mv.append(el("span", "mut", "Tháng chụp đầu tiên — chưa có kỳ trước để so."));

  // drill
  const dr = $("#drill");
  if (selStock) {
    const c = cons.find(x => x.symbol === selStock);
    dr.className = "card show";
    $("#drillTitle").textContent = selStock + " — " + (c ? c.n : 0) + " quỹ đang nắm (top 10)";
    const hist = months.map(m => { const k = consensus(m).find(x => x.symbol === selStock);
      return m.slice(5) + "/" + m.slice(0,4) + ": " + (k ? k.n : 0) + " quỹ"; });
    $("#drillCap").textContent = "Theo tháng chụp — " + hist.join(" · ");
    const rows2 = $("#drillRows"); rows2.replaceChildren();
    const fs = (c ? c.funds : []).slice().sort((a, b) => (b.pct||0) - (a.pct||0));
    const pk = fs[0] ? fs[0].pct || 1 : 1;
    for (const h of fs) {
      const r = el("div", "brow");
      r.append(el("div", "sym", h.fund));
      const w = el("div", "barwrap"), bar = el("div", "bar");
      bar.style.width = ((h.pct||0) / pk * 100 * 0.75) + "%";
      w.append(bar, el("span", "bval", fmt(h.pct) + "% NAV"));
      r.append(w, el("div", "delta", ""));
      rows2.append(r);
    }
  } else dr.className = "card";

  // industries: TB khong trong so
  const ind = new Map();
  for (const i of of("fund_industries", month)) {
    const e = ind.get(i.industry) || { sum:0, n:0 };
    e.sum += i.pct || 0; e.n++; ind.set(i.industry, e);
  }
  const inds = [...ind.entries()].map(([k, e]) => [k, e.sum / e.n, e.n])
    .sort((a, b) => b[1] - a[1]).slice(0, 12);
  const ib = $("#industries"); ib.replaceChildren();
  const ipk = inds[0] ? inds[0][1] : 1;
  for (const [name, avg, n] of inds) {
    const r = el("div", "brow");
    r.append(el("div", "sym", "")); r.firstChild.style.cssText = "font-weight:400;font-size:13px;min-width:0";
    r.firstChild.textContent = name;
    r.style.gridTemplateColumns = "170px 1fr 76px";
    const w = el("div", "barwrap"), bar = el("div", "bar");
    bar.style.width = (avg / ipk * 100 * 0.8) + "%";
    w.append(bar, el("span", "bval", fmt(avg) + "%"));
    r.append(w, el("div", "delta mut", n + " quỹ"));
    ib.append(r);
  }

  // funds table
  const cols = [["fund","Quỹ",0],["owner_s","Cty quản lý",0],["stock_pct","% CP",1],
    ["cash_pct","% Tiền",1],["coverage","Coverage top 10",1],
    ["nav_1m","NAV 1m",1],["nav_12m","NAV 12m",1],["nav_36m","NAV 36m",1]];
  const th = $("#funds thead"); th.replaceChildren();
  const hr = el("tr");
  for (const [k, label, num] of cols) {
    const h = el("th", num ? "num" : "", label + (sortKey === k ? (sortDir < 0 ? " ↓" : " ↑") : ""));
    h.addEventListener("click", () => { sortDir = sortKey === k ? -sortDir : -1; sortKey = k; render(); });
    hr.append(h);
  }
  th.append(hr);
  const tb = $("#funds tbody"); tb.replaceChildren();
  const sorted = rows.slice().sort((a, b) => {
    const x = a[sortKey], y = b[sortKey];
    if (x == null) return 1; if (y == null) return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * sortDir;
  });
  for (const r of sorted) {
    const tr = el("tr");
    const tdF = el("td", "", r.fund); tdF.style.fontWeight = "650"; tr.append(tdF);
    const tdO = el("td", "", r.owner_s); tdO.title = r.owner || ""; tr.append(tdO);
    tr.append(el("td", "num", fmt(r.stock_pct)), el("td", "num", fmt(r.cash_pct)));
    const tdC = el("td", "num");
    if (r.coverage != null) {
      const m = el("span", "meter"), t = el("span", "track"), f = el("span", "fill");
      f.style.width = Math.min(r.coverage, 100) + "%"; t.append(f);
      m.append(t, el("span", "", fmt(r.coverage, 0) + "%" + (r.coverage > 110 ? " ⚠" : "")));
      tdC.append(m);
    } else tdC.textContent = "—";
    tr.append(tdC);
    for (const k of ["nav_1m", "nav_12m", "nav_36m"]) {
      const v = r[k];
      tr.append(el("td", "num " + (v > 0 ? "pos" : v < 0 ? "neg" : ""),
        v == null ? "—" : (v > 0 ? "+" : "") + fmt(v) + "%"));
    }
    tb.append(tr);
  }
}

// filters
const sel = $("#month");
for (const m of months) {
  const o = el("option", "", "Tháng " + m.slice(5) + "/" + m.slice(0, 4)); o.value = m; sel.append(o);
}
sel.value = month;
sel.addEventListener("change", () => { month = sel.value; selStock = null; render(); });
$("#drillClose").addEventListener("click", () => { selStock = null; render(); });
$("#theme").addEventListener("click", () => {
  const cur = document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = cur === "dark" ? "light" : "dark";
});
$("#gen").textContent = DATA.generated;
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    p = main()
    webbrowser.open(p.resolve().as_uri())
