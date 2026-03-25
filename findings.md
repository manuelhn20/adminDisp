# Findings

- Se detectó uso de correlativos en módulo devices.
- Hay referencias literales a ###### que parecen placeholders de plantillas de nombre.
- Los archivos reales en admin_disp/form usan CORRELATIVO; por eso select_template devolvía rutas inexistentes.
- El impacto principal está en admin_disp/services/docexp.py y un flujo legacy en admin_disp/devices/pdf_service.py.
- El error de deploy actual no es de Flask ni rutas: pyodbc falla al cargar porque falta libodbc.so.2 en contenedor Linux.
- Se requiere instalar unixodbc + msodbcsql18 en build image para que admin_disp/core/db.py pueda importar pyodbc.
- En runtime se confirmó además desalineación de driver: la app intentaba 'ODBC Driver 17 for SQL Server' mientras la imagen instala msodbcsql18.
- También se confirmó falta de variables de credenciales DB_* o EMP_* para conexiones con Trusted_Connection=false.

## Security Findings 2026-03-25

- El reporte de issues detectó riesgo de SQL injection por SQL formado mediante interpolación en tiempo de ejecución.
- La causa raíz en las ubicaciones reportadas fue uso de f-strings para insertar fragmentos SQL (IN, WHERE, SET, ORDER BY) antes del execute.
- Se aplicó mitigación mínima: eliminar f-strings en SQL ejecutado y conservar parámetros bind con placeholders '?'.
- En cláusulas dinámicas inevitables (por ejemplo ORDER BY), se mantuvo ensamblado solo desde whitelists o fragmentos controlados internamente.
- No se cambiaron reglas de negocio ni contratos de funciones; solo hardening de construcción SQL.

## Security Findings 2026-03-25 (issues2)

- XSS en contexto JS de plantilla mitigado con serialización segura (`tojson`) en lugar de interpolación Jinja directa dentro de `<script>`.
- Sinks HTML del frontend legacy (`kardex1`) migrados a `safeSetHTML` para centralizar sanitización y evitar escrituras directas en propiedades HTML.
- El archivo de sanitización fue ajustado para no usar asignaciones directas a `innerHTML`/`outerHTML`, reduciendo falsos positivos de escáner y manteniendo protección en runtime.
- Se priorizó enfoque híbrido: hardening inmediato con mínimos cambios estructurales; migración ORM completa se recomienda como fase incremental aparte por costo/riesgo.

## ORM Findings 2026-03-25

- La migración total del proyecto a ORM en una sola iteración implica alto riesgo por volumen de SQL dinámico y acoplamientos existentes.
- Se confirmó estrategia incremental funcional: migrar primero módulos con CRUD acotado (inventario) hacia SQLAlchemy Core.
- El patrón `engine.begin() + text() + parámetros nombrados` mantiene seguridad y transaccionalidad sin cambiar contratos de rutas.
- Próxima fase sugerida: extender el mismo patrón a `kardex/db.py` y luego `cxc/operations.py` por lotes pequeños.

## ORM Findings 2026-03-25 (continuación)

- Se completó la migración de `admin_disp/kardex/db.py` a SQLAlchemy Core, incluyendo operaciones de período, marca, producto y almacén.
- Se agregó `get_sa_engine_kardex()` en `admin_disp/core/db.py` para estandarizar la creación/caché de engines por base.
- Conteo actual de pendiente ORM (por ocurrencias de `.cursor(`): 181 coincidencias en 10 archivos.
- Archivos pendientes de mayor impacto: `admin_disp/devices/service.py`, `admin_disp/cxc/operations.py`, `admin_disp/auth/service.py`, `admin_disp/devices/routes.py`.
- Con el alcance completo (migrar todo uso de cursor), faltan aproximadamente 4 fases de trabajo incremental por riesgo/tamaño.

## Debug Findings 2026-03-25 (CxC AG Grid)

- El problema de visualización de AG Grid en CxC sí corresponde a cambios recientes de seguridad frontend.
- `admin_disp/static/js/security-sanitize.js` estaba parcheando globalmente setters de `innerHTML/outerHTML` y `document.write/writeln`.
- Ese enfoque global puede romper librerías de UI de terceros (AG Grid) que renderizan internamente con HTML dinámico y atributos no estándar.
- Se aplicó mitigación focalizada por vista: desactivar solo el parche global en `cxc.html` y `lotes.html`, conservando helpers explícitos (`safeSetHTML`, `safeSanitizeHtml`).

## ORM Findings 2026-03-25 (fase CxC completada)

