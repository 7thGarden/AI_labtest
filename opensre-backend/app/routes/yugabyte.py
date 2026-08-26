from fastapi import APIRouter
from pydantic import BaseModel

from app.services import yugabyte

router = APIRouter(
    prefix="/api/yugabyte",
    tags=["YugabyteDB"],
)


class QueryRequest(BaseModel):
    sql: str


class InsertRequest(BaseModel):
    table: str
    data: dict


class UpdateRequest(BaseModel):
    table: str
    data: dict
    where: dict


class DeleteRequest(BaseModel):
    table: str
    where: dict


@router.get("/health")
def health():
    return yugabyte.health()


@router.post("/query")
def query_sql(request: QueryRequest):
    return yugabyte.query(request.sql)


@router.post("/execute")
def execute_sql(request: QueryRequest):
    return yugabyte.execute(request.sql)


@router.post("/insert")
def insert_record(request: InsertRequest):
    return yugabyte.insert(request.table, request.data)


@router.post("/update")
def update_record(request: UpdateRequest):
    return yugabyte.update(request.table, request.data, request.where)


@router.post("/delete")
def delete_record(request: DeleteRequest):
    return yugabyte.delete(request.table, request.where)