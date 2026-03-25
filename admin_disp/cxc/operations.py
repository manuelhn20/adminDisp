"""
Operaciones SQL para Cuentas por Cobrar (CxC).
Implementacion incremental sobre SQLAlchemy Core.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import text

from admin_disp.core.db import get_sa_engine_cxc

log = logging.getLogger("admin_disp.cxc.operations")


def _engine():
    return get_sa_engine_cxc()


def _in_params(values: Iterable[Any], prefix: str) -> Tuple[str, Dict[str, Any]]:
    vals = list(values)
    binds: Dict[str, Any] = {}
    placeholders: List[str] = []
    for idx, value in enumerate(vals):
        key = f"{prefix}{idx}"
        binds[key] = value
        placeholders.append(f":{key}")
    return ",".join(placeholders), binds


def ensure_lote_schema():
    """
    Garantiza que la tabla lote y columnas necesarias existan.
    Se ejecuta al arrancar la app y debe ser idempotente.
    """
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='lote')
                    CREATE TABLE [dbo].[lote] (
                        [id]                 INT            IDENTITY(1,1) NOT NULL,
                        [numeroLiquidacion] NVARCHAR(20)   NULL,
                        [fechaGeneracion]   DATETIME2(0)   NOT NULL DEFAULT GETDATE(),
                        [fechaFin]          DATETIME2(0)   NULL,
                        [ejecutivo]         NVARCHAR(255)  NULL,
                        [generadoPor]       NVARCHAR(255)  NULL,
                        [rangoFechas]       NVARCHAR(100)  NULL,
                        [estado]            NVARCHAR(20)   NOT NULL DEFAULT 'Procesado',
                        [total]             DECIMAL(18,2)  NULL,
                        [recibos]           NVARCHAR(MAX)  NULL,
                        [spFolderPath]      NVARCHAR(500)  NULL,
                        [spFileName]        NVARCHAR(255)  NULL,
                        [spFileId]          NVARCHAR(255)  NULL,
                        [spDownloadUrl]     NVARCHAR(2000) NULL,
                        CONSTRAINT [PK_lote] PRIMARY KEY CLUSTERED ([id] ASC)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    IF NOT EXISTS (
                        SELECT 1 FROM sys.columns
                        WHERE object_id = OBJECT_ID('[dbo].[cobro]') AND name = 'loteId'
                    )
                    ALTER TABLE [dbo].[cobro] ADD [loteId] INT NULL
                    """
                )
            )
            conn.execute(
                text(
                    """
                    IF NOT EXISTS (
                        SELECT 1 FROM sys.columns
                        WHERE object_id = OBJECT_ID('[dbo].[cobro]') AND name = 'estado'
                    )
                    ALTER TABLE [dbo].[cobro] ADD [estado] TINYINT NOT NULL DEFAULT 0
                    """
                )
            )
            conn.execute(
                text(
                    """
                    IF NOT EXISTS (
                        SELECT 1 FROM sys.columns
                        WHERE object_id = OBJECT_ID('[dbo].[lote]') AND name = 'spRevFileId'
                    )
                    ALTER TABLE [dbo].[lote] ADD [spRevFileId] NVARCHAR(255) NULL
                    """
                )
            )
            conn.execute(
                text(
                    """
                    IF NOT EXISTS (
                        SELECT 1 FROM sys.columns
                        WHERE object_id = OBJECT_ID('[dbo].[lote]') AND name = 'spRevDlUrl'
                    )
                    ALTER TABLE [dbo].[lote] ADD [spRevDlUrl] NVARCHAR(2000) NULL
                    """
                )
            )
        log.info("ensure_lote_schema: schema verificado/creado correctamente.")
    except Exception as exc:
        log.error("ensure_lote_schema ERROR: %s", exc, exc_info=True)
        raise


