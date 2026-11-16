"""Rebuild data/ from everything in sources/ and the CSVs in the project root.

sources/ is the record; data/ is generated and can be deleted and rebuilt at any time.
Hand-made knowledge lives in rules.csv (categories by pattern) and overrides.csv (per transaction),
which survive rebuilds because transaction ids are derived from the transaction itself.

Writes:
  data/finance.db          SQLite: accounts, statements, transactions, balances, latest_balances
  data/transactions.csv    every transaction, oldest first
  data/report.md           coverage, reconciliation, balances, debts, budget, recurring payments, what's coming up
"""
import csv
import hashlib
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

from ingest import ROOT, SOURCES, ingest, load_accounts, load_config, read_document

DATA = ROOT / "data"
CONFIG = load_config()
HOME = CONFIG.get("home_currency", "GBP")
CASH_TYPES = {"current", "savings", "cash"}
DEBT_TYPES = {"credit_card", "loan", "mortgage", "other_debt"}
ASSET_TYPES = CASH_TYPES | {"investment", "pension"}
TXN_FIELDS = ["id", "account_id", "date", "posted_date", "description", "details", "amount", "currency", "amount_home",
              "original_amount", "original_currency", "fx_rate", "balance_after", "fees", "category", "note",
              "external_id", "source_file"]
TODAY = date.today()


# ---------------------------------------------------------------------------------------------------------------
# Shared helpers (summary.py and dashboard.py import these)

def read_csv(name):
    path = ROOT / name
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]


def is_transfer(category):
    """Money moving between your own accounts: left out of income and spending."""
    return bool(category) and category.startswith("Transfer")


def matches(category, patterns):
    """True if category equals one of the patterns, or starts with one that ends in ':'."""
    return bool(category) and any(category == p or (p.endswith(":") and category.startswith(p)) for p in patterns)


def group_of(category):
    """'Housing: rent' -> 'Housing'."""
    return category.split(":")[0].strip() if category else "Uncategorised"


def fmt(v, currency=HOME, dp=2):
    symbol = {"GBP": "£", "EUR": "€", "USD": "$"}.get(currency, currency + " ")
    v = Decimal(str(v))
    return f"-{symbol}{-v:,.{dp}f}" if v < 0 else f"{symbol}{v:,.{dp}f}"


def month_of(d):
    return d.strftime("%Y-%m")


def months_between(start, end):
    months, d = [], start.replace(day=1)
    while d <= end:
        months.append(month_of(d))
        d = (d + timedelta(days=32)).replace(day=1)
    return months


# ---------------------------------------------------------------------------------------------------------------
# Loading

def txn_id(account_id, t, occurrence):
    key = "|".join(str(x) for x in (account_id, t["date"], t["amount"], t["description"], t.get("details"), occurrence))
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def assign_ids(account_id, txns):
    seen = Counter()
    for t in txns:
        key = (t["date"], t["amount"], t["description"], t.get("details"))
        t["id"] = txn_id(account_id, t, seen[key])
        seen[key] += 1


def parse_files(account, files, issues):
    """Parse every file of an account. Returns [(result, path)]."""
    out = []
    for path in files:
        parser, text = read_document(path)
        if not parser:
            issues.append(f"{path.relative_to(ROOT)}: no parser recognises this file any more")
            continue
        r = parser.parse(path, text)
        for line in r.get("unparsed", []):
            issues.append(f"{path.relative_to(ROOT)}: unparsed line: {line}")
        out.append((r, path))
    return out


def load_statements(account, parsed, issues):
    """Documents with opening/closing balances: each must reconcile and open where the previous one closed."""
    statements, txns = [], []
    for r, path in parsed:
        s = dict(r["statement"], account_id=account["id"], source_file=str(path.relative_to(ROOT)))
        total = s["opening_balance"] + sum(t["amount"] for t in r["transactions"])
        s["reconciles"] = total == s["closing_balance"]
        if not s["reconciles"]:
            issues.append(f"{s['source_file']}: opening + transactions = {total}, statement says {s['closing_balance']}")
        statements.append(s)
        txns += [dict(t, account_id=account["id"], source_file=s["source_file"]) for t in r["transactions"]]
    statements.sort(key=lambda s: s["statement_date"])
    for prev, cur in zip(statements, statements[1:]):
        cur["gap_before"] = prev["closing_balance"] != cur["opening_balance"]
    return statements, txns


