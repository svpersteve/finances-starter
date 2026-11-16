"""Template for a new parser. Copy to <bank>.py (no leading underscore) and fill in.

Two common shapes are sketched below: a PDF statement with opening/closing balances, and a CSV export with a
running balance. Delete the one you don't need. See __init__.py for the full contract.
"""
import csv
import re

from .common import day_month_with_year, mask_card_numbers, money, parse_date, squash

INSTITUTION = "Example Bank"
FILE_TYPES = {".pdf"}  # or {".csv"}, {".xlsx"}...

# One transaction line in the PDF's layout text, e.g. "02 Jun   03 Jun   TESCO STORES 1234      12.34"
TXN = re.compile(r"^\s*(\d{2} \w{3})\s{2,}(\d{2} \w{3})\s{2,}(.+?)\s{2,}([\d,]+\.\d{2})(\s*CR)?\s*$")


def detect(path, text):
    # Look for something only this institution's documents contain (its web address, a heading).
    return text is not None and "examplebank.com" in text and "Your statement" in text


def parse(path, text):
    # --- PDF statement ---------------------------------------------------------------------------------------
    card = re.search(r"Card number\s+[\d* ]+?(\d{4})\s*$", text, re.M).group(1)
    stmt_date = parse_date(re.search(r"Statement date\s+(\d{2} \w+ \d{4})", text).group(1), "%d %B %Y")
    opening = money(re.search(r"Previous balance\s+([\d,.]+)", text).group(1))
    closing = money(re.search(r"New balance\s+([\d,.]+)", text).group(1))
    txns, unparsed = [], []
    for line in text.splitlines():
        m = TXN.match(line)
        if not m:
            continue  # or unparsed.append(line.strip()) for lines inside the transactions section
        amount = money(m.group(4))
        txns.append({
            "date": day_month_with_year(m.group(1), stmt_date),
            "posted_date": day_month_with_year(m.group(2), stmt_date),
            "description": squash(m.group(3)),
            # A card balance is money owed: spending is negative, payments/refunds (CR) positive.
            "amount": amount if m.group(5) else -amount,
        })
    return {
        "identifier": card,
        # Card balances are stored negative (owed).
        "statement": {"statement_date": stmt_date, "opening_balance": -opening, "closing_balance": -closing},
        "transactions": txns,
        "unparsed": unparsed,
    }

    # --- CSV export with a running balance ------------------------------------------------------------------
    # with open(path, encoding="utf-8-sig") as f:
    #     rows = list(csv.DictReader(f))
    # txns = [{
    #     "date": parse_date(r["Date"], "%d/%m/%Y"),
    #     "description": squash(r["Description"]),
    #     "details": mask_card_numbers(squash(r.get("Reference"))) or None,
    #     "amount": money(r["Amount"]),
    #     "balance_after": money(r["Balance"]),
    # } for r in rows]
    # txns.reverse()  # if the export is newest first
    # return {"identifier": "<from the file name or a header row>", "transactions": txns, "unparsed": []}
