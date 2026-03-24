from functools import wraps
from flask import session, jsonify, redirect, url_for, request, abort
import time

# Roles soportados: admin, operador, auditor, superAdmin
# Las rutas pueden usar @require_roles([...], sistema='nombre_sistema')

VALID_ROLES = {"admin", "operador", "auditor", "superAdmin"}
VALID_SISTEMAS = {"dispositivos", "kardex", "cxc"}  # nombres cortos de sistemas

# Rate limiting simple: dict de {user_id: [(timestamp, endpoint), ...]}
_rate_limit_cache = {}
_RATE_LIMIT_WINDOW = 60  # segundos
_RATE_LIMIT_MAX_REQUESTS = 100  # máximo de requests por ventana

# IP-based rate limiting for login endpoint (brute-force protection)
_login_attempt_cache: dict = {}  # {ip: [timestamp, ...]}
_LOGIN_RATE_WINDOW: int = 300     # 5-minute sliding window
_LOGIN_MAX_ATTEMPTS: int = 10     # max attempts per window per IP

def require_ajax():
    """Decorador que requiere que la petición sea AJAX (protege endpoints de datos sensibles)"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Verificar que sea petición AJAX
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                request.headers.get('HX-Request') == 'true' or  # HTMX
                'fetch' in request.headers.get('Sec-Fetch-Mode', '')
            )
            
            if not is_ajax:
                abort(403)  # Forbidden - no permitir acceso directo
            
            return f(*args, **kwargs)
        return wrapper
    return decorator

def rate_limit():
    """Decorador para rate limiting básico por usuario"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                abort(401)  # No autenticado
            
            now = time.time()
            endpoint = request.endpoint
            
            # Limpiar registros antiguos
            if user_id in _rate_limit_cache:
                _rate_limit_cache[user_id] = [
                    (ts, ep) for ts, ep in _rate_limit_cache[user_id]
                    if now - ts < _RATE_LIMIT_WINDOW
                ]
            else:
                _rate_limit_cache[user_id] = []
            
            # Verificar límite
            if len(_rate_limit_cache[user_id]) >= _RATE_LIMIT_MAX_REQUESTS:
                abort(429)  # Too Many Requests
            
            # Registrar petición
            _rate_limit_cache[user_id].append((now, endpoint))
            
            return f(*args, **kwargs)
        return wrapper
    return decorator


def login_rate_limit():
    """IP-based rate limiter for the login endpoint.

    Limits each remote IP to _LOGIN_MAX_ATTEMPTS requests within _LOGIN_RATE_WINDOW
    seconds to prevent brute-force credential attacks.  Returns HTTP 429 when the
    limit is exceeded.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or '0.0.0.0'
            now = time.time()

            # Purge stale timestamps outside the sliding window
            _login_attempt_cache[ip] = [
                ts for ts in _login_attempt_cache.get(ip, [])
                if now - ts < _LOGIN_RATE_WINDOW
            ]

            if len(_login_attempt_cache[ip]) >= _LOGIN_MAX_ATTEMPTS:
                abort(429)  # Too Many Requests

            # Record this attempt BEFORE forwarding so every attempt counts,
            # including requests that result in 401 (wrong password).
            _login_attempt_cache[ip].append(now)

            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_roles(allowed_roles, sistema=None):
    """
    Decorador para validar roles de usuario.
    
    Args:
        allowed_roles: Lista de roles permitidos ['admin', 'operador', 'auditor']
        sistema: (Opcional) Nombre del sistema ('dispositivos', 'kardex', 'cxc')
                Si se omite, valida roles globales (para retrocompatibilidad)
    
    Ejemplos:
        @require_roles(['admin'], sistema='dispositivos')  # Admin de dispositivos
        @require_roles(['admin', 'operador'])  # Cualquier admin u operador (sin sistema específico)
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # SuperAdmin siempre tiene acceso
            if session.get('is_super_admin'):
                return f(*args, **kwargs)
            
            if sistema:
                # Validar rol en sistema específico
                sistemas_roles = session.get('sistemas_roles', {})
                rol_en_sistema = sistemas_roles.get(sistema)
                
                if not rol_en_sistema or rol_en_sistema not in allowed_roles:
                    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'error': 'Acceso denegado: rol insuficiente en este sistema'}), 403
                    abort(403)
            else:
                # Validación retrocompatible (roles globales sin sistema)
                roles = session.get('roles', [])
                roles = [r for r in roles if r in VALID_ROLES]
                if not roles or not any(r in allowed_roles for r in roles):
                    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return jsonify({'error': 'Acceso denegado'}), 403
                    abort(403)
            
            return f(*args, **kwargs)
        return wrapper
    return decorator
