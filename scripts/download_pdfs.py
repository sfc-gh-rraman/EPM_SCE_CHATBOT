"""Download all PDFs from manifest.json in parallel."""
from __future__ import annotations
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

OUT = Path("/Users/rraman/Documents/epm_sce_chatbot/data/sce_real")
PDF_DIR = OUT / "pdfs"
PDF_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST = OUT / "manifest.json"

SAFE = lambda s: s.replace("/", "_").replace("\\", "_")


def download_one(item, session):
    fname = SAFE(item["filename"])
    # year_bucket prefix to avoid collisions across years
    out = PDF_DIR / f"{item['year_bucket']}__{fname}"
    if out.exists() and out.stat().st_size == item["size_bytes"] and item["size_bytes"] > 0:
        return out, 0, "skip"
    try:
        r = session.get(item["url"], timeout=120, stream=True)
        r.raise_for_status()
        with open(out, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk)
        return out, out.stat().st_size, "ok"
    except Exception as e:
        return out, 0, f"fail: {e}"


def main():
    items = json.loads(MANIFEST.read_text())["files"]
    print(f"Downloading {len(items)} PDFs...")
    sess = requests.Session()
    sess.headers["User-Agent"] = "sce-epm-chatbot/1.0"
    t0 = time.time()
    ok = fail = skip = 0
    bytes_total = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(download_one, it, sess): it for it in items}
        for i, fut in enumerate(as_completed(futs), 1):
            out, sz, status = fut.result()
            if status == "ok":
                ok += 1; bytes_total += sz
            elif status == "skip":
                skip += 1
            else:
                fail += 1
                print(f"  [{i}/{len(items)}] FAIL {out.name}: {status}", file=sys.stderr)
            if i % 20 == 0:
                print(f"  [{i}/{len(items)}] ok={ok} skip={skip} fail={fail} ({(time.time()-t0):.0f}s)")
    print(f"\nDone: ok={ok} skip={skip} fail={fail} in {time.time()-t0:.0f}s, {bytes_total/1e6:.1f} MB downloaded")


if __name__ == "__main__":
    main()
