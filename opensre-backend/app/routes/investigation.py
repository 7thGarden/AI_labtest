from fastapi import APIRouter, Query

from app.services import git_correlation
from app.services import investigation
from app.utils.command import run_command

router = APIRouter(
    prefix="/api/investigation",
    tags=["Investigation"],
)


@router.get("/git-correlation")
def git_correlation_endpoint(
    incident_start: str | None = Query(
        default=None,
        description="ISO-8601 incident start time (e.g. 2026-09-01T12:43:00Z). "
        "Omit to attribute to the newest commit overall.",
    ),
    branch: str | None = Query(
        default=None,
        description="Branch/tag/SHA to correlate against (default = repo default branch).",
    ),
    limit: int = Query(default=10, ge=1, le=100),
):
    """
    Correlate an incident time with recent git history and identify the
    suspected change-point commit (the newest commit at-or-before the incident
    start). Read-only lookup against the GitHub API; never writes/pushes.
    """
    return git_correlation.correlate_commits(
        incident_start=incident_start,
        limit=limit,
        branch=branch,
    )


@router.get("/analyze")
def analyze_cluster():
    """
    Execute an OpenSRE investigation.
    """
    command = [
        "opensre",
        "investigate",
    ]

    return run_command(command)


@router.get("/evidence/pod/{namespace}/{pod_name}")
def pod_evidence(
    namespace: str,
    pod_name: str,
    context: str | None = Query(default=None),
    tail: int = Query(
        default=200,
        ge=10,
        le=500,
        description="Log lines fetched per container (current + previous when restarted).",
    ),
    signals_only: bool = Query(
        default=False,
        description="Return only the extracted log signals / structured events / timeline (lighter payload).",
    ),
):
    """
    Collect structured Kubernetes + VictoriaMetrics evidence for a pod
    without running an AI investigation.
    """
    result = investigation.collect_pod_evidence(
        namespace,
        pod_name,
        context,
        tail=tail,
    )
    if signals_only and result.get("success"):
        k8s = (result.get("evidence") or {}).get("kubernetes") or {}
        return {
            "success": True,
            "signals": {
                "pod": (result.get("evidence") or {}).get("pod"),
                "state": k8s.get("state"),
                "log_analysis": k8s.get("log_analysis"),
                "events_structured": k8s.get("events_structured"),
                "timeline": k8s.get("timeline"),
            },
        }
    return result


@router.get("/evidence/target/{target_type}")
def target_evidence(target_type: str):
    """
    Collect structured evidence for a host service target (Aerospike /
    YugabyteDB) without running an AI investigation.
    """
    return investigation.collect_target_evidence(target_type)


@router.get("/evidence/stack")
def stack_evidence(
    context: str | None = Query(default=None),
):
    """
    Collect structured evidence for the full observability stack
    (Kubernetes, VictoriaMetrics, OpenTelemetry, Grafana) without
    running an AI investigation.
    """
    return investigation.collect_stack_evidence(context)


@router.get("/evidence/nginx")
def nginx_evidence(
    context: str | None = Query(default=None),
    tail: int = Query(default=250, ge=10, le=2000),
):
    """
    Collect structured Nginx + Kubernetes + VictoriaMetrics evidence
    without running an AI investigation. Independent of databases.
    """
    return investigation.collect_nginx_evidence(context=context, tail=tail)


@router.get("/evidence/coredns")
def coredns_evidence(
    context: str | None = Query(default=None),
    tail: int = Query(default=150, ge=10, le=1000),
):
    """
    Collect structured CoreDNS + DNS probe + metrics + affected-workload
    evidence without running an AI investigation. Independent of databases.
    """
    return investigation.collect_coredns_evidence(context=context, tail=tail)


@router.get("/evidence/elasticsearch")
def elasticsearch_evidence(
    namespace: str | None = Query(default=None),
    pod: str | None = Query(default=None),
    service: str | None = Query(default=None),
    since_minutes: int = Query(default=60, ge=1, le=1440),
):
    """
    Collect structured Elasticsearch evidence without running an AI
    investigation. Read-only; no write/delete/index operations.
    """
    return investigation.collect_elasticsearch_evidence(
        namespace=namespace, pod=pod, service=service,
        since_minutes=since_minutes,
    )