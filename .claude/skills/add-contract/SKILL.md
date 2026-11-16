---
name: add-contract
description: File a contract, bill agreement, policy or important receipt - tenancy, mortgage, phone, broadband, energy, insurance, loan, subscription, employment, warranty - record its terms (cost, start, end, notice, renewal) so charges can be checked and notice dates aren't missed. Use when the owner hands over a contract or policy PDF, mentions signing or renewing something, asks "when does my X end?", "how much notice do I need?", or wants to switch provider, even if they don't say "contract".
---

# Add a contract

1. **Read it.** `pdftotext -layout <file> -`. Find: counterparty (use a role like "landlord" rather than a private
   person's name), type, signed date, start, end (or minimum term), cost and period, currency, notice period,
   what happens at the end (auto-renews? rolls monthly? price rise?), and anything unusual (early-exit fees,
   price-rise clauses, what's included).
2. **File it** as `sources/_documents/contracts/<signed-date>_<counterparty>_<type>.pdf` (copy; keep the original
   wherever the owner had it until they say otherwise).
3. **Record it** in `contracts.csv`. `notice_days` is the notice in days before `end` (e.g. 30), so "last day to
   give notice" appears in the report's Coming up. `category` is the ledger category its payments fall under.
4. **Check the charges.** Find its payments in the ledger (by category or merchant) and compare with the agreed
   cost. Flag any difference, and price rises since the start.
5. **Deadlines.** Add anything dated that isn't the end or notice date (a fixed-rate end, a review date,
   a deposit return) to `deadlines.csv`.
6. If the deal ends within 90 days or is out of contract, say so and offer to compare: what the owner pays now,
   and what to look for when switching. Don't recommend specific providers without checking current prices.
7. Commit `contracts.csv` and `deadlines.csv`.

Receipts (warranties, big purchases, deductible expenses) go in `sources/_documents/receipts/` as
`YYYY-MM-DD_vendor_item_total.pdf` with a row in `receipts.csv`, `transaction_id` matched to the ledger charge.
