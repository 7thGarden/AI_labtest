"""Kubernetes log + event analysis — pure functions, no I/O.

Extracts *relevant* evidence from pod logs and Kubernetes events so OpenSRE
receives signal instead of raw dumps:

- log lines matching failure signals (ERROR, Exception/Traceback, Failed,
  connection refused, timeout/timed out, OOMKilled, CrashLoopBackOff, probe
  failures), with pod/namespace/container/previous-iteration attribution.
  Original lines are preserved verbatim (timestamps intact); timestamps are
  only parsed best-effort for timeline ordering.
- Warning + relevant events (BackOff, Failed, Unhealthy, FailedScheduling,
  Killing, Pulled, Evicted, OOMKilling, ...) with timestamps for the timeline.

All caps are conservative: the digest budget (~2200 chars) is shared with pod
state and metrics, so relevance beats volume.
"""

import re

# ---------------------------------------------------------------------------
# Log signals (ordered by severity for labeling; a line takes the first match)
# ---------------------------------------------------------------------------

LOG_SIGNAL_PATTERNS = [
    ("oom_killed", re.compile(r"OOMKilled|out of memory|memory cgroup out of memory", re.IGNORECASE)),
    ("traceback", re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE)),
    # DNS resolution failures (kept ahead of generic timeout/connection
    # patterns so DNS-attributed lines keep DNS attribution).
    ("dns_failure", re.compile(
        r"temporary failure in name resolution|name or service not known"
        r"|no such host|SERVFAIL|NXDOMAIN.*SERVFAIL|host not found in upstream"
        r"|no resolver defined|could not resolve|could not be resolved"
        r"|name does not resolve|i/o timeout.*\(.*:53\)|read udp.*:53.*i/o timeout",
        re.IGNORECASE)),
    ("connection_refused", re.compile(r"connection refused|ECONNREFUSED", re.IGNORECASE)),
    ("timeout", re.compile(r"\btimed?\s?out\b|TimeoutError|deadline exceeded", re.IGNORECASE)),
    ("exception", re.compile(r"\b\w*(Exception|Error)\b\s*[:\[]|raise\s+\w*(Exception|Error)", re.IGNORECASE)),
    ("error", re.compile(r"\bERROR\b|\[error\]|\berror:", re.IGNORECASE)),
    ("failed", re.compile(r"\bFAILED\b|\bFailed\b|\bFAIL\b|probe failed|liveness probe|readiness probe", re.IGNORECASE)),
    ("crash", re.compile(r"CrashLoopBackOff|back-off restarting|exit code 1|FATAL|panic:", re.IGNORECASE)),
]

MAX_RELEVANT_LINES = 15
MAX_LINE_CHARS = 300
MAX_TAIL_CONTEXT_LINES = 5

# Best-effort timestamp detection (used only for ordering/labeling; the raw
# line is always preserved verbatim).
_TS_PATTERNS = [
    # 2026-09-11T07:00:00.123Z / 2026-09-11 07:00:00,123 / with +0000 offset
    re.compile(r"(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)"),
    # [11/Sep/2026:12:00:00 +0000] (nginx-style access logs in app output)
    re.compile(r"\[(?P<ts>\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2}[^\]]*)\]"),
    # 07:00:00.123 bare time
    re.compile(r"(?P<ts>\b\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b)"),
]


def _line_timestamp(line: str):
    for pat in _TS_PATTERNS:
        match = pat.search(line or "")
        if match:
            return match.group("ts")
    return None


def _line_signal(line: str):
    for signal, pat in LOG_SIGNAL_PATTERNS:
        if pat.search(line or ""):
            return signal
    return None


def extract_relevant_lines(
    text: str,
    pod: str,
    namespace: str,
    container: str | None = None,
    previous: bool = False,
    max_lines: int = MAX_RELEVANT_LINES,
    max_chars: int = MAX_LINE_CHARS,
):
    """
    Return relevant log entries as a list of dicts:
    {pod, namespace, container, previous, signal, ts, line}.
    Lines are preserved verbatim (truncated to max_chars only).
    """
    entries = []
    for raw in (text or "").splitlines():
        if not raw.strip():
            continue
        signal = _line_signal(raw)
        if signal is None:
            continue
        entries.append(
            {
                "pod": pod,
                "namespace": namespace,
                "container": container,
                "previous": previous,
                "signal": signal,
                "ts": _line_timestamp(raw),
                "line": raw[:max_chars],
            }
        )
        if len(entries) >= max_lines:
            break
    return entries


