"""Módulo Producción: pedidos, órdenes, detalles y gráficos."""
from collections import defaultdict
from datetime import date, datetime, timedelta

import config
import db
from services import ErrorNegocio
from services.comun import (
    auditar, codigo_orden, pagina_valida, paginar, parse_fecha, turno_actual, turnos, xlsx_bytes,
)

_FROM_ORDEN = """
    FROM OrdenProduccion o
    JOIN DetallePedido d ON d.idDetalle = o.idDetalle
    JOIN Pedido p ON p.idPedido = d.idPedido
    JOIN Cliente c ON c.idCliente = p.ClienteID
    JOIN Modelo m ON m.id = d.idModelo
    JOIN Usuario u ON u.id = o.idUsuarioCreador
"""


def _filtros(f):
    """Arma el WHERE común de órdenes/detalles a partir de los filtros del usuario."""
    where, params = [], []
    if f.get("cliente"):
        where.append("c.NombreCliente LIKE ?")
        params.append(f"%{f['cliente'].strip()}%")
    if f.get("lote"):
        where.append("o.lote LIKE ?")
        params.append(f"%{f['lote'].strip()}%")
    if f.get("estado"):
        where.append("o.Estado = ?")
        params.append(f["estado"])
    desde = parse_fecha(f.get("desde"), "fecha inicial")
    hasta = parse_fecha(f.get("hasta"), "fecha final")
    if desde:
        where.append("p.FechaPedido >= ?")
        params.append(datetime.combine(desde, datetime.min.time()))
    if hasta:
        where.append("p.FechaPedido < ?")
        params.append(datetime.combine(hasta + timedelta(days=1), datetime.min.time()))
    return (" WHERE " + " AND ".join(where)) if where else "", params


# --- Listados -------------------------------------------------------------------------
def listar_ordenes(filtros, page):
    where, params = _filtros(filtros)
    sql = (
        "SELECT o.idOrden, o.lote, c.NombreCliente AS cliente, p.FechaPedido AS fecha_creacion, "
        "o.FechaCompromiso AS fecha_compromiso, o.Estado AS estado " + _FROM_ORDEN + where
    )
    filas, info = paginar(sql, params, pagina_valida(page), "o.idOrden DESC")
    for f in filas:
        f["codigo"] = codigo_orden(f["fecha_creacion"], f["idOrden"])
    return filas, info


def listar_detalles(filtros, page):
    where, params = _filtros(filtros)
    sql = (
        "SELECT o.idOrden, o.lote, c.NombreCliente AS cliente, m.Nombre AS modelo, d.Color AS color, "
        "d.CantidadSolicitada AS cantidad, COALESCE(u.Nombre, u.Usuario) AS responsable "
        + _FROM_ORDEN + where
    )
    return paginar(sql, params, pagina_valida(page), "o.idOrden DESC")


def clientes():
    return [r["NombreCliente"] for r in db.query("SELECT NombreCliente FROM Cliente ORDER BY NombreCliente")]


