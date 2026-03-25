# admin_disp/cxc/operations.py
"""
Operaciones SQL para Cuentas por Cobrar (CxC).
Usa get_db_cxc() desde admin_disp.core.db para conexiones persistentes.
"""
import logging
from admin_disp.core.db import get_db_cxc

log = logging.getLogger('admin_disp.cxc.operations')


def ensure_lote_schema():
    """
    Garantiza que la tabla `lote` y las columnas `cobro.loteId` / `cobro.estado` existan.
    Se ejecuta una sola vez al arrancar la app. Es idempotente.
    Usa conexion directa (no g) para funcionar fuera de contexto de request.
    """
    import pyodbc as _pyodbc
    from flask import current_app as _app
    cfg = _app.config
    trusted = cfg.get('DB_TRUSTED', False)
    if trusted:
        _cs = (f"DRIVER={{{cfg['DB_DRIVER']}}};SERVER={cfg['DB_SERVER']};"
               f"DATABASE=cxc;Trusted_Connection=yes;")
    else:
        _cs = (f"DRIVER={{{cfg['DB_DRIVER']}}};SERVER={cfg['DB_SERVER']};"
               f"DATABASE=cxc;UID={cfg.get('DB_USER','')};PWD={cfg.get('DB_PASSWORD','')};")
    conn = _pyodbc.connect(_cs)
    try:
        c = conn.cursor()
        # 1. Tabla lote
        c.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='lote')
            CREATE TABLE [dbo].[lote] (
                [id]                 INT            IDENTITY(1,1) NOT NULL,
                [numeroLiquidacion] NVARCHAR(20)   NULL,
                [fechaGeneracion]   DATETIME2(0)   NOT NULL DEFAULT GETDATE(),
                [fechaFin]          DATETIME2(0)   NULL,
                [ejecutivo]          NVARCHAR(255)  NULL,
                [generadoPor]       NVARCHAR(255)  NULL,
                [rangoFechas]       NVARCHAR(100)  NULL,
                [estado]             NVARCHAR(20)   NOT NULL DEFAULT 'Procesado',
                [total]              DECIMAL(18,2)  NULL,
                [recibos]            NVARCHAR(MAX)  NULL,
                [spFolderPath]     NVARCHAR(500)  NULL,
                [spFileName]       NVARCHAR(255)  NULL,
                [spFileId]         NVARCHAR(255)  NULL,
                [spDownloadUrl]    NVARCHAR(2000) NULL,
                CONSTRAINT [PK_lote] PRIMARY KEY CLUSTERED ([id] ASC)
            )
        """)
        # 2. Columna cobro.loteId
        c.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM sys.columns
                WHERE object_id = OBJECT_ID('[dbo].[cobro]') AND name = 'loteId'
            )
            ALTER TABLE [dbo].[cobro] ADD [loteId] INT NULL
        """)
        # 3. Columna cobro.estado  (0=Recibido  1=Procesado  2=Finalizado)
        c.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM sys.columns
                WHERE object_id = OBJECT_ID('[dbo].[cobro]') AND name = 'estado'
            )
            ALTER TABLE [dbo].[cobro] ADD [estado] TINYINT NOT NULL DEFAULT 0
        """)
        # 4. Columnas lote para el archivo firmado temporal (rev)
        c.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM sys.columns
                WHERE object_id = OBJECT_ID('[dbo].[lote]') AND name = 'spRevFileId'
            )
            ALTER TABLE [dbo].[lote] ADD [spRevFileId] NVARCHAR(255) NULL
        """)
        c.execute("""
            IF NOT EXISTS (
                SELECT 1 FROM sys.columns
                WHERE object_id = OBJECT_ID('[dbo].[lote]') AND name = 'spRevDlUrl'
            )
            ALTER TABLE [dbo].[lote] ADD [spRevDlUrl] NVARCHAR(2000) NULL
        """)
        conn.commit()
        log.info('ensure_lote_schema: schema verificado/creado correctamente.')
    except Exception as e:
        log.error('ensure_lote_schema ERROR: %s', e, exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def ensure_sync_config():
    """Crea la tabla sync_config si no existe y asegura el registro id=1."""
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute("""
            IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name='sync_config')
            CREATE TABLE sync_config (
                id        INT PRIMARY KEY DEFAULT 1,
                lastSync DATETIME2 NULL
            )
        """)
        c.execute("""
            IF NOT EXISTS (SELECT 1 FROM sync_config WHERE id=1)
            INSERT INTO sync_config (id, lastSync) VALUES (1, NULL)
        """)
        conn.commit()
        log.debug("sync_config verificada/creada.")
    except Exception as e:
        log.error("Error en ensure_sync_config: %s", e)
        raise


def get_last_sync_dt():
    """Obtiene el timestamp del última sincronización."""
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute("SELECT lastSync FROM sync_config WHERE id=1")
        row = c.fetchone()
        return row[0] if row and row[0] else None
    finally:
        pass


def update_last_sync_dt(dt):
    """Actualiza el timestamp de la última sincronización."""
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute("UPDATE sync_config SET lastSync=? WHERE id=1", (dt,))
        conn.commit()
    finally:
        pass


# ─── cobro ────────────────────────────────────────────────────────────────────

def get_existing_sp_ids():
    """Retorna el set de spItemId ya existentes en la tabla cobro."""
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute("SELECT spItemId FROM cobro")
        return {row[0] for row in c.fetchall()}
    finally:
        pass


def bulk_insert_cobros(rows):
    """
    Inserta filas nuevas en cobro.
    Protege contra duplicados contando antes/después.
    Retorna cantidad de filas insertadas.
    """
    if not rows:
        return 0

    conn = get_db_cxc()
    try:
        c = conn.cursor()
        
        # ── Contar cuántas filas se insertarán ─────────────────────────────
        sp_item_ids = [r["spItemId"] for r in rows]
        placeholders = ",".join("?" for _ in sp_item_ids)
        query = "SELECT COUNT(*) FROM cobro WHERE spItemId IN (" + placeholders + ")"
        c.execute(query, sp_item_ids)
        existing_count = c.fetchone()[0]
        
        # ── Insertar todas las filas (la BD rechazará los duplicados) ──────
        sql = """
            INSERT INTO cobro (
                spItemId, codigoCliente, nombreCliente, banco, metodoPago,
                noFactura, valorPagado, noRecibo, creado, ejecutivo,
                ejecutivoEmail, sucursal, fechaCheque, comentarioAdicional,
                liquidado, liquidadoPor, fechaLiquidado, tieneComprobante
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """
        params = [
            (
                r["spItemId"], r["codigoCliente"], r["nombreCliente"],
                r["banco"], r["metodoPago"], r["noFactura"], r["valorPagado"],
                r["noRecibo"], r["creado"], r["ejecutivo"], r["ejecutivoEmail"],
                r["sucursal"], r["fechaCheque"], r["comentarioAdicional"],
                r["liquidado"], r["liquidadoPor"], r["fechaLiquidado"],
                r["tieneComprobante"],
            )
            for r in rows
        ]
        
        inserted_count = 0
        for param_set in params:
            try:
                c.execute(sql, param_set)
                inserted_count += 1
            except Exception:
                # Ignorar duplicados (spItemId existe)
                pass
        
        conn.commit()
        return inserted_count
    finally:
        pass


def bulk_upsert_cobros(rows):
    """
    Inserta O actualiza filas en cobro según spItemId:
    - Si el spItemId no existe → INSERT.
    - Si ya existe → UPDATE de todos los campos incluyendo liquidado/liquidadoPor/fechaLiquidado.
    Retorna (inserted, updated).
    """
    if not rows:
        return 0, 0

    conn = get_db_cxc()
    c = conn.cursor()
    inserted = 0
    updated  = 0

    sql_upd = """
        UPDATE cobro SET
            codigoCliente=?, nombreCliente=?, banco=?, metodoPago=?,
            noFactura=?, valorPagado=?, noRecibo=?, creado=?,
            ejecutivo=?, ejecutivoEmail=?, sucursal=?, fechaCheque=?,
            comentarioAdicional=?, tieneComprobante=?,
            liquidado=?, liquidadoPor=?, fechaLiquidado=?
        WHERE spItemId=?
    """
    sql_ins = """
        INSERT INTO cobro (
            spItemId, codigoCliente, nombreCliente, banco, metodoPago,
            noFactura, valorPagado, noRecibo, creado, ejecutivo,
            ejecutivoEmail, sucursal, fechaCheque, comentarioAdicional,
            liquidado, liquidadoPor, fechaLiquidado, tieneComprobante
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """

    for r in rows:
        upd_params = (
            r["codigoCliente"], r["nombreCliente"], r["banco"], r["metodoPago"],
            r["noFactura"], r["valorPagado"], r["noRecibo"], r["creado"],
            r["ejecutivo"], r["ejecutivoEmail"], r["sucursal"], r["fechaCheque"],
            r["comentarioAdicional"], r["tieneComprobante"],
            r["liquidado"], r["liquidadoPor"], r["fechaLiquidado"],
            r["spItemId"],
        )
        try:
            c.execute(sql_upd, upd_params)
            if c.rowcount and c.rowcount > 0:
                updated += 1
            else:
                # Not found: INSERT
                ins_params = (
                    r["spItemId"], r["codigoCliente"], r["nombreCliente"],
                    r["banco"], r["metodoPago"], r["noFactura"], r["valorPagado"],
                    r["noRecibo"], r["creado"], r["ejecutivo"], r["ejecutivoEmail"],
                    r["sucursal"], r["fechaCheque"], r["comentarioAdicional"],
                    r["liquidado"], r["liquidadoPor"], r["fechaLiquidado"],
                    r["tieneComprobante"],
                )
                c.execute(sql_ins, ins_params)
                inserted += 1
        except Exception as exc:
            log.warning("bulk_upsert_cobros: error en %s — %s", r.get("spItemId"), exc)

    conn.commit()
    return inserted, updated


def _is_registro_actualizable(item_id: str, conn):
    """
    Valida si un registro es actualizable según las reglas de negocio.
    
    NO actualizar si:
    - liquidado != NULL (está liquidado) Y estado = 2 (Finalizado)
    - liquidado != NULL Y loteId IS NOT NULL (pertenece a un lote)
    
    SÍ actualizar si:
    - liquidado IS NULL (no liquidado)
    - liquidado != NULL Y estado = 0 (Recibido)
    
    Retorna: (es_actualizable: bool, razon_si_no: str)
    """
    c = conn.cursor()
    try:
        c.execute(
            "SELECT [liquidado], [estado], [loteId] FROM [cobro] WHERE [spItemId] = ?",
            (item_id,)
        )
        row = c.fetchone()
        if not row:
            # Registro no existe, no se puede actualizar
            return False, "Registro no existe en BD"
        
        liquidado, estado, loteId = row
        
        # Si liquidado es NULL → no está liquidado → permitir actualización
        if liquidado is None:
            return True, "OK"
        
        # Si liquidado tiene valor (está liquidado), aplicar restricciones
        # Normalizar: cualquier valor que no sea explícitamente "No", "0", "false" es truthy
        is_liquidado = liquidado and str(liquidado).lower() not in ('no', '0', 'false', '')
        
        if not is_liquidado:
            # Valor falsy → permitir actualización
            return True, "OK"
        
        # Está liquidado, verificar estado y loteId
        if estado == 2:  # Finalizado
            return False, "Estado Finalizado: registro cerrado"
        
        if loteId is not None:
            return False, "Pertenece a un lote: registro procesado"
        
        # Está liquidado pero en estado Recibido y sin lote → permitir
        return True, "OK"
        
    except Exception as exc:
        log.warning(f"_is_registro_actualizable: error para {item_id} — {exc}")
        return False, f"Error validación: {exc}"


def update_blank_fields_with_validation(rows):
    """
    Actualiza SOLO los campos en blanco/NULL de registros existentes en cobro.
    
    Incluye validación previa según reglas de negocio: solo actualiza si el registro cumple:
    - NO si está liquidado (liquidado != NULL) y estado = Finalizado o tiene loteId
    - SÍ si no está liquidado (liquidado IS NULL)
    - SÍ si está liquidado pero estado = Recibido y sin lote
    
    Para cada fila: si spItemId existe en cobro, actualiza solo los campos
    donde la BD tiene NULL y el item de SP tiene valor.
    Mantiene intactos los campos que ya tienen datos.
    
    Retorna: count de registros actualizados.
    """
    if not rows:
        return 0
    
    conn = get_db_cxc()
    updated_count = 0
    skipped_count = 0
    
    # Campos que pueden estar en blanco y que queremos llenar
    blank_fields = [
        "codigoCliente", "nombreCliente", "banco", "metodoPago",
        "noFactura", "valorPagado", "noRecibo", "creado",
        "ejecutivo", "ejecutivoEmail", "sucursal", "fechaCheque",
        "comentarioAdicional", "liquidado", "liquidadoPor", "fechaLiquidado",
    ]
    
    c = conn.cursor()
    
    for r in rows:
        item_id = r.get("spItemId")
        if not item_id:
            continue
        
        # Validar si este registro puede ser actualizado
        es_actualizable, razon = _is_registro_actualizable(item_id, conn)
        if not es_actualizable:
            log.debug(f"update_blank_fields: saltando {item_id} — {razon}")
            skipped_count += 1
            continue
        
        # Para cada campo, actualizar si BD tiene NULL y SP tiene valor
        for field in blank_fields:
            value = r.get(field)
            # Solo actualizar si el valor en SP no es None/vacío
            if value is not None and value != "":
                try:
                    c.execute(
                        f"UPDATE cobro SET {field}=? WHERE spItemId=? AND {field} IS NULL",
                        (value, item_id)
                    )
                    if c.rowcount and c.rowcount > 0:
                        updated_count += c.rowcount
                except Exception as exc:
                    log.warning(f"update_blank_fields: error en {field} para {item_id} — {exc}")
    
    conn.commit()
    log.info(f"update_blank_fields: {updated_count} campos actualizados, {skipped_count} registros saltados")
    return updated_count


def update_liquidado_sql(item_ids, liquidadoPor, fecha_liquidado_iso):
    """Refleja la liquidación en SQL después de actualizarlo en SharePoint."""
    if not item_ids:
        return
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        placeholders = ",".join("?" for _ in item_ids)
        query = (
            "UPDATE cobro SET liquidado='Si', liquidadoPor=?, fechaLiquidado=? "
            "WHERE spItemId IN (" + placeholders + ")"
        )
        c.execute(query, [liquidadoPor, fecha_liquidado_iso] + list(item_ids))
        conn.commit()
    finally:
        pass


def get_cobros_paginated(start, length, filters):
    """
    Paginación server-side con soporte de sort dinámico.
    Retorna (rows, total_sin_filtros, total_con_filtros).
    """
    # Columnas permitidas para ORDER BY (whitelist de seguridad)
    # Mapeadas a identificadores SQL con bracket-quoting para evitar inyección
    SORTABLE = {
        "codigoCliente": "[codigoCliente]",
        "nombreCliente": "[nombreCliente]",
        "banco":          "[banco]",
        "metodoPago":    "[metodoPago]",
        "noFactura":     "[noFactura]",
        "valorPagado":   "[valorPagado]",
        "noRecibo":      "[noRecibo]",
        "creado":         "[creado]",
        "ejecutivo":      "[ejecutivo]",
        "sucursal":       "[sucursal]",
        "liquidado":      "[liquidado]",
        "fechaLiquidado": "[fechaLiquidado]",
    }
    raw_col  = (filters.get("sort_col") or "creado").strip()
    sort_col = SORTABLE.get(raw_col, "[creado]")
    sort_dir = "DESC" if (filters.get("sort_dir") or "DESC").upper() == "DESC" else "ASC"

    conn = get_db_cxc()
    try:
        c = conn.cursor()

        where  = ["1=1"]
        params = []

        if filters.get("sucursal"):
            where.append("sucursal=?")
            params.append(filters["sucursal"])

        if filters.get("ejecutivo"):
            where.append("ejecutivo LIKE ?")
            params.append(f"%{filters['ejecutivo']}%")

        if filters.get("cliente"):
            where.append("(codigoCliente LIKE ? OR nombreCliente LIKE ?)")
            v = f"%{filters['cliente']}%"
            params += [v, v]

        if filters.get("recibo"):
            where.append("noRecibo LIKE ?")
            params.append(f"%{filters['recibo']}%")

        if filters.get("liquidado") == "1":
            where.append("(liquidado IS NOT NULL AND liquidado != '' AND LOWER(liquidado) NOT IN ('no', '0', 'false'))")
        elif filters.get("liquidado") == "0":
            where.append("(liquidado IS NULL OR liquidado = '' OR LOWER(liquidado) IN ('no', '0', 'false'))")

        if filters.get("fecha_ini"):
            where.append("LEFT(creado,10) >= ?")
            params.append(filters["fecha_ini"])

        if filters.get("fechaFin"):
            where.append("LEFT(creado,10) <= ?")
            params.append(filters["fechaFin"])

        wc = " AND ".join(where)

        # Total sin filtros
        c.execute("SELECT COUNT(*) FROM cobro")
        total = c.fetchone()[0]

        # Total con filtros
        count_query = "SELECT COUNT(*) FROM cobro WHERE " + wc
        c.execute(count_query, params)
        filtered = c.fetchone()[0]

        # Página de datos con sort dinámico
        # estado: 0=Recibido  1=Procesado  2=Finalizado  (columna directa en cobro)
        _ESTADO_MAP = {0: 'Recibido', 1: 'Procesado', 2: 'Finalizado'}
        page_query = (
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
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
        )
        c.execute(page_query, params + [start, length])
        cols = [d[0] for d in c.description]
        rows = [dict(zip(cols, row)) for row in c.fetchall()]
        for r in rows:
            r['estado_cobro'] = _ESTADO_MAP.get(r.get('estado') or 0, 'Recibido')
        return rows, total, filtered
    finally:
        pass


def get_cobros_by_ids(item_ids):
    """
    Retorna las filas completas de cobro para una lista de spItemId.
    Usado por el endpoint de impresión de reporte.
    """
    if not item_ids:
        return []
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        placeholders = ",".join("?" for _ in item_ids)
        query = (
            """
            SELECT spItemId, codigoCliente, nombreCliente, banco, metodoPago,
                   noFactura, valorPagado, noRecibo, creado, ejecutivo,
                   sucursal, fechaCheque, comentarioAdicional,
                   liquidado, liquidadoPor, fechaLiquidado, tieneComprobante
            FROM cobro
            WHERE spItemId IN ("""
            + placeholders
            + """)
            ORDER BY creado DESC
            """
        )
        c.execute(query, item_ids)
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]
    finally:
        pass


