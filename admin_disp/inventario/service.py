# admin_disp/inventario/service.py
"""
Servicio de Inventario - Lógica de negocio para marcas, productos y movimientos
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from ..core.db import get_db_main

logger = logging.getLogger("admin_disp.inventario")


# ---------------------------------------------------------------------------
# MARCA
# ---------------------------------------------------------------------------

def get_marcas(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Obtiene todas las marcas (activas por defecto)"""
    conn = get_db_main()
    cur = conn.cursor()
    
    where = "" if include_inactive else "WHERE estado = 1"
    query = (
        """
        SELECT id, nombre, estado, createdAt, updatedAt
        FROM marca
        """
        + where
        + """
        ORDER BY nombre ASC
        """
    )
    cur.execute(query)
    
    rows = cur.fetchall()
    return [dict(zip([col[0] for col in cur.description], row)) for row in rows]


def get_marcas_activas() -> List[Dict[str, Any]]:
    """Obtiene solo marcas activas (para selects)"""
    return get_marcas(include_inactive=False)


def create_marca(nombre: str) -> int:
    """Crea una nueva marca"""
    conn = get_db_main()
    cur = conn.cursor()
    
    nombre_trim = nombre.strip()
    if not nombre_trim:
        raise ValueError("El nombre es requerido")
    
    try:
        # Verificar duplicado (case-insensitive)
        cur.execute("SELECT id FROM marca WHERE LOWER(nombre) = LOWER(?)", (nombre_trim,))
        if cur.fetchone():
            raise ValueError("Ya existe una marca con ese nombre")
        
        # Insertar
        cur.execute(
            "INSERT INTO marca (nombre, estado) OUTPUT INSERTED.id VALUES (?, 1)",
            (nombre_trim,)
        )
        marca_id = cur.fetchone()[0]
        conn.commit()
        logger.info("Marca creada id=%s nombre=%s", marca_id, nombre_trim)
        return marca_id
    except Exception as e:
        conn.rollback()
        logger.error("Error creando marca: %s", e)
        raise


def update_marca(marca_id: int, nombre: str) -> bool:
    """Actualiza una marca"""
    conn = get_db_main()
    cur = conn.cursor()
    
    nombre_trim = nombre.strip()
    if not nombre_trim:
        raise ValueError("El nombre es requerido")
    
    try:
        # Verificar que existe
        cur.execute("SELECT id FROM marca WHERE id = ?", (marca_id,))
        if not cur.fetchone():
            raise ValueError("Marca no encontrada")
        
        # Verificar duplicado en otra marca
        cur.execute(
            "SELECT id FROM marca WHERE LOWER(nombre) = LOWER(?) AND id != ?",
            (nombre_trim, marca_id)
        )
        if cur.fetchone():
            raise ValueError("Ya existe otra marca con ese nombre")
        
        # Actualizar
        cur.execute(
            "UPDATE marca SET nombre = ?, updatedAt = GETDATE() WHERE id = ?",
            (nombre_trim, marca_id)
        )
        conn.commit()
        logger.info("Marca actualizada id=%s", marca_id)
        return True
    except Exception as e:
        conn.rollback()
        logger.error("Error actualizando marca %s: %s", marca_id, e)
        raise


def toggle_marca_estado(marca_id: int) -> bool:
    """Activa/desactiva una marca (soft delete)"""
    conn = get_db_main()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT estado FROM marca WHERE id = ?", (marca_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Marca no encontrada")
        
        nuevo_estado = 1 - row[0]  # Toggle 0<->1
        cur.execute(
            "UPDATE marca SET estado = ?, updatedAt = GETDATE() WHERE id = ?",
            (nuevo_estado, marca_id)
        )
        conn.commit()
        logger.info("Marca %s activada/desactivada id=%s", nuevo_estado, marca_id)
        return True
    except Exception as e:
        conn.rollback()
        logger.error("Error toggling marca %s: %s", marca_id, e)
        raise


# ---------------------------------------------------------------------------
# PRODUCTO
# ---------------------------------------------------------------------------

