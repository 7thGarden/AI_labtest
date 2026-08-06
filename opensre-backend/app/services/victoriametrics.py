import requests

from app.core.config import settings


def health():

    try:

        response = requests.get(
            f"{settings.VICTORIA_METRICS_URL}/health",
            timeout=5,
        )

        return {
            "status": response.text,
        }

    except Exception as e:

        return {
            "status": "DOWN",
            "error": str(e),
        }