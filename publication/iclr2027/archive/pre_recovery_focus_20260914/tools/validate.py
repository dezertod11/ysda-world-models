"""Offline checks for reading PDFs, artifact links, sources, and built documents."""

import hashlib
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import unquote

from markdown_it import MarkdownIt
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]


def main():
    assert not any(path.is_symlink() for path in ROOT.rglob("*")), "Publication must be self-contained on D:"
    original = ROOT / "templates/user_original.tex"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == "aa4a5af06b2bf107346f432bd32ca4ef22f7480b57d855586ab0959f4dc37696"
    manifest = json.loads((ROOT / "reference_papers/manifest.json").read_text())
    report = json.loads((ROOT / "reference_papers/download_report.json").read_text())
    assert {p["id"] for p in manifest["papers"]} == {p["id"] for p in report["papers"]}
    for paper in report["papers"]:
        assert paper["status"] == "ok", paper
        path = ROOT / "reference_papers" / paper["pdf"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == paper["sha256"], path
        assert len(PdfReader(path).pages) == paper["pages"] > 0
    markdown = MarkdownIt()
    for path in ROOT.rglob("*.md"):
        relative = path.relative_to(ROOT)
        # Downloaded source documents can contain links relative to their websites.
        if relative.parts[0] in {".tools", "build", "templates"} or relative.parts[:2] == ("reference_papers", "text"):
            continue
        links = [child.attrGet("href" if child.type == "link_open" else "src")
                 for token in markdown.parse(path.read_text())
                 for child in (token.children or []) if child.type in {"link_open", "image"}]
        for target in links:
            if target.startswith(("https://", "http://", "#")):
                continue
            resolved = path.parent / unquote(target.split("#")[0])
            assert resolved.exists(), f"Broken link in {path.relative_to(ROOT)}: {target}"
    source = (ROOT / "manuscript/main.tex").read_text()
    bib = (ROOT / "manuscript/references.bib").read_text()
    entries = re.findall(r"@\w+\{([^,]+),", bib)
    assert len(entries) == len(set(entries)), "Duplicate BibTeX keys"
    cites = {key.strip() for group in re.findall(r"\\cite\w*\{([^}]+)\}", source)
             for key in group.split(",")}
    assert cites <= set(entries), f"Missing citations: {cites - set(entries)}"
    provenance = json.loads((ROOT / "manuscript/tables/provenance.json").read_text())
    assert provenance["evidence_snapshot"] == "2026-09-14"
    for item in provenance["inputs"]:
        path = ROOT.parents[1] / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], path
    assert len(provenance["inputs"]) == 13
    main_end = re.search(r"\\newlabel\{sec:main_end\}\{\{[^}]+\}\{(\d+)\}",
                         (ROOT / "build/iclr2027.aux").read_text())
    assert main_end and int(main_end.group(1)) <= 9, "ICLR main-text page budget exceeded"
    for name in ["main", "iclr2027"]:
        reader = PdfReader(ROOT / "build" / f"{name}.pdf")
        pages = [page.extract_text() or "" for page in reader.pages]
        assert all(page.strip() for page in pages), f"Blank PDF page: {name}"
        assert "54.77" in "\n".join(pages), f"Missing main result in {name}"
        compact_text = re.sub(r"\s+", "", "\n".join(pages)).upper()
        for expected in ["62.22", "83.85", "0.18948", "AIUSE", "0.650", "41/64", "39.06"]:
            assert expected in compact_text, f"Missing latest evidence: {expected}"
        log = (ROOT / "build" / f"{name}.log").read_text(errors="replace")
        assert "undefined" not in log.lower(), f"Undefined references in {name}"
        assert "Overfull" not in log, f"Overflow in {name}"
    with zipfile.ZipFile(ROOT / "build/iclr2027_sources.zip") as bundle:
        assert bundle.testzip() is None
        required = {"main.tex", "iclr2027.tex", "references.bib", "README.txt",
                    "iclr2027_conference.sty", "iclr2027_conference.bst",
                    "tables/decoder_h16.tex", "tables/decoder_h8.tex", "tables/observation_contract.tex",
                    "tables/consensus_scores.tex", "figures/mechanism_audit.pdf"}
        assert required <= set(bundle.namelist())
        assert all(not name.startswith("/") and ".." not in Path(name).parts for name in bundle.namelist())
        assert bundle.read("main.tex") == (ROOT / "manuscript/main.tex").read_bytes()
    for name in ["FULL_RESEARCH_REPORT.md", "RESEARCH_SUMMARY.md"]:
        content = (ROOT / name).read_text()
        assert content.count("$$") % 2 == 0, f"Unbalanced display math: {name}"
    result = {"reference_pdfs": len(report["papers"]), "bib_entries": len(entries),
              "compiled_documents": 2, "local_links": "ok", "pdf_hashes": "ok",
              "undefined_references": 0, "overfull_boxes": 0,
              "audited_table_inputs": len(provenance["inputs"]),
              "iclr_main_end_page": int(main_end.group(1)), "portable_sources": "ok"}
    result["deliverables"] = []
    for name in ["FULL_RESEARCH_REPORT.md", "RESEARCH_SUMMARY.md", "manuscript/main.tex",
                 "build/iclr2027.pdf", "build/iclr2027_sources.zip"]:
        path = ROOT / name
        row = {"file": name, "bytes": path.stat().st_size,
               "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if path.suffix in {".md", ".tex"}:
            row["words"] = len(path.read_text().split())
        result["deliverables"].append(row)
    (ROOT / "build/validation_report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
