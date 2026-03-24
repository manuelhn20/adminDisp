# =============================================================================
# KARDEX — Cambios en archivos existentes de admin_disp
# Aplica estos cambios manualmente en cada archivo indicado.
# =============================================================================


# =============================================================================
# 1. admin_disp/config.py
#    Agregar al final de la clase Config:
# =============================================================================

    # ── Base de datos KARDEX ─────────────────────────────────────────────────
    # Mismo servidor/credenciales que admin_disp, base de datos 'kardex'.
    KARDEX_DB_DRIVER   = os.getenv('KARDEX_DB_DRIVER',   DB_DRIVER)
    KARDEX_DB_SERVER   = os.getenv('KARDEX_DB_SERVER',   DB_SERVER)
    KARDEX_DB_DATABASE = os.getenv('KARDEX_DB_DATABASE', 'kardex')
    KARDEX_DB_USER     = os.getenv('KARDEX_DB_USER',     DB_USER)
    KARDEX_DB_PASSWORD = os.getenv('KARDEX_DB_PASSWORD', DB_PASSWORD)
    KARDEX_DB_TRUSTED  = os.getenv('KARDEX_DB_TRUSTED',  'false').lower() in ('1', 'true', 'yes')


# =============================================================================
# 2. admin_disp/core/db.py
#    a) En get_db_connection(), agregar el case 'kardex':
# =============================================================================

#   elif database_type == 'kardex':
#       return get_db_kardex()

#    b) Agregar la función get_db_kardex() después de get_db_cxc():
# =============================================================================

def get_db_kardex():
    """Conexión a base de datos KARDEX (control de inventario)."""
    if 'db_kardex' not in g:
        cfg = current_app.config
        conn_str = build_conn_str(
            cfg.get('KARDEX_DB_DRIVER', cfg['DB_DRIVER']),
            cfg.get('KARDEX_DB_SERVER', cfg['DB_SERVER']),
            cfg.get('KARDEX_DB_DATABASE', 'kardex'),
            cfg.get('KARDEX_DB_USER'),
            cfg.get('KARDEX_DB_PASSWORD'),
            cfg.get('KARDEX_DB_TRUSTED', False),
        )
        g.db_kardex = pyodbc.connect(conn_str)
    return g.db_kardex

#    c) En close_db(), agregar al final:
# =============================================================================

#   dbk = g.pop('db_kardex', None)
#   if dbk is not None:
#       try:
#           dbk.close()
#       except Exception:
#           pass


# =============================================================================
# 3. admin_disp/app.py
#    En create_app(), después del bloque de registro del blueprint CxC,
#    agregar el registro del blueprint KARDEX:
# =============================================================================

    # ── KARDEX (Control de Inventario) ───────────────────────────────────────
    try:
        from .kardex.routes import kardex_bp
        app.register_blueprint(kardex_bp)
        app.logger.info('Blueprint KARDEX registrado en /kardex')
    except Exception as _kardex_exc:
        app.logger.exception('No se pudo registrar el blueprint KARDEX: %s', _kardex_exc)


# =============================================================================
# 4. admin_disp/templates/base.html — Sidebar
#    Dentro del <ul class="sidebar-links">, agregar una nueva sección
#    DESPUÉS del bloque "Accesos directos" existente:
# =============================================================================

        <h4>
          <span>Inventario</span>
          <div class="menu-separator"></div>
        </h4>
        <li>
          <a href="/kardex/productos">
            <span class="material-symbols-outlined">inventory_2</span>Productos
          </a>
        </li>
        <li>
          <a href="/kardex/almacenes">
            <span class="material-symbols-outlined">warehouse</span>Almacenes
          </a>
        </li>
        <li>
          <a href="/kardex/marcas">
            <span class="material-symbols-outlined">label</span>Marcas
          </a>
        </li>
        <li>
          <a href="/kardex/periodos">
            <span class="material-symbols-outlined">calendar_month</span>Períodos
          </a>
        </li>
        <h4>
          <span>Sync Inventario</span>
          <div class="menu-separator"></div>
        </h4>
        <li>
          <a href="#" onclick="kardexSyncProductos(); return false;">
            <span class="material-symbols-outlined">sync</span>Sync Productos
          </a>
        </li>
        <li>
          <a href="#" onclick="kardexSyncAlmacenes(); return false;">
            <span class="material-symbols-outlined">sync_alt</span>Sync Almacenes
          </a>
        </li>

# =============================================================================
# 5. admin_disp/templates/base.html — Script de sync (antes de </body>)
#    Agregar justo antes de la etiqueta de cierre </body>:
# =============================================================================

  <script>
    async function kardexSyncProductos() {
      if (!confirm('¿Sincronizar productos y marcas desde SharePoint?')) return;
      try {
        showLoading('Sincronizando productos desde SharePoint...');
        const r = await fetch('/kardex/api/sync/productos', { method: 'POST' });
        const d = await r.json();
        hideLoading();
        if (d.success) {
          openGlobalSuccessModal(
            `Sync OK — Productos: ${d.productos?.inserted ?? 0} nuevos, ${d.productos?.updated ?? 0} actualizados.`
          );
        } else {
          openGlobalMessageModal('error', 'Error en sync productos', d.error || 'Error desconocido');
        }
      } catch(e) {
        hideLoading();
        openGlobalMessageModal('error', 'Error de conexión', e.message);
      }
    }

    async function kardexSyncAlmacenes() {
      if (!confirm('¿Sincronizar almacenes desde SharePoint?')) return;
      try {
        showLoading('Sincronizando almacenes desde SharePoint...');
        const r = await fetch('/kardex/api/sync/almacenes', { method: 'POST' });
        const d = await r.json();
        hideLoading();
        if (d.success) {
          openGlobalSuccessModal(
            `Sync OK — Almacenes: ${d.almacenes?.inserted ?? 0} nuevos, ${d.almacenes?.updated ?? 0} actualizados.`
          );
        } else {
          openGlobalMessageModal('error', 'Error en sync almacenes', d.error || 'Error desconocido');
        }
      } catch(e) {
        hideLoading();
        openGlobalMessageModal('error', 'Error de conexión', e.message);
      }
    }
  </script>
