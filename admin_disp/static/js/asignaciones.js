/* asignaciones.js - extracted from asignaciones.html */

// ============================================================================
// ESTADO DE VISTAS
// ============================================================================
let currentView = 'resumen'; // 'resumen' o 'historico'

// Variable global para documentación
let _asignacionIdDocumentacion = null;

// ============================================================================
// FUNCIONES AUXILIARES GLOBALES
// ============================================================================

/**
 * Formatea un correlativo a 6 dígitos con ceros a la izquierda
 * @param {string|number} correlativo - El correlativo a formatear
 * @returns {string} - Correlativo formateado (ej: "000036")
 */
function formatearCorrelativo(correlativo) {
  if (!correlativo) return '000000';
  return String(correlativo).padStart(6, '0');
}

// ============================================================================
// FUNCIONES CLAVE - DEFINIDAS PRIMERO PARA EVITAR ERRORES DE SCOPE
// ============================================================================

// Variable global para controlar z-index dinámico de modales
let _modalZIndexCounter = 12000;
const _openModalsStack = [];

// Funciones globales para manejo de modales
function openModal(id, focusFirst) {
  const el = document.getElementById(id);
  if (el) {
    // Incrementar z-index para la nueva modal
    _modalZIndexCounter += 2;
    const overlayZIndex = _modalZIndexCounter;
    const modalZIndex = _modalZIndexCounter + 1;
    
    // Aplicar z-index dinámico al overlay y modal
    el.style.zIndex = overlayZIndex;
    const modal = el.querySelector('.modal');
    if (modal) {
      modal.style.zIndex = modalZIndex;
    }
    
    // Agregar a la pila de modales abiertas
    _openModalsStack.push(id);
    
    el.classList.add('active');
    // Si abrimos el modal de documentación, asegurar que el indicador muestre el paso 1
    try { if (id === 'modalSeleccionarTipoDocumentacion' && typeof setDocumentationProgress === 'function') setDocumentationProgress(1); } catch(e) {}
    if (focusFirst) {
      try {
        const firstInput = el.querySelector('input, select, textarea');
        if (firstInput) setTimeout(() => firstInput.focus(), 100);
      } catch(e) {}
    }
  }
}



function closeModal(id) {
  const el = document.getElementById(id);
  try {
    if (el) {
      // Remover de la pila de modales abiertas
      const index = _openModalsStack.indexOf(id);
      if (index > -1) {
        _openModalsStack.splice(index, 1);
      }
      
      // Si el modal usa la clase 'active', solo ocultarlo
      if (el.classList && el.classList.contains('active')) {
        el.classList.remove('active');
        // Limpiar z-index inline
        el.style.zIndex = '';
        const modal = el.querySelector('.modal');
        if (modal) {
          modal.style.zIndex = '';
        }
      } else {
        // Si es un modal dinámo insertado en DOM, eliminarlo
        el.remove();
      }
    }
  } catch (e) {
    // Ignorar errores al remover el elemento
  }

  // Siempre intentar eliminar el overlay de la subida manual
  try {
    const overlay = document.getElementById('modalSubidaManualOverlay');
    if (overlay) overlay.remove();
  } catch (e) {}
}

// ============================================================================
// MODAL DE OBSERVACIONES (Solo para Celulares)
// ============================================================================

// Variable global para almacenar el callback de observaciones
let _observacionesCallback = null;

// Función para abrir la modal de observaciones
function abrirModalObservaciones(callback) {
  _observacionesCallback = callback;
  
  // Reset radio buttons
  document.querySelectorAll('input[name="observacion-estetica"]').forEach(rb => rb.checked = false);
  document.querySelectorAll('input[name="observacion-accesorios"]').forEach(rb => rb.checked = false);
  
  openModal('modalObservacionesDispositivo');
}

// Función para confirmar observaciones (se llama desde el HTML)
function confirmarObservacionesDispositivo() {
  const esteticaSeleccionada = document.querySelector('input[name="observacion-estetica"]:checked');
  const accesoriosSeleccionado = document.querySelector('input[name="observacion-accesorios"]:checked');
  
  if (!esteticaSeleccionada || !accesoriosSeleccionado) {
    alert('Por favor selecciona una opción en cada sección');
    return;
  }
  
  const observaciones = {
    'OBSERVACION1': esteticaSeleccionada.value,
    'OBSERVACION2': accesoriosSeleccionado.value
  };
  
  closeModal('modalObservacionesDispositivo');
  
  // Llamar al callback con las observaciones
  if (_observacionesCallback) {
    _observacionesCallback(observaciones);
    _observacionesCallback = null;
  }
}

// Declaraciín temprana de función para evitar ReferenceError
async function abrirModalSeleccionarTipoDocumentacion(asignacionId) {
  _asignacionIdDocumentacion = asignacionId;
  _asignacionIdActual = asignacionId; // Establecer también para el nuevo flujo
  
  // NIVEL 1: Mostrar carga inmediatamente
  showLoading('Verificando estado de documentos...');
  
  try {
    // Obtener datos básicos de la asignación para saber el estado actual
    const respAsig = await fetch(`/devices/asignacion/${asignacionId}`);
    if (!respAsig.ok) {
      hideLoading();
      alert('Error: No se pudo obtener datos de asignación');
      return;
    }
    
    const asignacion = await respAsig.json();
    // Guardar asignación en memoria para uso posterior en el flujo
    window._asignacionCurrent = asignacion;
    window._empleadoIdActual = asignacion.fk_id_empleado; // Guardar empleadoId para verificaciín de pasaporte
    const estado = asignacion.estado_documentacion || 0;
    
    // Guardar correlativo si existe en la asignación
    if (asignacion.correlativo) {
      window._correlativoActual = formatearCorrelativo(asignacion.correlativo);
    }
    
    // GUARDAR ESTADO PARA QUE generarDocumentacionNuevo() SEPA SI NECESITA PEDIR DATOS
    window._estadoActualCheckeado = estado;
    
    // debug log removed
    
    // NIVEL 2: Si ya está en estado 11 o 21, ir directamente a preview
    if (estado === 11 || estado === 21) {
      // debug log removed
      hideLoading();
      
      // Mostrar documentos existentes directamente
      const tipoFirma = estado === 11 ? 'digital' : 'manual';
      _tipoFirmaSeleccionado = tipoFirma;
      
      // Llamar a generarDocumentacionNuevo directamente sin pedir datos
      // (el backend devolverí los existentes)
      generarDocumentacionNuevo(asignacionId, tipoFirma);
      return;
    }

    // Estado 12: Captura de firmas digitales
    if (estado === 12) {
      hideLoading();
      try {
        _tipoFirmaSeleccionado = 'digital';
        
        // Asegurarse de tener el correlativo antes de abrir modal de firmas
        if (!window._correlativoActual && asignacion.correlativo) {
          window._correlativoActual = formatearCorrelativo(asignacion.correlativo);
        }
        
        // Abrir modal de captura de firma del empleado
        abrirModalCapturarFirmaEmpleado();
      } catch(e) {
        console.warn('Error abriendo modal de captura de firmas', e);
      }
      return;
    }

    // Estado 22: Firma manual - mostrar modal de subida de archivos
    if (estado === 22) {
      hideLoading();
      try {
        _tipoFirmaSeleccionado = 'manual';
        
        if (!window._correlativoActual && asignacion.correlativo) {
          window._correlativoActual = formatearCorrelativo(asignacion.correlativo);
        }
        
        // Abrir modal para subir archivos firmados
        abrirModalSubidaFirmaManual();
      } catch(e) {
        console.warn('Error abriendo modal de subida', e);
      }
      return;
    }

    // Estados 13 y 23: Documentos con firmas aplicadas - mostrar para confirmar/regenerar
    if (estado === 13 || estado === 23) {
      hideLoading();
      try {
        _tipoFirmaSeleccionado = estado === 13 ? 'digital' : 'manual';
        
        // Mostrar documentos con botones de confirmar/regenerar
        mostrarModalDocumentosOneDrive([], estado);
      } catch(e) {
        console.warn('Error mostrando modal para estado 13/23', e);
      }
      return;
    }

    // Estados 14, 24, 90: Documentos completados - mostrar modal informativa con step 4
    if (estado === 14 || estado === 24 || estado === 90) {
      hideLoading();
      try {
        // mostrarModalDocumentosOneDrive hace fetch de archivos internamente
        // y obtiene el correlativo del endpoint list-documentos
        mostrarModalDocumentosOneDrive([], 90);
      } catch(e) {
        console.warn('Error mostrando modal para estado final', e);
      }
      return;
    }
    
    hideLoading();
    // debug log removed
    
    // NIVEL 3: Si estado es 0, abrir modal para seleccionar tipo
    if (typeof openModal === 'function') {
      openModal('modalSeleccionarTipoDocumentacion');
      try{ if (typeof ensureDocProgress === 'function') ensureDocProgress('modalSeleccionarTipoDocumentacion'); } catch(e){}
      try{ if (typeof setDocumentationProgress === 'function') setDocumentationProgress(1, 'modalSeleccionarTipoDocumentacion'); } catch(e){}
    } else {
      try { openGlobalMessageModal('error', 'Error', 'openModal no está definida'); } catch(e) {}
    }
    
  } catch(e) {
    hideLoading();
    try { openGlobalMessageModal('error', 'Error', e && e.message ? e.message : 'Error verificando estado'); } catch(err) {}
    
    // Fallback: mostrar modal de selección
    if (typeof openModal === 'function') {
      openModal('modalSeleccionarTipoDocumentacion');
    }
  }
}

function seleccionarTipoDocumentacion(tipo) {
  if (!_asignacionIdDocumentacion) {
    alert('Error: No se especificó asignación');
    return;
  }
  if (tipo !== 'digital' && tipo !== 'manual') return alert('Tipo de documentación inválido');
  window._tipoFirmaSeleccionado = tipo;

  // Cerrar modal de selección
  try { closeModal('modalSeleccionarTipoDocumentacion'); } catch(e) {}
  
  // Llamar a generarDocumentacionNuevo que manejará el flujo completo
  // (incluyendo modal de observaciones para celulares)
  generarDocumentacionNuevo(_asignacionIdDocumentacion, tipo);
}

// función para alternar entre vista resumen e Histórico
function toggleHistoricoView() {
  const viewResumen = document.getElementById('viewResumen');
  const viewHistorico = document.getElementById('viewHistorico');
  if (!viewResumen || !viewHistorico) return;
  // determine previous state so we can clear filter when opening Histórico
  const wasResumen = (currentView === 'resumen');
  if (wasResumen) {
    viewResumen.style.display = 'none';
    viewHistorico.style.display = 'block';
    currentView = 'historico';
    const btnHist = document.getElementById('btnHistoricoAsignaciones');
    const btnVol = document.getElementById('btnVolverResumen');
    if (btnHist) btnHist.style.display = 'none';
    if (btnVol) btnVol.style.display = 'inline-block';
    // Update header title to indicate historial view
    try {
      const h1 = document.querySelector('.main-header h1');
      if (h1) h1.textContent = 'Usuarios y Asignaciones (Histórico Asignaciones)';
    } catch(e) {}
  } else {
    viewResumen.style.display = 'block';
    viewHistorico.style.display = 'none';
    currentView = 'resumen';
    const btnHist2 = document.getElementById('btnHistoricoAsignaciones');
    const btnVol2 = document.getElementById('btnVolverResumen');
    if (btnHist2) btnHist2.style.display = 'inline-block';
    if (btnVol2) btnVol2.style.display = 'none';
    // Restore header title
    try {
      const h1 = document.querySelector('.main-header h1');
      if (h1) h1.textContent = 'Usuarios y Asignaciones';
    } catch(e) {}
  }

  // Trigger the 'Acciones' reset on toggle (both directions) so filters/sorts are cleared
  try {
    const acciones = document.getElementById('thActionsAsignaciones') || document.getElementById('thActionsHistorico');
    if (acciones) {
      try { acciones.click(); } catch(e) { try { acciones.dispatchEvent(new MouseEvent('click')); } catch(_) {} }
    }
    const searchEl = document.getElementById('asignacionesPageSearch');
    const q = (searchEl || {}).value || '';
    const visible = (currentView === 'resumen') ? document.getElementById('viewResumen') : document.getElementById('viewHistorico');
    const hidden = (currentView === 'resumen') ? document.getElementById('viewHistorico') : document.getElementById('viewResumen');
    if (typeof applyTableSearchFilter === 'function') {
      applyTableSearchFilter(q, visible);
      applyTableSearchFilter('', hidden);
    }
  } catch(e) {}
}

// función auxiliar para abrir modal desde tabla resumen
function openEmpleadoDevicesModalFromResumen(empleadoId) {
  if (!empleadoId) return;
  loadAssignedDevicesForEmpleado(empleadoId);
  setTimeout(() => {
    openEmpleadoDevicesModal();
  }, 100);
}

// Recarga las opciones del selector de dispositivos (solo dispositivos sin asignar)
async function reloadDispositivosOptions() {
  try {
    const resp = await fetch('/devices/disponibles');
    if (!resp.ok) return;
    const devices = await resp.json();
    const select = document.querySelector('#formNewAsignacion select[name="fk_id_dispositivo"]');
    const selectId = document.getElementById('selectDispositivo');
    if (!select && !selectId) return;
    
    // Guardar valor seleccionado actual si existe
    const current = select?.value || selectId?.value;
    const htmlOptions = '<option value="">Seleccionar</option>' +
      devices.map(d => {
        const marca = (d.nombre_marca || '').trim();
        const modelo = (d.nombre_modelo || '').trim();
        const imei = (d.imei || '').trim();
        const label = `${marca} ${modelo}` + (imei ? ` | ${imei}` : '');
        return `<option value="${d.id_dispositivo}" data-tipo="${d.categoria}" data-fk-plan="${d.fk_id_plan || ''}" data-imei="${imei}" data-marca="${marca}" data-modelo="${modelo}">${label}</option>`;
      }).join('');
    
    // Actualizar ambos selects
    if (select) select.innerHTML = htmlOptions;
    if (selectId) selectId.innerHTML = htmlOptions;
    
    // Si el valor anterior ya no existe, dejar vacío
    if (current) {
      const targetSelect = select || selectId;
      const opt = targetSelect.querySelector(`option[value="${current}"]`);
      targetSelect.value = opt ? current : '';
    }
    
    // Resetear filtro de tipo
    document.getElementById('filterTipoDispositivo').value = '';
  } catch (err) {
    try { openGlobalMessageModal('error', 'Error', err && err.message ? err.message : 'Error recargando dispositivos'); } catch(e) {}
  }
}

// Filtrar dispositivos por tipo seleccionado
function filterDispositivosPorTipo() {
  const tipoSeleccionado = document.getElementById('filterTipoDispositivo').value;
  const select = document.getElementById('selectDispositivo');
  const options = select.querySelectorAll('option');
  
  options.forEach(option => {
    if (option.value === '') {
      // Mostrar siempre la opciín vacía
      option.style.display = 'block';
    } else {
      const tipoOpcion = option.getAttribute('data-tipo');
      if (tipoSeleccionado === '' || tipoOpcion === tipoSeleccionado) {
        option.style.display = 'block';
      } else {
        option.style.display = 'none';
      }
    }
  });
  
  // Resetear selección si la opciín actual está oculta
  if (select.value !== '' && select.options[select.selectedIndex].style.display === 'none') {
    select.value = '';
  }
}

// función para recargar tabla de asignaciones
async function reloadAsignacionesTable() {
  try {
    const resp = await fetch('/devices/asignaciones/tbody');
    if (!resp.ok) return;
    const data = await resp.json();

    // Update historico tbody if present
    const histTbody = document.querySelector('#historicoTable tbody');
    if (histTbody && data.historico !== undefined) {
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = data.historico.trim();
      const rows = tempDiv.querySelectorAll('tr');
      if (rows.length > 0) {
        histTbody.innerHTML = '';
        rows.forEach(row => histTbody.appendChild(row));
      }
      try { 
        const q = (document.getElementById('asignacionesPageSearch') || {}).value || ''; 
        if (typeof applyTableSearchFilter === 'function') applyTableSearchFilter(q, document.getElementById('viewHistorico')); 
      } catch(e) {}
    }

    // Update resumen tbody if present
    const resumenTbody = document.querySelector('#asignacionesTable tbody');
    if (resumenTbody && data.resumen !== undefined) {
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = data.resumen.trim();
      const rows = tempDiv.querySelectorAll('tr');
      if (rows.length > 0) {
        resumenTbody.innerHTML = '';
        rows.forEach(row => resumenTbody.appendChild(row));
      }
      try { 
        const q = (document.getElementById('asignacionesPageSearch') || {}).value || ''; 
        if (typeof applyTableSearchFilter === 'function') applyTableSearchFilter(q, document.getElementById('viewResumen')); 
      } catch(e) {}
    }
  } catch (err) {
  }
}

// Sincroniza los badges de conteo de dispositivos desde la vista resumen hacia la tabla Histórico
// syncDeviceBadges removed: historico view should not display device-count badges

// (Auditoría de asignaciones eliminadas: eliminado í no solicitado por el usuario)

// Auditoría de asignaciones eliminadas: funcionalidad eliminada por petición del usuario.

/* ========================================================================= */

// Bind local search input to shared filter for asignaciones page
document.addEventListener('DOMContentLoaded', () => {
  try {
    const s = document.getElementById('asignacionesPageSearch');
    if (s && !s._bound) {
      s.addEventListener('input', () => {
        const v = (s.value || '').trim();
        try {
          const container = (currentView === 'historico') ? document.getElementById('viewHistorico') : document.getElementById('viewResumen');
          if (typeof applyTableSearchFilter === 'function') applyTableSearchFilter(v, container);
        } catch(e) {}
      });
      s._bound = true;
    }
  } catch(e) {}
});

/* ========================================================================= */

// Dynamic script/css loader helpers
function loadScriptOnce(src){
  return new Promise((resolve,reject)=>{
    if(document.querySelector(`script[src="${src}"]`)) return resolve();
    const s=document.createElement('script'); s.src=src; s.onload=resolve; s.onerror=reject; document.head.appendChild(s);
  });
}
function loadCssOnce(href){
  return new Promise((resolve,reject)=>{
    if(document.querySelector(`link[href="${href}"]`)) return resolve();
    const l=document.createElement('link'); l.rel='stylesheet'; l.href=href; l.onload=resolve; l.onerror=reject; document.head.appendChild(l);
  });
}

async function ensureSignaturePad(){
  if(typeof SignaturePad !== 'undefined') return;
  await loadScriptOnce('https://cdn.jsdelivr.net/npm/signature_pad@5.1.3/dist/signature_pad.umd.min.js');
}

/* ========================================================================= */

let _signaturePad = null;
  let _undoStack = [];
  let _redoStack = [];
  
  // Variables para flujo dual en PDF (para Periféricos)
  let _pdfDualFlow = false;
  let _pdfAsignacionIdPending = null;
  let _pdfFirmaUsuario = null;
  let _pdfFirmaEmpleado = null;
  
  function openSolicitarFirma() {
    try {
      if (_pdfDualFlow && !_pdfFirmaUsuario) {
        setTimeout(() => {
          const titleEl = document.getElementById('signatureModalTitle');
          const btnEl = document.getElementById('btnSaveSignature');
          if (titleEl) titleEl.textContent = 'Ingresar Firma - Usuario del sistema';
          if (btnEl) btnEl.textContent = 'Siguiente';
        }, 50);
      }
      openModal && openModal('modalSignature');
      setTimeout(initSignaturePad, 100);
    } catch (e) {
      try { openGlobalMessageModal('error', 'Error', e && e.message ? e.message : 'No se pudo abrir el modal de firma'); } catch(err) {}
    }
  }

  async function initSignaturePad() {
    try { await ensureSignaturePad(); } catch(e) { console.warn('signature pad load failed', e); }
    const canvas = document.getElementById('signatureCanvas');
    if (!canvas) return;
    
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    const cssWidth = canvas.offsetWidth;
    const cssHeight = 400;
    canvas.width = Math.floor(cssWidth * ratio);
    canvas.height = Math.floor(cssHeight * ratio);
    const ctx = canvas.getContext('2d');
    ctx.scale(ratio, ratio);
    
    if (_signaturePad) {
      try { _signaturePad.off && _signaturePad.off(); } catch(e){}
      _signaturePad = null;
    }
    
    const isDarkMode = (document.documentElement && document.documentElement.getAttribute('data-dark-mode') === 'true') || (document.body && document.body.classList && document.body.classList.contains('dark-mode'));
    canvas.style.backgroundColor = '#e8e8e8';
    
    _signaturePad = new SignaturePad(canvas, {
      backgroundColor: '#ffffff',
      penColor: '#000000',
      minWidth: 1,
      maxWidth: 3,
      throttle: 16,
      minDistance: 5
    });
    
    _signaturePad.clear();
    _undoStack = [];
    _redoStack = [];

    // Guardar estado despuís de cada trazo
    _signaturePad.addEventListener('endStroke', saveState);

    const btnSave = document.getElementById('btnSaveSignature');
    if (btnSave && !btnSave._bound) {
      btnSave.addEventListener('click', saveSignature);
      btnSave._bound = true;
    }
  }

  function saveState() {
    if (!_signaturePad) return;
    const data = _signaturePad.toData();
    _undoStack.push(JSON.parse(JSON.stringify(data)));
    _redoStack = [];
  }

  function undoSignature() {
    if (!_signaturePad || _undoStack.length === 0) return;
    
    const currentData = _signaturePad.toData();
    if (currentData && currentData.length > 0) {
      _redoStack.push(JSON.parse(JSON.stringify(currentData)));
    }
    
    _undoStack.pop();
    const previousData = _undoStack.length > 0 ? _undoStack[_undoStack.length - 1] : [];
    _signaturePad.fromData(previousData);
  }

  function redoSignature() {
    if (!_signaturePad || _redoStack.length === 0) return;
    
    const nextData = _redoStack.pop();
    _undoStack.push(JSON.parse(JSON.stringify(nextData)));
    _signaturePad.fromData(nextData);
  }

  function clearSignature() {
    if (_signaturePad) {
      _signaturePad.clear();
      _undoStack = [];
      _redoStack = [];
    }
  }

  function closeSignatureModal() {
    try { closeModal && closeModal('modalSignature'); } catch(e){}
    try { if (_signaturePad) { _signaturePad.off && _signaturePad.off(); _signaturePad = null; } } catch(e){}
  }

  async function saveSignature() {
    try {
      if (!_signaturePad) return alert('Inicializando...');
      if (_signaturePad.isEmpty()) return alert('La firma está vacía');
      const canvas = document.getElementById('signatureCanvas');
      const dataUrl = canvas.toDataURL('image/png');

      // Flujo PDF dual (para Periféricos)
      if (_pdfDualFlow) {
        if (!_pdfFirmaUsuario) {
          _pdfFirmaUsuario = dataUrl;
          const titleEl = document.getElementById('signatureModalTitle');
          const btnEl = document.getElementById('btnSaveSignature');
          if (titleEl) titleEl.textContent = 'Ingresar Firma - Empleado de la Asignacion';
          if (btnEl) btnEl.textContent = 'Guardar';
          _signaturePad.clear();
          _undoStack = [];
          _redoStack = [];
          return;
        } else {
          _pdfFirmaEmpleado = dataUrl;
          closeSignatureModal();
          // Si ya existen identidades en memoria, enviar; si no, pedir al usuario
          if (window._identidadEmpleadoTemp && window._identidadUsuarioTemp) {
            window.pdfOpenInNewTab = false;
            // enviar directamente
            submitDocument(_pdfAsignacionIdPending || null, false);
            return;
          } else {
            window.pdfOpenInNewTab = false;
            openModal('modalSeleccionarTipoDocumentacion');
            return;
          }
        }
      }

      const resp = await fetch('/devices/asignaciones/submit-signature', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: dataUrl, asignacion_id: null })
      }).catch(() => null);
      let json = null;
      if (resp && resp.ok) json = await resp.json().catch(()=>null);
      if (json && json.success) {
        if (typeof openGlobalSuccessModal === 'function') openGlobalSuccessModal(json.message || 'Firma guardada'); else alert(json.message || 'Firma guardada');
        closeSignatureModal();
      } else if (resp === null) {
        if (typeof openGlobalMessageModal === 'function') openGlobalMessageModal('info','Solicitud','Firma capturada (no se envió al servidor)'); else alert('Firma capturada (no se envió al servidor)');
        closeSignatureModal();
      } else {
        const msg = (json && json.message) ? json.message : 'Error guardando la firma';
        if (typeof openGlobalMessageModal === 'function') openGlobalMessageModal('error','Error', msg); else alert(msg);
      }
    } catch (e) {
      try { openGlobalMessageModal('error', 'Error', e && e.message ? e.message : 'Error guardando la firma'); } catch(err) {}
    }
  }

  window.addEventListener('resize', () => { if (document.getElementById('modalSignature') && document.getElementById('modalSignature').classList.contains('active')) { setTimeout(initSignaturePad, 100); } });

/* ========================================================================= */

// Inicializar sorting compartido para las tablas de asignaciones
document.addEventListener('DOMContentLoaded', () => {
  try {
    // store original indices
    ['asignacionesTable','historicoTable'].forEach(id => {
      const t = document.getElementById(id);
      if (!t) return;
      const rows = Array.from(t.querySelectorAll('tbody tr'));
      rows.forEach((r,i) => { if (r.dataset.originalIndex === undefined) r.dataset.originalIndex = i; });
    });
    // Inicializar helper compartido para ambas tablas
    try { initTableSorting('#asignacionesTable', { iconPrefix: 'sortIndicator_' }); } catch(e) {}
    try { initTableSorting('#historicoTable', { iconPrefix: 'sortIndicator_h_' }); } catch(e) {}

    // Actions reset buttons: limpiar búsqueda y sorting compartido
    const act1 = document.getElementById('thActionsAsignaciones');
    if (act1 && !act1._boundReset) {
      act1.style.cursor = 'pointer';
      act1.addEventListener('click', () => {
        try {
          const t1 = document.getElementById('asignacionesTable'); if (t1 && typeof t1.clearSorting === 'function') t1.clearSorting();
          const t2 = document.getElementById('historicoTable'); if (t2 && typeof t2.clearSorting === 'function') t2.clearSorting();
        } catch(e) {}
        try { const p = document.getElementById('asignacionesPageSearch'); if (p) p.value = ''; } catch(e) {}
        try { const vr = document.getElementById('viewResumen'); const vh = document.getElementById('viewHistorico'); if (typeof applyTableSearchFilter === 'function') { applyTableSearchFilter('', vr); applyTableSearchFilter('', vh); } } catch(e) {}
      });
      act1._boundReset = true;
    }
    const act2 = document.getElementById('thActionsHistorico');
    if (act2 && !act2._boundReset) {
      act2.style.cursor = 'pointer';
      act2.addEventListener('click', () => {
        try {
          const t1 = document.getElementById('asignacionesTable'); if (t1 && typeof t1.clearSorting === 'function') t1.clearSorting();
          const t2 = document.getElementById('historicoTable'); if (t2 && typeof t2.clearSorting === 'function') t2.clearSorting();
        } catch(e) {}
        try { const p = document.getElementById('asignacionesPageSearch'); if (p) p.value = ''; } catch(e) {}
        try { const vr = document.getElementById('viewResumen'); const vh = document.getElementById('viewHistorico'); if (typeof applyTableSearchFilter === 'function') { applyTableSearchFilter('', vr); applyTableSearchFilter('', vh); } } catch(e) {}
      });
      act2._boundReset = true;
    }
  } catch(e) {}
});

/* ========================================================================= */

// Helpers for finalize modal in asignaciones page
          window.__finalizeEmpleadoPendingDeviceId = null;
          window.__finalizeEmpleadoPendingAsignacion = null;

          // openModal and closeModal are now defined globally at the top of the script

          async function openFinalizeAsignacionEmpleado(deviceId) {
            if (!deviceId) return;
            try {
              const r = await fetch(`/devices/${deviceId}/asignacion-activa`, { credentials: 'same-origin' });
              if (!r.ok) return openGlobalMessageModal('error', 'Error', 'No se pudo consultar la asignación activa');
              const j = await r.json();
              if (!j || !j.active || !j.asignacion) return openGlobalMessageModal('info', 'Info', 'No hay asignación activa para este dispositivo');
              window.__finalizeEmpleadoPendingDeviceId = deviceId;
              window.__finalizeEmpleadoPendingAsignacion = j.asignacion;
              const persona = j.asignacion.empleado_nombre || j.asignacion.fk_id_empleado || '-';
              const fecha = j.asignacion.fecha_inicio_asignacion ? new Date(j.asignacion.fecha_inicio_asignacion).toLocaleDateString() : '-';
              const msgEl = document.getElementById('finalizeEmpleadoMessage');
              if (msgEl) msgEl.innerHTML = `Finalizar asignación de <strong>${persona}</strong> (desde ${fecha}) para el dispositivo <strong>${deviceId}</strong>?`;
              const ci = document.getElementById('confirmFinalizeEmpleadoInput');
              const btn = document.getElementById('btnConfirmFinalizeEmpleado');
              const err = document.getElementById('finalizeEmpleadoError');
              if (ci) { ci.value = ''; ci.focus(); }
              if (btn) btn.disabled = true;
              if (err) { err.style.display = 'none'; err.textContent = ''; }
              openModal('modalFinalizeAsignacionEmpleado', true);
            } catch (e) {
              try { openGlobalMessageModal('error', 'Error', e && e.message ? e.message : 'Error comunicándose con el servidor'); } catch(err) {}
            }
          }

          document.addEventListener('DOMContentLoaded', function(){
            const modal = document.getElementById('modalFinalizeAsignacionEmpleado');
            if (!modal) return;
            const input = modal.querySelector('#confirmFinalizeEmpleadoInput');
            const btn = modal.querySelector('#btnConfirmFinalizeEmpleado');
            const btnCancel = modal.querySelector('#btnCancelFinalizeEmpleado');
            if (input && btn) {
              input.addEventListener('input', () => { try { btn.disabled = input.value.trim() !== 'CONFIRMAR'; } catch(e){} });
            }
            if (btnCancel) btnCancel.addEventListener('click', () => { closeModal('modalFinalizeAsignacionEmpleado'); });
            if (btn) {
              btn.addEventListener('click', async () => {
                if (!window.__finalizeEmpleadoPendingDeviceId) return;
                const ci = document.getElementById('confirmFinalizeEmpleadoInput');
                if (ci && ci.value.trim() !== 'CONFIRMAR') return;
                btn.disabled = true; btn.textContent = 'Finalizando...';
                try {
                  const r = await fetch(`/devices/${window.__finalizeEmpleadoPendingDeviceId}/finalizar-asignacion`, { method: 'POST', credentials: 'same-origin' });
                  const j = await r.json().catch(()=>({}));
                  if (r.ok && j.success) {
                    closeModal('modalFinalizeAsignacionEmpleado');
                    // remove row from modal table if present
                    try {
                      const tbody = document.querySelector('#modalEmpleadoDevices table tbody');
                      if (tbody) {
                        const row = tbody.querySelector(`tr[data-device-id="${window.__finalizeEmpleadoPendingDeviceId}"]`);
                        if (row) row.remove();
                      }
                    } catch(e){}
                    // refresh assigned devices count
                    try { if (typeof loadAssignedDevicesForEmpleado === 'function') loadAssignedDevicesForEmpleado(window.__currentEmpleadoDevicesId || ''); } catch(e){}
                    openGlobalSuccessModal(j.message || 'asignación finalizada');
                  } else {
                    const err = document.getElementById('finalizeEmpleadoError'); if (err) { err.style.display='block'; err.textContent = j.message || 'No se pudo finalizar la asignación'; }
                  }
                } catch (e) {
                  try { openGlobalMessageModal('error', 'Error', e && e.message ? e.message : 'Error finalizando la asignación'); } catch(err) {}
                  const err = document.getElementById('finalizeEmpleadoError'); if (err) { err.style.display='block'; err.textContent = 'Error del servidor'; }
                } finally {
                  btn.disabled = false; btn.textContent = 'Confirmar finalización';
                  window.__finalizeEmpleadoPendingDeviceId = null;
                  window.__finalizeEmpleadoPendingAsignacion = null;
                }
              });
            }
          });

