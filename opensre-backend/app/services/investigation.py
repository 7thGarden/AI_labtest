from app.services import kubectl
from app.services import victoriametrics


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
