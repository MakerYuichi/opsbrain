"""
routers/patterns.py — Pattern Breaker API

GET  /alerts            — list all persisted alerts
GET  /alerts/{alert_id} — single alert with full supporting facts
POST /alerts/run        — trigger pattern detection (runs in background)
GET  /alerts/run/status — check if detection is running
"""
import json
import threading
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/alerts", tags=["Pattern Breaker"])

_DB_URL  = os.getenv("DATABASE_URL", "sqlite:///./industrial_ki.db").replace(
    "sqlite+aiosqlite", "sqlite"
)
_engine  = create_engine(_DB_URL, connect_args={"check_same_thread": False})
_Session = sessionmaker(_engine)

# Simple in-process state for detection runs
_detection_state = {"running": False, "last_run": None, "last_count": 0, "error": None}


# ── Response models ───────────────────────────────────────────────────────────

class AlertSummary(BaseModel):
    alert_id:     str
    asset_id:     Optional[str]
    pattern_type: str
    description:  str
    confidence:   float
    source_fact_count: int
    created_at:   str
    risk_level:   str   # extracted from description prefix


class SupportingFact(BaseModel):
    fact_id:     str
    doc_id:      str
    doc_type:    Optional[str]
    asset_id:    Optional[str]
    fact_type:   str
    timestamp:   Optional[str]
    content:     str
    source_span_text: str
    confidence:  float


class AlertDetail(BaseModel):
    alert_id:      str
    asset_id:      Optional[str]
    pattern_type:  str
    description:   str
    confidence:    float
    risk_level:    str
    created_at:    str
    supporting_facts: list[SupportingFact]


class RunStatus(BaseModel):
    running:    bool
    last_run:   Optional[str]
    last_count: int
    error:      Optional[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _risk_level(description: str) -> str:
    for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if f"[{level}]" in description:
            return level
    return "UNKNOWN"


def _parse_span_text(span_json: Optional[str]) -> str:
    if not span_json:
        return ""
    try:
        return json.loads(span_json).get("text", "")
    except Exception:
        return str(span_json)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AlertSummary])
def list_alerts(asset_id: Optional[str] = None):
    with _Session() as session:
        if asset_id:
            rows = session.execute(text(
                "SELECT alert_id, asset_id, pattern_type, description, "
                "       confidence, source_fact_ids, created_at "
                "FROM alerts WHERE asset_id = :aid ORDER BY confidence DESC"
            ), {"aid": asset_id}).fetchall()
        else:
            rows = session.execute(text(
                "SELECT alert_id, asset_id, pattern_type, description, "
                "       confidence, source_fact_ids, created_at "
                "FROM alerts ORDER BY confidence DESC"
            )).fetchall()

    result = []
    for r in rows:
        try:
            fact_ids = json.loads(r[5] or "[]")
        except Exception:
            fact_ids = []
        result.append(AlertSummary(
            alert_id=r[0],
            asset_id=r[1],
            pattern_type=r[2],
            description=r[3] or "",
            confidence=float(r[4] or 0),
            source_fact_count=len(fact_ids),
            created_at=str(r[6]),
            risk_level=_risk_level(r[3] or ""),
        ))
    return result


@router.get("/run/status", response_model=RunStatus)
def detection_status():
    return RunStatus(
        running=_detection_state["running"],
        last_run=str(_detection_state["last_run"]) if _detection_state["last_run"] else None,
        last_count=_detection_state["last_count"],
        error=_detection_state["error"],
    )


@router.post("/run")
def trigger_detection(background_tasks: BackgroundTasks,
                      force: bool = False):
    if _detection_state["running"]:
        raise HTTPException(409, "Detection already running")

    def _run():
        _detection_state["running"] = True
        _detection_state["error"]   = None
        try:
            from pattern_engine import run_pattern_detection
            ids = run_pattern_detection(force_refresh=force)
            _detection_state["last_count"] = len(ids)
            _detection_state["last_run"]   = datetime.utcnow()
            # Invalidate the graph cache so the Graph Explorer picks up
            # any new edges written by pattern_engine.save_graph()
            from routers.graph import invalidate_graph_cache
            invalidate_graph_cache()
        except Exception as e:
            _detection_state["error"] = str(e)
        finally:
            _detection_state["running"] = False

    background_tasks.add_task(_run)
    return {"status": "started"}


@router.get("/{alert_id}", response_model=AlertDetail)
def get_alert(alert_id: str):
    with _Session() as session:
        row = session.execute(text(
            "SELECT alert_id, asset_id, pattern_type, description, "
            "       confidence, source_fact_ids, created_at "
            "FROM alerts WHERE alert_id = :aid"
        ), {"aid": alert_id}).fetchone()

        if not row:
            raise HTTPException(404, f"Alert {alert_id!r} not found")

        try:
            fact_ids = json.loads(row[5] or "[]")
        except Exception:
            fact_ids = []

        # Fetch supporting facts
        supporting: list[SupportingFact] = []
        if fact_ids:
            ph = ",".join(f":f{i}" for i in range(len(fact_ids)))
            fp = {f"f{i}": fid for i, fid in enumerate(fact_ids)}
            fact_rows = session.execute(text(f"""
                SELECT f.fact_id, f.doc_id, d.type, f.asset_id,
                       f.fact_type, f.timestamp, f.content,
                       f.source_span, f.confidence
                FROM facts f
                JOIN documents d ON f.doc_id = d.doc_id
                WHERE f.fact_id IN ({ph})
            """), fp).fetchall()

            for fr in fact_rows:
                supporting.append(SupportingFact(
                    fact_id=fr[0],
                    doc_id=fr[1],
                    doc_type=fr[2],
                    asset_id=fr[3],
                    fact_type=fr[4],
                    timestamp=str(fr[5]) if fr[5] else None,
                    content=fr[6],
                    source_span_text=_parse_span_text(fr[7]),
                    confidence=float(fr[8] or 0.8),
                ))

    return AlertDetail(
        alert_id=row[0],
        asset_id=row[1],
        pattern_type=row[2],
        description=row[3] or "",
        confidence=float(row[4] or 0),
        risk_level=_risk_level(row[3] or ""),
        created_at=str(row[6]),
        supporting_facts=supporting,
    )
