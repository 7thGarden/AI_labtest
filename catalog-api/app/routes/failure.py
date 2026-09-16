import logging
import os
import time
import uuid

from fastapi import APIRouter, Request

from app.core import latency

logger = logging.getLogger("catalog-api")

router = APIRouter(tags=["Failure Simulator"])

def _request_id(request: Request | None) -> str:
    if request is None:
        return str(uuid.uuid4())[:8]
    return request.headers.get("x-request-id") or str(uuid.uuid4())[:8]


@router.get("/failure/slow")
def slow_response(request: Request | None = None):
    rid = _request_id(request)
    logger.warning("slow-response start", extra={"request_id": rid})
    time.sleep(10)
    logger.error("slow-response timeout", extra={"request_id": rid, "error": "TIMED OUT after 10s"})
    return {
        "status": "completed",
        "delay": "10 seconds",
        "request_id": rid,
    }


@router.get("/failure/error")
def generate_error(request: Request | None = None):
    rid = _request_id(request)
    logger.error("Demo application exception", extra={
        "request_id": rid,
        "error": {"type": "Exception", "message": "Demo application exception"},
    })
    raise Exception("Demo application exception")


@router.get("/failure/connection-refused")
def connection_refused(request: Request | None = None):
    rid = _request_id(request)
    logger.error("CONNECTION REFUSED", extra={
        "request_id": rid,
        "error": {"type": "ConnectionError", "message": "Connection refused (host=127.0.0.1 port=5433)"},
    })
    return {
        "status": "connection-refused",
        "request_id": rid,
        "error": "Connection refused (host=127.0.0.1 port=5433)",
    }


@router.get("/failure/crash")
def crash_application():
    logger.critical("Application crash requested", extra={"error": {"type": "SystemExit", "message": "os._exit(1)"}})
    os._exit(1)


@router.get("/failure/cpu")
def cpu_spike():
    rid = str(uuid.uuid4())[:8]
    logger.warning("CPU spike start", extra={"request_id": rid})
    start = time.time()
    while time.time() - start < 20:
        pass
    logger.error("CPU spike completed", extra={"request_id": rid})
    return {"status": "CPU spike completed", "request_id": rid}


@router.get("/failure/memory")
def memory_leak():
    rid = str(uuid.uuid4())[:8]
    logger.warning("Memory leak start", extra={"request_id": rid})
    data = []
    for _ in range(300):
        data.append("X" * 1000000)
    logger.error("Memory allocated (possible OOM)", extra={"request_id": rid, "size_mb": len(data)})
    return {"status": "Memory allocated", "size_mb": len(data), "request_id": rid}


@router.get("/failure/timed-out")
def timed_out(request: Request | None = None):
    rid = _request_id(request)
    logger.error("TIMED OUT", extra={
        "request_id": rid,
        "error": {"type": "TimeoutError", "message": "Request timed out after 30s"},
    })
    return {"status": "timed-out", "request_id": rid}


@router.get("/failure/latency")
def set_latency(ms: int = 0):
    """Persistently add `ms` of extra latency to all catalog-api traffic
    (everything except /failure, /metrics and /health). `ms=0` turns it off."""
    delay = latency.set_delay_ms(ms)
    return {
        "status": "latency updated",
        "delay_ms": delay,
    }


@router.get("/failure/latency/status")
def latency_status():
    return {
        "status": "ok",
        "delay_ms": latency.get_delay_ms(),
    }