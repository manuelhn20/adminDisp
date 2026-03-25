# admin_disp/inventario/service.py
"""
Servicio de Inventario - Lógica de negocio para marcas, productos y movimientos
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import text

from ..core.db import get_sa_engine_main

logger = logging.getLogger("admin_disp.inventario")


def _fetch_all(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    engine = get_sa_engine_main()
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row) for row in result.mappings().all()]


def _fetch_one(query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    engine = get_sa_engine_main()
    with engine.connect() as conn:
        row = conn.execute(text(query), params or {}).mappings().first()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# MARCA
# ---------------------------------------------------------------------------

def get_marcas(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Obtiene todas las marcas (activas por defecto)"""
    if include_inactive:
        return _fetch_all(
            """
            SELECT id, nombre, estado, createdAt, updatedAt
            FROM marca
            ORDER BY nombre ASC
            """
        )
    return _fetch_all(
        """
        SELECT id, nombre, estado, createdAt, updatedAt
        FROM marca
        WHERE estado = 1
        ORDER BY nombre ASC
        """
    )


def get_marcas_activas() -> List[Dict[str, Any]]:
    """Obtiene solo marcas activas (para selects)"""
    return get_marcas(include_inactive=False)


def create_marca(nombre: str) -> int:
    """Crea una nueva marca"""
    nombre_trim = nombre.strip()
    if not nombre_trim:
        raise ValueError("El nombre es requerido")

    engine = get_sa_engine_main()
    try:
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT id FROM marca WHERE LOWER(nombre) = LOWER(:nombre)"),
                {"nombre": nombre_trim},
            ).first()
            if exists:
                raise ValueError("Ya existe una marca con ese nombre")

            marca_id = conn.execute(
                text("INSERT INTO marca (nombre, estado) OUTPUT INSERTED.id VALUES (:nombre, 1)"),
                {"nombre": nombre_trim},
            ).scalar_one()

        logger.info("Marca creada id=%s nombre=%s", marca_id, nombre_trim)
        return int(marca_id)
    except Exception as e:
        logger.error("Error creando marca: %s", e)
        raise


def update_marca(marca_id: int, nombre: str) -> bool:
    """Actualiza una marca"""
    nombre_trim = nombre.strip()
    if not nombre_trim:
        raise ValueError("El nombre es requerido")

    engine = get_sa_engine_main()
    try:
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT id FROM marca WHERE id = :marca_id"),
                {"marca_id": marca_id},
            ).first()
            if not exists:
                raise ValueError("Marca no encontrada")

            duplicated = conn.execute(
                text("SELECT id FROM marca WHERE LOWER(nombre) = LOWER(:nombre) AND id != :marca_id"),
                {"nombre": nombre_trim, "marca_id": marca_id},
            ).first()
            if duplicated:
                raise ValueError("Ya existe otra marca con ese nombre")

            conn.execute(
                text("UPDATE marca SET nombre = :nombre, updatedAt = GETDATE() WHERE id = :marca_id"),
                {"nombre": nombre_trim, "marca_id": marca_id},
            )

        logger.info("Marca actualizada id=%s", marca_id)
        return True
    except Exception as e:
        logger.error("Error actualizando marca %s: %s", marca_id, e)
        raise


def toggle_marca_estado(marca_id: int) -> bool:
    """Activa/desactiva una marca (soft delete)"""
    engine = get_sa_engine_main()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT estado FROM marca WHERE id = :marca_id"),
                {"marca_id": marca_id},
            ).first()
            if not row:
                raise ValueError("Marca no encontrada")

            nuevo_estado = 1 - row[0]
            conn.execute(
                text("UPDATE marca SET estado = :estado, updatedAt = GETDATE() WHERE id = :marca_id"),
                {"estado": nuevo_estado, "marca_id": marca_id},
            )

        logger.info("Marca %s activada/desactivada id=%s", nuevo_estado, marca_id)
        return True
    except Exception as e:
        logger.error("Error toggling marca %s: %s", marca_id, e)
        raise


# ---------------------------------------------------------------------------
# PRODUCTO
# ---------------------------------------------------------------------------

