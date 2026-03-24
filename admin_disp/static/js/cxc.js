/* cxc.js &mdash; PROIMA CxC
   AG Grid v32.3 &mdash; API actualizada (sin deprecated warnings)
   â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
(function () {
  'use strict';

  if (!window.CXC_FLAGS) {
    window.CXC_FLAGS = {
      CAN_LIQUIDAR: false,
      CAN_CONFIRM: true,
      IS_ADMIN: false,
      IS_SUPERADMIN: false,
      CURRENT_EJECUTIVO: '',
      CXC_ROLE: '',
    };
  }

  const FLAGS = window.CXC_FLAGS;
  const PAGE_SIZE_DEFAULT = 100;

  let currentSort = { col: 'creado', dir: 'DESC' };
  let gridApi;

  // Términos de búsqueda en vivo (para resaltar coincidencias en la tabla)
  let liveFilters = { cliente: '', recibo: '' };

  // Normaliza cadena: minúsculas + sin tildes/diacríticos
  function normalizeStr(s) {
    return String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  // Resalta `term` dentro de `text` con <mark class="hl">
  // Ignora tildes y mayúsculas tanto en el término como en el texto.
  function highlightCell(text, term) {
    if (!text) return '';
    const str = String(text);
    if (!term) return str;
    const normStr  = normalizeStr(str);
    const normTerm = normalizeStr(term);
    const esc = normTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re  = new RegExp(esc, 'g');
    let result = '';
    let lastIdx = 0;
    let match;
    while ((match = re.exec(normStr)) !== null) {
      // Añadir texto anterior sin marca
      result += str.slice(lastIdx, match.index);
      // Añadir la porción original (con tilde/mayúsculas originales) envuelta en mark
      result += '<mark class="hl">' + str.slice(match.index, match.index + match[0].length) + '</mark>';
      lastIdx = match.index + match[0].length;
    }
    result += str.slice(lastIdx);
    return result || str;
  }

  // Sincroniza liveFilters con los valores actuales de los inputs
  function syncLiveFilters() {
    liveFilters.cliente = (document.getElementById('filterCliente')?.value || '').trim();
    liveFilters.recibo  = (document.getElementById('filterRecibo')?.value  || '').trim();
  }

  let _liveSearchTimer = null;
  function reloadCurrentView() {
    if (_currentCxcView === 'finalizados') {
      _loadFinalizadosData();
    } else {
      reloadGrid();
    }
  }

  function debounceReload(ms) {
    clearTimeout(_liveSearchTimer);
    _liveSearchTimer = setTimeout(() => { syncLiveFilters(); reloadCurrentView(); }, ms || 400);
  }

  // â”€â”€ Modal helpers (confirm / alert / loading) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function showLoading(text) {
    const m = document.getElementById('globalLoadingModal');
    if (!m) return;
    const t = document.getElementById('globalLoadingText');
    if (t && text) t.textContent = text;
    m.classList.toggle('dark', document.documentElement.dataset.theme === 'dark');
    m.style.display = 'flex';
    m.setAttribute('aria-hidden', 'false');
  }

  function hideLoading() {
    const m = document.getElementById('globalLoadingModal');
    if (!m) return;
    m.style.display = 'none';
    m.setAttribute('aria-hidden', 'true');
  }

  function showConfirm(msg, onOk, onCancel, title, icon) {
    const overlay   = document.getElementById('confirmModal');
    if (!overlay) { if (onOk && confirm(msg)) onOk(); else if (onCancel) onCancel(); return; }
    document.getElementById('confirmModalMsg').textContent   = msg;
    document.getElementById('confirmModalTitle').textContent = title || 'Confirmación';
    document.getElementById('confirmModalIcon').textContent  = icon  || 'help';
    const close = () => overlay.classList.remove('open');
    // Replace buttons to remove previous listeners
    ['confirmModalOk', 'confirmModalCancel', 'confirmModalClose'].forEach(id => {
      const el = document.getElementById(id);
      const clone = el.cloneNode(true);
      el.replaceWith(clone);
    });
    document.getElementById('confirmModalOk').addEventListener('click', () => { close(); if (onOk) onOk(); });
    document.getElementById('confirmModalCancel').addEventListener('click', () => { close(); if (onCancel) onCancel(); });
    document.getElementById('confirmModalClose').addEventListener('click', close);
    overlay.classList.add('open');
  }

  function showAlert(msg, title, icon) {
    const overlay = document.getElementById('alertModal');
    if (!overlay) { alert(msg); return; }
    document.getElementById('alertModalMsg').textContent   = msg;
    document.getElementById('alertModalTitle').textContent = title || 'Información';
    document.getElementById('alertModalIcon').textContent  = icon  || 'info';
    const close = () => overlay.classList.remove('open');
    ['alertModalOk', 'alertModalClose'].forEach(id => {
      const el = document.getElementById(id);
      const clone = el.cloneNode(true);
      el.replaceWith(clone);
    });
    document.getElementById('alertModalOk').addEventListener('click', close);
    document.getElementById('alertModalClose').addEventListener('click', close);
    overlay.classList.add('open');
  }

  // â”€â”€ Theme â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function setTheme(isDark) {
    const html = document.documentElement;
    html.dataset.theme = isDark ? 'dark' : 'light';
    html.style.colorScheme = isDark ? 'dark' : 'light';
    document.body.classList.toggle('dark-mode', isDark);
    const icon = document.getElementById('themeIcon');
    if (icon) icon.textContent = isDark ? 'dark_mode' : 'light_mode';
    const modeLabel = document.getElementById('themeModeLabel');
    if (modeLabel) modeLabel.textContent = isDark ? 'Oscuro' : 'Claro';
    const gl = document.getElementById('globalLoadingModal');
    if (gl) gl.classList.toggle('dark', isDark);
  }

  function initTheme() {
    const btn   = document.getElementById('btnTheme');
    const saved = (() => { try { return localStorage.getItem('appTheme'); } catch { return null; } })();
    const isDark = saved === 'dark';
    setTheme(isDark);
    if (!btn) return;
    btn.addEventListener('click', () => {
      const next = document.documentElement.dataset.theme !== 'dark';
      try { localStorage.setItem('appTheme', next ? 'dark' : 'light'); } catch {}
      setTheme(next);
    });
  }

  // Fechas por defecto: mes actual
  function initUserMenu() {
    const menu   = document.getElementById('userMenu');
    const toggle = document.getElementById('userMenuToggle');
    if (!menu || !toggle) return;
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      menu.classList.toggle('open');
    });
    document.addEventListener('click', (e) => {
      if (!menu.contains(e.target)) menu.classList.remove('open');
    });
    const dropdown = document.getElementById('userMenuDropdown');
    if (dropdown) dropdown.addEventListener('click', (e) => e.stopPropagation());
  }

  // â”€â”€ Grid font-size controls (persisted) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function applyGridFontSize(px) {
    const val = (typeof px === 'number') ? `${px}px` : px;
    document.documentElement.style.setProperty('--cxc-grid-font-size', val);
    const disp = document.getElementById('currentFontSizeDisplay');
    if (disp) disp.textContent = `${String(val)}`;
  }

  function loadGridFontSize() {
    try {
      const saved = localStorage.getItem('cxcGridFontSize');
      const v = saved ? Number(saved) : 13;
      const n = Math.min(18, Math.max(10, Number(v) || 13));
      applyGridFontSize(n);
      return n;
    } catch (e) { applyGridFontSize(13); return 13; }
  }

  function initFontSizeControls() {
    loadGridFontSize();
    const btnDec = document.getElementById('btnFontDecrease');
    const btnInc = document.getElementById('btnFontIncrease');
    if (btnDec) btnDec.addEventListener('click', () => {
      const cur = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--cxc-grid-font-size')) || 13;
      const next = Math.max(10, cur - 1);
      try { localStorage.setItem('cxcGridFontSize', String(next)); } catch {}
      applyGridFontSize(next);
      try { reloadGrid(); } catch {}
    });
    if (btnInc) btnInc.addEventListener('click', () => {
      const cur = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--cxc-grid-font-size')) || 13;
      const next = Math.min(18, cur + 1);
      try { localStorage.setItem('cxcGridFontSize', String(next)); } catch {}
      applyGridFontSize(next);
      try { reloadGrid(); } catch {}
    });
  }

  function setDefaultDates() {
    const now     = new Date();
    const y       = now.getFullYear();
    const m       = String(now.getMonth() + 1).padStart(2, '0');
    const lastDay = new Date(y, now.getMonth() + 1, 0).getDate();
    const elS = document.getElementById('dateStart');
    const elE = document.getElementById('dateEnd');
    if (elS) elS.value = `${y}-${m}-01`;
    if (elE) elE.value = `${y}-${m}-${String(lastDay).padStart(2, '0')}`;
  }

  // â”€â”€ Filtros â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function getFilters() {
    const _ejec = (FLAGS.CXC_ROLE||'').toLowerCase() === 'auditor'
      ? (FLAGS.CURRENT_EJECUTIVO || '')
      : (document.getElementById('filterEjecutivo')?.value || '');
    return {
      sucursal:     document.getElementById('filterSucursal')?.value    || '',
      ejecutivo:    _ejec,
      cliente:      document.getElementById('filterCliente')?.value     || '',
      recibo:       document.getElementById('filterRecibo')?.value      || '',
      liquidado:    document.getElementById('filterLiquidado')?.value   || '',
      fecha_inicio: document.getElementById('dateStart')?.value         || '',
      fechaFin:    document.getElementById('dateEnd')?.value           || '',
    };
  }

  // â”€â”€ Viewer.js â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  // openViewer removed - now using window.open() to open comprobante in new tab

  // â”€â”€ UI helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function setStatus(msg) {
    // El statusLabel está oculto en CSS &mdash; actualizamos el recordsSummary del paging panel
    const rec = document.getElementById('recordsSummary');
    if (rec) rec.textContent = msg;
    // También actualizamos el status label por si está visible
    const el = document.getElementById('statusLabel');
    if (el) el.textContent = msg;
  }

  function updateTotal() {
    if (!gridApi) return;
    const selected = gridApi.getSelectedRows();
    const total = selected.reduce((acc, r) => acc + (r.Valor_Pagado_Raw || 0), 0);
    const el = document.getElementById('totalCobradoValue');
    if (el) el.textContent = 'L ' + total.toLocaleString('es-HN', {
      minimumFractionDigits: 2, maximumFractionDigits: 2,
    });
  }

  function updateActionButtons() {
    if (!gridApi) return;
    const selected = gridApi.getSelectedRows();
    const n = selected.length;

    if (FLAGS.CAN_LIQUIDAR) {
      const btn = document.getElementById('btnLiquidar');
      if (btn) {
        // Deshabilitar si no hay selección O si algún seleccionado ya está liquidado
        const hayLiquidados = selected.some(r => {
          const v = String(r.liquidado || '').toLowerCase().trim();
          return v === 'si' || v === 's\u00ed';
        });
        btn.disabled = n === 0 || hayLiquidados;
        const icon = btn.querySelector('.material-symbols-rounded');
        btn.innerHTML =
          `${icon ? icon.outerHTML : '<span class="material-symbols-rounded">payments</span>'} ` +
          (n > 0 ? `Liquidar seleccionados (${n})` : 'Liquidar seleccionados');
        btn.title = hayLiquidados ? 'No se puede liquidar registros ya liquidados' : '';
      }
    }

    const btnPrint = document.getElementById('btnPrint');
    if (btnPrint) {
      btnPrint.disabled = n === 0;
      const icon = btnPrint.querySelector('.material-symbols-rounded');
      btnPrint.innerHTML =
        `${icon ? icon.outerHTML : '<span class="material-symbols-rounded">print</span>'} ` +
        (n > 0 ? `Imprimir seleccionados (${n})` : 'Imprimir seleccionados');
    }
  }

  // â”€â”€ Datasource â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function buildDatasource(filters) {
    return {
      getRows(params) {
        const { startRow, endRow } = params;
        const qp = new URLSearchParams({
          start:        startRow,
          length:       endRow - startRow,
          sucursal:     filters.sucursal,
          ejecutivo:    filters.ejecutivo,
          cliente:      filters.cliente,
          recibo:       filters.recibo,
          liquidado:    filters.liquidado,
          fecha_inicio: filters.fecha_inicio,
          fechaFin:    filters.fechaFin,
          sort_col:     currentSort.col,
          sort_dir:     currentSort.dir,
        });

        fetch('/cxc/api/cobros?' + qp.toString())
          .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.json();
          })
          .then(data => {
            const total = data.recordsFiltered;
            setStatus(`${total.toLocaleString('es-HN')} registros encontrados`);
            params.successCallback(data.data, total);
            updateTotal();
          })
          .catch(err => {
            console.error('[CxC] Error /api/cobros:', err);
            setStatus('Error al cargar datos');
            params.failCallback();
          });
      },
    };
  }

  function reloadGrid() {
    if (!gridApi) return;
    syncLiveFilters();
    setStatus('Buscando...');
    gridApi.deselectAll();
    updateTotal();
    updateActionButtons();
    // Resetear el checkbox de "seleccionar página"
    const pageCb = getPageSelectCb();
    if (pageCb) { pageCb.checked = false; pageCb.indeterminate = false; }
    gridApi.setGridOption('datasource', buildDatasource(getFilters()));
  }

  // â”€â”€ Select-all página actual â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  //
  // AG Grid infinite row model NO soporta headerCheckbox nativo.
  // Inyectamos un <input type="checkbox"> propio dentro de la cabecera de la
  // columna de selección (pinned left) y lo manejamos manualmente.

  function getPageSelectCb() {
    return document.querySelector('#cobrosGrid .page-sel-cb');
  }

  // Devuelve todos los rowNodes de la página actual
  function getSelectableRenderedNodes() {
    if (!gridApi) return [];
    const page     = gridApi.paginationGetCurrentPage();   // 0-based
    const pageSize = gridApi.paginationGetPageSize();
    const startIdx = page * pageSize;
    const endIdx   = startIdx + pageSize;
    const nodes = [];
    for (let i = startIdx; i < endIdx; i++) {
      const node = gridApi.getDisplayedRowAtIndex(i);
      if (!node) break;                          // fin de datos
      if (node.data) nodes.push(node);
    }
    return nodes;
  }

  function syncPageSelectCheckbox() {
    const cb = getPageSelectCb();
    if (!cb) return;
    const nodes = getSelectableRenderedNodes();
    if (!nodes.length) { cb.checked = false; cb.indeterminate = false; return; }
    const sel = nodes.filter(n => n.isSelected()).length;
    if (sel === 0)           { cb.checked = false; cb.indeterminate = false; }
    else if (sel === nodes.length) { cb.checked = true;  cb.indeterminate = false; }
    else                     { cb.checked = false; cb.indeterminate = true; }
  }

  function injectPageSelectCheckbox() {
    if (!gridApi) return;
    // El header de la columna de selección está en la sección pinned-left
    const headerCell = document.querySelector(
      '#cobrosGrid .ag-pinned-left-header .ag-header-cell'
    );
    if (!headerCell) return;
    if (headerCell.querySelector('.page-sel-cb')) return; // ya inyectado

    const cb = document.createElement('input');
    cb.type      = 'checkbox';
    cb.className = 'page-sel-cb';
    cb.title     = 'Marcar / desmarcar todos los registros de esta página';

    // Vaciar el wrapper y colocar nuestro checkbox centrado
    const wrapper = headerCell.querySelector('.ag-header-cell-comp-wrapper') || headerCell;
    wrapper.innerHTML = '';
    wrapper.style.cssText = 'display:flex;align-items:center;justify-content:center;height:100%';
    wrapper.appendChild(cb);

    cb.addEventListener('change', () => {
      const nodes = getSelectableRenderedNodes();
      nodes.forEach(n => n.setSelected(cb.checked));
    });
  }

  // â”€â”€ AG Grid config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function initGrid() {

    const columnDefs = [
      // La columna de checkboxes ya NO va aquí &mdash; se declara en selectionColumnDef
      { field: 'codigoCliente', headerName: 'Código', width: 120, sortable: true,
        cellRenderer: (params) => highlightCell(params.value, liveFilters.cliente) },
      { field: 'nombreCliente', headerName: 'Nombre Cliente', minWidth: 171, flex: 1.026, sortable: true,
        cellRenderer: (params) => highlightCell(params.value, liveFilters.cliente) },
      { field: 'noFactura',     headerName: 'No. Factura',    minWidth: 126, flex: 0.722, sortable: true },
      { field: 'valorPagado',   headerName: 'Valor Pagado',   width: 170, sortable: true,
        cellStyle: { textAlign: 'right' } },
      { field: 'noRecibo',      headerName: 'No. Recibo',     width: 120, sortable: true,
        cellRenderer: (params) => highlightCell(params.value, liveFilters.recibo) },
      { field: 'creado',         headerName: 'Creado',         width: 180, sortable: true, sort: 'desc' },
      {
        field: 'liquidado',
        headerName: 'Liquidado',
        width: 130,
        sortable: true,
        cellRenderer: (params) => {
          if (!params.value) return '<span class="badge-liquidado badge-liq-no"><span class="badge-icon">&#x2715;</span>No</span>';
          const v = String(params.value || '').toLowerCase().trim();
          if (v === 'si' || v === 'sí')
            return '<span class="badge-liquidado badge-liq-si"><span class="badge-icon">&#x2713;</span>Sí</span>';
          return `<span class="badge-liquidado">${params.value}</span>`;
        },
      },
      {
        field: 'estado_cobro',
        headerName: 'Estado',
        width: 145,
        sortable: false,
        cellRenderer: (params) => {
          const v = params.value || 'Recibido';
          if (v === 'Finalizado')
            return '<span class="badge-liquidado badge-liq-si"><span class="material-symbols-rounded" style="font-size:13px;line-height:1">check_circle</span>Finalizado</span>';
          if (v === 'Procesado')
            return '<span class="badge-liquidado badge-estado-procesado"><span class="material-symbols-rounded" style="font-size:13px;line-height:1">pending</span>Procesado</span>';
          return '<span class="badge-liquidado badge-estado-recibido"><span class="material-symbols-rounded" style="font-size:13px;line-height:1">schedule</span>Recibido</span>';
        },
      },
      {
        colId: 'comprobante',
        headerName: 'Comprobante',
        width: 140,
        sortable: false,
        resizable: false,
        cellRenderer: (params) => {
          if (!params.data || !params.data.tieneComprobante) return '<span class="badge-no-comp">&mdash;</span>';
          return `<button class="btn-ver-img" title="Ver comprobante"
                          data-img="/cxc/comprobante/${params.data.spItemId}"
                          data-id="${params.data.spItemId}">
                    <span class="material-symbols-rounded">image</span>
                    <span>Ver</span>
                  </button>`;
        },
      },
      {
        colId: 'detalles',
        headerName: 'Detalles',
        width: 110,
        sortable: false,
        resizable: false,
        cellRenderer: (params) => {
          if (!params.data) return '';
            return `<button class="btn-detalles" data-id="${params.data.spItemId}" title="Ver detalles">
                      <span class="material-symbols-rounded" aria-hidden="true">open_in_new</span>
                    </button>`;
        },
      },
    ];

    const gridOptions = {
      columnDefs,

      // â”€â”€ Row model â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      rowModelType:   'infinite',
      cacheBlockSize: PAGE_SIZE_DEFAULT,
      maxBlocksInCache: 0,

      // â”€â”€ Paginación â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      pagination:              true,
      paginationPageSize:      PAGE_SIZE_DEFAULT,
      paginationPageSizeSelector: [100, 200, 500, 1000, 10000],

      // â”€â”€ Selección &mdash; API v32.2+ (sin deprecated warnings) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      //
      //   rowSelection.mode: 'multiRow'  â†’  antes: rowSelection: 'multiple'
      //   rowSelection.checkboxes: true  â†’  antes: checkboxSelection en colDef
      //   rowSelection.headerCheckbox: false  â†’  headerCheckbox NO soportado
      //                                           en infinite row model
      //   rowSelection.enableClickSelection: true   â†’  antes: suppressRowClickSelection: false
      //   rowSelection.enableSelectionWithoutKeys: true â†’ antes: rowMultiSelectWithClick: true
      //   rowSelection.isRowSelectable: fn  â†’  antes: isRowSelectable en gridOptions
      //
      rowSelection: {
        mode:                      'multiRow',
        checkboxes:                true,
        headerCheckbox:            false,     // NO soportado en infinite row model
        enableClickSelection:      true,
        enableSelectionWithoutKeys: true,
        // Todos los registros son seleccionables (incluido liquidado=Si)
        isRowSelectable:           (rowNode) => !!rowNode.data,
      },

      // â”€â”€ Columna de checkbox (reemplaza colDef manual "sel") â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
      selectionColumnDef: {
        width:           52,
        minWidth:        52,
        maxWidth:        52,
        pinned:          'left',
        resizable:       false,
        suppressMovable: true,
      },

      getRowId: (params) => String(params.data.spItemId),
      animateRows: false,

      defaultColDef: {
        resizable:      true,
        sortable:       true,
        filter:         false,
        wrapHeaderText: true,
      },

      localeText: {
        loadingOoo:   'Cargando...',
        noRowsToShow: 'Sin registros',
        page:         'Página',
        to:           'a',
        of:           'de',
        nextPage:     'Siguiente',
        lastPage:     'Última',
        firstPage:    'Primera',
        previousPage: 'Anterior',
      },

      onGridReady: (params) => {
        gridApi = params.api;
        gridApi.setGridOption('datasource', buildDatasource(getFilters()));
        enhanceAgGridPageSizeSelect(gridApi);
        // Inyectar el checkbox de selección de página después de que AG Grid
        // termine de renderizar su DOM de cabecera
        setTimeout(injectPageSelectCheckbox, 120);
      },

      onSelectionChanged: () => {
        updateActionButtons();
        updateTotal();
        syncPageSelectCheckbox();
      },

      onPaginationChanged: () => {
        updateTotal();
        // Al cambiar de página desmarcar el checkbox (los nodos cambian)
        const cb = getPageSelectCb();
        if (cb) { cb.checked = false; cb.indeterminate = false; }
        // Re-inyectar por si AG Grid re-renderizó el header
        setTimeout(injectPageSelectCheckbox, 80);
      },

      // Sort server-side: captura el cambio y recarga el datasource
      onSortChanged: (params) => {
        const sorted = params.api.getColumnState().filter(c => c.sort);
        if (sorted.length > 0) {
          currentSort = {
            col: sorted[0].colId,
            dir: String(sorted[0].sort).toUpperCase(),
          };
        } else {
          currentSort = { col: 'creado', dir: 'DESC' };
        }
        reloadGrid();
      },
    };

    agGrid.createGrid(document.getElementById('cobrosGrid'), gridOptions);

    // Delegación de click para botones "Ver" de comprobante y "Detalles"
    document.getElementById('cobrosGrid')?.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-ver-img');
      if (btn) {
        const itemId = btn.dataset.id;
        // Abrir directamente — el servidor hace redirect 302 a la URL real de SharePoint
        window.open(`/cxc/comprobante/${itemId}`, '_blank');
      }

      const det = e.target.closest('.btn-detalles');
      if (det) {
        const rowNode = gridApi.getRowNode(det.dataset.id);
        if (rowNode?.data) openDetallesModal(rowNode.data);
      }
    });
  }

  // â”€â”€ Ampliar selector de paginación â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function enhanceAgGridPageSizeSelect(api) {
    setTimeout(() => {
      const panel = document.querySelector('.ag-paging-panel');
      if (!panel) return;
      const sel = panel.querySelector('select');
      if (!sel) return;

      // Insertar resumen de registros a la izquierda del select
      if (!panel.querySelector('#recordsSummary')) {
        const el = document.createElement('div');
        el.id          = 'recordsSummary';
        el.className   = 'records-summary';
        el.style.cssText = 'margin-right:8px;font-size:13px;color:var(--muted)';
        sel.parentNode.insertBefore(el, sel);
      }

      sel.addEventListener('change', (e) => {
        const newSize = Number(e.target.value) || PAGE_SIZE_DEFAULT;
        api.setGridOption('cacheBlockSize', newSize);
        try { api.paginationSetPageSize(newSize); } catch {}
        reloadGrid();
      });
    }, 200);
  }

  // â”€â”€ Modal Detalles â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function openDetallesModal(data) {
    const modal = document.getElementById('detallesModal');
    const body  = document.getElementById('detallesModalBody');
    if (!modal || !body) return;

    // Colorear icono: verde si liquidado, rojo si no
    const iconEl = document.getElementById('detModalIcon');
    if (iconEl) {
      iconEl.style.color = data.liquidado_bool ? '#22c55e' : '#ef4444';
    }

    const fields = [
      { label: 'Código Cliente',       value: data.codigoCliente },
      { label: 'Nombre Cliente',       value: data.nombreCliente },
      { label: 'banco',                value: data.banco },
      { label: 'Método Pago',          value: data.metodoPago },
      { label: 'No. Factura',          value: data.noFactura },
      { label: 'Valor Pagado',         value: data.valorPagado },
      { label: 'No. Recibo',           value: data.noRecibo },
      { label: 'creado',               value: data.creado },
      { label: 'ejecutivo',            value: data.ejecutivo },
      { label: 'sucursal',             value: data.sucursal },
      { label: 'Fecha Cheque',         value: data.fechaCheque },
    ];

    // Split Comentario Adicional into ejecutivo / Liquidador (visually)
    const rawComentario = data.comentarioAdicional || '';
    const splitMarker = rawComentario.indexOf('\n') !== -1 ? '\n' : (rawComentario.indexOf('||') !== -1 ? '||' : null);
    if (splitMarker !== null) {
      const splitIdx = rawComentario.indexOf(splitMarker);
      fields.push({ label: 'Comentario ejecutivo',  value: rawComentario.substring(0, splitIdx).trim() || null });
      fields.push({ label: 'Comentario Liquidador', value: rawComentario.substring(splitIdx + splitMarker.length).trim() || null });
    } else {
      fields.push({ label: 'Comentario ejecutivo', value: rawComentario || null });
      fields.push({ label: 'Comentario Liquidador', value: null });
    }

    fields.push(
      { label: 'liquidado',            value: data.liquidado },
      { label: 'liquidado Por',        value: data.liquidadoPor },
      { label: 'Fecha liquidado',      value: data.fechaLiquidado },
    );

    body.innerHTML = fields.map(f => `
      <div class="det-row">
        <span class="det-label">${f.label}</span>
        <span class="det-value">${(f.value != null && f.value !== '') ? f.value : '<em class="det-empty">&mdash;</em>'}</span>
      </div>`).join('');

    // Badge de PDF en el header si el registro está liquidado
    const headerBadge = document.getElementById('detModalBadge');
    if (headerBadge) {
      headerBadge.innerHTML = '';

      if (data.liquidado_bool) {
        // Mostrar badge inmediatamente, sin esperar a la BD
        headerBadge.innerHTML = `
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="display:inline-flex;align-items:center;gap:5px;
              background:#dcfce7;color:#166534;border:1px solid #86efac;
              border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600;">
              <span class="material-symbols-rounded" style="font-size:15px;">payments</span>
              liquidado: S&iacute;
            </span>
          </div>`;

        // Si hay número de recibo, verificar si existe PDF guardado
        if (data.noRecibo) {
          fetch(`/cxc/liquidacion/pdf-info/${encodeURIComponent(data.noRecibo)}`, { credentials: 'same-origin' })
            .then(r => r.json())
            .then(info => {
              if (!info.found) return;
              const fileId   = info.spFileId   || '';
              const fileName = info.spFileName || 'liquidacion.pdf';
              const dlUrl    = info.spDownloadUrl || '';
              const badgeDiv = document.getElementById('detModalBadge');
              if (!badgeDiv) return;
              // Actualizar la etiqueta con la fecha del PDF
              const span = badgeDiv.querySelector('span:first-child');
              if (span) span.innerHTML = `
                <span class="material-symbols-rounded" style="font-size:15px;">payments</span>
                liquidado: S&iacute; &mdash; PDF ${info.fecha ? info.fecha.split('T')[0] : ''}`;
              // Agregar botón visor si hay fileId
              if (fileId) {
                const btn = document.createElement('button');
                btn.style.cssText = 'display:inline-flex;align-items:center;gap:4px;background:#eff6ff;color:#1d4ed8;border:1px solid #93c5fd;border-radius:20px;padding:3px 10px;font-size:11px;font-weight:600;cursor:pointer;';
                btn.innerHTML = `<span class="material-symbols-rounded" style="font-size:15px;">picture_as_pdf</span> ${fileName}`;
                btn.onclick = () => cxcOpenPDFViewer(encodeURIComponent(fileId), fileName, dlUrl);
                badgeDiv.querySelector('div').appendChild(btn);
              }
            })
            .catch(() => {});
        }
      }
    }

    modal.classList.add('open');
  }

  // â”€â”€ Acciones â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function initActions() {
    document.getElementById('btnVerProcesados')?.addEventListener('click', openProcesadosModal);
    document.getElementById('btnVerFinalizados')?.addEventListener('click', toggleFinalizadosView);
    document.getElementById('btnVolverCobros')?.addEventListener('click', toggleFinalizadosView);

    // â”€â”€ Modal Detalles &mdash; cerrar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    const detallesModal = document.getElementById('detallesModal');
    document.getElementById('btnCloseDetalles')?.addEventListener('click', () => {
      detallesModal?.classList.remove('open');
    });
    detallesModal?.addEventListener('click', (e) => {
      if (e.target === detallesModal) detallesModal.classList.remove('open');
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') detallesModal?.classList.remove('open');
    });

    document.getElementById('btnLimpiar')?.addEventListener('click', () => {
      ['filterSucursal', 'filterEjecutivo', 'filterCliente', 'filterRecibo', 'filterLiquidado'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
      });
      setDefaultDates();
      currentSort = { col: 'creado', dir: 'DESC' };
      // Restaurar ejecutivo para auditores después de limpiar
      if ((FLAGS.CXC_ROLE||'').toLowerCase() === 'auditor' && FLAGS.CURRENT_EJECUTIVO) {
        const elEj = document.getElementById('filterEjecutivo');
        if (elEj) elEj.value = FLAGS.CURRENT_EJECUTIVO;
      }
      reloadCurrentView();
    });

    ['filterCliente', 'filterRecibo'].forEach(id => {
      document.getElementById(id)?.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') { syncLiveFilters(); reloadCurrentView(); }
      });
      // Búsqueda en vivo: debounce 400 ms al escribir
      document.getElementById(id)?.addEventListener('input', () => debounceReload(400));
    });

    // ── Cargar dinámicamente ejecutivos cuando cambia la sucursal ──────────────
    const filterSucursalEl = document.getElementById('filterSucursal');
    if (filterSucursalEl) {
      filterSucursalEl.addEventListener('change', async () => {
        const sucursal = filterSucursalEl.value;
        if (sucursal) {
          // Cargar ejecutivos de esta sucursal
          try {
            const resp = await fetch(`/cxc/api/ejecutivos-por-sucursal?sucursal=${encodeURIComponent(sucursal)}`);
            if (resp.ok) {
              const ejecutivos = await resp.json();
              
              // Actualizar el select de ejecutivos
              const filterEjecutivoEl = document.getElementById('filterEjecutivo');
              if (filterEjecutivoEl) {
                const currentValue = filterEjecutivoEl.value;
                filterEjecutivoEl.innerHTML = '<option value="">Todos</option>';
                
                if (Array.isArray(ejecutivos)) {
                  ejecutivos.forEach(ej => {
                    const opt = document.createElement('option');
                    opt.value = ej;
                    opt.textContent = ej;
                    filterEjecutivoEl.appendChild(opt);
                  });
                }
                
                // Mantener selección anterior si sigue disponible, sino limpiar
                if (currentValue && ejecutivos.includes(currentValue)) {
                  filterEjecutivoEl.value = currentValue;
                } else {
                  filterEjecutivoEl.value = '';
                }
              }
            }
          } catch (err) {
            console.error('[CxC] Error cargando ejecutivos:', err);
          }
        } else {
          // Si se selecciona "Todas", recargar todos los ejecutivos
          location.reload();
        }
        
        // Recargar la vista con la sucursal seleccionada
        reloadCurrentView();
      });
    }

    // Selects dinámicos: recargar al cambiar
    ['filterEjecutivo', 'filterLiquidado'].forEach(id => {
      document.getElementById(id)?.addEventListener('change', () => reloadCurrentView());
    });
    ['dateStart', 'dateEnd'].forEach(id => {
      document.getElementById(id)?.addEventListener('change', () => reloadCurrentView());
    });

    document.getElementById('btnRefresh')?.addEventListener('click', reloadGrid);

    // â”€â”€ Liquidar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if (FLAGS.CAN_LIQUIDAR) {
      document.getElementById('btnLiquidar')?.addEventListener('click', () => {
        const selected = gridApi?.getSelectedRows() || [];
        if (!selected.length) return;

        // Bloquear si hay registros ya liquidados en la selección
        const yaLiquidados = selected.filter(r => {
          const v = String(r.liquidado || '').toLowerCase().trim();
          return v === 'si' || v === 'sí';
        });
        if (yaLiquidados.length) {
          showAlert(
            `No es posible realizar la liquidación.\n\n` +
            `${yaLiquidados.length} registro(s) seleccionado(s) ya están liquidados.\n` +
            `Deselecciona los registros liquidados e intenta nuevamente.`,
            'Liquidación no permitida',
            'block'
          );
          return;
        }

        showConfirm(
          `¿Liquidar ${selected.length} registro(s) seleccionado(s)?`,
          () => {
            fetch('/cxc/liquidar', {
              method:  'POST',
              headers: { 'Content-Type': 'application/json' },
              body:    JSON.stringify({ item_ids: selected.map(r => String(r.spItemId)) }),
            })
              .then(r => r.json())
              .then(data => {
                if (data.status === 'ok') {
                  let msg = `Liquidación aplicada.\nActualizados: ${data.actualizados}\nErrores: ${data.errores}`;
                  if (data.errores_detalle?.length)
                    msg += '\n\nDetalle:\n- ' + data.errores_detalle.join('\n- ');
                  showAlert(msg, 'Liquidación completada', 'check_circle');
                  gridApi.deselectAll();
                  reloadGrid();
                } else {
                  showAlert('Error: ' + (data.message || 'Error desconocido.'), 'Error', 'error');
                }
              })
              .catch(err => showAlert('Error al liquidar: ' + err, 'Error', 'error'));
          },
          null, 'Liquidar registros', 'payments'
        );
      });
    }

    document.getElementById('btnPrint')?.addEventListener('click', () => {
      const selected = gridApi?.getSelectedRows() || [];
      if (!selected.length) {
        showAlert('Seleccione al menos un registro para imprimir.', 'Sin selección', 'print_disabled');
        return;
      }

      const total = selected.reduce((acc, r) => acc + (r.Valor_Pagado_Raw || 0), 0);
      const totalFmt = 'L ' + total.toLocaleString('es-HN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      const nombres = [...new Set(selected.map(r => r.ejecutivo).filter(Boolean))].join(', ') || '\u2014';

      // Detectar si algún registro ya está liquidado, procesado o finalizado
      const hayNonRecibido = selected.some(r => {
        const est = (r.estado_cobro || '').trim();
        const liq = (r.liquidado || '').trim().toLowerCase();
        return (liq === 'si' || liq === 'sí') || est === 'Finalizado' || est === 'Procesado';
      });

      if (hayNonRecibido) {
        const cntNR = selected.filter(r => {
          const est = (r.estado_cobro || '').trim();
          const liq = (r.liquidado || '').trim().toLowerCase();
          return (liq === 'si' || liq === 'sí') || est === 'Finalizado' || est === 'Procesado';
        }).length;
        showConfirm(
          `Atención: ${cntNR} registro(s) ya están Liquidados.\n\n` +
          `Se generará un PDF de control únicamente.\n` +
          `NO se registrará una nueva liquidación ni se subirá el archivo a la nube.\n\n` +
          `Registros seleccionados: ${selected.length}\nTotal: ${totalFmt}`,
          () => _doGenerateLiqPDF(selected, true),
          null,
          'Generación de PDF',
          'description'
        );
      } else {
        showConfirm(
          `¿Estás seguro de proceder con la liquidación?\n\n` +
          `Registros seleccionados: ${selected.length}\n` +
          `ejecutivo(s): ${nombres}\n` +
          `Total: ${totalFmt}\n\n` +
          `Se generará el PDF y quedará registrado como una nueva Liquidación.`,
          () => _doGenerateLiqPDF(selected, false),
          null,
          'Comenzar Liquidación',
          'receipt_long'
        );
      }
    });

    async function _doGenerateLiqPDF(selected, isControlOnly = false) {
      // ── VALIDACIÓN: Asegurar que tenemos los datos necesarios ───────────────
      if (!selected || !selected.length) {
        showAlert('Error: No hay registros seleccionados. Por favor intenta de nuevo.', 'Sin registros', 'error');
        return;
      }

      const rows = selected.map(r => ({
        'Código cliente':       r.codigoCliente       || '',
        'Nombre cliente':       r.nombreCliente       || '',
        'Método pago':          r.metodoPago          || '',
        'No. Factura':          r.noFactura           || '',
        'Valor Pagado':         r.valorPagado         || '',
        'No. Recibo':           r.noRecibo            || '',
        'liquidado':            r.liquidado            || '',
        'fechaCheque':         r.fechaCheque         || '',
        'Comentario adicional': r.comentarioAdicional || '',
        'creado':               r.creado               || '',
        'estado_cobro':         r.estado_cobro         || '',
      }));

      const sp_item_ids = selected.map(r => String(r.spItemId)).filter(id => id && id !== 'undefined');
      
      // ── VALIDACIÓN: Asegurar que tenemos IDs de SharePoint válidos ──────────
      if (!isControlOnly && sp_item_ids.length === 0) {
        showAlert(
          'Error: No fue posible obtener los IDs de los registros. Por favor recarga la página e intenta de nuevo.',
          'Registros inválidos',
          'error'
        );
        return;
      }

      const payload = {
        ejecutivo:    [...new Set(selected.map(r => r.ejecutivo).filter(Boolean))][0] || '',
        fecha_inicio: document.getElementById('dateStart')?.value || '',
        fechaFin:    document.getElementById('dateEnd')?.value   || '',
        sp_item_ids:  sp_item_ids,
        is_control_only: isControlOnly,
        rows,
      };

      showLoading(isControlOnly ? 'Generando PDF de control...' : 'Generando liquidación...');
      try {
        const resp = await fetch('/cxc/liquidar/pdf-html', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify(payload),
        });
        hideLoading();

        if (!resp.ok) {
          const txt = await resp.text();
          showAlert('Error al generar PDF: ' + txt, 'Error', 'error');
          return;
        }

        const ct = (resp.headers.get('content-type') || '').toLowerCase();
        if (ct.includes('application/pdf')) {
          const loteId  = resp.headers.get('X-Lote-Id') || '';
          const numLiq  = resp.headers.get('X-Numero-Liq') || '';
          const blob    = await resp.blob();
          const blobUrl = URL.createObjectURL(blob);
          const pdfName = isControlOnly ? 'control_liquidacion.pdf' : (numLiq ? numLiq + '.pdf' : 'liquidacion.pdf');
          if (isControlOnly || !loteId) {
            cxcOpenPDFViewer('', pdfName, blobUrl, blobUrl);
          } else {
            _liqOpenDocsModal(1, loteId, numLiq, blobUrl);
          }
          gridApi.deselectAll();
          if (!isControlOnly) setTimeout(reloadGrid, 600);
        }
      } catch (err) {
        hideLoading();
        showAlert('Error al generar liquidación: ' + err, 'Error', 'error');
      }
    }

    // â”€â”€ Sync manual (SuperAdmin) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if (FLAGS.IS_SUPERADMIN) {
      function _executeSyncMode(mode) {
        const overlay = document.getElementById('syncChoiceModal');
        if (overlay) overlay.classList.remove('open');
        
        let modeLabel, endpoint;
        if (mode === 'update_all') {
          modeLabel = 'Actualizando registros';
          endpoint = '/cxc/api/sync';
        } else if (mode === 'fill_blanks') {
          modeLabel = 'Llenando campos en blanco';
          endpoint = '/cxc/api/sync-fill-blanks';
        } else {
          modeLabel = 'Cargando nuevos registros';
          endpoint = '/cxc/api/sync';
        }
        
        setStatus(modeLabel + '...');
        showLoading(modeLabel + '...');
        
        const fetchBody = mode === 'fill_blanks' ? {} : { mode };
        
        fetch(endpoint, {
          method:  'POST',
          headers: {'Content-Type': 'application/json'},
          body:    JSON.stringify(fetchBody),
        })
          .then(r => r.json())
          .then(data => {
            hideLoading();
            if (data.status === 'ok') {
              let lines = [];
              if (mode === 'fill_blanks') {
                lines = [
                  `Consultados en SP: ${data.fetched_from_sp}`,
                  `Campos llenados: ${data.updated_blank_fields}`,
                ];
              } else {
                lines = [
                  `Consultados en SP: ${data.fetched_from_sp}`,
                  `Insertados: ${data.inserted}`,
                ];
                if (data.updated > 0) lines.push(`Actualizados: ${data.updated}`);
                if (data.skipped > 0) lines.push(`Omitidos (ya existían): ${data.skipped}`);
              }
              showAlert(lines.join('\n'), 'Sincronización completada', 'sync');
              clearSyncBadge();  // ← LIMPIAR BADGE después del sync manual
              fetchSyncInfo();
              reloadGrid();
            } else {
              showAlert('Error en sync: ' + (data.message || ''), 'Error de sync', 'error');
              setStatus('Error en sync');
            }
          })
          .catch(err => { hideLoading(); showAlert('Error: ' + err, 'Error', 'error'); setStatus('Error'); });
      }

      document.getElementById('btnSync')?.addEventListener('click', () => {
        const overlay = document.getElementById('syncChoiceModal');
        if (!overlay) { _executeSyncMode('load_new'); return; }
        // Wire choice buttons (clone to remove previous listeners)
        ['syncBtnUpdateAll', 'syncBtnLoadNew', 'syncBtnFillBlanks', 'syncChoiceClose', 'syncChoiceCancel'].forEach(id => {
          const el = document.getElementById(id);
          if (!el) return;
          const clone = el.cloneNode(true);
          el.replaceWith(clone);
        });
        document.getElementById('syncBtnUpdateAll')?.addEventListener('click', () => _executeSyncMode('update_all'));
        document.getElementById('syncBtnLoadNew')?.addEventListener('click',   () => _executeSyncMode('load_new'));
        document.getElementById('syncBtnFillBlanks')?.addEventListener('click', () => _executeSyncMode('fill_blanks'));
        document.getElementById('syncChoiceClose')?.addEventListener('click',  () => overlay.classList.remove('open'));
        document.getElementById('syncChoiceCancel')?.addEventListener('click', () => overlay.classList.remove('open'));
        overlay.classList.add('open');
      });
    }
  }

  // â”€â”€ Chip de sync â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  let prevSyncDate = null;
  let _badgeCount = 0;

  function fetchSyncInfo() {
    fetch('/cxc/api/last-sync')
      .then(r => r.json())
      .then(data => {
        const dateEl  = document.getElementById('syncDateValue');

        if (data.lastSync) {
          // A veces el servidor devuelve ISO sin indicación de zona.
          // Asegurarnos de que Date lo interprete en UTC añadiendo 'Z' si falta.
          let raw = String(data.lastSync || '');
          if (!raw.match(/[Zz]|[+\-]\d{2}:?\d{2}$/)) raw = raw + 'Z';
          const d   = new Date(raw);
          const pad = (n) => String(n).padStart(2, '0');
          if (dateEl)
            dateEl.textContent =
              `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ` +
              `${pad(d.getHours())}:${pad(d.getMinutes())}`;

          // ── OPCIÓN C CON BADGE: Mostrar "datos nuevos" sin refrescar tabla ────
          if (prevSyncDate && prevSyncDate !== data.lastSync) {
            // Hay datos nuevos en SharePoint
            // En lugar de: reloadGrid();
            // Actualizar badge:
            updateSyncBadge(data.last_inserted || 0);
          }
        } else {
          if (dateEl) dateEl.innerHTML = '&mdash; (sin ejecutar)';
        }
        prevSyncDate = data.lastSync;
      })
      .catch(() => {
        const el = document.getElementById('syncDateValue');
        if (el) el.textContent = 'Error';
      });
  }

  // ── Nueva función: actualizar badge de nuevos registros ──────────────────────
  function updateSyncBadge(count) {
    const badge = document.getElementById('syncBadge');
    if (!badge) return;
    
    _badgeCount = (count || 0);
    
    if (_badgeCount > 0) {
      // Mostrar badge con el número de registros nuevos
      const displayCount = _badgeCount > 99 ? '99+' : `+${_badgeCount}`;
      badge.textContent = displayCount;
      badge.setAttribute('data-tooltip', `${_badgeCount} nuevos registros disponibles`);
      badge.classList.add('active');
      badge.style.display = 'inline-flex';
      
      // Log
      console.log(`[CxC] Badge actualizado: ${_badgeCount} nuevos registros`);
    }
  }

  // Función para limpiar el badge cuando el usuario hace clic en Sync
  function clearSyncBadge() {
    const badge = document.getElementById('syncBadge');
    if (!badge) return;
    badge.style.display = 'none';
    badge.classList.remove('active');
    _badgeCount = 0;
    // Resetear prevSyncDate para que fetchSyncInfo() no vuelva a mostrar el badge
    // inmediatamente después del sync manual
    prevSyncDate = null;
  }

  // Hacer clickable el chip de sync para forzar actualización inmediata
  document.addEventListener('click', (e) => {
    const chip = e.target.closest('.sync-info-chip');
    if (!chip) return;
    // Mostrar un feedback corto
    setStatus('Actualizando estado de sync...');
    clearSyncBadge();
    fetchSyncInfo();
    // También recargar la grilla (mismo efecto que el botón "Actualizar")
    reloadGrid();
  });

  // â”€â”€ Boot â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  // ── Filtros toggle (mobile) ─────────────────────────────────────────────
  function initMobileFiltersToggle() {
    const filtersEl = document.getElementById('filtersSection');
    const btnToggle = document.getElementById('btnToggleFiltros');
    if (!filtersEl || !btnToggle) return;

    const isPortraitMobile = () => window.innerWidth <= 480;
    const isLandscape      = () => window.innerHeight <= 500;

    function applyDefaults() {
      if (isLandscape()) {
        // Landscape: CSS oculta filtros; solo asegurar que no hay clase open
        document.body.classList.remove('mobile-filters-open');
        return;
      }
      if (isPortraitMobile()) {
        // Portrait mobile: filtros ocultos por defecto
        filtersEl.classList.add('filters--hidden');
        document.body.classList.remove('mobile-filters-open');
        btnToggle.querySelector('.material-symbols-rounded').textContent = 'filter_alt';
        btnToggle.classList.remove('filters-open');
      } else {
        // Desktop: siempre visibles
        filtersEl.classList.remove('filters--hidden');
        document.body.classList.remove('mobile-filters-open');
      }
    }

    btnToggle.addEventListener('click', () => {
      if (!isPortraitMobile()) return;
      const nowHidden = filtersEl.classList.toggle('filters--hidden');
      document.body.classList.toggle('mobile-filters-open', !nowHidden);
      btnToggle.querySelector('.material-symbols-rounded').textContent =
        nowHidden ? 'filter_alt' : 'filter_alt_off';
      btnToggle.classList.toggle('filters-open', !nowHidden);
    });

    applyDefaults();
    window.addEventListener('resize', applyDefaults);
  }

  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initUserMenu();
    initFontSizeControls();
    setDefaultDates();
    // Pre-cargar ejecutivo para auditores antes de inicializar grid
    if ((FLAGS.CXC_ROLE||'').toLowerCase() === 'auditor' && FLAGS.CURRENT_EJECUTIVO) {
      const elEj = document.getElementById('filterEjecutivo');
      if (elEj) elEj.value = FLAGS.CURRENT_EJECUTIVO;
    }
    initGrid();
    initActions();
    initMobileFiltersToggle();
    fetchSyncInfo();
    setInterval(fetchSyncInfo, 65_000);
  });

  // Exponer modales globalmente (accesibles desde onclick= handlers fuera del IIFE)
  window.showConfirm  = showConfirm;
  window.showAlert    = showAlert;
  window.showLoading  = showLoading;
  window.hideLoading  = hideLoading;
  window.getFilters   = getFilters;

})();

/* â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   Visor PDF de Liquidaciones &mdash; funciones globales (accesibles desde onclick)
   â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â• */

