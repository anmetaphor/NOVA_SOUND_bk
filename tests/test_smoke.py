"""Pruebas de humo SIN base de datos real.

Se sustituye la capa `db` por una BD simulada que devuelve filas de ejemplo y
registra todo el SQL ejecutado. Sirve para comprobar rutas, permisos, validaciones,
plantillas y -con sqlglot- que el T-SQL tenga sintaxis válida.
NO prueba el resultado de las consultas contra SQL Server real.
"""
import os
import sys
from datetime import date, datetime, time

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db  # noqa: E402
from app import app  # noqa: E402

SQL_LOG = []
USUARIO = {"id": 1, "email": "a@b.com", "nombre": "Ana", "rol": "Gerente",
           "Contrasena": generate_password_hash("password123")}
HOY = datetime.now()
ORDEN = {"idOrden": 7, "idDetalle": 3, "lote": "LT-261016-001", "objetivo": 100, "estado": "En proceso", "idLinea": 1,
         "FechaPedido": HOY, "cliente": "Walmart", "modelo": "NS-PRO", "color": "Azul", "producido": 20}


def responder(sql, params=()):
    s = " ".join(sql.split())
    SQL_LOG.append(s)
    if s.startswith("SELECT COUNT(*) FROM (") :
        return [{"c": 12}]
    if "FROM Usuario u" in s:
        return [dict(USUARIO)]
    if "FROM Linea" in s and "idLinea" in s and "SELECT idLinea," in s:
        return [{"idLinea": 1, "NombreLinea": "L-01"}, {"idLinea": 2, "NombreLinea": "L-02"}]
    if "FROM Turno ORDER" in s:
        return [{"idTurno": 1, "HorarioInicio": time(5), "HorarioFin": time(14)},
                {"idTurno": 2, "HorarioInicio": time(14), "HorarioFin": time(21, 30)}]
    if "FROM Modelo ORDER BY id" in s or "FROM Modelo" in s and "SELECT id, Nombre" in s:
        return [{"id": i, "Nombre": n, } for i, n in enumerate(["NS-MINI", "NS-SPORT", "NS-PRO", "NS-MAX"], 1)]
    if "SELECT Nombre FROM Modelo" in s:
        return [{"Nombre": n} for n in ["NS-MINI", "NS-SPORT", "NS-PRO", "NS-MAX"]]
    if "SELECT NombreCliente FROM Cliente" in s:
        return [{"NombreCliente": "Walmart"}]
    if "OFFSET" in s and "FROM OrdenProduccion o" in s:
        return [{"idOrden": 7, "lote": "LT-1", "cliente": "Walmart", "fecha_creacion": HOY, "fecha_compromiso": date.today(),
                 "estado": "En proceso", "modelo": "NS-PRO", "color": "Azul", "cantidad": 5, "responsable": "Ana"}]
    if "FROM Produccion pr" in s:
        return [{"idProduccion": 1, "cantidad": 10, "idTurno": 1, "HorarioInicio": time(5), "linea": "L-01", "idOrden": 7,
                 "FechaPedido": HOY, "operador": "Ana", "fecha": HOY}]
    if "SELECT TOP 1 p.idPedido" in s:
        return [{"idPedido": 1, "cliente": "Walmart", "fecha_entrega": date.today(), "estado": "En proceso"}]
    if "FROM DetallePedido d JOIN Modelo" in s and "idDetalle IN" in s:
        return [{"idDetalle": 3, "modelo": "NS-PRO", "color": "Azul", "cantidad": 5}]
    if "FROM Pieza pi JOIN EstadoPieza" in s:
        return [{"idDetalle": 3, "estado": "Empacada", "n": 4}]
    if "GROUP BY m.Nombre, d.Color" in s:
        return [{"modelo": "NS-PRO", "color": "Azul", "total": 230}, {"modelo": "NS-PRO", "color": "Negro", "total": 200}]
    if "FROM Pedido p" in s and "GROUP BY Estado" in s:
        return [{"estado": "En proceso", "n": 3}]
    if "FROM ProduccionTurno pt" in s:
        return [{"idTurno": 1, "obj": 100, "real": 80, "modelo": "NS-PRO", "total": 140}]
    if "SUM(o.CantidadObjetivo)" in s:
        return [{"modelo": "NS-PRO", "pendiente": 80}]
    if "ROW_NUMBER" in s:
        return [{"resultado": "Aprobada", "n": 9}, {"resultado": "Fallida", "n": 1}]
    if "FROM Pieza p JOIN EstadoPieza" in s and "GROUP BY e.Estado" in s:
        return [{"estado": "En retención", "n": 2}]
    if "SELECT TOP 1 p.numSerie" in s:
        return [{"numSerie": "NSP-261016-00001", "modelo": "NS-PRO", "color": "Azul", "lote": "LT-1", "linea": "L-01",
                 "idOrden": 7, "FechaPedido": HOY, "hallazgos": 1}]
    if "FROM OrdenProduccion o" in s and "WHERE o.idOrden" in s:
        return [dict(ORDEN)] if "o.Estado AS estado, o.CantidadObjetivo" not in s else [{"estado": "En proceso", "objetivo": 100, "producido": 20}]
    if "SELECT idPieza FROM Pieza WHERE numSerie IN" in s:
        return [{"idPieza": i} for i in range(1, 6)]
    if "FROM ProduccionTurno WITH" in s:
        return []
    return []


