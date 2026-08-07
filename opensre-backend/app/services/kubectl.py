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