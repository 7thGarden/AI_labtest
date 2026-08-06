from fastapi import APIRouter

from app.services import kubectl

router = APIRouter(
    prefix="/api/kubernetes",
)


@router.get("/nodes")
def nodes():
    return kubectl.get_nodes()


@router.get("/pods")
def pods():
    return kubectl.get_pods()


@router.get("/services")
def services():
    return kubectl.get_services()