def merge_exports(account, parsed):
    """Exports (CSV etc.) may overlap: keep each transaction once, then check the running balance chains."""
    has_balance = any(t.get("balance_after") is not None for r, _ in parsed for t in r["transactions"])
    merged, seen = [], Counter()
    for r, path in sorted((e for e in parsed if e[0]["transactions"]), key=lambda e: e[0]["transactions"][0]["date"]):
        counts = Counter()
        for t in r["transactions"]:
            # Banks sometimes rename a transaction once it settles, so the balance identifies it better.
            key = (t["date"], t["amount"], t.get("balance_after") if has_balance else t["description"])
            counts[key] += 1
            if counts[key] > seen[key]:
                merged.append(dict(t, account_id=account["id"], source_file=str(path.relative_to(ROOT))))
        seen |= counts
    merged.sort(key=lambda t: t["date"])  # stable: same-day order within an export is kept
    breaks = [(a, b) for a, b in zip(merged, merged[1:])
              if a.get("balance_after") is not None and b.get("balance_after") is not None
              and a["balance_after"] + b["amount"] != b["balance_after"]]
    return merged, breaks, has_balance


def load_rules():
    return [(re.compile(r["pattern"], re.I), r["category"], r.get("account_id") or None,
             Decimal(r["amount"]) if r.get("amount") else None) for r in read_csv("rules.csv")]


def categorise(txns, rules, overrides):
    for t in txns:
        haystack = f"{t['description']} {t.get('details') or ''}"
        t["category"] = next((cat for pattern, cat, acct, amount in rules
                              if (acct is None or acct == t["account_id"])
                              and (amount is None or t["amount"] == amount)
                              and pattern.search(haystack)), None)
        o = overrides.get(t["id"])
        if o:
            t["category"] = o.get("category") or t["category"]
            t["note"] = o.get("note") or None


def fx_rates():
    """fx_rates.csv: month,currency,rate — 1 unit of currency = rate units of the home currency."""
    rates = defaultdict(dict)
    for r in read_csv("fx_rates.csv"):
        rates[r["currency"]][r["month"]] = Decimal(r["rate"])
    return rates


def to_home(amount, currency, on, rates):
    """Convert to the home currency at that month's rate, or the nearest month's. None if no rate is known."""
    if amount is None:
        return None
    if currency == HOME:
        return Decimal(str(amount))
    by_month = rates.get(currency)
    if not by_month:
        return None
    m = month_of(on)
    key = m if m in by_month else min(by_month, key=lambda k: abs(int(k[:4]) * 12 + int(k[5:]) - int(m[:4]) * 12 - int(m[5:])))
    return (Decimal(str(amount)) * by_month[key]).quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------------------------------------------
# Report sections

def latest_balances(accounts, statements, txns, balances):
    """Latest known balance of every account: last statement, last running balance, or balances.csv (newest wins)."""
    latest = {}

    def offer(account_id, on, balance, source):
        if account_id not in latest or on >= latest[account_id][0]:
            latest[account_id] = (on, balance, source)

    for s in statements:
        offer(s["account_id"], s["statement_date"], s["closing_balance"], "last statement")
    for t in txns:
        if t.get("balance_after") is not None:
            offer(t["account_id"], t["date"], t["balance_after"], "last export")
    for b in sorted(balances, key=lambda b: b["date"]):
        offer(b["account_id"], b["date"], b["balance"], b["note"] or "balances.csv")
    return latest


def balances_section(accounts, latest, rates):
    lines = ["## Balances\n", "| Account | Type | Balance | As of | Source |", "|---|---|---|---|---|"]
    totals = Counter()
    for a in accounts:
        if a["id"] not in latest or a["status"] != "active":
            continue
        on, bal, source = latest[a["id"]]
        home = to_home(bal, a["currency"], on, rates)
        bucket = "cash" if a["type"] in CASH_TYPES else "debt" if a["type"] in DEBT_TYPES else "other assets"
        if home is not None:
            totals[bucket] += home
        stale = " (over 45 days old)" if (TODAY - on).days > 45 else ""
        lines.append(f"| {a['id']} | {a['type']} | {fmt(bal, a['currency'])} | {on}{stale} | {source} |")
    lines.append(f"\nCash {fmt(totals['cash'])} · other assets {fmt(totals['other assets'])} · "
                 f"debt {fmt(totals['debt'])} · net {fmt(sum(totals.values()))} (in {HOME})\n")
    return lines


