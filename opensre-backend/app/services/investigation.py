import socket

from app.core.config import settings
from app.services import aerospike
from app.services import containers
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
    "p95_latency_seconds": (
        "histogram_quantile(0.95, "
        "sum(rate(http_request_duration_seconds_bucket[1m])) by (le))"
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

    # VictoriaMetrics evidence
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

    return {
        "success": True,
        "evidence": evidence,
    }
