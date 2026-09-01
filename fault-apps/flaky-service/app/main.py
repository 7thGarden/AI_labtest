import random
import time

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(
    title="Order Service",
    version="1.0.0",
)

Instrumentator().instrument(app).expose(app)


@app.get("/")
def root():
    return {"message": "Order Service Running"}


@app.get("/health")
def health():
    return {"status": "UP"}


@app.get("/orders")
def orders():
    if random.random() < 0.30:
        raise Exception("checkout timeout while contacting payment gateway")

    time.sleep(random.uniform(0.005, 0.15))
    return {
        "order_id": random.randint(10000, 99999),
        "status": "created",
    }


@app.get("/slow")
def slow():
    time.sleep(random.uniform(3.0, 9.0))
    return {"status": "ok", "elapsed": "slow"}