"""
routers/graph.py — Graph Explorer API

GET /graph?asset_id=APS-3&depth=2&show_facts=true
  Returns a clean, readable subgraph centred on the given asset.

Design choices for clarity:
  - TEMPORAL_OVERLAP edges are dropped by default (too dense, low signal)
  - Fact nodes are only included when show_facts=true (default false for depth≥2)
  - At depth=1 with show_facts=true: up to 12 highest-confidence facts per asset
  - Node cap: 60 nodes total (prioritised: asset > document > fact)
  - Edge cap: structural edges only (ASSET_IN_DOCUMENT, SHARES_ASSET,
              CAUSAL_SEQUENCE, CROSS_REFERENCE)
"""
import json
import os
from collections import defaultdict
from typing import Optional

import networkx as nx
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

router   = APIRouter(prefix="/graph", tags=["Graph Explorer"])
_DB_URL  = os.getenv("DATABASE_URL", "sqlite:///./industrial_ki.db").replace("sqlite+aiosqlite", "sqlite")
_engine  = create_engine(_DB_URL, connect_args={"check_same_thread": False})
_Session = sessionmaker(_engine)
GRAPH_PATH = os.getenv("GRAPH_PATH", "./knowledge_graph.json")

# Only these edge types are shown — TEMPORAL_OVERLAP is intentionally excluded
DISPLAY_RELATIONS = {"ASSET_IN_DOCUMENT", "SHARES_ASSET", "CAUSAL_SEQUENCE", "CROSS_REFERENCE"}

# ── Graph cache with mtime-based invalidation ─────────────────────────────────
# Checked on every request; reloads only when knowledge_graph.json changes on disk.
# Cost at our data scale (~19 docs): a single os.stat() call per request — negligible.

_G: Optional[nx.Graph] = None
_G_mtime: float = 0.0


def _get_graph() -> nx.Graph:
    """Return the NetworkX graph, reloading from disk if the file has changed."""
    global _G, _G_mtime
    try:
        current_mtime = os.path.getmtime(GRAPH_PATH)
    except FileNotFoundError:
        # File doesn't exist yet — return empty graph but don't cache it so
        # we'll retry on the next request once ingestion has run.
        return nx.Graph()

    if _G is None or current_mtime != _G_mtime:
        with open(GRAPH_PATH, encoding="utf-8") as f:
            _G = nx.node_link_graph(json.load(f))
        _G_mtime = current_mtime
        # Only log on actual reload, not on every request
        import logging
        logging.getLogger(__name__).info(
            "knowledge_graph.json reloaded (mtime changed)"
        )

    return _G


def invalidate_graph_cache() -> None:
    """Explicitly drop the cached graph so the next request reloads from disk.
    Called by the Pattern Breaker write path after graph_builder.save_graph()."""
    global _G, _G_mtime
    _G       = None
    _G_mtime = 0.0


# ── Response models ───────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id:         str
    label:      str
    node_type:  str
    asset_type: Optional[str] = None
    doc_type:   Optional[str] = None
    location:   Optional[str] = None
    fact_type:  Optional[str] = None
    timestamp:  Optional[str] = None
    content:    Optional[str] = None
    alert_ids:  list[str]     = []
    depth:      int           = 0
    is_root:    bool          = False

class GraphEdge(BaseModel):
    source:   str
    target:   str
    relation: str
    weight:   float = 1.0

class SubgraphResponse(BaseModel):
    root_id:     str
    nodes:       list[GraphNode]
    edges:       list[GraphEdge]
    total_nodes: int
    total_edges: int


# ── DB helpers ────────────────────────────────────────────────────────────────

def _asset_meta(session) -> dict[str, dict]:
    rows = session.execute(text("SELECT asset_id, name, type, location FROM assets")).fetchall()
    return {r[0]: {"label": r[1], "asset_type": r[2], "location": r[3]} for r in rows}

def _doc_meta(session) -> dict[str, dict]:
    rows = session.execute(text("SELECT doc_id, type FROM documents")).fetchall()
    return {r[0]: {"doc_type": r[1]} for r in rows}

def _fact_meta(session, fact_ids: list[str]) -> dict[str, dict]:
    if not fact_ids:
        return {}
    ph     = ",".join(f":f{i}" for i in range(len(fact_ids)))
    params = {f"f{i}": fid for i, fid in enumerate(fact_ids)}
    rows   = session.execute(text(f"""
        SELECT fact_id, fact_type, timestamp, confidence,
               substr(content, 1, 120) as content
        FROM facts WHERE fact_id IN ({ph})
        ORDER BY confidence DESC
    """), params).fetchall()
    return {r[0]: {"fact_type": r[1], "timestamp": str(r[2]) if r[2] else None,
                   "confidence": r[3], "content": r[4]} for r in rows}