def loans_section(latest):
    """Payoff projection for each loan in loans.csv from its latest balance."""
    loans = read_csv("loans.csv")
    rows = []
    for loan in loans:
        if loan["account_id"] not in latest or not loan.get("monthly_payment"):
            continue
        on, balance, _ = latest[loan["account_id"]]
        owed, rate, payment = -balance, Decimal(loan["annual_rate"] or 0) / 12, Decimal(loan["monthly_payment"])
        remaining, interest, months = owed, Decimal(0), 0
        while remaining > 0 and months < 600:
            month_interest = (remaining * rate).quantize(Decimal("0.01"))
            if payment <= month_interest:
                months = None
                break
            interest += month_interest
            remaining -= min(payment - month_interest, remaining)
            months += 1
        if months is None:
            rows.append(f"| {loan['account_id']} | {fmt(owed)} | {Decimal(loan['annual_rate']) * 100:.2f}% | {fmt(payment)} "
                        f"| never: the payment doesn't cover the interest | | |")
            continue
        final = loan.get("final_payment_date")
        if not final:
            m = on.month - 1 + months
            final = f"~{on.year + m // 12}-{m % 12 + 1:02d} (projected)"
        rows.append(f"| {loan['account_id']} | {fmt(owed)} | {Decimal(loan['annual_rate'] or 0) * 100:.2f}% | {fmt(payment)} "
                    f"| {months} | {fmt(interest)} | {final} |")
    if not rows:
        return []
    return ["## Loans\n", "| Loan | Owed | Rate | Payment | Payments left | Interest still to pay | Final payment |",
            "|---|---|---|---|---|---|---|"] + rows + [""]


def lent_balances(txns):
    """Money lent to people: transactions categorised 'Lent: <name>' (out = lent, in = repaid) plus lent.csv."""
    by_person = defaultdict(lambda: [Decimal(0), Decimal(0), None])
    for t in txns:
        if (t.get("category") or "").startswith("Lent: ") and t.get("amount_home") is not None:
            p = by_person[t["category"][6:]]
            p[0 if t["amount_home"] < 0 else 1] += abs(t["amount_home"])
            p[2] = t["date"]
    for r in read_csv("lent.csv"):
        p = by_person[r["person"]]
        p[0] += Decimal(r["amount"])
        d = date.fromisoformat(r["date"])
        p[2] = max(p[2], d) if p[2] else d
    return dict(by_person)


def lent_section(txns):
    by_person = lent_balances(txns)
    if not by_person:
        return []
    lines = ["## Money owed to you\n", "| Person | Lent | Repaid | Outstanding | Last movement |", "|---|---|---|---|---|"]
    for person, (lent, repaid, last) in sorted(by_person.items()):
        lines.append(f"| {person} | {fmt(lent)} | {fmt(repaid)} | {fmt(lent - repaid)} | {last} |")
    return lines + [""]


def budget_actuals(txns, month):
    """[(line, budget, spent)] for a month from budget.csv (line,monthly,categories,note)."""
    out = []
    budget = read_csv("budget.csv")
    covered = []
    for b in budget:
        pats = [p.strip() for p in b["categories"].split(";") if p.strip()]
        covered += pats
        spent = -sum((t["amount_home"] for t in txns if month_of(t["date"]) == month and t.get("amount_home") is not None
                      and matches(t["category"], pats)), Decimal(0))
        out.append((b["line"], Decimal(b["monthly"]), spent))
    if budget:
        other = -sum((t["amount_home"] for t in txns if month_of(t["date"]) == month and t.get("amount_home") is not None
                      and t["amount_home"] < 0 and not is_transfer(t["category"]) and not matches(t["category"], covered)
                      and not (t["category"] or "").startswith(("Income", "Lent"))), Decimal(0))
        out.append(("Not in the budget", Decimal(0), other))
    return out


