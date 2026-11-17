"""Módulo Ensamble: registro de producción (genera piezas con número de serie) e histórico."""
from datetime import date, datetime, timedelta

import config
import db
from services import ErrorNegocio
from services.comun import (
    auditar, codigo_orden, id_estado_pieza, pagina_valida, paginar, parse_codigo_orden, parse_fecha, xlsx_bytes,
)

_SQL_ORDEN = """
    SELECT o.idOrden, o.idDetalle, o.lote, o.CantidadObjetivo AS objetivo, o.Estado AS estado,
           o.idLinea, p.FechaPedido, c.NombreCliente AS cliente, m.Nombre AS modelo, d.Color AS color,
           COALESCE((SELECT SUM(CantidadProducida) FROM Produccion WHERE idOrden = o.idOrden), 0) AS producido
    FROM OrdenProduccion o
    JOIN DetallePedido d ON d.idDetalle = o.idDetalle
    JOIN Pedido p ON p.idPedido = d.idPedido
    JOIN Cliente c ON c.idCliente = p.ClienteID
    JOIN Modelo m ON m.id = d.idModelo
"""


def buscar_orden(codigo):
    """Busca por código OP-AAMMDD-NN (o solo el número) o por lote. Devuelve dict o None."""
    codigo = (codigo or "").strip()
    id_orden = parse_codigo_orden(codigo)
    if id_orden is not None:
        o = db.query_one(_SQL_ORDEN + " WHERE o.idOrden = ?", (id_orden,))
    else:
        ordenes = db.query(_SQL_ORDEN + " WHERE o.lote = ? AND o.Estado = 'En proceso' ORDER BY o.idOrden", (codigo,))
        if len(ordenes) > 1:
            raise ErrorNegocio(
                "Ese lote tiene varias órdenes. Usa el código de la orden: "
                + ", ".join(codigo_orden(x["FechaPedido"], x["idOrden"]) for x in ordenes) + "."
            )
        o = ordenes[0] if ordenes else None
    if o:
        o["codigo"] = codigo_orden(o["FechaPedido"], o["idOrden"])
        o["pendiente"] = max(0, o["objetivo"] - int(o["producido"]))
        o["producido"] = int(o["producido"])
        o["FechaPedido"] = o["FechaPedido"].strftime("%d/%m/%Y")
    return o


def _serie_prefijo(modelo, hoy):
    pref = config.PREFIJO_SERIE.get(modelo) or "NS" + "".join(ch for ch in modelo.upper() if ch.isalpha())[2:3]
    return f"{pref}-{hoy:%y%m%d}-"


