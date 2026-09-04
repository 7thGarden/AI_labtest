import socket

from app.core.config import settings
from app.services import aerospike
from app.services import containers
from app.services import git_correlation
from app.services import grafana
from app.services import kubectl
from app.services import victoriametrics
from app.services import yugabyte


SERVICE_TARGETS = ("aerospike", "yugabyte")
STACK_TARGET = "stack"

VM_QUERIES = {
    "request_rate_rps": "sum(rate(http_requests_total[1m]))",
    "error_rate_5xx_per_s": "sum(rate(http_requests_total{status=\"5xx\"}[1m]))",
    "error_share_percent": (
        "sum(rate(http_requests_total{status=\"5xx\"}[1m])) "
        "/ clamp_min(sum(rate(http_requests_total[1m])), 1e-3) * 100"
    ),
    "p50_latency_seconds": (
        "histogram_quantile(0.50, "
        "sum(rate(http_request_duration_highr_seconds_bucket[1m])) by (le))"
    ),
    "p95_latency_seconds": (
        "histogram_quantile(0.95, "
        "sum(rate(http_request_duration_highr_seconds_bucket[1m])) by (le))"
    ),
    "p99_latency_seconds": (
        "histogram_quantile(0.99, "
        "sum(rate(http_request_duration_highr_seconds_bucket[1m])) by (le))"
    ),
}

OTEL_COLLECTOR_LABEL = "app.kubernetes.io/name=opentelemetry-collector"
OTEL_NAMESPACE = "observability"
OTEL_ENDPOINTS = {
    "otlp_grpc": "127.0.0.1:4317",
    "otlp_http": "127.0.0.1:4318",
    "in_cluster_service": (
        "otel-collector-opentelemetry-collector."
        "observability.svc.cluster.local:4317"
    ),
}
GRAFANA_DASHBOARD_UID = "opensre-overview"


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


