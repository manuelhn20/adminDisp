# admin_disp/cxc/routes.py
import json
import os
import io
import datetime
import logging
from functools import wraps

from flask import (
    Blueprint, render_template, Response,
    request, jsonify, session, redirect, url_for, current_app,
)

from .service import (
    get_image_bytes_for_item,
    get_image_bytes_playwright,
    get_image_field_raw,
    get_image_url_for_item,
    parse_image_field,
    liquidar_por_ids,
    sync_new_items_to_sql,
    sync_fill_blanks_from_sp,
    get_last_sync_info,
)
from .liqpdf import build_pdf_report_from_rows
from .operations import (
    get_cobros_paginated, get_distinct_values, get_cobros_by_ids,
    registrar_liquidacion_pdf, update_lote_sp_info, get_liquidacion_por_recibo, get_liquidaciones_recientes,
    get_codigo_empleado_by_nombre, fill_sucursal_from_empleados,
    get_lotes, finalizar_lote, get_cobros_by_lote, get_next_numero_liquidacion,
    get_lote_by_id, update_lote_estado,
    update_lote_rev_sp_info, clear_lote_rev_sp_info, get_ejecutivos_by_sucursal,
)
from ..services.onedrive_service import (
    upload_file_bytes,
    delete_file_by_id,
    rename_file_by_id,
)

log    = logging.getLogger('admin_disp.cxc.routes')
cxc_bp = Blueprint("cxc", __name__, url_prefix="/cxc")


# ─── Helpers de sesion ────────────────────────────────────────────────────────

def _get_cxc_role():
    if session.get('is_super_admin'):
        return 'Admin'
    return session.get('sistemas_roles', {}).get('cxc')


def _get_user_display_name():
    return session.get('empleado_nombre') or session.get('username') or ''


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            if request.is_json or request.path.startswith('/cxc/api/'):
                return jsonify({'error': 'No autenticado'}), 401
            return redirect(url_for('auth.login_form'))
        if _get_cxc_role() is None:
            if request.is_json or request.path.startswith('/cxc/api/'):
                return jsonify({'error': 'Sin acceso al modulo CxC'}), 403
            return redirect(url_for('auth.menu'))
        return f(*args, **kwargs)
    return decorated

# ─── Formateo ─────────────────────────────────────────────────────────────────

def _fmt_dt(iso_str):
    if not iso_str:
        return ""
    try:
        # Aceptar tanto strings ISO como objetos datetime
        if isinstance(iso_str, datetime.datetime):
            return iso_str.strftime("%d/%m/%Y %H:%M")
        # Normalizar: quitar Z, reemplazar T por espacio, cortar microsegundos
        s = str(iso_str).replace("Z", "").replace("T", " ")[:16].strip()
        d, t = s.split(" ")
        y, m, dd = d.split("-")
        return f"{dd}/{m}/{y} {t}"
    except Exception:
        return str(iso_str)


def _fmt_date(iso_str):
    if not iso_str:
        return ""
    try:
        y, m, d = str(iso_str)[:10].split("-")
        return f"{d}/{m}/{y}"
    except Exception:
        return str(iso_str)


def _fmt_money(value):
    if value is None:
        return ""
    try:
        return f"L {float(value):,.2f}"
    except Exception:
        return str(value)


def _serialize_row(row):
    liq = str(row.get("liquidado") or "").strip().lower()
    return {
        "spItemId":           row["spItemId"],
        "codigoCliente":       row.get("codigoCliente")       or "",
        "nombreCliente":       row.get("nombreCliente")       or "",
        "banco":                row.get("banco")                or "",
        "metodoPago":          row.get("metodoPago")          or "",
        "noFactura":           row.get("noFactura")           or "",
        "valorPagado":         _fmt_money(row.get("valorPagado")),
        "Valor_Pagado_Raw":     float(row.get("valorPagado")   or 0),
        "noRecibo":            row.get("noRecibo")            or "",
        "creado":               _fmt_dt(row.get("creado")),
        "ejecutivo":            row.get("ejecutivo")            or "",
        "sucursal":             row.get("sucursal")             or "",
        "fechaCheque":         _fmt_date(row.get("fechaCheque")),
        "comentarioAdicional": row.get("comentarioAdicional") or "",
        "liquidado":            row.get("liquidado")            or "",
        "liquidadoPor":        row.get("liquidadoPor")        or "",
        "fechaLiquidado":      _fmt_dt(row.get("fechaLiquidado")),
        "tieneComprobante":    bool(row.get("tieneComprobante")),
        "liquidado_bool":       liq in ("si", "si\u0301"),
        "estado_cobro":         row.get("estado_cobro", "Recibido"),
    }


# ─── Página principal ─────────────────────────────────────────────────────────

