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


@router.get("/latency")
def latency_metrics(
    window: int = Query(300, ge=30, le=3600),
    step: int = Query(30, ge=5, le=300),
    instance: str | None = Query(None),
    pod: str | None = Query(None),
):
    matcher = []

    if instance:
        matcher.append(f'instance="{instance}"')
    if pod:
        matcher.append(f'pod="{pod}"')

    return victoriametrics.latency_series(
        window_seconds=window,
        step=step,
        label_matcher=",".join(matcher) if matcher else "",
    )


@router.get("/latency/pods")
def latency_pods():
    return victoriametrics.latency_by_pod()
