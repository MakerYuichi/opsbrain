"""
routers/ingest_router.py — upload heterogeneous documents + trigger re-indexing
"""
import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

SUPPORTED = {".txt", ".pdf", ".xlsx", ".xls", ".csv", ".eml",
             ".png", ".jpg", ".jpeg", ".pid", ".md"}


class IngestStatus(BaseModel):
    status: str
    message: str
    formats_supported: list[str]


def _run_incremental_ingest(file_paths: list[str]):
    """Background: parse new files, extract facts, update graph + vector index."""
    from parser import parse_file
    from entity_extractor import extract_facts, _make_client
    from entity_resolver import EntityResolver
    from fact_builder import SyncSession, init_sync_db, upsert_asset, upsert_document, insert_facts
    from graph_builder import build_edges, load_networkx_graph, save_graph
    from rag_retriever import build_index_from_session

    init_sync_db()
    client = _make_client()
    resolver = EntityResolver()

    with SyncSession() as session:
        for fp in file_paths:
            doc = parse_file(fp)
            facts = extract_facts(doc, client)
            resolved = {}
            for i, f in enumerate(facts):
                raw_ids = list(f.get("asset_ids", []))
                if doc.asset_hint:
                    raw_ids.append(doc.asset_hint)
                resolved[i] = resolver.resolve_all(raw_ids)

            for rec in resolver.all_records():
                upsert_asset(session, rec.asset_id, rec.name, rec.type, rec.location, rec.aliases)

            upsert_document(session, doc.doc_id, doc.doc_type, doc.source_path, doc.raw_text)
            insert_facts(session, doc.doc_id, doc.raw_text, facts, resolved)

        session.commit()

        build_edges(session)
        session.commit()
        G = load_networkx_graph(session)
        save_graph(G)
        build_index_from_session(session)


@router.get("/formats", response_model=IngestStatus)
def list_formats():
    from doc_formats import supported_extensions
    return IngestStatus(
        status="ok",
        message="Heterogeneous ingestion supports PDF, spreadsheets, email, OCR images, P&ID exports, and plain text.",
        formats_supported=sorted(supported_extensions()),
    )


@router.post("/upload")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(400, "No files uploaded")

    saved: list[str] = []
    for uf in files:
        ext = Path(uf.filename or "").suffix.lower()
        if ext not in SUPPORTED:
            raise HTTPException(400, f"Unsupported format: {ext}. Supported: {sorted(SUPPORTED)}")

        dest = UPLOAD_DIR / (uf.filename or f"upload{ext}")
        content = await uf.read()
        dest.write_bytes(content)
        saved.append(str(dest.resolve()))

    background_tasks.add_task(_run_incremental_ingest, saved)
    return {
        "status": "accepted",
        "files": [Path(p).name for p in saved],
        "message": f"{len(saved)} file(s) queued for ingestion (parse → extract → graph → RAG index)",
    }


@router.post("/reindex")
def reindex_vectors():
    from rag_retriever import build_index_from_session
    from fact_builder import SyncSession

    with SyncSession() as session:
        n = build_index_from_session(session)
    return {"status": "ok", "chunks_indexed": n}
