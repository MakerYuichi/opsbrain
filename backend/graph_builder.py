"""
graph_builder.py — derive Edge rows from facts and load a NetworkX graph.

Edge derivation rules
──────────────────────
1. SHARES_ASSET      — two documents that mention the same asset_id
2. TEMPORAL_OVERLAP  — two facts on the same asset within a configurable
                       time window (default 30 days)
3. CROSS_REFERENCE   — extracted from explicit doc references in source_spans
                       (e.g. "see VSP-SHIFT-011")
4. CAUSAL_SEQUENCE   — DEFERRED_MAINTENANCE or INSTRUMENT_FAULT fact followed
                       by an INCIDENT_EVENT on the same asset chain within
                       the window

The graph is persisted as a JSON node-link file alongside the SQLite DB so
the FastAPI layer can reload it instantly without rerunning the pipeline.
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import networkx as nx
from sqlalchemy import text
from sqlalchemy.orm import Session

GRAPH_PATH = os.getenv("GRAPH_PATH", "./knowledge_graph.json")
TEMPORAL_WINDOW_DAYS = 30

# Fact types that are "precursor" signals (left side of a causal edge)
PRECURSOR_TYPES = {
    "DEFERRED_MAINTENANCE",
    "INSTRUMENT_FAULT",
    "SAFETY_VIOLATION",
    "PERMIT_STATUS",
    "RISK_OBSERVATION",
    "ALARM_RESPONSE",
}

# Cross-reference pattern — matches doc IDs embedded in text
_DOCREF_RE = re.compile(
    r"\b((?:LGP|VSP)-(?:MAINT|SHIFT|PERMIT|PTW|OEM|AUDIT|INCIDENT|QC|WO)"
    r"-\d{3,4}(?:-\d+)?)\b"
)


def _iter_facts(session: Session):
    """Yield all facts as dicts."""
    rows = session.execute(text(
        "SELECT fact_id, doc_id, asset_id, fact_type, timestamp, content, source_span "
        "FROM facts ORDER BY timestamp"
    )).fetchall()
    for r in rows:
        yield {
            "fact_id":    r[0],
            "doc_id":     r[1],
            "asset_id":   r[2],
            "fact_type":  r[3],
            "timestamp":  r[4],
            "content":    r[5],
            "source_span": r[6],
        }


def _upsert_edge(session: Session, from_id: str, to_id: str,
                 relation: str, source_fact_id: str = None,
                 weight: float = 1.0):
    """Insert edge if it doesn't exist; bump weight if it does."""
    from models import Edge
    existing = (
        session.query(Edge)
        .filter_by(from_id=from_id, to_id=to_id, relation_type=relation)
        .first()
    )
    if existing:
        existing.weight = min(existing.weight + 0.2, 5.0)
    else:
        session.add(Edge(
            from_id=from_id,
            to_id=to_id,
            relation_type=relation,
            source_fact_id=source_fact_id,
            weight=weight,
        ))


