"""
entity_extractor.py — LLM-powered extraction of structured facts from documents.

Routes through OpenRouter using the OpenAI-compatible API.
Primary model: google/gemma-4-31b-it:free (~2s/call, reliable JSON).
Falls back to other free models if the primary is rate-limited or unavailable.
"""
import json
import os
import re
import time
from typing import Any

from openai import OpenAI, RateLimitError, APIStatusError
from dotenv import load_dotenv
from parser import ParsedDocument

load_dotenv()

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Tried in order; on rate-limit we rotate to the next one
OPENROUTER_MODELS = [
    "google/gemma-4-26b-a4b-it:free",          # primary — higher RPM on free tier
    "google/gemma-4-31b-it:free",              # secondary
    "nvidia/nemotron-3-super-120b-a12b:free",  # tertiary fallback
]

FACT_TYPES = [
    "TEMPERATURE_READING",
    "INHIBITOR_DOSING",
    "DISSOLVED_OXYGEN_READING",
    "MAINTENANCE_ACTION",
    "DEFERRED_MAINTENANCE",
    "INSTRUMENT_FAULT",
    "PERMIT_STATUS",
    "SAFETY_VIOLATION",
    "SHIFT_OBSERVATION",
    "ALARM_RESPONSE",
    "INCIDENT_EVENT",
    "RISK_OBSERVATION",
    "QUALITY_READING",
    "PROCESS_PARAMETER",
    "WORK_ORDER",
]

SYSTEM_PROMPT = (
    "You are an industrial safety analyst. "
    "Extract structured facts from industrial documents and return ONLY a JSON array. "
    "No markdown fences, no prose, no wrapper object — start with [ end with ]."
)

USER_TEMPLATE = """\
Document ID: {doc_id} | Type: {doc_type} | Date: {doc_date} | Facility: {facility}

TEXT:
{text}

Return a JSON array. Each element has exactly:
  "fact_type"  — one of: {fact_types}
  "asset_ids"  — list of every equipment tag mentioned (ST-11, APS-3, LF-3, etc.)
  "timestamp"  — ISO date/datetime or null
  "content"    — one sentence describing the fact
  "source_span"— verbatim substring from the TEXT above
  "confidence" — float 0-1

Be exhaustive. For DEFERRED_MAINTENANCE state what was deferred and why.
For INSTRUMENT_FAULT include sensor tag and what it failed to read.
"""


def _make_client() -> OpenAI:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise EnvironmentError("GROQ_API_KEY not set in .env")
    return OpenAI(api_key=key, base_url=OPENROUTER_BASE)


def _parse_response(raw: str) -> list[dict]:
    """Robustly extract a JSON array from the model response."""
    raw = raw.strip()
    # Strip markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```\s*$",        "", raw, flags=re.MULTILINE)
    raw = raw.strip()
    # Unwrap {"facts": [...]} or similar
    if raw.startswith("{"):
        obj = json.loads(raw)
        for v in obj.values():
            if isinstance(v, list):
                return v
        raise ValueError(f"JSON object — no list found. Keys: {list(obj.keys())}")
    return json.loads(raw)


def _retry_after(exc: Exception) -> float:
    """Extract Retry-After seconds from exception, default 10s."""
    msg = str(exc)
    # OpenRouter embeds retry-after in the error body
    m = re.search(r"retry.after[\":\s]+(\d+)", msg, re.IGNORECASE)
    if m:
        return float(m.group(1))
    return 10.0


def extract_facts(doc: ParsedDocument, client: OpenAI) -> list[dict[str, Any]]:
    """Call OpenRouter to extract facts. Rotates models on rate-limit/404."""
    user_msg = USER_TEMPLATE.format(
        doc_id=doc.doc_id,
        doc_type=doc.doc_type,
        doc_date=doc.doc_date or "unknown",
        facility=doc.facility,
        text=doc.raw_text[:6000],      # ~1500 tokens — well within free quota
        fact_types=", ".join(FACT_TYPES),
    )
    headers = {
        "HTTP-Referer": "https://github.com/MakerYuichi/opsbrain",
        "X-Title": "Industrial KI Pipeline",
    }

    for model in OPENROUTER_MODELS:
        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user",   "content": user_msg},
                    ],
                    temperature=0.0,
                    max_tokens=2500,
                    extra_headers=headers,
                    timeout=45,
                )

                raw = resp.choices[0].message.content or ""
                if not raw.strip():
                    raise ValueError("Empty response from model")

                facts_list = _parse_response(raw)
                if not isinstance(facts_list, list):
                    raise ValueError("Not a JSON array")

                cleaned = []
                for f in facts_list:
                    if not isinstance(f, dict):
                        continue
                    ftype = str(f.get("fact_type", "")).upper().strip()
                    if ftype not in FACT_TYPES:
                        ftype = "RISK_OBSERVATION"
                    cleaned.append({
                        "fact_type":   ftype,
                        "asset_ids":   [str(a) for a in f.get("asset_ids", [])],
                        "timestamp":   f.get("timestamp"),
                        "content":     str(f.get("content", "")).strip(),
                        "source_span": str(f.get("source_span", "")).strip(),
                        "confidence":  float(f.get("confidence", 0.8)),
                    })

                short = model.split("/")[-1]
                print(f"[extractor] {doc.doc_id}: {len(cleaned)} facts [{short}]")
                return cleaned

            except RateLimitError as e:
                wait = _retry_after(e)
                print(f"[extractor] {doc.doc_id}: rate-limited on {model.split('/')[-1]} "
                      f"— rotating model (waited {wait:.0f}s would be needed)")
                break   # immediately rotate to next model, don't wait

            except APIStatusError as e:
                if e.status_code == 404:
                    print(f"[extractor] {doc.doc_id}: {model} unavailable (404) — next model")
                    break
                # Other 4xx/5xx — retry with backoff
                wait = 3 * (attempt + 1)
                print(f"[extractor] {doc.doc_id}: HTTP {e.status_code} attempt {attempt+1} "
                      f"— retrying in {wait}s")
                time.sleep(wait)

            except json.JSONDecodeError as e:
                print(f"[extractor] {doc.doc_id}: JSON error attempt {attempt+1}: {e}")
                if attempt < 2:
                    time.sleep(2)
                    continue
                break

            except Exception as e:
                print(f"[extractor] {doc.doc_id}: unexpected error [{model.split('/')[-1]}]: "
                      f"{type(e).__name__}: {e}")
                if attempt < 2:
                    time.sleep(3)
                    continue
                break

    print(f"[extractor] {doc.doc_id}: all models exhausted — returning []")
    return []


def extract_all(docs: list[ParsedDocument],
                client: OpenAI) -> dict[str, list[dict]]:
    """Extract facts from all documents. Returns {doc_id: [facts]}."""
    results = {}
    for i, doc in enumerate(docs, 1):
        print(f"[extractor] ({i}/{len(docs)}) {doc.doc_id}…")
        results[doc.doc_id] = extract_facts(doc, client)
        # 3s between calls keeps us at ~20 req/min — just under the free limit
        if i < len(docs):
            time.sleep(3)
    return results
