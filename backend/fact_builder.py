"""
fact_builder.py — persist Assets, Documents, Facts, and SensorReadings to SQLite.

All writes go through synchronous SQLAlchemy (using the sync sqlite driver) so
the ingestion pipeline can run as a plain script without an async event loop.
We use a separate sync engine here; the async engine in database.py is for
the FastAPI request handlers.
"""
import csv
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

# ── Sync engine (ingestion pipeline only) ─────────────────────────────────────
_DB_URL = os.getenv("DATABASE_URL", "sqlite:///./industrial_ki.db")
# Strip async prefix if someone accidentally puts aiosqlite in .env
_DB_URL = _DB_URL.replace("sqlite+aiosqlite", "sqlite")

sync_engine = create_engine(_DB_URL, echo=False,
                             connect_args={"check_same_thread": False})
SyncSession = sessionmaker(sync_engine)


def init_sync_db():
    """Create all tables (idempotent)."""
    from models import Base
    Base.metadata.create_all(sync_engine)
    print("[fact_builder] DB schema initialised")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_fact_id(doc_id: str, index: int) -> str:
    return f"{doc_id}-F{index:03d}"


def _parse_ts(ts_str: Optional[str]) -> Optional[datetime]:
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
                "%Y-%m-%d %H:%M:%S",  "%Y-%m-%d"):
        try:
            return datetime.strptime(ts_str[:19], fmt)
        except ValueError:
            continue
    return None


def _make_source_span(span_text: str, raw_text: str) -> str:
    """Return JSON {start, end, text} if span_text found in raw_text, else just {text}."""
    idx = raw_text.find(span_text)
    if idx >= 0:
        return json.dumps({"start": idx, "end": idx + len(span_text), "text": span_text})
    # Claude sometimes returns a slightly trimmed version — try stripped comparison
    stripped = span_text.strip()
    idx = raw_text.find(stripped)
    if idx >= 0:
        return json.dumps({"start": idx, "end": idx + len(stripped), "text": stripped})
    return json.dumps({"start": -1, "end": -1, "text": span_text})


# ── Upsert helpers ────────────────────────────────────────────────────────────

def upsert_asset(session: Session, asset_id: str, name: str, atype: str,
                 location: str, aliases: list[str]):
    from models import Asset
    existing = session.get(Asset, asset_id)
    if existing is None:
        a = Asset(asset_id=asset_id, name=name, type=atype, location=location)
        a.aliases = aliases
        session.add(a)
    else:
        # merge in any new aliases
        existing_aliases = set(existing.aliases)
        existing_aliases.update(aliases)
        existing.aliases = list(existing_aliases)


def upsert_document(session: Session, doc_id: str, doc_type: str,
                    source_path: str, raw_text: str,
                    upload_date: Optional[datetime] = None):
    from models import Document
    if session.get(Document, doc_id) is None:
        d = Document(
            doc_id=doc_id,
            type=doc_type,
            source_path=source_path,
            upload_date=upload_date or datetime.utcnow(),
            raw_text=raw_text,
        )
        session.add(d)


def insert_facts(session: Session, doc_id: str, raw_text: str,
                 raw_facts: list[dict[str, Any]],
                 resolved_asset_ids: dict[str, list[str]]) -> list[str]:
    """
    Persist fact rows.  resolved_asset_ids maps fact index → [canonical asset_id, …].
    Returns list of inserted fact_ids.
    """
    from models import Fact
    inserted = []
    for i, rf in enumerate(raw_facts):
        fid = _make_fact_id(doc_id, i)
        if session.get(Fact, fid):
            inserted.append(fid)
            continue

        asset_ids = resolved_asset_ids.get(i, [])
        # If multiple assets, create one row per asset (same fact, different asset links)
        if not asset_ids:
            asset_ids = [None]

        for aid in asset_ids:
            # Use a sub-index for multi-asset facts
            sub_fid = fid if len(asset_ids) == 1 else f"{fid}-{aid}"
            if session.get(Fact, sub_fid):
                continue
            f = Fact(
                fact_id=sub_fid,
                doc_id=doc_id,
                asset_id=aid,
                fact_type=rf["fact_type"],
                timestamp=_parse_ts(rf.get("timestamp")),
                content=rf["content"],
                source_span=_make_source_span(rf.get("source_span", ""), raw_text),
                confidence=float(rf.get("confidence", 0.8)),
            )
            session.add(f)
            inserted.append(sub_fid)

    return inserted


def load_sensor_csvs(session: Session, sensor_dir: str | Path,
                     resolver) -> int:
    """
    Read all sensor CSV files and persist SensorReading rows.
    Returns number of rows inserted.
    """
    from models import SensorReading
    sensor_dir = Path(sensor_dir)
    count = 0
    for csv_path in sorted(sensor_dir.glob("*.csv")):
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                asset_id = resolver.resolve(row.get("asset_id", "")) or row.get("asset_id", "")
                raw_val  = row.get("value", "")
                try:
                    value = float(raw_val)
                except (ValueError, TypeError):
                    value = None   # FAULT / empty

                ts = _parse_ts(row.get("timestamp"))
                if ts is None:
                    continue

                sr = SensorReading(
                    asset_id=asset_id,
                    sensor_id=row.get("sensor_id", ""),
                    timestamp=ts,
                    metric=row.get("sensor_type", row.get("metric", "unknown")),
                    value=value,
                    unit=row.get("unit", ""),
                    status=row.get("status", ""),
                    notes=row.get("notes", ""),
                )
                session.add(sr)
                count += 1
        print(f"[fact_builder] Loaded sensor CSV: {csv_path.name}")

    session.flush()
    return count
