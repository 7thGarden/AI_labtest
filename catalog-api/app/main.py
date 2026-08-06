from fastapi import FastAPI

from app.routes.health import router as health_router
from app.routes.products import router as products_router
from app.routes.failure import router as failure_router

app = FastAPI(
    title="Catalog API",
    version="1.0.0",
    description="Demo Catalog API for OpenSRE",
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(failure_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "application": "Catalog API",
        "status": "running",
        "version": "1.0.0"
    }