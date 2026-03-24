@echo off
REM Script para ejecutar la aplicación en el servidor (servicio sin pausa)

REM Cambiar al directorio de la aplicación
cd /d "%~dp0"

REM Activar entorno virtual
call .venv\Scripts\activate.bat

REM Configurar variables de entorno
set FLASK_DEBUG=0
set APP_HOST=0.0.0.0
set APP_PORT=8000

REM Ejecutar la aplicación usando el Python del entorno virtual explícitamente
"%~dp0.venv\Scripts\python.exe" "%~dp0app.py"