def collect_pod_evidence(
    namespace: str,
    pod_name: str,
    context: str | None = None,
):
    evidence = {
        "pod": {
            "namespace": namespace,
            "name": pod_name,
        },
        "cluster": context,
        "kubernetes": {},
        "metrics": {},
    }

    # Structured pod state (phase, node, container statuses, OOM/BackOff reasons)
    state_result = kubectl.get_pod_state(namespace, pod_name, context)

    if state_result.get("success"):
        evidence["kubernetes"]["state"] = state_result.get("state")
    else:
        evidence["kubernetes"]["state_error"] = (
            state_result.get("stderr")
            or state_result.get("error")
            or "Unable to collect pod state"
        )

    # Kubernetes pod details
    pod_result = kubectl.get_pod_details(
        namespace,
        pod_name,
        context,
    )

    if pod_result.get("success"):
        evidence["kubernetes"]["pod_details"] = pod_result.get(
            "stdout",
            "",
        )
    else:
        evidence["kubernetes"]["pod_details_error"] = pod_result.get(
            "stderr",
            "Unable to collect pod details",
        )

    # Pod status / restarts
    status_result = kubectl.get_pod_status(
        namespace,
        pod_name,
        context,
    )

    if status_result.get("success"):
        evidence["kubernetes"]["pod_status"] = status_result.get(
            "stdout",
            "",
        )
    else:
        evidence["kubernetes"]["pod_status_error"] = status_result.get(
            "stderr",
            "Unable to collect pod status",
        )

    # Pod events
    events_result = kubectl.get_pod_events(
        namespace,
        pod_name,
        context,
    )

    if events_result.get("success"):
        evidence["kubernetes"]["events"] = events_result.get(
            "stdout",
            "",
        )
    else:
        evidence["kubernetes"]["events_error"] = events_result.get(
            "stderr",
            "Unable to collect pod events",
        )

    # Container logs (root-cause detail: exceptions, OOM, probe failures)
    logs_result = kubectl.get_pod_logs(
        namespace,
        pod_name,
        tail=60,
        context=context,
    )

    if logs_result.get("success"):
        evidence["kubernetes"]["logs_tail"] = logs_result.get(
            "stdout",
            "",
        )[-4000:]
    else:
        evidence["kubernetes"]["logs_error"] = logs_result.get(
            "stderr",
            "Unable to collect pod logs",
        )

    # Previous-iteration logs (crashloop / already-restarted containers)
    previous_result = kubectl.get_pod_logs(
        namespace,
        pod_name,
        tail=40,
        previous=True,
        context=context,
    )

    if previous_result.get("success"):
        evidence["kubernetes"]["logs_previous"] = previous_result.get(
            "stdout",
            "",
        )[-3500:]
    else:
        evidence["kubernetes"]["logs_previous_available"] = False

    # Pod endpoint
    endpoint_result = kubectl.get_pod_endpoint(
        namespace,
        pod_name,
        context,
    )

    endpoint = None

    if endpoint_result.get("success"):
        endpoint = endpoint_result.get("stdout", "").strip()
        evidence["kubernetes"]["endpoint"] = endpoint
    else:
        evidence["kubernetes"]["endpoint_error"] = endpoint_result.get(
            "stderr",
            "Unable to determine pod endpoint",
        )

    # VictoriaMetrics evidence (scraped endpoint)
    if endpoint:
        up_result = victoriametrics.query(
            f'up{{instance="{endpoint}"}}'
        )

        evidence["metrics"]["up"] = up_result

        memory_result = victoriametrics.query(
            f'process_resident_memory_bytes{{instance="{endpoint}"}}'
        )

        evidence["metrics"]["memory"] = memory_result

        cpu_result = victoriametrics.query(
            f'process_cpu_seconds_total{{instance="{endpoint}"}}'
        )

        evidence["metrics"]["cpu"] = cpu_result

        requests_result = victoriametrics.query(
            f'http_requests_total{{instance="{endpoint}"}}'
        )

        evidence["metrics"]["requests"] = requests_result

    # VictoriaMetrics per-pod traffic + latency metrics (kubernetes-pods job)
    evidence["metrics"]["pod"] = _collect_pod_metrics(pod_name)

    evidence["git"] = git_correlation.correlate_commits(incident_start=None)

    return {
        "success": True,
        "evidence": evidence,
    }


def _collect_pod_metrics(pod_name: str):
    """
    Request rate, error rate and p50/p95/p99 latency for a single pod
    (kubernetes-pods scrape with a `pod` label). Returns None-free dict;
    missing keys mean the pod has no instrumented traffic.
    """
    label = f'pod="{pod_name}"'
    metrics = {}

    rate = _vm_scalar(
        f'sum(rate(http_requests_total{{{label}}}[1m]))'
    )
    error_rate = _vm_scalar(
        f'sum(rate(http_requests_total{{{label},status="5xx"}}[1m]))'
    )

    if rate is not None:
        metrics["request_rate_rps"] = rate

    if error_rate is not None:
        metrics["error_rate_5xx_per_s"] = error_rate
        metrics["error_share_percent"] = round(
            error_rate / (rate or 1e-6) * 100, 2
        )

    if rate is not None:
        base = (
            f'sum(rate(http_request_duration_highr_seconds_bucket{{{label}}}[1m]))'
            " by (le)"
        )
        for quantile, name in ((0.50, "p50"), (0.95, "p95"), (0.99, "p99")):
            value = _vm_scalar(f"histogram_quantile({quantile}, {base})")
            if value is not None:
                metrics[f"{name}_latency_seconds"] = value

    return metrics


