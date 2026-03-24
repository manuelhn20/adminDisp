// controllers/productoController.js
const db = require('../config/db');

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Verifica unicidad global de UPC entre upc1 y upc2 de todos los productos.
 * excludeId: id del producto a excluir en UPDATE (null en CREATE)
 */
const verificarUpcUnico = async (upc1, upc2, excludeId = null) => {
  const errores = [];

  if (upc1) {
    const [rows] = await db.query(
      `SELECT id FROM producto
       WHERE (upc1 = ? OR upc2 = ?)
       ${excludeId ? 'AND id != ?' : ''}
       LIMIT 1`,
      excludeId ? [upc1, upc1, excludeId] : [upc1, upc1]
    );
    if (rows.length > 0) errores.push(`UPC1 "${upc1}" ya está registrado en otro producto`);
  }

  if (upc2) {
    const [rows] = await db.query(
      `SELECT id FROM producto
       WHERE (upc1 = ? OR upc2 = ?)
       ${excludeId ? 'AND id != ?' : ''}
       LIMIT 1`,
      excludeId ? [upc2, upc2, excludeId] : [upc2, upc2]
    );
    if (rows.length > 0) errores.push(`UPC2 "${upc2}" ya está registrado en otro producto`);
  }

  // Validar que upc1 y upc2 no sean iguales entre sí
  if (upc1 && upc2 && upc1 === upc2) {
    errores.push('UPC1 y UPC2 no pueden tener el mismo valor');
  }

  return errores;
};

// ─── GET ALL ─────────────────────────────────────────────────────────────────
const getAll = async (req, res) => {
  try {
    const [rows] = await db.query(
      `SELECT
         p.id, p.nombre, p.descripcion, p.upc1, p.upc2,
         p.precio, p.estado, p.createdAt, p.updatedAt,
         p.marcaId,
         m.nombre  AS marcaNombre,
         m.estado  AS marcaEstado
       FROM producto p
       LEFT JOIN marca m ON m.id = p.marcaId
       ORDER BY p.nombre ASC`
    );
    res.json({ success: true, data: rows });
  } catch (err) {
    console.error('[producto.getAll]', err);
    res.status(500).json({ success: false, message: 'Error al obtener productos' });
  }
};

// ─── GET BY ID ───────────────────────────────────────────────────────────────
const getById = async (req, res) => {
  const { id } = req.params;
  try {
    const [rows] = await db.query(
      `SELECT
         p.id, p.nombre, p.descripcion, p.upc1, p.upc2,
         p.precio, p.estado, p.marcaId,
         m.nombre AS marcaNombre,
         m.estado AS marcaEstado
       FROM producto p
       LEFT JOIN marca m ON m.id = p.marcaId
       WHERE p.id = ?`,
      [id]
    );
    if (rows.length === 0) {
      return res.status(404).json({ success: false, message: 'Producto no encontrado' });
    }
    res.json({ success: true, data: rows[0] });
  } catch (err) {
    console.error('[producto.getById]', err);
    res.status(500).json({ success: false, message: 'Error al obtener producto' });
  }
};