@cxc_bp.route("/")
@login_required
def index():
    cxc_role       = _get_cxc_role()
    can_liquidar   = (cxc_role or '').lower() in ('admin', 'operador') or session.get('is_super_admin', False)
    can_confirm    = (cxc_role or '').lower() != 'auditor'
    is_admin       = cxc_role in ('Admin',) or session.get('is_super_admin', False)
    is_super_admin = session.get('is_super_admin', False)
    user_name      = _get_user_display_name()

    try:
        sucursales = get_distinct_values("sucursal")
        
        # ─── Filtro de sucursal para operadores ─────────────────────────────────
        # Si el usuario es un operador, solo mostrar ejecutivos de su sucursal
        cxc_role_lower = (cxc_role or '').lower()
        if cxc_role_lower == 'operador':
            operador_sucursal = session.get('empleado_sucursal', '')
            ejecutivos = get_ejecutivos_by_sucursal(operador_sucursal) if operador_sucursal else []
        else:
            ejecutivos = get_distinct_values("ejecutivo")
    except Exception as e:
        log.error("Error obteniendo listas de filtros: %s", e)
        sucursales = []
        ejecutivos = []

    return render_template(
        "cxc.html",
        can_liquidar   = can_liquidar,
        can_confirm    = can_confirm,
        is_admin       = is_admin,
        is_super_admin = is_super_admin,
        user_name      = user_name,
        cxc_role       = cxc_role,
        sucursales     = sucursales,
        ejecutivos     = ejecutivos,
    )


# Alias /cxc/cobros para compatibilidad
cxc_bp.add_url_rule('/cobros', endpoint='demo', view_func=index)


# ─── API: datos de la grilla ──────────────────────────────────────────────────

@cxc_bp.route("/api/cobros")
@login_required
def cobros_data():
    start  = int(request.args.get("start",  0))
    length = int(request.args.get("length", 100))

    filters = {
        "sucursal":  (request.args.get("sucursal")     or "").strip() or None,
        "ejecutivo": (request.args.get("ejecutivo")    or "").strip() or None,
        "cliente":   (request.args.get("cliente")      or "").strip() or None,
        "recibo":    (request.args.get("recibo")       or "").strip() or None,
        "liquidado": (request.args.get("liquidado")    or "").strip() or None,
        "fecha_ini": (request.args.get("fecha_inicio") or "").strip() or None,
        "fechaFin": (request.args.get("fechaFin")    or "").strip() or None,
        "sort_col":  (request.args.get("sort_col")     or "creado").strip(),
        "sort_dir":  (request.args.get("sort_dir")     or "DESC").strip().upper(),
    }

    # ─── Control de acceso: Auditors solo ven sus propios registros ────────────
    cxc_role = _get_cxc_role()
    current_user = _get_user_display_name()
    
    if (cxc_role or '').lower() == 'auditor':
        # Auditor: forzar filtro por su nombre
        requested_ejecutivo = filters.get("ejecutivo")
        if requested_ejecutivo and requested_ejecutivo != current_user:
            # Intenta acceder a datos de otro ejecutivo
            return jsonify({
                "data": [], "recordsTotal": 0, "recordsFiltered": 0,
                "error": "No tienes permiso para ver datos de otros ejecutivos",
            }), 403
        filters["ejecutivo"] = current_user
    
    # ─── Control de acceso: Operadores solo ven su sucursal ────────────────────
    elif (cxc_role or '').lower() == 'operador':
        # Operador: forzar filtro por su sucursal
        operador_sucursal = session.get('empleado_sucursal', '')
        requested_sucursal = filters.get("sucursal")
        if requested_sucursal and requested_sucursal != operador_sucursal:
            # Intenta acceder a datos de otra sucursal
            return jsonify({
                "data": [], "recordsTotal": 0, "recordsFiltered": 0,
                "error": "No tienes permiso para ver datos de otras sucursales",
            }), 403
        filters["sucursal"] = operador_sucursal

    try:
        rows, total, filtered = get_cobros_paginated(
            start=start, length=length, filters=filters,
        )
        return jsonify({
            "data":            [_serialize_row(r) for r in rows],
            "recordsTotal":    total,
            "recordsFiltered": filtered,
        })
    except Exception as e:
        log.error("Error en /api/cobros: %s", e, exc_info=True)
        return jsonify({
            "data": [], "recordsTotal": 0, "recordsFiltered": 0,
            "error": str(e),
        }), 500


# ─── API: info del último sync ────────────────────────────────────────────────

@cxc_bp.route("/api/last-sync")
@login_required
def last_sync_info():
    """Retorna cuándo fue el último sync y cuántos registros se insertaron la última vez."""
    try:
        info = get_last_sync_info()
        return jsonify(info)
    except Exception as e:
        log.error("Error en /api/last-sync: %s", e)
        return jsonify({"lastSync": None, "last_inserted": 0})


# ─── API: ejecutivos por sucursal ──────────────────────────────────────────────

@cxc_bp.route("/api/ejecutivos-por-sucursal")
@login_required
def get_ejecutivos_por_sucursal():
    """Retorna lista de ejecutivos para una sucursal específica."""
    sucursal = (request.args.get("sucursal") or "").strip()
    
    if not sucursal:
        return jsonify([])
    
    try:
        ejecutivos = get_ejecutivos_by_sucursal(sucursal)
        return jsonify(ejecutivos)
    except Exception as e:
        log.error("Error obteniendo ejecutivos para sucursal '%s': %s", sucursal, e)
        return jsonify([]), 500


# ─── API: sync manual ─────────────────────────────────────────────────────────