def ensure_sync_config():
    """Crea la tabla sync_config si no existe y asegura el registro id=1."""
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='sync_config')
                    CREATE TABLE sync_config (
                        id INT PRIMARY KEY DEFAULT 1,
                        lastSync DATETIME2 NULL
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    IF NOT EXISTS (SELECT 1 FROM sync_config WHERE id=1)
                    INSERT INTO sync_config (id, lastSync) VALUES (1, NULL)
                    """
                )
            )
        log.debug("sync_config verificada/creada.")
    except Exception as exc:
        log.error("Error en ensure_sync_config: %s", exc)
        raise


def get_last_sync_dt():
    """Obtiene el timestamp de la ultima sincronizacion."""
    engine = _engine()
    with engine.connect() as conn:
        return conn.execute(text("SELECT lastSync FROM sync_config WHERE id=1")).scalar()


def update_last_sync_dt(dt):
    """Actualiza el timestamp de la ultima sincronizacion."""
    engine = _engine()
    with engine.begin() as conn:
        conn.execute(text("UPDATE sync_config SET lastSync=:dt WHERE id=1"), {"dt": dt})


# cobro ------------------------------------------------------------------------

def get_existing_sp_ids():
    """Retorna el set de spItemId ya existentes en la tabla cobro."""
    engine = _engine()
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT spItemId FROM cobro")).all()
    return {row[0] for row in rows}


def bulk_insert_cobros(rows):
    """
    Inserta filas nuevas en cobro.
    Retorna cantidad de filas insertadas.
    """
    if not rows:
        return 0

    insert_sql = text(
        """
        INSERT INTO cobro (
            spItemId, codigoCliente, nombreCliente, banco, metodoPago,
            noFactura, valorPagado, noRecibo, creado, ejecutivo,
            ejecutivoEmail, sucursal, fechaCheque, comentarioAdicional,
            liquidado, liquidadoPor, fechaLiquidado, tieneComprobante
        )
        VALUES (
            :spItemId, :codigoCliente, :nombreCliente, :banco, :metodoPago,
            :noFactura, :valorPagado, :noRecibo, :creado, :ejecutivo,
            :ejecutivoEmail, :sucursal, :fechaCheque, :comentarioAdicional,
            :liquidado, :liquidadoPor, :fechaLiquidado, :tieneComprobante
        )
        """
    )

    inserted_count = 0
    engine = _engine()
    with engine.begin() as conn:
        for row in rows:
            try:
                conn.execute(insert_sql, row)
                inserted_count += 1
            except Exception:
                # Ignorar duplicados por spItemId.
                pass
    return inserted_count


def bulk_upsert_cobros(rows):
    """
    Inserta o actualiza filas en cobro segun spItemId.
    Retorna (inserted, updated).
    """
    if not rows:
        return 0, 0

    sql_upd = text(
        """
        UPDATE cobro SET
            codigoCliente=:codigoCliente,
            nombreCliente=:nombreCliente,
            banco=:banco,
            metodoPago=:metodoPago,
            noFactura=:noFactura,
            valorPagado=:valorPagado,
            noRecibo=:noRecibo,
            creado=:creado,
            ejecutivo=:ejecutivo,
            ejecutivoEmail=:ejecutivoEmail,
            sucursal=:sucursal,
            fechaCheque=:fechaCheque,
            comentarioAdicional=:comentarioAdicional,
            tieneComprobante=:tieneComprobante,
            liquidado=:liquidado,
            liquidadoPor=:liquidadoPor,
            fechaLiquidado=:fechaLiquidado
        WHERE spItemId=:spItemId
        """
    )
    sql_ins = text(
        """
        INSERT INTO cobro (
            spItemId, codigoCliente, nombreCliente, banco, metodoPago,
            noFactura, valorPagado, noRecibo, creado, ejecutivo,
            ejecutivoEmail, sucursal, fechaCheque, comentarioAdicional,
            liquidado, liquidadoPor, fechaLiquidado, tieneComprobante
        )
        VALUES (
            :spItemId, :codigoCliente, :nombreCliente, :banco, :metodoPago,
            :noFactura, :valorPagado, :noRecibo, :creado, :ejecutivo,
            :ejecutivoEmail, :sucursal, :fechaCheque, :comentarioAdicional,
            :liquidado, :liquidadoPor, :fechaLiquidado, :tieneComprobante
        )
        """
    )

    inserted = 0
    updated = 0
    engine = _engine()
    with engine.begin() as conn:
        for row in rows:
            try:
                result = conn.execute(sql_upd, row)
                if result.rowcount and result.rowcount > 0:
                    updated += 1
                else:
                    conn.execute(sql_ins, row)
                    inserted += 1
            except Exception as exc:
                log.warning("bulk_upsert_cobros: error en %s - %s", row.get("spItemId"), exc)

    return inserted, updated


def _is_registro_actualizable(item_id: str, conn) -> Tuple[bool, str]:
    """
    Valida si un registro es actualizable segun reglas de negocio.
    """
    try:
        row = conn.execute(
            text(
                "SELECT [liquidado], [estado], [loteId] FROM [cobro] WHERE [spItemId] = :item_id"
            ),
            {"item_id": item_id},
        ).first()
        if not row:
            return False, "Registro no existe en BD"

        liquidado, estado, lote_id = row

        if liquidado is None:
            return True, "OK"

        is_liquidado = bool(liquidado) and str(liquidado).lower() not in ("no", "0", "false", "")
        if not is_liquidado:
            return True, "OK"

        if estado == 2:
            return False, "Estado Finalizado: registro cerrado"
        if lote_id is not None:
            return False, "Pertenece a un lote: registro procesado"

        return True, "OK"
    except Exception as exc:
        log.warning("_is_registro_actualizable: error para %s - %s", item_id, exc)
        return False, f"Error validacion: {exc}"


def update_blank_fields_with_validation(rows):
    """
    Actualiza solo campos en blanco/NULL en cobro cuando el registro es actualizable.
    Retorna cantidad de campos actualizados.
    """
    if not rows:
        return 0

    blank_fields = [
        "codigoCliente",
        "nombreCliente",
        "banco",
        "metodoPago",
        "noFactura",
        "valorPagado",
        "noRecibo",
        "creado",
        "ejecutivo",
        "ejecutivoEmail",
        "sucursal",
        "fechaCheque",
        "comentarioAdicional",
        "liquidado",
        "liquidadoPor",
        "fechaLiquidado",
    ]
    blank_field_sql = {field: f"[{field}]" for field in blank_fields}

    updated_count = 0
    skipped_count = 0

    engine = _engine()
    with engine.begin() as conn:
        for item in rows:
            item_id = item.get("spItemId")
            if not item_id:
                continue

            es_actualizable, razon = _is_registro_actualizable(item_id, conn)
            if not es_actualizable:
                log.debug("update_blank_fields: saltando %s - %s", item_id, razon)
                skipped_count += 1
                continue

            for field in blank_fields:
                value = item.get(field)
                if value is None or value == "":
                    continue

                try:
                    safe_field = blank_field_sql[field]
                    update_sql = text(
                        f"UPDATE cobro SET {safe_field}=:value "
                        f"WHERE spItemId=:item_id AND {safe_field} IS NULL"
                    )
                    result = conn.execute(update_sql, {"value": value, "item_id": item_id})
                    if result.rowcount and result.rowcount > 0:
                        updated_count += result.rowcount
                except Exception as exc:
                    log.warning("update_blank_fields: error en %s para %s - %s", field, item_id, exc)

    log.info(
        "update_blank_fields: %d campos actualizados, %d registros saltados",
        updated_count,
        skipped_count,
    )
    return updated_count


def update_liquidado_sql(item_ids, liquidadoPor, fecha_liquidado_iso):
    """Refleja la liquidacion en SQL despues de actualizarlo en SharePoint."""
    if not item_ids:
        return

    in_clause, in_params = _in_params(item_ids, "item")
    params = {
        "liquidado_por": liquidadoPor,
        "fecha_liquidado": fecha_liquidado_iso,
        **in_params,
    }
    query = text(
        "UPDATE cobro SET liquidado='Si', liquidadoPor=:liquidado_por, fechaLiquidado=:fecha_liquidado "
        f"WHERE spItemId IN ({in_clause})"
    )

    engine = _engine()
    with engine.begin() as conn:
        conn.execute(query, params)


def get_cobros_paginated(start, length, filters):
    """
    Paginacion server-side con soporte de sort dinamico.
    Retorna (rows, total_sin_filtros, total_con_filtros).
    """
    sortable = {
        "codigoCliente": "[codigoCliente]",
        "nombreCliente": "[nombreCliente]",
        "banco": "[banco]",
        "metodoPago": "[metodoPago]",
        "noFactura": "[noFactura]",
        "valorPagado": "[valorPagado]",
        "noRecibo": "[noRecibo]",
        "creado": "[creado]",
        "ejecutivo": "[ejecutivo]",
        "sucursal": "[sucursal]",
        "liquidado": "[liquidado]",
        "fechaLiquidado": "[fechaLiquidado]",
    }

    raw_col = (filters.get("sort_col") or "creado").strip()
    sort_col = sortable.get(raw_col, "[creado]")
    sort_dir = "DESC" if (filters.get("sort_dir") or "DESC").upper() == "DESC" else "ASC"

    where = ["1=1"]
    params: Dict[str, Any] = {}

    if filters.get("sucursal"):
        where.append("sucursal=:sucursal")
        params["sucursal"] = filters["sucursal"]

    if filters.get("ejecutivo"):
        where.append("ejecutivo LIKE :ejecutivo")
        params["ejecutivo"] = f"%{filters['ejecutivo']}%"

    if filters.get("cliente"):
        where.append("(codigoCliente LIKE :cliente OR nombreCliente LIKE :cliente)")
        params["cliente"] = f"%{filters['cliente']}%"

    if filters.get("recibo"):
        where.append("noRecibo LIKE :recibo")
        params["recibo"] = f"%{filters['recibo']}%"

    if filters.get("liquidado") == "1":
        where.append("(liquidado IS NOT NULL AND liquidado != '' AND LOWER(liquidado) NOT IN ('no', '0', 'false'))")
    elif filters.get("liquidado") == "0":
        where.append("(liquidado IS NULL OR liquidado = '' OR LOWER(liquidado) IN ('no', '0', 'false'))")

    if filters.get("fecha_ini"):
        where.append("LEFT(creado,10) >= :fecha_ini")
        params["fecha_ini"] = filters["fecha_ini"]

    if filters.get("fechaFin"):
        where.append("LEFT(creado,10) <= :fecha_fin")
        params["fecha_fin"] = filters["fechaFin"]

    wc = " AND ".join(where)

    estado_map = {0: "Recibido", 1: "Procesado", 2: "Finalizado"}

    engine = _engine()
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM cobro")).scalar_one()
        filtered = conn.execute(text(f"SELECT COUNT(*) FROM cobro WHERE {wc}"), params).scalar_one()

        page_sql = text(
            """
            SELECT spItemId, codigoCliente, nombreCliente, banco, metodoPago,
                   noFactura, valorPagado, noRecibo, creado, ejecutivo,
                   sucursal, fechaCheque, comentarioAdicional,
                   liquidado, liquidadoPor, fechaLiquidado, tieneComprobante,
                   loteId, estado
            FROM cobro
            WHERE """
            + wc
            + """
            ORDER BY """
            + sort_col
            + " "
            + sort_dir
            + """
            OFFSET :start ROWS FETCH NEXT :length ROWS ONLY
            """
        )
        page_params = {**params, "start": int(start), "length": int(length)}
        rows = [dict(row) for row in conn.execute(page_sql, page_params).mappings().all()]

    for row in rows:
        row["estado_cobro"] = estado_map.get(row.get("estado") or 0, "Recibido")

    return rows, total, filtered


def get_cobros_by_ids(item_ids):
    """
    Retorna filas completas de cobro para una lista de spItemId.
    """
    if not item_ids:
        return []

    in_clause, in_params = _in_params(item_ids, "item")
    query = text(
        """
        SELECT spItemId, codigoCliente, nombreCliente, banco, metodoPago,
               noFactura, valorPagado, noRecibo, creado, ejecutivo,
               sucursal, fechaCheque, comentarioAdicional,
               liquidado, liquidadoPor, fechaLiquidado, tieneComprobante
        FROM cobro
        WHERE spItemId IN ("""
        + in_clause
        + """
        )
        ORDER BY creado DESC
        """
    )

    engine = _engine()
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(query, in_params).mappings().all()]


def get_distinct_values(column):
    """Retorna valores distintos de sucursal o ejecutivo para filtros."""
    column_sql = {
        "sucursal": "[sucursal]",
        "ejecutivo": "[ejecutivo]",
    }
    safe_col = column_sql.get(column)
    if not safe_col:
        return []

    if safe_col == "[sucursal]":
        query = text(
            "SELECT DISTINCT [sucursal] FROM cobro "
            "WHERE [sucursal] IS NOT NULL AND [sucursal]<>'' ORDER BY [sucursal]"
        )
    else:
        query = text(
            "SELECT DISTINCT [ejecutivo] FROM cobro "
            "WHERE [ejecutivo] IS NOT NULL AND [ejecutivo]<>'' ORDER BY [ejecutivo]"
        )

    engine = _engine()
    with engine.connect() as conn:
        return [row[0] for row in conn.execute(query).all()]


def get_ejecutivos_by_sucursal(sucursal):
    """Retorna los ejecutivos de una sucursal especifica."""
    if not sucursal:
        return []

    engine = _engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT DISTINCT [ejecutivo] FROM cobro "
                "WHERE [sucursal] = :sucursal AND [ejecutivo] IS NOT NULL AND [ejecutivo]<>'' "
                "ORDER BY [ejecutivo]"
            ),
            {"sucursal": sucursal},
        ).all()
    return [row[0] for row in rows]


# liquidaciones pdf ------------------------------------------------------------

def registrar_liquidacion_pdf(
    ejecutivo,
    generadoPor,
    rangoFechas,
    recibos_list,
    spFolderPath,
    spFileName,
    spFileId,
    spDownloadUrl,
    **kwargs,
):
    """Inserta un registro en lote cuando se genera y sube un PDF."""
    engine = _engine()
    try:
        recibos_json = " ".join(str(r) for r in recibos_list)
        total = kwargs.get("total")
        sp_item_ids = kwargs.get("sp_item_ids", [])
        numero_liquidacion = kwargs.get("numeroLiquidacion")

        with engine.begin() as conn:
            if not numero_liquidacion:
                cnt = (conn.execute(text("SELECT COUNT(*) FROM lote")).scalar() or 0) + 1
                numero_liquidacion = f"LIQ-{cnt:05d}"

            lote_id = conn.execute(
                text(
                    """
                    INSERT INTO lote (
                        ejecutivo, generadoPor, rangoFechas, recibos,
                        spFolderPath, spFileName, spFileId, spDownloadUrl,
                        numeroLiquidacion, estado, total
                    )
                    OUTPUT INSERTED.id
                    VALUES (
                        :ejecutivo, :generado_por, :rango_fechas, :recibos,
                        :sp_folder_path, :sp_file_name, :sp_file_id, :sp_download_url,
                        :numero_liquidacion, '11', :total
                    )
                    """
                ),
                {
                    "ejecutivo": ejecutivo,
                    "generado_por": generadoPor,
                    "rango_fechas": rangoFechas,
                    "recibos": recibos_json,
                    "sp_folder_path": spFolderPath,
                    "sp_file_name": spFileName,
                    "sp_file_id": spFileId,
                    "sp_download_url": spDownloadUrl,
                    "numero_liquidacion": numero_liquidacion,
                    "total": total,
                },
            ).scalar()

            rows_updated = 0
            if lote_id and sp_item_ids:
                in_clause, in_params = _in_params(sp_item_ids, "item")
                update_query = text(
                    "UPDATE cobro SET loteId=:lote_id, estado=1 "
                    f"WHERE spItemId IN ({in_clause})"
                )
                res = conn.execute(update_query, {"lote_id": lote_id, **in_params})
                rows_updated = res.rowcount or 0

        log.info(
            "registrar_liquidacion_pdf: loteId=%s numero=%s cobros_vinculados=%d/%d",
            lote_id,
            numero_liquidacion,
            rows_updated,
            len(sp_item_ids),
        )
        if rows_updated == 0 and sp_item_ids:
            log.warning(
                "registrar_liquidacion_pdf: 0 cobros vinculados para lote %s (sp_item_ids=%s).",
                numero_liquidacion,
                sp_item_ids[:5],
            )
        return lote_id
    except Exception:
        log.exception("Error registrando liquidacion PDF")
        return None


def update_lote_sp_info(loteId: int, spFileId: str, spDownloadUrl: str):
    """Actualiza campos SharePoint en un lote existente."""
    if not loteId:
        return
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE lote SET spFileId=:sp_file_id, spDownloadUrl=:sp_download_url WHERE id=:id"),
                {"sp_file_id": spFileId, "sp_download_url": spDownloadUrl, "id": loteId},
            )
    except Exception:
        log.exception("update_lote_sp_info: error actualizando lote %s", loteId)


def update_lote_rev_sp_info(loteId: int, rev_file_id: str, rev_dl_url: str):
    """Guarda ID y URL del archivo firmado (_rev) en un lote."""
    if not loteId:
        return
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE lote SET spRevFileId=:rev_id, spRevDlUrl=:rev_url WHERE id=:id"),
                {"rev_id": rev_file_id, "rev_url": rev_dl_url, "id": loteId},
            )
    except Exception:
        log.exception("update_lote_rev_sp_info: error actualizando lote %s", loteId)


def clear_lote_rev_sp_info(loteId: int):
    """Limpia campos del archivo rev en un lote."""
    if not loteId:
        return
    engine = _engine()
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE lote SET spRevFileId=NULL, spRevDlUrl=NULL WHERE id=:id"),
                {"id": loteId},
            )
    except Exception:
        log.exception("clear_lote_rev_sp_info: error actualizando lote %s", loteId)


def get_liquidacion_por_recibo(no_recibo: str):
    """
    Busca el ultimo PDF de liquidacion que contiene el recibo indicado.
    """
    engine = _engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT TOP 1
                        id, fechaGeneracion, ejecutivo, generadoPor,
                        spFolderPath, spFileName, spFileId, spDownloadUrl,
                        numeroLiquidacion, estado
                    FROM lote
                    WHERE recibos LIKE :recibo
                    ORDER BY fechaGeneracion DESC
                    """
                ),
                {"recibo": f'%"{no_recibo}"%'},
            ).mappings().first()

        if not row:
            return None

        return {
            "id": row.get("id"),
            "fecha": str(row.get("fechaGeneracion")),
            "ejecutivo": row.get("ejecutivo") or "",
            "generadoPor": row.get("generadoPor") or "",
            "spFolderPath": row.get("spFolderPath") or "",
            "spFileName": row.get("spFileName") or "",
            "spFileId": row.get("spFileId") or "",
            "spDownloadUrl": row.get("spDownloadUrl") or "",
            "numeroLiquidacion": row.get("numeroLiquidacion") or "",
            "estado": row.get("estado") or "Procesado",
        }
    except Exception:
        log.exception("Error buscando liquidacion por recibo")
        return None


