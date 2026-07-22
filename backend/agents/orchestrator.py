"""
agents/orchestrator.py — route natural-language tasks to the appropriate agent.
"""
from __future__ import annotations

import re

from agents.compliance_agent import run_compliance
from agents.maintenance_agent import run_maintenance
from agents.rca_agent import run_rca

_ASSET_RE = re.compile(r"\b([A-Z]{2,5}-\d{1,4})\b")


def _extract_asset(text: str) -> str | None:
    m = _ASSET_RE.search(text.upper())
    return m.group(1) if m else None


def classify_task(task: str) -> str:
    t = task.lower()
    if any(w in t for w in ("root cause", "rca", "why did", "why was", "explosion", "incident", "failure")):
        return "rca"
    if any(w in t for w in ("compliance", "regulatory", "permit", "oisd", "peso", "factory act", "audit gap")):
        return "compliance"
    if any(w in t for w in ("maintenance", "schedule", "work order", "deferred", "predictive")):
        return "maintenance"
    return "rca"  # default


def run_agent_task(task: str, asset_id: str | None = None) -> dict:
    agent_type = classify_task(task)
    aid = asset_id or _extract_asset(task)

    if agent_type == "rca":
        if not aid:
            aid = "APS-3"  # sensible demo default
        return {**run_rca(aid, task), "task": task, "routed_to": "rca"}

    if agent_type == "compliance":
        return {**run_compliance(aid), "task": task, "routed_to": "compliance"}

    if agent_type == "maintenance":
        return {**run_maintenance(aid), "task": task, "routed_to": "maintenance"}

    return {"error": "Unknown agent type", "task": task}
