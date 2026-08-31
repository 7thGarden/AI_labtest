import requests

from app.core.config import settings


def health():
    try:
        response = requests.get(
            f"{settings.GRAFANA_URL}/api/health",
            timeout=5,
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "status": data.get("database", "ok"),
                "version": data.get("version"),
                "commit": data.get("commit"),
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}",
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }