from fastapi import APIRouter
from pydantic import BaseModel
from app.services import investigation
from app.services import opensre_cli
from app.services import kubectl


class InvestigationRequest(BaseModel):
    alert_payload: str


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
def investigate_pod(namespace: str, pod_name: str):
    return investigation.investigate_pod(namespace, pod_name)
