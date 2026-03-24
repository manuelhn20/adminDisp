# admin_disp/inventario/routes.py
"""
Blueprint de rutas para el módulo INVENTARIO
"""

from flask import Blueprint, request, jsonify, render_template
import logging

from . import service

logger = logging.getLogger("admin_disp.inventario")

bp_inventario = Blueprint("inventario", __name__, url_prefix="/inventario",
                          template_folder="templates")


# ─── PÁGINAS HTML ──────────────────────────────────────────────────────────

@bp_inventario.route("/", methods=["GET"])
def index():
    """Página principal del módulo inventario"""
    return render_template("inventario/index.html")


@bp_inventario.route("/marcas", methods=["GET"])
def marcas_page():
    """Página de gestión de marcas"""
    return render_template("inventario/marcas.html")


@bp_inventario.route("/productos", methods=["GET"])
def productos_page():
    """Página de gestión de productos"""
    return render_template("inventario/productos.html")


@bp_inventario.route("/movimientos", methods=["GET"])
def movimientos_page():
    """Página de movimientos de stock"""
    return render_template("inventario/movimientos.html")


# ─── MARCAS - API ──────────────────────────────────────────────────────────

@bp_inventario.route("/api/marcas", methods=["GET"])
def api_get_marcas():
    """GET /api/marcas - Obtiene todas las marcas"""
    try:
        include_inactive = request.args.get("incluir_inactivas", False, type=bool)
        marcas = service.get_marcas(include_inactive=include_inactive)
        return jsonify({"success": True, "data": marcas}), 200
    except Exception as e:
        logger.exception("[marcas.getAll]")
        return jsonify({"success": False, "message": str(e)}), 500


@bp_inventario.route("/api/marcas/activas", methods=["GET"])
def api_get_marcas_activas():
    """GET /api/marcas/activas - Obtiene solo marcas activas (para selects)"""
    try:
        marcas = service.get_marcas_activas()
        return jsonify({"success": True, "data": marcas}), 200
    except Exception as e:
        logger.exception("[marcas.getActivas]")
        return jsonify({"success": False, "message": str(e)}), 500


