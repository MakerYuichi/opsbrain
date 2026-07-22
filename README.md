# Industrial Knowledge Intelligence Platform
**ET AI Hackathon 2.0 — Problem Statement #8**

Unifies fragmented industrial documents into a knowledge graph, then exposes:
- **Time Machine** — drag a timeline slider to see everything relevant to an asset on a given date
- **Pattern Breaker** — proactively surfaces recurring risk patterns across incidents
- **Graph Explorer** — visual node graph of how an asset connects to permits, logs, and records

Demo grounded in two real incidents: LG Polymers Vizag styrene leak (May 2020) and Vizag Steel Plant SMS-1 ladle explosion (June 2025).

---

## Stack
| Layer | Tech |
|-------|------|
| Backend | Python 3.11 + FastAPI |
| Storage | SQLite (SQLAlchemy) |
| Vector store | ChromaDB (local) with TF-IDF fallback |
| Graph | NetworkX |
| LLM | OpenRouter/Groq (Gemma-4) |
| Frontend | React 18 + TypeScript + Tailwind CSS |
| Graph viz | react-force-graph |

---

## Repo Structure

```
hackathon/
├── backend/
│   ├── main.py               # FastAPI app entry point
│   ├── database.py           # SQLite setup (async SQLAlchemy)
│   ├── requirements.txt
│   └── .env.example          # → copy to .env and add ANTHROPIC_API_KEY
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # Router + nav shell
│   │   ├── main.tsx
│   │   └── index.css         # Tailwind directives
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
├── data/
│   ├── synthetic_docs/       # 19 synthetic documents (Phase 1)
│   ├── sensor_readings/      # 4 CSV files of simulated sensor data
│   └── known_patterns_index.json  # 6 hand-labelled pattern types
└── docs/
    └── incident_research.md  # Research note on both real incidents
```

---

## Setup

### Backend
```bash
cd backend
pipenv shell                      # creates venv with system Python (3.14 is fine for Phase 1)
pipenv run pip install -r requirements.txt
cp .env.example .env
# edit .env — add your ANTHROPIC_API_KEY
pipenv run uvicorn main:app --reload
# → http://localhost:8000/health should return {"status":"ok"}
```

> **Phase 2 note:** `chromadb`, `sentence-transformers`, and `anthropic` are in
> `requirements.phase2.txt`. They currently need Python ≤3.12 for prebuilt wheels.
> Install them in a separate `python3.12 -m venv venv312` when you reach Phase 2.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

---

## Phase 1 Deliverables (complete)
- [x] Repo scaffolded (backend + frontend)
- [x] Incident research note (`docs/incident_research.md`)
- [x] 19 synthetic documents in `data/synthetic_docs/`
- [x] Simulated sensor readings (4 CSV files)
- [x] 6 hand-labelled known patterns (`data/known_patterns_index.json`)

## Phase 2 Deliverables (complete)
- [x] Document ingestion pipeline (chunking, embedding, ChromaDB + SQLite)
- [x] Heterogeneous document support (PDF, spreadsheets, email, OCR, P&ID)
- [x] LLM-powered entity extraction (Groq API, asset/date/event/risk signals)
- [x] Knowledge graph construction (NetworkX)
- [x] Hybrid RAG retrieval (vector + SQL keyword + graph expansion)
- [x] Time Machine API + UI
- [x] Pattern Breaker API + UI
- [x] Graph Explorer UI (react-force-graph)
- [x] Agentic workflows (RCA, Compliance, Maintenance agents)
- [x] Mobile/field technician API endpoints
- [x] Document validation framework
- [x] Performance metrics and benchmark suite
- [x] Compliance/regulatory mapping (Factory Act, OISD, PESO, ISO)