def budget_section(txns):
    if not read_csv("budget.csv"):
        return []
    lines = ["## Budget\n"]
    for month in (month_of(TODAY.replace(day=1) - timedelta(days=1)), month_of(TODAY)):
        rows = budget_actuals(txns, month)
        lines += [f"**{month}**{' (so far)' if month == month_of(TODAY) else ''}\n",
                  "| Line | Budget | Spent | Left |", "|---|---|---|---|"]
        for line, budget, spent in rows:
            flag = " ⚠" if budget and spent > budget else ""
            lines.append(f"| {line} | {fmt(budget)} | {fmt(spent)} | {fmt(budget - spent)}{flag} |")
        lines.append(f"| **Total** | **{fmt(sum(r[1] for r in rows))}** | **{fmt(sum(r[2] for r in rows))}** | |\n")
    lines.append("Accounts that aren't up to date make 'Spent' look low.\n")
    return lines


def merchant_key(t):
    """Group charges from the same merchant: the description (or the counterparty at the start of details, when
    the description is generic), lower case, without digits or punctuation, so changing amounts and dates match."""
    text = t["description"]
    if t.get("details") and re.match(r"(?i)card (transaction|payment)|direct debit|payment to|purchase", text):
        text = t["details"].split(" — ")[0]
    return " ".join(re.sub(r"[^a-z ]+", " ", text.lower()).split())


def recurring(txns, months_back=6):
    """Outgoing payments seen in at least 3 of the last `months_back` months: subscriptions, bills, direct debits."""
    start = (TODAY.replace(day=1) - timedelta(days=31 * (months_back - 1))).replace(day=1)
    groups = defaultdict(list)
    for t in txns:
        if t["date"] >= start and t["amount"] < 0 and not is_transfer(t["category"]):
            groups[(t["account_id"], merchant_key(t))].append(t)
    out = []
    for (account, key), ts in groups.items():
        months = {month_of(t["date"]) for t in ts}
        if len(months) >= 3 and key:
            last = max(ts, key=lambda t: t["date"])
            out.append({"merchant": last["description"], "account_id": account, "months": len(months),
                        "last_date": last["date"], "last_amount": last["amount"], "currency": last["currency"],
                        "category": last["category"], "active": (TODAY - last["date"]).days <= 40})
    return sorted(out, key=lambda r: (not r["active"], r["last_amount"]))


def recurring_section(txns):
    rows = recurring(txns)
    if not rows:
        return []
    lines = ["## Recurring payments\n",
             "Seen in 3+ of the last 6 months. Check each is still wanted; ones not seen for 40+ days may have stopped.\n",
             "| Merchant | Account | Months | Last | Amount | Category |", "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['merchant']} | {r['account_id']} | {r['months']} | {r['last_date']}"
                     f"{'' if r['active'] else ' (stopped?)'} | {fmt(-r['last_amount'], r['currency'])} | {r['category'] or '—'} |")
    return lines + [""]


def coming_up(days=90):
    """Deadlines (deadlines.csv) and contract end / notice dates (contracts.csv) in the next `days`, plus overdue."""
    items = []
    for d in read_csv("deadlines.csv"):
        if (d.get("done") or "").strip():
            continue
        items.append((date.fromisoformat(d["date"]), d["item"], d.get("note") or ""))
    for c in read_csv("contracts.csv"):
        if c.get("end"):
            end = date.fromisoformat(c["end"])
            items.append((end, f"{c['counterparty']} {c['type']} ends", c.get("renewal") or ""))
            if c.get("notice_days"):
                items.append((end - timedelta(days=int(c["notice_days"])),
                              f"Last day to give notice: {c['counterparty']} {c['type']}", c.get("notice") or ""))
    return sorted(i for i in items if i[0] <= TODAY + timedelta(days=days) and (i[0] >= TODAY - timedelta(days=60)))


def coming_up_section():
    items = coming_up()
    if not items:
        return []
    lines = ["## Coming up (next 90 days)\n", "| Date | What | Note |", "|---|---|---|"]
    for d, what, note in items:
        lines.append(f"| {d}{' **overdue**' if d < TODAY else ''} | {what} | {note} |")
    return lines + [""]


