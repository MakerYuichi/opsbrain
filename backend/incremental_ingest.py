"""
incremental_ingest.py — framework for incremental and streaming document ingestion.

Provides:
- Change detection for existing documents
- Event-driven processing hooks
- Incremental graph updates
- Queue-based processing interface
- Real-time document monitoring
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from fact_builder import SyncSession


@dataclass
class DocumentChange:
    """Represents a detected change in a document."""
    document_path: str
    previous_hash: Optional[str]
    current_hash: str
    change_type: str  # "added", "modified", "deleted"
    timestamp: str
    metadata: dict


@dataclass
class IngestionEvent:
    """Represents an ingestion event for queue processing."""
    event_id: str
    document_path: str
    event_type: str  # "new_document", "document_update", "document_delete"
    priority: int  # 1-10, 1 = highest
    payload: dict
    created_at: str
    processed: bool = False
    processed_at: Optional[str] = None


class ChangeDetector:
    """Detects changes in documents using file hashing."""

    def __init__(self, state_file: str = ".document_hashes.json"):
        self.state_file = Path(state_file)
        self.hashes: dict[str, str] = self._load_state()

    def _load_state(self) -> dict[str, str]:
        """Load previous file hashes from state file."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {}

    def _save_state(self):
        """Save current file hashes to state file."""
        with open(self.state_file, "w") as f:
            json.dump(self.hashes, f, indent=2)

    def _compute_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file contents."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def detect_changes(self, directory: str) -> list[DocumentChange]:
        """
        Scan directory and detect changes since last check.

        Returns list of DocumentChange objects.
        """
        changes = []
        current_files = set()

        for file_path in Path(directory).rglob("*"):
            if not file_path.is_file():
                continue

            # Skip certain files
            if file_path.name.startswith(".") or file_path.suffix in [".pyc", ".pyo"]:
                continue

            rel_path = str(file_path.relative_to(directory))
            current_files.add(rel_path)

            current_hash = self._compute_hash(file_path)
            previous_hash = self.hashes.get(rel_path)

            if previous_hash is None:
                # New file
                changes.append(DocumentChange(
                    document_path=rel_path,
                    previous_hash=None,
                    current_hash=current_hash,
                    change_type="added",
                    timestamp=datetime.utcnow().isoformat(),
                    metadata={"size": file_path.stat().st_size},
                ))
            elif previous_hash != current_hash:
                # Modified file
                changes.append(DocumentChange(
                    document_path=rel_path,
                    previous_hash=previous_hash,
                    current_hash=current_hash,
                    change_type="modified",
                    timestamp=datetime.utcnow().isoformat(),
                    metadata={"size": file_path.stat().st_size},
                ))

        # Check for deleted files
        for old_path in self.hashes:
            if old_path not in current_files:
                changes.append(DocumentChange(
                    document_path=old_path,
                    previous_hash=self.hashes[old_path],
                    current_hash="",
                    change_type="deleted",
                    timestamp=datetime.utcnow().isoformat(),
                    metadata={},
                ))

        # Update state
        self.hashes = {rel_path: self._compute_hash(Path(directory) / rel_path) for rel_path in current_files}
        self._save_state()

        return changes


class EventQueue:
    """In-memory queue for ingestion events (can be replaced with RabbitMQ/Kafka)."""

    def __init__(self):
        self.events: list[IngestionEvent] = []
        self.processing = False

    def enqueue(self, event: IngestionEvent):
        """Add event to queue, sorted by priority."""
        self.events.append(event)
        self.events.sort(key=lambda e: e.priority)

    def dequeue(self) -> Optional[IngestionEvent]:
        """Get next event from queue."""
        if not self.events:
            return None
        return self.events.pop(0)

    def peek(self) -> Optional[IngestionEvent]:
        """Look at next event without removing."""
        return self.events[0] if self.events else None

    def size(self) -> int:
        """Get queue size."""
        return len(self.events)

    def clear(self):
        """Clear all events."""
        self.events.clear()


