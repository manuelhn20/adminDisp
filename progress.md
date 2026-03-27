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

## 2026-03-25 (Fix flujo asignaciones - modal documentos)
- Investigado bloqueo de avance en paso "Documentos en OneDrive" dentro de Asignaciones (Devices).
- Causa raíz: handlers inline (`onclick`) en HTML dinámico eran removidos por sanitización global, dejando botones visibles pero sin acción.
- Fix aplicado en `admin_disp/static/js/asignaciones.js`: reemplazo de handlers inline por `addEventListener` para botones de Continuar, Descargar, Cancelar, Regenerar y Confirmar.
- Hardening adicional: normalización de `estado` a número para evitar desvíos por comparación estricta de tipos (`'21'` vs `21`).

## 2026-03-25 (Rollback CxC LIQ-00026)
- Ejecutada reversión transaccional solicitada para `LIQ-00026` (lote `id=109`) en base CxC.
- Cobros asociados actualizados a estado recibido y sin liquidación: `estado=0`, `liquidado=NULL`, `liquidadoPor=NULL`, `fechaLiquidado=NULL`, `loteId=NULL`.
- Eliminado el lote de liquidación `LIQ-00026` de tabla `lote`.
- Verificación posterior completada: `LOTE_LIQ00026_COUNT=0`, `COBROS_WITH_LOTE_109=0`, `COBROS_LOTE_109_ESTADO2_LIQSI=0`.

## 2026-03-25 (Fix AG Grid Kardex productos + modales)
- Investigado fallo en vista `kardex/productos`: no renderizaba AG Grid ni acciones de modales de Marcas/Almacenes/Períodos.
- Causa confirmada: `security-sanitize.js` con parche global activo en `base_kardex.html` interfería con render dinámico de AG Grid.
- Fix aplicado: soporte de desactivación por vista en `base_kardex.html` mediante flag `disable_global_sanitize_patch` antes de cargar sanitizer.
- Activado flag solo para `productos_view` en `admin_disp/kardex/routes.py` (`disable_global_sanitize_patch=True`).

## 2026-03-25 (Devices AG Grid fase 1 + modales)
- Aplicado flujo TDD para iniciar migración de Devices a AG Grid en 3 tablas clave: activos, eliminados y celulares.
- Fase RED: añadidas pruebas en `tests/test_devices_aggrid_migration.py` para exigir assets AG Grid, contenedores, bootstrap JS y endpoint de celulares.
- Implementación GREEN en `admin_disp/templates/dispositivos.html`: botones `Ver eliminados` y `Ver celulares` migrados a modales estilo Kardex (`modalDeletedDevicesGrid` y `modalCelularesGrid`).
- Implementación GREEN en `admin_disp/static/js/dispositivos.js`: creada inicialización `initDevicesAgGrids` con APIs `devicesGridApi`, `deletedDevicesGridApi`, `celularesGridApi`, delegación de acciones y recarga unificada por JSON.
- Implementación backend en `admin_disp/devices/routes.py`: nuevo endpoint `GET /devices/celulares/` con normalización de teléfono y activación de `disable_global_sanitize_patch=True` para vista Devices.
- Validación GREEN: `python -m unittest tests.test_devices_aggrid_migration -v` en verde (5/5 OK).

## 2026-03-25 (Debug Devices AG Grid visibilidad + modales)
- Reporte de usuario: en Devices la grilla principal quedaba visualmente en blanco y los modales de eliminados/celulares no renderizaban bien.
- Causa raíz identificada: combinación de inicialización AG Grid sobre contenedores ocultos (modales cerrados) y falta de tokens/altura explícita para AG Grid en `dispositivos.css`.
- Fix aplicado en `admin_disp/static/js/dispositivos.js`: creación diferida de grids de modales (`ensureDeletedDevicesGrid`, `ensureCelularesGrid`) y refresco de layout robusto (`_refreshGridLayout`) al abrir modal.
- Fix aplicado en `admin_disp/static/css/dispositivos.css`: alturas explícitas para contenedores AG Grid, tema claro/oscuro dedicado para contraste y ajuste de layout flex en modales de grids.
- Validación post-fix: `python -m unittest tests.test_devices_aggrid_migration -v` en verde (5/5 OK).