# ---------------------------------------------------------------------------------------------------------------
# Output

def sqlify(row):
    return {k: (float(v) if isinstance(v, Decimal) else str(v) if hasattr(v, "isoformat") else v) for k, v in row.items()}


def write_db(accounts, statements, txns, balances, latest):
    DATA.mkdir(exist_ok=True)
    db_path = DATA / "finance.db"
    db_path.unlink(missing_ok=True)
    db = sqlite3.connect(db_path)
    db.executescript(f"""
        CREATE TABLE accounts (id TEXT PRIMARY KEY, institution TEXT, name TEXT, type TEXT, currency TEXT,
            identifiers TEXT, status TEXT, notes TEXT);
        CREATE TABLE balances (account_id TEXT, date TEXT, balance REAL, note TEXT);
        CREATE TABLE latest_balances (account_id TEXT PRIMARY KEY, date TEXT, balance REAL, source TEXT);
        CREATE TABLE statements (account_id TEXT, statement_date TEXT, period_start TEXT, period_end TEXT,
            opening_balance REAL, closing_balance REAL, min_payment REAL, due_date TEXT, reconciles INTEGER,
            gap_before INTEGER, source_file TEXT);
        CREATE TABLE transactions ({', '.join(f + (' TEXT PRIMARY KEY' if f == 'id' else '') for f in TXN_FIELDS)});
        CREATE INDEX transactions_date ON transactions (account_id, date);
    """)
    cols = ["id", "institution", "name", "type", "currency", "identifiers", "status", "notes"]
    db.executemany(f"INSERT INTO accounts VALUES ({', '.join(':' + c for c in cols)})",
                   [{c: a.get(c) for c in cols} for a in accounts])
    db.executemany("INSERT INTO balances VALUES (:account_id, :date, :balance, :note)", [sqlify(b) for b in balances])
    db.executemany("INSERT INTO latest_balances VALUES (?, ?, ?, ?)",
                   [(k, str(d), float(b), s) for k, (d, b, s) in latest.items()])
    scols = ["account_id", "statement_date", "period_start", "period_end", "opening_balance", "closing_balance",
             "min_payment", "due_date", "reconciles", "gap_before", "source_file"]
    db.executemany(f"INSERT INTO statements VALUES ({', '.join(':' + c for c in scols)})",
                   [sqlify({c: s.get(c) for c in scols}) for s in statements])
    db.executemany(f"INSERT INTO transactions VALUES ({', '.join(':' + f for f in TXN_FIELDS)})",
                   [sqlify({f: t.get(f) for f in TXN_FIELDS}) for t in txns])
    db.commit()
    db.close()


