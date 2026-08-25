import psycopg2
from psycopg2.extras import RealDictCursor

from app.core.config import settings


def get_connection():
    return psycopg2.connect(
        host=settings.YUGABYTE_HOST,
        port=settings.YUGABYTE_PORT,
        database=settings.YUGABYTE_DATABASE,
        user=settings.YUGABYTE_USER,
        password=settings.YUGABYTE_PASSWORD,
    )


def health():
    try:
        conn = get_connection()
        conn.close()
        return {"success": True, "status": "connected"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute(sql: str):
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            if cur.description:
                data = cur.fetchall()
            else:
                data = {"affected_rows": cur.rowcount}
            conn.commit()
        conn.close()
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


def query(sql: str):
    return execute(sql)


def insert(table: str, data: dict):
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    values = tuple(data.values())
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING *"
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, values)
            result = cur.fetchone()
            conn.commit()
        conn.close()
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def update(table: str, data: dict, where: dict):
    set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
    where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])
    values = tuple(list(data.values()) + list(where.values()))
    sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause} RETURNING *"
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, values)
            result = cur.fetchone()
            conn.commit()
        conn.close()
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete(table: str, where: dict):
    where_clause = " AND ".join([f"{k} = %s" for k in where.keys()])
    values = tuple(where.values())
    sql = f"DELETE FROM {table} WHERE {where_clause} RETURNING *"
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, values)
            result = cur.fetchone()
            conn.commit()
        conn.close()
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}