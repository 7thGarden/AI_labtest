import aerospike
from aerospike import exception as aerospike_exception

from app.core.config import settings


def get_client():
    config = {
        "hosts": [
            (h.split(":")[0], int(h.split(":")[1])) for h in settings.AEROSPIKE_HOSTS.split(",")
        ],
    }
    return aerospike.client(config).connect()


def health():
    try:
        client = get_client()
        client.close()
        return {"success": True, "status": "connected"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def query(namespace: str, set_name: str, key: str):
    try:
        client = get_client()
        key_tuple = (namespace, set_name, key)
        _, _, bins = client.get(key_tuple)
        client.close()
        return {"success": True, "data": bins}
    except aerospike_exception.RecordNotFound:
        return {"success": False, "error": "Record not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def write(namespace: str, set_name: str, key: str, bins: dict):
    try:
        client = get_client()
        key_tuple = (namespace, set_name, key)
        client.put(key_tuple, bins)
        client.close()
        return {"success": True, "message": "Record written"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete(namespace: str, set_name: str, key: str):
    try:
        client = get_client()
        key_tuple = (namespace, set_name, key)
        client.remove(key_tuple)
        client.close()
        return {"success": True, "message": "Record deleted"}
    except aerospike_exception.RecordNotFound:
        return {"success": False, "error": "Record not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def scan(namespace: str, set_name: str):
    try:
        client = get_client()
        records = []
        scan = client.scan(namespace, set_name)
        scan.foreach(lambda r: records.append({"key": r[0][2], "bins": r[2]}))
        client.close()
        return {"success": True, "data": records}
    except Exception as e:
        return {"success": False, "error": str(e)}