from fastapi import APIRouter

from app.services import victoriametrics

router = APIRouter(
    prefix="/api/metrics",
)


@router.get("/health")
def health():
    return victoriametrics.health()