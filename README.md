# Personal finances, with Claude

A starter kit for keeping your whole financial life in one place on your own computer, built from your own bank
statements and kept up to date with Claude Code. It gives you:

- one ledger of every transaction from every account, checked against each statement's own totals so you know
  nothing is missing;
- where your money goes, by month and year, and a budget to compare against;
- what you owe (cards, loans), how long it'll take to clear, and which to pay first;
- recurring payments, so forgotten subscriptions and price rises stand out;
- contracts, notice periods, tax and renewal deadlines, so nothing sneaks up on you;
- money people owe you;
- a one-page dashboard.

Nothing leaves your computer. Your documents stay in `sources/`, which isn't committed to git.

## Keeping your copy private, and getting updates

Once you start using it, your copy holds your finances (accounts, rules, budget, debts). **Never push it back to
the repo you cloned it from.** Set it up like this after cloning:

```sh
git remote rename origin upstream          # the shared starter kit: pull updates from here, never push
git remote set-url --push upstream no-push # makes an accidental push fail
# optional: back up your own copy to a PRIVATE repo of your own
# git remote add origin git@github.com:<you>/<your-private-repo>.git
```

To get improvements to the scripts and skills later: `git pull upstream main`. Your own data is in the CSVs and
`sources/`, so updates rarely clash with it. If `CLAUDE.md` clashes, keep your "About me" section.

## Getting started

1. Install [Claude Code](https://claude.com/claude-code), plus Python 3 and poppler (for reading PDFs). On a Mac:
   `brew install python poppler`.
2. Put this folder somewhere that's backed up, `cd` into it, and run `claude`.
3. Say **"set this up"**. Claude interviews you about your accounts, bills, debts and goals, tells you which
   statements to download, and builds the readers ("parsers") for your banks as the files come in.

After that, the rhythm is:

- **Monthly:** download the new statements into `inbox/` and say "I've added statements", then "how did I do
  this month?".
- **Any time:** "refresh the dashboard", "which debt should I pay first?", "when does my phone contract end?",
  "how much did I spend on eating out this year?", "here's my new tenancy agreement".

## What's in here

- `CLAUDE.md`: how the project works, for Claude (and you). Claude fills in the "About me" part during setup.
- `.claude/skills/`: step-by-step routines Claude follows: `setup`, `add-statements`, `new-parser`,
  `month-review`, `dashboard`, `add-contract`, `debt-plan`.
- `scripts/`: the Python that files documents, checks them and builds the reports. Plain Python, no extra
  packages to install.
- `*.csv`: your own tables (accounts, categorisation rules, budget, loans, deadlines, contracts). They start empty.