def _namespace_summary(namespace: str, context: str | None = None):
    summary = {"namespace": namespace, "pods": []}

    pods_result = kubectl.get_pods(context)

    if not pods_result.get("success"):
        summary["error"] = pods_result.get("stderr", "Unable to list pods")
        return summary

    allowed_statuses = ("Running", "Succeeded", "Completed")
    status_counts = {}

    for line in pods_result.get("stdout", "").splitlines()[1:]:
        columns = line.split()
        if len(columns) >= 5 and columns[0] == namespace:
            entry = {
                "name": columns[1],
                "ready": columns[2],
                "status": columns[3],
                "restarts": columns[4],
            }
            summary["pods"].append(entry)
            status_counts[columns[3]] = status_counts.get(columns[3], 0) + 1

    summary["pod_count"] = len(summary["pods"])
    summary["status_counts"] = status_counts
    summary["degraded_pods"] = [
        pod
        for pod in summary["pods"]
        if pod["status"] not in allowed_statuses
    ]

    return summary


def _tcp_probe(host: str, ports):
    result = {}

    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        try:
            sock.connect((host, port))
            result[str(port)] = {"reachable": True}
        except Exception as exc:
            result[str(port)] = {"reachable": False, "error": str(exc)}
        finally:
            sock.close()

    return result


def _collect_kubernetes_summary(evidence, context):
    summary = {}

    nodes_result = kubectl.get_nodes(context)

    if nodes_result.get("success"):
        nodes = []

        for line in nodes_result.get("stdout", "").splitlines()[1:]:
            columns = line.split()
            if columns:
                nodes.append(
                    {
                        "name": columns[0],
                        "status": columns[1],
                        "roles": columns[2] if len(columns) > 2 else "",
                    }
                )

        summary["nodes"] = nodes
    else:
        summary["nodes_error"] = nodes_result.get("stderr")

    pods_result = kubectl.get_pods(context)
    pods = []

    if pods_result.get("success"):
        for line in pods_result.get("stdout", "").splitlines()[1:]:
            columns = line.split()
            if len(columns) >= 5:
                pods.append(
                    {
                        "namespace": columns[0],
                        "name": columns[1],
                        "ready": columns[2],
                        "status": columns[3],
                        "restarts": columns[4],
                    }
                )

    allowed_statuses = ("Running", "Succeeded", "Completed")

    summary["pods"] = pods[:60]
    summary["degraded_pods"] = [
        pod for pod in pods if pod["status"] not in allowed_statuses
    ]

    status_counts = {}
    for pod in pods:
        status_counts[pod["status"]] = status_counts.get(pod["status"], 0) + 1

    summary["pod_status_counts"] = status_counts
    evidence["kubernetes"] = summary


def _collect_vm_summary(evidence):
    summary = {"health": victoriametrics.health()}

    jobs_result = victoriametrics.label_values("job")

    if jobs_result.get("success"):
        summary["scrape_jobs"] = jobs_result.get("data", [])

    up_result = victoriametrics.query("up")

    if up_result.get("success"):
        targets = []

        for item in up_result.get("data", {}).get("data", {}).get("result", []):
            metric = item.get("metric", {})
            value = "0"

            if item.get("value"):
                value = str(item["value"][1])

            targets.append(
                {
                    "job": metric.get("job"),
                    "instance": metric.get("instance"),
                    "pod": metric.get("pod"),
                    "up": value,
                }
            )

        summary["scrape_targets"] = targets[:30]
        summary["scrape_targets_total"] = len(targets)
        summary["scrape_targets_down"] = len(
            [t for t in targets if t["up"] != "1"]
        )

    for key, query in VM_QUERIES.items():
        summary[key] = _vm_scalar(query)

    evidence["victoriametrics"] = summary


def _collect_otel_summary(evidence, context):
    summary = {
        "pipeline": "otlp (grpc :4317, http :4318) -> prometheusremotewrite -> victoriametrics",
        "endpoints": OTEL_ENDPOINTS,
        "reachability": _tcp_probe("127.0.0.1", (4317, 4318)),
    }

    pod_result = kubectl.get_first_pod_by_label(
        OTEL_NAMESPACE,
        OTEL_COLLECTOR_LABEL,
        context,
    )

    if pod_result.get("success"):
        pod = pod_result.get("stdout", "").strip()

        if pod:
            summary["collector_pod"] = pod

            status_result = kubectl.get_pod_status(
                OTEL_NAMESPACE,
                pod,
                context,
            )

            if status_result.get("success"):
                summary["pod_status"] = status_result.get("stdout", "").strip()

            logs_result = kubectl.get_pod_logs(
                OTEL_NAMESPACE,
                pod,
                tail=40,
                context=context,
            )

            if logs_result.get("success"):
                summary["logs_tail"] = logs_result.get("stdout", "")[-3500:]
            else:
                summary["logs_error"] = logs_result.get("stderr")
    else:
        summary["collector_pod_error"] = pod_result.get("stderr")

    evidence["opentelemetry"] = summary


