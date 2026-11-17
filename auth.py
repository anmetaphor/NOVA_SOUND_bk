"""Sesión y control de acceso por rol."""
from functools import wraps

from flask import abort, jsonify, redirect, request, session, url_for

import config


def usuario_actual():
    return session.get("usuario")


def _sin_sesion():
    if request.path.startswith("/api/"):
        return jsonify(error="Sesión expirada. Inicia sesión de nuevo."), 401
    return redirect(url_for("index"))


def modulo_requerido(modulo):
    """Decorador: exige sesión y que el rol tenga permiso sobre `modulo`."""
    permitidos = config.PERMISOS[modulo]

    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            u = usuario_actual()
            if not u:
                return _sin_sesion()
            if permitidos is not None and u["rol"] not in permitidos:
                if request.path.startswith("/api/"):
                    return jsonify(error="No tienes permiso para esta acción."), 403
                abort(403)
            return f(*args, **kwargs)

        return wrapper

    return deco
