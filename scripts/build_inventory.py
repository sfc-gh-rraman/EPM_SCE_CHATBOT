"""
Consolidate all real SCE PPA PDFs (downloaded dirs + zip extract) into one
flat folder with normalized filenames + a metadata CSV/parquet.

Filename patterns observed:
  A. "{YYYY-MM-DD}, {Counterparty}, {DocType}.pdf"                         (modern)
  B. "Confidential - market sensitive pursuant to D.06-06-066_{ID} {rest}" (legacy)
  C. "{ID}-{Counterparty} - {DocType}-{YYYYMMDD}-{exec}.pdf"               (mixed)

Output:
  /data/sce_real/pdfs_consolidated/  (renamed files: {project_id}__{slug}.pdf)
  /data/sce_real/inventory.parquet   (one row per PDF with parsed fields)
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from datetime import date

import pandas as pd

ROOT = Path("/Users/rraman/Documents/epm_sce_chatbot/data/sce_real")
DST  = ROOT / "pdfs_consolidated"
DST.mkdir(parents=True, exist_ok=True)

CONFID = re.compile(
    r"Confidential\s*-\s*market sensitive pursuant to D\.06-06-066[_\s]*(\d{3,5})\s*[-_,]?\s*(.+?)\.pdf$",
    re.IGNORECASE,
)
ID_PREFIX = re.compile(r"^(\d{3,5})\s*[-_]\s*(.+?)\.pdf$", re.IGNORECASE)
DATE_RES = [
    re.compile(r"\b(\d{4})[-_/](\d{2})[-_/](\d{2})\b"),                # YYYY-MM-DD
    re.compile(r"\b(\d{2})[-_/](\d{2})[-_/](\d{2})\b"),                # MM-DD-YY
    re.compile(r"\b(\d{4})(\d{2})(\d{2})\b"),                          # YYYYMMDD
    re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b"),              # M/D/YYYY
]
DOC_TYPE_KEYWORDS = [
    ("AMENDMENT_AND_RESTATED", r"amend(?:ed|ment).*restate|restate.*amend"),
    ("RESTATEMENT",            r"\brestate(?:d|ment)\b"),
    ("AMENDMENT",              r"\bamend(?:ed|ment)(?:\s*(?:no\.?|number|#)?\s*\d+)?\b"),
    ("SIDE_LETTER",            r"\bside\s*(?:letter|agreement)\b"),
    ("LETTER_AGREEMENT",       r"\bletter\s*ag(?:r|m)\w*\b"),
    ("NOTICE",                 r"\bnotice\b"),
    ("CONSENT",                r"\bconsent\b"),
    ("ASSIGNMENT",             r"\bassign(?:ment)?\b"),
    ("PPA",                    r"\b(?:ppa|ppsa|power\s*purchase)\b"),
    ("AGREEMENT",              r"\bagreement\b"),
]


def parse_filename(fname: str, parent: str = "") -> dict:
    """Extract project_id, counterparty, exec_date, doc_type from filename."""
    base = fname
    out = {
        "filename":     fname,
        "project_id":   None,
        "counterparty": None,
        "exec_date":    None,
        "doc_type":     None,
        "parent_dir":   parent,
    }

    body = base[:-4] if base.lower().endswith(".pdf") else base
    body = body.replace("&amp;", "&").replace("&#x7b;", "{").replace("&#x7d;", "}")

    # Project ID + body (legacy "Confidential ..." prefix or "{id}-..." prefix)
    m = CONFID.match(base)
    if m:
        out["project_id"], rest = m.group(1), m.group(2)
        body = rest
    else:
        m2 = ID_PREFIX.match(base)
        if m2:
            out["project_id"], body = m2.group(1), m2.group(2)
        else:
            # Project ID often appears as 4-digit number anywhere
            m3 = re.search(r"\b(\d{4,5})\b", base)
            if m3:
                out["project_id"] = m3.group(1)

    # Date
    for rx in DATE_RES:
        m = rx.search(body)
        if not m:
            continue
        a, b, c = m.groups()
        try:
            if len(a) == 4:                          # YYYY-?-?
                yr, mo, dy = int(a), int(b), int(c)
            elif len(c) == 4:                        # ?-?-YYYY
                if int(a) > 12:
                    yr, mo, dy = int(c), int(b), int(a)
                else:
                    yr, mo, dy = int(c), int(a), int(b)
            else:                                    # MM-DD-YY
                yr = 2000 + int(c) if int(c) < 70 else 1900 + int(c)
                mo, dy = int(a), int(b)
            if 1980 <= yr <= 2030 and 1 <= mo <= 12 and 1 <= dy <= 31:
                out["exec_date"] = date(yr, mo, dy).isoformat()
                break
        except ValueError:
            continue

    # Doc type
    body_lc = body.lower()
    for label, pat in DOC_TYPE_KEYWORDS:
        if re.search(pat, body_lc, re.IGNORECASE):
            out["doc_type"] = label
            break
    if not out["doc_type"]:
        out["doc_type"] = "OTHER"

    # Counterparty: prefer parent dir name when meaningful; else strip ID/date/doctype tokens
    if parent and parent not in ("zip_extract", "pdfs", "SCE Public PPAs"):
        out["counterparty"] = parent.strip()
    else:
        cp = body
        cp = re.sub(r"\d{4}[-_/]\d{2}[-_/]\d{2}", "", cp)
        cp = re.sub(r"\d{2}[-/]\d{2}[-/]\d{2,4}", "", cp)
        cp = re.sub(r"\b(amend\w*|restat\w*|ppa|ppsa|side\s*letter|notice|consent|assignment|executed|fully|final)\b", "", cp, flags=re.IGNORECASE)
        cp = re.sub(r"[,_\-]+", " ", cp).strip()
        out["counterparty"] = cp[:120] if cp else None

    return out


def slugify(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")[:80]


def main():
    rows = []
    seen = set()

    # 1. Files from manifest-driven download (data/sce_real/pdfs)
    for p in (ROOT / "pdfs").glob("*.pdf"):
        # filename was prefixed with year_bucket__
        m = re.match(r"^([\d-]+)__(.*)$", p.name)
        year_bucket = m.group(1) if m else ""
        clean = m.group(2) if m else p.name
        rows.append((p, clean, year_bucket, ""))

    # 2. Files from zip extract
    for p in (ROOT / "zip_extract").rglob("*.pdf"):
        parent = p.parent.name
        rows.append((p, p.name, "2017-2020", parent))

    print(f"Found {len(rows)} PDFs total")

    inventory = []
    for src, fname, year_bucket, parent in rows:
        meta = parse_filename(fname, parent)
        meta["year_bucket"] = year_bucket
        meta["src_path"]    = str(src)
        meta["size_bytes"]  = src.stat().st_size

        # Build normalized destination filename
        pid = meta["project_id"] or "NA"
        slug_parts = [pid, slugify(meta["counterparty"] or "unknown")]
        if meta["exec_date"]:
            slug_parts.append(meta["exec_date"])
        slug_parts.append(slugify(meta["doc_type"] or "DOC"))
        norm = "_".join(slug_parts) + ".pdf"
        # Avoid collisions
        i = 1
        while norm in seen:
            norm = "_".join(slug_parts) + f"_v{i}.pdf"
            i += 1
        seen.add(norm)
        meta["normalized_filename"] = norm

        dst = DST / norm
        if not dst.exists():
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                meta["copy_error"] = str(e)
        inventory.append(meta)

    df = pd.DataFrame(inventory)
    out_parquet = ROOT / "inventory.parquet"
    out_csv     = ROOT / "inventory.csv"
    df.to_parquet(out_parquet, index=False)
    df.to_csv(out_csv, index=False)

    print(f"\nWrote {len(df)} rows to:")
    print(f"  {out_parquet}")
    print(f"  {out_csv}")
    print(f"\nDoc type breakdown:")
    print(df["doc_type"].value_counts().to_string())
    print(f"\nDate parse rate: {df['exec_date'].notna().sum()}/{len(df)}")
    print(f"Counterparty rate: {df['counterparty'].notna().sum()}/{len(df)}")
    print(f"Project ID rate:   {df['project_id'].notna().sum()}/{len(df)}")
    print(f"\nFirst 5 rows:")
    print(df[["project_id","counterparty","exec_date","doc_type","normalized_filename"]].head().to_string(index=False))


if __name__ == "__main__":
    main()