@cxc_bp.route("/api/sync", methods=["POST"])
@login_required
def trigger_sync():
    if not session.get('is_super_admin'):
        return jsonify({"status": "error", "message": "Sin permisos."}), 403
    try:
        data         = request.get_json(silent=True) or {}
        mode         = data.get("mode", "load_new")          # "update_all" | "load_new"
        force_update = (mode == "update_all")
        log.info("Sync manual [mode=%s] solicitado por %s", mode, _get_user_display_name())
        result = sync_new_items_to_sql(force_full=True, force_update=force_update)
        return jsonify({"status": "ok", **result})
    except Exception as e:
        log.error("Error en sync manual: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@cxc_bp.route("/api/sync-fill-blanks", methods=["POST"])
@login_required
def trigger_sync_fill_blanks():
    """
    Sincroniza desde SP trayendo TODOS los registros y actualiza SOLO
    los campos en blanco/NULL sin afectar datos existentes.
    
    Ideal para:
    - Completar registros incompletos
    - Traer liquidaciones procesadas después de la inserción
    - Actualizar datos sin perder información actual
    """
    if not session.get('is_super_admin'):
        return jsonify({"status": "error", "message": "Sin permisos."}), 403
    try:
        log.info("Sync LLENAR BLANCOS solicitado por %s", _get_user_display_name())
        result = sync_fill_blanks_from_sp()
        return jsonify({"status": "ok", **result})
    except Exception as e:
        log.error("Error en sync fill blanks: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── Comprobante — retorna solo el URL directo sin descargar ──────────────────

@cxc_bp.route("/comprobante-url/<item_id>")
@login_required
def comprobante_url(item_id):
    """
    Retorna el URL directo del comprobante para abrirlo en nueva pestaña.
    No descarga nada, solo extrae la URL del campo Comprobante_Imagen.
    """
    try:
        from .service import get_graph_token, get_site_and_list_ids
        
        graph_token      = get_graph_token()
        site_id, list_id = get_site_and_list_ids(graph_token)

        # Leer el campo de imagen del item
        r = __import__('requests').get(
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/lists/{list_id}/items/{item_id}?expand=fields",
            headers={"Authorization": f"Bearer {graph_token}"},
            timeout=15,
        )
        if r.status_code != 200:
            return jsonify({"error": "Item no encontrado"}), 404

        item_json = r.json()
        raw_img   = item_json.get("fields", {}).get("Comprobante_Imagen")
        
        if not raw_img:
            return jsonify({"error": "Sin comprobante en este item"}), 404
        
        img_obj = parse_image_field(raw_img)
        
        # Intentar obtener URL directa del servidor
        img_url = img_obj.get("serverUrl") or img_obj.get("url")
        
        if img_url:
            return jsonify({"url": img_url})
        
        return jsonify({"error": "No se encontró URL en el comprobante"}), 400
        
    except Exception as e:
        log.error("Error obteniendo URL de comprobante %s: %s", item_id, e)
        return jsonify({"error": "No se pudo obtener la URL", "detail": str(e)[:200]}), 500


# ─── Comprobante — redirige al URL directo en SharePoint ──────────────────────

@cxc_bp.route("/comprobante/<item_id>")
@login_required
def comprobante(item_id):
    """
    Redirige (HTTP 302) al URL directo del comprobante en SharePoint.
    El frontend abre /cxc/comprobante/<id> en nueva pestaña y el navegador
    sigue el redirect automáticamente hasta la imagen real.
    """
    try:
        image_url = get_image_url_for_item(item_id)
        return redirect(image_url)
    except Exception as e:
        log.error("Error en comprobante(%s): %s", item_id, str(e)[:500], exc_info=True)
        return jsonify({"error": "No se pudo obtener el comprobante", "detail": str(e)[:200]}), 502


# ─── Comprobante — fallback Playwright (Windows Auth NTLM/Kerberos) ──────────

@cxc_bp.route("/comprobante-playwright/<item_id>")
@login_required
def comprobante_playwright(item_id):
    """
    Fallback Playwright para items donde los métodos REST fallan.
    Intenta primero el endpoint normal. Si ese falla, intenta Playwright 
    que navegará directo con Windows Auth (NTLM/Kerberos).
    """
    # 1. Intentar métodos REST normales primero
    try:
        img_bytes, content_type = get_image_bytes_for_item(item_id)
        resp = Response(img_bytes, mimetype=content_type)
        resp.headers["Cache-Control"] = "private, max-age=3600"
        return resp
    except Exception as e_normal:
        log.warning("Métodos REST fallaron para %s (%s) — intentando Playwright", item_id, e_normal)

    # 2. Fallback: Playwright con Windows Auth NTLM
    try:
        img_bytes, content_type = get_image_bytes_playwright(item_id)
        resp = Response(img_bytes, mimetype=content_type)
        resp.headers["Cache-Control"] = "private, max-age=3600"
        resp.headers["X-Playwright-Used"] = "1"
        return resp
    except Exception as e_pw:
        log.error("Playwright también falló para %s: %s", item_id, e_pw)
        return jsonify({"error": "No se pudo obtener el comprobante (playwright)", "detail": str(e_pw)[:200]}), 502


# ─── Debug: ver JSON crudo del campo imagen (solo admin/superadmin) ──────────
@cxc_bp.route("/comprobante-debug/<item_id>")
@login_required
def comprobante_debug(item_id):
    """Retorna el JSON crudo del campo Comprobante_Imagen para diagnóstico."""
    role = _get_cxc_role()
    if role not in ('Admin', 'SuperAdmin'):
        return jsonify({"error": "forbidden"}), 403
    try:
        raw = get_image_field_raw(item_id)
        return jsonify({"item_id": item_id, "raw": raw})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Diagnóstico: verificar que credenciales están cargadas (solo admin/superadmin) ─────

@cxc_bp.route("/diagnóstico", methods=["GET"])
@login_required
def diagnostico():
    """Retorna estado de credenciales y configuración para debugging."""
    role = _get_cxc_role()
    if role not in ('Admin', 'SuperAdmin'):
        return jsonify({"error": "forbidden"}), 403
    
    from .service import _get_sp_basic_auth
    
    basic_auth = _get_sp_basic_auth()
    has_user = bool(current_app.config.get('CXC_SP_BASIC_USER'))
    has_pass = bool(current_app.config.get('CXC_SP_BASIC_PASSWORD'))
    
    return jsonify({
        "status": "ok",
        "credentials_loaded": {
            "user_configured": has_user,
            "user_value": current_app.config.get('CXC_SP_BASIC_USER', '(no configurado)'),
            "password_configured": has_pass,
            "password_masked": "***" if has_pass else "(no configurado)",
        },
        "basic_auth_ready": basic_auth is not None,
        "sharepoint_config": {
            "hostname": current_app.config.get('CXC_SP_SITE_HOSTNAME'),
            "site_path": current_app.config.get('CXC_SP_SITE_PATH'),
            "list_name": current_app.config.get('CXC_SP_LIST_NAME'),
        }
    })


# ─── Debug: ver JSON crudo del campo imagen (solo admin/superadmin) ──────────
@cxc_bp.route("/comprobante-debug-old/<item_id>")


# ─── Generar PDF de liquidación (usa `liqpdf.build_pdf_report`) ───────────
@cxc_bp.route('/report/liq.pdf')
@login_required
def report_liq_pdf():
    """Genera el PDF de liquidación usando filtros desde querystring.

    Parámetros aceptados (querystring):
      - sucursal, ejecutivo, cliente, recibo, fecha_inicio (YYYY-MM-DD), fechaFin (YYYY-MM-DD)
    """
    from .liqpdf import build_pdf_report

    def _get_items_for_report():
        # Reusar paginación para obtener todos los registros según filtros
        filters = {}
        for k in ('sucursal', 'ejecutivo', 'cliente', 'recibo', 'fecha_inicio', 'fechaFin'):
            v = request.args.get(k)
            if v:
                # DB layer espera keys fecha_ini/fechaFin for date filters
                if k == 'fecha_inicio':
                    filters['fecha_ini'] = v
                elif k == 'fechaFin':
                    filters['fechaFin'] = v
                else:
                    filters[k] = v

        # Pedir una página grande para recuperar todos los registros (limite razonable)
        rows, total, _ = get_cobros_paginated(0, 1000000, filters)

        items = []
        for r in rows:
            item = {
                'Código cliente': r.get('codigoCliente') or r.get('codigoCliente') or '',
                'Nombre cliente': r.get('nombreCliente') or r.get('nombreCliente') or '',
                'Método pago': r.get('metodoPago') or r.get('metodoPago') or '',
                'No. Factura': r.get('noFactura') or r.get('noFactura') or '',
                'Valor Pagado': f"L { (r.get('valorPagado') or 0):,.2f}",
                'No. Recibo': r.get('noRecibo') or '',
                'fechaCheque': r.get('fechaCheque') or '',
                'Comentario adicional': r.get('comentarioAdicional') or '',
                'creado': _fmt_dt(r.get('creado')),
            }
            items.append(item)

        # columns not used by builder but return for compatibility
        columns = list(items[0].keys()) if items else []
        return items, columns

    return build_pdf_report(request.args, _get_items_for_report)


# ─── Liquidar ─────────────────────────────────────────────────────────────────

@cxc_bp.route("/liquidar", methods=["POST"])
@login_required
def liquidar():
    data     = request.get_json(silent=True) or {}
    item_ids = data.get("item_ids") or []

    liquidadoPor = _get_user_display_name()

    try:
        resultado = liquidar_por_ids(item_ids=item_ids, liquidadoPor=liquidadoPor)
        log.info(
            "Liquidacion por %s | Actualizados: %d | Errores: %d",
            liquidadoPor, resultado["actualizados"], resultado["errores"],
        )
        return jsonify({"status": "ok", **resultado})
    except Exception as e:
        log.error("Error en /liquidar: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── Rellenar sucursal vacía desde empleados ─────────────────────────────────

@cxc_bp.route("/api/fill-sucursal", methods=["POST"])
@login_required
def fill_sucursal():
    """
    Rellena la columna sucursal de los cobros donde está vacía,
    haciendo match por ejecutivoEmail = empleados.usuario (email completo).
    Solo accesible por super-admin.
    """
    if not session.get('is_super_admin'):
        return jsonify({"status": "error", "message": "Sin permisos."}), 403
    try:
        updated = fill_sucursal_from_empleados()
        return jsonify({
            "status": "ok",
            "updated": updated,
            "message": f"{updated} registro(s) actualizados.",
        })
    except Exception as e:
        log.error("Error en /api/fill-sucursal: %s", e, exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── Reporte PDF-HTML ─────────────────────────────────────────────────────────

@cxc_bp.route("/liquidar/pdf-html", methods=["POST"])
@login_required
def liquidar_pdf_html():
    """
    Recibe JSON con las filas ya seleccionadas en la grilla.
    NO consulta la BD — los datos vienen directo del grid.
    Renderiza reporte_cobros.html que el navegador imprime como PDF.

    Payload JSON esperado:
    {
        "ejecutivo":    "Carlos Martínez",
        "fecha_inicio": "2026-02-01",
        "fechaFin":    "2026-02-26",
        "rows": [
            {
                "Código cliente":       "C001",
                "Nombre cliente":       "Distribuidora Nacional S.A.",
                "Método pago":          "Transferencia",
                "No. Factura":          "FAC-12345",
                "Valor Pagado":         "L 12,500.00",
                "No. Recibo":           "REC-00123",
                "Comentario adicional": ""
            }, ...
        ]
    }
    """
    data = request.get_json(silent=True) or {}

    rows              = data.get("rows", [])
    ejecutivo         = (data.get("ejecutivo")    or "").strip()
    fecha_inicio      = (data.get("fecha_inicio") or "").strip()
    fechaFin         = (data.get("fechaFin")    or "").strip()
    sp_item_ids       = data.get("sp_item_ids", [])  # IDs de cobro para vincular al lote
    is_control_only   = data.get("is_control_only", False)  # True = solo PDF, sin lote

    if not rows:
        return "No hay registros para generar el reporte.", 400

    def _parse_val(v):
        try:
            return float(str(v).replace("L", "").replace(",", "").strip())
        except Exception:
            return 0.0

    def _fmt_display(s):
        if not s:
            return ""
        try:
            y, m, d = s.split("-")
            return f"{d}/{m}/{y}"
        except Exception:
            return s

    def _parse_creado_route(s):
        if not s:
            return None
        try:
            return datetime.datetime.strptime(str(s).split()[0], "%d/%m/%Y").date()
        except Exception:
            return None

    total_valor = sum(_parse_val(r.get("Valor Pagado", "")) for r in rows)
    total_fmt   = f"L {total_valor:,.2f}"

    # 3.3 — Período real desde el campo creado de los registros
    creado_dates = [_parse_creado_route(r.get("creado", "")) for r in rows]
    creado_dates = [d for d in creado_dates if d is not None]
    if creado_dates:
        min_cd = min(creado_dates)
        max_cd = max(creado_dates)
        if min_cd == max_cd:
            rango_txt = min_cd.strftime("%d/%m/%Y")
        else:
            rango_txt = f"{min_cd.strftime('%d/%m/%Y')} al {max_cd.strftime('%d/%m/%Y')}"
    elif fecha_inicio and fechaFin:
        rango_txt = f"{_fmt_display(fecha_inicio)} al {_fmt_display(fechaFin)}"
    elif fecha_inicio:
        rango_txt = f"Desde {_fmt_display(fecha_inicio)}"
    elif fechaFin:
        rango_txt = f"Hasta {_fmt_display(fechaFin)}"
    else:
        rango_txt = "Todos"

    fecha_hoy = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    # Generar PDF con ReportLab directamente
    ejecutivo_final = ejecutivo or _get_user_display_name()
    pdf_bytes = build_pdf_report_from_rows(
        rows          = rows,
        ejecutivo_txt = ejecutivo_final,
        rango_txt     = rango_txt,
    )

    # ── Detectar si algún registro ya está liquidado o si es PDF de control solamente ────
    # Si hay liquidados o es control_only: solo PDF de control, sin guardar en BD ni subir a SharePoint
    tiene_liquidados = any(
        str(r.get('liquidado', '') or '').strip().lower() in ('si', 'sí', '1', 'true')
        for r in rows
    )
    
    # Verificar si algún registro está en estado 'Finalizado'
    tiene_finalizados = any(
        str(r.get('estado_cobro', '') or '').strip().lower() == 'finalizado'
        for r in rows
    )

    if is_control_only or tiene_liquidados or tiene_finalizados:
        _fname = f"liquidacion_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        if is_control_only:
            reason = "control_only"
        elif tiene_liquidados:
            reason = "tiene_liquidados"
        else:
            reason = "tiene_finalizados"
        log.info('PDF de control (sin guardar): %d filas, ejecutivo=%s, razón=%s', len(rows), ejecutivo_final, reason)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"inline; filename={_fname}"},
        )

    # ── Buscar código de empleado para armar la ruta de carpeta ──────────────
    try:
        codigo_empleado = get_codigo_empleado_by_nombre(ejecutivo_final)
    except Exception:
        codigo_empleado = None

    import threading
    year         = datetime.datetime.now().strftime("%Y")
    folder_path  = f"IT/CxC/{year}/{codigo_empleado}" if codigo_empleado else f"IT/CxC/{year}"
    recibos_list = [str(r.get("No. Recibo", "")) for r in rows if r.get("No. Recibo")]
    generadoPor = _get_user_display_name()

    # ── Pre-generar número de liquidación y nombre de archivo ─────────────────
    numero_liq = get_next_numero_liquidacion()   # ej: LIQ-00003
    file_name  = f"{numero_liq}.pdf"             # ej: LIQ-00003.pdf

    # ── Validar que existan cobros para vincular ───────────────────────────────
    if not sp_item_ids:
        log.warning('Intento de crear liquidación sin cobros: ejecutivo=%s, rows=%d', ejecutivo_final, len(rows))
        return Response(
            "Error: No se pueden crear liquidaciones sin cobros vinculados.",
            status=400,
        )

    # ── Registrar en BD de forma SÍNCRONA (antes de devolver el PDF) ───────────
    # Esto garantiza que `cobro.loteId` y `lote.estado='Procesado'` queden
    # guardados antes de que el front-end recargue la grilla.
    try:
        lote_db_id = registrar_liquidacion_pdf(
            ejecutivo          = ejecutivo_final,
            generadoPor       = generadoPor,
            rangoFechas       = rango_txt,
            recibos_list       = recibos_list,
            spFolderPath     = folder_path,
            spFileName       = file_name,
            spFileId         = '',
            spDownloadUrl    = '',
            total              = total_valor,
            sp_item_ids        = sp_item_ids,
            numeroLiquidacion = numero_liq,
        )
    except Exception:
        log.exception('Error al registrar lote en BD')
        lote_db_id = None

    # ── Subir a SharePoint en hilo ──────────────────────────────
    app = current_app._get_current_object()
    _lote_db_id = lote_db_id   # capturar valor en closure

    def _upload_only():
        with app.app_context():
            try:
                ok, file_id, dl_url, err = upload_file_bytes(folder_path, file_name, pdf_bytes)
                if ok and _lote_db_id:
                    update_lote_sp_info(_lote_db_id, file_id or '', dl_url or '')
                elif not ok:
                    log.warning('No se pudo subir PDF a SharePoint: %s', err)
            except Exception:
                log.exception('Error en _upload_only')

    threading.Thread(target=_upload_only, daemon=True).start()

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename={file_name}",
            "X-Lote-Id": str(lote_db_id or ''),
            "X-Numero-Liq": numero_liq,
        },
    )