/* ========================================================================= */

// Pre-cargar cargo al seleccionar empleado en nueva asignación
    const selEmpNew = document.getElementById('selectEmpleadoNew');
    let assignedDevicesForSelectedEmployee = [];
    const btnShowEmpleadoDevices = document.getElementById('btnShowEmpleadoDevices');
    const countEmpleadoDevicesEl = document.getElementById('countEmpleadoDevices');

    async function loadAssignedDevicesForEmpleado(empleadoId) {
      const infoEl = document.getElementById('infoEmpleadoDevices');
      if (!empleadoId) {
        assignedDevicesForSelectedEmployee = [];
        if (countEmpleadoDevicesEl) countEmpleadoDevicesEl.textContent = '0';
        if (btnShowEmpleadoDevices) btnShowEmpleadoDevices.disabled = true;
        if (infoEl) infoEl.style.display = 'none';
        return;
      }
      try {
        const r = await fetch(`/devices/asignaciones/empleado/${empleadoId}`, { credentials: 'same-origin' });
        if (!r.ok) throw new Error('No se pudo obtener dispositivos');
        const j = await r.json();
        assignedDevicesForSelectedEmployee = Array.isArray(j.dispositivos) ? j.dispositivos : (j.dispositivos || []);
        // track current empleado id for modal actions
        window.__currentEmpleadoDevicesId = empleadoId;
        if (countEmpleadoDevicesEl) countEmpleadoDevicesEl.textContent = String(assignedDevicesForSelectedEmployee.length || 0);
        if (btnShowEmpleadoDevices) btnShowEmpleadoDevices.disabled = assignedDevicesForSelectedEmployee.length === 0;
        if (infoEl) infoEl.style.display = 'block';
      } catch (err) {
        try { openGlobalMessageModal('error', 'Error', err && err.message ? err.message : 'Error cargando dispositivos del empleado'); } catch(e) {}
        assignedDevicesForSelectedEmployee = [];
        if (countEmpleadoDevicesEl) countEmpleadoDevicesEl.textContent = '0';
        if (btnShowEmpleadoDevices) btnShowEmpleadoDevices.disabled = true;
        if (infoEl) infoEl.style.display = 'none';
      }
    }

    // Company select + syncing and filtering
    const selEmpresaNew = document.getElementById('selectEmpresaNew');

    function populateEmpresaOptions() {
      try {
        if (!selEmpNew || !selEmpresaNew) return;
        const seen = new Set();
        Array.from(selEmpNew.querySelectorAll('option')).forEach(opt => {
          const e = (opt.getAttribute('data-empresa') || '').toString().trim();
          if (e && !seen.has(e)) { seen.add(e); const o = document.createElement('option'); o.value = e; o.textContent = e; selEmpresaNew.appendChild(o); }
        });
      } catch(e) { console.warn('populateEmpresaOptions error', e); }
    }

    if (selEmpresaNew) {
      // populate list from employee options
      populateEmpresaOptions();
      selEmpresaNew.addEventListener('change', (ev) => {
        try {
          const val = (ev.target.value || '').toString();
          if (!selEmpNew) return;
          const opts = Array.from(selEmpNew.options);
          const prev = selEmpNew.value;
          opts.forEach(o => {
            const e = (o.getAttribute('data-empresa') || '').toString();
            if (!val || e === val) { o.style.display = ''; } else { o.style.display = 'none'; }
          });
          const curOpt = selEmpNew.querySelector(`option[value="${prev}"]`);
          if (curOpt && curOpt.style.display === 'none') {
            selEmpNew.value = '';
            try { loadAssignedDevicesForEmpleado(''); } catch(e) {}
          }
        } catch(e) { console.warn('empresa change error', e); }
      });
    }

    // Update assigned devices and empresa info when employee selection changes
    if (selEmpNew) {
      selEmpNew.addEventListener('change', (e) => {
        const val = e.target.value;
        loadAssignedDevicesForEmpleado(val);
        // propagate empresa to empresa-select
        try {
          const opt = e.target.selectedOptions && e.target.selectedOptions[0];
          const empresa = opt ? (opt.getAttribute('data-empresa') || '') : '';
          if (selEmpresaNew && empresa) {
            selEmpresaNew.value = empresa;
          }
        } catch(e) { console.warn('sync empresa error', e); }
      });
    }

    // función para abrir el modal de nueva asignación de forma segura
    function openNewAsignacionModal() {
      // Recargar opciones y resetear formulario
      try {
        reloadDispositivosOptions();
      } catch(e) {}
      const form = document.getElementById('formNewAsignacion');
      if (form) form.reset();
      // Asegurar estado inicial del campo fecha con fecha de hoy
      const fechaIn = document.querySelector('#formNewAsignacion input[name="fecha_inicio_asignacion"]');
      if (fechaIn) {
        const d = new Date();
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth()+1).padStart(2,'0');
        const dd = String(d.getDate()).padStart(2,'0');
        fechaIn.value = `${yyyy}-${mm}-${dd}`;
      }
      openModal('modalNewAsignacion');
    }

    if (btnShowEmpleadoDevices) {
      btnShowEmpleadoDevices.addEventListener('click', () => {
        openEmpleadoDevicesModal();
      });
    }

    // (Removed inline transfer button; top-level transfer button remains)

    function openEmpleadoDevicesModal() {
      const modalId = 'modalEmpleadoDevices';
      const modal = document.getElementById(modalId);
      if (!modal) return;
      const tbody = modal.querySelector('table tbody');
      if (!tbody) return;
      tbody.innerHTML = '';
          // If no devices assigned, show friendly message
          if (!assignedDevicesForSelectedEmployee || assignedDevicesForSelectedEmployee.length === 0) {
            tbody.innerHTML = `<tr class="empty-state"><td colspan="7" style="text-align:center; padding:12px;">No se han asignado dispositivos aún.</td></tr>`;
            openModal(modalId, true);
            return;
          }
          // Columns: Tipo, Identificador, No de serie, Marca, Modelo, Fecha Inicio, Fecha Fin, Acciones
          assignedDevicesForSelectedEmployee.forEach(d => {
          const sn = d.numero_serie || '-';
          const tipo = d.categoria || (d.tipo || '-');
          const identificador = d.identificador || '-';
          const marca = d.nombre_marca || (d.marca || '-');
          const modelo = d.nombre_modelo || (d.modelo || '-');
          // Fecha inicio/fin: puede venir en formato ISO o como texto
          const fechaInicioRaw = d.fecha_inicio_asignacion || d.fecha_inicio || null;
          const fechaInicio = fechaInicioRaw ? (new Date(fechaInicioRaw)).toLocaleDateString() : '-';
          // Acciones: Botón editar de dispositivo y Botón RMA (finalizar asignación)
          const asignId = d.id_asignacion || d.fk_id_asignacion || d.id_asignacion_rel || d.id_asignacion || null;
          const deviceId = d.id_dispositivo || d.id_dispositivo_rel || d.fk_id_dispositivo || d.id || null;
          const editAsignBtn = asignId ? `<button class="icon-action" title="Editar asignación" onclick="(typeof openEditAsignacionModal==='function')?openEditAsignacionModal(${asignId}):void(0)" style="width:44px;height:44px;border-radius:10px;background:transparent;border:none;display:inline-flex;align-items:center;justify-content:center;margin-right:6px;position:relative;"><div style="width:42px;height:42px;border-radius:50%;background:#06a7e6;position:absolute;"></div><img src='/static/img/create1.png' alt='Editar' style='width:28px;height:28px;position:relative;z-index:1;'></button>` : '';
          const editDeviceBtn = deviceId ? `<button class="icon-action" title="Editar dispositivo" onclick="openEditDeviceModal(${deviceId})" style="width:44px;height:44px;border-radius:10px;background:transparent;border:none;display:inline-flex;align-items:center;justify-content:center;margin-right:6px;position:relative;"><div style="width:42px;height:42px;border-radius:50%;background:#f59e0b;position:absolute;"></div><img src='/static/img/edd.png' alt='Editar dispositivo' style='width:32px;height:32px;position:relative;z-index:1;'></button>` : '';
          const rmaBtn = deviceId ? `<button class="icon-action" title="Finalizar asignación" onclick="openFinalizeAsignacionFromTable(${deviceId})" style="width:44px;height:44px;border-radius:10px;background:transparent;border:none;display:inline-flex;align-items:center;justify-content:center;position:relative;"><div style="width:42px;height:42px;border-radius:50%;background:#e04343;position:absolute;"></div><img src='/static/img/rma.png' alt='RMA' style='width:28px;height:28px;position:relative;z-index:1;'></button>` : '';
          const actionsHtml = `<div style="display:flex;justify-content:center;align-items:center;gap:8px;">${[editAsignBtn, editDeviceBtn, rmaBtn].filter(Boolean).join('')}</div>`;
          const row = `<tr data-device-id="${deviceId || ''}">
            <td>${tipo}</td>
            <td>${identificador}</td>
            <td><code>${sn}</code></td>
            <td>${marca}</td>
            <td>${modelo}</td>
            <td>${fechaInicio}</td>
            <td>${actionsHtml}</td>
          </tr>`;
          tbody.innerHTML += row;
        });
      openModal(modalId, true);
    }

  // Remove assigned device row from the "Dispositivos asignados" modal and update counters
  function removeAssignedDeviceRow(deviceId, empleadoId) {
    try {
      if (!deviceId) return;
      // update DOM in modal if open
      const modal = document.getElementById('modalEmpleadoDevices');
      const tbody = modal ? modal.querySelector('table tbody') : null;
      if (tbody) {
      const row = tbody.querySelector(`tr[data-device-id="${deviceId}"]`);
      if (row) row.remove();
        // update internal array and counters
        try {
          assignedDevicesForSelectedEmployee = (Array.isArray(assignedDevicesForSelectedEmployee) ? assignedDevicesForSelectedEmployee : []).filter(d => String(d.id_dispositivo || d.id || d.fk_id_dispositivo || '') !== String(deviceId));
        } catch(e) { assignedDevicesForSelectedEmployee = []; }
        if (countEmpleadoDevicesEl) countEmpleadoDevicesEl.textContent = String(assignedDevicesForSelectedEmployee.length || 0);
        if (btnShowEmpleadoDevices) btnShowEmpleadoDevices.disabled = assignedDevicesForSelectedEmployee.length === 0;
        if ((assignedDevicesForSelectedEmployee.length || 0) === 0 && tbody) {
          tbody.innerHTML = `<tr class="empty-state"><td colspan="7" style="text-align:center; padding:12px;">No se han asignado dispositivos aún.</td></tr>`;
        }
      }
      // If empleadoId provided, decrement resumen badge
      try {
        if (empleadoId) {
          const rowEmp = document.querySelector(`#viewResumen tr[data-emp-id="${empleadoId}"]`);
          if (rowEmp) {
            const badge = rowEmp.querySelector('.device-count-badge');
            if (badge) {
              const cur = parseInt(badge.textContent || '0', 10) || 0;
              const next = Math.max(0, cur - 1);
              badge.textContent = String(next);
              if (next > 0) badge.classList.add('has-count'); else badge.classList.remove('has-count');
            }
          }
        }
      } catch(e) { /* non-fatal */ }
    } catch(e) { console.warn('removeAssignedDeviceRow error', e); }
  }

  // Update Fecha Fin cell in Histórico table for an assignment
  function updateHistoricoFechaFin(asignacionId, fechaFinStr) {
    try {
      if (!asignacionId) return;
      const tbody = document.querySelector('#historicoTable tbody');
      if (!tbody) return;
      const row = tbody.querySelector(`tr[data-asignacion-id="${asignacionId}"]`);
      if (!row) return;
      // Fecha Fin is the 4th cell (0-based index 3)
      const cells = row.children;
      if (cells && cells.length >= 4) {
        // Normalize fechaFinStr to YYYY-MM-DD to match server-rendered rows
        let out = '-';
        try {
          if (fechaFinStr) {
            // If it's already a Date object, use it; otherwise try parsing
            let d = (fechaFinStr instanceof Date) ? fechaFinStr : new Date(fechaFinStr);
            if (!isNaN(d.getTime())) {
              const yyyy = d.getFullYear();
              const mm = String(d.getMonth() + 1).padStart(2, '0');
              const dd = String(d.getDate()).padStart(2, '0');
              out = `${yyyy}-${mm}-${dd}`;
            } else {
              // Fallback: if string looks like yyyy-mm-dd as prefix, take it
              const m = String(fechaFinStr).match(/(\d{4}-\d{2}-\d{2})/);
              out = m ? m[1] : String(fechaFinStr);
            }
          }
        } catch(e) { console.warn('format fechaFin failed', e); out = String(fechaFinStr || '-'); }
        cells[3].textContent = out || '-';
      }
    } catch(e) { console.warn('updateHistoricoFechaFin error', e); }
  }

    /* ===== Transfer modal handlers ===== */
    async function openTransferDevicesModal() {
      const modalId = 'modalTransferDevices';
      const modal = document.getElementById(modalId);
      if (!modal) return;

      const selectSource = modal.querySelector('#selectSourceEmpleado');
      const selectTarget = modal.querySelector('#selectTargetEmpleado');
      const tbody = modal.querySelector('#transferSourceTbody');
      if (!selectSource || !selectTarget) return;

      // populate source and target selects from empleados_options
      const empleados = (window._empleadosOptions || []);

      // Do NOT preselect based on the 'Nueva asignación' modal í selects must be independent
      selectSource.innerHTML = '<option value="">-- Seleccionar empleado origen --</option>' + empleados.map(e => `<option value="${e.id}">${e.name}</option>`).join('');
      // populate target excluding the (optional) preselected source (none at open)
      const buildTargetOptions = (excludeId) => '<option value="">-- Seleccionar empleado receptor --</option>' + empleados.filter(e => e.id !== excludeId).map(e => `<option value="${e.id}">${e.name}</option>`).join('');
      selectTarget.innerHTML = buildTargetOptions(null);

      // load devices when source changes: populate source table and update target options
      selectSource.onchange = async function (e) {
        const empId = e.target.value ? parseInt(e.target.value, 10) : null;
        // preserve previous target selection if possible
        const prevTarget = selectTarget.value;
        // populate source devices
        await loadSourceDevices(empId);
        // rebuild target options excluding the chosen source
        selectTarget.innerHTML = buildTargetOptions(empId);
        // restore previous target if still available and not equal to the new source
        if (prevTarget && String(prevTarget) !== String(empId)) {
          const opt = selectTarget.querySelector(`option[value="${prevTarget}"]`);
          if (opt) selectTarget.value = prevTarget;
        } else {
          selectTarget.value = '';
        }
        // clear target table content until selection (or reload if restored)
        document.getElementById('transferTargetTbody').innerHTML = '';
        if (selectTarget.value) loadTargetDevices(selectTarget.value);
      };

      // when target changes, load its devices for preview/conflict detection
      selectTarget.onchange = function(e) {
        const empId = e.target.value ? parseInt(e.target.value, 10) : null;
        loadTargetDevices(empId);
      };

      // clear previous rows and state, then open modal
      const tbodyInit = document.getElementById('transferSourceTbody');
      const tbodyTargetInit = document.getElementById('transferTargetTbody');
      if (tbodyInit) tbodyInit.innerHTML = `<tr class="empty-state"><td colspan="5" style="text-align:center; padding:12px;">Selecciona un empleado origen para ver sus dispositivos</td></tr>`;
      if (tbodyTargetInit) tbodyTargetInit.innerHTML = `<tr class="empty-state"><td colspan="5" style="text-align:center; padding:12px;">Selecciona un empleado receptor para ver sus dispositivos</td></tr>`;
      // prompt user to select source until an employee is chosen
      const noticeEl = document.getElementById('transferNotice');
      if (noticeEl) { noticeEl.textContent = 'Selecciona un empleado origen para ver sus dispositivos'; noticeEl.style.display = 'block'; }
      assignedDevicesForSelectedEmployee = [];
      const selectAllInit = document.getElementById('transferSelectAll');
      if (selectAllInit) { selectAllInit.checked = false; selectAllInit.indeterminate = false; }
      updateTransferNotice();
      openModal(modalId, true);
      // adjust layout immediately after open
      setTimeout(adjustTransferModal, 20);
    }

    let transferSourceDevices = [];
    let transferTargetDevices = [];

    async function loadSourceDevices(empId) {
      transferSourceDevices = [];
      const tbody = document.getElementById('transferSourceTbody');
      const label = document.getElementById('transferSourceLabel');
      if (label) label.textContent = empId ? document.querySelector(`#selectSourceEmpleado option[value="${empId}"]`).textContent : '-';
      if (!empId) { if (tbody) tbody.innerHTML = `<tr class="empty-state"><td colspan="5" style="text-align:center; padding:12px;">Selecciona un empleado origen para ver sus dispositivos</td></tr>`; updateTransferNotice(); return; }
      try {
        const r = await fetch(`/devices/asignaciones/empleado/${empId}`);
        if (!r.ok) throw new Error('No se pudo obtener dispositivos');
        const j = await r.json();
        const dispositivos = Array.isArray(j.dispositivos) ? j.dispositivos : (j.dispositivos || []);
        transferSourceDevices = dispositivos;
        if (tbody) {
          if (!dispositivos || dispositivos.length === 0) {
            tbody.innerHTML = `<tr class="empty-state"><td colspan="5" style="text-align:center; padding:12px;">El empleado seleccionado no tiene dispositivos para transferir</td></tr>`;
          } else {
            tbody.innerHTML = dispositivos.map(d => `
          <tr>
            <td><input type="checkbox" class="transfer-device-chk" value="${d.id_dispositivo}"></td>
            <td>${d.categoria || (d.tipo||'')}</td>
            <td><code>${d.numero_serie || ''}</code></td>
            <td>${d.nombre_marca || ''}</td>
            <td>${d.nombre_modelo || ''}</td>
          </tr>`).join('\n');
          }
        }
        // wire events
        Array.from(document.querySelectorAll('#transferSourceTbody .transfer-device-chk')).forEach(c => c.addEventListener('change', updateTransferNotice));
        const selectAll = document.getElementById('transferSelectAll');
        if (selectAll) {
          selectAll.checked = false; selectAll.indeterminate = false;
          if (!selectAll._bound) {
            selectAll.addEventListener('change', function(e){
              const checked = !!e.target.checked;
              const rows = Array.from(document.querySelectorAll('#transferSourceTbody .transfer-device-chk'));
              rows.forEach(chk => { chk.checked = checked; chk.dispatchEvent(new Event('change')); });
            });
            selectAll._bound = true;
          }
        }
        updateTransferNotice();
      } catch (e) {
        try { openGlobalMessageModal('error', 'Error', e && e.message ? e.message : 'Error cargando dispositivos origen'); } catch(err) {}
        if (tbody) tbody.innerHTML = '';
        transferSourceDevices = [];
        updateTransferNotice();
      }
    }

    async function loadTargetDevices(empId) {
      transferTargetDevices = [];
      const tbody = document.getElementById('transferTargetTbody');
      const label = document.getElementById('transferTargetLabel');
      if (label) label.textContent = empId ? document.querySelector(`#selectTargetEmpleado option[value="${empId}"]`).textContent : '-';
      if (!empId) { if (tbody) tbody.innerHTML = `<tr class="empty-state"><td colspan="5" style="text-align:center; padding:12px;">Selecciona un empleado receptor para ver sus dispositivos</td></tr>`; return; }
      try {
        const r = await fetch(`/devices/asignaciones/empleado/${empId}`);
        if (!r.ok) throw new Error('No se pudo obtener dispositivos');
        const j = await r.json();
        const dispositivos = Array.isArray(j.dispositivos) ? j.dispositivos : (j.dispositivos || []);
        transferTargetDevices = dispositivos;
        if (tbody) {
          if (!dispositivos || dispositivos.length === 0) {
            tbody.innerHTML = `<tr class="empty-state"><td colspan="5" style="text-align:center; padding:12px;">El empleado seleccionado no tiene dispositivos</td></tr>`;
          } else {
            tbody.innerHTML = dispositivos.map(d => `
          <tr>
            <td></td>
            <td>${d.categoria || (d.tipo||'')}</td>
            <td><code>${d.numero_serie || ''}</code></td>
            <td>${d.nombre_marca || ''}</td>
            <td>${d.nombre_modelo || ''}</td>
          </tr>`).join('\n');
          }
        }
      } catch (e) {
        try { openGlobalMessageModal('error', 'Error', e && e.message ? e.message : 'Error cargando dispositivos destino'); } catch(err) {}
        if (tbody) tbody.innerHTML = '';
        transferTargetDevices = [];
      }
    }

    async function confirmTransferDevices() {
      const selectSource = document.getElementById('selectSourceEmpleado');
      const empleadoFrom = selectSource?.value || selEmpNew?.value;
      const selectTarget = document.getElementById('selectTargetEmpleado');
      const empleadoTo = selectTarget?.value;
      if (!empleadoFrom || !empleadoTo) return showModalMessage('error', 'Error', 'Seleccione ambos empleados');

      const checks = Array.from(document.querySelectorAll('#transferSourceTbody .transfer-device-chk:checked'));
      if (checks.length === 0) return showModalMessage('error', 'Error', 'Seleccione al menos un dispositivo');

      const deviceIds = checks.map(c => parseInt(c.value, 10));
      // ensure we have target devices loaded for conflict detection
      if (!transferTargetDevices || transferTargetDevices.length === 0) {
        await loadTargetDevices(empleadoTo);
      }

      // detect conflicts by device type: if destination already has that tipo, it's a conflict
      const targetTypes = new Map();
      transferTargetDevices.forEach(d => {
        const t = (d.categoria || d.tipo || '').toString();
        if (!t) return;
        if (!targetTypes.has(t)) targetTypes.set(t, []);
        targetTypes.get(t).push(d);
      });

      const selectedDevices = deviceIds.map(id => transferSourceDevices.find(x => x.id_dispositivo === id)).filter(Boolean);
      const conflictsByType = new Map();
      selectedDevices.forEach(sd => {
        const t = (sd.categoria || sd.tipo || '').toString();
        if (targetTypes.has(t)) {
          if (!conflictsByType.has(t)) conflictsByType.set(t, []);
          conflictsByType.get(t).push(sd);
        }
      });

      if (conflictsByType.size > 0) {
        // build list for modal showing the devices that the destination already has
        const listEl = document.getElementById('transferConflictsList');
        const targetName = document.querySelector(`#selectTargetEmpleado option[value="${empleadoTo}"]`)?.textContent || 'Empleado destino';
        if (listEl) {
          listEl.innerHTML = '';
          conflictsByType.forEach((_, type) => {
            const targetDevicesOfType = targetTypes.get(type) || [];
            const items = targetDevicesOfType.map(d => `<strong>${d.numero_serie || ''}</strong> (${d.nombre_marca || ''} ${d.nombre_modelo || ''})`).join(', ');
            const li = document.createElement('li');
            li.innerHTML = `${type}: ${items}`;
            listEl.appendChild(li);
          });
        }
        // show modal with message including target name
        openModal('modalTransferConflicts');
        return;
      }

      // proceed with transfer since no conflicts
      try {
        const resp = await fetch('/devices/asignaciones/transfer', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          credentials: 'same-origin',
          body: JSON.stringify({ from_employee: parseInt(empleadoFrom,10), to_employee: parseInt(empleadoTo,10), device_ids: deviceIds })
        });
        const j = await resp.json().catch(()=>({}));
        if (resp.ok && j.success) {
          closeModal('modalTransferDevices');
          
          // Limpiar selectores del modal
          const selectSource = document.getElementById('selectSourceEmpleado');
          const selectTarget = document.getElementById('selectTargetEmpleado');
          if (selectSource) selectSource.value = '';
          if (selectTarget) selectTarget.value = '';
          
          // Recargar tabla usando tbody en lugar de recargar página completa
          if (typeof reloadAsignacionesTable === 'function') {
            await reloadAsignacionesTable();
          }
          
          openGlobalSuccessModal(j.message || 'Transferencia realizada');
        } else {
          openGlobalMessageModal('error', 'Error', j.message || 'No se pudo realizar la transferencia');
        }
      } catch (err) {
        try { openGlobalMessageModal('error', 'Error', err && err.message ? err.message : 'No se pudo realizar la transferencia'); } catch(e) {}
      }
    }

    function updateTransferNotice() {
      const modal = document.getElementById('modalTransferDevices');
      const notice = document.getElementById('transferNotice');
      const tbody = document.getElementById('transferSourceTbody');
      const selectSource = document.getElementById('selectSourceEmpleado');
      if (!notice) return;
      // If no source selected, ask the user to select one
      if (!selectSource || !selectSource.value) {
        notice.textContent = 'Selecciona un empleado origen para ver sus dispositivos';
        notice.style.display = 'block';
        return;
      }
      const rows = tbody ? Array.from(tbody.children) : [];
      if (rows.length === 0) {
        notice.textContent = 'No cuenta con dispositivos en transferencia de dispositivos';
        notice.style.display = 'block';
        return;
      }
      const checked = Array.from(modal.querySelectorAll('.transfer-device-chk:checked'));
      if (checked.length === 0) {
        notice.textContent = 'Selecciona los dispositivos a transferir';
        notice.style.display = 'block';
      } else {
        notice.style.display = 'none';
      }
      // update select-all checkbox state
      const selectAll = document.getElementById('transferSelectAll');
      if (selectAll) {
        const total = rows.length;
        const checkedCount = checked.length;
        selectAll.checked = checkedCount === total && total > 0;
        selectAll.indeterminate = checkedCount > 0 && checkedCount < total;
      }
    }

    // Adjust transfer modal sizing dynamically so the table area doesn't cause layout jumps
    function adjustTransferModal() {
      const modal = document.getElementById('modalTransferDevices');
      if (!modal || !modal.classList.contains('active')) return;
      const dialog = modal.querySelector('.modal');
      const header = dialog.querySelector('.modal-header');
      const footer = dialog.querySelector('.modal-footer');
      const tableContainer = dialog.querySelector('.table-container');
      // compute available height for table container
      const viewportH = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
      const headerH = header ? header.getBoundingClientRect().height : 0;
      const footerH = footer ? footer.getBoundingClientRect().height : 0;
      const selectsH = (dialog.querySelectorAll('select')?.length || 0) ? 70 : 0;
      // leave some breathing room
      const padding = 60;
      const available = Math.max(160, Math.floor(viewportH - headerH - footerH - selectsH - padding));
      if (tableContainer) {
        tableContainer.style.maxHeight = available + 'px';
        tableContainer.style.overflow = 'auto';
      }
    }

    // Recompute on resize while modal is open
    window.addEventListener('resize', () => {
      try { adjustTransferModal(); } catch(e){}
    });

    // Bind confirm button to open confirmation modal, and wire confirm/cancel inside it
    try {
      const btnConfirm = document.getElementById('btnConfirmTransfer');
      const btnYes = document.getElementById('btnTransferConfirmYes');
      const btnNo = document.getElementById('btnTransferConfirmNo');
      if (btnConfirm && !btnConfirm._bound) {
        btnConfirm.addEventListener('click', () => {
          // validate selection before showing confirm modal
          const selectSource = document.getElementById('selectSourceEmpleado');
          const selectTarget = document.getElementById('selectTargetEmpleado');
          const checks = Array.from(document.querySelectorAll('#transferSourceTbody .transfer-device-chk:checked'));
          if (!selectSource || !selectSource.value || !selectTarget || !selectTarget.value) {
            return showModalMessage('error','Error','Seleccione ambos empleados antes de confirmar');
          }
          if (checks.length === 0) {
            return showModalMessage('error','Error','Seleccione al menos un dispositivo');
          }
          openModal('modalTransferConfirm');
        });
        btnConfirm._bound = true;
      }
      if (btnNo && !btnNo._bound) {
        btnNo.addEventListener('click', () => closeModal('modalTransferConfirm'));
        btnNo._bound = true;
      }
      if (btnYes && !btnYes._bound) {
        btnYes.addEventListener('click', async () => {
          // close confirm modal and run transfer
          closeModal('modalTransferConfirm');
          try { await confirmTransferDevices(); } catch (err) { try { openGlobalMessageModal('error','Error', err && err.message ? err.message : 'No se pudo realizar la transferencia'); } catch(e) {} }
        });
        btnYes._bound = true;
      }
    } catch(e) { /* ignore */ }

/* ========================================================================= */

async function openEditAsignacionModal(id) {
  document.getElementById('editAsignacionError').style.display = 'none';
  document.getElementById('editAsignacionConfirm').value = '';
  document.getElementById('btnSaveAsignacion').disabled = true;
  try {
    const r = await fetch(`/devices/asignacion/${id}`);
    if (!r.ok) throw new Error('No encontrado');
    const data = await r.json();
    document.getElementById('editAsignacionId').value = id;
    document.getElementById('editAsignacionSerie').textContent = data.numero_serie || '';
    document.getElementById('editAsignacionMarca').textContent = data.nombre_marca || '';
    document.getElementById('editAsignacionModelo').textContent = data.nombre_modelo || '';
    document.getElementById('editAsignacionTipo').textContent = data.categoria || '';
    document.getElementById('editAsignacionEmpleado').textContent = data.empleado_nombre || data.fk_id_empleado;
    document.getElementById('editAsignacionFechaInicio').textContent = data.fecha_inicio_asignacion ? new Date(data.fecha_inicio_asignacion).toLocaleDateString() : '';
    document.getElementById('editAsignacionFechaFin').value = data.fecha_fin_asignacion ? data.fecha_fin_asignacion.split('T')[0] : '';
    document.getElementById('editAsignacionObservaciones').value = data.observaciones || '';
    openModal('modalEditAsignacion', true);
  } catch (err) {
    showModalMessage('error', 'Error', 'No se pudo cargar la asignación');
  }
}

