import asyncio

from fastapi import Depends, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.core import latency
from app.routes import failure, health, products

app = FastAPI(
    title="Catalog API",
    version="1.0.0",
)

Instrumentator().instrument(app).expose(app)


async def inject_extra_latency():
    """Injected delay applied to every (non-control) request. The sleep runs
    inside the request lifecycle so the instrumentator's histogram records it,
    which is what makes the spike visible on the Latency page."""
    delay = latency.get_delay_seconds()
    if delay > 0:
        await asyncio.sleep(delay)


app.include_router(health.router)

app.include_router(
    products.router,
    dependencies=[Depends(inject_extra_latency)],
)

app.include_router(failure.router)


@app.get("/")
def root():
    return {
        "message": "Catalog API Running",
    }