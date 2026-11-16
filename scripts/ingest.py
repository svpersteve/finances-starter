"""Sort new files from inbox/ (or the project root) into sources/<account>/ under a consistent name.

Nothing is deleted: exact or same-content copies go to sources/_duplicates/, and files no parser
recognises are left where they are and reported.
"""
import csv
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

from parsers import all_parsers
from parsers.common import pdf_text

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
SOURCES = ROOT / "sources"
DUPLICATES = SOURCES / "_duplicates"
ARCHIVES = SOURCES / "_archives"
INGESTIBLE = {".pdf", ".csv", ".xlsx", ".xls", ".ofx", ".qif", ".zip"}


def project_files():
    """CSVs in the root are the project's own tables, never statements."""
    return {p.name for p in ROOT.glob("*.csv")}


def load_config():
    path = ROOT / "config.json"
    return json.loads(path.read_text()) if path.exists() else {"home_currency": "GBP"}


def load_accounts():
    with open(ROOT / "accounts.csv") as f:
        return list(csv.DictReader(f))


def account_for(identifier, institution, accounts):
    for a in accounts:
        if a["institution"] == institution and str(identifier) in a["identifiers"].split(";"):
            return a["id"]
    return None


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def same_content(a, b):
    if sha256(a) == sha256(b):
        return True
    # Re-downloaded PDFs differ only in embedded metadata, so compare their text instead.
    return a.suffix.lower() == b.suffix.lower() == ".pdf" and pdf_text(a) == pdf_text(b)


def read_document(path):
    """Find the parser for a file. Returns (parser module or None, PDF text or None)."""
    suffix = path.suffix.lower()
    text = pdf_text(path) if suffix == ".pdf" else None
    for parser in all_parsers():
        if suffix in parser.FILE_TYPES:
            try:
                if parser.detect(path, text):
                    return parser, text
            except Exception:  # a parser choking on someone else's file just means "not mine"
                continue
    return None, text


def canonical_name(result, path):
    suffix = path.suffix.lower()
    statement = result.get("statement")
    if statement:
        return f"{statement['statement_date']}{suffix}"
    txns = result["transactions"]
    if txns:
        return f"{txns[0]['date']}_{txns[-1]['date']}{suffix}"
    return f"{result.get('name') or 'empty_' + sha256(path)[:8]}{suffix}"


def classify(path, accounts):
    """Return (account_id, canonical file name) or (None, reason)."""
    parser, text = read_document(path)
    if not parser:
        return None, "not recognised by any parser (use the new-parser skill)"
    result = parser.parse(path, text)
    account = account_for(result["identifier"], parser.INSTITUTION, accounts)
    if not account:
        return None, f"{parser.INSTITUTION} account '{result['identifier']}' is not in accounts.csv"
    return account, canonical_name(result, path)


def unique_path(path):
    n, candidate = 2, path
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
        n += 1
    return candidate


def unpack_zips(candidates):
    """Extract zips into the inbox so their contents are ingested like any other file."""
    out = []
    for path in candidates:
        if path.suffix.lower() != ".zip":
            out.append(path)
            continue
        INBOX.mkdir(exist_ok=True)
        ARCHIVES.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path) as z:
            for member in z.namelist():
                name = Path(member).name
                if member.endswith("/") or name.startswith("."):
                    continue
                target = INBOX / name
                if not target.exists():
                    target.write_bytes(z.read(member))
                    out.append(target)
        shutil.move(str(path), str(unique_path(ARCHIVES / path.name)))
        print(f"  unzipped {path.name} -> inbox/ (zip kept in sources/_archives/)")
    return out


def candidates():
    files = [p for p in INBOX.glob("*") if p.is_file()] if INBOX.exists() else []
    skip = project_files()
    files += [p for p in ROOT.glob("*") if p.is_file() and p.suffix.lower() in INGESTIBLE and p.name not in skip]
    return sorted(p for p in files if not p.name.startswith("."))


def ingest():
    accounts = load_accounts()
    filed, duplicates, unrecognised = 0, [], []
    for path in unpack_zips(candidates()):
        account, name = classify(path, accounts)
        if not account:
            unrecognised.append((path, name))
            continue
        target = SOURCES / account / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if same_content(path, target):
                DUPLICATES.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(unique_path(DUPLICATES / path.name)))
                duplicates.append((path.name, f"{account}/{name}"))
                continue
            target = unique_path(target)
        shutil.move(str(path), str(target))
        filed += 1

    print(f"Ingest: filed {filed} file(s) into sources/")
    for name, of in duplicates:
        print(f"  duplicate: {name} (same as {of}) -> sources/_duplicates/")
    for path, reason in unrecognised:
        print(f"  NOT FILED: {path.relative_to(ROOT)} — {reason}")
    return unrecognised


if __name__ == "__main__":
    sys.exit(1 if ingest() else 0)
