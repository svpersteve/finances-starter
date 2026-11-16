---
name: setup
description: First-session setup of the personal finances ledger - interview the owner about their life and money, register their accounts, plan which documents to collect and how far back, set up categories, a first budget, deadlines and debts, and get the first statements in and reconciling. Use when CLAUDE.md says "Not set up yet", when the owner says "set this up", "get started", "where do I begin", or when accounts.csv is empty, even if they don't say "setup".
---

# Setup

The aim of the first session: Claude knows enough about the owner's life to help, every account is registered,
and the first documents are in and reconciling. Don't try to do everything at once; get one account fully working
before widening.

## 1. Check the tools

`python3 --version` (3.9+) and `pdftotext -v`. If `pdftotext` is missing on a Mac: `brew install poppler`
(Homebrew first if needed). Run `git init` if the folder isn't a repo yet, and make a first commit.

## 2. Interview

Ask in small batches, conversationally, not as a form. Skip what doesn't apply.

1. **Life basics.** Country of residence (and tax residence if different), home currency, who else shares the
   money (partner, kids, flatmates), housing (rent, mortgage, living with family).
2. **Income.** Employed, self-employed or both; how often and into which account; other income (rent, side work,
   benefits, investments).
3. **Accounts.** Every current account, savings account, credit card, loan, mortgage, overdraft, buy-now-pay-later,
   investment and pension, including old or closed ones they want history for. For each: institution, what it's
   for, currency, and whether they can download statements (PDF) or exports (CSV/XLSX/OFX) from it.
4. **Bills and commitments.** Rent/mortgage, utilities, phone, internet, insurance, subscriptions, gym, childcare,
   car. Any contracts with end dates or notice periods.
5. **Debts and money owed.** Balances, rates and monthly payments they know; money lent to or borrowed from people.
6. **Tax.** What they file and when (self-assessment, quarterly payments, annual return), and whether they use an
   accountant. Their key dates go into `deadlines.csv`.
7. **Goals and worries.** What would make this worth it: stop running out before payday, clear a card, build an
   emergency fund, save for something, get tax under control, just know where it all goes.
8. **How far back.** Default: 12 months for spending patterns; longer (e.g. back to a tax year start, or years)
   if they want history for tax or to understand debt. Statements usually only go back so far online.
9. **Todo list.** Do they keep one (Apple Reminders, Todoist, Things, paper)? Actions that come out of reviews can
   go there if Claude has a way to reach it; otherwise list them at the end of each session.

## 3. Write it down

- Fill in "About me" in `CLAUDE.md`: a short factual paragraph or bullets. Replace "Not set up yet".
- `config.json`: `home_currency`.
- `accounts.csv`: one row per account (ids like `monzo-current`, `amex-cc`, `car-loan`). Leave `identifiers` blank
  until a document shows them.
- `balances.csv` and `loans.csv` for debts and assets with no documents yet (as of today, noted as "told by owner").
- `lent.csv` for money owed to them that no transaction will show.
- `deadlines.csv`: tax deadlines for their country and situation (check the current year's dates on the official
  tax authority site rather than from memory), plus renewals and anything else they mentioned.
- `contracts.csv`: the contracts they mentioned, even without the PDF yet (leave `file` blank).
- Commit.

## 4. First documents

Give them a short checklist: which statements/exports to download from which account, for which period, in which
format (prefer CSV/XLSX exports with a running balance for current accounts; PDF statements for credit cards,
because they carry opening and closing balances). Ask them to drop the files into `inbox/`.

Then for each new institution: `new-parser` skill. For each batch: `add-statements` skill. Start with the main
current account; it shows most of the money and where the other accounts get paid from.

## 5. Categories and budget

Once the main account is in, categorise with the owner (`add-statements` step 4), using the `Group: detail`
convention in CLAUDE.md. When three or more months are in, draft `budget.csv` from the real averages
(`summary.py` and the report's Recurring payments), go through it with them line by line, and adjust to their goals.

## 6. Finish

Run the report, summary and dashboard. Tell them in a few lines what's covered, what's missing, and the three
most useful things noticed so far (e.g. a subscription they forgot, a card costing a lot in interest, an upcoming
deadline). Suggest a rhythm: drop new statements in monthly and run `month-review`.