def summarize_signals(entries):
    counts: dict[str, int] = {}
    for entry in entries or []:
        signal = entry.get("signal", "unknown")
        counts[signal] = counts.get(signal, 0) + 1
    return counts


def tail_context(text: str, max_lines: int = MAX_TAIL_CONTEXT_LINES, max_chars: int = MAX_LINE_CHARS):
    """Last non-empty raw lines for context (verbatim, truncated)."""
    lines = [line for line in (text or "").splitlines() if line.strip()]
    return [line[:max_chars] for line in lines[-max_lines:]]


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

# Reasons worth surfacing, mapped to a coarse severity for the digest.
RELEVANT_EVENT_REASONS = {
    "FailedScheduling": "warning",
    "Failed": "warning",
    "FailedMount": "warning",
    "FailedAttachVolume": "warning",
    "Unhealthy": "warning",
    "BackOff": "warning",
    "CrashLoopBackOff": "warning",
    "ImagePullBackOff": "warning",
    "ErrImagePull": "warning",
    "OOMKilling": "warning",
    "Killing": "info",
    "Evicted": "warning",
    "NodeNotReady": "warning",
    "Pulled": "info",
    "Created": "info",
    "Started": "info",
    "Scheduled": "info",
    "SuccessfulCreate": "info",
}


def _event_timestamp(event: dict):
    for key in ("lastTimestamp", "firstTimestamp", "eventTime", "creationTimestamp"):
        value = event.get(key)
        if value:
            return value
    metadata = event.get("metadata") or {}
    return metadata.get("creationTimestamp")


def parse_events(event_items, max_events: int = 15, warnings_first: bool = True):
    """
    Normalize `kubectl get events -o json` items into timeline-ready dicts:
    {timestamp, reason, type, message, count, involved_object}.
    Warning events and relevant reasons sort first (stable), then by timestamp.
    """
    parsed = []
    for item in event_items or []:
        if not isinstance(item, dict):
            continue
        reason = item.get("reason", "")
        event_type = item.get("type", "")
        message = (item.get("message") or "")[:500]
        involved = item.get("involvedObject") or {}
        parsed.append(
            {
                "timestamp": _event_timestamp(item),
                "reason": reason,
                "type": event_type,
                "message": message,
                "count": item.get("count", 1),
                "involved_object": {
                    "kind": involved.get("kind"),
                    "name": involved.get("name"),
                    "fieldPath": involved.get("fieldPath"),
                },
                "relevant": reason in RELEVANT_EVENT_REASONS or event_type == "Warning",
            }
        )

    relevant = [e for e in parsed if e["relevant"]]
    others = [e for e in parsed if not e["relevant"]]

    def _sort_key(entry):
        # Warnings first (when requested), then timestamp string sort
        # (ISO-8601 sorts lexicographically).
        warn_rank = 0 if entry["type"] == "Warning" else 1
        return (warn_rank, entry.get("timestamp") or "")

    if warnings_first:
        relevant.sort(key=_sort_key)
        others.sort(key=lambda e: e.get("timestamp") or "")
    else:
        relevant.sort(key=lambda e: e.get("timestamp") or "")
        others.sort(key=lambda e: e.get("timestamp") or "")

    return (relevant + others)[:max_events]


def build_timeline(log_entries, structured_events, max_items: int = 20):
    """
    Merge log signals + events into a single best-effort timeline.
    Items without parseable timestamps keep their relative order at the end.
    """
    items = []
    for entry in log_entries or []:
        items.append(
            {
                "ts": entry.get("ts"),
                "source": f"log:{entry.get('container') or '?'}"
                + ("(previous)" if entry.get("previous") else ""),
                "text": f"[{entry.get('signal')}] {entry.get('line')}",
            }
        )
    for event in structured_events or []:
        items.append(
            {
                "ts": event.get("timestamp"),
                "source": "event",
                "text": f"{event.get('type')}/{event.get('reason')}: {event.get('message')}",
            }
        )

    with_ts = [i for i in items if i.get("ts")]
    without_ts = [i for i in items if not i.get("ts")]
    with_ts.sort(key=lambda i: i["ts"])
    return (with_ts + without_ts)[:max_items]