def get_distinct_values(column):
    """Retorna valores distintos de sucursal o ejecutivo para los filtros."""
    # Mapping explícito: sólo identificadores SQL pre-definidos entran en la query
    COLUMN_SQL = {
        "sucursal":  "[sucursal]",
        "ejecutivo": "[ejecutivo]",
    }
    safe_col = COLUMN_SQL.get(column)
    if not safe_col:
        return []
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT DISTINCT {safe_col} FROM cobro "
            f"WHERE {safe_col} IS NOT NULL AND {safe_col}<>'' ORDER BY {safe_col}"
        )
        return [row[0] for row in c.fetchall()]
    finally:
        pass


def get_ejecutivos_by_sucursal(sucursal):
    """Retorna los ejecutivos de una sucursal específica."""
    if not sucursal:
        return []
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT DISTINCT [ejecutivo] FROM cobro "
            "WHERE [sucursal] = ? AND [ejecutivo] IS NOT NULL AND [ejecutivo]<>'' "
            "ORDER BY [ejecutivo]",
            (sucursal,)
        )
        return [row[0] for row in c.fetchall()]
    finally:
        pass


# ── Liquidaciones PDF ──────────────────────────────────────────────────────────

def registrar_liquidacion_pdf(ejecutivo, generadoPor, rangoFechas, recibos_list,
                               spFolderPath, spFileName, spFileId, spDownloadUrl,
                               **kwargs):
    """
    Inserta un registro en la tabla lote cuando se genera y sube un PDF.

    Args:
        ejecutivo      : Nombre del ejecutivo del reporte
        generadoPor   : Usuario que generó el PDF (sesión)
        rangoFechas   : String de rango, ej: '01/03/2026 al 03/03/2026'
        recibos_list   : Lista de noRecibo incluidos en el PDF
        spFolderPath : Ruta de carpeta en SharePoint, ej: 'IT/CxC/2026'
        spFileName   : Nombre del archivo, ej: 'liq_2026-03-03_143022.pdf'
        spFileId     : ID del item en Graph API
        spDownloadUrl: URL de descarga directa

    Returns:
        int: ID del registro insertado, o None en caso de error
    """
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        recibos_json = ' '.join(str(r) for r in recibos_list)

        # Calcular total si no se proporcionó
        _total             = kwargs.get('total')
        _sp_item_ids       = kwargs.get('sp_item_ids', [])
        numeroLiquidacion = kwargs.get('numeroLiquidacion')

        # Si no se proporcionó un número pre-generado, generarlo aquí
        if not numeroLiquidacion:
            c.execute("SELECT COUNT(*) FROM lote")
            cnt = (c.fetchone()[0] or 0) + 1
            numeroLiquidacion = f"LIQ-{cnt:05d}"

        c.execute(
            """
            INSERT INTO lote
                (ejecutivo, generadoPor, rangoFechas, recibos,
                 spFolderPath, spFileName, spFileId, spDownloadUrl,
                 numeroLiquidacion, estado, total)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '11', ?)
            """,
            ejecutivo, generadoPor, rangoFechas, recibos_json,
            spFolderPath, spFileName, spFileId, spDownloadUrl,
            numeroLiquidacion, _total,
        )
        row = c.fetchone()
        loteId = row[0] if row else None

        # Vincular cobros al lote y marcarlos como Procesado (estado=1)
        rows_updated = 0
        if loteId and _sp_item_ids:
            placeholders = ','.join('?' for _ in _sp_item_ids)
            query = "UPDATE cobro SET loteId=?, estado=1 WHERE spItemId IN (" + placeholders + ")"
            c.execute(query, [loteId] + list(_sp_item_ids))
            rows_updated = c.rowcount

        conn.commit()
        log.info(
            'registrar_liquidacion_pdf: loteId=%s numero=%s cobros_vinculados=%d/%d',
            loteId, numeroLiquidacion, rows_updated, len(_sp_item_ids),
        )
        if rows_updated == 0 and _sp_item_ids:
            log.warning(
                'registrar_liquidacion_pdf: 0 cobros vinculados para lote %s '
                '(sp_item_ids=%s). Verificar columnas cobro.loteId/estado y los IDs.',
                numeroLiquidacion, _sp_item_ids[:5],
            )
        return loteId
    except Exception:
        log.exception('Error registrando liquidacion PDF')
        return None


