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
