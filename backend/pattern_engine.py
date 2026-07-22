"""
pattern_engine.py — cluster Fact rows into candidate patterns, call LLM to
narrate each cluster, persist Alert rows.

Clustering strategy
────────────────────
Primary key: (asset_id, fact_type)
Threshold  : ≥ 3 facts in the cluster (configurable)

Secondary merge: clusters on the same asset with related fact types
(e.g. DEFERRED_MAINTENANCE + INSTRUMENT_FAULT on APS-3) are merged into a
single multi-type cluster if they share at least 2 documents.

This gives us clusters that map cleanly to the 6 known patterns in
known_patterns_index.json without hard-coding them.
"""
import hashlib
import json
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from openai import OpenAI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

_DB_URL  = os.getenv("DATABASE_URL", "sqlite:///./industrial_ki.db").replace(
    "sqlite+aiosqlite", "sqlite"
)
_engine  = create_engine(_DB_URL, connect_args={"check_same_thread": False})
_Session = sessionmaker(_engine)

OPENROUTER_BASE   = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

# ── Fact types that indicate hazard precursors ────────────────────────────────
PRECURSOR_TYPES = {
    "DEFERRED_MAINTENANCE",
    "INSTRUMENT_FAULT",
    "SAFETY_VIOLATION",
    "ALARM_RESPONSE",
    "SHIFT_OBSERVATION",
    "RISK_OBSERVATION",
    "PERMIT_STATUS",
    "WORK_ORDER",
    "TEMPERATURE_READING",
    "QUALITY_READING",
}

# Related-type groups for secondary merging
RELATED_GROUPS = [
    {"DEFERRED_MAINTENANCE", "INSTRUMENT_FAULT", "WORK_ORDER"},
    {"SAFETY_VIOLATION", "ALARM_RESPONSE", "SHIFT_OBSERVATION"},
    {"PERMIT_STATUS", "SAFETY_VIOLATION", "RISK_OBSERVATION"},
    {"QUALITY_READING", "RISK_OBSERVATION"},
    {"TEMPERATURE_READING", "SHIFT_OBSERVATION", "ALARM_RESPONSE"},
]

MIN_CLUSTER_SIZE = 3   # minimum facts to form a cluster worth analysing


# ── Step 1: Load and cluster facts ───────────────────────────────────────────

def _load_precursor_facts(session) -> list[dict]:
    types_ph = ",".join(f"'{t}'" for t in PRECURSOR_TYPES)
    rows = session.execute(text(f"""
        SELECT f.fact_id, f.doc_id, d.type as doc_type,
               f.asset_id, f.fact_type, f.timestamp,
               f.content, f.source_span, f.confidence
        FROM facts f
        JOIN documents d ON f.doc_id = d.doc_id
        WHERE f.fact_type IN ({types_ph})
          AND f.asset_id IS NOT NULL
        ORDER BY f.asset_id, f.fact_type, f.timestamp
    """)).fetchall()
    return [
        {
            "fact_id":    r[0], "doc_id": r[1], "doc_type": r[2],
            "asset_id":   r[3], "fact_type": r[4],
            "timestamp":  str(r[5]) if r[5] else None,
            "content":    r[6],
            "source_span": r[7],
            "confidence": float(r[8] or 0.8),
        }
        for r in rows
    ]


def _primary_clusters(facts: list[dict]) -> dict[tuple, list[dict]]:
    """Group by (asset_id, fact_type)."""
    clusters: dict[tuple, list[dict]] = defaultdict(list)
    for f in facts:
        clusters[(f["asset_id"], f["fact_type"])].append(f)
    return {k: v for k, v in clusters.items() if len(v) >= MIN_CLUSTER_SIZE}


