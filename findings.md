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
