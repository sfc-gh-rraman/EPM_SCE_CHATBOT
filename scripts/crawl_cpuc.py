"""Crawl CPUC SCE PPA listings, build manifest, download all PDFs."""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, unquote

import requests

ROOT = "https://files.cpuc.ca.gov/RPS_PPAs/SCE%20Public%20PPAs/"
OUT_DIR = Path("/Users/rraman/Documents/epm_sce_chatbot/data/sce_real")
PDF_DIR = OUT_DIR / "pdfs"
PDF_DIR.mkdir(parents=True, exist_ok=True)
TOP_DIRS = ["1985-1989", "2002-2006", "2007-2012", "2013", "2013-2015", "2016-2017"]

LINK_RE = re.compile(r'<a href="([^"]+)">([^<]+)</a>', re.IGNORECASE)
SIZE_RE = re.compile(r'(\d+)\s+<a', re.IGNORECASE)


def list_dir(url: str, session: requests.Session, depth: int = 0):
    """Return (subdirs[list of urls], files[list of (url, name, size)])."""
    if depth > 4:
        return [], []
    try:
        r = session.get(url, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"  ! fetch fail {url}: {e}", file=sys.stderr)
        return [], []
    html = r.text
    subdirs, files = [], []
    # IIS listing format:  <pre>... date dir <a href="x/">x</a><br> ... date size <a href="f">f</a>...
    for m in re.finditer(
        r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s+(?:AM|PM))\s+(&lt;dir&gt;|<dir>|\d+)\s+<a\s+href="([^"]+)"\s*>([^<]+)</a>',
        html, re.IGNORECASE,
    ):
        _, size_or_dir, href, name = m.groups()
        if href in ("/", "../"):
            continue
        full = urljoin(url, href)
        is_dir = "dir" in size_or_dir.lower()
        if is_dir:
            subdirs.append(full)
        else:
            try:
                size = int(size_or_dir)
            except ValueError:
                size = 0
            if name.lower().endswith(".pdf"):
                files.append((full, unquote(name), size))
    return subdirs, files


def crawl(top_dir: str, session: requests.Session):
    """BFS-walk one top-level directory, collect all PDFs."""
    queue = [urljoin(ROOT, top_dir + "/")]
    files = []
    while queue:
        next_q = []
        # parallelize listing fetches
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(list_dir, u, session): u for u in queue}
            for fut in as_completed(futures):
                subs, fs = fut.result()
                next_q.extend(subs)
                files.extend(fs)
        queue = next_q
    return files


def main():
    sess = requests.Session()
    manifest = {"files": []}

    print("Crawling top-level directories...")
    for top in TOP_DIRS:
        t0 = time.time()
        files = crawl(top, sess)
        for url, name, size in files:
            manifest["files"].append({
                "url": url,
                "filename": name,
                "size_bytes": size,
                "year_bucket": top,
            })
        print(f"  {top}: {len(files)} PDFs ({time.time()-t0:.1f}s)")

    total = len(manifest["files"])
    total_mb = sum(f["size_bytes"] for f in manifest["files"]) / 1e6
    print(f"\nTotal: {total} PDFs, {total_mb:.1f} MB")

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
