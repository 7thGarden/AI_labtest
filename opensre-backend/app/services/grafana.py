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


def _get(path: str):
    try:
        response = requests.get(
            f"{settings.GRAFANA_URL}{path}",
            timeout=5,
        )
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def datasources():
    result = _get("/api/datasources")

    if not result.get("success"):
        return result

    return {
        "success": True,
        "datasources": [
            {
                "name": item.get("name"),
                "type": item.get("type"),
                "url": item.get("url"),
                "is_default": item.get("isDefault", False),
            }
            for item in result.get("data", [])
        ],
    }


def dashboards():
    result = _get("/api/search")

    if not result.get("success"):
        return result

    return {
        "success": True,
        "dashboards": [
            {
                "uid": item.get("uid"),
                "title": item.get("title"),
                "slug": item.get("slug"),
                "url": item.get("url"),
            }
            for item in result.get("data", [])
        ],
    }


def dashboard_summary(uid: str):
    """
    Fetch a dashboard and summarize its rows/panels so AI evidence includes
    what the operator is looking at without sending the full JSON blob.
    """
    result = _get(f"/api/dashboards/uid/{uid}")

    if not result.get("success"):
        return result

    dashboard = result.get("data", {}).get("dashboard", {})

    panels = []

    def walk(nodes):
        for node in nodes or []:
            sub = node.get("panels")
            if sub:
                panels.append(
                    {
                        "title": node.get("title"),
                        "type": node.get("type", "row"),
                        "panels": [p.get("title") for p in sub],
                    }
                )
                walk(sub)
            else:
                panels.append(
                    {
                        "title": node.get("title"),
                        "type": node.get("type"),
                        "data_sources": sorted(
                            {
                                (t.get("datasource") or {}).get("uid")
                                or t.get("datasource")
                                or "default"
                                for t in node.get("targets", [])
                            }
                        ),
                    }
                )

    walk(dashboard.get("panels", []))

    return {
        "success": True,
        "summary": {
            "title": dashboard.get("title"),
            "uid": dashboard.get("uid"),
            "panels": panels[:30],
        },
    }