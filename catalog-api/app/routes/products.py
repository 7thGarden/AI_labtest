from fastapi import APIRouter

router = APIRouter(tags=["Products"])


products = [
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


@router.get("/products")
def get_products():
    return products