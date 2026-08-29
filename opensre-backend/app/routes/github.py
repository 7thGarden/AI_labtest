from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services import github

router = APIRouter(
    prefix="/api/github",
    tags=["GitHub"],
)


class HealthResponse(BaseModel):
    success: bool
    status: str | None = None
    repo: str | None = None
    error: str | None = None


@router.get("/health", response_model=HealthResponse)
def health():
    return github.health()


@router.get("/branches")
def get_branches():
    return github.get_branches()


@router.get("/commits")
def get_commits(
    sha: str | None = Query(None, description="Branch name, tag, or commit SHA"),
    since: str | None = Query(None, description="ISO 8601 timestamp (e.g., 2024-01-01T00:00:00Z)"),
    until: str | None = Query(None, description="ISO 8601 timestamp"),
    limit: int = Query(50, ge=1, le=100),
):
    return github.get_commits(sha, since, until, limit)


@router.get("/workflows")
def get_workflow_runs(limit: int = Query(20, ge=1, le=100)):
    return github.get_workflow_runs(limit)


@router.get("/issues")
def get_issues(
    state: str = Query("open", pattern="^(open|closed|all)$"),
    limit: int = Query(30, ge=1, le=100),
):
    return github.get_issues(state, limit)


@router.get("/repo")
def get_repo_info():
    return github.get_repo_info()