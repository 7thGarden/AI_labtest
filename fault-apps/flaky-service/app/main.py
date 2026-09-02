import random
import threading
import time

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(
    title="Order Service",
    version="1.0.0",
)

Instrumentator().instrument(app).expose(app)

_delay_ms = 0
_delay_lock = threading.Lock()


def set_delay_ms(ms: int) -> int:
    global _delay_ms
    with _delay_lock:
        _delay_ms = max(0, int(ms))
        return _delay_ms


def get_delay_ms() -> int:
    with _delay_lock:
        return _delay_ms


def get_delay_seconds() -> float:
    with _delay_lock:
        return _delay_ms / 1000.0


def extra_latency():
    seconds = get_delay_seconds()
    if seconds > 0:
        time.sleep(seconds)


@app.get("/")
def root():
    return {"message": "Order Service Running"}


@app.get("/health")
def health():
    return {"status": "UP"}


@app.get("/latency")
def set_latency(ms: int = 0):
    """Persistently add `ms` of extra latency to all /orders + /slow traffic.
    `ms=0` turns it off."""
    delay = set_delay_ms(ms)
    return {
        "status": "latency updated",
        "delay_ms": delay,
    }


@app.get("/latency/status")
def latency_status():
    return {
        "status": "ok",
        "delay_ms": get_delay_ms(),
    }


@app.get("/orders")
def orders():
    extra_latency()
    if random.random() < 0.30:
        raise Exception("checkout timeout while contacting payment gateway")

    time.sleep(random.uniform(0.005, 0.15))
    return {
        "order_id": random.randint(10000, 99999),
        "status": "created",
    }


@app.get("/slow")
def slow():
    extra_latency()
    time.sleep(random.uniform(3.0, 9.0))
    return {"status": "ok", "elapsed": "slow"}