function closeEditAsignacionModal() {
  closeModal('modalEditAsignacion');
}

function refreshAsignacionSaveState() {
  const confirmText = document.getElementById('editAsignacionConfirm').value.trim();
  document.getElementById('btnSaveAsignacion').disabled = !(confirmText === 'CONFIRMAR');
}

['editAsignacionConfirm'].forEach(id => {
  const el = document.getElementById(id);
  if (el) el.addEventListener('input', refreshAsignacionSaveState);
});

/* ========================================================================= */

// Helper to open device editor from asignaciones: use in-page editor if available, otherwise redirect
function openEditDeviceFromAsignaciones(deviceId) {
  try {
    if (!deviceId) return;
    if (typeof openEditDeviceModal === 'function') {
      try {
        openEditDeviceModal(deviceId);
      } catch (err) {
        try { openGlobalMessageModal('error', 'Error', err && err.message ? err.message : 'No se pudo abrir el editor de dispositivo en esta ventana.'); } catch(e){ alert('No se pudo abrir el editor de dispositivo en esta ventana.'); }
      }
      return;
    }
  } catch (e) {
    console.warn('openEditDeviceModal not available in this page', e);
  }
  // If inline editor not available, show message instead of redirecting
  try { openGlobalMessageModal('info', 'Info', 'El editor en línea no está disponible en esta vista.'); } catch(e) { alert('El editor en línea no está disponible en esta vista.'); }
}

/* ========================================================================= */

// =========================
// GLOBAL FUNCTIONS (available to all onclick handlers)
// =========================

// Toggle IMEI2 field visibility for edit modal
function toggleEditImei2Field() {
  const chk = document.getElementById('checkEditImei2');
  const label = document.getElementById('labelEditImei2');
  const input = document.getElementById('editDeviceImei2');
  if (!chk || !label || !input) return;
  
  if (chk.checked) {
    // Show field and restore original value if exists
    label.style.display = '';
    input.required = true;
    // Restore original IMEI2 if it was cleared before
    if (!input.value && window.originalEditImei2) {
      input.value = window.originalEditImei2;
    }
  } else {
    // Hide field and save current value before clearing
    label.style.display = 'none';
    window.originalEditImei2 = input.value || '';
    input.required = false;
    input.value = '';
  }
}

// Minimal helpers copied to support inline editing flow
async function updateDeviceRow(deviceId) {
  if (!deviceId) return;
  try {
    const r = await fetch(`/devices/${deviceId}`);
    if (!r.ok) return;
    const d = await r.json();
    const targetRow = document.querySelector(`#devicesTable tbody tr[data-device-id="${deviceId}"]`);
    if (!targetRow) return;
    const statusColor = (d && d.estado !== undefined) ? (d.estado == 1 ? 'success' : d.estado == 2 ? 'warning' : d.estado == 3 ? 'secondary' : 'danger') : 'danger';
    const cells = targetRow.children;
    if (cells.length >= 6) {
      cells[0].textContent = d.categoria || '';
      cells[1].innerHTML = `<code>${d.numero_serie || ''}</code>`;
      cells[2].textContent = d.nombre_modelo || '';
      cells[3].textContent = d.nombre_marca || '';
      cells[4].innerHTML = `<span class="text-${statusColor}">${d.estado !== undefined ? d.estado : ''}</span>`;
      cells[5].textContent = d.ip_asignada || '';
    }
  } catch (e) { console.warn('updateDeviceRow failed', e); }
}

async function openEditDeviceModal(deviceId) {
  try {
    const errEl = document.getElementById('editDeviceError'); if (errEl) { errEl.style.display='none'; errEl.textContent=''; }
    // reset assignment UI
    try {
      const fieldset = document.getElementById('fieldsetAsignacion');
      const infoLabel = document.getElementById('labelAsignacionInfo');
      const inline = document.getElementById('inlineFinalizeContainer');
      const btn = document.getElementById('btnFinalizeAsignacion');
      if (inline) inline.style.display = 'none';
      if (infoLabel) { infoLabel.style.display = 'flex'; document.getElementById('infoAsignadoPersona').textContent = '-'; document.getElementById('infoAsignadoDesde').textContent = '-'; }
      if (btn) btn.style.display = 'none';
      if (fieldset) fieldset.style.display = 'none';
      pendingFinalizeDeviceId = null;
      pendingAsignacionData = null;
    } catch(e) { console.warn('Could not reset assignment UI', e); }
    const resp = await fetch(`/devices/${deviceId}`);
    if (!resp.ok) { const j = await resp.json().catch(()=>({})); return openGlobalMessageModal('error', 'Error', j.message || 'No se pudo cargar el dispositivo'); }
    const dev = await resp.json();
    const set = (id, value) => { const el = document.getElementById(id); if (!el) return; if (el.tagName === 'SELECT' || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.value = value ?? ''; };
    document.getElementById('editDeviceId').value = deviceId;
    const marcaSelect = document.getElementById('editSelectMarca');
    const modeloSelect = document.getElementById('editSelectModelo');
    if (dev.fk_id_marca) {
      let marcaOption = marcaSelect.querySelector(`option[value="${dev.fk_id_marca}"]`);
      if (!marcaOption) { marcaOption = document.createElement('option'); marcaOption.value = dev.fk_id_marca; marcaOption.textContent = dev.nombre_marca || `Marca ${dev.fk_id_marca}`; marcaSelect.appendChild(marcaOption); }
      marcaSelect.value = dev.fk_id_marca;
    }
    if (dev.fk_id_modelo) {
      let modeloOption = modeloSelect.querySelector(`option[value="${dev.fk_id_modelo}"]`);
      if (!modeloOption) { modeloOption = document.createElement('option'); modeloOption.value = dev.fk_id_modelo; modeloOption.textContent = dev.nombre_modelo || `Modelo ${dev.fk_id_modelo}`; modeloSelect.appendChild(modeloOption); }
      modeloSelect.value = dev.fk_id_modelo;
    }
    set('editDeviceTipo', dev.categoria);
    set('editDeviceSerial', dev.numero_serie);
    try { const elId = document.getElementById('editDeviceIdentificador'); if (elId) elId.value = dev.identificador || ''; } catch(e) {}
    set('editDeviceImei', dev.imei);
    set('editDeviceImei2', dev.imei2 || '');
    set('editDeviceMac', dev.direccion_mac);
    set('editDeviceIp', dev.ip_asignada);
    set('editDeviceObservaciones', dev.observaciones);
    let fechaValue = dev.fecha_obt || dev.fecha_obtencion || '';
    if (fechaValue && typeof fechaValue === 'string') { if (fechaValue.includes('-') && fechaValue.split('-').length === 3) { fechaValue = fechaValue.split('T')[0]; } else if (fechaValue.match(/^\d{4}-\d{2}-\d{2}/)) { fechaValue = fechaValue.match(/\d{4}-\d{2}-\d{2}/)[0]; } }
    set('editDeviceFechaObtencion', fechaValue);
    set('editDeviceColor', dev.color);
    set('editDeviceTamano', dev.tamano);
    set('editDeviceEstado', dev.estado);
    const cargadorEl = document.getElementById('editDeviceCargador'); if (cargadorEl) cargadorEl.checked = dev.cargador ? true : false;
    const checkEditImei2 = document.getElementById('checkEditImei2');
    const labelEditImei2 = document.getElementById('labelEditImei2');
    const editDeviceImei2 = document.getElementById('editDeviceImei2');
    if (editDeviceImei2 && dev.imei2) { window.originalEditImei2 = dev.imei2; checkEditImei2.checked = true; labelEditImei2.style.display = ''; } else { window.originalEditImei2 = ''; if (checkEditImei2) checkEditImei2.checked = false; if (labelEditImei2) labelEditImei2.style.display = 'none'; if (editDeviceImei2) editDeviceImei2.value = ''; }
    try { await checkActiveAsignacionForEdit(deviceId); } catch(e){ console.warn('checkActiveAsignacionForEdit failed', e); }
    toggleEditDispositivoFields && toggleEditDispositivoFields();
    openModal('modalEditDevice', true);
  } catch (e) { try { openGlobalMessageModal('error', 'Error', e && e.message ? e.message : 'No se pudo cargar el dispositivo'); } catch(err) {} }
}

// Toggle visibility of device fields based on device type
function toggleEditDispositivoFields() {
  const tipoSelect = document.getElementById('editDeviceTipo');
  const tipo = (tipoSelect?.value || '').toLowerCase();

  const isCelular = tipo === 'celular';
  const isTablet = tipo === 'tablet';
  const isPC = tipo === 'pc';
  const isMobile = isCelular || isTablet;
  const isLaptop = tipo === 'laptop';
  const isMonitor = tipo === 'monitor';
  const isImpresora = tipo === 'impresora';
  const isVoip = tipo === 'telefono voip';
  const isAuricular = tipo === 'auriculares';
  const isTeclado = tipo === 'teclado';
  const isRatom = tipo === 'mouse';
  const isRouter = tipo === 'router';
  const isSwitch = tipo === 'switch';
  const isUPS = tipo === 'ups';
  const isAdaptador = tipo === 'adaptador';
  const isPeriferico = isAuricular || isTeclado || isRatom || isMonitor || isImpresora || isVoip || isUPS;

  // IMEI: only for celular and tablet
  const imeiEditInput = document.getElementById('editDeviceImei');
  document.getElementById('labelEditImei').style.display = isMobile ? '' : 'none';
  document.getElementById('labelEditImei2Checkbox').style.display = isMobile ? '' : 'none';
  if (imeiEditInput) imeiEditInput.required = isMobile;
  if (!isMobile) {
    document.getElementById('checkEditImei2').checked = false;
    document.getElementById('labelEditImei2').style.display = 'none';
  }

  // MAC: hide for periféricos, monitor, UPS, Adaptador, Celular y PC
  const lblEditMac = document.getElementById('labelEditMac');
  lblEditMac.style.display = (isPeriferico || isMonitor || isCelular || isPC || isAdaptador) ? 'none' : '';
  if (lblEditMac.style.display === 'none') { try { const eMac = document.getElementById('editDeviceMac'); if (eMac) eMac.value = ''; } catch(e){} }

  // IP
  const lblEditIp = document.getElementById('labelEditIp');
  lblEditIp.style.display = (isCelular || isTablet || isRouter || isSwitch || isLaptop || isImpresora || isVoip || isPC) ? '' : 'none';
  if (lblEditIp.style.display === 'none') { try { const eIp = document.getElementById('editDeviceIp'); if (eIp) eIp.value = 'N/A'; } catch(e){} }

  // UPS fields
  const upsFieldsEdit = document.getElementById('upsFieldsEditDevice');
  if (upsFieldsEdit) upsFieldsEdit.style.display = isUPS ? '' : 'none';

  // Color: show for all
  document.getElementById('labelEditColor').style.display = '';

  // Tamaño: celular, tablet, monitor, laptop
  document.getElementById('labelEditTamano').style.display = (isCelular || isTablet || isMonitor || isLaptop) ? '' : 'none';

  // Cargador: ocultar para Adaptador
  document.getElementById('labelEditDeviceCargador').style.display = isAdaptador ? 'none' : '';

  // Observaciones: show for all
  document.getElementById('labelEditObservaciones').style.display = '';

  // Extensión VoIP: solo VoIP
  document.getElementById('labelEditExtension').style.display = isVoip ? '' : 'none';

  // Fecha obtención: show for all
  document.getElementById('labelEditFechaObt').style.display = '';

  // Estado: solo Impresora
  document.getElementById('labelEditDeviceEstado').style.display = isImpresora ? '' : 'none';
}

// =========================
// END GLOBAL FUNCTIONS
// =========================


// Save edit
document.getElementById('btnSaveEditDevice')?.addEventListener('click', async () => {
  const id = document.getElementById('editDeviceId').value;
  const editFechaVal = document.getElementById('editDeviceFechaObtencion')?.value || '';
  if (editFechaVal) { const d = new Date(editFechaVal); d.setHours(0,0,0,0); const today = new Date(); today.setHours(0,0,0,0); if (d > today) { openModal('modalFechaFutura'); return; } }
  const payload = {
    numero_serie: document.getElementById('editDeviceSerial')?.value || null,
    identificador: document.getElementById('editDeviceIdentificador')?.value || null,
    imei: document.getElementById('editDeviceImei')?.value || null,
    fecha_obt: document.getElementById('editDeviceFechaObtencion')?.value || null,
    imei2: document.getElementById('editDeviceImei2')?.value || null,
    direccion_mac: document.getElementById('editDeviceMac')?.value || null,
    ip_asignada: document.getElementById('editDeviceIp')?.value || null,
    observaciones: document.getElementById('editDeviceObservaciones')?.value || null,
    color: document.getElementById('editDeviceColor')?.value || null,
    tamano: document.getElementById('editDeviceTamano')?.value || null,
    cargador: document.getElementById('editDeviceCargador')?.checked ? 1 : 0,
    estado: (function(){ const v = document.getElementById('editDeviceEstado')?.value; return v !== '' ? parseInt(v) : null })(),
    fk_id_modelo: (document.getElementById('editSelectModelo')?.value) || null,
    fk_id_marca: (document.getElementById('editSelectMarca')?.value) || null,
    categoria: document.getElementById('editDeviceTipo')?.value || null
  };
  const tipo = payload.categoria?.toLowerCase() || '';
  if (['teclado', 'mouse', 'auriculares', 'monitor', 'pc', 'celular', 'tablet', 'ups', 'adaptador'].includes(tipo)) { payload.ip_asignada = null; }
  // Normalizar 'N/A' a null en cualquier caso
  if ((payload.ip_asignada || '').toString().toUpperCase() === 'N/A') { payload.ip_asignada = null; }
  try {
    const ipVal = payload.ip_asignada || '';
    if (ipVal) {
      const chk = await fetch('/devices/check-ip', { method: 'POST', headers: {'Content-Type':'application/json'}, credentials: 'same-origin', body: JSON.stringify({ ip: ipVal }) });
      if (chk.ok) {
        const chkData = await chk.json().catch(()=>({}));
        if (chkData.exists && chkData.device && parseInt(chkData.device.id_dispositivo) !== parseInt(id)) {
          const dev = chkData.device || {};
          const msgEl = document.getElementById('ipConflictMessage');
          if (msgEl) msgEl.textContent = `La dirección IP (${ipVal}) ya está asignada a ${dev.categoria || ''} ${dev.nombre_marca || ''} ${dev.nombre_modelo || ''}`;
          window.__pendingEditDevicePayload = payload;
          window.__pendingEditDeviceId = id;
          window.__pendingEditDeviceConflictOwner = dev;
          openModal('modalIpConflict');
          return;
        }
      }
    }
  } catch (e) { try { openGlobalMessageModal('error', 'Error', e && e.message ? e.message : 'IP check failed'); } catch(err) {} }
  try {
    const r = await fetch(`/devices/${id}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, credentials: 'same-origin', body: JSON.stringify(payload) });
    const data = await r.json().catch(()=>({}));
    if (r.ok && data.success) {
      closeModal('modalEditDevice');
      if (typeof reloadDevicesTable === 'function') await reloadDevicesTable();
      openGlobalSuccessModal(data.message || 'Dispositivo actualizado');
    } else {
      const err = document.getElementById('editDeviceError'); if (err) { err.textContent = data.message || 'No se pudo actualizar'; err.style.display='block'; }
    }
  } catch (err) { const el = document.getElementById('editDeviceError'); if (el) { el.textContent = 'Error actualizando dispositivo'; el.style.display='block'; } }
});

// Finalize assignment helpers (minimal wiring)
let pendingFinalizeDeviceId = null;
let pendingAsignacionData = null;
async function checkActiveAsignacionForEdit(deviceId) {
  const btn = document.getElementById('btnFinalizeAsignacion');
  const fieldset = document.getElementById('fieldsetAsignacion');
  const infoLabel = document.getElementById('labelAsignacionInfo');
  const inline = document.getElementById('inlineFinalizeContainer');
  if (!btn || !fieldset) return;
  pendingFinalizeDeviceId = null; pendingAsignacionData = null; btn.style.display = 'none'; fieldset.style.display = 'none';
  try {
    const r = await fetch(`/devices/${deviceId}/asignacion-activa`, { credentials: 'same-origin' });
    if (!r.ok) return;
    const j = await r.json();
    if (j && j.active && j.asignacion) {
      pendingFinalizeDeviceId = deviceId; 
      pendingAsignacionData = j.asignacion; 
      fieldset.style.display = 'block'; 
      if (infoLabel) infoLabel.style.display = 'flex'; 
      if (inline) inline.style.display = 'none';
      const rawPersona = j.asignacion.empleado_nombre || null; 
      const empleadoId = j.asignacion.fk_id_empleado || null; 
      const fecha = j.asignacion.fecha_inicio_asignacion ? new Date(j.asignacion.fecha_inicio_asignacion).toLocaleDateString() : '-';
      
      if (rawPersona && String(rawPersona).trim() !== '') { 
        document.getElementById('infoAsignadoPersona').textContent = rawPersona; 
        document.getElementById('finalizeAsignadoPersona') && (document.getElementById('finalizeAsignadoPersona').textContent = rawPersona); 
      } else if (empleadoId) { 
        document.getElementById('infoAsignadoPersona').textContent = String(empleadoId); 
        document.getElementById('finalizeAsignadoPersona') && (document.getElementById('finalizeAsignadoPersona').textContent = String(empleadoId)); 
        try { 
          const empResp = await fetch('/auth/employees', { credentials: 'same-origin' }); 
          if (empResp.ok) { 
            const empJson = await empResp.json(); 
            const list = empJson && empJson.employees ? empJson.employees : empJson || []; 
            const found = list.find(e => Number(e.IdEmpleado || e.id || e.Id) === Number(empleadoId)); 
            if (found) { 
              const name = found.NombreCompleto || found.name || found.Nombre || found.NombreEmpleado || found.NombreCompleto; 
              if (name) { 
                document.getElementById('infoAsignadoPersona').textContent = name; 
                document.getElementById('finalizeAsignadoPersona') && (document.getElementById('finalizeAsignadoPersona').textContent = name); 
              } 
            } 
          } 
        } catch (err) { 
          console.warn('Could not resolve empleado name', err); 
        } 
      } else { 
        document.getElementById('infoAsignadoPersona').textContent = '-'; 
        document.getElementById('finalizeAsignadoPersona') && (document.getElementById('finalizeAsignadoPersona').textContent = '-'); 
      }
      
      document.getElementById('infoAsignadoDesde').textContent = fecha; 
      document.getElementById('finalizeAsignadoDesde') && (document.getElementById('finalizeAsignadoDesde').textContent = fecha); 
      btn.style.display = 'block';
    }
  } catch (e) { try { openGlobalMessageModal('error', 'Error', e && e.message ? e.message : 'Error checking active assignment'); } catch(err) {} }
}

function finalizarAsignacionClick() { if (!pendingFinalizeDeviceId || !pendingAsignacionData) { openGlobalMessageModal('info', 'Info', 'No hay asignación activa para finalizar'); return; } openFinalizeAsignacionModal(); }

function cancelFinalizeAsignacionInline() { const infoLabel = document.getElementById('labelAsignacionInfo'); const btn = document.getElementById('btnFinalizeAsignacion'); const inline = document.getElementById('inlineFinalizeContainer'); const input = document.getElementById('editAsignacionConfirm'); const err = document.getElementById('inlineFinalizeAsignacionError'); if (inline) inline.style.display = 'none'; if (infoLabel) infoLabel.style.display = 'flex'; if (btn) btn.style.display = 'block'; if (input) { input.value = ''; } if (err) { err.style.display = 'none'; err.textContent = ''; } }

async function confirmFinalizeAsignacionInline() {
  const btn = document.getElementById('btnConfirmFinalizeInline'); const errEl = document.getElementById('inlineFinalizeAsignacionError'); if (!pendingFinalizeDeviceId) return; if (btn) { btn.disabled = true; btn.textContent = 'Finalizando...'; } if (errEl) { errEl.style.display = 'none'; errEl.textContent = ''; }
  try {
    const r = await fetch(`/devices/${pendingFinalizeDeviceId}/finalizar-asignacion`, { method: 'POST', credentials: 'same-origin' });
    const data = await r.json().catch(()=>({}));
    if (r.ok && data.success) {
      const inline = document.getElementById('inlineFinalizeContainer'); const fieldset = document.getElementById('fieldsetAsignacion'); const btnFin = document.getElementById('btnFinalizeAsignacion'); if (inline) inline.style.display = 'none'; if (btnFin) btnFin.style.display = 'none'; if (fieldset) fieldset.style.display = 'none'; try { await updateDeviceRow(pendingFinalizeDeviceId); } catch(e){ console.warn('updateDeviceRow failed', e); } try { removeAssignedDeviceRow(pendingFinalizeDeviceId, pendingAsignacionData && (pendingAsignacionData.fk_id_empleado || pendingAsignacionData.fk_id_empleado === 0 ? pendingAsignacionData.fk_id_empleado : null)); } catch(e){}
      if (data && data.fecha_fin) {
        try {
          const asignId = pendingAsignacionData && (pendingAsignacionData.id_asignacion || pendingAsignacionData.fk_id_asignacion || pendingAsignacionData.id || null);
          if (asignId) updateHistoricoFechaFin(asignId, data.fecha_fin);
        } catch(e) { console.warn('updateHistoricoFechaFin failed', e); }
      }
      pendingFinalizeDeviceId = null; pendingAsignacionData = null; openGlobalSuccessModal(data.message || 'asignación finalizada');
    } else { if (errEl) { errEl.textContent = data.message || 'No se pudo finalizar la asignación'; errEl.style.display = 'block'; } }
  } catch (e) { console.error('Error finalizing assignment (inline)', e); if (errEl) { errEl.textContent = 'Error: ' + (e && e.message ? e.message : e); errEl.style.display = 'block'; } } finally { if (btn) { btn.disabled = false; btn.textContent = 'Confirmar'; } }
}

// Open finalize assignment modal directly from table button
async function openFinalizeAsignacionFromTable(deviceId) {
  if (!deviceId) return;
  try {
    // First, load device data to populate device info in modal
    const deviceResp = await fetch(`/devices/${deviceId}`);
    if (!deviceResp.ok) {
      console.error('Device fetch failed:', deviceResp.status);
      openGlobalMessageModal('error', 'Error', 'No se pudo cargar el dispositivo');
      return;
    }
    const dev = await deviceResp.json();
    
    // Set device info for the modal label
    const set = (id, value) => { const el = document.getElementById(id); if (!el) return; if (el.tagName === 'SELECT' || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.value = value ?? ''; };
    set('editDeviceTipo', dev.categoria);
    set('editDeviceSerial', dev.numero_serie);
    const marcaSelect = document.getElementById('editSelectMarca');
    const modeloSelect = document.getElementById('editSelectModelo');
    if (dev.fk_id_marca && marcaSelect) {
      let marcaOption = marcaSelect.querySelector(`option[value="${dev.fk_id_marca}"]`);
      if (!marcaOption) { marcaOption = document.createElement('option'); marcaOption.value = dev.fk_id_marca; marcaOption.textContent = dev.nombre_marca || `Marca ${dev.fk_id_marca}`; marcaSelect.appendChild(marcaOption); }
      marcaSelect.value = dev.fk_id_marca;
    }
    if (dev.fk_id_modelo && modeloSelect) {
      let modeloOption = modeloSelect.querySelector(`option[value="${dev.fk_id_modelo}"]`);
      if (!modeloOption) { modeloOption = document.createElement('option'); modeloOption.value = dev.fk_id_modelo; modeloOption.textContent = dev.nombre_modelo || `Modelo ${dev.fk_id_modelo}`; modeloSelect.appendChild(modeloOption); }
      modeloSelect.value = dev.fk_id_modelo;
    }
    
    // Now load assignment data
    const r = await fetch(`/devices/${deviceId}/asignacion-activa`, { credentials: 'same-origin' });
    if (!r.ok) {
      console.error('Assignment fetch failed:', r.status);
      openGlobalMessageModal('error', 'Error', 'No se pudo consultar la asignación activa');
      return;
    }
    const j = await r.json();
    if (!j || !j.active || !j.asignacion) {
      openGlobalMessageModal('info', 'Info', 'No hay asignación activa para este dispositivo');
      return;
    }
    
    // Set pending data and open modal
    pendingFinalizeDeviceId = deviceId;
    pendingAsignacionData = j.asignacion;
    openFinalizeAsignacionModal();
  } catch (e) {
    console.error('Error opening finalize modal from table', e);
    openGlobalMessageModal('error', 'Error', 'Error: ' + e.message);
  }
}

function openFinalizeAsignacionModal() {
  if (!pendingFinalizeDeviceId || !pendingAsignacionData) return;
  const label = document.getElementById('finalizeDeviceLabel'); const tipo = document.getElementById('editDeviceTipo')?.value || ''; const marca = document.getElementById('editSelectMarca')?.selectedOptions[0]?.textContent || ''; const modelo = document.getElementById('editSelectModelo')?.selectedOptions[0]?.textContent || ''; const serie = document.getElementById('editDeviceSerial')?.value || '';
  if (label) label.textContent = `${tipo} - ${marca} - ${modelo} - ${serie}`;
  const personaEl = document.getElementById('finalizeAsignadoPersona'); if (personaEl) personaEl.textContent = pendingAsignacionData.empleado_nombre || pendingAsignacionData.fk_id_empleado || '-';
  const desdeEl = document.getElementById('finalizeAsignadoDesde'); if (desdeEl) desdeEl.textContent = pendingAsignacionData.fecha_inicio_asignacion ? new Date(pendingAsignacionData.fecha_inicio_asignacion).toLocaleDateString() : '-';
  const err = document.getElementById('finalizeAsignacionError'); if (err) err.style.display = 'none';
  try { const modal = document.getElementById('modalFinalizeAsignacion'); if (modal) { const ci = modal.querySelector('#confirmFinalizeInput'); const btn = modal.querySelector('#btnConfirmFinalizeAsignacion'); if (ci) ci.value = ''; if (btn) btn.disabled = true; } } catch(e) {}
  openModal('modalFinalizeAsignacion', true);
}

// Wire modal confirm input to enable confirm button
document.addEventListener('DOMContentLoaded', function(){
  const modal = document.getElementById('modalFinalizeAsignacion'); if (!modal) return; const input = modal.querySelector('#confirmFinalizeInput'); const btn = modal.querySelector('#btnConfirmFinalizeAsignacion'); const btnCancel = modal.querySelector('#btnCancelFinalizeAsignacion'); if (input && btn) { const handler = () => { try { btn.disabled = input.value.trim() !== 'CONFIRMAR'; } catch(e){} }; input.removeEventListener('input', handler); input.addEventListener('input', handler); handler(); } if (btnCancel) { btnCancel.addEventListener('click', () => { closeModal('modalFinalizeAsignacion'); }); } if (btn) { btn.addEventListener('click', async () => { if (input && input.value.trim() !== 'CONFIRMAR') return; await confirmFinalizeAsignacion(); }); } 
  
  // Wire editDeviceTipo to call toggleEditDispositivoFields
  const editDeviceTipo = document.getElementById('editDeviceTipo');
  if (editDeviceTipo) {
    editDeviceTipo.addEventListener('change', toggleEditDispositivoFields);
  }
});

async function confirmFinalizeAsignacion() {
  const btn = document.getElementById('btnConfirmFinalizeAsignacion'); if (!pendingFinalizeDeviceId) return; if (btn) { btn.disabled = true; btn.textContent = 'Finalizando...'; }
  try {
    const r = await fetch(`/devices/${pendingFinalizeDeviceId}/finalizar-asignacion`, { method: 'POST', credentials: 'same-origin' });
    const data = await r.json().catch(()=>({}));
      if (r.ok && data.success) {
      const fieldset = document.getElementById('fieldsetAsignacion');
      const btnFin = document.getElementById('btnFinalizeAsignacion');
      if (btnFin) btnFin.style.display = 'none';
      if (fieldset) fieldset.style.display = 'none';
      closeModal('modalFinalizeAsignacion');
      closeModal('modalEditDevice');
      try { await updateDeviceRow(pendingFinalizeDeviceId); } catch(e){ console.warn('updateDeviceRow failed', e); }
      try { removeAssignedDeviceRow(pendingFinalizeDeviceId, pendingAsignacionData && (pendingAsignacionData.fk_id_empleado || pendingAsignacionData.fk_id_empleado === 0 ? pendingAsignacionData.fk_id_empleado : null)); } catch(e) {}
      if (data && data.fecha_fin) {
        try {
          const asignId = pendingAsignacionData && (pendingAsignacionData.id_asignacion || pendingAsignacionData.fk_id_asignacion || pendingAsignacionData.id || null);
          if (asignId) updateHistoricoFechaFin(asignId, data.fecha_fin);
        } catch(e) { console.warn('updateHistoricoFechaFin failed', e); }
      }
      openGlobalSuccessModal(data.message || 'asignación finalizada');
      pendingFinalizeDeviceId = null;
      pendingAsignacionData = null;
    } else {
      const e = document.getElementById('finalizeAsignacionError'); if (e) { e.textContent = data.message || 'No se pudo finalizar la asignación'; e.style.display = 'block'; }
    }
  } catch (e) { console.error('Error finalizing assignment', e); const el = document.getElementById('finalizeAsignacionError'); if (el) { el.textContent = 'Error: ' + e.message; el.style.display = 'block'; } } finally { if (btn) { btn.disabled = false; btn.textContent = 'Confirmar finalización'; } }
}

// IP Conflict handlers
document.getElementById('btnIpKeep')?.addEventListener('click', () => {
  closeModal('modalIpConflict');
  if (window.__pendingEditDevicePayload) {
    const editIpInput = document.getElementById('editDeviceIp');
    if (editIpInput) {
      try { 
        editIpInput.setCustomValidity('Ingrese una direccion IP valida'); 
        try { editIpInput.reportValidity(); } catch(e){} 
      } catch(e){}
    }
    window.__pendingEditDevicePayload = null;
    window.__pendingEditDeviceConflictOwner = null;
  }
});

document.getElementById('btnIpReplace')?.addEventListener('click', async () => {
  const owner = window.__pendingEditDeviceConflictOwner;
  if (!owner || !owner.id_dispositivo) { try { openGlobalMessageModal('error', 'Error', 'No se encontro el dispositivo propietario de la IP'); } catch(e){} return; }
  try {
    const resp = await fetch('/devices/clear-ip', { method: 'POST', headers: {'Content-Type':'application/json'}, credentials: 'same-origin', body: JSON.stringify({ device_id: owner.id_dispositivo }) });
    const j = await resp.json().catch(()=>({}));
    if (!(resp.ok && j.success)) { try { openGlobalMessageModal('error', 'Error', j.message || 'No se pudo liberar la IP'); } catch(e){} return; }
    closeModal('modalIpConflict');
    if (window.__pendingEditDevicePayload) {
      const editIpInput = document.getElementById('editDeviceIp');
      if (editIpInput) { 
        try { 
          editIpInput.setCustomValidity(''); 
          try { editIpInput.reportValidity(); } catch(e){} 
        } catch(e){} 
        const el = document.getElementById('editIpError'); if (el) { el.textContent = ''; el.style.display = 'none'; } 
      }
      const payload = window.__pendingEditDevicePayload;
      const id = window.__pendingEditDeviceId;
      try {
        const r = await fetch(`/devices/${id}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, credentials: 'same-origin', body: JSON.stringify(payload) });
        const data = await r.json().catch(()=>({}));
        if (r.ok && data.success) { closeModal('modalEditDevice'); if (typeof reloadDevicesTable === 'function') await reloadDevicesTable(); openGlobalSuccessModal(data.message || 'Dispositivo actualizado'); } else { const err = document.getElementById('editDeviceError'); if (err) { err.textContent = data.message || 'No se pudo actualizar'; err.style.display='block'; } }
      } catch (e) { console.error('Error updating device after IP replace', e); const el = document.getElementById('editDeviceError'); if (el) { el.textContent = 'Error actualizando dispositivo'; el.style.display='block'; } }
      window.__pendingEditDevicePayload = null;
      window.__pendingEditDeviceConflictOwner = null;
      window.__pendingEditDeviceId = null;
      return;
    }
  } catch (e) { console.error('Error clearing IP', e); try { openGlobalMessageModal('error', 'Error', 'Error del servidor al liberar IP'); } catch(e2){} }
});

