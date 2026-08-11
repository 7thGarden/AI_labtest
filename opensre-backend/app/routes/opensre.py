from fastapi import APIRouter
from pydantic import BaseModel

from app.services import investigation
from app.services import opensre_cli


class InvestigationRequest(BaseModel):
    alert_payload: str


class ChatRequest(BaseModel):
    message: str
    cluster: str | None = None
    namespace: str | None = None
    pod: str | None = None


router = APIRouter(
    prefix="/api/opensre",
    tags=["OpenSRE"],
)


@router.get("/version")
def version():
    return opensre_cli.version()


@router.get("/doctor")
def doctor():
    return opensre_cli.doctor()


@router.get("/status")
def status():
    return opensre_cli.status()


@router.post("/investigate")
def investigate(request: InvestigationRequest):
    return opensre_cli.investigate(request.alert_payload)


@router.get("/investigate/pod/{namespace}/{pod_name}")
def investigate_pod(
    namespace: str,
    pod_name: str,
    context: str | None = None,
):
    evidence_result = investigation.collect_pod_evidence(
        namespace,
        pod_name,
        context,
    )

    if not evidence_result.get("success"):
        return evidence_result

    return opensre_cli.investigate(
        evidence_result["evidence"]
    )


@router.post("/chat")
def chat(request: ChatRequest):
    # If a pod is selected, collect real Kubernetes evidence
    # from the selected cluster before sending the request to OpenSRE.
    if request.namespace and request.pod:
        evidence_result = investigation.collect_pod_evidence(
            request.namespace,
            request.pod,
            request.cluster,
        )

        if not evidence_result.get("success"):
            return evidence_result

        evidence = evidence_result["evidence"]

        # Add the user's actual question to the evidence.
        evidence["question"] = request.message

        return opensre_cli.investigate(evidence)

    # Fallback when no pod is selected.
    return opensre_cli.chat(
        {
            "message": request.message,
            "context": {
                "cluster": request.cluster,
                "namespace": request.namespace,
                "pod": request.pod,
            },
        }
    )