# --- Crear pedido -----------------------------------------------------------------------
def crear_pedido(datos, usuario):
    """Crea Cliente (si es nuevo) + Pedido + DetallePedido + OrdenProduccion.

    datos = {cliente, fecha_compromiso, linea (NombreLinea), items:[{modelo, color, cantidad}]}
    Cada detalle genera su propia orden de producción; todas comparten el mismo lote
    (un lote = un pedido), que es lo que se busca en "Gráfico por pedido".
    """
    cliente = (datos.get("cliente") or "").strip()
    if not cliente or len(cliente) > 255:
        raise ErrorNegocio("Escribe el nombre del cliente.")
    fecha = parse_fecha(datos.get("fecha_compromiso"), "fecha compromiso")
    if not fecha:
        raise ErrorNegocio("Indica la fecha compromiso.")
    if fecha < date.today():
        raise ErrorNegocio("La fecha compromiso no puede estar en el pasado.")

    items = _normalizar_items(datos.get("items"))
    if not items:
        raise ErrorNegocio("Agrega al menos un producto a la orden.")

    id_linea = db.scalar("SELECT idLinea FROM Linea WHERE NombreLinea = ?", ((datos.get("linea") or "").strip(),))
    if id_linea is None:
        raise ErrorNegocio("Selecciona una línea válida.")
    modelos = {m["Nombre"]: m["id"] for m in db.query("SELECT id, Nombre FROM Modelo")}
    for it in items:
        if it["modelo"] not in modelos:
            raise ErrorNegocio(f"El modelo '{it['modelo']}' no existe.")

    turno = turno_actual()
    ahora = datetime.now()

    with db.transaction():
        id_cliente = db.scalar("SELECT idCliente FROM Cliente WHERE NombreCliente = ?", (cliente,))
        if id_cliente is None:
            id_cliente = db.insert("Cliente", "idCliente", {"NombreCliente": cliente, "TipoCliente": "General"})

        id_pedido = db.insert(
            "Pedido", "idPedido",
            {"ClienteID": id_cliente, "FechaPedido": ahora, "Estado": "En proceso", "FechaCompromiso": fecha},
        )
        prefijo = f"LT-{ahora:%y%m%d}-"
        n = db.scalar(
            "SELECT COUNT(DISTINCT lote) FROM OrdenProduccion WITH (UPDLOCK, HOLDLOCK) WHERE lote LIKE ?",
            (prefijo + "%",),
        )
        lote = f"{prefijo}{n + 1:03d}"

        ordenes = []
        for it in items:
            id_det = db.insert(
                "DetallePedido", "idDetalle",
                {"idPedido": id_pedido, "idModelo": modelos[it["modelo"]], "Color": it["color"],
                 "CantidadSolicitada": it["cantidad"]},
            )
            id_ord = db.insert(
                "OrdenProduccion", "idOrden",
                {"idDetalle": id_det, "idTurno": turno["idTurno"], "CantidadObjetivo": it["cantidad"],
                 "FechaCompromiso": fecha, "Estado": "En proceso", "idUsuarioCreador": usuario["id"],
                 "idLinea": id_linea, "lote": lote},
            )
            ordenes.append(codigo_orden(ahora, id_ord))

        auditar("Pedido", id_pedido, "Alta de pedido", usuario["id"], f"Lote {lote}", "", cliente, "Producción")

    return {"idPedido": id_pedido, "lote": lote, "ordenes": ordenes}


def _normalizar_items(items):
    """Valida y suma los productos repetidos (mismo modelo y color)."""
    if not isinstance(items, list):
        return []
    acum = {}
    for it in items:
        modelo = str((it or {}).get("modelo", "")).strip()
        color = str((it or {}).get("color", "")).strip().title()
        try:
            cant = int((it or {}).get("cantidad"))
        except (TypeError, ValueError):
            raise ErrorNegocio("La cantidad debe ser un número entero.")
        if not modelo or not color or len(color) > 50:
            raise ErrorNegocio("Cada producto necesita modelo y color (máx. 50 caracteres).")
        if not 1 <= cant <= config.MAX_CANTIDAD_DETALLE:
            raise ErrorNegocio(f"La cantidad debe estar entre 1 y {config.MAX_CANTIDAD_DETALLE}.")
        acum[(modelo, color)] = acum.get((modelo, color), 0) + cant
    if any(v > config.MAX_CANTIDAD_DETALLE for v in acum.values()):
        raise ErrorNegocio(f"La cantidad por producto no puede pasar de {config.MAX_CANTIDAD_DETALLE}.")
    return [{"modelo": k[0], "color": k[1], "cantidad": v} for k, v in acum.items()]


# --- Gráfico por pedido ------------------------------------------------------------------
def progreso_pedido(lote):
    lote = (lote or "").strip()
    if not lote:
        raise ErrorNegocio("Escribe el lote a buscar.")

    cab = db.query_one(
        "SELECT TOP 1 p.idPedido, c.NombreCliente AS cliente, p.FechaCompromiso AS fecha_entrega, p.Estado AS estado "
        "FROM OrdenProduccion o JOIN DetallePedido d ON d.idDetalle = o.idDetalle "
        "JOIN Pedido p ON p.idPedido = d.idPedido JOIN Cliente c ON c.idCliente = p.ClienteID "
        "WHERE o.lote = ?", (lote,),
    )
    if not cab:
        raise ErrorNegocio(f"No se encontró el lote '{lote}'.", 404)

    items = db.query(
        "SELECT d.idDetalle, m.Nombre AS modelo, d.Color AS color, d.CantidadSolicitada AS cantidad "
        "FROM DetallePedido d JOIN Modelo m ON m.id = d.idModelo "
        "WHERE d.idDetalle IN (SELECT idDetalle FROM OrdenProduccion WHERE lote = ?) ORDER BY d.idDetalle",
        (lote,),
    )
    piezas = db.query(
        "SELECT pi.idDetalle, e.Estado AS estado, COUNT(*) AS n "
        "FROM Pieza pi JOIN EstadoPieza e ON e.idEstado = pi.idEstado "
        "WHERE pi.idDetalle IN (SELECT idDetalle FROM OrdenProduccion WHERE lote = ?) "
        "GROUP BY pi.idDetalle, e.Estado", (lote,),
    )
    por_detalle = defaultdict(list)
    for p in piezas:
        por_detalle[p["idDetalle"]].append(p)

    total = sum(i["cantidad"] for i in items)
    avanzadas = 0
    progreso = []
    for it in items:
        con_pieza = 0
        for p in por_detalle[it["idDetalle"]]:
            con_pieza += p["n"]
            if p["estado"] in config.EST_EMPACADAS:
                avanzadas += p["n"]
            progreso.append({"modelo": it["modelo"], "color": it["color"], "estado": p["estado"], "cantidad": p["n"]})
        faltan = it["cantidad"] - con_pieza
        if faltan > 0:
            progreso.append({"modelo": it["modelo"], "color": it["color"], "estado": "Pendiente de ensamble", "cantidad": faltan})

    return {
        "lote": lote,
        "cliente": cab["cliente"],
        "estado": cab["estado"],
        "fecha_entrega": cab["fecha_entrega"].strftime("%d/%m/%Y"),
        "items": [{k: i[k] for k in ("modelo", "color", "cantidad")} for i in items],
        "progreso": progreso,
        "total": total,
        "avanzadas": avanzadas,
        "porcentaje": round(100 * avanzadas / total) if total else 0,
    }