## 2026-03-25 (Devices AG Grid UX: eliminar visible + negro + selección/copia)
- Se añadió columna de selección por checkbox (con selección múltiple) en las 3 grillas AG Grid de Devices para facilitar selección de registros.
- Se habilitó interacción de copia en celdas con `enableCellTextSelection`, selección por rango y orden de DOM estable para copiar con teclado.
- Se amplió el ancho de la columna `Acciones` en activos/celulares para asegurar visibilidad constante del botón de eliminar.
- Se cambió la paleta de la grilla a negro neutro (fondo/encabezado/filas alternas), eliminando el tono dark-blue.
- En la grilla de celulares se redujeron los anchos de columnas `Marca` y `Estado` aproximadamente en una decena para compactar visualmente.
- Validación: `python -m unittest tests.test_devices_aggrid_migration -v` en verde (5/5 OK).

## 2026-03-25 (Devices AG Grid refinement: remover checkboxes, mantener text selection)
- Usuario solicitó remover la capacidad de seleccionar registros (checkboxes) pero mantener la capacidad de seleccionar texto en celdas.
- Cambios realizados en `admin_disp/static/js/dispositivos.js`:
  - Removida la columna de selección (`_buildSelectionColumnDef()`) de todas las 3 grillas (activos, eliminados, celulares).
  - Removidas opciones de multi-select: `rowSelection: 'multiple'`, `rowMultiSelectWithClick: true`, `enableRangeSelection: true`, `ensureDomOrder: true`.
  - Mantenidas opciones de text selection: `enableCellTextSelection: true`, `copyHeadersToClipboard: true`, `suppressCellFocus: false`.
- Beneficios: Interfaz más limpia sin confundirse con selección de filas; selección de texto y copia por rango siguen funcionando normalmente.
- Validación: Sin errores sintácticos en archivo modificado.

## 2026-03-25 (Devices AG Grid Estado badge colors)
- Reporte de usuario: En la vista de celulares, el campo Estado no muestra los colores esperados.
- Causa: La función `_buildEstadoBadge()` usaba clases CSS (`text-danger`, `text-success`, etc.) que no se aplican correctamente en contexto de AG Grid con tema personalizado.
- Fix aplicado: Cambiar `_buildEstadoBadge()` para usar estilos inline en lugar de clases. Se mapean los colores (`danger`→`#dc3545`, `success`→`#28a745`, `warning`→`#ffc107`, `primary`→`#007bff`, `secondary`→`#6c757d`) y se aplican directamente con `style="color: [color]; font-weight: 600;"`.
- Ventaja: Estilos inline garantizan que los colores se rendericen correctamente dentro de celdas de AG Grid sin depender de hojas de estilo externas.

## 2026-03-25 (Devices modal celulares - tamaño y campo nombre)
- Reporte de usuario: La modal de celulares es muy angosta y el campo Nombre no es completamente visible.
- Cambios realizados:
  - En `admin_disp/static/css/dispositivos.css`: aumentar max-width de 1360px a 1600px y width de 96% a 98% para la modal.
  - En `admin_disp/static/js/dispositivos.js`: aumentar minWidth del campo Nombre de 180 a 240 y flex de 1 a 1.2 para darle más espacio visible.
- Validación: Sin errores sintácticos en archivos modificados.

## 2026-03-26 (Devices modal eliminados - ajuste de ancho y campos)
- Reporte de usuario: Modal de eliminados muy ancha; campo Acciones y botón de restaurar no visibles sin scroll.
- Causa: max-width 1600px era demasiado grande; Observaciones minWidth 250/flex 1.2 y Acciones minWidth 100/maxWidth 120 comprimían demasiado.
- Cambios realizados:
  - Modal eliminados: reducir max-width a 1300px (más equilibrado) y width a 97%.
  - Observaciones: reducir minWidth 250→220 y flex 1.2→1.
  - Acciones: aumentar minWidth 100→130 y maxWidth 120→150 para que botón sea visible sin scroll.
