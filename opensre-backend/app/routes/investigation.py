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
):
    """
    Collect structured Kubernetes + VictoriaMetrics evidence for a pod
    without running an AI investigation.
    """
    return investigation.collect_pod_evidence(
        namespace,
        pod_name,
        context,
    )


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