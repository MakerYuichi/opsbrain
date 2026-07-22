"""
test_precision_recall.py — honest precision/recall evaluation of Pattern Breaker.

Ground truth: data/known_patterns_index.json (6 hand-labelled patterns,
each with PRIMARY and SECONDARY document labels).

Matching logic
──────────────
An alert is a TRUE POSITIVE for known pattern KP-N if:
  - At least one of its source_fact_ids belongs to a document that is a
    PRIMARY label for KP-N in the ground truth.

This is intentionally generous on the retrieval side (we only require one
matching doc, not all of them) to avoid penalising the system for finding
real signals in additional documents.

A known pattern is DETECTED if at least one alert matches it.
An alert is a FALSE POSITIVE if it matches none of the known patterns.

We report:
  precision = TP_alerts / total_alerts
  recall    = detected_patterns / total_known_patterns
  per-pattern breakdown showing which alerts matched each KP
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from fact_builder import SyncSession
from sqlalchemy import text

KNOWN_PATTERNS_FILE = ROOT.parent / "data" / "known_patterns_index.json"


def load_ground_truth() -> dict:
    """Returns {doc_id: [pattern_id, ...]} for PRIMARY-labelled docs."""
    with open(KNOWN_PATTERNS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    doc_to_patterns: dict[str, list[str]] = {}
    pattern_meta: dict[str, str] = {}
    for p in data["patterns"]:
        pattern_meta[p["pattern_id"]] = p["pattern_name"]
        for doc in p["labelled_documents"]:
            if doc["label"] == "PRIMARY":
                doc_to_patterns.setdefault(doc["doc_id"], []).append(p["pattern_id"])
    return doc_to_patterns, pattern_meta, data["patterns"]


def load_alerts() -> list[dict]:
    with SyncSession() as session:
        rows = session.execute(text(
            "SELECT alert_id, asset_id, pattern_type, description, "
            "       confidence, source_fact_ids FROM alerts"
        )).fetchall()
    return [
        {
            "alert_id":       r[0],
            "asset_id":       r[1],
            "pattern_type":   r[2],
            "description":    (r[3] or "")[:120],
            "confidence":     float(r[4] or 0),
            "source_fact_ids": json.loads(r[5] or "[]"),
        }
        for r in rows
    ]


def fact_id_to_doc_id(fact_id: str) -> str:
    """Derive doc_id from fact_id (e.g. LGP-MAINT-002-F001-ST-11 → LGP-MAINT-002)."""
    with SyncSession() as session:
        row = session.execute(text(
            "SELECT doc_id FROM facts WHERE fact_id = :fid"
        ), {"fid": fact_id}).fetchone()
    return row[0] if row else ""


def evaluate():
    doc_to_patterns, pattern_meta, all_patterns = load_ground_truth()
    alerts = load_alerts()

    if not alerts:
        print("No alerts found in DB. Run pattern_engine.py first.")
        return

    total_known = len(all_patterns)
    known_pattern_ids = {p["pattern_id"] for p in all_patterns}

    # Build doc_id lookup for all fact_ids in all alerts (batch)
    all_fact_ids = list({fid for a in alerts for fid in a["source_fact_ids"]})
    fid_to_doc: dict[str, str] = {}
    if all_fact_ids:
        with SyncSession() as session:
            # SQLite supports up to 999 bind params; chunk if needed
            chunk = 200
            for i in range(0, len(all_fact_ids), chunk):
                batch = all_fact_ids[i:i+chunk]
                ph = ",".join(f":f{j}" for j in range(len(batch)))
                params = {f"f{j}": fid for j, fid in enumerate(batch)}
                rows = session.execute(text(
                    f"SELECT fact_id, doc_id FROM facts WHERE fact_id IN ({ph})"
                ), params).fetchall()
                for fid, did in rows:
                    fid_to_doc[fid] = did

    # ── Match each alert to known patterns ─────────────────────────────────
    alert_matched_patterns: dict[str, set[str]] = {}   # alert_id → {KP-ids}
    for alert in alerts:
        matched: set[str] = set()
        for fid in alert["source_fact_ids"]:
            doc_id = fid_to_doc.get(fid, "")
            if doc_id in doc_to_patterns:
                matched.update(doc_to_patterns[doc_id])
        alert_matched_patterns[alert["alert_id"]] = matched

    # ── Precision & Recall ─────────────────────────────────────────────────
    tp_alerts = [a for a in alerts if alert_matched_patterns[a["alert_id"]]]
    fp_alerts = [a for a in alerts if not alert_matched_patterns[a["alert_id"]]]

    detected_kp_ids: set[str] = set()
    for matched in alert_matched_patterns.values():
        detected_kp_ids.update(matched)
    detected_kp_ids &= known_pattern_ids

    precision = len(tp_alerts) / len(alerts) if alerts else 0.0
    recall    = len(detected_kp_ids) / total_known if total_known else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    # ── Print report ───────────────────────────────────────────────────────
    SEP = "═" * 72
    print(f"\n{SEP}")
    print("PATTERN BREAKER — PRECISION / RECALL REPORT")
    print(SEP)
    print(f"  Alerts generated : {len(alerts)}")
    print(f"  True positives   : {len(tp_alerts)}")
    print(f"  False positives  : {len(fp_alerts)}")
    print(f"  Known patterns   : {total_known}")
    print(f"  Detected patterns: {len(detected_kp_ids)}")
    print(f"  Missed patterns  : {total_known - len(detected_kp_ids)}")
    print()
    print(f"  Precision  : {precision:.2f}  ({len(tp_alerts)}/{len(alerts)} alerts map to a known pattern)")
    print(f"  Recall     : {recall:.2f}  ({len(detected_kp_ids)}/{total_known} known patterns detected)")
    print(f"  F1 score   : {f1:.2f}")

    print(f"\n{SEP}")
    print("PER-KNOWN-PATTERN BREAKDOWN")
    print(SEP)
    for kp in all_patterns:
        kid  = kp["pattern_id"]
        kname = kp["pattern_name"]
        matching_alerts = [
            a for a in alerts if kid in alert_matched_patterns[a["alert_id"]]
        ]
        status = "✓ DETECTED" if matching_alerts else "✗ MISSED"
        print(f"  {kid}  {status}")
        print(f"         {kname}")
        if matching_alerts:
            for ma in matching_alerts:
                print(f"         → {ma['alert_id']}  [{ma['pattern_type']}]  "
                      f"conf={ma['confidence']:.2f}")
        else:
            # Show what docs were supposed to be covered
            primary_docs = [d["doc_id"] for d in kp["labelled_documents"]
                            if d["label"] == "PRIMARY"]
            print(f"         primary docs: {primary_docs}")
        print()

    print(SEP)
    print("FALSE POSITIVE ALERTS (no match to any known pattern)")
    print(SEP)
    if not fp_alerts:
        print("  None — all alerts matched at least one known pattern.")
    else:
        for a in fp_alerts:
            print(f"  {a['alert_id']}  {a['pattern_type']}  conf={a['confidence']:.2f}")
            print(f"    {a['description'][:100]}")
    print()

    print(SEP)
    print("HONEST CAVEATS")
    print(SEP)
    print("  • Dataset size: 19 synthetic docs, 298 facts. Numbers are indicative only.")
    print("  • Matching is generous: 1 overlapping PRIMARY doc = TP.")
    print("  • Alerts from unfinished clusters (run timed out) lower recall artificially.")
    print("  • Re-run pattern_engine.py --force to complete all clusters.")
    print(SEP)
    print()

    return {"precision": precision, "recall": recall, "f1": f1}


if __name__ == "__main__":
    evaluate()
