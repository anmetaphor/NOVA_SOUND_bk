from datetime import date

from flask import (
    Flask, Response, jsonify, redirect, render_template, request, session, url_for,
)

import config
import db
from auth import modulo_requerido, usuario_actual
from services import ErrorNegocio, dashboard as svc_dashboard, ensamble as svc_ensamble
from services import produccion as svc_prod, usuarios as svc_usuarios
from services.comun import lineas, modelos, ventana_paginas, turnos, turno_actual

app = Flask(__name__)
app.config.from_object(config)
app.teardown_appcontext(db.close_db)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# --------------------------------------------------------------------------- helpers
@app.context_processor
def contexto():
    u = usuario_actual()
    hoy = date.today()
    return {
        "usuario": u,
        "user_badge": f"{u['rol']}: {u['nombre']}" if u else "",
        "linea_activa": session.get("linea", "L-01"),
        "hoy_iso": hoy.isoformat(),
        "fecha_larga": f"{hoy.day} {MESES[hoy.month - 1]} {hoy.year}",
        "url_pagina": lambda n: url_for(request.endpoint, **{**request.args.to_dict(), "page": n}),
        "ventana_paginas": ventana_paginas,
        "filtros": request.args,
    }


@app.errorhandler(ErrorNegocio)
def _error_negocio(e):
    if request.path.startswith("/api/"):
        return jsonify(error=e.mensaje), e.status
    return render_template("error.html", titulo="No se pudo completar", mensaje=e.mensaje), e.status


@app.errorhandler(403)
def _403(_e):
    return render_template("error.html", titulo="Sin permiso", mensaje="Tu rol no tiene acceso a esta sección."), 403


@app.errorhandler(404)
def _404(_e):
    if request.path.startswith("/api/"):
        return jsonify(error="No encontrado"), 404
    return render_template("error.html", titulo="No encontrado", mensaje="La página no existe."), 404


def _json():
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        raise ErrorNegocio("La petición debe enviarse como JSON.")
    return datos


def _xlsx(contenido, nombre):
    return Response(contenido, mimetype=XLSX, headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


def _filtros(*campos):
    return {c: request.args.get(c, "").strip() for c in campos}


# --------------------------------------------------------------------------- acceso
@app.route("/")
def index():
    if usuario_actual():
        return redirect(url_for("dashboard"))
    return render_template("index.html")


def _abrir_sesion(u):
    session.clear()
    session["usuario"] = {"id": u["id"], "nombre": u["nombre"], "email": u["email"], "rol": u["rol"]}


@app.route("/login", methods=["POST"])
def login():
    u = svc_usuarios.autenticar(request.form.get("email"), request.form.get("password"))
    if not u:
        return render_template("index.html", error="Correo o contraseña incorrectos.", modo="login"), 401
    _abrir_sesion(u)
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["POST"])
def register():
    try:
        u = svc_usuarios.registrar(request.form.get("nombre"), request.form.get("email"), request.form.get("password"))
    except ErrorNegocio as e:
        return render_template("index.html", error=e.mensaje, modo="registro"), e.status
    _abrir_sesion(u)
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# --------------------------------------------------------------------------- inicio
@app.route("/dashboard")
@modulo_requerido("dashboard")
def dashboard():
    return render_template("dashboard.html", r=svc_dashboard.resumen())


# --------------------------------------------------------------------------- producción
@app.route("/produccion/ordenes")
@modulo_requerido("produccion")
def ordenes_produccion():
    filas, info = svc_prod.listar_ordenes(_filtros("cliente", "lote", "estado", "desde", "hasta"), request.args.get("page"))
    return render_template("produccion_ordenes.html", filas=filas, info=info)


@app.route("/produccion/detalles")
@modulo_requerido("produccion")
def detalles_pedido():
    filas, info = svc_prod.listar_detalles(_filtros("cliente", "lote", "desde", "hasta"), request.args.get("page"))
    return render_template("produccion_detalles.html", filas=filas, info=info)


@app.route("/produccion/grafico-global")
@modulo_requerido("produccion")
def grafico_global():
    return render_template("produccion_grafico_global.html")


@app.route("/produccion/grafico-pedido")
@modulo_requerido("produccion")
def grafico_pedido():
    return render_template("produccion_grafico_pedido.html")


