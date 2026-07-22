"""
routers/agents.py — Agentic workflow API (RCA, Compliance, Maintenance, Orchestrator)
"""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from agents.compliance_agent import run_compliance
from agents.maintenance_agent import run_maintenance
from agents.orchestrator import run_agent_task
from agents.rca_agent import run_rca

router = APIRouter(prefix="/agents", tags=["Agents"])


class AgentRequest(BaseModel):
    asset_id: Optional[str] = None
    task: Optional[str] = None
    incident_description: Optional[str] = None
    facility: Optional[str] = None


class OrchestratorRequest(BaseModel):
    task: str
    asset_id: Optional[str] = None


@router.post("/rca")
def agent_rca(req: AgentRequest):
    if not req.asset_id:
        raise HTTPException(400, "asset_id required for RCA")
    return run_rca(req.asset_id, req.incident_description or req.task or "")


@router.post("/compliance")
def agent_compliance(req: AgentRequest):
    return run_compliance(req.asset_id, req.facility)


@router.post("/maintenance")
def agent_maintenance(req: AgentRequest):
    return run_maintenance(req.asset_id)


@router.post("/run")
def agent_orchestrator(req: OrchestratorRequest):
    if not req.task.strip():
        raise HTTPException(400, "task description required")
    return run_agent_task(req.task, req.asset_id)


@router.get("/capabilities")
def agent_capabilities():
    return {
        "agents": [
            {
                "id": "rca",
                "name": "Root Cause Analysis Agent",
                "endpoint": "POST /agents/rca",
                "description": "Fuses work orders, failure records, OEM manuals, sensors, and causal graph edges into structured RCA.",
            },
            {
                "id": "compliance",
                "name": "Regulatory Compliance Agent",
                "endpoint": "POST /agents/compliance",
                "description": "Maps Factory Act, OISD, PESO, environmental, and quality requirements against current facts and permits.",
            },
            {
                "id": "maintenance",
                "name": "Maintenance Intelligence Agent",
                "endpoint": "POST /agents/maintenance",
                "description": "Prioritized maintenance schedule from deferred work, open WOs, and sensor anomalies.",
            },
            {
                "id": "orchestrator",
                "name": "Task Orchestrator",
                "endpoint": "POST /agents/run",
                "description": "Routes natural-language tasks to the appropriate specialist agent.",
            },
        ]
    }
