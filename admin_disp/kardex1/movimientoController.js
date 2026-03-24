// controllers/movimientoController.js
const db = require('../config/db');

// ─── GET ALL RESÚMENES ────────────────────────────────────────────────────────
const getAll = async (req, res) => {
  try {
    const { tipo } = req.query; // filtro opcional: 'entrada' | 'salida' | 'ajuste'

    let sql = `
      SELECT
        r.id, r.tipo, r.fecha, r.referencia, r.observacion, r.estado,
        r.createdAt, r.updatedAt,
        COUNT(d.id)         AS totalLineas,
        SUM(d.cantidad)     AS totalCantidad,
        SUM(d.cantidad * d.precio) AS totalMonto
      FROM movimientoResumen r
      LEFT JOIN movimientoDetalle d ON d.movimientoResumenId = r.id AND d.estado = 1
    `;
    const params = [];

    if (tipo && ['entrada', 'salida', 'ajuste'].includes(tipo)) {
      sql += ` WHERE r.tipo = ?`;
      params.push(tipo);
    }

    sql += ` GROUP BY r.id ORDER BY r.fecha DESC, r.createdAt DESC`;

    const [rows] = await db.query(sql, params);
    res.json({ success: true, data: rows });
  } catch (err) {
    console.error('[movimiento.getAll]', err);
    res.status(500).json({ success: false, message: 'Error al obtener movimientos' });
  }
};

// ─── GET BY ID (resumen + detalle) ───────────────────────────────────────────
const getById = async (req, res) => {
  const { id } = req.params;
  try {
    const [[resumen]] = await db.query(
      `SELECT id, tipo, fecha, referencia, observacion, estado, createdAt
       FROM movimientoResumen WHERE id = ?`,
      [id]
    );
    if (!resumen) {
      return res.status(404).json({ success: false, message: 'Movimiento no encontrado' });
    }

    const [detalle] = await db.query(
      `SELECT
         d.id, d.productoId, d.cantidad, d.precio, d.estado,
         p.nombre AS productoNombre, p.upc1, p.upc2
       FROM movimientoDetalle d
       JOIN producto p ON p.id = d.productoId
       WHERE d.movimientoResumenId = ? AND d.estado = 1`,
      [id]
    );

    res.json({ success: true, data: { ...resumen, detalle } });
  } catch (err) {
    console.error('[movimiento.getById]', err);
    res.status(500).json({ success: false, message: 'Error al obtener movimiento' });
  }
};

// ─── CREATE (resumen + detalle en transacción) ───────────────────────────────
const create = async (req, res) => {
  const { tipo, fecha, referencia, observacion, detalle } = req.body;

  // Validaciones básicas
  if (!tipo || !['entrada', 'salida', 'ajuste'].includes(tipo)) {
    return res.status(400).json({ success: false, message: 'Tipo de movimiento inválido' });
  }
  if (!fecha) {
    return res.status(400).json({ success: false, message: 'La fecha es requerida' });
  }
  if (!Array.isArray(detalle) || detalle.length === 0) {
    return res.status(400).json({ success: false, message: 'El detalle no puede estar vacío' });
  }

  // Validar líneas de detalle
  for (const linea of detalle) {
    if (!linea.productoId || !linea.cantidad || linea.cantidad <= 0) {
      return res.status(400).json({
        success: false,
        message: 'Cada línea debe tener productoId y cantidad mayor a 0'
      });
    }
  }

  const conn = await db.getConnection();
  try {
    await conn.beginTransaction();

    // Insertar resumen
    const [resumenResult] = await conn.query(
      `INSERT INTO movimientoResumen (tipo, fecha, referencia, observacion, estado)
       VALUES (?, ?, ?, ?, 1)`,
      [tipo, fecha, referencia || null, observacion || null]
    );
    const resumenId = resumenResult.insertId;

    // Insertar líneas de detalle
    for (const linea of detalle) {
      await conn.query(
        `INSERT INTO movimientoDetalle
           (movimientoResumenId, productoId, cantidad, precio, estado)
         VALUES (?, ?, ?, ?, 1)`,
        [resumenId, linea.productoId, linea.cantidad, parseFloat(linea.precio) || 0]
      );
    }

    await conn.commit();
    res.status(201).json({ success: true, message: 'Movimiento registrado', id: resumenId });
  } catch (err) {
    await conn.rollback();
    console.error('[movimiento.create]', err);
    res.status(500).json({ success: false, message: 'Error al registrar movimiento' });
  } finally {
    conn.release();
  }
};

