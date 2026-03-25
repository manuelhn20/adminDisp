# admin_disp/kardex/routes.py
"""
Rutas del módulo KARDEX.
Todas las rutas requieren sesión activa y rol 'admin' u 'operador' en sistema 'kardex'.
"""

from __future__ import annotations

import logging
from flask import (
    Blueprint, render_template, jsonify, request,
    session, redirect, url_for
)

from ..common.rbac import require_roles
from . import db as kardex_db
from .service import sync_productos, sync_almacenes

logger = logging.getLogger("admin_disp.kardex")
# Session update: 2026-03-24 14:39:20 - Rebuild schema support and extraction compatibility.

kardex_bp = Blueprint("kardex", __name__,
                       template_folder="../templates",
                       url_prefix="/kardex")


def _login_required(f):
    """Redirecciona al login si no hay sesión."""
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login_form"))
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Páginas (HTML)
# ---------------------------------------------------------------------------

@kardex_bp.route("/")
@_login_required
def index():
    return redirect(url_for("kardex.productos_view"))


@kardex_bp.route("/productos")
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def productos_view():
    periodo_activo = kardex_db.get_periodo_activo()
    return render_template(
        "productos.html",
        page_title="Productos",
        periodo_activo=periodo_activo,
        disable_global_sanitize_patch=True,
    )


@kardex_bp.route("/almacenes")
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def almacenes_view():
    periodo_activo = kardex_db.get_periodo_activo()
    return render_template(
        "almacenes.html",
        page_title="Almacenes",
        periodo_activo=periodo_activo,
    )


@kardex_bp.route("/marcas")
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def marcas_view():
    periodo_activo = kardex_db.get_periodo_activo()
    return render_template(
        "marcas.html",
        page_title="Marcas",
        periodo_activo=periodo_activo,
    )


@kardex_bp.route("/periodos")
@_login_required
@require_roles(["admin"], sistema="kardex")
def periodos_view():
    return render_template(
        "periodos.html",
        page_title="Períodos",
    )


# ---------------------------------------------------------------------------
# API — Períodos
# ---------------------------------------------------------------------------

