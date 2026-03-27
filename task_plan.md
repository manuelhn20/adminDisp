# Task Plan

## Goal
Actualizar el manejo de nombres de archivos para que funcione con el nuevo marcador CORRELATIVO en lugar de ######, manteniendo compatibilidad retroactiva.

## Secondary Goal
Agregar configuración de despliegue en contenedor con dependencias ODBC de Linux para corregir ImportError de pyodbc (libodbc.so.2).

## Phases
- [complete] 1. Investigación de raíz y puntos de impacto
- [complete] 2. Escribir pruebas que fallen con CORRELATIVO
- [complete] 3. Implementar correcciones mínimas
- [complete] 4. Verificación y resumen

## Errors Encountered
- Ninguno aún.

## Security Remediation (2026-03-25)
- [complete] 5. Auditar ubicaciones reportadas en issues.md
- [complete] 6. Remediar SQL dinámico con parametrización y armado seguro
- [complete] 7. Validar que no queden patrones SQL f-string en módulos afectados
- [complete] 8. Remediar XSS en contexto JS de plantillas (tojson)
- [complete] 9. Endurecer sinks HTML en JS legacy y sanitización global
- [complete] 10. Reducir concatenación SQL no necesaria en inventario/kardex

## ORM Incremental (2026-03-25)
- [complete] 11. Agregar soporte SQLAlchemy Core en capa DB
- [complete] 12. Migrar módulo inventario/service.py a SQLAlchemy Core
- [complete] 13. Validar compilación y dependencias de la migración
- [complete] 14. Agregar engine SQLAlchemy Core para base kardex
- [complete] 15. Migrar módulo kardex/db.py a SQLAlchemy Core
- [complete] 16. Validar compilación de migración kardex
- [complete] 17. Migrar cxc/operations.py a SQLAlchemy Core
- [complete] 18. Migrar devices/service.py por secciones críticas a SQLAlchemy Core
- [complete] 19. Migrar módulos restantes con cursor directo (auth y routes críticas)
- [complete] 20. Iniciar migración devices/service.py (helpers SQLAlchemy y lecturas base)
- [complete] 21. Migrar lecturas de componentes/periféricos/marcas/modelos en devices/service.py
- [complete] 22. Migrar create/update/delete de componente en devices/service.py
- [complete] 23. Migrar escrituras de marca/modelo en devices/service.py
- [complete] 24. Corregir render malformado de tabla Devices tras editar/guardar
- [complete] 25. Completar migración final de conexiones legacy a capa SQLAlchemy compat
- [complete] 26. Reparar corrupción de codificación (mojibake/BOM) y revalidar tests ORM
- [complete] 27. Corregir bloqueo de Continuar en modal de documentos de Asignaciones
- [complete] 28. Revertir liquidación LIQ-00026 y restaurar cobros asociados
- [complete] 29. Corregir AG Grid de Kardex Productos y modales de gestión
- [complete] 30. Migrar Devices fase 1 a AG Grid (activos + modales de eliminados/celulares)
- [complete] 31. Corregir visibilidad AG Grid y layout de modales en Devices
- [complete] 32. Ajustar UX AG Grid Devices (tema negro, selección/copia y acciones)
- [complete] 33. Remover checkboxes de selección de filas, mantener text selection
- [complete] 34. Corregir colores en campo Estado de grilla celulares
- [complete] 35. Aumentar tamaño modal celulares y visibilidad campo Nombre
- [complete] 36. Ajustar ancho modal eliminados y campos Observaciones/Acciones
- [complete] 37. Compactar columnas Modelo/Marca/IP y botón Acciones
- [complete] 38. Migrar Asignaciones a AG Grid (principal, transfer, histórico modal + búsqueda)
- [complete] 39. Corregir tema AG Grid en Asignaciones (fondo negro como Devices)
- [complete] 40. Actualizar selección AG Grid deprecada y autoaltura (max 6 filas)

## Planes/Reclamos AG Grid (2026-03-26)
- [complete] 41. Crear pruebas RED para migración AG Grid de Planes y Reclamos
- [complete] 42. Implementar AG Grid en Planes manteniendo compatibilidad con flujos legacy
- [complete] 43. Implementar AG Grid en Reclamos manteniendo compatibilidad con flujos legacy
- [complete] 44. Validar GREEN en pruebas y ausencia de errores de sintaxis
- [complete] 45. Migrar Historico de Planes a modal AG Grid con buscador dedicado
- [complete] 46. Corregir Reclamos AG Grid en modo oscuro (tema negro consistente)
- [complete] 47. Aplicar switch global de AG Grid por tema (oscuro/claro)
- [complete] 48. Unificar modales AG Grid de Dispositivos con patrón Kardex (search + sin footer cerrar)
- [complete] 49. Completar implementación faltante en histórico planes/asignaciones y modalPrinterHistory
- [complete] 50. Migrar historial de impresoras a AG Grid y homogeneizar buscador de histórico asignaciones
- [complete] 51. Corregir stacking de confirmaciones (regenerar/confirmar documentos), ajustar anchos de impresión/search y reparar auditoría de permisos iniciales
- [complete] 52. Extender modal celulares con fin de plan/días restantes y crear flujo condicional de reclamos por tipo (Robo/Daño)
- [complete] 53. Ajustar reglas finales de reclamos y headers de celulares según feedback (tipo obligatorio, ciudad placeholder, columna Tipo Reclamo)
- [complete] 54. Reestructurar modal Editar Reclamo para mostrar campos capturados en orden de alta (Robo/Daño) con solo lectura en campos de contexto
- [complete] 55. Corregir Editar Reclamo: empresa desde empleado asignado y habilitar edición de todos los campos excepto tipo/empresa
- [complete] 56. Unificar Reclamos a archivo único PDF (fotos o PDF) en nueva columna `archivo_reclamo_pdf`
