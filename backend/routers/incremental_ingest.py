"""
routers/incremental_ingest.py — incremental ingestion API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from incremental_ingest import (
    IncrementalIngester,
    StreamingIngester,
    setup_watchdog_monitor,
)

router = APIRouter(prefix="/incremental", tags=["Incremental Ingestion"])

# Global ingester instance
_ingester: Optional[IncrementalIngester] = None


def get_ingester() -> IncrementalIngester:
    """Get or create global ingester instance."""
    global _ingester
    if _ingester is None:
        from pathlib import Path
        docs_dir = Path(__file__).parent.parent.parent / "data" / "synthetic_docs"
        _ingester = IncrementalIngester(str(docs_dir))
    return _ingester


class ScanRequest(BaseModel):
    docs_dir: Optional[str] = None


class ProcessRequest(BaseModel):
    max_events: int = 10


class MonitorRequest(BaseModel):
    interval_seconds: int = 30
    enable: bool = True


@router.post("/scan")
def scan_for_changes(req: ScanRequest):
    """
    Scan document directory for changes since last check.
    Returns detected changes and enqueues them for processing.
    """
    ingester = get_ingester()

    if req.docs_dir:
        from incremental_ingest import IncrementalIngester
        ingester = IncrementalIngester(req.docs_dir)

    changes = ingester.scan_for_changes()

    return {
        "changes_detected": len(changes),
        "changes": [
            {
                "document_path": c.document_path,
                "change_type": c.change_type,
                "timestamp": c.timestamp,
                "metadata": c.metadata,
            }
            for c in changes
        ],
        "queue_size": ingester.event_queue.size(),
    }


@router.post("/process")
def process_queue(req: ProcessRequest):
    """
    Process events from the ingestion queue.
    Processes up to max_events events and returns results.
    """
    ingester = get_ingester()

    results = []
    processed = 0

    while processed < req.max_events and ingester.event_queue.size() > 0:
        result = ingester.process_next_event()
        if result:
            results.append(result)
            processed += 1
        else:
            break

    return {
        "processed": processed,
        "remaining": ingester.event_queue.size(),
        "results": results,
    }


@router.get("/queue/status")
def get_queue_status():
    """Get current ingestion queue status."""
    ingester = get_ingester()
    return ingester.get_queue_status()


@router.post("/monitor")
def toggle_monitor(req: MonitorRequest, background_tasks: BackgroundTasks):
    """
    Enable or disable background file system monitoring.
    Uses polling-based change detection (watchdog available for production).
    """
    ingester = get_ingester()

    if req.enable:
        if not ingester.running:
            ingester.start_background_monitor(req.interval_seconds)
            return {
                "status": "monitoring_enabled",
                "interval_seconds": req.interval_seconds,
                "message": "Background monitoring started",
            }
        else:
            return {
                "status": "already_monitoring",
                "message": "Background monitoring already running",
            }
    else:
        ingester.stop_background_monitor()
        return {
            "status": "monitoring_disabled",
            "message": "Background monitoring stopped",
        }


@router.post("/stream")
def stream_extraction(document_path: str):
    """
    Stream entity extraction for a large document.
    Processes document in chunks to avoid memory issues.
    """
    streamer = StreamingIngester()

    try:
        results = []
        for progress in streamer.stream_extract_entities(document_path):
            results.append(progress)

        return {
            "document_path": document_path,
            "total_chunks": len(results),
            "progress_updates": results,
            "status": "completed",
        }
    except Exception as e:
        raise HTTPException(500, f"Streaming extraction failed: {str(e)}")


@router.get("/capabilities")
def get_capabilities():
    """Get incremental ingestion capabilities."""
    return {
        "change_detection": {
            "method": "file_hash_comparison",
            "state_file": ".document_hashes.json",
            "supported_events": ["added", "modified", "deleted"],
        },
        "queue_processing": {
            "type": "in_memory_priority_queue",
            "priorities": "1-10 (1=highest)",
            "can_replace_with": "RabbitMQ, AWS SQS, Kafka",
        },
        "streaming": {
            "chunk_size": 10000,
            "use_case": "large_documents",
            "yields": "progress_updates",
        },
        "monitoring": {
            "current": "polling_based",
            "production": "watchdog_file_system_watcher",
            "install": "pip install watchdog",
        },
    }


@router.post("/reset")
def reset_state():
    """Reset change detection state and clear queue."""
    ingester = get_ingester()
    ingester.event_queue.clear()
    ingester.change_detector.hashes.clear()
    ingester.change_detector._save_state()
    ingester.stop_background_monitor()

    return {
        "status": "reset",
        "message": "Change detection state and queue cleared",
    }
