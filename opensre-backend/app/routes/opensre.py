from fastapi import APIRouter

from app.services import opensre_cli

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