/* ========================================================================= */

document.getElementById('btnSaveAsignacion').addEventListener('click', async () => {
  const id = document.getElementById('editAsignacionId').value;
  const payload = {
    fecha_fin_asignacion: document.getElementById('editAsignacionFechaFin').value || null,
    observaciones: document.getElementById('editAsignacionObservaciones').value || null
  };
  try {
    const r = await fetch(`/devices/asignacion/${id}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    const data = await r.json().catch(()=>({}));
    if (r.ok && data.success) {
      closeEditAsignacionModal();
      // Recargar la tabla de asignaciones
      if (typeof reloadAsignacionesTable === 'function') {
        await reloadAsignacionesTable();
      }
      // Recargar la tabla de dispositivos si se marcí una fecha de fin
      if (payload.fecha_fin_asignacion && typeof reloadDevicesTable === 'function') {
        await reloadDevicesTable();
      }
      openGlobalSuccessModal(data.message || 'asignación actualizada');
    } else {
      document.getElementById('editAsignacionError').textContent = data.message || 'No se pudo actualizar la asignación';
      document.getElementById('editAsignacionError').style.display = 'block';
    }
  } catch (err) {
    document.getElementById('editAsignacionError').textContent = 'No se pudo actualizar la asignación';
    document.getElementById('editAsignacionError').style.display = 'block';
  }
});

// Manejar envío de formulario de nueva asignación
async function handleSubmitNewAsignacion(e) {
  e.preventDefault();
  const _form = document.getElementById('formNewAsignacion');
  const fechaInicioEl = _form ? _form.querySelector('input[name="fecha_inicio_asignacion"]') : null;
  if (!fechaInicioEl || !fechaInicioEl.value) {
    try { openGlobalErrorModal('La fecha de inicio es obligatoria.'); } catch(err) { alert('La fecha de inicio es obligatoria.'); }
    return;
  }
  if (_form && typeof _form.reportValidity === 'function') {
    if (!_form.reportValidity()) return;
  }

  // Check dispositivo/plan: if celular without plan, show confirmation modal
    try {
    const selDisp = document.getElementById('selectDispositivo');
    const selEmp = document.getElementById('selectEmpleadoNew');
    const opt = selDisp && selDisp.selectedOptions && selDisp.selectedOptions[0];
    const empOpt = selEmp && selEmp.selectedOptions && selEmp.selectedOptions[0];
    const tipo = opt ? (opt.getAttribute('data-tipo') || '') : '';
    const fkPlan = opt ? (opt.getAttribute('data-fk-plan') || '') : '';
    if (String(tipo).toLowerCase() === 'celular' && (!fkPlan || fkPlan === '')) {
      // If option lacks marca/modelo/imei attributes, fetch device details from API
      let marca = opt ? (opt.getAttribute('data-marca') || '') : '';
      let modelo = opt ? (opt.getAttribute('data-modelo') || '') : '';
      let imei = opt ? (opt.getAttribute('data-imei') || '') : '';
      if ((!marca || marca === '') || (!modelo || modelo === '') || (!imei || imei === '')) {
        try {
          const devId = opt ? opt.value : null;
          if (devId) {
            const respDev = await fetch(`/devices/${devId}`);
            if (respDev && respDev.ok) {
              const devJson = await respDev.json().catch(()=>null);
              if (devJson) {
                marca = marca || (devJson.nombre_marca || devJson.nombreMarca || '');
                modelo = modelo || (devJson.nombre_modelo || devJson.nombreModelo || devJson.nombre_modelo || '');
                imei = imei || (devJson.imei || devJson.imei2 || '');
              }
            }
          }
        } catch(fetchErr) { console.warn('Could not fetch device details', fetchErr); }
      }

      // Populate modal details
      document.getElementById('confirmDispMarca').textContent = marca || '-';
      document.getElementById('confirmDispModelo').textContent = modelo || '-';
      document.getElementById('confirmDispImei').textContent = imei || '-';
      document.getElementById('confirmEmpleadoName').textContent = (empOpt && empOpt.textContent) ? empOpt.textContent : '-';

      // Await user confirmation
      const confirmed = await new Promise((resolve) => {
        const btnYes = document.getElementById('btnAcceptAssignNoPlan');
        const btnNo = document.getElementById('btnCancelAssignNoPlan');
        const cleanup = () => {
          try { btnYes.removeEventListener('click', onYes); } catch(e){}
          try { btnNo.removeEventListener('click', onNo); } catch(e){}
        };
        const onYes = () => { cleanup(); closeModal('modalConfirmAssignNoPlan'); resolve(true); };
        const onNo = () => { cleanup(); closeModal('modalConfirmAssignNoPlan'); resolve(false); };
        btnYes.addEventListener('click', onYes);
        btnNo.addEventListener('click', onNo);
        openModal('modalConfirmAssignNoPlan');
      });

      if (!confirmed) {
        return; // user cancelled
      }
    }
  } catch (err) {
    console.warn('Error validating plan confirmation', err);
  }

  const formData = new FormData(_form || document.getElementById('formNewAsignacion'));
  try {
    const resp = await fetch('/devices/asignacion/new', { method: 'POST', body: formData });
    if (resp.ok) {
      const data = await resp.json().catch(() => ({}));
      closeModal('modalNewAsignacion');
      document.getElementById('formNewAsignacion').reset();
      try { const sel = document.getElementById('selectEmpleadoNew'); if (sel) sel.value = ''; if (typeof loadAssignedDevicesForEmpleado === 'function') await loadAssignedDevicesForEmpleado(''); } catch(e) {}

      try {
        const newRowHtml = data && data.new_row_html;
        if (newRowHtml) {
          const histTbody = document.querySelector('#historicoTable tbody');
          if (histTbody) {
            histTbody.insertAdjacentHTML('afterbegin', newRowHtml);
            try { const q = (document.getElementById('asignacionesPageSearch') || {}).value || ''; if (typeof applyTableSearchFilter === 'function') applyTableSearchFilter(q, document.getElementById('viewHistorico')); } catch(e) {}
            try {
              const newAsign = data && data.new_asign;
              const empleadoId = newAsign && (newAsign.fk_id_empleado || newAsign.fk_id_empleado === 0 ? String(newAsign.fk_id_empleado) : null);
              if (empleadoId) {
                const badge = document.querySelector(`#viewResumen tr[data-emp-id="${empleadoId}"] .device-count-badge`);
                if (badge) {
                  const cur = parseInt(badge.textContent || '0', 10) || 0;
                  const next = cur + 1;
                  badge.textContent = String(next);
                  if (next > 0) badge.classList.add('has-count'); else badge.classList.remove('has-count');
                }
              }
            } catch(e) {}
          } else if (typeof reloadAsignacionesTable === 'function') {
            await reloadAsignacionesTable();
          }
        } else {
          if (typeof reloadAsignacionesTable === 'function') await reloadAsignacionesTable();
        }
      } catch (e) { try { if (typeof reloadAsignacionesTable === 'function') await reloadAsignacionesTable(); } catch(_) {} }

      if (typeof reloadDispositivosOptions === 'function') await reloadDispositivosOptions();
      openGlobalSuccessModal(data.message || 'asignación creada exitosamente');
    } else {
      const data = await resp.json().catch(() => ({}));
      showModalMessage('error', 'Error', data.message || 'No se pudo crear la asignación');
    }
  } catch (err) {
    showModalMessage('error', 'Error', 'No se pudo crear la asignación');
  }
}

// Note: form uses inline onsubmit to avoid double-binding of the handler

// Ensure the 'Guardar asignación' button triggers the form submit reliably
try {
  const newSubmitBtn = document.querySelector('button[type="submit"][form="formNewAsignacion"]');
  if (newSubmitBtn) {
    newSubmitBtn.addEventListener('click', (ev) => {
      ev.preventDefault();
      const f = document.getElementById('formNewAsignacion');
      if (f) {
        if (typeof f.requestSubmit === 'function') f.requestSubmit();
        else f.dispatchEvent(new Event('submit', { cancelable: true }));
      }
    });
  }
} catch(e) { console.warn('bind submit fix failed', e); }

// ============================================================================
// FUNCIONES PARA GENERACIíN DE PDF DE ENTREGA
// ============================================================================

let pdfCurrentAsignacionId = null;

function formatDate(dateStr) {
  if (!dateStr) return 'N/A';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('es-ES');
  } catch (err) {
    return dateStr;
  }
}

async function downloadPDF() {
  if (!pdfCurrentAsignacionId) {
    showModalMessage('error', 'Error', 'ID de asignación no disponible');
    return;
  }
  _pdfAsignacionIdPending = pdfCurrentAsignacionId;
  _pdfFirmaUsuario = null;
  _pdfFirmaEmpleado = null;
  _pdfDualFlow = true;
  openSolicitarFirma();
}

function submitDocument(asignacionId, openInNewTab) {
  const identidadEmpleado = (window._identidadEmpleadoTemp || document.getElementById('sel_identidad_empleado')?.value || '').replace(/\D/g,'');
  const identidadUsuario = (window._identidadUsuarioTemp || document.getElementById('sel_identidad_usuario')?.value || '').replace(/\D/g,'');

  // Recopilar observaciones seleccionadas
  const observaciones = [];
  for (let i = 1; i <= 5; i++) {
    const checkbox = document.getElementById(`obs_${i}`);
    if (checkbox && checkbox.checked) {
      observaciones.push(checkbox.nextElementSibling.textContent.trim());
    } else {
      observaciones.push(''); // Si no está marcado, dejar vacío
    }
  }

  // If user requested preview in new tab, POST to download-pdf endpoint (returns file)
  (async () => {
    try {
      if (openInNewTab) {
        // open blank window to avoid popup blocking
        let win = window.open('about:blank');
        const fd = new FormData();
        fd.append('identidad_empleado', identidadEmpleado);
        fd.append('identidad_usuario', identidadUsuario);
        // adjuntar observaciones como campos observacion_1..observacion_5
        try {
          if (Array.isArray(observaciones)) {
            observaciones.forEach((o, idx) => fd.append(`observacion_${idx+1}`, o || ''));
          }
        } catch(e) { /* ignore */ }
        // attach signatures if present
        if (_pdfDualFlow && _pdfFirmaUsuario && _pdfFirmaEmpleado) {
          fd.append('firma_usuario', _pdfFirmaUsuario);
          fd.append('firma_empleado', _pdfFirmaEmpleado);
          _pdfDualFlow = false;
        }

        const resp = await fetch(`/devices/asignacion/${asignacionId}/download-pdf`, {
          method: 'POST',
          credentials: 'same-origin',
          body: fd
        }).catch(() => null);

        if (!resp) throw new Error('No response from server');

        const ct = (resp.headers.get('content-type') || '').toLowerCase();
        if (ct.includes('application/pdf') || ct.includes('application/vnd.openxmlformats-officedocument.wordprocessingml.document')) {
          const blob = await resp.blob();
          const cd = resp.headers.get('content-disposition') || '';
          const m = /filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/.exec(cd);
          let filename = m ? decodeURIComponent(m[1] || m[2]) : `DOCUMENTACION_ASIGNACION_${asignacionId}.pdf`;
          const blobUrl = URL.createObjectURL(blob);
          try { win.location = blobUrl; } catch (e) { window.location = blobUrl; }
          // Show confirm terms modal after opening preview
          try { window._previewAsignacionId = asignacionId; openModal('modalConfirmTerminos'); } catch(e) {}
        } else {
          const json = await resp.json().catch(() => null);
          const msg = json && json.message ? json.message : 'Error generando documento para previsualizar';
          if (typeof openGlobalMessageModal === 'function') openGlobalMessageModal('error','Error', msg); else alert(msg);
          try { if (win) win.close(); } catch(e) {}
        }

      } else {
        // Default: persist/generate documents on server (existing behavior)
        const url = `/devices/asignacion/${asignacionId}/generate-and-upload`;
        const body = { identidad_empleado: identidadEmpleado, identidad_usuario: identidadUsuario, observaciones };
        if (_pdfDualFlow && _pdfFirmaUsuario && _pdfFirmaEmpleado) {
          body.firma_usuario = _pdfFirmaUsuario;
          body.firma_empleado = _pdfFirmaEmpleado;
          _pdfDualFlow = false;
        }

        const resp = await fetch(url, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        }).catch(() => null);

        if (!resp) throw new Error('No response from server');

        const json = await resp.json().catch(() => null);
        if (json && json.success) {
          if (json.files && json.files.length) {
            if (typeof openGlobalMessageModal === 'function') openGlobalMessageModal('info','Upload','Documentos generados'); else alert('Documentos generados');
          } else {
            if (typeof openGlobalMessageModal === 'function') openGlobalMessageModal('info','Info',json.message || 'Operación finalizada'); else alert(json.message || 'Operación finalizada');
          }
        } else {
          const msg = json && json.message ? json.message : 'Error generando documentos';
          if (typeof openGlobalMessageModal === 'function') openGlobalMessageModal('error','Error', msg); else alert(msg);
        }
      }
    } catch (err) {
      console.error('submitDocument error', err);
      alert('Error al generar documentos');
    } finally {
      try { if (typeof window.hideLoading === 'function') window.hideLoading(); } catch(e){}
      try { closeModal('modalSeleccionarTipoDocumentacion'); } catch(e){}
      try { closeModal('modalDocumentacion'); } catch(e){}
    }
  })();
}

  function iniciarFirmaTrasTerminos() {
    try {
      closeModal('modalConfirmTerminos');
      // Preparar flujo dual para capturar primero usuario y luego empleado
      _pdfDualFlow = true;
      _pdfFirmaUsuario = null;
      _pdfFirmaEmpleado = null;
      // asignacion pendiente puede venir de window._previewAsignacionId
      _pdfAsignacionIdPending = window._previewAsignacionId || pdfCurrentAsignacionId || null;
      openSolicitarFirma();
    } catch (e) {
      console.error('iniciarFirmaTrasTerminos error', e);
    }
  }

// Open datos adicionales modal and mark that the generated PDF should open in a new tab (download/preview)
function downloadPDFPreview() {
  // Abrir modal de selección para pedir identidades si es necesario
  openModal('modalSeleccionarTipoDocumentacion');
  window.pdfOpenInNewTab = true;
}

// Formato estítico 4-4-5 (XXXX XXXX XXXXX) í solo visual, se guarda sin espacios
function formatIdentityDisplay(digits) {
  const d = (digits || '').replace(/\D/g,'').slice(0,13);
  if (!d) return '';
  const p1 = d.slice(0,4);
  const p2 = d.slice(4,8);
  const p3 = d.slice(8,13);
  return [p1,p2,p3].filter(Boolean).join(' ');
}

function onIdentityInput(inputEl, which) {
  const raw = (inputEl.value || '').replace(/\D/g,'').slice(0,13);
  inputEl.value = formatIdentityDisplay(raw);
  if (which === 'empleado') window._identidadEmpleadoTemp = raw;
  else window._identidadUsuarioTemp = raw;
}

// ============================================================================
// FUNCIONES DE GENERACIíN DE documentación
// ============================================================================

// función para enviar logs al backend
function enviarLog(mensaje, nivel = 'INFO') {
  fetch('/devices/asignacion/log', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    credentials: 'same-origin',
    body: JSON.stringify({ message: mensaje, level: nivel })
  }).catch(err => {
    console.warn('Error enviando log al backend:', err);
  });
}

function llamarGenerarDocumentacion(payload) {
  // Guardar payload para poder reintentar si se necesita actualizar pasaporte
  window._lastPayload = payload;
  
  // Si hay pasaporte temporal, agregarlo al payload
  if (window._pasaporteTemporal) {
    payload.pasaporte_temporal = window._pasaporteTemporal;
  }
  
  // Mostrar loading durante la verificaciín/generaciín
  const tipoFirma = payload.tipo_firma;
  const msgCarga = tipoFirma === 'digital' 
    ? 'Verificando documentos digitales...' 
    : 'Verificando documentos...';
  showLoading(msgCarga);
  
  fetch(`/devices/asignacion/${_asignacionIdActual}/generate-documentation`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  })
  .then(async r => {
    const jsonData = await r.json().catch(() => null);
    if (!jsonData) {
      throw new Error('JSON parsing failed');
    }
    return jsonData;
  })
  .then(data => {
    hideLoading();
    
    if (data.success) {
      // Guardar correlativo y asignacion_id en variables globales
      if (data.correlativo) {
        window._correlativoActual = formatearCorrelativo(data.correlativo);
      }
      if (_asignacionIdActual) window._asignacionIdParaDocumentos = _asignacionIdActual;
      
      // Actualizar tabla para mostrar el correlativo
      if (typeof reloadAsignacionesTable === 'function') {
        reloadAsignacionesTable();
      }
      
      const estado = data.estado || (tipoFirma === 'digital' ? 11 : 21);
      
      // Míquina de estados unificada - usa la misma función para digital y manual
      mostrarModalDocumentosOneDrive(data.archivos, estado);
    } else {
      openGlobalMessageModal('error', 'Error', data.message || 'Error desconocido');
    }
  })
  .catch(e => {
    hideLoading();
    openGlobalMessageModal('error', 'Error', 'Error en la solicitud: ' + e.message);
  });
}

// NUEVA función: Verificar pasaporte ANTES de generar documentación
function verificarYGenerarDocumentacion(payload) {
  const tipoFirma = payload.tipo_firma;
  
  // Obtener datos del empleado actual
  const empleadoId = _empleadoIdActual || window._empleadoIdActual;
  
  if (!empleadoId) {
    openGlobalMessageModal('error', 'Error', 'No se pudo identificar el empleado');
    return;
  }
  
  // Hacer fetch para obtener datos del empleado
  showLoading('Verificando datos del empleado...');
  
  fetch(`/devices/empleado/${empleadoId}`, {
    method: 'GET',
    credentials: 'same-origin',
    headers: {'Content-Type': 'application/json'}
  })
  .then(r => r.json())
  .then(empleado => {
    hideLoading();
    
    // Verificar si el pasaporte está vacío o es null
    const pasaporte = (empleado.pasaporte || '').trim();
    
    if (!pasaporte) {
      // NO tiene pasaporte: mostrar modal para ingresar
      document.getElementById('pasaporteModalMessage').textContent = `El empleado ${empleado.nombre_completo || 'no identificado'} no tiene identidad registrada.`;
      document.getElementById('pasaporteInput').value = '';
      document.getElementById('pasaporteError').style.display = 'none';
      window._pasaporteData = { empleadoId: empleadoId };
      window._generarDocPayload = payload; // Guardar el payload para despuís
      openModal('pasaporteModal');
      document.getElementById('pasaporteInput').focus();
    } else {
      // Sí tiene pasaporte: proceder directamente
      llamarGenerarDocumentacion(payload);
    }
  })
  .catch(e => {
    hideLoading();
    openGlobalMessageModal('error', 'Error', 'Error verificando empleado: ' + e.message);
  });
}

// Check if localStorage flag is set to open new asignacion modal
if(localStorage.getItem('openNewAsignacionModal') === 'true'){
  openNewAsignacionModal();
  localStorage.removeItem('openNewAsignacionModal');
}

/* ========================================================================= */

// ========================================================
// FUNCIONES PARA MANEJO DE documentación (CONTINUACIÓN)
// ========================================================
// Nota: abrirModalSeleccionarTipoDocumentacion y seleccionarTipoDocumentacion
// ya están declaradas al inicio del archivo

// DEPRECATED: Ya no se usa, se reemplazí por generarDocumentacionNuevo()
function generarDocumentacionDigital(asignacionId) {
  console.warn('generarDocumentacionDigital() está deprecado. Usar generarDocumentacionNuevo()');
  generarDocumentacionNuevo(asignacionId, 'digital');
}

// DEPRECATED: Ya no se usa
function abrirModalCargarFirmasManualmente(asignacionId) {
  console.warn('abrirModalCargarFirmasManualmente() está deprecado. Usar generarDocumentacionNuevo()');
  generarDocumentacionNuevo(asignacionId, 'manual');
}

// ========================================================
// FUNCIONES AUXILIARES - DRAG & DROP Y ARCHIVO
// ========================================================

function handleDragOver(e, element) {
  e.preventDefault();
  e.stopPropagation();
  element.style.borderColor = '#0066cc';
  element.style.backgroundColor = '#f0f7ff';
}

function handleDragLeave(e, element) {
  e.preventDefault();
  e.stopPropagation();
  element.style.borderColor = '#ddd';
  element.style.backgroundColor = '#f9f9f9';
}

function handleFileDrop(e, inputId) {
  e.preventDefault();
  e.stopPropagation();
  
  const zone = document.getElementById('dropZone' + (inputId === 'firma_responsable' ? 'Responsable' : 'Empleado'));
  if (zone) {
    zone.style.borderColor = '#ddd';
    zone.style.backgroundColor = '#f9f9f9';
  }
  
  const files = e.dataTransfer.files;
  if (files.length > 0) {
    const input = document.getElementById(inputId);
    input.files = files;
    actualizarNombreArchivo(inputId, input);
  }
}

function actualizarNombreArchivo(inputId, input) {
  const nombreEl = document.getElementById('nombreArchivo_' + inputId);
  if (input.files && input.files.length > 0) {
    const filename = input.files[0].name;
    if (nombreEl) {
      nombreEl.textContent = '? ' + filename;
      nombreEl.style.display = 'block';
    }
  } else {
    if (nombreEl) nombreEl.style.display = 'none';
  }
}

function cargarFirmasManualmente() {
  if (!_asignacionIdDocumentacion) {
    alert('Error: No se especificí asignación');
    return;
  }

  const firmaResponsable = document.getElementById('firma_responsable').files[0];
  const firmaEmpleado = document.getElementById('firma_empleado').files[0];

  if (!firmaResponsable || !firmaEmpleado) {
    alert('Por favor, selecciona ambas firmas');
    return;
  }

  const formData = new FormData();
  formData.append('firma_responsable', firmaResponsable);
  formData.append('firma_empleado', firmaEmpleado);

  const btnCargar = document.getElementById('btnCargarFirmas');
  btnCargar.disabled = true;
  btnCargar.textContent = 'Cargando...';

  fetch(`/devices/asignacion/${_asignacionIdDocumentacion}/documentacion/upload-firmas`, {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      alert('? Firmas cargadas correctamente');
      closeModal('modalCargarFirmasManualmente');
      // Limpiar formulario
      document.getElementById('formCargarFirmas').reset();
      document.getElementById('nombreArchivo_firma_responsable').style.display = 'none';
      document.getElementById('nombreArchivo_firma_empleado').style.display = 'none';
      // Recargar tabla de asignaciones
      if (typeof reloadAsignacionesTable === 'function') {
        reloadAsignacionesTable();
      }
    } else {
      alert('Error: ' + (data.error || 'No se pudieron cargar las firmas'));
    }
  })
  .catch(error => {
    console.error('Error:', error);
    alert('Error al cargar firmas: ' + error.message);
  })
  .finally(() => {
    btnCargar.disabled = false;
    btnCargar.textContent = 'Guardar Firmas';
  });
}

// ========================================================
// FUNCIONES PARA MODAL DE REVISIÓN
// ========================================================

let _archivosParaRevisar = [];
let _checkboxesEstadoOriginal = {};

function abrirModalRevision(asignacionId, archivos) {
  _asignacionIdDocumentacion = asignacionId;
  _archivosParaRevisar = archivos || [];
  _checkboxesEstadoOriginal = {};
  
  // Limpiar inputs
  document.getElementById('inputConfirmarRevision').value = '';
  document.getElementById('textareaObservaciones').value = '';
  document.getElementById('avisoCheckboxesSinMarcar').style.display = 'none';
  
  // Generar lista de checkboxes
  const container = document.getElementById('listaArchivosRevision');
  container.innerHTML = '';
  
  if (!_archivosParaRevisar || _archivosParaRevisar.length === 0) {
    container.innerHTML = '<p style="color:#999; text-align:center;">No hay archivos para revisar</p>';
  } else {
    _archivosParaRevisar.forEach((archivo, idx) => {
      const checkId = `chk_archivo_${idx}`;
      const div = document.createElement('div');
      div.style.marginBottom = '10px';
      div.style.display = 'flex';
      div.style.alignItems = 'center';
      div.style.gap = '12px';
      div.innerHTML = `
        <input type="checkbox" id="${checkId}" class="checkbox-archivo" 
               style="width:18px; height:18px; cursor:pointer;" 
               onchange="verificarCheckboxes()">
        <label for="${checkId}" style="margin:0; cursor:pointer; flex:1;">
          <strong>${archivo}</strong>
        </label>
      `;
      container.appendChild(div);
      _checkboxesEstadoOriginal[checkId] = false;
    });
  }
  
  openModal('modalRevisionArchivos');
}

function verificarCheckboxes() {
  const checkboxes = document.querySelectorAll('.checkbox-archivo');
  const todos = Array.from(checkboxes).every(cb => cb.checked);
  const ninguno = Array.from(checkboxes).every(cb => !cb.checked);
  
  const aviso = document.getElementById('avisoCheckboxesSinMarcar');
  if (!todos && !ninguno) {
    aviso.style.display = 'block';
  } else {
    aviso.style.display = 'none';
  }
}

function cerrarModalRevision() {
  // Desmarcar todos los checkboxes
  document.querySelectorAll('.checkbox-archivo').forEach(cb => {
    cb.checked = false;
  });
  
  // Limpiar inputs
  document.getElementById('inputConfirmarRevision').value = '';
  document.getElementById('textareaObservaciones').value = '';
  document.getElementById('avisoCheckboxesSinMarcar').style.display = 'none';
  
  closeModal('modalRevisionArchivos');
}

function guardarRevisionArchivos() {
  const confirmInput = document.getElementById('inputConfirmarRevision').value.trim();
  
  if (confirmInput !== 'CONFIRMAR') {
    alert('Debe escribir "CONFIRMAR" en mayúsculas para confirmar la revisión');
    return;
  }
  
  const checkboxes = document.querySelectorAll('.checkbox-archivo:checked');
  const archivosAprobados = Array.from(checkboxes).map((cb, idx) => {
    const label = cb.nextElementSibling.textContent.trim();
    return label;
  });
  
  const observaciones = document.getElementById('textareaObservaciones').value.trim();
  
  // Validar que hay al menos un archivo aprobado
  if (archivosAprobados.length === 0) {
    alert('Debe aprobar al menos un archivo');
    return;
  }
  
  // Llamar al endpoint
  fetch(`/devices/asignacion/${_asignacionIdDocumentacion}/revision`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      archivos_aprobados: archivosAprobados,
      usuario: (window._currentUsername || 'admin'),
      observaciones: observaciones
    })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      alert('Revisión guardada correctamente');
      closeModal('modalRevisionArchivos');
      // Reload tabla si es necesario
      if (typeof reloadAsignacionesTable === 'function') reloadAsignacionesTable();
    } else {
      alert('Error: ' + (data.error || 'Error desconocido'));
    }
  })
  .catch(err => {
    console.error('Error:', err);
    alert('Error al guardar revisiín');
  });
}

// ========================================================
// FUNCIONES PARA MODAL DE CONFIRMACIÓN FINAL
// ========================================================

function abrirModalConfirmacionFinal(asignacionId, archivos) {
  _asignacionIdDocumentacion = asignacionId;
  
  // Mostrar archivos
  const container = document.getElementById('listaArchivosFinales');
  container.innerHTML = '';
  
  if (archivos && archivos.length > 0) {
    archivos.forEach((archivo, idx) => {
      const div = document.createElement('div');
      div.style.padding = '8px 0';
      div.style.borderBottom = idx < archivos.length - 1 ? '1px solid #eee' : 'none';
      div.innerHTML = `<span style="color:#333;">? ${archivo}</span>`;
      container.appendChild(div);
    });
  } else {
    container.innerHTML = '<p style="color:#999; text-align:center;">No hay archivos</p>';
  }
  
  // Generar enlace para ver carpeta (será relativo a la carpeta del empleado)
  const enlace = document.getElementById('enlaceVerArchivos');
  enlace.href = `/descargas/documentos/${new Date().getFullYear()}/${String(new Date().getMonth() + 1).padStart(2, '0')}/`;
  
  openModal('modalConfirmacionFinal');
}

function confirmarDocumentacionFinal() {
  const btn = document.getElementById('btnConfirmarFinal');
  btn.disabled = true;
  btn.textContent = 'Procesando...';
  
  fetch(`/devices/asignacion/${_asignacionIdDocumentacion}/confirmar-final`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({})
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      alert('documentación confirmada exitosamente');
      closeModal('modalConfirmacionFinal');
      // Reload tabla
      if (typeof reloadAsignacionesTable === 'function') reloadAsignacionesTable();
    } else {
      alert('Error: ' + (data.error || 'Error desconocido'));
    }
  })
  .catch(err => {
    console.error('Error:', err);
    alert('Error al confirmar documentación');
  })
  .finally(() => {
    btn.disabled = false;
    btn.textContent = '? Visto Bueno';
  });
}

// ============================================================================
// NUEVO SISTEMA DE documentación - Basado en doc/proceso.txt
// ============================================================================

let _asignacionIdActual = null;
let _canvasFirmaEmpleadoCtx = null;
let _canvasFirmaUsuarioCtx = null;
let _firmaEmpleadoVacia = true;
let _firmaUsuarioVacia = true;
let _pdfDoc = null;
let _pdfPageNum = 1;
let _pdfPageRendering = false;
let _pdfScale = 1.5;
let _pdfDocFirmado = null;
let _pdfPageNumFirmado = 1;
let _pdfPageRenderingFirmado = false;
let _pdfScaleFirmado = 1.5;

