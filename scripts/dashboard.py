"""A one-page dashboard: data/dashboard.html, a self-contained file (no internet needed). Run after build.py.

Shows cash, debt and net position (with the change since the last snapshot), this month against the budget,
money in vs out for the last 12 months, where the money went, debts, recurring payments and what's coming up.
Also writes one snapshot a day to snapshots.csv (date,item,amount) so the next run can show what moved.
"""
import csv
import html
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from build import (CASH_TYPES, DATA, DEBT_TYPES, HOME, ROOT, TODAY, budget_actuals, coming_up, fmt, fx_rates, group_of,
                   is_transfer, lent_balances, month_of, read_csv, recurring, to_home)


def fmt0(v):
    return fmt(v, dp=0)


SNAPSHOTS = ROOT / "snapshots.csv"


def load():
    db = sqlite3.connect(DATA / "finance.db")
    db.row_factory = sqlite3.Row
    txns = []
    for r in db.execute("SELECT * FROM transactions ORDER BY date"):
        t = dict(r)
        t["date"] = date.fromisoformat(t["date"])
        t["amount"] = Decimal(str(t["amount"]))
        t["amount_home"] = Decimal(str(t["amount_home"])) if t["amount_home"] is not None else None
        txns.append(t)
    accounts = {r["id"]: dict(r) for r in db.execute("SELECT * FROM accounts")}
    latest = {r["account_id"]: (date.fromisoformat(r["date"]), Decimal(str(r["balance"])), r["source"])
              for r in db.execute("SELECT * FROM latest_balances")}
    return txns, accounts, latest


def position(accounts, latest, txns):
    rates = fx_rates()
    items, cash, debt, assets = {}, Decimal(0), Decimal(0), Decimal(0)
    for aid, (on, bal, _) in latest.items():
        a = accounts.get(aid)
        if not a or a["status"] != "active":
            continue
        home = to_home(bal, a["currency"], on, rates)
        if home is None:
            continue
        if a["type"] in CASH_TYPES:
            cash += home
        elif a["type"] in DEBT_TYPES:
            debt += home
            items[aid] = home
        else:
            assets += home
    owed = sum((lent - repaid for lent, repaid, _ in lent_balances(txns).values()), Decimal(0))
    items.update({"Cash": cash, "Other assets": assets, "Owed to you": owed})
    return cash, debt, assets, owed, items


def snapshot(items):
    """Append today's position once a day; return the latest earlier snapshot as {item: amount} and its date."""
    rows = []
    if SNAPSHOTS.exists():
        with open(SNAPSHOTS) as f:
            rows = list(csv.DictReader(f))
    earlier = [r for r in rows if r["date"] < str(TODAY)]
    prev_date = max((r["date"] for r in earlier), default=None)
    prev = {r["item"]: Decimal(r["amount"]) for r in earlier if r["date"] == prev_date}
    if not any(r["date"] == str(TODAY) for r in rows):
        with open(SNAPSHOTS, "a", newline="") as f:
            w = csv.writer(f)
            if not rows:
                w.writerow(["date", "item", "amount"])
            for k, v in items.items():
                w.writerow([TODAY, k, f"{v:.2f}"])
    return prev_date, prev


