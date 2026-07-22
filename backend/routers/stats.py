from fastapi import APIRouter
from sqlalchemy import text
from fact_builder import SyncSession

router = APIRouter(prefix="/stats", tags=["Stats"])

@router.get("")
def get_stats():
    with SyncSession() as session:
        counts = {}
        for table in ("assets", "documents", "facts", "edges", "sensor_readings", "alerts"):
            counts[table] = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()

        # alerts table stores risk level inside the description field prefixed [CRITICAL] etc.
        critical_count = session.execute(text(
            "SELECT COUNT(*) FROM alerts WHERE description LIKE '[CRITICAL]%'"
        )).scalar()

        facilities = session.execute(
            text("SELECT DISTINCT location FROM assets WHERE location IS NOT NULL")
        ).fetchall()

    return {
        "asset_count":          counts["assets"],
        "document_count":       counts["documents"],
        "fact_count":           counts["facts"],
        "edge_count":           counts["edges"],
        "sensor_reading_count": counts["sensor_readings"],
        "alert_count":          counts["alerts"],
        "critical_alert_count": critical_count,
        "facilities":           [f[0] for f in facilities],
    }
 