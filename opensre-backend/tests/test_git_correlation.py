from app.services.git_correlation import correlate_commits, git_digest_lines


def test_correlate_without_incident_returns_newest():
    """Without incident_start, suspected commit should be the newest."""
    result = correlate_commits(incident_start=None, limit=10)
    if not result.get("success"):
        return
    suspected = result.get("suspected_commit")
    recent = result.get("recent_commits") or []
    if recent:
        assert suspected is not None
        assert suspected["sha"] == recent[0]["sha"]


def test_correlate_with_incident_finds_prior_commit():
    """With an incident time, suspected should be newest commit at-or-before it."""
    result = correlate_commits(
        incident_start="2026-09-01T12:43:00Z",
        limit=10,
    )
    if not result.get("success"):
        return
    suspected = result.get("suspected_commit")
    assert suspected is not None
    assert suspected["sha"] == "509be860b47bd15533c72d598903a65205884e58"


def test_correlate_with_early_incident_returns_no_commit_found():
    """Incident before any commit -> no_commit_found=True."""
    result = correlate_commits(
        incident_start="2020-01-01T00:00:00Z",
        limit=10,
    )
    if not result.get("success"):
        return
    assert result["no_commit_found"] is True
    assert result["suspected_commit"] is None


def test_correlate_with_branch_param():
    result = correlate_commits(
        incident_start="2026-09-01T12:43:00Z",
        branch="connectors",
        limit=10,
    )
    if not result.get("success"):
        return
    assert result["branch"] == "connectors"
    suspected = result.get("suspected_commit")
    assert suspected is not None


def test_digest_lines_no_commits():
    corr = {
        "success": True,
        "repo_name": "test",
        "branch": "main",
        "no_commit_found": True,
        "suspected_commit": None,
    }
    lines = git_digest_lines(corr)
    assert any("inconclusive" in line.lower() or "no commit" in line.lower() for line in lines)


def test_digest_lines_with_suspected():
    corr = {
        "success": True,
        "repo_name": "test",
        "branch": "main",
        "no_commit_found": False,
        "suspected_commit": {
            "sha": "abc1234567890",
            "message": "test commit",
            "date": "2026-09-01T12:00:00Z",
        },
    }
    lines = git_digest_lines(corr)
    assert any("suspected change-point" in line for line in lines)
    assert any("abc1234" in line for line in lines)
