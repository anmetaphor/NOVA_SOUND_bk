"""Utilidades compartidas por los servicios."""
import io
import re
from datetime import date, datetime, time

import config
import db
from services import ErrorNegocio


# --- Fechas / paginación -------------------------------------------------------
def parse_fecha(texto, campo="fecha"):
    """'2026-10-16' -> date. Vacío -> None."""
    if not texto:
        return None
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        raise ErrorNegocio(f"La {campo} no tiene un formato válido (AAAA-MM-DD).")


def pagina_valida(valor):
    try:
        return max(1, int(valor))
    except (TypeError, ValueError):
        return 1


def paginar(sql_base, params, page, order_by, por_pagina=None):
    """Ejecuta `sql_base` (un SELECT sin ORDER BY) paginado con OFFSET/FETCH.

    Devuelve (filas, info) donde info = {page, pages, total}.
    """
    por_pagina = por_pagina or config.POR_PAGINA
    total = db.scalar(f"SELECT COUNT(*) FROM ({sql_base}) AS t", params) or 0
    pages = max(1, -(-total // por_pagina))
    page = min(max(1, page), pages)
    filas = db.query(
        f"{sql_base} ORDER BY {order_by} OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
        tuple(params) + ((page - 1) * por_pagina, por_pagina),
    )
    return filas, {"page": page, "pages": pages, "total": total}


def ventana_paginas(page, pages, ancho=5):
    """Números de página a mostrar en el paginador (máx. `ancho`)."""
    ini = max(1, min(page - ancho // 2, pages - ancho + 1))
    return list(range(ini, min(pages, ini + ancho - 1) + 1))


# --- Catálogos / turno ---------------------------------------------------------
def turnos():
    filas = db.query("SELECT idTurno, HorarioInicio, HorarioFin FROM Turno ORDER BY HorarioInicio")
    for i, t in enumerate(filas, start=1):
        t["etiqueta"] = f"T{i} ({_hhmm(t['HorarioInicio'])}–{_hhmm(t['HorarioFin'])})"
        t["corto"] = f"T{i}"
    return filas


def _hhmm(t):
    return t.strftime("%H:%M") if isinstance(t, time) else str(t)[:5]


def lineas():
    return db.query("SELECT idLinea, NombreLinea FROM Linea ORDER BY NombreLinea")


def modelos():
    return db.query("SELECT id, Nombre FROM Modelo ORDER BY id")


def turno_actual(ahora=None):
    """Turno que corresponde a la hora actual (si ninguno aplica, el primero)."""
    ahora = (ahora or datetime.now()).time()
    ts = turnos()
    if not ts:
        raise ErrorNegocio("No hay turnos configurados. Ejecuta sql/02_seed.sql.", 500)
    for t in ts:
        if t["HorarioInicio"] <= ahora < t["HorarioFin"]:
            return t
    return ts[0]


def id_estado_pieza(nombre):
    idx = db.scalar("SELECT idEstado FROM EstadoPieza WHERE Estado = ?", (nombre,))
    if idx is None:
        raise ErrorNegocio(
            f"Falta el estado de pieza '{nombre}'. Ejecuta sql/02_seed.sql.", 500
        )
    return idx


# --- Códigos legibles ------------------------------------------------------------
def codigo_orden(fecha, id_orden):
    """OP-261016-03 (fecha de creación del pedido + id de la orden)."""
    return f"OP-{fecha:%y%m%d}-{id_orden:02d}"


_RE_OP = re.compile(r"^OP-\d{6}-(\d+)$", re.IGNORECASE)


def parse_codigo_orden(texto):
    """'OP-261016-03' -> 3. Un número solo también se acepta. Otro texto -> None."""
    texto = (texto or "").strip()
    m = _RE_OP.match(texto)
    if m:
        return int(m.group(1))
    return int(texto) if texto.isdigit() else None


# --- Auditoría -------------------------------------------------------------------
def auditar(tabla, registro_id, accion, id_usuario, motivo, anterior="", nuevo="", categoria=None):
    db.insert(
        "Auditoria",
        "idAuditoria",
        {
            "TablaAfectada": tabla[:255],
            "registroId": registro_id,
            "Accion": accion[:255],
            "idUsuario": id_usuario,
            "FechaAccion": datetime.now(),
            "Motivo": motivo[:255],
            "ValorAnterior": str(anterior)[:255],
            "ValorNuevo": str(nuevo)[:255],
            "Categoria": categoria,
        },
    )


# --- Excel -------------------------------------------------------------------------
def xlsx_bytes(titulo, encabezados, filas):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = titulo[:31]
    ws.append(encabezados)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="5A189A")
    for f in filas:
        ws.append([v.strftime("%Y-%m-%d %H:%M") if isinstance(v, datetime) else v for v in f])
    for col in ws.columns:
        ancho = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(ancho + 3, 50)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
