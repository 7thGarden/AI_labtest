from fastapi import FastAPI

app = FastAPI(
    title="Catalog API",
    description="Demo Catalog API for OpenSRE",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "message": "Catalog API is running",
        "status": "healthy",
    }


@app.get("/health")
def health():
    return {
        "status": "UP",
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