@cxc_bp.route("/liquidacion/pdf-info/<path:no_recibo>", methods=["GET"])
@login_required
def liquidacion_pdf_info(no_recibo):
    """Devuelve JSON con info del último PDF de liquidación que contiene este recibo."""
    info = get_liquidacion_por_recibo(no_recibo)
    if not info:
        return jsonify({'found': False}), 200
    return jsonify({'found': True, **info}), 200


# ─── Liquidaciones / Lotes ───────────────────────────────────────────────────

@cxc_bp.route("/lotes", methods=["GET"])
@login_required
def lotes_list():
    """Retorna JSON con todos los lotes de liquidación."""
    try:
        limit = int(request.args.get('limit', 200))
    except Exception:
        limit = 200
    estado       = request.args.get('estado')       or None
    ejecutivo    = request.args.get('ejecutivo')    or None
    recibo       = request.args.get('recibo')       or None
    fecha_inicio = request.args.get('fecha_inicio') or None
    fechaFin    = request.args.get('fechaFin')    or None
    sucursal     = request.args.get('sucursal')     or None
    cliente      = request.args.get('cliente')      or None
    
    # ─── Control de acceso: Auditors solo ven sus propios registros ────────────
    cxc_role = _get_cxc_role()
    current_user = _get_user_display_name()
    
    if (cxc_role or '').lower() == 'auditor':
        # Auditor: forzar filtro por su nombre
        if ejecutivo and ejecutivo != current_user:
            # Intenta acceder a datos de otro ejecutivo
            return jsonify([]), 403
        ejecutivo = current_user
    
    # ─── Control de acceso: Operadores solo ven su sucursal ────────────────────
    elif (cxc_role or '').lower() == 'operador':
        # Operador: forzar filtro por su sucursal
        operador_sucursal = session.get('empleado_sucursal', '')
        if sucursal and sucursal != operador_sucursal:
            # Intenta acceder a datos de otra sucursal
            return jsonify([]), 403
        sucursal = operador_sucursal
    
    return jsonify(get_lotes(limit, estado=estado, ejecutivo=ejecutivo,
                             recibo=recibo, fecha_inicio=fecha_inicio,
                             fechaFin=fechaFin, sucursal=sucursal,
                             cliente=cliente))


