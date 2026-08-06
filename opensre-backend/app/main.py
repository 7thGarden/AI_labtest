from fastapi import FastAPI

from app.routes import health
from app.routes import kubernetes
from app.routes import opensre
from app.routes import metrics

app = FastAPI(
    title="OpenSRE Backend",
    version="1.0.0"
)

app.include_router(health.router)
app.include_router(kubernetes.router)
app.include_router(opensre.router)
app.include_router(metrics.router)