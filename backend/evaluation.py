"""
evaluation.py — chat answer quality and entity extraction accuracy benchmarks.

Provides:
- Chat answer relevance and accuracy scoring
- Entity extraction precision/recall by document type
- End-to-end fact accuracy validation
- Ground truth comparison for synthetic documents
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text
from fact_builder import SyncSession


@dataclass
class ChatEvaluationResult:
    """Result of chat answer quality evaluation."""
    query: str
    answer: str
    retrieved_facts: list[str]
    relevance_score: float  # 0.0 to 1.0
    fact_citation_accuracy: float  # 0.0 to 1.0
    hallucination_count: int
    missing_key_info: list[str]
    timestamp: str


@dataclass
class EntityExtractionResult:
    """Result of entity extraction evaluation."""
    document_type: str
    document_path: str
    ground_truth_entities: dict
    extracted_entities: dict
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    timestamp: str


class ChatEvaluator:
    """Evaluate chat answer quality using retrieved facts and ground truth."""

    def __init__(self):
        self.evaluations: list[ChatEvaluationResult] = []

    def evaluate_answer(
        self,
        query: str,
        answer: str,
        retrieved_facts: list[tuple],
        ground_truth_key_points: Optional[list[str]] = None,
    ) -> ChatEvaluationResult:
        """
        Evaluate a chat answer against retrieved facts and optional ground truth.

        Args:
            query: The user's question
            answer: The LLM's answer
            retrieved_facts: List of (fact_id, content, ...) tuples
            ground_truth_key_points: Optional list of key points that should be mentioned
        """
        # Extract fact IDs from answer (pattern: [FACT-ID])
        cited_ids = set(re.findall(r'\[([A-Z0-9\-]+)\]', answer))
        retrieved_ids = {f[0] for f in retrieved_facts}

        # Citation accuracy: how many retrieved facts were actually cited
        if retrieved_ids:
            citation_accuracy = len(cited_ids & retrieved_ids) / len(retrieved_ids)
        else:
            citation_accuracy = 0.0

        # Relevance score: based on answer length and fact usage
        if retrieved_facts:
            # Higher score if answer uses multiple facts and is substantive
            fact_usage = len(cited_ids) / max(len(retrieved_facts), 1)
            answer_substance = min(len(answer.split()) / 50, 1.0)  # Normalize to ~50 words as substantive
            relevance_score = (fact_usage * 0.6) + (answer_substance * 0.4)
        else:
            relevance_score = 0.0

        # Check for hallucinations (claims not in retrieved facts)
        hallucinations = self._detect_hallucinations(answer, retrieved_facts)

        # Check for missing key information
        missing_info = []
        if ground_truth_key_points:
            for point in ground_truth_key_points:
                if point.lower() not in answer.lower():
                    missing_info.append(point)

        result = ChatEvaluationResult(
            query=query,
            answer=answer,
            retrieved_facts=[f[0] for f in retrieved_facts],
            relevance_score=round(relevance_score, 3),
            fact_citation_accuracy=round(citation_accuracy, 3),
            hallucination_count=len(hallucinations),
            missing_key_info=missing_info,
            timestamp=datetime.utcnow().isoformat(),
        )

        self.evaluations.append(result)
        return result

    def _detect_hallucinations(self, answer: str, retrieved_facts: list[tuple]) -> list[str]:
        """
        Detect potential hallucinations by checking if specific claims appear in retrieved facts.
        This is a simplified heuristic - full hallucination detection requires more sophisticated NLP.
        """
        # Extract specific claims (numbers, dates, measurements) from answer
        claims = re.findall(r'\b\d+\.?\d*\s*(?:°C|°F|%|tons|bar|psi|days|hours|minutes)\b', answer)

        hallucinations = []
        fact_texts = " ".join(f[1].lower() for f in retrieved_facts)

        for claim in claims:
            if claim.lower() not in fact_texts:
                hallucinations.append(claim)

        return hallucinations

    def get_summary(self) -> dict:
        """Get summary of chat evaluations."""
        if not self.evaluations:
            return {"message": "No chat evaluations performed"}

        avg_relevance = sum(e.relevance_score for e in self.evaluations) / len(self.evaluations)
        avg_citation = sum(e.fact_citation_accuracy for e in self.evaluations) / len(self.evaluations)
        total_hallucinations = sum(e.hallucination_count for e in self.evaluations)

        return {
            "total_evaluations": len(self.evaluations),
            "avg_relevance_score": round(avg_relevance, 3),
            "avg_citation_accuracy": round(avg_citation, 3),
            "total_hallucinations": total_hallucinations,
            "hallucination_rate": round(total_hallucinations / len(self.evaluations), 2) if self.evaluations else 0.0,
        }


class EntityExtractionEvaluator:
    """Evaluate entity extraction accuracy against ground truth."""

    def __init__(self):
        self.evaluations: list[EntityExtractionResult] = []

    def evaluate_extraction(
        self,
        document_type: str,
        document_path: str,
        ground_truth: dict,
        extracted: dict,
    ) -> EntityExtractionResult:
        """
        Evaluate entity extraction against ground truth.

        Args:
            document_type: Type of document (pdf, txt, spreadsheet, etc.)
            document_path: Path to the document
            ground_truth: Dict of expected entities {entity_type: [values]}
            extracted: Dict of extracted entities {entity_type: [values]}
        """
        true_positives = 0
        false_positives = 0
        false_negatives = 0

        # Compare by entity type
        all_types = set(ground_truth.keys()) | set(extracted.keys())

        for entity_type in all_types:
            ground_set = set(str(v).lower() for v in ground_truth.get(entity_type, []))
            extracted_set = set(str(v).lower() for v in extracted.get(entity_type, []))

            tp = len(ground_set & extracted_set)
            fp = len(extracted_set - ground_set)
            fn = len(ground_set - extracted_set)

            true_positives += tp
            false_positives += fp
            false_negatives += fn

        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        result = EntityExtractionResult(
            document_type=document_type,
            document_path=document_path,
            ground_truth_entities=ground_truth,
            extracted_entities=extracted,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            precision=round(precision, 3),
            recall=round(recall, 3),
            f1_score=round(f1, 3),
            timestamp=datetime.utcnow().isoformat(),
        )

        self.evaluations.append(result)
        return result

    def get_summary_by_document_type(self) -> dict:
        """Get extraction accuracy summary grouped by document type."""
        if not self.evaluations:
            return {"message": "No extraction evaluations performed"}

        by_type = {}
        for eval in self.evaluations:
            doc_type = eval.document_type
            if doc_type not in by_type:
                by_type[doc_type] = {
                    "count": 0,
                    "total_tp": 0,
                    "total_fp": 0,
                    "total_fn": 0,
                }
            by_type[doc_type]["count"] += 1
            by_type[doc_type]["total_tp"] += eval.true_positives
            by_type[doc_type]["total_fp"] += eval.false_positives
            by_type[doc_type]["total_fn"] += eval.false_negatives

        summary = {}
        for doc_type, stats in by_type.items():
            precision = stats["total_tp"] / (stats["total_tp"] + stats["total_fp"]) if (stats["total_tp"] + stats["total_fp"]) > 0 else 0.0
            recall = stats["total_tp"] / (stats["total_tp"] + stats["total_fn"]) if (stats["total_tp"] + stats["total_fn"]) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

            summary[doc_type] = {
                "document_count": stats["count"],
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1_score": round(f1, 3),
            }

        return summary

    def get_overall_summary(self) -> dict:
        """Get overall extraction accuracy across all document types."""
        if not self.evaluations:
            return {"message": "No extraction evaluations performed"}

        total_tp = sum(e.true_positives for e in self.evaluations)
        total_fp = sum(e.false_positives for e in self.evaluations)
        total_fn = sum(e.false_negatives for e in self.evaluations)

        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            "total_evaluations": len(self.evaluations),
            "overall_precision": round(precision, 3),
            "overall_recall": round(recall, 3),
            "overall_f1_score": round(f1, 3),
            "by_document_type": self.get_summary_by_document_type(),
        }


def create_synthetic_ground_truth() -> dict:
    """
    Create synthetic ground truth for evaluation using known document structure.
    For synthetic documents, we can infer expected entities from document IDs and content.
    """
    ground_truth = {
        "LGP_001": {
            "asset_ids": ["ST-11"],
            "document_type": "maintenance_log",
            "facility": "Horizon Chemicals Pvt. Ltd.",
            "expected_entities": {
                "asset": ["ST-11"],
                "date": ["2019-06-15", "2019-07-20"],
                "maintenance_type": ["inhibitor top-up"],
            },
        },
        "LGP_008": {
            "asset_ids": ["ST-11"],
            "document_type": "permit",
            "facility": "Horizon Chemicals Pvt. Ltd.",
            "expected_entities": {
                "asset": ["ST-11"],
                "permit_type": ["environmental clearance"],
                "authority": ["NGT"],
            },
        },
        "VSP_009": {
            "asset_ids": ["APS-3"],
            "document_type": "maintenance_log",
            "facility": "Bharat Steel Works Ltd.",
            "expected_entities": {
                "asset": ["APS-3"],
                "system": ["argon purging"],
                "maintenance_type": ["routine inspection"],
            },
        },
        "VSP_014": {
            "asset_ids": ["APS-3"],
            "document_type": "permit",
            "facility": "Bharat Steel Works Ltd.",
            "expected_entities": {
                "asset": ["APS-3"],
                "permit_type": ["ladle refractory inspection"],
                "component": ["refractory lining"],
            },
        },
    }

    return ground_truth


def evaluate_entity_extraction_from_db() -> dict:
    """
    Evaluate entity extraction accuracy by comparing DB entities against synthetic ground truth.
    """
    ground_truth = create_synthetic_ground_truth()
    evaluator = EntityExtractionEvaluator()

    with SyncSession() as session:
        for doc_id, expected in ground_truth.items():
            # Get facts for this document from DB
            facts = session.execute(
                text("""
                    SELECT asset_id, fact_type, content
                    FROM facts
                    WHERE doc_id = :doc_id
                """),
                {"doc_id": doc_id},
            ).fetchall()

            # Extract entities from facts
            extracted_assets = list(set(f[0] for f in facts if f[0]))
            extracted_types = list(set(f[1] for f in facts))

            extracted_entities = {
                "asset": extracted_assets,
                "fact_type": extracted_types,
            }

            # Evaluate
            result = evaluator.evaluate_extraction(
                document_type=expected["document_type"],
                document_path=doc_id,
                ground_truth=expected["expected_entities"],
                extracted=extracted_entities,
            )

    return evaluator.get_overall_summary()


def run_chat_evaluation_sample() -> dict:
    """
    Run a sample chat evaluation using synthetic queries and expected responses.
    """
    evaluator = ChatEvaluator()

    # Sample evaluation cases based on known incidents
    test_cases = [
        {
            "query": "What caused the styrene leak at LG Polymers?",
            "ground_truth_points": [
                "temperature monitoring failure",
                "chilled brine system",
                "inhibitor top-up",
                "safety violations",
            ],
        },
        {
            "query": "What were the maintenance issues with APS-3 before the explosion?",
            "ground_truth_points": [
                "argon purging skipped",
                "refractory inspection",
                "deferred maintenance",
                "sensor anomalies",
            ],
        },
    ]

    # For each test case, we would normally run the actual chat and evaluate
    # For now, return the framework structure
    return {
        "evaluator_ready": True,
        "test_cases": test_cases,
        "note": "Run actual chat queries through /chat endpoint and evaluate with this framework",
    }
