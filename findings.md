# Findings

- Se detectó uso de correlativos en módulo devices.
- Hay referencias literales a ###### que parecen placeholders de plantillas de nombre.
- Los archivos reales en admin_disp/form usan CORRELATIVO; por eso select_template devolvía rutas inexistentes.
- El impacto principal está en admin_disp/services/docexp.py y un flujo legacy en admin_disp/devices/pdf_service.py.
- El error de deploy actual no es de Flask ni rutas: pyodbc falla al cargar porque falta libodbc.so.2 en contenedor Linux.
- Se requiere instalar unixodbc + msodbcsql18 en build image para que admin_disp/core/db.py pueda importar pyodbc.
