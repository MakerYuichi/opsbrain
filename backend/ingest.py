"""
ingest.py — end-to-end ingestion pipeline runner.

Usage:
    python ingest.py                   # full run
    python ingest.py --skip-extract    # skip Groq API calls, use cache
    python ingest.py --sample          # print Fact/Edge tables after run
    python ingest.py --reset           # wipe DB + cache before running
"""
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT       = Path(__file__).parent
DATA_DIR   = ROOT.parent / "data"
DOCS_DIR   = DATA_DIR / "synthetic_docs"
SENSOR_DIR = DATA_DIR / "sensor_readings"
CACHE_FILE = ROOT / ".extraction_cache.json"


# ── Stages ────────────────────────────────────────────────────────────────────

def stage_parse(docs_dir: Path):
    from parser import parse_directory
    docs = parse_directory(docs_dir)
    print(f"\n[ingest] Stage 1 — Parsed {len(docs)} documents")
    return docs


def stage_extract(docs, skip_cache: bool):
    from entity_extractor import extract_all, _make_client

    if not skip_cache and CACHE_FILE.exists():
        print(f"\n[ingest] Stage 2 — Using extraction cache ({CACHE_FILE.name})")
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)

    print(f"\n[ingest] Stage 2 — Extracting facts via Groq ({len(docs)} docs)…")
    client  = _make_client()
    results = extract_all(docs, client)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"[ingest] Cache saved → {CACHE_FILE.name}")
    return results


def stage_resolve(docs, extraction: dict):
    from entity_resolver import EntityResolver
    resolver = EntityResolver()
    print(f"\n[ingest] Stage 3 — Resolving entities…")

    resolved = {}
    for doc in docs:
        facts = extraction.get(doc.doc_id, [])
        resolved[doc.doc_id] = {}
        for i, f in enumerate(facts):
            raw_ids = list(f.get("asset_ids", []))
            if doc.asset_hint:
                raw_ids.append(doc.asset_hint)
            resolved[doc.doc_id][i] = resolver.resolve_all(raw_ids)

    total = sum(len(v) for d in resolved.values() for v in d.values())
    print(f"[ingest] Resolved {total} asset links")
    return resolver, resolved


def stage_persist(docs, extraction, resolver, resolved_map, sensor_dir: Path):
    from fact_builder import (
        init_sync_db, SyncSession, upsert_asset,
        upsert_document, insert_facts, load_sensor_csvs,
    )

    print(f"\n[ingest] Stage 4 — Persisting to SQLite…")
    init_sync_db()

    with SyncSession() as session:
        for rec in resolver.all_records():
            upsert_asset(session, rec.asset_id, rec.name,
                         rec.type, rec.location, rec.aliases)
        session.flush()
        print(f"[ingest]   {len(resolver.all_records())} assets upserted")

        total_facts = 0
        for doc in docs:
            upsert_document(session, doc.doc_id, doc.doc_type,
                            doc.source_path, doc.raw_text)
            fids = insert_facts(
                session, doc.doc_id, doc.raw_text,
                extraction.get(doc.doc_id, []),
                resolved_map.get(doc.doc_id, {}),
            )
            total_facts += len(fids)
        session.flush()
        print(f"[ingest]   {total_facts} fact rows inserted")

        sr = load_sensor_csvs(session, sensor_dir, resolver)
        print(f"[ingest]   {sr} sensor reading rows inserted")

        session.commit()
        print(f"[ingest]   Committed ✓")


def stage_graph():
    from fact_builder import SyncSession
    from graph_builder import build_edges, load_networkx_graph, save_graph

    print(f"\n[ingest] Stage 5 — Building knowledge graph…")
    with SyncSession() as session:
        build_edges(session)
        session.commit()
        G = load_networkx_graph(session)
    save_graph(G)
    return G


def stage_index_vectors():
    from fact_builder import SyncSession
    from rag_retriever import build_index_from_session

    print(f"\n[ingest] Stage 6 — Building RAG vector index…")
    with SyncSession() as session:
        n = build_index_from_session(session)
    print(f"[ingest]   Indexed {n} fact chunks")
    return n


def print_sample():
    from fact_builder import SyncSession
    from sqlalchemy import text

    print("\n" + "═" * 72)
    print("FACT TABLE SAMPLE  (earliest 10 by timestamp)")
    print("═" * 72)
    with SyncSession() as session:
        rows = session.execute(text(
            "SELECT fact_id, asset_id, fact_type, timestamp, "
            "       substr(content,1,75) AS content, confidence "
            "FROM facts ORDER BY timestamp NULLS LAST LIMIT 10"
        )).fetchall()
        for r in rows:
            print(f"  id        : {r[0]}")
            print(f"  asset     : {r[1]}")
            print(f"  type      : {r[2]}")
            print(f"  timestamp : {r[3]}")
            print(f"  content   : {r[4]}")
            print(f"  confidence: {r[5]:.2f}")
            print()

    print("═" * 72)
    print("EDGE TABLE SAMPLE  (top 10 by weight)")
    print("═" * 72)
    with SyncSession() as session:
        rows = session.execute(text(
            "SELECT from_id, to_id, relation_type, weight "
            "FROM edges ORDER BY weight DESC LIMIT 10"
        )).fetchall()
        for r in rows:
            print(f"  {r[0][:34]:34s} → {r[1][:34]:34s}  [{r[2]}]  w={r[3]:.1f}")

    print()
    print("═" * 72)
    print("TABLE COUNTS")
    print("═" * 72)
    with SyncSession() as session:
        for tbl in ("assets", "documents", "facts", "edges", "sensor_readings", "alerts"):
            n = session.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
            print(f"  {tbl:20s}: {n}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Industrial KI ingestion pipeline")
    ap.add_argument("--docs-dir",     default=str(DOCS_DIR))
    ap.add_argument("--sensor-dir",   default=str(SENSOR_DIR))
    ap.add_argument("--skip-extract", action="store_true",
                    help="Use cached extraction JSON (skip Groq API calls)")
    ap.add_argument("--sample",       action="store_true",
                    help="Print Fact/Edge sample after run")
    ap.add_argument("--reset",        action="store_true",
                    help="Delete DB and cache before running")
    ap.add_argument("--skip-index",   action="store_true",
                    help="Skip RAG vector index build")
    args = ap.parse_args()

    if args.reset:
        db_path = Path(os.getenv("DATABASE_URL", "sqlite:///./industrial_ki.db")
                       .replace("sqlite:///", ""))
        for p in [db_path, CACHE_FILE]:
            if p.exists():
                p.unlink()
                print(f"[ingest] Deleted {p}")
        from vector_store import reset_index
        reset_index()
        print("[ingest] Vector index reset")

    docs                    = stage_parse(Path(args.docs_dir))
    extraction              = stage_extract(docs, args.skip_extract)
    resolver, resolved_map  = stage_resolve(docs, extraction)
    stage_persist(docs, extraction, resolver, resolved_map, Path(args.sensor_dir))
    stage_graph()
    if not args.skip_index:
        stage_index_vectors()

    print("\n[ingest] ✓ Pipeline complete.")
    if args.sample:
        print_sample()


if __name__ == "__main__":
    main()
