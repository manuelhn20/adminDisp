// public/js/inventario/marcas.js
// ─── Estado global ─────────────────────────────────────────────────────────
const API = '/api/inventario';
let marcas = [];
let pendingToggleId   = null;
let pendingToggleEstado = null;

// ─── Inicialización ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  cargarMarcas();

  // Guardar con Enter en el input
  document.getElementById('marcaNombre').addEventListener('keydown', e => {
    if (e.key === 'Enter') guardarMarca();
  });
});

// ─── Cargar y renderizar tabla ───────────────────────────────────────────────
async function cargarMarcas() {
  try {
    const res  = await fetch(`${API}/marcas`);
    const json = await res.json();
    if (!json.success) throw new Error(json.message);
    marcas = json.data;
    renderizarTabla();
  } catch (err) {
    document.getElementById('tablaMarcas').innerHTML = `
      <tr><td colspan="5" class="text-center py-8 text-red-400">
        <i class="fa fa-triangle-exclamation mr-2"></i>Error al cargar marcas
      </td></tr>`;
  }
}

function renderizarTabla() {
  const tbody = document.getElementById('tablaMarcas');
  if (marcas.length === 0) {
    tbody.innerHTML = `
      <tr><td colspan="5" class="text-center py-8 text-gray-400">
        No hay marcas registradas
      </td></tr>`;
    return;
  }

  tbody.innerHTML = marcas.map(m => `
    <tr class="hover:bg-gray-50 transition ${m.estado === 0 ? 'opacity-60' : ''}">
      <td class="px-4 py-3 text-gray-500">${m.id}</td>
      <td class="px-4 py-3 font-medium">${escHtml(m.nombre)}</td>
      <td class="px-4 py-3">
        ${m.estado === 1
          ? `<span class="inline-flex items-center gap-1 bg-green-100 text-green-700 text-xs font-medium px-2.5 py-0.5 rounded-full">
               <i class="fa fa-circle text-[8px]"></i> Activa
             </span>`
          : `<span class="inline-flex items-center gap-1 bg-red-100 text-red-700 text-xs font-medium px-2.5 py-0.5 rounded-full">
               <i class="fa fa-circle text-[8px]"></i> Inactiva
             </span>`
        }
      </td>
      <td class="px-4 py-3 text-gray-400 text-xs">${formatFecha(m.createdAt)}</td>
      <td class="px-4 py-3 text-right">
        <div class="flex items-center justify-end gap-2">
          <button onclick="abrirModalEditar(${m.id})"
            class="p-1.5 text-blue-500 hover:bg-blue-50 rounded-lg transition" title="Editar">
            <i class="fa fa-pen-to-square"></i>
          </button>
          <button onclick="abrirModalConfirmar(${m.id}, ${m.estado})"
            class="p-1.5 rounded-lg transition ${
              m.estado === 1
                ? 'text-orange-500 hover:bg-orange-50'
                : 'text-green-500 hover:bg-green-50'
            }" title="${m.estado === 1 ? 'Desactivar' : 'Activar'}">
            <i class="fa ${m.estado === 1 ? 'fa-toggle-on' : 'fa-toggle-off'}"></i>
          </button>
        </div>
      </td>
    </tr>
  `).join('');
}

// ─── Modal Crear ────────────────────────────────────────────────────────────
function abrirModalCrear() {
  document.getElementById('marcaId').value    = '';
  document.getElementById('marcaNombre').value = '';
  document.getElementById('marcaError').classList.add('hidden');
  document.getElementById('modalMarcaTitulo').textContent = 'Nueva Marca';
  document.getElementById('btnGuardarTexto').textContent  = 'Guardar';
  document.getElementById('modalMarca').classList.remove('hidden');
  setTimeout(() => document.getElementById('marcaNombre').focus(), 100);
}

// ─── Modal Editar ───────────────────────────────────────────────────────────
function abrirModalEditar(id) {
  const marca = marcas.find(m => m.id === id);
  if (!marca) return;

  document.getElementById('marcaId').value     = marca.id;
  document.getElementById('marcaNombre').value = marca.nombre;
  document.getElementById('marcaError').classList.add('hidden');
  document.getElementById('modalMarcaTitulo').textContent = 'Editar Marca';
  document.getElementById('btnGuardarTexto').textContent  = 'Actualizar';
  document.getElementById('modalMarca').classList.remove('hidden');
  setTimeout(() => document.getElementById('marcaNombre').focus(), 100);
}

function cerrarModal() {
  document.getElementById('modalMarca').classList.add('hidden');
}

// ─── Guardar (crear o editar) ────────────────────────────────────────────────
async function guardarMarca() {
  const id     = document.getElementById('marcaId').value;
  const nombre = document.getElementById('marcaNombre').value.trim();
  const errorEl = document.getElementById('marcaError');

  errorEl.classList.add('hidden');

  if (!nombre) {
    mostrarError(errorEl, 'El nombre es requerido');
    return;
  }

  const esEdicion = !!id;
  const url    = esEdicion ? `${API}/marcas/${id}` : `${API}/marcas`;
  const method = esEdicion ? 'PUT' : 'POST';

  try {
    const res  = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre })
    });
    const json = await res.json();

    if (!json.success) {
      mostrarError(errorEl, json.message);
      return;
    }

    cerrarModal();
    mostrarToast(json.message, 'success');
    cargarMarcas();
  } catch (err) {
    mostrarError(errorEl, 'Error de conexión');
  }
}

// ─── Modal Confirmar Toggle Estado ──────────────────────────────────────────
function abrirModalConfirmar(id, estadoActual) {
  pendingToggleId     = id;
  pendingToggleEstado = estadoActual;

  const marca = marcas.find(m => m.id === id);
  const nombre = marca ? marca.nombre : '';

  const esDesactivar = estadoActual === 1;

  document.getElementById('confirmarIcono').innerHTML = esDesactivar
    ? `<span class="text-orange-500"><i class="fa fa-toggle-off"></i></span>`
    : `<span class="text-green-500"><i class="fa fa-toggle-on"></i></span>`;

  document.getElementById('confirmarTitulo').textContent = esDesactivar
    ? 'Desactivar Marca'
    : 'Activar Marca';

  document.getElementById('confirmarMensaje').textContent = esDesactivar
    ? `¿Desactivar la marca "${nombre}"? Los productos asociados mostrarán una advertencia.`
    : `¿Activar la marca "${nombre}"?`;

  const btnConfirmar = document.getElementById('btnConfirmar');
  btnConfirmar.className = `flex-1 px-4 py-2 text-sm font-medium text-white rounded-lg transition ${
    esDesactivar ? 'bg-orange-500 hover:bg-orange-600' : 'bg-green-600 hover:bg-green-700'
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
    const res  = await fetch(`${API}/marcas/${pendingToggleId}/estado`, { method: 'PATCH' });
    const json = await res.json();
    if (!json.success) {
      mostrarToast(json.message, 'error');
      return;
    }
    mostrarToast(json.message, 'success');
    cerrarModalConfirmar();
    cargarMarcas();
  } catch {
    mostrarToast('Error de conexión', 'error');
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
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

  if (tipo === 'success') {
    content.className = 'flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg text-sm font-medium text-white min-w-[260px] bg-green-600';
    icon.className    = 'fa fa-circle-check';
  } else {
    content.className = 'flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg text-sm font-medium text-white min-w-[260px] bg-red-600';
    icon.className    = 'fa fa-circle-xmark';
  }

  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 3000);
}

function formatFecha(str) {
  if (!str) return '-';
  const d = new Date(str);
  return d.toLocaleDateString('es-HN', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
