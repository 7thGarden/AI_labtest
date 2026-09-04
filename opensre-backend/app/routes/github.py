from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services import github
from app.services import investigation
from app.services import opensre_cli

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


@router.get("/workflow-runs/{run_id}/investigate")
def investigate_workflow_run(run_id: int):
    """
    Investigate a GitHub Actions workflow run. Collects run details, job
    steps, and git correlation, then feeds the evidence to OpenSRE for
    root-cause analysis.
    """
    evidence_result = investigation.collect_workflow_evidence(run_id)

    if not evidence_result.get("success"):
        return evidence_result

    evidence = evidence_result["evidence"]

    alert = {
        "labels": {
            "alertname": f"WorkflowFailed_{evidence['workflow_run']['name']}",
            "severity": "warning",
        },
        "annotations": {
            "summary": (
                f"GitHub Actions workflow '{evidence['workflow_run']['name']}' "
                f"concluded: {evidence['workflow_run']['conclusion']}"
            ),
            "description": evidence.get("summary", ""),
        },
        "startsAt": evidence["workflow_run"].get("created_at"),
    }

    payload = {
        "status": "firing",
        "labels": alert["labels"],
        "annotations": alert["annotations"],
        "startsAt": alert.get("startsAt"),
    }

    return opensre_cli.investigate(payload)