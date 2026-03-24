// routes/inventario.js
const express = require('express');
const router  = express.Router();

const marcaCtrl      = require('../controllers/marcaController');
const productoCtrl   = require('../controllers/productoController');
const movimientoCtrl = require('../controllers/movimientoController');

// ─── MARCAS ──────────────────────────────────────────────────────────────────
router.get   ('/marcas',             marcaCtrl.getAll);
router.get   ('/marcas/activas',     marcaCtrl.getActivas);   // para selects
router.post  ('/marcas',             marcaCtrl.create);
router.put   ('/marcas/:id',         marcaCtrl.update);
router.patch ('/marcas/:id/estado',  marcaCtrl.toggleEstado); // soft delete / reactivar
router.delete('/marcas/:id',         marcaCtrl.destroy);      // 405 — bloqueado

// ─── PRODUCTOS ───────────────────────────────────────────────────────────────
router.get   ('/productos',             productoCtrl.getAll);
router.get   ('/productos/:id',         productoCtrl.getById);
router.post  ('/productos',             productoCtrl.create);
router.put   ('/productos/:id',         productoCtrl.update);
router.patch ('/productos/:id/estado',  productoCtrl.toggleEstado);

// ─── MOVIMIENTOS ─────────────────────────────────────────────────────────────
router.get   ('/movimientos',         movimientoCtrl.getAll);     // ?tipo=entrada|salida|ajuste
router.get   ('/movimientos/stock',   movimientoCtrl.getStock);   // stock actual
router.get   ('/movimientos/:id',     movimientoCtrl.getById);
router.post  ('/movimientos',         movimientoCtrl.create);
router.put   ('/movimientos/:id',     movimientoCtrl.update);
router.delete('/movimientos/:id',     movimientoCtrl.softDelete); // soft delete

module.exports = router;
