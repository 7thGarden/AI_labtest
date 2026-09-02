"""Game-day automation: baseline -> inject -> measure -> recover -> report.

Runs one fault from the chaos runbook, samples VictoriaMetrics signals before,
during and after the fault window, health-gates the recovery, and persists a
report JSON (plus a one-line event entry) for the Chaos dashboard.
"""

import json
import random
import time
from pathlib import Path

from app.services import victoriametrics
from app.utils.command import run_command

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = PROJECT_ROOT / "chaos" / "runbook.sh"
EXPERIMENTS_DIR = PROJECT_ROOT / "chaos" / "experiments"

# fault -> (recover action, default pod regex used for metrics sampling)
# recover action "" means the fault self-heals (or has no runbook recovery).
FAULT_PLANS = {
    "aerospike-down": ("aerospike-up", ""),
    "yugabyte-down": ("yugabyte-up", ""),
    "pod-crash": ("", "catalog-api"),
    "pod-delete": ("", "catalog-api"),
    "pod-cpu": ("", "catalog-api"),
    "pod-memory": ("", "catalog-api"),
    "pod-latency": ("latency-off", "catalog-api"),
    "flaky-latency": ("flaky-latency-off", "flaky-service"),
    "system-pod-kill": ("", ""),
    "node-cordon": ("uncordon", ""),
    "node-drain": ("uncordon", ""),
    "node-network-latency": ("network-latency-off", ""),
}


def _pod_matcher(pod_regex):
    if pod_regex == "catalog-api":
        return 'pod=~"catalog-api-.*"'
    if pod_regex == "flaky-service":
        return 'pod=~"flaky-service-.*"'
    if pod_regex:
        return 'pod=~"{}"'.format(pod_regex)
    return 'pod!=""'


def _sample(query):
    """Return a float from a scalar-ish VM query, or None."""
    result = victoriametrics.query(query)
    if not result.get("success"):
        return None
    for item in result.get("data", {}).get("data", {}).get("result", []):
        try:
            value = float(item.get("value", [None, None])[1])
        except (TypeError, ValueError):
            continue
        return value
    return None


def _bucket_rates(matcher):
    """Rate of the latency cumulative histogram buckets (sum by le)."""
    result = victoriametrics.query(
        f'sum by (le) (rate('
        f'http_request_duration_highr_seconds_bucket{{job="kubernetes-pods",{matcher}}}[1m]))'
    )
    buckets = {}
    if not result.get("success"):
        return buckets
    for item in result.get("data", {}).get("data", {}).get("result", []):
        le = item.get("metric", {}).get("le")
        try:
            buckets[le] = float(item.get("value", [None, None])[1])
        except (TypeError, ValueError):
            continue
    return buckets


def _histogram_quantile(quantile, buckets):
    """Correct percentile from cumulative histogram bucket rates.

    VictoriaMetrics' histogram_quantile() miscomputes the flat cumulative case
    (all traffic inside the smallest bucket, e.g. a fully-healthy service after
    a delay is cleared), returning values from the tail buckets instead. This
    is the standard Prometheus interpolation over cumulative buckets.
    """
    try:
        total = buckets.get("+Inf")
        if total is None or total <= 0:
            return None
        order = []
        cumulative = []
        running = 0.0
        for le in sorted(
            (b for b in buckets if b != "+Inf"),
            key=lambda v: float(v),
        ):
            rate = buckets[le]
            if rate is None:
                continue
            # `sum by (le) (rate(bucket...))` already yields cumulative
            # per-second counts, one per le threshold.
            order.append(float(le))
            cumulative.append(rate)
        rank = quantile * total
        for i, upper in enumerate(order):
            if i == 0:
                if rank <= cumulative[0]:
                    fraction = rank / max(cumulative[0], 1e-12)
                    return fraction * upper
                continue
            if rank <= cumulative[i]:
                if cumulative[i] == cumulative[i - 1]:
                    continue
                fraction = (rank - cumulative[i - 1]) / (cumulative[i] - cumulative[i - 1])
                return order[i - 1] + fraction * (upper - order[i - 1])
        return order[-1] if order else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _signals(pod_regex):
    """Latest metrics snapshot for the target pod (or whole opensre workload)."""
    matcher = _pod_matcher(pod_regex)
    buckets = _bucket_rates(matcher)
    p50 = _histogram_quantile(0.50, buckets)
    p95 = _histogram_quantile(0.95, buckets)
    p99 = _histogram_quantile(0.99, buckets)
    rate = _sample(
        f'sum(rate(http_requests_total{{job="kubernetes-pods",{matcher}}}[1m]))'
    )
    errors = _sample(
        f'sum(rate(http_requests_total{{job="kubernetes-pods",{matcher},status=~"5.."}}[1m]))'
    )
    up = _sample(f'count(up{{job="kubernetes-pods",{matcher}}})')

    return {
        "req_s": rate,
        "5xx_s": errors,
        "5xx_pct": round(100 * errors / rate, 2) if errors is not None and rate else None,
        "p50_s": p50,
        "p95_s": p95,
        "p99_s": p99,
        "targets_up": up,
    }


def _run(args):
    """Run the runbook with the given argument list; returns command result."""
    result = run_command(["bash", str(RUNBOOK)] + args)
    return {
        "success": result.get("success", False),
        "stdout": (result.get("stdout") or "")[-2000:],
        "stderr": (result.get("stderr") or "")[-1000:],
    }


def _experiment_id():
    stamp = time.strftime("%Y%m%d%H%M%S")
    return f"exp-{stamp}-{random.randint(0, 9999):04d}"


