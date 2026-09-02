#!/usr/bin/env bash
#
# investigate-alert.sh - run an OpenSRE root-cause investigation on an alert
# with live cluster evidence attached, so the report verifies claims against
# real pod/log/metric data instead of producing "Non-Validated Claims".
#
# The `opensre` CLI has no built-in Kubernetes tooling, so this script
# collects evidence through the backend (/api/investigation/evidence/*) and
# passes ONE merged payload to `opensre investigate --input-json`.
#
# Usage:
#   ./scripts/investigate-alert.sh <alert-file.json> [kind-context]
#
# Env:
#   OPENRE_BACKEND_URL   backend base URL   (default http://127.0.0.1:8001)
#
# Examples:
#   ./scripts/investigate-alert.sh /tmp/grafana-alert.json kind-opensre-demo
#   OPENRE_BACKEND_URL=http://localhost:8001 ./scripts/investigate-alert.sh alert.json
#
set -euo pipefail

BACKEND_URL="${OPENRE_BACKEND_URL:-http://127.0.0.1:8001}"
INPUT="${1:-}"
CONTEXT="${2:-}"

if [[ -z "$INPUT" ]]; then
    echo "usage: $0 <alert-file.json> [kind-context]" >&2
    exit 2
fi

if [[ ! -f "$INPUT" ]]; then
    echo "error: alert file not found: $INPUT" >&2
    exit 2
fi

for cmd in curl python3 opensre; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "error: required command not found: $cmd" >&2
        exit 2
    fi
done

# ---------------------------------------------------------------------------
# 1. Determine the alert target (namespace / pod) from the alert JSON.
# ---------------------------------------------------------------------------
read -r NS POD <<< "$(python3 - "$INPUT" <<'PY'
import json, sys

with open(sys.argv[1]) as handle:
    raw = json.load(handle)

alert = raw
if isinstance(raw, dict) and isinstance(raw.get("alerts"), list):
    alert = raw["alerts"][0]
elif isinstance(raw, list):
    alert = raw[0]

labels = alert.get("labels") or {}
annotations = alert.get("annotations") or {}

ns = next(
    (labels.get(k) or annotations.get(k) for k in
     ("namespace", "kubernetes_namespace_name", "exported_namespace", "opensre_namespace")
     if labels.get(k) or annotations.get(k)),
    "",
)
pod = next(
    (labels.get(k) for k in
     ("pod", "kubernetes_pod_name", "exported_pod")
     if labels.get(k)),
    "",
)
print(f"{ns or ''}\n{pod or ''}")
PY
)"

# ---------------------------------------------------------------------------
# 2. Collect live evidence from the backend (it has kubectl + VictoriaMetrics).
# ---------------------------------------------------------------------------
CTX_FLAG=""
if [[ -n "$CONTEXT" ]]; then
    CTX_FLAG="?context=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$CONTEXT")"
fi

if [[ -n "$NS" && -n "$POD" ]]; then
    EVIDENCE_URL="$BACKEND_URL/api/investigation/evidence/pod/$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$NS")/$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$POD")${CTX_FLAG}"
    TARGET_LABEL="pod $POD"
else
    EVIDENCE_URL="$BACKEND_URL/api/investigation/evidence/stack${CTX_FLAG}"
    TARGET_LABEL="opensre-demo observability stack"
fi

if ! curl -sS -m 30 -o /tmp/.opensre-evidence.json "$EVIDENCE_URL"; then
    echo "error: backend unreachable at $BACKEND_URL (start 'uvicorn app.main:app' and try again)" >&2
    echo "  evidence URL: $EVIDENCE_URL" >&2
    exit 1
fi

if ! python3 - "$BACKEND_URL" <<'PY'
import json, sys, urllib.request, urllib.error

try:
    with open("/tmp/.opensre-evidence.json") as handle:
        data = json.load(handle)
except (OSError, ValueError):
    print("error: backend returned non-JSON; cancelling to avoid a thin report", file=sys.stderr)
    sys.exit(1)

if not data.get("success"):
    print("error: evidence collection failed (%s); refusing to run a bare-alert RCA" % data.get("error"))
    sys.exit(1)

json.dump(data.get("evidence", {}), open("/tmp/.opensre-evidence.json", "w"))
PY
then
    exit 1