def update_lote_sp_info(loteId: int, spFileId: str, spDownloadUrl: str):
    """Actualiza los campos de SharePoint en un lote ya registrado."""
    if not loteId:
        return
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute(
            "UPDATE lote SET spFileId=?, spDownloadUrl=? WHERE id=?",
            spFileId, spDownloadUrl, loteId,
        )
        conn.commit()
    except Exception:
        log.exception('update_lote_sp_info: error actualizando lote %s', loteId)


def update_lote_rev_sp_info(loteId: int, rev_file_id: str, rev_dl_url: str):
    """Guarda el ID y URL del archivo firmado (_rev) en SP para un lote."""
    if not loteId:
        return
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute(
            "UPDATE lote SET spRevFileId=?, spRevDlUrl=? WHERE id=?",
            rev_file_id, rev_dl_url, loteId,
        )
        conn.commit()
    except Exception:
        log.exception('update_lote_rev_sp_info: error actualizando lote %s', loteId)


def clear_lote_rev_sp_info(loteId: int):
    """Limpia los campos del archivo rev (tras confirmar/renombrar)."""
    if not loteId:
        return
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute(
            "UPDATE lote SET spRevFileId=NULL, spRevDlUrl=NULL WHERE id=?",
            loteId,
        )
        conn.commit()
    except Exception:
        log.exception('clear_lote_rev_sp_info: error actualizando lote %s', loteId)


