from fastapi import APIRouter, Query

from app.services import victoriametrics, grafana

router = APIRouter(
    prefix="/api/metrics",
    tags=["Metrics"],
)


@router.get("/health")
def health():
    return victoriametrics.health()


@router.get("/grafana/health")
def grafana_health():
    return grafana.health()


@router.get("/raw")
def raw_metrics():
    return victoriametrics.metrics()


@router.get("/query")
def query_metrics(query: str = Query(...)):
    return victoriametrics.query(query)


@router.get("/labels/{label}")
def metric_label_values(label: str):
    return victoriametrics.label_values(label)


@router.get("/targets")
def metrics_targets():
    return victoriametrics.targets()
