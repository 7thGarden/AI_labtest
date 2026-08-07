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