@app.route("/produccion/crear-orden")
@modulo_requerido("produccion")
def crear_orden():
    return render_template(
        "produccion_crear_orden.html",
        modelos=modelos(), lineas=lineas(), clientes=svc_prod.clientes(),
    )


@app.route("/api/produccion/pedidos", methods=["POST"])
@modulo_requerido("produccion")
def api_crear_pedido():
    return jsonify(svc_prod.crear_pedido(_json(), usuario_actual())), 201


@app.route("/api/produccion/grafico-global")
@modulo_requerido("produccion")
def api_grafico_global():
    return jsonify(svc_prod.grafico_global(request.args.get("tipo", "colores"), _filtros("desde", "hasta")))


@app.route("/api/produccion/grafico-pedido")
@modulo_requerido("produccion")
def api_grafico_pedido():
    return jsonify(svc_prod.progreso_pedido(request.args.get("lote")))


@app.route("/produccion/documento/global")
@modulo_requerido("produccion")
def documento_global():
    tipo = request.args.get("tipo", "colores")
    return _xlsx(svc_prod.documento_global(tipo, _filtros("desde", "hasta")), f"grafico_{tipo}.xlsx")


@app.route("/produccion/documento/pedido")
@modulo_requerido("produccion")
def documento_pedido():
    lote = request.args.get("lote", "")
    return _xlsx(svc_prod.documento_pedido(lote), f"pedido_{lote}.xlsx")


# --------------------------------------------------------------------------- ensamble
@app.route("/ensamble/registro")
@modulo_requerido("ensamble")
def ensamble_registro():
    return render_template(
        "ensamble_registro.html",
        turnos=turnos(), lineas=lineas(), turno_actual=turno_actual(),
        ultimos=svc_ensamble.ultimos_registros(),
    )


@app.route("/ensamble/historico")
@modulo_requerido("ensamble")
def ensamble_historico():
    f = _filtros("turno", "desde", "hasta")
    filas, info = svc_ensamble.historico(f, request.args.get("page"))
    return render_template("ensamble_historico.html", filas=filas, info=info, turnos=turnos())


@app.route("/ensamble/historico/reporte")
@modulo_requerido("ensamble")
def ensamble_reporte():
    return _xlsx(svc_ensamble.documento_historico(_filtros("turno", "desde", "hasta")), "historico_ensamble.xlsx")


@app.route("/api/ensamble/orden")
@modulo_requerido("ensamble")
def api_orden():
    o = svc_ensamble.buscar_orden(request.args.get("codigo"))
    if not o:
        raise ErrorNegocio("No se encontró esa orden.", 404)
    return jsonify({k: o[k] for k in ("codigo", "lote", "cliente", "modelo", "color", "objetivo", "producido", "pendiente", "estado")})


@app.route("/api/ensamble/registros", methods=["POST"])
@modulo_requerido("ensamble")
def api_registrar_ensamble():
    return jsonify(svc_ensamble.registrar(_json(), usuario_actual())), 201


@app.route("/api/ensamble/ultimos")
@modulo_requerido("ensamble")
def api_ultimos():
    return jsonify([
        {"linea": f["linea"], "orden": f["orden"], "cantidad": f["cantidad"], "operador": f["operador"]}
        for f in svc_ensamble.ultimos_registros()
    ])


# --------------------------------------------------------------------------- configuración
@app.route("/configuracion")
@modulo_requerido("configuracion")
def configuracion():
    return render_template("configuracion.html", usuarios=svc_usuarios.listar(), lineas=lineas(), niveles=config.NIVELES)


@app.route("/api/configuracion/rol", methods=["POST"])
@modulo_requerido("configuracion")
def api_cambiar_rol():
    d = _json()
    u = svc_usuarios.cambiar_rol(d.get("idUsuario"), d.get("nivel"), usuario_actual()["id"])
    if u["id"] == usuario_actual()["id"]:          # si se cambió su propio rol, actualiza la sesión
        session["usuario"] = {**usuario_actual(), "rol": u["rol"]}
    return jsonify(id=u["id"], rol=u["rol"])


@app.route("/api/configuracion/linea", methods=["POST"])
@modulo_requerido("dashboard")
def api_linea_activa():
    nombre = str(_json().get("linea", ""))
    if nombre not in [l["NombreLinea"] for l in lineas()]:
        raise ErrorNegocio("Línea no válida.")
    session["linea"] = nombre
    return jsonify(linea=nombre)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
