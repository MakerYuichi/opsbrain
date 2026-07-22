# OpsBrain - Industrial Knowledge Intelligence Platform
**ET AI Hackathon 2.0 — Problem Statement #8**

OpsBrain is an AI-powered platform that ingests heterogeneous industrial documents (PDFs, emails, P&IDs, spreadsheets, OCR scans), extracts structured knowledge using LLMs, and builds a unified knowledge graph. It exposes this intelligence through multiple interfaces:

- **Time Machine** — Timeline-based asset history exploration with date filtering
- **Pattern Breaker** — Proactive risk pattern detection (temperature excursions, deferred maintenance, permit expiration)
- **Graph Explorer** — Interactive knowledge graph visualization with causal chain reasoning
- **Chat** — Grounded conversational RAG with source citations
- **AI Agents** — Specialized workflows for RCA, Compliance, and Maintenance analysis
- **Mobile Field** — Mobile-optimized interface for field technicians

**Demo grounded in two real incidents:** LG Polymers Vizag styrene leak (May 2020) and Vizag Steel Plant SMS-1 ladle explosion (June 2025).

---

## Performance Metrics

| Metric | Result |
|--------|--------|
| Search Performance | 158.80 ms avg retrieval (86.7% faster than manual search) |
| Pattern Detection | 100% precision, 100% recall (on 6 known patterns) |
| Agent Performance | 4.85 s avg execution time (RCA, Compliance, Maintenance) |
| System Capacity | 300 facts, 20 assets, 22 documents |

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
│   ├── database.py           # SQLite setup (sync/async SQLAlchemy)
│   ├── models.py             # ORM models (Asset, Document, Fact, Edge, SensorReading, Alert)
│   ├── parser.py             # Document parsing for multiple formats
│   ├── entity_extractor.py   # LLM-based entity extraction
│   ├── entity_resolver.py    # Entity resolution and normalization
│   ├── fact_builder.py       # Knowledge graph construction
│   ├── rag_retriever.py      # Hybrid RAG (vector + SQL + graph)
│   ├── pattern_engine.py     # Pattern detection and alert generation
│   ├── ingest.py             # Document ingestion pipeline
│   ├── agents/               # AI agents (RCA, Compliance, Maintenance)
│   ├── routers/              # API endpoints
│   ├── requirements.txt
│   └── .env.example          # → copy to .env and add GROQ_API_KEY
├── frontend/
│   ├── src/
│   │   ├── pages/            # Dashboard, TimeMachine, PatternBreaker, GraphExplorer, Chat, Agents, MobileField
│   │   ├── components/       # Reusable components
│   │   ├── api/              # API client functions
│   │   ├── App.tsx           # Router + nav shell
│   │   ├── main.tsx
│   │   └── index.css         # Tailwind directives
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
├── data/
│   ├── synthetic_docs/       # 22 synthetic documents (19 txt + 3 heterogeneous)
│   ├── sensor_readings/      # 4 CSV files of simulated sensor data
│   └── known_patterns_index.json  # 6 hand-labelled pattern types
├── docs/
│   ├── incident_research.md  # Research note on both real incidents
│   ├── ARCHITECTURE.md       # Detailed architecture documentation
│   ├── ENTERPRISE_MIGRATION.md  # Migration path to enterprise scale
│   ├── DELIVERABLES_STATUS.md  # Status of expected deliverables
│   └── deck_content.md       # Technical deck content
├── benchmark_report.json     # Performance metrics from test runs
└── README.md
```

---

## Setup

### Backend
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt

# Set up environment variables
cp backend/.env.example backend/.env
# Edit backend/.env and add your GROQ_API_KEY

# Initialize database
cd backend
python -c "from database import init_sync_db; init_sync_db()"

# Run ingestion pipeline (optional - loads synthetic documents)
python ingest.py

# Start FastAPI server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# → http://localhost:8000/health should return {"status":"ok"}
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

---

## Features

### Document Ingestion
- Multi-format support: PDF, spreadsheets, email, OCR scans, P&ID drawings
- LLM-powered entity extraction (Gemma-4 via Groq/OpenRouter)
- Entity resolution and normalization
- Knowledge graph construction with NetworkX
- Extraction caching for cost optimization

### Hybrid RAG System
- Vector search via ChromaDB with TF-IDF fallback
- SQL keyword search for exact matching
- Graph expansion for cross-asset context
- Weighted result ranking
- Source citations and confidence scores

### AI Agents
- **Root Cause Analysis Agent**: Analyzes incident patterns, sensor anomalies, and maintenance history
- **Compliance Agent**: Checks against Factory Act, OISD, PESO, environmental permits, ISO standards
- **Maintenance Agent**: Generates prioritized maintenance schedules from deferred work and sensor faults

### Pattern Detection
- Automatic pattern clustering from precursor facts
- LLM-narrated alerts with confidence scores
- Pattern types: temperature excursions, deferred maintenance, permit expiration, sensor faults, near-misses
- Precision/recall evaluation against ground truth

### Frontend Interfaces
- **Dashboard**: System overview with key metrics and quick actions
- **Time Machine**: Timeline-based asset history exploration
- **Pattern Breaker**: Alert list with severity filters and evidence traceability
- **Graph Explorer**: Interactive knowledge graph with subgraph exploration
- **Chat**: Conversational RAG with source citations
- **Agents**: Tabbed interface for RCA, Compliance, and Maintenance with live progress display
- **Mobile Field**: Mobile-optimized interface for field technicians

### API Endpoints
- Core: `/chat`, `/timeline`, `/patterns`, `/graph`, `/ingest/upload`
- Agents: `/agents/rca`, `/agents/compliance`, `/agents/maintenance`
- Mobile: `/mobile/asset/{id}`, `/mobile/alerts`, `/mobile/incident`, `/mobile/sync/critical`
- Evaluation: `/evaluation/chat`, `/evaluation/entity`, `/benchmark/run`

## Deliverables

### Completed
- [x] Working prototype with all major components
- [x] Architecture documentation (`docs/ARCHITECTURE.md`)
- [x] Enterprise migration roadmap (`docs/ENTERPRISE_MIGRATION.md`)
- [x] Technical deck content (`docs/deck_content.md`)
- [x] Performance metrics (`benchmark_report.json`)
- [x] Heterogeneous document ingestion (PDF, email, P&ID)
- [x] Knowledge graph construction
- [x] Hybrid RAG retrieval system
- [x] AI agents (RCA, Compliance, Maintenance)
- [x] Pattern detection engine
- [x] Mobile field interface
- [x] Chat interface with source citations
- [x] Graph Explorer with causal chain visualization
- [x] Time Machine timeline explorer
- [x] Compliance monitoring against Indian regulations
- [x] Custom test suites with measured performance

### Documentation
- [x] README.md (this file)
- [x] Incident research note (`docs/incident_research.md`)
- [x] Architecture documentation (`docs/ARCHITECTURE.md`)
- [x] Enterprise migration path (`docs/ENTERPRISE_MIGRATION.md`)
- [x] Deliverables status (`docs/DELIVERABLES_STATUS.md`)
- [x] Technical deck content (`docs/deck_content.md`)

### Known Limitations
- Single-machine prototype (SQLite, local storage)
- 60-node graph cap for UX performance
- Free-tier LLM dependency (rate limits)
- Batch-only ingestion (no streaming)
- No multi-tenancy

See `docs/ENTERPRISE_MIGRATION.md` for the phased roadmap to enterprise-scale deployment.