def _collect_grafana_summary(evidence):
    summary = {
        "health": grafana.health(),
        "datasources": grafana.datasources().get("datasources", []),
        "dashboards": grafana.dashboards().get("dashboards", []),
    }

    dashboard_result = grafana.dashboard_summary(GRAFANA_DASHBOARD_UID)

    if dashboard_result.get("success"):
        summary["primary_dashboard"] = dashboard_result.get("summary")
    else:
        summary["primary_dashboard_error"] = dashboard_result.get("error")

    evidence["grafana"] = summary


def _collect_database_summary(evidence):
    summary = {}

    try:
        summary["aerospike"] = aerospike.health()
    except Exception as exc:
        summary["aerospike"] = {"success": False, "error": str(exc)}

    try:
        summary["yugabyte"] = yugabyte.health()
    except Exception as exc:
        summary["yugabyte"] = {"success": False, "error": str(exc)}

    evidence["databases"] = summary


def collect_stack_evidence(context: str | None = None):
    """
    Collect evidence for the entire observability stack (Kubernetes,
    VictoriaMetrics, OpenTelemetry and Grafana) so AI investigations can
    analyze platform-level incidents beyond a single pod or service.
    """
    evidence = {
        "target": {
            "type": STACK_TARGET,
            "name": "opensre-demo observability stack",
            "components": ["kubernetes", "victoriametrics", "opentelemetry",
                           "grafana"],
        },
        "cluster": context,
        "kubernetes": {},
        "victoriametrics": {},
        "opentelemetry": {},
        "grafana": {},
        "databases": {},
    }

    _collect_kubernetes_summary(evidence, context)
    _collect_vm_summary(evidence)
    _collect_otel_summary(evidence, context)
    _collect_grafana_summary(evidence)
    _collect_database_summary(evidence)

    evidence["git"] = git_correlation.correlate_commits(incident_start=None)

    return {
        "success": True,
        "evidence": evidence,
    }


def collect_target_evidence(target: str):
    """
    Collect evidence for a host service (container-backed database) that is
    not part of the Kubernetes cluster, so AI investigations can analyze it.
    """
    target = target.lower()

    if target not in SERVICE_TARGETS:
        return {
            "success": False,
            "error": (
                f"Unknown target '{target}'. Supported targets: "
                f"{', '.join(SERVICE_TARGETS)}"
            ),
        }

    evidence = {
        "target": {
            "type": target,
            "name": target,
        },
        "cluster": None,
        "service": {},
        "container": {},
        "metrics": {},
    }

    if target == "aerospike":
        evidence["service"]["display_name"] = "Aerospike"
        evidence["service"]["endpoint"] = settings.AEROSPIKE_HOSTS
        evidence["service"]["health"] = aerospike.health()
    else:
        evidence["service"]["display_name"] = "YugabyteDB"
        evidence["service"]["endpoint"] = (
            f"{settings.YUGABYTE_HOST}:{settings.YUGABYTE_PORT}"
        )
        evidence["service"]["health"] = yugabyte.health()

    evidence["container"]["state"] = containers.container_state(target)

    logs = containers.container_logs(target, tail=150)

    if logs.get("success"):
        evidence["container"]["logs"] = logs.get("stdout", "")[-4000:]
    else:
        evidence["container"]["logs_error"] = logs.get("stderr") or logs.get(
            "error",
            "Unable to collect container logs",
        )

    return {
        "success": True,
        "evidence": evidence,
    }


