from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash, session, send_file, current_app, make_response
from ..common.rbac import require_roles
from .service import DeviceService
from ..auth.service import AuthService, remap_estado_empleado
from datetime import datetime
import logging
from ..core.db import get_db_empleados, get_db_main
from .document_utils import has_correlativo_in_filename, filter_documents_by_correlativos
import os
import base64
import time
import shutil
from werkzeug.utils import secure_filename
import zipfile
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
onedrive_logger = logging.getLogger('admin_disp.onedrive')

# Logger específico para generación de documentos
gendocu_logger = logging.getLogger('admin_disp.gendocu')
gendocu_logger.setLevel(logging.DEBUG)
gendocu_logger.propagate = False  # No propagar a otros loggers

# Logger específico para asignaciones
asignaciones_logger = logging.getLogger('admin_disp.asignaciones')
asignaciones_logger.setLevel(logging.DEBUG)
asignaciones_logger.propagate = False

# Ensure errors from the devices package are persisted to logs/dispositivos.log
try:
    from pathlib import Path
    base_dir = Path(__file__).parent.parent.parent
    log_dir = base_dir / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configurar gendocu.log
    gendocu_file = str(log_dir / 'gendocu.log')
    if not any(getattr(h, 'baseFilename', None) == gendocu_file for h in gendocu_logger.handlers):
        gendocu_handler = logging.FileHandler(gendocu_file, encoding='utf-8')
        gendocu_handler.setLevel(logging.DEBUG)
        gendocu_fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        gendocu_handler.setFormatter(gendocu_fmt)
        gendocu_logger.addHandler(gendocu_handler)
    
    # Configurar asignaciones.log
    asignaciones_file = str(log_dir / 'asignaciones.log')
    if not any(getattr(h, 'baseFilename', None) == asignaciones_file for h in asignaciones_logger.handlers):
        asignaciones_handler = logging.FileHandler(asignaciones_file, encoding='utf-8')
        asignaciones_handler.setLevel(logging.DEBUG)
        asignaciones_fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        asignaciones_handler.setFormatter(asignaciones_fmt)
        asignaciones_logger.addHandler(asignaciones_handler)
    
    log_file = str(log_dir / 'dispositivos.log')
    parent_logger = logging.getLogger('admin_disp')
    # Create FileHandler only once
    if not any(getattr(h, 'baseFilename', None) == log_file for h in parent_logger.handlers):
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(logging.ERROR)
        fmt = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(fmt)
        parent_logger.addHandler(fh)
        # ensure parent logger doesn't ignore lower levels so exceptions propagate
        parent_logger.setLevel(logging.DEBUG)
except Exception:
    # If logging setup fails, fall back silently; app will still use default logging
    pass


