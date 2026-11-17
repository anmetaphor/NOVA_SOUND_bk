"""Inicio (Calidad Final): resumen del turno actual a partir de InspeccionCalidad y Pieza."""
from datetime import datetime

import config
import db
from services.comun import turno_actual


def resumen():
    ahora = datetime.now()
    t = turno_actual(ahora)
    ini = datetime.combine(ahora.date(), t["HorarioInicio"])
    fin = datetime.combine(ahora.date(), t["HorarioFin"])

    filas = db.query(
        "WITH u AS (SELECT idPieza, resultado, ROW_NUMBER() OVER (PARTITION BY idPieza ORDER BY fechaInspeccion DESC) AS rn "
        "FROM InspeccionCalidad WHERE fechaInspeccion >= ? AND fechaInspeccion < ?) "
        "SELECT resultado, COUNT(*) AS n FROM u WHERE rn = 1 GROUP BY resultado", (ini, fin),
    )
    cuenta = {f["resultado"]: f["n"] for f in filas}
    aprobadas, fallidas = cuenta.get("Aprobada", 0), cuenta.get("Fallida", 0)
    total = aprobadas + fallidas

    estados = db.query(
        "SELECT e.Estado AS estado, COUNT(*) AS n FROM Pieza p JOIN EstadoPieza e ON e.idEstado = p.idEstado "
        "WHERE e.Estado IN (?, ?) GROUP BY e.Estado", (config.EST_RETENCION, config.EST_RETRABAJO),
    )
    est = {e["estado"]: e["n"] for e in estados}

    abierto = db.query_one(
        "SELECT TOP 1 p.numSerie, m.Nombre AS modelo, d.Color AS color, o.lote, l.NombreLinea AS linea, "
        "o.idOrden, pe.FechaPedido, "
        "(SELECT COUNT(*) FROM HallazgoCalidad h JOIN InspeccionCalidad i ON i.id = h.idInspeccion "
        " WHERE i.idPieza = p.idPieza AND h.estatus = 'Abierto') AS hallazgos "
        "FROM Pieza p JOIN EstadoPieza e ON e.idEstado = p.idEstado "
        "JOIN OrdenProduccion o ON o.idOrden = p.idOrden JOIN Linea l ON l.idLinea = o.idLinea "
        "JOIN DetallePedido d ON d.idDetalle = p.idDetalle JOIN Modelo m ON m.id = d.idModelo "
        "JOIN Pedido pe ON pe.idPedido = d.idPedido "
        "WHERE e.Estado = ? ORDER BY p.FechaCreacion DESC", (config.EST_RETENCION,),
    )
    if abierto:
        from services.comun import codigo_orden

        abierto["orden"] = codigo_orden(abierto["FechaPedido"], abierto["idOrden"])

    pct = lambda n: f"{100 * n / total:.1f}" if total else "0.0"
    return {
        "turno": t, "total": total, "aprobadas": aprobadas, "fallidas": fallidas,
        "pct_aprobadas": pct(aprobadas), "pct_fallidas": pct(fallidas),
        "retencion": est.get(config.EST_RETENCION, 0), "retrabajo": est.get(config.EST_RETRABAJO, 0),
        "abierto": abierto,
    }
