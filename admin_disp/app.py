from flask import Flask, request, got_request_exception, render_template, Response, stream_with_context, url_for, redirect, send_from_directory, jsonify, session
import requests
import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


class SafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """TimedRotatingFileHandler that swallows file-rotation PermissionError on Windows.

    On Windows, os.rename used by the base handler can raise PermissionError
    if another process temporarily holds the file. We override doRollover
    to ignore such errors so the application doesn't emit logging internal
    tracebacks to stderr while still attempting rotation.
    """
    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            # Ignore permission errors during rotation (file locked by another process)
            return
        except OSError:
            # Be conservative and ignore OS-level rename errors as well
            return

# Scheduler
try:
    from apscheduler.schedulers.background import BackgroundScheduler
except Exception:
    BackgroundScheduler = None
from .config import Config
from .core.db import init_db_connections
from .auth.routes import auth_bp
from .devices.routes import devices_bp
from .services.docexp import docexp_bp


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)
    app.config['SESSION_TYPE'] = 'filesystem'

    # MS Graph credentials are expected to come from environment/config (`admin_disp.config`)

    init_db_connections(app)

    # ============================================================================
    # CONFIGURACIÓN DE LOGGING CENTRALIZADO
    # ============================================================================
    # Estructura:
    # - Logs por página principal: dispositivos.log, asignaciones.log, reclamos.log, planes.log
    # - Log unificado de servicios: services.log (con identificación de servicio en el mensaje)
    # - Logs específicos para servicios críticos: empleados_sync.log, printer.log
    # - Log de autenticación: auth.log
    # ============================================================================
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        log_dir = os.path.join(base_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Formato común para todos los logs
        log_format = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
        
        # 1. LOGS POR PÁGINA PRINCIPAL
        pages = ['dispositivos', 'asignaciones', 'reclamos', 'planes']
        for page in pages:
            logger_name = f'admin_disp.{page}'
            page_logger = logging.getLogger(logger_name)
            page_logger.setLevel(logging.INFO)
            file_path = os.path.join(log_dir, f'{page}.log')
            handler = SafeTimedRotatingFileHandler(file_path, when='midnight', backupCount=30, encoding='utf-8')
            handler.setFormatter(log_format)
            if not any(type(h) == type(handler) and getattr(h, 'baseFilename', None) == getattr(handler, 'baseFilename', None) for h in page_logger.handlers):
                page_logger.addHandler(handler)
        
        # 2. LOG UNIFICADO DE SERVICIOS (para todos los servicios generales)
        services_logger = logging.getLogger('admin_disp.services')
        services_logger.setLevel(logging.INFO)
        services_log_path = os.path.join(log_dir, 'services.log')
        services_handler = SafeTimedRotatingFileHandler(services_log_path, when='midnight', backupCount=30, encoding='utf-8')
        services_handler.setFormatter(log_format)
        if not any(type(h) == type(services_handler) and getattr(h, 'baseFilename', None) == getattr(services_handler, 'baseFilename', None) for h in services_logger.handlers):
            services_logger.addHandler(services_handler)
        
        # 3. LOGS ESPECÍFICOS PARA SERVICIOS CRÍTICOS
        
        # Sincronización de empleados (crítico - operación programada)
        empleados_logger = logging.getLogger('admin_disp.services.empleados_sync')
        empleados_logger.setLevel(logging.INFO)
        empleados_log_path = os.path.join(log_dir, 'empleados_sync.log')
        empleados_handler = SafeTimedRotatingFileHandler(empleados_log_path, when='midnight', backupCount=30, encoding='utf-8')
        empleados_handler.setFormatter(log_format)
        if not any(type(h) == type(empleados_handler) and getattr(h, 'baseFilename', None) == getattr(empleados_handler, 'baseFilename', None) for h in empleados_logger.handlers):
            empleados_logger.addHandler(empleados_handler)
        
        # Impresoras (crítico - operación programada)
        printer_logger = logging.getLogger('admin_disp.services.printer_reader')
        printer_logger.setLevel(logging.INFO)
        printer_log_path = os.path.join(log_dir, 'printer.log')
        printer_handler = SafeTimedRotatingFileHandler(printer_log_path, when='midnight', backupCount=30, encoding='utf-8')
        printer_handler.setFormatter(log_format)
        if not any(type(h) == type(printer_handler) and getattr(h, 'baseFilename', None) == getattr(printer_handler, 'baseFilename', None) for h in printer_logger.handlers):
            printer_logger.addHandler(printer_handler)
        

        
        # 4. LOG DE AUTENTICACIÓN
        auth_logger = logging.getLogger('admin_disp.auth')
        auth_logger.setLevel(logging.INFO)
        auth_log_path = os.path.join(log_dir, 'auth.log')
        auth_handler = SafeTimedRotatingFileHandler(auth_log_path, when='midnight', backupCount=30, encoding='utf-8')
        auth_handler.setFormatter(log_format)
        if not any(type(h) == type(auth_handler) and getattr(h, 'baseFilename', None) == getattr(auth_handler, 'baseFilename', None) for h in auth_logger.handlers):
            auth_logger.addHandler(auth_handler)

        # 5. LOG DE CUENTAS POR COBRAR (CxC)
        cxc_logger = logging.getLogger('admin_disp.cxc')
        cxc_logger.setLevel(logging.INFO)
        cxc_log_path = os.path.join(log_dir, 'cxc.log')
        cxc_handler = SafeTimedRotatingFileHandler(cxc_log_path, when='midnight', backupCount=30, encoding='utf-8')
        cxc_handler.setFormatter(log_format)
        if not any(type(h) == type(cxc_handler) and getattr(h, 'baseFilename', None) == getattr(cxc_handler, 'baseFilename', None) for h in cxc_logger.handlers):
            cxc_logger.addHandler(cxc_handler)

        # 6. LOG DE BACKUPS de bases de datos
        backup_logger = logging.getLogger('admin_disp.services.backup')
        backup_logger.setLevel(logging.INFO)
        backup_log_path = os.path.join(log_dir, 'backup.log')
        backup_handler = SafeTimedRotatingFileHandler(backup_log_path, when='midnight', backupCount=30, encoding='utf-8')
        backup_handler.setFormatter(log_format)
        if not any(type(h) == type(backup_handler) and getattr(h, 'baseFilename', None) == getattr(backup_handler, 'baseFilename', None) for h in backup_logger.handlers):
            backup_logger.addHandler(backup_handler)
        
    except Exception:
        app.logger.exception('No se pudo inicializar loggers de módulos')

    # ============================================================================
    # ERROR HANDLERS GLOBALES
    # ============================================================================
    @app.errorhandler(404)
    def not_found_error(error):
        """Manejo de páginas no encontradas."""
        app.logger.warning(f'404 Not Found: {request.url}')
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({'success': False, 'error': 'Recurso no encontrado'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden_error(error):
        """Manejo de acceso prohibido."""
        app.logger.warning(f'403 Forbidden: {request.url} - User: {session.get("user_id", "anonymous")}')
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({'success': False, 'error': 'Acceso prohibido'}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        """Manejo de errores internos del servidor."""
        app.logger.exception(f'500 Internal Server Error: {request.url}')
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
        return render_template('errors/500.html'), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        """Manejo global de excepciones no capturadas."""
        app.logger.exception(f'Unhandled Exception: {type(error).__name__} - {str(error)}')
        
        # Si es un error HTTP conocido, deja que Flask lo maneje
        if hasattr(error, 'code'):
            return error
        
        # Para excepciones genéricas
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({
                'success': False,
                'error': 'Ha ocurrido un error inesperado',
                'detail': str(error) if app.debug else None
            }), 500
        return render_template('errors/500.html'), 500

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(devices_bp, url_prefix='/devices')
    app.register_blueprint(docexp_bp)  # Ya tiene su propio prefix /api/docexp

    # Impresoras: historial y escaneo de tinta (prefijo /dispositivos)
    try:
        from .services.printer_reader import printerScanner
        if printerScanner is not None:
            app.register_blueprint(printerScanner)
            app.logger.info('Blueprint printerScanner registrado en /dispositivos')
    except Exception as _bp_exc:
        app.logger.warning(f'No se pudo registrar printerScanner: {_bp_exc}')

    # ── Cuentas por Cobrar (CxC) ─────────────────────────────────────────────
    try:
        from .cxc.routes import cxc_bp
        app.register_blueprint(cxc_bp)
        app.logger.info('Blueprint CxC registrado en /cxc')
        # Garantizar esquema de lotes/liquidaciones al arrancar
        with app.app_context():
            try:
                from .cxc.operations import ensure_lote_schema
                ensure_lote_schema()
            except Exception as _schema_exc:
                app.logger.error('ensure_lote_schema fallo: %s', _schema_exc, exc_info=True)
    except Exception as _cxc_exc:
        app.logger.exception('No se pudo registrar el blueprint CxC: %s', _cxc_exc)

    # ── KARDEX (Control de Inventario) ───────────────────────────────────────
    try:
        from .kardex.routes import kardex_bp
        app.register_blueprint(kardex_bp)
        app.logger.info('Blueprint KARDEX registrado en /kardex')
    except Exception as _kardex_exc:
        app.logger.exception('No se pudo registrar el blueprint KARDEX: %s', _kardex_exc)

    # ── INVENTARIO (Gestión de Inventario) ───────────────────────────────────
    try:
        from .inventario.routes import bp_inventario
        app.register_blueprint(bp_inventario)
        app.logger.info('Blueprint INVENTARIO registrado en /inventario')
    except Exception as _inventario_exc:
        app.logger.exception('No se pudo registrar el blueprint INVENTARIO: %s', _inventario_exc)

    # Registrar filtros personalizados de Jinja2
    @app.template_filter('format_correlativo')
    def format_correlativo_filter(correlativo):
        """
        Formatea un correlativo para display en la UI.
        
        - Si es el nuevo formato (PRO-TI-CE-XXX-NNNNNN), extrae el número
        - Si es un número, lo formatea con 6 dígitos  
        - Si es None o vacío, retorna '-'
        """
        if not correlativo:
            return '-'
        
        # Si es el nuevo formato completo (contiene guiones)
        if isinstance(correlativo, str) and '-' in correlativo:
            # Extraer el número de 6 dígitos del final
            try:
                partes = correlativo.split('-')
                if len(partes) >= 5:  # PRO-TI-CE-XXX-NNNNNN
                    return partes[-1].zfill(6)
            except Exception:
                pass
        
        # Si es un número (formato antiguo)
        try:
            return str(int(correlativo)).zfill(6)
        except (ValueError, TypeError):
            pass
        
        # Fallback: retornar como string
        return str(correlativo)

    # Sync health check endpoint (moved from services/routes.py)
    @app.route('/sync/health', methods=['GET'])
    def sync_health_check():
        """Health check endpoint for sync services."""
        return {'status': 'ok'}, 200

    @app.route('/sync/empleados', methods=['POST'])
    def sync_empleados_endpoint():
        """Endpoint para sincronizar empleados manualmente (UI). Requiere rol 'admin'."""
        try:
            roles = session.get('roles', []) if 'session' in globals() else []
        except Exception:
            roles = []

        # Simple role check (templates show the button only to admins)
        if 'admin' not in roles:
            return jsonify({'success': False, 'error': 'Permisos insuficientes'}), 403

        try:
            from .services.empleados_sync import sincronizar_empleados
            svc_logger = logging.getLogger('admin_disp.services.empleados_sync')
            svc_logger.info('[SYNC-HTTP] Inicio sincronización manual por UI')

            # support syncing per-source when requested by the frontend
            only = request.args.get('only')
            # accept 'primary' or 'alt' or None
            result = sincronizar_empleados(only=only) if only else sincronizar_empleados()
            if result is False:
                svc_logger.warning('[SYNC-HTTP] Sincronización finalizó con errores')
                return jsonify({'success': False, 'error': 'Error durante sincronización'}), 500
            svc_logger.info('[SYNC-HTTP] Sincronización completada. Registros procesados: %s', len(result))
            return jsonify({'success': True, 'count': len(result)}), 200
        except Exception as e:
            logging.getLogger('admin_disp.services.empleados_sync').exception('[SYNC-HTTP] Error en sincronización: %s', e)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/')
    def index():
        from flask import session, redirect, url_for
        if 'user_id' in session:
            return redirect(url_for('devices.ui_list'))
        return redirect(url_for('auth.login_form'))

    @app.route('/favicon.ico')
    def favicon():
        from flask import send_from_directory
        return send_from_directory(
            os.path.join(app.root_path, 'static', 'img'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
        )

    @app.route('/viewer_test')
    def viewer_test():
        from flask import render_template, request
        # URL opcional por query string: /viewer_test?url=...
        url = request.args.get('url', '').strip()
        if not url:
            # En caso de no especificar, usar un PDF de prueba alojado por PDFTron (evita MediaFire)
            url = 'https://pdftron.s3.amazonaws.com/downloads/pl/PDFTRON_about.pdf'
        return render_template('viewer_test.html', external_url=url)

    @app.route('/exports/documents/<path:subpath>')
    def serve_export_documents(subpath):
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            # project root is one level above package dir
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            docs_dir = os.path.join(project_root, 'exports', 'documents')
            # normalize
            docs_dir = os.path.normpath(docs_dir)
            return send_from_directory(docs_dir, subpath)
        except Exception:
            app.logger.exception('Error al servir documento de exports: %s', subpath)
            return ('Not found', 404)

    # Configurar scheduler para ejecutar escaneo de impresoras a las 08:00
    if BackgroundScheduler is not None:
        scheduler = BackgroundScheduler()

        def scheduled_printer_scan():
            try:
                with app.app_context():
                    # Importar la función principal del lector de impresoras
                    from .services.printer_reader import main as read_printers_main
                    # IPs configuradas (misma lista que en routes)
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
                    app.logger.info('[Scheduler] Ejecutando escaneo de impresoras programado a las 08:00')
                    try:
                        read_printers_main(ip_dict=ip_dict)
                        app.logger.info('[Scheduler] Escaneo de impresoras finalizado')
                    except Exception as e:
                        app.logger.exception('[Scheduler] Error al ejecutar escaneo programado: %s', e)
            except Exception:
                app.logger.exception('[Scheduler] Error interno en la tarea programada')

        # Programar jobs diarios: impresoras (08:20), empleados (08:25)
        # y actualización completa de registros de impresoras a las 08:30
        try:
            scheduler.add_job(scheduled_printer_scan, trigger='cron', hour=8, minute=20, id='daily_printer_scan')

            # Programar sincronización de empleados a las 08:25
            def scheduled_empleados_sync():
                try:
                    with app.app_context():
                        from .services.empleados_sync import sincronizar_empleados
                        app.logger.info('[Scheduler] Ejecutando sincronización de empleados desde SharePoint')
                        resultado = sincronizar_empleados()
                        if resultado:
                            app.logger.info('[Scheduler] Sincronización de empleados finalizada exitosamente')
                        else:
                            app.logger.warning('[Scheduler] Sincronización de empleados completada con errores')
                except Exception as e:
                    app.logger.exception('[Scheduler] Error durante sincronización de empleados: %s', e)
            
            scheduler.add_job(scheduled_empleados_sync, trigger='cron', hour=8, minute=25, id='daily_empleados_sync')

            # Job adicional: actualizar registros (guardar estado/tinta) de todas las impresoras a las 08:30
            def scheduled_update_printer_records():
                try:
                    with app.app_context():
                        from .services.printer_reader import load_printer_config, JobHistoryScanner
                        ip_dict = load_printer_config()
                        app.logger.info('[Scheduler] Ejecutando actualización de registros (historiales) de impresoras a las 08:30')
                        if not ip_dict:
                            app.logger.warning('[Scheduler] No hay impresoras configuradas para actualización')
                            return
                        scanner = JobHistoryScanner()
                        for ip, desc in ip_dict.items():
                            try:
                                result = scanner.scan(ip=ip, description=desc)
                                app.logger.info('[Scheduler] Historial %s -> %s (print_added=%s, copy_added=%s)', ip, result.get('status'), result.get('print_added'), result.get('copy_added'))
                            except Exception as e:
                                app.logger.exception('[Scheduler] Error actualizando historial %s: %s', ip, e)
                except Exception:
                    app.logger.exception('[Scheduler] Error interno en la tarea de actualización de registros')

            scheduler.add_job(scheduled_update_printer_records, trigger='cron', hour=8, minute=30, id='daily_printer_update_records')

            # ── CxC: sincronización SharePoint → SQL cada 60 segundos ──────
            def scheduled_cxc_sync():
                try:
                    with app.app_context():
                        from .cxc.service import sync_new_items_to_sql
                        result = sync_new_items_to_sql()
                        nuevos   = result["inserted"]
                        consultados = result["fetched_from_sp"]
                        app.logger.info(
                            '[CxC] Registros nuevos: %d de %d consultados en SP',
                            nuevos, consultados,
                        )
                except Exception as _e:
                    app.logger.error('[CxC] Error en sync programado: %s', _e, exc_info=True)

            from datetime import datetime as _dt
            scheduler.add_job(
                scheduled_cxc_sync,
                trigger='interval',
                seconds=60,
                id='cxc_sp_sync',
                name='CxC SharePoint → SQL sync',
                replace_existing=True,
                next_run_time=_dt.now(),   # primera ejecución inmediata
            )
            app.logger.info('[CxC Scheduler] Job de sync CxC registrado (cada 60 s)')

            # Backup nocturno de las 3 bases de datos a las 23:50
            def scheduled_db_backup():
                try:
                    with app.app_context():
                        from .services.backup_service import run_backups
                        run_backups(app)
                except Exception as _e:
                    app.logger.exception('[Backup] Error en backup programado: %s', _e)

            scheduler.add_job(
                scheduled_db_backup,
                trigger='cron',
                hour=23,
                minute=50,
                id='daily_db_backup',
                name='Backup nocturno BD (admin_disp, cxc, empleados)',
                replace_existing=True,
            )
            app.logger.info('[Backup] Job de backup nocturno registrado a las 23:50')

            # Iniciar scheduler sólo en el proceso principal del servidor (evita doble arranque con reloader)
            if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
                scheduler.start()
                app.logger.info('APScheduler iniciado, jobs programados a las 08:20 (impresoras), 08:25 (empleados) y 08:30 (actualizar registros de impresoras)')
            else:
                app.logger.info('APScheduler programado pero no iniciado en modo debug (reloader)')
        except Exception:
            app.logger.exception('No se pudo iniciar APScheduler')
        # Guardar scheduler en app para posible control futuro
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['apscheduler'] = scheduler


    else:
        app.logger.warning('APScheduler no está disponible. Instale APScheduler para habilitar el escaneo programado.')

    # Hook to write uncaught request exceptions into the module-specific logger
    def _log_request_exception(sender, exception, **extra):
        try:
            bp = getattr(request, 'blueprint', None) or 'app'
            endpoint = (request.endpoint or '').lower()
            path = (request.path or '').lower()
            # Map devices blueprint subpaths to module-specific loggers
            if bp == 'devices':
                if '/planes' in path or 'planes' in endpoint:
                    target = 'planes'
                elif 'asignacion' in path or 'asignacion' in endpoint or 'asignaciones' in endpoint:
                    target = 'asignaciones'
                elif 'reclamo' in path or 'reclamos' in endpoint:
                    target = 'reclamos'
                else:
                    target = 'dispositivos'
            else:
                target = bp

            logger = logging.getLogger(f'admin_disp.{target}')
            logger.exception('Unhandled exception on %s %s (endpoint=%s)', request.method, request.path, request.endpoint, exc_info=exception)
            app.logger.exception('Unhandled exception on %s %s (endpoint=%s)', request.method, request.path, request.endpoint, exc_info=exception)
        except Exception:
            app.logger.exception('Error while logging request exception')

    got_request_exception.connect(_log_request_exception, app)

    return app


if __name__ == '__main__':
    app = create_app()
    flask_env = os.getenv('FLASK_ENV', 'production').lower()
    debug = os.getenv('FLASK_DEBUG', '0').lower() in ('1', 'true', 'yes') and flask_env != 'production'
    app.run(debug=debug, port=8000, host='0.0.0.0')
