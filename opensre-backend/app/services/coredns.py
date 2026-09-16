"""CoreDNS investigation service — read-only, production-grade.

Makes CoreDNS a Kubernetes evidence source for OpenSRE incident
investigation (DNS latency / resolution failures). Covers:

- CoreDNS availability/health (pods in kube-system, phases, readiness)
- pod status / restarts (crash-looping CoreDNS)
- CoreDNS logs with DNS error analysis (SERVFAIL, timeouts, refused,
  forward-plugin failures, loop detection)
- kube-system events affecting CoreDNS
- kube-dns Service / Endpoints (cluster IP + ready backends)
- DNS metrics from the existing VictoriaMetrics setup where available:
  kube-state-metrics pod signals (restarts/phase) plus native
  coredns_dns_* series when scraped (usually absent — reported, not faked)
- live DNS resolution probe: times a real in-cluster lookup executed from an
  app pod (read-only `kubectl exec`), giving DNS query latency and
  success/failure even when no DNS metrics are scraped.

All operations are read-only and safe to run in production. Evidence stays
bounded: per-pod log tails are capped and only the newest signals surface.
"""

import json
import re

from app.core.config import settings
from app.services import victoriametrics
from app.utils.command import run_command

COREDNS_NAMESPACE = getattr(settings, "COREDNS_NAMESPACE", "kube-system")
COREDNS_LABEL = getattr(settings, "COREDNS_LABEL", "k8s-app=kube-dns")
COREDNS_DEPLOYMENT = getattr(settings, "COREDNS_DEPLOYMENT", "coredns")
COREDNS_PROBE_TARGET = getattr(
    settings, "COREDNS_PROBE_TARGET", "kubernetes.default.svc.cluster.local"
)

# Pods to run the live DNS probe from (first match wins, read-only exec).
PROBE_POD_LABELS = ("app=catalog-api", "app=flaky-service")
PROBE_NAMESPACE = "opensre"
PROBE_ATTEMPTS = 3
PROBE_TIMEOUT_S = 5

# Probe latency thresholds (milliseconds, measured end-to-end from an app pod
# through kube-dns). Cluster DNS is normally single-digit ms.
PROBE_WARN_MS = 200.0
PROBE_HIGH_MS = 1000.0

# CoreDNS log signatures. NXDOMAIN is counted separately as informational
# (usually a client typo, not a DNS outage); SERVFAIL/timeouts/refused and
# forward-plugin errors are failure signal.
LOG_PATTERNS = {
    "servfail": re.compile(r"SERVFAIL|server failure", re.IGNORECASE),
    "timeout": re.compile(
        r"i/o timeout|timed out|timeout|deadline exceeded", re.IGNORECASE
    ),
    "refused": re.compile(r"REFUSED|connection refused", re.IGNORECASE),
    "forward_error": re.compile(
        r"plugin/forward|no reachable backend|no upstream|"
        r"failure waiting for connection|connection failed",
        re.IGNORECASE,
    ),
    "loop": re.compile(r"loop detected|plugin/loop", re.IGNORECASE),
    "nxdomain": re.compile(r"NXDOMAIN", re.IGNORECASE),
    "error": re.compile(r"\bERROR\b|\[ERROR\]|\berror:", re.IGNORECASE),
}


def _run(cmd: list[str]):
    return run_command(cmd)


def _kubectl_base(context: str | None = None):
    cmd = ["kubectl"]
    if context:
        cmd.extend(["--context", context])
    return cmd


# ---------------------------------------------------------------------------
# Pod discovery / health
# ---------------------------------------------------------------------------

