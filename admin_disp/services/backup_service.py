import os
import glob
import logging
from urllib.parse import quote_plus
from sqlalchemy import create_engine

logger = logging.getLogger('admin_disp.services.backup')

# Bases de datos a respaldar: (nombre_db, tipo_conexion)
# tipo_conexion 'main' usa DB_* config, 'emp' usa EMP_* config
_DATABASES = [
    ('admin_disp', 'main'),
    ('cxc',        'main'),
    ('empleados',  'emp'),
]

MAX_BACKUPS = 7  # Cantidad de días de backups a conservar por base de datos


def _get_backup_dir():
    """Retorna la ruta absoluta de exports/backup/ y la crea si no existe."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    backup_dir = os.path.join(base_dir, 'exports', 'backup')
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def _prune_old_backups(backup_dir, db_name):
    """
    Elimina los backups más viejos de db_name si ya existen MAX_BACKUPS archivos.
    Los archivos tienen formato db_YYYYMMDD_HHMM.bak, por lo que orden
    alfabético coincide con orden cronológico.
    """
    pattern = os.path.join(backup_dir, f'{db_name}_*.bak')
    files = sorted(glob.glob(pattern))
    while len(files) >= MAX_BACKUPS:
        oldest = files.pop(0)
        try:
            os.remove(oldest)
            logger.info('[Backup] Eliminado backup antiguo: %s', os.path.basename(oldest))
        except OSError as e:
            logger.error('[Backup] No se pudo eliminar %s: %s', oldest, e)


def _build_conn_str(cfg, use_emp=False):
    """Construye connection string apuntando a master (para BACKUP DATABASE)."""
    if use_emp:
        driver  = cfg['EMP_DRIVER']
        server  = cfg['EMP_SERVER']
        user    = cfg.get('EMP_USER')
        pwd     = cfg.get('EMP_PASSWORD')
        trusted = cfg.get('EMP_TRUSTED', False)
    else:
        driver  = cfg['DB_DRIVER']
        server  = cfg['DB_SERVER']
        user    = cfg.get('DB_USER')
        pwd     = cfg.get('DB_PASSWORD')
        trusted = cfg.get('DB_TRUSTED', False)

    if trusted:
        return f"DRIVER={{{driver}}};SERVER={server};DATABASE=master;Trusted_Connection=yes;"
    return f"DRIVER={{{driver}}};SERVER={server};DATABASE=master;UID={user};PWD={pwd};"


def run_backups(app):
    """
    Ejecuta el backup de las bases de datos admin_disp, cxc y empleados.

    - Los archivos .bak se guardan en exports/backup/ con nombre YYYY MM DD_HHMM.bak
    - El path entregado a SQL Server es la ruta ABSOLUTA local; el servicio
      SQL Server debe tener permisos de escritura sobre esa carpeta.
    - Antes de cada backup se verifica si ya existen MAX_BACKUPS archivos de
      esa base; si es así, se elimina el más viejo primero.
    """
    from datetime import datetime

    backup_dir = _get_backup_dir()
    timestamp  = datetime.now().strftime('%Y%m%d_%H%M')

    logger.info('[Backup] === Iniciando backup de bases de datos (%s) ===', timestamp)

    errors = []
    for db_name, conn_type in _DATABASES:
        use_emp = (conn_type == 'emp')
        try:
            # 1. Podar backups anteriores si ya hay MAX_BACKUPS
            _prune_old_backups(backup_dir, db_name)

            # 2. Ruta absoluta del archivo de destino
            backup_file = os.path.abspath(
                os.path.join(backup_dir, f'{db_name}_{timestamp}.bak')
            )

            # 3. Ejecutar BACKUP DATABASE con autocommit (no puede correr en transacción)
            conn_str = _build_conn_str(app.config, use_emp=use_emp)
            logger.info('[Backup] Respaldando [%s] → %s', db_name, backup_file)

            connect_url = "mssql+pyodbc:///?odbc_connect=" + quote_plus(conn_str)
            engine = create_engine(connect_url, future=True, pool_pre_ping=True)
            try:
                sql = (
                    f"BACKUP DATABASE [{db_name}] "
                    f"TO DISK = N'{backup_file}' "
                    f"WITH COMPRESSION, FORMAT, INIT, "
                    f"NAME = N'{db_name} backup {timestamp}'"
                )
                with engine.connect() as conn:
                    conn = conn.execution_options(isolation_level='AUTOCOMMIT')
                    conn.exec_driver_sql(sql)
                logger.info('[Backup] Completado: [%s]', db_name)
            finally:
                engine.dispose()

        except Exception:
            logger.exception('[Backup] Error al respaldar [%s]', db_name)
            errors.append(db_name)

    if errors:
        logger.error('[Backup] Finalizado con errores en: %s', ', '.join(errors))
    else:
        logger.info('[Backup] === Backup completado exitosamente ===')