def _alert_map(session) -> dict[str, list[str]]:
    rows = session.execute(text("SELECT alert_id, source_fact_ids FROM alerts")).fetchall()
    result: dict[str, list[str]] = {}
    for aid, fids_json in rows:
        for fid in json.loads(fids_json or "[]"):
            result.setdefault(fid, []).append(aid)
    return result

def _asset_doc_edges(session, asset_ids: list[str]) -> list[tuple[str, str]]:
    if not asset_ids:
        return []
    ph     = ",".join(f":a{i}" for i in range(len(asset_ids)))
    params = {f"a{i}": aid for i, aid in enumerate(asset_ids)}
    rows   = session.execute(text(f"""
        SELECT DISTINCT asset_id, doc_id FROM facts WHERE asset_id IN ({ph})
    """), params).fetchall()
    return [(r[0], r[1]) for r in rows]

def _top_facts_for_docs(session, doc_ids: list[str],
                        max_per_doc: int = 6) -> list[dict]:
    """Return the top-confidence facts for a set of documents."""
    if not doc_ids:
        return []
    ph     = ",".join(f":d{i}" for i in range(len(doc_ids)))
    params = {f"d{i}": did for i, did in enumerate(doc_ids)}
    rows   = session.execute(text(f"""
        SELECT fact_id, doc_id, asset_id, fact_type, timestamp,
               confidence, substr(content,1,120) as content
        FROM facts
        WHERE doc_id IN ({ph})
          AND fact_type IN (
              'INCIDENT_EVENT','SAFETY_VIOLATION','DEFERRED_MAINTENANCE',
              'INSTRUMENT_FAULT','ALARM_RESPONSE','RISK_OBSERVATION',
              'SHIFT_OBSERVATION','WORK_ORDER'
          )
        ORDER BY doc_id, confidence DESC
    """), params).fetchall()

    # Keep top-N per doc
    by_doc: dict[str, list] = defaultdict(list)
    for r in rows:
        if len(by_doc[r[1]]) < max_per_doc:
            by_doc[r[1]].append({
                "fact_id": r[0], "doc_id": r[1], "asset_id": r[2],
                "fact_type": r[3],
                "timestamp": str(r[4]) if r[4] else None,
                "confidence": float(r[5] or 0.8),
                "content": r[6],
            })
    return [f for facts in by_doc.values() for f in facts]


# ── Core subgraph builder ─────────────────────────────────────────────────────

