/* planes_aggrid.js */

let planesGridApi = null;
let historicoPlanesGridApi = null;

function _planesRefreshLayout() {
  if (!planesGridApi) return;
  try { if (typeof planesGridApi.refreshCells === 'function') planesGridApi.refreshCells({ force: true }); } catch (e) {}
  try { if (typeof planesGridApi.sizeColumnsToFit === 'function') planesGridApi.sizeColumnsToFit(); } catch (e) {}
}

function _planesFormatNumero(numeroLinea) {
  const raw = String(numeroLinea || '').trim();
  if (!raw) return '-';
  const digits = raw.replace(/\D/g, '');
  if (digits.length < 9) return raw;
  const codeLen = Math.max(1, digits.length - 8);
  const code = digits.slice(0, codeLen);
  const number = digits.slice(codeLen);
  return `+(${code}) ${number.slice(0, 4)}-${number.slice(4)}`;
}

function _planesReadLegacyRows() {
  const rows = Array.from(document.querySelectorAll('#planes-tbody tr[data-id]'));
  return rows.map((tr) => ({
    id_plan: Number(tr.dataset.id || 0),
    numero_linea: tr.dataset.num || '',
    fecha_inicio: tr.dataset.inicio || '',
    fecha_fin: tr.dataset.fin || '',
    costo_plan: tr.dataset.costo || '',
    moneda_plan: tr.dataset.moneda || 'L',
    linked_tipo: tr.dataset.linkedTipo || '',
    linked_marca: tr.dataset.linkedMarca || '',
    linked_modelo: tr.dataset.linkedModelo || '',
    linked_imei: tr.dataset.linkedImei || '',
  }));
}

function _planesReadHistoricoLegacyRows() {
  const rows = Array.from(document.querySelectorAll('#historico-planes-tbody tr[data-id]'));
  return rows.map((tr) => ({
    id_historico: Number(tr.dataset.id || 0),
    id_plan: Number(tr.dataset.idPlan || 0),
    numero_linea: tr.dataset.num || '',
    fecha_operacion: tr.dataset.fechaOp || '',
    fecha_inicio: tr.dataset.inicio || '',
    fecha_fin: tr.dataset.fin || '',
    costo_plan: tr.dataset.costo || '',
    moneda_plan: tr.dataset.moneda || 'L',
  }));
}

