"""
routers/mobile.py — mobile/field technician API endpoints.

Optimized for field use cases:
- Quick asset lookup by tag or QR scan
- Offline-capable critical data sync
- Simplified incident reporting
- Equipment status summaries
- Urgent alerts and safety notifications
"""
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from fact_builder import SyncSession

router = APIRouter(prefix="/mobile", tags=["Mobile"])


class AssetLookupRequest(BaseModel):
    asset_id: Optional[str] = None
    qr_code: Optional[str] = None


class IncidentReportRequest(BaseModel):
    asset_id: str
    incident_type: str
    description: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    reported_by: str
    location: Optional[str] = None


class StatusCheckRequest(BaseModel):
    asset_id: str


@router.get("/asset/{asset_id}")
def get_mobile_asset_info(asset_id: str):
    """
    Get simplified asset information for mobile view.
    Includes critical status, recent alerts, and quick actions.
    """
    with SyncSession() as session:
        # Asset basic info
        asset = session.execute(
            text("""
                SELECT asset_id, name, type, location, aliases
                FROM assets WHERE asset_id = :aid
            """),
            {"aid": asset_id.upper()},
        ).fetchone()

        if not asset:
            raise HTTPException(404, f"Asset {asset_id} not found")

        # Recent facts (last 10)
        recent_facts = session.execute(
            text("""
                SELECT fact_id, fact_type, content, timestamp, confidence
                FROM facts
                WHERE asset_id = :aid
                ORDER BY timestamp DESC NULLS LAST
                LIMIT 10
            """),
            {"aid": asset_id.upper()},
        ).fetchall()

        # Active alerts
        alerts = session.execute(
            text("""
                SELECT alert_id, pattern_type, description, confidence, created_at
                FROM alerts
                WHERE asset_id = :aid
                ORDER BY created_at DESC
                LIMIT 5
            """),
            {"aid": asset_id.upper()},
        ).fetchall()

        # Sensor status (latest reading)
        sensor_status = session.execute(
            text("""
                SELECT sensor_id, metric, value, unit, status, timestamp
                FROM sensor_readings
                WHERE asset_id = :aid
                ORDER BY timestamp DESC
                LIMIT 1
            """),
            {"aid": asset_id.upper()},
        ).fetchone()

        # Deferred maintenance count
        maint_count = session.execute(
            text("""
                SELECT COUNT(*)
                FROM facts
                WHERE asset_id = :aid AND fact_type = 'DEFERRED_MAINTENANCE'
            """),
            {"aid": asset_id.upper()},
        ).scalar()

    return {
        "asset": {
            "asset_id": asset[0],
            "name": asset[1],
            "type": asset[2],
            "location": asset[3],
            "aliases": asset[4],
        },
        "status": {
            "sensor_status": {
                "sensor_id": sensor_status[0],
                "metric": sensor_status[1],
                "value": sensor_status[2],
                "unit": sensor_status[3],
                "status": sensor_status[4],
                "last_reading": str(sensor_status[5]) if sensor_status else None,
            }
            if sensor_status
            else None,
            "deferred_maintenance_count": maint_count or 0,
            "has_active_alerts": len(alerts) > 0,
        },
        "recent_activity": [
            {
                "fact_id": f[0],
                "type": f[1],
                "content": f[2][:100] + "..." if len(f[2]) > 100 else f[2],
                "timestamp": str(f[3]) if f[3] else None,
                "confidence": float(f[4]) if f[4] else None,
            }
            for f in recent_facts
        ],
        "active_alerts": [
            {
                "alert_id": a[0],
                "pattern_type": a[1],
                "description": a[2],
                "confidence": float(a[3]) if a[3] else 0.0,
                "created_at": str(a[4]),
            }
            for a in alerts
        ],
        "quick_actions": [
            {"action": "report_incident", "label": "Report Incident"},
            {"action": "view_maintenance", "label": "View Maintenance"},
            {"action": "check_compliance", "label": "Check Compliance"},
            {"action": "scan_qr", "label": "Scan QR Code"},
        ],
    }


@router.post("/lookup")
def quick_asset_lookup(req: AssetLookupRequest):
    """
    Quick asset lookup by tag ID or QR code.
    Returns minimal info for fast field identification.
    """
    identifier = req.asset_id or req.qr_code
    if not identifier:
        raise HTTPException(400, "Either asset_id or qr_code required")

    with SyncSession() as session:
        asset = session.execute(
            text("""
                SELECT asset_id, name, type, location
                FROM assets
                WHERE asset_id = :id OR aliases LIKE :id_pattern
                LIMIT 1
            """),
            {"id": identifier.upper(), "id_pattern": f"%{identifier}%"},
        ).fetchone()

        if not asset:
            raise HTTPException(404, f"Asset {identifier} not found")

        # Check for critical alerts
        critical_alerts = session.execute(
            text("""
                SELECT COUNT(*)
                FROM alerts
                WHERE asset_id = :aid AND severity = 'CRITICAL' AND status = 'ACTIVE'
            """),
            {"aid": asset[0]},
        ).scalar()

    return {
        "asset_id": asset[0],
        "name": asset[1],
        "type": asset[2],
        "location": asset[3],
        "has_critical_alerts": (critical_alerts or 0) > 0,
        "status": "CRITICAL" if (critical_alerts or 0) > 0 else "NORMAL",
    }