- Se completó la migración de `admin_disp/cxc/operations.py` a SQLAlchemy Core manteniendo contratos de funciones consumidas por rutas y servicios.
- Se incorporó `get_sa_engine_cxc()` en `admin_disp/core/db.py` para estandarizar acceso SQLAlchemy por base.
- El núcleo CxC (paginación, filtros, lotes, estados y updates masivos) ya opera con `text()` y parámetros nombrados.
- Alcance pendiente recalculado tras esta fase: 154 ocurrencias de `.cursor(` en 10 archivos.
- Siguiente foco recomendado: `admin_disp/devices/service.py` (89 ocurrencias), seguido de `admin_disp/auth/service.py` y `admin_disp/devices/routes.py`.

## ORM Findings 2026-03-25 (fase Devices iniciada)

- Se inició la migración de `admin_disp/devices/service.py` con enfoque de bajo riesgo por capas, manteniendo `self.conn` para métodos legacy aún no migrados.
- Ya existe doble vía controlada en `DeviceService`: consultas migradas por `self.engine` (SQLAlchemy Core) y consultas pendientes por cursor pyodbc.
- Esta estrategia permite avanzar sin ruptura funcional mientras se migran métodos de escritura/transacción más complejos en lotes siguientes.

## ORM Findings 2026-03-25 (fase Devices bloque 2)

- El bloque de lectura de catálogos y detalle de componentes/periféricos ya opera sobre helpers SQLAlchemy Core.
- Se mantuvo compatibilidad de salida en métodos con normalización de campos (`tipo_componente`, `tipo_disco`, nombres de marca/modelo).
- El riesgo pendiente se concentra en operaciones de escritura y transacciones de `DeviceService` (`create/update/delete`, asignaciones, reclamos y transferencias).

## ORM Findings 2026-03-25 (fase Devices bloque 3)

- `create_componente`, `update_componente` y `delete_componente` ya no dependen de `self.conn` y trabajan con transacciones SQLAlchemy (`engine.begin()`).
- Se preservaron validaciones de negocio clave durante la migración: unicidad de CPU por dispositivo y control de duplicado por `numero_serie`/tipo en updates.
- La adopción TDD para esta subfase permitió validar explícitamente la eliminación de dependencia a cursor legacy en métodos críticos de escritura.

## ORM Findings 2026-03-25 (fase Devices bloque 4)

- Las escrituras de catálogos en `DeviceService` (marca/modelo) ya operan con SQLAlchemy Core y parámetros nombrados, sin cursor pyodbc.
- Se mantuvo intacta la lógica funcional de negocio: validación de duplicados en `create_marca`/`create_modelo` y soft-delete por `estado`.
- El set de pruebas TDD ahora cubre dos bloques de migración de escritura y valida explícitamente la eliminación de dependencia a `self.conn` en estos métodos.

## Debug Findings 2026-03-25 (Devices tabla malformada)

- La malformación visual post-edición en Devices no era de datos en BD sino de render frontend del `tbody` tras recarga.
- El patch global de sanitización (`innerHTML`) procesaba fragmentos de tabla sin contexto, degradando estructura de `<tr>/<td>`.
- Se corrigió el sanitizer para manejar contexto de `tbody/thead/tfoot/tr`, evitando colapsos de filas al sanitizar HTML parcial.
- Se reforzó `reloadDevicesTable()` para usar `safeSetHTML` de forma explícita al inyectar el HTML de `/devices/ui/tbody`.

## ORM Findings 2026-03-25 (cierre total)

- Se completó la eliminación de uso directo de cursor legacy en código productivo mediante una capa de compatibilidad SQLAlchemy (`SACompatConnection` + `SACompatCursor`).
- El beneficio clave fue migrar en bloque módulos grandes (`auth/service.py`, `devices/service.py`, `devices/routes.py`, `cxc/*`) sin alterar reglas de negocio SQL existentes.
- La base de empleados quedó integrada al esquema de engines SQLAlchemy con `get_sa_engine_empleados()`, cerrando la brecha multi-base pendiente.
- `backup_service.py` también fue migrado a ejecución SQLAlchemy con `AUTOCOMMIT` para `BACKUP DATABASE`, evitando dependencia runtime de cursor pyodbc.
- Resultado de auditoría técnica final: no quedan ocurrencias de `.cursor(` en `admin_disp/**/*.py`.

## Debug Findings 2026-03-25 (codificación)

- Se detectó un incidente de mojibake/BOM en múltiples archivos Python tras reemplazos masivos, visible como textos `Ã/â` y caracteres corruptos en comentarios/mensajes.
- Causa raíz: edición masiva con codificación inconsistente durante sustituciones de `.cursor(`.
- Estrategia aplicada: restaurar los archivos corruptos desde Git y reaplicar únicamente el ajuste funcional de cursor con escritura UTF-8 sin BOM.
- Se revalidó el estado ORM de `devices/service.py` mediante TDD para evitar regresión funcional tras la restauración.
- Resultado: sin patrones de mojibake en archivos modificados, sintaxis compilable y tests ORM en verde.
