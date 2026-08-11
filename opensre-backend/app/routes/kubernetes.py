from fastapi import APIRouter, Query

from app.services import kubectl

router = APIRouter(
    prefix="/api/kubernetes",
    tags=["Kubernetes"],
)


@router.get("/clusters")
def clusters():
    return kubectl.get_clusters()


@router.get("/nodes")
def nodes(context: str | None = Query(default=None)):
    return kubectl.get_nodes(context)


@router.get("/pods")
def pods(context: str | None = Query(default=None)):
    return kubectl.get_pods(context)


@router.get("/services")
def services(context: str | None = Query(default=None)):
    return kubectl.get_services(context)


@router.get("/deployments")
def deployments(context: str | None = Query(default=None)):
    return kubectl.get_deployments(context)