@cxc_bp.route("/lotes/<int:loteId>/finalizar", methods=["POST"])
@login_required
def lote_finalizar(loteId):
    """Cambia el estado de un lote a Finalizado. Requiere estadoDoc=14 en el nuevo flujo."""
    _role = (_get_cxc_role() or '').lower()
    if _role not in ('admin', 'operador') and not session.get('is_admin') and not session.get('is_super_admin'):
        return jsonify({'status': 'error', 'message': 'Sin permisos.'}), 403

    # Verificar estadoDoc: si es un lote nuevo (estadoDoc no nulo) debe ser 14
    lote = get_lote_by_id(loteId)
    if not lote:
        return jsonify({'status': 'error', 'message': 'Lote no encontrado.'}), 404

    # Verificar estado: si es un sub-estado numérico (11-13) bloquear la liquidación
    estado = str(lote.get('estado') or '')
    try:
        estado_num = int(estado)
        if estado_num != 14:
            _labels = {11: 'generado (pendiente de firma)', 12: 'firmado (pendiente de confirmar)', 13: 'en revisión'}
            desc = _labels.get(estado_num, f'estado={estado}')
            return jsonify({'status': 'error', 'message': f'No se puede liquidar. El documento está {desc}.'}), 400
    except (ValueError, TypeError):
        pass  # Estado legacy 'Procesado' / 'Finalizado' — no bloquear

    finalizado_por = _get_user_display_name()
    ok = finalizar_lote(loteId, finalizado_por)
    if ok:
        return jsonify({'status': 'ok', 'message': 'Lote finalizado correctamente.'})
    return jsonify({'status': 'error', 'message': 'No se pudo finalizar (ya estaba finalizado o no existe).'}), 400