// Estado del visor
var _cxcPdfDoc       = null;
var _cxcScale        = 1.0;
var _cxcRotation     = 0; // Rotación en grados (0, 90, 180, 270)
var _cxcCurrentPage  = 1;
var _cxcPageRendering = false;
var _cxcPagePending  = null;
var _cxcPdfUrl       = null;
var _cxcPdfFileName  = null;
var _cxcZoomRaf      = null;

/**
 * Abre el visor interno mostrando el PDF de liquidación.
 * fileId: file ID de SharePoint (URL-encoded) ó URL directa de descarga
 * fileName: nombre del archivo para mostrar en la cabecera
 * directDlUrl: URL directa de descarga de OneDrive (opcional, más rápida)
 */
async function cxcOpenPDFViewer(fileId, fileName, directDlUrl, blobUrl) {
  try {
    _cxcPdfFileName = decodeURIComponent(fileName || 'liquidacion.pdf');

    // Construir URL de carga: blob > URL directa OneDrive > endpoint proxy
    if (blobUrl && blobUrl.startsWith('blob:')) {
      _cxcPdfUrl = blobUrl;
    } else if (directDlUrl && (directDlUrl.startsWith('https://') || directDlUrl.startsWith('/'))) {
      _cxcPdfUrl = directDlUrl;
    } else if (fileId) {
      _cxcPdfUrl = `/cxc/liquidacion/download/${fileId}?name=${encodeURIComponent(_cxcPdfFileName)}`;
    } else {
      console.warn('cxcOpenPDFViewer: no fileId ni directDlUrl ni blobUrl');
      return;
    }

    // Mostrar modal y resetear contenedor de páginas
    const modal  = document.getElementById('cxcPDFModal');
    const pages  = document.getElementById('cxcPDFPages');
    const title  = document.getElementById('cxcPDFTitle');
    if (!modal) return;

    showLoading('Cargando PDF, por favor espera...');
    if (pages) pages.innerHTML = '';
    _cxcScale = 1.0;
    _cxcRotation = 0; // Resetear rotación
    cxcUpdateZoomUI(100);
    modal.classList.add('active');
    if (title) title.textContent = _cxcPdfFileName;

    // Cargar PDF.js si no está disponible
    if (typeof window.pdfjsLib === 'undefined') {
      await cxcLoadPdfJs();
    }

    await cxcLoadPDF(_cxcPdfUrl);
    hideLoading();
  } catch (err) {
    hideLoading();
    console.error('cxcOpenPDFViewer error:', err);
    alert('No se pudo cargar el PDF: ' + (err && err.message ? err.message : err));
    cxcClosePDFModal();
  }
}

