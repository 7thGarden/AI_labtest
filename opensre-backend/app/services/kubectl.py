from app.utils.command import run_command


def get_nodes():
    return run_command(
        [
            "kubectl",
            "get",
            "nodes",
            "-o",
            "wide",
        ]
    )


def get_pods():
    return run_command(
        [
            "kubectl",
            "get",
            "pods",
            "-A",
        ]
    )


def get_services():
    return run_command(
        [
            "kubectl",
            "get",
            "svc",
            "-A",
        ]
    )


def get_deployments():
    return run_command(
        [
            "kubectl",
            "get",
            "deployments",
            "-A",
        ]
    )

def get_pod_details(namespace: str, pod_name: str):
    return run_command(
        [
            "kubectl",
            "describe",
            "pod",
            pod_name,
            "-n",
            namespace,
        ]
    )

def get_pod_endpoint(namespace: str, pod_name: str):
    return run_command(
        [
            "kubectl",
            "get",
            "pod",
            pod_name,
            "-n",
            namespace,
            "-o",
            "jsonpath={.status.podIP}:{.spec.containers[0].ports[0].containerPort}",
        ]
    )
