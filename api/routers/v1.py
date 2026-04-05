"""API Version 1 Router.

Groups all v1 endpoints under /v1 prefix for versioned API access.
"""

from fastapi import APIRouter

from .biomarkers import router as biomarkers_router, sources_router
from .signals import router as signals_router
from .baselines import router as baselines_router
from .annotations import router as annotations_router
from .status import router as status_router
from .analysis import router as analysis_router
from .jobs import router as jobs_router
from .oauth import router as oauth_router
from .sync import router as sync_router

# Create versioned router
router = APIRouter(prefix="/v1")

# Include all sub-routers
router.include_router(status_router)
router.include_router(biomarkers_router)
router.include_router(sources_router)
router.include_router(signals_router)
router.include_router(baselines_router)
router.include_router(annotations_router)
router.include_router(analysis_router)
router.include_router(jobs_router)
router.include_router(oauth_router)
router.include_router(sync_router)