- Validación: Sin errores sintácticos. Botón restaurar será visible en el viewport.

## 2026-03-26 (Devices modal eliminados - compactación de columnas)
- Reporte de usuario: Columnas Modelo, Marca y Dirección IP muy grandes; botón Acciones poco visible.
- Cambios realizados en `admin_disp/static/js/dispositivos.js`:
  - Modelo: minWidth 160→130, flex 1→0.9 (reduce espacio)
  - Marca: minWidth 150→130, flex 1→0.9 (reduce espacio)
  - Dirección IP: minWidth 150→130, flex 1→0.9 (reduce espacio)
  - Acciones: minWidth 130→100, maxWidth 150→130 (botón más compacto)
- Validación: Sin errores sintácticos. Columnas más compactas, botón Acciones más visible.

## 2026-03-26 (Asignaciones AG Grid: principal + transfer + histórico modal)
- Aplicado TDD (RED→GREEN) para migración de tablas en Asignaciones a AG Grid.
- RED: creado `tests/test_asignaciones_aggrid_migration.py` con 5 pruebas (assets AG Grid, contenedores, modal histórico, bootstrap JS y quickFilter por `asignacionesPageSearch`).
- GREEN en `admin_disp/templates/asignaciones.html`:
  - Agregados assets AG Grid v32.3.3.
  - Tabla principal migrada a contenedor `#asignacionesGrid`.
  - Tablas de transferir migradas a `#transferSourceGrid` y `#transferTargetGrid`.
  - Histórico migrado a modal `#modalHistoricoAsignacionesGrid` con grid `#historicoAsignacionesGrid`.
  - Inyectados seeds JSON: `window.__ASIGNACIONES_RESUMEN_DATA` y `window.__ASIGNACIONES_HISTORICO_DATA`.
- GREEN en `admin_disp/static/js/asignaciones.js`:
  - Nuevas APIs: `asignacionesGridApi`, `transferSourceGridApi`, `transferTargetGridApi`, `historicoAsignacionesGridApi`.
  - Nuevas funciones: `initAsignacionesAgGrids()` y `applyAsignacionesGridSearchFilter()`.
  - `toggleHistoricoView()` ahora abre/cierra modal histórico AG Grid.
  - `asignacionesPageSearch` ahora aplica `quickFilterText` a grid principal o histórico, y a grids de transfer cuando modal está abierto.
  - Flujo de transfer actualizado a selección AG Grid (sin checkboxes DOM legacy).
  - `reloadAsignacionesTable()` ahora consume `resumen_data`/`historico_data` y refresca rowData de grids.
- GREEN en `admin_disp/static/css/asignaciones.css`:
  - Agregado tema AG Grid negro consistente y sizing de contenedores (`asignaciones-grid`, `transfer-grid`, `historico-grid`).
  - Header de acciones centrado con `ag-actions-header`.
- Backend actualizado en `admin_disp/devices/routes.py` (`/asignaciones/tbody`) para devolver, además del HTML legacy, datasets JSON `resumen_data` y `historico_data`.
- Validación:
  - `python -m unittest tests.test_asignaciones_aggrid_migration -v` → 5/5 OK.
  - `python -m unittest tests.test_devices_aggrid_migration -v` → 5/5 OK (sin regresión).

## 2026-03-26 (Hotfix Asignaciones AG Grid en blanco / tema claro)
- Causa detectada: en `admin_disp/templates/asignaciones.html` el CSS de página (`asignaciones.css`) se cargaba antes de `ag-theme-material.css`, por lo que variables visuales dark de AG Grid quedaban sobreescritas por el tema base.
- Fix aplicado: reordenado en `extra_head` para cargar primero AG Grid (`ag-grid.css` + `ag-theme-material.css`) y luego `asignaciones.css` (mismo patrón usado en `dispositivos.html`).
- Refuerzo visual en `admin_disp/static/css/asignaciones.css`: estilos explícitos para `.ag-root-wrapper`, `.ag-header` y `.ag-paging-panel` usando `--ag-background-color` negro y `--ag-foreground-color` claro.
- Validación: `python -m unittest tests.test_asignaciones_aggrid_migration -v` → 5/5 OK.

