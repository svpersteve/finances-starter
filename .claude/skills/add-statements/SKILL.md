---
name: add-statements
description: Ingest new bank, card, loan, investment or other financial documents into the ledger, check they reconcile, categorise the new transactions, check expected payments, and commit. Use whenever the owner says they've added, dropped or downloaded a statement, export or receipt, says "new files in inbox" or "I've put the X statement in", even if they don't say "ingest".
---

# Add statements

1. **See what's new.** `ls inbox/` and any loose PDF/CSV/XLSX in the root. Note what the owner says each file is.
2. **Build.** `python3 scripts/build.py` (it runs `ingest.py` first). Every file should be filed to
   `sources/<account>/` or marked duplicate.
   - Refused because the account isn't in `accounts.csv`: it's a new account, or the row is missing its identifier.
     Ask what it is, add or fix the row, rebuild.
   - Not recognised by any parser: `new-parser` skill.
3. **Check `data/report.md`.**
   - Coverage: the account shows `N/N reconcile; 0 gap(s)` or `running balance unbroken`. A break is a parser
     or file problem (or a missing statement); fix it before going on, never paper over it.
   - Coverage gaps and Issues: anything new.
4. **Categorise.** List the new uncategorised transactions:
   `sqlite3 data/finance.db "select id,date,account_id,amount,description,details from transactions where category is null order by date desc limit 100"`.
   - A merchant that will recur → a rule in `rules.csv` (specific rules above broad ones; use `account_id` or
     `amount` to tell apart charges from the same merchant).
   - A one-off → a row in `overrides.csv` (`id,category,note`).
   - Moving money between own accounts and paying a card off → `Transfer: ...`; money to or from a person they lent
     to → `Lent: <name>`.
   - Ask about anything that can't be placed (unnamed transfers, payments to people) instead of guessing.
   Rebuild after changes and repeat until nothing recent is uncategorised.
5. **Expected payments.** Check against what should have happened: income arrived, rent and bills paid at the
   agreed amounts (`contracts.csv`), loan payments (`loans.csv`), repayments from people, refunds being waited on,
   subscriptions they cancelled not charging again. Look at the report's Recurring payments for anything new.
6. **Balances.** If a newer statement supersedes a balance in `balances.csv`, leave the row (the newer one wins)
   but mention it.
7. **Summarise and commit.** In a few lines: what was added (account, dates), reconcile status, anything notable
   (big or odd charges, new recurring payments, price rises), and follow-ups. Commit the CSV changes
   (`git add -A`; `data/` and `sources/` are ignored unless the owner changed that). Offer the `dashboard` skill.

Never edit files in `sources/`.