def documento_pedido(lote):
    d = progreso_pedido(lote)
    filas = [(d["lote"], d["cliente"], d["fecha_entrega"], p["modelo"], p["color"], p["estado"], p["cantidad"])
             for p in d["progreso"]]
    return xlsx_bytes(f"Pedido {lote}", ["Lote", "Cliente", "Fecha entrega", "Modelo", "Color", "Estado", "Cantidad"], filas)


# --- Gráfico global ------------------------------------------------------------------------
def _rango(filtros):
    desde = parse_fecha(filtros.get("desde"), "fecha inicial")
    hasta = parse_fecha(filtros.get("hasta"), "fecha final")
    return desde, hasta


def _where_pedido(desde, hasta, alias="p", col="FechaPedido"):
    w, prm = [], []
    if desde:
        w.append(f"{alias}.{col} >= ?")
        prm.append(datetime.combine(desde, datetime.min.time()))
    if hasta:
        w.append(f"{alias}.{col} < ?")
        prm.append(datetime.combine(hasta + timedelta(days=1), datetime.min.time()))
    return w, prm


def grafico_global(tipo, filtros):
    """Devuelve {titulo, descripcion, labels, series:[{nombre, valores}], resumen:[str]}."""
    desde, hasta = _rango(filtros)
    fn = {"colores": _g_colores, "estados": _g_estados, "turnos": _g_turnos, "estimaciones": _g_estimaciones}.get(tipo)
    if not fn:
        raise ErrorNegocio("Tipo de gráfico no válido.")
    return fn(desde, hasta)


def _g_colores(desde, hasta):
    w, prm = _where_pedido(desde, hasta)
    w.append("p.Estado <> 'Cancelado'")
    filas = db.query(
        "SELECT m.Nombre AS modelo, d.Color AS color, SUM(d.CantidadSolicitada) AS total "
        "FROM DetallePedido d JOIN Pedido p ON p.idPedido = d.idPedido JOIN Modelo m ON m.id = d.idModelo "
        f"WHERE {' AND '.join(w)} GROUP BY m.Nombre, d.Color", tuple(prm),
    )
    modelos = [m["Nombre"] for m in db.query("SELECT Nombre FROM Modelo ORDER BY id")]
    por_modelo = defaultdict(list)
    for f in filas:
        por_modelo[f["modelo"]].append((f["color"], int(f["total"])))
    top = {m: sorted(v, key=lambda x: -x[1])[:3] for m, v in por_modelo.items()}  # 3 más vendidos por modelo
    colores = []
    for m in modelos:
        for c, _ in top.get(m, []):
            if c not in colores:
                colores.append(c)
    series = [{"nombre": c, "valores": [dict(top.get(m, [])).get(c, 0) for m in modelos]} for c in colores]
    resumen = [f"{m}: " + ", ".join(f"{n} {c}" for c, n in top[m]) for m in modelos if top.get(m)]
    return {"titulo": "Modelos más vendidos por color",
            "descripcion": "El gráfico muestra cada modelo con sus 3 colores más vendidos",
            "labels": modelos, "series": series, "resumen": resumen}


