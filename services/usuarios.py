"""Usuarios, login y roles."""
import re

from werkzeug.security import check_password_hash, generate_password_hash

import config
import db
from services import ErrorNegocio
from services.comun import auditar

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SQL_USUARIO = """
    SELECT u.id, u.Usuario AS email, u.Contrasena, COALESCE(u.Nombre, u.Usuario) AS nombre,
           COALESCE(r.Rol, ?) AS rol
    FROM Usuario u
    LEFT JOIN UsuarioRol ur ON ur.idUsuario = u.id
    LEFT JOIN Rol r ON r.id = ur.idRol
"""


def autenticar(email, password):
    """Devuelve el usuario (dict sin hash) o None si las credenciales no son válidas."""
    email = (email or "").strip().lower()
    u = db.query_one(_SQL_USUARIO + " WHERE u.Usuario = ?", (config.ROL_OPERADOR, email))
    if not u or not check_password_hash(u["Contrasena"], password or ""):
        return None
    u.pop("Contrasena")
    return u


def registrar(nombre, email, password):
    nombre = (nombre or "").strip()
    email = (email or "").strip().lower()
    password = password or ""
    if not nombre or len(nombre) > 255:
        raise ErrorNegocio("Escribe tu nombre o ID de operador.")
    if not _RE_EMAIL.match(email) or len(email) > 255:
        raise ErrorNegocio("El correo no es válido.")
    if len(password) < 8:
        raise ErrorNegocio("La contraseña debe tener al menos 8 caracteres.")
    if db.scalar("SELECT COUNT(*) FROM Usuario WHERE Usuario = ?", (email,)):
        raise ErrorNegocio("Ya existe una cuenta con ese correo.", 409)

    with db.transaction():
        # El primer usuario del sistema es Gerente (puede asignar roles a los demás).
        hay_usuarios = db.scalar("SELECT COUNT(*) FROM Usuario WITH (UPDLOCK, HOLDLOCK)")
        rol = config.ROL_OPERADOR if hay_usuarios else config.ROL_GERENTE
        id_rol = db.scalar("SELECT id FROM Rol WHERE Rol = ?", (rol,))
        if id_rol is None:
            raise ErrorNegocio("Falta el catálogo de roles. Ejecuta sql/02_seed.sql.", 500)
        uid = db.insert(
            "Usuario",
            "id",
            {"Usuario": email, "Contrasena": generate_password_hash(password), "Nombre": nombre},
        )
        db.insert("UsuarioRol", "id", {"idRol": id_rol, "idUsuario": uid})
    return db.query_one(_SQL_USUARIO + " WHERE u.id = ?", (config.ROL_OPERADOR, uid))


def listar():
    return db.query(
        _SQL_USUARIO.replace("u.Contrasena,", "") + " ORDER BY COALESCE(u.Nombre, u.Usuario)",
        (config.ROL_OPERADOR,),
    )


def cambiar_rol(id_usuario, nivel, id_quien_cambia):
    rol = config.NIVELES.get(_a_int(nivel))
    if not rol:
        raise ErrorNegocio("Nivel de permisos no válido.")
    actual = db.query_one(_SQL_USUARIO + " WHERE u.id = ?", (config.ROL_OPERADOR, id_usuario))
    if not actual:
        raise ErrorNegocio("El usuario no existe.", 404)
    if actual["rol"] == rol:
        return actual

    with db.transaction():
        if actual["rol"] == config.ROL_GERENTE:
            gerentes = db.scalar(
                "SELECT COUNT(*) FROM UsuarioRol ur JOIN Rol r ON r.id = ur.idRol WHERE r.Rol = ?",
                (config.ROL_GERENTE,),
            )
            if gerentes <= 1:
                raise ErrorNegocio("Debe quedar al menos un Gerente en el sistema.", 409)
        id_rol = db.scalar("SELECT id FROM Rol WHERE Rol = ?", (rol,))
        db.execute("DELETE FROM UsuarioRol WHERE idUsuario = ?", (id_usuario,))
        db.insert("UsuarioRol", "id", {"idRol": id_rol, "idUsuario": id_usuario})
        auditar(
            "UsuarioRol", id_usuario, "Cambio de rol", id_quien_cambia,
            "Cambio desde Configuración", actual["rol"], rol, "Seguridad",
        )
    return {**actual, "rol": rol}


def _a_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
