# NOVA SOUND – Backend (Flask + SQL Server)

Backend del frontend de `CalidadYPruebas/NOVA_SOUND`. Mantiene las mismas rutas y plantillas;
los datos que antes eran de ejemplo ahora vienen de la base `nova_sound`.

## Puesta en marcha
1. En SQL Server ejecuta, en orden: `nova_sound.sql` → `sql/01_migracion.sql` → `sql/02_seed.sql`.
2. `pip install -r requirements.txt` (necesitas el *ODBC Driver 18 for SQL Server* instalado).
3. Define las variables de `.env.example` (`DB_SERVER`, `DB_NAME`, `DB_USER`/`DB_PASSWORD` o `DB_TRUSTED=1`, `SECRET_KEY`).
4. `python app.py` → http://localhost:5000
5. **El primer usuario que se registra queda como Gerente**; desde *Configuración* asigna roles al resto.

## Estructura
| Archivo | Qué hace |
|---|---|
| `app.py` | Rutas de páginas y API JSON (`/api/...`) |
| `config.py` | Roles, permisos por módulo, nombres de estados de pieza, límites |
| `db.py` | Conexión pyodbc por petición, `transaction()` |
| `auth.py` | Sesión y decorador `@modulo_requerido` |
| `services/` | Consultas y reglas de negocio (usuarios, producción, ensamble, dashboard) |
| `sql/` | Migración mínima y datos base |
| `tests/` | Pruebas de humo con BD simulada (`python -m pytest tests`) |

## Qué hace cada pantalla
- **Login / registro**: contraseña con hash; el correo se guarda en `Usuario.Usuario`, el nombre en `Usuario.Nombre` (columna nueva).
- **Crear orden**: crea `Cliente` (si es nuevo) + `Pedido` + `DetallePedido` + una `OrdenProduccion` por producto. Todas las órdenes de un pedido comparten **lote** (`LT-AAMMDD-NNN`). Código de orden mostrado: `OP-AAMMDD-<idOrden>`.
- **Órdenes / Detalles**: listados paginados (5 por página) con filtros (cliente, lote, estado, fechas).
- **Gráfico global**: 4 pestañas (colores, estados, turnos, estimaciones) + filtro de fechas + Excel.
- **Gráfico por pedido**: busca por lote; % = piezas *Empacada/Embarcada* ÷ cantidad solicitada.
- **Ensamble – registro**: valida orden en proceso y que no se sobreproduzca; crea `Produccion`, **una `Pieza` por unidad con número de serie** (`NSP-AAMMDD-00001`), sus `Ensamble` y actualiza `ProduccionTurno`. Al completar el objetivo la orden pasa a *Finalizado*.
- **Ensamble – histórico**: filtro por turno/fecha y reporte Excel.
- **Configuración**: cambia el rol de un usuario (con auditoría y sin dejar el sistema sin Gerente); la línea activa vive en la sesión.
- **Inicio (Calidad Final)**: resumen del turno actual desde `InspeccionCalidad` y `Pieza`.

Cambios de datos importantes quedan en la tabla `Auditoria`.

## Permisos (editables en `config.PERMISOS`)
Producción → Gerente · Ensamble → Operador y Gerente · Configuración → Gerente · Inicio → todos.

## Contrato para los módulos que faltan
Prueba Funcional, Calidad Final, Empaque, Embarque y Fin de Turno deben mover `Pieza.idEstado` entre los estados
de `config.ESTADOS_PIEZA` (`Ensamblada → Pruebas Funcionales → Aprobada → Empacada → Embarcada`, o `En retención` /
`En retrabajo` / `Scrap`). Ya dependen de esos nombres: el gráfico por pedido (Empacada/Embarcada) y el Inicio (En retención/En retrabajo).

## Decisiones y límites a revisar con el equipo
- `Produccion` no tiene fecha ni notas: la fecha del histórico sale de `Ensamble.FechaEnsamble`; las *Observaciones* se guardan en `Auditoria.Motivo`.
- `Produccion.idValidador` es NOT NULL y sin FK; por ahora se llena con el propio operador.
- El campo *Responsable* de "Crear orden" es el usuario en sesión (no hay columna para otro responsable).
- "Línea activa" y tema/fuente no se guardan en BD (sesión y `localStorage`).
- En `nova_sound.sql` el `CHECK` de `auditoriaCierre` trae `Correcci�n` (problema de codificación del archivo); guárdalo en UTF-8 con BOM o UTF-16 antes de ejecutarlo.
- Pruebas: corren contra una BD **simulada** y validan la sintaxis T-SQL con `sqlglot`; falta una pasada contra SQL Server real.