// ========================================================
// PASO 1: Generar documentación (Estado 0 ? 11/21)
// ========================================================

function generarDocumentacionNuevo(asignacionId, tipoFirma) {
  _asignacionIdActual = asignacionId;
  
  // Guardar el tipo de firma seleccionado para usarlo después
  window._tipoFirmaSeleccionado = tipoFirma;
  
  // Obtener información de la asignación para verificar categoría del dispositivo
  const asignacion = window._asignacionCurrent || {};
  const categoria = asignacion.categoria || '';
  
  // Solo pedir observaciones si es un Celular
  if (categoria === 'Celular') {
    // Abrir modal de observaciones primero
    abrirModalObservaciones(function(observaciones) {
      // Una vez capturadas las observaciones, continuar con el flujo normal
      const payload = {
        tipo_firma: tipoFirma,
        observaciones: observaciones
      };
      
      // Guardar observaciones globalmente para usarlas después si las necesitamos
      window._observacionesDispositivo = observaciones;
      
      // Verificar pasaporte ANTES de hacer la solicitud
      verificarYGenerarDocumentacion(payload);
    });
  } else {
    // Para otros dispositivos (Laptop, Tablet, Periférico), continuar sin observaciones
    const payload = {
      tipo_firma: tipoFirma,
      observaciones: {}  // Sin observaciones para otros tipos
    };
    
    // Verificar pasaporte ANTES de hacer la solicitud
    verificarYGenerarDocumentacion(payload);
  }
}


// confirmarDatosAdicionales removed í flow replaced by inline selection + confirm modal

// ========================================================
// PASO B2: Mostrar Documentos para Lectura (Estado 11)
// ========================================================

async function mostrarModalDocumentosOneDrive(archivos, estado) {
  // Estado 11: Mostrar documentos con checkbox para confirmar lectura
  try {
    const estadoNum = Number(estado);
    const modal = document.getElementById('modalDocumentosOneDrive');
    const container = document.getElementById('pdfCardsContainer');
    
    if (!modal || !container) {
      console.error('Elementos de modal no encontrados');
      alert('Error: Modal no disponible');
      return;
    }
    
    // Guardar asignacionId en window para que sea accesible globalmente
    if (!window._asignacionIdParaDocumentos && _asignacionIdActual) {
      window._asignacionIdParaDocumentos = _asignacionIdActual;
    }
    
    // Mostrar modal and set documentation progress according to estado
    modal.classList.add('active');
    try{ if (typeof ensureDocProgress === 'function') ensureDocProgress('modalDocumentosOneDrive'); } catch(e){}
    try {
      if (typeof setDocumentationProgress === 'function'){
        var targetStep = 2; // default
        var st = estadoNum;
        if (st === 13 || st === 22 || st === 23) targetStep = 3;  // Estados 13, 22, 23: paso 3
        else if (st === 11 || st === 21) targetStep = 2;  // Estados 11, 21: paso 2
        else if (st === 14 || st === 24 || st === 90) targetStep = 4;  // Estados finales: paso 4
        // apply the step for this modal
        setDocumentationProgress(targetStep, 'modalDocumentosOneDrive');
      }
    } catch(e) {}
    
    let files = null;
    let correlativo = null;
    
    // Siempre obtener la lista actualizada desde el servidor (OneDrive)
    // para evitar usar resultados pasados o 'cacheados'. Mostrar solo los archivos
    // que realmente tienen URL de descarga y excluir revisiones temporales ("rev").
    showLoading('Obteniendo archivos de OneDrive...');
    const response = await fetch(`/devices/asignacion/${_asignacionIdActual}/list-documentos`, {
      method: 'GET',
      credentials: 'same-origin'
    });
    const data = await response.json();
    hideLoading();

    if (!data || !data.success) {
      container.innerHTML = `
        <div class="pdf-cards-empty">
          <p><strong>No se encontraron documentos</strong></p>
          <p>${(data && data.error) ? data.error : 'No hay archivos para mostrar'}</p>
        </div>
      `;
      return;
    }

    // El backend ya devuelve los archivos correctos según el estado (incluyendo/excluyendo "rev").
    // Solo filtramos entradas nulas o sin URL descargable.
    const fetchedFiles = Array.isArray(data.files) ? data.files : [];
    const filteredList = fetchedFiles.filter(f => {
      if (!f) return false;
      const name = (f.nombre || f.name || '').toString();
      if (!name) return false;
      if (!(f.url || f.download_url || f.downloadUrl)) return false;
      return true;
    });
    files = filteredList;
    // Limpiar elemento de estado anterior si existe
    try {
      const old = document.getElementById('pdfFilesStatus');
      if (old) old.remove();
    } catch(e) {}

    correlativo = data.correlativo || window._correlativoActual;
    
    // Actualizar correlativo global si lo recibimos (formatear a 6 dígitos)
    if (correlativo && correlativo !== '000000') {
      window._correlativoActual = formatearCorrelativo(correlativo);
    }
    
    // Renderizar cards con metadata real
    renderPDFCards(files, container);
    
    // Agregar checkbox y botones segín estado
    if (estadoNum === 11 || estadoNum === 21) {
      // Estados 11/21: Agregar checkbox "He leído y acepto"
      agregarCheckboxAceptacion(correlativo, estadoNum);
    } else if (estadoNum === 22) {
      // Estado 22: Mostrar Botón para subir archivos firmados manualmente
      agregarBotonSubidaManual(correlativo);
    } else if (estadoNum === 13 || estadoNum === 23) {
      // Estados 13/23: Mostrar botones Confirmar/Regenerar
      agregarBotonesEstado13(correlativo, estadoNum);
    } else if (estadoNum === 14 || estadoNum === 24 || estadoNum === 90) {
      // Estados 14, 24, 90: Informativo - solo mostrar boton Cerrar y Descargar
      agregarBotonesEstado90(correlativo);
    }
    
  } catch(e) {
    console.error('Error mostrando documentos:', e);
    hideLoading();
    alert('Error mostrando documentos: ' + e.message);
  }
}

// Agregar checkbox de aceptaciín para estados 11 y 21
function agregarCheckboxAceptacion(correlativo, estado) {
  const modal = document.getElementById('modalDocumentosOneDrive');
  if (!modal) return;
  
  let actionsContainer = modal.querySelector('.modal-docs-actions');
  if (!actionsContainer) {
    actionsContainer = document.createElement('div');
    actionsContainer.className = 'modal-docs-actions';
    actionsContainer.style.cssText = 'padding: 12px 20px; border-top: 1px solid #e5e7eb; margin-top: 2px;';
    const modalBody = modal.querySelector('.modal-body') || modal.querySelector('.modal');
    modalBody.appendChild(actionsContainer);
  }
  
  actionsContainer.innerHTML = `
    <div style="text-align: center; margin-bottom: 16px;">
      <div style="font-size: 0.95rem; color: #e5e7eb; font-weight: 500; margin: 0;">Confirma que has revisado todos los documentos antes de continuar con el proceso de firma.</div>
    </div>
    <div style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 16px;">
      <input type="checkbox" id="chkAceptoTerminos" style="width: 18px; height: 18px; cursor: pointer; margin-top: 0px; flex-shrink: 0;">
      <label for="chkAceptoTerminos" style="flex:1; cursor: pointer; user-select: none;">
        <div class="docs-accept-text" style="font-weight: 600;">He leído y acepto los términos y condiciones de los documentos.</div>
      </label>
    </div>
    <div style="display: flex; gap: 12px; justify-content: space-between;">
      <button class="btn" id="btnDownloadDocs" style="background: #10b981; color: white; border: none;">Descargar archivos</button>
      <div style="display: flex; gap: 12px;">
        <button class="btn" id="btnCancelDocs" style="background: #f97316; color: white; border: none;">Cancelar</button>
        <button class="btn btn-primary" id="btnContinueDocs" disabled>Continuar</button>
      </div>
    </div>
  `;

  // Attach checkbox listener to toggle Continue button
  const chk = actionsContainer.querySelector('#chkAceptoTerminos');
  const btn = actionsContainer.querySelector('#btnContinueDocs');
  const btnDownload = actionsContainer.querySelector('#btnDownloadDocs');
  const btnCancel = actionsContainer.querySelector('#btnCancelDocs');
  const estadoNum = Number(estado);
  if (chk && btn) {
    chk.addEventListener('change', function() {
      btn.disabled = !this.checked;
    });
    btn.addEventListener('click', function() {
      confirmarLecturaYContinuar(correlativo, estadoNum);
    });
  }
  if (btnDownload) {
    btnDownload.addEventListener('click', function() {
      descargarArchivosZip(correlativo);
    });
  }
  if (btnCancel) {
    btnCancel.addEventListener('click', function() {
      closeModal('modalDocumentosOneDrive');
    });
  }
}

// Confirmar lectura y pasar a siguiente estado (11?12 digital, 21?22 manual)
async function confirmarLecturaYContinuar(correlativo, estado) {
  const checkbox = document.getElementById('chkAceptoTerminos');
  
  if (!checkbox || !checkbox.checked) {
    if (typeof openGlobalMessageModal === 'function') {
      openGlobalMessageModal('error', 'Confirmación requerida', 'Debes marcar la casilla para confirmar que has leído y aceptas los términos y condiciones de los documentos.\n\nPor favor, revisa los documentos y marca la casilla antes de continuar.');
    } else {
      alert('Confirmación requerida\n\nDebes marcar la casilla para confirmar que has leído y aceptas los términos y condiciones de los documentos.\n\nPor favor, revisa los documentos y marca la casilla antes de continuar.');
    }
    return;
  }
  
  // Obtener asignacionId
  const asignacionId = window._asignacionIdParaDocumentos || _asignacionIdActual;
  if (!asignacionId) {
    if (typeof openGlobalMessageModal === 'function') {
      openGlobalMessageModal('error', 'Error', 'No se pudo identificar la asignación');
    } else {
      alert('Error: No se pudo identificar la asignación');
    }
    return;
  }
  
  // Determinar si es firma digital o manual
  const esManual = Number(estado) === 21;
  const endpoint = esManual ? 'mark-manual-documents-read' : 'mark-documents-read';
  
  // Mostrar loading
  if (typeof showLoading === 'function') {
    showLoading('Confirmando lectura de documentos...');
  }
  
  try {
    // Llamar al endpoint correspondiente
    const response = await fetch(`/devices/asignacion/${asignacionId}/${endpoint}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'}
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: `HTTP ${response.status}` }));
      throw new Error(errorData.message || 'Error al confirmar lectura');
    }
    
    const result = await response.json();
    
    if (!result.success) {
      throw new Error(result.message || 'Error al confirmar lectura');
    }
    
    // Ocultar loading
    if (typeof hideLoading === 'function') {
      hideLoading();
    }
    
    // Cerrar modal de documentos
    closeModal('modalDocumentosOneDrive');
    
    // Guardar correlativo en variable global
    window._correlativoActual = formatearCorrelativo(correlativo);
    
    if (esManual) {
      // Manual: abrir modal para subir archivos firmados
      setTimeout(() => abrirModalSubidaFirmaManual(), 300);
    } else {
      // Digital: abrir modal para captura de firma del empleado
      setTimeout(() => abrirModalCapturarFirmaEmpleado(), 300);
    }
    
  } catch (error) {
    console.error('Error confirmando lectura:', error);
    
    if (typeof hideLoading === 'function') {
      hideLoading();
    }
    
    if (typeof openGlobalMessageModal === 'function') {
      openGlobalMessageModal('error', 'Error', `No se pudo confirmar la lectura:\n${error.message}`);
    } else {
      alert(`Error: No se pudo confirmar la lectura:\n${error.message}`);
    }
  }
}

// Estado 90: mostrar solo Botón Cerrar (modal informativa)
function agregarBotonesEstado90(correlativo) {
  const modal = document.getElementById('modalDocumentosOneDrive');
  if (!modal) return;
  let actionsContainer = modal.querySelector('.modal-docs-actions');
  if (!actionsContainer) {
    actionsContainer = document.createElement('div');
    actionsContainer.className = 'modal-docs-actions';
    actionsContainer.style.cssText = 'padding: 20px; border-top: 1px solid #e5e7eb; margin-top: 20px; display:flex; justify-content:flex-end;';
    const modalBody = modal.querySelector('.modal-body') || modal.querySelector('.modal');
    modalBody.appendChild(actionsContainer);
  }
  actionsContainer.innerHTML = `
    <div style="display:flex; gap:12px; justify-content: space-between; width: 100%;">
      <button class="btn" id="btnDownloadEstado90" style="background: #10b981; color: white; border: none;">Descargar archivos</button>
      <button class="btn" id="btnCloseEstado90" style="background: #f97316; color: white; border: none;">Cerrar</button>
    </div>
  `;
  const btnDownload = actionsContainer.querySelector('#btnDownloadEstado90');
  const btnClose = actionsContainer.querySelector('#btnCloseEstado90');
  if (btnDownload) {
    btnDownload.addEventListener('click', function() {
      descargarArchivosZip(correlativo);
    });
  }
  if (btnClose) {
    btnClose.addEventListener('click', function() {
      closeModal('modalDocumentosOneDrive');
    });
  }
}

// ESTADO 22: Botón para subir archivos firmados manualmente
function agregarBotonSubidaManual(correlativo) {
  const modal = document.getElementById('modalDocumentosOneDrive');
  if (!modal) return;
  
  let actionsContainer = modal.querySelector('.modal-docs-actions');
  if (!actionsContainer) {
    actionsContainer = document.createElement('div');
    actionsContainer.className = 'modal-docs-actions';
    actionsContainer.style.cssText = 'padding: 20px; border-top: 1px solid #e5e7eb; margin-top: 20px;';
    const modalBody = modal.querySelector('.modal-body') || modal.querySelector('.modal');
    modalBody.appendChild(actionsContainer);
  }
  
  actionsContainer.innerHTML = `
    <div style="background: #fef3c7; border: 1px solid #fbbf24; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
      <div style="display: flex; align-items: start; gap: 12px;">
        <svg style="width: 24px; height: 24px; color: #f59e0b; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"/>
        </svg>
        <div>
          <strong style="color: #92400e;">Firma Manual</strong>
          <p style="margin: 4px 0 0 0; font-size: 0.9rem; color: #78350f;">
            Descarga los documentos generados, impímelos y fírmalos manualmente. Luego escanea cada documento firmado como PDF y súbelos aquí.
          </p>
        </div>
      </div>
    </div>
    <div style="display: flex; gap: 12px; justify-content: space-between;">
      <button class="btn" id="btnDownloadManualDocs" style="background: #10b981; color: white; border: none;">Descargar archivos</button>
      <div style="display: flex; gap: 12px;">
        <button class="btn" id="btnCancelManualDocs" style="background: #f97316; color: white; border: none;">Cancelar</button>
        <button class="btn btn-primary" id="btnOpenUploadManual">Subir archivos firmados</button>
      </div>
    </div>
  `;
  const btnDownload = actionsContainer.querySelector('#btnDownloadManualDocs');
  const btnCancel = actionsContainer.querySelector('#btnCancelManualDocs');
  const btnOpenUpload = actionsContainer.querySelector('#btnOpenUploadManual');
  if (btnDownload) {
    btnDownload.addEventListener('click', function() {
      descargarArchivosZip(correlativo);
    });
  }
  if (btnCancel) {
    btnCancel.addEventListener('click', function() {
      closeModal('modalDocumentosOneDrive');
    });
  }
  if (btnOpenUpload) {
    btnOpenUpload.addEventListener('click', function() {
      abrirModalSubidaFirmaManual();
    });
  }
}

// ESTADO 22: Abrir modal para subir archivos firmados manualmente
function abrirModalSubidaFirmaManual() {
  const asignacionId = window._asignacionIdParaDocumentos || _asignacionIdActual;
  if (!asignacionId) {
    openGlobalMessageModal('error', 'Error', 'No se pudo identificar la asignación');
    return;
  }
  
  const correlativo = window._correlativoActual || '';
  window._correlativoParaDescarga = correlativo;
  
  // Limpiar input de archivos si existe
  const existingInput = document.getElementById('fileInputManual');
  if (existingInput) existingInput.value = '';
  
  const fileList = document.getElementById('fileList');
  if (fileList) fileList.innerHTML = '';
  
  const btnSubir = document.getElementById('btnSubirArchivos');
  if (btnSubir) btnSubir.disabled = true;
  
  // Abrir modal
  openModal('modalSubidaManual');
  
  // Setup drag & drop después de un pequeño delay para asegurar que el modal esté visible
  setTimeout(() => {
    const dropZone = document.getElementById('dropZoneManual');
    if (!dropZone) return;
    
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.style.borderColor = '#3b82f6';
      dropZone.style.background = 'rgba(59, 130, 246, 0.1)';
    });
    dropZone.addEventListener('dragleave', () => {
      dropZone.style.borderColor = '#4b5563';
      dropZone.style.background = 'transparent';
    });
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.style.borderColor = '#4b5563';
      dropZone.style.background = 'transparent';
      const files = e.dataTransfer.files;
      document.getElementById('fileInputManual').files = files;
      handleFileSelect({target: {files}});
    });
  }, 100);
}

// Manejar selección de archivos
let _archivosManual = []; // Array para almacenar archivos

function handleFileSelect(event) {
  const files = event.target.files;
  
  if (!files || files.length === 0) {
    return;
  }
  
  // Validar que sean PDFs
  const invalidFiles = Array.from(files).filter(f => !f.name.toLowerCase().endsWith('.pdf'));
  if (invalidFiles.length > 0) {
    openGlobalMessageModal('error', 'Archivos inválidos', 'Solo se permiten archivos PDF.');
    event.target.value = '';
    return;
  }
  
  // Agregar nuevos archivos al array sin duplicados
  const archivosDuplicados = [];
  const archivosAgregados = [];
  
  Array.from(files).forEach(file => {
    const existe = _archivosManual.find(f => f.name.toLowerCase() === file.name.toLowerCase());
    if (existe) {
      archivosDuplicados.push(file.name);
    } else {
      _archivosManual.push(file);
      archivosAgregados.push(file.name);
    }
  });
  
  // Limpiar el input para permitir seleccionar los mismos archivos de nuevo
  event.target.value = '';
  
  // Mostrar mensaje si hay duplicados
  if (archivosDuplicados.length > 0) {
    const plural = archivosDuplicados.length > 1;
    let mensaje = `${plural ? 'Los siguientes archivos ya están' : 'El siguiente archivo ya está'} en la lista:\n\n`;
    archivosDuplicados.forEach(nombre => {
      mensaje += `• ${nombre}\n\n`;
    });
    mensaje += `${plural ? 'Estos archivos no se agregaron' : 'Este archivo no se agregó'} nuevamente.`;
    
    openGlobalMessageModal('warning', 'Archivos duplicados', mensaje);
  }
  
  // Renderizar lista
  renderFileList();
}

function renderFileList() {
  const fileList = document.getElementById('fileList');
  const btnSubir = document.getElementById('btnSubirArchivos');
  
  if (_archivosManual.length === 0) {
    fileList.innerHTML = '';
    btnSubir.disabled = true;
    return;
  }
  
  // Obtener archivos esperados
  const asignacion = window._asignacionCurrent || {};
  const categoria = (asignacion.categoria || '').toLowerCase();
  const correlativo = window._correlativoActual || '000000';
  
  let archivosEsperados = [];
  if (categoria === 'laptop') {
    archivosEsperados = [
      `PRO-TI-CE-004-${correlativo} CERTIFICADO ENTREGA DE COMPUTADORA.pdf`
    ];
  } else if (categoria === 'celular') {
    archivosEsperados = [
      `PRO-TI-CE-001-${correlativo} CERTIFICADO DE COMPROMISO Y ENTREGA DE TELEFONO CORPORATIVO.pdf`,
      `PRO-TI-CE-002-${correlativo} MEMORANDO DE ENTREGA.pdf`
    ];
  } else if (categoria === 'tablet') {
    archivosEsperados = [`PRO-TI-CE-003-${correlativo} ENTREGA DE TABLET.pdf`];
  } else {
    archivosEsperados = [`PRO-TI-CE-005-${correlativo} ENTREGA DE PERIFERICO.pdf`];
  }
  
  // Renderizar lista de archivos
  fileList.innerHTML = '<h4 style="margin: 0 0 12px 0; font-size: 0.9rem; color: #e5e7eb; font-weight: 600;">Archivos seleccionados:</h4>';
  
  _archivosManual.forEach((file, idx) => {
    const sizeKB = (file.size / 1024).toFixed(2);
    
    // Verificar si el archivo es válido
    const esValido = archivosEsperados.some(esperado => 
      file.name.toLowerCase().replace(/\s+/g, ' ') === esperado.toLowerCase().replace(/\s+/g, ' ')
    );
    
    const iconColor = esValido ? '#10b981' : '#ef4444';
    const iconPath = esValido 
      ? 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' // Check circle
      : 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z'; // X circle
    
    fileList.innerHTML += `
      <div style="display: flex; align-items: center; gap: 10px; padding: 12px; background: #1f2937; border: 1px solid ${esValido ? '#10b981' : '#374151'}; border-radius: 8px; margin-bottom: 8px;">
        <svg style="width: 20px; height: 20px; color: #9ca3af; flex-shrink: 0;" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"/>
        </svg>
        <div style="flex: 1; display: flex; flex-direction: column; gap: 4px; min-width: 0;">
          <input type="text" value="${file.name}" 
                 onchange="renombrarArchivo(${idx}, this.value)"
                 style="background: #111827; border: 1px solid #374151; color: #e5e7eb; padding: 4px 8px; border-radius: 4px; font-size: 0.875rem; width: 100%;" />
          <span style="font-size: 0.75rem; color: #9ca3af;">${sizeKB} KB</span>
        </div>
        <svg style="width: 18px; height: 18px; color: ${iconColor}; flex-shrink: 0;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="${iconPath}"/>
        </svg>
        <button onclick="eliminarArchivo(${idx})" style="background: #374151; border: none; color: #9ca3af; padding: 6px; border-radius: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s;" onmouseover="this.style.background='#ef4444'; this.style.color='white';" onmouseout="this.style.background='#374151'; this.style.color='#9ca3af';">
          <svg style="width: 16px; height: 16px;" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
          </svg>
        </button>
      </div>
    `;
  });
  
  btnSubir.disabled = false;
}

function renombrarArchivo(idx, nuevoNombre) {
  if (!nuevoNombre || nuevoNombre.trim() === '') {
    openGlobalMessageModal('error', 'Error', 'El nombre no puede estar vacío');
    renderFileList();
    return;
  }
  
  // Verificar si ya existe otro archivo con ese nombre
  const nombreNormalizado = nuevoNombre.trim().toLowerCase();
  const duplicado = _archivosManual.find((f, i) => i !== idx && f.name.toLowerCase() === nombreNormalizado);
  
  if (duplicado) {
    // Mensaje mejor formateado con saltos de línea y viñeta
    let mensajeDup = 'Ya existe un archivo con ese nombre:\n\n';
    mensajeDup += `• ${nuevoNombre.trim()}\n\n`;
    mensajeDup += 'No se realizó el cambio. Por favor elija otro nombre.';
    openGlobalMessageModal('error', 'Nombre duplicado', mensajeDup);
    renderFileList();
    return;
  }
  
  // Crear nuevo File object con el nuevo nombre
  const archivoOriginal = _archivosManual[idx];
  const nuevoArchivo = new File([archivoOriginal], nuevoNombre.trim(), { type: archivoOriginal.type });
  _archivosManual[idx] = nuevoArchivo;
  
  renderFileList();
}

function eliminarArchivo(idx) {
  _archivosManual.splice(idx, 1);
  renderFileList();
}

// ESTADO 22→23: Subir documentos firmados manualmente
async function subirDocumentosFirmadosManual() {
  const asignacionId = window._asignacionIdParaDocumentos || _asignacionIdActual;
  if (!asignacionId) {
    openGlobalMessageModal('error', 'Error', 'No se pudo identificar la asignación');
    return;
  }
  
  if (!_archivosManual || _archivosManual.length === 0) {
    openGlobalMessageModal('error', 'Error', 'No se han seleccionado archivos');
    return;
  }
  
  // Obtener asignación y correlativo
  const asignacion = window._asignacionCurrent || {};
  const categoria = (asignacion.categoria || '').toLowerCase();
  const correlativo = window._correlativoActual || '000000';
  
  // Definir nombres esperados de archivos según tipo de dispositivo
  let archivosEsperados = [];
  
  if (categoria === 'laptop') {
    archivosEsperados = [
      `PRO-TI-CE-004-${correlativo} CERTIFICADO ENTREGA DE COMPUTADORA.pdf`
    ];
  } else if (categoria === 'celular') {
    archivosEsperados = [
      `PRO-TI-CE-001-${correlativo} CERTIFICADO DE COMPROMISO Y ENTREGA DE TELEFONO CORPORATIVO.pdf`,
      `PRO-TI-CE-002-${correlativo} MEMORANDO DE ENTREGA.pdf`
    ];
  } else if (categoria === 'tablet') {
    archivosEsperados = [
      `PRO-TI-CE-003-${correlativo} ENTREGA DE TABLET.pdf`
    ];
  } else {
    // Periféricos
    archivosEsperados = [
      `PRO-TI-CE-005-${correlativo} ENTREGA DE PERIFERICO.pdf`
    ];
  }
  
  // Normalizar nombres de archivos subidos
  const archivosSubidos = _archivosManual.map(f => f.name.trim());
  
  // Verificar si los archivos subidos coinciden con los esperados
  const archivosEncontrados = [];
  const archivosFaltantes = [];
  const archivosIncorrectos = [];
  
  // Comparar cada archivo esperado
  for (const esperado of archivosEsperados) {
    const encontrado = archivosSubidos.find(subido => {
      return subido.toLowerCase().replace(/\s+/g, ' ') === esperado.toLowerCase().replace(/\s+/g, ' ');
    });
    
    if (encontrado) {
      archivosEncontrados.push(esperado);
    } else {
      archivosFaltantes.push(esperado);
    }
  }
  
  // Detectar archivos que no coinciden con ningún esperado
  for (const subido of archivosSubidos) {
    const esValido = archivosEsperados.some(esperado => 
      subido.toLowerCase().replace(/\s+/g, ' ') === esperado.toLowerCase().replace(/\s+/g, ' ')
    );
    
    if (!esValido) {
      archivosIncorrectos.push(subido);
    }
  }
  
  // Validaciones
  if (archivosIncorrectos.length > 0) {
    // Hay archivos con nombres incorrectos
    let mensaje = 'El nombre de los archivos está en el formato incorrecto.\n\n';
    mensaje += 'Utilice los siguientes formatos para cada archivo:\n\n';
    archivosEsperados.forEach(nombre => {
      const nombreSinExt = nombre.replace('.pdf', '');
      mensaje += `• ${nombreSinExt}\n\n`;
    });
    
    openGlobalMessageModal('error', 'Formato incorrecto', mensaje);
    return;
  }
  
  if (archivosFaltantes.length > 0) {
    // Faltan archivos
    const plural = archivosFaltantes.length > 1 ? 's' : '';
    let mensaje = `Falta${plural === 's' ? 'n' : ''} ${archivosFaltantes.length} archivo${plural}:\n\n`;
    archivosFaltantes.forEach(nombre => {
      const nombreSinExt = nombre.replace('.pdf', '');
      mensaje += `• ${nombreSinExt}\n\n`;
    });
    
    openGlobalMessageModal('warning', 'Documentos incompletos', mensaje);
    return;
  }
  
  showLoading('Subiendo documentos firmados...');
  
  try {
    // Crear FormData para enviar archivos
    const formData = new FormData();
    _archivosManual.forEach((file, idx) => {
      formData.append('files', file);
    });
    
    const response = await fetch(`/devices/asignacion/${asignacionId}/upload-signed-documents`, {
      method: 'POST',
      credentials: 'same-origin',
      body: formData
    });
    
    hideLoading();
    
    // Leer el body UNA SOLA VEZ para evitar "body stream already read"
    const contentType = response.headers.get('content-type');
    let result;
    
    if (contentType && contentType.includes('application/json')) {
      result = await response.json();
    } else {
      const text = await response.text();
      // Si es HTML, es un error del servidor
      if (text.includes('<')) {
        throw new Error(`Error del servidor (${response.status}). Revisa los logs del servidor.`);
      }
      // Intentar parsear como JSON por si acaso
      try {
        result = JSON.parse(text);
      } catch (e) {
        throw new Error(text || `Error HTTP ${response.status}`);
      }
    }
    
    if (!response.ok) {
      throw new Error(result.message || `Error HTTP ${response.status}`);
    }
    
    if (!result.success) {
      throw new Error(result.message || 'Error desconocido');
    }
    
    // Cerrar modal de subida
    closeModal('modalSubidaManual');
    
    // Actualizar tabla
    if (typeof reloadAsignacionesTable === 'function') {
      reloadAsignacionesTable();
    }
    
    // Mostrar documentos subidos en estado 23
    await mostrarModalDocumentosOneDrive(result.archivos || [], 23);
    
  } catch (error) {
    console.error('Error subiendo documentos:', error);
    hideLoading();
    openGlobalMessageModal('error', 'Error', `No se pudieron subir los documentos:\\n${error.message}`);
  }
}

// ESTADO 23\u219224\u219290: Confirmar documentos manuales finales
async function confirmarDocumentosManualesFinales(correlativo) {
  const asignacionId = window._asignacionIdParaDocumentos || _asignacionIdActual;
  if (!asignacionId) {
    openGlobalMessageModal('error', 'Error', 'No se pudo identificar la asignación');
    return;
  }
  
  showLoading('Confirmando documentos finales...');
  
  try {
    const response = await fetch(`/devices/asignacion/${asignacionId}/confirm-manual-documents`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'}
    });
    
    const result = await response.json();
    
    hideLoading();
    
    if (!response.ok || !result.success) {
      throw new Error(result.message || `HTTP ${response.status}`);
    }
    
    // Actualizar tabla
    if (typeof reloadAsignacionesTable === 'function') {
      reloadAsignacionesTable();
    }
    
    // Mostrar estado final
    await mostrarModalDocumentosOneDrive(result.archivos || [], 90);
    
    openGlobalSuccessModal('Los documentos han sido confirmados y el proceso de firma manual ha finalizado correctamente.');
    
  } catch (error) {
    console.error('Error confirmando documentos:', error);
    hideLoading();
    openGlobalMessageModal('error', 'Error', `No se pudieron confirmar los documentos:\\n${error.message}`);
  }
}

// Descargar archivos en ZIP con correlativo
async function descargarArchivosZip(correlativo) {
  try {
    // Preserve active modal so we can restore it after download (prevent unexpected modal close)
    const activeModalEl = document.querySelector('.modal-overlay.active');
    const activeModalId = activeModalEl ? activeModalEl.id : null;

    showLoading('Agrupando archivos en ZIP...');
    
    // Intentar obtener asignacionId de diferentes fuentes
    const asignacionId = window._asignacionIdParaDocumentos || 
                         window._asignacionIdActual || 
                         window._asignacionIdDocumentacion ||
                         _asignacionIdActual;
    
    if (!asignacionId) {
      hideLoading();
      alert('Error: No se pudo identificar la asignación');
      return;
    }
    
    if (!correlativo) {
      hideLoading();
      alert('Error: No se pudo identificar el correlativo');
      return;
    }
    
    const response = await fetch(`/devices/asignacion/${asignacionId}/download-zip?correlativo=${correlativo}`, {
      method: 'GET',
      credentials: 'same-origin'
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: 'Error desconocido' }));
      throw new Error(errorData.error || `Error HTTP ${response.status}`);
    }
    
    // Descargar archivo
    const blob = await response.blob();
    
    // Verificar que el blob no está vacío
    if (blob.size === 0) {
      throw new Error('El archivo ZIP está vacío');
    }
    
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${correlativo}.zip`;
    document.body.appendChild(a);
    a.click();
    
    // Limpiar despuís de un breve delay
    setTimeout(() => {
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    }, 100);
    
    hideLoading();
    // Re-open previously active modal if it was closed by the download
    try { if (activeModalId) openModal(activeModalId); } catch(e) {}
    
  } catch(e) {
    hideLoading();
    console.error('Error descargando ZIP:', e);
    // Try to re-open active modal if it was closed
    try { const activeModalEl = document.querySelector('.modal-overlay.active'); if (!activeModalEl) { if (typeof window._lastActiveModalId !== 'undefined' && window._lastActiveModalId) openModal(window._lastActiveModalId); } } catch(err) {}
    if (typeof openGlobalMessageModal === 'function') {
      openGlobalMessageModal('error', 'Error al descargar', 'No se pudieron descargar los archivos: ' + e.message);
    } else {
      alert('Error al descargar archivos: ' + e.message);
    }
  }
}

// función helper para extraer correlativo del nombre de archivo
function extraerCorrelativo(nombre) {
  // Buscar patrín PRO-TI-CE-00X-NNNNNN
  const match = nombre.match(/PRO-TI-CE-\d+-([\d]{6})/);
  return match ? match[1] : null;
}

// ============================================================================
// FUNCIONES PARA FLUJO DE FIRMAS DIGITALES (Estados 11?12?13?14)
// ============================================================================

// Variables globales para almacenar firmas durante el flujo
window._firmaEmpleadoDataUrl = null;
window._firmaUsuarioDataUrl = null;

// ESTADO 11 ? 12: Capturar firma del empleado
function abrirModalCapturarFirmaEmpleado() {
  // Configurar el modal de firma para el empleado
  const titleEl = document.getElementById('signatureModalTitle');
  const btnEl = document.getElementById('btnSaveSignature');
  
  if (titleEl) titleEl.textContent = 'Capturar Firma - Empleado';
  if (btnEl) {
    btnEl.textContent = 'Siguiente';
    // Limpiar eventos previos y agregar nuevo
    const newBtn = btnEl.cloneNode(true);
    btnEl.parentNode.replaceChild(newBtn, btnEl);
    
    // MARCAR COMO BOUND ANTES de setTimeout(initSignaturePad)
    // Esto previene que initSignaturePad agregue el listener viejo de saveSignature()
    newBtn._bound = true;
    
    newBtn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      if (!_signaturePad || _signaturePad.isEmpty()) {
        alert('Firma requerida\n\nPor favor, captura la firma del empleado antes de continuar.');
        return;
      }
      
      // Guardar firma del empleado
      const canvas = document.getElementById('signatureCanvas');
      window._firmaEmpleadoDataUrl = canvas.toDataURL('image/png');
      
      // Cerrar modal y abrir el siguiente para capturar firma del usuario
      closeModal('modalSignature');
      setTimeout(abrirModalCapturarFirmaUsuario, 300);
    });
  }
  
  // Abrir modal y inicializar canvas
  if (typeof openModal === 'function') {
    openModal('modalSignature');
    setTimeout(initSignaturePad, 100);
  }
}

