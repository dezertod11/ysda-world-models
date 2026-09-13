"""Download the curated public PDFs and record integrity and extraction results.

Run with a Python environment containing requests and pypdf. Existing valid
PDFs are reused; extracted text is a local, ignored reading aid.
"""

import hashlib
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent


def main():
    papers = json.loads((ROOT / "papers.json").read_text())["papers"]
    text_dir = ROOT / ".text"
    text_dir.mkdir(exist_ok=True)
    manifest_path = ROOT / "download_manifest.json"
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    previous = {row["id"]: row for row in previous}
    rows = []
    with requests.Session() as session:
        for paper in papers:
            path = ROOT / paper["file"]
            row = {"id": paper["id"], "file": paper["file"], "requested_url": paper["pdf"]}
            try:
                if path.exists():
                    data = path.read_bytes()
                    row.update({k: v for k, v in previous.get(paper["id"], {}).items()
                                if k in {"downloaded_at_utc", "resolved_url"}})
                else:
                    for attempt in range(3):
                        try:
                            response = session.get(paper["pdf"], timeout=(15, 90))
                            response.raise_for_status()
                            data = response.content
                            if not data.startswith(b"%PDF-"):
                                raise ValueError("Response is not a PDF")
                            PdfReader(io.BytesIO(data))
                            temp = path.with_suffix(".part")
                            temp.write_bytes(data)
                            temp.replace(path)
                            row["resolved_url"] = response.url
                            row["downloaded_at_utc"] = datetime.now(timezone.utc).isoformat()
                            break
                        except (requests.RequestException, ValueError):
                            if attempt == 2:
                                raise
                            time.sleep(3 * (attempt + 1))
                if not data.startswith(b"%PDF-"):
                    raise ValueError("Existing file is not a PDF; retained for inspection")
                reader = PdfReader(io.BytesIO(data))
                pages = [page.extract_text() or "" for page in reader.pages]
                text = "\n".join(f"\n--- PDF PAGE {i + 1} ---\n{p}" for i, p in enumerate(pages))
                if not pages or len(text.strip()) < 500:
                    raise ValueError("PDF has insufficient extractable text")
                (text_dir / (paper["id"] + ".txt")).write_text(text, encoding="utf-8")
                row.update(status="ok", bytes=len(data), pages=len(pages),
                           sha256=hashlib.sha256(data).hexdigest(),
                           pdf_title=str((reader.metadata or {}).get("/Title", "")),
                           checked_at_utc=datetime.now(timezone.utc).isoformat())
                print(f'{paper["id"]}: {len(pages)} pages, {len(data) / 2**20:.2f} MiB', flush=True)
            except Exception as error:
                row.update(status="error", error=str(error))
                print(f'{paper["id"]}: ERROR {error}', flush=True)
            rows.append(row)
            manifest_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    failed = [row["id"] for row in rows if row["status"] != "ok"]
    print(f"Completed {len(rows) - len(failed)}/{len(papers)}; failed={failed}", flush=True)
    return bool(failed)


if __name__ == "__main__":
    raise SystemExit(main())