@cxc_bp.route("/lotes/<int:loteId>/subir-firmado", methods=["POST"])
@login_required
def lote_subir_firmado(loteId):
    """
    Recibe el PDF firmado del usuario y lo sube a OneDrive/SharePoint como
    {numeroLiquidacion}_rev.pdf → actualiza estadoDoc a 12.
    """
    lote = get_lote_by_id(loteId)
    if not lote:
        return jsonify({'status': 'error', 'message': 'Lote no encontrado.'}), 404

    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No se recibió archivo (campo "file" requerido).'}), 400

    f = request.files['file']
    if not f.filename or not f.filename.lower().endswith('.pdf'):
        return jsonify({'status': 'error', 'message': 'Solo se permite subir archivos PDF.'}), 400

    file_bytes = f.read()
    if not file_bytes:
        return jsonify({'status': 'error', 'message': 'El archivo recibido está vacío.'}), 400

    # Nombre del archivo con sufijo rev (espacio antes de rev)
    numero = lote.get('numeroLiquidacion') or f'LIQ-{loteId:05d}'
    rev_filename = f'{numero} rev.pdf'
    folder_path  = lote.get('spFolderPath') or f'IT/CxC/{datetime.datetime.now().year}'

    ok, file_id, dl_url, err = upload_file_bytes(folder_path, rev_filename, file_bytes)
    if not ok:
        log.error('lote_subir_firmado: error subiendo %s a %s: %s', rev_filename, folder_path, err)
        return jsonify({'status': 'error', 'message': f'Error al subir el archivo a la nube: {err}'}), 500

    update_lote_estado(loteId, '12')
    update_lote_rev_sp_info(loteId, file_id or '', dl_url or '')
    log.info('lote_subir_firmado: lote=%s → %s/%s subido, estado=12 por %s',
             loteId, folder_path, rev_filename, _get_user_display_name())
    return jsonify({
        'status': 'ok',
        'message': f'Archivo {rev_filename} subido correctamente. Pendiente de confirmación.',
        'rev_filename': rev_filename,
        'rev_file_id': file_id or '',
        'rev_dl_url': dl_url or '',
        'estado': '12',
    })