// ESTADO 12: Capturar firma del usuario
function abrirModalCapturarFirmaUsuario() {
  // Configurar el modal de firma para el usuario
  const titleEl = document.getElementById('signatureModalTitle');
  const btnEl = document.getElementById('btnSaveSignature');
  
  if (titleEl) titleEl.textContent = 'Capturar Firma - Usuario del Sistema';
  if (btnEl) {
    btnEl.textContent = 'Aplicar Firmas';
    // Limpiar eventos previos y agregar nuevo
    const newBtn = btnEl.cloneNode(true);
    btnEl.parentNode.replaceChild(newBtn, btnEl);
    
    // MARCAR COMO BOUND ANTES de setTimeout(initSignaturePad)
    // Esto previene que initSignaturePad agregue el listener viejo de saveSignature()
    newBtn._bound = true;
    
    newBtn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      if (!_signaturePad || _signaturePad.isEmpty()) {
        alert('Firma requerida\n\nPor favor, captura la firma del usuario antes de continuar.');
        return;
      }
      
      // Guardar firma del usuario
      const canvas = document.getElementById('signatureCanvas');
      window._firmaUsuarioDataUrl = canvas.toDataURL('image/png');
      
      // Cerrar modal y aplicar firmas a documentos
      closeModal('modalSignature');
      setTimeout(aplicarFirmasADocumentos, 300);
    });
  }
  
  // Abrir modal y inicializar canvas
  if (typeof openModal === 'function') {
    openModal('modalSignature');
    setTimeout(initSignaturePad, 100);
  }
}

// ESTADO 12 ? 13: Aplicar firmas a documentos (llamada backend)
async function aplicarFirmasADocumentos() {
  if (!window._correlativoActual) {
    if (typeof openGlobalMessageModal === 'function') {
      openGlobalMessageModal('error', 'Error', 'No se encontró el correlativo de los documentos.');
    } else {
      alert('Error: No se encontró el correlativo de los documentos.');
    }
    return;
  }
  
  if (!window._firmaEmpleadoDataUrl || !window._firmaUsuarioDataUrl) {
    if (typeof openGlobalMessageModal === 'function') {
      openGlobalMessageModal('error', 'Error', 'Faltan las firmas capturadas. Por favor, captura ambas firmas antes de continuar.');
    } else {
      alert('Error: Faltan las firmas capturadas.');
    }
    return;
  }
  
  // Mostrar modal de carga y actualizar stepper a paso 3
  try { if (typeof setDocumentationProgress === 'function') setDocumentationProgress(3); } catch(e){}
  if (typeof showLoading === 'function') {
    showLoading('Verificando estado y agregando firmas...');
  } else if (typeof openGlobalMessageModal === 'function') {
    openGlobalMessageModal('info', 'Agregando Firmas', 'Por favor espera mientras se verifica el estado y se agregan las firmas ingresadas a los documentos...', false);
  }
  
  try {
    // Validar que tenemos el asignacion_id
    const asignacionId = window._asignacionIdParaDocumentos || _asignacionIdActual;
    if (!asignacionId) {
      throw new Error('No se encontró el ID de asignación');
    }
    
    // PRIMERO: Verificar el estado actual de la asignación
    const estadoResp = await fetch(`/devices/asignacion/${asignacionId}/estado-documentacion`, {
      method: 'GET',
      credentials: 'same-origin'
    });
    
    const estadoData = await estadoResp.json().catch(() => null);
    
    if (!estadoResp.ok || !estadoData || !estadoData.success) {
      throw new Error(estadoData?.message || 'No se pudo verificar el estado de la asignación');
    }
    
    // Validar que está en estado 12
    if (estadoData.estado_documentacion !== 12) {
      throw new Error(`${estadoData.descripcion_estado}\n\nAcción requerida: ${estadoData.siguiente_paso}`);
    }
    
    // SEGUNDO: Preparar payload de firmas
    const payload = {
      firma_empleado_b64: window._firmaEmpleadoDataUrl,
      firma_usuario_b64: window._firmaUsuarioDataUrl,
      observaciones: window._observacionesDispositivo || {}  // Incluir observaciones si están disponibles
    };
    
    // TERCERO: Aplicar firmas
    const response = await fetch(`/devices/asignacion/${asignacionId}/apply-signatures`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'same-origin'
    });
    
    const resultRaw = await response.json().catch(() => null);
    
    if (!response.ok) {
      // Si el backend indica que se requiere pasaporte, abrir modal para capturarlo
      if (resultRaw && resultRaw.requiere_pasaporte) {
        document.getElementById('pasaporteModalMessage').textContent = resultRaw.message || 'El empleado no tiene identidad registrada.';
        document.getElementById('pasaporteInput').value = '';
        document.getElementById('pasaporteError').style.display = 'none';
        window._pasaporteData = { empleadoId: resultRaw.empleado_id };
        // Guardar payload de apply-signatures para reintentar luego
        window._applySignPayload = payload;
        window._pasaporteAfterApplySignatures = true;
        
        openModal('pasaporteModal');
        document.getElementById('pasaporteInput').focus();
        // Cerrar loaders
        if (typeof hideLoading === 'function') hideLoading();
        if (typeof closeGlobalMessageModal === 'function') closeGlobalMessageModal();
        return;
      }
      
      // Si el estado es inválido, mostrar mensaje específico
      if (resultRaw && resultRaw.estado_actual !== undefined) {
        const estadoActual = resultRaw.estado_actual;
        let mensajeDetallado = resultRaw.message || '';
        
        if (estadoActual === 11) {
          mensajeDetallado += '\n\nAcción requerida: Marque todos los documentos como leídos en el paso anterior y acepte los términos.';
        } else if (estadoActual > 12) {
          mensajeDetallado += '\n\nLa asignación ya ha avanzado en el proceso de documentación.';
        }
        
        throw new Error(mensajeDetallado);
      }
      
      const errorMessage = (resultRaw && resultRaw.message) ? resultRaw.message : `HTTP ${response.status}`;
      throw new Error(`Error aplicando firmas: ${errorMessage}`);
    }

    const result = resultRaw || {};
    
    // Cerrar loader
    if (typeof hideLoading === 'function') {
      hideLoading();
    }
    if (typeof closeGlobalMessageModal === 'function') {
      closeGlobalMessageModal();
    }
    
    if (result.success && result.archivos) {
      // Mostrar documentos con firmas aplicadas (estado 13)
      mostrarModalDocumentosOneDrive(result.archivos, 13);
    } else {
      throw new Error(result.message || 'No se pudieron aplicar las firmas');
    }
    
  } catch (error) {
    console.error('Error aplicando firmas:', error);
    
    // Cerrar loader
    if (typeof hideLoading === 'function') {
      hideLoading();
    }
    if (typeof closeGlobalMessageModal === 'function') {
      closeGlobalMessageModal();
    }
    
    if (typeof openGlobalMessageModal === 'function') {
      openGlobalMessageModal('error', 'Error', `No se pudieron aplicar las firmas:\n${error.message}`);
    } else {
      alert(`⚠ Error\n\nNo se pudieron aplicar las firmas:\n${error.message}`);
    }
  }
}

// UI para ESTADOS 13/23: Agregar botones Confirmar y Regenerar
function agregarBotonesEstado13(correlativo, estado) {
  const modal = document.getElementById('modalDocumentosOneDrive');
  if (!modal) return;
  
  let actionsContainer = modal.querySelector('.modal-docs-actions');
  if (!actionsContainer) {
    actionsContainer = document.createElement('div');
    actionsContainer.className = 'modal-docs-actions';
    actionsContainer.style.cssText = 'padding: 20px; border-top: 1px solid #e5e7eb; margin-top: 20px;';
    const modalBody = modal.querySelector('.modal-body') || modal.querySelector('.modal');
    modalBody.appendChild(actionsContainer);
  }
  
  const confirmarFn = estado === 23 ? confirmarDocumentosManualesFinales : confirmarDocumentosFinales;
  
  actionsContainer.innerHTML = `
    <div style="display: flex; gap: 12px; justify-content: space-between; margin-bottom: 10px;">
      <button class="btn" id="btnDownloadEstado13" style="background: #10b981; color: white; border: none;">Descargar archivos</button>
      <div style="display: flex; gap: 12px;">
        <button class="btn btn-warning" id="btnRegenerarEstado13">
          Regenerar Documentos
        </button>
        <button class="btn btn-success" id="btnConfirmarEstado13">
          Confirmar Documentos
        </button>
      </div>
    </div>
    <p style="margin: 0; font-size: 0.8rem; color: #6b7280; text-align: center;">
      <strong>Regenerar:</strong> Elimina estos documentos y vuelve al inicio para generar nuevamente.<br>
      <strong>Confirmar:</strong> Marca los documentos como finales y completa el proceso.
    </p>
  `;

  const btnDownload = actionsContainer.querySelector('#btnDownloadEstado13');
  const btnRegenerar = actionsContainer.querySelector('#btnRegenerarEstado13');
  const btnConfirmar = actionsContainer.querySelector('#btnConfirmarEstado13');
  if (btnDownload) {
    btnDownload.addEventListener('click', function() {
      descargarArchivosZip(correlativo);
    });
  }
  if (btnRegenerar) {
    btnRegenerar.addEventListener('click', function() {
      regenerarDocumentos(correlativo);
    });
  }
  if (btnConfirmar) {
    btnConfirmar.addEventListener('click', function() {
      confirmarFn(correlativo);
    });
  }
}

// ESTADO 13 ? 14: Confirmar documentos finales
async function confirmarDocumentosFinales(correlativo) {
  // Usar modal de confirmación existente
  openGlobalDeleteModal(
    async () => {
      // Cerrar el modal de documentos actual
      closeModal('modalDocumentosOneDrive');
      
      // Mostrar loader con stepper en paso 4
      if (typeof showLoading === 'function') {
        showLoading('Confirmando documentos finales...');
      } else if (typeof openGlobalMessageModal === 'function') {
        openGlobalMessageModal('info', 'Finalizando', 'Confirmando documentos finales...', false);
      }
      
      // Actualizar stepper a paso 4 mientras carga
      try { 
        if (typeof setDocumentationProgress === 'function') {
          setDocumentationProgress(4); 
        }
      } catch(e) {}
      
      try {
        const payload = {
          correlativo: correlativo,
          asignacion_id: window._asignacionIdParaDocumentos || _asignacionIdActual || null
        };
        
        const response = await fetch(`/devices/asignacion/${payload.asignacion_id}/confirmar-final`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          credentials: 'same-origin'
        });
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ message: `HTTP ${response.status}` }));
          throw new Error(errorData.message || 'Error al finalizar documentos');
        }
        
        const result = await response.json();
        
        // Cerrar loader
        if (typeof hideLoading === 'function') {
          hideLoading();
        } else if (typeof closeGlobalMessageModal === 'function') {
          closeGlobalMessageModal();
        }
        
        // Actualizar tabla
        if (typeof reloadAsignacionesTable === 'function') {
          reloadAsignacionesTable();
        }
        
        // Mostrar modal de documentos en estado 14/90 con stepper en paso 4
        await mostrarModalDocumentosOneDrive(result.archivos || [], result.estado || 14);
        
      } catch (error) {
        console.error('Error finalizando documentos:', error);
        
        if (typeof closeGlobalMessageModal === 'function') {
          closeGlobalMessageModal();
        }
        
        if (typeof openGlobalMessageModal === 'function') {
          openGlobalMessageModal('error', 'Error', `No se pudieron finalizar los documentos:\n${error.message}`);
        } else {
          alert(`? Error\n\nNo se pudieron finalizar los documentos:\n${error.message}`);
        }
      }
    },
    'Confirmar Documentos',
    '¿Confirmar documentos?\n\nSe marcarán los documentos como finales y se completará el proceso de generación.'
  );
}

// ESTADO 13 ? 0: Regenerar documentos (eliminar y volver a estado inicial)
async function regenerarDocumentos(correlativo) {
  // Usar modal de confirmación existente
  openGlobalDeleteModal(
    async () => {
      // Mostrar loader
      showLoading('Eliminando documentos...');
      
      try {
        const payload = {
          correlativo: correlativo,
          asignacion_id: window._asignacionIdParaDocumentos || null
        };
        
        const response = await fetch('/devices/delete-documents-by-correlativo', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          credentials: 'same-origin'
        });
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ message: `HTTP ${response.status}` }));
          throw new Error(errorData.message || 'Error al eliminar documentos');
        }
        
        const result = await response.json();
        
        // Cerrar loader
        hideLoading();
        
        // Cerrar modal de documentos
        closeModal('modalDocumentosOneDrive');
        
        // Limpiar variables globales
        window._correlativoActual = null;
        window._firmaEmpleadoDataUrl = null;
        window._firmaUsuarioDataUrl = null;
        window._asignacionIdParaDocumentos = null;
        
        // Volver a abrir modal de selección de tipo
        if (window._asignacionIdActual) {
          abrirModalSeleccionarTipoDocumentacion(window._asignacionIdActual);
        }
        
      } catch (error) {
        hideLoading();
        
        if (typeof openGlobalMessageModal === 'function') {
          openGlobalMessageModal('error', 'Error', `No se pudieron eliminar los documentos:\n${error.message}`);
        } else {
          alert(`Error\n\nNo se pudieron eliminar los documentos:\n${error.message}`);
        }
      }
    },
    'Regenerar Documentos',
    'ADVERTENCIA: Se eliminarán TODOS los documentos actuales con este correlativo y deberás iniciar el proceso desde el principio.\n\n¿Estás seguro?'
  );
}

// ============================================================================
// FIN FUNCIONES FLUJO FIRMAS DIGITALES
// ============================================================================

// ============================================================================
// FUNCIONES PARA FLUJO DE FIRMAS MANUALES (Estados 21?22?23?24)
// ============================================================================

// ESTADO 21: Mostrar modal con descarga ZIP de documentos sin placeholders
function mostrarModalDescargaManual(archivos, correlativo) {
  // Validar que archivos sea un array
  if (!Array.isArray(archivos)) {
    console.error('[ERROR] archivos no es un array', {tipo: typeof archivos, valor: archivos});
    openGlobalMessageModal('error', 'Error', 'Formato de datos incorrecto. Se esperaba un array.');
    return;
  }
  
  const modal = document.getElementById('modalDocumentosOneDrive');
  if (!modal) {
    alert('Error: No se encontró el modal de documentos');
    return;
  }
  
  // Abrir modal
  if (typeof openModal === 'function') {
    openModal('modalDocumentosOneDrive');
  } else {
    modal.style.display = 'flex';
  }
  
  const modalBody = modal.querySelector('.modal-body') || modal.querySelector('.modal');
  if (!modalBody) return;
  
  modalBody.innerHTML = '<div class="loading">Preparando documentos...</div>';
  
  // Renderizar contenido del estado 21
  setTimeout(() => {
    modalBody.innerHTML = `
      <div style="padding: 20px;">
        <div style="background: #fef3c7; border: 1px solid #fbbf24; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
          <h4 style="margin: 0 0 10px 0; color: #92400e; font-size: 1.1rem;">Firma Manual - Descarga de Documentos</h4>
          <p style="margin: 0; color: #78350f; line-height: 1.5;">
            Los documentos han sido generados sin placeholders de firma digital.<br>
            Descarga el archivo ZIP, imprime los documentos, obtén las firmas manuscritas y luego sube los documentos escaneados.
          </p>
        </div>
        
        <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
          <h5 style="margin: 0 0 15px 0; color: #1f2937; font-size: 1rem;">Documentos Generados</h5>
          <ul style="margin: 0; padding-left: 20px; color: #4b5563; line-height: 1.8;">
            ${archivos.map(a => `<li><strong>${a.nombre || a.name || 'Documento'}</strong></li>`).join('')}
          </ul>
        </div>
        
        <div style="background: #eff6ff; border: 1px solid #93c5fd; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
          <h5 style="margin: 0 0 10px 0; color: #1e40af; font-size: 0.95rem;">Instrucciones</h5>
          <ol style="margin: 0; padding-left: 20px; color: #1e3a8a; line-height: 1.8; font-size: 0.9rem;">
            <li>Descarga el archivo ZIP con todos los documentos</li>
            <li>Extrae e imprime cada documento</li>
            <li>Obtén las firmas manuscritas en los documentos impresos</li>
            <li>Escanea los documentos firmados en formato PDF</li>
            <li>Nombra cada archivo escaneado agregando el sufijo <strong>_rev</strong> antes de <code>.pdf</code><br>
                <small style="color: #6b7280;">Ejemplo: <code>PRO-TI-CE-001-123456 CARTA.pdf</code> ? <code>PRO-TI-CE-001-123456 CARTA_rev.pdf</code></small>
            </li>
            <li>Sube los archivos escaneados en la siguiente pantalla</li>
          </ol>
        </div>
        
        <div style="display: flex; gap: 12px; justify-content: flex-end;">
          <button class="btn btn-secondary" onclick="closeModal('modalDocumentosOneDrive')">Cancelar</button>
          <button class="btn btn-primary" onclick="descargarZipDocumentos('${correlativo}')">
            Descargar ZIP
          </button>
          <button class="btn btn-success" onclick="abrirModalSubirDocumentosFirmados('${correlativo}', ${JSON.stringify(archivos).replace(/'/g, '&#39;')})">
            Continuar ? Subir Firmados
          </button>
        </div>
      </div>
    `;
  }, 100);
}

// Descargar ZIP con documentos generados
async function descargarZipDocumentos(correlativo) {
  try {
    if (typeof openGlobalMessageModal === 'function') {
      openGlobalMessageModal('info', 'Preparando ZIP', 'Generando archivo ZIP con los documentos...', false);
    }
    
    const response = await fetch(`/download-documents-zip/${correlativo}`, {
      method: 'GET',
      credentials: 'same-origin'
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: `HTTP ${response.status}` }));
      throw new Error(errorData.message || 'Error al descargar ZIP');
    }
    
    // Descargar el archivo
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Documentos_${correlativo}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    if (typeof closeGlobalMessageModal === 'function') {
      closeGlobalMessageModal();
    }
    
    if (typeof openGlobalSuccessModal === 'function') {
      openGlobalSuccessModal('El archivo ZIP se ha descargado correctamente.');
    }
    
  } catch (error) {
    console.error('Error descargando ZIP:', error);
    
    if (typeof closeGlobalMessageModal === 'function') {
      closeGlobalMessageModal();
    }
    
    if (typeof openGlobalMessageModal === 'function') {
      openGlobalMessageModal('error', 'Error', `No se pudo descargar el archivo ZIP:\n${error.message}`);
    } else {
      alert(`? Error\n\nNo se pudo descargar el archivo ZIP:\n${error.message}`);
    }
  }
}

// ESTADO 22: Abrir modal para subir documentos firmados con validaciín
function abrirModalSubirDocumentosFirmados(correlativo, archivosOriginales) {
  closeModal('modalDocumentosOneDrive');
  
  // Crear modal de subida si no existe
  let uploadModal = document.getElementById('modalSubirDocumentosFirmados');
  if (!uploadModal) {
    uploadModal = document.createElement('div');
    uploadModal.id = 'modalSubirDocumentosFirmados';
    uploadModal.className = 'modal-overlay';
    uploadModal.innerHTML = `
      <div class="modal" style="max-width: 800px;">
        <div class="modal-header">
          <h3>Subir Documentos Firmados</h3>
          <button class="modal-close" onclick="closeModal('modalSubirDocumentosFirmados')">&times;</button>
        </div>
        <div class="modal-body" id="uploadModalBody"></div>
      </div>
    `;
    document.body.appendChild(uploadModal);
  }
  
  const modalBody = document.getElementById('uploadModalBody');
  if (!modalBody) return;
  
  // Generar lista de archivos esperados con sufijo _rev
  const archivosEsperados = archivosOriginales.map(a => {
    const nombre = a.nombre || a.name || '';
    return nombre.replace('.pdf', '_rev.pdf');
  });
  
  modalBody.innerHTML = `
    <div style="padding: 20px;">
      <div style="background: #eff6ff; border: 1px solid #93c5fd; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
        <h5 style="margin: 0 0 10px 0; color: #1e40af;">Archivos Esperados</h5>
        <ul style="margin: 0; padding-left: 20px; color: #1e3a8a; line-height: 1.8; font-size: 0.9rem;">
          ${archivosEsperados.map(nombre => `<li><code>${nombre}</code></li>`).join('')}
        </ul>
        <p style="margin: 10px 0 0 0; font-size: 0.85rem; color: #6b7280;">
          Los nombres deben coincidir exactamente, incluyendo el sufijo <strong>_rev</strong> antes de <code>.pdf</code>
        </p>
      </div>
      
      <div style="border: 2px dashed #d1d5db; border-radius: 8px; padding: 30px; text-align: center; background: #f9fafb; margin-bottom: 20px;">
        <input type="file" id="inputDocumentosFirmados" multiple accept=".pdf" style="display: none;">
        <label for="inputDocumentosFirmados" style="cursor: pointer;">
          <div style="font-size: 3rem; margin-bottom: 10px;"></div>
          <p style="margin: 0; color: #4b5563; font-size: 1rem;"><strong>Click para seleccionar archivos PDF</strong></p>
          <p style="margin: 5px 0 0 0; color: #6b7280; font-size: 0.85rem;">o arrastra los archivos aquí</p>
        </label>
      </div>
      
      <div id="listaArchivosSeleccionados" style="margin-bottom: 20px;"></div>
      
      <div style="display: flex; gap: 12px; justify-content: flex-end;">
        <button class="btn btn-secondary" onclick="closeModal('modalSubirDocumentosFirmados')">Cancelar</button>
        <button class="btn btn-primary" id="btnSubirDocumentosFirmados" disabled onclick="subirDocumentosFirmados('${correlativo}', ${JSON.stringify(archivosEsperados).replace(/'/g, '&#39;')})">
          Subir Documentos
        </button>
      </div>
    </div>
  `;
  
  // Abrir modal
  if (typeof openModal === 'function') {
    openModal('modalSubirDocumentosFirmados');
  } else {
    uploadModal.style.display = 'flex';
  }
  
  // Agregar eventos para seleccionar archivos
  const input = document.getElementById('inputDocumentosFirmados');
  const listaDiv = document.getElementById('listaArchivosSeleccionados');
  const btnSubir = document.getElementById('btnSubirDocumentosFirmados');
  
  input.addEventListener('change', function(e) {
    const files = Array.from(e.target.files);
    mostrarArchivosSeleccionados(files, archivosEsperados, listaDiv, btnSubir);
  });
  
  // Drag & drop
  const dropZone = modalBody.querySelector('[style*="dashed"]');
  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = '#3b82f6';
    dropZone.style.background = '#eff6ff';
  });
  
  dropZone.addEventListener('dragleave', () => {
    dropZone.style.borderColor = '#d1d5db';
    dropZone.style.background = '#f9fafb';
  });
  
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = '#d1d5db';
    dropZone.style.background = '#f9fafb';
    
    const files = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
    input.files = e.dataTransfer.files;
    mostrarArchivosSeleccionados(files, archivosEsperados, listaDiv, btnSubir);
  });
  
  // Guardar archivos esperados en el modal para usarlos despuís
  window._archivosEsperados = archivosEsperados;
}

// Mostrar archivos seleccionados y validar nombres
function mostrarArchivosSeleccionados(files, archivosEsperados, listaDiv, btnSubir) {
  if (files.length === 0) {
    listaDiv.innerHTML = '';
    btnSubir.disabled = true;
    return;
  }
  
  let html = '<div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 15px;"><h5 style="margin: 0 0 10px 0; color: #1f2937;">Archivos Seleccionados:</h5><ul style="margin: 0; padding-left: 20px; list-style: none;">';
  
  let todosValidos = files.length === archivosEsperados.length;
  const nombresSeleccionados = files.map(f => f.name);
  
  archivosEsperados.forEach(esperado => {
    const encontrado = nombresSeleccionados.includes(esperado);
    if (!encontrado) todosValidos = false;
    
    html += `<li style="margin-bottom: 8px; color: ${encontrado ? '#059669' : '#dc2626'}; font-size: 0.9rem;">
      ${encontrado ? '?' : '?'} <code>${esperado}</code>
      ${!encontrado ? '<span style="color: #6b7280;"> - No encontrado</span>' : ''}
    </li>`;
  });
  
  files.forEach(f => {
    if (!archivosEsperados.includes(f.name)) {
      todosValidos = false;
      html += `<li style="margin-bottom: 8px; color: #dc2626; font-size: 0.9rem;">
        ? <code>${f.name}</code> <span style="color: #6b7280;"> - No esperado</span>
      </li>`;
    }
  });
  
  html += '</ul></div>';
  
  if (!todosValidos) {
    html += '<div style="background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 12px; margin-top: 10px; color: #991b1b; font-size: 0.85rem;">Los archivos seleccionados no coinciden con los esperados. Verifica los nombres.</div>';
  }
  
  listaDiv.innerHTML = html;
  btnSubir.disabled = !todosValidos;
}

// ESTADO 22: Subir documentos firmados al servidor
async function subirDocumentosFirmados(correlativo, archivosEsperados) {
  const input = document.getElementById('inputDocumentosFirmados');
  const files = input.files;
  
  if (!files || files.length === 0) {
    alert('Por favor selecciona los archivos PDF firmados.');
    return;
  }
  
  // Validar que todos los archivos esperados están presentes
  const nombresSeleccionados = Array.from(files).map(f => f.name);
  const faltantes = archivosEsperados.filter(e => !nombresSeleccionados.includes(e));
  
  if (faltantes.length > 0) {
    alert(`Faltan archivos:\n\n${faltantes.join('\n')}\n\nPor favor selecciona todos los archivos requeridos.`);
    return;
  }
  
  // Mostrar loader
  if (typeof openGlobalMessageModal === 'function') {
    openGlobalMessageModal('info', 'Subiendo Archivos', 'Por favor espera mientras se suben los documentos...', false);
  }
  
  try {
    const formData = new FormData();
    formData.append('correlativo', correlativo);
    formData.append('asignacion_id', window._asignacionIdParaDocumentos || '');
    
    Array.from(files).forEach(file => {
      formData.append('files', file);
    });
    
    const response = await fetch('/upload-signed-documents', {
      method: 'POST',
      body: formData,
      credentials: 'same-origin'
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: `HTTP ${response.status}` }));
      throw new Error(errorData.message || 'Error al subir documentos');
    }
    
    const result = await response.json();
    
    // Cerrar loader y modal de subida
    if (typeof closeGlobalMessageModal === 'function') {
      closeGlobalMessageModal();
    }
    
    closeModal('modalSubirDocumentosFirmados');
    
    // Pasar al estado 23 - verificaciín y renombrado
    if (result.success) {
      mostrarModalVerificacionDocumentos(correlativo, result.archivos_subidos);
    } else {
      throw new Error(result.message || 'No se pudieron subir los documentos');
    }
    
  } catch (error) {
    console.error('Error subiendo documentos:', error);
    
    if (typeof closeGlobalMessageModal === 'function') {
      closeGlobalMessageModal();
    }
    
    if (typeof openGlobalMessageModal === 'function') {
      openGlobalMessageModal('error', 'Error', `No se pudieron subir los documentos:\n${error.message}`);
    } else {
      alert(`? Error\n\nNo se pudieron subir los documentos:\n${error.message}`);
    }
  }
}

