import json

from app.core.config import settings
from app.utils.command import run_command


def version():
    return run_command(
        [
            settings.OPENSRE_BINARY,
            "--version",
        ]
    )


def doctor():
    return run_command(
        [
            settings.OPENSRE_BINARY,
            "doctor",
        ]
    )


def status():
    return run_command(
        [
            settings.OPENSRE_BINARY,
            "status",
        ]
    )


def onboard():
    return run_command(
        [
            settings.OPENSRE_BINARY,
            "onboard",
        ]
    )


def investigate(alert: dict):
    return run_command(
        [
            settings.OPENSRE_BINARY,
            "investigate",
            "--input-json",
            json.dumps(alert),
        ]
    )


def chat(prompt: dict):
    context = prompt.get("context", {})

    alert = {
        "alertname": "OpenSREWebChat",
        "status": "firing",
        "severity": "info",
        "labels": {
            "cluster": context.get("cluster"),
            "namespace": context.get("namespace"),
            "pod": context.get("pod"),
        },
        "annotations": {
            "summary": "OpenSRE Web Chat",
            "description": prompt.get("message", ""),
        },
    }

    return run_command(
        [
            settings.OPENSRE_BINARY,
            "investigate",
            "--input-json",
            json.dumps(alert),
        ]
    )