def get_liquidacion_por_recibo(no_recibo: str):
    """
    Busca el último PDF de liquidación que contiene el recibo indicado.

    Returns:
        dict con {id, fechaGeneracion, ejecutivo, spFolderPath,
                  spFileName, spFileId, spDownloadUrl}
        o None si no hay registro.
    """
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        # Busca el registro más reciente que contenga el recibo (JSON array o substring)
        c.execute(
            """
            SELECT TOP 1
                id, fechaGeneracion, ejecutivo, generadoPor,
                spFolderPath, spFileName, spFileId, spDownloadUrl,
                numeroLiquidacion, estado
            FROM lote
            WHERE recibos LIKE ?
            ORDER BY fechaGeneracion DESC
            """,
            f'%"{no_recibo}"%',
        )
        row = c.fetchone()
        if not row:
            return None
        return {
            'id':                row[0],
            'fecha':             str(row[1]),
            'ejecutivo':         row[2] or '',
            'generadoPor':      row[3] or '',
            'spFolderPath':    row[4] or '',
            'spFileName':      row[5] or '',
            'spFileId':        row[6] or '',
            'spDownloadUrl':   row[7] or '',
            'numeroLiquidacion': row[8] or '',
            'estado':            row[9] or 'Procesado',
        }
    except Exception:
        import logging
        logging.getLogger('admin_disp.cxc.operations').exception('Error buscando liquidacion por recibo')
        return None


