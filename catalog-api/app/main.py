from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(
    title="Catalog API",
    version="1.0.0"
)

Instrumentator().instrument(app).expose(app)


@app.get("/")
def root():
    return {
        "message": "Catalog API Running"
    }


@app.get("/health")
def health():
    return {
        "status": "UP"
    }


@app.get("/products")
def products():
    return [
        {
            "id": 1,
            "name": "Laptop",
            "price": 85000,
        },
        {
            "id": 2,
            "name": "Keyboard",
            "price": 2500,
        },
        {
            "id": 3,
            "name": "Mouse",
            "price": 1200,
        },
    ]


@app.get("/failure")
def failure():
    raise Exception("Demo Failure")