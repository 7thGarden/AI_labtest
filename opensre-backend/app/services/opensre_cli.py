from app.core.config import settings
from app.utils.command import run


def doctor():

    return run(
        [
            settings.OPENSRE_BINARY,
            "doctor",
        ]
    )


def status():

    return run(
        [
            settings.OPENSRE_BINARY,
            "status",
        ]
    )


def version():

    return run(
        [
            settings.OPENSRE_BINARY,
            "--version",
        ]
    )