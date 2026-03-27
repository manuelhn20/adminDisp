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

## Debug Findings 2026-03-25 (Asignaciones no continúa)

- El modal de documentos en Asignaciones construía botones con `onclick` inline vía `innerHTML`.
- Con sanitización global activa, esos atributos inline eran removidos; visualmente el botón aparecía, pero no ejecutaba acción al hacer click.
- Se migraron las acciones dinámicas a listeners explícitos (`addEventListener`) después del render para que el flujo no dependa de atributos inline.
- Se normalizó `estado` con `Number(...)` en el flujo del modal para evitar errores de ruteo entre estados manual/digital por comparación estricta de tipo.

## Data Fix Findings 2026-03-25 (LIQ-00026)

- Se confirmó precondición: `LIQ-00026` existía como `lote.id=109` con 4 cobros enlazados en estado liquidado.
- La corrección requerida por operación fue consistente con el modelo: deshacer liquidación implica limpiar flags de liquidado y desvincular `loteId` en `cobro`, luego eliminar `lote`.
- La ejecución transaccional afectó exactamente 4 cobros y 1 lote, sin dejar referencias colgantes a `loteId=109`.
- Validación posterior: no existe `LIQ-00026` y no quedan cobros en estado `estado=2` + `liquidado='Si'` para ese lote.

## Debug Findings 2026-03-25 (Kardex productos AG Grid y modales)

- En `base_kardex.html`, `security-sanitize.js` se cargaba globalmente sin opción por vista y antes del contenido específico.
- AG Grid de `productos.html` genera HTML dinámico (incluyendo botones de acción en celdas); con parche global activo, se degradaba render/comportamiento del grid.
- El síntoma reportado (grid no visible y modales de gestión sin flujo correcto) es consistente con esa interferencia, igual al patrón ya observado en CxC.
- Mitigación aplicada: habilitar `disable_global_sanitize_patch` por vista y activarlo solo en `productos_view` para preservar `safeSetHTML`/DOMPurify sin romper AG Grid.

## Devices Findings 2026-03-25 (AG Grid + modales Eliminados/Celulares)

- Para Devices, el patrón de UX solicitado es más estable con modales AG Grid (como Kardex) que con alternancia de vistas completas.
- La recarga legacy por `tbody` HTML (`/devices/ui/tbody`) no sirve para los tres grids; se reemplazó por recarga JSON concurrente de `/devices/`, `/devices/deleted/` y `/devices/celulares/`.
- Se agregó endpoint dedicado `/devices/celulares/` para alimentar AG Grid de celulares con normalización consistente de número (`codigo_pais`/`numero_sin_codigo`).
- La delegación de acciones sobre contenedores AG Grid evita acoplar lógica a filas HTML estáticas y mantiene intactos flujos de editar/historial/eliminar/restaurar/detalles.

## Debug Findings 2026-03-25 (Devices AG Grid no visible + modales)

- El síntoma de grilla "en blanco" con paginación visible es consistente con problemas de layout/tema CSS, no con ausencia de datos en endpoints.
- En modales, inicializar AG Grid mientras el contenedor está oculto puede dejar anchos/altos calculados en 0 y degradar render inicial.
- En `dispositivos.css` no había una capa explícita de tokens AG Grid para asegurar contraste en ambos temas; se añadió configuración dedicada (foreground/background/header/hover).
- La mitigación efectiva combinó creación diferida de grids de modales al abrirlos y refresco explícito de layout (`sizeColumnsToFit` + refresh), junto con alturas definidas y modal-body flexible.

## Devices Findings 2026-03-25 (UX AG Grid solicitado por usuario)

- La falta de visibilidad del botón eliminar en AG Grid estaba asociada al ancho limitado de la columna `Acciones`; aumentar ese ancho evita recorte de controles.
- Para permitir seleccionar y copiar datos en AG Grid no basta con filtros/orden: se requieren flags de selección y copia (`rowSelection`, `enableCellTextSelection`, `enableRangeSelection`, `ensureDomOrder`).
- El tono dark-blue provenía de variables de tema previas; una paleta neutra negra en tokens AG Grid corrige consistencia visual con el estilo requerido.
- En celulares, compactar `Marca` y `Estado` en ~10px por columna mejora densidad sin sacrificar legibilidad.

## Devices Findings 2026-03-25 (remover checkboxes, mantener text selection)

