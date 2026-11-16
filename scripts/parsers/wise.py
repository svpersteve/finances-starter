"""Wise balance statements, exported as CSV (one file per currency balance).

In Wise: open a balance → Statements → Download → CSV. The file is named
statement_<balance id>_<CUR>_<from>_<to>.csv; the balance id goes in accounts.csv identifiers.
"""
import csv
import re
from decimal import Decimal

from .common import mask_card_numbers, parse_date, squash

INSTITUTION = "Wise"
FILE_TYPES = {".csv"}
HEADER_START = '"TransferWise ID",Date,'


def detect(path, text):
    with open(path, encoding="utf-8-sig") as f:
        return f.readline().startswith(HEADER_START)


def payee_account(number):
    return f"to account {number.replace(' ', '')}" if number else None


def parse(path, text):
    m = re.match(r"statement_(\d+)_[A-Z]{3}_(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})", path.name)
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    txns = []
    # The export is newest first; reverse so running balances read forwards.
    for row in reversed(rows):
        counterparty = row.get("Payee Name") or row.get("Payer Name") or row.get("Merchant")
        txns.append({
            "date": parse_date(row["Date"], "%d-%m-%Y"),
            "description": squash(row["Description"]),
            "details": mask_card_numbers(squash(" — ".join(v for v in (
                counterparty, row.get("Payment Reference"), row.get("Note"),
                payee_account(row.get("Payee Account Number"))) if v))) or None,
            "amount": Decimal(row["Amount"]),
            "balance_after": Decimal(row["Running Balance"]),
            "external_id": row["TransferWise ID"],
            "fees": Decimal(row["Total fees"]) if row.get("Total fees") else None,
        })
    return {
        "identifier": m.group(1) if m else "",
        "transactions": txns,
        "unparsed": [],
        "name": f"{m.group(2)}_{m.group(3)}" if m else None,
    }
