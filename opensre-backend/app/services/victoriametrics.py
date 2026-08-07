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


def metrics():
    try:
        response = requests.get(
            f"{settings.VICTORIA_METRICS_URL}/metrics",
            timeout=5,
        )

        return {
            "success": True,
            "metrics": response.text,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }