"""
Operaciones de base de datos para el modulo KARDEX.
Usa SQLAlchemy Core sobre la conexion 'kardex' registrada en core/db.py.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..core.db import get_sa_engine_kardex

logger = logging.getLogger("admin_disp.kardex")
# Session update: 2026-03-24 14:39:20 - Rebuild schema support and extraction compatibility.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_all(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    engine = get_sa_engine_kardex()
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row) for row in result.mappings().all()]


def _fetch_one(query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    engine = get_sa_engine_kardex()
    with engine.connect() as conn:
        row = conn.execute(text(query), params or {}).mappings().first()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# PERIODO
# ---------------------------------------------------------------------------

def get_periodos() -> List[Dict[str, Any]]:
    return _fetch_all(
        """
        SELECT id, nombre, mes, ano, fechaInicio, fechaFin, status, createdAt
        FROM periodo
        ORDER BY ano DESC, mes DESC
        """
    )


def get_periodo_activo() -> Optional[Dict[str, Any]]:
    return _fetch_one(
        """
        SELECT id, nombre, mes, ano, fechaInicio, fechaFin, status, createdAt
        FROM periodo
        WHERE status = 1
        """
    )


def create_periodo(
    nombre: str,
    mes: int,
    ano: int,
    fecha_inicio: str,
    fecha_fin: str,
) -> Dict[str, Any]:
    """
    Crea un periodo. Si se marca como activo, desactiva el anterior.
    El nuevo periodo siempre se crea como Inactivo; se activa con activate_periodo().
    """
    engine = get_sa_engine_kardex()
    try:
        with engine.begin() as conn:
            exists = conn.execute(
                text(
                    """
                    SELECT TOP 1 id
                    FROM periodo
                    WHERE nombre = :nombre OR (mes = :mes AND ano = :ano)
                    """
                ),
                {"nombre": nombre, "mes": mes, "ano": ano},
            ).first()
            if exists:
                raise ValueError("Ya existe un periodo con ese nombre o para ese mes/ano.")

            new_id = conn.execute(
                text(
                    """
                    INSERT INTO periodo (nombre, mes, ano, fechaInicio, fechaFin, status)
                    OUTPUT INSERTED.id
                    VALUES (:nombre, :mes, :ano, :fecha_inicio, :fecha_fin, 0)
                    """
                ),
                {
                    "nombre": nombre,
                    "mes": mes,
                    "ano": ano,
                    "fecha_inicio": fecha_inicio,
                    "fecha_fin": fecha_fin,
                },
            ).scalar_one()

        logger.info("Periodo creado id=%s nombre=%s", new_id, nombre)
        return {"id": int(new_id), "success": True}
    except Exception as e:
        logger.error("Error creando periodo: %s", e)
        raise


def activate_periodo(periodo_id: int) -> bool:
    """
    Activa un periodo y desactiva todos los demas.
    El indice unico filtrado en BD garantiza solo 1 activo.
    """
    engine = get_sa_engine_kardex()
    try:
        with engine.begin() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM periodo WHERE id = :periodo_id"),
                {"periodo_id": periodo_id},
            ).first()
            if not exists:
                return False

            # El activo anterior pasa a 2 (periodo ya pasado/deshabilitado).
            conn.execute(text("UPDATE periodo SET status = 2 WHERE status = 1"))
            # Luego activar el seleccionado.
            conn.execute(
                text("UPDATE periodo SET status = 1 WHERE id = :periodo_id"),
                {"periodo_id": periodo_id},
            )

        logger.info("Periodo id=%s activado", periodo_id)
        return True
    except Exception as e:
        logger.error("Error activando periodo %s: %s", periodo_id, e)
        raise


def update_periodo(
    periodo_id: int,
    nombre: str,
    mes: int,
    ano: int,
    fecha_inicio: str,
    fecha_fin: str,
) -> bool:
    """Actualiza un periodo existente."""
    engine = get_sa_engine_kardex()
    try:
        with engine.begin() as conn:
            updated = conn.execute(
                text(
                    """
                    UPDATE periodo
                    SET nombre = :nombre, mes = :mes, ano = :ano, fechaInicio = :fecha_inicio, fechaFin = :fecha_fin
                    OUTPUT INSERTED.id
                    WHERE id = :periodo_id
                    """
                ),
                {
                    "nombre": nombre,
                    "mes": mes,
                    "ano": ano,
                    "fecha_inicio": fecha_inicio,
                    "fecha_fin": fecha_fin,
                    "periodo_id": periodo_id,
                },
            ).first()
        return bool(updated)
    except Exception as e:
        logger.error("Error actualizando periodo %s: %s", periodo_id, e)
        raise


def set_periodo_estado(periodo_id: int, estado: int) -> bool:
    """Cambia estado del periodo: 0 (programado), 1 (activo), 2 (pasado/deshabilitado)."""
    if estado == 1:
        return activate_periodo(periodo_id)

    engine = get_sa_engine_kardex()
    try:
        with engine.begin() as conn:
            updated = conn.execute(
                text(
                    """
                    UPDATE periodo
                    SET status = :estado
                    OUTPUT INSERTED.id
                    WHERE id = :periodo_id
                    """
                ),
                {"estado": estado, "periodo_id": periodo_id},
            ).first()
        return bool(updated)
    except Exception as e:
        logger.error("Error cambiando estado de periodo %s: %s", periodo_id, e)
        raise


def delete_periodo(periodo_id: int) -> bool:
    engine = get_sa_engine_kardex()
    try:
        # Soft delete logico: marca status = 2 (periodo pasado/deshabilitado).
        with engine.begin() as conn:
            updated = conn.execute(
                text(
                    """
                    UPDATE periodo
                    SET status = 2
                    OUTPUT INSERTED.id
                    WHERE id = :periodo_id
                    """
                ),
                {"periodo_id": periodo_id},
            ).first()
        return bool(updated)
    except Exception as e:
        logger.error("Error eliminando periodo %s: %s", periodo_id, e)
        raise


# ---------------------------------------------------------------------------
# MARCA
# ---------------------------------------------------------------------------

def get_marcas(include_inactive: bool = True) -> List[Dict[str, Any]]:
    if include_inactive:
        return _fetch_all(
            """
            SELECT id, name, description, status, syncDate
            FROM marca
            ORDER BY name
            """
        )
    return _fetch_all(
        """
        SELECT id, name, description, status, syncDate
        FROM marca
        WHERE status = 1
        ORDER BY name
        """
    )


def update_marca(marca_id: str, name: str, description: str) -> bool:
    """Actualiza nombre y descripcion de marca."""
    engine = get_sa_engine_kardex()
    try:
        with engine.begin() as conn:
            updated = conn.execute(
                text(
                    """
                    UPDATE marca
                    SET name = :name, description = :description, syncDate = GETDATE()
                    OUTPUT INSERTED.id
                    WHERE id = :marca_id
                    """
                ),
                {"name": name, "description": description, "marca_id": int(marca_id)},
            ).first()
        return bool(updated)
    except Exception as e:
        logger.error("Error actualizando marca %s: %s", marca_id, e)
        raise


def set_marca_estado(marca_id: str, estado: int) -> bool:
    """Soft delete/restore de marca usando status (1/0)."""
    engine = get_sa_engine_kardex()
    try:
        with engine.begin() as conn:
            updated = conn.execute(
                text(
                    """
                    UPDATE marca
                    SET status = :estado, syncDate = GETDATE()
                    OUTPUT INSERTED.id
                    WHERE id = :marca_id
                    """
                ),
                {"estado": estado, "marca_id": int(marca_id)},
            ).first()
        return bool(updated)
    except Exception as e:
        logger.error("Error cambiando estado de marca %s: %s", marca_id, e)
        raise


def upsert_marcas(marcas: List[Dict[str, Any]]) -> Dict[str, int]:
    """INSERT o UPDATE de marcas desde el Excel de SharePoint."""
    engine = get_sa_engine_kardex()
    inserted = 0
    updated = 0
    try:
        with engine.begin() as conn:
            for m in marcas:
                name = (m.get("name") or "").strip()
                description = (m.get("description") or "").strip()
                if not name:
                    continue

                row = conn.execute(
                    text("SELECT id FROM marca WHERE name = :name"),
                    {"name": name},
                ).first()
                if row:
                    conn.execute(
                        text(
                            """
                            UPDATE marca
                            SET description = :description, status = 1, syncDate = GETDATE()
                            WHERE id = :marca_id
                            """
                        ),
                        {"description": description or name, "marca_id": int(row[0])},
                    )
                    updated += 1
                else:
                    conn.execute(
                        text(
                            """
                            INSERT INTO marca (name, description, status, syncDate)
                            VALUES (:name, :description, 1, GETDATE())
                            """
                        ),
                        {"name": name, "description": description or name},
                    )
                    inserted += 1

        logger.info("Marcas sync: inserted=%s updated=%s", inserted, updated)
        return {"inserted": inserted, "updated": updated}
    except Exception as e:
        logger.error("Error en upsert_marcas: %s", e)
        raise


# ---------------------------------------------------------------------------
# PRODUCTO
# ---------------------------------------------------------------------------

def get_productos(solo_disponibles: bool = False) -> List[Dict[str, Any]]:
    if solo_disponibles:
        return _fetch_all(
            """
            SELECT p.id, p.itemName, p.brand, COALESCE(m.name, p.brand) AS brandNombre,
                   p.categoria, p.um, p.status, p.syncDate
            FROM producto p
            LEFT JOIN marca m ON p.brand = m.name
            WHERE p.status = 1
            ORDER BY p.itemName
            """
        )
    return _fetch_all(
        """
        SELECT p.id, p.itemName, p.brand, COALESCE(m.name, p.brand) AS brandNombre,
               p.categoria, p.um, p.status, p.syncDate
        FROM producto p
        LEFT JOIN marca m ON p.brand = m.name
        ORDER BY p.itemName
        """
    )


def upsert_productos(productos: List[Dict[str, Any]]) -> Dict[str, int]:
    """INSERT o UPDATE de productos desde el Excel de SharePoint."""
    engine = get_sa_engine_kardex()
    inserted = 0
    updated = 0
    try:
        with engine.begin() as conn:
            for p in productos:
                pid = p.get("id")
                item_name = p.get("itemName")
                if not pid or not item_name:
                    continue

                exists = conn.execute(
                    text("SELECT id FROM producto WHERE id = :pid"),
                    {"pid": pid},
                ).first()
                if exists:
                    conn.execute(
                        text(
                            """
                            UPDATE producto
                            SET itemName = :item_name,
                                brand = :brand,
                                categoria = :categoria,
                                um = :um,
                                status = :status,
                                syncDate = GETDATE()
                            WHERE id = :pid
                            """
                        ),
                        {
                            "item_name": item_name,
                            "brand": p.get("brand"),
                            "categoria": p.get("categoria"),
                            "um": p.get("um"),
                            "status": p.get("status", 1),
                            "pid": pid,
                        },
                    )
                    updated += 1
                else:
                    conn.execute(
                        text(
                            """
                            INSERT INTO producto (id, itemName, brand, categoria, um, status, syncDate)
                            VALUES (:pid, :item_name, :brand, :categoria, :um, :status, GETDATE())
                            """
                        ),
                        {
                            "pid": pid,
                            "item_name": item_name,
                            "brand": p.get("brand"),
                            "categoria": p.get("categoria"),
                            "um": p.get("um"),
                            "status": p.get("status", 1),
                        },
                    )
                    inserted += 1

        logger.info("Productos sync: inserted=%s updated=%s", inserted, updated)
        return {"inserted": inserted, "updated": updated}
    except Exception as e:
        logger.error("Error en upsert_productos: %s", e)
        raise


# ---------------------------------------------------------------------------
# ALMACEN
# ---------------------------------------------------------------------------

def get_almacenes(solo_activos: bool = True) -> List[Dict[str, Any]]:
    """
    Por defecto retorna solo almacenes activos (status = 1).
    """
    if solo_activos:
        return _fetch_all(
            """
            SELECT id, idName, company, status, description, type, syncDate
            FROM almacen
            WHERE status = 1
            ORDER BY idName
            """
        )
    return _fetch_all(
        """
        SELECT id, idName, company, status, description, type, syncDate
        FROM almacen
        ORDER BY idName
        """
    )


def upsert_almacenes(almacenes: List[Dict[str, Any]]) -> Dict[str, int]:
    """INSERT o UPDATE de almacenes desde el Excel de SharePoint."""
    engine = get_sa_engine_kardex()
    inserted = 0
    updated = 0
    try:
        with engine.begin() as conn:
            for a in almacenes:
                id_name = (a.get("idName") or "").strip()
                if not id_name:
                    continue

                row = conn.execute(
                    text("SELECT id FROM almacen WHERE idName = :id_name"),
                    {"id_name": id_name},
                ).first()
                if row:
                    conn.execute(
                        text(
                            """
                            UPDATE almacen
                            SET company = :company,
                                status = :status,
                                description = :description,
                                type = :type,
                                syncDate = GETDATE()
                            WHERE id = :almacen_id
                            """
                        ),
                        {
                            "company": a.get("company"),
                            "status": a.get("status", 1),
                            "description": a.get("description", ""),
                            "type": a.get("type", "General"),
                            "almacen_id": int(row[0]),
                        },
                    )
                    updated += 1
                else:
                    conn.execute(
                        text(
                            """
                            INSERT INTO almacen (idName, company, status, description, type, syncDate)
                            VALUES (:id_name, :company, :status, :description, :type, GETDATE())
                            """
                        ),
                        {
                            "id_name": id_name,
                            "company": a.get("company"),
                            "status": a.get("status", 1),
                            "description": a.get("description", ""),
                            "type": a.get("type", "General"),
                        },
                    )
                    inserted += 1

        logger.info("Almacenes sync: inserted=%s updated=%s", inserted, updated)
        return {"inserted": inserted, "updated": updated}
    except Exception as e:
        logger.error("Error en upsert_almacenes: %s", e)
        raise


def update_almacen(
    almacen_id: str,
    descripcion: str,
    id_name: Optional[str] = None,
    company: Optional[str] = None,
    tipo_almacen: Optional[str] = None,
) -> bool:
    """Actualiza datos de un almacen existente."""
    engine = get_sa_engine_kardex()
    try:
        final_id_name = (id_name or "").strip() or descripcion
        with engine.begin() as conn:
            updated = conn.execute(
                text(
                    """
                    UPDATE almacen
                    SET idName = :id_name,
                        description = :descripcion,
                        company = :company,
                        type = :tipo_almacen,
                        syncDate = GETDATE()
                    OUTPUT INSERTED.id
                    WHERE id = :almacen_id
                    """
                ),
                {
                    "id_name": final_id_name,
                    "descripcion": descripcion,
                    "company": company,
                    "tipo_almacen": tipo_almacen,
                    "almacen_id": int(almacen_id),
                },
            ).first()
        return bool(updated)
    except Exception as e:
        logger.error("Error actualizando almacen %s: %s", almacen_id, e)
        raise


def set_almacen_status(almacen_id: str, status: int) -> bool:
    """Soft delete/restore de almacen usando status (1 activo, 0 inactivo)."""
    engine = get_sa_engine_kardex()
    try:
        with engine.begin() as conn:
            updated = conn.execute(
                text(
                    """
                    UPDATE almacen
                    SET status = :status, syncDate = GETDATE()
                    OUTPUT INSERTED.id
                    WHERE id = :almacen_id
                    """
                ),
                {"status": status, "almacen_id": int(almacen_id)},
            ).first()
        return bool(updated)
    except Exception as e:
        logger.error("Error cambiando estado de almacen %s: %s", almacen_id, e)
        raise


# ---------------------------------------------------------------------------
# CREAR MARCAS, PRODUCTOS, ALMACENES (Usuario manual)
# ---------------------------------------------------------------------------

def create_marca(name: str, description: str = "") -> Dict[str, Any]:
    """Crea una nueva marca."""
    engine = get_sa_engine_kardex()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO marca (name, description, status, syncDate)
                    OUTPUT INSERTED.id, INSERTED.name, INSERTED.description, INSERTED.status, INSERTED.syncDate
                    VALUES (:name, :description, 1, GETDATE())
                    """
                ),
                {"name": name, "description": description or name},
            ).mappings().first()

        if not row:
            raise RuntimeError("No se pudo crear la marca")

        result = dict(row)
        logger.info("Marca creada: id=%s name=%s", result["id"], name)
        return result
    except Exception as e:
        logger.error("Error creando marca: %s", e)
        raise


