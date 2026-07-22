"""
agents/rca_agent.py — Root Cause Analysis agent.

Fuses work order history, failure records, OEM manuals, sensor anomalies,
and knowledge-graph causal edges into a structured RCA report.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from agents.base import (
    call_llm, facts_to_context, get_causal_chain,
    get_sensor_anomalies, retrieve_context, span_text,
)
from fact_builder import SyncSession

SYSTEM = """You are an industrial RCA (Root Cause Analysis) expert agent.
Given retrieved facts, causal graph edges, and sensor anomalies, produce a
structured RCA report using ONLY the provided evidence.

Format your response as:

## Incident Summary
(1-2 sentences)

## Timeline of Contributing Events
(bullet list, chronological, cite [FACT-ID] for each)

## Root Causes
(numbered list with 5-Why depth where evidence supports it)

## Contributing Factors
(bullet list)

## Sensor / Instrument Evidence
(if any anomalies provided)

## Recommended Corrective Actions
(prioritized: Immediate / Short-term / Long-term)

## Confidence Assessment
(High/Medium/Low with brief justification)

Be specific to the asset and facility. Never invent facts not in the evidence."""


def run_rca(asset_id: str, incident_description: str = "") -> dict:
    query = f"root cause analysis incident failure {asset_id} {incident_description}"
    rows, retrieval_meta = retrieve_context(query, asset_ids=[asset_id], limit=25)

    with SyncSession() as session:
        causal = get_causal_chain(session, asset_id)
        sensors = get_sensor_anomalies(session, asset_id)

        # Incident facts
        incident_rows = session.execute(text("""
            SELECT fact_id, content, source_span, doc_id, confidence, asset_id
            FROM facts
            WHERE asset_id = :aid AND fact_type IN
              ('INCIDENT_EVENT', 'DEFERRED_MAINTENANCE', 'INSTRUMENT_FAULT',
               'SAFETY_VIOLATION', 'ALARM_RESPONSE', 'SHIFT_OBSERVATION')
            ORDER BY timestamp ASC
        """), {"aid": asset_id}).fetchall()

        asset_info = session.execute(text(
            "SELECT name, type, location FROM assets WHERE asset_id = :aid"
        ), {"aid": asset_id}).fetchone()

    # Merge incident rows into context
    seen = {r[0] for r in rows}
    all_rows = list(rows) + [r for r in incident_rows if r[0] not in seen]
    all_rows.sort(key=lambda r: r[4] or 0, reverse=True)

    context = facts_to_context(all_rows[:30])
    causal_text = "\n".join(
        f"  {e['from']} → {e['to']} (w={e['weight']:.1f}, fact={e['fact_id']})"
        for e in causal
    ) or "  (no causal edges found)"

    sensor_text = "\n".join(
        f"  {s['timestamp']} {s['sensor_id']} {s['metric']}={s['value']} status={s['status']}"
        for s in sensors
    ) or "  (no sensor anomalies)"

    user_msg = f"""ASSET: {asset_id} ({asset_info[0] if asset_info else 'unknown'})
TYPE: {asset_info[1] if asset_info else 'unknown'}
LOCATION: {asset_info[2] if asset_info else 'unknown'}
INCIDENT CONTEXT: {incident_description or 'Infer from facts'}

RETRIEVED FACTS (hybrid RAG):
{context}

CAUSAL GRAPH EDGES:
{causal_text}

SENSOR ANOMALIES:
{sensor_text}

Produce the RCA report."""

    report = call_llm(SYSTEM, user_msg)

    sources = [
        {
            "fact_id": r[0],
            "content": r[1],
            "source_span": span_text(r[2]),
            "doc_id": r[3],
            "confidence": float(r[4]),
        }
        for r in all_rows[:15]
    ]

    return {
        "agent": "rca",
        "asset_id": asset_id,
        "report": report,
        "sources": sources,
        "causal_edges": causal,
        "sensor_anomalies": sensors,
        "retrieval_meta": retrieval_meta,
        "generated_at": datetime.utcnow().isoformat(),
    }
