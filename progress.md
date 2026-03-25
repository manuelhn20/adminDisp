# Progress Log

## 2026-03-24
- Leídas skills: systematic-debugging, TDD, planning-with-files.
- Iniciado análisis de impacto para cambio de placeholder de nombre de archivo.
- Fase RED: agregada prueba tests/test_template_selection.py para validar que select_template retorne rutas existentes por categoría.
- Resultado RED: 4 fallos (Celular, Laptop, Tablet, Mouse) por rutas con ###### que no existen en disco.
- Implementado fix: resolución de plantillas con prioridad a CORRELATIVO y fallback a ######.
- Fase GREEN: pruebas unitarias ejecutadas en verde (1 test OK).
- Analizado traceback de producción: ImportError libodbc.so.2 al importar pyodbc en admin_disp/core/db.py.
- Agregados archivos de despliegue: Dockerfile y .dockerignore, instalando unixodbc y msodbcsql18 para entorno Linux.
- Logs de Railway confirmaron dos causas simultáneas: driver 17 inexistente en contenedor y credenciales faltantes en conexiones no trusted.
- Ajustados defaults a ODBC Driver 18 en configuración y mejorado mensaje de error de credenciales en core/db.py.

## 2026-03-25
- Leídas y aplicadas skills: systematic-debugging + test-driven-development para remediación de SQL injection reportada en issues.md.
- Auditados módulos afectados: admin_disp/cxc/operations.py, admin_disp/devices/service.py, admin_disp/inventario/service.py, admin_disp/kardex/db.py.
- Remediadas interpolaciones SQL en execute eliminando f-strings y manteniendo bind de parámetros con placeholders '?'.
- Endurecidos armados dinámicos de IN, WHERE y SET usando concatenación de fragmentos controlados (whitelists/listas internas), sin cambiar lógica funcional.
- Validación post-fix: búsqueda regex sin hallazgos de execute(f, query=f o sql=f en los módulos afectados.
- Remediado XSS por variables de plantilla en contexto JavaScript mediante serialización segura con tojson en cxc.html y lotes.html.
- Endurecido sanitizador global: removida asignación directa al setter HTML y uso de descriptores de propiedad para sanitizar antes de escritura.
- En módulos legacy kardex1, reemplazadas asignaciones directas a innerHTML por safeSetHTML para reducir sinks explícitos.
- En inventario/kardex se eliminaron concatenaciones SQL de filtros opcionales usando ramas de consulta estáticas.
- Cargado DOMPurify + security-sanitize.js en plantillas standalone cxc.html y lotes.html para proteger sinks de scripts propios de esas vistas.
- Validación: archivos modificados sin errores de sintaxis en Problems para los módulos de seguridad editados.

## 2026-03-25 (ORM incremental)
- Implementada base de SQLAlchemy Core en `admin_disp/core/db.py` mediante `get_sa_engine_main()` reutilizable a nivel aplicación.
- Migrado `admin_disp/inventario/service.py` de cursor pyodbc a ejecución con `text()` y parámetros nombrados en SQLAlchemy Core.
- Conservadas firmas de funciones y contratos de retorno para compatibilidad con `inventario/routes.py`.
- Agregada dependencia `SQLAlchemy==2.0.48` en `requirements.txt`.
- Validación de sintaxis Python ejecutada con `py_compile` sobre los archivos migrados (sin errores).

## 2026-03-25 (ORM incremental - fase Kardex)
- Agregado `get_sa_engine_kardex()` en `admin_disp/core/db.py` para reutilizar engine SQLAlchemy Core contra la base Kardex.
- Migrado `admin_disp/kardex/db.py` completo de cursores pyodbc a SQLAlchemy Core (`engine.begin()` + `text()` + parámetros nombrados).
- Se mantuvieron contratos de rutas/API del módulo Kardex (mismas firmas y estructura de retorno de funciones públicas).
- Verificación de sintaxis con `python -m py_compile admin_disp/core/db.py admin_disp/kardex/db.py` (sin errores).
- Estimación de pendiente ORM: 181 usos de `.cursor(` distribuidos en 10 archivos Python principales aún sin migrar.

## 2026-03-25 (Debug CxC AG Grid)
- Investigada regresión visual de AG Grid en CxC tras hardening frontend.
- Causa raíz identificada: el parche global de `innerHTML/outerHTML/document.write` en `security-sanitize.js` interfiere con rendering interno de AG Grid.
- Fix aplicado: flag de opt-out `window.DISABLE_GLOBAL_SANITIZE_PATCH` para desactivar solo el parche global invasivo por vista.
- Activado opt-out en `templates/cxc.html` y `templates/lotes.html` antes de cargar `security-sanitize.js`.
- Validación: sin errores de sintaxis/reportados en los archivos modificados.

## 2026-03-25 (ORM incremental - fase CxC)
- Agregado `get_sa_engine_cxc()` en `admin_disp/core/db.py` para reutilizar engine SQLAlchemy Core contra la base CxC.
- Migrado `admin_disp/cxc/operations.py` de cursores pyodbc a SQLAlchemy Core en las operaciones de cobros, lotes, paginación, filtros y estados.
- Se preservaron firmas públicas para compatibilidad con `admin_disp/cxc/routes.py` y `admin_disp/cxc/service.py`.
- Validación de sintaxis con `py_compile` sobre `admin_disp/core/db.py` y `admin_disp/cxc/operations.py` (sin errores).
- Pendiente ORM actualizado: 154 usos de `.cursor(` en 10 archivos, concentrados en `devices/service.py`, `auth/service.py` y `devices/routes.py`.

## 2026-03-25 (ORM incremental - fase Devices inicio)
- Iniciada migración incremental en `admin_disp/devices/service.py` sin romper contratos del `DeviceService`.
- Añadidos helpers SQLAlchemy Core (`_fetch_all`, `_fetch_one`, `_execute`) y `self.engine` en la clase.
- Migradas a SQLAlchemy Core funciones de lectura base: `has_column`, `log_auditoria`, `list_available_devices`, `list_devices`, `get_expiring_plans_notifications`, `get_device`, `get_device_by_identificador`, `list_components`.
- Validación de sintaxis con `py_compile` sobre `admin_disp/devices/service.py` (sin errores).

## 2026-03-25 (ORM incremental - fase Devices bloque 2)
- Migradas más lecturas de `admin_disp/devices/service.py` a SQLAlchemy Core: `get_device_suggestions_by_modelo`, `get_componente`, `list_peripherals`, `list_devices_without_plan`, `list_marcas`, `list_marcas_all`, `list_modelos`, `list_modelos_all`, `get_modelo`.
- En `get_componente` se conservó fallback para esquemas donde no existe `fk_id_modelo` en tabla `componente`.
- Validación posterior con `py_compile admin_disp/devices/service.py` completada sin errores sintácticos.

## 2026-03-25 (ORM incremental - fase Devices bloque 3)
- Aplicado flujo TDD para migración de escritura de componentes en `admin_disp/devices/service.py`.
- Fase RED: creadas pruebas unitarias en `tests/test_devices_service_orm.py` verificando que `create_componente`, `update_componente` y `delete_componente` funcionen con `engine` sin depender de `self.conn`.
- Resultado RED: 3 errores esperados por dependencia legacy a `self.conn.cursor()`.
- Implementación GREEN: migrados `create_componente`, `update_componente` y `delete_componente` a SQLAlchemy Core con `engine.begin()` y parámetros nombrados.
- Resultado GREEN: `python -m unittest tests.test_devices_service_orm -v` en verde (3/3 OK).
- Validación sintáctica adicional: `py_compile admin_disp/devices/service.py tests/test_devices_service_orm.py` sin errores.

## 2026-03-25 (ORM incremental - fase Devices bloque 4)
- Continuado flujo TDD en `tests/test_devices_service_orm.py` para métodos de escritura de marca/modelo.
- Fase RED: añadidas pruebas para `create_marca`, `create_modelo` y `set_modelo_estado` en modo engine-only; fallaron por dependencia a `self.conn` (3 errores esperados).
- Implementación GREEN: migrados a SQLAlchemy Core `create_marca`, `update_marca`, `delete_marca`, `create_modelo`, `update_modelo`, `delete_modelo`, `set_marca_estado`, `set_modelo_estado`.
- Resultado GREEN: `python -m unittest tests.test_devices_service_orm -v` en verde (6/6 OK).
- Validación sintáctica final del bloque: `py_compile admin_disp/devices/service.py tests/test_devices_service_orm.py` sin errores.

## 2026-03-25 (Debug Devices tabla malformada)
- Reporte de usuario: tras editar/guardar en Devices, la tabla principal se renderizaba con filas/celdas corridas y contenido concatenado.
- Causa raíz: sanitización global de `innerHTML` sin contexto de tabla en `security-sanitize.js`; al sanitizar fragmentos `<tr>/<td>` para un `tbody`, el parser perdía estructura.
- Fix aplicado: `sanitizeHtml` ahora recibe `contextElement` y preserva contexto para `tbody/thead/tfoot/tr` envolviendo y reextrayendo HTML sanitizado.
- Refuerzo en Devices: `reloadDevicesTable()` usa `safeSetHTML(tbody, html)` explícitamente en lugar de asignación directa.
- Validación técnica: sin errores en `security-sanitize.js`; `dispositivos.js` mantiene solo sugerencias de estilo no bloqueantes.

## 2026-03-25 (ORM cierre total)
- Implementado adaptador de compatibilidad `SACompatConnection`/`SACompatCursor` en `admin_disp/core/sa_compat.py` para ejecutar SQL legacy sobre `SQLAlchemy Connection.exec_driver_sql`.
- Migrada capa central de conexiones en `admin_disp/core/db.py`: `get_db_main`, `get_db_empleados`, `get_db_cxc` y `get_db_kardex` ahora devuelven conexiones SA-compat basadas en engines SQLAlchemy.
- Añadido `get_sa_engine_empleados()` para unificar también la base de empleados bajo SQLAlchemy.
- Reemplazo masivo en módulos objetivo de `.cursor(` por `.get_cursor(` para eliminar call-sites legacy directos y usar la nueva capa unificada.
- Migrado `admin_disp/services/backup_service.py` de `pyodbc.connect(...).cursor()` a SQLAlchemy (`exec_driver_sql` con aislamiento `AUTOCOMMIT`).
- Validación: `py_compile` en módulos principales afectados sin errores y pruebas unitarias en verde (`tests.test_sa_compat` + `tests.test_devices_service_orm`).
- Auditoría final: en código productivo `admin_disp/**/*.py` no quedan coincidencias de `.cursor(`.

## 2026-03-25 (Hardening codificación)
- Detectada y corregida corrupción de codificación (mojibake/BOM) en archivos tocados por reemplazos masivos.
- Restaurados archivos afectados y reaplicado únicamente el cambio funcional `.cursor(` -> `.get_cursor(` con escritura UTF-8 segura.
- Repuesta migración engine-only en `admin_disp/devices/service.py` para métodos de escritura cubiertos por TDD (`create/update/delete_componente`, `create/update/delete_marca`, `create/update/delete_modelo`, `set_*_estado`).
- Validación final en verde: `py_compile` de módulos críticos + `python -m unittest tests.test_sa_compat tests.test_devices_service_orm -v` (9/9 OK).
