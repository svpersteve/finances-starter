---
name: debt-plan
description: Work out how to pay down the owner's debts - what each costs, which to pay first, how long it takes and how much interest it saves - and check progress month to month. Use when the owner asks "which debt should I pay first?", "how long until I'm debt free?", "should I overpay?", "what if I paid £X more?", mentions a 0% offer ending or a balance transfer, or has spare money and debts, even if they don't say "plan".
---

# Debt plan

1. **What's owed.** Report → Balances and Loans: each debt's balance, as of when, and its source. Bring stale
   ones up to date (ask for the app balance → `balances.csv`, or a new statement).
2. **What each costs.** For each debt: the headline rate on new spending and any promotional rates with their end
   dates and balances (read from the latest card statement, which usually lists them), minimum payment, and fees.
   A card mostly on a 0% promotion looks cheap but its purchase rate is what new spending costs. Put loan terms in
   `loans.csv`.
3. **Order.** Default to highest interest rate first (avalanche) while paying minimums on the rest. Two exceptions
   to discuss: a 0% promotion ending soon (clear it before it reverts) and a small balance the owner would be
   motivated to close (snowball). Let the owner choose.
4. **How much a month.** From the last three months: income less regular spending (summary or report), less a
   buffer. Don't plan to use money that's needed for tax or annual bills.
5. **Project.** Month by month, with the chosen extra payment going to the first debt and rolling to the next once
   it's cleared: when each is cleared, total interest, and the difference against minimums only. Show it as a
   short table.
6. **Write it down.** Record the plan (monthly amount, order, target dates) in CLAUDE.md under About me, and put
   promotion end dates in `deadlines.csv`.
7. **Check progress** at each `month-review`: balances against the plan, new spending on cards being paid down.

Don't recommend specific financial products. If the owner is struggling to make minimum payments, say so plainly
and point them to free debt advice in their country (e.g. StepChange or Citizens Advice in the UK) before
anything else.
