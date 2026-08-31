import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME = "OpenSRE Backend"
    VERSION = "1.0.0"

    OPENSRE_BINARY = os.getenv("OPENSRE_BINARY", "opensre")

    VICTORIA_METRICS_URL = os.getenv(
        "VICTORIA_METRICS_URL",
        "http://localhost:8428",
    )

    GRAFANA_URL = os.getenv(
        "GRAFANA_URL",
        "http://localhost:3000",
    )

    AEROSPIKE_HOSTS = os.getenv("AEROSPIKE_HOSTS", "127.0.0.1:3001")
    AEROSPIKE_NAMESPACE = os.getenv("AEROSPIKE_NAMESPACE", "test")

    YUGABYTE_HOST = os.getenv("YUGABYTE_HOST", "127.0.0.1")
    YUGABYTE_PORT = int(os.getenv("YUGABYTE_PORT", "5433"))
    YUGABYTE_DATABASE = os.getenv("YUGABYTE_DATABASE", "yugabyte")
    YUGABYTE_USER = os.getenv("YUGABYTE_USER", "yugabyte")
    YUGABYTE_PASSWORD = os.getenv("YUGABYTE_PASSWORD", "yugabyte")

    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
    GITHUB_REPO = os.getenv("GITHUB_REPO", "")
    GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com")


settings = Settings()