def get_liquidaciones_recientes(limit: int = 50):
    """Retorna los ultimos N lotes."""
    engine = _engine()
    try:
        limit_value = int(limit)
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, fechaGeneracion, ejecutivo, generadoPor,
                           rangoFechas, spFileName, spFileId, spDownloadUrl,
                           numeroLiquidacion, estado, fechaFin, total
                    FROM lote
                    ORDER BY fechaGeneracion DESC
                    OFFSET 0 ROWS FETCH NEXT :limit_value ROWS ONLY
                    """
                ),
                {"limit_value": limit_value},
            ).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        log.exception("Error listando liquidaciones")
        return []


def get_lotes(
    limit: int = 200,
    estado: str = None,
    ejecutivo: str = None,
    recibo: str = None,
    fecha_inicio: str = None,
    fechaFin: str = None,
    sucursal: str = None,
    cliente: str = None,
):
    """Retorna lotes con conteo de cobros asociados, con filtros opcionales."""
    conditions: List[str] = []
    params: Dict[str, Any] = {}

    if estado == "Procesado":
        conditions.append("(l.estado IN ('Procesado', '11', '12', '13', '14'))")
    elif estado in ("Finalizado", "Recibido"):
        conditions.append("l.estado = :estado")
        params["estado"] = estado

    if ejecutivo:
        conditions.append("l.ejecutivo LIKE :ejecutivo")
        params["ejecutivo"] = f"%{ejecutivo}%"

    if recibo:
        conditions.append(
            "EXISTS (SELECT 1 FROM cobro c2 WHERE c2.loteId = l.id AND c2.noRecibo LIKE :recibo)"
        )
        params["recibo"] = f"%{recibo}%"

    if sucursal:
        conditions.append(
            "EXISTS (SELECT 1 FROM cobro c2 WHERE c2.loteId = l.id AND c2.sucursal = :sucursal)"
        )
        params["sucursal"] = sucursal

    if cliente:
        conditions.append(
            "EXISTS (SELECT 1 FROM cobro c2 WHERE c2.loteId = l.id "
            "AND (c2.nombreCliente LIKE :cliente_nombre OR c2.codigoCliente LIKE :cliente_codigo))"
        )
        params["cliente_nombre"] = f"%{cliente}%"
        params["cliente_codigo"] = f"%{cliente}%"

    if fecha_inicio:
        conditions.append("l.fechaGeneracion >= :fecha_inicio")
        params["fecha_inicio"] = fecha_inicio

    if fechaFin:
        conditions.append("l.fechaGeneracion < DATEADD(day, 1, CAST(:fecha_fin AS date))")
        params["fecha_fin"] = fechaFin

    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    limit_value = int(limit)

    query = text(
        """
        SELECT l.id, l.numeroLiquidacion, l.estado,
               l.fechaGeneracion, l.fechaFin,
               l.ejecutivo, l.generadoPor, l.total,
               l.spFileId, l.spFileName, l.spDownloadUrl,
               (SELECT COUNT(*) FROM cobro c WHERE c.loteId = l.id) AS num_cobros,
               l.liquidadoPor,
               l.spRevFileId, l.spRevDlUrl
        FROM lote l
        """
        + where_sql
        + """
        ORDER BY l.fechaGeneracion DESC
        OFFSET 0 ROWS FETCH NEXT :limit_value ROWS ONLY
        """
    )

    engine = _engine()
    try:
        with engine.connect() as conn:
            rows = [
                dict(row)
                for row in conn.execute(query, {**params, "limit_value": limit_value}).mappings().all()
            ]

        for row in rows:
            for key in ("fechaGeneracion", "fechaFin"):
                if row.get(key) is not None:
                    row[key] = str(row[key])
        return rows
    except Exception:
        log.exception("Error en get_lotes")
        return []


def get_next_numero_liquidacion() -> str:
    """Reserva y retorna el proximo numero de liquidacion."""
    engine = _engine()
    try:
        with engine.connect() as conn:
            cnt = (conn.execute(text("SELECT COUNT(*) FROM lote")).scalar() or 0) + 1
        return f"LIQ-{cnt:05d}"
    except Exception:
        import time

        return f"LIQ-{int(time.time())}"


def finalizar_lote(loteId: int, finalizado_por: str = None):
    """
    Cambia estado a Finalizado, registra fechaFin y actualiza cobros del lote.
    """
    now = datetime.datetime.now()
    liquidado_por = finalizado_por or "Sistema"
    fecha_iso = now.strftime("%Y-%m-%dT%H:%M:%S")

    engine = _engine()
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    UPDATE lote
                    SET estado = 'Finalizado', fechaFin = :now, liquidadoPor = :liquidado_por
                    WHERE id = :lote_id AND estado != 'Finalizado'
                    """
                ),
                {"now": now, "liquidado_por": liquidado_por, "lote_id": loteId},
            )
            affected = result.rowcount or 0

            if affected > 0:
                conn.execute(
                    text(
                        """
                        UPDATE cobro
                        SET estado = 2,
                            liquidado = 'Si',
                            liquidadoPor = :liquidado_por,
                            fechaLiquidado = :fecha_iso
                        WHERE loteId = :lote_id
                          AND (liquidado IS NULL OR liquidado NOT IN ('Si', 'si', 'SI', '1', 'true'))
                        """
                    ),
                    {
                        "liquidado_por": liquidado_por,
                        "fecha_iso": fecha_iso,
                        "lote_id": loteId,
                    },
                )

        return affected > 0
    except Exception:
        log.exception("Error en finalizar_lote id=%s", loteId)
        return False