# Helper: append concise messages to logs/asignaciones.log for assignment flow tracing
def _write_asignaciones_log(message: str, level: str = 'INFO'):
    try:
        from datetime import datetime as _dt
        base_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
        logs_dir = os.path.join(base_dir, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        log_path = os.path.join(logs_dir, 'asignaciones.log')
        ts = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as _f:
            _f.write(f"{ts} [{level}] {message}\n")
    except Exception:
        logger.exception('No se pudo escribir en logs/asignaciones.log')

# Códigos de país más comunes (orden por longitud descendente para evitar conflictos)
COUNTRY_CODES = ['886', '880', '878', '855', '852', '850', '840', '838', '836', '834', '833', '832', '831', '830', '685', '683', '681', '679', '678', '677', '676', '675', '674', '673', '672', '670', '668', '666', '665', '664', '663', '662', '661', '660', '658', '657', '656', '655', '654', '653', '652', '651', '850', '504', '503', '502', '501', '500', '423', '421', '420', '389', '387', '386', '385', '383', '382', '381', '380', '379', '378', '376', '375', '374', '373', '372', '371', '370', '359', '358', '357', '356', '355', '354', '353', '352', '351', '350', '39', '36', '34', '33', '32', '31', '30', '299', '298', '297', '291', '290', '269', '268', '267', '266', '265', '264', '263', '262', '261', '260', '258', '257', '256', '255', '254', '253', '252', '251', '250', '249', '248', '246', '245', '244', '243', '242', '241', '240', '239', '238', '237', '236', '235', '234', '233', '232', '231', '230', '229', '228', '227', '226', '225', '224', '223', '222', '221', '220', '218', '216', '212', '211', '1', '44', '45', '46', '47', '48', '49', '55', '56', '57', '58', '60', '61', '62', '63', '64', '65', '66', '81', '82', '84', '86', '90', '92', '93', '94', '95', '98']

def extract_country_code_and_number(numero_linea):
    """
    Detecta el código de país del número de línea y lo separa.
    Retorna: (codigo_pais, numero_sin_codigo)
    
    Soporta formatos:
    - "39 87654321" (con espacio)
    - "3987654321" (sin espacio)
    """
    if not numero_linea:
        return None, ''
    
    # Si ya tiene espacio, simplemente dividir
    if ' ' in numero_linea:
        parts = numero_linea.strip().split()
        if len(parts) == 2:
            return parts[0], parts[1]
    
    # Si no tiene espacio, limpiar y buscar
    numero_limpio = numero_linea.replace(' ', '').strip()
    if not numero_limpio.isdigit():
        return None, numero_linea
    
    # Intentar coincidir con códigos conocidos (en orden por longitud)
    for code in sorted(COUNTRY_CODES, key=len, reverse=True):
        if numero_limpio.startswith(code):
            return code, numero_limpio[len(code):]
    
    # Si no coincide, asumir que los primeros 3 dígitos son el código
    if len(numero_limpio) >= 4:
        return numero_limpio[:3], numero_limpio[3:]
    
    return numero_limpio, ''


def _get_componente_especifico(componentes: list, tipo: str) -> str:
    """
    Extrae datos específicos de un componente según su tipo.
    
    CPU: retorna "MARCA MODELO" (desde las columnas del componente)
    RAM/DISCO: retorna "CAPACIDAD GB"
    """
    if not componentes:
        return 'N/A'

    # CPU: comportamiento original (marca + modelo)
    if tipo == 'CPU':
        for comp in componentes:
            if comp.get('tipo_componente') == tipo:
                marca = (comp.get('nombre_marca') or comp.get('marca') or '').strip()
                modelo = (comp.get('nombre_modelo') or comp.get('modelo') or comp.get('descripcion') or '').strip()
                if marca or modelo:
                    resultado = f"{marca} {modelo}".strip()
                    return resultado if resultado else 'N/A'
                return 'N/A'

    # RAM: sumar módulos cuando haya más de uno
    if tipo == 'RAM':
        caps = []
        for comp in componentes:
            if comp.get('tipo_componente') == tipo:
                cap = comp.get('capacidad') or ''
                if cap:
                    caps.append(str(cap).strip())

        if not caps:
            return 'N/A'

        total_gb = 0.0
        parsed_any = False
        for c in caps:
            s = c.upper().replace(',', '.').strip()
            # Extract numeric part
            num_str = ''.join(ch for ch in s if (ch.isdigit() or ch == '.'))
            if not num_str:
                continue
            try:
                val = float(num_str)
            except Exception:
                continue

            if 'MB' in s and 'GB' not in s:
                # Convert MB to GB (approx 1024 MB = 1 GB)
                total_gb += val / 1024.0
                parsed_any = True
            else:
                # Assume GB when unit absent or contains 'GB'
                total_gb += val
                parsed_any = True

        if parsed_any:
            if total_gb.is_integer():
                return f"{int(total_gb)} GB"
            return f"{round(total_gb,2)} GB"

        # Fallback: concatenar capacidades tal cual si no se pudieron parsear
        return ' + '.join(caps)

    # DISCO y otros: comportamiento original (primera capacidad encontrada)
    for comp in componentes:
        if comp.get('tipo_componente') == tipo:
            capacidad = comp.get('capacidad') or ''
            if capacidad:
                if not str(capacidad).upper().endswith('GB'):
                    return f"{capacidad} GB"
                return str(capacidad)
            return 'N/A'

    return 'N/A'


devices_bp = Blueprint('devices', __name__)


# Log incoming asignacion/documentation requests to asignaciones.log for diagnostics
@devices_bp.before_app_request
def _log_asignaciones_requests():
    try:
        p = request.path or ''
        # Only log requests related to asignaciones/documentacion to avoid noise
        if '/asignacion/' in p or 'documentacion' in p:
            qs = request.query_string.decode('utf-8') if request.query_string else ''
            _write_asignaciones_log(f'[REQUEST] {request.method} {p} q={qs}')
    except Exception:
        pass

# UI listing
@devices_bp.get('/ui')
@require_roles(['reporteria','operador','admin','auditor'], sistema='dispositivos')
def ui_list():
    try:
        logger.info("=== Iniciando carga de página dispositivos ===")
        svc = DeviceService()
        
        logger.info("Obteniendo lista de dispositivos...")
        devices = svc.list_devices()
        logger.info(f"Dispositivos obtenidos: {len(devices)}")
        
        logger.info("Obteniendo dispositivos eliminados...")
        devices_eliminados = svc.list_deleted_devices()
        logger.info(f"Dispositivos eliminados: {len(devices_eliminados)}")
        
        logger.info("Obteniendo celulares...")
        devices_celulares = svc.list_celulares()
        logger.info(f"Celulares obtenidos: {len(devices_celulares)}")
        
        # Procesar números de línea de celulares para separar código de país y número
        for c in devices_celulares:
            numero_linea = c.get('numero_linea') or ''
            parts = numero_linea.strip().split()
            if len(parts) >= 2:
                c['codigo_pais'] = parts[0]
                c['numero_sin_codigo'] = parts[1]
            else:
                code, number = extract_country_code_and_number(numero_linea)
                c['codigo_pais'] = code
                c['numero_sin_codigo'] = number
        
        logger.info("Obteniendo marcas y modelos...")
        marcas = svc.list_marcas()
        modelos = svc.list_modelos()
        logger.info(f"Marcas: {len(marcas)}, Modelos: {len(modelos)}")
        
        logger.info("Renderizando template dispositivos.html")
        return render_template('dispositivos.html', devices=devices, devices_eliminados=devices_eliminados, devices_celulares=devices_celulares, marcas_options=marcas, modelos_options=modelos)
    except Exception as e:
        logger.exception(f"ERROR CRÍTICO en ui_list: {e}")
        return f"Error cargando dispositivos: {str(e)}", 500

# UI para ver dispositivos eliminados
@devices_bp.get('/ui/deleted')
@require_roles(['reporteria','operador','admin'], sistema='dispositivos')
def ui_list_deleted():
    svc = DeviceService()
    devices = svc.list_deleted_devices()
    marcas = svc.list_marcas()
    modelos = svc.list_modelos()
    return render_template('dispositivosEliminados.html', devices=devices, marcas_options=marcas, modelos_options=modelos)

# UI para ver auditoría (registro de acciones)
@devices_bp.get('/ui/auditoria')
@require_roles(['reporteria','admin'], sistema='dispositivos')
def ui_auditoria():
    """Muestra el registro de auditoría con acciones realizadas por usuarios"""
    svc = DeviceService()
    logs = svc.list_auditoria_logs()
    return render_template('auditoria.html', logs=logs)


# Endpoint para recibir y persistir firmas enviadas desde la UI (PNG base64)
@devices_bp.post('/asignaciones/submit-signature')
@require_roles(['operador','admin','reporteria'], sistema='dispositivos')
def submit_signature():
    try:
        payload = request.get_json(silent=True) or {}
        img = payload.get('image')
        asignacion_id = payload.get('asignacion_id')
        if not img:
            return jsonify(success=False, message='No image provided'), 400
        # Accept data URLs or raw base64
        if isinstance(img, str) and img.startswith('data:'):
            img = img.split(',', 1)[1]
        try:
            data = base64.b64decode(img)
        except Exception:
            return jsonify(success=False, message='Invalid base64 image'), 400

        # Registrar en auditoría si el servicio está disponible
        try:
            svc = DeviceService()
            svc.log_auditoria(session.get('username','UNKNOWN'), 'CREATE', 'firma_asignacion', asignacion_id or None, 'Firma capturada en memoria')
        except Exception:
            logger.exception('Auditoría falló al registrar firma')

        return jsonify(success=True, message='Firma capturada')
    except Exception:
        logger.exception('Error guardando firma')
        return jsonify(success=False, message='Error del servidor'), 500

# UI para gestionar marcas
@devices_bp.get('/ui/marcas')
@require_roles(['operador','admin'], sistema='dispositivos')
def ui_list_marcas():
    svc = DeviceService()
    marcas = svc.list_marcas()
    return render_template('marcas.html', marcas=marcas)


# Preview isolado de la sidebar (no modifica plantillas principales)
@devices_bp.get('/ui/sidebar-preview')
@require_roles(['reporteria','operador','admin','auditor'], sistema='dispositivos')
def ui_sidebar_preview():
    """Página de preview para la nueva barra lateral responsiva (aislada)."""
    return render_template('sidebar_preview.html')

# UI tbody para recargar solo la tabla de dispositivos
@devices_bp.get('/ui/tbody')
@require_roles(['reporteria','operador','admin','auditor'], sistema='dispositivos')
def get_devices_tbody():
    """Devuelve solo el tbody de la tabla de dispositivos para AJAX refresh."""
    svc = DeviceService()
    # Procesar parámetros de ordenamiento desde query string
    sort_field = request.args.get('sort')
    sort_dir = request.args.get('dir', 'desc')
    devices = svc.list_devices(sort_field=sort_field, sort_dir=sort_dir)
    return render_template('dispositivosTbody.html', devices=devices)

# UI para gestionar modelos
@devices_bp.get('/ui/modelos')
@require_roles(['operador','admin'], sistema='dispositivos')
def ui_list_modelos():
    svc = DeviceService()
    modelos = svc.list_modelos()
    marcas = svc.list_marcas()
    return render_template('modelos.html', modelos=modelos, marcas_options=marcas)

# JSON listing
@devices_bp.get('/')
@require_roles(['reporteria','operador','admin','auditor'], sistema='dispositivos')
def list_devices():
    svc = DeviceService()
    # Permitir ordenamiento por query params: ?sort=estado&dir=asc
    sort_field = request.args.get('sort')
    sort_dir = request.args.get('dir', 'desc')
    try:
        return jsonify(svc.list_devices(sort_field=sort_field, sort_dir=sort_dir))
    except Exception:
        return jsonify(svc.list_devices())

@devices_bp.get('/disponibles')
@require_roles(['operador','admin'], sistema='dispositivos')
def list_available_devices_api():
    """API: devuelve dispositivos disponibles para asignar (estado 0 y sin asignación activa)"""
    svc = DeviceService()
    return jsonify(svc.list_available_devices())


@devices_bp.get('/sin-plan')
@require_roles(['operador','admin'], sistema='dispositivos')
def list_devices_without_plan_api():
    """API: devuelve dispositivos tipo 'Celular' sin plan vinculado (o sin asignación activa)."""
    svc = DeviceService()
    return jsonify(svc.list_devices_without_plan())

@devices_bp.get('/next-ip')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_next_available_ip_api():
    """API: devuelve la siguiente dirección IP disponible."""
    svc = DeviceService()
    next_ip = svc.get_next_available_ip()
    return jsonify({'next_ip': next_ip})


@devices_bp.get('/next-identifier')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_next_identifier_api():
    """API: devuelve el siguiente identificador disponible según empresa y tipo.
    Query params: empresa (PROIMA|ELMIGO), tipo (categoria del dispositivo)
    Retorna: { identifier: 'PRO-PC-00001' }
    """
    try:
        empresa = request.args.get('empresa', '').upper()
        tipo = request.args.get('tipo', '').lower()
        
        if empresa not in ['PROIMA', 'ELMIGO']:
            return jsonify({'success': False, 'message': 'Empresa inválida'}), 400
        
        if not tipo:
            return jsonify({'success': False, 'message': 'Tipo de dispositivo requerido'}), 400
        
        # Mapeo de tipos a acrónimos
        acronimos = {
            'laptop': 'PC',
            'pc': 'PC',
            'celular': 'CEL',
            'tablet': 'TAB',
            'router': 'ROU',
            'router ap': 'AP',
            'switch': 'SW',
            'monitor': 'MNT',
            'impresora': 'IMP',
            'telefono voip': 'TIP',
            'teclado': 'TEC',
            'mouse': 'MOU',
            'auriculares': 'HEA',
            'ups': 'UPS',
            'adaptador': 'ADP'
        }
        
        acronimo = acronimos.get(tipo)
        if not acronimo:
            return jsonify({'success': False, 'message': f'Tipo de dispositivo no soportado: {tipo}'}), 400
        
        prefijo = 'PRO' if empresa == 'PROIMA' else 'ELM'
        
        # Buscar el máximo correlativo para esta empresa Y tipo de dispositivo
        svc = DeviceService()
        cur = svc.conn.get_cursor()
        
        # Buscar todos los identificadores que empiecen con el prefijo específico: empresa-tipo
        # Ejemplo: PRO-PC-%, PRO-MOU-%, ELM-CEL-%
        patron = f"{prefijo}-{acronimo}-%"
        cur.execute("""
            SELECT identificador FROM dispositivo 
            WHERE identificador LIKE ? 
            AND identificador IS NOT NULL
        """, (patron,))
        
        # Calcular el siguiente correlativo como max existente + 1
        max_correlativo = 0
        for row in cur.fetchall():
            identificador = row[0]
            partes = identificador.split('-')
            if len(partes) == 3:
                try:
                    correlativo = int(partes[2])
                    if correlativo > max_correlativo:
                        max_correlativo = correlativo
                except ValueError:
                    continue

        # Siguiente correlativo (arranca en 1 si no hay existentes)
        siguiente = max_correlativo + 1
        
        # Generar identificador
        identificador = f"{prefijo}-{acronimo}-{siguiente:05d}"
        
        return jsonify({'success': True, 'identifier': identificador}), 200
        
    except Exception as e:
        logger.exception('Error generando siguiente identificador')
        return jsonify({'success': False, 'message': 'Error del servidor'}), 500


@devices_bp.post('/check-ip')
@require_roles(['operador','admin'], sistema='dispositivos')
def check_ip_api():
    """POST JSON: { ip: '192.168.0.27' } -> devuelve si existe y el dispositivo que la tiene."""
    try:
        data = request.get_json(silent=True) or {}
        ip = data.get('ip') if isinstance(data, dict) else None
        if not ip:
            return jsonify({'exists': False, 'message': 'IP no provista'}), 400
        svc = DeviceService()
        dev = svc.find_device_by_ip(ip)
        if not dev:
            return jsonify({'exists': False}), 200
        return jsonify({'exists': True, 'device': dev}), 200
    except Exception:
        logger.exception('Error checking IP')
        return jsonify({'exists': False, 'message': 'Error del servidor'}), 500


@devices_bp.post('/check-serial')
@require_roles(['operador','admin'], sistema='dispositivos')
def check_serial_api():
    """POST JSON: { numero_serie: 'ABC123', device_id: 123 (opcional) } 
    -> devuelve si existe y el dispositivo que lo tiene."""
    try:
        data = request.get_json(silent=True) or {}
        numero_serie = data.get('numero_serie', '').strip().upper()
        device_id = data.get('device_id')
        if not numero_serie:
            return jsonify({'exists': False}), 200
        svc = DeviceService()
        cur = svc.conn.get_cursor()
        # Consulta case-insensitive usando UPPER
        if device_id:
            cur.execute("""
                SELECT d.id_dispositivo, m.categoria, ma.nombre_marca, mo.nombre_modelo, d.numero_serie
                FROM dispositivo d
                LEFT JOIN modelo mo ON d.fk_id_modelo = mo.id_modelo
                LEFT JOIN marca ma ON mo.fk_id_marca = ma.id_marca
                LEFT JOIN modelo m ON mo.id_modelo = m.id_modelo
                WHERE UPPER(d.numero_serie) = ? AND d.id_dispositivo != ? AND d.estado != 3
            """, (numero_serie, device_id))
        else:
            cur.execute("""
                SELECT d.id_dispositivo, m.categoria, ma.nombre_marca, mo.nombre_modelo, d.numero_serie
                FROM dispositivo d
                LEFT JOIN modelo mo ON d.fk_id_modelo = mo.id_modelo
                LEFT JOIN marca ma ON mo.fk_id_marca = ma.id_marca
                LEFT JOIN modelo m ON mo.id_modelo = m.id_modelo
                WHERE UPPER(d.numero_serie) = ? AND d.estado != 3
            """, (numero_serie,))
        row = cur.fetchone()
        if row:
            return jsonify({
                'exists': True, 
                'device': {
                    'id_dispositivo': row[0],
                    'categoria': row[1] or 'dispositivo',
                    'nombre_marca': row[2] or '',
                    'nombre_modelo': row[3] or '',
                    'numero_serie': row[4] or ''
                }
            }), 200
        return jsonify({'exists': False}), 200
    except Exception:
        logger.exception('Error checking serial number')
        return jsonify({'exists': False}), 500


@devices_bp.post('/check-identifier')
@require_roles(['operador','admin'], sistema='dispositivos')
def check_identifier_api():
    """POST JSON: { identifier: 'PRO-PC-00001', device_id: 123 (opcional) } 
    -> devuelve si existe y el dispositivo que lo tiene.
    Si device_id está presente, ignora ese dispositivo (para ediciones)."""
    cur = None
    try:
        data = request.get_json(silent=True) or {}
        identifier = data.get('identifier', '').strip()
        device_id = data.get('device_id')
        
        logger.debug(f'check_identifier_api called with identifier={identifier}, device_id={device_id}')
        
        if not identifier:
            return jsonify({'exists': False, 'message': 'Identificador no provisto'}), 400
        
        try:
            svc = DeviceService()
        except Exception as e:
            logger.error(f'Failed to create DeviceService: {str(e)}')
            return jsonify({'exists': False, 'message': f'Error al crear servicio: {str(e)}'}), 500
        
        if not svc.conn:
            logger.error('Database connection not available in check_identifier_api')
            return jsonify({'exists': False, 'message': 'Error de conexión a base de datos'}), 500
        
        cur = svc.conn.get_cursor()
        
        if device_id:
            # Excluir el dispositivo actual (para edición)
            logger.debug(f'Checking identifier excluding device_id={device_id}')
            cur.execute("""
                SELECT d.id_dispositivo, m.categoria, d.identificador 
                FROM dispositivo d
                JOIN modelo m ON d.fk_id_modelo = m.id_modelo
                WHERE d.identificador = ? AND d.id_dispositivo != ?
            """, (identifier, device_id))
        else:
            # Crear nuevo dispositivo
            logger.debug(f'Checking identifier for new device')
            cur.execute("""
                SELECT d.id_dispositivo, m.categoria, d.identificador 
                FROM dispositivo d
                JOIN modelo m ON d.fk_id_modelo = m.id_modelo
                WHERE d.identificador = ?
            """, (identifier,))
        
        row = cur.fetchone()
        if not row:
            logger.debug(f'Identifier {identifier} not found - available')
            return jsonify({'exists': False}), 200
        
        device = {
            'id_dispositivo': row[0],
            'categoria': row[1],
            'identificador': row[2]
        }
        logger.debug(f'Identifier {identifier} already exists for device {device}')
        return jsonify({'exists': True, 'device': device}), 200
        
    except Exception as e:
        logger.exception(f'Error checking identifier: {str(e)}')
        return jsonify({'exists': False, 'message': f'Error del servidor: {str(e)}'}), 500
    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass


@devices_bp.post('/clear-ip')
@require_roles(['operador','admin'], sistema='dispositivos')
def clear_ip_api():
    """POST JSON: { device_id: 123 } -> limpia ip_asignada del dispositivo indicado."""
    try:
        data = request.get_json(silent=True) or {}
        device_id = data.get('device_id') if isinstance(data, dict) else None
        if not device_id:
            return jsonify({'success': False, 'message': 'device_id requerido'}), 400
        svc = DeviceService()
        ok = svc.clear_ip(int(device_id))
        return jsonify({'success': ok}), 200
    except Exception:
        logger.exception('Error clearing IP')
        return jsonify({'success': False, 'message': 'Error del servidor'}), 500

@devices_bp.get('/<int:device_id>')
@require_roles(['reporteria','operador','admin'], sistema='dispositivos')
def get_device(device_id: int):
    svc = DeviceService()
    dev = svc.get_device(device_id)
    if not dev:
        return jsonify({'error': 'No encontrado'}), 404
    # Normalize fecha_obt to ISO format (YYYY-MM-DD) for input[type=date]
    try:
        fecha_val = dev.get('fecha_obt')
        if fecha_val:
            if hasattr(fecha_val, 'isoformat') and callable(fecha_val.isoformat):
                dev['fecha_obt'] = fecha_val.isoformat()[:10]
            elif isinstance(fecha_val, str):
                dev['fecha_obt'] = fecha_val.split('T')[0].split(' ')[0]
            else:
                dev['fecha_obt'] = str(fecha_val)[:10]
        else:
            dev['fecha_obt'] = ''
    except Exception:
        dev['fecha_obt'] = ''
    return jsonify(dev)

@devices_bp.get('/modelos/tbody')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_modelos_tbody():
    """Devuelve solo el tbody de la tabla de modelos para AJAX refresh."""
    svc = DeviceService()
    modelos = svc.list_modelos()
    return render_template('modelosTbody.html', modelos=modelos)


# =====================
# RUTAS PARA PLANES
# =====================
@devices_bp.get('/planes')
@require_roles(['operador','admin'], sistema='dispositivos')
def lista_planes():
    svc = DeviceService()
    planes = svc.list_planes()
    # Procesar números para separar código de país y número
    for p in planes:
        numero_linea = p.get('numero_linea') or ''
        parts = numero_linea.strip().split()
        if len(parts) >= 2:
            p['codigo_pais'] = parts[0]
            p['numero_sin_codigo'] = parts[1]
        else:
            code, number = extract_country_code_and_number(numero_linea)
            p['codigo_pais'] = code
            p['numero_sin_codigo'] = number
    return render_template('planes.html', planes=planes)


@devices_bp.get('/planes/notifications')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_planes_notifications():
    """API: devuelve notificaciones de planes que vencen en 2 meses o menos."""
    svc = DeviceService()
    try:
        notifs = svc.get_expiring_plans_notifications()
        return jsonify({'success': True, 'notifications': notifs}), 200
    except Exception as e:
        logger.exception('Error getting plan notifications')
        return jsonify({'success': False, 'message': 'No se pudieron obtener notificaciones'}), 500


@devices_bp.post('/planes/<int:plan_id>/renew')
@require_roles(['operador','admin'], sistema='dispositivos')
def renew_plan_api(plan_id: int):
    """API: Renueva un plan. Body JSON: { fecha_inicio, fecha_fin, costo_plan, moneda_plan, device_id (optional) }"""
    data = request.get_json() or {}
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin')
    costo_plan = data.get('costo_plan')
    moneda_plan = data.get('moneda_plan', 'L')
    device_id = data.get('device_id')

    # Basic validation
    if not fecha_inicio or costo_plan is None:
        return jsonify({'success': False, 'message': 'fecha_inicio y costo_plan son requeridos'}), 400

    svc = DeviceService()
    try:
        # Ensure numeric costo
        try:
            costo_val = float(costo_plan) if costo_plan is not None and str(costo_plan) != '' else None
        except:
            return jsonify({'success': False, 'message': 'Costo inválido'}), 400

        result = svc.renew_plane(plan_id, fecha_inicio, fecha_fin, costo_val, moneda_plan, device_id and int(device_id))
        # Log auditoria
        usuario = session.get('username', 'UNKNOWN')
        svc.log_auditoria(usuario, 'UPDATE', 'plan', plan_id, f'Plan renovado - Dispositivo ID: {device_id}')
        return jsonify({'success': True, 'message': 'Plan renovado correctamente', 'result': result}), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 404
    except Exception as e:
        logger.exception('Error renewing plan')
        # Include exception detail for debugging in development environment
        return jsonify({'success': False, 'message': 'No se pudo renovar el plan. Contacte al administrador.', 'detail': str(e)}), 500


@devices_bp.get('/planes/tbody')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_planes_tbody():
    svc = DeviceService()
    planes = svc.list_planes()
    # Procesar números para separar código de país y número
    for p in planes:
        numero_linea = p.get('numero_linea') or ''
        parts = numero_linea.strip().split()
        if len(parts) >= 2:
            p['codigo_pais'] = parts[0]
            p['numero_sin_codigo'] = parts[1]
        else:
            code, number = extract_country_code_and_number(numero_linea)
            p['codigo_pais'] = code
            p['numero_sin_codigo'] = number
    return render_template('planesTbody.html', planes=planes)


@devices_bp.get('/planes/historico/tbody')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_historico_planes_tbody():
    svc = DeviceService()
    historico = svc.list_historico_planes()
    # Procesar números para separar código de país y número
    for h in historico:
        numero_linea = h.get('numero_linea') or ''
        parts = numero_linea.strip().split()
        if len(parts) >= 2:
            h['codigo_pais'] = parts[0]
            h['numero_sin_codigo'] = parts[1]
        else:
            code, number = extract_country_code_and_number(numero_linea)
            h['codigo_pais'] = code
            h['numero_sin_codigo'] = number
    return render_template('historicoPlanesTbody.html', historico=historico)


@devices_bp.get('/planes/historico/<int:historico_id>/devices')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_devices_by_historico(historico_id: int):
    svc = DeviceService()
    try:
        devices = svc.get_devices_by_historico(historico_id)
        return jsonify({'success': True, 'devices': devices}), 200
    except Exception:
        logger.exception('Error getting devices for historico %s', historico_id)
        return jsonify({'success': False, 'devices': []}), 500


@devices_bp.get('/planes/<int:plan_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_plan_api(plan_id: int):
    svc = DeviceService()
    p = svc.get_plane(plan_id)
    if not p:
        return jsonify({'error': 'Plan no encontrado'}), 404
    return jsonify(p), 200

@devices_bp.get('/planes/check-numero/<numero_linea>')
@require_roles(['operador','admin'], sistema='dispositivos')
def check_numero_linea(numero_linea: str):
    """Verifica si un número de línea ya existe en el sistema"""
    if not numero_linea or not numero_linea.strip():
        return jsonify({'exists': False}), 200
    
    svc = DeviceService()
    existing_plan = svc.get_plane_by_numero_linea(numero_linea)
    
    return jsonify({
        'exists': existing_plan is not None,
        'message': 'Este número de línea ya existe en el sistema' if existing_plan else ''
    }), 200


@devices_bp.post('/planes/new')
@require_roles(['operador','admin'], sistema='dispositivos')
def create_plane():
    # accept JSON or form data
    data = request.get_json(silent=True) or request.form
    numero_linea = data.get('numero_linea')
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin') or None
    costo_plan = data.get('costo_plan')
    moneda_plan = data.get('moneda_plan', 'USD')  # Default to USD if not provided
    
    # Validar formato - debe tener código de país + 8 dígitos mínimo
    if not numero_linea:
        return jsonify({'success': False, 'message': 'Número de línea requerido'}), 400
    
    numero_linea_limpio = numero_linea.strip()
    
    # Debe ser solo dígitos, con longitud entre 9 y 12 caracteres (código + número)
    if not numero_linea_limpio.isdigit():
        return jsonify({'success': False, 'message': 'El número debe contener solo dígitos'}), 400
    
    if len(numero_linea_limpio) < 9 or len(numero_linea_limpio) > 12:
        return jsonify({'success': False, 'message': 'El número debe tener entre 9 y 12 dígitos (código de país + 8 dígitos)'}), 400
    
    # Segundo: Verificar que no exista en la BD
    svc = DeviceService()
    try:
        existing = svc.get_plane_by_numero_linea(numero_linea_limpio)
        if existing:
            return jsonify({'success': False, 'message': 'Este número de línea ya existe en el sistema', 'duplicate': True}), 409
    except:
        pass  # Si hay error en búsqueda, continuar
    
    try:
        # Allow numeric string for costo
        costo_val = float(costo_plan) if costo_plan is not None and str(costo_plan) != '' else None
    except:
        return jsonify({'success': False, 'message': 'Costo inválido'}), 400
    
    try:
        # Crear plan en estado pendiente - requiere vinculación obligatoria
        new_id = svc.create_plane_pending(numero_linea_limpio, fecha_inicio, fecha_fin, costo_val, moneda_plan)
        # Log auditoria
        usuario = session.get('username', 'UNKNOWN')
        svc.log_auditoria(usuario, 'CREATE', 'plan', new_id, f'Línea: {numero_linea_limpio}')
        return jsonify({
            'success': True, 
            'message': 'Plan creado. Selecciona un dispositivo para completar.', 
            'id_plan': new_id,
            'plan_data': {
                'id_plan': new_id,
                'numero_linea': numero_linea_limpio,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'costo_plan': costo_val,
                'moneda_plan': moneda_plan
            }
        }), 201
    except ValueError as ve:
        svc.rollback_plan_pending()
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        svc.rollback_plan_pending()
        logger.exception('Error creating plane')
        return jsonify({'success': False, 'message': 'No se pudo crear el plan. Contacte al administrador.'}), 500


@devices_bp.post('/planes/create-and-link')
@require_roles(['operador','admin'], sistema='dispositivos')
def create_plane_and_link():
    """Endpoint transaccional: crea plan + valida dispositivo sin plan + vincula
    
    JSON body:
    {
      "numero_linea": "50487654321",
      "fecha_inicio": "2025-12-31",
      "fecha_fin": "2027-07-31",
      "costo_plan": 27.5,
      "moneda_plan": "$",
      "device_id": 123
    }
    
    Respuestas:
    - 201: Éxito "El plan se agregó con éxito, vinculación exitosa"
    - 400: Error de validación (número inválido, etc.)
    - 409: Dispositivo ya tiene plan asignado
    - 500: Error servidor
    """
    data = request.get_json() or {}
    numero_linea = data.get('numero_linea', '').strip()
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin') or None
    costo_plan = data.get('costo_plan')
    moneda_plan = data.get('moneda_plan', '$')
    device_id = data.get('device_id')
    
    # Validaciones básicas
    if not numero_linea:
        return jsonify({'success': False, 'message': 'Número de línea requerido'}), 400
    if not fecha_inicio:
        return jsonify({'success': False, 'message': 'Fecha inicio requerida'}), 400
    if not device_id:
        return jsonify({'success': False, 'message': 'Dispositivo requerido'}), 400
    
    # Normalizar: aceptar con o sin espacio, guardar con espacio
    # Ejemplo: "39 87654321" o "3987654321" -> guardar como "39 87654321"
    numero_linea_limpio = numero_linea.replace(' ', '')  # Remover espacios para validación
    
    # Validar formato número (debe ser solo dígitos, mínimo 9 caracteres: código (1-3) + número (8))
    if not numero_linea_limpio.isdigit():
        return jsonify({'success': False, 'message': 'El número debe contener solo dígitos'}), 400
    if len(numero_linea_limpio) < 9 or len(numero_linea_limpio) > 12:
        return jsonify({'success': False, 'message': 'El número debe tener entre 9 y 12 dígitos (código de país + 8 dígitos)'}), 400
    
    # Detectar código y número, luego guardar con espacio
    codigo_pais, numero_sin_codigo = extract_country_code_and_number(numero_linea_limpio)
    numero_linea = f"{codigo_pais} {numero_sin_codigo}"
    
    # Validar costo
    try:
        costo_val = float(costo_plan) if costo_plan is not None and str(costo_plan) != '' else 0
    except:
        return jsonify({'success': False, 'message': 'Costo inválido'}), 400
    
    svc = DeviceService()
    try:
        # 1. Verificar que no existe un plan con ese número de línea
        existing_plan = svc.get_plane_by_numero_linea(numero_linea)
        if existing_plan:
            return jsonify({'success': False, 'message': 'Este número de línea ya existe en el sistema'}), 409
        
        # 2. Verificar que el dispositivo NO tiene plan asignado
        device = svc.get_device(device_id)
        if not device:
            return jsonify({'success': False, 'message': 'Dispositivo no encontrado'}), 404
        if device.get('fk_id_plan'):
            # Dispositivo ya tiene plan: error + rollback
            return jsonify({'success': False, 'message': 'El dispositivo ya tiene un plan asignado'}), 409
        
        # 3. Crear el plan y vincular (transacción)
        new_plan_id = svc.create_plane(numero_linea, fecha_inicio, fecha_fin, costo_val, moneda_plan)
        
        # 4. Vincular el dispositivo al plan
        result = svc.link_plan_to_device(device_id, new_plan_id, fecha_inicio)
        
        # 5. Éxito
        return jsonify({
            'success': True,
            'message': 'El plan se agregó con éxito, vinculación exitosa',
            'id_plan': new_plan_id,
            'device_id': device_id,
            'plan_data': {
                'numero_linea': numero_linea,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'costo_plan': costo_val,
                'moneda_plan': moneda_plan
            }
        }), 201
    except Exception as e:
        logger.exception('Error in create_plane_and_link')
        return jsonify({'success': False, 'message': 'Error creando plan: ' + str(e)}), 500


@devices_bp.put('/planes/<int:plan_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def update_plane_api(plan_id: int):
    data = request.get_json() or {}
    numero_linea = data.get('numero_linea', '').strip()
    fecha_inicio = data.get('fecha_inicio')
    fecha_fin = data.get('fecha_fin') or None
    costo_plan = data.get('costo_plan')
    moneda_plan = data.get('moneda_plan', 'USD')  # Default to USD if not provided
    
    # Normalizar: aceptar con o sin espacio, guardar con espacio
    numero_linea_limpio = numero_linea.replace(' ', '')
    if not numero_linea_limpio.isdigit() or len(numero_linea_limpio) < 9 or len(numero_linea_limpio) > 12:
        return jsonify({'success': False, 'message': 'El número debe tener entre 9 y 12 dígitos (código de país + 8 dígitos)'}), 400
    
    # Detectar código y número, luego guardar con espacio
    codigo_pais, numero_sin_codigo = extract_country_code_and_number(numero_linea_limpio)
    numero_linea = f"{codigo_pais} {numero_sin_codigo}"
    
    try:
        costo_val = float(costo_plan) if costo_plan is not None and str(costo_plan) != '' else None
    except:
        return jsonify({'success': False, 'message': 'Costo inválido'}), 400
    svc = DeviceService()
    try:
        svc.update_plane(plan_id, numero_linea, fecha_inicio, fecha_fin, costo_val, moneda_plan)
        return jsonify({'success': True, 'message': 'Plan actualizado correctamente'}), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception:
        logger.exception('Error updating plane')
        return jsonify({'success': False, 'message': 'No se pudo actualizar el plan. Contacte al administrador.'}), 500


@devices_bp.delete('/planes/<int:plan_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def delete_plane_api(plan_id: int):
    svc = DeviceService()
    try:
        svc.delete_plane(plan_id)
        # Log auditoria
        usuario = session.get('username', 'UNKNOWN')
        svc.log_auditoria(usuario, 'DELETE', 'plan', plan_id, 'Plan eliminado')
        return jsonify({'success': True, 'message': 'Plan eliminado correctamente'}), 200
    except Exception as e:
        logger.exception('Error deleting plan')
        return jsonify({'success': False, 'message': 'No se pudo eliminar el plan. Contacte al administrador.'}), 500


@devices_bp.get('/suggestions/<int:modelo_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_device_suggestions_api(modelo_id: int):
    """API: obtiene dispositivos sugeridos basados en el modelo seleccionado"""
    svc = DeviceService()
    try:
        suggestions = svc.get_device_suggestions_by_modelo(modelo_id)
        return jsonify(suggestions), 200
    except Exception as e:
        logger.exception('Error getting device suggestions')
        return jsonify({'error': str(e)}), 500


@devices_bp.post('/planes/<int:plan_id>/confirm')
@require_roles(['operador','admin'], sistema='dispositivos')
def confirm_plane_transaction(plan_id: int):
    """Confirma la transacción de un plan creado con estado pendiente de vinculación"""
    svc = DeviceService()
    try:
        svc.confirm_plan_pending()
        return jsonify({'success': True, 'message': 'Plan confirmado exitosamente'}), 200
    except Exception as e:
        logger.exception('Error confirming plan transaction')
        svc.rollback_plan_pending()
        return jsonify({'success': False, 'message': 'Error confirmando el plan. Contacte al administrador.'}), 500


@devices_bp.post('/planes/<int:plan_id>/rollback')
@require_roles(['operador','admin'], sistema='dispositivos')
def rollback_plane_transaction(plan_id: int):
    """Revierte la creación de un plan si no se completó la vinculación obligatoria"""
    svc = DeviceService()
    try:
        svc.rollback_plan_pending()
        return jsonify({'success': True, 'message': 'Plan descartado correctamente'}), 200
    except Exception as e:
        logger.exception('Error rolling back plan transaction')
        return jsonify({'success': False, 'message': 'Error revirtiendo el plan. Contacte al administrador.'}), 500

@devices_bp.get('/asignaciones/tbody')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_asignaciones_tbody():
    """Devuelve solo el tbody de la tabla de asignaciones para AJAX refresh."""
    svc = DeviceService()
    asignaciones = svc.list_asignaciones()

    # Build resumen employees list (same logic as in lista_asignaciones)
    empleados = []
    try:
        conn_emp = get_db_empleados()
        cur_emp = conn_emp.get_cursor()
        try:
            cur_emp.execute("SELECT id_empleado, nombre_completo, empresa, puesto FROM empleados ORDER BY nombre_completo")
            rows = cur_emp.fetchall()
        except Exception:
            rows = []

        for r in rows:
            try:
                empleados.append({
                    'IdEmpleado': r[0],
                    'NombreCompleto': r[1],
                    'Empresa': r[2],
                    'Cargo': r[3],
                })
            except Exception:
                continue
    except Exception:
        empleados = []

    # Attach dispositivos counts per empleado using asignaciones data
    counts_map = {}
    try:
        for a in asignaciones:
            try:
                emp_id = int(a.get('fk_id_empleado') or 0)
                counts_map[emp_id] = int(a.get('dispositivos_count') or 0)
            except Exception:
                continue
    except Exception:
        counts_map = {}

    for e in empleados:
        try:
            eid = int(e.get('IdEmpleado'))
            e['DispositivosCount'] = counts_map.get(eid, 0)
        except Exception:
            e['DispositivosCount'] = 0

    # Render both partials and return JSON so the frontend can update both tables
    historico_html = render_template('asignacionesTbody.html', asignaciones=asignaciones)
    resumen_html = render_template('asignacionesResumen.html', empleados_options=empleados)
    return jsonify({'historico': historico_html, 'resumen': resumen_html})


@devices_bp.get('/asignaciones/active')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_active_asignaciones_api():
    """API JSON: devuelve asignaciones activas (sin fecha_fin) para uso en selects dinámicos."""
    svc = DeviceService()
    try:
        asignaciones = svc.list_active_asignaciones()
        return jsonify({'success': True, 'asignaciones': asignaciones}), 200
    except Exception as e:
        logger.exception('Error listing active asignaciones')
        return jsonify({'success': False, 'message': 'No se pudo obtener las asignaciones activas. Contacte al administrador.'}), 500

@devices_bp.get('/asignaciones/empleado/<int:empleado_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_dispositivos_empleado(empleado_id):
    """Obtiene los dispositivos asignados activos de un empleado"""
    svc = DeviceService()
    dispositivos = svc.get_dispositivos_empleado(empleado_id)
    return jsonify({'dispositivos': dispositivos})


@devices_bp.post('/asignaciones/transfer')
@require_roles(['operador','admin'], sistema='dispositivos')
def transfer_asignaciones():
    """Transferir dispositivos seleccionados de un empleado a otro.
    JSON body: { from_employee: int, to_employee: int, device_ids: [int] }
    """
    try:
        data = request.get_json(force=True) if request.is_json else request.get_json() or {}
    except Exception as e:
        logger.exception('Error parsing JSON in transfer_asignaciones')
        return jsonify({'success': False, 'message': 'Error al procesar la solicitud. Datos inválidos.'}), 400
    
    from_emp = data.get('from_employee')
    to_emp = data.get('to_employee')
    device_ids = data.get('device_ids') or []
    
    if not from_emp or not to_emp or not device_ids:
        return jsonify({'success': False, 'message': 'Parámetros incompletos'}), 400
    
    svc = DeviceService()
    try:
        svc.transfer_devices_between_empleados(int(from_emp), int(to_emp), list(map(int, device_ids)), usuario_id=session.get('user_id'))
        return jsonify({'success': True, 'message': 'Transferencia completada correctamente'}), 200
    except ValueError as ve:
        logger.error(f'Validation error in transfer_asignaciones: {ve}')
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.exception('Error during transfer_asignaciones')
        return jsonify({'success': False, 'message': f'No se pudo completar la transferencia: {str(e)}'}), 500


@devices_bp.get('/reclamos/tbody')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_reclamos_tbody():
    """Devuelve solo el tbody de la tabla de reclamos para AJAX refresh."""
    svc = DeviceService()
    reclamos = svc.list_reclamos()
    return render_template('reclamosTbody.html', reclamos=reclamos)

@devices_bp.post('/modelo/new')
@require_roles(['operador','admin'], sistema='dispositivos')
def create_modelo():
    # Handle both JSON and form data
    data = request.get_json() or request.form
    svc = DeviceService()
    try:
        nombre = data.get('nombre_modelo')
        tipo = data.get('categoria')
        marca_id = data.get('fk_id_marca')
        # Optional estado (when creating from component modal we may want estado=2)
        estado = data.get('estado') if isinstance(data, dict) else None
        # Campos UPS
        salidas = data.get('salidas')
        capacidad = data.get('capacidad')

        if not all([nombre, tipo, marca_id]):
            return jsonify({
                'success': False,
                'message': 'Todos los campos son requeridos (nombre_modelo, categoria, fk_id_marca)'
            }), 200
        
        try:
            estado_val = int(estado) if estado is not None and estado != '' else 1
        except Exception:
            estado_val = 1
        
        try:
            salidas_val = int(salidas) if salidas is not None and salidas != '' else None
        except Exception:
            salidas_val = None

        modelo_id = svc.create_modelo(nombre, tipo, marca_id, estado=estado_val, salidas=salidas_val, capacidad=capacidad)
        return jsonify({
            'success': True,
            'message': 'Modelo creado exitosamente',
            'id_modelo': modelo_id
        })
    except ValueError as ve:
        # Return 200 with success:false to avoid browser console errors on duplicates/validation
        return jsonify({'success': False, 'message': str(ve)}), 200
    except Exception as e:
        logger.exception('Error creating modelo')
        return jsonify({
            'success': False,
            'message': 'No se pudo crear el modelo. Contacte al administrador.'
        }), 500

# GET marcas para API
@devices_bp.get('/marca/')
@require_roles(['reporteria','operador','admin'], sistema='dispositivos')
def get_marcas_api():
    svc = DeviceService()
    return jsonify(svc.list_marcas())


@devices_bp.get('/marca/all')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_marcas_all_api():
    svc = DeviceService()
    return jsonify(svc.list_marcas_all())

# GET modelos para API
@devices_bp.get('/modelo/')
@require_roles(['reporteria','operador','admin'], sistema='dispositivos')
def get_modelos_api():
    svc = DeviceService()
    estado = request.args.get('estado')
    categoria = request.args.get('categoria')
    try:
        estado_val = int(estado) if estado is not None and estado != '' else None
    except Exception:
        estado_val = None
    return jsonify(svc.list_modelos(estado=estado_val, categoria=categoria))


@devices_bp.get('/modelo/all')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_modelos_all_api():
    svc = DeviceService()
    return jsonify(svc.list_modelos_all())

@devices_bp.get('/modelo/<int:modelo_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_modelo_api(modelo_id: int):
    """Obtiene un modelo por ID con sus campos UPS."""
    svc = DeviceService()
    try:
        modelo = svc.get_modelo(modelo_id)
        if not modelo:
            return jsonify({'success': False, 'message': 'Modelo no encontrado'}), 404
        return jsonify(modelo), 200
    except Exception as e:
        logger.exception('Error getting modelo')
        return jsonify({'success': False, 'message': 'Error obteniendo modelo'}), 500

@devices_bp.post('/marca/new')
@require_roles(['operador','admin'], sistema='dispositivos')
def create_marca_api():
    """Crea una marca nueva. Acepta JSON o form data con `nombre_marca`."""
    data = request.get_json(silent=True) or request.form
    nombre = data.get('nombre_marca') or data.get('nombre')
    if not nombre:
        return jsonify({'success': False, 'message': 'nombre_marca es requerido'}), 200
    svc = DeviceService()
    try:
        marca_id, nombre_out = svc.create_marca(nombre)
        return jsonify({'success': True, 'message': 'Marca creada', 'id_marca': marca_id, 'nombre_marca': nombre_out}), 201
    except ValueError as ve:
        # user-friendly message without quoting internal value
        msg = str(ve)
        if 'Ya existe' in msg:
            return jsonify({'success': False, 'message': 'Ya existe una marca con ese nombre'}), 200
        return jsonify({'success': False, 'message': 'Dato inválido'}), 200
    except Exception as e:
        logger.exception('Error creating marca')
        return jsonify({'success': False, 'error': 'No se pudo crear la marca. Contacte al administrador.'}), 500


@devices_bp.put('/marca/<int:marca_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def update_marca_api(marca_id: int):
    """API JSON: actualiza una marca. Devuelve mensajes amigables en caso de fallo."""
    data = request.get_json() or {}
    nombre = data.get('nombre_marca')

    if not nombre:
        return jsonify({'success': False, 'message': 'El nombre de la marca es requerido'}), 400

    svc = DeviceService()
    try:
        svc.update_marca(marca_id, nombre)
        return jsonify({'success': True, 'message': 'Se ha realizado con éxito'}), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception:
        return jsonify({'success': False, 'message': 'No se pudo actualizar la marca. Verifica los datos.'}), 400


@devices_bp.delete('/marca/<int:marca_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def delete_marca_api(marca_id: int):
    """API JSON: elimina una marca; devuelve 200 con success=false si hay error."""
    svc = DeviceService()
    try:
        svc.delete_marca(marca_id)
        return jsonify({'success': True, 'message': 'Marca eliminada correctamente'}), 200
    except Exception as e:
        error_msg = str(e).lower()
        # Detectar errores de integridad referencial (FK constraint)
        if 'foreign key' in error_msg or 'integrity' in error_msg or 'constraint' in error_msg:
            return jsonify({'success': False, 'message': 'No se puede eliminar esta marca porque está asociada a modelos. Elimina los modelos primero.'}), 200
        # Error genérico
        return jsonify({'success': False, 'message': 'No se pudo eliminar la marca. Verifica si hay modelos o dispositivos asociados.'}), 200


    @devices_bp.put('/marca/<int:marca_id>/estado')
    @require_roles(['operador','admin'], sistema='dispositivos')
    def update_marca_estado_api(marca_id: int):
        data = request.get_json() or {}
        if 'estado' not in data:
            return jsonify({'success': False, 'message': 'Campo estado requerido'}), 400
        try:
            estado = int(data.get('estado'))
        except Exception:
            return jsonify({'success': False, 'message': 'Valor de estado inválido'}), 400
        svc = DeviceService()
        try:
            svc.set_marca_estado(marca_id, estado)
            return jsonify({'success': True, 'message': 'Estado actualizado'}), 200
        except Exception:
            return jsonify({'success': False, 'message': 'No se pudo actualizar el estado de la marca'}), 500


@devices_bp.put('/modelo/<int:modelo_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def update_modelo_api(modelo_id: int):
    """API JSON: actualiza un modelo. Devuelve mensajes amigables en caso de fallo."""
    data = request.get_json() or {}
    nombre = data.get('nombre_modelo')
    tipo = data.get('categoria')
    fk_id_marca = data.get('fk_id_marca')
    # Campos UPS
    salidas = data.get('salidas')
    capacidad = data.get('capacidad')

    if not all([nombre, tipo, fk_id_marca]):
        return jsonify({'success': False, 'message': 'Todos los campos son requeridos'}), 400
    
    try:
        salidas_val = int(salidas) if salidas is not None and salidas != '' else None
    except Exception:
        salidas_val = None

    svc = DeviceService()
    try:
        svc.update_modelo(modelo_id, nombre, tipo, int(fk_id_marca), salidas=salidas_val, capacidad=capacidad)
        return jsonify({'success': True, 'message': 'Se ha realizado con éxito'}), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception:
        return jsonify({'success': False, 'message': 'No se pudo actualizar el modelo. Verifica los datos.'}), 400


@devices_bp.put('/modelo/<int:modelo_id>/estado')
@require_roles(['operador','admin'], sistema='dispositivos')
def update_modelo_estado_api(modelo_id: int):
    data = request.get_json() or {}
    if 'estado' not in data:
        return jsonify({'success': False, 'message': 'Campo estado requerido'}), 400
    try:
        estado = int(data.get('estado'))
    except Exception:
        return jsonify({'success': False, 'message': 'Valor de estado inválido'}), 400
    svc = DeviceService()
    try:
        svc.set_modelo_estado(modelo_id, estado)
        return jsonify({'success': True, 'message': 'Estado actualizado'}), 200
    except Exception:
        return jsonify({'success': False, 'message': 'No se pudo actualizar el estado del modelo'}), 500


@devices_bp.get('/modelo/delete/<int:modelo_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def delete_modelo(modelo_id: int):
    """Elimina un modelo si no está referenciado por dispositivos; muestra mensaje amigable si hay FK."""
    svc = DeviceService()
    try:
        svc.delete_modelo(modelo_id)
        flash('Modelo eliminado correctamente', 'success')
    except Exception as e:
        # Probablemente restricción FK si existen dispositivos asociados
        flash('No se pudo eliminar el modelo. Verifica si hay dispositivos asociados.', 'error')
    return redirect(url_for('devices.lista_modelos'))



@devices_bp.delete('/modelo/<int:modelo_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def delete_modelo_api(modelo_id: int):
    """API JSON: elimina un modelo; devuelve 200 con success=false si hay error."""
    svc = DeviceService()
    try:
        svc.delete_modelo(modelo_id)
        return jsonify({'success': True, 'message': 'Modelo eliminado correctamente'}), 200
    except Exception as e:
        error_msg = str(e).lower()
        # Detectar errores de integridad referencial (FK constraint)
        if 'foreign key' in error_msg or 'integrity' in error_msg or 'constraint' in error_msg:
            return jsonify({'success': False, 'message': 'No se puede eliminar este modelo porque está asociado a dispositivos. Elimina los dispositivos primero.'}), 200
        # Error genérico
        return jsonify({'success': False, 'message': 'No se pudo eliminar el modelo. Verifica si hay dispositivos asociados.'}), 200

@devices_bp.get('/asignaciones')
@require_roles(['operador','admin'], sistema='dispositivos')
def lista_asignaciones():
    svc = DeviceService()
    asignaciones = svc.list_asignaciones()
    # Obtener dispositivos disponibles para asignar (estado 0 y sin asignación activa)
    dispositivos_sin_asignar = svc.list_available_devices()
    # Obtener empleados directamente desde la BD `empleados` y mapear
    # columnas al formato esperado por la plantilla (IdEmpleado, NombreCompleto, Empresa, Cargo/puesto)
    empleados = []
    try:
        conn_emp = get_db_empleados()
        cur_emp = conn_emp.get_cursor()
        try:
            # Traer campos desde empleados: id_empleado, nombre_completo, empresa, puesto, estado
            cur_emp.execute(
                "SELECT id_empleado, nombre_completo, empresa, puesto, estado FROM empleados ORDER BY nombre_completo"
            )
            rows = cur_emp.fetchall()
        except Exception:
            rows = []

        for r in rows:
            try:
                estado_raw = None
                try:
                    estado_raw = r[4]
                except Exception:
                    estado_raw = None
                is_active = True
                try:
                    is_active = (remap_estado_empleado(estado_raw) == 1)
                except Exception:
                    is_active = True

                empleados.append({
                    'IdEmpleado': r[0],
                    'NombreCompleto': r[1],
                    'Empresa': r[2],
                            'Cargo': r[3],  # puesto from empleados
                    'Estado': estado_raw,
                    'IsActive': is_active
                })
            except Exception:
                continue
    except Exception as e:
        logger.exception('Error leyendo empleados desde empleados')
        empleados = []
    # Construir mapa de conteo de dispositivos por empleado usando los datos ya calculados en asignaciones
    counts_map = {}
    try:
        for a in asignaciones:
            try:
                emp_id = int(a.get('fk_id_empleado') or 0)
                # cada fila de asignaciones incluye 'dispositivos_count' calculado en el servicio
                counts_map[emp_id] = int(a.get('dispositivos_count') or 0)
            except Exception:
                continue
    except Exception:
        counts_map = {}

    # Adjuntar conteo a la lista de empleados para que siempre se pueda mostrar en la plantilla
    for e in empleados:
        try:
            eid = int(e.get('IdEmpleado'))
            e['DispositivosCount'] = counts_map.get(eid, 0)
        except Exception:
            e['DispositivosCount'] = 0

    return render_template('asignaciones.html', asignaciones=asignaciones, dispositivos_options=dispositivos_sin_asignar, empleados_options=empleados)


@devices_bp.get('/<int:device_id>/asignaciones/device')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_asignaciones_por_device(device_id: int):
    """API JSON: devuelve las asignaciones (historial) de un dispositivo."""
    svc = DeviceService()
    try:
        asignaciones = svc.list_asignaciones()
        # Filtrar por dispositivo
        historial = [a for a in asignaciones if int(a.get('fk_id_dispositivo') or 0) == int(device_id)]
        return jsonify({'success': True, 'asignaciones': historial}), 200
    except Exception as e:
        logger.exception('Error getting asignaciones por device')
        return jsonify({'success': False, 'message': 'No se pudo obtener el historial de asignaciones. Contacte al administrador.'}), 500


@devices_bp.delete('/asignacion/<int:asignacion_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def delete_asignacion_api(asignacion_id: int):
    """API JSON: elimina una asignación; retorna mensaje genérico en caso de fallo."""
    svc = DeviceService()
    try:
        svc.delete_asignacion(asignacion_id)
        return jsonify({'success': True, 'message': 'Se ha realizado con éxito'}), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception:
        return jsonify({'success': False, 'message': 'No se pudo eliminar la asignación. Verifica si hay dependencias.'}), 400

@devices_bp.post('/asignacion/new')
@require_roles(['operador','admin'], sistema='dispositivos')
def create_asignacion():
    form = request.form
    svc = DeviceService()
    try:
        # Prevent creating assignment for inactive employees
        empleado_id = form.get('fk_id_empleado')
        try:
            emp = svc.get_empleado(int(empleado_id)) if empleado_id else None
        except Exception:
            emp = None
        if emp:
            try:
                if remap_estado_empleado(emp.get('estado')) != 1:
                    return jsonify({'success': False, 'message': 'No se puede crear asignación: empleado inactivo.'}), 400
            except Exception:
                pass
        # Convertir fecha_fin_asignacion vacía a None para que sea NULL en BD
        fecha_fin = form.get('fecha_fin_asignacion') or None
        reemplazo_flag = True if form.get('reemplazo') in ('1','on','true','True') else False
        new_id = svc.create_asignacion(
            form.get('fk_id_dispositivo'),
            form.get('fk_id_empleado'),
            form.get('codigo_plaza'),
            form.get('fecha_inicio_asignacion'),
            fecha_fin,
            form.get('observaciones'),
            reemplazo_flag
        )

        # Render a single-row partial for the new assignment so the frontend
        # can insert it into the histórico without a full page reload.
        try:
            new_asign = svc.get_asignacion(new_id) if new_id else None
            if new_asign:
                # Render a single historico-style row so the frontend insertion
                # matches the structure used in the #historicoTable (edit + PDF actions).
                row_html = render_template('asignacionesNewRow.html', asignacion=new_asign)
            else:
                row_html = ''
        except Exception:
            row_html = ''

        # Also include the created asignacion as JSON so the frontend can
        # update resumen counters without an extra fetch.
        try:
            new_asign_json = new_asign if new_asign else None
        except Exception:
            new_asign_json = None
        # Log auditoria
        usuario = session.get('username', 'UNKNOWN')
        dispositivo_id = form.get('fk_id_dispositivo')
        svc.log_auditoria(usuario, 'CREATE', 'asignacion', new_id, f'Dispositivo ID: {dispositivo_id}')
        return jsonify({
            'success': True,
            'message': 'Asignación creada exitosamente',
            'new_row_html': row_html,
            'new_asign': new_asign_json
        })
    except Exception as e:
        logger.exception('Error creating asignacion')
        return jsonify({
            'success': False,
            'message': 'No se pudo crear la asignación. Contacte al administrador.'
        }), 500


@devices_bp.post('/asignacion/link-plan')
@require_roles(['operador','admin'], sistema='dispositivos')
def link_plan_to_device_api():
    data = request.get_json() or {}
    device_id = data.get('device_id')
    plan_id = data.get('plan_id')
    fecha_inicio = data.get('fecha_inicio')
    # Optional country code / extension provided by the frontend (e.g. '504' or '+504')
    ext = data.get('extension') or data.get('country_code') or data.get('codigo_pais') or data.get('ext')
    if not device_id or not plan_id:
        return jsonify({'success': False, 'message': 'device_id y plan_id son requeridos'}), 400
    svc = DeviceService()
    try:
        # Normalize plan_id when it's a simple value and an extension is provided
        def normalize_number(p, extension):
            try:
                s = str(p).strip()
            except Exception:
                s = ''
            if not s:
                return s
            # If already contains +, assume complete
            if s.startswith('+'):
                return s
            # Clean non-digit characters from extension and number
            import re
            ext_digits = ''
            if extension:
                ext_digits = re.sub(r"\D", "", str(extension))
            num_digits = re.sub(r"\D", "", s)
            if ext_digits:
                return f"+{ext_digits}{num_digits}"
            # If no extension provided and number looks short, default to +504
            if len(num_digits) < 8:
                return f"+504{num_digits}"
            return f"+{num_digits}"

        if not isinstance(plan_id, dict):
            # normalize simple values
            plan_id = normalize_number(plan_id, ext)

        result = svc.link_plan_to_device(int(device_id), plan_id, fecha_inicio)
        # result is a dict with device_id and id_plan
        return jsonify({'success': True, 'message': 'Plan vinculado al dispositivo', 'id_plan': result.get('id_plan'), 'device_id': result.get('device_id')}), 200
    except ValueError as ve:
        # Errores de validación/negocio: devolver 400 con mensaje claro
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.exception('Error linking plan to device')
        return jsonify({'success': False, 'message': 'No se pudo vincular el plan al dispositivo. Contacte al administrador.'}), 500


@devices_bp.get('/asignacion/<int:asignacion_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_asignacion_api(asignacion_id: int):
    svc = DeviceService()
    a = svc.get_asignacion(asignacion_id)
    if not a:
        return jsonify({'error': 'Asignación no encontrada'}), 404
    # Audit log: record who accessed which assignment (IDOR traceability)
    usuario = session.get('username', 'UNKNOWN')
    svc.log_auditoria(usuario, 'READ', 'asignacion', asignacion_id, 'Acceso vía API')
    return jsonify(a), 200


@devices_bp.put('/asignacion/<int:asignacion_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def update_asignacion_api(asignacion_id: int):
    data = request.get_json() or {}
    fecha_fin = data.get('fecha_fin_asignacion')
    observ = data.get('observaciones')
    try:
        svc = DeviceService()
        # IDOR protection: verify the assignment exists before any modification.
        # Prevents blind writes to arbitrary IDs and ensures 404 is returned consistently.
        if not svc.get_asignacion(asignacion_id):
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        svc.update_asignacion_end_date(asignacion_id, fecha_fin)
        if observ is not None:
            cur = svc.conn.get_cursor()
            cur.execute("UPDATE asignacion SET observaciones = ? WHERE id_asignacion = ?", (observ, asignacion_id))
            svc.conn.commit()
        usuario = session.get('username', 'UNKNOWN')
        svc.log_auditoria(usuario, 'UPDATE', 'asignacion', asignacion_id, 'Actualización vía API')
        return jsonify({'success': True, 'message': 'Asignación actualizada'}), 200
    except Exception:
        return jsonify({'success': False, 'message': 'No se pudo actualizar la asignación'}), 400

@devices_bp.get('/reclamos')
@require_roles(['operador','admin'], sistema='dispositivos')
def lista_reclamos():
    svc = DeviceService()
    reclamos = svc.list_reclamos()
    # Para crear un nuevo reclamo solo permitimos asignaciones activas (empleados con dispositivo actualmente vinculado)
    asignaciones = svc.list_active_asignaciones()
    return render_template('reclamos.html', reclamos=reclamos, asignaciones_options=asignaciones)


@devices_bp.delete('/reclamo/<int:reclamo_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def delete_reclamo_api(reclamo_id: int):
    """API JSON: elimina un reclamo; retorna mensaje genérico en caso de fallo."""
    svc = DeviceService()
    try:
        svc.delete_reclamo(reclamo_id)
        return jsonify({'success': True, 'message': 'Se ha realizado con éxito'}), 200
    except Exception:
        return jsonify({'success': False, 'message': 'No se pudo eliminar el reclamo. Verifica si hay dependencias.'}), 400

@devices_bp.post('/reclamo/new')
@require_roles(['operador','admin'], sistema='dispositivos')
def create_reclamo():
    form = request.form
    svc = DeviceService()
    try:
        # Procesar imágenes si existen
        img_evidencia = None
        img_form = None
        
        if 'img_evidencia' in request.files:
            file_evidencia = request.files['img_evidencia']
            if file_evidencia and file_evidencia.filename != '':
                img_evidencia = file_evidencia.read()
        
        if 'img_form' in request.files:
            file_form = request.files['img_form']
            if file_form and file_form.filename != '':
                img_form = file_form.read()
        
        # Support new optional incident fields: 'fecha_incidencia' and 'lugar_incidencia'
        fecha_incidencia = form.get('fecha_incidencia') or form.get('fecha_robo')
        lugar_incidencia = form.get('lugar_incidencia') or form.get('lugar_robo')
        reclamo_id = svc.create_reclamo(
            form.get('fk_id_asignacion'),
            fecha_incidencia,
            lugar_incidencia,
            form.get('fecha_inicio_reclamo'),
            form.get('lugar_reclamo'),
            form.get('estado_proceso'),
            None,
            img_evidencia,
            img_form
        )
        # Log auditoria
        usuario = session.get('username', 'UNKNOWN')
        asignacion_id = form.get('fk_id_asignacion')
        svc.log_auditoria(usuario, 'CREATE', 'reclamo', reclamo_id, f'Asignación ID: {asignacion_id}')
        return jsonify({
            'success': True,
            'message': 'Reclamo creado exitosamente'
        })
    except Exception as e:
        logger.exception('Error creating reclamo')
        return jsonify({
            'success': False,
            'message': 'No se pudo crear el reclamo. Contacte al administrador.'
        }), 500


@devices_bp.get('/reclamo/<int:reclamo_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_reclamo_api(reclamo_id: int):
    svc = DeviceService()
    r = svc.get_reclamo(reclamo_id)
    if not r:
        return jsonify({'error': 'Reclamo no encontrado'}), 404
    # Detect presence of stored images to allow previews without fetching binary yet
    try:
        cur = svc.conn.get_cursor()
        cur.execute("SELECT CASE WHEN img_evidencia IS NULL THEN 0 ELSE 1 END AS has_evid, CASE WHEN img_form IS NULL THEN 0 ELSE 1 END AS has_form FROM reclamo_seguro WHERE id_reclamo = ?", (reclamo_id,))
        row = cur.fetchone()
        if row:
            r['has_img_evidencia'] = bool(row[0])
            r['has_img_form'] = bool(row[1])
        else:
            r['has_img_evidencia'] = False
            r['has_img_form'] = False
    except Exception:
        r['has_img_evidencia'] = False
        r['has_img_form'] = False
    # Normalize date fields to ISO 'YYYY-MM-DD' so <input type="date"> accepts them
    for dkey in ('fecha_robo', 'fecha_inicio_reclamo', 'fecha_fin_reclamo'):
        try:
            val = r.get(dkey)
            if val is None:
                r[dkey] = ''
            else:
                # If it's a date/datetime-like object with isoformat
                if hasattr(val, 'isoformat') and callable(val.isoformat):
                    r[dkey] = val.isoformat()[:10]
                elif isinstance(val, str):
                    # trim time part if present
                    r[dkey] = val.split('T')[0].split(' ')[0]
                else:
                    r[dkey] = str(val)[:10]
        except Exception:
            r[dkey] = ''

    return jsonify(r), 200


@devices_bp.get('/reclamo/<int:reclamo_id>/evidencia')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_reclamo_evidencia(reclamo_id: int):
    svc = DeviceService()
    cur = svc.conn.get_cursor()
    cur.execute("SELECT img_evidencia FROM reclamo_seguro WHERE id_reclamo = ?", (reclamo_id,))
    row = cur.fetchone()
    if not row or not row[0]:
        return ('', 404)
    data = row[0]
    from flask import Response
    return Response(data, mimetype='image/*')


@devices_bp.get('/reclamo/<int:reclamo_id>/form')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_reclamo_form_image(reclamo_id: int):
    svc = DeviceService()
    cur = svc.conn.get_cursor()
    cur.execute("SELECT img_form FROM reclamo_seguro WHERE id_reclamo = ?", (reclamo_id,))
    row = cur.fetchone()
    if not row or not row[0]:
        return ('', 404)
    data = row[0]
    from flask import Response
    return Response(data, mimetype='image/*')


@devices_bp.put('/reclamo/<int:reclamo_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def update_reclamo_api(reclamo_id: int):
    # Procesar tanto JSON como FormData
    data = request.get_json(silent=True) or request.form or {}
    estado = data.get('estado_proceso')
    # Accept fecha_incidencia / fecha_robo and fecha_inicio_reclamo
    fecha_robo = data.get('fecha_incidencia') or data.get('fecha_robo') or None
    fecha_inicio = data.get('fecha_inicio_reclamo') or None
    # Normalize empty strings to None so date columns receive NULL instead of ''
    fecha_fin = data.get('fecha_fin_reclamo') or None
    lugar = data.get('lugar_reclamo') or None
    
    # Procesar imágenes si existen
    img_evidencia = None
    img_form = None
    
    if 'img_evidencia' in request.files:
        file_evidencia = request.files['img_evidencia']
        if file_evidencia and file_evidencia.filename != '':
            img_evidencia = file_evidencia.read()
    
    if 'img_form' in request.files:
        file_form = request.files['img_form']
        if file_form and file_form.filename != '':
            img_form = file_form.read()
    
    try:
        estado_val = 1 if str(estado) in ['1', 'true', 'True', True] else 0
    except:
        estado_val = 0
    # Validate provided dates (not future)
    try:
        from datetime import datetime
        if fecha_robo:
            # allow YYYY-MM-DD or ISO strings
            fr = datetime.fromisoformat(fecha_robo)
            if fr.date() > datetime.now().date():
                return jsonify({'success': False, 'message': 'Fecha de incidencia no puede ser futura.'}), 400
        if fecha_inicio:
            fi = datetime.fromisoformat(fecha_inicio)
            if fi.date() > datetime.now().date():
                return jsonify({'success': False, 'message': 'Fecha inicio no puede ser futura.'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'Formato de fecha inválido.'}), 400
    except Exception:
        pass
    svc = DeviceService()
    try:
        # Support removal flags from form ('1'|'0')
        remove_evid = (request.form.get('remove_img_evidencia') in ('1','true','True','on')) if request.form else False
        remove_form = (request.form.get('remove_img_form') in ('1','true','True','on')) if request.form else False
        svc.update_reclamo(reclamo_id, estado_val, fecha_fin, lugar, img_evidencia, img_form, remove_img_evidencia=remove_evid, remove_img_form=remove_form, fecha_robo=fecha_robo, fecha_inicio_reclamo=fecha_inicio)
        return jsonify({'success': True, 'message': 'Reclamo actualizado correctamente'}), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.exception('Error updating reclamo')
        return jsonify({'success': False, 'message': 'No se pudo actualizar el reclamo. Contacte al administrador.'}), 500

@devices_bp.post('/new')
@require_roles(['operador','admin'], sistema='dispositivos')
def create_device():
    form = request.form
    svc = DeviceService()
    try:
        fk_id_modelo = form.get('fk_id_modelo')
        if not fk_id_modelo:
            flash('Error: Debe seleccionar un modelo', 'error')
            return redirect(url_for('devices.ui_list'))
        
        # Obtener el modelo para extraer categoria
        modelo = svc.get_modelo(int(fk_id_modelo))
        if not modelo:
            flash('Error: Modelo no encontrado', 'error')
            return redirect(url_for('devices.ui_list'))
        
        # Convertir estado de string a número para almacenamiento
        estado_form = form.get('estado')
        # Try to parse numeric estado; support values 0,1,2,3,4 (4 = Uso general)
        estado = 0
        if estado_form is not None and estado_form != '':
            try:
                estado_val = int(estado_form)
                if estado_val in (0, 1, 2, 3, 4):
                    estado = estado_val
            except Exception:
                # fallback: map known string tokens
                estado_map = {'0': 0, '1': 1, '2': 2, '3': 3, '4': 4}
                estado = estado_map.get(estado_form, 0)
        
        # validate fecha_obt (accept new 'fecha_obt' or legacy 'fecha_obtencion') if provided
        fecha_obt = form.get('fecha_obtencion') or form.get('fecha_obt') or None
        if fecha_obt:
            try:
                fecha_val = datetime.fromisoformat(fecha_obt).date()
                # Validation of future dates is handled by frontend
            except Exception:
                flash('Formato de fecha inválido para Fecha de obtención', 'error')
                return redirect(url_for('devices.ui_list'))

        # If the DB schema doesn't include the column, ignore the supplied value to avoid SQL errors
        try:
            # Prefer new column name 'fecha_obt', fallback to legacy 'fecha_obtencion'
            if fecha_obt and not (svc.has_column('dispositivo', 'fecha_obt') or svc.has_column('dispositivo', 'fecha_obtencion')):
                fecha_obt = None
        except Exception:
            fecha_obt = None

        # Include identificador if the DB schema supports it
        identificador_val = None
        # Prepare conflict map to accumulate any duplicates across fields
        dup_conflicts = {'identificador': False, 'numero_serie': False, 'imei': False}
        try:
            if svc.has_column('dispositivo', 'identificador'):
                identificador_val = (form.get('identificador') or '').strip()
                # Validar que el identificador no esté vacío
                if not identificador_val:
                    flash('Error: El identificador es obligatorio', 'error')
                    return redirect(url_for('devices.ui_list'))
                # Validar que no exista otro dispositivo con el mismo identificador (case-insensitive)
                existing = svc.get_device_by_identificador(identificador_val)
                if existing:
                    # mark identificador conflict but continue to check other fields
                    dup_conflicts['identificador'] = True
        except Exception as e:
            logger.exception('Error validating identificador')
            flash('Error validando identificador', 'error')
            return redirect(url_for('devices.ui_list'))

        # Pre-check for duplicate numero_serie / imei to provide detailed conflicts to AJAX clients
        try:
            numero_serie_val = (form.get('numero_serie') or '').strip()
            imei_val = (form.get('imei') or '').strip()
            imei2_val = (form.get('imei2') or '').strip()
            cur = svc.conn.get_cursor()
            if numero_serie_val:
                cur.execute("SELECT id_dispositivo FROM dispositivo WHERE numero_serie = ?", (numero_serie_val,))
                if cur.fetchone():
                    dup_conflicts['numero_serie'] = True
            if imei_val:
                cur.execute("SELECT id_dispositivo FROM dispositivo WHERE imei = ? OR imei2 = ?", (imei_val, imei_val))
                if cur.fetchone():
                    dup_conflicts['imei'] = True
            if imei2_val:
                cur.execute("SELECT id_dispositivo FROM dispositivo WHERE imei = ? OR imei2 = ?", (imei2_val, imei2_val))
                if cur.fetchone():
                    dup_conflicts['imei'] = True
            if any(dup_conflicts.values()):
                if request.accept_mimetypes.accept_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'message': 'Conflictos con campos existentes', 'conflicts': dup_conflicts}), 400
                # Fallback flash for non-AJAX
                msgs = []
                if dup_conflicts['identificador']:
                    msgs.append('identificador')
                if dup_conflicts['numero_serie']:
                    msgs.append('número de serie')
                if dup_conflicts['imei']:
                    msgs.append('IMEI')
                flash(f'Error: Ya existe un dispositivo con {", ".join(msgs)}', 'error')
                return redirect(url_for('devices.ui_list'))
        except Exception:
            # If duplicate checks fail for any reason, continue and let create_device handle DB errors
            pass

        # Para periféricos (no conectables) asignar "N/A" a ip_asignada si viene vacío
        # NOTA: dispositivos como Celular, Tablet, Laptop y PC deben recibir una IP automática cuando corresponda,
        # por lo que no los forzamos a N/A aquí.
        ip_asignada_val = form.get('ip_asignada') or None
        categoria_lower = (modelo.get('categoria') or '').lower()
        # Categorías consideradas periféricos (las etiquetas en UI/modelos)
        perif_types = {'monitor', 'impresora', 'ups', 'teclado', 'mouse', 'auriculares', 'adaptador'}
        if categoria_lower in perif_types and 'voip' not in categoria_lower and not ip_asignada_val:
            ip_asignada_val = 'N/A'
        
        device_id = svc.create_device(
            fk_id_modelo=int(fk_id_modelo),
            numero_serie=form.get('numero_serie'),
            identificador=identificador_val,
            fecha_obtencion=fecha_obt,
            imei=form.get('imei') or None,
            imei2=form.get('imei2') or None,
            direccion_mac=form.get('direccion_mac') or None,
            ip_asignada=ip_asignada_val,
            tamano=form.get('tamano') or None,
            color=form.get('color') or None,
            observaciones=form.get('observaciones') or None,
            cargador=(form.get('cargador') == 'on'),
            estado=estado,
        )
        # Crear componentes por defecto para el nuevo dispositivo: CPU, RAM y DISCO
        try:
            try:
                svc.create_componente(fk_id_dispositivo=device_id, tipo_componente='CPU')
            except Exception:
                # ignore individual failures
                logger.debug('No se pudo crear componente CPU por defecto para dispositivo %s', device_id)
            try:
                svc.create_componente(fk_id_dispositivo=device_id, tipo_componente='RAM')
            except Exception:
                logger.debug('No se pudo crear componente RAM por defecto para dispositivo %s', device_id)
            try:
                svc.create_componente(fk_id_dispositivo=device_id, tipo_componente='DISCO')
            except Exception:
                logger.debug('No se pudo crear componente DISCO por defecto para dispositivo %s', device_id)
        except Exception:
            # No debe bloquear la creación del dispositivo si la lógica de componentes falla
            logger.exception('Error creando componentes por defecto para dispositivo %s', device_id)
        # Fetch the created device to return complete data
        device = svc.get_device(device_id)
        # `svc.get_device` and `svc.get_modelo` return dicts
        device_data = {
            'id_dispositivo': device.get('id_dispositivo') if isinstance(device, dict) else getattr(device, 'id_dispositivo', None),
            'numero_serie': device.get('numero_serie') if isinstance(device, dict) else getattr(device, 'numero_serie', None),
            'nombre_modelo': modelo.get('nombre_modelo') if isinstance(modelo, dict) else getattr(modelo, 'nombre_modelo', None),
            'categoria': modelo.get('categoria') if isinstance(modelo, dict) else getattr(modelo, 'categoria', None),
            'nombre_marca': device.get('nombre_marca') if isinstance(device, dict) else getattr(device, 'nombre_marca', None),
            'estado': device.get('estado') if isinstance(device, dict) else getattr(device, 'estado', None),
            'ip_asignada': device.get('ip_asignada') if isinstance(device, dict) else getattr(device, 'ip_asignada', None)
        }
        # Log auditoria
        usuario = session.get('username', 'UNKNOWN')
        numero_serie_str = device.get('numero_serie') if isinstance(device, dict) else getattr(device, 'numero_serie', '')
        svc.log_auditoria(usuario, 'CREATE', 'dispositivo', device_id, f'Número serie: {numero_serie_str}')
        return jsonify({
            'success': True,
            'message': 'Dispositivo creado',
            'device_id': device_id,
            'device': device_data
        })
    except Exception as e:
        logger.exception('Error creating device')
        return jsonify({
            'success': False,
            'message': 'No se pudo crear el dispositivo. Contacte al administrador.'
        }), 500
    finally:
        # If tinta tracking requested, update printers config file with the IP and detail
        try:
            tinta_flag = (form.get('tinta_seguimiento') in ('1','on','true','True')) if form else False
            tinta_detail = (form.get('tinta_seguimiento_detalle') or '').strip() if form else ''
            ip_val = (form.get('ip_asignada') or '').strip() if form else ''
            if tinta_flag and ip_val:
                # load existing config (ip->desc) and update
                from pathlib import Path
                import json
                base_dir = Path(__file__).parent.parent.parent
                cfg_file = base_dir / 'exports' / 'printer_config.json'
                cfg = {}
                if cfg_file.exists():
                    try:
                        with open(cfg_file, 'r', encoding='utf-8') as f:
                            cfg = json.load(f) or {}
                        logger.info(f"Loaded existing printer_config.json with {len(cfg.get('printers', {}))} printers")
                    except Exception as e:
                        logger.error(f"Failed to load printer_config.json: {e}")
                        cfg = {}
                else:
                    logger.info("printer_config.json does not exist, creating new")
                    
                # ensure top-level dict
                if not isinstance(cfg, dict): 
                    logger.warning("cfg is not a dict, resetting to empty dict")
                    cfg = {}
                    
                ip_map = cfg.get('printers', {}) if isinstance(cfg.get('printers', {}), dict) else {}
                logger.info(f"ip_map before update has {len(ip_map)} printers: {list(ip_map.keys())}")
                
                # Migrar formato antiguo a nuevo si es necesario
                for ip_key, ip_value in list(ip_map.items()):
                    if isinstance(ip_value, str):
                        ip_map[ip_key] = {'descripcion': ip_value, 'estado': 1}
                
                # set description (prefer provided detail, else keep existing or use ip)
                existing_printer = ip_map.get(ip_val, {})
                desc = tinta_detail or (existing_printer.get('descripcion') if isinstance(existing_printer, dict) else existing_printer) or ip_val
                
                # Guardar con nuevo formato: {"descripcion": "...", "estado": 1}
                ip_map[ip_val] = {'descripcion': desc, 'estado': 1}
                
                logger.info(f"Adding/updating printer: {ip_val} = {desc} (estado: 1)")
                logger.info(f"ip_map after update has {len(ip_map)} printers: {list(ip_map.keys())}")
                
                cfg['printers'] = ip_map
                cfg['last_updated'] = __import__('datetime').datetime.now().isoformat()
                cfg_file.parent.mkdir(parents=True, exist_ok=True)
                with open(cfg_file, 'w', encoding='utf-8') as f:
                    json.dump(cfg, f, indent=2, ensure_ascii=False)
                logger.info(f"Successfully saved printer_config.json with {len(ip_map)} printers")
        except Exception as e:
            # don't break main flow if config write fails
            logger.exception(f'Failed to update printer_config.json: {e}')


def update_printer_config_state(ip_address: str, new_state: int):
    """
    Actualiza el estado de una impresora en printer_config.json
    new_state: 0 (inactiva) o 1 (activa)
    """
    try:
        from pathlib import Path
        import json
        base_dir = Path(__file__).parent.parent.parent
        cfg_file = base_dir / 'exports' / 'printer_config.json'
        
        if not cfg_file.exists():
            logger.info(f"printer_config.json does not exist, cannot update state for {ip_address}")
            return
        
        with open(cfg_file, 'r', encoding='utf-8') as f:
            cfg = json.load(f) or {}
        
        if not isinstance(cfg, dict):
            cfg = {}
        
        ip_map = cfg.get('printers', {})
        
        # Migrar formato de lista a diccionario si es necesario
        if isinstance(ip_map, list):
            logger.info(f"Migrating printer config from list to dict format")
            new_ip_map = {}
            for printer in ip_map:
                if isinstance(printer, dict):
                    ip = printer.get('ip')
                    if ip:
                        descripcion = printer.get('description') or printer.get('descripcion', ip)
                        # Si no tiene estado, asumir activo (1)
                        estado = printer.get('estado', 1)
                        new_ip_map[ip] = {'descripcion': descripcion, 'estado': estado}
            ip_map = new_ip_map
        elif not isinstance(ip_map, dict):
            ip_map = {}
        
        # Migrar formato antiguo (string values) si es necesario
        for ip_key, ip_value in list(ip_map.items()):
            if isinstance(ip_value, str):
                ip_map[ip_key] = {'descripcion': ip_value, 'estado': 1}
        
        # Actualizar estado si la IP existe
        if ip_address in ip_map:
            if isinstance(ip_map[ip_address], dict):
                ip_map[ip_address]['estado'] = new_state
                logger.info(f"Updated printer {ip_address} state to {new_state}")
            else:
                # Formato antiguo, convertir
                ip_map[ip_address] = {'descripcion': ip_map[ip_address], 'estado': new_state}
                logger.info(f"Migrated and updated printer {ip_address} state to {new_state}")
            
            cfg['printers'] = ip_map
            cfg['last_updated'] = __import__('datetime').datetime.now().isoformat()
            
            with open(cfg_file, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        else:
            logger.info(f"Printer {ip_address} not found in config, skipping state update")
    except Exception as e:
        logger.exception(f"Failed to update printer state for {ip_address}: {e}")


@devices_bp.post('/<int:device_id>/copy-components')
@require_roles(['operador','admin'], sistema='dispositivos')
def copy_components_api(device_id: int):
    """API: copia componentes de un dispositivo fuente al dispositivo recién creado"""
    data = request.get_json() or {}
    componentes = data.get('componentes', [])
    
    if not componentes:
        return jsonify({'success': False, 'message': 'No hay componentes para copiar'}), 400
    
    svc = DeviceService()
    try:
        cur = svc.conn.get_cursor()

        # Eliminar todos los componentes existentes del dispositivo (los vacíos creados por defecto)
        # para evitar duplicados al copiar la sugerencia.
        cur.execute("DELETE FROM componente WHERE fk_id_dispositivo = ?", (device_id,))
        svc.conn.commit()

        # Construir un dict tipo_int -> comp para deduplicar: si la sugerencia tiene duplicados
        # del mismo tipo (posible si el origen fue creado con el bug anterior), quedarse solo
        # con el que tenga más datos (capacidad o marca presentes).
        comp_by_tipo = {}
        for comp in componentes:
            tipo_raw = comp.get('tipo_componente')
            tipo_int = None

            if isinstance(tipo_raw, int):
                tipo_int = tipo_raw
            elif isinstance(tipo_raw, str):
                if tipo_raw.isdigit():
                    tipo_int = int(tipo_raw)
                else:
                    tipo_text = tipo_raw.strip().upper()
                    if tipo_text == 'CPU':
                        tipo_int = 0
                    elif tipo_text == 'RAM':
                        tipo_int = 1
                    elif tipo_text == 'DISCO':
                        tipo_int = 2

            if tipo_int not in (0, 1, 2):
                continue

            existing = comp_by_tipo.get(tipo_int)
            if existing is None:
                comp_by_tipo[tipo_int] = comp
            else:
                # Preferir el que tenga más datos
                has_data = bool(comp.get('capacidad') or comp.get('fk_id_marca') or comp.get('frecuencia'))
                if has_data:
                    comp_by_tipo[tipo_int] = comp

        copied_count = 0
        for tipo_int, comp in comp_by_tipo.items():
            svc.create_componente(
                fk_id_dispositivo=device_id,
                tipo_componente=str(tipo_int),
                frecuencia=comp.get('frecuencia'),
                tipo_memoria=comp.get('tipo_memoria'),
                tipo_modulo=comp.get('tipo_modulo'),
                capacidad=comp.get('capacidad'),
                tipo_disco=comp.get('tipo_disco'),
                fk_id_marca=comp.get('fk_id_marca'),
                fk_id_modelo=comp.get('fk_id_modelo'),
                numero_serie=None,  # No copiar número de serie
            )
            copied_count += 1

        # Si la sugerencia no incluye algún tipo (ej. CPU para celulares sin CPU), crear en blanco
        for tipo_int in (0, 1, 2):
            if tipo_int not in comp_by_tipo:
                try:
                    svc.create_componente(fk_id_dispositivo=device_id, tipo_componente=str(tipo_int))
                except Exception:
                    pass  # No crítico

        return jsonify({'success': True, 'message': f'{copied_count} componente(s) copiado(s) exitosamente'}), 200
    except Exception as e:
        logger.exception('Error copying components')
        return jsonify({'success': False, 'message': str(e)}), 500


@devices_bp.delete('/<int:device_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def delete_device_api(device_id: int):
    """API JSON: elimina un dispositivo (backup + delete) y devuelve mensaje genérico en caso de fallo."""
    svc = DeviceService()
    try:
        # Obtener info del dispositivo antes de eliminarlo para detectar si es impresora
        dispositivo = svc.get_device(device_id)
        
        # aceptar motivo opcional en JSON para auditoría
        data = request.get_json(silent=True) or {}
        motivo = data.get('motivo_baja') if isinstance(data, dict) else None
        # llamamos al método que hace backup y marca como eliminado (estado=3)
        svc.backup_and_delete_device(device_id, motivo_baja=motivo)
        
        # Si es una impresora con IP, marcar como inactiva (estado=0) en printer_config.json
        if dispositivo and dispositivo.get('categoria') == 'Impresora' and dispositivo.get('ip_asignada'):
            update_printer_config_state(dispositivo['ip_asignada'], 0)
            logger.info(f"Printer {dispositivo['ip_asignada']} marked as inactive (estado=0) after deletion")
        
        # Log auditoria
        usuario = session.get('username', 'UNKNOWN')
        descripcion = f'Motivo: {motivo}' if motivo else 'Sin motivo especificado'
        svc.log_auditoria(usuario, 'DELETE', 'dispositivo', device_id, descripcion)
        return jsonify({'success': True, 'message': 'Dispositivo eliminado correctamente'}), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.exception('Error deleting device')
        return jsonify({'success': False, 'message': 'No se pudo eliminar el dispositivo. Contacte al administrador.'}), 500


# Obtener asignación activa del dispositivo
@devices_bp.get('/<int:device_id>/asignacion-activa')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_active_asignacion(device_id: int):
    svc = DeviceService()
    asign = svc.get_active_asignacion_by_device(device_id)
    if not asign:
        return jsonify({'active': False}), 200
    return jsonify({'active': True, 'asignacion': asign}), 200


# =====================
# COMPONENTES (per-device)
# =====================
@devices_bp.get('/<int:device_id>/componentes')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_componentes_by_device(device_id: int):
    svc = DeviceService()
    try:
        comps = svc.list_components(device_id)
        return jsonify({'success': True, 'componentes': comps}), 200
    except Exception as e:
        logger.exception('Error listing componentes for device')
        return jsonify({'success': False, 'message': 'No se pudieron obtener los componentes del dispositivo. Contacte al administrador.'}), 500


@devices_bp.post('/<int:device_id>/componente/new')
@require_roles(['operador','admin'], sistema='dispositivos')
def create_componente_api(device_id: int):
    # Accept JSON or form data
    data = request.get_json(silent=True) or request.form or {}
    tipo = data.get('tipo_componente')
    frecuencia = data.get('frecuencia')
    tipo_memoria = data.get('tipo_memoria')
    tipo_modulo = data.get('tipo_modulo')
    capacidad = data.get('capacidad')
    tipo_disco = data.get('tipo_disco')
    fk_id_marca = data.get('fk_id_marca')
    numero_serie = data.get('numero_serie')

    svc = DeviceService()
    try:
        new_id = svc.create_componente(
            fk_id_dispositivo=device_id,
            tipo_componente=tipo,
            frecuencia=frecuencia,
            tipo_memoria=tipo_memoria,
            tipo_modulo=tipo_modulo,
            capacidad=capacidad,
            tipo_disco=tipo_disco,
            fk_id_marca=fk_id_marca,
            numero_serie=numero_serie
        )
        # Return the created component record for convenience
        comps = svc.list_components(device_id)
        created = next((c for c in comps if c.get('id_componente') == new_id), None)
        return jsonify({'success': True, 'message': 'Componente creado', 'id_componente': new_id, 'componente': created}), 201
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.exception('Error creating componente')
        try:
            logging.getLogger('admin_disp.dispositivos').exception('Error creating componente: payload=%s exception=%s', data, e)
        except Exception:
            pass
        return jsonify({'success': False, 'message': 'No se pudo crear el componente. Contacte al administrador.'}), 500

@devices_bp.get('/<int:device_id>/componentes/<int:componente_id>')
@require_roles(['reporteria','operador','admin'], sistema='dispositivos')
def get_componente_by_id(device_id: int, componente_id: int):
    try:
        svc = DeviceService()
        componente = svc.get_componente(componente_id)
        if not componente or componente.get('fk_id_dispositivo') != device_id:
            return jsonify({'success': False, 'message': 'Componente no encontrado'}), 404
        return jsonify({'success': True, 'componente': componente}), 200
    except Exception as e:
        print(f'ERROR get_componente: {str(e)}', flush=True)
        logger.exception('Error getting componente')
        try:
            logging.getLogger('admin_disp.dispositivos').exception('Error getting componente %s: %s', componente_id, e)
        except Exception:
            pass
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@devices_bp.put('/<int:device_id>/componentes/<int:componente_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def update_componente_api(device_id: int, componente_id: int):
    try:
        svc = DeviceService()
        data = request.get_json() or {}
        # Log incoming payload to help debugging failures during update
        try:
            logger.debug('update_componente_api payload for componente_id=%s: %s', componente_id, data)
        except Exception:
            pass
        
        # Verify component belongs to this device
        comp = svc.get_componente(componente_id)
        if not comp or comp.get('fk_id_dispositivo') != device_id:
            return jsonify({'success': False, 'message': 'Componente no encontrado'}), 404
        
        svc.update_componente(
            componente_id=componente_id,
            tipo_componente=data.get('tipo_componente'),
            frecuencia=data.get('frecuencia'),
            tipo_memoria=data.get('tipo_memoria'),
            tipo_modulo=data.get('tipo_modulo'),
            capacidad=data.get('capacidad'),
            tipo_disco=data.get('tipo_disco'),
            fk_id_marca=data.get('fk_id_marca'),
            fk_id_modelo=data.get('fk_id_modelo'),
            estado=data.get('estado'),
            numero_serie=data.get('numero_serie'),
            observaciones=data.get('observaciones')
        )
        
        # Return updated componente (already normalized by get_componente)
        updated = svc.get_componente(componente_id)
        return jsonify({'success': True, 'message': 'Componente actualizado', 'componente': updated}), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        # Log full exception and payload for debugging
        try:
            logger.exception('Error updating componente id=%s payload=%s', componente_id, data)
        except Exception:
            logger.exception('Error updating componente (exception while logging additional context)')
        try:
            logging.getLogger('admin_disp.dispositivos').exception('Error updating componente id=%s payload=%s exception=%s', componente_id, data, e)
        except Exception:
            pass
        return jsonify({'success': False, 'message': 'No se pudo actualizar el componente'}), 500

@devices_bp.delete('/<int:device_id>/componentes/<int:componente_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def delete_componente_api(device_id: int, componente_id: int):
    try:
        svc = DeviceService()
        # Verify component belongs to this device
        comp = svc.get_componente(componente_id)
        if not comp or comp.get('fk_id_dispositivo') != device_id:
            return jsonify({'success': False, 'message': 'Componente no encontrado'}), 404
        
        # Soft-delete: marcar el componente con estado = 3 (eliminado/oculto)
        try:
            svc.update_componente(componente_id=componente_id, estado=3)
            return jsonify({'success': True, 'message': 'Componente marcado como eliminado'}), 200
        except Exception:
            # Fallback: si no se pudo actualizar, intentar borrar físicamente como último recurso
            svc.delete_componente(componente_id)
            return jsonify({'success': True, 'message': 'Componente eliminado'}), 200
    except Exception as e:
        logger.exception('Error deleting componente')
        try:
            logging.getLogger('admin_disp.dispositivos').exception('Error deleting componente id=%s exception=%s', componente_id, e)
        except Exception:
            pass
        return jsonify({'success': False, 'message': 'No se pudo eliminar el componente'}), 500

@devices_bp.put('/<int:device_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def update_device_api(device_id: int):
    data = request.get_json() or {}
    # permitir sólo campos permitidos
    # permitir actualizar la FK al modelo y las observaciones
    allowed = ['numero_serie', 'identificador', 'imei', 'imei2', 'direccion_mac', 'ip_asignada', 'tamano', 'color', 'cargador', 'estado', 'fk_id_modelo', 'observaciones', 'fecha_obtencion', 'fecha_obt']
    # accept either 'fecha_obt' (new) or 'fecha_obtencion' (legacy)
    payload = {k: data.get(k) for k in allowed if k in data}
    
    # Obtener dispositivo actual para detectar cambios de estado en impresoras
    svc = DeviceService()
    dispositivo_actual = svc.get_device(device_id)
    
    # Coercionar `estado` a entero (0..3) para almacenar en BD
    if 'estado' in payload:
        raw = payload['estado']
        estado_int = None
        # Si viene como int
        if isinstance(raw, int):
            estado_int = raw
        # Si viene como string numérica
        elif isinstance(raw, str):
            if raw.isdigit():
                try:
                    estado_int = int(raw)
                except:
                    estado_int = None
            else:
                txt = raw.strip().lower()
                if txt in ('sin asignar', 'sin_asignar', 'sin-asignar', 'sinasignar'):
                    estado_int = 0
                elif txt in ('asignado', 'asignada'):
                    estado_int = 1
                elif txt in ('en reparacion', 'en_reparacion', 'en-reparacion', 'en reparación'):
                    estado_int = 2
                elif txt in ('eliminado', 'eliminada'):
                    estado_int = 3
                elif txt in ('uso general', 'uso_general', 'uso-general', 'usoGeneral'):
                    estado_int = 4

        # Fallback a 0 si no se pudo determinar
        if estado_int is None:
            estado_int = 0

        # Asegurar rango válido
        try:
            estado_int = int(estado_int)
        except:
            estado_int = 0
        if estado_int < 0 or estado_int > 4:
            estado_int = 0

        payload['estado'] = estado_int
    
    if not payload:
        return jsonify({'success': False, 'message': 'No hay campos válidos para actualizar'}), 400
    
    # Validar identificador si se está actualizando
    if 'identificador' in payload and payload['identificador']:
        payload['identificador'] = str(payload['identificador']).strip()
        # Verificar que no exista otro dispositivo con el mismo identificador
        svc = DeviceService()
        existing = svc.get_device_by_identificador(payload['identificador'])
        if existing and existing.get('id_dispositivo') != device_id:
            return jsonify({'success': False, 'message': f'Ya existe un dispositivo con el identificador "{payload["identificador"]}"'}), 400
    # Coercionar fk_id_modelo a int si se provee
    if 'fk_id_modelo' in payload:
        try:
            payload['fk_id_modelo'] = int(payload['fk_id_modelo']) if payload['fk_id_modelo'] not in (None, '') else None
        except:
            payload['fk_id_modelo'] = None
    # Validate fecha (accept either key)
    fecha_key = None
    if 'fecha_obt' in payload:
        fecha_key = 'fecha_obt'
    elif 'fecha_obtencion' in payload:
        fecha_key = 'fecha_obtencion'
    if fecha_key and payload.get(fecha_key):
        try:
            fecha_val = datetime.fromisoformat(payload[fecha_key]).date()
            # Validation of future dates is handled by frontend
        except Exception:
            return jsonify({'success': False, 'message': f'Formato de fecha inválido para {fecha_key}'}), 400
    svc = DeviceService()
    try:
        # If DB schema doesn't include identificador, avoid sending it
        try:
            if 'identificador' in payload and not svc.has_column('dispositivo', 'identificador'):
                payload.pop('identificador', None)
        except Exception:
            pass

        # Si el payload no incluye ip_asignada pero el dispositivo (o el nuevo modelo) es celular/tablet/periférico
        # y no es VoIP, asegurarse de dejar 'N/A' en lugar de NULL/vacío.
        try:
            final_category = None
            # Si se está cambiando el modelo, obtener la categoría del nuevo modelo
            if 'fk_id_modelo' in payload and payload.get('fk_id_modelo'):
                try:
                    new_modelo = svc.get_modelo(int(payload.get('fk_id_modelo')))
                    final_category = (new_modelo.get('categoria') or '').lower() if new_modelo else None
                except Exception:
                    final_category = None
            # Si no hay cambio de modelo, tomar la categoría actual
            if not final_category and dispositivo_actual:
                final_category = (dispositivo_actual.get('categoria') or '').lower()
            if final_category:
                perif_types = {'monitor', 'impresora', 'ups', 'teclado', 'mouse', 'auriculares', 'adaptador'}
                if ('voip' not in final_category) and (final_category in ('celular', 'tablet') or final_category in perif_types):
                    if 'ip_asignada' not in payload or not payload.get('ip_asignada'):
                        payload['ip_asignada'] = 'N/A'
        except Exception:
            # No bloquear la actualización por este ajuste; seguir con los datos tal cual
            pass

        svc.update_device(device_id, **payload)
        
        # Si es una impresora y cambió el estado, actualizar printer_config.json
        if dispositivo_actual and dispositivo_actual.get('categoria') == 'Impresora' and dispositivo_actual.get('ip_asignada'):
            if 'estado' in payload:
                nuevo_estado = payload['estado']
                # estado=4 (uso general) → marcar impresora como activa (estado=1)
                # estado=2 (reparación) → marcar impresora como inactiva (estado=0)
                # estado=3 (eliminado) → marcar impresora como inactiva (estado=0)
                if nuevo_estado == 4:
                    update_printer_config_state(dispositivo_actual['ip_asignada'], 1)
                    logger.info(f"Printer {dispositivo_actual['ip_asignada']} activated (estado=1) after device estado change to uso general")
                elif nuevo_estado in (2, 3):
                    update_printer_config_state(dispositivo_actual['ip_asignada'], 0)
                    logger.info(f"Printer {dispositivo_actual['ip_asignada']} deactivated (estado=0) after device estado change to {nuevo_estado}")
        
        # Log auditoria
        usuario = session.get('username', 'UNKNOWN')
        campos_actualizados = ', '.join(payload.keys())
        svc.log_auditoria(usuario, 'UPDATE', 'dispositivo', device_id, f'Campos: {campos_actualizados}')
        return jsonify({'success': True, 'message': 'Dispositivo actualizado correctamente'}), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception:
        return jsonify({'success': False, 'message': 'No se pudo actualizar el dispositivo.'}), 400


@devices_bp.post('/<int:device_id>/finalizar-asignacion')
@require_roles(['operador','admin'], sistema='dispositivos')
def finalizar_asignacion_device(device_id: int):
    svc = DeviceService()
    try:
        fecha_fin = svc.finalize_assignment_by_device(device_id)
        if not fecha_fin:
            return jsonify({'success': False, 'message': 'No hay una asignación activa para este dispositivo.'}), 400
        # Include finalized date in response so the frontend can update the histórico row
        try:
            fecha_fin_str = fecha_fin.isoformat()
        except Exception:
            fecha_fin_str = str(fecha_fin)
        # Log auditoria
        usuario = session.get('username', 'UNKNOWN')
        svc.log_auditoria(usuario, 'UPDATE', 'asignacion', device_id, f'Asignación finalizada - Fecha fin: {fecha_fin_str}')
        return jsonify({'success': True, 'message': 'Asignación finalizada y dispositivo liberado.', 'fecha_fin': fecha_fin_str}), 200
    except Exception:
        logger.exception('Error finalizing assignment for device %s', device_id)
        return jsonify({'success': False, 'message': 'No se pudo finalizar la asignación. Intenta nuevamente.', 'detail': 'Internal error logged'}), 500

# =============================================
# RUTAS PARA ADMINISTRACIÓN DE USUARIOS
# DEPRECADAS - Ahora se usa modal en menu.html con auth/routes.py
# =============================================

# @devices_bp.get('/usuarios')
# @require_roles(['admin'], sistema='dispositivos')
# def usuarios_admin():
#     """Página de administración de usuarios"""
#     auth_svc = AuthService()
#     employees = auth_svc.get_employees_without_user()
#     roles = auth_svc.get_roles()
#     return render_template('usuarios.html', employees=employees, roles=roles)

# @devices_bp.get('/usuarios/sin-usuario')
# @require_roles(['admin'], sistema='dispositivos')
# def get_employees_without_user():
#     """API: obtiene empleados sin cuenta asociada"""
#     auth_svc = AuthService()
#     employees = auth_svc.get_employees_without_user()
#     return jsonify(employees)


# @devices_bp.get('/usuarios/roles')
# @require_roles(['admin'], sistema='dispositivos')
# def get_roles_api():
#     """API: obtiene roles disponibles"""
#     auth_svc = AuthService()
#     roles = auth_svc.get_roles()
#     return jsonify(roles)

# @devices_bp.get('/usuarios/lista')
# @require_roles(['admin'], sistema='dispositivos')
# def list_users_api():
#     """API: lista todos los usuarios activos"""
#     auth_svc = AuthService()
#     users = auth_svc.list_all_users()
#     return jsonify(users)


@devices_bp.get('/current-user')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def get_current_user():
    """API: obtiene información del usuario actual en sesión"""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No hay sesión activa'}), 401
        
        username = session.get('username', 'Usuario')
        
        # Intentar obtener nombre completo del empleado asociado
        nombre = username
        try:
            svc = DeviceService()
            cur = get_db_empleados().get_cursor()
            cur.execute("SELECT fk_id_empleado FROM empleados.dbo.usuarios WHERE id_usuario = ?", (session['user_id'],))
            user_row = cur.fetchone()
            if user_row and user_row[0]:
                empleado = svc.get_empleado(user_row[0])
                if empleado:
                    nombre = empleado.get('nombre_completo') or username
            cur.close()
        except Exception as e:
            logger.warning(f'Error obteniendo empleado del usuario: {e}')
        
        return jsonify({
            'id': session.get('user_id'),
            'username': username,
            'nombre': nombre,
            'role': session.get('role', 'operador')
        }), 200
        
    except Exception as e:
        logger.exception(f'Error en get_current_user: {e}')
        return jsonify({'error': 'Error interno'}), 500


@devices_bp.post('/asignacion/log')
@require_roles(['reporteria','operador','admin','auditor'], sistema='dispositivos')
def log_asignacion_frontend():
    """Endpoint para recibir logs desde el frontend y guardarlos en asignaciones.log"""
    try:
        data = request.json or {}
        msg = data.get('message', '')
        level = data.get('level', 'INFO').upper()
        
        if msg:
            asignaciones_logger.log(
                getattr(logging, level, logging.INFO),
                f'[FRONTEND] {msg}'
            )
        
        return jsonify({'success': True}), 200
    except Exception as e:
        asignaciones_logger.exception(f'Error en log_asignacion_frontend: {e}')
        return jsonify({'error': str(e)}), 500


@devices_bp.get('/current-user-details')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def get_current_user_details():
    """API: devuelve información extendida del usuario en sesión (nombre, puesto y empleado si existe)."""
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'No hay sesión activa'}), 401

        user_id = session.get('user_id')
        auth_svc = AuthService()
        user = auth_svc.get_user_by_id(user_id)

        # Default values
        resp = {
            'user_id': user_id,
            'username': session.get('username'),
            'nombre_usuario': session.get('username') or '',
            'puesto': None,
            'nombre_empleado': None,
            'fk_id_empleado': None
        }

        try:
            if user:
                resp['fk_id_empleado'] = user.get('IdEmpleado') or user.get('IdEmpleado') if user.get('IdEmpleado') is not None else user.get('IdEmpleado')
                # Prefer nombre_completo si está disponible
                resp['nombre_usuario'] = user.get('NombreCompleto') or user.get('NombreCompleto') or resp['nombre_usuario']
                # If there is an empleado id, fetch empleado details
                if resp['fk_id_empleado']:
                    svc = DeviceService()
                    empleado = svc.get_empleado(resp['fk_id_empleado'])
                    if empleado:
                        resp['nombre_empleado'] = empleado.get('nombre_completo') or empleado.get('NombreCompleto')
                        resp['puesto'] = empleado.get('puesto') or empleado.get('Puesto')
        except Exception:
            pass

        return jsonify(resp), 200
    except Exception as e:
        logger.exception('Error en get_current_user_details')
        return jsonify({'error': 'Error interno'}), 500


# DEPRECADAS - Rutas de edición/consulta de usuarios movidas a auth/routes.py
# @devices_bp.get('/usuarios/<int:user_id>')
# @require_roles(['admin'], sistema='dispositivos')
# def get_user_api(user_id: int):
#     """API: obtiene detalles de un usuario"""
#     auth_svc = AuthService()
#     user = auth_svc.get_user_by_id(user_id)
#     if not user:
#         return jsonify({'error': 'Usuario no encontrado'}), 404
#     return jsonify(user)


@devices_bp.get('/empleado/<int:empleado_id>')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_empleado_api(empleado_id: int):
    """API: devuelve datos básicos de un empleado por su ID."""
    svc = DeviceService()
    empleado = svc.get_empleado(empleado_id)
    if not empleado:
        return jsonify({'error': 'Empleado no encontrado'}), 404
    return jsonify(empleado), 200


@devices_bp.post('/empleado/<int:empleado_id>/update-pasaporte')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def update_empleado_pasaporte(empleado_id: int):
    """API: actualiza el pasaporte de un empleado."""
    data = request.get_json() or {}
    pasaporte = (data.get('pasaporte') or '').strip()
    
    if not pasaporte:
        return jsonify({'success': False, 'message': 'Pasaporte es requerido'}), 400
    
    # Validar formato xxxx-xxxx-xxxxx
    import re
    if not re.match(r'^\d{4}-\d{4}-\d{5}$', pasaporte):
        return jsonify({'success': False, 'message': 'Formato de pasaporte inválido. Debe ser: xxxx-xxxx-xxxxx'}), 400
    
    try:
        conn = get_db_empleados()
        cur = conn.get_cursor()
        
        # Verificar que el empleado existe
        cur.execute("SELECT id_empleado FROM empleados.dbo.empleados WHERE id_empleado = ?", (empleado_id,))
        if not cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Empleado no encontrado'}), 404
        
        # Actualizar pasaporte
        cur.execute(
            "UPDATE empleados.dbo.empleados SET pasaporte = ? WHERE id_empleado = ?",
            (pasaporte, empleado_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f'Pasaporte actualizado para empleado {empleado_id}')
        return jsonify({'success': True, 'message': 'Pasaporte actualizado correctamente'}), 200
        
    except Exception as e:
        logger.exception(f'Error actualizando pasaporte del empleado {empleado_id}')
        return jsonify({'success': False, 'message': f'Error actualizando pasaporte: {str(e)}'}), 500


# DEPRECADAS - Ahora se usan endpoints en auth/routes.py para gestión multi-sistema
# @devices_bp.put('/usuarios/<int:user_id>')
# @require_roles(['admin'], sistema='dispositivos')
# def update_user_admin(user_id: int):
#     """API: actualiza rol y/o contraseña de un usuario (actualización, no desactivación)"""
#     data = request.get_json()
#     role_id = data.get('role_id')
#     password = data.get('password')  # opcional
#     
#     if not role_id:
#         return jsonify({'error': 'role_id es requerido'}), 400
#     
#     auth_svc = AuthService()
#     
#     # Verificar que el usuario existe
#     user = auth_svc.get_user_by_id(user_id)
#     if not user:
#         return jsonify({'error': 'Usuario no encontrado'}), 404
#     
#     try:
#         success, result = auth_svc.update_user(user_id, role_id, password)
#         if success:
#             return jsonify({
#                 'success': True,
#                 'message': 'Usuario actualizado correctamente',
#                 'user_id': user_id
#             }), 200
#         else:
#             return jsonify({'error': 'Error actualizando usuario'}), 500
#     except Exception as e:
#         current_app.logger.exception('Error actualizando usuario')
#         return jsonify({'error': 'Error actualizando usuario'}), 500


# @devices_bp.delete('/usuarios/<int:user_id>')
# @require_roles(['admin'], sistema='dispositivos')
# def deactivate_user_admin(user_id: int):
#     """API: desactiva un usuario (desactivación: Activo = 0)"""
#     auth_svc = AuthService()
#     
#     # Verificar que el usuario existe
#     user = auth_svc.get_user_by_id(user_id)
#     if not user:
#         return jsonify({'error': 'Usuario no encontrado'}), 404
#     
#     try:
#         success, result = auth_svc.deactivate_user(user_id)
#         if success:
#             return jsonify({
#                 'success': True,
#                 'message': 'Usuario desactivado correctamente',
#                 'user_id': user_id
#             }), 200
#         else:
#             return jsonify({'error': 'Error desactivando usuario'}), 500
#     except Exception as e:
#         current_app.logger.exception('Error desactivando usuario')
#         return jsonify({'error': 'Error desactivando usuario'}), 500


# @devices_bp.get('/usuarios/desactivados')
# @require_roles(['admin'], sistema='dispositivos')
# def list_deactivated_users_api():
#     """API: lista usuarios desactivados"""
#     auth_svc = AuthService()
#     users = auth_svc.list_deactivated_users()
#     return jsonify(users)


# @devices_bp.post('/usuarios/<int:user_id>/restore')
# @require_roles(['admin'], sistema='dispositivos')
# def restore_user_api(user_id: int):
#     """API: restaura (reactiva) un usuario desactivado"""
#     auth_svc = AuthService()
#     user = auth_svc.get_user_by_id(user_id)
#     if not user:
#         return jsonify({'error': 'Usuario no encontrado'}), 404
#     try:
#         success, result = auth_svc.restore_user(user_id)
#         if success:
#             return jsonify({'success': True, 'message': 'Usuario restaurado correctamente', 'user_id': user_id}), 200
#         else:
#             return jsonify({'error': 'Error restaurando usuario'}), 500
#     except Exception as e:
#         current_app.logger.exception('Error restaurando usuario')
        return jsonify({'error': 'Error restaurando usuario'}), 500


# =============================================
# DISPOSITIVOS ELIMINADOS (SOFT DELETE)
# =============================================

@devices_bp.get('/deleted/')
@require_roles(['reporteria','operador','admin'], sistema='dispositivos')
def list_deleted_devices():
    """API: lista dispositivos eliminados"""
    svc = DeviceService()
    return jsonify(svc.list_deleted_devices())


@devices_bp.post('/deleted/<int:device_id>/restore')
@require_roles(['operador','admin'], sistema='dispositivos')
def restore_device_api(device_id: int):
    """API: restaura un dispositivo eliminado"""
    svc = DeviceService()
    try:
        svc.restore_deleted_device(device_id)
        return jsonify({
            'success': True,
            'message': 'Dispositivo restaurado correctamente'
        }), 200
    except Exception as e:
        current_app.logger.exception('Error restaurando dispositivo')
        error_msg = str(e)
        if 'no encontrado' in error_msg.lower():
            return jsonify({'error': 'Dispositivo no encontrado'}), 404
        return jsonify({'error': 'Error restaurando dispositivo'}), 500


# =============================================
# ASIGNACIONES ELIMINADAS (AUDITORÍA)
# =============================================

@devices_bp.get('/asignaciones/deleted/')
@require_roles(['admin'], sistema='dispositivos')
def list_deleted_asignaciones():
    """API: lista asignaciones cuyo dispositivo fue eliminado (solo admins)"""
    svc = DeviceService()
    return jsonify(svc.list_deleted_asignaciones())


# NOTE: Peripherals CRUD removed — functionality deprecated and UI updated.
# If you need to restore, reintroduce the endpoints and corresponding
# service methods in `DeviceService`.


# =============================================
# LECTORES DE IMPRESORAS (PLAYWRIGHT)
# =============================================

@devices_bp.post('/printers/scan')
@require_roles(['admin'], sistema='dispositivos')
def scan_printers():
    """POST: Ejecuta script Playwright para leer impresoras y guardar datos en JSON"""
    try:
        # Restringir ejecución manual fuera de la franja de las 08:00 (hora del servidor)
        # Permitir bypass si se proporciona `force` en args o en JSON body.
        now = datetime.now()
        # examine force flag in query string or JSON body
        force_flag = False
        try:
            if request.args.get('force') in ('1', 'true', 'True'):
                force_flag = True
        except Exception:
            pass
        try:
            body = request.get_json(silent=True) or {}
            if isinstance(body, dict) and body.get('force') in (True, 'true', 'True', '1'):
                force_flag = True
        except Exception:
            pass
        if now.hour != 8 and not force_flag:
            logger.info('Manual printers scan attempted outside scheduled hour; denied')
            return jsonify({'success': False, 'message': 'La ejecución manual está deshabilitada fuera de la hora programada (08:00). Si desea forzarla use el campo de confirmación.'}), 403

        from ..services.printer_reader import main as read_printers_main
        
        # Leer configuracion persistida en exports/printer_config.json si existe
        from pathlib import Path
        import json
        base_dir = Path(__file__).parent.parent.parent
        cfg_file = base_dir / 'exports' / 'printer_config.json'
        ip_dict = None
        if cfg_file.exists():
            try:
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f) or {}
                all_printers = cfg.get('printers', {})
                
                # Filtrar solo impresoras con estado=1
                ip_dict = {}
                
                # Manejar formato de lista (nuevo)
                if isinstance(all_printers, list):
                    for printer in all_printers:
                        if isinstance(printer, dict):
                            ip = printer.get('ip')
                            if ip:
                                # Si tiene campo 'estado', verificar que sea 1; si no, asumir activo
                                estado = printer.get('estado', 1)
                                if estado == 1:
                                    descripcion = printer.get('description') or printer.get('descripcion', ip)
                                    ip_dict[ip] = descripcion
                # Manejar formato de diccionario (antiguo)
                elif isinstance(all_printers, dict):
                    for ip, printer_info in all_printers.items():
                        if isinstance(printer_info, dict):
                            if printer_info.get('estado') == 1:
                                ip_dict[ip] = printer_info.get('descripcion', ip)
                        elif isinstance(printer_info, str):
                            # Formato antiguo, asumir activo
                            ip_dict[ip] = printer_info
                
                logger.info(f"Loaded {len(ip_dict)} active printers for scan (filtered by estado=1)")
            except Exception as e:
                logger.error(f"Failed to load printer config: {e}")
                ip_dict = None

        # Fallback a lista embebida si no hay config
        if not ip_dict:
            ip_dict = {
                "192.168.0.138": "Facturacion ElmigoTGU",
                "192.168.0.187": "PROIMA 1er piso TGU",
                "192.168.0.155": "Elmigo TGU",
                "192.168.0.102": "Facturacion PROIMA TGU",
                "192.168.0.29": "Contabilidad TGU",
                "192.168.0.10": "Canon color",
                "192.168.1.114": "PROIMA SPS",
                "192.168.2.202": "Elmigo SPS"
            }

        results = read_printers_main(ip_dict=ip_dict)
        
        # Calculate results summary
        total = len(results)
        success = sum(1 for r in results if r.get('status') == 'Exito')
        failed = total - success
        
        return jsonify({
            'success': True,
            'message': f'Lectura de impresoras completada: {success} exitosas, {failed} fallidas',
            'results': results,
            'summary': {
                'total': total,
                'success': success,
                'failed': failed
            }
        }), 200
    except Exception as e:
        logger.exception(f"Error al leer impresoras: {e}")
        return jsonify({
            'success': False,
            'message': f'Error al leer impresoras: {str(e)}'
        }), 500


@devices_bp.get('/printers/data')
@require_roles(['reporteria','operador','admin'], sistema='dispositivos')
def get_printer_data():
    """GET: Retorna datos de impresoras desde JSON (para cargar en campanita)"""
    try:
        from pathlib import Path
        import json
        
        base_dir = Path(__file__).parent.parent.parent
        printer_file = base_dir / "exports" / "printer_data.json"
        
        if not printer_file.exists():
            return jsonify({
                'success': True,
                'printers': [],
                'message': 'Aún no hay datos de impresoras'
            }), 200
        
        with open(printer_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify({
            'success': True,
            'printers': data.get('printers', []),
            'last_updated': data.get('last_updated')
        }), 200
    except Exception as e:
        logger.exception(f"Error al leer datos de impresoras: {e}")
        return jsonify({
            'success': False,
            'message': f'Error al leer datos: {str(e)}'
        }), 500


# =====================
# RUTAS PARA PDF DE ASIGNACIONES
# =====================
@devices_bp.get('/asignacion/<int:asignacion_id>/pdf-preview')
@require_roles(['operador','admin'], sistema='dispositivos')
def preview_entrega_pdf(asignacion_id: int):
    """API: Genera y guarda los PDFs (igual que /generate-and-upload). Retorna datos de la asignación."""
    svc = DeviceService()
    try:
        # Obtener asignación
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404

        device_id = asignacion.get('fk_id_dispositivo')
        dispositivo = svc.get_device(device_id)
        if not dispositivo:
            return jsonify({'success': False, 'message': 'Dispositivo no encontrado'}), 404

        # Obtener componentes del dispositivo (CPU, RAM, DISCO)
        componentes = svc.list_components(device_id)
        
        # Obtener plan/línea si existe
        plan_id = dispositivo.get('fk_id_plan')
        numero_linea = ''
        costo_plan = 0
        if plan_id:
            try:
                plan = svc.get_plane(plan_id)
                if plan:
                    numero_linea = plan.get('numero_linea', '')
                    costo_plan = plan.get('costo_plan', 0)
            except Exception as e:
                pass

        # Agregar datos de plan a asignación
        asignacion['numero_linea'] = numero_linea
        asignacion['costo_plan'] = costo_plan

        # Obtener empleado
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        
        if not empleado:
            return jsonify({'success': False, 'message': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        
        # EMPLEADO: nombre desde asignación
        nombre_empleado = (asignacion.get('empleado_nombre') or '').strip()
        
        # USUARIO ACTUAL: nombre y puesto desde la BD
        nombre_usuario = '[NOMBRE_USUARIO]'
        puesto_usuario = '[PUESTO]'
        if empleado_id:
            try:
                empleado_bd = svc.get_empleado(empleado_id)
                if empleado_bd:
                    nombre_usuario = (empleado_bd.get('nombre_completo') or '').strip() or '[NOMBRE_USUARIO]'
                    puesto_usuario = (empleado_bd.get('puesto') or '').strip() or '[PUESTO]'
            except Exception as e:
                pass
        
        # Tipo de dispositivo
        tipo_disp = (dispositivo.get('categoria') or dispositivo.get('tipo') or '') or ''
        
        # Extract numero_serie from device or components
        numero_serie_device = (dispositivo.get('numero_serie') or '').strip()
        if not numero_serie_device and componentes:
            for comp in componentes:
                ns = (comp.get('numero_serie') or '').strip()
                if ns:
                    numero_serie_device = ns
                    break
        
        # Obtener sistema operativo desde observaciones del componente CPU (campo [OS] en laptops)
        observaciones_so = '[OS]'
        if componentes:
            for comp in componentes:
                if comp.get('tipo_componente') == 'CPU':
                    obs = (comp.get('observaciones') or '').strip()
                    if obs:
                        observaciones_so = obs
                    break
        
        # Calcular meses usando fecha_inicio y fecha_fin del plan
        meses_str = 'N/A'
        try:
            from dateutil.relativedelta import relativedelta
            def _to_date_m(v):
                if not v: return None
                if isinstance(v, str): return datetime.fromisoformat(v).date()
                return v.date() if hasattr(v, 'date') else v
            _pi = _to_date_m(asignacion.get('plan_fecha_inicio'))
            _pf = _to_date_m(asignacion.get('plan_fecha_fin'))
            if _pi:
                if not _pf: _pf = datetime.now().date()
                _d = relativedelta(_pf, _pi)
                meses_str = f"{_d.years * 12 + _d.months} meses"
        except Exception as e:
            pass
        
        # Construir fields dict (igual que en /generate-and-upload)
        fields = {
            'NUMERO_ASIGNACION': str(asignacion_id),
            'NOMBRE_EMPLEADO': nombre_empleado,
            'IDENTIDAD_EMPLEADO': '[IDENTIDAD_EMPLEADO]',
            'IDENTIDAD_USUARIO': '[IDENTIDAD_USUARIO]',
            'NOMBRE_USUARIO': nombre_usuario or '[NOMBRE_USUARIO]',
            'PUESTO': puesto_usuario or '[PUESTO]',
            'FECHA': '',
            'MARCA': dispositivo.get('nombre_marca') or '[MARCA]',
            'MODELO': dispositivo.get('nombre_modelo') or '[MODELO]',
            'NUMERO_LINEA': numero_linea or 'N/A',
            'IMEI': dispositivo.get('imei') or '[IMEI]',
            'PROCESADOR': _get_componente_especifico(componentes, 'CPU'),
            'RAM': _get_componente_especifico(componentes, 'RAM'),
            'ALMACENAMIENTO': _get_componente_especifico(componentes, 'DISCO'),
            'OS': observaciones_so,
            'TAMANO': str(dispositivo.get('tamano') or '[TAMANO]'),
            'CARGADOR': 'Sí' if dispositivo.get('cargador') else 'No',
            'COSTO': str(costo_plan) if costo_plan else 'N/A',
            'MESES': meses_str,
            'FIRMA_USUARIO': '[FIRMA_USUARIO]',
            'FIRMA_EMPLEADO': '[FIRMA_EMPLEADO]',
        }
        
        # Only add NUMERO_SERIE and CATEGORIA if found
        if numero_serie_device:
            fields['NUMERO_SERIE'] = numero_serie_device
        if tipo_disp:
            fields['CATEGORIA'] = tipo_disp
        
        # Establecer FECHA
        try:
            fecha_inicio = asignacion.get('fecha_inicio_asignacion')
            if fecha_inicio:
                if isinstance(fecha_inicio, str):
                    fecha_inicio = datetime.fromisoformat(fecha_inicio).date()
                elif hasattr(fecha_inicio, 'date'):
                    fecha_inicio = fecha_inicio.date()
                fields['FECHA'] = fecha_inicio.strftime('%d/%m/%Y')
        except Exception as e:
            fields['FECHA'] = datetime.now().strftime('%d/%m/%Y')
        
        # NO generar ni guardar archivos aquí. Solo retornar los datos de la asignación.
        # Los archivos se generarán cuando el usuario confirme en /generate-and-upload o /download-pdf
        
        response_data = {
            'success': True,
            'asignacion': asignacion,
            'dispositivo': dispositivo,
            'empleado': empleado,
            'coordinador': {
                'nombre': 'Coordinador IT',
                'numero_identidad': '_______________'
            }
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.exception(f'Error en pdf-preview: {e}')
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


def _format_numero_linea(numero_linea_raw: str) -> str:
    """Compat: se mantiene la firma para no tocar el resto del archivo.

    Implementación delegada a `services/docx_common.py` para eliminar duplicación.
    """
    try:
        from ..services.docx_common import format_numero_linea
    except Exception:
        # fallback en caso de ejecucion fuera de paquete
        from docx_common import format_numero_linea

    return format_numero_linea(numero_linea_raw)


def _format_costo_con_moneda(costo_plan: float, moneda_plan: str) -> str:
    """Compat: se mantiene la firma para no tocar el resto del archivo.

    Implementación delegada a `services/docx_common.py` para eliminar duplicación.
    """
    try:
        from ..services.docx_common import format_costo_con_moneda
    except Exception:
        from docx_common import format_costo_con_moneda

    return format_costo_con_moneda(costo_plan, moneda_plan)


@devices_bp.post('/asignacion/<int:asignacion_id>/generate-and-upload')
@require_roles(['operador','admin'], sistema='dispositivos')
def generate_and_upload(asignacion_id: int):
    """
    FASE 5 - Genera documentos y los guarda localmente en carpeta de empleado.
    Estructura: exports/documents/YYYY/MM/CODIGO_EMPLEADO/PRO-TI-CE-00X-NNNNNN NOMBRE.docx
    """
    from ..services.docgen import DocumentGenerator
    from ..services.documento_folder_service import save_documento_to_onedrive
    
    svc = DeviceService()
    try:
        # Obtener tipo_firma del request (digital o manual)
        data = request.get_json() or {}
        tipo_firma = data.get('tipo_firma', 'digital')  # Por defecto digital para compatibilidad
        
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404

        device_id = asignacion.get('fk_id_dispositivo')
        dispositivo = svc.get_device(device_id)
        if not dispositivo:
            return jsonify({'success': False, 'message': 'Dispositivo no encontrado'}), 404

        # Obtener componentes del dispositivo (CPU, RAM, DISCO)
        componentes = svc.list_components(device_id)
        
        # Log raw device type fields for debugging visibility in server console
        try:
            for idx, comp in enumerate(componentes):
                pass
        except Exception:
            pass

        # Identidades: Ya NO se solicitan manualmente, se obtienen desde BD (campo pasaporte)
        # Firmas capturadas (base64) - solo para firma digital
        firma_usuario_b64 = request.json.get('firma_usuario') if request.is_json else None
        firma_empleado_b64 = request.json.get('firma_empleado') if request.is_json else None
        
        logger.info(f'Firmas recibidas: usuario={bool(firma_usuario_b64)}, empleado={bool(firma_empleado_b64)}')

        # Obtener ID del empleado desde la asignación
        empleado_id = asignacion.get('fk_id_empleado')
        
        # Obtener datos completos del empleado (incluyendo pasaporte)
        empleado = svc.get_empleado(empleado_id)
        if not empleado:
            try:
                # Si empleado_id parece ser un código (no numérico), intentar resolver por código
                if empleado_id and not str(empleado_id).isdigit():
                    empleado_alt = svc.get_empleado_by_codigo(str(empleado_id))
                    if empleado_alt:
                        empleado = empleado_alt
                        empleado_id = empleado.get('id_empleado') or empleado.get('IdEmpleado') or empleado.get('id')
            except Exception:
                pass

        if not empleado:
            logger.info(f'Empleado no encontrado. fk_id_empleado raw: {empleado_id!r}')
            return jsonify({'success': False, 'message': 'Empleado no encontrado', 'fk_id_empleado': empleado_id}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')

        # EMPLEADO: El nombre ya viene en asignacion['empleado_nombre'] desde get_asignacion()
        nombre_empleado = (asignacion.get('empleado_nombre') or '').strip()
        logger.info(f'Nombre del empleado desde asignacion: {nombre_empleado}')
        
        # Inicializar empleado_data (por compatibilidad con codigo_emp)
        empleado_data = {'nombre_completo': nombre_empleado}

        # Build fields dict expected by docexp
        try:
            from admin_disp.services import docexp as de
        except Exception:
            de = None

        # IDENTIDAD_EMPLEADO: Obtener pasaporte desde BD
        identidad_empleado_field = (empleado.get('pasaporte') or '').strip()
        if not identidad_empleado_field:
            # Si pasaporte está vacío, solicitar modal (devolver error especial)
            logger.warning(f'Pasaporte del empleado {empleado_id} está vacío')
            return jsonify({
                'success': False, 
                'message': 'Pasaporte del empleado no registrado',
                'requiere_pasaporte': True,
                'empleado_id': empleado_id,
                'empleado_nombre': nombre_empleado
            }), 400
        
        # USUARIO ACTUAL: nombre y puesto desde la BD usando fk_id_empleado del usuario, NO del empleado de la asignación
        nombre_usuario = '[NOMBRE_USUARIO]'
        puesto_usuario = '[PUESTO]'
        identidad_usuario_field = '[IDENTIDAD_USUARIO]'  # Default si no tiene empleado vinculado
        
        # Obtener usuario actual (quien está logueado)
        current_user = None
        try:
            from flask import session
            if 'user_id' in session:
                cur_emp = get_db_empleados().get_cursor()
                cur_emp.execute("SELECT id_usuario, fk_id_empleado FROM empleados.dbo.usuarios WHERE id_usuario = ?", (session['user_id'],))
                user_row = cur_emp.fetchone()
                if user_row:
                    current_user = {'id_usuario': user_row[0], 'fk_id_empleado': user_row[1]}
                cur_emp.close()
        except Exception as e:
            logger.warning(f'Error obteniendo usuario actual: {e}')
        
        # Si el usuario tiene fk_id_empleado, obtener nombre, puesto y pasaporte del empleado vinculado
        if current_user and current_user.get('fk_id_empleado'):
            try:
                empleado_bd = svc.get_empleado(current_user['fk_id_empleado'])
                if empleado_bd:
                    nombre_usuario = (empleado_bd.get('nombre_completo') or '').strip() or '[NOMBRE_USUARIO]'
                    puesto_usuario = (empleado_bd.get('puesto') or '').strip() or '[PUESTO]'
                    # Obtener pasaporte del usuario
                    pasaporte_usuario = (empleado_bd.get('pasaporte') or '').strip()
                    if pasaporte_usuario:
                        identidad_usuario_field = pasaporte_usuario
                    else:
                        # Si usuario logueado no tiene pasaporte, solicitar modal
                        logger.warning(f'Pasaporte del usuario {current_user["fk_id_empleado"]} está vacío')
                        return jsonify({
                            'success': False,
                            'message': 'Pasaporte del usuario no registrado', 
                            'requiere_pasaporte_usuario': True,
                            'usuario_id': current_user['fk_id_empleado'],
                            'usuario_nombre': nombre_usuario
                        }), 400
            except Exception as e:
                logger.exception(f'Error extrayendo datos del empleado vinculado al usuario: {e}')
        # Si NO tiene fk_id_empleado (como admin), dejar [IDENTIDAD_USUARIO] tal cual
        
        # Número de línea - desde asignación (que ahora obtiene del plan en BD)
        numero_linea_raw = ''
        if asignacion:
            numero_linea_raw = (asignacion.get('numero_linea') or '').strip()
        
        # Formatear número de línea
        numero_linea = _format_numero_linea(numero_linea_raw) if numero_linea_raw else 'N/A'
        
        # Costo con moneda
        costo_plan_value = asignacion.get('costo_plan') if asignacion else None
        moneda_plan_value = asignacion.get('moneda_plan') if asignacion else 'L'
        costo_formateado = _format_costo_con_moneda(costo_plan_value, moneda_plan_value)
        
        # Tipo de dispositivo
        tipo_disp = (dispositivo.get('categoria') or dispositivo.get('tipo') or '') or ''
        
        # Extract numero_serie from device or components
        numero_serie_device = (dispositivo.get('numero_serie') or '').strip()
        if not numero_serie_device and componentes:
            for comp in componentes:
                ns = (comp.get('numero_serie') or '').strip()
                if ns:
                    numero_serie_device = ns
                    break
        
        logger.info(f'[NUMERO_SERIE] Dispositivo ID {dispositivo.get("id_dispositivo")}: numero_serie="{numero_serie_device}"')
        logger.info(f'[CATEGORIA] Dispositivo ID {dispositivo.get("id_dispositivo")}: tipo_disp="{tipo_disp}"')
        
        # Calcular meses usando fecha_inicio y fecha_fin del plan
        meses_str = 'N/A'
        try:
            from dateutil.relativedelta import relativedelta
            def _to_date_m(v):
                if not v: return None
                if isinstance(v, str): return datetime.fromisoformat(v).date()
                return v.date() if hasattr(v, 'date') else v
            _pi = _to_date_m(asignacion.get('plan_fecha_inicio'))
            _pf = _to_date_m(asignacion.get('plan_fecha_fin'))
            if _pi:
                if not _pf: _pf = datetime.now().date()
                _d = relativedelta(_pf, _pi)
                meses_str = f"{_d.years * 12 + _d.months} meses"
                logger.info(f'[MESES] plan {_pi} -> {_pf} = {meses_str}')
        except Exception as e:
            logger.warning(f'[MESES] Error calculando meses: {e}')
        
        # Obtener sistema operativo desde observaciones del componente CPU (campo [OS] en laptops)
        observaciones_so = '[OS]'
        if componentes:
            for comp in componentes:
                if comp.get('tipo_componente') == 'CPU':
                    obs = (comp.get('observaciones') or '').strip()
                    if obs:
                        observaciones_so = obs
                    break
        
        # DEBUG: Log completo de dispositivo y componentes
        logger.info(f"===== DEBUG DISPOSITIVO {device_id} =====")
        logger.info(f"dispositivo KEYS: {list(dispositivo.keys())}")
        logger.info(f"dispositivo.tamano = {dispositivo.get('tamano')}")
        logger.info(f"dispositivo.cargador = {dispositivo.get('cargador')}")
        logger.info(f"Total componentes: {len(componentes)}")
        for idx, comp in enumerate(componentes):
            logger.info(f"Componente {idx}: tipo={comp.get('tipo_componente')}, marca={comp.get('nombre_marca')}, modelo={comp.get('nombre_modelo')}, capacidad={comp.get('capacidad')}")
        
        procesador_val = _get_componente_especifico(componentes, 'CPU')
        ram_val = _get_componente_especifico(componentes, 'RAM')
        almacenamiento_val = _get_componente_especifico(componentes, 'DISCO')
        
        logger.info(f"PROCESADOR calculado: {procesador_val}")
        logger.info(f"RAM calculado: {ram_val}")
        logger.info(f"ALMACENAMIENTO calculado: {almacenamiento_val}")
        logger.info(f"===== FIN DEBUG =====")
        
        fields = {
            'NUMERO_ASIGNACION': str(asignacion_id),
            'NOMBRE_EMPLEADO': nombre_empleado,
            'IDENTIDAD_EMPLEADO': identidad_empleado_field,
            'IDENTIDAD_USUARIO': identidad_usuario_field,
            'NOMBRE_USUARIO': nombre_usuario or '[NOMBRE_USUARIO]',
            # NO agregar PUESTO si es '[PUESTO]' - dejar sin reemplazar
            # 'PUESTO': puesto_usuario or '[PUESTO]',
            'FECHA': '',
            'MARCA': dispositivo.get('nombre_marca') or '[MARCA]',
            'MODELO': dispositivo.get('nombre_modelo') or '[MODELO]',
            'NUMERO_LINEA': numero_linea,
            'IMEI': dispositivo.get('imei') or '[IMEI]',
            'PROCESADOR': procesador_val,
            'RAM': ram_val,
            'ALMACENAMIENTO': almacenamiento_val,
            'OS': observaciones_so,
            'TAMANO': str(dispositivo.get('tamano') or '[TAMANO]'),
            'CARGADOR': 'Sí' if dispositivo.get('cargador') else 'No',
            'COSTO': costo_formateado,
            'MESES': meses_str,
        }
        
        # Solo agregar placeholders de firma si es firma digital
        # En firma manual, NO incluir estos campos para que se eliminen del documento
        if tipo_firma == 'digital':
            fields['FIRMA_USUARIO'] = '[FIRMA_USUARIO]'
            fields['FIRMA_EMPLEADO'] = '[FIRMA_EMPLEADO]'
        else:
            # En modo manual, NO incluir estos campos (se eliminarán del documento)
            logger.info('Modo manual: campos de firma NO incluidos (se eliminarán del documento)')
        
        # Only add NUMERO_SERIE, SERVICE_TAG, IDENTIFICADOR and CATEGORIA if found
        if numero_serie_device:
            fields['NUMERO_SERIE'] = numero_serie_device
            fields['SERVICE_TAG'] = numero_serie_device
        if tipo_disp:
            fields['CATEGORIA'] = tipo_disp
        
        # Agregar IDENTIFICADOR (si no existe, agregar vacío para eliminar placeholder)
        identificador_device = (dispositivo.get('identificador') or '').strip()
        fields['IDENTIFICADOR'] = identificador_device  # Siempre agregar, incluso si está vacío
        if identificador_device:
            logger.info(f'IDENTIFICADOR agregado: {identificador_device}')
        else:
            logger.info('IDENTIFICADOR vacío - placeholder se eliminará del documento')
        
        # Agregar PUESTO solo si tiene valor real (no '[PUESTO]')
        if puesto_usuario and puesto_usuario != '[PUESTO]':
            fields['PUESTO'] = puesto_usuario
        
        # Asignar CORRELATIVO usando el nuevo sistema de formatos
        from .correlativo_helper import obtener_o_generar_correlativo, extraer_numero_correlativo
        
        try:
            cur_corr = svc.conn.get_cursor()
            cur_corr.execute("SELECT correlativo FROM asignacion WITH (UPDLOCK, HOLDLOCK) WHERE id_asignacion = ?", (asignacion_id,))
            row_corr = cur_corr.fetchone()
            correlativo_actual = row_corr[0] if row_corr else None
            cur_corr.close()
            
            # Obtener la categoría del dispositivo
            categoria = dispositivo.get('categoria', '').strip()
            if not categoria:
                raise Exception(f"No se pudo determinar la categoría del dispositivo para asignación {asignacion_id}")
            
            # Obtener o generar el correlativo usando el nuevo sistema
            correlativo_completo = obtener_o_generar_correlativo(
                svc.conn, 
                asignacion_id, 
                categoria, 
                correlativo_actual
            )
            
            if not correlativo_completo:
                raise Exception('No se pudo generar correlativo con el nuevo sistema')
            
            # Extraer solo el número de 6 dígitos para el campo CORRELATIVO en el documento
            fields['CORRELATIVO'] = extraer_numero_correlativo(correlativo_completo)
            logger.info(f'Correlativo asignado para asignacion {asignacion_id}: {correlativo_completo} (número: {fields["CORRELATIVO"]})')
            
        except Exception as e:
            logger.exception('Error asignando correlativo desde la BD')
            return jsonify({'success': False, 'message': 'No se pudo asignar correlativo desde la base de datos', 'detail': str(e)}), 500
        
        # Establecer FECHA desde fecha_inicio_asignacion si existe
        try:
            fecha_inicio = asignacion.get('fecha_inicio_asignacion')
            if fecha_inicio:
                if isinstance(fecha_inicio, str):
                    fecha_inicio = datetime.fromisoformat(fecha_inicio).date()
                elif hasattr(fecha_inicio, 'date'):
                    fecha_inicio = fecha_inicio.date()
                fields['FECHA'] = fecha_inicio.strftime('%d/%m/%Y')
        except Exception as e:
            logger.warning(f'Error formateando fecha_inicio_asignacion: {e}')
            fields['FECHA'] = datetime.now().strftime('%d/%m/%Y')
        
        logger.info(f'Fields dict completo: {fields}')

        # Usar docgen/docexp para generar documentos
        if de is not None:
            import base64
            
            # Decodificar firmas si existen (bytes puros, sin BytesIO)
            images_map = None
            if firma_usuario_b64 or firma_empleado_b64:
                images_map = {}
                if firma_usuario_b64:
                    try:
                        img_data = base64.b64decode(firma_usuario_b64.split(',')[-1])
                        images_map['FIRMA_USUARIO'] = img_data  # bytes directamente
                    except Exception as e:
                        logger.exception(f'Error decodificando firma_usuario: {e}')
                if firma_empleado_b64:
                    try:
                        img_data = base64.b64decode(firma_empleado_b64.split(',')[-1])
                        images_map['FIRMA_EMPLEADO'] = img_data  # bytes directamente
                    except Exception as e:
                        logger.exception(f'Error decodificando firma_empleado: {e}')
            
            # Generar documentos EN MEMORIA
            if tipo_disp == 'Celular':
                result = de.export_celular(fields, images_map=images_map)
            elif tipo_disp == 'Laptop':
                result = de.export_laptop(fields, images_map=images_map)
            elif tipo_disp == 'Tablet':
                result = de.export_tablet(fields, images_map=images_map)
            elif tipo_disp in ['Auricular', 'Auriculares', 'Teclado', 'Ratón', 'Monitor', 'Impresora', 'VoIP', 'Router', 'Switch']:
                result = de.export_periferico(fields, images_map=images_map)
            else:
                result = de.export_periferico(fields, images_map=images_map)
            
            # ========================================================
            # FASE 5 - GUARDAR DOCUMENTOS LOCALMENTE + CONVERTIR A PDF
            # ========================================================
            
            # DEBUG: Ver qué documentos se generaron
            logger.info(f'tipo_disp={tipo_disp}, result.files contiene {len(result.files)} documentos')
            for idx, doc_file in enumerate(result.files):
                logger.info(f'  Documento {idx+1}: {doc_file.name} ({len(doc_file.content)} bytes)')
            
            fecha_actual = datetime.now().date()
            year = fecha_actual.year
            month = fecha_actual.month
            
            # Variables para tracking de archivos generados y errores
            archivos_generados = []
            errores = []
            output_docx_dir = None
            
            try:
                for idx, doc_file in enumerate(result.files, 1):
                    logger.info(f'\n=== Procesando documento {idx}/{len(result.files)}: {doc_file.name} ===')

                    # Extraer prefix y descripción para construir nombre de archivo con correlativo
                    filename = doc_file.name.replace('.docx', '').replace('.docm', '')
                    import re
                    match = re.match(r'(PRO-TI-CE-\d+)-[\d#]+\s+(.+)$', filename)

                    if not match:
                        error_msg = f'No se pudo parsear nombre de documento: {doc_file.name}'
                        errores.append(error_msg)
                        logger.error(error_msg)
                        continue

                    documento_prefix = match.group(1)
                    documento_tipo = match.group(2)

                    # Obtener bytes del contenido
                    file_content = doc_file.content
                    if isinstance(file_content, bytes):
                        content_bytes = file_content
                    elif hasattr(file_content, 'getvalue'):
                        content_bytes = file_content.getvalue()
                    elif hasattr(file_content, 'read'):
                        file_content.seek(0)
                        content_bytes = file_content.read()
                    else:
                        error_msg = f'Tipo de contenido no soportado: {type(file_content).__name__}'
                        errores.append(error_msg)
                        logger.error(error_msg)
                        continue

                    logger.info(f'  Convirtiendo {doc_file.name} a PDF en memoria')
                    # Convertir a PDF en un tmp file y leer bytes
                    import tempfile
                    try:
                        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_docx:
                            tmp_docx.write(content_bytes)
                            tmp_docx_path = tmp_docx.name

                        tmp_pdf_path = tmp_docx_path.replace('.docx', '.pdf')
                        pdf_path = de.convert_docx_to_pdf(tmp_docx_path, tmp_pdf_path)

                        if pdf_path and os.path.exists(pdf_path):
                            with open(pdf_path, 'rb') as f:
                                pdf_bytes = f.read()

                            # Construir nombre final que incluya correlativo (6 dígitos)
                            correlativo_str = fields.get('CORRELATIVO') or str(0).zfill(6)
                            pdf_filename = f"{documento_prefix}-{correlativo_str} {documento_tipo}.pdf"

                            logger.info(f'  Subiendo PDF a OneDrive: {pdf_filename} ({len(pdf_bytes)} bytes)')
                            success, url, error = save_documento_to_onedrive(codigo_empleado, pdf_filename, pdf_bytes)

                            if success:
                                from flask import url_for
                                local_url = url_for('devices.get_documento', asignacion_id=asignacion_id, filename=pdf_filename, _external=True)
                                archivos_generados.append({'nombre': pdf_filename, 'url': local_url})
                                onedrive_logger.info(f'PDF subido exitosamente: {pdf_filename}')
                            else:
                                errores.append(f'Error subiendo {pdf_filename}: {error}')
                                onedrive_logger.error(f'Error subiendo {pdf_filename}: {error}')

                        else:
                            errores.append(f'Error convirtiendo {doc_file.name} a PDF')

                    except Exception as ex:
                        logger.exception(f'Error procesando documento {doc_file.name}: {ex}')
                        errores.append(f'Error en {doc_file.name}: {str(ex)}')
                    finally:
                        # Limpiar temporales
                        try:
                            if 'tmp_docx_path' in locals() and os.path.exists(tmp_docx_path):
                                os.unlink(tmp_docx_path)
                            if 'tmp_pdf_path' in locals() and os.path.exists(tmp_pdf_path):
                                os.unlink(tmp_pdf_path)
                        except Exception:
                            pass

                logger.info(f'RESUMEN: {len(archivos_generados)} archivos subidos a OneDrive, {len(errores)} errores')

            except Exception as e:
                error_msg = f'Error en el flujo de generación: {str(e)}'
                errores.append(error_msg)
                logger.exception(error_msg)
            
            # Actualizar estado de documentación
            svc.update_asignacion_estado_doc(asignacion_id, 'generada')

            # Registrar descarga automática: incrementar contador y actualizar marca de tiempo
            try:
                svc.record_download(asignacion_id)
                logger.info(f'Automatic download record updated for asignacion {asignacion_id}')
            except Exception:
                logger.exception('Failed to record automatic download for asignacion')

            # Respuesta: usar los archivos subidos a OneDrive
            if archivos_generados:
                logger.info(f'Asignación {asignacion_id}: {len(archivos_generados)} archivos subidos a OneDrive')
                return jsonify({
                    'success': True,
                    'message': f'{len(archivos_generados)} documento(s) generados y subidos a OneDrive',
                    'asignacion_id': asignacion_id,
                    'files_saved': archivos_generados,
                    'errors': errores if errores else None
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'No se pudieron generar ni subir los documentos',
                    'errors': errores
                }), 500
        else:
            # docexp módulo no disponible
            logger.error('docexp module not available')
            return jsonify({'success': False, 'message': 'Document generation module not available'}), 500

    except Exception as e:
        logger.exception(f'Error en generate-and-upload: {e}')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


# =====================================================
# FASE 3 - ENDPOINTS DE DOCUMENTACIÓN (Digital/Manual)
# =====================================================

@devices_bp.post('/asignacion/<int:asignacion_id>/documentacion/seleccionar-tipo')
@require_roles(['operador','admin'], sistema='dispositivos')
def seleccionar_tipo_documentacion(asignacion_id: int):
    """
    Selecciona el tipo de documentación: digital o manual
    También obtiene y guarda el CORRELATIVO en este punto
    
    POST body:
    {
        "tipo": "digital" | "manual"
    }
    """
    from ..services.documento_folder_service import get_documento_folder_path
    svc = DeviceService()
    
    try:
        data = request.get_json(force=True)
        tipo = data.get('tipo', '').lower()
        
        if tipo not in ['digital', 'manual']:
            return jsonify({'success': False, 'error': 'Tipo de documentación inválido'}), 400
        
        # Obtener asignación
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'error': 'Asignación no encontrada'}), 404
        
        # Obtener y guardar CORRELATIVO usando el nuevo sistema de formatos
        from .correlativo_helper import obtener_o_generar_correlativo, extraer_numero_correlativo
        
        correlativo_str = None
        try:
            db = get_db_main()
            cur_corr = db.get_cursor()
            
            # Verificar estado_documentacion y si ya existe CORRELATIVO
            cur_corr.execute("SELECT estado_documentacion, correlativo FROM dbo.asignacion WHERE id_asignacion = ?", (asignacion_id,))
            row = cur_corr.fetchone()
            
            if row:
                estado_doc = row[0]
                correlativo_actual = row[1]
                
                if correlativo_actual:
                    # Ya tiene CORRELATIVO - extraer el número para display
                    correlativo_str = extraer_numero_correlativo(correlativo_actual)
                elif estado_doc == 0:
                    # Solo asignar si estado_documentacion es 0 (inicial)
                    # Obtener categoría del dispositivo
                    dispositivo = svc.get_dispositivo(asignacion.get('fk_id_dispositivo'))
                    if dispositivo:
                        categoria = dispositivo.get('categoria', '').strip()
                        if categoria:
                            # Generar nuevo CORRELATIVO con formato completo
                            correlativo_completo = obtener_o_generar_correlativo(
                                db, 
                                asignacion_id, 
                                categoria, 
                                None
                            )
                            
                            if correlativo_completo:
                                correlativo_str = extraer_numero_correlativo(correlativo_completo)
                                logger.info(f'Asignación {asignacion_id}: Generado CORRELATIVO = {correlativo_completo} (display: {correlativo_str})')
                            else:
                                logger.error(f'No se pudo generar correlativo para asignación {asignacion_id}')
                        else:
                            logger.error(f'No se pudo obtener categoría del dispositivo para asignación {asignacion_id}')
                    else:
                        logger.error(f'No se pudo obtener dispositivo para asignación {asignacion_id}')
                else:
                    logger.warning(f'Asignación {asignacion_id}: Estado documentación es {estado_doc}, no es 0. No se asigna CORRELATIVO.')
            else:
                logger.error(f'Asignación {asignacion_id} no encontrada en BD')
            
            cur_corr.close()
        except Exception as e:
            logger.exception(f'Error obteniendo/guardando CORRELATIVO en seleccionar-tipo para asignación {asignacion_id}: {e}')
        
        # Actualizar estado en BD
        fecha_actual = datetime.now().date()
        updated = svc.update_asignacion_estado_doc(asignacion_id, tipo)
        
        if updated:
            logger.info(f"Asignación {asignacion_id}: Tipo de documentación seleccionado = {tipo}")
            return jsonify({
                'success': True,
                'message': f'Tipo de documentación seleccionado: {tipo}',
                'asignacion_id': asignacion_id,
                'tipo': tipo,
                'correlativo': correlativo_str
            }), 200
        else:
            return jsonify({'success': False, 'error': 'No se pudo actualizar el estado'}), 500
            
    except Exception as e:
        logger.exception(f'Error seleccionando tipo de documentación: {e}')
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500


@devices_bp.post('/asignacion/<int:asignacion_id>/documentacion/upload-firmas')
@require_roles(['operador','admin'], sistema='dispositivos')
def upload_firmas_manual(asignacion_id: int):
    """
    Carga archivos de firmas manualmente (flujo manual)
    
    Form-data:
        - firma_responsable: archivo PDF
        - firma_empleado: archivo PDF
    """
    from ..services.documento_folder_service import save_firma_file
    from werkzeug.utils import secure_filename
    
    svc = DeviceService()
    
    try:
        # Obtener asignación y empleado
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'error': 'Asignación no encontrada'}), 404
        
        empleado_id = asignacion.get('fk_id_empleado')
        
        # Obtener código del empleado
        empleado = svc.get_empleado(empleado_id)
        if not empleado:
            return jsonify({'success': False, 'error': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        
        # Datos de carpeta
        fecha_actual = datetime.now().date()
        year = fecha_actual.year
        month = fecha_actual.month
        
        # Validar archivos
        if 'firma_responsable' not in request.files or 'firma_empleado' not in request.files:
            return jsonify({'success': False, 'error': 'Faltan archivos de firma'}), 400
        
        firma_responsable = request.files.get('firma_responsable')
        firma_empleado = request.files.get('firma_empleado')
        
        if not firma_responsable or not firma_empleado:
            return jsonify({'success': False, 'error': 'Archivos de firma vacíos'}), 400
        
        # Validar extensión
        allowed_ext = {'pdf', 'png', 'jpg', 'jpeg'}
        
        def allowed_file(filename):
            return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_ext
        
        if not allowed_file(firma_responsable.filename) or not allowed_file(firma_empleado.filename):
            return jsonify({'success': False, 'error': 'Archivos deben ser PDF, PNG o JPG'}), 400
        
        # Guardar firmas
        responsable_ok, resp_path, resp_err = save_firma_file(
            year, month, codigo_empleado, 'responsable',
            firma_responsable.read(),
            secure_filename(firma_responsable.filename)
        )
        
        empleado_ok, emp_path, emp_err = save_firma_file(
            year, month, codigo_empleado, 'empleado',
            firma_empleado.read(),
            secure_filename(firma_empleado.filename)
        )
        
        if not responsable_ok or not empleado_ok:
            error_msg = resp_err or emp_err or 'Error desconocido'
            return jsonify({'success': False, 'error': error_msg}), 500
        
        # Actualizar estado a 'firmada'
        svc.update_asignacion_estado_doc(asignacion_id, 'firmada')
        
        return jsonify({
            'success': True,
            'message': 'Firmas cargadas exitosamente',
            'asignacion_id': asignacion_id,
            'firma_responsable': resp_path,
            'firma_empleado': emp_path
        }), 200
        
    except Exception as e:
        logger.exception(f'Error cargando firmas: {e}')
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500


@devices_bp.get('/asignacion/<int:asignacion_id>/documentacion/estado')
@require_roles(['operador','admin'], sistema='dispositivos')
def get_documentacion_estado(asignacion_id: int):
    """Obtiene el estado actual de la documentación de una asignación"""
    svc = DeviceService()
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'error': 'Asignación no encontrada'}), 404
        
        estado = asignacion.get('estado_documentacion', 'pendiente')
        
        return jsonify({
            'success': True,
            'asignacion_id': asignacion_id,
            'estado_documentacion': estado
        }), 200
        
    except Exception as e:
        logger.exception(f'Error obteniendo estado de documentación: {e}')
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

@devices_bp.post('/asignacion/<int:asignacion_id>/revision')
@require_roles(['operador','admin'], sistema='dispositivos')
def guardar_revision_archivos(asignacion_id: int):
    """Guarda revisión de archivos en log_revision.log"""
    svc = DeviceService()
    from admin_disp.services.documento_folder_service import write_revision_log
    from datetime import datetime
    
    try:
        data = request.get_json() or {}
        archivos_aprobados = data.get('archivos_aprobados', [])
        usuario = data.get('usuario', 'sin_usuario')
        observaciones = data.get('observaciones', '')
        
        # Obtener asignación
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'error': 'Asignación no encontrada'}), 404
        
        # Obtener empleado para código
        emp_id = asignacion.get('fk_id_empleado')
        empleados = svc.list_empleados()
        empleado = next((e for e in empleados if int(e.get('id_empleado', 0)) == int(emp_id or 0)), None)
        
        if not empleado:
            return jsonify({'success': False, 'error': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado', 'DESCONOCIDO')
        
        # Escribir log
        year = datetime.now().year
        month = datetime.now().month
        success, log_path, error = write_revision_log(year, month, codigo_empleado, usuario, archivos_aprobados, observaciones)
        
        if not success:
            return jsonify({'success': False, 'error': error}), 500
        
        # Actualizar estado a 23 (pendiente aprobación) o 24 (aprobado)
        # Por ahora marcar como revisado
        svc.update_asignacion_estado_doc(asignacion_id, 23)
        
        return jsonify({
            'success': True,
            'message': 'Revisión guardada correctamente',
            'log_path': log_path
        }), 200
        
    except Exception as e:
        logger.exception(f'Error guardando revisión: {e}')
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500


@devices_bp.post('/asignacion/<int:asignacion_id>/confirmar-final')
@require_roles(['operador','admin'], sistema='dispositivos')
def confirmar_documentacion_final(asignacion_id: int):
    """Confirma documentación y cambia estado a 90 (exitosa)"""
    svc = DeviceService()
    
    try:
        # Verificar asignación
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'error': 'Asignación no encontrada'}), 404
        
        # Cambiar estado a 90 (completada/exitosa)
        svc.update_asignacion_estado_doc(asignacion_id, 90)
        
        return jsonify({
            'success': True,
            'message': 'Documentación confirmada exitosamente',
            'nuevo_estado': 90
        }), 200
        
    except Exception as e:
        logger.exception(f'Error confirmando documentación: {e}')
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500


# ============================================================================
# ENDPOINT DE DIAGNÓSTICO (sin autenticación)
# ============================================================================

@devices_bp.get('/diagnosis/health')
@require_roles(['reporteria','operador','admin','auditor'], sistema='dispositivos')
def diagnosis_health():
    """Endpoint de diagnóstico para verificar que el servidor responde."""
    return jsonify({
        'status': 'ok',
        'message': 'Servidor respondiendo correctamente',
        'timestamp': datetime.now().isoformat(),
        'session_user': session.get('user_id'),
        'session_roles': session.get('roles', [])
    }), 200


# ============================================================================
# HELPER: Determinar cantidad de documentos esperados por categoría
# ============================================================================

def _get_expected_docs_count(categoria: str) -> int:
    """
    Retorna la cantidad de documentos esperados según la categoría del dispositivo.
    
    - Celular: 3 documentos (CE-001, CE-002, CE-003)
    - Laptop: 1 documento (CE-004)
    - Tablet: 1 documento (CE-006)
    - Periférico: 1 documento (CE-005)
    """
    categoria_lower = (categoria or '').lower().strip()
    
    if categoria_lower == 'celular':
        return 3
    elif categoria_lower == 'laptop':
        return 1
    elif categoria_lower == 'tablet':
        return 1
    elif categoria_lower in ['teclado', 'mouse', 'auriculares', 'monitor', 'impresora', 
                              'teléfono voip', 'telefono voip', 'router', 'switch']:
        return 1
    else:
        # Por defecto, asumimos 1 documento
        return 1

# ============================================================================
# NUEVOS ENDPOINTS - SISTEMA DE DOCUMENTACIÓN CON ESTADOS
# Basado en doc/proceso.txt
# TODO: Deprecar y eliminar /generate-and-upload cuando este sistema esté completo
# ============================================================================

@devices_bp.post('/asignacion/<int:asignacion_id>/generate-documentation')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def generate_documentation(asignacion_id: int):
    """
    PASO B1/C1: Genera documentos base (sin firmas) y los sube a OneDrive.
    
    Input: { tipo_firma: "digital" | "manual" }
    Output: { success, estado, archivos: [...] }
    
    Estados:
    - tipo_firma="digital" → cambiar a estado 11
    - tipo_firma="manual" → cambiar a estado 21
    - En caso de error → estado 110 o 210 respectivamente
    
    Nota: Las identidades se obtienen automáticamente desde el campo pasaporte en BD.
    """
    from admin_disp.core.db import get_db_main
    svc = DeviceService()
    db = get_db_main()
    
    _write_asignaciones_log(f'[generate-documentation] INICIO asignacion={asignacion_id}')
    
    try:
        data = request.get_json() or {}
        tipo_firma = data.get('tipo_firma')  # 'digital' o 'manual'
        observaciones_payload = data.get('observaciones', {})  # Diccionario con OBSERVACION1 y OBSERVACION2 (solo para celulares)
        
        # Validaciones
        if tipo_firma not in ['digital', 'manual']:
            _write_asignaciones_log(f'[generate-documentation] asignacion={asignacion_id} invalid tipo_firma: {tipo_firma}')
            return jsonify({'success': False, 'message': 'tipo_firma debe ser "digital" o "manual"'}), 400
        
        # Obtener asignación
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            _write_asignaciones_log(f'[generate-documentation] asignacion={asignacion_id} no encontrada')
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        # Log con información de categoría (asignacion es un diccionario)
        categoria = asignacion.get('categoria', 'unknown')
        _write_asignaciones_log(f'[generate-documentation] asignacion={asignacion_id} tipo_firma={tipo_firma} categoria={categoria} observaciones={observaciones_payload}')
        
        # Obtener dispositivo temprano para conocer la categoría
        device_id = asignacion.get('fk_id_dispositivo')
        dispositivo = svc.get_device(device_id)
        if not dispositivo:
            return jsonify({'success': False, 'message': 'Dispositivo no encontrado'}), 404
        
        # Obtener categoría para determinar cantidad de documentos esperados
        categoria_dispositivo = dispositivo.get('categoria') or dispositivo.get('tipo') or ''
        expected_docs_count = _get_expected_docs_count(categoria_dispositivo)
        gendocu_logger.info(f'Categoría: {categoria_dispositivo}, documentos esperados: {expected_docs_count}')
        
        # Obtener empleado AHORA (lo usaremos para todas las verificaciones)
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        if not empleado:
            _write_asignaciones_log(f'[generate-documentation] asignacion={asignacion_id} empleado_id={empleado_id} no encontrado')
            return jsonify({'success': False, 'message': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        if not codigo_empleado:
            _write_asignaciones_log(f'[generate-documentation] asignacion={asignacion_id} empleado_id={empleado_id} sin codigo_empleado')
            return jsonify({'success': False, 'message': 'Código de empleado no disponible'}), 404
        
        # ====================================================================
        # VERIFICAR ESTADO: Si ya está en 11 o 21, NO regenerar
        # ====================================================================
        estado_actual = asignacion.get('estado_documentacion', 0)
        if estado_actual in [11, 21]:
            # Ya fue generada. Solo retornar los archivos existentes
            gendocu_logger.info(f'Asignación en estado {estado_actual}. Buscando archivos existentes.')
            
            correlativo_value = asignacion.get('correlativo')
            correlativo_str = str(correlativo_value).zfill(6) if correlativo_value is not None else '000000'
            gendocu_logger.info(f'[ESTADO-CHECK] Correlativo obtenido de asignacion: {correlativo_value} -> {correlativo_str}')
            
            try:
                from admin_disp.services.documento_folder_service import list_documentos_from_onedrive
                success, documentos_existentes, error = list_documentos_from_onedrive(codigo_empleado)

                if success and documentos_existentes:
                    # Filtrar documentos que contengan el CORRELATIVO en el nombre
                    docs_con_correlativo = filter_documents_by_correlativos(documentos_existentes, [correlativo_str])
                    gendocu_logger.info(f'{len(docs_con_correlativo)} documentos encontrados con correlativo {correlativo_str}')
                    for doc in docs_con_correlativo:
                        gendocu_logger.info(f'  - {doc.get("name")}')

                    # Si encontramos archivos con el correlativo, retornarlos.
                    if docs_con_correlativo:
                        from flask import url_for
                        archivos_formateados = [
                            {
                                'nombre': doc.get('name', 'Documento'),
                                'url': url_for('devices.get_documento', asignacion_id=asignacion_id, filename=doc.get('name'), _external=True),
                                'download_url': doc.get('download_url', ''),
                                'size': doc.get('size', 0),
                                'id': doc.get('id', doc.get('name', ''))
                            }
                            for doc in docs_con_correlativo
                        ]
                        return jsonify({
                            'success': True,
                            'archivos_existen': True,
                            'message': 'Los documentos ya fueron generados',
                            'archivos': archivos_formateados,
                            'raw_documentos': [d.get('name') for d in documentos_existentes],
                            'correlativo': correlativo_str,
                            'estado': estado_actual
                        }), 200

                    # FALLBACK: No se halló correlativo en los nombres.
                    # Si el correlativo de la asignación es el valor por defecto '000000',
                    # no devolvemos todos los PDFs para evitar mezclar correlativos distintos.
                    if correlativo_str == '000000':
                        from flask import url_for
                        return jsonify({
                            'success': True,
                            'archivos_existen': False,
                            'message': 'Correlativo no disponible en la asignación; no se mostrarán archivos.',
                            'archivos': [],
                            'raw_documentos': [d.get('name') for d in documentos_existentes],
                            'correlativo': correlativo_str,
                            'estado': estado_actual
                        }), 200

                    from flask import url_for
                    archivos_todos = [
                        {
                            'nombre': doc.get('name', 'Documento'),
                            'url': url_for('devices.get_documento', asignacion_id=asignacion_id, filename=doc.get('name'), _external=True)
                        }
                        for doc in documentos_existentes
                    ]
                    return jsonify({
                        'success': True,
                        'archivos_existen': True,
                        'message': 'No se encontró correlativo en nombres; mostrando archivos existentes',
                        'archivos': archivos_todos,
                        'raw_documentos': [d.get('name') for d in documentos_existentes],
                        'correlativo': correlativo_str,
                        'estado': estado_actual
                    }), 200
            except Exception as e:
                gendocu_logger.warning(f'Error listando documentos existentes: {e}')
                return jsonify({'success': False, 'message': 'Error al obtener documentos existentes'}), 500
        
        # ====================================================================
        # VERIFICAR SI DOCUMENTOS YA EXISTEN (incluso si estado es 0)
        # ====================================================================
        correlativo_value = asignacion.get('correlativo')
        correlativo_str = str(correlativo_value).zfill(6) if correlativo_value is not None else '000000'
        gendocu_logger.info(f'Asignación {asignacion_id}: Estado {estado_actual}, verificando si documentos ya existen con CORRELATIVO {correlativo_str}')
        
        try:
            from admin_disp.services.documento_folder_service import list_documentos_from_onedrive
            success, documentos_existentes, error = list_documentos_from_onedrive(codigo_empleado)
            
            if success and documentos_existentes:
                # Filtrar documentos que contengan el CORRELATIVO en el nombre
                docs_con_correlativo = filter_documents_by_correlativos(documentos_existentes, [correlativo_str])
                
                if docs_con_correlativo and len(docs_con_correlativo) >= expected_docs_count:
                    # DOCUMENTOS YA EXISTEN: NO REGENERAR
                    gendocu_logger.info(f'{len(docs_con_correlativo)} documentos ya existen. No se regenerarán.')
                    for doc in docs_con_correlativo:
                        gendocu_logger.info(f'  - {doc.get("name")}')
                    
                    # Transformar al formato que espera el frontend
                    from flask import url_for
                    archivos_formateados = [
                        {
                            'nombre': doc.get('name', 'Documento'),
                            'url': url_for('devices.get_documento', asignacion_id=asignacion_id, filename=doc.get('name'), _external=True),
                            'download_url': doc.get('download_url', ''),
                            'size': doc.get('size', 0),
                            'id': doc.get('id', doc.get('name', ''))
                        }
                        for doc in docs_con_correlativo
                    ]
                    
                    return jsonify({
                        'success': True,
                        'archivos_existen': True,
                        'message': 'Los documentos ya fueron generados anteriormente',
                        'archivos': archivos_formateados,
                        'raw_documentos': [d.get('name') for d in documentos_existentes],
                        'correlativo': correlativo_str,
                        'estado': estado_actual
                    }), 200
        except Exception as e:
            gendocu_logger.warning(f'Error verificando documentos existentes en OneDrive: {e}')
            # Continuar con generación si hay error en la verificación
        
        # Obtener componentes del dispositivo (inicializar como lista vacía si no existen)
        componentes = []
        try:
            componentes = svc.list_components(device_id) or []
        except Exception as e:
            gendocu_logger.warning(f'Error obteniendo componentes: {e}')
        
        # Preparar placeholders (sin firmas aún, solo datos base)
        nombre_empleado = asignacion.get('empleado_nombre') or empleado.get('nombre_completo') or 'N/A'
        
        # Obtener usuario actual
        nombre_usuario = '[NOMBRE_USUARIO]'
        puesto_usuario = '[PUESTO]'
        try:
            if 'user_id' in session:
                cur_user = db.get_cursor()
                cur_user.execute("SELECT fk_id_empleado FROM empleados.dbo.usuarios WHERE id_usuario = ?", (session['user_id'],))
                user_row = cur_user.fetchone()
                if user_row and user_row[0]:
                    emp_usuario = svc.get_empleado(user_row[0])
                    if emp_usuario:
                        nombre_usuario = emp_usuario.get('nombre_completo') or '[NOMBRE_USUARIO]'
                        puesto_usuario = emp_usuario.get('puesto') or '[PUESTO]'
                cur_user.close()
        except Exception as e:
            gendocu_logger.warning(f'Error obteniendo usuario actual: {e}')
        
        # Número de línea y costo
        numero_linea_raw = (asignacion.get('numero_linea') or '').strip()
        numero_linea = _format_numero_linea(numero_linea_raw) if numero_linea_raw else 'N/A'
        costo_plan_value = asignacion.get('costo_plan') or 0
        moneda_plan_value = asignacion.get('moneda_plan') or 'L'
        costo_plan = _format_costo_con_moneda(costo_plan_value, moneda_plan_value)
        
        # Calcular meses usando fecha_inicio y fecha_fin del plan
        meses_str = 'N/A'
        try:
            from dateutil.relativedelta import relativedelta
            def _to_date_m(v):
                if not v: return None
                if isinstance(v, str): return datetime.fromisoformat(v).date()
                return v.date() if hasattr(v, 'date') else v
            _pi = _to_date_m(asignacion.get('plan_fecha_inicio'))
            _pf = _to_date_m(asignacion.get('plan_fecha_fin'))
            if _pi:
                if not _pf: _pf = datetime.now().date()
                _d = relativedelta(_pf, _pi)
                meses_str = f"{_d.years * 12 + _d.months} meses"
                gendocu_logger.info(f'[MESES] plan {_pi} -> {_pf} = {meses_str}')
            else:
                gendocu_logger.warning(f'[MESES] plan_fecha_inicio no disponible para asignacion={asignacion_id}')
        except Exception as e:
            gendocu_logger.warning(f'[MESES] Error calculando meses: {e}')
        
        # Fecha del documento
        fecha_field = datetime.now().strftime('%d/%m/%Y')
        try:
            fecha_inicio = asignacion.get('fecha_inicio_asignacion')
            if fecha_inicio:
                if isinstance(fecha_inicio, str):
                    fecha_inicio = datetime.fromisoformat(fecha_inicio).date()
                elif hasattr(fecha_inicio, 'date'):
                    fecha_inicio = fecha_inicio.date()
                fecha_field = fecha_inicio.strftime('%d/%m/%Y')
        except Exception:
            pass
        
        # Generar TODOS los correlativos necesarios para esta categoría
        from .correlativo_helper import generar_correlativos_para_asignacion, extraer_numero_correlativo
        
        correlativos_dict = {}
        try:
            db = get_db_main()
            cur_corr = db.get_cursor()

            # Verificar si ya tiene correlativo generado
            try:
                cur_corr.execute("SELECT correlativo FROM dbo.asignacion WITH (UPDLOCK, HOLDLOCK) WHERE id_asignacion = ?", (asignacion_id,))
            except Exception:
                cur_corr.execute("SELECT correlativo FROM dbo.asignacion WHERE id_asignacion = ?", (asignacion_id,))

            corr_row = cur_corr.fetchone()
            correlativo_actual = corr_row[0] if corr_row else None

            if correlativo_actual:
                # Ya existe - reconstruir dict de correlativos basado en la categoría
                # correlativo_actual es INT, necesitamos formatearlo
                categoria = asignacion.get('categoria', '').strip()
                if categoria:
                    try:
                        from .correlativo_helper import get_formats_for_categoria
                        formatos = get_formats_for_categoria(categoria)
                        
                        # Formatear el número con ceros a la izquierda
                        numero_formateado = str(correlativo_actual).zfill(6)
                        
                        # Reconstruir dict de correlativos para todos los formatos
                        for formato in formatos:
                            correlativos_dict[formato] = f"{formato}-{numero_formateado}"
                    except Exception as e:
                        gendocu_logger.error(f'Error reconstruyendo correlativos: {e}')
                        # Fallback: usar el correlativo actual formateado para el primer formato
                        numero_formateado = str(correlativo_actual).zfill(6)
                        correlativos_dict = {f'PRO-TI-CE-001': f'PRO-TI-CE-001-{numero_formateado}'}
            else:
                # No existe correlativo: generar con el nuevo sistema
                categoria = asignacion.get('categoria', '').strip()
                if not categoria:
                    gendocu_logger.error(f'No se pudo determinar categoría para asignación {asignacion_id}')
                    cur_corr.close()
                    return jsonify({
                        'success': False,
                        'message': 'No se pudo determinar la categoría del dispositivo'
                    }), 400
                
                # Generar todos los correlativos necesarios
                correlativos_dict = generar_correlativos_para_asignacion(db, categoria)
                
                if not correlativos_dict:
                    gendocu_logger.error(f'No se pudo generar correlativos para asignación {asignacion_id}')
                    cur_corr.close()
                    return jsonify({
                        'success': False,
                        'message': 'Error generando correlativos para los documentos'
                    }), 500
                
                # Guardar el PRIMER correlativo en asignacion.correlativo (como referencia)
                # Extraer solo el número del correlativo para guardar como INT
                primer_correlativo_completo = list(correlativos_dict.values())[0]
                correlativo_numero = int(primer_correlativo_completo.split('-')[-1])
                cur_corr.execute(
                    "UPDATE asignacion SET correlativo = ? WHERE id_asignacion = ?",
                    (correlativo_numero, asignacion_id)
                )
                db.commit()
                
                gendocu_logger.debug(f'Correlativos generados para asignación {asignacion_id}')

            cur_corr.close()
        except Exception as e:
            gendocu_logger.exception(f'Error gestionando correlativos: {e}')
            return jsonify({
                'success': False,
                'message': f'Error gestionando correlativos: {str(e)}'
            }), 500
        
        # Extraer números de todos los correlativos para búsqueda
        import re
        correlativos_numeros = [
            extraer_numero_correlativo(corr) 
            for corr in correlativos_dict.values()
        ]
        
        # ====================================================================
        # VERIFICAR SI LOS ARCHIVOS YA EXISTEN EN ONEDRIVE
        # Si existen, retornar para mostrar modal de preview (sin regenerar)
        # ====================================================================
        try:
            from admin_disp.services.documento_folder_service import list_documentos_from_onedrive
            
            success, documentos_existentes, error = list_documentos_from_onedrive(codigo_empleado)
            
            if success and documentos_existentes:
                # Filtrar solo archivos con el CORRELATIVO actual
                docs_con_correlativo = filter_documents_by_correlativos(documentos_existentes, correlativos_numeros)

                if len(docs_con_correlativo) >= expected_docs_count:

                    # Transformar al formato que espera el frontend
                    # Incluir URL directa de OneDrive para descarga rápida + URL proxy como fallback
                    from flask import url_for
                    archivos_formateados = [
                        {
                            'nombre': doc.get('name', 'Documento'),
                            'url': url_for('devices.get_documento', asignacion_id=asignacion_id, filename=doc.get('name'), _external=True),
                            'download_url': doc.get('download_url', ''),  # URL directa de OneDrive (más rápido)
                            'size': doc.get('size', 0),
                            'id': doc.get('id', doc.get('name', ''))
                        }
                        for doc in docs_con_correlativo
                    ]

                    # Antes de retornar, asegurar que el estado en BD refleje que los documentos existen
                    nuevo_estado = 11 if tipo_firma == 'digital' else 21
                    try:
                        updated = svc.update_asignacion_estado_doc(asignacion_id, nuevo_estado)
                        if updated:
                            gendocu_logger.info(f'Asignación {asignacion_id}: estado_documentacion actualizado a {nuevo_estado} (docs ya existían)')
                        else:
                            gendocu_logger.warning(f'Asignación {asignacion_id}: no se pudo actualizar estado_documentacion a {nuevo_estado} (docs ya existían)')
                    except Exception as e:
                        gendocu_logger.exception(f'Error actualizando estado_documentacion antes de retornar (asignacion={asignacion_id}): {e}')

                    # Retornar estado indicando que ya existen
                    return jsonify({
                        'success': True,
                        'archivos_existen': True,
                        'message': f'Encontrados {len(archivos_formateados)} documentos con correlativo {correlativo_str}',
                        'archivos': archivos_formateados,
                        'raw_documentos': [d.get('name') for d in documentos_existentes],
                        'correlativo': correlativo_str,
                        'estado': nuevo_estado
                    }), 200
            
        except Exception as e:
            gendocu_logger.warning(f'Error verificando documentos existentes: {e}')
            # Continuar con la generación si hay error en la verificación
        
        # Extract numero_serie from device or components
        numero_serie_device = (dispositivo.get('numero_serie') or '').strip()
        if not numero_serie_device and componentes:
            for comp in componentes:
                ns = (comp.get('numero_serie') or '').strip()
                if ns:
                    numero_serie_device = ns
                    break
        
        # Extract tipo_disp for CATEGORIA
        tipo_disp = dispositivo.get('categoria') or dispositivo.get('tipo') or ''
        
        # ====================================================================
        # OBTENER IDENTIDADES AUTOMÁTICAMENTE DESDE BD (PASAPORTE)
        # ====================================================================
        # IDENTIDAD_EMPLEADO: Obtener pasaporte desde BD o usar temporal
        identidad_empleado = (empleado.get('pasaporte') or '').strip()
        
        # Si no existe en BD, usar el pasaporte temporal del payload
        if not identidad_empleado:
            identidad_empleado = (request.json.get('pasaporte_temporal') or '').strip()
        
        # Si sigue sin haber, pedir que ingrese
        if not identidad_empleado:
            gendocu_logger.warning(f'Empleado {empleado_id} no tiene pasaporte en BD')
            return jsonify({
                'success': False,
                'requiere_pasaporte': True,
                'empleado_id': empleado_id,
                'message': 'El empleado no tiene pasaporte registrado en la base de datos'
            }), 400
        
        # IDENTIDAD_USUARIO: Obtener pasaporte del usuario actual
        identidad_usuario = '[IDENTIDAD_USUARIO]'  # Default si no tiene empleado vinculado
        nombre_usuario = '[NOMBRE_USUARIO]'
        puesto_usuario = '[PUESTO]'
        try:
            if 'user_id' in session:
                db_empleados = get_db_empleados()
                cur_usr = db_empleados.get_cursor()
                cur_usr.execute(
                    "SELECT fk_id_empleado FROM dbo.usuarios WHERE id_usuario = ?",
                    (session['user_id'],)
                )
                usr_row = cur_usr.fetchone()
                cur_usr.close()
                
                if usr_row and usr_row[0]:
                    # Usuario tiene empleado vinculado, obtener su pasaporte, nombre y puesto
                    empleado_usuario = svc.get_empleado(usr_row[0])
                    if empleado_usuario:
                        pasaporte_usuario = (empleado_usuario.get('pasaporte') or '').strip()
                        nombre_usuario = (empleado_usuario.get('nombre_completo') or '').strip()
                        puesto_usuario = (empleado_usuario.get('puesto') or '').strip()
                        
                        if pasaporte_usuario:
                            identidad_usuario = pasaporte_usuario
                        else:
                            gendocu_logger.warning(f'Usuario {session["user_id"]} tiene empleado pero sin pasaporte')
                            return jsonify({
                                'success': False,
                                'requiere_pasaporte_usuario': True,
                                'empleado_id': usr_row[0],
                                'message': 'El usuario no tiene pasaporte registrado en la base de datos'
                            }), 400
                        
                        # Actualizar con los valores obtenidos
                        if nombre_usuario:
                            gendocu_logger.info(f'Nombre usuario obtenido: {nombre_usuario}')
                        if puesto_usuario:
                            gendocu_logger.info(f'Puesto usuario obtenido: {puesto_usuario}')
                else:
                    # Usuario no tiene empleado vinculado (admin), dejar placeholder
                    gendocu_logger.info(f'Usuario {session["user_id"]} no tiene empleado vinculado, usando [IDENTIDAD_USUARIO]')
        except Exception as e:
            gendocu_logger.exception(f'Error obteniendo pasaporte de usuario: {e}')
        
        gendocu_logger.info(f'Identidades obtenidas: empleado={identidad_empleado}, usuario={identidad_usuario}')
        
        # Obtener componentes
        componentes = svc.list_components(device_id)
        
        # Obtener sistema operativo desde observaciones del componente CPU (campo [OS] en laptops)
        observaciones_so = '[OS]'
        if componentes:
            for comp in componentes:
                if comp.get('tipo_componente') == 'CPU':
                    obs = (comp.get('observaciones') or '').strip()
                    if obs:
                        observaciones_so = obs
                    break
        
        fields = {
            'NUMERO_ASIGNACION': str(asignacion_id),
            'NOMBRE_EMPLEADO': nombre_empleado,
            'IDENTIDAD_EMPLEADO': identidad_empleado,
            'NOMBRE_USUARIO': nombre_usuario,
            'IDENTIDAD_USUARIO': identidad_usuario,
            'PUESTO': puesto_usuario,
            'FECHA': fecha_field,
            'MARCA': dispositivo.get('nombre_marca') or '[MARCA]',
            'MODELO': dispositivo.get('nombre_modelo') or '[MODELO]',
            'NUMERO_LINEA': numero_linea,
            'IMEI': dispositivo.get('imei') or '[IMEI]',
            'PROCESADOR': _get_componente_especifico(componentes, 'CPU'),
            'RAM': _get_componente_especifico(componentes, 'RAM'),
            'ALMACENAMIENTO': _get_componente_especifico(componentes, 'DISCO'),
            'OBSERVACION1': observaciones_payload.get('OBSERVACION1', ''),
            'OBSERVACION2': observaciones_payload.get('OBSERVACION2', ''),
            'OS': observaciones_so,
            'TAMANO': str(dispositivo.get('tamano') or '[TAMANO]'),
            'CARGADOR': 'Sí' if dispositivo.get('cargador') else 'No',
            'COSTO': costo_plan,
            'MESES': meses_str,
            'CORRELATIVOS': correlativos_dict,
        }
        
        # Manejo de placeholders de firma según tipo_firma:
        # - Manual: NO incluir campos de firma (se eliminarán del documento automáticamente)
        # - Digital: incluir placeholders que serán reemplazados con firmas reales en apply-signatures
        if tipo_firma == 'digital':
            # Solo en modo digital incluir placeholders de firma
            fields['FIRMA_USUARIO'] = '[FIRMA_USUARIO]'
            fields['FIRMA_EMPLEADO'] = '[FIRMA_EMPLEADO]'
            gendocu_logger.info(f'Modo digital: placeholders de firma incluidos para reemplazo posterior')
        else:
            # Modo manual: NO incluir estos campos para que se eliminen del documento
            gendocu_logger.info(f'Modo manual: campos de firma NO incluidos (se eliminarán del documento)')
        
        # Only add NUMERO_SERIE, IDENTIFICADOR and CATEGORIA if found
        if numero_serie_device:
            fields['NUMERO_SERIE'] = numero_serie_device
        if tipo_disp:
            fields['CATEGORIA'] = tipo_disp
        
        # Agregar IDENTIFICADOR (si no existe, agregar vacío para eliminar placeholder)
        identificador_device = (dispositivo.get('identificador') or '').strip()
        fields['IDENTIFICADOR'] = identificador_device  # Siempre agregar, incluso si está vacío
        if identificador_device:
            gendocu_logger.info(f'IDENTIFICADOR agregado: {identificador_device}')
        else:
            gendocu_logger.info('IDENTIFICADOR vacío - placeholder se eliminará del documento')
        
        # Generar documentos usando docexp
        try:
            from admin_disp.services import docexp as de
        except Exception:
            return jsonify({'success': False, 'message': 'Módulo de generación no disponible'}), 500
        
        tipo_disp = dispositivo.get('categoria') or dispositivo.get('tipo') or ''
        
        # Generar según tipo
        if tipo_disp == 'Celular':
            result = de.export_celular(fields)
        elif tipo_disp == 'Laptop':
            result = de.export_laptop(fields)
        elif tipo_disp == 'Tablet':
            result = de.export_tablet(fields)
        else:
            result = de.export_periferico(fields)
        
        # Importar servicio de documentos
        from admin_disp.services.documento_folder_service import save_documento_to_onedrive
        
        # Nota: Graph API PUT :/content crea carpetas automáticamente si no existen
        # No es necesario pre-crear las carpetas manualmente
        
        archivos_generados = []
        errores = []
        
        for doc_file in result.files:
            try:
                # Obtener contenido DOCX
                file_content = doc_file.content
                if isinstance(file_content, bytes):
                    content_bytes = file_content
                elif hasattr(file_content, 'getvalue'):
                    content_bytes = file_content.getvalue()
                elif hasattr(file_content, 'read'):
                    file_content.seek(0)
                    content_bytes = file_content.read()
                else:
                    raise ValueError(f'Tipo de contenido no soportado: {type(file_content).__name__}')
                
                # Convertir a PDF en memoria
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_docx:
                    tmp_docx.write(content_bytes)
                    tmp_docx_path = tmp_docx.name
                
                tmp_pdf_path = tmp_docx_path.replace('.docx', '.pdf')
                pdf_path = de.convert_docx_to_pdf(tmp_docx_path, tmp_pdf_path)
                
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, 'rb') as f:
                        pdf_bytes = f.read()
                    
                    # Subir a OneDrive con logging detallado
                    pdf_filename = doc_file.name.replace('.docx', '.pdf').replace('.docm', '.pdf')
                    onedrive_logger.info(f"Guardando PDF en OneDrive: {pdf_filename} ({len(pdf_bytes)} bytes) para empleado {codigo_empleado}")
                    
                    success, url, error = save_documento_to_onedrive(codigo_empleado, pdf_filename, pdf_bytes)
                    
                    if success:
                        # Generar URL local para acceder al documento a través del endpoint
                        from flask import url_for
                        local_url = url_for('devices.get_documento', asignacion_id=asignacion_id, filename=pdf_filename, _external=True)
                        archivos_generados.append({'nombre': pdf_filename, 'url': local_url})
                        onedrive_logger.info(f"PDF guardado exitosamente: {pdf_filename}")
                    else:
                        errores.append(f'Error subiendo {pdf_filename}: {error}')
                        onedrive_logger.error(f"Error guardando {pdf_filename}: {error}")
                    
                    # Limpiar archivos temporales
                    try:
                        os.unlink(tmp_docx_path)
                        os.unlink(pdf_path)
                    except:
                        pass
                else:
                    errores.append(f'Error convirtiendo {doc_file.name} a PDF')
                    
            except Exception as e:
                gendocu_logger.exception(f'Error procesando documento {doc_file.name}')
                errores.append(f'Error en {doc_file.name}: {str(e)}')
        
        # Determinar estado según resultado
        if archivos_generados:
            if tipo_firma == 'digital':
                nuevo_estado = 11 if not errores else 110
            else:  # manual
                nuevo_estado = 21 if not errores else 210
            
            # Actualizar estado en BD
            svc.update_asignacion_estado_doc(asignacion_id, nuevo_estado)
            
            return jsonify({
                'success': True,
                'estado': nuevo_estado,
                'archivos': archivos_generados,
                'correlativo': correlativo_str,
                'errores': errores if errores else None
            }), 200
        else:
            # Todo falló
            nuevo_estado = 110 if tipo_firma == 'digital' else 210
            svc.update_asignacion_estado_doc(asignacion_id, nuevo_estado)
            
            return jsonify({
                'success': False,
                'message': 'No se pudo generar ningún documento',
                'estado': nuevo_estado,
                'errores': errores
            }), 500
            
    except Exception as e:
        gendocu_logger.exception(f'Error en generate-documentation: {e}')
        _write_asignaciones_log(f'[generate-documentation] asignacion={asignacion_id} EXCEPTION: {str(e)}', 'ERROR')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


@devices_bp.get('/asignacion/<int:asignacion_id>/documento/<path:filename>')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def get_documento(asignacion_id: int, filename: str):
    """
    Descarga y sirve un documento desde OneDrive.
    """
    from flask import send_file
    from io import BytesIO
    
    gendocu_logger.info(f'[PROXY-DOCUMENTO] Solicitud de descarga: asignacion={asignacion_id}, archivo={filename}')
    
    svc = DeviceService()
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            gendocu_logger.warning(f'[PROXY-DOCUMENTO] Asignación {asignacion_id} no encontrada')
            return jsonify({'error': 'Asignación no encontrada'}), 404
        
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        if not empleado:
            gendocu_logger.warning(f'[PROXY-DOCUMENTO] Empleado {empleado_id} no encontrado')
            return jsonify({'error': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        if not codigo_empleado:
            gendocu_logger.warning(f'[PROXY-DOCUMENTO] Código de empleado no disponible para empleado_id={empleado_id}')
            return jsonify({'error': 'Código de empleado no disponible'}), 404
        
        gendocu_logger.info(f'[PROXY-DOCUMENTO] Descargando desde OneDrive: empleado={codigo_empleado}, archivo={filename}')
        
        # Descargar desde OneDrive
        from admin_disp.services.documento_folder_service import download_documento_from_onedrive
        
        success, file_bytes, error = download_documento_from_onedrive(codigo_empleado, filename)
        
        if not success:
            gendocu_logger.error(f'[PROXY-DOCUMENTO] Error descargando {filename}: {error}')
            return jsonify({'error': f'Error descargando archivo: {error}'}), 500
        
        gendocu_logger.info(f'[PROXY-DOCUMENTO] Archivo descargado exitosamente: {filename} ({len(file_bytes)} bytes)')
        
        # Registrar descarga
        try:
            svc.record_download(asignacion_id)
            gendocu_logger.info(f'[PROXY-DOCUMENTO] Descarga registrada para asignacion {asignacion_id}')
        except Exception as e:
            gendocu_logger.warning(f'[PROXY-DOCUMENTO] No se pudo registrar descarga: {e}')
        
        # Servir archivo
        return send_file(
            BytesIO(file_bytes),
            mimetype='application/pdf',
            as_attachment=False,
            download_name=filename
        )
        
    except Exception as e:
        gendocu_logger.exception(f'[PROXY-DOCUMENTO] Error sirviendo documento {filename}: {e}')
        return jsonify({'error': 'Error interno'}), 500


@devices_bp.get('/asignacion/<int:asignacion_id>/list-documentos')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def list_documentos_asignacion(asignacion_id: int):
    """
    Lista todos los documentos de una asignación desde OneDrive con metadata completa.
    Opcionalmente filtra por correlativo si se proporciona.
    """
    from admin_disp.services.documento_folder_service import list_documentos_from_onedrive
    import re
    
    svc = DeviceService()
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'error': 'Asignación no encontrada'}), 404
        
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        if not empleado:
            return jsonify({'success': False, 'error': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        if not codigo_empleado:
            return jsonify({'success': False, 'error': 'Código de empleado no disponible'}), 404
        
        # Obtener correlativo para filtrar
        correlativo = asignacion.get('correlativo')
        correlativo_str = str(correlativo).zfill(6) if correlativo is not None else None
        
        gendocu_logger.info(f'[LIST-DOCS] Listando documentos para asignacion {asignacion_id}, empleado {codigo_empleado}, correlativo {correlativo_str}')
        
        # Listar documentos desde OneDrive sin caché para obtener siempre datos frescos
        success, documentos, error = list_documentos_from_onedrive(codigo_empleado, use_cache=False)
        
        if not success:
            return jsonify({'success': False, 'error': error or 'Error listando documentos'}), 500
        
        # Filtrar por correlativo siexiste
        if correlativo_str and correlativo_str != '000000':
            documentos_filtrados = filter_documents_by_correlativos(documentos, [correlativo_str])
            gendocu_logger.info(f'[LIST-DOCS] Filtrados {len(documentos_filtrados)} documentos con correlativo {correlativo_str}')
        else:
            documentos_filtrados = documentos
            gendocu_logger.info(f'[LIST-DOCS] Sin filtro de correlativo, devolviendo {len(documentos)} documentos')
        
        # Filtrar por sufijo " rev" según el estado:
        # - Estados 22, 23 (flujo manual - revisión): mostrar SOLO archivos con " rev"
        # - Resto de estados: excluir archivos con " rev" (solo mostrar documentos finales)
        import re
        estado_doc = asignacion.get('estado_documentacion', 0)
        if estado_doc in [22, 23]:
            # Solo mostrar archivos que contengan " rev" (con espacio antes) en el nombre
            # Ejemplo: "documento rev.pdf" -> TRUE, "documento.pdf" -> FALSE
            documentos_con_rev = [d for d in documentos_filtrados if re.search(r' rev(?=\.pdf$)', d.get('name', ''), re.IGNORECASE)]
            gendocu_logger.info(f'[LIST-DOCS] Estado {estado_doc}: Mostrando SOLO archivos rev: {len(documentos_con_rev)}/{len(documentos_filtrados)}')
            for doc in documentos_filtrados:
                tiene_rev = re.search(r' rev(?=\.pdf$)', doc.get('name', ''), re.IGNORECASE) is not None
                gendocu_logger.debug(f'[LIST-DOCS]   - {doc.get("name", "")}: tiene_rev={tiene_rev}')
            documentos_filtrados = documentos_con_rev
        else:
            # Para todos los demás estados: excluir archivos con " rev" (son versiones de revisión temporal)
            documentos_sin_rev = [d for d in documentos_filtrados if not re.search(r' rev(?=\.pdf$)', d.get('name', ''), re.IGNORECASE)]
            gendocu_logger.info(f'[LIST-DOCS] Estado {estado_doc}: Excluyendo archivos rev: {len(documentos_sin_rev)}/{len(documentos_filtrados)} documentos finales')
            documentos_filtrados = documentos_sin_rev
        
        # Transformar a formato compatible con frontend (incluir URL directa de OneDrive para preview rápido)
        from flask import url_for
        files_formatted = []
        for doc in documentos_filtrados:
            files_formatted.append({
                'id': doc.get('name', ''),
                'name': doc.get('name', ''),
                'size': doc.get('size', 0),
                'url': url_for('devices.get_documento', asignacion_id=asignacion_id, filename=doc.get('name'), _external=True),
                'webUrl': doc.get('webUrl', ''),
                'download_url': doc.get('download_url', ''),  # URL directa de OneDrive (más rápido para preview)
                'downloadUrl': doc.get('download_url', '')     # Alias para compatibilidad
            })
        
        return jsonify({
            'success': True,
            'files': files_formatted,
            'count': len(files_formatted),
            'correlativo': correlativo_str
        }), 200
        
    except Exception as e:
        gendocu_logger.exception(f'[LIST-DOCS] Error listando documentos: {e}')
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@devices_bp.get('/asignacion/<int:asignacion_id>/download-zip')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def download_documentos_zip(asignacion_id: int):
    """
    Descarga todos los documentos de una asignación en un archivo ZIP nombrado con el correlativo.
    """
    from admin_disp.services.documento_folder_service import list_documentos_from_onedrive
    import re
    import io
    import zipfile
    import requests
    from flask import send_file
    
    gendocu_logger.info(f'[DOWNLOAD-ZIP] ===== INICIO ===== asignacion_id={asignacion_id}')
    
    svc = DeviceService()
    correlativo_param = request.args.get('correlativo')
    gendocu_logger.info(f'[DOWNLOAD-ZIP] correlativo_param={correlativo_param}')
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        gendocu_logger.info(f'[DOWNLOAD-ZIP] asignacion obtenida: {asignacion is not None}')
        
        if not asignacion:
            gendocu_logger.error(f'[DOWNLOAD-ZIP] Asignación {asignacion_id} no encontrada')
            return jsonify({'success': False, 'error': 'Asignación no encontrada'}), 404
        
        empleado_id = asignacion.get('fk_id_empleado')
        gendocu_logger.info(f'[DOWNLOAD-ZIP] empleado_id={empleado_id}')
        
        if not empleado_id:
            gendocu_logger.error(f'[DOWNLOAD-ZIP] Asignación {asignacion_id} sin empleado asociado')
            return jsonify({'success': False, 'error': 'Asignación sin empleado asociado'}), 404
        
        empleado = svc.get_empleado(empleado_id)
        gendocu_logger.info(f'[DOWNLOAD-ZIP] empleado obtenido: {empleado is not None}')
        
        if not empleado:
            gendocu_logger.error(f'[DOWNLOAD-ZIP] Empleado {empleado_id} no encontrado')
            return jsonify({'success': False, 'error': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        gendocu_logger.info(f'[DOWNLOAD-ZIP] codigo_empleado={codigo_empleado}')
        
        if not codigo_empleado:
            gendocu_logger.error(f'[DOWNLOAD-ZIP] Empleado {empleado_id} sin código')
            return jsonify({'success': False, 'error': 'Código de empleado no disponible'}), 404
        
        # Obtener correlativo
        correlativo = correlativo_param or asignacion.get('correlativo')
        gendocu_logger.info(f'[DOWNLOAD-ZIP] correlativo final={correlativo}')
        
        if not correlativo:
            gendocu_logger.error(f'[DOWNLOAD-ZIP] No se pudo obtener correlativo para asignación {asignacion_id}')
            return jsonify({'success': False, 'error': 'No se pudo obtener correlativo'}), 404
        
        correlativo_str = str(correlativo).zfill(6)
        gendocu_logger.info(f'[DOWNLOAD-ZIP] correlativo_str={correlativo_str}')
        
        gendocu_logger.info(f'[DOWNLOAD-ZIP] Iniciando descarga para asignacion {asignacion_id}, empleado {codigo_empleado}, correlativo {correlativo_str}')
        
        # Listar documentos desde OneDrive
        gendocu_logger.info(f'[DOWNLOAD-ZIP] Llamando a list_documentos_from_onedrive con codigo={codigo_empleado}')
        success, documentos, error = list_documentos_from_onedrive(codigo_empleado)
        
        gendocu_logger.info(f'[DOWNLOAD-ZIP] Resultado list_documentos: success={success}, num_docs={len(documentos) if documentos else 0}, error={error}')
        
        if not success:
            gendocu_logger.error(f'[DOWNLOAD-ZIP] Error listando documentos: {error}')
            return jsonify({'success': False, 'error': error or 'Error listando documentos'}), 500
        
        gendocu_logger.info(f'[DOWNLOAD-ZIP] Encontrados {len(documentos)} documentos en OneDrive')
        
        # Filtrar por correlativo
        documentos_filtrados = filter_documents_by_correlativos(documentos, [correlativo_str])
        
        gendocu_logger.info(f'[DOWNLOAD-ZIP] Documentos filtrados: {len(documentos_filtrados)}')
        for doc in documentos_filtrados:
            gendocu_logger.info(f'[DOWNLOAD-ZIP]   - {doc.get("name")}')
        
        if not documentos_filtrados:
            gendocu_logger.warning(f'[DOWNLOAD-ZIP] No hay documentos con correlativo {correlativo_str}')
            return jsonify({'success': False, 'error': f'No hay documentos con el correlativo {correlativo_str}'}), 404
        
        # Crear ZIP en memoria
        zip_buffer = io.BytesIO()
        archivos_agregados = 0
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for doc in documentos_filtrados:
                # El servicio retorna 'download_url' no '@microsoft.graph.downloadUrl'
                download_url = doc.get('download_url') or doc.get('@microsoft.graph.downloadUrl')
                
                if not download_url:
                    gendocu_logger.warning(f'[DOWNLOAD-ZIP] Documento sin URL de descarga: {doc.get("name")}')
                    gendocu_logger.debug(f'[DOWNLOAD-ZIP] Documento completo: {doc}')
                    continue
                
                try:
                    gendocu_logger.info(f'[DOWNLOAD-ZIP] Descargando: {doc.get("name")}')
                    # Descargar contenido del archivo
                    resp = requests.get(download_url, timeout=30)
                    if resp.status_code == 200:
                        # Agregar al ZIP
                        zip_file.writestr(doc.get('name', 'documento.pdf'), resp.content)
                        archivos_agregados += 1
                        gendocu_logger.info(f'[DOWNLOAD-ZIP] Agregado al ZIP: {doc.get("name")} ({len(resp.content)} bytes)')
                    else:
                        gendocu_logger.warning(f'[DOWNLOAD-ZIP] Error HTTP {resp.status_code} descargando {doc.get("name")}')
                except Exception as e:
                    gendocu_logger.warning(f'[DOWNLOAD-ZIP] Error descargando {doc.get("name")}: {e}')
        
        if archivos_agregados == 0:
            gendocu_logger.error('[DOWNLOAD-ZIP] No se pudo agregar ningún archivo al ZIP')
            return jsonify({'success': False, 'error': 'No se pudieron descargar los archivos'}), 500
        
        gendocu_logger.info(f'[DOWNLOAD-ZIP] ZIP creado exitosamente con {archivos_agregados} archivos, tamaño={zip_buffer.tell()} bytes')
        zip_buffer.seek(0)
        
        # Registrar descarga (contar como 1 descarga, no por cantidad de archivos)
        try:
            svc.record_download(asignacion_id)
            gendocu_logger.info(f'[DOWNLOAD-ZIP] Descarga registrada para asignacion {asignacion_id}')
        except Exception as e:
            gendocu_logger.warning(f'[DOWNLOAD-ZIP] No se pudo registrar descarga: {e}')
        
        gendocu_logger.info(f'[DOWNLOAD-ZIP] Enviando archivo {correlativo_str}.zip')
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{correlativo_str}.zip'
        )
        
    except Exception as e:
        gendocu_logger.error(f'[DOWNLOAD-ZIP] EXCEPCIÓN: {type(e).__name__}: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
        gendocu_logger.exception(f'[DOWNLOAD-ZIP] Error: {e}')
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@devices_bp.post('/asignacion/<int:asignacion_id>/mark-documents-read')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def mark_documents_read(asignacion_id: int):
    """
    PASO B2: Marca documentos como leídos (estado 11 → 12)
    """
    svc = DeviceService()
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        estado_actual = asignacion.get('estado_documentacion', 0)
        if estado_actual != 11:
            return jsonify({'success': False, 'message': f'Estado inválido. Actual: {estado_actual}, esperado: 11'}), 400
        
        svc.update_asignacion_estado_doc(asignacion_id, 12)
        
        logger.info(f'Documentos marcados como leídos para asignación {asignacion_id}')
        
        return jsonify({'success': True, 'estado': 12}), 200
        
    except Exception as e:
        logger.exception(f'Error en mark-documents-read: {e}')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


@devices_bp.post('/asignacion/<int:asignacion_id>/mark-manual-documents-read')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def mark_manual_documents_read(asignacion_id: int):
    """
    FIRMA MANUAL: Marca documentos como leídos (estado 21 → 22)
    """
    svc = DeviceService()
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        estado_actual = asignacion.get('estado_documentacion', 0)
        if estado_actual != 21:
            return jsonify({'success': False, 'message': f'Estado inválido. Actual: {estado_actual}, esperado: 21'}), 400
        
        svc.update_asignacion_estado_doc(asignacion_id, 22)
        
        logger.info(f'Documentos manuales marcados como leídos para asignación {asignacion_id}')
        
        return jsonify({'success': True, 'estado': 22}), 200
        
    except Exception as e:
        logger.exception(f'Error en mark-manual-documents-read: {e}')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


@devices_bp.post('/asignacion/<int:asignacion_id>/upload-signed-documents')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def upload_signed_documents(asignacion_id: int):
    """
    FIRMA MANUAL: Recibe archivos PDF firmados y los sube a OneDrive (estado 22 → 23)
    """
    from werkzeug.utils import secure_filename
    from admin_disp.services.documento_folder_service import save_documento_to_onedrive
    
    svc = DeviceService()
    
    try:
        # Verificar estado
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        estado_actual = asignacion.get('estado_documentacion', 0)
        if estado_actual != 22:
            return jsonify({'success': False, 'message': f'Estado inválido. Actual: {estado_actual}, esperado: 22'}), 400
        
        # Obtener archivos del request
        if 'files' not in request.files:
            return jsonify({'success': False, 'message': 'No se enviaron archivos'}), 400
        
        files = request.files.getlist('files')
        if not files or len(files) == 0:
            return jsonify({'success': False, 'message': 'No se enviaron archivos'}), 400
        
        # Validar que sean PDFs
        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({'success': False, 'message': f'Archivo inválido: {file.filename}. Solo se permiten PDFs.'}), 400
        
        # Obtener código de empleado para OneDrive
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        if not empleado:
            return jsonify({'success': False, 'message': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        if not codigo_empleado:
            return jsonify({'success': False, 'message': 'Código de empleado no disponible'}), 404
        
        correlativo = asignacion.get('correlativo')
        correlativo_str = str(correlativo).zfill(6) if correlativo else '000000'
        
        logger.info(f'Subiendo {len(files)} documentos firmados manualmente para asignación {asignacion_id}, correlativo {correlativo_str}')
        
        # Subir cada archivo a OneDrive
        uploaded_files = []
        for file in files:
            # Obtener nombre original y preservar espacios (no usar secure_filename que convierte a _)
            original_filename = file.filename.strip()
            file_bytes = file.read()
            
            # Validar que el nombre sea seguro pero preservando espacios
            # Eliminar caracteres peligrosos pero mantener espacios
            import re
            safe_filename = re.sub(r'[<>:"/\\|?*]', '', original_filename)
            
            # Agregar sufijo " rev" antes de la extensión .pdf
            # Ejemplo: "PRO-TI-CE-006-000036 ENTREGA DE PERIFERICO.pdf" -> "PRO-TI-CE-006-000036 ENTREGA DE PERIFERICO rev.pdf"
            if safe_filename.lower().endswith('.pdf'):
                filename = safe_filename[:-4] + ' rev.pdf'
            else:
                filename = safe_filename
            
            logger.info(f'Renombrando archivo: {original_filename} -> {filename}')
            
            # Subir a OneDrive usando la función correcta
            success, url_or_path, error_msg = save_documento_to_onedrive(codigo_empleado, filename, file_bytes)
            
            if not success:
                logger.error(f'Error subiendo {filename}: {error_msg}')
                return jsonify({'success': False, 'message': f'Error subiendo {filename}: {error_msg}'}), 500
            
            uploaded_files.append({
                'nombre': filename,
                'url': url_or_path or f'/devices/asignacion/{asignacion_id}/documento/{filename}'
            })
            
            logger.info(f'Archivo subido: {filename}')
        
        # Actualizar estado a 23
        svc.update_asignacion_estado_doc(asignacion_id, 23)
        
        logger.info(f'Documentos manuales subidos exitosamente. Estado 22→23 para asignación {asignacion_id}')
        
        return jsonify({
            'success': True,
            'estado': 23,
            'archivos': uploaded_files,
            'message': f'{len(uploaded_files)} archivos subidos correctamente'
        }), 200
        
    except Exception as e:
        logger.exception(f'Error en upload-signed-documents: {e}')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


@devices_bp.post('/asignacion/<int:asignacion_id>/confirm-manual-documents')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def confirm_manual_documents(asignacion_id: int):
    """
    FIRMA MANUAL: Confirma documentos finales (estado 23 → 24 → 90)
    - Elimina archivos originales (sin sufijo rev)
    - Renombra archivos con rev quitándoles el sufijo
    """
    svc = DeviceService()
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        estado_actual = asignacion.get('estado_documentacion', 0)
        if estado_actual != 23:
            return jsonify({'success': False, 'message': f'Estado inválido. Actual: {estado_actual}, esperado: 23'}), 400
        
        # Obtener empleado y código
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        if not empleado:
            return jsonify({'success': False, 'message': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        if not codigo_empleado:
            return jsonify({'success': False, 'message': 'Código de empleado no disponible'}), 404
        
        correlativo = asignacion.get('correlativo')
        correlativo_str = str(correlativo).zfill(6) if correlativo else '000000'
        
        # Listar documentos desde OneDrive
        from admin_disp.services.documento_folder_service import list_documentos_from_onedrive, delete_documento_from_onedrive, rename_documento_in_onedrive
        import re
        
        success, documentos, error = list_documentos_from_onedrive(codigo_empleado)
        if not success:
            return jsonify({'success': False, 'message': f'Error listando documentos: {error}'}), 500
        
        # Filtrar documentos con el correlativo actual
        docs_con_correlativo = filter_documents_by_correlativos(documentos, [correlativo_str])
        
        logger.info(f'Confirmando documentos manuales: {len(docs_con_correlativo)} archivos con correlativo {correlativo_str}')
        
        # Separar archivos con y sin sufijo rev (case-insensitive)
        archivos_con_rev = [d for d in docs_con_correlativo if re.search(r' rev(?=\.pdf$)', d.get('name', ''), re.IGNORECASE)]
        archivos_sin_rev = [d for d in docs_con_correlativo if not re.search(r' rev(?=\.pdf$)', d.get('name', ''), re.IGNORECASE)]
        
        logger.info(f'  - Archivos con rev: {len(archivos_con_rev)}')
        logger.info(f'  - Archivos sin rev: {len(archivos_sin_rev)}')
        
        # 1. Eliminar archivos SIN rev
        for doc in archivos_sin_rev:
            filename = doc.get('name')
            logger.info(f'Eliminando archivo original: {filename}')
            del_success, del_error = delete_documento_from_onedrive(codigo_empleado, filename)
            if not del_success:
                logger.warning(f'Error eliminando {filename}: {del_error}')
        
        # 2. Renombrar archivos CON rev quitándoles el sufijo
        for doc in archivos_con_rev:
            old_name = doc.get('name')
            # Quitar " rev" del nombre (case-insensitive)
            new_name = re.sub(r' rev(?=\.pdf$)', '', old_name, flags=re.IGNORECASE)
            
            if old_name != new_name:
                logger.info(f'Renombrando: {old_name} -> {new_name}')
                rename_success, rename_error = rename_documento_in_onedrive(codigo_empleado, old_name, new_name)
                if not rename_success:
                    logger.warning(f'Error renombrando {old_name}: {rename_error}')
        
        # Actualizar a estado 24 (confirmados) y luego a 90 (finalizados)
        svc.update_asignacion_estado_doc(asignacion_id, 24)
        svc.update_asignacion_estado_doc(asignacion_id, 90)
        
        logger.info(f'Documentos manuales confirmados. Estado 23→24→90 para asignación {asignacion_id}')
        
        # Obtener archivos para mostrar
        from admin_disp.services.documento_folder_service import list_documentos_from_onedrive
        import re
        
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        codigo_empleado = empleado.get('codigo_empleado') if empleado else None
        
        archivos = []
        if codigo_empleado:
            success, documentos, error = list_documentos_from_onedrive(codigo_empleado)
            if success and documentos:
                correlativo = asignacion.get('correlativo')
                correlativo_str = str(correlativo).zfill(6) if correlativo else None
                
                # Filtrar por correlativo
                if correlativo_str:
                    for doc in documentos:
                        name = doc.get('name', '')
                        if correlativo_str in name:
                            archivos.append({
                                'nombre': name,
                                'url': f'/devices/asignacion/{asignacion_id}/documento/{name}'
                            })
        
        return jsonify({
            'success': True,
            'estado': 90,
            'archivos': archivos,
            'message': 'Documentos confirmados exitosamente. Proceso de firma manual completado.'
        }), 200
        
    except Exception as e:
        logger.exception(f'Error en confirm-manual-documents: {e}')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


@devices_bp.post('/asignacion/<int:asignacion_id>/submit-signatures')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def submit_signatures(asignacion_id: int):
    """
    PASO B3-B4: Recibe firmas, regenera PDFs firmados y los sube a OneDrive.
    
    Input: { 
        firma_empleado_b64: str,
        firma_usuario_b64: str,
        identidad_empleado: str,
        identidad_usuario: str
    }
    Output: { success, estado: 14 | 130, archivos: [...] }
    """
    svc = DeviceService()
    
    try:
        data = request.get_json() or {}
        firma_empleado_b64 = data.get('firma_empleado_b64')
        firma_usuario_b64 = data.get('firma_usuario_b64')
        identidad_empleado = data.get('identidad_empleado', '').strip()
        identidad_usuario = data.get('identidad_usuario', '').strip()
        
        if not all([firma_empleado_b64, firma_usuario_b64, identidad_empleado, identidad_usuario]):
            return jsonify({'success': False, 'message': 'Faltan datos de firmas o identidades'}), 400
        
        # Verificar estado
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        estado_actual = asignacion.get('estado_documentacion', 0)
        if estado_actual != 12:
            return jsonify({'success': False, 'message': f'Estado inválido. Actual: {estado_actual}, esperado: 12'}), 400
        
        # Actualizar a estado 13 (generando PDFs firmados)
        svc.update_asignacion_estado_doc(asignacion_id, 13)
        
        # Decodificar firmas Base64
        import base64
        from io import BytesIO
        from PIL import Image
        
        try:
            # Decodificar imagen de firma empleado
            firma_emp_data = firma_empleado_b64.split(',')[1] if ',' in firma_empleado_b64 else firma_empleado_b64
            firma_emp_bytes = base64.b64decode(firma_emp_data)
            firma_emp_img = Image.open(BytesIO(firma_emp_bytes))
            
            # Decodificar imagen de firma usuario
            firma_usr_data = firma_usuario_b64.split(',')[1] if ',' in firma_usuario_b64 else firma_usuario_b64
            firma_usr_bytes = base64.b64decode(firma_usr_data)
            firma_usr_img = Image.open(BytesIO(firma_usr_bytes))
            
        except Exception as e:
            logger.error(f'Error decodificando firmas: {e}')
            svc.update_asignacion_estado_doc(asignacion_id, 130)
            return jsonify({'success': False, 'estado': 130, 'message': f'Error en firmas: {str(e)}'}), 400
        
        # Obtener datos del dispositivo y empleado
        device_id = asignacion.get('fk_id_dispositivo')
        dispositivo = svc.get_device(device_id)
        if not dispositivo:
            svc.update_asignacion_estado_doc(asignacion_id, 130)
            return jsonify({'success': False, 'estado': 130, 'message': 'Dispositivo no encontrado'}), 404
        
        # Obtener componentes del dispositivo
        componentes = []
        try:
            componentes = svc.get_device_components(device_id) or []
        except Exception as e:
            logger.warning(f'Error obteniendo componentes: {e}')
        
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        if not empleado:
            svc.update_asignacion_estado_doc(asignacion_id, 130)
            return jsonify({'success': False, 'estado': 130, 'message': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        if not codigo_empleado:
            svc.update_asignacion_estado_doc(asignacion_id, 130)
            return jsonify({'success': False, 'estado': 130, 'message': 'Código de empleado no disponible'}), 404
        
        # Preparar placeholders CON firmas
        nombre_empleado = asignacion.get('empleado_nombre') or empleado.get('nombre_completo') or 'N/A'
        
        nombre_usuario = '[NOMBRE_USUARIO]'
        puesto_usuario = '[PUESTO]'
        try:
            if 'user_id' in session:
                cur_user = get_db_empleados().get_cursor()
                cur_user.execute("SELECT fk_id_empleado FROM empleados.dbo.usuarios WHERE id_usuario = ?", (session['user_id'],))
                user_row = cur_user.fetchone()
                if user_row and user_row[0]:
                    emp_usuario = svc.get_empleado(user_row[0])
                    if emp_usuario:
                        nombre_usuario = emp_usuario.get('nombre_completo') or '[NOMBRE_USUARIO]'
                        puesto_usuario = emp_usuario.get('puesto') or '[PUESTO]'
                cur_user.close()
        except Exception as e:
            logger.warning(f'Error obteniendo usuario actual: {e}')
        
        numero_linea_raw = (asignacion.get('numero_linea') or '').strip()
        numero_linea = _format_numero_linea(numero_linea_raw) if numero_linea_raw else 'N/A'
        costo_plan_value = asignacion.get('costo_plan') or 0
        moneda_plan_value = asignacion.get('moneda_plan') or 'L'
        costo_plan = _format_costo_con_moneda(costo_plan_value, moneda_plan_value)
        
        meses_str = 'N/A'
        try:
            from dateutil.relativedelta import relativedelta
            def _to_date_m(v):
                if not v: return None
                if isinstance(v, str): return datetime.fromisoformat(v).date()
                return v.date() if hasattr(v, 'date') else v
            _pi = _to_date_m(asignacion.get('plan_fecha_inicio'))
            _pf = _to_date_m(asignacion.get('plan_fecha_fin'))
            if _pi:
                if not _pf: _pf = datetime.now().date()
                _d = relativedelta(_pf, _pi)
                meses_str = f"{_d.years * 12 + _d.months} meses"
        except Exception as e:
            logger.warning(f'[MESES] Error calculando meses: {e}')
        
        fecha_field = datetime.now().strftime('%d/%m/%Y')
        try:
            fecha_inicio = asignacion.get('fecha_inicio_asignacion')
            if fecha_inicio:
                if isinstance(fecha_inicio, str):
                    fecha_inicio = datetime.fromisoformat(fecha_inicio).date()
                elif hasattr(fecha_inicio, 'date'):
                    fecha_inicio = fecha_inicio.date()
                fecha_field = fecha_inicio.strftime('%d/%m/%Y')
        except Exception:
            pass
        
        # Extract numero_serie from device or components
        numero_serie_device = (dispositivo.get('numero_serie') or '').strip()
        if not numero_serie_device and componentes:
            for comp in componentes:
                ns = (comp.get('numero_serie') or '').strip()
                if ns:
                    numero_serie_device = ns
                    break
        
        # Extract tipo_disp for CATEGORIA
        tipo_disp = dispositivo.get('categoria') or dispositivo.get('tipo') or ''
        
        # Obtener componentes
        componentes = svc.list_components(device_id)
        
        # Obtener sistema operativo desde observaciones del componente CPU (campo [OS] en laptops)
        observaciones_so = '[OS]'
        if componentes:
            for comp in componentes:
                if comp.get('tipo_componente') == 'CPU':
                    obs = (comp.get('observaciones') or '').strip()
                    if obs:
                        observaciones_so = obs
                    break
        
        fields = {
            'NUMERO_ASIGNACION': str(asignacion_id),
            'NOMBRE_EMPLEADO': nombre_empleado,
            'IDENTIDAD_EMPLEADO': identidad_empleado,
            'NOMBRE_USUARIO': nombre_usuario,
            'IDENTIDAD_USUARIO': identidad_usuario,
            'PUESTO': puesto_usuario,
            'FECHA': fecha_field,
            'MARCA': dispositivo.get('nombre_marca') or '[MARCA]',
            'MODELO': dispositivo.get('nombre_modelo') or '[MODELO]',
            'NUMERO_LINEA': numero_linea,
            'IMEI': dispositivo.get('imei') or '[IMEI]',
            'PROCESADOR': _get_componente_especifico(componentes, 'CPU'),
            'RAM': _get_componente_especifico(componentes, 'RAM'),
            'ALMACENAMIENTO': _get_componente_especifico(componentes, 'DISCO'),
            'OS': observaciones_so,
            'TAMANO': str(dispositivo.get('tamano') or '[TAMANO]'),
            'CARGADOR': 'Sí' if dispositivo.get('cargador') else 'No',
            'COSTO': costo_plan,
            'MESES': meses_str
        }
        
        # Only add NUMERO_SERIE and CATEGORIA if found
        if numero_serie_device:
            fields['NUMERO_SERIE'] = numero_serie_device
        if tipo_disp:
            fields['CATEGORIA'] = tipo_disp
        
        # Generar documentos usando docexp
        try:
            from admin_disp.services import docexp as de
        except Exception:
            svc.update_asignacion_estado_doc(asignacion_id, 130)
            return jsonify({'success': False, 'estado': 130, 'message': 'Módulo de generación no disponible'}), 500
        
        # Preparar firmas en memoria (sin guardar en archivos temporales)
        images_map = {}
        if firma_emp_bytes:
            images_map['FIRMA_EMPLEADO'] = firma_emp_bytes
        if firma_usr_bytes:
            images_map['FIRMA_USUARIO'] = firma_usr_bytes
        
        tipo_disp = dispositivo.get('categoria') or dispositivo.get('tipo') or ''
        
        if tipo_disp == 'Celular':
            result = de.export_celular(fields, images_map=images_map if images_map else None)
        elif tipo_disp == 'Laptop':
            result = de.export_laptop(fields, images_map=images_map if images_map else None)
        elif tipo_disp == 'Tablet':
            result = de.export_tablet(fields, images_map=images_map if images_map else None)
        else:
            result = de.export_periferico(fields, images_map=images_map if images_map else None)
        
        # Eliminar documentos previos de OneDrive
        from admin_disp.services.documento_folder_service import save_documento_to_onedrive, delete_all_documentos_from_onedrive
        
        delete_all_documentos_from_onedrive(codigo_empleado)
        
        # Convertir a PDF y subir
        archivos_generados = []
        errores = []
        tmp_files_to_cleanup = []  # Rastrear temporales para limpieza garantizada
        
        try:
            for doc_file in result.files:
                tmp_docx_path = None
                tmp_pdf_path = None
                try:
                    file_content = doc_file.content
                    if isinstance(file_content, bytes):
                        content_bytes = file_content
                    elif hasattr(file_content, 'getvalue'):
                        content_bytes = file_content.getvalue()
                    elif hasattr(file_content, 'read'):
                        file_content.seek(0)
                        content_bytes = file_content.read()
                    else:
                        raise ValueError(f'Tipo de contenido no soportado: {type(file_content).__name__}')
                    
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_docx:
                        tmp_docx.write(content_bytes)
                        tmp_docx_path = tmp_docx.name
                    
                    tmp_files_to_cleanup.append(tmp_docx_path)
                    
                    tmp_pdf_path = tmp_docx_path.replace('.docx', '.pdf')
                    pdf_path = de.convert_docx_to_pdf(tmp_docx_path, tmp_pdf_path)
                    
                    if tmp_pdf_path and tmp_pdf_path not in tmp_files_to_cleanup:
                        tmp_files_to_cleanup.append(tmp_pdf_path)
                    
                    if pdf_path and os.path.exists(pdf_path):
                        with open(pdf_path, 'rb') as f:
                            pdf_bytes = f.read()
                        
                        pdf_filename = doc_file.name.replace('.docx', '.pdf').replace('.docm', '.pdf')
                        success, url, error = save_documento_to_onedrive(codigo_empleado, pdf_filename, pdf_bytes)
                        
                        if success:
                            # Generar URL local para acceder al documento a través del endpoint
                            from flask import url_for
                            local_url = url_for('devices.get_documento', asignacion_id=asignacion_id, filename=pdf_filename, _external=True)
                            archivos_generados.append({'nombre': pdf_filename, 'url': local_url})
                        else:
                            errores.append(f'Error subiendo {pdf_filename}: {error}')
                    else:
                        errores.append(f'Error convirtiendo {doc_file.name} a PDF')
                        
                except Exception as e:
                    logger.exception(f'Error procesando documento {doc_file.name}')
                    errores.append(f'Error en {doc_file.name}: {str(e)}')
        finally:
            # Limpieza garantizada de todos los archivos temporales (DOCX y PDF)
            for tmp_path in tmp_files_to_cleanup:
                try:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                        logger.debug(f'Limpiado archivo temporal: {tmp_path}')
                except Exception as e:
                    logger.warning(f'No se pudo eliminar archivo temporal {tmp_path}: {e}')
        
        
        # Determinar estado final
        if archivos_generados and not errores:
            nuevo_estado = 14
        else:
            nuevo_estado = 130
        
        svc.update_asignacion_estado_doc(asignacion_id, nuevo_estado)
        
        logger.info(f'Firmas procesadas para asignación {asignacion_id}')
        
        return jsonify({
            'success': True,
            'estado': 14,
            'message': 'Firmas aplicadas correctamente'
        }), 200
        
    except Exception as e:
        logger.exception(f'Error en submit-signatures: {e}')
        # Marcar como error
        svc.update_asignacion_estado_doc(asignacion_id, 130)
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}', 'estado': 130}), 500


@devices_bp.post('/asignacion/<int:asignacion_id>/confirm-resguardo')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def confirm_resguardo(asignacion_id: int):
    """
    PASO B5/C5: Confirma resguardo final (estado 14 o 24 → 90)
    """
    svc = DeviceService()
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        estado_actual = asignacion.get('estado_documentacion', 0)
        if estado_actual not in [14, 24]:
            return jsonify({'success': False, 'message': f'Estado inválido. Actual: {estado_actual}, esperado: 14 o 24'}), 400
        
        svc.update_asignacion_estado_doc(asignacion_id, 90)
        
        logger.info(f'Documentación resguardada exitosamente para asignación {asignacion_id}')
        
        return jsonify({'success': True, 'estado': 90}), 200
        
    except Exception as e:
        logger.exception(f'Error en confirm-resguardo: {e}')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


# ============================================================================
# ENDPOINT DIAGNÓSTICO: Verificar Estado de Asignación
# ============================================================================

@devices_bp.get('/asignacion/<int:asignacion_id>/estado-documentacion')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def get_estado_documentacion(asignacion_id: int):
    """
    Endpoint de diagnóstico para verificar el estado actual de una asignación.
    Usado por el cliente para determinar qué paso debe completar.
    
    Output: { 
        success, 
        estado_documentacion: int,
        tipo_firma: 'digital'|'manual',
        siguiente_paso: str,
        mensaje: str
    }
    """
    svc = DeviceService()
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        estado = asignacion.get('estado_documentacion', 0)
        tipo_firma = asignacion.get('tipo_firma') or 'digital'
        
        # Mapear estado a descripción y próximo paso
        estado_map = {
            0: ('Generación pendiente', 'Generar documentos'),
            10: ('Documentos generados', 'Revisar documentos'),
            11: ('Documentos a revisar', 'Marcar como leídos y capturar firmas'),
            12: ('Listo para firmas', 'Capturar y aplicar firmas'),
            13: ('Firmas aplicadas', 'Confirmar resguardo'),
            14: ('Resguardo confirmado', 'Completado'),
            21: ('Documentos para firma manual', 'Subir documentos firmados'),
            22: ('Documentos subidos', 'Revisar'),
            23: ('Documentos revisados', 'Confirmar'),
            24: ('Confirmar resguardo', 'Completado'),
            90: ('Completado', 'N/A'),
            130: ('Error en documentación', 'Contactar administrador'),
        }
        
        desc, siguiente = estado_map.get(estado, ('Estado desconocido', 'Desconocido'))
        
        return jsonify({
            'success': True,
            'estado_documentacion': estado,
            'tipo_firma': tipo_firma,
            'descripcion_estado': desc,
            'siguiente_paso': siguiente,
            'mensaje': f'Estado actual: {desc}. Próximo paso: {siguiente}'
        }), 200
        
    except Exception as e:
        logger.exception(f'Error en get_estado_documentacion: {e}')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


# ============================================================================
# NUEVO ENDPOINT: Aplicar Solo Firmas (PASO B3b - Estado 12→13)
# ============================================================================

@devices_bp.post('/asignacion/<int:asignacion_id>/apply-signatures')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def apply_signatures(asignacion_id: int):
    """
    PASO B3b: Regenera documentos DOCX completos con firmas aplicadas.
    
    Input: { 
        firma_empleado_b64: str,
        firma_usuario_b64: str
    }
    Output: { success, estado: 13, archivos: [...] }
    
    Flujo:
    1. Obtener todos los datos de la asignación (igual que generate-documentation)
    2. Decodificar firmas Base64
    3. Regenerar DOCX con TODOS los datos + firmas incluidas
    4. Convertir DOCX→PDF
    5. Subir PDFs con firmas a OneDrive (reemplazando los anteriores)
    6. Actualizar estado a 13
    """
    from admin_disp.core.db import get_db_main
    svc = DeviceService()
    
    try:
        data = request.get_json() or {}
        firma_empleado_b64 = data.get('firma_empleado_b64')
        firma_usuario_b64 = data.get('firma_usuario_b64')
        observaciones_payload = data.get('observaciones', {})  # Recibir observaciones del frontend
        
        if not all([firma_empleado_b64, firma_usuario_b64]):
            return jsonify({'success': False, 'message': 'Faltan datos de firmas'}), 400
        
        # Verificar estado
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        estado_actual = asignacion.get('estado_documentacion', 0)
        if estado_actual != 12:
            # Construir un mensaje de error más descriptivo según el estado actual
            if estado_actual == 11:
                msg = 'Estado inválido: Debe marcar los documentos como leídos y aceptar los términos ANTES de capturar firmas.'
            elif estado_actual < 11:
                msg = f'Estado inválido: Debe generar los documentos primero (estado actual: {estado_actual})'
            elif estado_actual > 12:
                msg = f'Estado inválido: La asignación ya está en un estado posterior (estado: {estado_actual}). Los documentos pueden ya estar procesados.'
            else:
                msg = f'Estado inválido. Actual: {estado_actual}, esperado: 12'
            
            gendocu_logger.warning(f'[APPLY-SIGNATURES] {msg} | asignacion_id={asignacion_id}')
            return jsonify({
                'success': False, 
                'message': msg,
                'estado_actual': estado_actual,
                'estado_esperado': 12
            }), 400
        
        try:
            firma_emp_data = firma_empleado_b64.split(',')[1] if ',' in firma_empleado_b64 else firma_empleado_b64
            firma_emp_bytes = base64.b64decode(firma_emp_data)
            
            firma_usr_data = firma_usuario_b64.split(',')[1] if ',' in firma_usuario_b64 else firma_usuario_b64
            firma_usr_bytes = base64.b64decode(firma_usr_data)
            
            gendocu_logger.info(f'[APPLY-SIGNATURES] Firmas decodificadas: emp={len(firma_emp_bytes)}B, usr={len(firma_usr_bytes)}B')
        except Exception as e:
            gendocu_logger.error(f'[APPLY-SIGNATURES] Error decodificando firmas: {e}')
            svc.update_asignacion_estado_doc(asignacion_id, 130)
            return jsonify({'success': False, 'estado': 130, 'message': f'Error en firmas: {str(e)}'}), 400
        
        # ====================================================================
        # OBTENER TODOS LOS DATOS (IGUAL QUE EN GENERATE-DOCUMENTATION)
        # ====================================================================
        
        # Obtener datos del empleado
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        if not empleado:
            svc.update_asignacion_estado_doc(asignacion_id, 130)
            return jsonify({'success': False, 'estado': 130, 'message': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        if not codigo_empleado:
            svc.update_asignacion_estado_doc(asignacion_id, 130)
            return jsonify({'success': False, 'estado': 130, 'message': 'Código de empleado no disponible'}), 404
        
        # Obtener correlativo
        correlativo = asignacion.get('correlativo')
        if not correlativo:
            svc.update_asignacion_estado_doc(asignacion_id, 130)
            return jsonify({'success': False, 'estado': 130, 'message': 'Correlativo no disponible'}), 404
        
        correlativo_str = str(correlativo).zfill(6)
        gendocu_logger.info(f'[APPLY-SIGNATURES] Inicio: correlativo={correlativo_str}, asignacion={asignacion_id}')
        
        # Obtener dispositivo y componentes
        device_id = asignacion.get('fk_id_dispositivo')
        dispositivo = svc.get_device(device_id)
        if not dispositivo:
            return jsonify({'success': False, 'message': 'Dispositivo no encontrado'}), 404
        
        componentes = []
        try:
            componentes = svc.get_device_components(device_id) or []
        except Exception as e:
            gendocu_logger.warning(f'Error obteniendo componentes: {e}')
        
        # Preparar datos para placeholders
        nombre_empleado = asignacion.get('empleado_nombre') or empleado.get('nombre_completo') or 'N/A'
        
        # Obtener usuario actual
        nombre_usuario = '[NOMBRE_USUARIO]'
        puesto_usuario = '[PUESTO]'
        try:
            if 'user_id' in session:
                db_main = get_db_main()
                cur_usr = db_main.get_cursor()
                cur_usr.execute("SELECT fk_id_empleado FROM empleados.dbo.usuarios WHERE id_usuario = ?", (session['user_id'],))
                usr_row = cur_usr.fetchone()
                cur_usr.close()
                
                if usr_row and usr_row[0]:
                    empleado_usuario = svc.get_empleado(usr_row[0])
                    if empleado_usuario:
                        nombre_usuario = empleado_usuario.get('nombre_completo') or '[NOMBRE_USUARIO]'
                        puesto_usuario = empleado_usuario.get('puesto') or '[PUESTO]'
        except Exception as e:
            gendocu_logger.warning(f'Error obteniendo usuario actual: {e}')
        
        # Obtener IDENTIDADES desde BD o usar temporal del payload
        identidad_empleado = (empleado.get('pasaporte') or '').strip()
        
        # Si no existe en BD, usar el pasaporte temporal del payload
        if not identidad_empleado:
            identidad_empleado = (data.get('pasaporte_temporal') or '').strip()
            if identidad_empleado:
                gendocu_logger.info(f'[APPLY-SIGNATURES] Usando pasaporte_temporal para empleado {empleado_id}: {identidad_empleado}')
        
        # Si sigue sin haber, pedir que ingrese
        if not identidad_empleado:
            gendocu_logger.warning(f'[APPLY-SIGNATURES] Empleado {empleado_id} no tiene pasaporte en BD ni temporal')
            gendocu_logger.info(f'[APPLY-SIGNATURES] Solicitando pasaporte_temporal al frontend para asignacion {asignacion_id}')
            # Indicar al frontend que se requiere pasaporte temporal para continuar
            return jsonify({
                'success': False,
                'requiere_pasaporte': True,
                'empleado_id': empleado_id,
                'message': 'El empleado no tiene pasaporte registrado en la base de datos'
            }), 400
        
        gendocu_logger.info(f'[APPLY-SIGNATURES] Usando identidad empleado: {identidad_empleado}')
        
        identidad_usuario = '[IDENTIDAD_USUARIO]'
        try:
            if 'user_id' in session:
                db_main = get_db_main()
                cur_usr = db_main.get_cursor()
                cur_usr.execute("SELECT fk_id_empleado FROM empleados.dbo.usuarios WHERE id_usuario = ?", (session['user_id'],))
                usr_row = cur_usr.fetchone()
                cur_usr.close()
                
                if usr_row and usr_row[0]:
                    empleado_usuario = svc.get_empleado(usr_row[0])
                    if empleado_usuario:
                        pasaporte_usuario = (empleado_usuario.get('pasaporte') or '').strip()
                        if pasaporte_usuario:
                            identidad_usuario = pasaporte_usuario
        except Exception as e:
            gendocu_logger.warning(f'Error obteniendo identidad usuario: {e}')
        
        gendocu_logger.info(f'Identidades obtenidas: empleado={identidad_empleado}, usuario={identidad_usuario}')
        
        # Número de línea y costo
        numero_linea_raw = (asignacion.get('numero_linea') or '').strip()
        numero_linea = _format_numero_linea(numero_linea_raw) if numero_linea_raw else 'N/A'
        costo_plan_value = asignacion.get('costo_plan') or 0
        moneda_plan_value = asignacion.get('moneda_plan') or 'L'
        costo_plan = _format_costo_con_moneda(costo_plan_value, moneda_plan_value)
        
        # Calcular meses usando fecha_inicio y fecha_fin del plan
        meses_str = 'N/A'
        try:
            from dateutil.relativedelta import relativedelta
            def _to_date_m(v):
                if not v: return None
                if isinstance(v, str): return datetime.fromisoformat(v).date()
                return v.date() if hasattr(v, 'date') else v
            _pi = _to_date_m(asignacion.get('plan_fecha_inicio'))
            _pf = _to_date_m(asignacion.get('plan_fecha_fin'))
            if _pi:
                if not _pf: _pf = datetime.now().date()
                _d = relativedelta(_pf, _pi)
                meses_str = f"{_d.years * 12 + _d.months} meses"
                gendocu_logger.info(f'[MESES] plan {_pi} -> {_pf} = {meses_str}')
            else:
                gendocu_logger.warning(f'[MESES] plan_fecha_inicio no disponible en firma asignacion={asignacion_id}')
        except Exception as e:
            gendocu_logger.warning(f'[MESES] Error calculando meses (firma): {e}')
        
        # Fecha del documento
        fecha_field = datetime.now().strftime('%d/%m/%Y')
        try:
            fecha_inicio = asignacion.get('fecha_inicio_asignacion')
            if fecha_inicio:
                if isinstance(fecha_inicio, str):
                    fecha_inicio = datetime.fromisoformat(fecha_inicio).date()
                elif hasattr(fecha_inicio, 'date'):
                    fecha_inicio = fecha_inicio.date()
                fecha_field = fecha_inicio.strftime('%d/%m/%Y')
        except Exception:
            pass
        
        # Número de serie
        numero_serie_device = (dispositivo.get('numero_serie') or '').strip()
        if not numero_serie_device and componentes:
            for comp in componentes:
                ns = (comp.get('numero_serie') or '').strip()
                if ns:
                    numero_serie_device = ns
                    break
        
        tipo_disp = dispositivo.get('categoria') or dispositivo.get('tipo') or ''
        
        # ====================================================================
        # GENERAR DOCUMENTOS CON FIRMAS
        # ====================================================================
        
        from admin_disp.services import docexp as de
        from admin_disp.services.documento_folder_service import save_documento_to_onedrive
        
        # Preparar map de placeholders + firmas
        images_map = {
            'FIRMA_EMPLEADO': firma_emp_bytes,
            'FIRMA_USUARIO': firma_usr_bytes
        }
        
        # Obtener componentes
        componentes = svc.list_components(device_id)
        
        # Obtener sistema operativo desde observaciones del componente CPU (campo [OS] en laptops)
        observaciones_so = '[OS]'
        if componentes:
            for comp in componentes:
                if comp.get('tipo_componente') == 'CPU':
                    obs = (comp.get('observaciones') or '').strip()
                    if obs:
                        observaciones_so = obs
                    break
        
        # Preparar fields dict
        fields = {
            'NOMBRE_EMPLEADO': nombre_empleado,
            'IDENTIDAD_EMPLEADO': identidad_empleado,
            'NOMBRE_USUARIO': nombre_usuario,
            'PUESTO': puesto_usuario,
            'IDENTIDAD_USUARIO': identidad_usuario,
            'CORRELATIVO': correlativo_str,
            'FECHA': fecha_field,
            'NUMERO_SERIE': numero_serie_device,
            'MARCA': dispositivo.get('nombre_marca') or 'N/A',
            'MODELO': dispositivo.get('nombre_modelo') or 'N/A',
            'CATEGORIA': tipo_disp,  # No usar .upper(), mantener tal como viene de BD
            'NUMERO_LINEA': numero_linea,
            'COSTO': costo_plan,  # Template espera 'COSTO', no 'COSTO_PLAN'
            'IMEI': dispositivo.get('imei') or '[IMEI]',  # Agregar IMEI del dispositivo
            'PROCESADOR': _get_componente_especifico(componentes, 'CPU'),
            'RAM': _get_componente_especifico(componentes, 'RAM'),
            'ALMACENAMIENTO': _get_componente_especifico(componentes, 'DISCO'),
            'OBSERVACION1': observaciones_payload.get('OBSERVACION1', ''),  # Añadir observaciones
            'OBSERVACION2': observaciones_payload.get('OBSERVACION2', ''),  # Añadir observaciones
            'OS': observaciones_so,
            'TAMANO': str(dispositivo.get('tamano') or '[TAMANO]'),
            'CARGADOR': 'Sí' if dispositivo.get('cargador') else 'No',
            'MESES': meses_str
        }
        
        # Generar documentos según categoría usando docexport
        archivos_generados = []
        errores = []
        
        try:
            # Usar tipo_disp tal como viene (Monitor, Laptop, etc.)
            gendocu_logger.info(f'[APPLY-SIGNATURES] Generando documentos para categoría {tipo_disp}')
            
            # Usar docexport como en generate-documentation
            result = de.docexport(tipo_disp, fields, images_map)
            
            if not result.files:
                gendocu_logger.error(f'[APPLY-SIGNATURES] No se generaron archivos para categoría {tipo_disp}')
                svc.update_asignacion_estado_doc(asignacion_id, 130)
                return jsonify({'success': False, 'estado': 130, 'message': f'No se generaron documentos para categoría {tipo_disp}'}), 500
            
            gendocu_logger.info(f'[APPLY-SIGNATURES] Generados {len(result.files)} documentos DOCX')
            
            # Procesar cada documento generado
            for doc_file in result.files:
                tmp_docx_path = None
                tmp_pdf_path = None
                try:
                    # Obtener contenido DOCX
                    file_content = doc_file.content
                    if isinstance(file_content, bytes):
                        content_bytes = file_content
                    elif hasattr(file_content, 'getvalue'):
                        content_bytes = file_content.getvalue()
                    elif hasattr(file_content, 'read'):
                        file_content.seek(0)
                        content_bytes = file_content.read()
                    else:
                        raise ValueError(f'Tipo de contenido no soportado: {type(file_content).__name__}')
                    
                    # Convertir DOCX a PDF
                    import tempfile
                    import os
                    
                    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_docx:
                        tmp_docx.write(content_bytes)
                        tmp_docx_path = tmp_docx.name
                    
                    tmp_pdf_path = tmp_docx_path.replace('.docx', '.pdf')
                    pdf_path = de.convert_docx_to_pdf(tmp_docx_path, tmp_pdf_path)
                    
                    if pdf_path and os.path.exists(pdf_path):
                        with open(pdf_path, 'rb') as f:
                            pdf_bytes = f.read()
                        
                        # Construir nombre de archivo PDF
                        pdf_filename = doc_file.name.replace('.docx', '.pdf').replace('.docm', '.pdf')
                        
                        gendocu_logger.info(f"[APPLY-SIGNATURES] Guardando PDF: {pdf_filename} ({len(pdf_bytes)} bytes)")
                        
                        # Subir a OneDrive
                        success, url, error = save_documento_to_onedrive(codigo_empleado, pdf_filename, pdf_bytes)
                        
                        if success:
                            from flask import url_for
                            local_url = url_for('devices.get_documento', asignacion_id=asignacion_id, filename=pdf_filename, _external=True)
                            archivos_generados.append({'nombre': pdf_filename, 'url': local_url})
                            gendocu_logger.info(f"[APPLY-SIGNATURES] ✓ PDF guardado: {pdf_filename}")
                        else:
                            errores.append(f'Error subiendo {pdf_filename}: {error}')
                            gendocu_logger.error(f"[APPLY-SIGNATURES] Error guardando {pdf_filename}: {error}")
                    else:
                        errores.append(f'Error convirtiendo {doc_file.name} a PDF')
                        
                except Exception as e:
                    gendocu_logger.exception(f'[APPLY-SIGNATURES] Error procesando documento {doc_file.name}')
                    errores.append(f'Error en {doc_file.name}: {str(e)}')
                finally:
                    # Limpieza garantizada de temporales
                    if tmp_docx_path:
                        try:
                            if os.path.exists(tmp_docx_path):
                                os.unlink(tmp_docx_path)
                        except Exception as e:
                            gendocu_logger.warning(f'No se pudo eliminar {tmp_docx_path}: {e}')
                    if tmp_pdf_path:
                        try:
                            if os.path.exists(tmp_pdf_path):
                                os.unlink(tmp_pdf_path)
                        except Exception as e:
                            gendocu_logger.warning(f'No se pudo eliminar {tmp_pdf_path}: {e}')
            
            # Actualizar estado a 13 (documentos con firmas aplicadas)
            if archivos_generados:
                svc.update_asignacion_estado_doc(asignacion_id, 13)
                gendocu_logger.info(f'[APPLY-SIGNATURES] Completado: {len(archivos_generados)} archivos procesados, {len(errores)} errores')
                
                return jsonify({
                    'success': True,
                    'estado': 13,
                    'archivos': archivos_generados,
                    'correlativo': correlativo_str,
                    'errores': errores if errores else None
                }), 200
            else:
                # Todo falló
                svc.update_asignacion_estado_doc(asignacion_id, 130)
                return jsonify({
                    'success': False,
                    'estado': 130,
                    'message': 'No se pudo generar ningún documento con firmas',
                    'errores': errores
                }), 500
                
        except Exception as e:
            gendocu_logger.exception(f'Error generando documentos: {e}')
            svc.update_asignacion_estado_doc(asignacion_id, 130)
            return jsonify({'success': False, 'estado': 130, 'message': f'Error interno: {str(e)}'}), 500
        
    except Exception as e:
        gendocu_logger.exception(f'[APPLY-SIGNATURES] Error crítico: {e}')
        try:
            svc.update_asignacion_estado_doc(asignacion_id, 130)
        except:
            pass
        return jsonify({'success': False, 'estado': 130, 'message': f'Error interno: {str(e)}'}), 500


# ============================================================================
# Endpoint obsoleto eliminado: /apply-signatures-to-documents
# La conversión PDF→DOCX→PDF se ha reemplazado por regeneración directa
# de DOCX con firmas en /asignacion/<id>/apply-signatures
# ============================================================================


@devices_bp.post('/asignacion/<int:asignacion_id>/upload-signed-files')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def upload_signed_files(asignacion_id: int):
    """
    PASO C3: Sube archivos firmados manualmente a OneDrive.
    
    Input: FormData con archivos PDF
    Output: { success, estado: 22 | 210, archivos: [...] }
    """
    svc = DeviceService()
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        estado_actual = asignacion.get('estado_documentacion', 0)
        if estado_actual not in [21, 23]:  # Permitir desde estado 21 o 23 (resubida)
            return jsonify({'success': False, 'message': f'Estado inválido. Actual: {estado_actual}'}), 400
        
        # Obtener archivos de la petición
        if 'archivos' not in request.files:
            return jsonify({'success': False, 'message': 'No se recibieron archivos'}), 400
        
        archivos = request.files.getlist('archivos')
        if not archivos:
            return jsonify({'success': False, 'message': 'Lista de archivos vacía'}), 400
        
        # Obtener empleado y código
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        if not empleado:
            return jsonify({'success': False, 'message': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        if not codigo_empleado:
            return jsonify({'success': False, 'message': 'Código de empleado no disponible'}), 404
        
        # Validar nomenclatura de archivos
        # Formato esperado: PRO-TI-CE-XXX-NNNNNN <Tipo>.pdf
        import re
        pattern = r'^PRO-TI-CE-\w{3}-\d{6}\s.+\.pdf$'
        
        archivos_validos = []
        errores = []
        
        for archivo in archivos:
            if not archivo.filename:
                continue
            
            # Validar extensión
            if not archivo.filename.lower().endswith('.pdf'):
                errores.append(f'{archivo.filename}: debe ser PDF')
                continue
            
            # Validar nomenclatura
            if not re.match(pattern, archivo.filename):
                errores.append(f'{archivo.filename}: nomenclatura incorrecta (PRO-TI-CE-XXX-NNNNNN <Tipo>.pdf)')
                continue
            
            archivos_validos.append(archivo)
        
        if not archivos_validos:
            svc.update_asignacion_estado_doc(asignacion_id, 210)
            return jsonify({
                'success': False,
                'estado': 210,
                'message': 'Ningún archivo válido para subir',
                'errores': errores
            }), 400
        
        # Eliminar documentos previos de OneDrive
        from admin_disp.services.documento_folder_service import save_documento_to_onedrive, delete_all_documentos_from_onedrive
        
        delete_all_documentos_from_onedrive(codigo_empleado)
        
        # Subir archivos a OneDrive
        archivos_subidos = []
        
        for archivo in archivos_validos:
            try:
                file_content = archivo.read()
                success, url, error = save_documento_to_onedrive(codigo_empleado, archivo.filename, file_content)
                
                if success:
                    archivos_subidos.append({'nombre': archivo.filename, 'url': url})
                else:
                    errores.append(f'{archivo.filename}: {error}')
                    
            except Exception as e:
                logger.exception(f'Error subiendo {archivo.filename}')
                errores.append(f'{archivo.filename}: {str(e)}')
        
        if archivos_subidos:
            nuevo_estado = 22 if not errores else 210
            svc.update_asignacion_estado_doc(asignacion_id, nuevo_estado)
            
            return jsonify({
                'success': True,
                'estado': nuevo_estado,
                'archivos': archivos_subidos,
                'errores': errores if errores else None
            }), 200
        else:
            svc.update_asignacion_estado_doc(asignacion_id, 210)
            return jsonify({
                'success': False,
                'estado': 210,
                'message': 'No se pudo subir ningún archivo',
                'errores': errores
            }), 500
        
        logger.info(f'Archivos firmados subidos para asignación {asignacion_id}')
        
        return jsonify({'success': True, 'estado': 22}), 200
        
    except Exception as e:
        logger.exception(f'Error en upload-signed-files: {e}')
        svc.update_asignacion_estado_doc(asignacion_id, 210)
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}', 'estado': 210}), 500


@devices_bp.post('/asignacion/<int:asignacion_id>/review-documents')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def review_documents(asignacion_id: int):
    """
    PASO C4-C6: Revisor aprueba o rechaza documentos.
    
    Input: { accion: "aprobar" | "rechazar", comentario: str }
    Output: { success, estado: 24 | 23 }
    """
    svc = DeviceService()
    
    try:
        data = request.get_json() or {}
        accion = data.get('accion')
        comentario = data.get('comentario', '')
        
        if accion not in ['aprobar', 'rechazar']:
            return jsonify({'success': False, 'message': 'Acción inválida'}), 400
        
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        estado_actual = asignacion.get('estado_documentacion', 0)
        if estado_actual != 22:
            return jsonify({'success': False, 'message': f'Estado inválido. Actual: {estado_actual}, esperado: 22'}), 400
        
        if accion == 'aprobar':
            nuevo_estado = 24
            mensaje = 'Documentos aprobados'
        else:
            nuevo_estado = 23
            mensaje = f'Documentos rechazados: {comentario}'
        
        svc.update_asignacion_estado_doc(asignacion_id, nuevo_estado)
        
        # Registrar en logs
        usuario = session.get('username', 'desconocido')
        logger.info(f'Revisión de asignación {asignacion_id} por {usuario}: {accion} - {comentario}')
        
        return jsonify({'success': True, 'estado': nuevo_estado, 'message': mensaje}), 200
        
    except Exception as e:
        logger.exception(f'Error en review-documents: {e}')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


@devices_bp.get('/asignacion/<int:asignacion_id>/documentation-status')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def documentation_status(asignacion_id: int):
    """
    Verifica el estado actual de documentación y sincronización con OneDrive.
    
    Output: { estado, archivos: [...], sincronizado: bool }
    """
    svc = DeviceService()
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        estado_bd = asignacion.get('estado_documentacion', 0)
        
        # Obtener empleado y código
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        if not empleado:
            return jsonify({'success': False, 'message': 'Empleado no encontrado'}), 404
        
        codigo_empleado = empleado.get('codigo_empleado')
        if not codigo_empleado:
            return jsonify({'success': False, 'message': 'Código de empleado no disponible'}), 404
        
        # Listar archivos en OneDrive
        from admin_disp.services.documento_folder_service import list_documentos_from_onedrive
        
        success, archivos, error = list_documentos_from_onedrive(codigo_empleado)
        
        if not success:
            return jsonify({
                'success': False,
                'message': f'Error consultando OneDrive: {error}',
                'estado_bd': estado_bd,
                'archivos': [],
                'sincronizado': False
            }), 500
        
        # Verificar sincronización: si estado > 0 debe haber archivos
        sincronizado = True
        if estado_bd > 0 and estado_bd < 90:
            if not archivos:
                sincronizado = False
        
        return jsonify({
            'success': True,
            'estado_bd': estado_bd,
            'archivos': archivos,
            'sincronizado': sincronizado
        }), 200
        
    except Exception as e:
        logger.exception(f'Error en documentation-status: {e}')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


@devices_bp.post('/asignacion/<int:asignacion_id>/cancel-documentation')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def cancel_documentation(asignacion_id: int):
    """
    FLUJO D: Cancela el proceso de documentación, elimina archivos y cambia estado a 99.
    """
    svc = DeviceService()
    
    try:
        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404
        
        # Obtener empleado y código
        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        if empleado and empleado.get('codigo_empleado'):
            codigo_empleado = empleado.get('codigo_empleado')
            
            # Eliminar archivos de OneDrive
            from admin_disp.services.documento_folder_service import delete_all_documentos_from_onedrive
            
            try:
                delete_all_documentos_from_onedrive(codigo_empleado)
                logger.info(f'Archivos eliminados de OneDrive para código {codigo_empleado}')
            except Exception as e:
                logger.warning(f'Error eliminando archivos de OneDrive: {e}')
        
        svc.update_asignacion_estado_doc(asignacion_id, 99)
        
        logger.info(f'Proceso de documentación cancelado para asignación {asignacion_id}')
        
        return jsonify({'success': True, 'estado': 99}), 200
        
    except Exception as e:
        logger.exception(f'Error en cancel-documentation: {e}')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


@devices_bp.post('/delete-documents-by-correlativo')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def delete_documents_by_correlativo():
    """
    Elimina todos los documentos OneDrive de una asignación y restablece
    estado_documentacion a 0, permitiendo regenerar desde el inicio.
    
    Body JSON: { "correlativo": "...", "asignacion_id": <int> }
    """
    svc = DeviceService()
    try:
        data = request.get_json(force=True) or {}
        asignacion_id = data.get('asignacion_id')
        correlativo = (data.get('correlativo') or '').strip()

        if not asignacion_id:
            return jsonify({'success': False, 'message': 'asignacion_id es requerido'}), 400

        asignacion = svc.get_asignacion(int(asignacion_id))
        if not asignacion:
            return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404

        empleado_id = asignacion.get('fk_id_empleado')
        empleado = svc.get_empleado(empleado_id)
        if empleado and empleado.get('codigo_empleado'):
            codigo_empleado = empleado.get('codigo_empleado')
            from admin_disp.services.documento_folder_service import delete_all_documentos_from_onedrive
            try:
                delete_all_documentos_from_onedrive(codigo_empleado)
                logger.info(f'Archivos eliminados de OneDrive para correlativo {correlativo} (código {codigo_empleado})')
            except Exception as e:
                logger.warning(f'Error eliminando archivos de OneDrive en regenerar: {e}')

        svc.update_asignacion_estado_doc(int(asignacion_id), 0)
        logger.info(f'Estado de documentación restablecido a 0 para asignación {asignacion_id} (correlativo {correlativo})')

        return jsonify({'success': True, 'message': 'Documentos eliminados y estado restablecido'}), 200

    except Exception as e:
        logger.exception(f'Error en delete-documents-by-correlativo: {e}')
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


# ============================================================================
# FIN NUEVOS ENDPOINTS
# ============================================================================


    @devices_bp.get('/asignacion/<int:asignacion_id>/onedrive-files')
    @require_roles(['operador','admin'], sistema='dispositivos')
    def onedrive_files(asignacion_id: int):
        """Lista archivos PDF en la carpeta OneDrive del empleado (IT/Administracion de Dispositivos/<YEAR>/<CODIGO_EMPLEADO>)."""
        svc = DeviceService()
        try:
            asignacion = svc.get_asignacion(asignacion_id)
            if not asignacion:
                return jsonify({'success': False, 'message': 'Asignación no encontrada'}), 404

            empleado_id = asignacion.get('fk_id_empleado')
            empleado = svc.get_empleado(empleado_id)
            if not empleado:
                return jsonify({'success': False, 'message': 'Empleado no encontrado'}), 404

            codigo_empleado = empleado.get('codigo_empleado')
            if not codigo_empleado:
                return jsonify({'success': False, 'message': 'Código de empleado no disponible'}), 404

            from admin_disp.services.documento_folder_service import list_documentos_from_onedrive
            success, files, error = list_documentos_from_onedrive(codigo_empleado)
            if not success:
                return jsonify({'success': False, 'message': error or 'Error listando archivos'}), 500

            return jsonify({'success': True, 'files': files}), 200

        except Exception as e:
            logger.exception(f'Error en onedrive-files: {e}')
            return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


            @devices_bp.get('/onedrive-files')
            @require_roles(['operador','admin'], sistema='dispositivos')
            def onedrive_files_by_code():
                """Lista archivos PDF en la carpeta OneDrive dado un `codigo` (query param).
                Uso: /devices/onedrive-files?codigo=P-EM-000125
                """
                try:
                    codigo = request.args.get('codigo')
                    if not codigo:
                        return jsonify({'success': False, 'message': 'codigo query param requerido'}), 400

                    # Llamar al servicio que lista por codigo
                    from admin_disp.services.documento_folder_service import list_documentos_from_onedrive
                    success, files, error = list_documentos_from_onedrive(codigo)
                    if not success:
                        return jsonify({'success': False, 'message': error or 'Error listando archivos'}), 500

                    return jsonify({'success': True, 'files': files}), 200

                except Exception as e:
                    logger.exception(f'Error en onedrive-files-by-code: {e}')
                    return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


            @devices_bp.get('/onedrive/documento/<string:codigo>/<path:filename>')
            @require_roles(['operador','admin'], sistema='dispositivos')
            def download_documento_by_code(codigo: str, filename: str):
                """Descarga un documento PDF por `codigo` de empleado y lo sirve al navegador.
                Ruta: /devices/onedrive/documento/<codigo>/<filename>
                """
                from flask import send_file


# ============================================================================
# ENDPOINTS DE TEST - OneDrive PDF Viewer
# ============================================================================


# ==============================
# SHAREPOINT FOLDERS MANAGEMENT
# ==============================
@devices_bp.post('/sharepoint/eliminar-carpetas-numeradas')
@require_roles(['admin','operador'], sistema='dispositivos')
def eliminar_carpetas_numeradas():
    """
    Elimina las carpetas 01..12 dentro de IT/Administracion de Dispositivos/2026 si existen.
    """
    # Endpoint removed: deletion of numbered folders is no longer exposed.
    return jsonify({'success': False, 'message': 'Endpoint deshabilitado'}), 404