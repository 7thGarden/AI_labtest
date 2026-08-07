from fastapi import APIRouter

from app.services import victoriametrics

router = APIRouter(
    prefix="/api/metrics",
    tags=["VictoriaMetrics"],
)


@router.get("/health")
def health():
    return victoriametrics.health()


@router.get("/raw")
def raw_metrics():
    return victoriametrics.metrics()