def collect_workflow_evidence(run_id: int):
    """
    Collect evidence for a GitHub Actions workflow run so OpenSRE can
    investigate a failed pipeline. Gathers run details, job steps, and
    the commit it ran against.
    """
    from app.services import github

    run_result = github.get_workflow_run(run_id)
    if not run_result.get("success"):
        return {
            "success": False,
            "error": run_result.get("error", "Unable to fetch workflow run"),
        }

    run = run_result["data"]
    head_sha = run.get("head_sha") or ""
    conclusion = run.get("conclusion") or run.get("status") or "unknown"

    evidence = {
        "workflow_run": {
            "id": run.get("id"),
            "name": run.get("name"),
            "branch": run.get("head_branch"),
            "conclusion": conclusion,
            "status": run.get("status"),
            "head_sha": head_sha,
            "html_url": run.get("html_url"),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "event": run.get("event"),
        },
        "jobs": [],
        "git": git_correlation.correlate_commits(
            incident_start=run.get("created_at"),
            branch=run.get("head_branch"),
        ),
    }

    jobs_result = github.get_workflow_run_jobs(run_id)
    failed_steps = []

    if jobs_result.get("success"):
        for job in jobs_result.get("data") or []:
            job_info = {
                "name": job.get("name"),
                "conclusion": job.get("conclusion"),
                "status": job.get("status"),
                "started_at": job.get("started_at"),
                "completed_at": job.get("completed_at"),
                "steps": [],
            }
            for step in job.get("steps") or []:
                step_info = {
                    "name": step.get("name"),
                    "conclusion": step.get("conclusion"),
                    "status": step.get("status"),
                }
                job_info["steps"].append(step_info)
                if step.get("conclusion") == "failure":
                    failed_steps.append(
                        f"{job.get('name')} / {step.get('name')}"
                    )
            evidence["jobs"].append(job_info)

    summary_lines = [
        f"workflow: {run.get('name')} (run #{run_id})",
        f"branch: {run.get('head_branch')}",
        f"commit: {head_sha[:7]}",
        f"conclusion: {conclusion}",
        f"event: {run.get('event')}",
    ]
    if failed_steps:
        summary_lines.append(f"failed steps: {'; '.join(failed_steps)}")

    git_corr = evidence.get("git") or {}
    suspected = git_corr.get("suspected_commit") or {}
    if suspected.get("sha"):
        summary_lines.append(
            f"suspected change-point: {suspected['sha'][:7]} "
            f"'{suspected.get('message', '')}'"
        )

    evidence["summary"] = "\n".join(summary_lines)

    return {
        "success": True,
        "evidence": evidence,
    }


_ALERT_NAMESPACE_KEYS = (
    "namespace",
    "kubernetes_namespace_name",
    "exported_namespace",
    "opensre_namespace",
)

_ALERT_POD_KEYS = (
    "pod",
    "kubernetes_pod_name",
    "exported_pod",
)


def _alert_target(alert: dict):
    labels = alert.get("labels") or {}

    namespace = None
    for key in _ALERT_NAMESPACE_KEYS:
        if labels.get(key):
            namespace = labels[key]
            break
    else:
        annotations = alert.get("annotations") or {}
        for key in _ALERT_NAMESPACE_KEYS:
            if annotations.get(key):
                namespace = annotations[key]
                break

    pod = None
    for key in _ALERT_POD_KEYS:
        if labels.get(key):
            pod = labels[key]
            break

    return namespace, pod


