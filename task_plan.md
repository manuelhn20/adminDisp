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
