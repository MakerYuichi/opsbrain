"""
rag_retriever.py — hybrid retrieval: vector RAG + SQL keyword + asset graph expansion.

Combines semantic similarity (embeddings) with structured filters for grounded chat
and agent workflows.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from vector_store import ScoredChunk, query_vectors

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "of", "in", "on", "at", "to",
    "for", "with", "by", "from", "about", "into", "what", "which", "who",
    "when", "where", "how", "why", "that", "this", "these", "those", "and",
    "or", "but", "not", "any", "all", "both", "each", "few", "more", "most",
    "other", "some", "such", "than", "then", "there", "they", "their", "them",
    "before", "after", "during", "over", "under", "warnings", "preceded",
    "caused", "happened", "show", "tell", "me", "us", "give", "list",
}


def _extract_keywords(question: str) -> list[str]:
    words = re.sub(r"[^a-zA-Z0-9\-_]", " ", question).split()
    return [w.upper() for w in words if len(w) >= 3 and w.lower() not in STOPWORDS]


def _extract_asset_ids(question: str, known: list[str]) -> list[str]:
    q_upper = question.upper()
    return [aid for aid in known if aid.upper() in q_upper]


def _connected_asset_ids(session: Session, asset_ids: list[str]) -> list[str]:
    if not asset_ids:
        return []
    ph = ",".join(f":a{i}" for i in range(len(asset_ids)))
    p = {f"a{i}": a for i, a in enumerate(asset_ids)}
    rows = session.execute(text(f"""
        SELECT DISTINCT f2.asset_id
        FROM facts f1 JOIN facts f2 ON f1.doc_id = f2.doc_id
        WHERE f1.asset_id IN ({ph})
          AND f2.asset_id IS NOT NULL
          AND f2.asset_id NOT IN ({ph})
    """), p).fetchall()
    return [r[0] for r in rows]


def _sql_keyword_retrieve(session: Session, keywords: list[str],
                          asset_ids: list[str], limit: int) -> list[tuple]:
    rows: list[tuple] = []
    if asset_ids:
        ph = ",".join(f":aa{i}" for i in range(len(asset_ids)))
        p = {f"aa{i}": a for i, a in enumerate(asset_ids)}
        p["lim"] = limit
        rows += session.execute(text(f"""
            SELECT fact_id, content, source_span, doc_id, confidence, asset_id
            FROM facts WHERE asset_id IN ({ph})
            ORDER BY confidence DESC LIMIT :lim
        """), p).fetchall()

    if keywords:
        like_cls = " OR ".join(f"UPPER(content) LIKE :k{i}" for i in range(len(keywords)))
        kp = {f"k{i}": f"%{kw}%" for i, kw in enumerate(keywords)}
        kp["lim2"] = limit
        krows = session.execute(text(f"""
            SELECT fact_id, content, source_span, doc_id, confidence, asset_id
            FROM facts WHERE {like_cls}
            ORDER BY confidence DESC LIMIT :lim2
        """), kp).fetchall()
        seen = {r[0] for r in rows}
        rows += [r for r in krows if r[0] not in seen]

    rows.sort(key=lambda r: -(r[4] or 0))
    return rows[:limit]


def _merge_results(
    vector_hits: list[ScoredChunk],
    sql_rows: list[tuple],
    session: Session,
    limit: int,
) -> list[tuple]:
    """
    Merge vector + SQL results into unified SQL-row tuples.
    Score = 0.6 * vector_score + 0.4 * confidence (normalized).
    """
    by_id: dict[str, dict] = {}

    for r in sql_rows:
        by_id[r[0]] = {"row": r, "vscore": 0.0, "conf": float(r[4] or 0)}

    for hit in vector_hits:
        fid = hit.metadata.get("fact_id") or hit.chunk_id
        if fid in by_id:
            by_id[fid]["vscore"] = max(by_id[fid]["vscore"], hit.score)
        else:
            # Fetch full row from DB
            row = session.execute(text("""
                SELECT fact_id, content, source_span, doc_id, confidence, asset_id
                FROM facts WHERE fact_id = :fid
            """), {"fid": fid}).fetchone()
            if row:
                by_id[fid] = {"row": row, "vscore": hit.score, "conf": float(row[4] or 0)}

    ranked = sorted(
        by_id.values(),
        key=lambda x: -(0.6 * x["vscore"] + 0.4 * x["conf"]),
    )
    return [x["row"] for x in ranked[:limit]]


def hybrid_retrieve(
    question: str,
    session: Session,
    known_assets: list[str],
    limit: int = 15,
    asset_filter: Optional[list[str]] = None,
) -> tuple[list[tuple], dict]:
    """
    Returns (fact_rows, retrieval_meta).
    Each row: (fact_id, content, source_span, doc_id, confidence, asset_id)
    """
    assets = asset_filter or _extract_asset_ids(question, known_assets)
    all_assets = list(set(assets + _connected_asset_ids(session, assets)))
    keywords = _extract_keywords(question)

    vector_hits = query_vectors(question, limit=limit, asset_filter=all_assets or None)
    sql_rows = _sql_keyword_retrieve(session, keywords, all_assets, limit)

    merged = _merge_results(vector_hits, sql_rows, session, limit)

    meta = {
        "retrieval": "hybrid_rag",
        "vector_hits": len(vector_hits),
        "keyword_hits": len(sql_rows),
        "merged": len(merged),
        "assets": all_assets,
    }
    return merged, meta


def build_index_from_session(session: Session) -> int:
    """Rebuild vector index from all facts in SQLite."""
    from vector_store import index_facts, reset_index

    reset_index()
    rows = session.execute(text("""
        SELECT fact_id, content, doc_id, asset_id, confidence, fact_type
        FROM facts
    """)).fetchall()

    chunks = []
    for r in rows:
        chunks.append({
            "chunk_id": r[0],
            "text": r[1],
            "fact_id": r[0],
            "doc_id": r[2],
            "asset_id": r[3] or "",
            "confidence": float(r[4] or 0),
            "fact_type": r[5],
        })
    return index_facts(chunks)