def collect_alert_evidence(
    alert: dict,
    context: str | None = None,
):
    """
    Attach live cluster evidence to an alert so the OpenSRE RCA can verify
    claims about a pod or namespace instead of relying on the alert alone.

    The OpenSRE CLI's investigate command treats its input as an ALERT payload
    (it reads `labels` / `annotations` directly), so this returns a normalised
    alert whose description carries a compact evidence digest. That is what
    makes the report grounded: the agent reads `annotations.description` and
    can cite real pod/event/metric facts.
    """
    namespace, pod = _alert_target(alert)

    evidence = None

    if namespace and pod:
        result = collect_pod_evidence(namespace, pod, context)

        if result.get("success"):
            evidence = result["evidence"]
            evidence["kubernetes"]["namespace"] = _namespace_summary(
                namespace,
                context,
            )
            evidence["target"] = {
                "type": "pod",
                "namespace": namespace,
                "name": pod,
            }

    if evidence is None:
        result = collect_stack_evidence(context)

        if result.get("success"):
            evidence = result["evidence"]
            evidence["target"] = {
                "type": STACK_TARGET,
                "namespace": namespace,
                "name": "opensre-demo observability stack",
            }

    if evidence is None:
        # Never silently forward a bare alert: that produces unverifiable
        # "Non-Validated Claims" triage instead of a grounded RCA.
        return {
            "success": False,
            "error": "Unable to collect live cluster evidence for the alert",
        }

    starts_at = alert.get("startsAt") or alert.get("starts_at")
    git_corr = git_correlation.correlate_commits(incident_start=starts_at)
    evidence["git"] = git_corr

    digest = _evidence_digest(alert, evidence, git_corr)

    payload = _normalize_alert(alert, digest)

    return {
        "success": True,
        "payload": payload,
        "evidence": evidence,
        "evidence_digest": digest,
    }


def _normalize_alert(alert: dict, digest: str):
    """
    Flatten an alert into the exact shape the OpenSRE CLI's investigate
    command reads, with the evidence digest embedded in the description.
    """
    labels = dict(alert.get("labels") or {})
    annotations = dict(alert.get("annotations") or {})

    if not labels.get("alertname"):
        labels["alertname"] = alert.get("alertname") or "OpenSRE Alert"

    summary = annotations.get("summary") or annotations.get("message")
    description = annotations.get("description") or annotations.get("message")

    annotations["description"] = (
        f"{digest}\n\nalert description: {description}"
        if description
        else digest
    )

    if not annotations.get("summary") and summary:
        annotations["summary"] = summary

    return {
        "status": alert.get("status") or "firing",
        "labels": labels,
        "annotations": annotations,
        "startsAt": alert.get("startsAt") or alert.get("starts_at"),
        "endsAt": alert.get("endsAt") or alert.get("ends_at"),
    }


