"""
agents/maintenance_agent.py — Predictive maintenance & schedule optimization agent.

Analyzes deferred maintenance, open work orders, sensor trends, and OEM
intervals to produce a prioritized maintenance schedule.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text

from agents.base import call_llm, facts_to_context, get_sensor_anomalies, retrieve_context
from fact_builder import SyncSession

SYSTEM = """You are a maintenance planning agent for an asset-intensive plant.
Given deferred maintenance facts, work orders, sensor anomalies, and OEM
references, produce a prioritized maintenance schedule.

Format:

## Maintenance Priority Queue
For each item:
- Priority: P1 (immediate) / P2 (this week) / P3 (scheduled)
- Asset ID
- Task description
- Rationale (cite [FACT-ID])
- Estimated risk if deferred
- Suggested window

## Sensor-Driven Recommendations
(any anomalies requiring inspection)

## OEM Interval Compliance
(gaps vs recommended intervals)

Be actionable. Ground every recommendation in cited facts."""


def run_maintenance(asset_id: str | None = None) -> dict:
    query = f"deferred maintenance work order schedule inspection {asset_id or 'all assets'}"
    asset_filter = [asset_id] if asset_id else None
    rows, retrieval_meta = retrieve_context(query, asset_ids=asset_filter, limit=25)

    with SyncSession() as session:
        maint_clause = "WHERE f.asset_id = :aid" if asset_id else ""
        params: dict = {"aid": asset_id} if asset_id else {}

        maint_rows = session.execute(text(f"""
            SELECT f.fact_id, f.content, f.source_span, f.doc_id, f.confidence,
                   f.asset_id, f.fact_type, f.timestamp
            FROM facts f
            {maint_clause}
            {"AND" if asset_id else "WHERE"} f.fact_type IN (
              'DEFERRED_MAINTENANCE', 'WORK_ORDER', 'MAINTENANCE_ACTION',
              'INSTRUMENT_FAULT', 'PROCESS_PARAMETER'
            )
            ORDER BY
              CASE f.fact_type
                WHEN 'DEFERRED_MAINTENANCE' THEN 1
                WHEN 'WORK_ORDER' THEN 2
                WHEN 'INSTRUMENT_FAULT' THEN 3
                ELSE 4
              END,
              f.timestamp ASC NULLS LAST
            LIMIT 30
        """), params).fetchall()

        sensors = get_sensor_anomalies(session, asset_id) if asset_id else []
        if not asset_id:
            sensors = session.execute(text("""
                SELECT sensor_id, timestamp, metric, value, unit, status, notes, asset_id
                FROM sensor_readings
                WHERE status IN ('FAULT', 'WARN')
                ORDER BY timestamp DESC LIMIT 15
            """)).fetchall()
            sensors = [
                {"sensor_id": r[0], "timestamp": str(r[1]), "metric": r[2],
                 "value": r[3], "unit": r[4], "status": r[5], "notes": r[6],
                 "asset_id": r[7]}
                for r in sensors
            ]

    seen = {r[0] for r in rows}
    all_rows = list(rows) + [r[:6] for r in maint_rows if r[0] not in seen]

    context = facts_to_context(all_rows[:25])
    sensor_text = "\n".join(
        f"  {s.get('asset_id','?')} {s['timestamp']} {s['sensor_id']} {s['status']}"
        for s in sensors
    ) or "  (no active sensor faults)"

    user_msg = f"""SCOPE: {asset_id or 'All plant assets'}

MAINTENANCE FACTS (hybrid RAG):
{context}

SENSOR FAULTS/WARNINGS:
{sensor_text}

Produce the prioritized maintenance schedule."""

    report = call_llm(SYSTEM, user_msg)

    # Build structured queue from facts
    queue = []
    for r in maint_rows:
        priority = "P1" if r[6] == "DEFERRED_MAINTENANCE" else "P2" if r[6] == "WORK_ORDER" else "P3"
        queue.append({
            "priority": priority,
            "fact_id": r[0],
            "asset_id": r[5],
            "fact_type": r[6],
            "content": r[1],
            "timestamp": str(r[7]) if r[7] else None,
        })

    return {
        "agent": "maintenance",
        "asset_id": asset_id,
        "schedule_report": report,
        "priority_queue": queue,
        "sensor_faults": sensors,
        "retrieval_meta": retrieval_meta,
        "generated_at": datetime.utcnow().isoformat(),
    }