def create_producto(
    item_name: str,
    brand: Optional[str] = None,
    categoria: Optional[str] = None,
    um: Optional[str] = None,
    product_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Crea un nuevo producto."""
    engine = get_sa_engine_kardex()
    try:
        pid = product_id or f"MAN-{uuid.uuid4().hex[:12].upper()}"
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO producto (id, itemName, brand, categoria, um, status, syncDate)
                    OUTPUT INSERTED.id, INSERTED.itemName, INSERTED.brand, INSERTED.categoria, INSERTED.um, INSERTED.status
                    VALUES (:pid, :item_name, :brand, :categoria, :um, 1, GETDATE())
                    """
                ),
                {
                    "pid": pid,
                    "item_name": item_name,
                    "brand": brand,
                    "categoria": categoria,
                    "um": um,
                },
            ).mappings().first()

        if not row:
            raise RuntimeError("No se pudo crear el producto")

        result = dict(row)
        logger.info("Producto creado: id=%s itemName=%s", result["id"], item_name)
        return result
    except Exception as e:
        logger.error("Error creando producto: %s", e)
        raise


def set_producto_estado(producto_id: str, estado: int) -> bool:
    """Soft delete/restore de producto usando status (1 activo, 0 inactivo)."""
    engine = get_sa_engine_kardex()
    try:
        with engine.begin() as conn:
            updated = conn.execute(
                text(
                    """
                    UPDATE producto
                    SET status = :estado, syncDate = GETDATE()
                    OUTPUT INSERTED.id
                    WHERE id = :producto_id
                    """
                ),
                {"estado": estado, "producto_id": producto_id},
            ).first()
        return bool(updated)
    except Exception as e:
        logger.error("Error cambiando estado de producto %s: %s", producto_id, e)
        raise


def create_almacen(
    descripcion: str,
    company: Optional[str] = None,
    tipo_almacen: Optional[str] = None,
    id_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Crea un nuevo almacen."""
    engine = get_sa_engine_kardex()
    try:
        final_id_name = (id_name or "").strip() or descripcion
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO almacen (idName, company, status, description, type, syncDate)
                    OUTPUT INSERTED.id, INSERTED.idName, INSERTED.company, INSERTED.status, INSERTED.description, INSERTED.type
                    VALUES (:id_name, :company, 1, :descripcion, :tipo_almacen, GETDATE())
                    """
                ),
                {
                    "id_name": final_id_name,
                    "company": company,
                    "descripcion": descripcion,
                    "tipo_almacen": tipo_almacen,
                },
            ).mappings().first()

        if not row:
            raise RuntimeError("No se pudo crear el almacen")

        result = dict(row)
        logger.info("Almacen creado: id=%s idName=%s", result["id"], final_id_name)
        return result
    except Exception as e:
        logger.error("Error creando almacen: %s", e)
        raise
