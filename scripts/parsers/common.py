"""Helpers shared by parsers."""
import html
import re
import subprocess
from datetime import date, datetime
from decimal import Decimal

MONTHS = {m: i for i, m in enumerate(
    ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY",
     "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], start=1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})


def pdf_text(path):
    """Text of a PDF with its layout kept (needs poppler: `brew install poppler`)."""
    return subprocess.run(["pdftotext", "-layout", str(path), "-"],
                          capture_output=True, text=True, check=True).stdout


def money(s):
    """'£1,234.56', '-$5.00', '1.234,56 €' (continental) -> Decimal. A trailing 'CR' or '-' is not handled here."""
    s = re.sub(r"[^\d,.\-]", "", s.strip())
    if re.fullmatch(r"-?[\d.]*,\d{1,2}", s):  # comma as the decimal point
        s = s.replace(".", "").replace(",", ".")
    return Decimal(s.replace(",", ""))


def parse_date(s, fmt):
    return datetime.strptime(s.strip(), fmt).date()


def day_month_with_year(s, statement_date):
    """'02 JUNE' or '02 Jun' on a statement dated 2025-06-08 -> 2025-06-02 (rolls back a year across January)."""
    day, month = s.split()
    m = MONTHS[month.upper()]
    year = statement_date.year - (1 if m > statement_date.month else 0)
    return date(year, m, int(day))


def mask_card_numbers(s):
    """Keep only the last four digits of any long card or account number."""
    return re.sub(r"\b\d{8,15}(\d{4})\b", r"****\1", s) if s else s


def squash(s):
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()