def _g_estados(desde, hasta):
    w, prm = _where_pedido(desde, hasta)
    filas = db.query(
        "SELECT Estado AS estado, COUNT(*) AS n FROM Pedido p"
        + (f" WHERE {' AND '.join(w)}" if w else "") + " GROUP BY Estado", tuple(prm),
    )
    cuenta = {f["estado"]: f["n"] for f in filas}
    labels = ["En proceso", "Finalizado", "Cancelado"]
    return {"titulo": "Estados de pedido", "descripcion": "Cantidad de pedidos según su estado",
            "labels": labels, "series": [{"nombre": "Pedidos", "valores": [cuenta.get(e, 0) for e in labels]}],
            "resumen": [f"{e}: {cuenta.get(e, 0)} pedidos" for e in labels]}


def _g_turnos(desde, hasta):
    w, prm = _where_pedido(desde, hasta, alias="pt", col="fecha")
    filas = db.query(
        "SELECT pt.idTurno, SUM(pt.produccionObjetivo) AS obj, SUM(pt.produccionReal) AS real "
        "FROM ProduccionTurno pt" + (f" WHERE {' AND '.join(w)}" if w else "") + " GROUP BY pt.idTurno",
        tuple(prm),
    )
    datos = {f["idTurno"]: f for f in filas}
    ts = turnos()
    return {"titulo": "Cantidades por turno", "descripcion": "Producción objetivo contra producción real por turno",
            "labels": [t["corto"] for t in ts],
            "series": [{"nombre": "Objetivo", "valores": [int(datos.get(t["idTurno"], {}).get("obj") or 0) for t in ts]},
                       {"nombre": "Real", "valores": [int(datos.get(t["idTurno"], {}).get("real") or 0) for t in ts]}],
            "resumen": [f"{t['etiqueta']}: {int(datos.get(t['idTurno'], {}).get('real') or 0)} de "
                        f"{int(datos.get(t['idTurno'], {}).get('obj') or 0)} u." for t in ts]}


def _g_estimaciones(_desde, _hasta):
    """Pendiente por modelo en órdenes en proceso y días estimados al ritmo de los últimos 14 días."""
    pend = db.query(
        "SELECT m.Nombre AS modelo, SUM(o.CantidadObjetivo) - COALESCE(SUM(pr.prod), 0) AS pendiente "
        "FROM OrdenProduccion o JOIN DetallePedido d ON d.idDetalle = o.idDetalle JOIN Modelo m ON m.id = d.idModelo "
        "LEFT JOIN (SELECT idOrden, SUM(CantidadProducida) AS prod FROM Produccion GROUP BY idOrden) pr "
        "ON pr.idOrden = o.idOrden WHERE o.Estado = 'En proceso' GROUP BY m.Nombre"
    )
    ritmo = db.query(
        "SELECT m.Nombre AS modelo, SUM(pt.produccionReal) AS total "
        "FROM ProduccionTurno pt JOIN OrdenProduccion o ON o.idOrden = pt.idOrden "
        "JOIN DetallePedido d ON d.idDetalle = o.idDetalle JOIN Modelo m ON m.id = d.idModelo "
        "WHERE pt.fecha >= ? GROUP BY m.Nombre", (date.today() - timedelta(days=14),),
    )
    pend = {f["modelo"]: int(f["pendiente"] or 0) for f in pend}
    dia = {f["modelo"]: int(f["total"] or 0) / 14 for f in ritmo}
    modelos = [m["Nombre"] for m in db.query("SELECT Nombre FROM Modelo ORDER BY id")]
    resumen = []
    for m in modelos:
        p, r = pend.get(m, 0), dia.get(m, 0)
        if p == 0:
            resumen.append(f"{m}: sin pendientes")
        elif r == 0:
            resumen.append(f"{m}: {p} pendientes (sin producción reciente para estimar)")
        else:
            resumen.append(f"{m}: {p} pendientes, ~{-(-p // max(1, round(r)))} días al ritmo de {r:.0f} u./día")
    return {"titulo": "Estimaciones", "descripcion": "Unidades pendientes por modelo y tiempo estimado para terminarlas",
            "labels": modelos, "series": [{"nombre": "Pendientes", "valores": [pend.get(m, 0) for m in modelos]}],
            "resumen": resumen}


def documento_global(tipo, filtros):
    g = grafico_global(tipo, filtros)
    filas = [[lab] + [s["valores"][i] for s in g["series"]] for i, lab in enumerate(g["labels"])]
    return xlsx_bytes(g["titulo"], [""] + [s["nombre"] for s in g["series"]], filas)