## 2026-03-26 (Asignaciones AG Grid: deprecaciones + altura dinámica en transfer)
- Eliminadas APIs deprecadas de AG Grid en `admin_disp/static/js/asignaciones.js`:
  - Se removió `checkboxSelection` y `headerCheckboxSelection` en `columnDefs`.
  - Se migró `rowSelection: 'multiple'` a `rowSelection` objeto (`mode: 'multiRow'`, `checkboxes: true`, `headerCheckbox: true`).
- Reducido tamaño vertical de grids de transferencia con autoajuste por cantidad de dispositivos:
  - Nueva función `_asigAutoHeightForDevicesGrid(containerId, rowCount, maxRows)`.
  - Se aplica en origen/destino al abrir modal, cargar empleado y limpiar selección.
  - Límite visual configurado a 6 filas.
- Evitada advertencia de `sizeColumnsToFit` en grids ocultos:
  - `_asigRefreshGridLayout` ahora verifica visibilidad del contenedor antes de llamar `sizeColumnsToFit`.
  - Se actualizó llamada a `_asigRefreshGridLayout` pasando id de contenedor en los grids relevantes.
- Validación: `python -m unittest tests.test_asignaciones_aggrid_migration -v` → 5/5 OK.

## 2026-03-26 (Planes/Reclamos AG Grid implementación)
- Aplicado flujo TDD (RED -> GREEN) para implementación AG Grid en módulos Planes y Reclamos.
- RED: creada suite `tests/test_planes_reclamos_aggrid_migration.py` con 4 pruebas (assets AG Grid + contenedores + bootstrap JS en ambos módulos).
- RED validado: ejecución inicial con fallos esperados por ausencia de assets/containers/scripts AG Grid.
- GREEN en backend: `admin_disp/devices/routes.py` actualizado para renderizar `planes.html` y `reclamos.html` con `disable_global_sanitize_patch=True`.
- GREEN en templates:
  - `admin_disp/templates/planes.html`: assets AG Grid, contenedor `#planesGrid`, tabla legacy oculta y carga de `js/planes_aggrid.js`.
  - `admin_disp/templates/reclamos.html`: bloque `extra_head` con assets AG Grid, contenedor `#reclamosGrid`, tabla legacy oculta y carga de `js/reclamos_aggrid.js`.
  - `admin_disp/templates/reclamos.html` y `admin_disp/templates/reclamosTbody.html`: agregado `data-id` por fila para sincronización de acciones.
- GREEN en frontend JS:
  - `admin_disp/static/js/planes_aggrid.js`: inicialización AG Grid, quick filter, acciones Editar/Renovar y sincronización con `refreshPlanesTbody`.
  - `admin_disp/static/js/reclamos_aggrid.js`: inicialización AG Grid, quick filter, acciones Editar/Eliminar y sincronización con `reloadReclamosTable`.
- Validación final GREEN: `python -m unittest tests.test_planes_reclamos_aggrid_migration -v` -> 4/4 OK.

## 2026-03-26 (Reclamos AG Grid tema oscuro)
- Reporte de usuario: la grilla AG Grid de Reclamos quedó en tema claro/blanco.
- Fase RED: se añadió prueba en `tests/test_planes_reclamos_aggrid_migration.py` para exigir tokens dark y clase scoped de Reclamos.
- Implementación GREEN en `admin_disp/templates/reclamos.html`:
  - clase scoped `reclamos-ag-grid` aplicada al contenedor `#reclamosGrid`.
  - tokens AG Grid dark (`--ag-background-color: #070707` y relacionados) + estilos de wrapper/header/paging/celdas.
- Validación GREEN: `python -m unittest tests/test_planes_reclamos_aggrid_migration.py` en verde (6/6 OK).

