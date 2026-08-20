from app.utils.command import run_command


def get_clusters():
    return run_command(
        [
            "kubectl",
            "config",
            "get-contexts",
            "-o",
            "name",
        ]
    )


def get_nodes(context: str | None = None):
    command = [
        "kubectl",
    ]

    if context:
        command.extend(["--context", context])

    command.extend(
        [
            "get",
            "nodes",
            "-o",
            "wide",
        ]
    )

    return run_command(command)


def get_pods(context: str | None = None):
    command = [
        "kubectl",
    ]

    if context:
        command.extend(["--context", context])

    command.extend(
        [
            "get",
            "pods",
            "-A",
        ]
    )

    return run_command(command)


def get_services(context: str | None = None):
    command = [
        "kubectl",
    ]

    if context:
        command.extend(["--context", context])

    command.extend(
        [
            "get",
            "svc",
            "-A",
        ]
    )

    return run_command(command)


def get_deployments(context: str | None = None):
    command = [
        "kubectl",
    ]

    if context:
        command.extend(["--context", context])

    command.extend(
        [
            "get",
            "deployments",
            "-A",
        ]
    )

    return run_command(command)


def get_pod_details(
    namespace: str,
    pod_name: str,
    context: str | None = None,
):
    command = [
        "kubectl",
    ]

    if context:
        command.extend(["--context", context])

    command.extend(
        [
            "describe",
            "pod",
            pod_name,
            "-n",
            namespace,
        ]
    )

    return run_command(command)


def get_pod_status(
    namespace: str,
    pod_name: str,
    context: str | None = None,
):
    command = [
        "kubectl",
    ]

    if context:
        command.extend(["--context", context])

    command.extend(
        [
            "get",
            "pod",
            pod_name,
            "-n",
            namespace,
            "-o",
            "wide",
        ]
    )

    return run_command(command)


def get_pod_events(
    namespace: str,
    pod_name: str,
    context: str | None = None,
):
    command = [
        "kubectl",
    ]

    if context:
        command.extend(["--context", context])

    command.extend(
        [
            "get",
            "events",
            "-n",
            namespace,
            "--field-selector",
            f"involvedObject.name={pod_name}",
            "--sort-by=.metadata.creationTimestamp",
        ]
    )

    return run_command(command)


def get_pod_endpoint(
    namespace: str,
    pod_name: str,
    context: str | None = None,
):
    command = [
        "kubectl",
    ]

    if context:
        command.extend(["--context", context])

    command.extend(
        [
            "get",
            "pod",
            pod_name,
            "-n",
            namespace,
            "-o",
            "jsonpath={.status.podIP}:{.spec.containers[0].ports[0].containerPort}",
        ]
    )

    return run_command(command)
