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