/** Cierra el visor de PDF */
function cxcClosePDFModal() {
  const modal = document.getElementById('cxcPDFModal');
  if (modal) modal.classList.remove('active');
  _cxcPdfDoc = null;
  _cxcRotation = 0; // Resetear rotación
}

/** Carga PDF.js desde CDN de forma dinámica */
function cxcLoadPdfJs() {
  return new Promise((resolve, reject) => {
    if (typeof window.pdfjsLib !== 'undefined') { resolve(); return; }
    const script = document.createElement('script');
    script.src  = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@5.4.530/build/pdf.min.mjs';
    script.type = 'module';
    script.onload = () => {
      import('https://cdn.jsdelivr.net/npm/pdfjs-dist@5.4.530/build/pdf.min.mjs')
        .then(mod => {
          window.pdfjsLib = mod;
          mod.GlobalWorkerOptions.workerSrc =
            'https://cdn.jsdelivr.net/npm/pdfjs-dist@5.4.530/build/pdf.worker.min.mjs';
          resolve();
        })
        .catch(reject);
    };
    script.onerror = () => reject(new Error('No se pudo cargar PDF.js'));
    document.head.appendChild(script);
  });
}

/** Carga y renderiza el PDF desde una URL (todas las páginas) */
async function cxcLoadPDF(url) {
  try {
    const loadingTask = window.pdfjsLib.getDocument(url);
    _cxcPdfDoc     = await loadingTask.promise;
    _cxcCurrentPage = 1;

    // Ajustar rangos del slider al tamaño real de la primera página
    try {
      const firstPage = await _cxcPdfDoc.getPage(1);
      const vp        = firstPage.getViewport({ scale: 1 });
      const body      = document.getElementById('cxcPDFBody');
      const w         = (body && body.clientWidth) ? body.clientWidth - 24 : window.innerWidth * 0.85;
      const fitPct    = Math.round(w / vp.width * 100);
      const slider    = document.getElementById('cxcZoomSlider');
      if (slider) {
        slider.min   = String(Math.max(50, Math.min(fitPct, 75)));
        slider.max   = '300';
        slider.step  = '5';
        slider.value = '100';
      }
      cxcUpdateZoomUI(100);
    } catch (_) { /* non-fatal */ }

    await cxcRenderAllPages();
  } catch (err) {
    throw new Error('No se pudo cargar el documento PDF: ' + (err && err.message ? err.message : err));
  }
}

