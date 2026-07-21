"""
Industrial Knowledge Intelligence Platform - FastAPI Backend
Entry point. Features (ingestion, graph, Time Machine, Pattern Breaker, Graph Explorer)
will be added in subsequent phases.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Industrial Knowledge Intelligence API",
    description="Unified industrial document intelligence with Time Machine, Pattern Breaker, and Graph Explorer",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
