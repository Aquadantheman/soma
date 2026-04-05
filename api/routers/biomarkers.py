"""Biomarker types and data sources endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database import get_db
from ..schemas import BiomarkerType, DataSource
from ..auth import require_auth, AuthContext

router = APIRouter(prefix="/biomarkers", tags=["biomarkers"])


@router.get("", response_model=list[BiomarkerType])
def list_biomarkers(
    category: str | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> list[BiomarkerType]:
    """List all registered biomarker types, optionally filtered by category."""
    query = "SELECT * FROM biomarker_types"
    params = {}

    if category:
        query += " WHERE category = :category"
        params["category"] = category

    query += " ORDER BY category, slug"

    result = db.execute(text(query), params)
    rows = result.mappings().all()
    return [BiomarkerType(**row) for row in rows]


@router.get("/categories")
def list_categories(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> list[str]:
    """List all biomarker categories."""
    result = db.execute(
        text("SELECT DISTINCT category FROM biomarker_types ORDER BY category")
    )
    return [row[0] for row in result]


@router.get("/{slug}", response_model=BiomarkerType)
def get_biomarker(
    slug: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> BiomarkerType:
    """Get a specific biomarker type by slug."""
    result = db.execute(
        text("SELECT * FROM biomarker_types WHERE slug = :slug"),
        {"slug": slug},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Biomarker '{slug}' not found")
    return BiomarkerType(**row)


# ─────────────────────────────────────────
# DATA SOURCES
# ─────────────────────────────────────────
sources_router = APIRouter(prefix="/sources", tags=["sources"])


@sources_router.get("", response_model=list[DataSource])
def list_sources(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> list[DataSource]:
    """List all data sources."""
    result = db.execute(text("SELECT * FROM data_sources ORDER BY name"))
    rows = result.mappings().all()
    return [DataSource(**row) for row in rows]


@sources_router.get("/{slug}", response_model=DataSource)
def get_source(
    slug: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> DataSource:
    """Get a specific data source by slug."""
    result = db.execute(
        text("SELECT * FROM data_sources WHERE slug = :slug"),
        {"slug": slug},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Source '{slug}' not found")
    return DataSource(**row)


# Combine both routers
router.include_router(sources_router)