def bars_svg(series, width=640, height=200):
    """Grouped bars: series = [(label, money_in, money_out)]."""
    if not series:
        return "<p class=muted>No data yet.</p>"
    top = max(max(i, o) for _, i, o in series) or 1
    n, pad, base = len(series), 28, height - 24
    slot = (width - pad) / n
    bw = slot * 0.36
    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Money in and out by month">']
    for frac in (0.5, 1):
        y = base - (base - 10) * frac
        out.append(f'<line x1="{pad}" x2="{width}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                   f'<text x="{pad - 4}" y="{y + 4:.1f}" class="axis" text-anchor="end">{top * frac / 1000:.0f}k</text>')
    for k, (label, i, o) in enumerate(series):
        x = pad + k * slot + slot * 0.12
        for j, (v, cls) in enumerate(((i, "in"), (o, "out"))):
            h = (base - 10) * v / top
            out.append(f'<rect x="{x + j * bw:.1f}" y="{base - h:.1f}" width="{bw - 2:.1f}" height="{h:.1f}" rx="2" class="{cls}">'
                       f'<title>{label} {"in" if cls == "in" else "out"}: {fmt0(round(v))}</title></rect>')
        out.append(f'<text x="{x + bw:.1f}" y="{height - 6}" class="axis" text-anchor="middle">{label[5:]}</text>')
    return "".join(out) + "</svg>"


def hbar_rows(pairs, total):
    out = []
    for name, v in pairs:
        pct = 100 * v / total if total else 0
        out.append(f'<div class="hrow"><span>{html.escape(name)}</span><div class="track"><div class="fill" '
                   f'style="width:{pct:.1f}%"></div></div><span class="num">{fmt0(round(v))}</span></div>')
    return "".join(out)


def delta(now, before):
    if before is None:
        return ""
    d = now - before
    if abs(d) < 1:
        return '<span class="muted">no change</span>'
    good = d > 0
    return f'<span class="{"good" if good else "bad"}">{"+" if d > 0 else ""}{fmt0(round(d))}</span>'


def build_page():
    txns, accounts, latest = load()
    cash, debt, assets, owed, items = position(accounts, latest, txns)
    prev_date, prev = snapshot(items)
    net = cash + assets + debt + owed

    # Money in vs out, last 12 months
    months = []
    d = TODAY.replace(day=1)
    for _ in range(12):
        months.insert(0, month_of(d))
        d = (d - timedelta(days=1)).replace(day=1)
    flow = defaultdict(lambda: [Decimal(0), Decimal(0)])
    spend_by_group = defaultdict(Decimal)
    for t in txns:
        if t["amount_home"] is None or is_transfer(t["category"]) or (t["category"] or "").startswith("Lent"):
            continue
        m = month_of(t["date"])
        if m not in months:
            continue
        if t["amount_home"] > 0 and (t["category"] or "Income").startswith("Income"):
            flow[m][0] += t["amount_home"]
        else:
            flow[m][1] -= t["amount_home"]
            spend_by_group[group_of(t["category"])] -= t["amount_home"]
    series = [(m, float(flow[m][0]), float(max(flow[m][1], 0))) for m in months]
    groups = sorted(((g, v) for g, v in spend_by_group.items() if v > 0), key=lambda kv: -kv[1])[:12]

    # Budget this month
    this_month = month_of(TODAY)
    budget_rows = budget_actuals(txns, this_month)
    budget_html = ""
    if budget_rows:
        budget_html = "<table><tr><th>Line</th><th>Budget</th><th>Spent</th><th>Left</th></tr>" + "".join(
            f'<tr><td>{html.escape(l)}</td><td class=num>{fmt(b)}</td><td class=num>{fmt(s)}</td>'
            f'<td class="num {"bad" if b and s > b else ""}">{fmt(b - s)}</td></tr>' for l, b, s in budget_rows) + "</table>"
    else:
        budget_html = "<p class=muted>No budget yet: add lines to budget.csv.</p>"

    debts = sorted(((aid, v) for aid, v in items.items() if aid in accounts), key=lambda kv: kv[1])
    debt_html = "".join(f'<tr><td>{html.escape(accounts[aid]["name"] or aid)}</td><td class=num>{fmt(-v)}</td>'
                        f'<td class=num>{delta(v, prev.get(aid)) if prev else ""}</td></tr>' for aid, v in debts) \
        or '<tr><td colspan=3 class=muted>No debts recorded.</td></tr>'
    rec = [r for r in recurring(txns) if r["active"]]
    rec_html = "".join(f'<tr><td>{html.escape(r["merchant"])}</td><td>{html.escape(r["category"] or "—")}</td>'
                       f'<td class=num>{fmt(-r["last_amount"], r["currency"])}</td></tr>' for r in rec[:20]) \
        or '<tr><td colspan=3 class=muted>None found yet.</td></tr>'
    up = coming_up()
    up_html = "".join(f'<tr><td>{d_}</td><td>{html.escape(w)}{" <b class=bad>overdue</b>" if d_ < TODAY else ""}</td></tr>'
                      for d_, w, _ in up) or '<tr><td colspan=2 class=muted>Nothing in the next 90 days.</td></tr>'
    uncategorised = sum(1 for t in txns if not t["category"] and t["date"] >= TODAY - timedelta(days=60))
    stale = [aid for aid, (on, _, _) in latest.items()
             if accounts.get(aid, {}).get("status") == "active" and (TODAY - on).days > 35]
    warnings = []
    if stale:
        warnings.append(f"Out of date (35+ days): {', '.join(stale)}.")
    if uncategorised:
        warnings.append(f"{uncategorised} transactions in the last 60 days aren't categorised yet.")

    since = f"Since {prev_date}" if prev_date else "First snapshot today"
    tiles = [("Cash", cash, prev.get("Cash")), ("Debt", debt, sum((v for k, v in prev.items() if k in accounts), Decimal(0)) if prev else None),
             ("Owed to you", owed, prev.get("Owed to you")), ("Net position", net, None)]
    tiles_html = "".join(f'<div class=tile><div class=label>{l}</div><div class=big>{fmt0(round(v))}</div>'
                         f'<div class=small>{delta(v, p)}</div></div>' for l, v, p in tiles)
    page = TEMPLATE.format(
        home=HOME, today=TODAY, since=since, tiles=tiles_html,
        warnings="".join(f"<p class=warn>{html.escape(w)}</p>" for w in warnings),
        budget=budget_html, month=this_month, bars=bars_svg(series),
        groups=hbar_rows(groups, groups[0][1] if groups else 0) or "<p class=muted>No spending yet.</p>",
        debts=debt_html, recurring=rec_html, coming=up_html)
    (DATA / "dashboard.html").write_text(page)
    print(f"Wrote {DATA / 'dashboard.html'}")


TEMPLATE = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1"><title>Money dashboard</title>
<style>
:root {{ --bg:#f7f7f5; --card:#fff; --ink:#1d1d1b; --muted:#6b6b66; --line:#e4e4df; --in:#2f7d5b; --out:#c4553a;
  --fill:#5470c6; --good:#2f7d5b; --bad:#b3412a; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#161615; --card:#21211f; --ink:#ececea; --muted:#9a9a94;
  --line:#33332f; --in:#5bb98c; --out:#e07a5f; --fill:#7c96e8; --good:#5bb98c; --bad:#ef8a6f; }} }}
* {{ box-sizing:border-box }} body {{ margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.45 -apple-system, system-ui, sans-serif; }}
main {{ max-width:1000px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:22px; margin:0 0 4px }} h2 {{ font-size:15px; margin:0 0 12px; color:var(--muted); font-weight:600 }}
.muted, .small {{ color:var(--muted); font-size:13px }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin:18px 0 }}
.tile, .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px }}
.label {{ color:var(--muted); font-size:13px }} .big {{ font-size:24px; font-weight:650; font-variant-numeric:tabular-nums }}
.grid2 {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:12px; margin-bottom:12px }}
.card {{ margin-bottom:12px; overflow-x:auto }}
table {{ width:100%; border-collapse:collapse; font-size:14px }} td, th {{ padding:6px 4px; border-bottom:1px solid var(--line); text-align:left }}
th {{ color:var(--muted); font-weight:500 }} .num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap }}
.good {{ color:var(--good) }} .bad {{ color:var(--bad) }}
.warn {{ background:var(--card); border-left:3px solid var(--bad); padding:8px 12px; margin:6px 0; border-radius:4px }}
svg {{ width:100%; height:auto }} .in {{ fill:var(--in) }} .out {{ fill:var(--out) }}
.grid {{ stroke:var(--line) }} .axis {{ fill:var(--muted); font-size:11px }}
.legend span {{ display:inline-block; width:10px; height:10px; border-radius:2px; margin:0 4px 0 12px }}
.hrow {{ display:grid; grid-template-columns:140px 1fr 90px; gap:8px; align-items:center; margin:6px 0; font-size:14px }}
.track {{ background:var(--line); height:10px; border-radius:5px }} .fill {{ background:var(--fill); height:10px; border-radius:5px }}
</style></head><body><main>
<h1>Money dashboard</h1><div class=muted>Built {today} · amounts in {home} · {since}</div>
{warnings}
<div class=tiles>{tiles}</div>
<div class=grid2>
<div class=card><h2>Budget, {month} so far</h2>{budget}</div>
<div class=card><h2>Coming up</h2><table>{coming}</table></div>
</div>
<div class=card><h2>Money in and out, last 12 months</h2>
<div class="legend small"><span style="background:var(--in)"></span>In<span style="background:var(--out)"></span>Out</div>{bars}</div>
<div class=grid2>
<div class=card><h2>Where it went, last 12 months</h2>{groups}</div>
<div class=card><h2>Debts</h2><table><tr><th>Account</th><th class=num>Owed</th><th class=num>Change</th></tr>{debts}</table></div>
</div>
<div class=card><h2>Recurring payments still going</h2><table><tr><th>Merchant</th><th>Category</th><th class=num>Last charge</th></tr>{recurring}</table></div>
</main></body></html>
"""

if __name__ == "__main__":
    build_page()
