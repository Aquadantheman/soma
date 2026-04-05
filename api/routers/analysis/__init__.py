"""Analysis router package.

Combines all analysis sub-routers into a single router.
Organized by domain for maintainability and scalability:

- proven: Core statistical analyses (circadian, weekly, trends, anomalies)
- advanced: Cross-correlations, recovery models, seasonality, readiness
- stability: Data quality, convergence, drift detection
- derived: Compound metrics derived from multiple biomarkers
- sleep: Sleep architecture analysis (REM%, Deep%, Efficiency)
- daylight: Daylight exposure analysis and sleep correlations
- vo2max: Cardiorespiratory fitness with validated ACSM norms
- body_composition: BMI (WHO), body fat percentile (ACSM), weight trends
- holistic: Cross-domain synthesis with wellness scoring and insights
"""

from fastapi import APIRouter

from .proven import router as proven_router
from .advanced import router as advanced_router
from .stability import router as stability_router
from .derived import router as derived_router
from .sleep import router as sleep_router
from .daylight import router as daylight_router
from .vo2max import router as vo2max_router
from .body_composition import router as body_composition_router
from .holistic import router as holistic_router

# Main router that includes all sub-routers
router = APIRouter(prefix="/analysis", tags=["analysis"])

# Include sub-routers
# Note: Order matters for documentation - most commonly used first
router.include_router(proven_router)
router.include_router(advanced_router)
router.include_router(stability_router)
router.include_router(derived_router)
router.include_router(sleep_router)
router.include_router(daylight_router)
router.include_router(vo2max_router)
router.include_router(body_composition_router)
router.include_router(holistic_router)

__all__ = ["router"]