fi

# ---------------------------------------------------------------------------
# 3. Build a normalised alert whose description carries the evidence digest,
#    matching the shape the OpenSRE CLI's investigate command actually reads.
# ---------------------------------------------------------------------------
python3 - "$INPUT" <<'PY'
import json, sys

with open(sys.argv[1]) as handle:
    raw = json.load(handle)

alert = raw
if isinstance(raw, dict) and isinstance(raw.get("alerts"), list):
    alert = raw["alerts"][0]
elif isinstance(raw, list):
    alert = raw[0]

with open("/tmp/.opensre-evidence.json") as handle:
    evidence = json.load(handle)

labels = dict(alert.get("labels") or {})
annotations = dict(alert.get("annotations") or {})
alertname = labels.get("alertname") or alert.get("alertname") or "OpenSRE Alert"

lines = [f"ALERT: {alertname} (severity={labels.get('severity') or 'unknown'})"]
k8s = evidence.get("kubernetes") or {}

state = k8s.get("state")
if state:
    lines.append(
        f"pod phase={state.get('phase')} node={state.get('node')} ip={state.get('pod_ip')}"
    )
    for container in state.get("containers", []) or []:
        current = container.get("state") or {}
        last = container.get("last_state") or {}
        detail = current.get("reason") or last.get("reason") or "n/a"
        exit_code = last.get("exit_code")
        lines.append(
            f"container {container.get('name')}: ready={container.get('ready')} "
            f"restarts={container.get('restart_count') or 0} reason={detail}"
            + (f" exitCode={exit_code}" if exit_code is not None else "")
        )

status = (k8s.get("pod_status") or "").strip().splitlines()
if len(status) > 1:
    lines.append(f"kubectl: {status[1]}")

events = (k8s.get("events") or "").strip().splitlines()
relevant = [
    line
    for line in events[1:]
    if any(token in line for token in (
        "OOMKilled", "CrashLoopBackOff", "ImagePullBackOff", "BackOff",
        "FailedScheduling", "Unhealthy", "Failed", "Killing", "Evicted",
    ))
]
if relevant:
    lines.append("cluster events:")
    lines.extend(f"  {line}" for line in relevant[-5:])

logs = (k8s.get("logs_tail") or "").strip().splitlines()
if logs:
    lines.append("log tail (last lines):")
    lines.extend(f"  {line[:200]}" for line in logs[-4:] if line.strip())

pod_metrics = (evidence.get("metrics") or {}).get("pod") or {}
if pod_metrics:
    pieces = [
        f"req/s={pod_metrics.get('request_rate_rps')}",
        f"5xx/s={pod_metrics.get('error_rate_5xx_per_s')}",
        f"5xx%={pod_metrics.get('error_share_percent')}",
        f"p50={pod_metrics.get('p50_latency_seconds')}s",
        f"p95={pod_metrics.get('p95_latency_seconds')}s",
        f"p99={pod_metrics.get('p99_latency_seconds')}s",
    ]
    lines.append("pod metrics (last 1m): " + ", ".join(pieces))

digest = "\n".join(lines).strip()[:1800]

original = annotations.get("description") or annotations.get("message") or annotations.get("summary")
annotations["description"] = (
    f"{digest}\n\nalert description: {original}" if original else digest
)

normalized = {
    "status": alert.get("status") or "firing",
    "labels": labels,
    "annotations": annotations,
    "startsAt": alert.get("startsAt") or alert.get("starts_at"),
    "endsAt": alert.get("endsAt") or alert.get("ends_at"),
}

with open("/tmp/.opensre-input.json", "w") as handle:
    json.dump(normalized, handle)
PY

# ---------------------------------------------------------------------------
# 4. Run the grounded investigation.
# ---------------------------------------------------------------------------
echo ">> investigating $TARGET_LABEL with live cluster evidence"
echo "   (alert: $(python3 -c "import json;print(json.load(open('/tmp/.opensre-input.json'))['labels'].get('alertname','?'))"))"
echo

set +e
opensre investigate --input-json "$(cat /tmp/.opensre-input.json)"
CLIEXIT=$?
set -e

rm -f /tmp/.opensre-evidence.json /tmp/.opensre-input.json

exit "$CLIEXIT"