/** Renderiza todas las páginas del PDF en el contenedor scrollable */
async function cxcRenderAllPages() {
  if (!_cxcPdfDoc) return;
  const container = document.getElementById('cxcPDFPages');
  if (!container) return;
  container.innerHTML = '';
  const numPages = _cxcPdfDoc.numPages;
  for (let i = 1; i <= numPages; i++) {
    const page     = await _cxcPdfDoc.getPage(i);
    // Usar getViewport con rotation para que PDF.js maneje la rotación correctamente
    const viewport = page.getViewport({ scale: _cxcScale, rotation: _cxcRotation });
    
    const canvas   = document.createElement('canvas');
    canvas.width   = viewport.width;
    canvas.height  = viewport.height;
    container.appendChild(canvas);
    const ctx = canvas.getContext('2d');
    
    // Llenar con fondo blanco para evitar áreas sombreadas
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    await page.render({ canvasContext: ctx, viewport }).promise;
  }
}

/** Renderiza la página indicada del PDF actual (mantenido por compatibilidad) */
async function cxcRenderPage(num) {
  await cxcRenderAllPages();
}

/** Aumenta el zoom en 15% (máx 300%) */
function cxcZoomIn() {
  const pct = Math.round(_cxcScale * 100);
  if (pct < 300) {
    _cxcScale = Math.min(3.0, _cxcScale + 0.15);
    cxcUpdateZoomUI(Math.round(_cxcScale * 100));
    if (_cxcPdfDoc) cxcRenderAllPages();
  }
}

/** Reduce el zoom en 15% (mín 50%) */
function cxcZoomOut() {
  const pct = Math.round(_cxcScale * 100);
  if (pct > 50) {
    _cxcScale = Math.max(0.5, _cxcScale - 0.15);
    cxcUpdateZoomUI(Math.round(_cxcScale * 100));
    if (_cxcPdfDoc) cxcRenderAllPages();
  }
}

/** Handler en vivo del slider (throttled con requestAnimationFrame) */
function cxcOnZoomInput(value) {
  const v = parseInt(value);
  if (_cxcZoomRaf) cancelAnimationFrame(_cxcZoomRaf);
  _cxcZoomRaf = requestAnimationFrame(() => {
    _cxcZoomRaf = null;
    cxcSetZoom(v);
  });
}

/** Aplica un nivel de zoom específico (en %) */
function cxcSetZoom(pct) {
  _cxcScale = pct / 100;
  cxcUpdateZoomUI(pct);
  if (_cxcPdfDoc) cxcRenderAllPages();
}

/** Ajusta el zoom para que la página ocupe el ancho del visor */
async function cxcFitWidth() {
  if (!_cxcPdfDoc) return;
  try {
    const page = await _cxcPdfDoc.getPage(1);
    const vp   = page.getViewport({ scale: 1 });
    const body = document.getElementById('cxcPDFBody');
    const w    = (body && body.clientWidth) ? body.clientWidth - 24 : window.innerWidth * 0.85;
    const pct  = Math.round(w / vp.width * 100);
    const slider = document.getElementById('cxcZoomSlider');
    const min  = slider ? parseInt(slider.min || '50') : 50;
    const max  = slider ? parseInt(slider.max || '300') : 300;
    cxcSetZoom(Math.max(min, Math.min(max, pct)));
  } catch (e) { console.warn('cxcFitWidth failed', e); }
}

/** Rota el PDF a la izquierda (90 grados en sentido antihorario) */
function cxcRotateLeft() {
  if (!_cxcPdfDoc) return;
  _cxcRotation = (_cxcRotation - 90) % 360;
  if (_cxcRotation < 0) _cxcRotation += 360;
  cxcRenderAllPages();
}

