import pyodbc
from flask import current_app, g


def build_conn_str(driver, server, database, user=None, password=None, trusted=False):
    """Construye connection string para SQL Server."""
    if trusted:
        return f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
    if not user or not password:
        raise ValueError(
            f"Credenciales requeridas para BD '{database}' cuando Trusted_Connection es false "
            f"(esperado: DB_USER/DB_PASSWORD o EMP_USER/EMP_PASSWORD)."
        )
    return f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};UID={user};PWD={password};"


def get_db_connection(database_type='main'):
    """
    Obtiene una conexión persistente a SQL Server según tipo de BD.
    Tipos: 'main', 'empleados', 'cxc', 'kardex'
    
    Utiliza Flask's g context para reutilizar conexiones dentro del mismo request.
    """
    if database_type == 'main':
        return get_db_main()
    elif database_type == 'empleados':
        return get_db_empleados()
    elif database_type == 'cxc':
        return get_db_cxc()
    elif database_type == 'kardex':
        return get_db_kardex()
    else:
        raise ValueError(f"Tipo de BD desconocido: {database_type}")


def get_db_main():
    """Conexión a base de datos principal (admin_disp)."""
    if 'db_main' not in g:
        cfg = current_app.config
        conn_str = build_conn_str(
            cfg['DB_DRIVER'], cfg['DB_SERVER'], cfg['DB_DATABASE'],
            cfg.get('DB_USER'), cfg.get('DB_PASSWORD'), cfg.get('DB_TRUSTED')
        )
        g.db_main = pyodbc.connect(conn_str)
    return g.db_main


def get_db_empleados():
    """Conexión a base de datos de empleados."""
    if 'db_empleados' not in g:
        cfg = current_app.config
        conn_str = build_conn_str(
            cfg['EMP_DRIVER'], cfg['EMP_SERVER'], cfg['EMP_DATABASE'],
            cfg.get('EMP_USER'), cfg.get('EMP_PASSWORD'), cfg.get('EMP_TRUSTED')
        )
        g.db_empleados = pyodbc.connect(conn_str)
    return g.db_empleados


def get_db_cxc():
    """Conexión a base de datos de CxC (Cuentas por Cobrar)."""
    if 'db_cxc' not in g:
        cfg = current_app.config
        conn_str = build_conn_str(
            cfg['DB_DRIVER'], cfg['DB_SERVER'], 'cxc',
            cfg.get('DB_USER'), cfg.get('DB_PASSWORD'), cfg.get('DB_TRUSTED')
        )
        g.db_cxc = pyodbc.connect(conn_str)
    return g.db_cxc


def get_db_kardex():
    """Conexión a base de datos de Kardex (control de inventario)."""
    if 'db_kardex' not in g:
        cfg = current_app.config
        conn_str = build_conn_str(
            cfg['DB_DRIVER'], cfg['DB_SERVER'], 'kardex',
            cfg.get('DB_USER'), cfg.get('DB_PASSWORD'), cfg.get('DB_TRUSTED')
        )
        g.db_kardex = pyodbc.connect(conn_str)
    return g.db_kardex


def close_db(e=None):
    """Cierra todas las conexiones abiertas en el contexto actual."""
    db = g.pop('db_main', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass
    dbe = g.pop('db_empleados', None)
    if dbe is not None:
        try:
            dbe.close()
        except Exception:
            pass
    dbc = g.pop('db_cxc', None)
    if dbc is not None:
        try:
            dbc.close()
        except Exception:
            pass
    dbk = g.pop('db_kardex', None)
    if dbk is not None:
        try:
            dbk.close()
        except Exception:
            pass


def init_db_connections(app):
    """Registra el teardown function para cerrar conexiones al final del request."""
    @app.teardown_appcontext
    def _close_db(exception):
        close_db(exception)
