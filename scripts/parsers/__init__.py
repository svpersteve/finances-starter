"""Every module in this folder (except common.py and names starting with '_') is a parser.

A parser module defines:

    INSTITUTION = "Wise"          # matched against the institution column in accounts.csv
    FILE_TYPES = {".csv"}         # file extensions it can read (lower case)

    def detect(path, text):       # text is the PDF's text for PDFs, else None. Return True if this is yours.
    def parse(path, text):        # return a dict, see below

parse() returns:

    {
      "identifier": "1234",       # card last 4, IBAN tail, account id... matched against accounts.csv identifiers
      "transactions": [           # oldest first
          {"date": date, "description": str, "amount": Decimal,   # negative = money out / more owed
           # optional: "posted_date", "details", "balance_after", "external_id", "fees",
           #           "original_amount", "original_currency", "fx_rate"
          }, ...],
      "statement": {              # only for documents with an opening and closing balance (e.g. card statements)
          "statement_date": date, "opening_balance": Decimal, "closing_balance": Decimal,
          # optional: "period_start", "period_end", "min_payment", "due_date"
      },
      "unparsed": [str, ...],     # lines that looked like transactions but didn't match: build reports them
      "name": "optional canonical file name stem, used when there are no transactions",
    }

Build checks every statement (opening + transactions = closing, and each opens where the last closed) and every
export with balance_after (the running balance chains row to row). A parser isn't done until both hold.
See _template.py for a starting point.
"""
import importlib
import pkgutil

_cache = None


def all_parsers():
    global _cache
    if _cache is None:
        _cache = [importlib.import_module(f"{__name__}.{m.name}") for m in pkgutil.iter_modules(__path__)
                  if not m.name.startswith("_") and m.name != "common"]
    return _cache