/** Rota el PDF a la derecha (90 grados en sentido horario) */
function cxcRotateRight() {
  if (!_cxcPdfDoc) return;
  _cxcRotation = (_cxcRotation + 90) % 360;
  cxcRenderAllPages();
}

/** Actualiza slider y etiqueta de zoom en la UI */
function cxcUpdateZoomUI(pct) {
  const slider = document.getElementById('cxcZoomSlider');
  const label  = document.getElementById('cxcZoomLabel');
  if (slider) slider.value = String(pct);
  if (label)  label.textContent = pct + '%';
}

/** Descarga el PDF actualmente abierto */
function cxcDownloadPDF() {
  if (!_cxcPdfUrl || !_cxcPdfFileName) { alert('No hay documento para descargar'); return; }
  const a = document.createElement('a');
  const url = _cxcPdfUrl + (_cxcPdfUrl.includes('?') ? '&' : '?') +
              'name=' + encodeURIComponent(_cxcPdfFileName);
  a.href = url;
  a.download = _cxcPdfFileName.endsWith('.pdf') ? _cxcPdfFileName : _cxcPdfFileName + '.pdf';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/** Imprime el PDF actualmente abierto */
async function cxcPrintPDF() {
  if (!_cxcPdfUrl) { alert('No hay documento para imprimir'); return; }
  try {
    const resp = await fetch(_cxcPdfUrl, { credentials: 'same-origin' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const blob    = await resp.blob();
    const blobUrl = URL.createObjectURL(blob);
    const win     = window.open('', '_blank');
    if (!win) { alert('Bloqueador de ventanas activo &mdash; permite ventanas emergentes para imprimir.'); URL.revokeObjectURL(blobUrl); return; }
    const title   = (_cxcPdfFileName || 'Documento').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    win.document.write(
      `<!doctype html><html><head><title>${title}</title>` +
      `<style>*{margin:0;padding:0}html,body{height:100%;overflow:hidden}` +
      `iframe{width:100%;height:100%;border:none}</style></head>` +
      `<body><iframe src="${blobUrl}" onload="this.contentWindow.print()"></iframe></body></html>`
    );
    win.document.close();
  } catch (err) {
    alert('No se pudo imprimir: ' + (err && err.message ? err.message : err));
  }
}

// Cerrar el visor al presionar Escape
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    const modal = document.getElementById('cxcPDFModal');
    if (modal && modal.classList.contains('active')) cxcClosePDFModal();
  }
});