def get_lote_by_id(loteId: int):
    """Retorna metadata de un lote por ID, o None si no existe."""
    engine = _engine()
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, numeroLiquidacion, ejecutivo, spFolderPath,
                           spFileId, spFileName, spDownloadUrl, estado,
                           spRevFileId, spRevDlUrl
                    FROM lote WHERE id = :lote_id
                    """
                ),
                {"lote_id": loteId},
            ).mappings().first()
        return dict(row) if row else None
    except Exception:
        log.exception("get_lote_by_id error id=%s", loteId)
        return None


def update_lote_estado(loteId: int, nuevo_estado: str) -> bool:
    """Actualiza el campo estado de un lote."""
    engine = _engine()
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("UPDATE lote SET estado = :estado WHERE id = :lote_id"),
                {"estado": str(nuevo_estado), "lote_id": loteId},
            )
        return (result.rowcount or 0) > 0
    except Exception:
        log.exception("update_lote_estado error id=%s nuevo_estado=%s", loteId, nuevo_estado)
        return False


def get_cobros_by_lote(loteId: int):
    """Retorna todos los cobros vinculados a un lote."""
    engine = _engine()
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT spItemId, codigoCliente, nombreCliente, banco, metodoPago,
                           noFactura, valorPagado, noRecibo, creado, ejecutivo,
                           sucursal, liquidado, liquidadoPor, fechaLiquidado
                    FROM cobro
                    WHERE loteId = :lote_id
                    ORDER BY creado DESC
                    """
                ),
                {"lote_id": loteId},
            ).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        log.exception("Error en get_cobros_by_lote id=%s", loteId)
        return []