// ESTADO 23: Verificar y confirmar documentos subidos (eliminar originales, renombrar _rev)
function mostrarModalVerificacionDocumentos(correlativo, archivosSubidos) {
  const modal = document.getElementById('modalDocumentosOneDrive');
  if (!modal) return;
  
  // Abrir modal
  if (typeof openModal === 'function') {
    openModal('modalDocumentosOneDrive');
  } else {
    modal.style.display = 'flex';
  }
  
  const modalBody = modal.querySelector('.modal-body') || modal.querySelector('.modal');
  if (!modalBody) return;
  
  modalBody.innerHTML = `
    <div style="padding: 20px;">
      <div style="background: #d1fae5; border: 1px solid #6ee7b7; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
        <h4 style="margin: 0 0 10px 0; color: #065f46; font-size: 1.1rem;">? Documentos Subidos Correctamente</h4>
        <p style="margin: 0; color: #047857; line-height: 1.5;">
          Los documentos firmados han sido subidos exitosamente.<br>
          Al confirmar, se eliminarán los documentos originales sin firmas y se renombrarán los archivos <code>_rev</code> a sus nombres finales.
        </p>
      </div>
      
      <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
        <h5 style="margin: 0 0 15px 0; color: #1f2937; font-size: 1rem;">Archivos Subidos</h5>
        <ul style="margin: 0; padding-left: 20px; color: #4b5563; line-height: 1.8;">
          ${archivosSubidos.map(a => `<li><code>${a.nombre || a.name || 'Documento'}</code></li>`).join('')}
        </ul>
      </div>
      
      <div style="background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
        <h5 style="margin: 0 0 10px 0; color: #92400e; font-size: 0.95rem;">Acción Requerida</h5>
        <p style="margin: 0; color: #78350f; font-size: 0.9rem; line-height: 1.5;">
          Al confirmar se realizarán las siguientes acciones:<br>
          1. Se eliminarán los documentos originales (sin firmas)<br>
          2. Se renombrarán los archivos <code>_rev.pdf</code> a <code>.pdf</code> (nombres finales)<br>
          3. Se marcará el proceso como completado
        </p>
      </div>
      
      <div style="display: flex; gap: 12px; justify-content: flex-end;">
        <button class="btn btn-secondary" onclick="closeModal('modalDocumentosOneDrive')">Cancelar</button>
        <button class="btn btn-success" onclick="finalizarFlujoManual('${correlativo}')">
          ? Confirmar y Finalizar
        </button>
      </div>
    </div>
  `;
}

// ESTADO 23 ? 24: Finalizar flujo manual (eliminar originales, renombrar _rev, marcar completado)
async function finalizarFlujoManual(correlativo) {
  // Usar modal de confirmación existente
  openGlobalDeleteModal(
    async () => {
      // Mostrar loader
      if (typeof openGlobalMessageModal === 'function') {
        openGlobalMessageModal('info', 'Finalizando', 'Procesando documentos finales...', false);
      }
      
      try {
        const payload = {
          correlativo: correlativo,
          asignacion_id: window._asignacionIdParaDocumentos || null
        };
        
        const response = await fetch('/finalize-manual-signature-flow', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          credentials: 'same-origin'
        });
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ message: `HTTP ${response.status}` }));
          throw new Error(errorData.message || 'Error al finalizar flujo manual');
        }
        
        const result = await response.json();
        
        // Cerrar loader
        if (typeof closeGlobalMessageModal === 'function') {
          closeGlobalMessageModal();
        }
        
        // Actualizar tabla
        if (typeof reloadAsignacionesTable === 'function') {
          reloadAsignacionesTable();
        }
        
        // Mostrar modal de documentos en estado 24
        await mostrarModalDocumentosOneDrive(result.archivos || [], 24);
        
      } catch (error) {
        console.error('Error finalizando flujo manual:', error);
        
        if (typeof closeGlobalMessageModal === 'function') {
          closeGlobalMessageModal();
        }
        
        if (typeof openGlobalMessageModal === 'function') {
          openGlobalMessageModal('error', 'Error', `No se pudo finalizar el flujo manual:\n${error.message}`);
        } else {
          alert(`? Error\n\nNo se pudo finalizar el flujo manual:\n${error.message}`);
        }
      }
    },
    'Finalizar Firma Manual',
    '¿Finalizar proceso de firma manual?\n\nSe eliminarán los documentos originales y se renombrarán los firmados a sus nombres finales.'
  );
}

// ============================================================================
// FIN FUNCIONES FLUJO FIRMAS MANUALES
// ============================================================================

// función eliminada - ahora se usa modalDocumentosOneDrive

    // (Removed duplicate rendering block - use central renderPDFCards / mostrarModalDocumentosOneDrive)

function updateConfirmStateDocsPreview(){
  const all = Array.from(document.querySelectorAll('#modalDocsPreview .doc-chk'));
  const checkedAll = all.length ? all.every(c => c.checked) : false;
  const terms = document.getElementById('chkAcceptTerms')?.checked;
  const btn = document.getElementById('btnConfirmDocs');
  if(btn) btn.disabled = !(checkedAll && terms);
}

function openInModalViewerDocsPreview(file){
  let viewer = document.getElementById('modalDocsInlineViewer');
  // Ensure an object URL exists when opening viewer: create one from Blob if necessary
  if(!file.previewUrl && file.previewBlob){
    try{ file.previewUrl = URL.createObjectURL(file.previewBlob); }catch(e){ file.previewUrl = null; }
  }
  // Decide which URL to use: prefer in-memory previewUrl if available
  const srcUrl = file.previewUrl || file.url;
  if(!viewer){
    viewer = document.createElement('div'); viewer.id='modalDocsInlineViewer';
    viewer.style.position='fixed'; viewer.style.inset='0';
    viewer.style.background='rgba(0,0,0,0.6)';
    viewer.style.display='flex';
    viewer.style.alignItems='center';
    viewer.style.justifyContent='center';
    viewer.style.zIndex='99999';

    const box = document.createElement('div');
    box.style.width='92%'; box.style.height='88%';
    box.style.background='#fff';
    box.style.borderRadius='10px';
    box.style.overflow='hidden';
    box.style.position='relative';

    const toolbar = document.createElement('div');
    toolbar.style.position='absolute';
    toolbar.style.top='12px';
    toolbar.style.right='12px';
    toolbar.style.zIndex='100001';
    const btn = document.createElement('button');
    btn.className='btn btn-secondary';
    btn.textContent='Cerrar';
    btn.addEventListener('click', ()=>{
      try{
        // Revoke object URL if we created one
        try{
          const iframe = viewer.querySelector('iframe');
          if(iframe && iframe._objectUrl){ URL.revokeObjectURL(iframe._objectUrl); }
        }catch(e){}
        viewer.remove(); const modal = document.getElementById('modalDocsPreview'); if(modal) modal.style.pointerEvents='';
      }catch(e){}
    });
    toolbar.appendChild(btn);

    const iframe = document.createElement('iframe');
    iframe.style.width='100%'; iframe.style.height='100%'; iframe.style.border='0';
    iframe._objectUrl = null;
    iframe._objectFile = null;
    try{
      const frag = 'toolbar=0&navpanes=0';
      iframe.src = (srcUrl.indexOf('#') === -1) ? (srcUrl + '#' + frag) : (srcUrl + '&' + frag);
    }catch(e){ iframe.src = srcUrl; }

    // If using a previewUrl (blob), store it on iframe for later revoke
    if(file.previewUrl){ iframe._objectUrl = file.previewUrl; iframe._objectFile = file; }

    box.appendChild(toolbar);
    box.appendChild(iframe);
    viewer.appendChild(box);
    document.body.appendChild(viewer);

    const modal = document.getElementById('modalDocsPreview'); if(modal) modal.style.pointerEvents='none';
  } else {
    const iframe = viewer.querySelector('iframe');
    if(iframe){
      // revoke previous objectUrl if any and clear the previous file's previewUrl
      try{
        if(iframe._objectUrl){
          try{ if(iframe._objectFile && iframe._objectFile.previewUrl === iframe._objectUrl){ iframe._objectFile.previewUrl = null; } }catch(e){}
          URL.revokeObjectURL(iframe._objectUrl);
          iframe._objectUrl = null;
          iframe._objectFile = null;
        }
      }catch(e){}

      // ensure current file has previewUrl if blob exists
      if(!file.previewUrl && file.previewBlob){
        try{ file.previewUrl = URL.createObjectURL(file.previewBlob); }catch(e){}
      }

      iframe.src = srcUrl;
      if(file.previewUrl){ iframe._objectUrl = file.previewUrl; iframe._objectFile = file; }
    }
    viewer.style.display='flex';
  }
}

function confirmarLecturaDocsPreview(){
  const err = document.getElementById('docsPreviewError');
  if(err){ err.style.display='none'; err.textContent=''; }

  const all = Array.from(document.querySelectorAll('#modalDocsPreview .doc-chk'));
  const checkedAll = all.length ? all.every(c => c.checked) : false;
  const terms = document.getElementById('chkAcceptTerms')?.checked;

  if(!checkedAll || !terms){
    if(err){
      err.style.display='block';
      err.textContent = 'Debes marcar todos los documentos como leídos y aceptar los términos para continuar.';
    }
    return;
  }

  // Marcar como leídos y avanzar a firmas
  showLoading('Validando lectura de documentos...');
  fetch(`/devices/asignacion/${_asignacionIdActual}/mark-documents-read`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'}
  })
  .then(r => r.json())
  .then(data => {
    hideLoading();
    if (data.success && data.estado === 12) {
      closeModal('modalDocsPreview');
      ensureIdentidades(_asignacionIdActual, () => abrirModalCapturaFirmas());
    } else {
      if(err){
        err.style.display='block';
        err.textContent = (data && (data.message || data.error)) ? (data.message || data.error) : 'Error marcando documentos como leídos.';
      } else {
        alert('Error marcando documentos como leídos');
      }
    }
  })
  .catch(e => {
    hideLoading();
    if(err){ err.style.display='block'; err.textContent = 'Error: ' + e.message; } else { alert('Error: ' + e.message); }
  });
}

function previsualizarDocumento(url, nombre) {
  document.getElementById('nombreDocumentoVisor').textContent = nombre;
  document.getElementById('visorPDF').style.display = 'block';
  cargarPDF(url, 'pdfCanvas', false);
}

function cerrarVisorPDF() {
  document.getElementById('visorPDF').style.display = 'none';
  if (_pdfDoc) {
    _pdfDoc.destroy();
    _pdfDoc = null;
  }
  _pdfPageNum = 1;
  _pdfScale = 1.5;
}

// ========================================================
// PASO B3: Proceder a Firmar (Estado 11 ? 12)
// ========================================================

function procederAFirmar() {
  if (!document.getElementById('chkHeLeidoDocumentos').checked) {
    document.getElementById('msgErrorLectura').style.display = 'block';
    return;
  }
  
  // Llamar endpoint para marcar documentos como leídos
  fetch(`/devices/asignacion/${_asignacionIdActual}/mark-documents-read`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'}
  })
  .then(r => r.json())
  .then(data => {
    if (data.success && data.estado === 12) {
      closeModal('modalLecturaDocumentos');
      abrirModalCapturaFirmas();
    } else {
      alert('Error marcando documentos como leídos');
    }
  })
  .catch(e => {
    alert('Error: ' + e.message);
  });
}

// ========================================================
// PASO B3: Captura de Firmas (Estado 12)
// ========================================================

function abrirModalCapturaFirmas() {
  // Inicializar canvas
  const canvasEmpleado = document.getElementById('canvasFirmaEmpleado');
  const canvasUsuario = document.getElementById('canvasFirmaUsuario');
  
  if (canvasEmpleado && canvasUsuario) {
    _canvasFirmaEmpleadoCtx = canvasEmpleado.getContext('2d');
    _canvasFirmaUsuarioCtx = canvasUsuario.getContext('2d');
    
    // Limpiar canvas
    _canvasFirmaEmpleadoCtx.clearRect(0, 0, canvasEmpleado.width, canvasEmpleado.height);
    _canvasFirmaUsuarioCtx.clearRect(0, 0, canvasUsuario.width, canvasUsuario.height);
    
    // Configurar fondo blanco
    _canvasFirmaEmpleadoCtx.fillStyle = '#ffffff';
    _canvasFirmaEmpleadoCtx.fillRect(0, 0, canvasEmpleado.width, canvasEmpleado.height);
    _canvasFirmaUsuarioCtx.fillStyle = '#ffffff';
    _canvasFirmaUsuarioCtx.fillRect(0, 0, canvasUsuario.width, canvasUsuario.height);
    
    // Setup de eventos de dibujo
    setupCanvasDrawing(canvasEmpleado, _canvasFirmaEmpleadoCtx, 'empleado');
    setupCanvasDrawing(canvasUsuario, _canvasFirmaUsuarioCtx, 'usuario');
  }
  
  _firmaEmpleadoVacia = true;
  _firmaUsuarioVacia = true;
  
  document.getElementById('capturaIdentidadEmpleado').value = '';
  document.getElementById('capturaIdentidadUsuario').value = '';
  document.getElementById('msgErrorFirmas').style.display = 'none';
  
  openModal('modalCapturaFirmas');
}

function setupCanvasDrawing(canvas, ctx, tipo) {
  let dibujando = false;
  let ultimoX = 0;
  let ultimoY = 0;
  
  const iniciarDibujo = (e) => {
    dibujando = true;
    const rect = canvas.getBoundingClientRect();
    ultimoX = (e.clientX || e.touches[0].clientX) - rect.left;
    ultimoY = (e.clientY || e.touches[0].clientY) - rect.top;
    
    if (tipo === 'empleado') _firmaEmpleadoVacia = false;
    if (tipo === 'usuario') _firmaUsuarioVacia = false;
  };
  
  const dibujar = (e) => {
    if (!dibujando) return;
    e.preventDefault();
    
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX || e.touches[0].clientX) - rect.left;
    const y = (e.clientY || e.touches[0].clientY) - rect.top;
    
    ctx.beginPath();
    ctx.moveTo(ultimoX, ultimoY);
    ctx.lineTo(x, y);
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.stroke();
    
    ultimoX = x;
    ultimoY = y;
  };
  
  const terminarDibujo = () => {
    dibujando = false;
  };
  
  canvas.addEventListener('mousedown', iniciarDibujo);
  canvas.addEventListener('mousemove', dibujar);
  canvas.addEventListener('mouseup', terminarDibujo);
  canvas.addEventListener('mouseleave', terminarDibujo);
  
  canvas.addEventListener('touchstart', iniciarDibujo);
  canvas.addEventListener('touchmove', dibujar);
  canvas.addEventListener('touchend', terminarDibujo);
}

function limpiarFirma(tipo) {
  if (tipo === 'empleado') {
    const canvas = document.getElementById('canvasFirmaEmpleado');
    _canvasFirmaEmpleadoCtx.clearRect(0, 0, canvas.width, canvas.height);
    _canvasFirmaEmpleadoCtx.fillStyle = '#ffffff';
    _canvasFirmaEmpleadoCtx.fillRect(0, 0, canvas.width, canvas.height);
    _firmaEmpleadoVacia = true;
  } else {
    const canvas = document.getElementById('canvasFirmaUsuario');
    _canvasFirmaUsuarioCtx.clearRect(0, 0, canvas.width, canvas.height);
    _canvasFirmaUsuarioCtx.fillStyle = '#ffffff';
    _canvasFirmaUsuarioCtx.fillRect(0, 0, canvas.width, canvas.height);
    _firmaUsuarioVacia = true;
  }
}

function validarIdentidadCaptura() {
  // función auxiliar para validar mientras el usuario escribe
}

function confirmarFirmas() {
  const identidadEmpleado = document.getElementById('capturaIdentidadEmpleado').value.trim();
  const identidadUsuario = document.getElementById('capturaIdentidadUsuario').value.trim();
  
  if (!identidadEmpleado || identidadEmpleado.length !== 13) {
    document.getElementById('msgErrorFirmas').textContent = 'Identidad del empleado invílida';
    document.getElementById('msgErrorFirmas').style.display = 'block';
    return;
  }
  
  if (!identidadUsuario || identidadUsuario.length !== 13) {
    document.getElementById('msgErrorFirmas').textContent = 'Identidad del usuario invílida';
    document.getElementById('msgErrorFirmas').style.display = 'block';
    return;
  }
  
  if (_firmaEmpleadoVacia || _firmaUsuarioVacia) {
    document.getElementById('msgErrorFirmas').textContent = 'Por favor complete ambas firmas';
    document.getElementById('msgErrorFirmas').style.display = 'block';
    return;
  }
  
  // Convertir canvas a base64
  const canvasEmpleado = document.getElementById('canvasFirmaEmpleado');
  const canvasUsuario = document.getElementById('canvasFirmaUsuario');
  
  const firmaEmpleadoB64 = canvasEmpleado.toDataURL('image/png');
  const firmaUsuarioB64 = canvasUsuario.toDataURL('image/png');
  
  const payload = {
    firma_empleado_b64: firmaEmpleadoB64,
    firma_usuario_b64: firmaUsuarioB64,
    identidad_empleado: identidadEmpleado,
    identidad_usuario: identidadUsuario,
    observaciones: window._observacionesDispositivo || {}  // Incluir observaciones si están disponibles
  };
  
  // Cerrar modal de captura y mostrar carga
  closeModal('modalCapturaFirmas');
  try { if (typeof setDocumentationProgress === 'function') setDocumentationProgress(3); } catch(e){}
  showLoading('Agregando las firmas ingresadas...');
  
  // Llamar endpoint para reemplazar SOLO las firmas
  fetch(`/devices/asignacion/${_asignacionIdActual}/apply-signatures`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  })
  .then(r => r.json())
  .then(data => {
    hideLoading();
    
    if (data.success && (data.estado === 13 || data.estado === 14)) {
      mostrarModalDocumentosFirmados(data.archivos || []);
    } else {
      alert('Error aplicando firmas: ' + (data.message || 'Error desconocido'));
    }
  })
  .catch(e => {
    hideLoading();
    alert('Error: ' + e.message);
  });
}

// ========================================================
// PASO B5: Documentos Firmados Finales (Estado 14)
// ========================================================

function mostrarModalDocumentosFirmados(archivos) {
  const lista = document.getElementById('listaDocumentosFirmados');
  lista.innerHTML = '';
  
  if (!archivos || archivos.length === 0) {
    lista.innerHTML = '<p style="color:#999; text-align:center;">No hay documentos disponibles</p>';
  } else {
    archivos.forEach((archivo, idx) => {
      const div = document.createElement('div');
      div.style.cssText = 'padding:12px; margin-bottom:8px; border:1px solid #28a745; border-radius:6px; background:#f0f8f5; display:flex; justify-content:space-between; align-items:center;';
      div.innerHTML = `
        <div>
          <span style="font-weight:600; color:#28a745;">${archivo.nombre || archivo}</span>
        </div>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-secondary btn-small" onclick="previsualizarDocumentoFirmado('${archivo.url || archivo}', '${archivo.nombre || archivo}')">
            Ver
          </button>
          <a href="${archivo.url || archivo}" download class="btn btn-secondary btn-small" style="text-decoration:none;">
            Descargar
          </a>
        </div>
      `;
      lista.appendChild(div);
    });
  }
  
  openModal('modalDocumentosFirmadosFinales');
}

function previsualizarDocumentoFirmado(url, nombre) {
  document.getElementById('nombreDocumentoVisorFirmado').textContent = nombre;
  document.getElementById('visorPDFFirmado').style.display = 'block';
  cargarPDF(url, 'pdfCanvasFirmado', true);
}

function cerrarVisorPDFFirmado() {
  document.getElementById('visorPDFFirmado').style.display = 'none';
  if (_pdfDocFirmado) {
    _pdfDocFirmado.destroy();
    _pdfDocFirmado = null;
  }
  _pdfPageNumFirmado = 1;
  _pdfScaleFirmado = 1.5;
}

function descargarTodosLosPDFs() {
  alert('función de descarga masiva en desarrollo');
}

function confirmarResguardoFinal() {
  // Usar modal de confirmación existente
  openGlobalDeleteModal(
    async () => {
      mostrarLoading('Resguardando documentación...');
      
      try {
        const response = await fetch(`/devices/asignacion/${_asignacionIdActual}/confirm-resguardo`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'}
        });
        
        const data = await response.json();
        ocultarLoading();
        
        if (data.success && data.estado === 90) {
          closeModal('modalDocumentosFirmadosFinales');
          
          // Actualizar tabla
          if (typeof reloadAsignacionesTable === 'function') {
            reloadAsignacionesTable();
          }
          
          // Mostrar modal de documentos en estado 90
          await mostrarModalDocumentosOneDrive(data.archivos || [], 90);
        } else {
          if (typeof openGlobalMessageModal === 'function') {
            openGlobalMessageModal('error', 'Error', data.message || 'Error desconocido');
          } else {
            alert('? Error: ' + (data.message || 'Error desconocido'));
          }
        }
      } catch (e) {
        ocultarLoading();
        if (typeof openGlobalMessageModal === 'function') {
          openGlobalMessageModal('error', 'Error', e.message);
        } else {
          alert('? Error: ' + e.message);
        }
      }
    },
    'Confirmar Resguardo Final',
    'íConfirmar resguardo final de documentación?\n\nEsta acciín completarí el proceso.'
  );
}

// PDF.js Viewer Functions
// ========================================================

async function cargarPDF(url, canvasId, esFirmado) {
  try {
    const pdfjsLib = window.pdfjsLib;
    if (!pdfjsLib) {
      console.error('PDF.js no está cargado');
      return;
    }
    
    const loadingTask = pdfjsLib.getDocument(url);
    const pdf = await loadingTask.promise;
    
    if (esFirmado) {
      _pdfDocFirmado = pdf;
      _pdfPageNumFirmado = 1;
      renderizarPagina(_pdfPageNumFirmado, canvasId, true);
    } else {
      _pdfDoc = pdf;
      _pdfPageNum = 1;
      renderizarPagina(_pdfPageNum, canvasId, false);
    }
  } catch (error) {
    console.error('Error cargando PDF:', error);
    alert('Error al cargar el PDF: ' + error.message);
  }
}

async function renderizarPagina(num, canvasId, esFirmado) {
  const pdfDoc = esFirmado ? _pdfDocFirmado : _pdfDoc;
  const scale = esFirmado ? _pdfScaleFirmado : _pdfScale;
  
  if (!pdfDoc) return;
  
  if (esFirmado) {
    _pdfPageRenderingFirmado = true;
  } else {
    _pdfPageRendering = true;
  }
  
  try {
    const page = await pdfDoc.getPage(num);
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext('2d');
    const viewport = page.getViewport({ scale: scale });
    
    canvas.height = viewport.height;
    canvas.width = viewport.width;
    
    const renderContext = {
      canvasContext: ctx,
      viewport: viewport
    };
    
    await page.render(renderContext).promise;
    
    // Actualizar info de pígina
    const infoId = esFirmado ? 'pdfPageInfoFirmado' : 'pdfPageInfo';
    const zoomId = esFirmado ? 'zoomLevelFirmado' : 'zoomLevel';
    document.getElementById(infoId).textContent = `Pígina ${num} de ${pdfDoc.numPages}`;
    document.getElementById(zoomId).textContent = Math.round(scale * 100) + '%';
    
  } catch (error) {
    console.error('Error renderizando pígina:', error);
  } finally {
    if (esFirmado) {
      _pdfPageRenderingFirmado = false;
    } else {
      _pdfPageRendering = false;
    }
  }
}

function navegarPDF(direccion) {
  if (!_pdfDoc || _pdfPageRendering) return;
  
  if (direccion === 'prev' && _pdfPageNum > 1) {
    _pdfPageNum--;
    renderizarPagina(_pdfPageNum, 'pdfCanvas', false);
  } else if (direccion === 'next' && _pdfPageNum < _pdfDoc.numPages) {
    _pdfPageNum++;
    renderizarPagina(_pdfPageNum, 'pdfCanvas', false);
  }
}

function navegarPDFFirmado(direccion) {
  if (!_pdfDocFirmado || _pdfPageRenderingFirmado) return;
  
  if (direccion === 'prev' && _pdfPageNumFirmado > 1) {
    _pdfPageNumFirmado--;
    renderizarPagina(_pdfPageNumFirmado, 'pdfCanvasFirmado', true);
  } else if (direccion === 'next' && _pdfPageNumFirmado < _pdfDocFirmado.numPages) {
    _pdfPageNumFirmado++;
    renderizarPagina(_pdfPageNumFirmado, 'pdfCanvasFirmado', true);
  }
}

function zoomPDF(direccion) {
  if (!_pdfDoc || _pdfPageRendering) return;
  
  if (direccion === 'in') {
    _pdfScale = Math.min(_pdfScale + 0.25, 3.0);
  } else {
    _pdfScale = Math.max(_pdfScale - 0.25, 0.5);
  }
  
  renderizarPagina(_pdfPageNum, 'pdfCanvas', false);
}

function zoomPDFFirmado(direccion) {
  if (!_pdfDocFirmado || _pdfPageRenderingFirmado) return;
  
  if (direccion === 'in') {
    _pdfScaleFirmado = Math.min(_pdfScaleFirmado + 0.25, 3.0);
  } else {
    _pdfScaleFirmado = Math.max(_pdfScaleFirmado - 0.25, 0.5);
  }
  
  renderizarPagina(_pdfPageNumFirmado, 'pdfCanvasFirmado', true);
}

// ============================================================================
// FLUJO FIRMA MANUAL - Descarga, Subida, Revisiín
// ============================================================================

// Variables para firma manual
let _archivosEsperados = [];
let _archivosSeleccionados = [];

// PASO C2a: Mostrar modal de descarga (con archivos recibidos del endpoint)
function mostrarModalDescargaManual(asignacionId, archivos) {
  _asignacionIdActual = asignacionId;
  
  // Si ya tenemos archivos del endpoint, mostrarlos directamente
    if (archivos && archivos.length > 0) {
    _archivosEsperados = archivos;
    renderizarListaDescarga(archivos);
    try { if (typeof setDocumentationProgress === 'function') setDocumentationProgress(2); } catch(e) {}
    openModal('modalDescargaFirmaManual');
  } else {
    // Fallback: Si no vienen archivos, cargarlos del endpoint
    abrirModalDescargaManual(asignacionId);
  }
}

// PASO C2b: Abrir modal de descarga de documentos (fallback - carga desde BD)
function abrirModalDescargaManual(asignacionId) {
  _asignacionIdActual = asignacionId;
  
  // Cargar documentos de OneDrive para descarga
  fetch(`/devices/asignacion/${asignacionId}/documentation-status`)
    .then(r => r.json())
    .then(data => {
      if (data.success && data.archivos && data.archivos.length > 0) {
        _archivosEsperados = data.archivos;
        renderizarListaDescarga(data.archivos);
        openModal('modalDescargaFirmaManual');
      } else {
        alert('No se encontraron documentos para descargar');
      }
    })
    .catch(err => {
      console.error('Error:', err);
      alert('Error al cargar documentos');
    });
}

function renderizarListaDescarga(documentos) {
  const container = document.getElementById('listaDocumentosDescarga');
  container.innerHTML = '';
  
  documentos.forEach((doc, idx) => {
    const div = document.createElement('div');
    div.style.cssText = 'padding:15px; border:1px solid #ddd; border-radius:6px; margin-bottom:10px; display:flex; align-items:center; justify-content:space-between; background:white;';
    div.innerHTML = `
      <div style="flex:1;">
        <div style="font-weight:600; color:#333; margin-bottom:4px;">${doc.nombre || 'Documento ' + (idx + 1)}</div>
        <div style="font-size:0.85em; color:#999;">${doc.tipo || ''}</div>
      </div>
      <button class="btn btn-primary" onclick="descargarDocumento('${doc.url}', '${doc.nombre}')">
        Descargar
      </button>
    `;
    container.appendChild(div);
  });
}