// ─── UPDATE (resumen + reemplazo de detalle activo) ──────────────────────────
const update = async (req, res) => {
  const { id } = req.params;
  const { tipo, fecha, referencia, observacion, detalle } = req.body;

  if (!tipo || !['entrada', 'salida', 'ajuste'].includes(tipo)) {
    return res.status(400).json({ success: false, message: 'Tipo de movimiento inválido' });
  }
  if (!fecha) {
    return res.status(400).json({ success: false, message: 'La fecha es requerida' });
  }
  if (!Array.isArray(detalle) || detalle.length === 0) {
    return res.status(400).json({ success: false, message: 'El detalle no puede estar vacío' });
  }

  const conn = await db.getConnection();
  try {
    const [[existe]] = await conn.query(
      `SELECT id, estado FROM movimientoResumen WHERE id = ?`, [id]
    );
    if (!existe) {
      conn.release();
      return res.status(404).json({ success: false, message: 'Movimiento no encontrado' });
    }
    if (existe.estado === 0) {
      conn.release();
      return res.status(409).json({
        success: false,
        message: 'No se puede editar un movimiento eliminado'
      });
    }

    await conn.beginTransaction();

    // Actualizar resumen
    await conn.query(
      `UPDATE movimientoResumen
       SET tipo = ?, fecha = ?, referencia = ?, observacion = ?
       WHERE id = ?`,
      [tipo, fecha, referencia || null, observacion || null, id]
    );

    // Soft delete de detalle anterior
    await conn.query(
      `UPDATE movimientoDetalle SET estado = 0 WHERE movimientoResumenId = ?`, [id]
    );

    // Insertar nuevo detalle
    for (const linea of detalle) {
      await conn.query(
        `INSERT INTO movimientoDetalle
           (movimientoResumenId, productoId, cantidad, precio, estado)
         VALUES (?, ?, ?, ?, 1)`,
        [id, linea.productoId, linea.cantidad, parseFloat(linea.precio) || 0]
      );
    }

    await conn.commit();
    res.json({ success: true, message: 'Movimiento actualizado' });
  } catch (err) {
    await conn.rollback();
    console.error('[movimiento.update]', err);
    res.status(500).json({ success: false, message: 'Error al actualizar movimiento' });
  } finally {
    conn.release();
  }
};

// ─── SOFT DELETE ──────────────────────────────────────────────────────────────
const softDelete = async (req, res) => {
  const { id } = req.params;
  const conn = await db.getConnection();
  try {
    const [[existe]] = await conn.query(
      `SELECT id, estado FROM movimientoResumen WHERE id = ?`, [id]
    );
    if (!existe) {
      conn.release();
      return res.status(404).json({ success: false, message: 'Movimiento no encontrado' });
    }
    if (existe.estado === 0) {
      conn.release();
      return res.status(409).json({ success: false, message: 'El movimiento ya está eliminado' });
    }

    await conn.beginTransaction();

    // Soft delete resumen
    await conn.query(
      `UPDATE movimientoResumen SET estado = 0 WHERE id = ?`, [id]
    );
    // Soft delete de todo su detalle
    await conn.query(
      `UPDATE movimientoDetalle SET estado = 0 WHERE movimientoResumenId = ?`, [id]
    );

    await conn.commit();
    res.json({ success: true, message: 'Movimiento eliminado' });
  } catch (err) {
    await conn.rollback();
    console.error('[movimiento.softDelete]', err);
    res.status(500).json({ success: false, message: 'Error al eliminar movimiento' });
  } finally {
    conn.release();
  }
};

// ─── STOCK ACTUAL ─────────────────────────────────────────────────────────────
const getStock = async (req, res) => {
  try {
    const [rows] = await db.query(`SELECT * FROM vw_stock ORDER BY producto ASC`);
    res.json({ success: true, data: rows });
  } catch (err) {
    console.error('[movimiento.getStock]', err);
    res.status(500).json({ success: false, message: 'Error al obtener stock' });
  }
};

module.exports = { getAll, getById, create, update, softDelete, getStock };
