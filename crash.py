[2026-03-24 22:49:01,752] INFO in app: Blueprint printerScanner registrado en /dispositivos
[2026-03-24 22:49:02,084] INFO in app: Blueprint CxC registrado en /cxc
[2026-03-24 22:49:02,088] ERROR in app: ensure_lote_schema fallo: ('01000', "[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 17 for SQL Server' : file not found (0) (SQLDriverConnect)")
Traceback (most recent call last):
  File "/app/admin_disp/app.py", line 206, in create_app
    ensure_lote_schema()
  File "/app/admin_disp/cxc/operations.py", line 28, in ensure_lote_schema
    conn = _pyodbc.connect(_cs)
           ^^^^^^^^^^^^^^^^^^^^
pyodbc.Error: ('01000', "[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 17 for SQL Server' : file not found (0) (SQLDriverConnect)")
[2026-03-24 22:49:02,210] INFO in app: Blueprint KARDEX registrado en /kardex
[2026-03-24 22:49:02,226] INFO in app: Blueprint INVENTARIO registrado en /inventario
[2026-03-24 22:49:02,239] INFO in app: [CxC Scheduler] Job de sync CxC registrado (cada 60 s)
[2026-03-24 22:49:02,240] INFO in app: [Backup] Job de backup nocturno registrado a las 23:50
[2026-03-24 22:49:02,245] INFO in app: APScheduler iniciado, jobs programados a las 08:20 (impresoras), 08:25 (empleados) y 08:30 (actualizar registros de impresoras)
[2026-03-24 22:49:02,246] ERROR in app: [CxC] Error en sync programado: Credenciales requeridas si no es Trusted Connection
Press CTRL+C to quit
ValueError: Credenciales requeridas si no es Trusted Connection

Problema 2
          ^^^^^^^^^^^^^
  File "/app/admin_disp/auth/service.py", line 33, in __init__
    self.conn = get_db_empleados()
                ^^^^^^^^^^^^^^^^^^
  File "/app/admin_disp/core/db.py", line 53, in get_db_empleados
    g.db_empleados = pyodbc.connect(conn_str)
                     ^^^^^^^^^^^^^^^^^^^^^^^^
pyodbc.Error: ('01000', "[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 17 for SQL Server' : file not found (0) (SQLDriverConnect)")
100.64.0.2 - - [24/Mar/2026 22:52:07] "POST /auth/login HTTP/1.1" 500 -
100.64.0.2 - - [24/Mar/2026 22:52:13] "GET /static/img/cg.png HTTP/1.1" 304 -
100.64.0.2 - - [24/Mar/2026 22:52:37] "POST /auth/validar-usuario HTTP/1.1" 500 -
100.64.0.2 - - [24/Mar/2026 22:52:37] "POST /auth/request-reset HTTP/1.1" 200 -
100.64.0.2 - - [24/Mar/2026 22:52:44] "GET /static/css/neumorphism-login.css HTTP/1.1" 304 -
100.64.0.2 - - [24/Mar/2026 22:52:44] "GET /static/css/login.css HTTP/1.1" 304 -
    rv = self.dispatch_request()
    raise ValueError('Credenciales requeridas si no es Trusted Connection')
ValueError: Credenciales requeridas si no es Trusted Connection
[2026-03-24 22:53:03,426] ERROR in app: Unhandled Exception: Error - ('01000', "[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 17 for SQL Server' : file not found (0) (SQLDriverConnect)")
               ^^^^^^^^^^^^^^^
  File "/app/admin_disp/cxc/service.py", line 205, in sync_new_items_to_sql
