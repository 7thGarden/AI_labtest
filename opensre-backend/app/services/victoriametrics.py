import requests

from app.core.config import settings


def health():
    try:
        response = requests.get(
            f"{settings.VICTORIA_METRICS_URL}/health",
            timeout=5,
        )

        return {
            "success": True,
            "status": response.text,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def query(query: str):
    try:
        response = requests.get(
            f"{settings.VICTORIA_METRICS_URL}/api/v1/query",
            params={"query": query},
            timeout=10,
        )

        response.raise_for_status()

        return {
            "success": True,
            "data": response.json(),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def query_range(query: str, start: float, end: float, step: float):
    try:
        response = requests.get(
            f"{settings.VICTORIA_METRICS_URL}/api/v1/query_range",
            params={"query": query, "start": start, "end": end, "step": step},
            timeout=15,
        )

        response.raise_for_status()

        return {
            "success": True,
            "data": response.json(),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def metrics():
    return query("up")


def label_values(label: str):
    try:
        response = requests.get(
            f"{settings.VICTORIA_METRICS_URL}/api/v1/label/{label}/values",
            timeout=10,
        )

        response.raise_for_status()

        return {
            "success": True,
            "data": response.json().get("data", []),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def targets():
    """
    Discover scrape targets (pods / nodes / instances) from the `up` metric so
    the Metrics page can build per-target dashboards. Falls back to kubectl for
    pods / nodes when the metrics-backed discovery is empty so the dropdowns
    always stay populated.
    """
    result = query(
        "up",
    )

    pods = set()
    nodes = set()
    instances = set()
    jobs = set()

    if result.get("success"):
        series = (
            result.get("data", {})
            .get("data", {})
            .get("result", [])
        )

        for item in series:
            labels = item.get("metric", {})
            pod = labels.get("pod")
            node = labels.get("node")
            instance = labels.get("instance")
            job = labels.get("job")

            if pod:
                pods.add(pod)
            if node:
                nodes.add(node)
            if instance:
                instances.add(instance)
            if job:
                jobs.add(job)

    # Fallback enrichment from kubectl so selectors never empty
    if not pods:
        try:
            from app.services import kubectl

            pod_res = kubectl.get_pods()
            if pod_res.get("success"):
                for line in pod_res.get("stdout", "").splitlines()[1:]:
                    cols = line.split()
                    if len(cols) >= 2:
                        pods.add(cols[1])
        except Exception:
            pass

    if not nodes:
        try:
            from app.services import kubectl

            node_res = kubectl.get_nodes()
            if node_res.get("success"):
                for line in node_res.get("stdout", "").splitlines()[1:]:
                    cols = line.split()
                    if cols:
                        nodes.add(cols[0])
        except Exception:
            pass

    return {
        "success": True,
        "data": {
            "pods": sorted(pods),
            "nodes": sorted(nodes),
            "instances": sorted(instances),
            "jobs": sorted(jobs),
        },
    }


def latency_series(
    window_seconds: int,
    step: int,
    label_matcher: str = "",
):
    """
    Fetch p50 / p95 / p99 request-latency time series over the last
    ``window_seconds`` and return them as flattened {t, value} points using the
    high-resolution ``http_request_duration_highr_seconds_bucket`` histogram.
    Returns the same success/data shape as the other VM helpers.
    """
    end = None
    start = None
    try:
        import time

        end = time.time()
        start = end - window_seconds
    except Exception:
        pass

    if start is None:
        return {"success": False, "error": "unable to compute time window"}

    base = "sum(rate(http_request_duration_highr_seconds_bucket{job!=\"\""
    if label_matcher:
        base += f",{label_matcher}"
    base += "}[1m])) by (le)"

    quantiles = {0.50: "p50", 0.95: "p95", 0.99: "p99"}
    series = {}

    for quantile, name in quantiles.items():
        expr = (
            f"histogram_quantile({quantile}, {base})"
        )
        result = query_range(expr, start, end, step)

        if not result.get("success"):
            series[name] = None
            continue

        points = []

        for item in (
            result.get("data", {})
            .get("data", {})
            .get("result", [])
        ):
            values = item.get("values") or []
            for ts, value in values:
                try:
                    points.append(
                        {"t": int(ts), "v": float(value)}
                    )
                except (TypeError, ValueError):
                    continue

        series[name] = points

    if all(series[name] is None for name in quantiles.values()):
        return {
            "success": False,
            "error": "no latency data available",
        }

    return {
        "success": True,
        "data": {
            "series": series,
            "window_seconds": window_seconds,
            "step": step,
        },
    }


def latency_by_pod():
    """
    Latest p50 / p95 / p99 latency and request rate for each pod in the
    `opensre` namespace, plus a `high` flag when p99 exceeds the tail-latency
    threshold. Pods with no instrumentor scrape (no `http_requests_total`) are
    still listed with `has_data: false` so the Latency page selector covers the
    whole namespace.
    """
    high_threshold = 1.0
    per_pod = {}

    quantiles = {0.50: "p50", 0.95: "p95", 0.99: "p99"}
    base = 'sum by (le, pod) (rate(http_request_duration_highr_seconds_bucket{job="kubernetes-pods"}[1m]))'

    for quantile, name in quantiles.items():
        result = query(f"histogram_quantile({quantile}, {base})")

        if not result.get("success"):
            continue

        for item in (
            result.get("data", {})
            .get("data", {})
            .get("result", [])
        ):
            pod = item.get("metric", {}).get("pod")
            if not pod:
                continue

            try:
                value = float(item.get("value", [None, None])[1])
            except (TypeError, ValueError):
                continue

            per_pod.setdefault(pod, {"pod": pod})[name] = value

    rate_result = query(
        'sum by (pod) (rate(http_requests_total{job="kubernetes-pods"}[1m]))'
    )

    if rate_result.get("success"):
        for item in (
            rate_result.get("data", {})
            .get("data", {})
            .get("result", [])
        ):
            pod = item.get("metric", {}).get("pod")
            if not pod:
                continue

            try:
                value = float(item.get("value", [None, None])[1])
            except (TypeError, ValueError):
                value = None

            per_pod.setdefault(pod, {"pod": pod})["rate"] = value

    # Full pod inventory for the opensre namespace so the Latency page selector
    # shows every app pod, even ones that expose no latency metrics yet.
    opensre_pods = set()

    try:
        from app.services import kubectl

        pod_res = kubectl.get_pods()
        if pod_res.get("success"):
            for line in pod_res.get("stdout", "").splitlines():
                cols = line.split()
                if len(cols) >= 2 and cols[0] == "opensre":
                    opensre_pods.add(cols[1])
    except Exception:
        pass

    pod_names = opensre_pods | set(per_pod.keys())

    pods = []
    for pod in pod_names:
        data = per_pod.get(pod, {})
        p99 = data.get("p99")
        has_data = p99 is not None or data.get("rate") is not None
        pods.append(
            {
                "pod": pod,
                "p50": data.get("p50"),
                "p95": data.get("p95"),
                "p99": p99,
                "rate": data.get("rate"),
                "high": bool(p99 is not None and p99 > high_threshold),
                "has_data": has_data,
            }
        )

    pods.sort(key=lambda p: (-p["has_data"], -(p["rate"] or 0), p["pod"]))

    return {
        "success": True,
        "data": {
            "pods": pods,
            "high_latency_threshold_s": high_threshold,
        },
    }