def responder_scalar(sql, params=()):
    s = " ".join(sql.split())
    SQL_LOG.append(s)
    if s.startswith("SELECT COUNT(*) FROM ("):
        return 12
    if "FROM Usuario WHERE" in s:
        return 0
    if "FROM Usuario WITH" in s:
        return 1
    if "SELECT idLinea FROM Linea" in s:
        return 1
    if "SELECT idEstado" in s:
        return 1
    if "COUNT(DISTINCT lote)" in s:
        return 2
    if "MAX(CAST(RIGHT" in s:
        return 41
    if "COUNT(*) FROM UsuarioRol" in s:
        return 2
    if "SELECT idCliente" in s:
        return None
    if "SELECT id FROM Rol" in s:
        return 2
    if "COUNT(*) FROM Turno" in s or "COUNT(*) FROM Linea" in s:
        return 1
    return 1


@pytest.fixture(autouse=True)
def bd_simulada(monkeypatch):
    SQL_LOG.clear()
    monkeypatch.setattr(db, "query", responder)
    monkeypatch.setattr(db, "query_one", lambda s, p=(): (responder(s, p) or [None])[0])
    monkeypatch.setattr(db, "scalar", responder_scalar)
    monkeypatch.setattr(db, "execute", lambda s, p=(): SQL_LOG.append(" ".join(s.split())) or 1)
    monkeypatch.setattr(db, "executemany", lambda s, p: SQL_LOG.append(" ".join(s.split())) or 1)
    contador = iter(range(100, 1000))
    monkeypatch.setattr(db, "insert", lambda t, c, v: SQL_LOG.append(f"INSERT INTO [{t}] ({','.join(v)}) OUTPUT INSERTED.[{c}] VALUES ({','.join('?' for _ in v)})") or next(contador))
    from contextlib import nullcontext
    monkeypatch.setattr(db, "transaction", nullcontext)


@pytest.fixture
def cli():
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def sesion(cli):
    r = cli.post("/login", data={"email": "a@b.com", "password": "password123"})
    assert r.status_code == 302
    return cli


def test_rutas_exigen_sesion(cli):
    for ruta in ["/dashboard", "/produccion/ordenes", "/ensamble/registro", "/configuracion"]:
        assert cli.get(ruta).status_code == 302
    assert cli.get("/api/produccion/grafico-global").status_code == 401


def test_login_incorrecto(cli):
    r = cli.post("/login", data={"email": "a@b.com", "password": "mala"})
    assert r.status_code == 401 and "incorrectos" in r.get_data(as_text=True)


def test_paginas_renderizan(sesion):
    for ruta in ["/dashboard", "/produccion/ordenes", "/produccion/ordenes?page=2&cliente=wal&desde=2026-01-01",
                 "/produccion/detalles", "/produccion/grafico-global", "/produccion/grafico-pedido",
                 "/produccion/crear-orden", "/ensamble/registro", "/ensamble/historico", "/configuracion"]:
        r = sesion.get(ruta)
        assert r.status_code == 200, ruta
    html = sesion.get("/produccion/ordenes").get_data(as_text=True)
    assert "OP-" in html and "Walmart" in html and "Gerente: Ana" in html


def test_fecha_invalida_en_filtro(sesion):
    assert sesion.get("/produccion/ordenes?desde=hola").status_code == 400


@pytest.mark.parametrize("tipo", ["colores", "estados", "turnos", "estimaciones"])
def test_graficos(sesion, tipo):
    r = sesion.get(f"/api/produccion/grafico-global?tipo={tipo}")
    assert r.status_code == 200 and r.json["labels"] and r.json["series"]
    assert sesion.get(f"/produccion/documento/global?tipo={tipo}").status_code == 200


def test_grafico_pedido(sesion):
    r = sesion.get("/api/produccion/grafico-pedido?lote=LT-261016-001")
    assert r.status_code == 200 and r.json["porcentaje"] == 80
    assert sesion.get("/api/produccion/grafico-pedido?lote=").status_code == 400