def _merge_related(
    primary: dict[tuple, list[dict]]
) -> list[dict[str, Any]]:
    """
    Merge (asset_id, fact_type) clusters that:
      - share the same asset_id
      - belong to the same RELATED_GROUP
      - share at least 2 doc_ids
    Returns list of merged cluster dicts.
    """
    # Group keys by asset
    by_asset: dict[str, list[tuple]] = defaultdict(list)
    for key in primary:
        by_asset[key[0]].append(key)

    used: set[tuple] = set()
    merged_clusters: list[dict[str, Any]] = []

    for asset_id, keys in by_asset.items():
        # Try to merge within each related group
        for group in RELATED_GROUPS:
            group_keys = [k for k in keys if k[1] in group and k not in used]
            if len(group_keys) < 2:
                continue
            # Check document overlap
            doc_sets = [set(f["doc_id"] for f in primary[k]) for k in group_keys]
            # Simple check: any two clusters share ≥ 2 docs
            merged = []
            for i in range(len(group_keys)):
                for j in range(i + 1, len(group_keys)):
                    shared = doc_sets[i] & doc_sets[j]
                    if len(shared) >= 2:
                        if group_keys[i] not in used:
                            merged += primary[group_keys[i]]
                            used.add(group_keys[i])
                        if group_keys[j] not in used:
                            merged += primary[group_keys[j]]
                            used.add(group_keys[j])
            if merged:
                types = list({f["fact_type"] for f in merged})
                merged_clusters.append({
                    "cluster_id":  f"{asset_id}__{'_'.join(sorted(types))}",
                    "asset_id":    asset_id,
                    "fact_types":  types,
                    "facts":       merged,
                    "is_merged":   True,
                })

    # Add remaining un-merged clusters as singletons
    for key, facts in primary.items():
        if key not in used:
            merged_clusters.append({
                "cluster_id": f"{key[0]}__{key[1]}",
                "asset_id":   key[0],
                "fact_types": [key[1]],
                "facts":      facts,
                "is_merged":  False,
            })

    return merged_clusters


def build_clusters() -> list[dict[str, Any]]:
    with _Session() as session:
        facts = _load_precursor_facts(session)
    primary  = _primary_clusters(facts)
    clusters = _merge_related(primary)
    print(f"[pattern_engine] {len(facts)} precursor facts → "
          f"{len(primary)} primary clusters → "
          f"{len(clusters)} merged clusters")
    return clusters


# ── Step 2: LLM narration ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an industrial safety analyst. I will give you a cluster of safety-relevant \
facts extracted from industrial maintenance logs, shift logs, and permit records.

Respond with ONLY a JSON object — no markdown, no prose before or after.
Schema:
{
  "is_pattern": true/false,
  "pattern_type": "<short snake_case name, e.g. RECURRING_PURGE_SKIP>",
  "description": "<2-3 sentence plain-English description of the recurring pattern>",
  "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "confidence": <float 0.0-1.0>,
  "cited_fact_ids": ["<fact_id>", ...],
  "oem_reference": "<relevant OEM manual section if mentioned in any fact, else null>",
  "recommendation": "<one concrete action to break this pattern>"
}

Rules:
- Set is_pattern=false if the facts are just noise or a single isolated event.
- cited_fact_ids MUST contain only IDs from the facts provided.
- confidence should reflect: how consistent is the repetition? how safety-critical?
- oem_reference: if any fact mentions an OEM section number or manual, cite it.
"""

USER_TEMPLATE = """\
Asset: {asset_id}
Fact types in cluster: {fact_types}
Cluster size: {count} facts across {doc_count} documents

FACTS:
{facts_block}

