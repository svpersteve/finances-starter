---
name: month-review
description: Review a month of the owner's finances - spending against the budget, bills and income that should or shouldn't have happened, recurring payments, debts, money owed, and deadlines coming up - and turn it into a short list of actions. Use when the owner asks "how did I do this month?", "am I on budget?", "anything I've missed?", for a monthly review or check-up, or at month end, even if they don't say "review".
---

# Month review

Pick the month (default: the last full month; this month so far if asked mid-month).

1. **Is the data current?** In `data/report.md`, check each active account's latest date. If any end well before
   the month's end, list which statements to download and offer to wait; a review on half the data misleads.
   Ingest anything new with `add-statements`.
2. **Uncategorised first.** Categorise the month's uncategorised transactions before trusting any totals.
3. **Budget.** The report's Budget section (or `budget_actuals` in `build.py` for another month). List lines over
   budget with the biggest few transactions behind each, and the biggest items "Not in the budget". If a line is
   over every month, suggest changing the budget or the habit, and let the owner decide.
4. **Expected in.** Income at the usual amount and date; repayments from people (`Lent:`); refunds being waited on.
5. **Expected out.** Rent/mortgage, bills and loans at the agreed amounts (`contracts.csv`, `loans.csv`). Flag price
   rises.
6. **Shouldn't be there.** New recurring payments (report → Recurring payments), subscriptions the owner said
   they cancelled, duplicate charges, fees and interest (`Debt: interest & fees`), foreign transaction fees.
7. **Debt and cash.** Change in cash and in each debt since last month (`snapshots.csv`, report → Balances). Is the
   debt plan on track (`debt-plan`)?
8. **Coming up.** Deadlines and contract notice dates in the next 90 days (report → Coming up); annual bills due
   next month.

Report in a short summary: on or over budget (and by how much), what's missing, what shouldn't be there, debt and
cash change, what's coming up. End with a numbered list of actions (cancel X, chase refund Y, give notice on Z by
date). Offer to put them in the owner's todo list if Claude can reach it. Then `dashboard`.
