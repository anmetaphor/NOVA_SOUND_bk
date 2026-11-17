"""Acceso a SQL Server con pyodbc (una conexión por petición)."""
from contextlib import contextmanager

from flask import g

import config


def _conn_str():
    base = (
        f"DRIVER={{{config.DB_DRIVER}}};SERVER={config.DB_SERVER};"
        f"DATABASE={config.DB_NAME};TrustServerCertificate=yes;"
    )
    if config.DB_TRUSTED:
        return base + "Trusted_Connection=yes;"
    return base + f"UID={config.DB_USER};PWD={config.DB_PASSWORD};"


def get_db():
    if "db" not in g:
        import pyodbc  # import perezoso: permite correr las pruebas sin driver

        g.db = pyodbc.connect(_conn_str(), autocommit=True)
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _rows(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def query(sql, params=()):
    """SELECT -> lista de dicts."""
    cur = get_db().cursor()
    try:
        cur.execute(sql, params)
        return _rows(cur)
    finally:
        cur.close()


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def scalar(sql, params=()):
    cur = get_db().cursor()
    try:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()


def execute(sql, params=()):
    cur = get_db().cursor()
    try:
        cur.execute(sql, params)
        return cur.rowcount
    finally:
        cur.close()


def executemany(sql, seq_params):
    cur = get_db().cursor()
    try:
        cur.executemany(sql, seq_params)
        return cur.rowcount
    finally:
        cur.close()


def insert(table, id_col, values):
    """INSERT de una fila; devuelve el id generado (IDENTITY).

    `table` e `id_col` salen siempre del código (nunca del usuario).
    """
    cols = ", ".join(f"[{c}]" for c in values)
    marks = ", ".join("?" for _ in values)
    sql = f"INSERT INTO [{table}] ({cols}) OUTPUT INSERTED.[{id_col}] VALUES ({marks})"
    return scalar(sql, tuple(values.values()))


@contextmanager
def transaction():
    """Agrupa varias escrituras: todo se guarda o todo se revierte."""
    conn = get_db()
    previo = conn.autocommit
    conn.autocommit = False
    try:
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = previo