@router.post("/incident")
def report_incident(req: IncidentReportRequest):
    """
    Submit a field incident report.
    Creates a fact record and triggers alert if severity is HIGH/CRITICAL.
    """
    with SyncSession() as session:
        # Verify asset exists
        asset = session.execute(
            text("SELECT asset_id FROM assets WHERE asset_id = :aid"),
            {"aid": req.asset_id.upper()},
        ).fetchone()

        if not asset:
            raise HTTPException(404, f"Asset {req.asset_id} not found")

        # Insert incident fact
        fact_id = f"INC-{req.asset_id.upper()}-{int(time.time())}"
        session.execute(
            text("""
                INSERT INTO facts (fact_id, content, source_span, doc_id, confidence, asset_id, fact_type, timestamp)
                VALUES (:fid, :content, :span, :doc, :conf, :aid, :ftype, datetime('now'))
            """),
            {
                "fid": fact_id,
                "content": f"Field incident report: {req.description}",
                "span": '{"source": "mobile_app", "reported_by": "' + req.reported_by + '"}',
                "doc": f"MOBILE-{req.asset_id}",
                "conf": 0.95,
                "aid": req.asset_id.upper(),
                "ftype": "INCIDENT_EVENT",
            },
        )

        # Create alert if high severity
        if req.severity in ("HIGH", "CRITICAL"):
            alert_id = f"ALT-{fact_id}"
            session.execute(
                text("""
                    INSERT INTO alerts (alert_id, alert_type, severity, message, asset_id, status, created_at)
                    VALUES (:aid, :atype, :sev, :msg, :asset, 'ACTIVE', datetime('now'))
                """),
                {
                    "aid": alert_id,
                    "atype": "FIELD_INCIDENT",
                    "sev": req.severity,
                    "msg": f"Field incident reported: {req.incident_type} - {req.description}",
                    "asset": req.asset_id.upper(),
                },
            )

        session.commit()

    return {
        "status": "submitted",
        "fact_id": fact_id,
        "severity": req.severity,
        "alert_created": req.severity in ("HIGH", "CRITICAL"),
        "message": "Incident report submitted successfully",
    }


@router.post("/status")
def get_asset_status(req: StatusCheckRequest):
    """
    Get current asset status summary for field technicians.
    Focuses on operational status and immediate concerns.
    """
    with SyncSession() as session:
        # Get latest sensor readings
        sensors = session.execute(
            text("""
                SELECT sensor_id, metric, value, unit, status, timestamp
                FROM sensor_readings
                WHERE asset_id = :aid AND timestamp >= datetime('now', '-24 hours')
                ORDER BY timestamp DESC
                LIMIT 5
            """),
            {"aid": req.asset_id.upper()},
        ).fetchall()

        # Get recent maintenance status
        maint_status = session.execute(
            text("""
                SELECT fact_type, content, timestamp
                FROM facts
                WHERE asset_id = :aid AND fact_type IN ('DEFERRED_MAINTENANCE', 'WORK_ORDER', 'MAINTENANCE_ACTION')
                ORDER BY timestamp DESC NULLS LAST
                LIMIT 3
            """),
            {"aid": req.asset_id.upper()},
        ).fetchall()

        # Check for any safety violations
        safety_issues = session.execute(
            text("""
                SELECT COUNT(*)
                FROM facts
                WHERE asset_id = :aid AND fact_type IN ('SAFETY_VIOLATION', 'ALARM_RESPONSE')
                AND timestamp >= datetime('now', '-7 days')
            """),
            {"aid": req.asset_id.upper()},
        ).scalar()

    # Determine overall status
    has_faults = any(s[4] in ("FAULT", "WARN") for s in sensors)
    has_deferred = any(m[0] == "DEFERRED_MAINTENANCE" for m in maint_status)
    has_safety_issues = (safety_issues or 0) > 0

    if has_safety_issues:
        overall_status = "CRITICAL"
    elif has_faults:
        overall_status = "WARNING"
    elif has_deferred:
        overall_status = "ATTENTION"
    else:
        overall_status = "NORMAL"

    return {
        "asset_id": req.asset_id.upper(),
        "overall_status": overall_status,
        "sensor_summary": [
            {
                "sensor_id": s[0],
                "metric": s[1],
                "value": s[2],
                "unit": s[3],
                "status": s[4],
                "last_reading": str(s[5]),
            }
            for s in sensors
        ],
        "maintenance_summary": [
            {
                "type": m[0],
                "content": m[1][:80] + "..." if len(m[1]) > 80 else m[1],
                "timestamp": str(m[2]) if m[2] else None,
            }
            for m in maint_status
        ],
        "safety_issues_last_7_days": safety_issues or 0,
        "recommended_actions": _get_mobile_recommendations(overall_status, has_faults, has_deferred),
    }


