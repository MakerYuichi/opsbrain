"""
vector_store.py — embedding index for hybrid RAG.

Primary:  ChromaDB persistent collection (sentence-transformers via chromadb default)
Fallback: SQLite + TF-IDF vectors (pure Python, any Python version)
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
COLLECTION = "industrial_facts"
FALLBACK_DB = os.getenv("EMBEDDING_FALLBACK_DB", "./embeddings_fallback.db")

_chroma_client = None
_collection = None
_use_chroma: Optional[bool] = None


@dataclass
class ScoredChunk:
    chunk_id: str
    text: str
    metadata: dict
    score: float
    source: str   # "vector" | "keyword" | "hybrid"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9\-_]{2,}", text.lower())


def _try_init_chroma():
    global _chroma_client, _collection, _use_chroma
    if _use_chroma is not None:
        return _use_chroma
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
        ef = embedding_functions.DefaultEmbeddingFunction()
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        _use_chroma = True
        print("[vector_store] Using ChromaDB")
    except Exception as e:
        print(f"[vector_store] ChromaDB unavailable ({e}) — using TF-IDF fallback")
        _use_chroma = False
    return _use_chroma


# ── TF-IDF fallback ─────────────────────────────────────────────────────────

def _init_fallback_db():
    conn = sqlite3.connect(FALLBACK_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id   TEXT PRIMARY KEY,
            text       TEXT NOT NULL,
            metadata   TEXT,
            tfidf_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS corpus_stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            doc_freq_json TEXT,
            total_docs INTEGER
        )
    """)
    conn.commit()
    return conn


def _compute_tfidf_vectors(chunks: list[tuple[str, str, dict]]) -> None:
    """chunks: [(chunk_id, text, metadata), ...]"""
    conn = _init_fallback_db()
    conn.execute("DELETE FROM chunks")
    conn.execute("DELETE FROM corpus_stats")

    doc_tokens = []
    for _, text, _ in chunks:
        doc_tokens.append(_tokenize(text))

    # Document frequency
    df: dict[str, int] = {}
    for tokens in doc_tokens:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1

    n = max(len(chunks), 1)
    for (chunk_id, text, meta), tokens in zip(chunks, doc_tokens):
        tf: dict[str, float] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        for t in tf:
            tf[t] /= max(len(tokens), 1)

        tfidf = {}
        for t, freq in tf.items():
            idf = math.log((n + 1) / (df.get(t, 0) + 1)) + 1
            tfidf[t] = freq * idf

        conn.execute(
            "INSERT INTO chunks (chunk_id, text, metadata, tfidf_json) VALUES (?,?,?,?)",
            (chunk_id, text, json.dumps(meta), json.dumps(tfidf)),
        )

    conn.execute(
        "INSERT INTO corpus_stats (id, doc_freq_json, total_docs) VALUES (1, ?, ?)",
        (json.dumps(df), n),
    )
    conn.commit()
    conn.close()
    print(f"[vector_store] TF-IDF index built: {len(chunks)} chunks")


def _cosine(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a.get(k, 0) * b.get(k, 0) for k in set(a) | set(b))
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _fallback_query(query: str, limit: int = 15) -> list[ScoredChunk]:
    conn = _init_fallback_db()
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    rows = conn.execute("SELECT doc_freq_json, total_docs FROM corpus_stats WHERE id=1").fetchone()
    if not rows:
        conn.close()
        return []

    df = json.loads(rows[0])
    n = rows[1]
    q_tf: dict[str, float] = {}
    for t in q_tokens:
        q_tf[t] = q_tf.get(t, 0) + 1
    for t in q_tf:
        q_tf[t] /= len(q_tokens)
    q_vec = {t: (q_tf[t] * (math.log((n + 1) / (df.get(t, 0) + 1)) + 1)) for t in q_tf}

    results = []
    for chunk_id, text, meta_json, tfidf_json in conn.execute(
        "SELECT chunk_id, text, metadata, tfidf_json FROM chunks"
    ):
        score = _cosine(q_vec, json.loads(tfidf_json))
        if score > 0:
            results.append(ScoredChunk(
                chunk_id=chunk_id,
                text=text,
                metadata=json.loads(meta_json or "{}"),
                score=score,
                source="vector",
            ))
    conn.close()
    results.sort(key=lambda x: -x.score)
    return results[:limit]


# ── Public API ────────────────────────────────────────────────────────────────

def index_facts(facts: list[dict]) -> int:
    """
    Index fact rows. Each fact dict needs:
      chunk_id, text, fact_id, doc_id, asset_id, confidence, fact_type
    """
    if not facts:
        return 0

    chunks = [
        (
            f["chunk_id"],
            f["text"],
            {k: f[k] for k in ("fact_id", "doc_id", "asset_id", "confidence", "fact_type") if k in f},
        )
        for f in facts
    ]

    if _try_init_chroma():
        ids = [c[0] for c in chunks]
        documents = [c[1] for c in chunks]
        metadatas = [c[2] for c in chunks]
        # Chroma upsert in batches
        batch = 100
        for i in range(0, len(ids), batch):
            _collection.upsert(
                ids=ids[i:i + batch],
                documents=documents[i:i + batch],
                metadatas=metadatas[i:i + batch],
            )
        print(f"[vector_store] ChromaDB indexed {len(facts)} chunks")
        return len(facts)

    _compute_tfidf_vectors(chunks)
    return len(facts)


def query_vectors(query: str, limit: int = 15, asset_filter: Optional[list[str]] = None) -> list[ScoredChunk]:
    if _try_init_chroma():
        where = None
        if asset_filter:
            where = {"asset_id": {"$in": asset_filter}}
        try:
            res = _collection.query(
                query_texts=[query],
                n_results=min(limit * 2, 30),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            out = []
            if res and res["ids"] and res["ids"][0]:
                for i, cid in enumerate(res["ids"][0]):
                    dist = res["distances"][0][i] if res["distances"] else 0
                    score = 1.0 - dist  # cosine distance → similarity
                    meta = res["metadatas"][0][i] if res["metadatas"] else {}
                    text = res["documents"][0][i] if res["documents"] else ""
                    out.append(ScoredChunk(cid, text, meta or {}, score, "vector"))
            out.sort(key=lambda x: -x.score)
            return out[:limit]
        except Exception as e:
            print(f"[vector_store] Chroma query failed: {e}")

    results = _fallback_query(query, limit * 2)
    if asset_filter:
        filt = set(asset_filter)
        results = [r for r in results if r.metadata.get("asset_id") in filt]
    return results[:limit]


def reset_index() -> None:
    global _collection, _use_chroma
    if _try_init_chroma():
        try:
            import chromadb
            _chroma_client.delete_collection(COLLECTION)
            _collection = None
            _use_chroma = None
            _try_init_chroma()
        except Exception:
            pass
    fb = Path(FALLBACK_DB)
    if fb.exists():
        fb.unlink()