def registrar(datos, usuario):
    """Registra producción: Produccion + N piezas (Pieza + Ensamble) + ProduccionTurno."""
    try:
        cantidad = int(datos.get("cantidad"))
    except (TypeError, ValueError):
        raise ErrorNegocio("La cantidad debe ser un número entero.")
    if cantidad <= 0:
        raise ErrorNegocio("La cantidad ensamblada debe ser mayor a 0.")
    if cantidad > config.MAX_PIEZAS_POR_REGISTRO:
        raise ErrorNegocio(f"Máximo {config.MAX_PIEZAS_POR_REGISTRO} piezas por registro.")

    id_turno = _a_int(datos.get("idTurno"), "turno")
    id_linea = _a_int(datos.get("idLinea"), "línea")
    if not db.scalar("SELECT COUNT(*) FROM Turno WHERE idTurno = ?", (id_turno,)):
        raise ErrorNegocio("Selecciona un turno válido.")
    if not db.scalar("SELECT COUNT(*) FROM Linea WHERE idLinea = ?", (id_linea,)):
        raise ErrorNegocio("Selecciona una línea válida.")

    orden = buscar_orden(datos.get("orden"))
    if not orden:
        raise ErrorNegocio("La orden activa no existe.", 404)
    id_estado = id_estado_pieza(config.EST_ENSAMBLADA)
    ahora = datetime.now()
    hoy = ahora.date()

    with db.transaction():
        # Se relee la orden dentro de la transacción (con bloqueo) para evitar sobreproducir en paralelo.
        fila = db.query_one(
            "SELECT o.Estado AS estado, o.CantidadObjetivo AS objetivo, "
            "COALESCE((SELECT SUM(CantidadProducida) FROM Produccion WHERE idOrden = o.idOrden), 0) AS producido "
            "FROM OrdenProduccion o WITH (UPDLOCK, HOLDLOCK) WHERE o.idOrden = ?", (orden["idOrden"],),
        )
        if fila["estado"] != "En proceso":
            raise ErrorNegocio(f"La orden está '{fila['estado']}'; solo se registra sobre órdenes en proceso.", 409)
        pendiente = fila["objetivo"] - int(fila["producido"])
        if cantidad > pendiente:
            raise ErrorNegocio(f"La orden solo tiene {pendiente} unidades pendientes; no puedes registrar {cantidad}.", 409)

        id_prod = db.insert(
            "Produccion", "idProduccion",
            {"idOrden": orden["idOrden"], "CantidadProducida": cantidad, "idUsuarioOperador": usuario["id"],
             "idTurno": id_turno, "idLinea": id_linea, "idValidador": usuario["id"]},
        )

        # Números de serie consecutivos del día para ese modelo.
        pref = _serie_prefijo(orden["modelo"], hoy)
        ultimo = db.scalar(
            "SELECT MAX(CAST(RIGHT(numSerie, 5) AS INT)) FROM Pieza WITH (UPDLOCK, HOLDLOCK) WHERE numSerie LIKE ?",
            (pref + "%",),
        ) or 0
        series = [f"{pref}{ultimo + i:05d}" for i in range(1, cantidad + 1)]
        db.executemany(
            "INSERT INTO Pieza (idOrden, idDetalle, idEstado, FechaCreacion, numSerie, idCajaAlmacen) VALUES (?,?,?,?,?,NULL)",
            [(orden["idOrden"], orden["idDetalle"], id_estado, ahora, s) for s in series],
        )
        ids = []
        for i in range(0, len(series), 500):
            lote_series = series[i:i + 500]
            marcas = ",".join("?" for _ in lote_series)
            ids += [r["idPieza"] for r in db.query(f"SELECT idPieza FROM Pieza WHERE numSerie IN ({marcas})", tuple(lote_series))]
        db.executemany(
            "INSERT INTO Ensamble (idProduccion, idPieza, FechaEnsamble, Ensamblado) VALUES (?,?,?,1)",
            [(id_prod, i, ahora) for i in ids],
        )

        # Resumen por turno/línea/orden/día (alimenta gráficos y reporte de fin de turno).
        pt = db.query_one(
            "SELECT id FROM ProduccionTurno WITH (UPDLOCK) WHERE idTurno = ? AND idLinea = ? AND idOrden = ? AND fecha = ?",
            (id_turno, id_linea, orden["idOrden"], hoy),
        )
        if pt:
            db.execute("UPDATE ProduccionTurno SET produccionReal = produccionReal + ? WHERE id = ?", (cantidad, pt["id"]))
        else:
            db.insert("ProduccionTurno", "id",
                      {"idTurno": id_turno, "idLinea": id_linea, "idOrden": orden["idOrden"],
                       "produccionObjetivo": fila["objetivo"], "produccionReal": cantidad, "fecha": hoy})

        if cantidad == pendiente:
            db.execute("UPDATE OrdenProduccion SET Estado = 'Finalizado' WHERE idOrden = ?", (orden["idOrden"],))

        obs = (datos.get("observaciones") or "").strip()
        motivo = f"{orden['codigo']} · {cantidad} u." + (f" · {obs}" if obs else "")  # Produccion no tiene columna de notas
        auditar("Produccion", id_prod, "Registro de ensamble", usuario["id"],
                motivo, "", f"{series[0]}..{series[-1]}", "Ensamble")

    return {"idProduccion": id_prod, "codigoRegistro": f"ENS-{id_prod}", "piezas": cantidad,
            "primeraSerie": series[0], "ultimaSerie": series[-1], "ordenFinalizada": cantidad == pendiente}