def get_liquidaciones_recientes(limit: int = 50):
    """Retorna los últimos N lotes."""
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        limit_value = int(limit)
        c.execute(
            """
            SELECT id, fechaGeneracion, ejecutivo, generadoPor,
                   rangoFechas, spFileName, spFileId, spDownloadUrl,
                   numeroLiquidacion, estado, fechaFin, total
            FROM lote
            ORDER BY fechaGeneracion DESC
            OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
            """,
            (limit_value,),
        )
        cols = ['id', 'fechaGeneracion', 'ejecutivo', 'generadoPor',
                'rangoFechas', 'spFileName', 'spFileId', 'spDownloadUrl',
                'numeroLiquidacion', 'estado', 'fechaFin', 'total']
        return [dict(zip(cols, row)) for row in c.fetchall()]
    except Exception:
        import logging
        logging.getLogger('admin_disp.cxc.operations').exception('Error listando liquidaciones')
        return []


def get_lotes(limit: int = 200, estado: str = None, ejecutivo: str = None,
              recibo: str = None, fecha_inicio: str = None, fechaFin: str = None,
              sucursal: str = None, cliente: str = None):
    """Retorna lotes con conteo de cobros asociados, con filtros opcionales."""
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        conditions = []
        params = []
        if estado == 'Procesado':
            # Incluye el valor legacy 'Procesado' y los sub-estados numéricos 11-14
            conditions.append("(l.estado IN ('Procesado', '11', '12', '13', '14'))")
        elif estado in ('Finalizado', 'Recibido'):
            conditions.append('l.estado = ?')
            params.append(estado)
        if ejecutivo:
            conditions.append('l.ejecutivo LIKE ?')
            params.append(f'%{ejecutivo}%')
        if recibo:
            conditions.append('EXISTS (SELECT 1 FROM cobro c2 WHERE c2.loteId = l.id AND c2.noRecibo LIKE ?)')
            params.append(f'%{recibo}%')
        if sucursal:
            conditions.append('EXISTS (SELECT 1 FROM cobro c2 WHERE c2.loteId = l.id AND c2.sucursal = ?)')
            params.append(sucursal)
        if cliente:
            conditions.append('EXISTS (SELECT 1 FROM cobro c2 WHERE c2.loteId = l.id AND (c2.nombreCliente LIKE ? OR c2.codigoCliente LIKE ?))')
            params.append(f'%{cliente}%')
            params.append(f'%{cliente}%')
        if fecha_inicio:
            conditions.append('l.fechaGeneracion >= ?')
            params.append(fecha_inicio)
        if fechaFin:
            conditions.append('l.fechaGeneracion < DATEADD(day, 1, CAST(? AS date))')
            params.append(fechaFin)
        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        limit_value = int(limit)
        query = (
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
            + where
            + """
            ORDER BY l.fechaGeneracion DESC
            OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY
            """
        )
        c.execute(query, params + [limit_value])
        cols = ['id', 'numeroLiquidacion', 'estado', 'fechaGeneracion', 'fechaFin',
                'ejecutivo', 'generadoPor', 'total', 'spFileId', 'spFileName',
                'spDownloadUrl', 'num_cobros', 'liquidadoPor',
                'spRevFileId', 'spRevDlUrl']
        rows = []
        for row in c.fetchall():
            d = dict(zip(cols, row))
            # Serializar fechas
            for k in ('fechaGeneracion', 'fechaFin'):
                if d[k] is not None:
                    d[k] = str(d[k])
            rows.append(d)
        return rows
    except Exception:
        log.exception('Error en get_lotes')
        return []


