// controllers/marcaController.js
const db = require('../config/db');

// ─── GET ALL ────────────────────────────────────────────────────────────────
const getAll = async (req, res) => {
  try {
    const [rows] = await db.query(
      `SELECT id, nombre, estado, createdAt, updatedAt
       FROM marca
       ORDER BY nombre ASC`
    );
    res.json({ success: true, data: rows });
  } catch (err) {
    console.error('[marca.getAll]', err);
    res.status(500).json({ success: false, message: 'Error al obtener marcas' });
  }
};

// ─── GET ACTIVAS (para selects en producto) ──────────────────────────────────
const getActivas = async (req, res) => {
  try {
    const [rows] = await db.query(
      `SELECT id, nombre FROM marca WHERE estado = 1 ORDER BY nombre ASC`
    );
    res.json({ success: true, data: rows });
  } catch (err) {
    console.error('[marca.getActivas]', err);
    res.status(500).json({ success: false, message: 'Error al obtener marcas activas' });
  }
};

// ─── CREATE ─────────────────────────────────────────────────────────────────
const create = async (req, res) => {
  const { nombre } = req.body;

  if (!nombre || !nombre.trim()) {
    return res.status(400).json({ success: false, message: 'El nombre es requerido' });
  }

  try {
    // Verificar nombre duplicado (incluyendo inactivas)
    const [exists] = await db.query(
      `SELECT id FROM marca WHERE LOWER(nombre) = LOWER(?) LIMIT 1`,
      [nombre.trim()]
    );
    if (exists.length > 0) {
      return res.status(409).json({ success: false, message: 'Ya existe una marca con ese nombre' });
    }

    const [result] = await db.query(
      `INSERT INTO marca (nombre, estado) VALUES (?, 1)`,
      [nombre.trim()]
    );
    res.status(201).json({ success: true, message: 'Marca creada', id: result.insertId });
  } catch (err) {
    console.error('[marca.create]', err);
    res.status(500).json({ success: false, message: 'Error al crear marca' });
  }
};

// ─── UPDATE ─────────────────────────────────────────────────────────────────
const update = async (req, res) => {
  const { id } = req.params;
  const { nombre } = req.body;

  if (!nombre || !nombre.trim()) {
    return res.status(400).json({ success: false, message: 'El nombre es requerido' });
  }

  try {
    // Verificar que existe
    const [marca] = await db.query(`SELECT id FROM marca WHERE id = ?`, [id]);
    if (marca.length === 0) {
      return res.status(404).json({ success: false, message: 'Marca no encontrada' });
    }

    // Verificar nombre duplicado en otra marca
    const [dup] = await db.query(
      `SELECT id FROM marca WHERE LOWER(nombre) = LOWER(?) AND id != ? LIMIT 1`,
      [nombre.trim(), id]
    );
    if (dup.length > 0) {
      return res.status(409).json({ success: false, message: 'Ya existe una marca con ese nombre' });
    }

    await db.query(
      `UPDATE marca SET nombre = ? WHERE id = ?`,
      [nombre.trim(), id]
    );
    res.json({ success: true, message: 'Marca actualizada' });
  } catch (err) {
    console.error('[marca.update]', err);
    res.status(500).json({ success: false, message: 'Error al actualizar marca' });
  }
};

// ─── TOGGLE ESTADO (soft delete / reactivar) ─────────────────────────────────
const toggleEstado = async (req, res) => {
  const { id } = req.params;

  try {
    const [rows] = await db.query(
      `SELECT id, estado FROM marca WHERE id = ?`,
      [id]
    );
    if (rows.length === 0) {
      return res.status(404).json({ success: false, message: 'Marca no encontrada' });
    }

    const nuevoEstado = rows[0].estado === 1 ? 0 : 1;
    await db.query(`UPDATE marca SET estado = ? WHERE id = ?`, [nuevoEstado, id]);

    const accion = nuevoEstado === 1 ? 'activada' : 'desactivada';
    res.json({ success: true, message: `Marca ${accion}`, estado: nuevoEstado });
  } catch (err) {
    console.error('[marca.toggleEstado]', err);
    res.status(500).json({ success: false, message: 'Error al cambiar estado de marca' });
  }
};

// ─── DELETE (bloqueado — usar toggleEstado) ──────────────────────────────────
const destroy = async (req, res) => {
  // No permitimos DELETE físico en marcas para evitar problemas de cascada
  // El frontend no debería llamar este endpoint, pero lo protegemos igual
  return res.status(405).json({
    success: false,
    message: 'Las marcas no se eliminan físicamente. Use PATCH /estado para desactivar.'
  });
};

module.exports = { getAll, getActivas, create, update, toggleEstado, destroy };
