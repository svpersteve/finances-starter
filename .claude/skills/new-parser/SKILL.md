---
name: new-parser
description: Add support for a new kind of financial document (a new bank, card, loan, investment or pension statement, or a changed export format) - write the parser, register the account, and prove it reconciles. Use when ingest reports a file no parser recognises, a new account turns up, or a bank changes its export format, even if the owner doesn't say "parser".
---

# New parser

A parser isn't done until `data/report.md` shows the account reconciling with no breaks.

1. **Look at the document.** PDF: `pdftotext -layout <file> - | head -150`. CSV: the header and first rows.
   XLSX: `python3 -c "import zipfile; ..."` or ask for a CSV export instead if the bank offers one (no extra
   libraries are installed; prefer CSV). Find:
   - the account identifier (card last 4, IBAN/account number tail, an id in the file name);
   - opening/closing balance (statements) or a running balance column (exports);
   - date format, sign convention (separate debit/credit columns? "CR" suffix?), currency, row order;
   - whether the format or language changed over time (compare an old and a new file).
2. **Prefer the document with balances.** If the bank offers both, use the format that lets the build check
   completeness: statements with opening/closing, or exports with a running balance.
3. **New version of an existing format?** Extend that parser's `detect`/`parse` instead of adding a module.
4. **Write `scripts/parsers/<institution>.py`** from `_template.py` (contract in `parsers/__init__.py`):
   `INSTITUTION`, `FILE_TYPES`, `detect(path, text)` and `parse(path, text)`. Transactions oldest first, amounts as
   `Decimal`, negative = money out / more owed, credit card balances negative. Mask card numbers with
   `mask_card_numbers`. Make `detect` specific (the bank's web address plus a heading) so it never claims another
   bank's file. No wiring needed: the module is picked up automatically.
5. **Register the account** in `accounts.csv`: `institution` exactly as `INSTITUTION`, the identifier in
   `identifiers`. For a foreign-currency account, add rates to `fx_rates.csv`.
6. **Build and reconcile.** `python3 scripts/build.py`. In `report.md`, every statement reconciles and follows
   on, or the running balance is unbroken, and there are no "unparsed line" issues. Fix until clean. Then check a
   few transactions by eye against the document, including a refund and a foreign-currency one if there are any.
7. **Categorise** the new account's transactions (`add-statements` step 4).
8. **Commit** the parser and CSVs. If the workflow changed, update CLAUDE.md.

Investment and pension accounts: ask how the owner wants them shown. Usually a balance in `balances.csv` from
the latest valuation is enough; contributions in and out are `Transfer: ...` on the paying account.