## 2026-03-26 (AG Grid switch global oscuro/claro)
- Requerimiento de usuario: mantener AG Grid en negro cuando el tema sea oscuro y cambiar automáticamente a paleta clara cuando el tema sea claro.
- Fase RED: agregada prueba en `tests/test_planes_reclamos_aggrid_migration.py` para exigir reglas globales de switch en `admin_disp/static/css/style.css`.
- Implementación GREEN en `admin_disp/static/css/style.css`:
  - Reglas globales para `html[data-dark-mode="true"] .ag-theme-material` (paleta dark).
  - Reglas globales para `html:not([data-dark-mode="true"]) .ag-theme-material` (paleta light).
  - Ajuste global de wrappers/celdas AG Grid para usar variables activas por tema.
- Validación GREEN: `python -m unittest tests/test_planes_reclamos_aggrid_migration.py` en verde (7/7 OK).

## 2026-03-26 (Dispositivos modales AG Grid alineadas a Kardex)
- Requerimiento de usuario: replicar patrón visual de Kardex (Marcas/Almacenes/Períodos) en modales AG Grid de Dispositivos.
- Fase RED: añadidas pruebas en `tests/test_devices_aggrid_migration.py` para exigir:
  - search bar dedicada por modal AG Grid de Dispositivos.
  - estructura de toolbar en modal (`deletedDevicesModalToolbar`, `celularesModalToolbar`).
  - eliminación de botones de cerrar en footer para esas modales.
- Implementación GREEN en `admin_disp/templates/dispositivos.html`:
  - `#modalDeletedDevicesGrid` y `#modalCelularesGrid` ahora incluyen toolbar con `input` de búsqueda.
  - removidos footers con botón `Cerrar` en ambas modales AG Grid.
- Implementación GREEN en `admin_disp/static/js/dispositivos.js`:
  - nuevas funciones `bindDevicesModalSearchInputs`, `applyDeletedDevicesSearchFilter`, `applyCelularesSearchFilter`.
  - conexión de quick filter por modal al abrir Eliminados/Celulares.
- Implementación GREEN en `admin_disp/static/css/dispositivos.css`:
  - layout toolbar superior en modal y ajuste de body/grid para diseño minimalista tipo Kardex.
  - limpieza de tokens AG Grid hardcodeados para respetar switch global de tema.
- Validación final GREEN:
  - `python -m unittest tests/test_devices_aggrid_migration.py tests/test_planes_reclamos_aggrid_migration.py` -> 14/14 OK.

## 2026-03-26 (Cierre total de faltantes reportados por usuario)
- Requerimiento pendiente: completar implementación en `modalHistoricoPlanes`, `modalHistoricoAsignacionesGrid` y `modalPrinterHistory`.
- Cambios aplicados en templates:
  - `admin_disp/templates/planes.html`: removido footer con botón `Cerrar` en modal histórico de planes.
  - `admin_disp/templates/asignaciones.html`: removido footer con botón `Cerrar` en modal histórico de asignaciones.
  - `admin_disp/templates/base.html`: removido footer con botón `Cerrar` en `modalPrinterHistory`; agregado input `printerHistorySearchInput` y filtro funcional `applyPrinterHistorySearchFilter` para impresión/copias.
- Integración de búsqueda en `modalPrinterHistory`:
  - El filtro se aplica por pestaña activa (Impresión/Copias).
  - Se reaplica automáticamente al cambiar pestaña y al paginar.
  - Se limpia al abrir/cerrar el modal para evitar residuos de estado.
- Validación GREEN final:
  - `python -m unittest tests/test_planes_reclamos_aggrid_migration.py tests/test_asignaciones_aggrid_migration.py tests/test_printer_history_modal_ui.py -v` -> 16/16 OK.

## 2026-03-26 (Refinamiento UI + AG Grid para historial de impresoras)
- Ajuste visual solicitado por usuario en histórico de asignaciones:
  - `admin_disp/templates/asignaciones.html`: input `historicoAsignacionesSearchInput` actualizado a estilo consistente (`placeholder="Buscar en histórico..."`, ancho `260px`).