@cxc_bp.route("/lotes/<int:loteId>/confirmar", methods=["POST"])
@login_required
def lote_confirmar(loteId):
    """
    Confirma el documento revisado → estadoDoc=14, lo que habilita la liquidación.
    Solo accesible por Admin/SuperAdmin/Operador (no ejecutivo/Auditor).
    """
    cxc_role = _get_cxc_role()
    if (cxc_role or '').lower() == 'auditor':
        return jsonify({'status': 'error', 'message': 'Sin permisos para confirmar documentos.'}), 403

    lote = get_lote_by_id(loteId)
    if not lote:
        return jsonify({'status': 'error', 'message': 'Lote no encontrado.'}), 404

    update_lote_estado(loteId, '14')

    # Gestión de archivos en SharePoint:
    # 1. Eliminar el original (sin sufijo rev)
    # 2. Renombrar el firmado ({numero} rev.pdf → {numero}.pdf)
    orig_file_id = lote.get('spFileId') or ''
    rev_file_id  = lote.get('spRevFileId') or ''
    numero       = lote.get('numeroLiquidacion') or f'LIQ-{loteId:05d}'
    final_name   = f'{numero}.pdf'

    if orig_file_id:
        ok_del, err_del = delete_file_by_id(orig_file_id)
        if not ok_del:
            log.warning('lote_confirmar: no se pudo eliminar original %s: %s', orig_file_id, err_del)

    if rev_file_id:
        ok_ren, err_ren = rename_file_by_id(rev_file_id, final_name)
        if ok_ren:
            # El file_id se mantiene tras renombrar; actualizar spFileId con el id del rev
            update_lote_sp_info(loteId, rev_file_id, '')
            clear_lote_rev_sp_info(loteId)
        else:
            log.warning('lote_confirmar: no se pudo renombrar rev %s → %s: %s', rev_file_id, final_name, err_ren)

    log.info('lote_confirmar: lote=%s confirmado (estado=14) por %s', loteId, _get_user_display_name())
    return jsonify({
        'status': 'ok',
        'message': 'Documento confirmado. La liquidación está ahora habilitada.',
        'estado': '14',
    })


@cxc_bp.route("/lotes/<int:loteId>/marcar-revision", methods=["POST"])
@login_required
def lote_marcar_revision(loteId):
    """Marca el documento como en revisión → estadoDoc=13."""
    lote = get_lote_by_id(loteId)
    if not lote:
        return jsonify({'status': 'error', 'message': 'Lote no encontrado.'}), 404
    update_lote_estado(loteId, '13')
    log.info('lote_marcar_revision: lote=%s → estado=13 por %s', loteId, _get_user_display_name())
    return jsonify({'status': 'ok', 'estado': '13'})


@cxc_bp.route("/lotes/<int:loteId>/regenerar", methods=["POST"])
@login_required
def lote_regenerar(loteId):
    """Regresa el lote al estado 11 (generado, pendiente de firma) y elimina el archivo rev de OneDrive."""
    cxc_role = _get_cxc_role()
    if (cxc_role or '').lower() == 'auditor':
        return jsonify({'status': 'error', 'message': 'Sin permisos.'}), 403
    lote = get_lote_by_id(loteId)
    if not lote:
        return jsonify({'status': 'error', 'message': 'Lote no encontrado.'}), 404
    # Eliminar el archivo rev de OneDrive si existe
    rev_file_id = lote.get('spRevFileId') or ''
    if rev_file_id:
        try:
            delete_file_by_id(rev_file_id)
        except Exception as e:
            log.warning('lote_regenerar: no se pudo eliminar rev file %s: %s', rev_file_id, e)
        clear_lote_rev_sp_info(loteId)
    update_lote_estado(loteId, '11')
    log.info('lote_regenerar: lote=%s → estado=11 por %s', loteId, _get_user_display_name())
    return jsonify({'status': 'ok', 'estado': '11', 'message': 'Lote regresado a estado generado.'})


