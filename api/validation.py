"""Input validation and sanitization for Soma API.

Security features:
- Slug validation (prevents SQL injection via identifiers)
- String length limits (prevents memory exhaustion)
- Pattern validation for structured inputs
- Range validation for numeric inputs

All public endpoints should use these validators.
"""

import re
from typing import Optional, Annotated
from fastapi import Query, Path, HTTPException

from .observability import get_logger

logger = get_logger("validation")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# Maximum string lengths
MAX_SLUG_LENGTH = 64
MAX_LABEL_LENGTH = 256
MAX_NOTES_LENGTH = 4096
MAX_QUERY_PARAM_LENGTH = 256

# Valid slug pattern (alphanumeric, underscores, hyphens)
SLUG_PATTERN = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')

# Valid patterns for specific fields
BIOMARKER_SLUG_PATTERN = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
SOURCE_SLUG_PATTERN = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')

# Query parameter constraints
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000
MIN_LIMIT = 1
MAX_OFFSET = 100000  # Prevent extremely deep pagination
MAX_DAYS = 3650  # 10 years max


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def validate_slug(value: str, field_name: str = "slug") -> str:
    """Validate a slug identifier.

    Args:
        value: The slug to validate
        field_name: Name of the field for error messages

    Returns:
        The validated slug (lowercase)

    Raises:
        HTTPException: If validation fails
    """
    if not value:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} cannot be empty"
        )

    # Length check
    if len(value) > MAX_SLUG_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be {MAX_SLUG_LENGTH} characters or less"
        )

    # Normalize to lowercase
    value = value.lower().strip()

    # Pattern check
    if not SLUG_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must start with a letter and contain only lowercase letters, numbers, underscores, and hyphens"
        )

    return value


def validate_biomarker_slug(value: str) -> str:
    """Validate a biomarker slug.

    Biomarker slugs use underscores (e.g., heart_rate_resting).
    """
    if not value:
        raise HTTPException(
            status_code=400,
            detail="biomarker_slug cannot be empty"
        )

    value = value.lower().strip()

    if len(value) > MAX_SLUG_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"biomarker_slug must be {MAX_SLUG_LENGTH} characters or less"
        )

    if not BIOMARKER_SLUG_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail="biomarker_slug must start with a letter and contain only lowercase letters, numbers, and underscores"
        )

    return value


def validate_source_slug(value: str) -> str:
    """Validate a data source slug.

    Source slugs may use hyphens (e.g., apple-health).
    """
    if not value:
        raise HTTPException(
            status_code=400,
            detail="source_slug cannot be empty"
        )

    value = value.lower().strip()

    if len(value) > MAX_SLUG_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"source_slug must be {MAX_SLUG_LENGTH} characters or less"
        )

    if not SOURCE_SLUG_PATTERN.match(value):
        raise HTTPException(
            status_code=400,
            detail="source_slug must start with a letter and contain only lowercase letters, numbers, underscores, and hyphens"
        )

    return value


def sanitize_string(
    value: str,
    max_length: int = MAX_QUERY_PARAM_LENGTH,
    field_name: str = "value"
) -> str:
    """Sanitize a string input.

    - Strips whitespace
    - Enforces length limits
    - Removes null bytes (potential injection)

    Args:
        value: The string to sanitize
        max_length: Maximum allowed length
        field_name: Name for error messages

    Returns:
        The sanitized string

    Raises:
        HTTPException: If validation fails
    """
    if not value:
        return value

    # Remove null bytes (potential SQL/command injection)
    value = value.replace('\x00', '')

    # Strip and check length
    value = value.strip()

    if len(value) > max_length:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be {max_length} characters or less"
        )

    return value


def validate_limit(value: int) -> int:
    """Validate a pagination limit parameter."""
    if value < MIN_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"limit must be at least {MIN_LIMIT}"
        )

    if value > MAX_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"limit must be {MAX_LIMIT} or less"
        )

    return value


def validate_offset(value: int) -> int:
    """Validate a pagination offset parameter."""
    if value < 0:
        raise HTTPException(
            status_code=400,
            detail="offset cannot be negative"
        )

    if value > MAX_OFFSET:
        raise HTTPException(
            status_code=400,
            detail=f"offset must be {MAX_OFFSET} or less"
        )

    return value


def validate_days(value: int, min_days: int = 1) -> int:
    """Validate a days parameter."""
    if value < min_days:
        raise HTTPException(
            status_code=400,
            detail=f"days must be at least {min_days}"
        )

    if value > MAX_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"days must be {MAX_DAYS} or less"
        )

    return value


# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI DEPENDENCIES (Type-annotated validators)
# ─────────────────────────────────────────────────────────────────────────────

# These can be used as type annotations in endpoint parameters

ValidatedLimit = Annotated[
    int,
    Query(
        default=DEFAULT_LIMIT,
        ge=MIN_LIMIT,
        le=MAX_LIMIT,
        description=f"Maximum number of results ({MIN_LIMIT}-{MAX_LIMIT})"
    )
]

ValidatedOffset = Annotated[
    int,
    Query(
        default=0,
        ge=0,
        le=MAX_OFFSET,
        description="Number of results to skip (pagination)"
    )
]

ValidatedDays = Annotated[
    int,
    Query(
        default=30,
        ge=1,
        le=MAX_DAYS,
        description=f"Number of days of history (1-{MAX_DAYS})"
    )
]

BiomarkerSlugPath = Annotated[
    str,
    Path(
        min_length=1,
        max_length=MAX_SLUG_LENGTH,
        pattern=r'^[a-z][a-z0-9_]{0,63}$',
        description="Biomarker identifier (e.g., heart_rate_resting)"
    )
]

BiomarkerSlugQuery = Annotated[
    Optional[str],
    Query(
        default=None,
        min_length=1,
        max_length=MAX_SLUG_LENGTH,
        pattern=r'^[a-z][a-z0-9_]{0,63}$',
        description="Filter by biomarker identifier"
    )
]

SourceSlugQuery = Annotated[
    Optional[str],
    Query(
        default=None,
        min_length=1,
        max_length=MAX_SLUG_LENGTH,
        pattern=r'^[a-z][a-z0-9_-]{0,63}$',
        description="Filter by data source identifier"
    )
]


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORY VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

# Valid annotation categories
VALID_ANNOTATION_CATEGORIES = frozenset([
    "medication",
    "exercise",
    "stress",
    "illness",
    "social",
    "sleep",
    "diet",
    "travel",
    "work",
    "other",
])


def validate_annotation_category(value: str) -> str:
    """Validate an annotation category."""
    value = value.lower().strip()

    if value not in VALID_ANNOTATION_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{value}'. Valid categories: {', '.join(sorted(VALID_ANNOTATION_CATEGORIES))}"
        )

    return value


# Valid biomarker categories
VALID_BIOMARKER_CATEGORIES = frozenset([
    "cardiac",
    "respiratory",
    "sleep",
    "activity",
    "metabolic",
    "mental",
    "body_composition",
    "environmental",
])


def validate_biomarker_category(value: str) -> str:
    """Validate a biomarker category."""
    value = value.lower().strip()

    if value not in VALID_BIOMARKER_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid biomarker category '{value}'. Valid categories: {', '.join(sorted(VALID_BIOMARKER_CATEGORIES))}"
        )

    return value
