from fastapi import APIRouter, Query

from app.services import investigation
from app.utils.command import run_command

router = APIRouter(
    prefix="/api/investigation",
    tags=["Investigation"],
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