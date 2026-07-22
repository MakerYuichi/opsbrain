"""
agents/base.py — shared utilities for agentic workflows.
"""
from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI
from sqlalchemy import text

from fact_builder import SyncSession
from rag_retriever import hybrid_retrieve

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

_client: OpenAI | None = None


def get_llm_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("GROQ_API_KEY", ""),
            base_url=OPENROUTER_BASE,
        )
    return _client


def load_known_assets(session) -> list[str]:
    rows = session.execute(text("SELECT asset_id FROM assets")).fetchall()
    return [r[0] for r in rows]


def retrieve_context(query: str, asset_ids: list[str] | None = None, limit: int = 20) -> tuple[list[tuple], dict]:
    with SyncSession() as session:
        known = load_known_assets(session)
        return hybrid_retrieve(query, session, known, limit=limit, asset_filter=asset_ids)


def span_text(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return json.loads(raw).get("text", raw)
    except Exception:
        return raw


def facts_to_context(rows: list[tuple]) -> str:
    lines = []
    for r in rows:
        lines.append(f"[{r[0]}] asset={r[5]} type doc={r[3]} conf={r[4]:.2f}: {r[1]}")
    return "\n".join(lines)


def call_llm(system: str, user: str, max_tokens: int = 1200) -> str:
    client = get_llm_client()
    headers = {
        "HTTP-Referer": "https://github.com/MakerYuichi/opsbrain",
        "X-Title": "opsbrain-agents",
    }
    last_err = None
    for model in OPENROUTER_MODELS:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
                extra_headers=headers,
                timeout=60,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            last_err = e
            continue
    return f"LLM unavailable ({last_err}). See structured findings below."


def get_causal_chain(session, asset_id: str) -> list[dict]:
    """Pull CAUSAL_SEQUENCE edges involving this asset."""
    rows = session.execute(text("""
        SELECT e.from_id, e.to_id, e.relation_type, e.weight, e.source_fact_id
        FROM edges e
        WHERE e.relation_type = 'CAUSAL_SEQUENCE'
          AND (e.from_id = :aid OR e.to_id = :aid
               OR e.from_id IN (SELECT doc_id FROM facts WHERE asset_id = :aid)
               OR e.to_id IN (SELECT doc_id FROM facts WHERE asset_id = :aid))
        ORDER BY e.weight DESC LIMIT 20
    """), {"aid": asset_id}).fetchall()
    return [{"from": r[0], "to": r[1], "relation": r[2], "weight": r[3], "fact_id": r[4]} for r in rows]


def get_sensor_anomalies(session, asset_id: str, limit: int = 10) -> list[dict]:
    rows = session.execute(text("""
        SELECT sensor_id, timestamp, metric, value, unit, status, notes
        FROM sensor_readings
        WHERE asset_id = :aid AND status IN ('FAULT', 'WARN', 'MANUAL_READ')
        ORDER BY timestamp DESC LIMIT :lim
    """), {"aid": asset_id, "lim": limit}).fetchall()
    return [
        {"sensor_id": r[0], "timestamp": str(r[1]), "metric": r[2],
         "value": r[3], "unit": r[4], "status": r[5], "notes": r[6]}
        for r in rows
    ]
