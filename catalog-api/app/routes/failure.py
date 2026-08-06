import os
import time

from fastapi import APIRouter

router = APIRouter(tags=["Failure Simulator"])


@router.get("/failure/slow")
def slow_response():
    time.sleep(10)

    return {
        "status": "completed",
        "delay": "10 seconds",
    }


@router.get("/failure/error")
def generate_error():
    raise Exception("Demo application exception")


@router.get("/failure/crash")
def crash_application():
    os._exit(1)


@router.get("/failure/cpu")
def cpu_spike():
    start = time.time()

    while time.time() - start < 20:
        pass

    return {
        "status": "CPU spike completed",
    }


@router.get("/failure/memory")
def memory_leak():
    data = []

    for _ in range(300):
        data.append("X" * 1000000)

    return {
        "status": "Memory allocated",
        "size_mb": len(data),
    }