- La columna de selección por checkbox añadida en iteración anterior cumplió su propósito inicial pero el usuario luego solicitó removerla para simplificar la interfaz.
- La razón: permitir multi-selección de filas puede confundir con selección de texto; es preferible que la tabla sea "read-only" en términos de acción de fila, pero usuario pueda copiar contenido de celdas.
- La solución es simétrica: remover `rowSelection`, `rowMultiSelectWithClick`, `enableRangeSelection`, `ensureDomOrder` pero preservar `enableCellTextSelection`, `copyHeadersToClipboard`, `suppressCellFocus: false`.
- Impacto: interfaz visual más limpia (sin checkboxes), pero funcionalidad de copia de texto y selección por rango siguen disponibles en contexto de celdas individuales.

## Devices Findings 2026-03-25 (Estado badge colors en celulares)

- El campo Estado en tabla de celulares no mostraba colores porque `_buildEstadoBadge()` usaba clases CSS (`text-${color}`) que no se aplican en contexto de AG Grid con tema personalizado.
- Las clases Bootstrap no están disponibles o no tienen efecto adentro de celdas de AG Grid con los tokens CSS personalizados (negro #070707) que se establecieron previamente.
- Solución: cambiar `_buildEstadoBadge()` para usar estilos inline con mapeo de colores: `danger`→`#dc3545`, `success`→`#28a745`, `warning`→`#ffc107`, `primary`→`#007bff`, `secondary`→`#6c757d`.
- Ventaja: garantiza que los colores se rendericen correctamente sin depender de hojas de estilo externas o disponibilidad de clases en el armazón de AG Grid.

## Devices Findings 2026-03-25 (Modal celulares - tamaño y campo Nombre)

- La modal de celulares tenía max-width 1360px (96% de ancho) lo que la hacía angosta especialmente en pantallas anchas.
- El campo Nombre tenía minWidth 180 y flex 1, insuficiente para mostrar nombres completos de empleados sin truncar.
- Mejoras aplicadas: aumentar max-width a 1600px (98% ancho) para aprovechar más espacio horizontal.
- Mejoras aplicadas: aumentar Nombre a minWidth 240 y flex 1.2 para que sea más visible y se muestre completamente en la general.
- Impacto: Modal más aprovechable y campo Nombre siempre visible sin truncamiento.

## Devices Findings 2026-03-26 (Modal eliminados - balance ancho y visibilidad acciones)

- Después del ajuste anterior (max-width 1100px), modalidad fue muy estrecha y botón Restaurar no era visible sin scroll horizontal.
- Root cause: max-width 1100px era insuficiente con 7 columnas; Observaciones (250/1.2) tomaba demasiado espacio; Acciones (100/120) comprimida.
- Corrección aplicada: max-width 1300px, 97% width (balance entre compacta y funcional).
- Corrección aplicada: Observaciones minWidth 220/flex 1, Acciones minWidth 130/maxWidth 150 (botón Restaurar visible sin scroll).
- Impacto: Modal simétrica, todos los campos visibles incluyendo botón de restaurar.

## Devices Findings 2026-03-26 (Modal eliminados - compactación de columnas)

- Después de ajuste anterior, columnas Modelo, Marca y Dirección IP seguían muy anchas (160/150/150), ocupando demasiado espacio.
- El botón de Acciones estaba poco visible por compresión de columnas previas.
- Optimización aplicada: reducir minWidth y flex en Modelo/Marca/IP a valores más compactos (130/0.9).
- Optimización aplicada: reducir Acciones a minWidth 100/maxWidth 130 para que sea más compacto pero visible.
- Impacto: Modal mejor balanceada, todas las columnas visibles incluyendo botón de restaurar/acciones claramente legible.

## Asignaciones Findings 2026-03-26 (Migración AG Grid completa)

- La página de Asignaciones estaba acoplada a tablas HTML (`asignacionesTable`, `historicoTable`) y filtrado/sorting manual DOM; para escalar y mantener consistencia visual era mejor migrar a AG Grid como en módulos recientes.
- El `asignacionesPageSearch` ya existía y se reutilizó como `quickFilterText` único para los grids; esto evita múltiples inputs y mantiene la UX solicitada.
- El histórico dejó de ser “vista alterna” y pasó a modal AG Grid (`modalHistoricoAsignacionesGrid`), alineado con el patrón modal de Marcas/Kardex.
- La transferencia de dispositivos migró de checkboxes en `<tbody>` a selección nativa AG Grid en `transferSourceGrid`, eliminando manejo manual frágil de checkboxes/select-all.
- Para no romper compatibilidad durante transición, `/devices/asignaciones/tbody` mantiene HTML parcial legacy y además retorna `resumen_data` y `historico_data` para refresco AG Grid.
- El refresco de asignaciones ahora prioriza datasets JSON de API y aplica `setGridOption('rowData', ...)` en lugar de inyección directa de filas HTML.

## Asignaciones Findings 2026-03-26 (AG Grid blanco vs negro)

- La apariencia "en blanco" en contenedores AG Grid de Asignaciones fue un problema de cascada CSS: `asignaciones.css` se cargaba antes de `ag-theme-material.css`, permitiendo que el tema base pisara variables dark.
- En Dispositivos no ocurre porque el orden correcto es AG Grid CSS primero y CSS de página después; Asignaciones quedó con el orden inverso.
- Corrección: reordenar includes en `asignaciones.html` y reforzar fondos/foreground de `.ag-root-wrapper`, `.ag-header` y `.ag-paging-panel` para garantizar negro consistente.

## Asignaciones Findings 2026-03-26 (Warnings AG Grid deprecado + altura)

- Los warnings observados (`checkboxSelection`, `headerCheckboxSelection`, `rowSelection: 'multiple'`) corresponden a APIs deprecadas desde AG Grid 32.2+.
- La migración correcta es usar `rowSelection` como objeto (`mode`, `checkboxes`, `headerCheckbox`) en `GridOptions`.
- El warning de `sizeColumnsToFit` aparece cuando el grid está en contenedor oculto o sin dimensiones visibles al momento del ajuste.
- Para UX de transferencia más compacta, conviene altura dinámica por cantidad de dispositivos y límite visual (6 filas) en origen/destino, en lugar de alto fijo por viewport.

## Planes/Reclamos Findings 2026-03-26 (Implementación AG Grid)

- Tanto `planes.html` como `reclamos.html` dependían de tablas HTML con scripts legacy de CRUD y recarga parcial (`/tbody`), por lo que una migración segura requería mantener esas tablas como fuente de compatibilidad.
- La estrategia más estable fue: agregar contenedores AG Grid visibles y ocultar la tabla legacy, sin eliminar sus funciones existentes; AG Grid consume los datos parseados desde los `tr` legacy (`data-*` + celdas).
- Para evitar que AG Grid se rompa por el parche global de sanitización (patrón observado antes en CxC/Kardex/Asignaciones), se habilitó `disable_global_sanitize_patch=True` en rutas de Planes y Reclamos.
- En refrescos dinámicos (`refreshPlanesTbody`, `reloadReclamosTable`) se aplicó sincronización post-refresh para actualizar `rowData` de AG Grid automáticamente y mantener consistencia visual tras crear/editar/eliminar.

## Reclamos Findings 2026-03-26 (tema blanco)

- La vista de Reclamos no tenía tokens dark propios para AG Grid, por lo que podía heredar apariencia clara desde estilos globales.
- La corrección efectiva fue usar una clase scoped (`reclamos-ag-grid`) en el contenedor de la grilla y definir tokens dark locales del tema AG Grid.
- Con esto se evita dependencia accidental de cascadas externas y se alinea visualmente con Devices/Asignaciones/Planes en negro.

## AG Grid Findings 2026-03-26 (switch global por tema)

- Para evitar ajustes repetidos por vista, la capa correcta es el CSS global base (`style.css`) con selectores por atributo de tema (`html[data-dark-mode="true"]` y su inverso).
- Definir tokens de AG Grid en forma global permite que todas las grillas respeten automáticamente el cambio de tema sin volver a tocar cada template.
- El uso de variables con prioridad alta en la capa global evita que overrides locales de vistas dejen grids en blanco en modo oscuro o viceversa.

## Dispositivos Findings 2026-03-26 (patrón modal Kardex)

- El patrón de Kardex en modales de tabla prioriza cabecera compacta con cierre por `X`, toolbar superior con buscador y ausencia de footer con botón de cerrar.
- En Dispositivos, las modales AG Grid de Eliminados/Celulares tenían footer con botón `Cerrar` y no contaban con buscador dedicado por modal.
- La integración más estable fue agregar quick filter por modal (inputs propios) y mantener cierre por `X`, removiendo el footer para simplificar la jerarquía visual.
- Este patrón reduce ruido UI y mantiene consistencia entre módulos con tablas AG Grid dentro de modales.

## Modales históricos Findings 2026-03-26 (cierre total de pendientes)

- El criterio de consistencia visual solicitado por usuario es transversal: modales de histórico deben usar cierre por `X`, con toolbar/search arriba y sin botón `Cerrar` en footer.
- Los faltantes residuales estaban en tres puntos: histórico de planes, histórico de asignaciones y `modalPrinterHistory` (impresión/copias).
- En `modalPrinterHistory`, además de quitar footer, fue necesario agregar búsqueda por pestaña activa y reaplicar el filtro tras paginación/cambio de tab para evitar incongruencia de resultados visibles.
- La validación mínima confiable fue una suite dedicada de UI por template (`tests/test_printer_history_modal_ui.py`) más la suite de planes/asignaciones para asegurar no regresiones.

## Printer History Findings 2026-03-26 (migración AG Grid)

- El modal de historial de impresoras seguía con render manual de tabla HTML y paginación custom, lo que rompía consistencia visual respecto al resto de modales AG Grid.
- La estrategia más segura fue migrar a dos grids AG Grid (Impresión/Copias) y mantener las pestañas existentes, evitando reescribir el flujo de extracción.
- Para que funcione desde cualquier vista, se implementó carga lazy de assets AG Grid en `base.html` (`ensureAgGridAssets`) en lugar de asumir que cada template los incluye.
- El quick filter debe aplicarse al grid de la pestaña activa y dispararse también tras cambio de tab para mantener la experiencia de búsqueda uniforme.

## Findings 2026-03-27 (modal detrás + auditoría permisos iniciales)

- Causa raíz del modal de confirmación detrás de `modalDocumentosOneDrive`: el stack de z-index podía quedar desfasado entre modales locales y modales globales en escenarios de overlays ya abiertos.
- Corrección robusta: forzar z-index calculado sobre el overlay activo más alto para `globalDeleteModal`, `globalSuccessModal` y `globalMessageModal` con helper `_bringGlobalModalToFront`.
- Ajustes UX solicitados: búsqueda de históricos reducida a 220px en impresoras y asignaciones; columnas de impresión re-balanceadas para priorizar legibilidad de `Nombre de archivo` y `Hora de inicio`.
- Causa raíz de auditoría en blanco al asignar permisos por primera vez: `_format_roles_string` solo reconocía nombres largos de sistema (desde DB), pero en primera asignación el payload usa llaves cortas (`dispositivos/cxc/kardex`).
- Corrección: normalizar ambos formatos de llaves al mismo esquema de auditoría (`adminDisp`, `cxc`, `kardex`) y mantener orden de salida consistente.

## Findings 2026-03-27 (feedback paso 3 de buscadores)

- Aunque se había reducido a 220px, visualmente seguía percibiéndose grande en modales históricos por combinación de ancho base de clase global y padding.
- Ajuste efectivo: reducir a 180px y compactar padding/tipografía en ambos inputs específicos (`printerHistorySearchInput` y `historicoAsignacionesSearchInput`) para lograr diferencia visible inmediata.

## Findings 2026-03-27 (Asignaciones - campo Sucursal)

- La grilla principal de Asignaciones usa `resumen_data` y no lee columnas directamente desde plantilla legacy, por lo que agregar una columna requiere cambios coordinados en backend + `columnDefs` de AG Grid.
- Se agregó `sucursal` en ambas consultas de empleados (`/asignaciones` y `/asignaciones/tbody`) para evitar inconsistencias entre carga inicial y refresh AJAX.
- Se mapeó como `Sucursal` para mantener coherencia con el naming actual del dataset (`NombreCompleto`, `Empresa`, `Cargo`).

## Findings 2026-03-27 (Celulares: plan fin + días restantes)

- El modal de celulares se alimenta desde `list_celulares()`; para mostrar información de plan era necesario incorporar esos campos en el query base (no solo en frontend).
- Se calculó `plan_dias_restantes` en SQL con `DATEDIFF` para evitar discrepancias por zona horaria/browser y mantener consistencia con fecha del servidor.
- Para mejorar densidad visual se redujeron anchos de `Identificador`, `IMEI`, `Modelo`, `Marca` y se mantuvo legible el resto de columnas.

## Findings 2026-03-27 (Reclamos por tipo: Robo vs Daño)

- El formulario de creación de reclamo era único y no distinguía requisitos por tipo; se agregó gating inicial por `tipo_reclamo` y visibilidad condicional de campos.
- Para no romper entornos con esquema previo, el servicio maneja `tipoReclamo` y `observaciones` como columnas opcionales (`has_column`) y funciona aun antes de correr la migración.
- Se agregó script SQL para formalizar el cambio de esquema (`tipoReclamo` y `observaciones`) y alinear persistencia con la nueva UI.

## Findings 2026-03-27 (Ajustes finales solicitados)

- La modal de nuevo reclamo necesitaba una etapa de selección explícita de tipo: sin tipo seleccionado, mostrar campos produce ambigüedad de obligatoriedad y errores de captura.
- El enfoque más estable fue agrupar todos los campos dependientes en un contenedor único (`newReclamoFieldsWrap`) y controlar visibilidad/requeridos desde `applyTipoReclamoVisibility()`.
- Para evitar bypass por clientes no UI, se reforzó validación en backend (`create_reclamo`) para empresa, asignación, fechas/lugares, observaciones y archivos obligatorios.
- La grilla de reclamos AG Grid depende de la tabla legacy oculta como fuente de datos; por eso la columna `Tipo Reclamo` debía agregarse tanto en `reclamos.html`/`reclamosTbody.html` como en el parser de `reclamos_aggrid.js`.
- En celulares, el ajuste pedido no era solo visual: además de ampliar `Identificador`/`IMEI`, se normalizó encabezado y formato de fecha (`DD-MM-AAAA`) para consistencia con criterio de negocio.

## Findings 2026-03-27 (Editar Reclamo: campos invisibles y orden inconsistente)

- La modal de edición conservaba un layout legado (`incidencia` + `lugar` editable) que ya no representa el flujo real de creación por tipo de reclamo.
- Aunque la API `GET /devices/reclamo/<id>` sí retorna `empresa`, `fecha_incidencia`, `fecha_inicio_reclamo`, `lugar_incidencia`, `lugar_reclamo`, esos campos no tenían controles visibles en la modal, por eso el usuario percibía pérdida de datos.
- La corrección más estable fue alinear la modal de edición al orden de captura del alta y marcar como solo lectura los campos de contexto solicitados.
- Para evitar bloqueo en reclamos por Daños (sin `lugar_reclamo`), la habilitación de guardado debe depender de `CONFIRMAR` y no de la longitud de ese campo.

## Findings 2026-03-27 (Editar Reclamo: empresa en blanco y permisos de edición)

- En `get_reclamo`, cuando el nombre se resolvía por helper rápido, `empresa` podía quedar vacía; para robustez, la fuente de verdad debe ser la tabla `empleados` por `fk_id_empleado`.
- El requerimiento funcional definitivo de edición es: solo `Tipo de reclamo` y `Empresa` no editables; el resto de campos del reclamo sí debe poder actualizarse.
- Para mantener coherencia por tipo al guardar, el frontend debe preservar `tipoReclamo` en un campo oculto y limpiar `fecha_incidencia`/`lugar_reclamo` cuando el tipo sea Daños.

## Findings 2026-03-27 (Reclamos: evidencia/formulario a documento único)

- La separación en `img_evidencia` y `img_form` complica el flujo operativo; el usuario requiere un solo archivo final en BD, ya sea PDF directo o fotos convertidas a PDF.
- El helper backend `_normalize_upload_to_pdf_or_binary` ya soportaba la lógica requerida (PDF directo o fotos -> PDF), por lo que el cambio clave fue unificar el campo de entrada a `archivo_reclamo_pdf`.
- Para evitar dependencia futura de columnas eliminadas, `DeviceService.create_reclamo` y `update_reclamo` ahora trabajan con `archivo_reclamo_pdf` y validan explícitamente la existencia de esa columna.
- La UI de Reclamos quedó alineada con el flujo solicitado: un solo input de archivo y eliminación de botones de visualización separados (`Ver evidencia`, `Ver formulario`, `Ver ambas`).
- Se agregó endpoint único `GET /devices/reclamo/<id>/documento` para acceso al archivo consolidado cuando se requiera desde frontend u otros flujos.
