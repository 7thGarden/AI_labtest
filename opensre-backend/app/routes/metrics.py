from fastapi import APIRouter, Query

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


@router.get("/query")
def query_metrics(query: str = Query(...)):
    return victoriametrics.query(query)
