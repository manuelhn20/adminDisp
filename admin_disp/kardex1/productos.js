// public/js/inventario/productos.js
const API = '/api/inventario';
let productos = [];
let pendingToggleId     = null;
let pendingToggleEstado = null;

// ─── Init ──────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  cargarTodo();
});

async function cargarTodo() {
  await Promise.all([cargarMarcasSelect(), cargarProductos()]);
}

// ─── Cargar marcas activas en el select ────────────────────────────────────
async function cargarMarcasSelect() {
  try {
    const res  = await fetch(`${API}/marcas/activas`);
    const json = await res.json();
    if (!json.success) return;

    const select = document.getElementById('productoMarcaId');
    select.innerHTML = '<option value="">— Sin marca —</option>';
    json.data.forEach(m => {
      const opt = document.createElement('option');
      opt.value       = m.id;
      opt.textContent = m.nombre;
      select.appendChild(opt);
    });
  } catch { /* silencioso */ }
}

// ─── Cargar productos ──────────────────────────────────────────────────────
async function cargarProductos() {
  try {
    const res  = await fetch(`${API}/productos`);
    const json = await res.json();
    if (!json.success) throw new Error();
    productos = json.data;
    renderizarTabla();
  } catch {
    document.getElementById('tablaProductos').innerHTML = `
      <tr><td colspan="8" class="text-center py-8 text-red-400">
        <i class="fa fa-triangle-exclamation mr-2"></i>Error al cargar productos
      </td></tr>`;
  }
}

// ─── Renderizar tabla ──────────────────────────────────────────────────────
function renderizarTabla() {
  const tbody = document.getElementById('tablaProductos');
  if (productos.length === 0) {
    tbody.innerHTML = `
      <tr><td colspan="8" class="text-center py-8 text-gray-400">
        No hay productos registrados
      </td></tr>`;
    return;
  }

  tbody.innerHTML = productos.map(p => `
    <tr class="hover:bg-gray-50 transition ${p.estado === 0 ? 'opacity-60' : ''}">
      <td class="px-4 py-3 text-gray-500">${p.id}</td>
      <td class="px-4 py-3 font-medium">${escHtml(p.nombre)}</td>
      <td class="px-4 py-3">
        ${renderMarca(p)}
      </td>
      <td class="px-4 py-3 text-gray-500 font-mono text-xs">${p.upc1 || '—'}</td>
      <td class="px-4 py-3 text-gray-500 font-mono text-xs">${p.upc2 || '—'}</td>
      <td class="px-4 py-3 text-right font-medium">L ${formatNum(p.precio)}</td>
      <td class="px-4 py-3">
        ${p.estado === 1
          ? `<span class="inline-flex items-center gap-1 bg-green-100 text-green-700 text-xs font-medium px-2.5 py-0.5 rounded-full">
               <i class="fa fa-circle text-[8px]"></i> Activo
             </span>`
          : `<span class="inline-flex items-center gap-1 bg-red-100 text-red-700 text-xs font-medium px-2.5 py-0.5 rounded-full">
               <i class="fa fa-circle text-[8px]"></i> Inactivo
             </span>`
        }
      </td>
      <td class="px-4 py-3 text-right">
        <div class="flex items-center justify-end gap-2">
          <button onclick="abrirModal('editar', ${p.id})"
            class="p-1.5 text-blue-500 hover:bg-blue-50 rounded-lg transition" title="Editar">
            <i class="fa fa-pen-to-square"></i>
          </button>
          <button onclick="abrirModalConfirmar(${p.id}, ${p.estado})"
            class="p-1.5 rounded-lg transition ${
              p.estado === 1
                ? 'text-orange-500 hover:bg-orange-50'
                : 'text-green-500 hover:bg-green-50'
            }" title="${p.estado === 1 ? 'Desactivar' : 'Activar'}">
            <i class="fa ${p.estado === 1 ? 'fa-toggle-on' : 'fa-toggle-off'}"></i>
          </button>
        </div>
      </td>
    </tr>
  `).join('');
}

/**
 * Renderiza la celda de marca:
 * - Si no tiene marca: guión
 * - Si tiene marca activa: nombre
 * - Si tiene marca INACTIVA: nombre + badge de advertencia
 */
function renderMarca(p) {
  if (!p.marcaNombre) return '<span class="text-gray-400">—</span>';

  if (p.marcaEstado === 0) {
    return `
      <div class="flex items-center gap-1.5">
        <span>${escHtml(p.marcaNombre)}</span>
        <span class="inline-flex items-center gap-1 bg-amber-100 text-amber-700 text-xs font-medium px-2 py-0.5 rounded-full"
              title="La marca está inactiva">
          <i class="fa fa-triangle-exclamation text-[10px]"></i> Inactiva
        </span>
      </div>`;
  }

  return escHtml(p.marcaNombre);
}

// ─── Abrir Modal (crear o editar) ──────────────────────────────────────────
function abrirModal(modo, id = null) {
  limpiarModal();

  if (modo === 'editar' && id !== null) {
    const p = productos.find(x => x.id === id);
    if (!p) return;

    document.getElementById('productoId').value          = p.id;
    document.getElementById('productoNombre').value      = p.nombre;
    document.getElementById('productoDescripcion').value = p.descripcion || '';
    document.getElementById('productoUpc1').value        = p.upc1 || '';
    document.getElementById('productoUpc2').value        = p.upc2 || '';
    document.getElementById('productoMarcaId').value     = p.marcaId || '';
    document.getElementById('productoPrecio').value      = p.precio;

    document.getElementById('modalProductoTitulo').textContent = 'Editar Producto';
    document.getElementById('btnProductoTexto').textContent    = 'Actualizar';
  } else {
    document.getElementById('modalProductoTitulo').textContent = 'Nuevo Producto';
    document.getElementById('btnProductoTexto').textContent    = 'Guardar';
  }

  document.getElementById('modalProducto').classList.remove('hidden');
  setTimeout(() => document.getElementById('productoNombre').focus(), 100);
}

