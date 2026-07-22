"""
routers/timeline.py — Time Machine API

GET /assets                           — all assets for AssetPicker
GET /assets/{asset_id}/last-date      — last fact date for an asset
GET /timeline?asset_id=&date=         — facts + sensors + OEM refs in 24h window
"""
import json
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

router  = APIRouter()
_DB_URL = os.getenv("DATABASE_URL", "sqlite:///./industrial_ki.db").replace(
    "sqlite+aiosqlite", "sqlite"
)
_engine  = create_engine(_DB_URL, connect_args={"check_same_thread": False})
_Session = sessionmaker(_engine)


# ── Response models ───────────────────────────────────────────────────────────

class SourceSpan(BaseModel):
    start: int
    end:   int
    text:  str

class EvidenceFact(BaseModel):
    fact_id:          str
    doc_id:           str
    doc_type:         Optional[str]
    asset_id:         Optional[str]
    fact_type:        str
    timestamp:        Optional[str]
    content:          str
    source_span:      SourceSpan
    confidence:       float
    raw_text_excerpt: Optional[str]

class SensorPoint(BaseModel):
    sensor_id: str
    timestamp: str
    metric:    str
    value:     Optional[float]
    unit:      Optional[str]
    status:    str
    notes:     Optional[str]

class OEMReference(BaseModel):
    doc_id:         str
    excerpt:        str
    relevance_note: str

class TimelineResponse(BaseModel):
    asset_id:       str
    asset_name:     str
    window_start:   str
    window_end:     str
    facts:          list[EvidenceFact]
    sensor_readings: list[SensorPoint]
    oem_references: list[OEMReference]

class AssetItem(BaseModel):
    asset_id: str
    name:     str
    type:     str
    location: Optional[str]

class AssetLastDate(BaseModel):
    asset_id: str
    date:     str   # ISO YYYY-MM-DD of the last fact for this asset


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_span(span_json: Optional[str]) -> SourceSpan:
    if not span_json:
        return SourceSpan(start=-1, end=-1, text="")
    try:
        d = json.loads(span_json)
        return SourceSpan(start=int(d.get("start",-1)), end=int(d.get("end",-1)), text=str(d.get("text","")))
    except Exception:
        return SourceSpan(start=-1, end=-1, text=str(span_json))

def _excerpt(raw_text: Optional[str], span: SourceSpan, context: int = 200) -> Optional[str]:
    if not raw_text or span.start < 0:
        return None
    s = max(0, span.start - context)
    e = min(len(raw_text), span.end + context)
    snippet = raw_text[s:e]
    rel_s, rel_e = span.start - s, span.end - s
    if 0 <= rel_s < rel_e <= len(snippet):
        snippet = snippet[:rel_s] + ">>>" + snippet[rel_s:rel_e] + "<<<" + snippet[rel_e:]
    return snippet.strip()

def _connected_asset_ids(session, asset_id: str) -> list[str]:
    rows = session.execute(text("""
        SELECT DISTINCT f2.asset_id
        FROM facts f1 JOIN facts f2 ON f1.doc_id = f2.doc_id
        WHERE f1.asset_id = :aid AND f2.asset_id IS NOT NULL AND f2.asset_id != :aid
    """), {"aid": asset_id}).fetchall()
    return [r[0] for r in rows]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/assets", response_model=list[AssetItem])
def list_assets():
    with _Session() as session:
        rows = session.execute(text(
            "SELECT asset_id, name, type, location FROM assets ORDER BY name"
        )).fetchall()
    return [AssetItem(asset_id=r[0], name=r[1], type=r[2], location=r[3]) for r in rows]


@router.get("/assets/{asset_id}/last-date", response_model=AssetLastDate)
def asset_last_date(asset_id: str):
    """
    Return the date of the most recent fact for this asset.
    Used by the cross-feature nav so 'View in Time Machine' lands on a date
    that actually has data, not today's date.
    """
    with _Session() as session:
        row = session.execute(text("""
            SELECT MAX(timestamp) FROM facts
            WHERE asset_id = :aid AND timestamp IS NOT NULL
        """), {"aid": asset_id}).fetchone()

        if not row or not row[0]:
            # Fallback: try sensor readings
            row2 = session.execute(text("""
                SELECT MAX(timestamp) FROM sensor_readings
                WHERE asset_id = :aid
            """), {"aid": asset_id}).fetchone()
            if not row2 or not row2[0]:
                raise HTTPException(404, f"No dated facts for asset {asset_id!r}")
            ts_str = str(row2[0])
        else:
            ts_str = str(row[0])

    # Return just the date portion (YYYY-MM-DD)
    date_str = ts_str[:10]
    return AssetLastDate(asset_id=asset_id, date=date_str)


