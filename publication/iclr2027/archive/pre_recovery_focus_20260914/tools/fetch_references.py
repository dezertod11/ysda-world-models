"""Build a private, verifiable reading collection from its public-source manifest."""

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
REFERENCES = ROOT / "reference_papers"


def validate(path):
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("Response is not a PDF")
    reader = PdfReader(path)
    if not reader.pages:
        raise ValueError("Empty PDF")
    return reader


def main():
    manifest = json.loads((REFERENCES / "manifest.json").read_text())
    pdf_dir, text_dir = REFERENCES / "pdfs", REFERENCES / "text"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    report_path = REFERENCES / "download_report.json"
    previous = json.loads(report_path.read_text()) if report_path.exists() else {"papers": []}
    previous = {row["id"]: row for row in previous["papers"]}
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "papers": []}
    session = requests.Session()
    session.headers["User-Agent"] = "WorldModelPublicationReadingCollection/1.0"
    for paper in manifest["papers"]:
        target = pdf_dir / f'{paper["id"]}.pdf'
        row = {"id": paper["id"], "title": paper["title"], "page": paper["page"]}
        try:
            if target.exists():
                try:
                    validate(target)
                except Exception:
                    target.unlink()
            if target.exists():
                validate(target)
                row["acquired_from"] = previous.get(paper["id"], {}).get("acquired_from", paper.get("local_source", "existing local PDF"))
                if previous.get(paper["id"], {}).get("version_note"):
                    row["version_note"] = previous[paper["id"]]["version_note"]
            else:
                local = PROJECT / paper.get("local_source", "__no_local_source__")
                if local.is_file():
                    validate(local)
                    shutil.copyfile(local, target)
                    row["acquired_from"] = str(local.relative_to(PROJECT))
                else:
                    errors = []
                    urls = [paper["pdf_url"]]
                    if paper.get("fallback_url"):
                        urls.append(paper["fallback_url"])
                    for url in urls:
                        try:
                            with session.get(url, timeout=(20, 180), stream=True) as response:
                                response.raise_for_status()
                                with tempfile.NamedTemporaryFile(dir=pdf_dir, suffix=".part", delete=False) as stream:
                                    temporary = Path(stream.name)
                                    try:
                                        for chunk in response.iter_content(1024 * 1024):
                                            stream.write(chunk)
                                    except Exception:
                                        temporary.unlink(missing_ok=True)
                                        raise
                            try:
                                validate(temporary)
                                temporary.replace(target)
                            finally:
                                temporary.unlink(missing_ok=True)
                            row["acquired_from"] = url
                            if url == paper.get("fallback_url"):
                                row["version_note"] = paper["fallback_note"]
                            break
                        except Exception as exc:
                            errors.append(f"{url}: {exc}")
                    else:
                        raise RuntimeError("; ".join(errors))
            reader = validate(target)
            row.update(status="ok", pages=len(reader.pages), bytes=target.stat().st_size,
                       sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                       pdf=f"pdfs/{target.name}", metadata_title=str((reader.metadata or {}).get("/Title", "")))
            text_path = text_dir / f'{paper["id"]}.txt'
            if not text_path.exists() or previous.get(paper["id"], {}).get("sha256") != row["sha256"]:
                with text_path.open("w", encoding="utf-8") as output:
                    for index, page in enumerate(reader.pages, 1):
                        output.write(f"\n--- PDF page {index} ---\n{page.extract_text() or ''}\n")
            print(f'OK {paper["id"]}: {len(reader.pages)} pages', flush=True)
        except Exception as exc:
            row.update(status="error", error=str(exc))
            print(f'ERROR {paper["id"]}: {exc}', flush=True)
        report["papers"].append(row)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if any(row["status"] != "ok" for row in report["papers"]):
        raise SystemExit("Some references could not be acquired; see download_report.json")


if __name__ == "__main__":
    main()
