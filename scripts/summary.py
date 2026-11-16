"""Yearly summary of income, spending by group, and what was left, from data/finance.db.

Run after build.py. Writes data/summary.md. Amounts are in the home currency (config.json).

Transfers between your own accounts ('Transfer: ...') are left out so nothing is counted twice; spending on a
credit card counts when it's spent, and paying the card off is a transfer. 'Lent: ...' is shown separately
because it should come back.
"""
import sqlite3
from collections import defaultdict
from datetime import date, timedelta

from build import DATA, HOME, fmt, group_of, is_transfer


def fmt0(v):
    return "—" if not v else fmt(v, dp=0)


def load():
    db = sqlite3.connect(DATA / "finance.db")
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute("SELECT date, amount_home, category FROM transactions WHERE amount_home IS NOT NULL")]
    for r in rows:
        r["date"] = date.fromisoformat(r["date"])
    return rows


def summarise():
    txns = load()
    if not txns:
        print("No transactions yet.")
        return
    latest = max(t["date"] for t in txns)
    years = list(range(min(t["date"] for t in txns).year, latest.year + 1))
    window_start = (latest.replace(day=1) - timedelta(days=330)).replace(day=1)
    cols = years + ["12m"]
    income, spending, lent = defaultdict(float), defaultdict(float), defaultdict(float)
    for t in txns:
        cat = t["category"]
        if is_transfer(cat):
            continue
        keys = [t["date"].year] + (["12m"] if t["date"] >= window_start else [])
        for k in keys:
            if cat and cat.startswith("Income"):
                income[(cat.split(":", 1)[-1].strip(), k)] += t["amount_home"]
            elif cat and cat.startswith("Lent"):
                lent[k] += t["amount_home"]
            elif cat is None and t["amount_home"] > 0:
                income[("Uncategorised money in", k)] += t["amount_home"]
            else:
                spending[(group_of(cat), k)] += -t["amount_home"]

    head = "| | " + " | ".join(str(y) for y in years) + f" | 12 months to {latest:%b %Y} | per month |"
    sep = "|---|" + "---|" * (len(cols) + 1)

    def table(title, data):
        lines = [f"## {title}", "", head, sep]
        names = sorted({n for n, _ in data}, key=lambda n: -abs(data.get((n, "12m"), 0)) or 0)
        for n in names:
            vals = [data.get((n, c), 0) for c in cols]
            lines.append(f"| {n} | " + " | ".join(fmt0(round(v)) for v in vals) + f" | {fmt0(round(vals[-1] / 12))} |")
        totals = [sum(data.get((n, c), 0) for n in names) for c in cols]
        lines.append("| **Total** | " + " | ".join(f"**{fmt0(round(v))}**" for v in totals) + f" | **{fmt0(round(totals[-1] / 12))}** |")
        return lines + [""], totals

    out = ["# Summary", "", f"In {HOME}. Data up to {latest}; {years[-1]} is a part year, and so is the first year "
           "if records start part-way through it. Transfers between your own accounts are left out.", ""]
    inc_lines, inc = table("Income", income)
    spend_lines, spend = table("Spending", spending)
    out += inc_lines + spend_lines
    out += ["## Left over", "", head, sep,
            "| Income less spending | " + " | ".join(fmt0(round(i - s)) for i, s in zip(inc, spend))
            + f" | {fmt0(round((inc[-1] - spend[-1]) / 12))} |",
            "| Lent to people (net) | " + " | ".join(fmt0(round(lent[c])) for c in cols) + " | |", "",
            "A shortfall was covered by savings or borrowing; a surplus went to savings or paying down debt. "
            "Missing accounts or months make this less reliable: check report.md first.", ""]
    (DATA / "summary.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    summarise()
