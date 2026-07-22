"""
routers/validation.py — document quality validation API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from validation import (
    validate_asset_tag,
    validate_date_string,
    validate_document_quality,
    validate_extraction_batch,
    validate_real_document,
)
from doc_formats import extract_text, ExtractedDocument

router = APIRouter(prefix="/validation", tags=["Validation"])


class AssetTagValidationRequest(BaseModel):
    tag: str


class DateValidationRequest(BaseModel):
    date_string: str


class DocumentValidationRequest(BaseModel):
    file_path: Optional[str] = None
    raw_text: Optional[str] = None
    format_type: Optional[str] = None


class BatchValidationRequest(BaseModel):
    file_paths: list[str]


@router.post("/asset-tag")
def validate_asset_tag_endpoint(req: AssetTagValidationRequest):
    """Validate an asset tag against industrial patterns."""
    result = validate_asset_tag(req.tag)
    return {
        "entity_type": result.entity_type,
        "entity_value": result.entity_value,
        "confidence": result.confidence,
        "validation_source": result.validation_source,
        "is_verified": result.is_verified,
        "issues": result.issues,
    }


@router.post("/date")
def validate_date_endpoint(req: DateValidationRequest):
    """Validate a date string."""
    result = validate_date_string(req.date_string)
    return {
        "entity_type": result.entity_type,
        "entity_value": result.entity_value,
        "confidence": result.confidence,
        "validation_source": result.validation_source,
        "is_verified": result.is_verified,
        "issues": result.issues,
    }


@router.post("/document")
def validate_document_endpoint(req: DocumentValidationRequest):
    """Validate a document's quality and extraction confidence."""
    if req.file_path:
        result = validate_real_document(req.file_path)
    elif req.raw_text and req.format_type:
        doc = ExtractedDocument(
            source_path="inline",
            format_type=req.format_type,
            raw_text=req.raw_text,
            metadata={},
        )
        result = validate_document_quality(doc)
    else:
        raise HTTPException(
            400, "Either file_path or (raw_text + format_type) required"
        )

    return {
        "document_path": result.document_path,
        "is_valid": result.is_valid,
        "quality_score": result.quality_score,
        "format_type": result.format_type,
        "text_length": result.text_length,
        "extraction_confidence": result.extraction_confidence,
        "issues": result.issues,
        "warnings": result.warnings,
        "timestamp": result.timestamp,
    }


@router.post("/batch")
def validate_batch_endpoint(req: BatchValidationRequest):
    """Validate a batch of documents and return summary statistics."""
    from pathlib import Path

    docs = []
    for fp in req.file_paths:
        path = Path(fp)
        if path.exists():
            try:
                doc = extract_text(path)
                docs.append(doc)
            except Exception as e:
                # Include error in results
                pass

    if not docs:
        raise HTTPException(400, "No valid documents found in file_paths")

    results = validate_extraction_batch(docs)
    return results


@router.get("/patterns")
def list_validation_patterns():
    """List the validation patterns used for asset tags and dates."""
    from validation import _ASSET_TAG_PATTERNS, _DATE_PATTERNS, _REQUIRED_DOCUMENT_FIELDS

    return {
        "asset_tag_patterns": _ASSET_TAG_PATTERNS,
        "date_patterns": _DATE_PATTERNS,
        "required_document_fields": _REQUIRED_DOCUMENT_FIELDS,
    }
