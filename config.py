"""Configuración central de NOVA SOUND.

Todo lo que dependa del entorno se lee de variables de entorno (ver .env.example).
Lo que es "regla del negocio" (nombres de estados, permisos por rol) vive aquí
para que el equipo lo pueda ajustar en un solo lugar.
"""
import os

# --- Flask -----------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esta-clave-en-produccion")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# --- SQL Server --------------------------------------------------------------
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_NAME = os.getenv("DB_NAME", "nova_sound")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_TRUSTED = os.getenv("DB_TRUSTED", "0") == "1"   # 1 = autenticación de Windows

# --- Roles (tabla Rol) -------------------------------------------------------
ROL_OPERADOR = "Operador"
ROL_INSPECTOR = "Inspector"
ROL_GERENTE = "Gerente"

# Nivel que muestra la pantalla de Configuración -> nombre del rol en la BD
NIVELES = {1: ROL_OPERADOR, 2: ROL_INSPECTOR, 3: ROL_GERENTE}

# Qué roles pueden entrar a cada módulo. None = cualquier usuario con sesión.
PERMISOS = {
    "dashboard": None,
    "produccion": (ROL_GERENTE,),
    "ensamble": (ROL_OPERADOR, ROL_GERENTE),
    "configuracion": (ROL_GERENTE,),
}

# --- Estados de pieza (tabla EstadoPieza) ----------------------------------
# Los demás módulos (Prueba Funcional, Calidad Final, Empaque, Embarque)
# deben mover las piezas entre estos estados. Se crean en sql/02_seed.sql.
ESTADOS_PIEZA = [
    "Ensamblada",
    "Pruebas Funcionales",
    "Aprobada",
    "En retención",
    "En retrabajo",
    "Scrap",
    "Empacada",
    "Embarcada",
]
EST_ENSAMBLADA = "Ensamblada"
EST_RETENCION = "En retención"
EST_RETRABAJO = "En retrabajo"
EST_EMPACADAS = ("Empacada", "Embarcada")   # cuentan como "pedido avanzado" en el gráfico

# Prefijo de número de serie por modelo (NSP-261016-00942 = NS-PRO)
PREFIJO_SERIE = {"NS-MINI": "NSM", "NS-SPORT": "NSS", "NS-PRO": "NSP", "NS-MAX": "NSX"}

# --- Límites -----------------------------------------------------------------
POR_PAGINA = 5
MAX_PIEZAS_POR_REGISTRO = 1000
MAX_CANTIDAD_DETALLE = 10000