@bp_inventario.route("/api/marcas", methods=["POST"])
def api_create_marca():
    """POST /api/marcas - Crea una nueva marca"""
    try:
        data = request.get_json()
        nombre = data.get("nombre", "").strip()
        
        if not nombre:
            return jsonify({"success": False, "message": "El nombre es requerido"}), 400
        
        marca_id = service.create_marca(nombre)
        return jsonify({
            "success": True,
            "message": "Marca creada",
            "id": marca_id
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 409
    except Exception as e:
        logger.exception("[marcas.create]")
        return jsonify({"success": False, "message": str(e)}), 500


@bp_inventario.route("/api/marcas/<int:marca_id>", methods=["PUT"])
def api_update_marca(marca_id):
    """PUT /api/marcas/:id - Actualiza una marca"""
    try:
        data = request.get_json()
        nombre = data.get("nombre", "").strip()
        
        if not nombre:
            return jsonify({"success": False, "message": "El nombre es requerido"}), 400
        
        service.update_marca(marca_id, nombre)
        return jsonify({"success": True, "message": "Marca actualizada"}), 200
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404 if "no encontrada" in str(e).lower() else 409
    except Exception as e:
        logger.exception("[marcas.update]")
        return jsonify({"success": False, "message": str(e)}), 500


@bp_inventario.route("/api/marcas/<int:marca_id>/estado", methods=["PATCH"])
def api_toggle_marca_estado(marca_id):
    """PATCH /api/marcas/:id/estado - Activa/desactiva una marca"""
    try:
        service.toggle_marca_estado(marca_id)
        return jsonify({"success": True, "message": "Marca actualizada"}), 200
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404
    except Exception as e:
        logger.exception("[marcas.toggleEstado]")
        return jsonify({"success": False, "message": str(e)}), 500


# ─── PRODUCTOS - API ───────────────────────────────────────────────────────

@bp_inventario.route("/api/productos", methods=["GET"])
def api_get_productos():
    """GET /api/productos - Obtiene todos los productos"""
    try:
        include_inactive = request.args.get("incluir_inactivos", False, type=bool)
        productos = service.get_productos(include_inactive=include_inactive)
        return jsonify({"success": True, "data": productos}), 200
    except Exception as e:
        logger.exception("[productos.getAll]")
        return jsonify({"success": False, "message": str(e)}), 500


@bp_inventario.route("/api/productos/<int:producto_id>", methods=["GET"])
def api_get_producto(producto_id):
    """GET /api/productos/:id - Obtiene un producto por ID"""
    try:
        producto = service.get_producto_by_id(producto_id)
        if not producto:
            return jsonify({"success": False, "message": "Producto no encontrado"}), 404
        return jsonify({"success": True, "data": producto}), 200
    except Exception as e:
        logger.exception("[productos.getById]")
        return jsonify({"success": False, "message": str(e)}), 500


@bp_inventario.route("/api/productos", methods=["POST"])
def api_create_producto():
    """POST /api/productos - Crea un nuevo producto"""
    try:
        data = request.get_json()
        nombre = data.get("nombre", "").strip()
        
        if not nombre:
            return jsonify({"success": False, "message": "El nombre es requerido"}), 400
        
        producto_id = service.create_producto(
            nombre=nombre,
            descripcion=data.get("descripcion"),
            upc1=data.get("upc1"),
            upc2=data.get("upc2"),
            marca_id=data.get("marcaId"),
            precio=float(data.get("precio", 0))
        )
        return jsonify({
            "success": True,
            "message": "Producto creado",
            "id": producto_id
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 409
    except Exception as e:
        logger.exception("[productos.create]")
        return jsonify({"success": False, "message": str(e)}), 500


@bp_inventario.route("/api/productos/<int:producto_id>", methods=["PUT"])
def api_update_producto(producto_id):
    """PUT /api/productos/:id - Actualiza un producto"""
    try:
        data = request.get_json()
        service.update_producto(
            producto_id=producto_id,
            nombre=data.get("nombre"),
            descripcion=data.get("descripcion"),
            upc1=data.get("upc1"),
            upc2=data.get("upc2"),
            marca_id=data.get("marcaId"),
            precio=float(data.get("precio")) if "precio" in data else None
        )
        return jsonify({"success": True, "message": "Producto actualizado"}), 200
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404 if "no encontrado" in str(e).lower() else 409
    except Exception as e:
        logger.exception("[productos.update]")
        return jsonify({"success": False, "message": str(e)}), 500


@bp_inventario.route("/api/productos/<int:producto_id>/estado", methods=["PATCH"])
def api_toggle_producto_estado(producto_id):
    """PATCH /api/productos/:id/estado - Activa/desactiva un producto"""
    try:
        service.toggle_producto_estado(producto_id)
        return jsonify({"success": True, "message": "Producto actualizado"}), 200
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 404
    except Exception as e:
        logger.exception("[productos.toggleEstado]")
        return jsonify({"success": False, "message": str(e)}), 500


# ─── MOVIMIENTOS - API ─────────────────────────────────────────────────────

@bp_inventario.route("/api/movimientos", methods=["GET"])
def api_get_movimientos():
    """GET /api/movimientos - Obtiene movimientos (?tipo=entrada|salida|ajuste)"""
    try:
        tipo = request.args.get("tipo")
        include_inactive = request.args.get("incluir_inactivos", False, type=bool)
        movimientos = service.get_movimientos(tipo=tipo, include_inactive=include_inactive)
        return jsonify({"success": True, "data": movimientos}), 200
    except Exception as e:
        logger.exception("[movimientos.getAll]")
        return jsonify({"success": False, "message": str(e)}), 500


@bp_inventario.route("/api/movimientos/stock", methods=["GET"])
def api_get_stock():
    """GET /api/movimientos/stock - Obtiene stock actual por producto"""
    try:
        stock = service.get_stock()
        return jsonify({"success": True, "data": stock}), 200
    except Exception as e:
        logger.exception("[movimientos.getStock]")
        return jsonify({"success": False, "message": str(e)}), 500


@bp_inventario.route("/api/movimientos", methods=["POST"])
def api_create_movimiento():
    """POST /api/movimientos - Crea un movimiento de stock"""
    try:
        data = request.get_json()
        producto_id = data.get("productoId")
        tipo = data.get("tipo", "").lower()
        cantidad = int(data.get("cantidad", 0))
        
        if not producto_id or not tipo:
            return jsonify({"success": False, "message": "Faltan parámetros"}), 400
        
        movimiento_id = service.create_movimiento(
            producto_id=producto_id,
            tipo=tipo,
            cantidad=cantidad,
            referencia=data.get("referencia"),
            observacion=data.get("observacion")
        )
        return jsonify({
            "success": True,
            "message": "Movimiento registrado",
            "id": movimiento_id
        }), 201
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        logger.exception("[movimientos.create]")
        return jsonify({"success": False, "message": str(e)}), 500


@bp_inventario.route("/api/movimientos/<int:movimiento_id>", methods=["DELETE"])
def api_delete_movimiento(movimiento_id):
    """DELETE /api/movimientos/:id - Elimina lógicamente un movimiento"""
    try:
        service.soft_delete_movimiento(movimiento_id)
        return jsonify({"success": True, "message": "Movimiento eliminado"}), 200
    except Exception as e:
        logger.exception("[movimientos.delete]")
        return jsonify({"success": False, "message": str(e)}), 500