def _a_int(v, nombre):
    try:
        return int(v)
    except (TypeError, ValueError):
        raise ErrorNegocio(f"Selecciona un {nombre} válido.")


# --- Histórico -----------------------------------------------------------------------------
# Produccion no tiene fecha propia: se toma la de sus piezas en Ensamble.
_SQL_HIST = """
    SELECT pr.idProduccion, pr.CantidadProducida AS cantidad, pr.idTurno, t.HorarioInicio,
           l.NombreLinea AS linea, o.idOrden, p.FechaPedido, COALESCE(u.Nombre, u.Usuario) AS operador,
           (SELECT MIN(e.FechaEnsamble) FROM Ensamble e WHERE e.idProduccion = pr.idProduccion) AS fecha
    FROM Produccion pr
    JOIN OrdenProduccion o ON o.idOrden = pr.idOrden
    JOIN DetallePedido d ON d.idDetalle = o.idDetalle
    JOIN Pedido p ON p.idPedido = d.idPedido
    JOIN Turno t ON t.idTurno = pr.idTurno
    JOIN Linea l ON l.idLinea = pr.idLinea
    JOIN Usuario u ON u.id = pr.idUsuarioOperador
"""


def _hist_sql(filtros):
    outer, params = [], []
    if filtros.get("turno"):
        outer.append("h.idTurno = ?")
        params.append(_a_int(filtros["turno"], "turno"))
    desde, hasta = parse_fecha(filtros.get("desde"), "fecha inicial"), parse_fecha(filtros.get("hasta"), "fecha final")
    if desde:
        outer.append("h.fecha >= ?")
        params.append(datetime.combine(desde, datetime.min.time()))
    if hasta:
        outer.append("h.fecha < ?")
        params.append(datetime.combine(hasta + timedelta(days=1), datetime.min.time()))
    sql = f"SELECT * FROM ({_SQL_HIST}) h" + (" WHERE " + " AND ".join(outer) if outer else "")
    return sql, params


def _decorar(filas, nombres_turno):
    for f in filas:
        f["registro"] = f"ENS-{f['idProduccion']}"
        f["turno"] = nombres_turno.get(f["idTurno"], "")
        f["orden"] = codigo_orden(f["FechaPedido"], f["idOrden"])
    return filas


def historico(filtros, page):
    from services.comun import turnos

    nombres = {t["idTurno"]: t["corto"] for t in turnos()}
    sql, params = _hist_sql(filtros)
    filas, info = paginar(sql, params, pagina_valida(page), "h.fecha DESC, h.idProduccion DESC", por_pagina=10)
    return _decorar(filas, nombres), info


def documento_historico(filtros):
    from services.comun import turnos

    nombres = {t["idTurno"]: t["corto"] for t in turnos()}
    sql, params = _hist_sql(filtros)
    filas = _decorar(db.query(sql + " ORDER BY h.fecha DESC, h.idProduccion DESC", tuple(params)), nombres)
    return xlsx_bytes(
        "Histórico ensamble",
        ["ID Registro", "Turno", "Línea", "Orden", "Cantidad ensamblada", "Operador", "Fecha y hora"],
        [(f["registro"], f["turno"], f["linea"], f["orden"], f["cantidad"], f["operador"], f["fecha"]) for f in filas],
    )


def ultimos_registros(limite=5):
    """Últimos registros del día (los muestra la pantalla de registro)."""
    filas = db.query(
        f"SELECT TOP {int(limite)} * FROM ({_SQL_HIST}) h WHERE h.fecha >= ? ORDER BY h.fecha DESC, h.idProduccion DESC",
        (datetime.combine(date.today(), datetime.min.time()),),
    )
    for f in filas:
        f["orden"] = codigo_orden(f["FechaPedido"], f["idOrden"])
    return filas
