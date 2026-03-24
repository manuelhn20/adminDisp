@echo off
REM ==========================================================
REM  start.bat  -  Arranque automatico de PROIMA Admin Disp
REM  Uso: simplemente doble-clic o ejecutar desde cmd/PowerShell
REM
REM  Que hace este script:
REM   1. Verifica si Python 3.12 esta instalado
REM   2. Crea el venv (.venv) si no existe
REM   3. Instala/actualiza dependencias desde requirements.txt
REM   4. Levanta la aplicacion
REM ==========================================================

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo  ============================
echo   PROIMA - Admin Dispositivos
echo  ============================
echo.

REM --------------- 1. Buscar Python -------------------------
set PYTHON_EXE=

REM Intentar con 'py -3.12' (Python Launcher para Windows)
py -3.12 --version >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_EXE=py -3.12
    goto :FOUND_PYTHON
)

REM Intentar con 'python' del PATH
python --version >nul 2>&1
if %errorlevel%==0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
    echo  Python detectado: !PY_VER!
    set PYTHON_EXE=python
    goto :FOUND_PYTHON
)

REM Intentar con python3
python3 --version >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_EXE=python3
    goto :FOUND_PYTHON
)

echo  [ERROR] No se encontro Python en el sistema.
echo  Descarga Python 3.12 desde https://www.python.org/downloads/
echo  Asegurate de marcar "Add Python to PATH" durante la instalacion.
echo.
pause
exit /b 1

:FOUND_PYTHON
echo  Python encontrado: %PYTHON_EXE%

REM --------------- 2. Crear venv si no existe ---------------
if not exist ".venv\Scripts\python.exe" (
    echo  Creando entorno virtual...
    %PYTHON_EXE% -m venv .venv
    if %errorlevel% neq 0 (
        echo  [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo  Entorno virtual creado.
) else (
    echo  Entorno virtual existente encontrado.
)

REM --------------- 3. Instalar dependencias -----------------
echo  Verificando dependencias...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo  [ERROR] Fallo la instalacion de dependencias.
    echo  Revisa requirements.txt o tu conexion a internet.
    pause
    exit /b 1
)
echo  Dependencias OK.

REM --------------- 3b. Instalar navegadores Playwright ------
echo  Configurando Playwright (descarga navegadores)...
.venv\Scripts\python.exe -m playwright install 
if %errorlevel% neq 0 (
    echo  [WARNING] Fallo la instalacion de Playwright. Continuando...
)
echo  Playwright OK.

REM --------------- 4. Levantar app --------------------------
echo.
echo  Iniciando servidor en http://0.0.0.0:8000 ...
echo  (Ctrl+C para detener)
echo.
set FLASK_DEBUG=0
set APP_HOST=0.0.0.0
set APP_PORT=8000
.venv\Scripts\python.exe app.py

pause
