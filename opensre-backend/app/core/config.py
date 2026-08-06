import os

from dotenv import load_dotenv

load_dotenv()


class Settings:

    PROJECT_NAME = "OpenSRE Backend"

    VERSION = "1.0.0"

    OPENSRE_BINARY = os.getenv(
        "OPENSRE_BINARY",
        "opensre",
    )

    KUBECONFIG = os.getenv(
        "KUBECONFIG",
        os.path.expanduser("~/.kube/config"),
    )

    VICTORIA_METRICS_URL = os.getenv(
        "VICTORIA_METRICS_URL",
        "http://localhost:8428",
    )

    GRAFANA_URL = os.getenv(
        "GRAFANA_URL",
        "http://localhost:3000",
    )


settings = Settings()