def _steady_verdict(baseline, during, after):
    """Steady-state hypothesis: is the measured during-window degraded, and
    did signals recover afterwards?"""
    baseline_p99 = baseline.get("p99_s")
    during_p99 = during.get("p99_s")
    after_p99 = after.get("p99_s")

    threshold = 3 * max(baseline_p99 or 0.0, 0.05)
    degraded = bool(during_p99 is not None and during_p99 > threshold)
    recovered = (
        during_p99 is None
        or (after_p99 is not None and after_p99 <= max(baseline_p99 or 0.0, 0.05) * 3)
    )
    return {
        "degraded": degraded,
        "recovered": recovered,
        "baseline_p99_s": baseline_p99,
        "during_p99_s": during_p99,
        "after_p99_s": after_p99,
        "threshold_s": round(threshold, 3),
    }


def _steady_sample(samples, pick):
    """Pick the representative sample across repeats.

    ``during`` uses the worst (max p99) sample, ``after`` the healthiest
    (min p99) sample, so a phase-boundary artifact (in-flight requests at the
    fault on/off moments plus scrape cadence) does not corrupt the report.
    """
    if not samples:
        return {}
    return max(samples, key=lambda s: s.get("p99_s") or 0.0) if pick == "max" else min(
        samples, key=lambda s: s.get("p99_s") if s.get("p99_s") is not None else float("inf")
    )


def run_game_day(action, duration_s=30):
    """Run a full game-day cycle for one chaos fault.

    The latency percentiles come from a 1-minute rate() lookback, so the fault
    must stay active for the full lookback before each ``during`` snapshot, and
    the recovery window must fill with clean samples before ``after``. Each
    phase is sampled twice and reduced (max p99 for during, min p99 for after)
    to guard against phase-boundary artifacts.
    """
    duration_s = max(60, int(duration_s or 60))
    plan = FAULT_PLANS.get(action)
    if not plan:
        return {
            "success": False,
            "error": f"Unknown fault '{action}'. Available: {sorted(FAULT_PLANS.keys())}",
        }
    recover_action, pod_regex = plan
    experiment_id = _experiment_id()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    baseline = _signals(pod_regex)
    inject_result = _run([action])
    if not inject_result.get("success"):
        _persist(experiment_id, action, started, duration_s, baseline, None, None,
                 inject_result, recover_action, {"error": "injection failed"})
        return {
            "success": False,
            "error": inject_result.get("stderr") or inject_result.get("stdout") or "injection failed",
        }

    time.sleep(duration_s)
    during_a = _signals(pod_regex)
    time.sleep(25)
    during_b = _signals(pod_regex)
    during = _steady_sample([during_a, during_b], pick="max")

    recover_result = None
    if recover_action:
        recover_result = _run(["recover", recover_action])
        time.sleep(65)
        after_a = _signals(pod_regex)
        time.sleep(50)
        after_b = _signals(pod_regex)
        after = _steady_sample([after_a, after_b], pick="min")
    else:
        time.sleep(120)
        after_a = _signals(pod_regex)
        time.sleep(45)
        after_b = _signals(pod_regex)
        after = _steady_sample([after_a, after_b], pick="min")

    verdict = _steady_verdict(baseline, during, after)
    report = {
        "id": experiment_id,
        "fault": action,
        "recover_action": recover_action or None,
        "started": started,
        "duration_s": duration_s,
        "pod_target": pod_regex or "all-opensre",
        "baseline": baseline,
        "during": during,
        "after": after,
        "verdict": verdict,
        "injection": {
            "success": inject_result.get("success"),
            "stdout": inject_result.get("stdout")[-500:],
        },
        "recovery": {
            "success": bool(recover_result and recover_result.get("success")),
            "stdout": (recover_result or {}).get("stdout", "")[-300:],
        }
        if recover_result
        else None,
        "success": True,
    }
    _persist(experiment_id, action, started, duration_s, baseline, during, after,
             inject_result, recover_action, verdict)
    return {"success": True, "report": report}


def _persist(experiment_id, action, started, duration_s, baseline, during, after,
             inject_result, recover_action, verdict):
    """Write the game-day report JSON + a compact event line."""
    try:
        EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    report_path = EXPERIMENTS_DIR / f"{experiment_id}.json"
    report = {
        "id": experiment_id,
        "kind": "game-day",
        "fault": action,
        "recover_action": recover_action or None,
        "started": started,
        "duration_s": duration_s,
        "baseline": baseline,
        "during": during,
        "after": after,
        "verdict": verdict,
        "injection": {
            "success": inject_result.get("success"),
            "stdout": inject_result.get("stdout", "")[-300:],
        },
    }
    try:
        report_path.write_text(json.dumps(report, indent=2))
    except OSError:
        pass

    event = {
        "id": experiment_id,
        "kind": "game-day",
        "fault": action,
        "target": _pod_target_label(action),
        "params": f"duration={duration_s}s",
        "note": f"game-day report -> {report_path.name}",
        "ts": started,
    }
    try:
        with (EXPERIMENTS_DIR / "events.jsonl").open("a") as handle:
            handle.write(json.dumps(event) + "\n")
    except OSError:
        pass


def _pod_target_label(action):
    _recover, pod_regex = FAULT_PLANS.get(action, ("", ""))
    return pod_regex or "all-opensre"


def history(limit=200):
    """Newest-first event list from chaos/experiments/events.jsonl."""
    events = []
    try:
        with (EXPERIMENTS_DIR / "events.jsonl").open() as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return {"success": True, "data": []}
    events.reverse()
    return {"success": True, "data": events[:limit]}


def active():
    """Currently-active faults from chaos/experiments/active.json."""
    try:
        with (EXPERIMENTS_DIR / "active.json").open() as handle:
            data = json.load(handle)
    except (FileNotFoundError, ValueError, OSError):
        data = {}
    return {"success": True, "data": data}