class IncrementalIngester:
    """Manages incremental ingestion with change detection and event processing."""

    def __init__(self, docs_dir: str, state_file: str = ".document_hashes.json"):
        self.docs_dir = Path(docs_dir)
        self.change_detector = ChangeDetector(state_file)
        self.event_queue = EventQueue()
        self.running = False

    def scan_for_changes(self) -> list[DocumentChange]:
        """Scan document directory for changes."""
        if not self.docs_dir.exists():
            return []

        changes = self.change_detector.detect_changes(str(self.docs_dir))

        # Convert changes to ingestion events
        for change in changes:
            if change.change_type == "deleted":
                event = IngestionEvent(
                    event_id=f"evt-{int(time.time())}-{change.document_path.replace('/', '-')}",
                    document_path=change.document_path,
                    event_type="document_delete",
                    priority=5,
                    payload={"previous_hash": change.previous_hash},
                    created_at=change.timestamp,
                )
            else:
                event = IngestionEvent(
                    event_id=f"evt-{int(time.time())}-{change.document_path.replace('/', '-')}",
                    document_path=change.document_path,
                    event_type="new_document" if change.change_type == "added" else "document_update",
                    priority=3,  # New/updated documents get medium priority
                    payload={
                        "file_hash": change.current_hash,
                        "metadata": change.metadata,
                    },
                    created_at=change.timestamp,
                )
            self.event_queue.enqueue(event)

        return changes

    def process_next_event(self) -> Optional[dict]:
        """
        Process next event from queue.

        Returns processing result or None if queue empty.
        """
        event = self.event_queue.dequeue()
        if not event:
            return None

        try:
            result = self._process_event(event)
            event.processed = True
            event.processed_at = datetime.utcnow().isoformat()
            return result
        except Exception as e:
            return {
                "event_id": event.event_id,
                "status": "error",
                "error": str(e),
                "document_path": event.document_path,
            }

    def _process_event(self, event: IngestionEvent) -> dict:
        """Process a single ingestion event."""
        from parser import parse_file
        from entity_extractor import extract_facts, _make_client
        from entity_resolver import EntityResolver
        from fact_builder import (
            SyncSession, init_sync_db, upsert_asset,
            upsert_document, insert_facts
        )
        from graph_builder import build_edges
        from rag_retriever import build_index_from_session

        full_path = self.docs_dir / event.document_path

        if event.event_type == "document_delete":
            # Handle document deletion
            with SyncSession() as session:
                doc_id = full_path.stem
                session.execute(
                    text("DELETE FROM facts WHERE doc_id = :doc_id"),
                    {"doc_id": doc_id}
                )
                session.execute(
                    text("DELETE FROM documents WHERE doc_id = :doc_id"),
                    {"doc_id": doc_id}
                )
                session.commit()

            return {
                "event_id": event.event_id,
                "status": "deleted",
                "document_path": event.document_path,
                "doc_id": doc_id,
            }

        # Handle new/updated documents
        doc = parse_file(full_path)
        client = _make_client()
        facts = extract_facts(doc, client)
        resolver = EntityResolver()

        resolved = {}
        for i, f in enumerate(facts):
            raw_ids = list(f.get("asset_ids", []))
            if doc.asset_hint:
                raw_ids.append(doc.asset_hint)
            resolved[i] = resolver.resolve_all(raw_ids)

        init_sync_db()

        with SyncSession() as session:
            # Delete old facts if this is an update
            if event.event_type == "document_update":
                session.execute(
                    text("DELETE FROM facts WHERE doc_id = :doc_id"),
                    {"doc_id": doc.doc_id}
                )

            for rec in resolver.all_records():
                upsert_asset(session, rec.asset_id, rec.name,
                             rec.type, rec.location, rec.aliases)

            upsert_document(session, doc.doc_id, doc.doc_type,
                            doc.source_path, doc.raw_text)
            fids = insert_facts(session, doc.doc_id, doc.raw_text,
                               facts, resolved)

            build_edges(session)
            session.commit()

            # Rebuild vector index for affected document
            build_index_from_session(session)

        return {
            "event_id": event.event_id,
            "status": "processed",
            "event_type": event.event_type,
            "document_path": event.document_path,
            "doc_id": doc.doc_id,
            "facts_extracted": len(facts),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def start_background_monitor(self, interval_seconds: int = 30):
        """
        Start background monitoring for document changes.

        This would typically run in a separate thread or process.
        For production, replace with file system watcher (watchdog) or message queue.
        """
        import threading

        def monitor_loop():
            while self.running:
                try:
                    changes = self.scan_for_changes()
                    if changes:
                        print(f"[IncrementalIngester] Detected {len(changes)} changes")
                except Exception as e:
                    print(f"[IncrementalIngester] Monitor error: {e}")
                time.sleep(interval_seconds)

        self.running = True
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()

    def stop_background_monitor(self):
        """Stop background monitoring."""
        self.running = False

    def get_queue_status(self) -> dict:
        """Get current queue status."""
        return {
            "queue_size": self.event_queue.size(),
            "next_event": self.event_queue.peek().event_id if self.event_queue.peek() else None,
            "monitoring": self.running,
        }


class StreamingIngester:
    """
    Streaming ingestion interface for large documents.

    Processes documents in chunks to avoid memory issues.
    """

    def __init__(self):
        self.chunk_size = 10000  # characters per chunk

    def stream_extract_entities(self, document_path: str) -> list[dict]:
        """
        Stream entity extraction for large documents.

        Yields entities as they are extracted rather than waiting for full document.
        """
        from doc_formats import extract_text
        from entity_extractor import extract_facts, _make_client

        doc = extract_text(document_path)
        text = doc.raw_text

        # Split into chunks
        chunks = [
            text[i:i + self.chunk_size]
            for i in range(0, len(text), self.chunk_size)
        ]

        client = _make_client()
        all_entities = []

        for i, chunk in enumerate(chunks):
            # Create a temporary document for this chunk
            from parser import ParsedDocument
            temp_doc = ParsedDocument(
                doc_id=f"{doc.source_path}-chunk-{i}",
                doc_type="streaming_chunk",
                facility="unknown",
                asset_hint="",
                doc_date=None,
                source_path=doc.source_path,
                raw_text=chunk,
            )

            try:
                entities = extract_facts(temp_doc, client)
                all_entities.extend(entities)
                yield {
                    "chunk_index": i,
                    "chunk_size": len(chunk),
                    "entities_found": len(entities),
                    "progress": (i + 1) / len(chunks) * 100,
                }
            except Exception as e:
                yield {
                    "chunk_index": i,
                    "error": str(e),
                    "progress": (i + 1) / len(chunks) * 100,
                }

        return all_entities


def setup_watchdog_monitor(docs_dir: str, event_callback):
    """
    Set up file system watcher for real-time change detection.

    Requires: pip install watchdog

    This is a production-ready alternative to polling-based change detection.
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class DocumentHandler(FileSystemEventHandler):
            def __init__(self, callback):
                self.callback = callback

            def on_created(self, event):
                if not event.is_directory:
                    self.callback({
                        "type": "created",
                        "path": event.src_path,
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            def on_modified(self, event):
                if not event.is_directory:
                    self.callback({
                        "type": "modified",
                        "path": event.src_path,
                        "timestamp": datetime.utcnow().isoformat(),
                    })

            def on_deleted(self, event):
                if not event.is_directory:
                    self.callback({
                        "type": "deleted",
                        "path": event.src_path,
                        "timestamp": datetime.utcnow().isoformat(),
                    })

        event_handler = DocumentHandler(event_callback)
        observer = Observer()
        observer.schedule(event_handler, docs_dir, recursive=True)
        observer.start()

        return observer
    except ImportError:
        print("[setup_watchdog_monitor] watchdog not installed. Install with: pip install watchdog")
        return None


# Example usage
if __name__ == "__main__":
    # Example 1: Change detection and processing
    ingester = IncrementalIngester("../data/synthetic_docs")

    print("Scanning for changes...")
    changes = ingester.scan_for_changes()
    print(f"Found {len(changes)} changes")

    print("Processing queue...")
    while ingester.event_queue.size() > 0:
        result = ingester.process_next_event()
        print(f"Processed: {result}")

    # Example 2: Streaming extraction for large documents
    # streamer = StreamingIngester()
    # for progress in streamer.stream_extract_entities("large_document.pdf"):
    #     print(f"Progress: {progress['progress']:.1f}%")
