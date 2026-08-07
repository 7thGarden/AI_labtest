from fastapi import APIRouter
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