// ── Modal Liquidaciones Procesadas ───────────────────────────────────────────
async function openProcesadosModal() {
  const modal   = document.getElementById('procesadosModal');
  const content = document.getElementById('procesadosModalContent');
  if (!modal) return;
  modal.classList.add('open');
  content.innerHTML = '<div style="text-align:center;padding:32px;color:var(--muted);"><span class="material-symbols-rounded" style="font-size:32px;display:block;margin-bottom:8px">hourglass_empty</span>Cargando liquidaciones procesadas...</div>';

  document.getElementById('procesadosModalClose')?.addEventListener('click', () => {
    modal.classList.remove('open');
  }, { once: true });
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.remove('open');
  }, { once: true });

  try {
    const _procQp = new URLSearchParams('estado=Procesado');
    const _flags  = window.CXC_FLAGS || {};
    if ((_flags.CXC_ROLE||'').toLowerCase() === 'auditor' && _flags.CURRENT_EJECUTIVO) {
      _procQp.set('ejecutivo', _flags.CURRENT_EJECUTIVO);
    }
    const resp = await fetch(`/cxc/lotes?${_procQp}`, { credentials: 'same-origin' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const lotes = await resp.json();
    content.innerHTML = _renderProcesadosTable(lotes);
  } catch (err) {
    content.innerHTML = `<div style="padding:24px;color:#ef4444;">Error al cargar: ${err}</div>`;
  }
}

function _renderProcesadosTable(lotes) {
  if (!lotes.length) {
    return '<div style="text-align:center;padding:40px;color:var(--muted);">No hay liquidaciones procesadas.</div>';
  }

  const fmtDate = raw => raw ? String(raw).replace('T',' ').replace(/\.\d+$/,'').substring(0,16) : '&mdash;';
  const fmtMoney = v => v != null ? 'L ' + parseFloat(v).toLocaleString('es-HN',{minimumFractionDigits:2,maximumFractionDigits:2}) : '&mdash;';

  // Badges para estadoDoc
  const estadoDocBadge = {
    11: '<span class="lb-procesado" style="font-size:10px;white-space:nowrap"> Generado</span>',
    12: '<span class="lb-procesado" style="font-size:10px;white-space:nowrap;background:linear-gradient(135deg,rgba(234,179,8,.22),rgba(234,179,8,.10));border-color:rgba(234,179,8,.55);color:#eab308"><span class="material-symbols-rounded" style="font-size:11px;vertical-align:-2px">draw</span> Firmado</span>',
    13: '<span class="lb-procesado" style="font-size:10px;white-space:nowrap;background:linear-gradient(135deg,rgba(99,102,241,.22),rgba(99,102,241,.10));border-color:rgba(99,102,241,.55);color:#a5b4fc"><span class="material-symbols-rounded" style="font-size:11px;vertical-align:-2px">manage_search</span> En revisión</span>',
    14: '<span class="lb-finalizado" style="font-size:10px;white-space:nowrap"><span class="material-symbols-rounded" style="font-size:11px;vertical-align:-2px">verified</span> Confirmado</span>',
  };

  const rows = lotes.map(l => {
    const _pdfFileId  = (l.spFileId || '').replace(/'/g, "\\'");
    const _pdfDlUrl   = (l.spDownloadUrl || '').replace(/'/g, "\\'");
    const _pdfName    = (l.spFileName && l.spFileName.trim()) || (l.numeroLiquidacion ? l.numeroLiquidacion + '.pdf' : 'liquidacion.pdf');
    const _revFileId  = (l.spRevFileId || '').replace(/'/g, "\\'");
    const _revDlUrl   = (l.spRevDlUrl  || '').replace(/'/g, "\\'");
    const _pdfProxyUrl = `/cxc/lotes/${l.id}/pdf`;
    const _hasPdf = !!(l.spFileId || l.spDownloadUrl || (l.spFileName && l.spFileName.trim()));
    const _pdfOpenId = l.spFileId ? encodeURIComponent(l.spFileId) : '';
    const _pdfOpenDl = l.spFileId ? _pdfDlUrl : _pdfProxyUrl;
    const numLiq = (l.numeroLiquidacion || ('#' + l.id));
    const btnCob = `<button class="lote-btn lote-btn--cob" style="white-space:nowrap;display:inline-flex;gap:4px;align-items:center" onclick="openCobrosLoteModal(${l.id},'${numLiq.replace(/'/g,"\\'")}')"><span class="material-symbols-rounded" style="font-size:13px;flex-shrink:0">stacks</span><span style="white-space:nowrap">${l.num_cobros} cobro(s)</span></button>`;

    // Estado doc — '11'-'14' son sub-estados del flujo de documento;
    // 'Procesado' (legacy) y null siguen el comportamiento original
    let estadoDoc = null;
    const estadoRaw = String(l.estado || '');
    const estadoNum = parseInt(estadoRaw);
    if (!isNaN(estadoNum) && estadoNum >= 11 && estadoNum <= 14) estadoDoc = estadoNum;

    const _safeNumLiq = numLiq.replace(/'/g, "\\'");
    const btnPdf = _hasPdf
      ? (estadoDoc !== null
          ? `<button class="lote-btn lote-btn--pdf" onclick="_liqViewDocModal(${estadoDoc},${l.id},'${_safeNumLiq}','${_pdfFileId}','${_pdfOpenDl}','${_revFileId}','${_revDlUrl}')"> PDF</button>`
          : `<button class="lote-btn lote-btn--pdf" onclick="cxcOpenPDFViewer('${_pdfOpenId}','${_pdfName.replace(/'/g,"\\'")}','${_pdfOpenDl}')"> PDF</button>`)
      : '<span style="color:var(--muted);font-size:11px">Sin PDF</span>';

    // Verificar si el usuario puede liquidar
    const _canLiq = !!(window.CXC_FLAGS && window.CXC_FLAGS.CAN_LIQUIDAR);

    let docBadge = '';
    let actionBtns = '';

    if (estadoDoc === null || estadoDoc === 0) {
      // Registros anteriores sin flujo de doc → comportamiento original
      actionBtns = _canLiq
        ? `<button class="lote-btn lote-btn--fin" onclick="_procesadoFinalizarClick(${l.id},this)"><span class="material-symbols-rounded" style="font-size:13px">payments</span> Liquidar</button>`
        : '';
    } else if (estadoDoc === 11) {
      docBadge = estadoDocBadge[11];
      actionBtns =
        `<button class="lote-btn lote-btn--upload" onclick="_subirDocumentoClick(${l.id},'${numLiq.replace(/'/g,"\\'")}')"><span class="material-symbols-rounded" style="font-size:13px">upload_file</span> Subir documento</button>` +
        (_canLiq ? `<button class="lote-btn lote-btn--fin" disabled title="Sube el documento firmado para habilitar"><span class="material-symbols-rounded" style="font-size:13px">payments</span> Liquidar</button>` : '');
    } else if (estadoDoc === 12) {
      docBadge = estadoDocBadge[12];
      actionBtns =
        `<button class="lote-btn lote-btn--confirm" onclick="_revisarDocClick(${l.id},12,'${numLiq.replace(/'/g,"\'")}','${_revFileId}','${_revDlUrl}')"><span class="material-symbols-rounded" style="font-size:13px">manage_search</span> Revisar documento</button>` +
        (_canLiq ? `<button class="lote-btn lote-btn--fin" disabled title="Revisa el documento para habilitar"><span class="material-symbols-rounded" style="font-size:13px">payments</span> Liquidar</button>` : '');
    } else if (estadoDoc === 13) {
      docBadge = estadoDocBadge[13];
      actionBtns =
        `<button class="lote-btn lote-btn--confirm" onclick="_revisarDocClick(${l.id},13,'${numLiq.replace(/'/g,"\'")}','${_revFileId}','${_revDlUrl}')"><span class="material-symbols-rounded" style="font-size:13px">manage_search</span> Revisar documento</button>` +
        (_canLiq ? `<button class="lote-btn lote-btn--fin" disabled title="Confirma el documento para habilitar"><span class="material-symbols-rounded" style="font-size:13px">payments</span> Liquidar</button>` : '');
    } else if (estadoDoc === 14) {
      docBadge = estadoDocBadge[14];
      actionBtns = _canLiq
        ? `<button class="lote-btn lote-btn--fin" onclick="_procesadoFinalizarClick(${l.id},this)"><span class="material-symbols-rounded" style="font-size:13px">payments</span> Liquidar</button>`
        : '';
    } else {
      actionBtns = _canLiq
        ? `<button class="lote-btn lote-btn--fin" onclick="_procesadoFinalizarClick(${l.id},this)"><span class="material-symbols-rounded" style="font-size:13px">payments</span> Liquidar</button>`
        : '';
    }

    return `<tr>
      <td style="font-weight:800;color:var(--brand,#22c55e)" data-num="${numLiq}">${numLiq}</td>
      <td>${l.ejecutivo||'&mdash;'}</td>
      <td>${fmtDate(l.fechaGeneracion)}</td>
      <td style="font-weight:700;white-space:nowrap">${fmtMoney(l.total)}</td>
      <td>${docBadge}</td>
      <td>${btnCob}</td>
      <td><div style="display:flex;gap:5px;flex-wrap:wrap;align-items:center">${btnPdf}${actionBtns}</div></td>
    </tr>`;
  }).join('');

  return `<table class="lotes-tbl">
    <thead><tr>
      <th>No. Liquidaci&oacute;n</th><th>ejecutivo</th>
      <th>Fecha Inicio</th><th style="min-width:155px">Total</th><th>Estado Archivo</th><th>Cobros</th><th>Acciones</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

function _procesadoFinalizarClick(loteId, btnEl) {
  const row    = typeof btnEl === 'object' ? btnEl.closest('tr') : null;
  const numero = row?.querySelector('td[data-num]')?.dataset.num || ('#' + loteId);
  const msg = `¿Estas seguro que quieres confirmar la liquidación de ${numero}?\n\nEsto cambiará el estado a "Finalizado" y marcará los cobros como liquidado.`;
  showConfirm(msg, () => _doFinalizarLote(loteId, row), null, 'Confirmar Liquidación', 'payments');
}

async function _doFinalizarLote(loteId, rowEl) {
  try {
    const resp = await fetch(`/cxc/lotes/${loteId}/finalizar`, { method: 'POST', credentials: 'same-origin' });
    const data = await resp.json();
    if (data.status === 'ok') {
      if (rowEl) {
        // Reemplazar el botón Finalizar por el badge liquidado
        const btnFin = rowEl.querySelector('.lote-btn--fin');
        if (btnFin) {
          const badge = document.createElement('span');
          badge.className = 'lb-finalizado';
          badge.textContent = '✓ liquidado';
          btnFin.replaceWith(badge);
        }
        // Atenuar la fila para indicar que ya fue procesada
        rowEl.style.transition = 'opacity .4s';
        rowEl.style.opacity = '0.5';
      }
    } else {
      showAlert(data.message || 'Error al liquidar.', 'Liquidar', 'error');
    }
  } catch (err) {
    showAlert('Error: ' + err, 'Liquidar', 'error');
  }
}

// ── Subir PDF firmado ─────────────────────────────────────────────────────────
function _subirFirmadoClick(loteId) {
  const input = document.createElement('input');
  input.type    = 'file';
  input.accept  = 'application/pdf,.pdf';
  input.style.display = 'none';
  document.body.appendChild(input);

  input.addEventListener('change', async () => {
    const file = input.files[0];
    document.body.removeChild(input);
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showAlert('Solo se permiten archivos PDF.', 'Tipo incorrecto', 'block');
      return;
    }

    const fd = new FormData();
    fd.append('file', file);

    showLoading('Subiendo documento firmado...');
    try {
      const resp = await fetch(`/cxc/lotes/${loteId}/subir-firmado`, {
        method: 'POST',
        body: fd,
        credentials: 'same-origin',
      });
      hideLoading();
      const data = await resp.json();
      if (data.status === 'ok') {
        showAlert(data.message, 'Documento subido', 'check_circle');
        openProcesadosModal();
      } else {
        showAlert(data.message || 'Error al subir el archivo.', 'Error', 'error');
      }
    } catch (err) {
      hideLoading();
      showAlert('Error al subir: ' + err, 'Error', 'error');
    }
  });

  input.click();
}

// ── Confirmar documento ───────────────────────────────────────────────────────
function _confirmarDocClick(loteId, btnEl) {
  showConfirm(
    '¿Confirmar el documento firmado y habilitar la liquidación?\n\nEsta acción valida el documento revisado.',
    async () => {
      showLoading('Confirmando documento...');
      try {
        const resp = await fetch(`/cxc/lotes/${loteId}/confirmar`, {
          method: 'POST',
          credentials: 'same-origin',
        });
        hideLoading();
        const data = await resp.json();
        if (data.status === 'ok') {
          showAlert('Documento confirmado. La liquidación está habilitada.', 'Confirmado', 'verified');
          openProcesadosModal();
        } else {
          showAlert(data.message || 'Error al confirmar.', 'Error', 'error');
        }
      } catch (err) {
        hideLoading();
        showAlert('Error: ' + err, 'Error', 'error');
      }
    },
    null, 'Confirmar documento', 'verified'
  );
}

// ── Liquidaciones: Flujo de Documentos ───────────────────────────────────────
const _PDF_CARD_IMG = '<img src="/static/img/pdf.png" style="width:36px;height:36px;object-fit:contain;filter:drop-shadow(0 2px 4px rgba(99,102,241,.4));" alt="PDF">';

function _liqBuildCard(numLiq, fileLabel, proxyUrl, fileId, dlUrl) {
  const safeId   = (fileId  || '').replace(/'/g, "\\'");
  // Always proxy through the server — never use SharePoint direct URLs in the browser (CORS)
  const _serverUrl = fileId
    ? `/cxc/liquidacion/download/${encodeURIComponent(fileId)}`
    : proxyUrl;
  const safeUrl  = _serverUrl.replace(/'/g, "\\'");
  const safeName = fileLabel.replace(/'/g, "\\'");
  return `<div class="pdf-card" onclick="cxcOpenPDFViewer('${safeId}','${safeName}','${safeUrl}')">
    <div class="pdf-card-icon">${_PDF_CARD_IMG}</div>
    <div class="pdf-card-title">${fileLabel}</div>
    <div style="text-align:center;margin-top:12px;">
      <span class="pdf-card-badge">Toca aquí para visualizar</span>
    </div>
  </div>`;
}

// Abre liqDocsModal en el paso indicado.
// blobUrl: solo para step 1 (PDF recién generado en memoria)
// revFileId, revDlUrl: solo para step 3 (archivo firmado en SharePoint)
function _liqOpenDocsModal(step, loteId, numLiq, blobUrl, revFileId, revDlUrl) {
  const modal = document.getElementById('liqDocsModal');
  if (!modal) return;

  modal.classList.add('open');
  setTimeout(() => {
    if (typeof setDocumentationProgress === 'function') setDocumentationProgress(step);
  }, 60);

  if (step === 1) {
    _liqRenderStep1(loteId, numLiq, blobUrl);
  } else if (step === 3) {
    _liqRenderStep3(loteId, numLiq, revFileId || '', revDlUrl || '');
  } else {
    _liqRenderStep4(loteId, numLiq);
  }

  const closeBtn = document.getElementById('liqDocsModalClose');
  if (closeBtn) {
    const nb = closeBtn.cloneNode(true);
    closeBtn.parentNode.replaceChild(nb, closeBtn);
    nb.addEventListener('click', () => modal.classList.remove('open'));
  }
  modal.onclick = (e) => {
    if (e.target === modal) {
      modal.classList.remove('open');
      try { const t = document.getElementById('liqSubirModalTitle'); if (t) t.textContent = 'Subir Documento Firmado'; } catch(e){}
    }
  };
}

function _liqRenderStep1(loteId, numLiq, blobUrl) {
  const cardCont = document.getElementById('liqDocsCardContainer');
  const actions  = document.getElementById('liqDocsActions');
  const title    = document.getElementById('liqDocsModalTitle');
  if (title) title.textContent = 'Documento generado — ' + numLiq;
  const safeUrl  = (blobUrl || '').replace(/'/g, "\\'");
  const safeName = (numLiq + '.pdf').replace(/'/g, "\\'");
  if (cardCont) {
    cardCont.innerHTML = `<div class="pdf-card" onclick="cxcOpenPDFViewer('','${safeName}','${safeUrl}','${safeUrl}')">
      <div class="pdf-card-icon">${_PDF_CARD_IMG}</div>
      <div class="pdf-card-title">${numLiq}.pdf</div>
      <div style="text-align:center;margin-top:12px;">
        <span class="pdf-card-badge">Toca aquí para visualizar</span>
      </div>
    </div>`;
  }
  if (actions) {
    const safeNum = numLiq.replace(/'/g, "\\'");
    actions.innerHTML = `
      <button class="modal-btn modal-btn--ghost" onclick="document.getElementById('liqDocsModal').classList.remove('open')">Cerrar</button>
      <button class="modal-btn modal-btn--primary" onclick="_liqContinuarASubir(${loteId},'${safeNum}')">
        <span class="material-symbols-rounded" style="font-size:14px;vertical-align:-3px">upload_file</span> Subir documento
      </button>`;
  }
}

function _liqRenderStep3(loteId, numLiq, revFileId, revDlUrl) {
  const cardCont = document.getElementById('liqDocsCardContainer');
  const actions  = document.getElementById('liqDocsActions');
  const title    = document.getElementById('liqDocsModalTitle');
  if (title) title.textContent = 'Revisión de documentos — ' + numLiq;
  const proxyUrl = `/cxc/lotes/${loteId}/pdf`;
  if (cardCont) {
    cardCont.innerHTML = _liqBuildCard(numLiq, numLiq + ' rev.pdf', proxyUrl, revFileId, revDlUrl);
  }
  if (actions) {
    const safeNum = numLiq.replace(/'/g, "\\'");
    const _canConfirm = (window.CXC_FLAGS?.CAN_CONFIRM !== false);
    actions.innerHTML = `
      <button class="modal-btn modal-btn--ghost" onclick="document.getElementById('liqDocsModal').classList.remove('open')">Cerrar</button>
      <button class="lote-btn lote-btn--fin" onclick="_liqRegenerarDoc(${loteId},'${safeNum}')">
        <span class="material-symbols-rounded" style="font-size:13px">restart_alt</span> Regenerar
      </button>
      ${_canConfirm ? `<button class="lote-btn lote-btn--confirm" onclick="_liqConfirmar(${loteId})">
        <span class="material-symbols-rounded" style="font-size:13px">verified</span> Confirmar
      </button>` : ''}`;
  }
}

function _liqRenderStep4(loteId, numLiq) {
  const cardCont = document.getElementById('liqDocsCardContainer');
  const actions  = document.getElementById('liqDocsActions');
  const title    = document.getElementById('liqDocsModalTitle');
  if (title) title.textContent = 'Documento en Onedrive';
  const proxyUrl = `/cxc/lotes/${loteId}/pdf`;
  if (cardCont) {
    cardCont.innerHTML = _liqBuildCard(numLiq, numLiq + '.pdf', proxyUrl, '', '');
  }
  if (actions) {
    actions.innerHTML = `
      <button class="modal-btn modal-btn--primary" onclick="document.getElementById('liqDocsModal').classList.remove('open')">Cerrar</button>`;
  }
}

// Vista de documento desde botón PDF de la tabla — state-aware
function _liqViewDocModal(estadoDoc, loteId, numLiq, fileId, dlUrl, revFileId, revDlUrl) {
  const modal = document.getElementById('liqDocsModal');
  if (!modal) return;

  const title       = document.getElementById('liqDocsModalTitle');
  const stepWrapper = modal.querySelector('.doc-progress-steps-wrapper');
  const stepLabels  = modal.querySelector('.liq-step-labels');
  const cardCont    = document.getElementById('liqDocsCardContainer');
  const actions     = document.getElementById('liqDocsActions');
  const proxyUrl    = `/cxc/lotes/${loteId}/pdf`;

  if (title) title.textContent = 'Documento en Onedrive';

  if (estadoDoc === 14 || estadoDoc === 24) {
    // Confirmado: sin stepper, mostrar archivo final (ya renombrado)
    if (stepWrapper) stepWrapper.style.display = 'none';
    if (stepLabels)  stepLabels.style.display  = 'none';
    if (cardCont) {
      cardCont.innerHTML = _liqBuildCard(numLiq, numLiq + '.pdf', proxyUrl, fileId || '', dlUrl || '');
    }
  } else {
    // Estados 11/12/13: mostrar stepper en el paso correspondiente
    if (stepWrapper) stepWrapper.style.display = '';
    if (stepLabels)  stepLabels.style.display  = '';

    const step = estadoDoc === 11 ? 1 : estadoDoc === 12 ? 2 : 3;
    setTimeout(() => {
      if (typeof setDocumentationProgress === 'function') setDocumentationProgress(step);
    }, 60);

    if (estadoDoc === 11) {
      if (cardCont) {
        cardCont.innerHTML = _liqBuildCard(numLiq, numLiq + '.pdf', proxyUrl, fileId || '', dlUrl || '');
      }
    } else {
      // 12 / 13: mostrar archivo original — el rev se ve desde "Revisar documento"
      if (cardCont) {
        cardCont.innerHTML = _liqBuildCard(numLiq, numLiq + '.pdf', proxyUrl, fileId || '', dlUrl || '');
      }
    }
  }

  if (actions) {
    actions.innerHTML = `<button class="modal-btn modal-btn--primary" onclick="document.getElementById('liqDocsModal').classList.remove('open')">Cerrar</button>`;
  }

  modal.classList.add('open');

  const closeBtn = document.getElementById('liqDocsModalClose');
  if (closeBtn) {
    const nb = closeBtn.cloneNode(true);
    closeBtn.parentNode.replaceChild(nb, closeBtn);
    nb.addEventListener('click', () => modal.classList.remove('open'));
  }
  modal.onclick = (e) => { if (e.target === modal) modal.classList.remove('open'); };
}

// Botón "Continuar" (paso 1) → cierra docs modal, abre modal de subida
function _liqContinuarASubir(loteId, numLiq) {
  const docsModal = document.getElementById('liqDocsModal');
  if (docsModal) docsModal.classList.remove('open');
  _subirDocumentoClick(loteId, numLiq);
}

// Abre liqSubirModal (desde tabla estado 11, o desde botón Continuar del paso 1)
function _subirDocumentoClick(loteId, numLiq) {
  const modal = document.getElementById('liqSubirModal');
  if (!modal) return;

  window._liqPendingFile   = null;
  window._liqPendingPhotos = [];

  const expectedSpan = document.getElementById('liqSubirExpectedName');
  if (expectedSpan) expectedSpan.textContent = numLiq + '.pdf';

  const fotosSpan = document.getElementById('liqFotosExpectedName');
  if (fotosSpan) fotosSpan.textContent = numLiq + ' rev.pdf';

  // Insert reference in modal title (ej. "Subir Documento Firmado — LIQ-00001")
  try {
    const titleEl = document.getElementById('liqSubirModalTitle');
    if (titleEl) {
      titleEl.textContent = `Subir Documento Firmado — ${numLiq}`;
    }
  } catch (e) { console.warn('Could not set liqSubir modal title reference', e); }

  const preview      = document.getElementById('liqFilePreview');
  const photoPreview = document.getElementById('liqPhotoPreview');
  const confirmBtn   = document.getElementById('liqSubirConfirmBtn');
  if (preview)      preview.innerHTML = '';
  if (photoPreview) photoPreview.innerHTML = '';
  if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.onclick = null; }

  // Botón descargar → proxy del PDF original generado
  const dlBtn = document.getElementById('liqDescargarBtn');
  if (dlBtn) dlBtn.onclick = () => window.open(`/cxc/lotes/${loteId}/pdf`, '_blank');

  // Re-bind PDF file input
  const fileInput = document.getElementById('liqFileInput');
  if (fileInput) {
    const ni = fileInput.cloneNode(true);
    fileInput.parentNode.replaceChild(ni, fileInput);
    ni.addEventListener('change', (e) => _liqFileSelect(e, loteId, numLiq));
  }

  // Re-bind gallery photo input
  const photoInput = document.getElementById('liqPhotoInput');
  if (photoInput) {
    const np = photoInput.cloneNode(true);
    photoInput.parentNode.replaceChild(np, photoInput);
    np.addEventListener('change', (e) => _liqPhotoSelect(e, loteId, numLiq));
  }

  // Re-bind camera input
  const cameraInput = document.getElementById('liqCameraInput');
  if (cameraInput) {
    const nc = cameraInput.cloneNode(true);
    cameraInput.parentNode.replaceChild(nc, cameraInput);
    nc.addEventListener('change', (e) => _liqPhotoSelect(e, loteId, numLiq));
  }

  const dropZone = document.getElementById('liqDropZone');
  if (dropZone) {
    dropZone.ondragover  = (e) => { e.preventDefault(); dropZone.classList.add('dragover'); };
    dropZone.ondragleave = ()  => dropZone.classList.remove('dragover');
    dropZone.ondrop      = (e) => {
      e.preventDefault(); dropZone.classList.remove('dragover');
      const f = e.dataTransfer?.files;
      if (f?.length) _liqFileSelect({ target: { files: f } }, loteId, numLiq);
    };
  }

  const photoDropZone = document.getElementById('liqPhotoDropZone');
  if (photoDropZone) {
    photoDropZone.ondragover  = (e) => { e.preventDefault(); photoDropZone.classList.add('dragover'); };
    photoDropZone.ondragleave = ()  => photoDropZone.classList.remove('dragover');
    photoDropZone.ondrop      = (e) => {
      e.preventDefault(); photoDropZone.classList.remove('dragover');
      const f = e.dataTransfer?.files;
      if (f?.length) _liqPhotoSelect({ target: { files: f } }, loteId, numLiq);
    };
  }

  // Tab switching — re-clone to clear previous listeners
  const tabPDF   = document.getElementById('liqTabPDF');
  const tabFotos = document.getElementById('liqTabFotos');
  if (tabPDF && tabFotos) {
    const tpClone = tabPDF.cloneNode(true);
    tabPDF.parentNode.replaceChild(tpClone, tabPDF);
    const tfClone = tabFotos.cloneNode(true);
    tabFotos.parentNode.replaceChild(tfClone, tabFotos);
    tpClone.addEventListener('click', () => _liqSetUploadMode('pdf', loteId, numLiq));
    tfClone.addEventListener('click', () => _liqSetUploadMode('fotos', loteId, numLiq));
  }

  _liqSetUploadMode('fotos', loteId, numLiq);

  ['liqSubirCancelBtn', 'liqSubirModalClose'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) {
      const nb = btn.cloneNode(true);
      btn.parentNode.replaceChild(nb, btn);
      nb.addEventListener('click', () => {
        modal.classList.remove('open');
        try { const t = document.getElementById('liqSubirModalTitle'); if (t) t.textContent = 'Subir Documento Firmado'; } catch(e){}
      });
    }
  });

  modal.onclick = (e) => { if (e.target === modal) modal.classList.remove('open'); };
  modal.classList.add('open');

  // Inicializar barra del stepper estático (paso 2 de 4)
  setTimeout(() => {
    try {
      const cont = document.getElementById('liqSubirProgressContainer');
      const bar  = document.getElementById('liqSubirProgressBar');
      if (!cont || !bar) return;
      const circles = cont.querySelectorAll('.doc-circle');
      const rect    = cont.getBoundingClientRect();
      const centers = Array.from(circles).map(c => { const r = c.getBoundingClientRect(); return r.left + r.width / 2; });
      bar.style.left  = (centers[0] - rect.left) + 'px';
      bar.style.width = (centers[1] - centers[0]) + 'px';
    } catch (e) {}
  }, 60);
}

function _liqFileSelect(event, loteId, numLiq) {
  const file = event?.target?.files?.[0];
  window._liqPendingFile = file || null;
  _liqRenderFilePreview(loteId, numLiq);
}

function _liqRenderFilePreview(loteId, numLiq) {
  const preview    = document.getElementById('liqFilePreview');
  const confirmBtn = document.getElementById('liqSubirConfirmBtn');
  const file       = window._liqPendingFile;
  if (!preview || !confirmBtn) return;

  if (!file) {
    preview.innerHTML = '';
    confirmBtn.disabled = true;
    confirmBtn.onclick = null;
    return;
  }

  const isValid     = true;
  const sizeKb      = (file.size / 1024).toFixed(2);
  const safeNumLiq  = numLiq.replace(/'/g, "\\'");
  const iconPath    = 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z';
  const iconColor   = '#10b981';
  const borderColor = '#10b981';
  const safeFileName = file.name.replace(/"/g, '&quot;');

  preview.innerHTML = `
    <h4 style="margin:0 0 12px;font-size:0.9rem;color:#e5e7eb;font-weight:600;">Archivos seleccionados:</h4>
    <div style="display:flex;align-items:center;gap:10px;padding:12px;background:#1f2937;border:1px solid ${borderColor};border-radius:8px;">
      <svg style="width:20px;height:20px;color:#9ca3af;flex-shrink:0;" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"/>
      </svg>
      <div style="flex:1;display:flex;flex-direction:column;gap:4px;min-width:0;">
        <input type="text" id="liqFileNameInput" value="${safeFileName}"
               onchange="_liqRenameInline(${loteId},'${safeNumLiq}',this.value)"
               style="background:#111827;border:1px solid #374151;color:#e5e7eb;padding:4px 8px;border-radius:4px;font-size:0.875rem;width:100%;" />
        <span style="font-size:0.75rem;color:#9ca3af;">${sizeKb} KB</span>
      </div>
      <svg style="width:18px;height:18px;color:${iconColor};flex-shrink:0;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${iconPath}"/>
      </svg>
      <button onclick="_liqEliminarArchivo()" style="background:#374151;border:none;color:#9ca3af;padding:6px;border-radius:4px;cursor:pointer;display:flex;align-items:center;" onmouseover="this.style.background='#ef4444';this.style.color='white';" onmouseout="this.style.background='#374151';this.style.color='#9ca3af';">
        <svg style="width:16px;height:16px;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
        </svg>
      </button>
    </div>`;

  confirmBtn.disabled = !isValid;
  confirmBtn.onclick  = isValid ? () => _liqSubirArchivo(loteId, numLiq, window._liqPendingFile) : null;
}

function _liqRenameInline(loteId, numLiq, newName) {
  if (!newName || !newName.trim() || !window._liqPendingFile) return;
  window._liqPendingFile = new File([window._liqPendingFile], newName.trim(), { type: window._liqPendingFile.type });
  _liqRenderFilePreview(loteId, numLiq);
}

function _liqEliminarArchivo() {
  window._liqPendingFile = null;
  const preview    = document.getElementById('liqFilePreview');
  const confirmBtn = document.getElementById('liqSubirConfirmBtn');
  if (preview)    preview.innerHTML = '';
  if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.onclick = null; }
  const fi = document.getElementById('liqFileInput');
  if (fi) fi.value = '';
}

// ── Tab: modo de carga (PDF firmado ↔ Fotos auto-PDF) ──────────────────────
function _liqSetUploadMode(mode, loteId, numLiq) {
  window._liqUploadMode = mode;
  const isPDF        = mode === 'pdf';
  const contentPDF   = document.getElementById('liqTabContentPDF');
  const contentFotos = document.getElementById('liqTabContentFotos');
  const tabPDF       = document.getElementById('liqTabPDF');
  const tabFotos     = document.getElementById('liqTabFotos');
  const confirmBtn   = document.getElementById('liqSubirConfirmBtn');

  if (contentPDF)   contentPDF.style.display  = isPDF ? 'flex' : 'none';
  if (contentFotos) contentFotos.style.display = isPDF ? 'none' : 'flex';
  if (tabPDF) {
    tabPDF.style.borderBottomColor = isPDF ? '#6366f1' : 'transparent';
    tabPDF.style.color             = isPDF ? '#a5b4fc' : 'var(--muted)';
  }
  if (tabFotos) {
    tabFotos.style.borderBottomColor = isPDF ? 'transparent' : '#6366f1';
    tabFotos.style.color             = isPDF ? 'var(--muted)' : '#a5b4fc';
  }
  if (isPDF) {
    const file    = window._liqPendingFile;
    const isValid = !!file;
    if (confirmBtn) {
      confirmBtn.disabled = !isValid;
      confirmBtn.onclick  = isValid ? () => _liqSubirArchivo(loteId, numLiq, file) : null;
    }
  } else {
    const count = (window._liqPendingPhotos || []).length;
    if (confirmBtn) {
      confirmBtn.disabled = count === 0;
      confirmBtn.onclick  = count > 0 ? () => _liqGenerarYSubirPDFDesdePhotos(loteId, numLiq) : null;
    }
  }
}

// ── Selección de fotos (galería + cámara) ─────────────────────────────
const LIQ_MAX_PHOTOS = 5;

function _liqPhotoSelect(event, loteId, numLiq) {
  const newFiles = Array.from(event?.target?.files || []).filter(f => f.type.startsWith('image/'));
  if (!newFiles.length) return;
  const current   = window._liqPendingPhotos || [];
  const available = LIQ_MAX_PHOTOS - current.length;
  if (available <= 0) {
    showAlert(`Límite alcanzado: máximo ${LIQ_MAX_PHOTOS} fotos.`, 'Límite de fotos', 'error');
    if (event?.target) event.target.value = '';
    return;
  }
  const toAdd = newFiles.slice(0, available);
  if (newFiles.length > available) {
    showAlert(`Solo se agregaron ${toAdd.length} foto${toAdd.length !== 1 ? 's' : ''} (límite: ${LIQ_MAX_PHOTOS}).`, 'Aviso', 'error');
  }
  window._liqPendingPhotos = current.concat(toAdd);
  if (event?.target) event.target.value = '';
  _liqRenderPhotoPreview(loteId, numLiq);
}

function _liqRenderPhotoPreview(loteId, numLiq) {
  const preview    = document.getElementById('liqPhotoPreview');
  const confirmBtn = document.getElementById('liqSubirConfirmBtn');
  const photos     = window._liqPendingPhotos || [];
  if (!preview || !confirmBtn) return;

  if (!photos.length) {
    preview.innerHTML   = '';
    confirmBtn.disabled = true;
    confirmBtn.onclick  = null;
    return;
  }

  const safeNumLiq = numLiq.replace(/'/g, "\\'");
  const atMax      = photos.length >= LIQ_MAX_PHOTOS;
  const thumbsHtml = photos.map((f, i) => {
    const objUrl = URL.createObjectURL(f);
    return `<div style="position:relative;aspect-ratio:1;background:#111827;border:1px solid #374151;border-radius:6px;overflow:hidden;">
      <img src="${objUrl}" alt="Foto ${i + 1}" style="width:100%;height:100%;object-fit:cover;" loading="lazy">
      <button onclick="_liqEliminarFoto(${i},${loteId},'${safeNumLiq}'); event.stopPropagation();"
              style="position:absolute;top:2px;right:2px;background:rgba(0,0,0,.65);border:none;color:#fff;width:18px;height:18px;border-radius:50%;cursor:pointer;font-size:12px;line-height:18px;text-align:center;padding:0;"
              title="Eliminar">×</button>
      <span style="position:absolute;bottom:0;left:0;right:0;font-size:9px;color:#d1d5db;background:rgba(0,0,0,.55);text-align:center;padding:1px 2px;">${i + 1}</span>
    </div>`;
  }).join('');

  const countColor = atMax ? '#ef4444' : '#e5e7eb';
  const maxBadge   = atMax
    ? `<span style="font-size:0.72rem;background:#ef444422;color:#ef4444;border:1px solid #ef4444;border-radius:4px;padding:1px 6px;margin-left:6px;">máx.</span>`
    : '';

  preview.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
      <h4 style="margin:0;font-size:0.88rem;color:${countColor};font-weight:600;display:flex;align-items:center;">
        ${photos.length}/${LIQ_MAX_PHOTOS} fotos${maxBadge}
      </h4>
      <button onclick="_liqEliminarTodasFotos(${loteId},'${safeNumLiq}'); event.stopPropagation();"
              style="background:#374151;border:none;color:#9ca3af;padding:4px 9px;border-radius:4px;cursor:pointer;font-size:0.75rem;"
              onmouseover="this.style.color='#ef4444'" onmouseout="this.style.color='#9ca3af'">Quitar todas</button>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(76px,1fr));gap:8px;">${thumbsHtml}</div>`;

  confirmBtn.disabled = false;
  confirmBtn.onclick  = () => _liqGenerarYSubirPDFDesdePhotos(loteId, numLiq);
}

function _liqEliminarFoto(index, loteId, numLiq) {
  window._liqPendingPhotos = (window._liqPendingPhotos || []).filter((_, i) => i !== index);
  _liqRenderPhotoPreview(loteId, numLiq);
}

function _liqEliminarTodasFotos(loteId, numLiq) {
  window._liqPendingPhotos = [];
  _liqRenderPhotoPreview(loteId, numLiq);
}

// ── Generación de PDF desde fotos y subida ───────────────────────────
async function _liqGenerarYSubirPDFDesdePhotos(loteId, numLiq) {
  const photos = window._liqPendingPhotos || [];
  if (!photos.length) return;
  showLoading(`Generando PDF con ${photos.length} foto${photos.length !== 1 ? 's' : ''}…`);
  try {
    const pdfFile = await _liqGenerarPDFDesdePhotos(photos, numLiq);
    await _liqSubirArchivo(loteId, numLiq, pdfFile);
  } catch (err) {
    hideLoading();
    showAlert('Error al generar el PDF: ' + err.message, 'Error', 'error');
  }
}

async function _liqGenerarPDFDesdePhotos(photos, numLiq) {
  if (!window.jspdf) throw new Error('jsPDF no está disponible. Recarga la página e inténtalo de nuevo.');
  const { jsPDF } = window.jspdf;
  // Landscape letter: 279.4 × 215.9 mm
  const pageW = 279.4, pageH = 215.9, margin = 8;
  const maxW  = pageW - 2 * margin;
  const maxH  = pageH - 2 * margin;
  const doc   = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'letter' });

  for (let i = 0; i < photos.length; i++) {
    if (i > 0) doc.addPage();
    // Normaliza formato, resolución y orientación EXIF vía canvas → siempre JPEG limpio
    const { dataUrl, w: imgW, h: imgH } = await _liqImageToJpeg(photos[i]);
    let drawW, drawH;
    if (imgW / maxW >= imgH / maxH) {
      drawW = maxW;  drawH = maxW * imgH / imgW;
    } else {
      drawH = maxH;  drawW = maxH * imgW / imgH;
    }
    const x = margin + (maxW - drawW) / 2;
    const y = margin + (maxH - drawH) / 2;
    doc.addImage(dataUrl, 'JPEG', x, y, drawW, drawH, undefined, 'FAST');
  }

  const blob = doc.output('blob');
  return new File([blob], numLiq + ' rev.pdf', { type: 'application/pdf' });
}

/**
 * Carga una imagen en un <canvas> y la exporta como JPEG (calidad 0.92).
 * Esto:
 *  - Normaliza formatos (WebP, HEIC, etc.) a JPEG compatible con jsPDF
 *  - El navegador aplica la orientación EXIF automáticamente al renderizar la <img>
 *  - Reduce imágenes de alta resolución al máximo de 2 048 px en el lado mayor
 */
function _liqImageToJpeg(file) {
  const MAX_PX = 2048;
  return new Promise((resolve, reject) => {
    const objUrl = URL.createObjectURL(file);
    const img    = new Image();
    img.onload = () => {
      URL.revokeObjectURL(objUrl);
      let w = img.naturalWidth;
      let h = img.naturalHeight;
      if (w === 0 || h === 0) { reject(new Error('Imagen vacía o formato no soportado')); return; }
      // Escalar si supera el máximo
      if (w > MAX_PX || h > MAX_PX) {
        if (w >= h) { h = Math.round(h * MAX_PX / w); w = MAX_PX; }
        else        { w = Math.round(w * MAX_PX / h); h = MAX_PX; }
      }
      const canvas  = document.createElement('canvas');
      canvas.width  = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(img, 0, 0, w, h);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
      resolve({ dataUrl, w, h });
    };
    img.onerror = () => { URL.revokeObjectURL(objUrl); reject(new Error('No se pudo cargar la imagen')); };
    img.src = objUrl;
  });
}

function _liqFotoADataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = (e) => resolve(e.target.result);
    reader.onerror = ()  => reject(new Error('No se pudo leer la imagen'));
    reader.readAsDataURL(file);
  });
}

function _liqGetImageDimensions(dataUrl) {
  return new Promise((resolve) => {
    const img  = new Image();
    img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight });
    img.src    = dataUrl;
  });
}