def write_csv(txns):
    with open(DATA / "transactions.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TXN_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(txns)


def load_all(issues=None, coverage=None):
    """Parse and check every source. Returns (accounts, statements, txns, balances, report coverage rows)."""
    issues = [] if issues is None else issues
    coverage = [] if coverage is None else coverage
    accounts = load_accounts()
    balances = [dict(r, date=date.fromisoformat(r["date"]), balance=Decimal(r["balance"])) for r in read_csv("balances.csv")]
    statements, txns, rows = [], [], []
    for account in accounts:
        folder = SOURCES / account["id"]
        files = sorted(p for p in folder.glob("*") if p.is_file() and not p.name.startswith(".")) if folder.exists() else []
        if not files:
            status = (f"{account['status']}" if account["status"] != "active"
                      else "balance from balances.csv" if account["type"] in DEBT_TYPES | {"investment", "pension", "cash"}
                      else "no files yet")
            rows.append(f"| {account['id']} | — | — | — | 0 | {status} |")
            continue
        parsed = parse_files(account, files, issues)
        acct_txns = []
        stmt_files = [e for e in parsed if e[0].get("statement")]
        export_files = [e for e in parsed if not e[0].get("statement")]
        if stmt_files:
            stmts, acct_txns = load_statements(account, stmt_files, issues)
            statements += stmts
            bad = [s for s in stmts if not s["reconciles"]]
            gaps = [s for s in stmts if s.get("gap_before")]
            rows.append(f"| {account['id']} | {len(stmts)} statements | {stmts[0]['statement_date']} | "
                        f"{stmts[-1]['statement_date']} | {len(acct_txns)} | "
                        f"{len(stmts) - len(bad)}/{len(stmts)} reconcile; {len(gaps)} gap(s) |")
            have = {month_of(s["statement_date"]) for s in stmts}
            # No statement is issued while nothing is owed, so a month between two zero balances isn't missing.
            zero = set()
            for prev, cur in zip(stmts, stmts[1:]):
                if prev["closing_balance"] == 0 and cur["opening_balance"] == 0:
                    zero.update(months_between(prev["statement_date"], cur["statement_date"]))
            missing = [m for m in months_between(stmts[0]["statement_date"], stmts[-1]["statement_date"])
                       if m not in have and m not in zero]
            if missing:
                coverage.append(f"- **{account['id']}**: missing statements for {', '.join(missing)}")
            for s in gaps:
                coverage.append(f"- **{account['id']}**: statement {s['statement_date']} doesn't open where the previous one closed")
        if export_files:
            merged, breaks, has_balance = merge_exports(account, export_files)
            if merged:
                check = ("no running balance in export" if not has_balance
                         else "running balance unbroken" if not breaks else f"{len(breaks)} break(s)")
                rows.append(f"| {account['id']} | {len(export_files)} export(s) | {merged[0]['date']} | {merged[-1]['date']} | "
                            f"{len(merged)} | {check} |")
            else:
                rows.append(f"| {account['id']} | {len(export_files)} export(s) | — | — | 0 | empty |")
            for a, b in breaks:
                coverage.append(f"- **{account['id']}**: balance doesn't follow on between {a['date']} and {b['date']} "
                                f"(missing transactions or a missing export?)")
            acct_txns += merged
        for t in acct_txns:
            t.setdefault("currency", account["currency"])
            if t["date"] > TODAY:
                issues.append(f"{t['source_file']}: transaction dated in the future ({t['date']})")
        acct_txns.sort(key=lambda t: t["date"])
        assign_ids(account["id"], acct_txns)
        txns += acct_txns
        if account["status"] == "active" and acct_txns and (TODAY - acct_txns[-1]["date"]).days > 35:
            coverage.append(f"- **{account['id']}**: latest transaction is {acct_txns[-1]['date']}; download a newer export")
    return accounts, statements, txns, balances, rows


def build():
    unfiled = ingest()
    issues = [f"Not filed: {p.relative_to(ROOT)} — {why}" for p, why in unfiled]
    coverage = []
    accounts, statements, txns, balances, rows = load_all(issues, coverage)

    overrides = {r["id"]: r for r in read_csv("overrides.csv")}
    categorise(txns, load_rules(), overrides)
    rates = fx_rates()
    no_rate = Counter()
    for t in txns:
        t["amount_home"] = to_home(t["amount"], t["currency"], t["date"], rates)
        if t["amount_home"] is None:
            no_rate[t["currency"]] += 1
    for cur, n in no_rate.items():
        issues.append(f"{n} {cur} transactions have no {cur}→{HOME} rate: add rows to fx_rates.csv")
    txns.sort(key=lambda t: (t["date"], t["account_id"]))
    latest = latest_balances(accounts, statements, txns, balances)

    write_db(accounts, statements, txns, balances, latest)
    write_csv(txns)

    uncategorised = sum(1 for t in txns if not t["category"])
    report = ["# Finance report\n", f"Built {TODAY}. Amounts in {HOME} unless shown otherwise.\n",
              "## Coverage\n", "| Account | Source | From | To | Transactions | Checks |", "|---|---|---|---|---|---|"]
    report += rows
    report.append(f"\n{len(txns)} transactions in total; {uncategorised} uncategorised.\n")
    report += balances_section(accounts, latest, rates)
    report += loans_section(latest)
    report += lent_section(txns)
    report += budget_section(txns)
    report += recurring_section(txns)
    report += coming_up_section()
    report.append("## Coverage gaps\n")
    report.extend(coverage or ["None found."])
    report.append("\n## Issues\n")
    report.extend([f"- {i}" for i in issues] or ["None."])
    (DATA / "report.md").write_text("\n".join(report) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    build()
