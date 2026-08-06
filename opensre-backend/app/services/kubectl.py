from app.utils.command import run


def get_nodes():

    return run(
        [
            "kubectl",
            "get",
            "nodes",
            "-o",
            "wide",
        ]
    )


def get_pods():

    return run(
        [
            "kubectl",
            "get",
            "pods",
            "-A",
        ]
    )


def get_services():

    return run(
        [
            "kubectl",
            "get",
            "svc",
            "-A",
        ]
    )