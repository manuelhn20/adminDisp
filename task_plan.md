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