async function _liqSubirArchivo(loteId, numLiq, file) {
  const subModal = document.getElementById('liqSubirModal');
  const fd = new FormData();
  fd.append('file', file);
  showLoading('Subiendo documento firmado...');
  try {
    const resp = await fetch(`/cxc/lotes/${loteId}/subir-firmado`, {
      method: 'POST', body: fd, credentials: 'same-origin',
    });
    hideLoading();
    const data = await resp.json();
    if (data.status === 'ok') {
      if (subModal) subModal.classList.remove('open');
      // Refrescar la tabla de procesados en el fondo para actualizar estado y botones
      const procContent = document.getElementById('procesadosModalContent');
      if (procContent) {
        fetch('/cxc/lotes?estado=Procesado', { credentials: 'same-origin' })
          .then(r => r.json()).then(lotes => { procContent.innerHTML = _renderProcesadosTable(lotes); })
          .catch(() => {});
      }
      _liqOpenDocsModal(3, loteId, numLiq, null, data.rev_file_id || '', data.rev_dl_url || '');
    } else {
      showAlert(data.message || 'Error al subir el archivo.', 'Error', 'error');
    }
  } catch (err) {
    hideLoading();
    showAlert('Error al subir: ' + err, 'Error', 'error');
  }
}

// Desde tabla Procesadas: estado 12 → POST marcar-revision → 13 → paso 3
// Desde tabla Procesadas: estado 13 → paso 3 directamente
async function _revisarDocClick(loteId, estadoDoc, numLiq, revFileId, revDlUrl) {
  if (estadoDoc === 12) {
    showLoading('Marcando en revisión...');
    try {
      const resp = await fetch(`/cxc/lotes/${loteId}/marcar-revision`, {
        method: 'POST', credentials: 'same-origin',
      });
      hideLoading();
      const data = await resp.json();
      if (data.status === 'ok') {
        _liqOpenDocsModal(3, loteId, numLiq, null, revFileId || '', revDlUrl || '');
      } else {
        showAlert(data.message || 'Error.', 'Error', 'error');
      }
    } catch (err) {
      hideLoading();
      showAlert('Error: ' + err, 'Error', 'error');
    }
  } else {
    _liqOpenDocsModal(3, loteId, numLiq, null, revFileId || '', revDlUrl || '');
  }
}

