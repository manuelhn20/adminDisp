# admin_disp/kardex/db.py
"""
Operaciones de base de datos para el módulo KARDEX.
Usa la conexión 'kardex' registrada en core/db.py.
"""

from __future__ import annotations
import logging
import uuid
from typing import Any, Dict, List, Optional
from ..core.db import get_db_kardex

logger = logging.getLogger("admin_disp.kardex")
# Session update: 2026-03-24 14:39:20 - Rebuild schema support and extraction compatibility.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(cursor, row) -> Dict[str, Any]:
    """Convierte una fila pyodbc a dict usando los nombres de columna del cursor."""
    cols = [col[0] for col in cursor.description]
    return dict(zip(cols, row))


def _rows_to_list(cursor, rows) -> List[Dict[str, Any]]:
    return [_row_to_dict(cursor, r) for r in rows]


# ---------------------------------------------------------------------------
# PERIODO
# ---------------------------------------------------------------------------

def get_periodos() -> List[Dict[str, Any]]:
    conn = get_db_kardex()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nombre, mes, ano, fechaInicio, fechaFin, status, createdAt
        FROM periodo
        ORDER BY ano DESC, mes DESC
    """)
    return _rows_to_list(cur, cur.fetchall())


def get_periodo_activo() -> Optional[Dict[str, Any]]:
    conn = get_db_kardex()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nombre, mes, ano, fechaInicio, fechaFin, status, createdAt
        FROM periodo
        WHERE status = 1
    """)
    row = cur.fetchone()
    return _row_to_dict(cur, row) if row else None


def create_periodo(nombre: str, mes: int, ano: int,
                   fecha_inicio: str, fecha_fin: str) -> Dict[str, Any]:
    """
    Crea un período. Si se marca como activo, desactiva el anterior.
    El nuevo período siempre se crea como Inactivo; se activa con activate_periodo().
    """
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        # Evitar duplicados por nombre o por combinación mes/año.
        cur.execute("""
            SELECT TOP 1 id
            FROM periodo
            WHERE nombre = ? OR (mes = ? AND ano = ?)
        """, (nombre, mes, ano))
        if cur.fetchone():
            raise ValueError("Ya existe un período con ese nombre o para ese mes/año.")

        cur.execute("""
            INSERT INTO periodo (nombre, mes, ano, fechaInicio, fechaFin, status)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, 0)
        """, (nombre, mes, ano, fecha_inicio, fecha_fin))
        new_id = cur.fetchone()[0]
        conn.commit()
        logger.info("Período creado id=%s nombre=%s", new_id, nombre)
        return {"id": new_id, "success": True}
    except Exception as e:
        conn.rollback()
        logger.error("Error creando período: %s", e)
        raise


def activate_periodo(periodo_id: int) -> bool:
    """
    Activa un período y desactiva todos los demás.
    El índice único filtrado en BD garantiza solo 1 activo.
    """
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM periodo WHERE id = ?", (periodo_id,))
        if not cur.fetchone():
            return False

        # El activo anterior pasa a 2 (período ya pasado/deshabilitado).
        cur.execute("UPDATE periodo SET status = 2 WHERE status = 1")
        # Luego activar el seleccionado.
        cur.execute("UPDATE periodo SET status = 1 WHERE id = ?", (periodo_id,))
        conn.commit()
        logger.info("Período id=%s activado", periodo_id)
        return True
    except Exception as e:
        conn.rollback()
        logger.error("Error activando período %s: %s", periodo_id, e)
        raise


def update_periodo(periodo_id: int, nombre: str, mes: int, ano: int,
                   fecha_inicio: str, fecha_fin: str) -> bool:
    """Actualiza un período existente."""
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE periodo
            SET nombre = ?, mes = ?, ano = ?, fechaInicio = ?, fechaFin = ?
            WHERE id = ?
        """, (nombre, mes, ano, fecha_inicio, fecha_fin, periodo_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error("Error actualizando período %s: %s", periodo_id, e)
        raise


def set_periodo_estado(periodo_id: int, estado: int) -> bool:
    """Cambia estado del período: 0 (programado), 1 (activo), 2 (pasado/deshabilitado)."""
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        if estado == 1:
            return activate_periodo(periodo_id)

        cur.execute("UPDATE periodo SET status = ? WHERE id = ?", (estado, periodo_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error("Error cambiando estado de período %s: %s", periodo_id, e)
        raise


def delete_periodo(periodo_id: int) -> bool:
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        # Soft delete lógico: marca status = 2 (período pasado/deshabilitado).
        cur.execute("UPDATE periodo SET status = 2 WHERE id = ?", (periodo_id,))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error("Error eliminando período %s: %s", periodo_id, e)
        raise


# ---------------------------------------------------------------------------
# MARCA
# ---------------------------------------------------------------------------

def get_marcas(include_inactive: bool = True) -> List[Dict[str, Any]]:
    conn = get_db_kardex()
    cur = conn.cursor()

    where = "" if include_inactive else " WHERE status = 1"
    query_marcas = (
        "SELECT id, name, description, status, syncDate "
        "FROM marca" + where + " "
        "ORDER BY name"
    )
    cur.execute(query_marcas)

    return _rows_to_list(cur, cur.fetchall())


def update_marca(marca_id: str, name: str, description: str) -> bool:
    """Actualiza nombre y descripción de marca."""
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE marca SET name = ?, description = ?, syncDate = GETDATE() WHERE id = ?",
            (name, description, int(marca_id))
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error("Error actualizando marca %s: %s", marca_id, e)
        raise


def set_marca_estado(marca_id: str, estado: int) -> bool:
    """Soft delete/restore de marca usando status (1/0)."""
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE marca SET status = ?, syncDate = GETDATE() WHERE id = ?", (estado, int(marca_id)))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error("Error cambiando estado de marca %s: %s", marca_id, e)
        raise


def upsert_marcas(marcas: List[Dict[str, Any]]) -> Dict[str, int]:
    """INSERT o UPDATE de marcas desde el Excel de SharePoint."""
    conn = get_db_kardex()
    cur = conn.cursor()
    inserted = updated = 0
    try:
        for m in marcas:
            name = (m.get("name") or "").strip()
            description = (m.get("description") or "").strip()
            if not name:
                continue
            cur.execute("SELECT id FROM marca WHERE name = ?", (name,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE marca SET description = ?, status = 1, syncDate = GETDATE() WHERE id = ?",
                    (description or name, int(row[0]))
                )
                updated += 1
            else:
                cur.execute(
                    "INSERT INTO marca (name, description, status, syncDate) VALUES (?, ?, 1, GETDATE())",
                    (name, description or name)
                )
                inserted += 1
        conn.commit()
        logger.info("Marcas sync: inserted=%s updated=%s", inserted, updated)
        return {"inserted": inserted, "updated": updated}
    except Exception as e:
        conn.rollback()
        logger.error("Error en upsert_marcas: %s", e)
        raise


# ---------------------------------------------------------------------------
# PRODUCTO
# ---------------------------------------------------------------------------

def get_productos(solo_disponibles: bool = False) -> List[Dict[str, Any]]:
    conn = get_db_kardex()
    cur = conn.cursor()
    where = " WHERE p.status = 1" if solo_disponibles else ""
    query_productos = (
        "SELECT p.id, p.itemName, p.brand, COALESCE(m.name, p.brand) AS brandNombre, "
        "p.categoria, p.um, p.status, p.syncDate "
        "FROM producto p "
        "LEFT JOIN marca m ON p.brand = m.name" + where + " "
        "ORDER BY p.itemName"
    )
    cur.execute(query_productos)
    return _rows_to_list(cur, cur.fetchall())


def upsert_productos(productos: List[Dict[str, Any]]) -> Dict[str, int]:
    """INSERT o UPDATE de productos desde el Excel de SharePoint."""
    conn = get_db_kardex()
    cur = conn.cursor()
    inserted = updated = 0
    try:
        for p in productos:
            pid = p.get("id")
            item_name = p.get("itemName")
            if not pid or not item_name:
                continue
            cur.execute("SELECT id FROM producto WHERE id = ?", (pid,))
            if cur.fetchone():
                cur.execute("""
                    UPDATE producto
                    SET itemName = ?, brand = ?, categoria = ?, um = ?, status = ?, syncDate = GETDATE()
                    WHERE id = ?
                """, (item_name, p.get("brand"), p.get("categoria"),
                      p.get("um"), p.get("status", 1), pid))
                updated += 1
            else:
                cur.execute("""
                    INSERT INTO producto (id, itemName, brand, categoria, um, status, syncDate)
                    VALUES (?, ?, ?, ?, ?, ?, GETDATE())
                """, (pid, item_name, p.get("brand"), p.get("categoria"),
                      p.get("um"), p.get("status", 1)))
                inserted += 1
        conn.commit()
        logger.info("Productos sync: inserted=%s updated=%s", inserted, updated)
        return {"inserted": inserted, "updated": updated}
    except Exception as e:
        conn.rollback()
        logger.error("Error en upsert_productos: %s", e)
        raise


# ---------------------------------------------------------------------------
# ALMACEN
# ---------------------------------------------------------------------------

def get_almacenes(solo_activos: bool = True) -> List[Dict[str, Any]]:
    """
    Por defecto retorna solo almacenes activos (status = 1).
    """
    conn = get_db_kardex()
    cur = conn.cursor()
    where = " WHERE status = 1" if solo_activos else ""
    query_almacenes = (
        "SELECT id, idName, company, status, description, type, syncDate "
        "FROM almacen" + where + " "
        "ORDER BY idName"
    )
    cur.execute(query_almacenes)
    return _rows_to_list(cur, cur.fetchall())


def upsert_almacenes(almacenes: List[Dict[str, Any]]) -> Dict[str, int]:
    """INSERT o UPDATE de almacenes desde el Excel de SharePoint."""
    conn = get_db_kardex()
    cur = conn.cursor()
    inserted = updated = 0
    try:
        for a in almacenes:
            id_name = (a.get("idName") or "").strip()
            if not id_name:
                continue
            cur.execute("SELECT id FROM almacen WHERE idName = ?", (id_name,))
            row = cur.fetchone()
            if row:
                cur.execute("""
                    UPDATE almacen
                    SET company = ?, status = ?, description = ?, type = ?, syncDate = GETDATE()
                    WHERE id = ?
                """, (
                    a.get("company"),
                    a.get("status", 1),
                    a.get("description", ""),
                    a.get("type", "General"),
                    int(row[0]),
                ))
                updated += 1
            else:
                cur.execute("""
                    INSERT INTO almacen (idName, company, status, description, type, syncDate)
                    VALUES (?, ?, ?, ?, ?, GETDATE())
                """, (
                    id_name,
                    a.get("company"),
                    a.get("status", 1),
                    a.get("description", ""),
                    a.get("type", "General"),
                ))
                inserted += 1
        conn.commit()
        logger.info("Almacenes sync: inserted=%s updated=%s", inserted, updated)
        return {"inserted": inserted, "updated": updated}
    except Exception as e:
        conn.rollback()
        logger.error("Error en upsert_almacenes: %s", e)
        raise


def update_almacen(almacen_id: str, descripcion: str,
                   id_name: Optional[str] = None,
                   company: Optional[str] = None,
                   tipo_almacen: Optional[str] = None) -> bool:
    """Actualiza datos de un almacén existente."""
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        final_id_name = (id_name or "").strip() or descripcion
        cur.execute("""
            UPDATE almacen
            SET idName = ?, description = ?, company = ?, type = ?, syncDate = GETDATE()
            WHERE id = ?
        """, (final_id_name, descripcion, company, tipo_almacen, int(almacen_id)))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error("Error actualizando almacén %s: %s", almacen_id, e)
        raise


def set_almacen_status(almacen_id: str, status: int) -> bool:
    """Soft delete/restore de almacén usando status (1 activo, 0 inactivo)."""
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE almacen SET status = ?, syncDate = GETDATE() WHERE id = ?", (status, int(almacen_id)))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error("Error cambiando estado de almacén %s: %s", almacen_id, e)
        raise


# ---------------------------------------------------------------------------
# CREAR MARCAS, PRODUCTOS, ALMACENES (Usuario manual)
# ---------------------------------------------------------------------------

def create_marca(name: str, description: str = "") -> Dict[str, Any]:
    """Crea una nueva marca."""
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO marca (name, description, status, syncDate)
            OUTPUT INSERTED.id, INSERTED.name, INSERTED.description, INSERTED.status, INSERTED.syncDate
            VALUES (?, ?, 1, GETDATE())
        """, (name, description or name))
        row = cur.fetchone()
        conn.commit()
        result = _row_to_dict(cur, row)
        logger.info("Marca creada: id=%s name=%s", result['id'], name)
        return result
    except Exception as e:
        conn.rollback()
        logger.error("Error creando marca: %s", e)
        raise


