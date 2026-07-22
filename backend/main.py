"""
Industrial Knowledge Intelligence Platform — FastAPI Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Industrial Knowledge Intelligence API",
    description="Time Machine, Pattern Breaker, Graph Explorer, Chat",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.timeline import router as timeline_router
from routers.patterns import router as patterns_router
from routers.graph    import router as graph_router
from routers.chat     import router as chat_router
from routers.stats    import router as stats_router
from routers.agents   import router as agents_router
from routers.ingest_router import router as ingest_router
from routers.validation import router as validation_router
from routers.metrics import router as metrics_router
from routers.mobile import router as mobile_router
from routers.benchmark import router as benchmark_router
from routers.evaluation import router as evaluation_router
from routers.incremental_ingest import router as incremental_ingest_router

app.include_router(timeline_router, tags=["Time Machine"])
app.include_router(patterns_router)
app.include_router(graph_router)
app.include_router(chat_router)
app.include_router(stats_router)
app.include_router(agents_router)
app.include_router(ingest_router)
app.include_router(validation_router)
app.include_router(metrics_router)
app.include_router(mobile_router)
app.include_router(benchmark_router)
app.include_router(evaluation_router)
app.include_router(incremental_ingest_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