def get_next_numero_liquidacion() -> str:
    """Reserva y retorna el próximo número de liquidación (LIQ-00001 format)."""
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM lote")
        cnt = (c.fetchone()[0] or 0) + 1
        return f"LIQ-{cnt:05d}"
    except Exception:
        import time
        return f"LIQ-{int(time.time())}"


def finalizar_lote(loteId: int, finalizado_por: str = None):
    """
    Cambia el estado a 'Finalizado', registra fechaFin y marca
    los cobros del lote como liquidado='Si' en la tabla cobro.
    """
    import datetime as _dt
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        now = _dt.datetime.now()
        c.execute(
            """
            UPDATE lote
               SET estado = 'Finalizado', fechaFin = ?,
                   liquidadoPor = ?
             WHERE id = ? AND estado != 'Finalizado'
            """,
            now, finalizado_por or 'Sistema', loteId,
        )
        affected = c.rowcount
        if affected > 0:
            fecha_iso = now.strftime('%Y-%m-%dT%H:%M:%S')
            liquidadoPor = finalizado_por or 'Sistema'
            c.execute(
                """
                UPDATE cobro
                   SET estado = 2,
                       liquidado = 'Si',
                       liquidadoPor = ?,
                       fechaLiquidado = ?
                 WHERE loteId = ?
                   AND (liquidado IS NULL OR liquidado NOT IN ('Si', 'si', 'SI', '1', 'true'))
                """,
                liquidadoPor, fecha_iso, loteId,
            )
        conn.commit()
        return affected > 0
    except Exception:
        log.exception('Error en finalizar_lote id=%s', loteId)
        return False


