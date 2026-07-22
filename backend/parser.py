"""
parser.py — extract raw text + metadata from heterogeneous document files.

Delegates format-specific extraction to doc_formats.py, then applies
metadata field extractors common across all document types.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from doc_formats import extract_text, scan_directory, supported_extensions


@dataclass
class ParsedDocument:
    doc_id:      str
    doc_type:    str
    facility:    str
    asset_hint:  str
    doc_date:    Optional[str]
    source_path: str
    raw_text:    str
    word_count:  int = field(init=False)
    format_type: str = "txt"      # pdf | spreadsheet | email | ocr | pid | …
    extra_meta:  dict = field(default_factory=dict)

    def __post_init__(self):
        self.word_count = len(self.raw_text.split())


_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

_TYPE_MAP = [
    ("Maintenance Log",    "maintenance_log"),
    ("Shift Log",          "shift_log"),
    ("OEM Manual",         "oem_manual"),
    ("Permit to Work",     "permit_to_work"),
    ("Environmental",      "permit_environmental"),
    ("Safety Inspection",  "audit_report"),
    ("Minor Incident",     "incident_report"),
    ("Quality Control",    "qc_report"),
    ("Work Order",         "work_order"),
    ("P&ID",               "pid_drawing"),
    ("Piping",             "pid_drawing"),
]

_FACILITY_FROM_PREFIX = {
    "LGP": "Horizon Chemicals Pvt. Ltd., Eastport Industrial Zone",
    "VSP": "Bharat Steel Works Ltd.",
}


def _field(text: str, *keys: str) -> Optional[str]:
    for key in keys:
        m = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _clean_type(raw: str, format_type: str = "txt") -> str:
    if format_type == "pid":
        return "pid_drawing"
    if format_type == "email":
        return "email_archive"
    if format_type == "spreadsheet":
        return "spreadsheet_record"
    if format_type == "pdf":
        return "pdf_document"
    raw = raw.strip()
    for keyword, slug in _TYPE_MAP:
        if keyword.lower() in raw.lower():
            return slug
    return "document"


def _doc_id_from_path(path: Path, text: str) -> str:
    found = _field(text, "DOCUMENT ID", "DOC ID", "Document ID")
    if found:
        return found.strip()
    # Derive from filename: LGP_001_... → LGP-001 style or keep stem
    stem = path.stem.replace("_", "-")
    m = re.match(r"([A-Z]{2,4})-(\d{3,4})", stem.upper())
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return path.stem


def parse_file(path: str | Path) -> ParsedDocument:
    path = Path(path)
    extracted = extract_text(path)
    raw_text = extracted.raw_text

    if not raw_text.strip():
        print(f"[parser] WARN: empty extraction from {path.name}")

    doc_id = _doc_id_from_path(path, raw_text)
    raw_type = _field(raw_text, "TYPE") or ""
    doc_type = _clean_type(raw_type, extracted.format_type)

    facility = _field(raw_text, "FACILITY") or ""
    if not facility:
        prefix = doc_id.split("-")[0] if "-" in doc_id else doc_id[:3]
        facility = _FACILITY_FROM_PREFIX.get(prefix.upper(), "unknown")

    asset_hint = (
        _field(raw_text, "ASSET")
        or _field(raw_text, "APPLICABLE ASSET")
        or ""
    )
    # P&ID tag inventory fallback
    if not asset_hint and extracted.metadata.get("pid_tags"):
        asset_hint = ", ".join(extracted.metadata["pid_tags"][:5])

    date_raw = (
        _field(raw_text, "DATE")
        or _field(raw_text, "DATE ISSUED")
        or _field(raw_text, "VALID FROM")
        or _field(raw_text, "PERIOD")
        or extracted.metadata.get("email", {}).get("date", "")
        or ""
    )
    dm = _DATE_RE.search(str(date_raw))
    doc_date = dm.group(1) if dm else None

    return ParsedDocument(
        doc_id=doc_id,
        doc_type=doc_type,
        facility=facility,
        asset_hint=asset_hint,
        doc_date=doc_date,
        source_path=str(path.resolve()),
        raw_text=raw_text,
        format_type=extracted.format_type,
        extra_meta=extracted.metadata,
    )


def parse_directory(docs_dir: str | Path) -> list[ParsedDocument]:
    docs_dir = Path(docs_dir)
    results = []
    files = scan_directory(docs_dir)
    if not files:
        # Legacy: flat *.txt only
        files = sorted(docs_dir.glob("*.txt"))

    for p in files:
        try:
            results.append(parse_file(p))
        except Exception as e:
            print(f"[parser] WARN: could not parse {p.name}: {e}")

    fmts = {}
    for d in results:
        fmts[d.format_type] = fmts.get(d.format_type, 0) + 1
    fmt_summary = ", ".join(f"{k}={v}" for k, v in sorted(fmts.items()))
    print(f"[parser] Parsed {len(results)} documents ({fmt_summary}) from {docs_dir}")
    return results


if __name__ == "__main__":
    import sys
    docs = parse_directory(sys.argv[1] if len(sys.argv) > 1 else "../data/synthetic_docs")
    for d in docs:
        print(f"  {d.doc_id:20s}  {d.doc_type:22s}  [{d.format_type:12s}]  {d.doc_date}  {d.word_count}w")
