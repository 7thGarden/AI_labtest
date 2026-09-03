"""Git commit correlation for incident investigations.

Ties an on-cluster incident (pod degradation, alert, game-day) to the most
recent repository commit at-or-before the incident start time. The backend
reads the remote repo over the GitHub API, so only *pushed* commits are
visible -- this is a read-only lookup, never a write/push.
"""

from datetime import datetime, timezone

from app.core.config import settings
from app.services import github


def _parse_iso(value):
    """Parse an ISO-8601 timestamp to a UTC-aware datetime, or None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _commit_record(commit):
    info = commit.get("commit") or {}
    author = info.get("author") or {}
    return {
        "sha": commit.get("sha"),
        "message": (info.get("message") or "").splitlines()[0]
        if info.get("message")
        else "",
        "author": author.get("name") or (commit.get("author") or {}).get("login"),
        "date": author.get("date"),
    }


def correlate_commits(incident_start=None, limit=10, branch=None):
    """
    Return the remotest commits newest-first, marking the first commit at-or-
    before ``incident_start`` (or the newest overall when no timestamp is
    given) as the suspected change point. Returns a dict with a ``success``
    flag; on failure/short-circuit the caller can skip git enrichment.

    ``branch`` selects the branch/tag/SHA to correlate against (defaults to the
    repository default branch, matching what the GitHub page shows). This makes
    attribution unambiguous in a multi-branch repo.
    """
    repo = getattr(settings, "GITHUB_REPO", None) or ""
    dash = repo.rstrip("/").rpartition("/")[-1]
    repo_name = dash or "repository"

    commits_result = github.get_commits(sha=branch, limit=limit)
    if not commits_result.get("success"):
        return {
            "success": False,
            "error": commits_result.get("error", "GitHub commits unavailable"),
        }

    raw = commits_result.get("data") or []
    commits = [_commit_record(c) for c in raw]

    incident_at = _parse_iso(incident_start)

    requested_found = False
    suspected = None
    if incident_at is not None:
        for entry in commits:
            date = _parse_iso(entry.get("date"))
            if date is not None and date <= incident_at:
                suspected = entry
                requested_found = True
                break
    elif commits:
        suspected = commits[0]
        requested_found = True

    window_before = []
    if incident_at is not None:
        window_before = [
            entry
            for entry in commits
            if (d := _parse_iso(entry.get("date"))) is not None
            and d <= incident_at
        ][:3]
    else:
        window_before = commits[:3]

    return {
        "success": True,
        "repo": repo or None,
        "repo_name": repo_name,
        "incident_start": incident_start,
        "branch": branch,
        "suspected_commit": suspected,
        "found_before_incident": requested_found,
        "no_commit_found": bool(incident_at is not None and not requested_found),
        "recent_commits": commits[:limit],
        "window_before_incident": window_before,
    }


def git_digest_lines(correlation):
    """Human-readable lines for the evidence digest, or [] if not usable."""
    if not correlation or not correlation.get("success"):
        return []

    lines = []
    repo = correlation.get("repo_name") or correlation.get("repo") or "repository"
    branch = correlation.get("branch") or "default branch"

    if correlation.get("no_commit_found"):
        lines.append(
            f"git history ({repo}): no commit found at-or-before the incident "
            f"start on '{branch}' - the incident predates the available history "
            f"or pre-dates any deploy; attribution is inconclusive"
        )
        return lines

    suspected = correlation.get("suspected_commit")
    if suspected and suspected.get("sha"):
        date = suspected.get("date") or "?"
        lines.append(
            f"git history ({repo}, {branch}): suspected change-point "
            f"commit {suspected['sha'][:7]} '{suspected.get('message')}' "
            f"({date})"
        )
    else:
        lines.append(f"git history ({repo}): no commits available to correlate")

    window = correlation.get("window_before_incident") or []
    if window:
        recent = ", ".join(
            f"{entry['sha'][:7]}'{entry.get('message')}'"
            for entry in window
            if entry.get("sha")
        )
        lines.append(f"commits before incident: {recent}")

    return lines