def get_lote_by_id(loteId: int):
    """Retorna metadata de un lote por su ID, o None si no existe."""
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT id, numeroLiquidacion, ejecutivo, spFolderPath,
                   spFileId, spFileName, spDownloadUrl, estado,
                   spRevFileId, spRevDlUrl
            FROM lote WHERE id = ?
            """,
            loteId,
        )
        row = c.fetchone()
        if not row:
            return None
        cols = ['id', 'numeroLiquidacion', 'ejecutivo', 'spFolderPath',
                'spFileId', 'spFileName', 'spDownloadUrl', 'estado',
                'spRevFileId', 'spRevDlUrl']
        return dict(zip(cols, row))
    except Exception:
        log.exception('get_lote_by_id error id=%s', loteId)
        return None


def update_lote_estado(loteId: int, nuevo_estado: str) -> bool:
    """
    Actualiza el campo estado de un lote.
    Valores de documento: '11'=generado, '12'=firmado, '13'=en_revision, '14'=confirmado.
    El valor 'Finalizado' lo gestiona finalizar_lote().
    """
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute("UPDATE lote SET estado = ? WHERE id = ?", str(nuevo_estado), loteId)
        conn.commit()
        return (c.rowcount or 0) > 0
    except Exception:
        log.exception('update_lote_estado error id=%s nuevo_estado=%s', loteId, nuevo_estado)
        return False


def get_cobros_by_lote(loteId: int):
    """Retorna todos los cobros vinculados a un lote."""
    conn = get_db_cxc()
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT spItemId, codigoCliente, nombreCliente, banco, metodoPago,
                   noFactura, valorPagado, noRecibo, creado, ejecutivo,
                   sucursal, liquidado, liquidadoPor, fechaLiquidado
            FROM cobro
            WHERE loteId = ?
            ORDER BY creado DESC
            """,
            loteId,
        )
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]
    except Exception:
        log.exception('Error en get_cobros_by_lote id=%s', loteId)
        return []