def create_producto(item_name: str, brand: Optional[str] = None, 
                   categoria: Optional[str] = None, um: Optional[str] = None,
                   product_id: Optional[str] = None) -> Dict[str, Any]:
    """Crea un nuevo producto."""
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        pid = product_id or f"MAN-{uuid.uuid4().hex[:12].upper()}"
        cur.execute("""
            INSERT INTO producto (id, itemName, brand, categoria, um, status, syncDate)
            OUTPUT INSERTED.id, INSERTED.itemName, INSERTED.brand, INSERTED.categoria, INSERTED.um, INSERTED.status
            VALUES (?, ?, ?, ?, ?, 1, GETDATE())
        """, (pid, item_name, brand, categoria, um))
        row = cur.fetchone()
        conn.commit()
        result = _row_to_dict(cur, row)
        logger.info("Producto creado: id=%s itemName=%s", result['id'], item_name)
        return result
    except Exception as e:
        conn.rollback()
        logger.error("Error creando producto: %s", e)
        raise


def set_producto_estado(producto_id: str, estado: int) -> bool:
    """Soft delete/restore de producto usando status (1 activo, 0 inactivo)."""
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE producto SET status = ?, syncDate = GETDATE() WHERE id = ?", (estado, producto_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        logger.error("Error cambiando estado de producto %s: %s", producto_id, e)
        raise


def create_almacen(descripcion: str, company: Optional[str] = None,
                  tipo_almacen: Optional[str] = None,
                  id_name: Optional[str] = None) -> Dict[str, Any]:
    """Crea un nuevo almacén."""
    conn = get_db_kardex()
    cur = conn.cursor()
    try:
        final_id_name = (id_name or "").strip() or descripcion
        cur.execute("""
            INSERT INTO almacen (idName, company, status, description, type, syncDate)
            OUTPUT INSERTED.id, INSERTED.idName, INSERTED.company, INSERTED.status, INSERTED.description, INSERTED.type
            VALUES (?, ?, 1, ?, ?, GETDATE())
        """, (final_id_name, company, descripcion, tipo_almacen))
        row = cur.fetchone()
        conn.commit()
        result = _row_to_dict(cur, row)
        logger.info("Almacén creado: id=%s idName=%s", result['id'], final_id_name)
        return result
    except Exception as e:
        conn.rollback()
        logger.error("Error creando almacén: %s", e)
        raise