def get_coredns_pods(
    namespace: str | None = None, context: str | None = None
):
    """List CoreDNS pods by label selector (structured, bounded)."""
    ns = namespace or COREDNS_NAMESPACE
    cmd = _kubectl_base(context) + [
        "get", "pods", "-n", ns, "-l", COREDNS_LABEL, "-o", "json",
    ]
    result = _run(cmd)
    if not result.get("success"):
        return result
    try:
        data = json.loads(result.get("stdout", "{}"))
        pods = []
        for item in data.get("items", []) or []:
            meta = item.get("metadata", {})
            status = item.get("status", {})
            cs_list = status.get("containerStatuses", []) or []
            pods.append(
                {
                    "name": meta.get("name"),
                    "namespace": meta.get("namespace"),
                    "phase": status.get("phase"),
                    "pod_ip": status.get("podIP"),
                    "node": item.get("spec", {}).get("nodeName"),
                    "ready": all(
                        c.get("ready") for c in cs_list
                    ) if cs_list else False,
                    "restart_count": sum(
                        c.get("restartCount", 0) for c in cs_list
                    ),
                    "containers": [
                        {
                            "name": c.get("name"),
                            "ready": c.get("ready"),
                            "restart_count": c.get("restartCount"),
                            "state": c.get("state"),
                            "last_state": c.get("lastState"),
                        }
                        for c in cs_list
                    ],
                }
            )
        return {"success": True, "pods": pods, "count": len(pods)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def health(namespace: str | None = None, context: str | None = None):
    """Quick health: are CoreDNS pods present, Running and ready?"""
    ns = namespace or COREDNS_NAMESPACE
    pods_res = get_coredns_pods(ns, context)
    if not pods_res.get("success"):
        return {
            "success": False,
            "status": "unknown",
            "error": pods_res.get("error") or pods_res.get("stderr"),
        }
    pods = pods_res.get("pods", [])
    if not pods:
        return {
            "success": True,
            "status": "not_deployed",
            "namespace": ns,
            "pods": [],
            "message": f"No pods with label {COREDNS_LABEL} in {ns}",
        }
    running = [p for p in pods if p.get("phase") == "Running"]
    ready = [p for p in pods if p.get("ready")]
    restarts = sum(p.get("restart_count", 0) for p in pods)
    if len(ready) == len(pods):
        status = "healthy"
    elif running:
        status = "degraded"
    else:
        status = "down"
    return {
        "success": True,
        "status": status,
        "namespace": ns,
        "pods": pods,
        "running_pods": len(running),
        "ready_pods": len(ready),
        "total_pods": len(pods),
        "restart_count_total": restarts,
    }


# ---------------------------------------------------------------------------
# Logs / events / service
# ---------------------------------------------------------------------------

def get_coredns_logs(
    namespace: str | None = None,
    pod_name: str | None = None,
    tail: int = 150,
    previous: bool = False,
    context: str | None = None,
):
    """Fetch CoreDNS container logs (read-only, capped)."""
    ns = namespace or COREDNS_NAMESPACE
    if not pod_name:
        pods_res = get_coredns_pods(ns, context)
        if not pods_res.get("success") or not pods_res.get("pods"):
            return {"success": False, "error": "No CoreDNS pods found"}
        pod_name = pods_res["pods"][0]["name"]
    cmd = _kubectl_base(context)
    if previous:
        cmd.append("--previous")
    cmd.extend(["logs", pod_name, "-n", ns, "--tail", str(tail)])
    return _run(cmd)


def get_coredns_events(
    namespace: str | None = None, context: str | None = None
):
    """kube-system events mentioning CoreDNS (read-only, capped)."""
    ns = namespace or COREDNS_NAMESPACE
    result = _run(
        _kubectl_base(context)
        + ["get", "events", "-n", ns, "--sort-by=.lastTimestamp"]
    )
    if not result.get("success"):
        return result
    lines = (result.get("stdout") or "").splitlines()
    header = lines[:1]
    coredns_lines = [
        line for line in lines[1:] if "coredns" in line.lower()
    ][-30:]
    return {
        "success": True,
        "stdout": "\n".join(header + coredns_lines),
        "matched": len(coredns_lines),
        "total": max(0, len(lines) - 1),
    }


def service_and_endpoints(
    namespace: str | None = None, context: str | None = None
):
    """kube-dns Service + Endpoints (read-only)."""
    ns = namespace or COREDNS_NAMESPACE
    svc = _run(
        _kubectl_base(context) + ["get", "svc", "kube-dns", "-n", ns, "-o", "wide"]
    )
    if not svc.get("success"):
        svc = _run(_kubectl_base(context) + ["get", "svc", "-n", ns])
    ep = _run(
        _kubectl_base(context)
        + ["get", "endpoints", "kube-dns", "-n", ns, "-o", "yaml"]
    )
    ep_text = (ep.get("stdout") or "")[:2500]
    ready_addresses = len(re.findall(r"ip:\s+\d+\.\d+\.\d+\.\d+", ep_text))
    return {
        "service": svc,
        "endpoints_success": ep.get("success"),
        "endpoints_ready_addresses": ready_addresses,
        "endpoints_excerpt": ep_text,
    }


def analyze_logs(log_text: str):
    """Count DNS failure signatures; keep bounded verbatim samples."""
    lines = [line for line in (log_text or "").splitlines() if line.strip()]
    counts = {key: 0 for key in LOG_PATTERNS}
    samples: dict[str, list[str]] = {key: [] for key in LOG_PATTERNS}
    for line in lines:
        for key, pattern in LOG_PATTERNS.items():
            if pattern.search(line):
                counts[key] += 1
                if len(samples[key]) < 3:
                    samples[key].append(line[:400])
    interesting = []
    for line in lines[-30:]:
        lowered = line.lower()
        if any(
            token in lowered
            for token in ("servfail", "timeout", "refused", "forward",
                          "loop", "error", "nxdomain")
        ) and len(interesting) < 10:
            interesting.append(line[:400])
    return {
        "total_lines": len(lines),
        "counts": counts,
        "samples": samples,
        "interesting_tail": interesting,
        "has_servfail": counts["servfail"] > 0,
        "has_timeout": counts["timeout"] > 0,
        "has_forward_error": counts["forward_error"] > 0,
        "has_loop": counts["loop"] > 0,
    }


# ---------------------------------------------------------------------------
# Live DNS resolution probe (read-only kubectl exec from an app pod)
# ---------------------------------------------------------------------------

def _probe_command(target: str):
    # The whole probe is one read-only `kubectl exec python3 -c` invocation:
    # N timed getaddrinfo attempts against the in-cluster resolver.
    # Newline-joined (never `;`-joined: compound statements are illegal
    # after a semicolon and `python3 -c` would SyntaxError).
    return "\n".join(
        [
            "import socket,time,json",
            f"socket.setdefaulttimeout({PROBE_TIMEOUT_S})",
            f"target={target!r}",
            f"attempts={PROBE_ATTEMPTS}",
            "ok=0;lats=[];err=None;ips=[]",
            "for _ in range(attempts):",
            "    t0=time.perf_counter()",
            "    try:",
            "        infos=socket.getaddrinfo(target,None)",
            "        dt=(time.perf_counter()-t0)*1000.0",
            "        lats.append(dt);ok+=1",
            "        ips=sorted({i[4][0] for i in infos})",
            "    except Exception as e:",
            "        dt=(time.perf_counter()-t0)*1000.0",
            "        lats.append(dt);err=str(e)[:200]",
            "print(json.dumps({'target':target,'attempts':attempts,'ok':ok,"
            "'latency_ms':lats,'ips':ips,'error':err}))",
        ]
    )


def dns_probe(
    namespace: str | None = None,
    context: str | None = None,
    target: str | None = None,
):
    """Time a real in-cluster DNS lookup from an app pod (read-only).

    Returns per-target latency samples + success count. This is the primary
    DNS-query-latency source when CoreDNS prometheus metrics are not scraped
    (the default: vmagent only scrapes annotated pods).
    """
    name = target or COREDNS_PROBE_TARGET
    probe_pod = None
    for label in PROBE_POD_LABELS:
        res = _run(
            _kubectl_base(context)
            + [
                "get", "pods", "-n", PROBE_NAMESPACE, "-l", label,
                "-o", "jsonpath={.items[0].metadata.name}",
            ]
        )
        if res.get("success") and (res.get("stdout") or "").strip():
            probe_pod = (res.get("stdout") or "").strip()
            break
    if not probe_pod:
        return {
            "success": False,
            "available": False,
            "error": f"No probe pod found in {PROBE_NAMESPACE} "
                     f"(labels {PROBE_POD_LABELS})",
        }
    cmd = _kubectl_base(context) + [
        "exec", "-n", PROBE_NAMESPACE, probe_pod, "--",
        "python3", "-c", _probe_command(name),
    ]
    result = _run(cmd)
    if not result.get("success"):
        return {
            "success": False,
            "available": False,
            "probe_pod": probe_pod,
            "target": name,
            "error": (result.get("stderr") or result.get("stdout")
                      or "probe exec failed")[:500],
        }
    try:
        payload = json.loads((result.get("stdout") or "").strip().splitlines()[-1])
    except Exception as exc:
        return {
            "success": False,
            "available": False,
            "probe_pod": probe_pod,
            "target": name,
            "error": f"unable to parse probe output: {exc}",
            "raw": (result.get("stdout") or "")[:500],
        }
    lats = [float(v) for v in payload.get("latency_ms", []) or []]
    ok = int(payload.get("ok", 0) or 0)
    attempts = int(payload.get("attempts", 0) or 0)
    avg = round(sum(lats) / len(lats), 2) if lats else None
    worst = round(max(lats), 2) if lats else None
    if ok == 0:
        verdict = "failing"
    elif avg is not None and avg >= PROBE_HIGH_MS:
        verdict = "slow"
    elif avg is not None and avg >= PROBE_WARN_MS:
        verdict = "degraded"
    else:
        verdict = "ok"
    return {
        "success": True,
        "available": True,
        "probe_pod": probe_pod,
        "probe_namespace": PROBE_NAMESPACE,
        "target": name,
        "attempts": attempts,
        "succeeded": ok,
        "latency_ms_avg": avg,
        "latency_ms_max": worst,
        "latency_ms_samples": [round(v, 2) for v in lats[:PROBE_ATTEMPTS]],
        "resolved_ips": (payload.get("ips") or [])[:5],
        "error": payload.get("error"),
        "verdict": verdict,
        "thresholds_ms": {"warn": PROBE_WARN_MS, "high": PROBE_HIGH_MS},
    }


# ---------------------------------------------------------------------------
# VictoriaMetrics evidence (best-effort; missing series are reported, not faked)
# ---------------------------------------------------------------------------

def _vm_scalar(query: str):
    try:
        result = victoriametrics.query(query)
        if not result.get("success"):
            return None
        series = result.get("data", {}).get("data", {}).get("result", [])
        if series and series[0].get("value"):
            return round(float(series[0]["value"][1]), 4)
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    return None


def coredns_vm_metrics(namespace: str | None = None):
    """DNS metrics from the existing VictoriaMetrics setup (best-effort).

    kube-state-metrics signals (restarts/phase) are expected to exist;
    native coredns_dns_* series only exist if CoreDNS is scraped — when
    absent the evidence says so explicitly instead of inventing values.
    """
    ns = namespace or COREDNS_NAMESPACE
    pod_matcher = f'namespace="{ns}",pod=~"coredns-.*"'
    values: dict = {}
    notes: list[str] = []

    restarts = _vm_scalar(
        f"sum(kube_pod_container_status_restarts_total{{{pod_matcher}}})"
    )
    running = _vm_scalar(
        f'sum(kube_pod_status_phase{{{pod_matcher},phase="Running"}})'
    )
    if restarts is not None:
        values["restarts_total"] = restarts
    if running is not None:
        values["running_pods"] = running
    kube_state_ok = restarts is not None or running is not None
    if not kube_state_ok:
        notes.append(
            "no kube-state-metrics CoreDNS series in VictoriaMetrics "
            "(kube-state-metrics scrape missing or no coredns pods)"
        )

    dns_queries = _vm_scalar("sum(rate(coredns_dns_requests_total[2m]))")
    servfail = _vm_scalar(
        'sum(rate(coredns_dns_responses_total{rcode="SERVFAIL"}[2m]))'
    )
    dns_p95 = _vm_scalar(
        "histogram_quantile(0.95, "
        "sum(rate(coredns_dns_request_duration_seconds_bucket[2m])) by (le))"
    )
    native = {}
    if dns_queries is not None:
        native["dns_requests_per_s"] = dns_queries
    if servfail is not None:
        native["dns_servfail_per_s"] = servfail
    if dns_p95 is not None:
        native["dns_request_p95_seconds"] = dns_p95
    if native:
        values.update(native)
    else:
        notes.append(
            "no coredns_dns_* series in VictoriaMetrics — CoreDNS is not "
            "scraped by vmagent (only prometheus.io/scrape-annotated pods "
            "are); DNS latency comes from the live resolution probe instead"
        )

    return {
        "values": values,
        "kube_state_available": kube_state_ok,
        "coredns_native_available": bool(native),
        "notes": notes,
        "queries": {
            "restarts_total": "sum(kube_pod_container_status_restarts_total"
                              f"{{{pod_matcher}}})",
            "dns_requests": "sum(rate(coredns_dns_requests_total[2m]))",
            "dns_servfail": 'sum(rate(coredns_dns_responses_total'
                            '{rcode="SERVFAIL"}[2m]))',
        },
    }


# ---------------------------------------------------------------------------
# Full investigation + alert classification
# ---------------------------------------------------------------------------

def investigate_coredns(
    namespace: str | None = None,
    context: str | None = None,
    tail: int = 150,
):
    """Comprehensive read-only CoreDNS investigation — structured evidence."""
    ns = namespace or COREDNS_NAMESPACE
    evidence: dict = {
        "coredns": {
            "namespace": ns,
            "label": COREDNS_LABEL,
            "deployment": COREDNS_DEPLOYMENT,
            "pods": [],
            "health": {},
            "health_status": "unknown",
            "logs": {},
            "log_analysis": {},
            "events": {},
            "service": {},
            "probe": {},
            "metrics": {},
        }
    }
    node = evidence["coredns"]

    pods_res = get_coredns_pods(ns, context)
    pods = pods_res.get("pods", []) if pods_res.get("success") else []
    node["pods"] = pods
    if not pods_res.get("success"):
        node["pods_error"] = (
            pods_res.get("stderr") or pods_res.get("error")
            or "Unable to list CoreDNS pods"
        )

    node["health"] = health(ns, context)
    node["health_status"] = node["health"].get("status", "unknown")

    ev = get_coredns_events(ns, context)
    node["events"] = {
        "success": ev.get("success", False),
        "matched": ev.get("matched", 0),
        "total": ev.get("total", 0),
        "stdout": (ev.get("stdout") or "")[:4000],
        "stderr": (ev.get("stderr") or ev.get("error") or "")[:1000],
    }

    se = service_and_endpoints(ns, context)
    node["service"] = {
        "service_stdout": (se["service"].get("stdout") or "")[:2500],
        "service_success": se["service"].get("success"),
        "endpoints_success": se.get("endpoints_success"),
        "endpoints_ready_addresses": se.get("endpoints_ready_addresses"),
        "endpoints_excerpt": (se.get("endpoints_excerpt") or "")[:2500],
    }

    all_logs = ""
    per_pod_logs = []
    for pod in pods[:2]:  # CoreDNS usually runs 2 replicas; cap at 2
        pod_name = pod["name"]
        logs_res = get_coredns_logs(
            ns, pod_name, tail=tail, context=context
        )
        text = (logs_res.get("stdout") or "")[-8000:]
        analysis = analyze_logs(text) if text.strip() else {
            "total_lines": 0,
            "counts": {k: 0 for k in LOG_PATTERNS},
        }
        per_pod_logs.append(
            {
                "pod": pod_name,
                "logs_success": logs_res.get("success"),
                "logs_tail": text[-4000:],
                "logs_error": logs_res.get("stderr", "")[:500]
                if not logs_res.get("success") else None,
                "analysis": analysis,
            }
        )
        all_logs += "\n" + text

    node["logs"]["per_pod"] = per_pod_logs
    node["logs"]["aggregated_raw"] = all_logs[:8000]
    node["log_analysis"] = (
        analyze_logs(all_logs)
        if all_logs.strip()
        else {"total_lines": 0, "counts": {k: 0 for k in LOG_PATTERNS}}
    )

    try:
        node["probe"] = dns_probe(context=context)
    except Exception as exc:
        node["probe"] = {"success": False, "available": False,
                         "error": str(exc)[:300]}

    try:
        node["metrics"] = coredns_vm_metrics(ns)
    except Exception as exc:
        node["metrics"] = {"values": {}, "notes": [str(exc)[:300]]}

    # Summary for the evidence digest + OpenSRE question framing.
    try:
        agg = node["log_analysis"] or {}
        counts = agg.get("counts", {}) if isinstance(agg, dict) else {}
        probe = node.get("probe", {}) if isinstance(
            node.get("probe"), dict) else {}
        metrics = node.get("metrics", {}) if isinstance(
            node.get("metrics"), dict) else {}
        values = metrics.get("values", {}) or {}
        node["summary"] = {
            "health_status": node.get("health_status"),
            "total_pods": len(pods),
            "running_pods": node["health"].get("running_pods"),
            "ready_pods": node["health"].get("ready_pods"),
            "restart_count_total": node["health"].get("restart_count_total"),
            "restarts_total_vm": values.get("restarts_total"),
            "probe_verdict": probe.get("verdict"),
            "probe_latency_ms_avg": probe.get("latency_ms_avg"),
            "probe_succeeded": probe.get("succeeded"),
            "probe_attempts": probe.get("attempts"),
            "servfail": counts.get("servfail", 0),
            "dns_timeouts": counts.get("timeout", 0),
            "dns_refused": counts.get("refused", 0),
            "forward_errors": counts.get("forward_error", 0),
            "loop_detected": counts.get("loop", 0),
            "nxdomain": counts.get("nxdomain", 0),
            "log_lines": agg.get("total_lines", 0),
            "coredns_native_metrics": metrics.get(
                "coredns_native_available", False),
        }
    except Exception:
        node["summary"] = {}

    return evidence


def is_coredns_alert(alert: dict) -> bool:
    """Classify whether an alert is DNS/CoreDNS-related (no hardcoded RCA)."""
    labels = alert.get("labels") or {}
    annotations = alert.get("annotations") or {}
    haystack = " ".join(
        [
            str(labels.get("alertname", "")),
            str(labels.get("job", "")),
            str(labels.get("pod", "")),
            str(labels.get("namespace", "")),
            str(annotations.get("summary", "")),
            str(annotations.get("description", "")),
        ]
    ).lower()
    tokens = [
        "coredns",
        "kube-dns",
        "kube_dns",
        "dns",
        "servfail",
        "nxdomain",
        "name resolution",
        "could not resolve",
        "could not be resolved",
        "no such host",
        "temporary failure",
        "nameserver",
    ]
    return any(token in haystack for token in tokens)