def get_productos(include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Obtiene todos los productos con info de marca"""
    conn = get_db_main()
    cur = conn.cursor()
    
    where = "" if include_inactive else "WHERE p.estado = 1"
    query = (
        """
        SELECT p.id, p.nombre, p.descripcion, p.upc1, p.upc2,
               p.marcaId, m.nombre AS marcaNombre, p.precio, p.estado,
               p.createdAt, p.updatedAt
        FROM producto p
        LEFT JOIN marca m ON p.marcaId = m.id
        """
        + where
        + """
        ORDER BY p.nombre ASC
        """
    )
    cur.execute(query)
    
    rows = cur.fetchall()
    return [dict(zip([col[0] for col in cur.description], row)) for row in rows]


def get_producto_by_id(producto_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene un producto por ID"""
    conn = get_db_main()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT p.id, p.nombre, p.descripcion, p.upc1, p.upc2,
               p.marcaId, m.nombre AS marcaNombre, p.precio, p.estado,
               p.createdAt, p.updatedAt
        FROM producto p
        LEFT JOIN marca m ON p.marcaId = m.id
        WHERE p.id = ?
    """, (producto_id,))
    
    row = cur.fetchone()
    if not row:
        return None
    
    return dict(zip([col[0] for col in cur.description], row))


def create_producto(nombre: str, descripcion: str = None, upc1: str = None,
                   upc2: str = None, marca_id: int = None, precio: float = 0.0) -> int:
    """Crea un nuevo producto"""
    conn = get_db_main()
    cur = conn.cursor()
    
    nombre_trim = nombre.strip()
    if not nombre_trim:
        raise ValueError("El nombre es requerido")
    
    try:
        # Verificar unicidad de UPCs
        if upc1:
            cur.execute("SELECT id FROM producto WHERE upc1 = ? OR upc2 = ?", (upc1, upc1))
            if cur.fetchone():
                raise ValueError(f"UPC1 '{upc1}' ya existe")
        
        if upc2:
            cur.execute("SELECT id FROM producto WHERE upc1 = ? OR upc2 = ?", (upc2, upc2))
            if cur.fetchone():
                raise ValueError(f"UPC2 '{upc2}' ya existe")
        
        # Insertar
        cur.execute("""
            INSERT INTO producto (nombre, descripcion, upc1, upc2, marcaId, precio, estado)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (nombre_trim, descripcion, upc1 or None, upc2 or None, marca_id, precio))
        
        producto_id = cur.fetchone()[0]
        conn.commit()
        logger.info("Producto creado id=%s nombre=%s", producto_id, nombre_trim)
        return producto_id
    except Exception as e:
        conn.rollback()
        logger.error("Error creando producto: %s", e)
        raise