async function _liqConfirmar(loteId) {
  showLoading('Confirmando documento...');
  try {
    const resp = await fetch(`/cxc/lotes/${loteId}/confirmar`, {
      method: 'POST', credentials: 'same-origin',
    });
    hideLoading();
    const data = await resp.json();
    if (data.status === 'ok') {
      const modal = document.getElementById('liqDocsModal');
      if (modal) modal.classList.remove('open');
      showAlert('Documento confirmado. La liquidación está habilitada.', 'Confirmado', 'verified');
      openProcesadosModal();
    } else {
      showAlert(data.message || 'Error al confirmar.', 'Error', 'error');
    }
  } catch (err) {
    hideLoading();
    showAlert('Error: ' + err, 'Error', 'error');
  }
}

async function _liqRegenerarDoc(loteId, numLiq) {
  showConfirm(
    `¿Regenerar el documento ${numLiq}?\n\nEl estado volverá a "Generado" y deberá subir un nuevo documento firmado.`,
    async () => {
      showLoading('Regresando a estado generado...');
      try {
        const resp = await fetch(`/cxc/lotes/${loteId}/regenerar`, {
          method: 'POST', credentials: 'same-origin',
        });
        hideLoading();
        const data = await resp.json();
        if (data.status === 'ok') {
          const modal = document.getElementById('liqDocsModal');
          if (modal) modal.classList.remove('open');
          openProcesadosModal();
        } else {
          showAlert(data.message || 'Error al regenerar.', 'Error', 'error');
        }
      } catch (err) {
        hideLoading();
        showAlert('Error: ' + err, 'Error', 'error');
      }
    },
    null, 'Regenerar documento', 'restart_alt'
  );
}

// ── Grid Liquidaciones Finalizadas ───────────────────────────────────────────
var _finalizadosGridApi = null;
var _currentCxcView = 'cobros';

function toggleFinalizadosView() {
  const viewCobros      = document.getElementById('viewCobros');
  const viewFin         = document.getElementById('viewFinalizados');
  const btnVerProc      = document.getElementById('btnVerProcesados');
  const btnVerFin       = document.getElementById('btnVerFinalizados');
  const btnVolver       = document.getElementById('btnVolverCobros');
  const btnLiq          = document.getElementById('btnLiquidar');
  const btnSync         = document.getElementById('btnSync');
  const btnPrint        = document.getElementById('btnPrint');
  // Antes de cambiar de vista, limpiar filtros para que la vista nueva muestre
  // todos los registros por defecto.
  const clearFilters = () => {
    ['filterSucursal', 'filterEjecutivo', 'filterCliente', 'filterRecibo', 'filterLiquidado'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    // Restaurar fechas al primer y último día del mes actual
    if (typeof setDefaultDates === 'function') setDefaultDates();
  };

  if (_currentCxcView === 'cobros') {
    // Entrando a la vista de Liquidados: limpiar filtros y mostrar la tabla de lotes
    clearFilters();
    if (viewCobros) viewCobros.style.display = 'none';
    if (viewFin)    viewFin.style.display    = 'block';
    if (btnVerProc) btnVerProc.style.display = 'none';
    if (btnVerFin)  btnVerFin.style.display  = 'none';
    if (btnLiq)     btnLiq.style.display     = 'none';
    if (btnSync)    btnSync.style.display    = 'none';
    if (btnPrint)   btnPrint.style.display   = 'none';
    if (btnVolver)  btnVolver.style.display  = '';
    _currentCxcView = 'finalizados';
    if (!_finalizadosGridApi) _initFinalizadosGrid();
    _loadFinalizadosData();
  } else {
    // Volviendo a Cobros: limpiar filtros y mostrar la tabla cobros
    clearFilters();
    if (viewCobros) viewCobros.style.display = '';
    if (viewFin)    viewFin.style.display    = 'none';
    if (btnVerProc) btnVerProc.style.display = '';
    if (btnVerFin)  btnVerFin.style.display  = '';
    if (btnLiq)     btnLiq.style.display     = '';
    if (btnSync)    btnSync.style.display    = '';
    if (btnPrint)   btnPrint.style.display   = '';
    if (btnVolver)  btnVolver.style.display  = 'none';
    _currentCxcView = 'cobros';
    // No recargar la grilla aquí: usamos el modal de carga / control manual
  }
}

async function _loadFinalizadosData() {
  if (!_finalizadosGridApi) return;
  try {
    const f  = typeof getFilters === 'function' ? getFilters() : {};
    const qp = new URLSearchParams({ estado: 'Finalizado', limit: 500 });
    if (f.ejecutivo)    qp.set('ejecutivo',    f.ejecutivo);
    if (f.recibo)       qp.set('recibo',       f.recibo);
    if (f.cliente)      qp.set('cliente',      f.cliente);
    if (f.fecha_inicio) qp.set('fecha_inicio', f.fecha_inicio);
    if (f.fechaFin)    qp.set('fechaFin',    f.fechaFin);
    const resp = await fetch('/cxc/lotes?' + qp.toString(), { credentials: 'same-origin' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const lotes = await resp.json();
    _finalizadosGridApi.setGridOption('rowData', lotes);
    if (!lotes.length) _finalizadosGridApi.showNoRowsOverlay();
    else _finalizadosGridApi.hideOverlay();
  } catch (err) {
    _finalizadosGridApi.setGridOption('rowData', []);
    _finalizadosGridApi.hideOverlay();
    window.showAlert('Error al cargar finalizados: ' + err, 'Error', 'error');
  }
}

function _initFinalizadosGrid() {
  const container = document.getElementById('finalizadosGridView');
  if (!container || typeof agGrid === 'undefined') return;
  if (_finalizadosGridApi) {
    try { _finalizadosGridApi.destroy(); } catch(_) {}
    _finalizadosGridApi = null;
  }

  const fmtDate  = raw => raw ? String(raw).replace('T',' ').replace(/\.\d+$/,'').substring(0,16) : '\u2014';
  const fmtMoney = v   => v != null ? 'L\u00a0' + parseFloat(v).toLocaleString('es-HN',{minimumFractionDigits:2,maximumFractionDigits:2}) : '\u2014';

  const colDefs = [
    {
      field: 'numeroLiquidacion',
      headerName: 'No. Liquidación',
      width: 165,
      cellRenderer: p => {
        const v = p.value || ('#' + (p.data && p.data.id));
        return `<span style="font-weight:800;color:var(--brand,#22c55e)">${v}</span>`;
      },
    },
    { field: 'ejecutivo', headerName: 'Ejecutivo', width: 130, minWidth: 80 },
    { field: 'liquidadoPor', headerName: 'Liquidado por', width: 150, minWidth: 80,
      cellRenderer: p => p.value ? `<span>${p.value}</span>` : '<span style="color:var(--muted)">—</span>',
    },
    {
      field: 'fechaFin', headerName: 'Fecha de Liquidación', width: 145, flex: 1,
      valueFormatter: p => fmtDate(p.value),
    },
    {
      field: 'total', headerName: 'Total', width: 155, flex: 1,
      cellRenderer: p => `<span style="font-weight:700">${fmtMoney(p.value)}</span>`,
    },
    {
      field: 'num_cobros', headerName: 'Cobros', width: 160, sortable: false,
      cellRenderer: p => {
        const d = p.data;
        if (!d) return '';
        const num = d.numeroLiquidacion || ('#' + d.id);
        return `<button class="lote-btn lote-btn--cob" onclick="openCobrosLoteModal(${d.id},'${num.replace(/'/g,"\\'")}')"><span class="material-symbols-rounded" style="font-size:13px">stacks</span>\u00a0${p.value || 0} cobro(s)</button>`;
      },
    },
    {
      field: 'spFileId', headerName: 'Acciones', width: 165, sortable: false, resizable: false,
      cellRenderer: p => {
        const d = p.data;
        if (!d) return '<span style="color:var(--muted);font-size:11px">\u2014</span>';
        const hasPdf = !!(d.spFileId || d.spDownloadUrl || (d.spFileName && d.spFileName.trim()));
        if (!hasPdf) return '<span style="color:var(--muted);font-size:11px">Sin PDF</span>';
        const pdfName = (d.spFileName && d.spFileName.trim()) || (d.numeroLiquidacion ? d.numeroLiquidacion + '.pdf' : 'liquidacion.pdf');
        const pdfId   = d.spFileId ? encodeURIComponent(d.spFileId) : '';
        const pdfUrl  = d.spFileId ? (d.spDownloadUrl || '').replace(/'/g,"\\'") : `/cxc/lotes/${d.id}/pdf`;
        return `<button class="lote-btn lote-btn--pdf" onclick="cxcOpenPDFViewer('${pdfId}','${pdfName.replace(/'/g,"\\'")}','${pdfUrl}')">Ver PDF</button>`;
      },
    },
  ];

  _finalizadosGridApi = agGrid.createGrid(container, {
    columnDefs: colDefs,
    rowData: [],
    defaultColDef: { sortable: true, resizable: true, suppressMovable: true },
    rowHeight: 42,
    headerHeight: 38,
    overlayLoadingTemplate: '<span style="color:var(--muted);font-size:13px">Cargando...</span>',
    overlayNoRowsTemplate: '<span style="color:var(--muted);font-size:13px">No hay liquidaciones.</span>',
  });
}

// openFinalizadosModal reemplazada por toggleFinalizadosView (ver arriba)

// ── Sub-modal Cobros de Lote ──────────────────────────────────────────────────
async function openCobrosLoteModal(loteId, numero) {
  const modal   = document.getElementById('cobrosLoteModal');
  const content = document.getElementById('cobrosLoteContent');
  const titulo  = document.getElementById('cobrosLoteTitulo');
  if (!modal) return;
  if (titulo) titulo.textContent = 'Cobros — ' + (numero || ('#' + loteId));
  content.innerHTML = '<div style="text-align:center;padding:32px;color:var(--muted);">Cargando...</div>';
  modal.classList.add('open');

  document.getElementById('cobrosLoteModalClose')?.addEventListener('click', () => {
    modal.classList.remove('open');
  }, { once: true });
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.classList.remove('open');
  }, { once: true });

  try {
    const resp = await fetch(`/cxc/lotes/${loteId}/cobros`, { credentials: 'same-origin' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const cobros = await resp.json();
    if (!cobros.length) {
      content.innerHTML = '<div style="text-align:center;padding:40px;color:var(--muted);">Sin cobros asociados a este lote.</div>';
      return;
    }
    const fmtMoney = v => v != null ? 'L ' + parseFloat(v).toLocaleString('es-HN',{minimumFractionDigits:2,maximumFractionDigits:2}) : '&mdash;';
    const fmtDate  = raw => raw ? String(raw).replace('T',' ').replace(/\.\d+$/,'').substring(0,16) : '&mdash;';
    const total    = cobros.reduce((acc, c) => acc + (parseFloat(c.valorPagado) || 0), 0);
    const rows = cobros.map((c,i) => `<tr>
      <td style="color:var(--muted);text-align:center">${i+1}</td>
      <td>${c.noRecibo||'&mdash;'}</td>
      <td style="font-weight:600">${c.nombreCliente||'&mdash;'}</td>
      <td>${c.noFactura||'&mdash;'}</td>
      <td style="font-weight:700;color:var(--brand,#22c55e)">${fmtMoney(c.valorPagado)}</td>
      <td>${c.metodoPago||'&mdash;'}</td>
      <td>${c.banco||'&mdash;'}</td>
      <td>${c.ejecutivo||'&mdash;'}</td>
    </tr>`).join('');
    content.innerHTML = `
      <div style="padding:0 0 10px;display:flex;align-items:center;justify-content:space-between;">
        <span style="font-size:11px;color:var(--muted);">${cobros.length} registro(s)</span>
        <span style="font-size:13px;font-weight:700;color:var(--brand,#22c55e);">Total: ${fmtMoney(total)}</span>
      </div>
      <table class="cobros-tbl">
        <thead><tr>
          <th>#</th><th>No. Recibo</th><th>Cliente</th><th>Factura</th>
          <th>Valor Pagado</th><th>M&eacute;todo Pago</th><th>banco</th><th>ejecutivo</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (err) {
    content.innerHTML = `<div style="padding:24px;color:#ef4444;">Error: ${err}</div>`;
  }
}