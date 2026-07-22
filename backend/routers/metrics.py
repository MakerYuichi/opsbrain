"""
routers/metrics.py — performance metrics and evaluation API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from metrics import (
    evaluate_pattern_detection,
    get_collector,
    timed_search,
)
from fact_builder import SyncSession
from sqlalchemy import text

router = APIRouter(prefix="/metrics", tags=["Metrics"])


class SearchBenchmarkRequest(BaseModel):
    query: str
    limit: int = 15


class AgentBenchmarkRequest(BaseModel):
    agent_type: str
    task: str


@router.get("/summary")
def get_metrics_summary():
    """Get comprehensive metrics summary."""
    collector = get_collector()
    return collector.export_metrics()


@router.get("/search")
def get_search_metrics():
    """Get search performance metrics."""
    collector = get_collector()
    return collector.get_search_summary()


@router.get("/patterns")
def get_pattern_metrics():
    """Get pattern detection metrics."""
    collector = get_collector()
    return collector.get_pattern_summary()


@router.get("/agents")
def get_agent_metrics():
    """Get agent workflow metrics."""
    collector = get_collector()
    return collector.get_agent_summary()


@router.post("/search/benchmark")
def benchmark_search(req: SearchBenchmarkRequest):
    """Run a single search benchmark and record metrics."""
    with SyncSession() as session:
        known = [r[0] for r in session.execute(text("SELECT asset_id FROM assets")).fetchall()]
        rows, retrieval_meta, elapsed_ms = timed_search(req.query, session, known, req.limit)

    return {
        "query": req.query,
        "retrieval_time_ms": round(elapsed_ms, 2),
        "results_count": len(rows),
        "retrieval_meta": retrieval_meta,
        "sources": [
            {
                "fact_id": r[0],
                "content": r[1][:100] + "..." if len(r[1]) > 100 else r[1],
                "confidence": float(r[4]) if r[4] else 0.0,
            }
            for r in rows[:5]
        ],
    }


@router.post("/patterns/evaluate")
def evaluate_patterns():
    """Run pattern detection evaluation against known patterns."""
    return evaluate_pattern_detection()


@router.post("/reset")
def reset_metrics():
    """Reset all collected metrics."""
    from metrics import _collector

    _collector.search_history.clear()
    _collector.pattern_history.clear()
    _collector.agent_history.clear()
    return {"status": "reset", "message": "All metrics cleared"}


@router.get("/live")
def get_live_metrics():
    """Get live system metrics."""
    collector = get_collector()

    with SyncSession() as session:
        total_facts = session.execute(text("SELECT COUNT(*) FROM facts")).scalar()
        total_assets = session.execute(text("SELECT COUNT(*) FROM assets")).scalar()
        total_docs = session.execute(text("SELECT COUNT(*) FROM documents")).scalar()

    return {
        "system_stats": {
            "total_facts": total_facts,
            "total_assets": total_assets,
            "total_documents": total_docs,
        },
        "performance": {
            "total_searches": len(collector.search_history),
            "avg_search_time_ms": round(
                sum(m.retrieval_time_ms for m in collector.search_history) / len(collector.search_history),
                2,
            )
            if collector.search_history
            else 0.0,
            "total_pattern_evaluations": len(collector.pattern_history),
            "total_agent_executions": len(collector.agent_history),
        },
        "last_updated": collector.search_history[-1].timestamp if collector.search_history else None,
    }