def update_producto(producto_id: int, nombre: str = None, descripcion: str = None,
                   upc1: str = None, upc2: str = None, marca_id: int = None,
                   precio: float = None) -> bool:
    """Actualiza un producto"""
    conn = get_db_main()
    cur = conn.cursor()
    
    try:
        # Verificar que existe
        cur.execute("SELECT id, upc1, upc2 FROM producto WHERE id = ?", (producto_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Producto no encontrado")
        
        old_upc1, old_upc2 = row[1], row[2]
        
        # Validar UPC1
        if upc1 and upc1 != old_upc1:
            cur.execute("SELECT id FROM producto WHERE (upc1 = ? OR upc2 = ?) AND id != ?",
                       (upc1, upc1, producto_id))
            if cur.fetchone():
                raise ValueError(f"UPC1 '{upc1}' ya existe")
        
        # Validar UPC2
        if upc2 and upc2 != old_upc2:
            cur.execute("SELECT id FROM producto WHERE (upc1 = ? OR upc2 = ?) AND id != ?",
                       (upc2, upc2, producto_id))
            if cur.fetchone():
                raise ValueError(f"UPC2 '{upc2}' ya existe")
        
        # Construir UPDATE dinámico
        updates = []
        params = []
        if nombre:
            updates.append("nombre = ?")
            params.append(nombre.strip())
        if descripcion is not None:
            updates.append("descripcion = ?")
            params.append(descripcion)
        if upc1 is not None:
            updates.append("upc1 = ?")
            params.append(upc1 or None)
        if upc2 is not None:
            updates.append("upc2 = ?")
            params.append(upc2 or None)
        if marca_id is not None:
            updates.append("marcaId = ?")
            params.append(marca_id or None)
        if precio is not None:
            updates.append("precio = ?")
            params.append(precio)
        
        if not updates:
            return True
        
        updates.append("updatedAt = GETDATE()")
        params.append(producto_id)
        
        set_clause = ', '.join(updates)
        query = "UPDATE producto SET " + set_clause + " WHERE id = ?"
        cur.execute(query, params)
        conn.commit()
        logger.info("Producto actualizado id=%s", producto_id)
        return True
    except Exception as e:
        conn.rollback()
        logger.error("Error actualizando producto %s: %s", producto_id, e)
        raise


def toggle_producto_estado(producto_id: int) -> bool:
    """Activa/desactiva un producto (soft delete)"""
    conn = get_db_main()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT estado FROM producto WHERE id = ?", (producto_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("Producto no encontrado")
        
        nuevo_estado = 1 - row[0]
        cur.execute(
            "UPDATE producto SET estado = ?, updatedAt = GETDATE() WHERE id = ?",
            (nuevo_estado, producto_id)
        )
        conn.commit()
        logger.info("Producto estado toggled id=%s nuevo_estado=%s", producto_id, nuevo_estado)
        return True
    except Exception as e:
        conn.rollback()
        logger.error("Error toggling producto %s: %s", producto_id, e)
        raise


# ---------------------------------------------------------------------------
# MOVIMIENTO
# ---------------------------------------------------------------------------

def get_movimientos(tipo: str = None, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """Obtiene movimientos (entrada/salida/ajuste)"""
    conn = get_db_main()
    cur = conn.cursor()
    
    where_parts = ["WHERE m.estado = 1"] if not include_inactive else ["WHERE 1=1"]
    params = []
    
    if tipo:
        where_parts.append("AND m.tipo = ?")
        params.append(tipo)
    
    where_clause = " ".join(where_parts) if where_parts[0] != "WHERE 1=1" else where_parts[0]
    query = (
        """
        SELECT m.id, m.productoId, p.nombre AS producto, m.tipo, m.cantidad,
               m.referencia, m.observacion, m.estado, m.createdAt, m.updatedAt
        FROM movimiento m
        JOIN producto p ON m.productoId = p.id
        """
        + where_clause
        + """
        ORDER BY m.createdAt DESC
        """
    )
    cur.execute(query, params)
    
    rows = cur.fetchall()
    return [dict(zip([col[0] for col in cur.description], row)) for row in rows]


def get_stock() -> List[Dict[str, Any]]:
    """Obtiene stock actual por producto (de la vista materializada)"""
    conn = get_db_main()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM v_stock_actual ORDER BY nombre ASC")
    
    rows = cur.fetchall()
    return [dict(zip([col[0] for col in cur.description], row)) for row in rows]


def create_movimiento(producto_id: int, tipo: str, cantidad: int,
                     referencia: str = None, observacion: str = None) -> int:
    """Crea un movimiento de stock"""
    conn = get_db_main()
    cur = conn.cursor()
    
    if tipo not in ('entrada', 'salida', 'ajuste'):
        raise ValueError("Tipo debe ser 'entrada', 'salida' o 'ajuste'")
    
    if cantidad == 0:
        raise ValueError("Cantidad no puede ser 0")
    
    try:
        # Verificar que el producto existe
        cur.execute("SELECT id FROM producto WHERE id = ? AND estado = 1", (producto_id,))
        if not cur.fetchone():
            raise ValueError("Producto no encontrado")
        
        # Insertar movimiento
        cur.execute("""
            INSERT INTO movimiento (productoId, tipo, cantidad, referencia, observacion, estado)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, 1)
        """, (producto_id, tipo, cantidad, referencia, observacion))
        
        mov_id = cur.fetchone()[0]
        conn.commit()
        logger.info("Movimiento creado id=%s producto=%s tipo=%s cantidad=%s",
                   mov_id, producto_id, tipo, cantidad)
        return mov_id
    except Exception as e:
        conn.rollback()
        logger.error("Error creando movimiento: %s", e)
        raise


def soft_delete_movimiento(movimiento_id: int) -> bool:
    """Elimina lógicamente un movimiento"""
    conn = get_db_main()
    cur = conn.cursor()
    
    try:
        cur.execute(
            "UPDATE movimiento SET estado = 0, updatedAt = GETDATE() WHERE id = ?",
            (movimiento_id,)
        )
        conn.commit()
        logger.info("Movimiento eliminado (soft) id=%s", movimiento_id)
        return True
    except Exception as e:
        conn.rollback()
        logger.error("Error eliminando movimiento %s: %s", movimiento_id, e)
        raise
