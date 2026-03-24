import os
import sys

# Auto-bootstrap: si no estamos corriendo con el Python del venv, re-ejecutar con el correcto.
# Funciona con ruta relativa al directorio del script, en cualquier maquina.
_here = os.path.dirname(os.path.abspath(__file__))
_venv_python = os.path.join(
    _here, '.venv', 'Scripts' if sys.platform == 'win32' else 'bin', 'python.exe' if sys.platform == 'win32' else 'python'
)
if os.path.exists(_venv_python) and os.path.abspath(sys.executable) != os.path.abspath(_venv_python):
    os.execv(_venv_python, [_venv_python] + sys.argv)

from admin_disp.app import create_app

app = create_app()

if __name__ == '__main__':
    host = os.getenv('APP_HOST', '0.0.0.0')
    port = int(os.getenv('APP_PORT', '8000'))
    debug = os.getenv('FLASK_DEBUG', '0').lower() in ('1', 'true', 'yes')
    app.run(host=host, port=port, debug=debug)