def build_edges(session: Session):
    """Derive and persist all Edge rows from existing facts."""
    facts = list(_iter_facts(session))
    print(f"[graph_builder] Building edges from {len(facts)} facts…")

    # Index by asset_id and by doc_id
    by_asset: dict[str, list[dict]]  = defaultdict(list)
    by_doc:   dict[str, list[dict]]  = defaultdict(list)
    for f in facts:
        if f["asset_id"]:
            by_asset[f["asset_id"]].append(f)
        by_doc[f["doc_id"]].append(f)

    edge_count = 0

    # ── Rule 1: SHARES_ASSET ─────────────────────────────────────────────────
    for asset_id, asset_facts in by_asset.items():
        doc_ids = list({f["doc_id"] for f in asset_facts})
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                _upsert_edge(session, doc_ids[i], doc_ids[j], "SHARES_ASSET",
                             weight=1.0)
                edge_count += 1

    # ── Rule 2: TEMPORAL_OVERLAP (same asset, within 30 days) ────────────────
    for asset_id, asset_facts in by_asset.items():
        timed = [f for f in asset_facts if f["timestamp"]]
        timed.sort(key=lambda x: x["timestamp"])
        window = timedelta(days=TEMPORAL_WINDOW_DAYS)
        for i, fa in enumerate(timed):
            ts_a = datetime.fromisoformat(str(fa["timestamp"]).replace(" ", "T")[:19])
            for fb in timed[i + 1:]:
                ts_b = datetime.fromisoformat(str(fb["timestamp"]).replace(" ", "T")[:19])
                if ts_b - ts_a > window:
                    break
                if fa["doc_id"] != fb["doc_id"]:
                    _upsert_edge(session, fa["fact_id"], fb["fact_id"],
                                 "TEMPORAL_OVERLAP", source_fact_id=fa["fact_id"])
                    edge_count += 1

    # ── Rule 3: CROSS_REFERENCE (doc IDs mentioned in source_spans) ──────────
    for f in facts:
        span_data = f.get("source_span") or ""
        try:
            span_text = json.loads(span_data).get("text", span_data)
        except (json.JSONDecodeError, AttributeError):
            span_text = span_data
        for ref_doc_id in _DOCREF_RE.findall(span_text):
            if ref_doc_id != f["doc_id"]:
                _upsert_edge(session, f["doc_id"], ref_doc_id,
                             "CROSS_REFERENCE", source_fact_id=f["fact_id"])
                edge_count += 1

    # ── Rule 4: CAUSAL_SEQUENCE (precursor → incident on connected assets) ────
    precursor_facts = [f for f in facts if f["fact_type"] in PRECURSOR_TYPES and f["timestamp"]]
    incident_facts  = [f for f in facts if f["fact_type"] == "INCIDENT_EVENT" and f["timestamp"]]

    # Build a quick asset adjacency map: assets that share a doc are "connected"
    asset_cooccur: dict[str, set[str]] = defaultdict(set)
    for doc_facts in by_doc.values():
        doc_assets = {f["asset_id"] for f in doc_facts if f["asset_id"]}
        for a in doc_assets:
            asset_cooccur[a].update(doc_assets - {a})

    window = timedelta(days=90)  # wider window for causal chain
    for pf in precursor_facts:
        ts_p = datetime.fromisoformat(str(pf["timestamp"]).replace(" ", "T")[:19])
        for inf in incident_facts:
            # Same asset OR connected asset
            same_or_adjacent = (
                pf["asset_id"] == inf["asset_id"] or
                (inf["asset_id"] and inf["asset_id"] in asset_cooccur.get(pf["asset_id"] or "", set()))
            )
            if not same_or_adjacent:
                continue
            ts_i = datetime.fromisoformat(str(inf["timestamp"]).replace(" ", "T")[:19])
            if timedelta(0) <= ts_i - ts_p <= window:
                _upsert_edge(session, pf["fact_id"], inf["fact_id"],
                             "CAUSAL_SEQUENCE", source_fact_id=pf["fact_id"],
                             weight=1.5)
                edge_count += 1

    session.flush()
    print(f"[graph_builder] {edge_count} edges derived and persisted")


def load_networkx_graph(session: Session) -> nx.Graph:
    """Build and return a NetworkX graph from the edges + asset/doc nodes in DB."""
    from sqlalchemy import text as sq_text

    G = nx.Graph()

    # Add asset nodes
    assets = session.execute(sq_text(
        "SELECT asset_id, name, type, location FROM assets"
    )).fetchall()
    for a in assets:
        G.add_node(a[0], label=a[1], node_type="asset",
                   asset_type=a[2], location=a[3])

    # Add document nodes
    docs = session.execute(sq_text(
        "SELECT doc_id, type, upload_date FROM documents"
    )).fetchall()
    for d in docs:
        G.add_node(d[0], label=d[0], node_type="document", doc_type=d[1],
                   upload_date=str(d[2]))

    # Add edges
    edges = session.execute(sq_text(
        "SELECT from_id, to_id, relation_type, weight FROM edges"
    )).fetchall()
    for e in edges:
        G.add_edge(e[0], e[1], relation=e[2], weight=e[3])

    print(f"[graph_builder] NetworkX graph: {G.number_of_nodes()} nodes, "
          f"{G.number_of_edges()} edges")
    return G


def save_graph(G: nx.Graph, path: str = GRAPH_PATH):
    """Persist graph to JSON node-link format."""
    data = nx.node_link_data(G)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, default=str, indent=2)
    print(f"[graph_builder] Graph saved → {path}")


def load_graph(path: str = GRAPH_PATH) -> nx.Graph:
    """Reload graph from JSON (fast path for API startup)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return nx.node_link_graph(data)