Does this cluster represent a recurring industrial safety pattern?
"""


def _make_client() -> OpenAI:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise EnvironmentError("GROQ_API_KEY not set in .env")
    return OpenAI(api_key=key, base_url=OPENROUTER_BASE)


def _narrate_cluster(
    cluster: dict[str, Any],
    client: OpenAI,
    oem_texts: dict[str, str],
) -> dict[str, Any] | None:
    """Call LLM to narrate one cluster. Returns parsed JSON or None."""
    facts = cluster["facts"]
    doc_ids = list({f["doc_id"] for f in facts})

    # Build facts block — include content + source_span text
    lines = []
    for f in facts[:20]:  # cap at 20 to stay within token budget
        span_text = ""
        if f.get("source_span"):
            try:
                span_text = json.loads(f["source_span"]).get("text", "")[:100]
            except Exception:
                span_text = str(f["source_span"])[:100]
        lines.append(
            f'  [{f["fact_id"]}] {f["fact_type"]} | {f["asset_id"]} | '
            f'{(f["timestamp"] or "")[:10]} | {f["content"][:120]}'
        )
        if span_text:
            lines.append(f'    source: "{span_text}"')

    user_msg = USER_TEMPLATE.format(
        asset_id=cluster["asset_id"],
        fact_types=", ".join(cluster["fact_types"]),
        count=len(facts),
        doc_count=len(doc_ids),
        facts_block="\n".join(lines),
    )

    for model in OPENROUTER_MODELS:
        for attempt in range(2):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": user_msg},
                    ],
                    temperature=0.1,
                    max_tokens=800,
                    extra_headers={
                        "HTTP-Referer": "https://github.com/MakerYuichi/opsbrain",
                        "X-Title": "Industrial KI Pattern Breaker",
                    },
                    timeout=40,
                )
                raw = resp.choices[0].message.content or ""
                raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
                raw = re.sub(r"\s*```\s*$",        "", raw,       flags=re.MULTILINE)
                return json.loads(raw.strip())

            except json.JSONDecodeError:
                if attempt == 0:
                    time.sleep(2)
                    continue
                break
            except Exception as e:
                err = str(e).lower()
                if "404" in err or "unavailable" in err:
                    break  # try next model
                if "rate" in err or "429" in err:
                    time.sleep(15)
                else:
                    print(f"[pattern_engine] LLM error [{model}]: {e}")
                    if attempt == 0:
                        time.sleep(3)
                    else:
                        break
    return None


# ── Step 3: Persist alerts ────────────────────────────────────────────────────

def _alert_id(cluster_id: str) -> str:
    return "ALERT-" + hashlib.md5(cluster_id.encode()).hexdigest()[:10].upper()


def persist_alert(session, cluster: dict, narration: dict) -> str | None:
    """Insert an Alert row if it doesn't exist. Returns alert_id or None."""
    from models import Alert

    if not narration.get("is_pattern"):
        return None
    cited = narration.get("cited_fact_ids", [])
    if not cited:
        return None

    alert_id = _alert_id(cluster["cluster_id"])
    if session.get(Alert, alert_id):
        return alert_id  # already exists

    a = Alert(
        alert_id=alert_id,
        asset_id=cluster["asset_id"],
        pattern_type=narration.get("pattern_type", "UNKNOWN_PATTERN"),
        description=(
            f"[{narration.get('risk_level','?')}] "
            + narration.get("description", "")
            + (f" Recommendation: {narration['recommendation']}"
               if narration.get("recommendation") else "")
        ),
        confidence=float(narration.get("confidence", 0.5)),
        created_at=datetime.utcnow(),
    )
    a.source_fact_ids = cited
    session.add(a)
    return alert_id


# ── Step 4: Full run ──────────────────────────────────────────────────────────

def run_pattern_detection(force_refresh: bool = False) -> list[str]:
    """
    Run the full pattern detection pipeline.
    Returns list of alert_ids persisted.
    """
    from models import Alert, Base

    # Ensure schema
    from fact_builder import sync_engine
    Base.metadata.create_all(sync_engine)

    # Load OEM texts for reference
    with _Session() as session:
        oem_rows = session.execute(text(
            "SELECT doc_id, raw_text FROM documents WHERE type = 'oem_manual'"
        )).fetchall()
    oem_texts = {r[0]: r[1] for r in oem_rows}

    clusters = build_clusters()
    client   = _make_client()

    alert_ids: list[str] = []
    for i, cluster in enumerate(clusters, 1):
        cid = cluster["cluster_id"]

        # Skip if alert already exists and not forcing refresh
        existing_id = _alert_id(cid)
        with _Session() as session:
            from models import Alert
            if not force_refresh and session.get(Alert, existing_id):
                print(f"[pattern_engine] ({i}/{len(clusters)}) {cid} — skipped (cached)")
                alert_ids.append(existing_id)
                continue

        print(f"[pattern_engine] ({i}/{len(clusters)}) Narrating {cid} "
              f"({len(cluster['facts'])} facts)…")
        narration = _narrate_cluster(cluster, client, oem_texts)
        if narration is None:
            print(f"[pattern_engine]   → LLM failed, skipping")
            continue

        if not narration.get("is_pattern"):
            print(f"[pattern_engine]   → Not a pattern (LLM verdict)")
            continue

        with _Session() as session:
            aid = persist_alert(session, cluster, narration)
            session.commit()

        if aid:
            print(f"[pattern_engine]   → Alert {aid} | "
                  f"{narration.get('pattern_type')} | "
                  f"conf={narration.get('confidence'):.2f} | "
                  f"risk={narration.get('risk_level')}")
            alert_ids.append(aid)

        time.sleep(2)  # rate-limit buffer

    print(f"[pattern_engine] Done. {len(alert_ids)} alerts persisted.")
    return alert_ids


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Re-narrate all clusters")
    args = ap.parse_args()
    run_pattern_detection(force_refresh=args.force)
