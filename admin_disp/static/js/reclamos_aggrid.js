/* reclamos_aggrid.js */

let reclamosGridApi = null;

function _reclamosRefreshLayout() {
  if (!reclamosGridApi) return;
  try { if (typeof reclamosGridApi.refreshCells === 'function') reclamosGridApi.refreshCells({ force: true }); } catch (e) {}
  try { if (typeof reclamosGridApi.sizeColumnsToFit === 'function') reclamosGridApi.sizeColumnsToFit(); } catch (e) {}
}

function _reclamosReadLegacyRows() {
  const rows = Array.from(document.querySelectorAll('#reclamosTable tbody tr[data-id]'));
  return rows.map((tr) => {
    const tds = tr.querySelectorAll('td');
    const tipoReclamoText = (tds[5] ? tds[5].textContent : '').trim();
    const estadoText = (tds[6] ? tds[6].textContent : '').trim();
    return {
      id_reclamo: Number(tr.dataset.id || 0),
      empleado_nombre: (tds[0] ? tds[0].textContent : '').trim(),
      empresa: (tds[1] ? tds[1].textContent : '').trim(),
      numero_serie: (tds[2] ? tds[2].textContent : '').trim(),
      nombre_marca: (tds[3] ? tds[3].textContent : '').trim(),
      nombre_modelo: (tds[4] ? tds[4].textContent : '').trim(),
      tipo_reclamo_texto: tipoReclamoText || '-',
      estado_proceso: /completado/i.test(estadoText),
      estado_texto: estadoText,
    };
  });
}

function _reclamosEstadoRenderer(params) {
  const done = !!(params.data && params.data.estado_proceso);
  return `<span style="color:${done ? '#28a745' : '#ffc107'};font-weight:600;">${done ? 'Completado' : 'En proceso'}</span>`;
}

function _reclamosActionsRenderer(params) {
  const id = Number(params.data && params.data.id_reclamo);
  return (
    `<button class="btn btn-primary btn-small btn-grid-edit-reclamo" data-reclamo-id="${id}" title="Editar reclamo" ` +
    'style="width:44px;height:44px;border-radius:10px;background:transparent;border:none;display:inline-flex;align-items:center;justify-content:center;margin-right:6px;position:relative;">' +
    '<div style="width:42px;height:42px;border-radius:50%;background:#06a7e6;position:absolute;"></div>' +
    '<img src="/static/img/edi.png" alt="Editar" style="width:32px;height:32px;position:relative;z-index:1;">' +
    '</button>' +
    `<button class="btn btn-danger btn-small btn-grid-del-reclamo" data-reclamo-id="${id}" title="Eliminar reclamo" ` +
    'style="width:44px;height:44px;border-radius:10px;background:transparent;border:none;display:inline-flex;align-items:center;justify-content:center;position:relative;">' +
    '<div style="width:42px;height:42px;border-radius:50%;background:#e04343;position:absolute;"></div>' +
    '<img src="/static/img/del.png" alt="Eliminar" style="width:32px;height:32px;position:relative;z-index:1;">' +
    '</button>'
  );
}

function initReclamosAgGrid() {
  if (reclamosGridApi) return;
  const el = document.getElementById('reclamosGrid');
  if (!el || !window.agGrid) return;

  reclamosGridApi = agGrid.createGrid(el, {
    columnDefs: [
      { headerName: 'Empleado', field: 'empleado_nombre', minWidth: 180, flex: 1.2 },
      { headerName: 'Empresa', field: 'empresa', minWidth: 150, flex: 1 },
      { headerName: 'Serie', field: 'numero_serie', minWidth: 130, flex: 0.9 },
      { headerName: 'Marca', field: 'nombre_marca', minWidth: 130, flex: 0.9 },
      { headerName: 'Modelo', field: 'nombre_modelo', minWidth: 130, flex: 0.9 },
      { headerName: 'Tipo Reclamo', field: 'tipo_reclamo_texto', minWidth: 140, flex: 0.9 },
      { headerName: 'Estado', field: 'estado_texto', minWidth: 120, flex: 0.8, cellRenderer: _reclamosEstadoRenderer },
      { headerName: 'Acciones', field: 'id_reclamo', minWidth: 140, maxWidth: 170, sortable: false, filter: false, cellRenderer: _reclamosActionsRenderer },
    ],
    rowData: _reclamosReadLegacyRows(),
    defaultColDef: { sortable: true, filter: true, resizable: true },
    enableCellTextSelection: true,
    copyHeadersToClipboard: true,
    pagination: true,
    paginationPageSize: 25,
    paginationPageSizeSelector: [25, 50, 100],
    animateRows: true,
  });

  el.addEventListener('click', (ev) => {
    const btnEdit = ev.target.closest('.btn-grid-edit-reclamo');
    if (btnEdit) {
      const id = Number(btnEdit.getAttribute('data-reclamo-id') || 0);
      if (id && typeof window.openEditReclamoModal === 'function') {
        window.openEditReclamoModal(id);
      }
      return;
    }

    const btnDelete = ev.target.closest('.btn-grid-del-reclamo');
    if (btnDelete) {
      const id = Number(btnDelete.getAttribute('data-reclamo-id') || 0);
      if (id && typeof window.openGlobalDeleteModal === 'function') {
        window.openGlobalDeleteModal(`/devices/reclamo/${id}`, 'Confirmar eliminacion', id);
      }
    }
  });

  const search = document.getElementById('reclamosPageSearch');
  if (search && !search._agBound) {
    search.addEventListener('input', () => {
      const v = (search.value || '').trim();
      if (reclamosGridApi) reclamosGridApi.setGridOption('quickFilterText', v);
    });
    search._agBound = true;
  }

  _reclamosRefreshLayout();
}

(function wireReclamosLegacyRefreshSync() {
  if (typeof window === 'undefined') return;
  const oldFn = window.reloadReclamosTable;
  if (typeof oldFn !== 'function' || oldFn._agWrapped) return;
  const wrapped = async function wrappedReloadReclamosTable() {
    const result = await oldFn.apply(this, arguments);
    try {
      if (reclamosGridApi) {
        reclamosGridApi.setGridOption('rowData', _reclamosReadLegacyRows());
        _reclamosRefreshLayout();
      }
    } catch (e) {}
    return result;
  };
  wrapped._agWrapped = true;
  window.reloadReclamosTable = wrapped;
})();

document.addEventListener('DOMContentLoaded', () => {
  initReclamosAgGrid();
  setTimeout(_reclamosRefreshLayout, 0);
});