// ─── CREATE ──────────────────────────────────────────────────────────────────
const create = async (req, res) => {
  const { nombre, descripcion, upc1, upc2, marcaId, precio } = req.body;

  if (!nombre || !nombre.trim()) {
    return res.status(400).json({ success: false, message: 'El nombre del producto es requerido' });
  }

  try {
    // Verificar unicidad global de UPCs
    const erroresUpc = await verificarUpcUnico(
      upc1 ? upc1.trim() : null,
      upc2 ? upc2.trim() : null
    );
    if (erroresUpc.length > 0) {
      return res.status(409).json({ success: false, message: erroresUpc.join(' | ') });
    }

    // Verificar que la marca exista y esté activa si se proporciona
    if (marcaId) {
      const [marca] = await db.query(
        `SELECT id, estado FROM marca WHERE id = ?`, [marcaId]
      );
      if (marca.length === 0) {
        return res.status(400).json({ success: false, message: 'La marca seleccionada no existe' });
      }
    }

    const [result] = await db.query(
      `INSERT INTO producto (nombre, descripcion, upc1, upc2, marcaId, precio, estado)
       VALUES (?, ?, ?, ?, ?, ?, 1)`,
      [
        nombre.trim(),
        descripcion ? descripcion.trim() : null,
        upc1 ? upc1.trim() : null,
        upc2 ? upc2.trim() : null,
        marcaId || null,
        parseFloat(precio) || 0
      ]
    );
    res.status(201).json({ success: true, message: 'Producto creado', id: result.insertId });
  } catch (err) {
    // Capturar error de trigger de BD (unicidad cruzada)
    if (err.sqlState === '45000') {
      return res.status(409).json({ success: false, message: err.message });
    }
    console.error('[producto.create]', err);
    res.status(500).json({ success: false, message: 'Error al crear producto' });
  }
};

// ─── UPDATE ──────────────────────────────────────────────────────────────────
const update = async (req, res) => {
  const { id } = req.params;
  const { nombre, descripcion, upc1, upc2, marcaId, precio } = req.body;

  if (!nombre || !nombre.trim()) {
    return res.status(400).json({ success: false, message: 'El nombre del producto es requerido' });
  }

  try {
    const [existe] = await db.query(`SELECT id FROM producto WHERE id = ?`, [id]);
    if (existe.length === 0) {
      return res.status(404).json({ success: false, message: 'Producto no encontrado' });
    }

    // Verificar unicidad global de UPCs excluyendo el producto actual
    const erroresUpc = await verificarUpcUnico(
      upc1 ? upc1.trim() : null,
      upc2 ? upc2.trim() : null,
      parseInt(id)
    );
    if (erroresUpc.length > 0) {
      return res.status(409).json({ success: false, message: erroresUpc.join(' | ') });
    }

    if (marcaId) {
      const [marca] = await db.query(`SELECT id FROM marca WHERE id = ?`, [marcaId]);
      if (marca.length === 0) {
        return res.status(400).json({ success: false, message: 'La marca seleccionada no existe' });
      }
    }

    await db.query(
      `UPDATE producto
       SET nombre = ?, descripcion = ?, upc1 = ?, upc2 = ?, marcaId = ?, precio = ?
       WHERE id = ?`,
      [
        nombre.trim(),
        descripcion ? descripcion.trim() : null,
        upc1 ? upc1.trim() : null,
        upc2 ? upc2.trim() : null,
        marcaId || null,
        parseFloat(precio) || 0,
        id
      ]
    );
    res.json({ success: true, message: 'Producto actualizado' });
  } catch (err) {
    if (err.sqlState === '45000') {
      return res.status(409).json({ success: false, message: err.message });
    }
    console.error('[producto.update]', err);
    res.status(500).json({ success: false, message: 'Error al actualizar producto' });
  }
};

// ─── TOGGLE ESTADO ───────────────────────────────────────────────────────────
const toggleEstado = async (req, res) => {
  const { id } = req.params;
  try {
    const [rows] = await db.query(`SELECT id, estado FROM producto WHERE id = ?`, [id]);
    if (rows.length === 0) {
      return res.status(404).json({ success: false, message: 'Producto no encontrado' });
    }
    const nuevoEstado = rows[0].estado === 1 ? 0 : 1;
    await db.query(`UPDATE producto SET estado = ? WHERE id = ?`, [nuevoEstado, id]);
    const accion = nuevoEstado === 1 ? 'activado' : 'desactivado';
    res.json({ success: true, message: `Producto ${accion}`, estado: nuevoEstado });
  } catch (err) {
    console.error('[producto.toggleEstado]', err);
    res.status(500).json({ success: false, message: 'Error al cambiar estado del producto' });
  }
};

module.exports = { getAll, getById, create, update, toggleEstado };
