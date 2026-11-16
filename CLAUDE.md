# Personal finances

A queryable ledger of my whole financial life, built from my own bank, card and loan documents. The goal is full
visibility (where the money goes, what I owe, what's coming up) and help managing it month to month: a budget,
bills and contracts, debts, money people owe me, and deadlines.

## About me

<!-- The setup skill fills this in during the first session. Keep it short and factual: country of residence,
home currency, how I'm paid (employed / self-employed / both), tax situation, accounts in use, goals
(e.g. clear a card, build a buffer, save for X), and anything Claude should always keep in mind. -->

Not set up yet: run the `setup` skill.

## Workflow

1. I put new statements and exports into `inbox/` (or the folder root).
2. `python3 scripts/build.py`. It first runs `scripts/ingest.py`, which files each new document into
   `sources/<account-id>/` under a canonical name, then rebuilds everything in `data/` from `sources/` and the CSVs.
3. Read `data/report.md`: coverage per account, reconciliation, balances, loans, money owed to me, budget vs actual,
   recurring payments, what's coming up, gaps and issues.
4. `python3 scripts/summary.py` for the yearly income / spending summary (`data/summary.md`).
5. `python3 scripts/dashboard.py` for a one-page dashboard (`data/dashboard.html`, opens in any browser).

Needs Python 3.9+ and, for PDFs, `pdftotext` (`brew install poppler` on a Mac). Nothing else to install.

## Layout

- `sources/<account-id>/`: original documents, renamed, never edited. This is the record.
  - `sources/_duplicates/`: copies ingest found to be identical. Safe to empty once reviewed.
  - `sources/_archives/`: zips whose contents were extracted and ingested.
  - `sources/_documents/`: reference documents that aren't parsed (tax returns, letters).
    - `contracts/`: contracts, named `<signed-date>_<counterparty>_<type>.pdf`, listed in `contracts.csv`.
    - `receipts/`: receipts worth keeping (warranties, deductible expenses), listed in `receipts.csv`.
- `data/`: generated; safe to delete and rebuild. `finance.db` (SQLite), `transactions.csv`, `report.md`,
  `summary.md`, `dashboard.html`.
- `config.json`: `home_currency` (all totals are converted to it).
- `accounts.csv`: account registry (`id,institution,name,type,currency,identifiers,status,notes`).
  - `institution` must match the parser's `INSTITUTION`; `identifiers` (`;`-separated: card last 4, IBAN tail,
    Wise balance id) map a document to an account. Ingest refuses documents for unknown accounts.
  - `type`: `current`, `savings`, `cash`, `investment`, `pension` (assets) or `credit_card`, `loan`, `mortgage`,
    `other_debt` (debts).
  - `status`: `active`, `closed`, `pass-through` (money only routed through it) or `unused`.
    Non-active accounts don't need files.
- `balances.csv`: balances no document shows (`account_id,date,balance,note`, negative = owed), e.g. a loan, a pension,
  cash, or a balance read from an app. The newest of this and the latest statement/export wins.
- `loans.csv`: loan terms (rate as a fraction, e.g. 0.069; monthly payment; final date). The report projects
  payments and interest left from these and the latest balance.
- `lent.csv`: money lent to people that no transaction shows (`person,date,amount,note`).
- `budget.csv`: `line,monthly,categories,note`. `categories` is `;`-separated category names, or prefixes ending in
  `:` (e.g. `Eating out;Food delivery` or `Housing:`). Spending outside every line shows as "Not in the budget".
- `deadlines.csv`: dated things that matter (`date,item,area,done,note`): tax filing and payment dates, renewals,
  MOT, passport expiry. Put anything in `done` once it's done. The report shows the next 90 days and overdue ones.
- `contracts.csv`: tenancy, phone, energy, insurance, loans, subscriptions with terms
  (`file,type,counterparty,signed,start,end,cost,cost_period,currency,notice,notice_days,renewal,category,note`).
  `end` and `notice_days` put "last day to give notice" into Coming up; `category` is the ledger category its
  payments fall under, so charges can be checked against the agreed price.
- `receipts.csv`: `file,date,vendor,item,total,currency,tax,transaction_id,note`.
- `fx_rates.csv`: `month,currency,rate` (1 unit of currency = rate in the home currency) for accounts in another
  currency. The nearest month is used when one is missing.
- `rules.csv`: categorisation. `pattern` (case-insensitive regex over `description details`), `category`,
  optional `account_id`, optional `amount` (exact signed amount, to tell apart charges from the same merchant).
  First match wins: put specific rules above general ones.
- `overrides.csv`: per-transaction `id,category,note`. Ids are a hash of the transaction, so they survive rebuilds.
- `snapshots.csv`: written by `dashboard.py` once a day (cash, each debt, money owed to me) so the next refresh
  can say what moved.
- `scripts/parsers/`: one module per document format. Any module there (except `common.py` and names starting
  with `_`) is picked up automatically; see `scripts/parsers/__init__.py` for the contract and `_template.py`.

## Conventions

- Amounts are from my point of view: negative = money out / more owed. Credit card and loan balances are negative.
- Categories are `Group: detail` (e.g. `Housing: rent`, `Transport: fuel`). Groups make the summary and dashboard;
  keep the list short and consistent. Special groups:
  - `Income: <source>` (salary, side work, refunds that aren't returns, interest).
  - `Transfer: <what>` for money between my own accounts, including paying off a credit card. A transfer appears in
    both accounts and is left out of income and spending.
  - `Lent: <name>` both ways (paying for someone is out, their repayment is in). The report nets them.
  - `Tax: <what>` for tax payments; `Debt: interest & fees` for interest and card fees.
- Suggested starting groups: Housing, Bills, Groceries, Eating out, Transport, Shopping, Health, Personal care,
  Entertainment, Subscriptions, Travel, Gifts, Kids/Pets (if any), Insurance, Tax, Debt, Cash, Other.
- Transactions are not deduplicated across accounts; overlapping exports of the same account are merged by
  `build.py`, so never hand-trim files.
- Every parser must be checked against the document's own totals: statement opening + transactions = closing, or
  the running balance chains row to row. A new parser isn't done until `report.md` shows no breaks.
- Never edit files in `sources/`. Corrections go in `overrides.csv`, `rules.csv` or `balances.csv`.
- Ask rather than guess when a transaction can't be placed (an unnamed transfer, a payment to a person).

## Adding a new source type

Use the `new-parser` skill: look at the document (`pdftotext -layout`, or the CSV header), write
`scripts/parsers/<name>.py` from `_template.py`, add the account to `accounts.csv`, rebuild, and confirm it
reconciles.

## Backups and privacy

The documents contain account numbers, card numbers and my address. Keep everything local: don't publish, upload
or share raw transactions or identifiers unless I ask. Card numbers are masked to the last four digits.
People's names (in `Lent:` categories and `lent.csv`) stay out of anything shared.

`sources/` is the record and isn't in git by default (see `.gitignore`), so back up the folder (Time Machine,
iCloud Drive, an encrypted drive). If I choose to push the repo to a **private** remote, remove `sources/` from
`.gitignore` then, and never before.
