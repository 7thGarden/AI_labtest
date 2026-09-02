import random
import time

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Traffic Probe")

Instrumentator().instrument(app).expose(app)


@app.get("/health")
def health():
    return {"status": "UP"}


@app.get("/probe")
def probe():
    time.sleep(random.uniform(0.002, 0.012))
    return {"status": "ok"}