def test_crear_pedido(sesion):
    manana = date.today().isoformat()
    ok = {"cliente": "Walmart", "fecha_compromiso": manana, "linea": "L-01",
          "items": [{"modelo": "NS-MINI", "color": "azul", "cantidad": 2}, {"modelo": "NS-MINI", "color": "Azul", "cantidad": 3}]}
    r = sesion.post("/api/produccion/pedidos", json=ok)
    assert r.status_code == 201, r.json
    assert r.json["lote"].startswith("LT-") and len(r.json["ordenes"]) == 1       # mismo modelo+color se suma
    for malo, texto in [({**ok, "items": []}, "al menos un producto"),
                        ({**ok, "cliente": " "}, "cliente"),
                        ({**ok, "fecha_compromiso": "2020-01-01"}, "pasado"),
                        ({**ok, "items": [{"modelo": "NS-MINI", "color": "Azul", "cantidad": 0}]}, "entre 1"),
                        ({**ok, "items": [{"modelo": "NS-XXX", "color": "Azul", "cantidad": 1}]}, "no existe")]:
        r = sesion.post("/api/produccion/pedidos", json=malo)
        assert r.status_code == 400 and texto in r.json["error"], (malo, r.json)
    assert sesion.post("/api/produccion/pedidos", data="x").status_code == 400


def test_registrar_ensamble(sesion):
    base = {"idTurno": 1, "idLinea": 1, "orden": "OP-261016-07", "cantidad": 5}
    r = sesion.post("/api/ensamble/registros", json=base)
    assert r.status_code == 201, r.json
    assert r.json["primeraSerie"].endswith("00042") and r.json["piezas"] == 5
    assert sesion.post("/api/ensamble/registros", json={**base, "cantidad": 0}).status_code == 400
    r = sesion.post("/api/ensamble/registros", json={**base, "cantidad": 81})
    assert r.status_code == 409 and "80 unidades pendientes" in r.json["error"]


def test_buscar_orden_api(sesion):
    r = sesion.get("/api/ensamble/orden?codigo=OP-261016-07")
    assert r.status_code == 200 and r.json["pendiente"] == 80


def test_roles(cli, monkeypatch):
    op = {**USUARIO, "rol": "Operador"}
    monkeypatch.setitem(globals(), "USUARIO", op)
    cli.post("/login", data={"email": "a@b.com", "password": "password123"})
    assert cli.get("/ensamble/registro").status_code == 200
    assert cli.get("/produccion/ordenes").status_code == 403
    assert cli.get("/configuracion").status_code == 403
    assert cli.post("/api/produccion/pedidos", json={}).status_code == 403


def test_cambiar_rol(sesion):
    assert sesion.post("/api/configuracion/rol", json={"idUsuario": 1, "nivel": 9}).status_code == 400
    assert sesion.post("/api/configuracion/rol", json={"idUsuario": 1, "nivel": 3}).status_code == 200


def test_registro_valida(cli):
    r = cli.post("/register", data={"nombre": "X", "email": "malo", "password": "12345678"})
    assert r.status_code == 400 and "correo" in r.get_data(as_text=True)
    r = cli.post("/register", data={"nombre": "X", "email": "x@y.com", "password": "corta"})
    assert "8 caracteres" in r.get_data(as_text=True)


def test_sintaxis_tsql():
    """Todo el SQL generado en las pruebas anteriores debe parsear como T-SQL."""
    import sqlglot

    app.config["TESTING"] = True
    c = app.test_client()
    c.post("/login", data={"email": "a@b.com", "password": "password123"})
    for ruta in ["/dashboard", "/produccion/ordenes?cliente=a&estado=En proceso&desde=2026-01-01&hasta=2026-12-31",
                 "/produccion/detalles", "/ensamble/historico?turno=1&desde=2026-01-01", "/ensamble/registro",
                 "/api/produccion/grafico-global?tipo=colores", "/api/produccion/grafico-global?tipo=estados&desde=2026-01-01",
                 "/api/produccion/grafico-global?tipo=turnos&desde=2026-01-01&hasta=2026-02-01",
                 "/api/produccion/grafico-global?tipo=estimaciones", "/api/produccion/grafico-pedido?lote=x",
                 "/api/ensamble/orden?codigo=OP-261016-07"]:
        c.get(ruta)
    c.post("/api/ensamble/registros", json={"idTurno": 1, "idLinea": 1, "orden": "7", "cantidad": 5})
    c.post("/api/produccion/pedidos", json={"cliente": "Z", "fecha_compromiso": date.today().isoformat(), "linea": "L-01",
                                            "items": [{"modelo": "NS-PRO", "color": "Rojo", "cantidad": 1}]})
    errores = []
    for sql in set(SQL_LOG):
        try:
            sqlglot.parse_one(sql.replace("OFFSET ? ROWS FETCH NEXT ? ROWS ONLY", "OFFSET 0 ROWS FETCH NEXT 5 ROWS ONLY"), read="tsql")
        except Exception as e:  # noqa: BLE001
            errores.append((sql[:150], str(e)[:120]))
    assert not errores, errores
    assert len(set(SQL_LOG)) > 25