def get_productos(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Obtiene todos los productos con info de marca"""
    if include_inactive:
        return _fetch_all(
            """
            SELECT p.id, p.nombre, p.descripcion, p.upc1, p.upc2,
                   p.marcaId, m.nombre AS marcaNombre, p.precio, p.estado,
                   p.createdAt, p.updatedAt
            FROM producto p
            LEFT JOIN marca m ON p.marcaId = m.id
            ORDER BY p.nombre ASC
            """
        )
    return _fetch_all(
        """
        SELECT p.id, p.nombre, p.descripcion, p.upc1, p.upc2,
               p.marcaId, m.nombre AS marcaNombre, p.precio, p.estado,
               p.createdAt, p.updatedAt
        FROM producto p
        LEFT JOIN marca m ON p.marcaId = m.id
        WHERE p.estado = 1
        ORDER BY p.nombre ASC
        """
    )


def get_producto_by_id(producto_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un producto por ID"""
    return _fetch_one("""
        SELECT p.id, p.nombre, p.descripcion, p.upc1, p.upc2,
               p.marcaId, m.nombre AS marcaNombre, p.precio, p.estado,
               p.createdAt, p.updatedAt
        FROM producto p
        LEFT JOIN marca m ON p.marcaId = m.id
        WHERE p.id = :producto_id
    """, {"producto_id": producto_id})


def create_producto(nombre: str, descripcion: str = None, upc1: str = None,
                   upc2: str = None, marca_id: int = None, precio: float = 0.0) -> int:
    """Crea un nuevo producto"""
    nombre_trim = nombre.strip()
    if not nombre_trim:
        raise ValueError("El nombre es requerido")

    engine = get_sa_engine_main()
    try:
        with engine.begin() as conn:
            if upc1:
                duplicated = conn.execute(
                    text("SELECT id FROM producto WHERE upc1 = :upc OR upc2 = :upc"),
                    {"upc": upc1},
                ).first()
                if duplicated:
                    raise ValueError(f"UPC1 '{upc1}' ya existe")

            if upc2:
                duplicated = conn.execute(
                    text("SELECT id FROM producto WHERE upc1 = :upc OR upc2 = :upc"),
                    {"upc": upc2},
                ).first()
                if duplicated:
                    raise ValueError(f"UPC2 '{upc2}' ya existe")

            producto_id = conn.execute(
                text(
                    """
                    INSERT INTO producto (nombre, descripcion, upc1, upc2, marcaId, precio, estado)
                    OUTPUT INSERTED.id
                    VALUES (:nombre, :descripcion, :upc1, :upc2, :marca_id, :precio, 1)
                    """
                ),
                {
                    "nombre": nombre_trim,
                    "descripcion": descripcion,
                    "upc1": upc1 or None,
                    "upc2": upc2 or None,
                    "marca_id": marca_id,
                    "precio": precio,
                },
            ).scalar_one()

        logger.info("Producto creado id=%s nombre=%s", producto_id, nombre_trim)
        return int(producto_id)
    except Exception as e:
        logger.error("Error creando producto: %s", e)
        raise


def update_producto(producto_id: int, nombre: str = None, descripcion: str = None,
                   upc1: str = None, upc2: str = None, marca_id: int = None,
                   precio: float = None) -> bool:
    """Actualiza un producto"""
    engine = get_sa_engine_main()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT id, upc1, upc2 FROM producto WHERE id = :producto_id"),
                {"producto_id": producto_id},
            ).first()
            if not row:
                raise ValueError("Producto no encontrado")

            old_upc1, old_upc2 = row[1], row[2]

            if upc1 and upc1 != old_upc1:
                duplicated = conn.execute(
                    text("SELECT id FROM producto WHERE (upc1 = :upc OR upc2 = :upc) AND id != :producto_id"),
                    {"upc": upc1, "producto_id": producto_id},
                ).first()
                if duplicated:
                    raise ValueError(f"UPC1 '{upc1}' ya existe")

            if upc2 and upc2 != old_upc2:
                duplicated = conn.execute(
                    text("SELECT id FROM producto WHERE (upc1 = :upc OR upc2 = :upc) AND id != :producto_id"),
                    {"upc": upc2, "producto_id": producto_id},
                ).first()
                if duplicated:
                    raise ValueError(f"UPC2 '{upc2}' ya existe")

            updates = []
            params: Dict[str, Any] = {"producto_id": producto_id}

            if nombre:
                updates.append("nombre = :nombre")
                params["nombre"] = nombre.strip()
            if descripcion is not None:
                updates.append("descripcion = :descripcion")
                params["descripcion"] = descripcion
            if upc1 is not None:
                updates.append("upc1 = :upc1")
                params["upc1"] = upc1 or None
            if upc2 is not None:
                updates.append("upc2 = :upc2")
                params["upc2"] = upc2 or None
            if marca_id is not None:
                updates.append("marcaId = :marca_id")
                params["marca_id"] = marca_id or None
            if precio is not None:
                updates.append("precio = :precio")
                params["precio"] = precio

            if not updates:
                return True

            set_clause = ', '.join(updates + ["updatedAt = GETDATE()"])
            query = f"UPDATE producto SET {set_clause} WHERE id = :producto_id"
            conn.execute(text(query), params)

        logger.info("Producto actualizado id=%s", producto_id)
        return True
    except Exception as e:
        logger.error("Error actualizando producto %s: %s", producto_id, e)
        raise


