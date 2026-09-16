from app.services import k8s_log_analysis as m


SAMPLE_LOGS = """2026-09-11T07:00:01Z INFO starting server on :8000
2026-09-11T07:00:02Z ERROR: Failed to connect to database at yugabyte:5433
Traceback (most recent call last):
  File "app.py", line 1, in <module>
ConnectionError: connection refused (host=127.0.0.1 port=5433)
2026-09-11T07:00:05Z INFO Retry 1/3 ...
2026-09-11T07:00:09Z FATAL: Could not initialize database connection
2026-09-11T07:00:10Z upstream timed out after 30s
"""


def test_extract_relevant_lines_labels_signals():
    entries = m.extract_relevant_lines(SAMPLE_LOGS, "p", "opensre", "c1", False)
    assert entries, "expected signal lines to be extracted"
    signals = {e["signal"] for e in entries}
    assert "connection_refused" in signals
    assert "timeout" in signals
    assert "traceback" in signals
    for entry in entries:
        assert entry["pod"] == "p"
        assert entry["namespace"] == "opensre"
        assert entry["container"] == "c1"
        assert entry["previous"] is False
        assert len(entry["line"]) <= m.MAX_LINE_CHARS


def test_extract_preserves_timestamps():
    entries = m.extract_relevant_lines(SAMPLE_LOGS, "p", "opensre", "c1", False)
    error_entry = next(e for e in entries if e["signal"] == "error" or "Failed to connect" in e["line"])
    assert error_entry["ts"] == "2026-09-11T07:00:02Z"
    # verbatim line content preserved
    assert "Failed to connect" in error_entry["line"]


def test_extract_caps_lines():
    big = "\n".join(f"2026-09-11T07:00:{i:02d}Z ERROR boom {i}" for i in range(100))
    entries = m.extract_relevant_lines(big, "p", "opensre", "c1", False)
    assert len(entries) == m.MAX_RELEVANT_LINES


def test_extract_empty_and_clean_logs():
    assert m.extract_relevant_lines("", "p", "opensre", "c1", False) == []
    clean = "2026-09-11T07:00:01Z INFO ok\n2026-09-11T07:00:02Z INFO still ok\n"
    assert m.extract_relevant_lines(clean, "p", "opensre", "c1", False) == []


def test_summarize_signals():
    entries = m.extract_relevant_lines(SAMPLE_LOGS, "p", "opensre", "c1", False)
    counts = m.summarize_signals(entries)
    assert counts.get("connection_refused") == 1
    assert counts.get("timeout") == 1
    assert sum(counts.values()) == len(entries)


def test_parse_events_warnings_first_with_timestamps():
    items = [
        {
            "reason": "Pulled",
            "type": "Normal",
            "message": "ok",
            "count": 1,
            "lastTimestamp": "2026-09-11T06:59:00Z",
            "involvedObject": {"kind": "Pod", "name": "p"},
        },
        {
            "reason": "BackOff",
            "type": "Warning",
            "message": "Back-off restarting failed container",
            "count": 5,
            "lastTimestamp": "2026-09-11T07:01:00Z",
            "involvedObject": {"kind": "Pod", "name": "p"},
        },
    ]
    parsed = m.parse_events(items)
    assert parsed[0]["reason"] == "BackOff"
    assert parsed[0]["timestamp"] == "2026-09-11T07:01:00Z"
    assert parsed[0]["count"] == 5
    assert parsed[0]["relevant"] is True


def test_build_timeline_merges_and_orders():
    entries = m.extract_relevant_lines(SAMPLE_LOGS, "p", "opensre", "c1", False)
    events = m.parse_events([
        {
            "reason": "Unhealthy",
            "type": "Warning",
            "message": "Readiness probe failed",
            "lastTimestamp": "2026-09-11T07:00:06Z",
            "involvedObject": {"kind": "Pod", "name": "p"},
        },
    ])
    timeline = m.build_timeline(entries, events)
    assert timeline
    assert any(i["source"] == "event" for i in timeline)
    assert any(i["source"].startswith("log:") for i in timeline)
    stamped = [i["ts"] for i in timeline if i["ts"]]
    assert stamped == sorted(stamped)
