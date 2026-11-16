---
name: dashboard
description: Rebuild the one-page finances dashboard (cash, debt, net position, budget this month, money in and out, where it went, debts, recurring payments, coming up) and say what moved since last time; also change the budget. Use when the owner asks to refresh or open the dashboard, after new statements or balances, or when they change the plan ("budget £X for Y", "add a line for Z"), even if they don't name the dashboard.
---

# Dashboard

## Refresh

1. `python3 scripts/build.py` if any sources or CSVs changed.
2. `python3 scripts/dashboard.py`. It writes `data/dashboard.html` and, once a day, a snapshot to `snapshots.csv`.
3. `open data/dashboard.html` (Mac) so the owner can see it.
4. Say in a few lines what moved since the previous snapshot (cash, each debt, money owed) and anything over
   budget this month. Commit `snapshots.csv`.

The page is a local file with the owner's real numbers. Don't publish or upload it anywhere unless they ask; if
they do, say plainly who will be able to see it first.

## Changing the budget

Lines live in `budget.csv` (`line,monthly,categories,note`). `categories` is `;`-separated category names or
prefixes ending in `:`. Add a `note` with the reason and date when a line changes for a reason the owner gave.
Every category should belong to at most one line; spending in none shows as "Not in the budget".

Yearly or irregular costs (insurance, car service, Christmas, annual subscriptions): budget them monthly (yearly
cost / 12) and suggest the owner sets that amount aside each month, so the month the bill lands isn't a shock.

## Changing the page

The layout is the `TEMPLATE` string and `build_page()` in `scripts/dashboard.py`. Keep it a single self-contained
file with no external scripts, working in light and dark mode and on a phone.