def _evidence_digest(alert: dict, evidence: dict, git_corr=None, max_chars: int = 2200):
    """
    Compact, human-readable summary of the live facts collected for an alert.
    Folding this into the payload (and description) guarantees the agent sees
    the evidence even if it ignores the structured `evidence` key.
    """
    lines = []

    labels = alert.get("labels") or {}
    annotations = alert.get("annotations") or {}
    alertname = labels.get("alertname") or alert.get("alertname") or "alert"

    lines.append(
        f"ALERT: {alertname} "
        f"(severity={labels.get('severity') or 'unknown'}, "
        f"namespace={labels.get('namespace') or '?'})"
    )
    summary = annotations.get("summary") or annotations.get("message")
    if summary:
        lines.append(f"alert summary: {summary}")

    pod = evidence.get("pod") or {}
    if pod.get("name"):
        lines.append(f"target pod: {pod['name']} (namespace {pod['namespace']})")

    k8s = evidence.get("kubernetes") or {}

    state = k8s.get("state")
    if state:
        lines.append(
            f"pod phase={state.get('phase')} "
            f"node={state.get('node')} ip={state.get('pod_ip')}"
        )
        for container in state.get("containers", []) or []:
            current = container.get("state") or {}
            last = container.get("last_state") or {}
            detail = current.get("reason") or last.get("reason")
            exit_code = last.get("exit_code")
            restart = container.get("restart_count") or 0
            lines.append(
                f"container {container.get('name')}: ready={container.get('ready')} "
                f"restarts={restart} lastState={detail or 'n/a'}"
                + (f" exitCode={exit_code}" if exit_code is not None else "")
            )

    status = (k8s.get("pod_status") or "").strip().splitlines()
    if status and len(status) > 1:
        header = status[0].replace("NOMINATED NODE", "NOMINATED").replace(
            "READINESS GATES",
            "READINESS",
        )
        lines.append(f"kubectl: {header}")
        lines.append(f"kubectl: {status[1]}")

    events = (k8s.get("events") or "").strip().splitlines()
    reason_tokens = (
        "OOMKilled",
        "CrashLoopBackOff",
        "ImagePullBackOff",
        "BackOff",
        "FailedScheduling",
        "Unhealthy",
        "Failed",
        "Killing",
        "Evicted",
    )
    relevant = [
        line
        for line in events[1:]
        if any(token in line for token in reason_tokens)
    ]
    if relevant:
        lines.append("cluster events:")
        lines.extend(f"  {line}" for line in relevant[-6:])

    logs = (k8s.get("logs_tail") or "").strip().splitlines()
    if logs:
        lines.append("log tail (last lines):")
        lines.extend(f"  {line[:220]}" for line in logs[-5:] if line.strip())

    metrics = evidence.get("metrics") or {}
    pod_metrics = metrics.get("pod") or {}
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

    ns = k8s.get("namespace")
    if isinstance(ns, dict) and ns.get("status_counts"):
        counts = ", ".join(
            f"{k}={v}" for k, v in sorted(ns["status_counts"].items())
        )
        degraded = ns.get("degraded_pods") or []
        if degraded:
            lines.append(
                "namespace degraded pods: "
                + ", ".join(
                    f"{p['name']}({p['status']})" for p in degraded[:8]
                )
            )
        lines.append(f"namespace {ns.get('namespace')} status counts: {counts}")

    kubernetes = evidence.get("kubernetes") or {}
    if isinstance(ns, dict) and isinstance(kubernetes, dict) and \
            kubernetes.get("pod_status_counts"):
        counts = ", ".join(
            f"{k}={v}"
            for k, v in sorted(kubernetes["pod_status_counts"].items())
        )
        degraded = kubernetes.get("degraded_pods") or []
        if degraded:
            lines.append(
                "degraded pods: "
                + ", ".join(
                    f"{p['name']}({p['status']})" for p in degraded[:8]
                )
            )
        lines.append(f"cluster pod status counts: {counts}")

    vm = evidence.get("victoriametrics") or {}
    vm_metrics = [
        f"req/s={vm.get('request_rate_rps')}",
        f"5xx/s={vm.get('error_rate_5xx_per_s')}",
        f"5xx%={vm.get('error_share_percent')}",
        f"p50={vm.get('p50_latency_seconds')}s",
        f"p95={vm.get('p95_latency_seconds')}s",
        f"p99={vm.get('p99_latency_seconds')}s",
    ]
    if any(value is not None for value in (
        vm.get("request_rate_rps"),
        vm.get("error_share_percent"),
        vm.get("p99_latency_seconds"),
    )):
        lines.append("cluster metrics (last 1m): " + ", ".join(vm_metrics))

    if vm.get("scrape_targets_total") is not None:
        lines.append(
            f"scrape targets: {vm['scrape_targets_total']} total, "
            f"{vm['scrape_targets_down']} down "
            f"(health={vm.get('health', {}).get('status')})"
        )

    if evidence.get("grafana"):
        lines.append(
            f"grafana health: {evidence['grafana'].get('health', {}).get('status')}"
        )

    otel = evidence.get("opentelemetry") or {}
    if otel.get("pod_status"):
        lines.append(f"otel collector pod: {otel['pod_status']}")

    databases = evidence.get("databases") or {}
    for name, item in databases.items():
        if isinstance(item, dict) and not item.get("success"):
            lines.append(f"database {name}: unhealthy ({item.get('error')})")

    git_lines = git_correlation.git_digest_lines(git_corr)
    if git_lines:
        lines.append("")
        lines.extend(git_lines)

    digest = "\n".join(lines).strip()
    return digest[:max_chars]

