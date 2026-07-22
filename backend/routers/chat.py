"""
routers/chat.py — Conversational Q&A with hybrid RAG retrieval.

Retrieval strategy:
1. Vector semantic search (ChromaDB or TF-IDF fallback)
2. SQL keyword + asset_id matching
3. 1-hop graph expansion via shared documents
4. Merge and rank: 0.6 × vector score + 0.4 × fact confidence
5. LLM answer with [FACT-ID] citations and confidence scores
"""
import json
import os
from fastapi import APIRouter
from pydantic import BaseModel
from openai import OpenAI
from fact_builder import SyncSession
from rag_retriever import hybrid_retrieve

router = APIRouter(prefix="/chat", tags=["Chat"])

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
MODEL = "google/gemma-4-26b-a4b-it:free"

def _span_text(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return json.loads(raw).get("text", raw)
    except Exception:
        return raw


# ── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    history:  list[dict] = []   # [{"role": "user"|"assistant", "text": "..."}]

class CitedFact(BaseModel):
    fact_id:     str
    content:     str
    source_span: str
    doc_id:      str
    confidence:  float

class ChatResponse(BaseModel):
    answer:          str
    sources:         list[CitedFact]
    retrieval_mode:  str = "hybrid_rag"
    retrieval_stats: dict = {}


# ── Route ─────────────────────────────────────────────────────────────────────

SYSTEM = """You are OpsBrain, a safety analyst assistant for the Industrial Knowledge
Intelligence platform, covering two incidents:
- LGP: Horizon Chemicals styrene storage tank (ST-11) gas leak chain (2019-2020)
- VSP: Bharat Steel Works argon purging station (APS-3) ladle explosion chain (2025)

Response style rules:
- Greetings, small talk, "what can you do", thanks/goodbyes -> reply in 1-2 short
  sentences, casual tone, no bullet lists, no restating your full capabilities every
  time. Only mention the incidents/example questions if the user seems unsure what
  to ask.
- Safety/asset/incident questions -> answer using ONLY the RETRIEVED FACTS block
  below, citing fact IDs like [FACT-ID] after each claim. Include confidence
  when relevant (e.g. "high confidence 0.92"). Be as detailed as the facts require.
- If facts are provided but insufficient, say what you know and what's missing.
- If no facts were retrieved for a substantive question, say so plainly and suggest
  what to ask instead (e.g. mention a specific asset like APS-3, ST-11, LF-3, CHR-01).
- Be direct and specific. Never repeat your intro/capabilities unless asked what
  you can do.
"""

@router.post("", response_model=ChatResponse)
def ask(req: ChatRequest):
    q = req.question.strip()
    if not q:
        return ChatResponse(answer="Ask me something about ST-11 or APS-3.", sources=[])

    retrieval_meta: dict = {}
    with SyncSession() as session:
        from sqlalchemy import text as sql_text
        known = [r[0] for r in session.execute(sql_text("SELECT asset_id FROM assets")).fetchall()]
        combined_query = q
        if req.history:
            last_assistant = next(
                (m["text"] for m in reversed(req.history) if m.get("role") == "assistant"),
                ""
            )
            if last_assistant:
                combined_query = q + " " + last_assistant[:200]
        rows, retrieval_meta = hybrid_retrieve(combined_query, session, known, limit=15)

    # Build LLM messages — inject history for multi-turn context
    messages: list[dict] = [{"role": "system", "content": SYSTEM}]

    # Add prior turns (cap at last 6 to save tokens)
    for turn in req.history[-6:]:
        role = turn.get("role", "user")
        text_ = turn.get("text", "")
        if role in ("user", "assistant") and text_:
            messages.append({"role": role, "content": text_})

    # Current turn: inject retrieved facts (if any) + question
    if rows:
        context = "\n".join(
            f"[{r[0]}] asset={r[5]} doc={r[3]} conf={r[4]:.2f}: {r[1]}"
            for r in rows
        )
        user_content = f"RETRIEVED FACTS:\n{context}\n\nQUESTION: {q}"
    else:
        user_content = f"(No facts retrieved from the knowledge graph for this query.)\n\nQUESTION: {q}"

    messages.append({"role": "user", "content": user_content})

    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.3,
            extra_headers={
                "HTTP-Referer": "https://github.com/MakerYuichi/opsbrain",
                "X-Title": "opsbrain-chat",
            },
        )
        answer = completion.choices[0].message.content or "No answer generated."
    except Exception as e:
        answer = (
            f"LLM unavailable ({type(e).__name__}). Key facts: "
            + "; ".join(r[1][:80] for r in rows[:3])
            if rows
            else f"LLM unavailable ({type(e).__name__}). Try again shortly."
        )

    sources = [
        CitedFact(fact_id=r[0], content=r[1], source_span=_span_text(r[2]),
                  doc_id=r[3], confidence=float(r[4]))
        for r in rows
    ]
    return ChatResponse(
        answer=answer,
        sources=sources,
        retrieval_mode=retrieval_meta.get("retrieval", "hybrid_rag"),
        retrieval_stats=retrieval_meta,
    )