"""
routers/evaluation.py — chat quality and entity extraction accuracy API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from evaluation import (
    ChatEvaluator,
    EntityExtractionEvaluator,
    evaluate_entity_extraction_from_db,
    run_chat_evaluation_sample,
)

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


class ChatEvaluationRequest(BaseModel):
    query: str
    answer: str
    retrieved_fact_ids: list[str]
    ground_truth_key_points: Optional[list[str]] = None


class EntityExtractionRequest(BaseModel):
    document_type: str
    document_path: str
    ground_truth_entities: dict
    extracted_entities: dict


@router.post("/chat")
def evaluate_chat_answer(req: ChatEvaluationRequest):
    """
    Evaluate a chat answer's quality against retrieved facts.
    Returns relevance score, citation accuracy, and hallucination detection.
    """
    evaluator = ChatEvaluator()

    # Convert fact IDs to tuple format expected by evaluator
    retrieved_facts = [(fid, f"Content for {fid}", None, f"doc_{fid}", 0.8, None) for fid in req.retrieved_fact_ids]

    result = evaluator.evaluate_answer(
        query=req.query,
        answer=req.answer,
        retrieved_facts=retrieved_facts,
        ground_truth_key_points=req.ground_truth_key_points,
    )

    return {
        "query": result.query,
        "relevance_score": result.relevance_score,
        "citation_accuracy": result.fact_citation_accuracy,
        "hallucination_count": result.hallucination_count,
        "missing_key_info": result.missing_key_info,
        "timestamp": result.timestamp,
    }


@router.get("/chat/summary")
def get_chat_evaluation_summary():
    """Get summary of all chat evaluations performed."""
    evaluator = ChatEvaluator()
    return evaluator.get_summary()


@router.post("/entity")
def evaluate_entity_extraction(req: EntityExtractionRequest):
    """
    Evaluate entity extraction accuracy against ground truth.
    Returns precision, recall, and F1 score by document type.
    """
    evaluator = EntityExtractionEvaluator()

    result = evaluator.evaluate_extraction(
        document_type=req.document_type,
        document_path=req.document_path,
        ground_truth=req.ground_truth_entities,
        extracted=req.extracted_entities,
    )

    return {
        "document_type": result.document_type,
        "precision": result.precision,
        "recall": result.recall,
        "f1_score": result.f1_score,
        "true_positives": result.true_positives,
        "false_positives": result.false_positives,
        "false_negatives": result.false_negatives,
        "timestamp": result.timestamp,
    }


@router.get("/entity/summary")
def get_entity_extraction_summary():
    """Get summary of entity extraction evaluations by document type."""
    evaluator = EntityExtractionEvaluator()
    return evaluator.get_summary_by_document_type()


@router.post("/entity/from-db")
def evaluate_extraction_from_database():
    """
    Evaluate entity extraction accuracy using database entities against synthetic ground truth.
    Compares extracted entities in the database to expected entities for known documents.
    """
    return evaluate_entity_extraction_from_db()


@router.get("/chat/sample")
def get_chat_evaluation_sample():
    """Get sample chat evaluation test cases."""
    return run_chat_evaluation_sample()


@router.post("/reset")
def reset_evaluations():
    """Reset all evaluation data."""
    chat_eval = ChatEvaluator()
    entity_eval = EntityExtractionEvaluator()
    # Clear internal lists (accessing private attributes for reset)
    chat_eval.evaluations.clear()
    entity_eval.evaluations.clear()
    return {"status": "reset", "message": "All evaluation data cleared"}