Traceback (most recent call last):
    ensure_sync_config()
  File "/app/admin_disp/core/db.py", line 10, in build_conn_str
  File "/usr/local/lib/python3.12/site-packages/flask/app.py", line 917, in full_dispatch_request
  File "/app/admin_disp/cxc/operations.py", line 101, in ensure_sync_config
  File "/app/admin_disp/core/db.py", line 61, in get_db_cxc
    conn = get_db_cxc()
           ^^^^^^^^^^^^
    conn_str = build_conn_str(
[2026-03-24 22:53:02,236] ERROR in app: [CxC] Error en sync programado: Credenciales requeridas si no es Trusted Connection
Traceback (most recent call last):
  File "/app/admin_disp/app.py", line 413, in scheduled_cxc_sync
    result = sync_new_items_to_sql()
             ^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/admin_disp/auth/service.py", line 33, in __init__
    self.conn = get_db_empleados()
                ^^^^^^^^^^^^^^^^^^
  File "/app/admin_disp/core/db.py", line 53, in get_db_empleados
  File "/usr/local/lib/python3.12/site-packages/flask/app.py", line 902, in dispatch_request
  File "/app/admin_disp/common/rbac.py", line 99, in wrapper
    return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]
    return f(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
           ^^^^^^^^^^^^^^^^^^
  File "/app/admin_disp/auth/routes.py", line 65, in login
    svc = AuthService()
          ^^^^^^^^^^^^^
         ^^^^^^^^^^^^^^^^^^^^^^^
    g.db_empleados = pyodbc.connect(conn_str)
                     ^^^^^^^^^^^^^^^^^^^^^^^^
pyodbc.Error: ('01000', "[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 17 for SQL Server' : file not found (0) (SQLDriverConnect)")
100.64.0.2 - - [24/Mar/2026 22:53:03] "POST /auth/login HTTP/1.1" 500 -
100.64.0.2 - - [24/Mar/2026 22:53:15] "GET /static/css/login.css HTTP/1.1" 304 -
100.64.0.2 - - [24/Mar/2026 22:53:15] "GET /static/css/neumorphism-login.css HTTP/1.1" 304 -
100.64.0.2 - - [24/Mar/2026 22:53:15] "GET /static/img/proimabg.png HTTP/1.1" 304 -
100.64.0.2 - - [24/Mar/2026 22:53:15] "GET /static/img/cg.png HTTP/1.1" 304 -
100.64.0.2 - - [24/Mar/2026 22:53:15] "GET /auth/login HTTP/1.1" 200 -
100.64.0.2 - - [24/Mar/2026 22:53:15] "GET /static/img/chk.png HTTP/1.1" 304 -
100.64.0.2 - - [24/Mar/2026 22:53:15] "GET /static/img/fail.png HTTP/1.1" 304 -
100.64.0.2 - - [24/Mar/2026 22:53:15] "GET /static/js/neumorphism-login.js HTTP/1.1" 304 -
100.64.0.2 - - [24/Mar/2026 22:53:15] "GET /static/img/war.png HTTP/1.1" 304 -
100.64.0.2 - - [24/Mar/2026 22:53:15] "GET /static/js/login.js HTTP/1.1" 304 -
100.64.0.2 - - [24/Mar/2026 22:53:15] "GET /static/img/favicon.ico HTTP/1.1" 304 -
[2026-03-24 22:53:22,485] ERROR in app: Unhandled Exception: Error - ('01000', "[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 17 for SQL Server' : file not found (0) (SQLDriverConnect)")
Traceback (most recent call last):
  File "/usr/local/lib/python3.12/site-packages/flask/app.py", line 917, in full_dispatch_request
    rv = self.dispatch_request()
         ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/flask/app.py", line 902, in dispatch_request
    return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/admin_disp/common/rbac.py", line 99, in wrapper
    return f(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^
  File "/app/admin_disp/auth/routes.py", line 65, in login
    svc = AuthService()
          ^^^^^^^^^^^^^
  File "/app/admin_disp/auth/service.py", line 33, in __init__
    self.conn = get_db_empleados()
                ^^^^^^^^^^^^^^^^^^
  File "/app/admin_disp/core/db.py", line 53, in get_db_empleados
    g.db_empleados = pyodbc.connect(conn_str)
                     ^^^^^^^^^^^^^^^^^^^^^^^^
100.64.0.2 - - [24/Mar/2026 22:53:22] "POST /auth/login HTTP/1.1" 500 -
pyodbc.Error: ('01000', "[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 17 for SQL Server' : file not found (0) (SQLDriverConnect)")
  File "/app/admin_disp/auth/routes.py", line 65, in login
    svc = AuthService()
          ^^^^^^^^^^^^^
  File "/app/admin_disp/auth/service.py", line 33, in __init__
    self.conn = get_db_empleados()
                ^^^^^^^^^^^^^^^^^^
  File "/app/admin_disp/core/db.py", line 53, in get_db_empleados
    g.db_empleados = pyodbc.connect(conn_str)
                     ^^^^^^^^^^^^^^^^^^^^^^^^
[2026-03-24 22:53:40,693] ERROR in app: Unhandled Exception: Error - ('01000', "[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 17 for SQL Server' : file not found (0) (SQLDriverConnect)")
Traceback (most recent call last):
  File "/usr/local/lib/python3.12/site-packages/flask/app.py", line 917, in full_dispatch_request
    rv = self.dispatch_request()
         ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/site-packages/flask/app.py", line 902, in dispatch_request
    return self.ensure_sync(self.view_functions[rule.endpoint])(**view_args)  # type: ignore[no-any-return]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/admin_disp/common/rbac.py", line 99, in wrapper
    return f(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^
pyodbc.Error: ('01000', "[01000] [unixODBC][Driver Manager]Can't open lib 'ODBC Driver 17 for SQL Server' : file not found (0) (SQLDriverConnect)")
100.64.0.2 - - [24/Mar/2026 22:53:40] "POST /auth/login HTTP/1.1" 500 -
[2026-03-24 22:54:02,236] ERROR in app: [CxC] Error en sync programado: Credenciales requeridas si no es Trusted Connection
Traceback (most recent call last):
           ^^^^^^^^^^^^
  File "/app/admin_disp/app.py", line 413, in scheduled_cxc_sync
  File "/app/admin_disp/core/db.py", line 61, in get_db_cxc
    conn_str = build_conn_str(
    result = sync_new_items_to_sql()
               ^^^^^^^^^^^^^^^
             ^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/admin_disp/core/db.py", line 10, in build_conn_str
    raise ValueError('Credenciales requeridas si no es Trusted Connection')
ValueError: Credenciales requeridas si no es Trusted Connection
  File "/app/admin_disp/cxc/service.py", line 205, in sync_new_items_to_sql
    ensure_sync_config()
  File "/app/admin_disp/cxc/operations.py", line 101, in ensure_sync_config
    conn = get_db_cxc()