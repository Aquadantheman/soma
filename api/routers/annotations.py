"""Annotations endpoints for life events correlation."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional

from ..database import get_db
from ..schemas import Annotation, AnnotationCreate
from ..auth import require_auth, AuthContext

router = APIRouter(prefix="/annotations", tags=["annotations"])


@router.get("", response_model=list[Annotation])
def list_annotations(
    category: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> list[Annotation]:
    """
    List annotations with optional filters.

    Categories: medication, exercise, stress, illness, social
    """
    conditions = []
    params = {"limit": limit, "offset": offset}

    if category:
        conditions.append("category = :category")
        params["category"] = category

    if start_time:
        conditions.append("time >= :start_time")
        params["start_time"] = start_time

    if end_time:
        conditions.append("time <= :end_time")
        params["end_time"] = end_time

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    query = f"""
        SELECT id, time, duration_s, category, label, notes, meta
        FROM annotations
        WHERE {where_clause}
        ORDER BY time DESC
        LIMIT :limit OFFSET :offset
    """

    result = db.execute(text(query), params)
    rows = result.mappings().all()
    return [Annotation(**row) for row in rows]


@router.get("/categories")
def list_annotation_categories(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> list[str]:
    """List all annotation categories that have been used."""
    result = db.execute(
        text("SELECT DISTINCT category FROM annotations ORDER BY category")
    )
    return [row[0] for row in result]


@router.get("/{annotation_id}", response_model=Annotation)
def get_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> Annotation:
    """Get a specific annotation by ID."""
    result = db.execute(
        text("""
            SELECT id, time, duration_s, category, label, notes, meta
            FROM annotations
            WHERE id = :id
        """),
        {"id": annotation_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return Annotation(**row)


@router.post("", response_model=Annotation)
def create_annotation(
    annotation: AnnotationCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> Annotation:
    """
    Create a new annotation.

    Use annotations to mark life events that may correlate with biomarker changes:
    - **medication**: Started/stopped/changed medication
    - **exercise**: Workout, run, yoga, etc.
    - **stress**: Work deadline, conflict, travel
    - **illness**: Cold, flu, infection
    - **social**: Party, isolation, good conversation
    """
    result = db.execute(
        text("""
            INSERT INTO annotations (time, duration_s, category, label, notes, meta)
            VALUES (:time, :duration_s, :category, :label, :notes, :meta)
            RETURNING id
        """),
        {
            "time": annotation.time,
            "duration_s": annotation.duration_s,
            "category": annotation.category,
            "label": annotation.label,
            "notes": annotation.notes,
            "meta": annotation.meta,
        },
    )
    new_id = result.scalar()
    db.commit()

    return Annotation(
        id=new_id,
        time=annotation.time,
        duration_s=annotation.duration_s,
        category=annotation.category,
        label=annotation.label,
        notes=annotation.notes,
        meta=annotation.meta,
    )


@router.delete("/{annotation_id}")
def delete_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> dict:
    """Delete an annotation."""
    result = db.execute(
        text("DELETE FROM annotations WHERE id = :id RETURNING id"),
        {"id": annotation_id},
    )
    deleted_id = result.scalar()
    db.commit()

    if not deleted_id:
        raise HTTPException(status_code=404, detail="Annotation not found")

    return {"deleted": annotation_id}