def toggle_producto_estado(producto_id: int) -> bool:
    """Activa/desactiva un producto (soft delete)"""
    engine = get_sa_engine_main()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT estado FROM producto WHERE id = :producto_id"),
                {"producto_id": producto_id},
            ).first()
            if not row:
                raise ValueError("Producto no encontrado")

            nuevo_estado = 1 - row[0]
            conn.execute(
                text("UPDATE producto SET estado = :estado, updatedAt = GETDATE() WHERE id = :producto_id"),
                {"estado": nuevo_estado, "producto_id": producto_id},
            )

        logger.info("Producto estado toggled id=%s nuevo_estado=%s", producto_id, nuevo_estado)
        return True
    except Exception as e:
        logger.error("Error toggling producto %s: %s", producto_id, e)
        raise


# ---------------------------------------------------------------------------
# MOVIMIENTO
# ---------------------------------------------------------------------------

def get_movimientos(tipo: str = None, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Obtiene movimientos (entrada/salida/ajuste)"""
    if include_inactive and tipo:
        return _fetch_all(
            """
            SELECT m.id, m.productoId, p.nombre AS producto, m.tipo, m.cantidad,
                   m.referencia, m.observacion, m.estado, m.createdAt, m.updatedAt
            FROM movimiento m
            JOIN producto p ON m.productoId = p.id
            WHERE m.tipo = :tipo
            ORDER BY m.createdAt DESC
            """,
            {"tipo": tipo},
        )
    if include_inactive:
        return _fetch_all(
            """
            SELECT m.id, m.productoId, p.nombre AS producto, m.tipo, m.cantidad,
                   m.referencia, m.observacion, m.estado, m.createdAt, m.updatedAt
            FROM movimiento m
            JOIN producto p ON m.productoId = p.id
            ORDER BY m.createdAt DESC
            """
        )
    if tipo:
        return _fetch_all(
            """
            SELECT m.id, m.productoId, p.nombre AS producto, m.tipo, m.cantidad,
                   m.referencia, m.observacion, m.estado, m.createdAt, m.updatedAt
            FROM movimiento m
            JOIN producto p ON m.productoId = p.id
            WHERE m.estado = 1 AND m.tipo = :tipo
            ORDER BY m.createdAt DESC
            """,
            {"tipo": tipo},
        )
    return _fetch_all(
        """
        SELECT m.id, m.productoId, p.nombre AS producto, m.tipo, m.cantidad,
               m.referencia, m.observacion, m.estado, m.createdAt, m.updatedAt
        FROM movimiento m
        JOIN producto p ON m.productoId = p.id
        WHERE m.estado = 1
        ORDER BY m.createdAt DESC
        """
    )


def get_stock() -> List[Dict[str, Any]]:
    """Obtiene stock actual por producto (de la vista materializada)"""
    return _fetch_all("SELECT * FROM v_stock_actual ORDER BY nombre ASC")


def create_movimiento(producto_id: int, tipo: str, cantidad: int,
                     referencia: str = None, observacion: str = None) -> int:
    """Crea un movimiento de stock"""
    if tipo not in ('entrada', 'salida', 'ajuste'):
        raise ValueError("Tipo debe ser 'entrada', 'salida' o 'ajuste'")

    if cantidad == 0:
        raise ValueError("Cantidad no puede ser 0")

    engine = get_sa_engine_main()
    try:
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT id FROM producto WHERE id = :producto_id AND estado = 1"),
                {"producto_id": producto_id},
            ).first()
            if not exists:
                raise ValueError("Producto no encontrado")

            mov_id = conn.execute(
                text(
                    """
                    INSERT INTO movimiento (productoId, tipo, cantidad, referencia, observacion, estado)
                    OUTPUT INSERTED.id
                    VALUES (:producto_id, :tipo, :cantidad, :referencia, :observacion, 1)
                    """
                ),
                {
                    "producto_id": producto_id,
                    "tipo": tipo,
                    "cantidad": cantidad,
                    "referencia": referencia,
                    "observacion": observacion,
                },
            ).scalar_one()

        logger.info("Movimiento creado id=%s producto=%s tipo=%s cantidad=%s",
                   mov_id, producto_id, tipo, cantidad)
        return int(mov_id)
    except Exception as e:
        logger.error("Error creando movimiento: %s", e)
        raise


def soft_delete_movimiento(movimiento_id: int) -> bool:
    """Elimina lógicamente un movimiento"""
    engine = get_sa_engine_main()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE movimiento SET estado = 0, updatedAt = GETDATE() WHERE id = :movimiento_id"),
                {"movimiento_id": movimiento_id},
            )
        logger.info("Movimiento eliminado (soft) id=%s", movimiento_id)
        return True
    except Exception as e:
        logger.error("Error eliminando movimiento %s: %s", movimiento_id, e)
        raise