- Migración funcional en historial de impresoras:
  - `admin_disp/templates/base.html`: reemplazo de render legacy por tablas HTML en `modalPrinterHistory` por 2 grids AG Grid (`printerHistoryGridPrint` y `printerHistoryGridCopy`).
  - Carga lazy de assets AG Grid en base con `ensureAgGridAssets` para evitar dependencia de cada vista.
  - Inicialización y carga de datos por pestaña con `initPrinterHistoryAgGrid`, `_setPrinterHistoryGridData` y `_loadHistoryContent`.
  - Filtro de búsqueda conectado a quick filter de AG Grid con `applyPrinterHistorySearchFilter`.
  - Se eliminó la paginación manual legacy (botones Anterior/Siguiente de tabla HTML) y se usa paginación nativa AG Grid.
- TDD aplicado:
  - `tests/test_printer_history_modal_ui.py`: nuevas pruebas RED para contenedores AG Grid y bootstrap JS.
  - `tests/test_asignaciones_aggrid_migration.py`: prueba de consistencia visual del buscador histórico.
- Validación GREEN:
  - `python -m unittest tests/test_printer_history_modal_ui.py tests/test_asignaciones_aggrid_migration.py tests/test_planes_reclamos_aggrid_migration.py -v` -> 18/18 OK.

## 2026-03-27 (Fixes modales documentos + impresión + auditoría permisos)
- Aplicado flujo TDD RED->GREEN para los 5 ajustes reportados por usuario.
- `admin_disp/templates/base.html`:
  - agregado helper `_bringGlobalModalToFront(modalId)` para forzar que modales globales de confirmación/mensaje queden al frente del stack actual.
  - `openGlobalDeleteModal`, `openGlobalSuccessModal` y `openGlobalMessageModal` ahora invocan `_bringGlobalModalToFront(...)`.
  - ajuste visual en `modalPrinterHistory`: `printerHistorySearchInput` reducido a `220px`.
  - ajuste de columnas AG Grid en pestaña Impresión: `Hora de inicio` más ancha, `Nombre de archivo` más ancha, `Hojas x copias` más compacta.
- `admin_disp/templates/asignaciones.html`: `historicoAsignacionesSearchInput` reducido a `220px`.
- `admin_disp/auth/service.py`: `_format_roles_string` actualizado para aceptar llaves cortas (`dispositivos`, `cxc`, `kardex`) además de llaves largas de BD, corrigiendo auditoría vacía en primera asignación de permisos.
- Tests RED/GREEN:
  - actualizado `tests/test_printer_history_modal_ui.py` con checks de stacking global, ancho de buscador y definición de columnas.
  - actualizado `tests/test_asignaciones_aggrid_migration.py` para ancho compacto del buscador histórico.
  - creado `tests/test_auth_roles_audit_format.py` para validar formateo de auditoría con llaves cortas/largas.
- Validación GREEN:
  - `python -m unittest tests.test_printer_history_modal_ui tests.test_asignaciones_aggrid_migration tests.test_auth_roles_audit_format` -> 15/15 OK.
  - `python -m unittest` -> 39/39 OK.

## 2026-03-27 (Ajuste correctivo Paso 3 - barras de búsqueda)
- Se aplicó corrección adicional por feedback del usuario: el tamaño seguía viéndose grande.
- `admin_disp/templates/base.html`: `printerHistorySearchInput` reducido de forma más agresiva a `width:180px; padding:6px 10px; font-size:0.9rem;`.
- `admin_disp/templates/asignaciones.html`: `historicoAsignacionesSearchInput` ajustado al mismo tamaño compacto.
- Tests actualizados para reflejar el nuevo tamaño objetivo:
  - `tests/test_printer_history_modal_ui.py`
  - `tests/test_asignaciones_aggrid_migration.py`
- Validación:
  - `python -m unittest tests.test_printer_history_modal_ui tests.test_asignaciones_aggrid_migration` -> 13/13 OK.
  - `python -m unittest` -> 39/39 OK.

## 2026-03-27 (Ajuste de ancho modal historial impresoras)
- Ajuste solicitado por usuario para mejorar visibilidad de la columna `Hojas x copias`.
- `admin_disp/templates/base.html`: modal `#modalPrinterHistory` ampliada de `max-width:860px; width:95vw;` a `max-width:980px; width:97vw;`.
- Validación rápida:
  - `python -m unittest tests.test_printer_history_modal_ui` -> 7/7 OK.

