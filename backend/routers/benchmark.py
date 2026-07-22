"""
routers/benchmark.py — benchmark execution API endpoints.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from benchmark import BenchmarkSuite, run_benchmark_suite

router = APIRouter(prefix="/benchmark", tags=["Benchmark"])


class BenchmarkRequest(BaseModel):
    quick: bool = False
    export: bool = True


@router.post("/run")
def run_benchmark(req: BenchmarkRequest, background_tasks: BackgroundTasks):
    """
    Run the full benchmark suite or quick benchmark.
    Can export results to file in the background.
    """
    if req.quick:
        suite = BenchmarkSuite()
        suite.benchmark_search_performance(["test query"])
        suite.benchmark_system_capacity()
        results = {
            "status": "complete",
            "mode": "quick",
            "results_count": len(suite.results),
            "results": [
                {
                    "benchmark": r.benchmark_name,
                    "metric": r.metric_name,
                    "value": r.value,
                    "unit": r.unit,
                }
                for r in suite.results
            ],
        }
    else:
        results = run_benchmark_suite()
        results["mode"] = "full"

    if req.export:
        background_tasks.add_task(
            lambda: BenchmarkSuite().export_report(
                "/Users/sanchiagarwal/VS_Code/hackathon/benchmark_report.json"
            )
        )
        results["export_scheduled"] = True

    return results


@router.get("/report")
def get_benchmark_report():
    """Get the latest benchmark report if available."""
    from pathlib import Path
    import json

    report_path = Path("/Users/sanchiagarwal/VS_Code/hackathon/benchmark_report.json")
    if not report_path.exists():
        raise HTTPException(404, "No benchmark report found. Run /benchmark/run first.")

    with open(report_path) as f:
        return json.load(f)


@router.get("/summary")
def get_benchmark_summary():
    """Get a summary of benchmark capabilities."""
    return {
        "benchmarks_available": [
            {
                "id": "search_performance",
                "name": "Search Performance",
                "description": "Measures query latency, result quality, and compares to manual baseline",
                "metrics": ["avg_latency_ms", "avg_results_per_query", "avg_confidence_score"],
            },
            {
                "id": "pattern_detection",
                "name": "Pattern Detection",
                "description": "Evaluates precision, recall, and F1 score against known patterns",
                "metrics": ["avg_precision", "avg_recall", "avg_f1_score"],
            },
            {
                "id": "agent_workflows",
                "name": "Agent Workflows",
                "description": "Measures execution time and success rate for RCA, compliance, and maintenance agents",
                "metrics": ["rca_execution_time_ms", "compliance_execution_time_ms", "maintenance_execution_time_ms"],
            },
            {
                "id": "system_capacity",
                "name": "System Capacity",
                "description": "Measures database size, index size, and overall system capacity",
                "metrics": ["total_facts", "total_assets", "index_size_mb"],
            },
        ],
        "baseline_comparisons": {
            "search_latency": "7.5x faster than manual keyword search",
            "pattern_precision": "Baseline: 20% random matching",
            "agent_execution": "Compared to manual analysis time",
        },
    }