# empleados helpers ------------------------------------------------------------

def get_codigo_empleado_by_nombre(nombre: str):
    """
    Busca el codigo de empleado en la BD de empleados por nombre completo.
    """
    from admin_disp.core.db import get_db_empleados

    if not nombre or not nombre.strip():
        return None

    conn = get_db_empleados()
    try:
        cur = conn.get_cursor()
        cur.execute(
            "SELECT TOP 1 codigo_empleado FROM empleados "
            "WHERE LOWER(nombre_completo) = LOWER(?)",
            nombre.strip(),
        )
        row = cur.fetchone()
        return row[0].strip() if row and row[0] else None
    except Exception:
        log.exception("Error buscando codigo_empleado para '%s'", nombre)
        return None


def fill_sucursal_from_empleados():
    """
    Actualiza sucursal en cobro cuando esta vacia, usando ejecutivoEmail -> empleados.usuario.
    """
    from admin_disp.core.db import get_db_empleados

    emp_conn = get_db_empleados()
    try:
        c_emp = emp_conn.get_cursor()
        c_emp.execute(
            "SELECT usuario, sucursal FROM empleados "
            "WHERE usuario IS NOT NULL AND usuario <> '' "
            "  AND sucursal IS NOT NULL AND sucursal <> ''"
        )
        mapping = {
            row[0].strip().lower(): row[1]
            for row in c_emp.fetchall()
            if row[0]
        }
        if not mapping:
            log.warning("fill_sucursal_from_empleados: no se encontro mapeo en empleados")
            return 0

        updated = 0
        engine = _engine()
        with engine.begin() as conn:
            cobros = conn.execute(
                text(
                    "SELECT spItemId, ejecutivoEmail FROM cobro "
                    "WHERE (sucursal IS NULL OR sucursal = '') AND ejecutivoEmail IS NOT NULL"
                )
            ).all()

            for sp_item_id, ejecutivo_email in cobros:
                if not ejecutivo_email:
                    continue
                sucursal = mapping.get(str(ejecutivo_email).strip().lower())
                if not sucursal:
                    continue

                result = conn.execute(
                    text("UPDATE cobro SET sucursal = :sucursal WHERE spItemId = :sp_item_id"),
                    {"sucursal": sucursal, "sp_item_id": sp_item_id},
                )
                updated += result.rowcount or 0

        log.info("fill_sucursal_from_empleados: %d registros actualizados", updated)
        return updated
    except Exception:
        log.exception("Error en fill_sucursal_from_empleados")
        return 0