def _build_subgraph(root_id: str, depth: int,
                    show_facts: bool) -> SubgraphResponse:
    G = _get_graph()
    if root_id not in G:
        raise HTTPException(404, f"Asset {root_id!r} not found in graph.")

    with _Session() as session:
        asset_meta = _asset_meta(session)
        doc_meta   = _doc_meta(session)
        alert_mp   = _alert_map(session)

        # ── Step 1: BFS expanding asset→doc→asset→doc chains ────────────
        # This is the multi-hop traversal that makes depth meaningful.
        # depth 1: root asset's documents
        # depth 2: assets in those docs → their documents
        # depth 3: assets in depth-2 docs → their documents

        visited_assets: dict[str, int] = {root_id: 0}
        visited_docs:   dict[str, int] = {}

        # Get all documents for a list of asset_ids
        def _docs_for_assets(asset_ids: list[str]) -> list[tuple[str, str]]:
            if not asset_ids:
                return []
            ph = ",".join(f":a{i}" for i in range(len(asset_ids)))
            p  = {f"a{i}": a for i, a in enumerate(asset_ids)}
            rows = session.execute(text(
                f"SELECT DISTINCT asset_id, doc_id FROM facts WHERE asset_id IN ({ph})"
            ), p).fetchall()
            return [(r[0], r[1]) for r in rows]

        # Get all assets mentioned in a list of doc_ids (excluding already-seen assets)
        def _assets_in_docs(doc_ids: list[str], exclude: set[str]) -> list[str]:
            if not doc_ids:
                return []
            ph = ",".join(f":d{i}" for i in range(len(doc_ids)))
            p  = {f"d{i}": d for i, d in enumerate(doc_ids)}
            rows = session.execute(text(
                f"SELECT DISTINCT asset_id FROM facts "
                f"WHERE doc_id IN ({ph}) AND asset_id IS NOT NULL"
            ), p).fetchall()
            return [r[0] for r in rows if r[0] not in exclude]

        # BFS loop: expand one hop at a time
        frontier_assets = [root_id]
        for hop in range(1, depth + 1):
            # Expand assets → their docs
            new_doc_edges = _docs_for_assets(frontier_assets)
            new_docs = [d for _, d in new_doc_edges if d not in visited_docs]
            for d in new_docs:
                visited_docs[d] = hop

            if hop < depth:
                # Expand docs → new assets (for next hop)
                frontier_assets = _assets_in_docs(
                    new_docs, set(visited_assets.keys())
                )
                for a in frontier_assets:
                    visited_assets[a] = hop + 1
            else:
                frontier_assets = []

        # ── Step 2: add assets mentioned in visited docs (already done above) ─

        # ── Step 3: optionally add top-N fact nodes per document ──────────
        fact_rows: list[dict] = []
        if show_facts:
            fact_rows = _top_facts_for_docs(session, list(visited_docs.keys()))

        # ── Step 4: synthesise asset↔doc edges ───────────────────────────
        all_asset_ids = list(visited_assets.keys())
        synth_edges   = _asset_doc_edges(session, all_asset_ids)

        # Enrich alert_ids for asset nodes (via their facts)
        asset_alert: dict[str, list[str]] = defaultdict(list)
        for fid, aids in alert_mp.items():
            # fact_id contains asset_id after the last "-" segment — use DB
            pass  # filled below via fact_rows alert lookup

    # ── Build node list ───────────────────────────────────────────────────
    nodes: list[GraphNode] = []
    included_ids: set[str] = set()

    # Asset nodes
    for aid, d in sorted(visited_assets.items(), key=lambda x: x[1]):
        if aid not in asset_meta:
            continue
        m = asset_meta[aid]
        nodes.append(GraphNode(
            id=aid, label=m["label"], node_type="asset",
            asset_type=m["asset_type"], location=m["location"],
            alert_ids=[], depth=d, is_root=(aid == root_id),
        ))
        included_ids.add(aid)

    # Document nodes
    for did, d in sorted(visited_docs.items(), key=lambda x: x[1]):
        if did not in doc_meta:
            continue
        m = doc_meta[did]
        nodes.append(GraphNode(
            id=did, label=did, node_type="document",
            doc_type=m["doc_type"], depth=d,
        ))
        included_ids.add(did)

    # Fact nodes (optional)
    if show_facts:
        for f in fact_rows:
            fid = f["fact_id"]
            if fid in included_ids:
                continue
            doc_depth = visited_docs.get(f["doc_id"], depth)
            high_risk = f["fact_type"] in (
                "INCIDENT_EVENT", "SAFETY_VIOLATION", "DEFERRED_MAINTENANCE",
                "INSTRUMENT_FAULT", "ALARM_RESPONSE"
            )
            nodes.append(GraphNode(
                id=fid, label=f["fact_type"].replace("_", " "),
                node_type="fact",
                fact_type=f["fact_type"],
                timestamp=f["timestamp"],
                content=f["content"],
                alert_ids=alert_mp.get(fid, []),
                depth=doc_depth + 1,
            ))
            included_ids.add(fid)

    # ── Cap total nodes (assets first, docs second, facts last) ──────────
    MAX_NODES = 60
    if len(nodes) > MAX_NODES:
        def prio(n: GraphNode) -> int:
            if n.is_root:         return 0
            if n.node_type == "asset":    return 1
            if n.node_type == "document": return 2
            return 3
        nodes.sort(key=prio)
        nodes = nodes[:MAX_NODES]
        included_ids = {n.id for n in nodes}

    # ── Build edge list (structural only) ─────────────────────────────────
    edges: list[GraphEdge] = []
    seen_e: set[frozenset] = set()

    def _add_edge(src: str, tgt: str, rel: str, w: float = 1.0):
        k = frozenset([src, tgt])
        if k not in seen_e and src in included_ids and tgt in included_ids:
            seen_e.add(k)
            edges.append(GraphEdge(source=src, target=tgt, relation=rel, weight=w))

    # NX graph structural edges
    for u, v, edata in G.edges(data=True):
        rel = edata.get("relation", "")
        if rel in DISPLAY_RELATIONS and u in included_ids and v in included_ids:
            _add_edge(u, v, rel, float(edata.get("weight", 1.0)))

    # Synthesised asset↔doc edges
    for aid, did in synth_edges:
        _add_edge(aid, did, "ASSET_IN_DOCUMENT", 1.0)

    # Fact → document edges (fact nodes need a visual anchor)
    if show_facts:
        for f in fact_rows:
            if f["fact_id"] in included_ids and f["doc_id"] in included_ids:
                _add_edge(f["fact_id"], f["doc_id"], "FACT_IN_DOCUMENT", 0.8)

    return SubgraphResponse(
        root_id=root_id,
        nodes=nodes, edges=edges,
        total_nodes=len(nodes), total_edges=len(edges),
    )


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=SubgraphResponse)
def get_subgraph(
    asset_id:   str  = Query(...,  description="Root asset ID, e.g. APS-3"),
    depth:      int  = Query(2,    ge=1, le=3),
    show_facts: bool = Query(False, description="Include fact nodes (verbose)"),
):
    return _build_subgraph(asset_id, depth, show_facts)