@kardex_bp.route("/api/periodos", methods=["GET"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_periodos_list():
    try:
        data = kardex_db.get_periodos()
        # Serializar fechas
        for row in data:
            for key in ("fechaInicio", "fechaFin", "createdAt"):
                if row.get(key) and hasattr(row[key], "isoformat"):
                    row[key] = row[key].isoformat()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error("Error listando períodos: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/periodos", methods=["POST"])
@_login_required
@require_roles(["admin"], sistema="kardex")
def api_periodos_create():
    try:
        body = request.get_json(force=True)
        result = kardex_db.create_periodo(
            nombre=body["nombre"],
            mes=int(body["mes"]),
            ano=int(body["ano"]),
            fecha_inicio=body["fechaInicio"],
            fecha_fin=body["fechaFin"],
        )
        return jsonify({"success": True, **result}), 201
    except KeyError as e:
        return jsonify({"success": False, "error": f"Campo requerido: {e}"}), 400
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error("Error creando período: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/periodos/<int:periodo_id>", methods=["PUT"])
@_login_required
@require_roles(["admin"], sistema="kardex")
def api_periodos_update(periodo_id: int):
    try:
        body = request.get_json(force=True)
        updated = kardex_db.update_periodo(
            periodo_id=periodo_id,
            nombre=body["nombre"],
            mes=int(body["mes"]),
            ano=int(body["ano"]),
            fecha_inicio=body["fechaInicio"],
            fecha_fin=body["fechaFin"],
        )
        return jsonify({"success": bool(updated)})
    except KeyError as e:
        return jsonify({"success": False, "error": f"Campo requerido: {e}"}), 400
    except Exception as e:
        logger.error("Error actualizando período %s: %s", periodo_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/periodos/<int:periodo_id>/activar", methods=["POST"])
@_login_required
@require_roles(["admin"], sistema="kardex")
def api_periodos_activar(periodo_id: int):
    try:
        kardex_db.activate_periodo(periodo_id)
        return jsonify({"success": True, "message": f"Período {periodo_id} activado"})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error("Error activando período %s: %s", periodo_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/periodos/<int:periodo_id>/estado", methods=["POST"])
@_login_required
@require_roles(["admin"], sistema="kardex")
def api_periodos_estado(periodo_id: int):
    try:
        body = request.get_json(force=True) or {}
        estado = body.get("estado")
        
        # Aceptar 0/1/2 (numérico) o strings equivalentes
        if isinstance(estado, str):
            estado = int(estado)
        
        if estado not in {0, 1, 2}:
            return jsonify({"success": False, "error": "Estado inválido. Usa 0 (programado), 1 (activo) o 2 (pasado/deshabilitado)."}), 400
        
        changed = kardex_db.set_periodo_estado(periodo_id, estado)
        return jsonify({"success": bool(changed)})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.error("Error cambiando estado de período %s: %s", periodo_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/periodos/<int:periodo_id>", methods=["DELETE"])
@_login_required
@require_roles(["admin"], sistema="kardex")
def api_periodos_delete(periodo_id: int):
    try:
        deleted = kardex_db.delete_periodo(periodo_id)
        if not deleted:
            return jsonify({
                "success": False,
                "error": "No se puede inactivar: el período está activo o no existe."
            }), 400
        return jsonify({"success": True, "message": "Período inactivado"})
    except Exception as e:
        logger.error("Error eliminando período %s: %s", periodo_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# API — Marcas
# ---------------------------------------------------------------------------

@kardex_bp.route("/api/marcas", methods=["GET"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_marcas_list():
    try:
        incluir_inactivas = request.args.get("incluirInactivas", "1") == "1"
        data = kardex_db.get_marcas(include_inactive=incluir_inactivas)
        for row in data:
            if row.get("syncedAt") and hasattr(row["syncedAt"], "isoformat"):
                row["syncedAt"] = row["syncedAt"].isoformat()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error("Error listando marcas: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/marcas/<marca_id>", methods=["PUT"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_marcas_update(marca_id: str):
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        if not name:
            return jsonify({"success": False, "error": "Nombre requerido"}), 400
        updated = kardex_db.update_marca(marca_id, name, description)
        return jsonify({"success": bool(updated)})
    except Exception as e:
        logger.error("Error actualizando marca %s: %s", marca_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/marcas/<marca_id>/estado", methods=["POST"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_marcas_estado(marca_id: str):
    try:
        data = request.get_json(force=True) or {}
        if "estado" not in data:
            return jsonify({"success": False, "error": "Campo estado requerido"}), 400
        estado = int(data.get("estado"))
        if estado not in (0, 1):
            return jsonify({"success": False, "error": "Estado inválido"}), 400
        changed = kardex_db.set_marca_estado(marca_id, estado)
        return jsonify({"success": bool(changed)})
    except Exception as e:
        logger.error("Error cambiando estado de marca %s: %s", marca_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# API — Productos
# ---------------------------------------------------------------------------

@kardex_bp.route("/api/productos", methods=["GET"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_productos_list():
    try:
        solo_disponibles = request.args.get("disponibles", "0") == "1"
        data = kardex_db.get_productos(solo_disponibles=solo_disponibles)
        for row in data:
            if row.get("syncedAt") and hasattr(row["syncedAt"], "isoformat"):
                row["syncedAt"] = row["syncedAt"].isoformat()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error("Error listando productos: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# API — Almacenes
# ---------------------------------------------------------------------------

@kardex_bp.route("/api/almacenes", methods=["GET"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_almacenes_list():
    try:
        todos = request.args.get("todos", "0") == "1"
        data = kardex_db.get_almacenes(solo_activos=not todos)
        for row in data:
            if row.get("syncedAt") and hasattr(row["syncedAt"], "isoformat"):
                row["syncedAt"] = row["syncedAt"].isoformat()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error("Error listando almacenes: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/marcas", methods=["POST"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_marcas_create():
    try:
        data = request.get_json() or {}
        name = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        if not name:
            return jsonify({"success": False, "error": "Nombre requerido"}), 400
        result = kardex_db.create_marca(name, description)
        return jsonify({"success": True, "data": result, "id": result.get("id")}), 201
    except Exception as e:
        logger.error("Error creando marca: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/productos", methods=["POST"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_productos_create():
    try:
        data = request.get_json() or {}
        item_name = data.get("itemName", "").strip()
        if not item_name:
            return jsonify({"success": False, "error": "Nombre requerido"}), 400
        result = kardex_db.create_producto(
            item_name=item_name,
            brand=data.get("marca"),
            categoria=data.get("categoria", "").strip(),
            um=data.get("um", "").strip()
        )
        return jsonify({"success": True, "data": result, "id": result.get("id")}), 201
    except Exception as e:
        logger.error("Error creando producto: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/productos/<producto_id>/estado", methods=["POST"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_productos_estado(producto_id: str):
    try:
        data = request.get_json(force=True) or {}
        if "estado" not in data:
            return jsonify({"success": False, "error": "Campo estado requerido"}), 400
        estado = int(data.get("estado"))
        if estado not in (0, 1):
            return jsonify({"success": False, "error": "Estado inválido"}), 400
        changed = kardex_db.set_producto_estado(producto_id, estado)
        return jsonify({"success": bool(changed)})
    except Exception as e:
        logger.error("Error cambiando estado de producto %s: %s", producto_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/almacenes", methods=["POST"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_almacenes_create():
    try:
        data = request.get_json() or {}
        descripcion = data.get("descripcion", "").strip()
        if not descripcion:
            return jsonify({"success": False, "error": "Descripción requerida"}), 400
        result = kardex_db.create_almacen(
            descripcion=descripcion,
            id_name=data.get("idName", "").strip(),
            company=data.get("company", "").strip(),
            tipo_almacen=data.get("tipoAlmacen", "").strip()
        )
        return jsonify({"success": True, "data": result, "id": result.get("id")}), 201
    except Exception as e:
        logger.error("Error creando almacén: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/almacenes/<almacen_id>", methods=["PUT"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_almacenes_update(almacen_id: str):
    try:
        data = request.get_json() or {}
        descripcion = (data.get("descripcion") or "").strip()
        if not descripcion:
            return jsonify({"success": False, "error": "Descripción requerida"}), 400
        updated = kardex_db.update_almacen(
            almacen_id=almacen_id,
            descripcion=descripcion,
            id_name=(data.get("idName") or "").strip(),
            company=(data.get("company") or "").strip(),
            tipo_almacen=(data.get("tipoAlmacen") or "").strip(),
        )
        return jsonify({"success": bool(updated)})
    except Exception as e:
        logger.error("Error actualizando almacén %s: %s", almacen_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


@kardex_bp.route("/api/almacenes/<almacen_id>/estado", methods=["POST"])
@_login_required
@require_roles(["admin", "operador"], sistema="kardex")
def api_almacenes_estado(almacen_id: str):
    try:
        data = request.get_json(force=True) or {}
        if "status" not in data:
            return jsonify({"success": False, "error": "Campo status requerido"}), 400
        status = int(data.get("status"))
        if status not in (0, 1):
            return jsonify({"success": False, "error": "Status inválido"}), 400
        changed = kardex_db.set_almacen_status(almacen_id, status)
        return jsonify({"success": bool(changed)})
    except Exception as e:
        logger.error("Error cambiando estado de almacén %s: %s", almacen_id, e)
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------------------------------------------------------
# API — Sincronización SharePoint
# ---------------------------------------------------------------------------

@kardex_bp.route("/api/sync/productos", methods=["POST"])
@_login_required
@require_roles(["admin"], sistema="kardex")
def api_sync_productos():
    logger.info("[KARDEX] Sync productos solicitado por usuario=%s",
                session.get("username"))
    result = sync_productos()
    status = 200 if result.get("success") else 500
    return jsonify(result), status


@kardex_bp.route("/api/sync/almacenes", methods=["POST"])
@_login_required
@require_roles(["admin"], sistema="kardex")
def api_sync_almacenes():
    logger.info("[KARDEX] Sync almacenes solicitado por usuario=%s",
                session.get("username"))
    result = sync_almacenes()
    status = 200 if result.get("success") else 500
    return jsonify(result), status