# ── Empleados helpers ─────────────────────────────────────────────────────────

def get_codigo_empleado_by_nombre(nombre: str):
    """
    Busca el código de empleado en la BD de empleados por nombre completo.

    Args:
        nombre: Nombre completo del ejecutivo a buscar (case-insensitive)

    Returns:
        str: codigo_empleado (ej: 'TGU001') o None si no se encuentra
    """
    from admin_disp.core.db import get_db_empleados
    if not nombre or not nombre.strip():
        return None
    conn = get_db_empleados()
    try:
        c = conn.cursor()
        c.execute(
            "SELECT TOP 1 codigo_empleado FROM empleados "
            "WHERE LOWER(nombre_completo) = LOWER(?)",
            nombre.strip(),
        )
        row = c.fetchone()
        return row[0].strip() if row and row[0] else None
    except Exception:
        log.exception("Error buscando codigo_empleado para '%s'", nombre)
        return None


def fill_sucursal_from_empleados():
    """
    Actualiza la columna sucursal en cobro para filas donde está vacía,
    haciendo match por ejecutivoEmail = empleados.usuario (email completo).

    Returns:
        int: Cantidad de filas actualizadas
    """
    from admin_disp.core.db import get_db_empleados
    cxc_conn = get_db_cxc()
    emp_conn = get_db_empleados()
    try:
        c_emp = emp_conn.cursor()
        # Obtener mapeo email completo → sucursal desde la BD de empleados
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
            log.warning("fill_sucursal_from_empleados: no se encontró mapeo en empleados")
            return 0

        # Obtener cobros con sucursal vacía o nula
        c_cxc = cxc_conn.cursor()
        c_cxc.execute(
            "SELECT spItemId, ejecutivoEmail FROM cobro "
            "WHERE (sucursal IS NULL OR sucursal = '') AND ejecutivoEmail IS NOT NULL"
        )
        cobros = c_cxc.fetchall()

        updated = 0
        for spItemId, ejecutivo_email in cobros:
            if not ejecutivo_email:
                continue
            email_key = ejecutivo_email.strip().lower()
            sucursal = mapping.get(email_key)
            if sucursal:
                c_cxc.execute(
                    "UPDATE cobro SET sucursal = ? WHERE spItemId = ?",
                    (sucursal, spItemId),
                )
                updated += 1

        cxc_conn.commit()
        log.info("fill_sucursal_from_empleados: %d registros actualizados", updated)
        return updated
    except Exception:
        log.exception("Error en fill_sucursal_from_empleados")
        return 0
