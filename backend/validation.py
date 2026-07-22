"""
validation.py — document quality validation and extraction confidence scoring.

Provides validation framework for real plant documents with quality checks,
format validation, and confidence scoring for extracted entities.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from doc_formats import extract_text, ExtractedDocument


@dataclass
class ValidationResult:
    """Validation result for a document."""
    document_path: str
    is_valid: bool
    quality_score: float  # 0.0 to 1.0
    issues: list[str]
    warnings: list[str]
    format_type: str
    text_length: int
    extraction_confidence: float
    timestamp: str


@dataclass
class EntityValidation:
    """Validation for extracted entities."""
    entity_type: str
    entity_value: str
    confidence: float
    validation_source: str  # "pattern_match", "catalog_lookup", "contextual"
    is_verified: bool
    issues: list[str]


# Validation patterns for industrial assets
_ASSET_TAG_PATTERNS = [
    r"\b[A-Z]{2,5}-\d{1,4}[A-Z]?\b",  # ST-11, APS-3, LF-3
    r"\b[A-Z]{2,5}/\d{1,4}[A-Z]?\b",  # ST/11, APS/3
    r"\b[A-Z]{2,5}\d{1,4}[A-Z]?\b",   # ST11, APS3
]

_DATE_PATTERNS = [
    r"\d{4}-\d{2}-\d{2}",  # ISO format
    r"\d{2}/\d{2}/\d{4}",  # US format
    r"\d{2}-\d{2}-\d{4}",  # European format
]

_REQUIRED_DOCUMENT_FIELDS = [
    "document_id",
    "document_type",
    "facility",
    "date",
]


def validate_asset_tag(tag: str) -> EntityValidation:
    """Validate an asset tag against industrial patterns."""
    tag = tag.strip().upper()
    confidence = 0.0
    issues = []
    is_verified = False
    source = "pattern_match"

    # Check against known patterns
    for pattern in _ASSET_TAG_PATTERNS:
        if re.match(pattern, tag):
            confidence = 0.9
            is_verified = True
            break

    # Additional checks
    if len(tag) < 3:
        issues.append("Asset tag too short")
        confidence = max(confidence - 0.3, 0.0)

    if not any(c.isalpha() for c in tag):
        issues.append("Asset tag missing alphabetic prefix")
        confidence = max(confidence - 0.2, 0.0)

    if not any(c.isdigit() for c in tag):
        issues.append("Asset tag missing numeric identifier")
        confidence = max(confidence - 0.2, 0.0)

    return EntityValidation(
        entity_type="asset_tag",
        entity_value=tag,
        confidence=confidence,
        validation_source=source,
        is_verified=is_verified,
        issues=issues,
    )


def validate_date_string(date_str: str) -> EntityValidation:
    """Validate a date string."""
    date_str = date_str.strip()
    confidence = 0.0
    issues = []
    is_verified = False
    source = "pattern_match"

    for pattern in _DATE_PATTERNS:
        if re.search(pattern, date_str):
            confidence = 0.85
            is_verified = True
            break

    # Try to parse
    try:
        # Try common formats
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
            try:
                datetime.strptime(date_str, fmt)
                confidence = 0.95
                is_verified = True
                break
            except ValueError:
                continue
    except Exception:
        issues.append("Could not parse date")

    if not is_verified:
        issues.append("Date format not recognized")

    return EntityValidation(
        entity_type="date",
        entity_value=date_str,
        confidence=confidence,
        validation_source=source,
        is_verified=is_verified,
        issues=issues,
    )


def validate_document_quality(doc: ExtractedDocument) -> ValidationResult:
    """Validate overall document quality."""
    issues = []
    warnings = []
    quality_score = 1.0
    text = doc.raw_text

    # Text length check
    if len(text.strip()) < 50:
        issues.append("Document text too short (< 50 chars)")
        quality_score -= 0.4
    elif len(text.strip()) < 200:
        warnings.append("Document text very short (< 200 chars)")
        quality_score -= 0.2

    # Required field presence
    text_lower = text.lower()
    missing_fields = []
    for field in _REQUIRED_DOCUMENT_FIELDS:
        if field.replace("_", " ") not in text_lower:
            missing_fields.append(field)

    if missing_fields:
        warnings.append(f"Missing expected fields: {', '.join(missing_fields)}")
        quality_score -= 0.1 * len(missing_fields)

    # Format-specific validation
    if doc.format_type == "pdf":
        if doc.metadata.get("pages", 0) == 0:
            issues.append("PDF has no extractable pages")
            quality_score -= 0.5
        if doc.metadata.get("ocr_used"):
            warnings.append("PDF required OCR - text may have errors")
            quality_score -= 0.15

    elif doc.format_type == "spreadsheet":
        if not doc.metadata.get("sheets"):
            issues.append("Spreadsheet has no extractable sheets")
            quality_score -= 0.4

    elif doc.format_type == "email":
        email_meta = doc.metadata.get("email", {})
        if not email_meta.get("from"):
            warnings.append("Email missing sender information")
            quality_score -= 0.1
        if not email_meta.get("subject"):
            warnings.append("Email missing subject")
            quality_score -= 0.05

    elif doc.format_type in ("ocr", "pid"):
        if doc.metadata.get("ocr") and not doc.metadata.get("pid_tags"):
            warnings.append("OCR extraction found no equipment tags")
            quality_score -= 0.1

    # Extraction confidence based on format
    format_confidence = {
        "txt": 0.95,
        "pdf": 0.85,
        "spreadsheet": 0.90,
        "email": 0.88,
        "ocr": 0.70,
        "pid": 0.80,
        "csv_doc": 0.92,
    }.get(doc.format_type, 0.75)

    # Clamp score
    quality_score = max(0.0, min(1.0, quality_score))

    return ValidationResult(
        document_path=doc.source_path,
        is_valid=quality_score >= 0.5,
        quality_score=quality_score,
        issues=issues,
        warnings=warnings,
        format_type=doc.format_type,
        text_length=len(text),
        extraction_confidence=format_confidence,
        timestamp=datetime.utcnow().isoformat(),
    )


def validate_extraction_batch(docs: list[ExtractedDocument]) -> dict:
    """Validate a batch of documents and return summary statistics."""
    results = [validate_document_quality(doc) for doc in docs]

    valid_count = sum(1 for r in results if r.is_valid)
    avg_quality = sum(r.quality_score for r in results) / len(results) if results else 0.0

    format_breakdown = {}
    for r in results:
        format_breakdown[r.format_type] = format_breakdown.get(r.format_type, 0) + 1

    common_issues = {}
    for r in results:
        for issue in r.issues:
            common_issues[issue] = common_issues.get(issue, 0) + 1

    common_warnings = {}
    for r in results:
        for warning in r.warnings:
            common_warnings[warning] = common_warnings.get(warning, 0) + 1

    return {
        "total_documents": len(results),
        "valid_documents": valid_count,
        "invalid_documents": len(results) - valid_count,
        "average_quality_score": round(avg_quality, 3),
        "format_breakdown": format_breakdown,
        "common_issues": sorted(common_issues.items(), key=lambda x: -x[1]),
        "common_warnings": sorted(common_warnings.items(), key=lambda x: -x[1]),
        "individual_results": [
            {
                "path": r.document_path,
                "valid": r.is_valid,
                "quality_score": r.quality_score,
                "format": r.format_type,
                "issues": r.issues,
                "warnings": r.warnings,
            }
            for r in results
        ],
    }


def validate_real_document(file_path: str | Path) -> ValidationResult:
    """Validate a real plant document from file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    doc = extract_text(path)
    return validate_document_quality(doc)