function descargarDocumento(url, nombre) {
  const a = document.createElement('a');
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function abrirModalSubidaFirmados() {
  closeModal('modalDescargaFirmaManual');
  _archivosSeleccionados = [];
  document.getElementById('listaArchivosSubida').innerHTML = '';
  document.getElementById('btnEnviarFirmados').disabled = true;
  document.getElementById('btnEnviarFirmados').style.opacity = '0.5';
  document.getElementById('erroresValidacionSubida').style.display = 'none';
  openModal('modalSubidaFirmados');
}

// Drag & Drop para subida
function handleDragOverSubida(e) {
  e.preventDefault();
  e.stopPropagation();
  e.currentTarget.style.borderColor = '#4CAF50';
  e.currentTarget.style.background = '#f1f8f4';
}

function handleDragLeaveSubida(e) {
  e.preventDefault();
  e.stopPropagation();
  e.currentTarget.style.borderColor = '#ddd';
  e.currentTarget.style.background = '#f9f9f9';
}

function handleDropSubida(e) {
  e.preventDefault();
  e.stopPropagation();
  e.currentTarget.style.borderColor = '#ddd';
  e.currentTarget.style.background = '#f9f9f9';
  
  const files = e.dataTransfer.files;
  handleFilesSubida(files);
}

function handleFilesSubida(files) {
  _archivosSeleccionados = Array.from(files).filter(f => f.type === 'application/pdf');
  
  if (_archivosSeleccionados.length === 0) {
    alert('Solo se aceptan archivos PDF');
    return;
  }
  
  validarYRenderizarArchivos();
}

function validarYRenderizarArchivos() {
  const errores = [];
  const container = document.getElementById('listaArchivosSubida');
  container.innerHTML = '';
  
  // Validar que los nombres coincidan exactamente con los esperados
  const nombresEsperados = _archivosEsperados.map(d => d.nombre);
  const nombresSeleccionados = _archivosSeleccionados.map(f => f.name);
  
  // Verificar que todos los archivos esperados están presentes
  nombresEsperados.forEach(nombre => {
    if (!nombresSeleccionados.includes(nombre)) {
      errores.push(`Falta el archivo: ${nombre}`);
    }
  });
  
  // Verificar que no haya archivos extra
  nombresSeleccionados.forEach(nombre => {
    if (!nombresEsperados.includes(nombre)) {
      errores.push(`Archivo no esperado: ${nombre}`);
    }
  });
  
  // Mostrar errores si hay
  if (errores.length > 0) {
    const divErrores = document.getElementById('erroresValidacionSubida');
    divErrores.innerHTML = '<strong>Errores de validación:</strong><ul style="margin:10px 0 0 0; padding-left:20px;">' +
      errores.map(e => `<li>${e}</li>`).join('') +
      '</ul>';
    divErrores.style.display = 'block';
    document.getElementById('btnEnviarFirmados').disabled = true;
    document.getElementById('btnEnviarFirmados').style.opacity = '0.5';
  } else {
    document.getElementById('erroresValidacionSubida').style.display = 'none';
    document.getElementById('btnEnviarFirmados').disabled = false;
    document.getElementById('btnEnviarFirmados').style.opacity = '1';
  }
  
  // Renderizar lista de archivos
  _archivosSeleccionados.forEach(file => {
    const div = document.createElement('div');
    const esValido = nombresEsperados.includes(file.name);
    div.style.cssText = `padding:12px; border:1px solid ${esValido ? '#4CAF50' : '#dc3545'}; border-radius:6px; margin-bottom:8px; display:flex; align-items:center; gap:12px; background:${esValido ? '#f1f8f4' : '#ffe6e6'};`;
    div.innerHTML = `
      <div style="font-size:1.5em;">${esValido ? 'Vílido' : 'Invílido'}</div>
      <div style="flex:1;">
        <div style="font-weight:600; color:#333;">${file.name}</div>
        <div style="font-size:0.85em; color:#666;">${(file.size / 1024).toFixed(1)} KB</div>
      </div>
      <button class="btn btn-sm btn-danger" onclick="removerArchivo('${file.name}')">Quitar</button>
    `;
    container.appendChild(div);
  });
}

function removerArchivo(nombre) {
  _archivosSeleccionados = _archivosSeleccionados.filter(f => f.name !== nombre);
  validarYRenderizarArchivos();
}

function enviarArchivosFirmados() {
  if (_archivosSeleccionados.length === 0) {
    alert('Seleccione archivos para subir');
    return;
  }
  
  const btn = document.getElementById('btnEnviarFirmados');
  btn.disabled = true;
  btn.textContent = 'Subiendo...';
  
  const formData = new FormData();
  formData.append('asignacion_id', _asignacionIdActual);
  _archivosSeleccionados.forEach(file => {
    formData.append('archivos', file);
  });
  
  fetch('/upload-signed-files', {
    method: 'POST',
    body: formData
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      alert('Archivos subidos exitosamente. Ahora deben ser revisados por un operador/administrador.');
      closeModal('modalSubidaFirmados');
      if (typeof reloadAsignacionesTable === 'function') reloadAsignacionesTable();
    } else {
      alert('Error: ' + (data.error || 'Error desconocido'));
    }
  })
  .catch(err => {
    console.error('Error:', err);
    alert('Error al subir archivos');
  })
  .finally(() => {
    btn.disabled = false;
    btn.textContent = 'Enviar para Revisiín';
  });
}

// PASO C4: Revisar documentos (para operador/admin)
function abrirModalRevisionDocumentos(asignacionId) {
  _asignacionIdActual = asignacionId;
  
  // Cargar documentos y info del usuario actual
  Promise.all([
    fetch(`/devices/asignacion/${asignacionId}/documentation-status`).then(r => r.json()),
    fetch('/current-user').then(r => r.json())  // Asumiendo que existe este endpoint
  ])
  .then(([dataDoc, dataUser]) => {
    if (dataDoc.success && dataDoc.archivos && dataDoc.archivos.length > 0) {
      document.getElementById('nombreRevisor').textContent = dataUser.nombre || dataUser.username || 'Usuario';
      renderizarListaRevision(dataDoc.archivos);
      document.getElementById('campoComentariosRechazo').style.display = 'none';
      document.getElementById('msgErrorRevision').style.display = 'none';
      openModal('modalRevisionDocumentos');
    } else {
      alert('No se encontraron documentos para revisar');
    }
  })
  .catch(err => {
    console.error('Error:', err);
    alert('Error al cargar documentos para revisiín');
  });
}

function renderizarListaRevision(documentos) {
  const container = document.getElementById('listaDocumentosRevision');
  container.innerHTML = '';
  
  documentos.forEach((doc, idx) => {
    const div = document.createElement('div');
    div.style.cssText = 'padding:15px; border:1px solid #ddd; border-radius:6px; margin-bottom:12px; background:white;';
    div.innerHTML = `
      <div style="display:flex; align-items:flex-start; gap:12px;">
        <input type="checkbox" id="checkDoc${idx}" class="checkbox-revision" onchange="verificarTodosCheckados()" 
               style="width:20px; height:20px; margin-top:4px;">
        <div style="flex:1;">
          <label for="checkDoc${idx}" style="font-weight:600; color:#333; cursor:pointer; margin-bottom:6px; display:block;">
            ${doc.nombre || 'Documento ' + (idx + 1)}
          </label>
          <div style="font-size:0.85em; color:#666; margin-bottom:10px;">${doc.tipo || ''}</div>
          <button class="btn btn-sm btn-primary" onclick="verDocumentoRevision('${doc.url}')">
            Ver Documento
          </button>
        </div>
      </div>
    `;
    container.appendChild(div);
  });
}

function verificarTodosCheckados() {
  const checkboxes = document.querySelectorAll('.checkbox-revision');
  const todosCheckados = Array.from(checkboxes).every(cb => cb.checked);
  const btn = document.getElementById('btnAprobarDocumentos');
  btn.disabled = !todosCheckados;
  btn.style.opacity = todosCheckados ? '1' : '0.5';
}

function verDocumentoRevision(url) {
  window.open(url, '_blank');
}

function mostrarCampoRechazo() {
  const campo = document.getElementById('campoComentariosRechazo');
  if (campo.style.display === 'none') {
    campo.style.display = 'block';
    document.getElementById('textareaComentariosRechazo').focus();
  } else {
    // Enviar rechazo
    enviarRevision('rechazar');
  }
}

function aprobarDocumentos() {
  // Usar modal de confirmación existente
  openGlobalDeleteModal(
    () => {
      enviarRevision('aprobar');
    },
    'Aprobar Documentos',
    '¿Está seguro de aprobar todos los documentos?\n\nEsto cambiará el estado a 24 (Listo para confirmación final).'
  );
}

function enviarRevision(accion) {
  const comentarios = document.getElementById('textareaComentariosRechazo').value.trim();
  
  if (accion === 'rechazar' && !comentarios) {
    document.getElementById('msgErrorRevision').textContent = 'Debe especificar comentarios al rechazar';
    document.getElementById('msgErrorRevision').style.display = 'block';
    return;
  }
  
  const btn = accion === 'aprobar' ? document.getElementById('btnAprobarDocumentos') : null;
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Procesando...';
  }
  
  fetch('/review-documents', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      asignacion_id: _asignacionIdActual,
      accion: accion,
      comentarios: comentarios || null
    })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      alert(accion === 'aprobar' ? 'Documentos aprobados exitosamente' : 'Documentos rechazados. El usuario debe corregir y volver a subir.');
      closeModal('modalRevisionDocumentos');
      if (typeof reloadAsignacionesTable === 'function') reloadAsignacionesTable();
    } else {
      alert('Error: ' + (data.error || 'Error desconocido'));
    }
  })
  .catch(err => {
    console.error('Error:', err);
    alert('Error al procesar revisiín');
  })
  .finally(() => {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '? Aprobar Todos';
    }
  });
}

// ============================================================================
// FIN NUEVO SISTEMA
// ============================================================================

// Variables globales para el visor PDF
let pdfDoc = null;
let currentPage = 1;
let pageRendering = false;
let pageNumPending = null;
let scale = 1.0;
let pdfRotation = 0; // Variable para la rotación en grados (0, 90, 180, 270)
let currentPDFUrl = null;
let currentPDFFileName = null;

/**
 * Abre la modal de OneDrive y carga la lista de PDFs
 */
async function openOneDriveModal(asignacionId, archivos, estado) {
  try {
    const modal = document.getElementById('modalDocumentosOneDrive');
    const container = document.getElementById('pdfCardsContainer');
    
    if (!modal || !container) {
      console.error('Elementos de modal no encontrados');
      return;
    }
    
    // Mostrar modal y usar el modal global de carga
    modal.classList.add('active');
    try { showLoading('Cargando documentos desde OneDrive...'); } catch(e) { /* fallback silently */ }
    
    // Llamar al endpoint para listar PDFs
    const response = await fetch('/devices/test/onedrive/list-pdfs', {
      method: 'GET',
      credentials: 'same-origin'
    });
    
    const data = await response.json();
    
    if (!data.success || !data.files || data.files.length === 0) {
      try { hideLoading(); } catch(e) {}
      container.innerHTML = `
        <div class="pdf-cards-empty">
          <svg fill="currentColor" viewBox="0 0 16 16">
            <path d="M14 14V4.5L9.5 0H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2zM9.5 3A1.5 1.5 0 0 0 11 4.5h2V14a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1h5.5v2z"/>
          </svg>
          <p><strong>No se encontraron documentos PDF</strong></p>
          <p>${data.message || 'La carpeta está vacía o no existe'}</p>
        </div>
      `;
    }

    // Ocultar global loader y renderizar las cards
    try { hideLoading(); } catch(e) {}
    renderPDFCards(data.files, container);
    
  } catch (error) {
    try { hideLoading(); } catch(e) {}
    try { openGlobalMessageModal('error', 'Error', error && error.message ? error.message : 'Error al cargar documentos'); } catch(e) { /* fallback */ }
    const container = document.getElementById('pdfCardsContainer');
    if (container) {
      container.innerHTML = `
        <div class="pdf-cards-empty">
          <p><strong>Error al cargar documentos</strong></p>
          <p>${error.message || 'Error desconocido'}</p>
        </div>
      `;
    }
  }
}

/**
 * Renderiza las cards de PDFs en el contenedor
 */
function renderPDFCards(files, container) {
  // Filtrar solo entradas nulas o sin URL descargable.
  // El backend ya controla qué archivos se deben mostrar según el estado.
  const filtered = (Array.isArray(files) ? files.slice() : []).filter(f => {
    if (!f) return false;
    const name = (f.name || f.nombre || '').toString();
    if (!name) return false;
    if (!f.url && !f.download_url && !f.downloadUrl) return false;
    return true;
  });

  container.innerHTML = '';

  filtered.forEach(file => {
    // Compute a display name using correlativo if available
    let displayName = file.name || file.nombre || '';
    try {
      const m = displayName.match(/(PRO-TI-CE-\d+-)([\d]{6})(.*)$/);
      if (m) {
        const corr = (window._correlativoActual && String(window._correlativoActual).padStart ? String(window._correlativoActual).padStart(6,'0') : window._correlativoActual) || m[2];
        displayName = m[1] + (corr || m[2]) + (m[3] || '');
      }
    } catch(e) { /* ignore */ }
    const card = document.createElement('div');
    card.className = 'pdf-card';
    // Usar URL directa de OneDrive si está disponible (más rápido), fallback a proxy
    const directUrl = file.download_url || file.downloadUrl || '';
    card.onclick = () => openPDFViewer(file.id, file.name, directUrl);
    
    const size = formatFileSize(file.size);
    
    card.innerHTML = `
      <div class="pdf-card-icon">
        <img src="/static/img/pdf.png" alt="PDF" style="width: 36px; height: 36px; object-fit: contain;">
      </div>
      <h4 class="pdf-card-title" title="${file.name}">${displayName}</h4>
      <div class="pdf-card-meta">
        <span class="pdf-card-size">${size}</span>
      </div>
    `;
    
    container.appendChild(card);
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="pdf-cards-empty">
        <p><strong>No se encontraron documentos disponibles en OneDrive</strong></p>
        <p>Si esperabas ver archivos aquí, por favor revisa que la sincronización con OneDrive haya finalizado.</p>
      </div>
    `;
  }

  // Ajustar tamaío de la modal segín nímero de cards: si solo 1, hacerla mís angosta
  try {
    const modalEl = document.querySelector('#modalDocumentosOneDrive .modal');
    const cardCount = container.children.length;
    if (modalEl) {
      if (cardCount === 1) {
        modalEl.style.maxWidth = '680px';
      } else if (cardCount <= 2) {
        modalEl.style.maxWidth = '820px';
      } else {
        modalEl.style.maxWidth = '';
      }
    }
  } catch(e) { console.warn('resize modal error', e); }
}

/**
 * Formatea el tamaío del archivo en bytes a formato legible
 */
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Abre el visor de PDF con PDF.js
 * @param {string} fileId - ID del archivo o nombre
 * @param {string} fileName - Nombre del archivo
 * @param {string} directDownloadUrl - URL directa de OneDrive (opcional, más rápido)
 */
async function openPDFViewer(fileId, fileName, directDownloadUrl) {
  try {
    currentPDFFileName = fileName;
    
    // Preferir URL directa de OneDrive si está disponible (es mucho más rápido)
    if (directDownloadUrl && directDownloadUrl.startsWith('https://')) {
      currentPDFUrl = directDownloadUrl;
    }
    // Fallback: usar endpoint proxy si fileId parece un nombre de archivo
    else if (fileId.includes('PRO-TI-CE')) {
      // Es un documento generado, usar endpoint proxy con asignacion_id
      currentPDFUrl = `/devices/asignacion/${_asignacionIdActual}/documento/${fileId}`;
    } else {
      // Es del Botón TEST, usar endpoint original
      currentPDFUrl = `/devices/test/onedrive/download-pdf/${fileId}`;
    }
    
    const modal = document.getElementById('modalPDFViewer');
    const title = document.getElementById('pdfViewerTitle');
    const loaderContainer = document.getElementById('pdfLoaderContainer');
    const canvas = document.getElementById('pdfViewerCanvas');
    
    if (!modal) {
      console.error('Modal de visor PDF no encontrado');
      return;
    }
    
    // Limpiar canvas y mostrar loader (usar modal global)
    canvas.width = 0;
    canvas.height = 0;
    try { showLoading('Cargando documento...'); } catch(e) {}
    scale = 1.0;
    updateZoomSlider(100);
    
    modal.classList.add('active');
    if (title) title.textContent = fileName;
    
    // Cargar PDF.js dinámamente si no está cargado
    if (typeof pdfjsLib === 'undefined') {
      await loadPDFjs();
    }
    
    // Cargar el PDF
    await loadPDF(currentPDFUrl);
    
  } catch (error) {
    try { hideLoading(); } catch(e) {}
    try { openGlobalMessageModal('error', 'Error', error && error.message ? error.message : 'Error al abrir el documento PDF'); } catch(e) {}
    closeModal('modalPDFViewer');
  }
}

/**
 * Carga PDF.js desde CDN
 */
function loadPDFjs() {
  return new Promise((resolve, reject) => {
    if (typeof pdfjsLib !== 'undefined') {
      resolve();
      return;
    }
    
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@5.4.530/build/pdf.min.mjs';
    script.type = 'module';
    script.onload = () => {
      // Configurar worker
      import('https://cdn.jsdelivr.net/npm/pdfjs-dist@5.4.530/build/pdf.min.mjs')
        .then(pdfjsModule => {
          window.pdfjsLib = pdfjsModule;
          pdfjsModule.GlobalWorkerOptions.workerSrc = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@5.4.530/build/pdf.worker.min.mjs';
          resolve();
        })
        .catch(reject);
    };
    script.onerror = () => reject(new Error('No se pudo cargar PDF.js'));
    document.head.appendChild(script);
  });
}

/**
 * Carga y renderiza el PDF
 */
async function loadPDF(url) {
  try {
    const loadingTask = pdfjsLib.getDocument(url);
    pdfDoc = await loadingTask.promise;
    currentPage = 1;
    pdfRotation = 0; // Resetear rotación cuando se carga un nuevo PDF
    
    // Ocultar loader global cuando el PDF cargue exitosamente
    try { hideLoading(); } catch(e) {}
    
    // Configurar slider dinámo segín tamaío de pígina y contenedor
    try {
      const firstPage = await pdfDoc.getPage(1);
      const vp = firstPage.getViewport({ scale: 1 });
      const viewerBody = document.getElementById('pdfViewerBody');
      const containerWidth = (viewerBody && viewerBody.clientWidth) ? viewerBody.clientWidth : window.innerWidth * 0.8;
      const scaleFit = containerWidth / vp.width;

      const fitPercent = Math.round(scaleFit * 100);
      const minPercent = Math.max(50, Math.min(fitPercent, 100));
      const maxPercent = Math.max(250, Math.round(Math.max(2.5, scaleFit * 2) * 100));

      const slider = document.getElementById('zoomSlider');
      if (slider) {
        slider.min = String(minPercent);
        slider.max = String(maxPercent);
        slider.step = '5';
        // keep initial value at 100% per user preference
        slider.value = '100';
      }
      updateZoomSlider(100);
    } catch (e) {
      // ignore slider dynamic setup failures
      console.warn('Could not setup dynamic slider ranges', e);
      updateZoomSlider(100);
    }

    // Renderizar primera pígina
    await renderPage(currentPage);
    
  } catch (error) {
    try { hideLoading(); } catch(e) {}
    try { openGlobalMessageModal('error', 'Error', error && error.message ? error.message : 'No se pudo cargar el documento PDF'); } catch(e) {}
    throw new Error('No se pudo cargar el documento PDF');
  }
}

/**
 * Renderiza una pígina del PDF en el canvas
 */
async function renderPage(num) {
  if (pageRendering) {
    pageNumPending = num;
    return;
  }
  
  pageRendering = true;
  
  try {
    const page = await pdfDoc.getPage(num);
    const canvas = document.getElementById('pdfViewerCanvas');
    const ctx = canvas.getContext('2d');
    
    // Aplicar zoom y rotación usando getViewport (PDF.js se encarga de todo)
    const viewport = page.getViewport({ scale: scale, rotation: pdfRotation });
    
    canvas.height = viewport.height;
    canvas.width = viewport.width;
    
    // Llenar con fondo blanco para evitar áreas sombreadas
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    const renderContext = {
      canvasContext: ctx,
      viewport: viewport
    };
    
    await page.render(renderContext).promise;
    
    pageRendering = false;
    
    if (pageNumPending !== null) {
      renderPage(pageNumPending);
      pageNumPending = null;
    }
    
  } catch (error) {
    console.error('Error renderizando pígina:', error);
    pageRendering = false;
  }
}

/**
 * Aumenta el zoom del PDF (míximo 200%)
 */
function zoomInPDF() {
  const zoomPercentage = Math.round(scale * 100);
  if (zoomPercentage < 200) {
    scale = Math.min(2.0, scale + 0.15);
    updateZoomSlider(Math.round(scale * 100));
    renderPage(currentPage);
  }
}

/**
 * Disminuye el zoom del PDF (mínimo 100%)
 */
function zoomOutPDF() {
  const zoomPercentage = Math.round(scale * 100);
  if (zoomPercentage > 100) {
    scale = Math.max(1.0, scale - 0.15);
    updateZoomSlider(Math.round(scale * 100));
    renderPage(currentPage);
  }
}

/**
 * Actualiza el zoom desde el slider
 */
function updateZoomFromSlider(percentage) {
  const value = parseInt(percentage);
  // Immediate apply when slider change is committed (fallback)
  scale = value / 100;
  updateZoomSlider(value);
  if (pdfDoc) {
    renderPage(currentPage);
  }
}

// Live input handler with requestAnimationFrame throttling
let _zoomRaf = null;
let _zoomPending = null;
function onZoomSliderInput(value) {
  const v = parseInt(value);
  _zoomPending = v;
  const apply = () => {
    _zoomRaf = null;
    if (_zoomPending === null) return;
    scale = _zoomPending / 100;
    updateZoomSlider(_zoomPending);
    if (pdfDoc) renderPage(currentPage);
    _zoomPending = null;
  };
  if (_zoomRaf) cancelAnimationFrame(_zoomRaf);
  _zoomRaf = requestAnimationFrame(apply);
}

// Fit-to-width button handler
async function fitToWidth() {
  try {
    if (!pdfDoc) return;
    const page = await pdfDoc.getPage(currentPage || 1);
    const vp = page.getViewport({ scale: 1 });
    const viewerBody = document.getElementById('pdfViewerBody');
    const containerWidth = (viewerBody && viewerBody.clientWidth) ? viewerBody.clientWidth : window.innerWidth * 0.8;
    const fitScale = containerWidth / vp.width;
    // compute percent and clamp to slider range
    const percent = Math.round(fitScale * 100);
    const slider = document.getElementById('zoomSlider');
    if (slider) {
      const min = parseInt(slider.min || '50');
      const max = parseInt(slider.max || '250');
      const clamped = Math.max(min, Math.min(max, percent));
      slider.value = clamped;
      onZoomSliderInput(clamped);
    } else {
      scale = fitScale;
      renderPage(currentPage);
      updateZoomSlider(Math.round(scale * 100));
    }
  } catch (e) {
    console.warn('fitToWidth failed', e);
  }
}

/**
 * Actualiza la posiciín del slider y el label de zoom
 */
function updateZoomSlider(percentage) {
  const slider = document.getElementById('zoomSlider');
  const label = document.getElementById('zoomLabel');
  if (slider) slider.value = percentage;
  if (label) label.textContent = percentage + '%';
}

/**
 * Rota el PDF a la izquierda (90 grados en sentido antihorario)
 */
function rotatePDFLeft() {
  if (!pdfDoc) return;
  pdfRotation = (pdfRotation - 90) % 360;
  if (pdfRotation < 0) pdfRotation += 360;
  renderPage(currentPage);
}

/**
 * Rota el PDF a la derecha (90 grados en sentido horario)
 */
function rotatePDFRight() {
  if (!pdfDoc) return;
  pdfRotation = (pdfRotation + 90) % 360;
  renderPage(currentPage);
}

/**
 * Descarga el PDF actual
 */
function downloadCurrentPDF() {
  if (!currentPDFUrl || !currentPDFFileName) {
    alert('No hay documento para descargar');
    return;
  }
  
  // Construir URL con nombre del archivo como parímetro
  const downloadUrl = currentPDFUrl + '?name=' + encodeURIComponent(currentPDFFileName);
  
  // Crear link y descargar
  const link = document.createElement('a');
  link.href = downloadUrl;
  link.download = currentPDFFileName.endsWith('.pdf') ? currentPDFFileName : currentPDFFileName + '.pdf';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/**
 * Imprime el PDF actualmente cargado en el visor.
 * Intenta descargar el PDF como blob, abrir una nueva ventana con el PDF embebido
 * y lanzar el diálogo de impresión automáticamente.
 */
async function printCurrentPDF() {
  if (!currentPDFUrl) {
    alert('No hay documento para imprimir');
    return;
  }

  try {
    // Intentar obtener el PDF como blob (usar mismas credenciales que la descarga)
    const resp = await fetch(currentPDFUrl, { credentials: 'same-origin' });
    if (!resp.ok) throw new Error('Error descargando el PDF: HTTP ' + resp.status);
    const blob = await resp.blob();

    const blobUrl = URL.createObjectURL(blob);

    // Abrir nueva ventana y escribir HTML que embebe el PDF y llama a print()
    const w = window.open('', '_blank');
    if (!w) {
      alert('No se pudo abrir la ventana de impresión. Revisa el bloqueador de popups.');
      URL.revokeObjectURL(blobUrl);
      return;
    }

    const title = (currentPDFFileName || 'Documento') .replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const html = `<!doctype html>
      <html>
        <head>
          <title>${title}</title>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <style>html,body{height:100%;margin:0}</style>
        </head>
        <body>
          <embed src="${blobUrl}" type="application/pdf" width="100%" height="100%" />
          <script>
            function doPrint(){
              try{ window.focus(); window.print(); }catch(e){/* ignore */}
            }
            window.onload = function(){ setTimeout(doPrint, 500); };
          <\/script>
        </body>
      </html>`;

    w.document.open();
    w.document.write(html);
    w.document.close();

    // Liberar blob URL luego de un tiempo
    setTimeout(() => URL.revokeObjectURL(blobUrl), 30000);

  } catch (e) {
    console.error('printCurrentPDF error', e);
    alert('No se pudo imprimir el documento: ' + (e && e.message ? e.message : e));
  }
}

// Formatea los títulos de las cards: separa prefijo (línea superior) y resto
function formatPdfCardTitles() {
  try {
    const container = document.getElementById('pdfCardsContainer');
    if (!container) return;

    const cards = Array.from(container.children || []);
    cards.forEach(card => {
      if (!card) return;

      // buscar el elemento que contiene el nombre original
      let titleEl = card.querySelector('.pdf-card-title') || card.querySelector('.card-title') || card.querySelector('h4') || card.querySelector('h3') || card.querySelector('.title') || card.querySelector('p');
      if (!titleEl) return;

      let raw = (titleEl.textContent || '').trim();
      if (!raw) return;

      // ya procesado?
      if (card.querySelector('.pdf-card-prefix')) return;

      // quitar sufijo .pdf si existe
      const withoutExt = raw.replace(/\.pdf$/i, '').trim();

      // dividir en prefijo (primer espacio) y resto
      const firstSpaceIdx = withoutExt.indexOf(' ');
      if (firstSpaceIdx === -1) {
        // nada que separar, dejar el texto sin extensiín
        titleEl.textContent = withoutExt;
        return;
      }

      const prefix = withoutExt.slice(0, firstSpaceIdx).trim();
      const rest = withoutExt.slice(firstSpaceIdx + 1).trim();

      // Validar que el "prefix" tiene formato tipo PRO-XXX-... o es lo suficientemente largo
      const looksLikePrefix = /[A-Z0-9]+(-[A-Z0-9]+)+/.test(prefix) || prefix.length >= 8;
      if (!looksLikePrefix) {
        // no parece prefijo; dejar como título sin extensiín
        titleEl.textContent = withoutExt;
        return;
      }

      // Crear elementos separados
      const prefixEl = document.createElement('div');
      prefixEl.className = 'pdf-card-prefix';
      prefixEl.textContent = prefix;

      const titleTextEl = document.createElement('div');
      titleTextEl.className = 'pdf-card-title';
      titleTextEl.textContent = rest;

      // Reemplazar en el DOM: sustituir el titleEl por prefixEl + titleTextEl
      try {
        titleEl.parentNode.replaceChild(prefixEl, titleEl);
        prefixEl.insertAdjacentElement('afterend', titleTextEl);
      } catch (e) {
        // fallback: setear texto simple
        titleEl.textContent = withoutExt;
      }
    });
  } catch (e) {
    console.warn('formatPdfCardTitles failed', e);
  }
}

// Observar inserciones en el contenedor de cards y formatear automíticamente
(function attachPdfCardsObserver(){
  try {
    const container = document.getElementById('pdfCardsContainer');
    if (!container) return;

    const observer = new MutationObserver((mutations) => {
      // pequeía espera para que el contenido interno quede establecido
      setTimeout(formatPdfCardTitles, 50);
    });

    observer.observe(container, { childList: true, subtree: true });

    // formatear inicialmente por si ya hay elementos
    setTimeout(formatPdfCardTitles, 60);
  } catch (e) { console.warn('attachPdfCardsObserver failed', e); }
})();

/* ========================================================================= */

// Variables globales para el modal de pasaporte
let pasaporteModalCallback = null;

// Formatear input de identidad automíticamente
document.getElementById('pasaporteInput').addEventListener('input', function(e) {
  let value = e.target.value;
  
  // Remover todo excepto dígitos
  let digitsOnly = value.replace(/\D/g, '');
  
  // Limitar a 13 dígitos
  if (digitsOnly.length > 13) {
    digitsOnly = digitsOnly.substring(0, 13);
  }
  
  // Formatear: xxxx-xxxx-xxxxx
  let formatted = '';
  if (digitsOnly.length > 0) {
    formatted = digitsOnly.substring(0, 4);
    if (digitsOnly.length > 4) {
      formatted += '-' + digitsOnly.substring(4, 8);
    }
    if (digitsOnly.length > 8) {
      formatted += '-' + digitsOnly.substring(8, 13);
    }
  }
  
  e.target.value = formatted;
});

// Event listener para el Botón Guardar
document.getElementById('pasaporteGuardar').addEventListener('click', async function() {
  const pasaporte = document.getElementById('pasaporteInput').value.trim();
  const errorDiv = document.getElementById('pasaporteError');
  
  // Validar
  if (!pasaporte || pasaporte.length !== 15 || !pasaporte.match(/^\d{4}-\d{4}-\d{5}$/)) {
    errorDiv.textContent = 'Debe ingresar 13 dígitos';
    errorDiv.style.display = 'block';
    return;
  }
  
  // Guardar en variable temporal
  window._pasaporteTemporal = pasaporte;

  // Si vinimos desde el flujo de apply-signatures, reintentar con pasaporte temporal
  if (window._pasaporteAfterApplySignatures && window._pasaporteData && window._pasaporteData.empleadoId) {
    closeModal('pasaporteModal');
    window._pasaporteAfterApplySignatures = false;

    // Reintentar apply-signatures con pasaporte temporal en el payload
    const aplicarPayload = window._applySignPayload || null;
    const asignacionIdToUse = window._asignacionIdParaDocumentos || window._asignacionIdActual || _asignacionIdActual;
    
    if (!aplicarPayload) {
      alert('ERROR TÉCNICO: No se encontró el payload guardado de apply-signatures. Por favor reporta este error.');
      return;
    }
    
    if (!asignacionIdToUse) {
      alert('ERROR TÉCNICO: No se encontró el ID de asignación. Por favor reporta este error.');
      return;
    }
    
    if (aplicarPayload && asignacionIdToUse) {
      // Agregar pasaporte_temporal al payload
      aplicarPayload.pasaporte_temporal = pasaporte;
      
      try {
        if (typeof showLoading === 'function') showLoading('Agregando datos a los documentos...');
        const resp = await fetch(`/devices/asignacion/${asignacionIdToUse}/apply-signatures`, {
          method: 'POST',
          credentials: 'same-origin',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(aplicarPayload)
        });
        const respJson = await resp.json().catch(() => null);
        
        if (!resp.ok || !respJson || !respJson.success) {
          throw new Error((respJson && respJson.message) || `HTTP ${resp.status}`);
        }
        // Éxito: mostrar documentos con firmas
        if (respJson.archivos) {
          mostrarModalDocumentosOneDrive(respJson.archivos, 13);
        }
      } catch (err) {
        if (typeof openGlobalMessageModal === 'function') openGlobalMessageModal('error', 'Error', 'No se pudo aplicar las firmas: ' + err.message);
        else alert('Error: ' + err.message);
      } finally {
        if (typeof hideLoading === 'function') hideLoading();
        if (typeof closeGlobalMessageModal === 'function') closeGlobalMessageModal();
      }
    }

    return;
  }

  // Cerrar modal y reintentar generaciín con el payload guardado (flujo original)
  closeModal('pasaporteModal');
  const payload = window._generarDocPayload;
  if (payload) {
    llamarGenerarDocumentacion(payload);
  }
});

document.getElementById('pasaporteInput').addEventListener('keypress', function(e) {
  if (e.key === 'Enter') document.getElementById('pasaporteGuardar').click();
});
