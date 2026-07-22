"""
agents/compliance_agent.py — Regulatory compliance gap detection agent.

Maps Factory Act, OISD, PESO, environmental, and quality requirements against
current facts, permits, and equipment states.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from agents.base import call_llm, retrieve_context, span_text
from fact_builder import SyncSession

RULES_PATH = Path(__file__).parent.parent.parent / "data" / "compliance_rules.json"

SYSTEM = """You are a regulatory compliance analyst for Indian heavy industry.
Given compliance rules and matching evidence facts, identify GAPS where
requirements are not met.

For each gap provide:
- regulation ID and name
- severity (CRITICAL / HIGH / MEDIUM)
- gap description (what is missing or violated)
- supporting fact citations [FACT-ID]
- recommended remediation

Only flag gaps supported by evidence. If a requirement appears satisfied, note COMPLIANT."""


def _load_rules() -> list[dict]:
    with open(RULES_PATH, encoding="utf-8") as f:
        return json.load(f)["regulations"]


def _match_facts_for_rule(session, rule: dict, asset_id: str | None) -> list[tuple]:
    forbidden = rule.get("forbidden_patterns", [])
    keywords = rule.get("evidence_keywords", [])
    applies_types = rule.get("applies_to_types", [])

    asset_clause = ""
    params: dict = {}
    if asset_id:
        asset_clause = "AND f.asset_id = :aid"
        params["aid"] = asset_id
    elif applies_types:
        ph = ",".join(f":t{i}" for i in range(len(applies_types)))
        for i, t in enumerate(applies_types):
            params[f"t{i}"] = t
        asset_clause = f"AND a.type IN ({ph})"

    type_ph = ",".join(f"'{t}'" for t in forbidden) if forbidden else "'RISK_OBSERVATION'"

    kw_clause = ""
    if keywords:
        kw_parts = " OR ".join(f"UPPER(f.content) LIKE :kw{i}" for i in range(len(keywords)))
        for i, kw in enumerate(keywords):
            params[f"kw{i}"] = f"%{kw.upper()}%"
        kw_clause = f"AND ({kw_parts})"

    rows = session.execute(text(f"""
        SELECT f.fact_id, f.content, f.source_span, f.doc_id, f.confidence,
               f.asset_id, f.fact_type, a.type as asset_type
        FROM facts f
        LEFT JOIN assets a ON f.asset_id = a.asset_id
        WHERE f.fact_type IN ({type_ph})
        {asset_clause}
        {kw_clause}
        ORDER BY f.confidence DESC
        LIMIT 15
    """), params).fetchall()
    return rows


def _get_permit_facts(session, asset_id: str | None = None) -> list[dict]:
    """Extract permit-related facts with expiration information."""
    permit_types = ["PERMIT_STATUS", "PERMIT_TO_WORK", "ENVIRONMENTAL_CLEARANCE"]

    asset_clause = "AND f.asset_id = :aid" if asset_id else ""
    params = {"aid": asset_id} if asset_id else {}

    rows = session.execute(text(f"""
        SELECT f.fact_id, f.content, f.source_span, f.doc_id, f.asset_id,
               f.fact_type, f.timestamp, d.raw_text
        FROM facts f
        LEFT JOIN documents d ON f.doc_id = d.doc_id
        WHERE f.fact_type IN ('PERMIT_STATUS', 'PERMIT_TO_WORK', 'ENVIRONMENTAL_CLEARANCE')
        {asset_clause}
        ORDER BY f.timestamp DESC NULLS LAST
        LIMIT 20
    """), params).fetchall()

    permits = []
    for r in rows:
        permit_info = {
            "fact_id": r[0],
            "content": r[1],
            "asset_id": r[4],
            "permit_type": r[5],
            "timestamp": str(r[6]) if r[6] else None,
            "document_text": r[7],
        }

        # Extract expiration date from content or document text
        import re
        date_patterns = [
            r"valid\s+until\s*:?\s*(\d{4}-\d{2}-\d{2})",
            r"expiry\s*:?\s*(\d{4}-\d{2}-\d{2})",
            r"expires?\s*:?\s*(\d{4}-\d{2}-\d{2})",
            r"valid\s+through\s*:?\s*(\d{4}-\d{2}-\d{2})",
        ]

        text_to_search = f"{r[1]} {r[7] or ''}"
        for pattern in date_patterns:
            match = re.search(pattern, text_to_search, re.IGNORECASE)
            if match:
                permit_info["expiration_date"] = match.group(1)
                break

        # Check if expired
        if permit_info.get("expiration_date"):
            from datetime import datetime
            try:
                exp_date = datetime.strptime(permit_info["expiration_date"], "%Y-%m-%d")
                permit_info["is_expired"] = exp_date < datetime.utcnow()
            except ValueError:
                permit_info["is_expired"] = None
        else:
            permit_info["is_expired"] = None

        permits.append(permit_info)

    return permits


def run_compliance(asset_id: str | None = None, facility: str | None = None) -> dict:
    rules = _load_rules()
    gaps: list[dict] = []
    compliant: list[dict] = []

    with SyncSession() as session:
        # Get permit facts for expiration checking
        permit_facts = _get_permit_facts(session, asset_id)

        # Check for expired permits
        expired_permits = [p for p in permit_facts if p.get("is_expired") is True]
        if expired_permits:
            gaps.append({
                "reg_id": "PERMIT-EXPIRATION",
                "name": "Permit Expiration Check",
                "authority": "Regulatory",
                "requirement": "All permits must be valid and current",
                "severity": "CRITICAL",
                "evidence": [
                    {
                        "fact_id": p["fact_id"],
                        "content": f"Expired permit: {p['permit_type']} - expired on {p.get('expiration_date', 'unknown')}",
                        "fact_type": p["permit_type"],
                        "asset_id": p["asset_id"],
                        "source_span": p["content"],
                    }
                    for p in expired_permits
                ],
            })

        for rule in rules:
            rows = _match_facts_for_rule(session, rule, asset_id)
            if not rows:
                compliant.append({
                    "reg_id": rule["reg_id"],
                    "name": rule["name"],
                    "status": "NO_EVIDENCE",
                    "note": "No matching violation facts found (may indicate compliance or missing data)",
                })
                continue

            # Gap detected if forbidden fact types present
            violation_facts = [
                r for r in rows
                if r[6] in rule.get("forbidden_patterns", [])
            ]
            if violation_facts:
                gaps.append({
                    "reg_id": rule["reg_id"],
                    "name": rule["name"],
                    "authority": rule["authority"],
                    "requirement": rule["requirement"],
                    "severity": "CRITICAL" if "DEFERRED" in str(violation_facts[0][6]) else "HIGH",
                    "evidence": [
                        {
                            "fact_id": r[0],
                            "content": r[1],
                            "fact_type": r[6],
                            "asset_id": r[5],
                            "source_span": span_text(r[2]),
                        }
                        for r in violation_facts[:5]
                    ],
                })
            else:
                compliant.append({
                    "reg_id": rule["reg_id"],
                    "name": rule["name"],
                    "status": "COMPLIANT",
                    "evidence_count": len(rows),
                })

    # RAG enrichment for narrative
    query = f"compliance regulatory permit safety violation {asset_id or facility or ''}"
    rag_rows, retrieval_meta = retrieve_context(query, asset_ids=[asset_id] if asset_id else None, limit=10)
    rag_context = "\n".join(f"[{r[0]}] {r[1]}" for r in rag_rows)

    rules_summary = json.dumps(gaps, indent=2)
    permit_summary = json.dumps([{"permit_type": p["permit_type"], "asset_id": p["asset_id"], "is_expired": p.get("is_expired")} for p in permit_facts], indent=2)
    narrative = call_llm(SYSTEM, f"""COMPLIANCE GAPS DETECTED:
{rules_summary}

PERMIT STATUS:
{permit_summary}

ADDITIONAL RAG CONTEXT:
{rag_context}

Produce a compliance gap report with remediation priorities.""")

    return {
        "agent": "compliance",
        "asset_id": asset_id,
        "facility": facility,
        "gaps": gaps,
        "compliant": compliant,
        "gap_count": len(gaps),
        "permit_facts": permit_facts,
        "expired_permits": len(expired_permits),
        "report": narrative,
        "retrieval_meta": retrieval_meta,
        "generated_at": datetime.utcnow().isoformat(),
    }
