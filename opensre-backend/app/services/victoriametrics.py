import requests

from app.core.config import settings


def health():
    try:
        response = requests.get(
            f"{settings.VICTORIA_METRICS_URL}/health",
            timeout=5,
        )

        return {
            "success": True,
            "status": response.text,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def query(query: str):
    try:
        response = requests.get(
            f"{settings.VICTORIA_METRICS_URL}/api/v1/query",
            params={"query": query},
            timeout=10,
        )

        response.raise_for_status()

        return {
            "success": True,
            "data": response.json(),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def metrics():
    return query("up")