function _planesActionsCellRenderer(params) {
  const id = Number(params.data && params.data.id_plan);
  const numero = String((params.data && params.data.numero_linea) || '').replace(/'/g, "\\'");
  return (
    `<button type="button" class="btn btn-primary btn-small btn-grid-edit" data-plan-id="${id}" title="Editar plan" ` +
    'style="width:44px;height:44px;border-radius:10px;background:transparent;border:none;display:inline-flex;align-items:center;justify-content:center;margin-right:6px;position:relative;">' +
    '<div style="width:42px;height:42px;border-radius:50%;background:#06a7e6;position:absolute;"></div>' +
    '<img src="/static/img/edi.png" alt="Editar" style="width:32px;height:32px;position:relative;z-index:1;">' +
    '</button>' +
    `<button type="button" class="btn btn-secondary btn-small btn-grid-renew" data-plan-id="${id}" data-numero="${numero}" title="Renovar" ` +
    'style="width:44px;height:44px;border-radius:10px;background:transparent;border:none;display:inline-flex;align-items:center;justify-content:center;position:relative;">' +
    '<div style="width:42px;height:42px;border-radius:50%;background:#f59e0b;position:absolute;"></div>' +
    '<img src="/static/img/renew.png" alt="Renovar" style="width:42px;height:42px;position:relative;z-index:1;">' +
    '</button>'
  );
}

function _historicoPlanesFormatNumero(numeroLinea) {
  return _planesFormatNumero(numeroLinea);
}

function _historicoPlanesActionsCellRenderer(params) {
  const id = Number(params.data && params.data.id_historico);
  return (
    `<button type="button" class="btn btn-secondary btn-small btn-grid-historico-view" data-historico-id="${id}" title="Ver">Ver</button>`
  );
}

function initPlanesAgGrid() {
  if (planesGridApi) return;
  const el = document.getElementById('planesGrid');
  if (!el || !window.agGrid) return;

  planesGridApi = agGrid.createGrid(el, {
    columnDefs: [
      { headerName: 'Numero de linea', field: 'numero_linea', minWidth: 170, flex: 1.2, valueFormatter: p => _planesFormatNumero(p.value) },
      { headerName: 'Inicio', field: 'fecha_inicio', minWidth: 120, flex: 0.8 },
      { headerName: 'Fin', field: 'fecha_fin', minWidth: 120, flex: 0.8 },
      { headerName: 'Costo', field: 'costo_plan', minWidth: 120, flex: 0.8, valueFormatter: p => `${(p.data && p.data.moneda_plan) || 'L'} ${p.value || ''}` },
      { headerName: 'Acciones', field: 'id_plan', minWidth: 150, maxWidth: 180, sortable: false, filter: false, cellRenderer: _planesActionsCellRenderer },
    ],
    rowData: _planesReadLegacyRows(),
    defaultColDef: { sortable: true, filter: true, resizable: true },
    enableCellTextSelection: true,
    copyHeadersToClipboard: true,
    pagination: true,
    paginationPageSize: 25,
    paginationPageSizeSelector: [25, 50, 100],
    animateRows: true,
  });

  el.addEventListener('click', (ev) => {
    const btnEdit = ev.target.closest('.btn-grid-edit');
    if (btnEdit) {
      const id = Number(btnEdit.getAttribute('data-plan-id') || 0);
      const data = _planesReadLegacyRows().find(r => r && Number(r.id_plan) === id);
      if (id && data && typeof window.openEditPlaneModal === 'function') {
        window.openEditPlaneModal(id, data);
      }
      return;
    }

    const btnRenew = ev.target.closest('.btn-grid-renew');
    if (btnRenew) {
      const id = Number(btnRenew.getAttribute('data-plan-id') || 0);
      const numero = btnRenew.getAttribute('data-numero') || '';
      if (id && typeof window.openRenewPlanModal === 'function') {
        window.openRenewPlanModal(id, numero);
      }
    }
  });

  const search = document.getElementById('planesPageSearch');
  if (search && !search._agBound) {
    search.addEventListener('input', () => {
      const v = (search.value || '').trim();
      if (planesGridApi) planesGridApi.setGridOption('quickFilterText', v);
    });
    search._agBound = true;
  }

  _planesRefreshLayout();
}

function _refreshHistoricoPlanesGridLayout() {
  if (!historicoPlanesGridApi) return;
  try { if (typeof historicoPlanesGridApi.refreshCells === 'function') historicoPlanesGridApi.refreshCells({ force: true }); } catch (e) {}
  try { if (typeof historicoPlanesGridApi.sizeColumnsToFit === 'function') historicoPlanesGridApi.sizeColumnsToFit(); } catch (e) {}
}

function initHistoricoPlanesAgGrid() {
  if (historicoPlanesGridApi) return;
  const el = document.getElementById('historicoPlanesGrid');
  if (!el || !window.agGrid) return;

  historicoPlanesGridApi = agGrid.createGrid(el, {
    columnDefs: [
      { headerName: 'Numero de linea', field: 'numero_linea', minWidth: 170, flex: 1.2, valueFormatter: p => _historicoPlanesFormatNumero(p.value) },
      { headerName: 'Fecha operacion', field: 'fecha_operacion', minWidth: 140, flex: 0.9 },
      { headerName: 'Inicio', field: 'fecha_inicio', minWidth: 120, flex: 0.85 },
      { headerName: 'Fin', field: 'fecha_fin', minWidth: 120, flex: 0.85 },
      { headerName: 'Costo', field: 'costo_plan', minWidth: 120, flex: 0.8, valueFormatter: p => `${(p.data && p.data.moneda_plan) || 'L'} ${p.value || ''}` },
      { headerName: 'Acciones', field: 'id_historico', minWidth: 130, maxWidth: 150, sortable: false, filter: false, cellRenderer: _historicoPlanesActionsCellRenderer },
    ],
    rowData: _planesReadHistoricoLegacyRows(),
    defaultColDef: { sortable: true, filter: true, resizable: true },
    pagination: true,
    paginationPageSize: 25,
    paginationPageSizeSelector: [25, 50, 100],
    animateRows: true,
  });

  el.addEventListener('click', async (ev) => {
    const btnView = ev.target.closest('.btn-grid-historico-view');
    if (!btnView) return;
    const historicoId = Number(btnView.getAttribute('data-historico-id') || 0);
    if (!historicoId) return;
    if (typeof window.openHistoricoDevicesModal === 'function') {
      await window.openHistoricoDevicesModal(historicoId);
    }
  });

  const search = document.getElementById('historicoPlanesSearch');
  if (search && !search._agHistoricoBound) {
    search.addEventListener('input', () => {
      const v = (search.value || '').trim();
      if (historicoPlanesGridApi) historicoPlanesGridApi.setGridOption('quickFilterText', v);
    });
    search._agHistoricoBound = true;
  }

  _refreshHistoricoPlanesGridLayout();
}

function refreshHistoricoPlanesGridFromLegacy() {
  if (!historicoPlanesGridApi) return;
  try {
    historicoPlanesGridApi.setGridOption('rowData', _planesReadHistoricoLegacyRows());
    _refreshHistoricoPlanesGridLayout();
  } catch (e) {}
}

if (typeof window !== 'undefined') {
  window.initHistoricoPlanesAgGrid = initHistoricoPlanesAgGrid;
  window.refreshHistoricoPlanesGridFromLegacy = refreshHistoricoPlanesGridFromLegacy;
}

(function wirePlanesLegacyRefreshSync() {
  if (typeof window === 'undefined') return;
  const oldFn = window.refreshPlanesTbody;
  if (typeof oldFn !== 'function' || oldFn._agWrapped) return;
  const wrapped = async function wrappedRefreshPlanesTbody() {
    const result = await oldFn.apply(this, arguments);
    try {
      if (planesGridApi) {
        planesGridApi.setGridOption('rowData', _planesReadLegacyRows());
        _planesRefreshLayout();
      }
    } catch (e) {}
    return result;
  };
  wrapped._agWrapped = true;
  window.refreshPlanesTbody = wrapped;
})();

document.addEventListener('DOMContentLoaded', () => {
  initPlanesAgGrid();
  setTimeout(_planesRefreshLayout, 0);
});