## 2026-03-27 (Asignaciones - columna Sucursal)
- Requerimiento implementado: agregar campo `Sucursal` en la tabla principal de la página de Asignaciones (AG Grid).
- Backend actualizado en `admin_disp/devices/routes.py`:
  - `GET /devices/asignaciones`: consulta de empleados ahora incluye `sucursal` y se mapea como `Sucursal` en `empleados_options`.
  - `GET /devices/asignaciones/tbody`: consulta de resumen para refresh AJAX también incluye `sucursal` y se retorna en `resumen_data`.
- Frontend actualizado en `admin_disp/static/js/asignaciones.js`:
  - Nueva columna AG Grid: `Sucursal` (`field: 'Sucursal'`) en la grilla de resumen.
- Pruebas:
  - `tests/test_asignaciones_aggrid_migration.py` actualizado para validar columna `Sucursal` y presencia del mapeo en rutas.
  - `python -m unittest tests.test_asignaciones_aggrid_migration` -> 7/7 OK.
  - `python -m unittest` -> 40/40 OK.

## 2026-03-27 (Dispositivos celulares + reclamos por tipo)
- Requisito 1 implementado en modal de celulares:
  - `admin_disp/devices/service.py`: `list_celulares()` ahora incluye `plan_fecha_fin` y `plan_dias_restantes`.
  - `admin_disp/static/js/dispositivos.js`: agregadas columnas `Fecha fin plan` y `Días restantes` justo después de `Número de Línea`.
- Requisito 2 implementado en modal de celulares:
  - Compactadas columnas `Identificador`, `IMEI`, `Modelo`, `Marca` reduciendo `minWidth/maxWidth/flex`.
- Requisito 3 implementado en reclamos:
  - `admin_disp/templates/reclamos.html`: selector inicial `Tipo de reclamo` (`Robo`/`Daño`), lógica condicional `applyTipoReclamoVisibility()` y campo `Observaciones`.
  - Para `Robo` se exigen `Fecha de incidencia` y `Lugar del reclamo`; para `Daño` se ocultan y no son requeridos.
  - `admin_disp/devices/routes.py`: validación de `tipo_reclamo` y envío de `tipo_reclamo` + `observaciones` al servicio.
  - `admin_disp/devices/service.py`: soporte de columnas opcionales `tipoReclamo` y `observaciones` en list/get/create/update con compatibilidad si la columna aún no existe.
  - Script de migración agregado: `scripts/add_tipo_reclamo_to_reclamo_seguro.sql`.
- Validación:
  - `python -m unittest tests.test_devices_aggrid_migration tests.test_planes_reclamos_aggrid_migration` -> 19/19 OK.
  - `python -m unittest` -> 44/44 OK.

## 2026-03-27 (Correcciones finales modal Reclamos y Celulares)
- Aplicado TDD (RED->GREEN) para feedback del usuario en 3 frentes: visibilidad inicial de modal, headers/formatos en celulares y columna Tipo Reclamo.
- `admin_disp/templates/reclamos.html`:
  - Se agregó `newReclamoFieldsWrap` para ocultar todos los campos (excepto tipo) hasta seleccionar `Robo` o `Daño`.
  - `Empresa`, `Asignación`, `Lugar de la incidencia`, `Estado`, `Observaciones`, `Evidencia` y `Formulario` quedan validados como obligatorios.
  - En `Lugar del reclamo (ciudad)` se agregó opción placeholder `Seleccionar ciudad`.
  - Se añadió columna `Tipo Reclamo` en tabla legacy (fuente AG Grid) con texto `Robo`/`Daño`.
- `admin_disp/static/js/reclamos_aggrid.js`:
  - Parseo actualizado para leer `tipo_reclamo_texto` desde la tabla legacy.
  - Nueva columna AG Grid visible: `Tipo Reclamo`.
