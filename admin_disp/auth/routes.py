from datetime import datetime
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for, current_app
from .service import AuthService, AuthServiceExtended, remap_estado_empleado
from ..common.rbac import require_roles, login_rate_limit
import logging
import os
from functools import wraps

logger = logging.getLogger('admin_disp.auth')
auth_bp = Blueprint('auth', __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_company_name():
    return current_app.config.get('COMPANY_NAME', 'PROIMA')


def login_required(f):
    """Verifica que el usuario esté autenticado. Si no, lo redirige al login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            if request.is_json:
                return jsonify({'error': 'No autenticado'}), 401
            return redirect(url_for('auth.login_form'))
        return f(*args, **kwargs)
    return decorated


def _build_legacy_roles(sistemas_roles):
    """Extrae una lista plana de roles para retrocompatibilidad con código legacy."""
    keys = ('dispositivos', 'kardex', 'cxc')
    return [sistemas_roles[k] for k in keys if sistemas_roles.get(k)]


# ---------------------------------------------------------------------------
# Rutas públicas
# ---------------------------------------------------------------------------

@auth_bp.get('/login')
def login_form():
    """Renderiza la página de inicio de sesión."""
    return render_template('login.html', company_name=_get_company_name())


@auth_bp.post('/login')
@login_rate_limit()
def login():
    if request.is_json:
        data = request.get_json(force=True)
        username = data.get('username')
        password = data.get('password')
    else:
        username = request.form.get('username')
        password = request.form.get('password')

    logger.info(
        'Login attempt from %s username="%s" json=%s password_provided=%s',
        request.remote_addr, username, request.is_json, bool(password)
    )

    svc = AuthService()
    ok, user = svc.verify_credentials(username, password)

    if not ok:
        if request.is_json:
            return jsonify({'error': 'Credenciales inválidas'}), 401
        return render_template('login.html', error='Credenciales inválidas',
                               company_name=_get_company_name()), 401

    svc_ext = AuthServiceExtended()
    try:
        sistemas_roles = svc_ext.get_user_systems_roles(user[0])
    except Exception:
        logger.exception('Error obteniendo roles para user %s', user[0])
        try:
            old_roles = svc.get_user_roles(user[0])
            sistemas_roles = {
                'dispositivos': old_roles[0] if old_roles else None,
                'kardex': None,
                'cxc': None,
                'is_super_admin': False,
            }
        except Exception:
            sistemas_roles = {'dispositivos': None, 'kardex': None, 'cxc': None, 'is_super_admin': False}

    roles_legacy = _build_legacy_roles(sistemas_roles)
    empleado_nombre = svc.get_empleado_name(user[0])
    empleado_sucursal = svc.get_empleado_sucursal(user[0])

    # Normalizar nombre de empleado para usuarios especiales (mapeos rápidos)
    username_val = (user[1] or '').lower()
    if username_val == 'joel.reyes@proimahn.com':
        empleado_nombre = 'Joel Reyes'

    session['user_id'] = user[0]
    session['username'] = user[1]
    session['empleado_nombre'] = (empleado_nombre or user[1])
    session['empleado_sucursal'] = empleado_sucursal or ''
    session['sistemas_roles'] = sistemas_roles
    session['is_super_admin'] = sistemas_roles.get('is_super_admin', False)
    session['roles'] = roles_legacy
    session['rol_nombre'] = (
        'SuperAdmin' if session['is_super_admin'] else (roles_legacy[0] if roles_legacy else 'Usuario')
    )

    logger.info('Login exitoso para %s - Roles: %s', user[1], sistemas_roles)

    if request.is_json:
        return jsonify({'ok': True, 'roles': roles_legacy})
    return redirect(url_for('auth.menu'))


@auth_bp.post('/validar-usuario')
def validar_usuario():
    """Valida si el usuario existe y si tiene código vigente.

    Este endpoint es usado exclusivamente por el flujo de "Olvidó su contraseña".
    """
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').strip()

        if not username:
            return jsonify({'error': 'Usuario requerido'}), 400

        svc = AuthService()
        cur = svc.conn.cursor()
        cur.execute(
            "SELECT id_usuario, fecha_ultimo_acceso, codigo, fecha_codigo FROM usuarios WHERE username = ?",
            (username,)
        )
        user_row = cur.fetchone()

        if not user_row:
            return jsonify({'error': 'Usuario no encontrado'}), 404

        user_id, fecha_ultimo_acceso, codigo, fecha_codigo = user_row

        vigente = False
        if codigo and fecha_codigo:
            from datetime import timedelta
            vigente = (fecha_codigo + timedelta(hours=1)) > datetime.now()

        return jsonify({
            'success': True,
            'user_id': user_id,
            'username': username,
            'tiene_codigo': bool(codigo),
            'codigo_vigente': vigente,
            'fecha_ultimo_acceso': fecha_ultimo_acceso.isoformat() if fecha_ultimo_acceso else None,
        }), 200

    except Exception:
        logger.exception('Error en validar_usuario')
        return jsonify({'error': 'Error al validar usuario'}), 500


@auth_bp.post('/request-reset')
def request_reset():
    """Registra una solicitud de recuperación de contraseña para que TI la procese."""
    try:
        data = request.get_json(force=True)
        username = (data.get('username') or '').strip()

        if not username:
            return jsonify({'error': 'Usuario requerido'}), 400

        logs_dir = os.path.abspath(os.path.join(current_app.root_path, '..', 'logs'))
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, 'request_reset.log')
        line = f"{datetime.utcnow().isoformat()}Z REQUEST_RESET {request.remote_addr} {username}\n"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line)

        return jsonify({'ok': True, 'message': 'Solicitud registrada. El departamento de TI procesará su petición.'}), 200

    except Exception:
        logger.exception('Error en request_reset')
        return jsonify({'error': 'Error interno'}), 500


@auth_bp.post('/logs/<page>')
def client_logs(page):
    """Recibe logs del frontend y los persiste en archivos bajo /logs."""
    try:
        data = request.get_json(force=False, silent=True) or {}
        level = data.get('level', 'INFO') if isinstance(data, dict) else 'INFO'
        message = data.get('message', '') if isinstance(data, dict) else (request.get_data(as_text=True) or '').strip()

        logs_dir = os.path.abspath(os.path.join(current_app.root_path, '..', 'logs'))
        os.makedirs(logs_dir, exist_ok=True)
        log_file = os.path.join(logs_dir, f"{page}.log")
        line = f"{datetime.utcnow().isoformat()}Z [{level}] {request.remote_addr} {message}\n"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line)

        return jsonify({'ok': True}), 200

    except Exception:
        logger.exception('Error en client_logs')
        return jsonify({'error': 'Error al escribir log'}), 500


@auth_bp.get('/menu')
@login_required
def menu():
    return render_template('menu.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    if request.is_json:
        return jsonify({'ok': True})
    return redirect(url_for('auth.login_form'))


@auth_bp.get('/me')
@require_roles(['reporteria', 'operador', 'admin'])
def me():
    return jsonify({
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'roles': session.get('roles', []),
    })


# ---------------------------------------------------------------------------
# Gestión de usuarios (primer admin / legacy)
# ---------------------------------------------------------------------------

@auth_bp.post('/create-first-admin')
def create_first_admin():
    """Crea el primer usuario admin (solo disponible si no existe ningún usuario)."""
    try:
        svc = AuthService()
        if svc.is_first_user_exists():
            return jsonify({'error': 'Ya existe un administrador. No se puede crear otro.'}), 403

        data = request.get_json(force=True)
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or len(username) < 3:
            return jsonify({'error': 'Username debe tener al menos 3 caracteres'}), 400
        if not password or len(password) < 6:
            return jsonify({'error': 'Contraseña debe tener al menos 6 caracteres'}), 400

        success, result = svc.create_first_admin_usuario(username, password)
        if success:
            return jsonify({'ok': True, 'user_id': result, 'message': 'Administrador creado exitosamente. Inicia sesión ahora.'}), 201
        return jsonify({'error': result}), 400

    except Exception:
        logger.exception('Error en create_first_admin')
        return jsonify({'error': 'Error interno'}), 500


@auth_bp.post('/create-user')
@require_roles(['admin'], sistema='dispositivos')
def create_user_api():
    """Crea un nuevo usuario con hash de contraseña y rol (solo admin)."""
    try:
        svc = AuthService()
        data = request.get_json(force=True)

        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        role_name = data.get('role_name', '').strip()
        employee_id = data.get('employee_id')

        if not username:
            return jsonify({'success': False, 'error': 'El nombre de usuario es requerido'}), 400
        if not password:
            return jsonify({'success': False, 'error': 'La contraseña es requerida'}), 400
        if not role_name:
            return jsonify({'success': False, 'error': 'El rol es requerido'}), 400

        success, result = svc.create_user(username, password, role_name, employee_id)
        if success:
            return jsonify({'success': True, 'user_id': result, 'message': f'Usuario {username} creado exitosamente'}), 201
        return jsonify({'success': False, 'error': result}), 400

    except Exception:
        logger.exception('Error en create_user_api')
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@auth_bp.get('/employees')
@require_roles(['operador', 'admin'])
def list_employees_api():
    svc = AuthService()
    return jsonify({'employees': svc.get_all_employees()})


# ---------------------------------------------------------------------------
# Gestión de usuarios multi-sistema
# ---------------------------------------------------------------------------

def _require_super_admin():
    """Devuelve una respuesta 403 si el usuario no es superAdmin, o None si sí lo es."""
    if not session.get('is_super_admin'):
        return jsonify({'error': 'Solo superAdmin puede gestionar usuarios'}), 403
    return None


@auth_bp.get('/empleados/activos')
@require_roles(['admin'], sistema='dispositivos')
def get_empleados_activos():
    """Retorna empleados activos con email para validación de autofill."""
    err = _require_super_admin()
    if err:
        return err
    try:
        return jsonify({'empleados': AuthServiceExtended().get_active_employees_with_email()}), 200
    except Exception:
        logger.exception('Error en get_empleados_activos')
        return jsonify({'error': 'Error al obtener empleados'}), 500


@auth_bp.get('/empleados/todos-activos')
@require_roles(['admin'], sistema='dispositivos')
def get_todos_empleados_activos():
    """Retorna TODOS los empleados activos, incluyendo los que no tienen usuario."""
    err = _require_super_admin()
    if err:
        return err
    try:
        return jsonify({'empleados': AuthServiceExtended().get_all_active_employees()}), 200
    except Exception:
        logger.exception('Error en get_todos_empleados_activos')
        return jsonify({'error': 'Error al obtener empleados'}), 500


@auth_bp.get('/sistemas')
@require_roles(['admin'], sistema='dispositivos')
def get_sistemas():
    """Retorna la lista de sistemas disponibles."""
    err = _require_super_admin()
    if err:
        return err
    try:
        return jsonify({'sistemas': AuthServiceExtended().get_sistemas()}), 200
    except Exception:
        logger.exception('Error en get_sistemas')
        return jsonify({'error': 'Error al obtener sistemas'}), 500


@auth_bp.get('/roles')
@require_roles(['admin'], sistema='dispositivos')
def get_roles_genericos():
    """Retorna roles genéricos (excluye superAdmin)."""
    err = _require_super_admin()
    if err:
        return err
    try:
        return jsonify({'roles': AuthServiceExtended().get_roles_genericos()}), 200
    except Exception:
        logger.exception('Error en get_roles_genericos')
        return jsonify({'error': 'Error al obtener roles'}), 500


@auth_bp.get('/usuarios')
@require_roles(['admin'], sistema='dispositivos')
def get_all_usuarios():
    """Retorna lista de todos los usuarios."""
    err = _require_super_admin()
    if err:
        return err
    try:
        return jsonify({'usuarios': AuthServiceExtended().get_all_users()}), 200
    except Exception:
        logger.exception('Error en get_all_usuarios')
        return jsonify({'error': 'Error al obtener usuarios'}), 500


@auth_bp.post('/usuarios/create')
@require_roles(['admin'], sistema='dispositivos')
def create_usuario_multi_sistema():
    """Crea usuario con roles asignados por sistema."""
    err = _require_super_admin()
    if err:
        return err
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        employee_id = data.get('employee_id')
        sistemas_roles = data.get('sistemas_roles', {})

        if not username:
            return jsonify({'error': 'El usuario es requerido'}), 400
        if not employee_id:
            return jsonify({'error': 'Debe seleccionar un empleado'}), 400

        success, result = AuthServiceExtended().create_user_with_systems(username, password, employee_id, sistemas_roles)
        if success:
            return jsonify({'success': True, 'user_id': result['user_id'], 'message': f'Usuario {username} creado exitosamente'}), 201
        return jsonify({'error': result}), 400

    except Exception:
        logger.exception('Error en create_usuario_multi_sistema')
        return jsonify({'error': 'Error al crear usuario'}), 500


@auth_bp.get('/usuarios/<int:user_id>')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def get_usuario_by_id(user_id):
    """Retorna información detallada de un usuario específico."""
    try:
        usuario = AuthServiceExtended().get_usuario_by_id(user_id)
        if usuario:
            return jsonify({'usuario': usuario}), 200
        return jsonify({'error': 'Usuario no encontrado'}), 404
    except Exception:
        logger.exception('Error en get_usuario_by_id')
        return jsonify({'error': 'Error al obtener usuario'}), 500


@auth_bp.get('/usuarios/<int:user_id>/roles')
@require_roles(['operador', 'admin'], sistema='dispositivos')
def get_usuario_roles(user_id):
    """Retorna roles actuales de un usuario por sistema."""
    try:
        return jsonify({'sistemas_roles': AuthServiceExtended().get_user_systems_roles(user_id)}), 200
    except Exception:
        logger.exception('Error en get_usuario_roles')
        return jsonify({'error': 'Error al obtener roles'}), 500


@auth_bp.put('/usuarios/<int:user_id>/roles')
@require_roles(['admin'], sistema='dispositivos')
def update_usuario_roles(user_id):
    """Actualiza roles de un usuario en los sistemas (solo SuperAdmin)."""
    err = _require_super_admin()
    if err:
        return err
    try:
        data = request.get_json(force=True)
        sistemas_roles = data.get('sistemas_roles', {})
        usuario_actual = session.get('username', 'UNKNOWN')
        success, message = AuthServiceExtended().update_user_systems_roles(
            user_id, 
            sistemas_roles, 
            usuario_actual=usuario_actual
        )
        if success:
            return jsonify({'success': True, 'message': message}), 200
        return jsonify({'error': message}), 400
    except Exception:
        logger.exception('Error en update_usuario_roles')
        return jsonify({'error': 'Error al actualizar roles'}), 500


@auth_bp.get('/usuarios/<int:user_id>/codigo')
@require_roles(['admin'], sistema='dispositivos')
def get_codigo_temporal(user_id):
    """Obtiene el código temporal de un usuario (solo SuperAdmin)."""
    err = _require_super_admin()
    if err:
        return err
    try:
        success, result = AuthServiceExtended().get_codigo_temporal(user_id)
        if success:
            return jsonify({'success': True, **result}), 200
        return jsonify({'error': result}), 400
    except Exception:
        logger.exception('Error en get_codigo_temporal')
        return jsonify({'error': 'Error al obtener código'}), 500


@auth_bp.post('/usuarios/<int:user_id>/codigo/regenerar')
@require_roles(['admin'], sistema='dispositivos')
def regenerar_codigo_temporal(user_id):
    """Regenera el código temporal de un usuario (solo SuperAdmin)."""
    err = _require_super_admin()
    if err:
        return err
    try:
        success, result = AuthServiceExtended().regenerar_codigo_temporal(user_id)
        if success:
            return jsonify({'success': True, 'fecha_generacion': datetime.now().isoformat(), **result}), 200
        return jsonify({'error': result}), 400
    except Exception:
        logger.exception('Error en regenerar_codigo_temporal')
        return jsonify({'error': 'Error al regenerar código'}), 500


@auth_bp.post('/validar-codigo')
def validar_codigo_temporal():
    """Valida el código temporal de un usuario (endpoint público para recuperación)."""
    try:
        data = request.get_json(force=True)
        username = data.get('username', '').strip()
        codigo = data.get('codigo', '').strip()

        if not username or not codigo:
            return jsonify({'error': 'Usuario y código son requeridos'}), 400
        if len(codigo) != 6 or not codigo.isdigit():
            return jsonify({'error': 'El código debe ser de 6 dígitos'}), 400

        success, result = AuthServiceExtended().validar_codigo_temporal(username, codigo)
        if success:
            session['codigo_validado'] = True
            session['temp_user_id'] = result['user_id']
            session['temp_username'] = result['username']
            return jsonify({'success': True, 'message': 'Código válido. Proceda a establecer su contraseña.', 'user_id': result['user_id']}), 200
        return jsonify({'error': result}), 400

    except Exception:
        logger.exception('Error en validar_codigo_temporal')
        return jsonify({'error': 'Error al validar código'}), 500


@auth_bp.post('/establecer-password')
def establecer_password():
    """Establece la contraseña definitiva tras validar código temporal."""
    try:
        if not session.get('codigo_validado'):
            return jsonify({'error': 'Debe validar el código temporal primero'}), 403

        data = request.get_json(force=True)
        password = data.get('password', '').strip()
        password_confirm = data.get('password_confirm', '').strip()

        if not password:
            return jsonify({'error': 'La contraseña es requerida'}), 400
        if password != password_confirm:
            return jsonify({'error': 'Las contraseñas no coinciden'}), 400

        user_id = session.get('temp_user_id')
        if not user_id:
            return jsonify({'error': 'No se identificó el usuario'}), 400

        success, message = AuthServiceExtended().establecer_password(user_id, password)
        if success:
            session.pop('codigo_validado', None)
            session.pop('temp_user_id', None)
            session.pop('temp_username', None)
            return jsonify({'success': True, 'message': message}), 200
        return jsonify({'error': message}), 400

    except Exception:
        logger.exception('Error en establecer_password')
        return jsonify({'error': 'Error al establecer contraseña'}), 500


@auth_bp.post('/sync-from-sharepoint')
def sync_from_sharepoint():
    """Webhook para sincronizar usuarios.estado desde empleados.estado."""
    try:
        cfg_secret = current_app.config.get('SHAREPOINT_SYNC_SECRET')
        if cfg_secret and cfg_secret != request.headers.get('X-Shared-Secret'):
            logger.warning('Unauthorized sync_from_sharepoint call')
            return jsonify({'error': 'Unauthorized'}), 401

        updated = AuthServiceExtended().sync_users_with_empleados_estado()
        logger.info('SharePoint sync triggered. usuarios updated: %s', updated)
        return jsonify({'success': True, 'updated': updated}), 200

    except Exception:
        logger.exception('Error en sync_from_sharepoint')
        return jsonify({'error': 'Error al sincronizar'}), 500