function limpiarModal() {
  document.getElementById('productoId').value          = '';
  document.getElementById('productoNombre').value      = '';
  document.getElementById('productoDescripcion').value = '';
  document.getElementById('productoUpc1').value        = '';
  document.getElementById('productoUpc2').value        = '';
  document.getElementById('productoMarcaId').value     = '';
  document.getElementById('productoPrecio').value      = '';
  document.getElementById('productoError').classList.add('hidden');
}

function cerrarModal() {
  document.getElementById('modalProducto').classList.add('hidden');
}

// ─── Guardar Producto (crear / editar) ─────────────────────────────────────
async function guardarProducto() {
  const id          = document.getElementById('productoId').value;
  const nombre      = document.getElementById('productoNombre').value.trim();
  const descripcion = document.getElementById('productoDescripcion').value.trim();
  const upc1        = document.getElementById('productoUpc1').value.trim();
  const upc2        = document.getElementById('productoUpc2').value.trim();
  const marcaId     = document.getElementById('productoMarcaId').value;
  const precio      = document.getElementById('productoPrecio').value;
  const errorEl     = document.getElementById('productoError');

  errorEl.classList.add('hidden');

  if (!nombre) { mostrarError(errorEl, 'El nombre es requerido'); return; }
  if (!precio || isNaN(precio) || parseFloat(precio) < 0) {
    mostrarError(errorEl, 'Ingrese un precio válido'); return;
  }
  if (upc1 && upc2 && upc1 === upc2) {
    mostrarError(errorEl, 'UPC1 y UPC2 no pueden tener el mismo valor'); return;
  }

  const esEdicion = !!id;
  const url    = esEdicion ? `${API}/productos/${id}` : `${API}/productos`;
  const method = esEdicion ? 'PUT' : 'POST';

  try {
    const res  = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        nombre, descripcion,
        upc1: upc1 || null,
        upc2: upc2 || null,
        marcaId: marcaId || null,
        precio: parseFloat(precio)
      })
    });
    const json = await res.json();
    if (!json.success) { mostrarError(errorEl, json.message); return; }

    cerrarModal();
    mostrarToast(json.message, 'success');
    cargarProductos();
  } catch {
    mostrarError(errorEl, 'Error de conexión');
  }
}

// ─── Modal Confirmar Toggle Estado ─────────────────────────────────────────
function abrirModalConfirmar(id, estadoActual) {
  pendingToggleId     = id;
  pendingToggleEstado = estadoActual;

  const p          = productos.find(x => x.id === id);
  const nombre     = p ? p.nombre : '';
  const esDesact   = estadoActual === 1;

  document.getElementById('confirmarIcono').innerHTML = esDesact
    ? `<span class="text-orange-500"><i class="fa fa-toggle-off text-5xl"></i></span>`
    : `<span class="text-green-500"><i class="fa fa-toggle-on text-5xl"></i></span>`;

  document.getElementById('confirmarTitulo').textContent  = esDesact ? 'Desactivar Producto' : 'Activar Producto';
  document.getElementById('confirmarMensaje').textContent = esDesact
    ? `¿Desactivar el producto "${nombre}"?`
    : `¿Activar el producto "${nombre}"?`;

  const btn = document.getElementById('btnConfirmar');
  btn.className = `flex-1 px-4 py-2 text-sm font-medium text-white rounded-lg transition ${
    esDesact ? 'bg-orange-500 hover:bg-orange-600' : 'bg-green-600 hover:bg-green-700'
  }`;

  document.getElementById('modalConfirmar').classList.remove('hidden');
}

function cerrarModalConfirmar() {
  document.getElementById('modalConfirmar').classList.add('hidden');
  pendingToggleId     = null;
  pendingToggleEstado = null;
}

async function confirmarToggle() {
  if (pendingToggleId === null) return;
  try {
    const res  = await fetch(`${API}/productos/${pendingToggleId}/estado`, { method: 'PATCH' });
    const json = await res.json();
    if (!json.success) { mostrarToast(json.message, 'error'); return; }
    mostrarToast(json.message, 'success');
    cerrarModalConfirmar();
    cargarProductos();
  } catch {
    mostrarToast('Error de conexión', 'error');
  }
}

// ─── Helpers ───────────────────────────────────────────────────────────────
function mostrarError(el, msg) {
  el.textContent = msg;
  el.classList.remove('hidden');
}

function mostrarToast(msg, tipo = 'success') {
  const toast   = document.getElementById('toast');
  const content = document.getElementById('toastContent');
  const icon    = document.getElementById('toastIcon');
  const msgEl   = document.getElementById('toastMsg');

  msgEl.textContent = msg;
  content.className = `flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg text-sm font-medium text-white min-w-[260px] ${
    tipo === 'success' ? 'bg-green-600' : 'bg-red-600'
  }`;
  icon.className = tipo === 'success' ? 'fa fa-circle-check' : 'fa fa-circle-xmark';

  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 3000);
}

function formatNum(n) {
  return parseFloat(n || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