- `admin_disp/templates/reclamosTbody.html`: columna `Tipo Reclamo` agregada para refresh AJAX consistente.
- `admin_disp/static/js/dispositivos.js`:
  - Celulares: `Identificador` e `IMEI` ampliados.
  - Header actualizado a `Fecha Fin Plan`.
  - Formato de fecha cambiado a `DD-MM-AAAA`.
  - Header `Días restantes` renombrado a `Restantes`.
- `admin_disp/devices/routes.py`:
  - Validaciones backend reforzadas en creación de reclamo para campos obligatorios por tipo y exigencia de `img_evidencia` + `img_form`.
- Pruebas:
  - RED: pruebas nuevas/modificadas fallaron primero (5 fallos esperados).
  - GREEN: `python -m unittest tests.test_devices_aggrid_migration tests.test_planes_reclamos_aggrid_migration` -> 20/20 OK.
  - Regresión: `python -m unittest` -> 45/45 OK.

## 2026-03-27 (Reclamos - modal Editar con orden de captura y campos visibles)
- Se reestructuró `admin_disp/templates/reclamos.html` en `modalEditReclamo` para reflejar el mismo orden del formulario de alta:
  - Tipo de reclamo
  - Empresa
  - Asignación
  - Fecha de la incidencia (solo Robo)
  - Fecha inicio del reclamo
  - Lugar de la incidencia
  - Lugar del reclamo (solo Robo)
  - Observaciones
  - Estado del proceso
  - Evidencia/Formulario
- Se reemplazaron campos antiguos de edición por campos de solo lectura para contexto histórico (`empresa`, `fecha_incidencia`, `fecha_inicio_reclamo`, `lugar_incidencia`, `lugar_reclamo`) según requerimiento.
- Se actualizó `openEditReclamoModal(id)` para poblar y mostrar/ocultar bloques por tipo (`Robo`/`Daños`) usando `tipoReclamo` retornado por API.
- Se ajustó la validación del botón Guardar para depender solo de la verificación `CONFIRMAR` (antes dependía de `lugar_reclamo` editable).

## 2026-03-27 (Reclamos - corrección final de empresa y campos editables)
- `admin_disp/devices/service.py` (`get_reclamo`): se corrigió la resolución de `empresa` para que siempre se obtenga desde `empleados` usando `fk_id_empleado` de la asignación vinculada al dispositivo.
- `admin_disp/templates/reclamos.html`:
  - Se mantuvo **solo lectura** en `Tipo de reclamo` y `Empresa`.
  - Se habilitó edición en `Fecha de la incidencia`, `Fecha inicio del reclamo`, `Lugar de la incidencia`, `Lugar del reclamo` y `Observaciones`.
  - `Lugar del reclamo` en edición volvió a `select` con catálogo de ciudades, consistente con la creación.
  - Se agregó `editReclamoTipoRaw` para mantener comportamiento por tipo al guardar (Robo/Daños).
  - Se empezó a enviar `observaciones` en `PUT /devices/reclamo/<id>` desde la modal de edición.

  ## 2026-03-27 (Reclamos - archivo único PDF y limpieza de botones)
  - Se unificó el flujo de carga documental de reclamos a un único campo `archivo_reclamo_pdf` (acepta PDF o fotos múltiples para generar PDF).
  - `admin_disp/templates/reclamos.html`: removidos los campos separados de Evidencia/Formulario y eliminados los botones `Ver evidencia`, `Ver formulario` y `Ver ambas`.
  - `admin_disp/devices/routes.py`: `POST/PUT` de reclamos ahora procesan `request.files.getlist('archivo_reclamo_pdf')` y endpoint único `GET /devices/reclamo/<id>/documento`.
  - `admin_disp/devices/service.py`: persistencia/actualización migrada a columna `archivo_reclamo_pdf` con validación explícita de existencia de columna.
  - Script agregado: `scripts/add_archivo_reclamo_pdf_to_reclamo_seguro.sql`.
  - Pruebas: `python -m unittest tests.test_planes_reclamos_aggrid_migration tests.test_devices_aggrid_migration` -> 20/20 OK.
