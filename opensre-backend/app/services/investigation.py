import json

from app.services import opensre_cli


def investigate_pod(namespace: str, pod_name: str):
    alert = {
        "alertname": "KubernetesPodInvestigation",
        "status": "firing",
        "severity": "critical",
        "labels": {
            "namespace": namespace,
            "pod": pod_name,
        },
        "annotations": {
            "summary": f"Investigate Kubernetes pod {pod_name}",
            "description": (
                f"Investigate the health and root cause of pod "
                f"{pod_name} in namespace {namespace}."
            ),
        },
    }

    return opensre_cli.investigate(alert)