def _get_mobile_recommendations(status: str, has_faults: bool, has_deferred: bool) -> List[str]:
    """Generate context-aware recommendations for field technicians."""
    actions = []

    if status == "CRITICAL":
        actions.extend([
            "Immediate safety assessment required",
            "Do not proceed with operations",
            "Contact supervisor immediately",
            "Document all observations",
        ])
    elif status == "WARNING":
        actions.extend([
            "Check sensor readings",
            "Review fault indicators",
            "Consider operational adjustments",
        ])
    elif status == "ATTENTION":
        actions.extend([
            "Review deferred maintenance items",
            "Schedule maintenance window",
            "Monitor equipment closely",
        ])
    else:
        actions.extend([
            "Continue normal operations",
            "Perform routine checks",
        ])

    if has_faults:
        actions.append("Investigate sensor faults")

    if has_deferred:
        actions.append("Address deferred maintenance")

    return actions


@router.get("/alerts")
def get_mobile_alerts(asset_id: Optional[str] = None, limit: int = 10):
    """
    Get active alerts for mobile view.
    Can filter by asset or get all facility-wide alerts.
    """
    with SyncSession() as session:
        if asset_id:
            alerts = session.execute(
                text("""
                    SELECT alert_id, pattern_type, description, confidence, asset_id, created_at
                    FROM alerts
                    WHERE asset_id = :aid
                    ORDER BY created_at DESC
                    LIMIT :lim
                """),
                {"aid": asset_id.upper(), "lim": limit},
            ).fetchall()
        else:
            alerts = session.execute(
                text("""
                    SELECT alert_id, pattern_type, description, confidence, asset_id, created_at
                    FROM alerts
                    ORDER BY created_at DESC
                    LIMIT :lim
                """),
                {"lim": limit},
            ).fetchall()

    return {
        "alerts": [
            {
                "alert_id": a[0],
                "pattern_type": a[1],
                "description": a[2],
                "confidence": float(a[3]) if a[3] else 0.0,
                "asset_id": a[4],
                "created_at": str(a[5]),
            }
            for a in alerts
        ],
        "total_count": len(alerts),
    }


@router.get("/sync/critical")
def get_critical_sync_data():
    """
    Get critical data for offline sync.
    Returns essential asset info, active alerts, and recent incidents.
    Optimized for mobile bandwidth constraints.
    """
    with SyncSession() as session:
        # Critical assets (those with alerts)
        critical_assets = session.execute(
            text("""
                SELECT DISTINCT a.asset_id, a.name, a.type, a.location
                FROM assets a
                JOIN alerts al ON a.asset_id = al.asset_id
            """)
        ).fetchall()

        # All active alerts
        alerts = session.execute(
            text("""
                SELECT alert_id, pattern_type, description, confidence, asset_id, created_at
                FROM alerts
                ORDER BY created_at DESC
            """)
        ).fetchall()

        # Recent incidents (last 24 hours)
        recent_incidents = session.execute(
            text("""
                SELECT fact_id, asset_id, content, timestamp
                FROM facts
                WHERE fact_type = 'INCIDENT_EVENT'
                AND timestamp >= datetime('now', '-24 hours')
                ORDER BY timestamp DESC
            """)
        ).fetchall()

    return {
        "sync_timestamp": "datetime('now')",
        "critical_assets": [
            {"asset_id": a[0], "name": a[1], "type": a[2], "location": a[3]}
            for a in critical_assets
        ],
        "active_alerts": [
            {
                "alert_id": a[0],
                "pattern_type": a[1],
                "description": a[2],
                "confidence": float(a[3]) if a[3] else 0.0,
                "asset_id": a[4],
                "created_at": str(a[5]),
            }
            for a in alerts
        ],
        "recent_incidents": [
            {
                "fact_id": a[0],
                "asset_id": a[1],
                "content": a[2][:100] + "..." if len(a[2]) > 100 else a[2],
                "timestamp": str(a[3]),
            }
            for a in recent_incidents
        ],
        "data_size_estimate": "compressed_for_mobile",
    }


# Import time for incident ID generation
import time