@router.get("/timeline", response_model=TimelineResponse)
def get_timeline(
    asset_id:     str = Query(...),
    date:         str = Query(...),
    window_hours: int = Query(24),
):
    try:
        end_dt   = datetime.strptime(date[:10], "%Y-%m-%d").replace(hour=23, minute=59)
        start_dt = end_dt - timedelta(hours=window_hours)
    except ValueError:
        raise HTTPException(400, f"Invalid date: {date!r}")

    with _Session() as session:
        asset_row = session.execute(text(
            "SELECT asset_id, name FROM assets WHERE asset_id = :aid"
        ), {"aid": asset_id}).fetchone()
        if not asset_row:
            raise HTTPException(404, f"Asset {asset_id!r} not found")

        asset_name = asset_row[1]
        connected  = _connected_asset_ids(session, asset_id)
        all_assets = [asset_id] + connected[:6]

        ph     = ",".join(f":a{i}" for i in range(len(all_assets)))
        params: dict = {"start": start_dt, "end": end_dt}
        for i, a in enumerate(all_assets):
            params[f"a{i}"] = a

        fact_rows = session.execute(text(f"""
            SELECT f.fact_id, f.doc_id, d.type, f.asset_id,
                   f.fact_type, f.timestamp, f.content, f.source_span,
                   f.confidence, d.raw_text
            FROM facts f JOIN documents d ON f.doc_id = d.doc_id
            WHERE f.asset_id IN ({ph})
              AND f.timestamp >= :start AND f.timestamp <= :end
            ORDER BY f.timestamp, f.fact_type
        """), params).fetchall()

        # OEM manual facts have no timestamp — pull them via relevant docs
        relevant_doc_ids = list({r[1] for r in fact_rows})
        if relevant_doc_ids:
            dp = ",".join(f":d{i}" for i in range(len(relevant_doc_ids)))
            dp_vals = {f"d{i}": d for i, d in enumerate(relevant_doc_ids)}
            oem_rows = session.execute(text(f"""
                SELECT f.fact_id, f.doc_id, d.type, f.asset_id,
                       f.fact_type, f.timestamp, f.content, f.source_span,
                       f.confidence, d.raw_text
                FROM facts f JOIN documents d ON f.doc_id = d.doc_id
                WHERE d.type = 'oem_manual'
                  AND f.doc_id IN ({dp}) AND f.timestamp IS NULL
            """), dp_vals).fetchall()
        else:
            oem_rows = []

        # Build EvidenceFact list
        seen: set[str] = set()
        facts_out: list[EvidenceFact] = []
        for r in fact_rows + oem_rows:
            if r[0] in seen:
                continue
            seen.add(r[0])
            span = _parse_span(r[7])
            facts_out.append(EvidenceFact(
                fact_id=r[0], doc_id=r[1], doc_type=r[2], asset_id=r[3],
                fact_type=r[4], timestamp=str(r[5]) if r[5] else None,
                content=r[6], source_span=span,
                confidence=float(r[8] or 0.8),
                raw_text_excerpt=_excerpt(r[9], span),
            ))

        # Sensor readings in window
        sr_rows = session.execute(text(f"""
            SELECT sensor_id, timestamp, metric, value, unit, status, notes
            FROM sensor_readings
            WHERE asset_id IN ({ph}) AND timestamp >= :start AND timestamp <= :end
            ORDER BY timestamp
        """), params).fetchall()

        sensors_out = [
            SensorPoint(sensor_id=r[0], timestamp=str(r[1]), metric=r[2],
                        value=r[3], unit=r[4] or "", status=r[5] or "", notes=r[6] or "")
            for r in sr_rows
        ]

        # OEM references via connected assets
        oem_ap = ",".join(f":oa{i}" for i in range(len(all_assets)))
        oem_p  = {f"oa{i}": a for i, a in enumerate(all_assets)}
        oem_ref_rows = session.execute(text(f"""
            SELECT DISTINCT d.doc_id, d.raw_text
            FROM documents d JOIN facts f ON f.doc_id = d.doc_id
            WHERE d.type = 'oem_manual' AND f.asset_id IN ({oem_ap})
            LIMIT 3
        """), oem_p).fetchall()

        oem_refs_out: list[OEMReference] = []
        for doc_id, raw_text in oem_ref_rows:
            if not raw_text:
                continue
            idx = raw_text.lower().find(asset_id.lower())
            if idx < 0: idx = 0
            excerpt = raw_text[max(0, idx-50):min(len(raw_text), idx+400)].strip()
            oem_refs_out.append(OEMReference(
                doc_id=doc_id, excerpt=excerpt,
                relevance_note=f"OEM manual references asset {asset_id}",
            ))

    return TimelineResponse(
        asset_id=asset_id, asset_name=asset_name,
        window_start=start_dt.isoformat(), window_end=end_dt.isoformat(),
        facts=facts_out, sensor_readings=sensors_out, oem_references=oem_refs_out,
    )