@cxc_bp.route("/lotes/<int:loteId>/cobros", methods=["GET"])
@login_required
def lote_cobros(loteId):
    """Retorna los cobros vinculados a un lote."""
    rows = get_cobros_by_lote(loteId)
    # Serializar fechas
    for r in rows:
        for k in ('creado', 'fechaLiquidado'):
            if r.get(k) is not None:
                r[k] = str(r[k])
    return jsonify(rows)


@cxc_bp.route("/liquidaciones", methods=["GET"])
@login_required
def liquidaciones_list():
    """Retorna JSON con las últimas liquidaciones registradas (para tabla de gestión)."""
    try:
        limit = int(request.args.get('limit', 100))
    except Exception:
        limit = 100
    registros = get_liquidaciones_recientes(limit=limit)
    # Serializar fechas
    for r in registros:
        if r.get('fechaGeneracion'):
            r['fechaGeneracion'] = str(r['fechaGeneracion'])
    return jsonify({'data': registros})


@cxc_bp.route("/lotes/<int:loteId>/pdf", methods=["GET"])
@login_required
def lote_pdf(loteId):
    """Sirve el PDF de un lote: desde SharePoint si está disponible, o lo regenera desde DB."""
    from .operations import get_cobros_by_lote
    from .liqpdf import build_pdf_report_from_rows

    # Obtener metadata del lote
    conn = None
    try:
        from ..core.db import get_db_cxc
        conn = get_db_cxc()
        c = conn.cursor()
        c.execute(
            "SELECT id, numeroLiquidacion, ejecutivo, rangoFechas, "
            "spFileId, spFileName, spDownloadUrl "
            "FROM lote WHERE id = ?",
            loteId,
        )
        row = c.fetchone()
    except Exception:
        log.exception("Error al buscar lote id=%s para PDF", loteId)
        row = None

    if not row:
        return "Lote no encontrado.", 404

    numero_liq, ejecutivo, rangoFechas, spFileId, spFileName, spDownloadUrl = (
        row[1], row[2], row[3], row[4] or '', row[5] or '', row[6] or ''
    )
    file_name = spFileName or (numero_liq + '.pdf' if numero_liq else 'liquidacion.pdf')

    # Si tiene file_id en SP → proxy download
    if spFileId:
        from ..services.onedrive_service import download_pdf_bytes
        ok, file_bytes, err = download_pdf_bytes(spFileId)
        if ok:
            return Response(
                file_bytes,
                mimetype="application/pdf",
                headers={"Content-Disposition": f"inline; filename={file_name}"},
            )

    # Fallback: regenerar desde cobros almacenados
    cobros = get_cobros_by_lote(loteId)
    if not cobros:
        return "PDF no disponible (sin cobros asociados).", 404

    # Mapear columnas DB → formato esperado por build_pdf_report_from_rows
    def _map(r):
        return {
            "Código cliente":       r.get("codigoCliente") or "",
            "Nombre cliente":       r.get("nombreCliente") or "",
            "Método pago":          r.get("metodoPago") or "",
            "No. Factura":          r.get("noFactura") or "",
            "Valor Pagado":         r.get("valorPagado") or "",
            "No. Recibo":           r.get("noRecibo") or "",
            "liquidado":            r.get("liquidado") or "",
            "fechaCheque":         r.get("fechaCheque") or "",
            "Comentario adicional": "",
            "creado":               str(r.get("creado") or ""),
        }

    rows_mapped = [_map(r) for r in cobros]
    pdf_bytes = build_pdf_report_from_rows(
        rows          = rows_mapped,
        ejecutivo_txt = ejecutivo or "",
        rango_txt     = rangoFechas or "Todos",
    )
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename={file_name}"},
    )


@cxc_bp.route("/lotes/ui", methods=["GET"])
@login_required
def lotes_ui():
    """Página dedicada de Liquidaciones (AG Grid)."""
    role = _get_cxc_role()
    return render_template(
        'lotes.html',
        user_name    = session.get('empleado_nombre') or session.get('username') or '',
        can_liquidar = role in ('Admin', 'Operador') or session.get('is_admin') or session.get('is_super_admin'),
        is_admin     = session.get('is_admin', False),
        is_super_admin = session.get('is_super_admin', False),
    )


@cxc_bp.route("/liquidacion/download/<path:file_id>", methods=["GET"])
@login_required
def liquidacion_download(file_id):
    """Descarga un PDF de liquidación desde SharePoint por ID de archivo Graph."""
    from ..services.onedrive_service import download_pdf_bytes
    file_name = request.args.get('name', 'liquidacion.pdf')
    ok, file_bytes, err = download_pdf_bytes(file_id)
    if not ok:
        return f"No se pudo descargar el archivo: {err}", 404
    return Response(
        file_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename={file_name}"},
    )
