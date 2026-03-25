/* ============================================================ */
/* dispositivos.js - Scripts extraídos de dispositivos.html    */
/* ============================================================ */

let pendingDeleteId = null;
let modalZIndex = 12000;

// Helper function para mostrar mensajes de error/éxito
function showModalMessage(message, type = 'error') {
  const title = type === 'error' ? 'Error' : type === 'success' ? 'Éxito' : 'Información';
  openGlobalMessageModal(type, title, message);
}

// Page-scoped modal helpers that also clear IP validation state to prevent persistent native bubbles
function closeModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) {
    el.classList.remove('active');
    // Restaurar z-index cuando se cierra el modal
    el.style.zIndex = '';
  }
  try {
    const newIp = document.querySelector('input[name="ip_asignada"]');
    if (newIp) { try { newIp.setCustomValidity(''); try { newIp.reportValidity(); } catch(e){} } catch(e){}; const niErr = document.getElementById('newIpError'); if (niErr) { niErr.textContent=''; niErr.style.display='none'; } }
    const editIp = document.getElementById('editDeviceIp');
    if (editIp) { try { editIp.setCustomValidity(''); try { editIp.reportValidity(); } catch(e){} } catch(e){}; const eiErr = document.getElementById('editIpError'); if (eiErr) { eiErr.textContent=''; eiErr.style.display='none'; } }
  } catch(e) { console.warn('clear validation state failed', e); }
}

function openModal(modalId, preserveScroll=false) {
  // If preserveScroll is requested, capture and restore page coordinates to
  // avoid browser auto-scroll caused by native validation reporting.
  const shouldPreserve = !!preserveScroll;
  const el = document.getElementById(modalId);

  let prevScrollX = 0, prevScrollY = 0;
  if (shouldPreserve) {
    prevScrollX = (typeof window.scrollX !== 'undefined') ? window.scrollX : window.pageXOffset || 0;
    prevScrollY = (typeof window.scrollY !== 'undefined') ? window.scrollY : window.pageYOffset || 0;
  }

  if (el) {
    el.classList.add('active');
    // Incrementar z-index para asegurar que este modal aparezca encima
    modalZIndex += 2;
    el.style.zIndex = modalZIndex;
  }
  try {
    const newIp = document.querySelector('input[name="ip_asignada"]'); if (newIp) try { newIp.setCustomValidity(''); try { newIp.reportValidity(); } catch(e){} } catch(e){}
    const editIp = document.getElementById('editDeviceIp'); if (editIp) try { editIp.setCustomValidity(''); try { editIp.reportValidity(); } catch(e){} } catch(e){}
  } catch(e) { console.warn('clear validation on open failed', e); }

  // If preserving, restore previous coords; otherwise (default) scroll page to top
  try {
    if (shouldPreserve) {
      window.scrollTo(prevScrollX, prevScrollY);
      setTimeout(() => { try { window.scrollTo(prevScrollX, prevScrollY); } catch(e){} }, 50);
    } else {
      try { window.scrollTo(0, 0); } catch(e) {}
    }
  } catch(e) {}
}

// Define estado maps for status display
const ESTADO_MAP = {
  '0': 'Sin asignar',
  0: 'Sin asignar',
  '1': 'Asignado',
  1: 'Asignado',
  '2': 'En reparación',
  2: 'En reparación',
  '3': 'Eliminado',
  3: 'Eliminado'
};

const ESTADO_COLOR_MAP = {
  '0': 'danger',
  0: 'danger',
  '1': 'success',
  1: 'success',
  '2': 'warning',
  2: 'warning',
  '3': 'secondary',
  3: 'secondary'
};

// Estado 4: Uso general (UI label + color)
ESTADO_MAP['4'] = 'Uso general';
ESTADO_MAP[4] = 'Uso general';
ESTADO_COLOR_MAP['4'] = 'primary';
ESTADO_COLOR_MAP[4] = 'primary';

// Toggle verbose dev logs (set true to enable console logs used for debugging)
window.__DEV_LOGS = false;

function getEstadoText(estado) {
  if (!estado && estado !== 0) return 'Sin asignar';
  return ESTADO_MAP && ESTADO_MAP[estado] ? ESTADO_MAP[estado] : String(estado) || 'Desconocido';
}

function getEstadoColor(estado) {
  if (!estado && estado !== 0) return 'danger';
  return ESTADO_COLOR_MAP && ESTADO_COLOR_MAP[estado] ? ESTADO_COLOR_MAP[estado] : 'secondary';
}

// Update a single device row in-place after partial changes
async function updateDeviceRow(deviceId) {
  if (!deviceId) return;
  if (window.__DEV_LOGS) console.log('[updateDeviceRow] Starting for deviceId:', deviceId);
  try {
    const r = await fetch(`/devices/${deviceId}`);
    if (!r.ok) { console.warn('[updateDeviceRow] Fetch failed, status:', r.status); return; }
    const d = await r.json();
    if (window.__DEV_LOGS) console.log('[updateDeviceRow] Fetched device data:', d);
    // Find row by data-device-id attribute
    const targetRow = document.querySelector(`#devicesTable tbody tr[data-device-id="${deviceId}"]`);
    if (!targetRow) { console.warn('[updateDeviceRow] Row not found for deviceId:', deviceId); return; }
    if (window.__DEV_LOGS) console.log('[updateDeviceRow] Found target row, updating cells');
    // update columns matching the table layout (must match <thead> order)
    const statusColor = getEstadoColor(d.estado);
    // expected cells: 0:tipo,1:identificador,2:numero_serie,3:modelo,4:marca,5:estado,6:ip,7:actions
    const cells = targetRow.children;
    if (cells.length >= 8) {
      cells[0].textContent = d.categoria || '';
      cells[1].textContent = d.identificador || '';
      cells[2].innerHTML = `<code>${d.numero_serie || ''}</code>`;
      cells[3].textContent = d.nombre_modelo || '';
      cells[4].textContent = d.nombre_marca || '';
      cells[5].innerHTML = `<span class="text-${statusColor}">${getEstadoText(d.estado)}</span>`;
      cells[6].textContent = d.ip_asignada || '';
      if (window.__DEV_LOGS) console.log('[updateDeviceRow] Row updated successfully. New estado:', d.estado, 'Color:', statusColor);
    } else {
      console.warn('[updateDeviceRow] Not enough cells:', cells.length);
    }
  } catch (e) {
    console.error('[updateDeviceRow] Error:', e);
  }
}

// ============================================
// PRINTER SCANNING
// ============================================
// `scanPrinters()` removed — use the sidebar "Revisar" flow (`revisarImpresoras()`) for scanning.

function openDeleteDeviceModal(deviceId, sn, marca, modelo, tipo) {
  pendingDeleteId = deviceId;
  document.getElementById('confirmDeleteSN').textContent = sn || '-';
  document.getElementById('confirmDeleteMarca').textContent = marca || '-';
  document.getElementById('confirmDeleteModelo').textContent = modelo || '-';
  document.getElementById('confirmDeleteTipo').textContent = tipo || '-';
  document.getElementById('confirmDeleteReason').value = '';
  
  // Limpiar mensaje de error previo
  const errorEl = document.getElementById('confirmDeleteError');
  if (errorEl) {
    errorEl.style.display = 'none';
    errorEl.textContent = '';
  }
  
  openModal('modalConfirmDelete', true);
}

async function confirmDeleteDevice() {
  if (!pendingDeleteId) return;
  
  const reason = document.getElementById('confirmDeleteReason').value?.trim() || '';
  const errorEl = document.getElementById('confirmDeleteError');
  
  // Validate that reason is provided
  if (!reason) {
    if (errorEl) {
      errorEl.textContent = 'El motivo de baja es requerido';
      errorEl.style.display = 'block';
      errorEl.style.opacity = '1';
      // Auto-hide after 3 seconds
      setTimeout(() => {
        if (errorEl) {
          errorEl.style.opacity = '0';
          setTimeout(() => {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
            errorEl.style.opacity = '1';
          }, 1000);
        }
      }, 3000);
    }
    return; // Salir sin deshabilitar el botón para permitir reintento
  }
  
  const btn = document.getElementById('btnConfirmDelete');
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = 'Eliminando...';
  
  try {
    const resp = await fetch(`/devices/${pendingDeleteId}`, {
      method: 'DELETE',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ motivo_baja: reason })
    });
    const data = await resp.json().catch(() => ({}));
    if (resp.ok && data.success) {
      // Close modal and show success message
      closeModal('modalConfirmDelete');
      if (typeof reloadDevicesTable === 'function') await reloadDevicesTable();
      openGlobalSuccessModal(data.message || 'Dispositivo eliminado exitosamente');
    } else {
      // Show error in modal
      const errMsg = data.message || 'No se pudo eliminar el dispositivo';
      if (errorEl) {
        errorEl.textContent = errMsg;
        errorEl.style.display = 'block';
        errorEl.style.opacity = '1';
        // Auto-hide after 3 seconds
        setTimeout(() => {
          if (errorEl) {
            errorEl.style.opacity = '0';
            setTimeout(() => {
              errorEl.style.display = 'none';
              errorEl.textContent = '';
              errorEl.style.opacity = '1';
            }, 1000);
          }
        }, 3000);
      } else {
        openGlobalMessageModal('error', 'Error', errMsg);
      }
    }
  } catch (err) {
    console.error('Error deleting device', err);
    const errMsg = 'Error al eliminar el dispositivo';
    if (errorEl) {
      errorEl.textContent = errMsg;
      errorEl.style.display = 'block';
      errorEl.style.opacity = '1';
      // Auto-hide after 3 seconds
      setTimeout(() => {
        if (errorEl) {
          errorEl.style.opacity = '0';
          setTimeout(() => {
            errorEl.style.display = 'none';
            errorEl.textContent = '';
            errorEl.style.opacity = '1';
          }, 1000);
        }
      }, 3000);
    } else {
      openGlobalMessageModal('error', 'Error', errMsg);
    }
  } finally {
    btn.disabled = false;
    btn.textContent = 'Eliminar';
    pendingDeleteId = null;
  }
}

document.getElementById('btnConfirmDelete')?.addEventListener('click', confirmDeleteDevice);
// Validate new device fecha_ob before submit
document.getElementById('formNewDevice')?.addEventListener('submit', function(e){
  e.preventDefault(); // Always prevent default form submission
  const el = document.getElementById('newDeviceFechaObtencion');
  if (!el) return;
  const v = el.value;
  if (!v) return;
  // Use string comparison to avoid timezone issues
  const today = new Date();
  const todayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
  if (v > todayStr) {
    openModal('modalFechaFutura');
    return;
  }
});

// Bind the local devices page search to the shared global search/filter logic
document.addEventListener('DOMContentLoaded', () => {
  // Wizard: Abrir modal de nuevo dispositivo si venimos de wizard
  if (localStorage.getItem('wizardOpenNewDevice') === 'true') {
    localStorage.removeItem('wizardOpenNewDevice');
    setTimeout(() => {
      if (typeof openNewDeviceModal === 'function') {
        openNewDeviceModal();
      }
    }, 300);
  }
  
  try {
    const localSearch = document.getElementById('devicesPageSearch');
    if (localSearch && !localSearch._bound) {
      localSearch.addEventListener('input', (e) => {
        const v = (localSearch.value || '').trim();
        try { if (typeof applyGlobalTableSearchFilter === 'function') applyGlobalTableSearchFilter(v); } catch(e) {}
      });
      localSearch._bound = true;
    }
  } catch(e) { /* ignore */ }
  // If the page was opened with ?open_edit=<id>, open the edit modal for that device
  try {
    const params = new URLSearchParams(window.location.search);
    const openEdit = params.get('open_edit');
    if (openEdit && typeof openEditDeviceModal === 'function') {
      // try to parse numeric id
      const id = parseInt(openEdit, 10);
      if (!Number.isNaN(id)) {
        // slight delay to allow DOM to finish initializing
        setTimeout(() => openEditDeviceModal(id), 120);
      }
    }
  } catch (e) { /* ignore */ }
});

/* ---- */

// Docs preview modal logic
async function openDocsPreviewModal(employeeCode){
  try{
    // default params
    const year = 2026; const month = 1; const code = employeeCode || 'P-EM-000125';
    const grid = document.getElementById('docsPreviewGrid');
    grid.innerHTML = '<div class="loading">Buscando archivos...</div>';
    // open modal
    openModal('modalDocsPreview', true);
    // fetch list
    const resp = await fetch(`/documents/list/${year}/${month}/${encodeURIComponent(code)}`);
    if(!resp.ok){ grid.innerHTML = '<div class="loading">No se pudo obtener la lista de documentos.</div>'; return; }
    const j = await resp.json().catch(()=>({success:false, files:[]}));
    const files = (j && j.success) ? (j.files || []) : [];
    if(!files.length){ grid.innerHTML = '<div class="loading">No hay PDFs en la carpeta indicada.</div>'; return; }
    grid.innerHTML = '';
    files.forEach((f, idx)=>{
      const c = document.createElement('div'); c.className='docs-card';
      const b = document.createElement('div'); b.className='badge';
      const img = document.createElement('img'); img.className = 'pdf-icon'; img.src = '/static/img/pdf.png'; img.width = 45; img.height = 45; img.alt='PDF';
      b.appendChild(img);
      const label = document.createElement('div'); label.className='label'; label.textContent = f.name;
      const wrap = document.createElement('div'); wrap.className='chkwrap';
      const cb = document.createElement('input'); cb.type='checkbox'; cb.className='doc-chk'; cb.dataset.file = f.name; cb.id = 'docchk_'+idx;
      cb.addEventListener('change', updateConfirmState);
      wrap.appendChild(cb);
      c.appendChild(b); c.appendChild(label); c.appendChild(wrap);
      // click to open in new modal viewer window inside modal (reuse viewer area if exists)
      c.addEventListener('click', (ev)=>{
        // prevent checkbox toggle when clicking the checkbox
        if(ev.target && ev.target.tagName === 'INPUT') return;
        // open pdf in a centered viewer modal overlay
        openInModalViewer(f);
      });
      grid.appendChild(c);
    });
    // wire terms checkbox
    document.getElementById('chkAcceptTerms').checked = false;
    document.getElementById('chkAcceptTerms').removeEventListener('change', updateConfirmState);
    document.getElementById('chkAcceptTerms').addEventListener('change', updateConfirmState);
    updateConfirmState();
  }catch(e){
    console.error('openDocsPreviewModal', e);
    const grid = document.getElementById('docsPreviewGrid'); if(grid) grid.innerHTML = '<div class="loading">Error cargando documentos.</div>';
  }
}

function updateConfirmState(){
  const all = Array.from(document.querySelectorAll('.doc-chk'));
  const checkedAll = all.length ? all.every(c => c.checked) : false;
  const terms = document.getElementById('chkAcceptTerms')?.checked;
  const btn = document.getElementById('btnConfirmDocs');
  if(btn) btn.disabled = !(checkedAll && terms);
}

function openInModalViewer(file){
  // create a simple overlay viewer inside the docs modal
  // if already exists, replace iframe src
  let viewer = document.getElementById('modalDocsInlineViewer');
  if(!viewer){
    viewer = document.createElement('div'); viewer.id = 'modalDocsInlineViewer';
    viewer.style.position='fixed'; viewer.style.inset='0'; viewer.style.background='rgba(0,0,0,0.6)'; viewer.style.display='flex'; viewer.style.alignItems='center'; viewer.style.justifyContent='center';
    // Ensure the viewer overlays any existing modal by using a very large z-index
    viewer.style.zIndex='99999';
    const box = document.createElement('div'); box.style.width='90%'; box.style.height='86%'; box.style.background='#fff'; box.style.borderRadius='8px'; box.style.overflow='hidden';
    // Box should be above the overlay
    box.style.zIndex = '100000';
    const toolbar = document.createElement('div'); toolbar.style.position='absolute'; toolbar.style.top='18px'; toolbar.style.right='18px'; toolbar.style.zIndex='100001';
    const btn = document.createElement('button'); btn.className='btn'; btn.textContent='Cerrar'; btn.addEventListener('click', ()=>{ try{ viewer.remove();
        // restore modal pointer events (in case we disabled them)
        const modal = document.getElementById('modalDocsPreview'); if(modal) { modal.style.pointerEvents = ''; }
      }catch(e){} });
    toolbar.appendChild(btn);
    const iframe = document.createElement('iframe'); iframe.style.width='100%'; iframe.style.height='100%'; iframe.style.border='0';
    // Try to request the PDF without the viewer sidebar (many viewers support fragment params)
    try{
      const frag = 'toolbar=0&navpanes=0';
      iframe.src = (file.url.indexOf('#') === -1) ? (file.url + '#' + frag) : (file.url + '&' + frag);
    }catch(e){ iframe.src = file.url; }
    box.appendChild(toolbar); box.appendChild(iframe);
    viewer.appendChild(box);
    // append to body so it sits above other positioned elements
    document.body.appendChild(viewer);
    // prevent the underlying modal from intercepting pointer events while viewer is visible
    const modal = document.getElementById('modalDocsPreview'); if(modal) { modal.style.pointerEvents = 'none'; }
  } else {
    const iframe = viewer.querySelector('iframe'); if(iframe) iframe.src = file.url;
    viewer.style.display = 'flex';
  }
}

document.getElementById('btnConfirmDocs')?.addEventListener('click', async function(){
  // simple confirmation action: close modal and show success
  const btn = this; btn.disabled = true; btn.textContent = 'Confirmando...';
  try{
    // Here you could POST to server to register the review; for demo just show success
    closeModal('modalDocsPreview');
    openGlobalSuccessModal('Lectura confirmada. Gracias.');
  }catch(e){ console.error(e); }
  finally{ btn.disabled = false; btn.textContent = 'Confirmar lectura'; }
});

/* ---- */

// Handlers for IP conflict modal
document.getElementById('btnIpKeep')?.addEventListener('click', () => {
  closeModal('modalIpConflict');
  // If pending new device, show inline error in new IP field
  if (window.__pendingNewDeviceForm) {
    const ipInput = document.querySelector('input[name="ip_asignada"]');
    // Do NOT clear the new-device IP input; show HTML5 validation bubble and inline message
    if (ipInput) {
      try {
        ipInput.setCustomValidity('Ingrese una direccion IP valida');
        ipInput.reportValidity();
      } catch (e) { console.warn('reportValidity failed', e); }
    }
    // Do not show inline error; rely on native HTML5 validation bubble only
    window.__pendingNewDeviceForm = null;
    window.__pendingNewDeviceConflictOwner = null;
  }
  // If pending edit, set inline error and show native validation bubble but do NOT clear the input
  if (window.__pendingEditDevicePayload) {
    const editIpInput = document.getElementById('editDeviceIp');
    // Show HTML5 validation bubble
    if (editIpInput) {
      try {
        editIpInput.setCustomValidity('Ingrese una direccion IP valida');
        editIpInput.reportValidity();
      } catch (e) {
        // reportValidity may not be supported in some environments; fall back to inline message
        console.warn('reportValidity failed', e);
      }
    }
    // Do not show inline error; rely on native HTML5 validation bubble only
    window.__pendingEditDevicePayload = null;
    window.__pendingEditDeviceConflictOwner = null;
  }
});

document.getElementById('btnIpReplace')?.addEventListener('click', async () => {
  // Determine owner device id from pending objects
  const owner = window.__pendingNewDeviceConflictOwner || window.__pendingEditDeviceConflictOwner;
  if (!owner || !owner.id_dispositivo) {
    showModalMessage('No se encontró el dispositivo propietario de la IP', 'error');
    return;
  }
  try {
    const resp = await fetch('/devices/clear-ip', { method: 'POST', headers: {'Content-Type':'application/json'}, credentials: 'same-origin', body: JSON.stringify({ device_id: owner.id_dispositivo }) });
    const j = await resp.json().catch(()=>({}));
    if (!(resp.ok && j.success)) {
      showModalMessage(j.message || 'No se pudo liberar la IP', 'error');
      return;
    }
    // If clearing succeeded, continue with pending operation
    closeModal('modalIpConflict');
    if (window.__pendingNewDeviceForm) {
      // Clear any custom validity / inline error on the new IP input before submitting
      const newIpInput = document.querySelector('input[name="ip_asignada"]');
      if (newIpInput) {
        try { newIpInput.setCustomValidity(''); try { newIpInput.reportValidity(); } catch(e){} } catch(e){}
        const el = document.getElementById('newIpError'); if (el) { el.textContent = ''; el.style.display = 'none'; }
      }
      const formData = window.__pendingNewDeviceForm;
      try {
        const r = await fetch('/devices/new', { method: 'POST', body: formData, credentials: 'same-origin' });
        if (r.ok) {
          const data = await r.json().catch(()=>({}));
          
          // Wizard: Si venimos de wizard, actualizar estado y redirigir a planes
          const wizardState = localStorage.getItem('wizardState');
          if (wizardState) {
            try {
              const state = JSON.parse(wizardState);
              if (state.active && state.step === 1 && data.id_dispositivo) {
                state.deviceId = data.id_dispositivo;
                state.step = 2;
                localStorage.setItem('wizardState', JSON.stringify(state));
                
                closeModal('modalNewDevice');
                document.getElementById('formNewDevice').reset();
                
                // Redirigir a página de planes con flag
                localStorage.setItem('wizardOpenNewPlan', 'true');
                window.location.href = '/devices/planes';
                return;
              }
            } catch(e) { console.error('Error wizard:', e); }
          }
          
          closeModal('modalNewDevice');
          document.getElementById('formNewDevice').reset();
          if (typeof reloadDevicesTable === 'function') await reloadDevicesTable();
          openGlobalSuccessModal(data.message || 'Dispositivo creado exitosamente');
        } else {
          const data = await r.json().catch(()=>({}));
          showModalMessage(data.message || 'No se pudo crear el dispositivo', 'error');
        }
      } catch (e) {
        console.error('Error creando dispositivo tras reemplazar IP', e);
        showModalMessage('Error creando dispositivo', 'error');
      }
      window.__pendingNewDeviceForm = null;
      window.__pendingNewDeviceConflictOwner = null;
      return;
    }

    if (window.__pendingEditDevicePayload) {
      // Clear any custom validity / inline error on the edit IP input before submitting
      const editIpInput = document.getElementById('editDeviceIp');
      if (editIpInput) {
        try { editIpInput.setCustomValidity(''); try { editIpInput.reportValidity(); } catch(e){} } catch(e){}
        const el = document.getElementById('editIpError'); if (el) { el.textContent = ''; el.style.display = 'none'; }
      }
      const payload = window.__pendingEditDevicePayload;
      const id = window.__pendingEditDeviceId;
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
      } catch (e) {
        console.error('Error actualizando dispositivo tras reemplazar IP', e);
        showModalMessage('Error actualizando dispositivo', 'error');
      }
      window.__pendingEditDevicePayload = null;
      window.__pendingEditDeviceConflictOwner = null;
      window.__pendingEditDeviceId = null;
      return;
    }
  } catch (e) {
    console.error('Error liberando IP', e);
    showModalMessage('Error del servidor al liberar IP', 'error');
  }
});
// Clear custom validity and inline errors when user edits IP inputs
(function(){
  const newIp = document.querySelector('input[name="ip_asignada"]');
  if (newIp) {
    const _clearNewIpValidity = () => { try { newIp.setCustomValidity(''); try { newIp.reportValidity(); } catch(e){} } catch(e){}; const el = document.getElementById('newIpError'); if (el) { el.textContent = ''; el.style.display = 'none'; } };
    newIp.addEventListener('input', _clearNewIpValidity);
    newIp.addEventListener('change', _clearNewIpValidity);
    newIp.addEventListener('blur', _clearNewIpValidity);
    // Wire the 'Dejar N/A' checkbox if present
    const chkIpNA = document.getElementById('checkIpNA');
    if (chkIpNA) {
      chkIpNA.addEventListener('change', function(){
        try {
          // Ensure we have a hidden field to submit the ip when the visible input is disabled
          const formEl = document.getElementById('formNewDevice');
          let hidden = document.getElementById('ip_asignada_hidden');
          if (chkIpNA.checked) {
            newIp.value = 'N/A';
            newIp.disabled = true;
            if (!hidden && formEl) {
              hidden = document.createElement('input');
              hidden.type = 'hidden';
              hidden.id = 'ip_asignada_hidden';
              hidden.name = 'ip_asignada';
              formEl.appendChild(hidden);
            }
            if (hidden) hidden.value = 'N/A';
          } else {
            newIp.disabled = false;
            if (hidden && hidden.parentNode) hidden.parentNode.removeChild(hidden);
            // fetch next available ip to repopulate
            fetch('/devices/next-ip')
              .then(r => r.json())
              .then(d => { if (d && d.next_ip) newIp.value = d.next_ip; })
              .catch(()=>{});
          }
        } catch(e) { console.warn('error toggling N/A checkbox', e); }
      });
    }
  }
  const editIp = document.getElementById('editDeviceIp');
  if (editIp) {
    const _clearEditIpValidity = () => { try { editIp.setCustomValidity(''); try { editIp.reportValidity(); } catch(e){} } catch(e){}; const el = document.getElementById('editIpError'); if (el) { el.textContent = ''; el.style.display = 'none'; } };
    editIp.addEventListener('input', _clearEditIpValidity);
    editIp.addEventListener('change', _clearEditIpValidity);
    editIp.addEventListener('blur', _clearEditIpValidity);
  }
  // Ensure the New Device submit button clears any custom validity before browser constraint validation runs
  try {
    const newSubmitBtn = document.querySelector('button[form="formNewDevice"][type="submit"]');
    if (newSubmitBtn) {
      newSubmitBtn.addEventListener('click', () => {
        try {
          const ni = document.querySelector('input[name="ip_asignada"]');
          if (ni) {
            try { ni.setCustomValidity(''); } catch(e){}
            try { ni.dispatchEvent(new Event('input', { bubbles: true })); } catch(e){}
            try { ni.blur(); ni.focus(); } catch(e){}
            try { ni.reportValidity(); } catch(e){}
          }
        } catch(e) {}
      });
    }
  } catch(e) {}
})();

/* ---- */

// Filter modelos by selected marca in New/Edit device modals
document.addEventListener('DOMContentLoaded', function(){
  const selectMarcaNew = document.getElementById('selectMarcaNew');
  const selectModeloNew = document.getElementById('selectModeloNew');
  const editSelectMarca = document.getElementById('editSelectMarca');
  const editSelectModelo = document.getElementById('editSelectModelo');

  function filterModelosByMarcaAndTipo(selectModelo, marcaId, tipoValue){
    if(!selectModelo) return;
    const options = Array.from(selectModelo.querySelectorAll('option'));
    options.forEach(opt => {
      const fk = opt.getAttribute('data-fk-marca');
      const tipo = opt.getAttribute('data-tipo');
      // keep placeholder visible (no data-fk-marca)
      if(!fk) { opt.style.display = ''; opt.disabled = false; return; }
      
      const marcaMatch = !marcaId || String(fk).trim().toLowerCase() === String(marcaId).trim().toLowerCase();
      // data-tipo may contain a single value or a comma-separated list. Compare case-insensitively.
      let tipoMatch = false;
      if (!tipoValue) {
        tipoMatch = true;
      } else if (!tipo) {
        tipoMatch = false;
      } else {
        const tipos = String(tipo).split(',').map(s => s.trim().toLowerCase());
        tipoMatch = tipos.includes(String(tipoValue).trim().toLowerCase());
      }
      
      if(marcaMatch && tipoMatch){
        opt.style.display = '';
        opt.disabled = false;
      } else {
        opt.style.display = 'none';
        opt.disabled = true;
      }
    });
    // If current selection became disabled, reset to placeholder
    try{
      if(selectModelo.selectedOptions && selectModelo.selectedOptions.length){
        if(selectModelo.selectedOptions[0].disabled) selectModelo.value = '';
      }
    }catch(e){}
  }

  const selectTipoNew = document.getElementById('selectTipoNew');
  const selectTipoEdit = document.getElementById('editDeviceTipo');

  if(selectMarcaNew){
    selectMarcaNew.addEventListener('change', function(e){ 
      filterModelosByMarcaAndTipo(selectModeloNew, e.target.value, selectTipoNew ? selectTipoNew.value : ''); 
    });
  }
  if(selectTipoNew){
    selectTipoNew.addEventListener('change', function(e){ 
      filterModelosByMarcaAndTipo(selectModeloNew, selectMarcaNew ? selectMarcaNew.value : '', e.target.value); 
    });
  }
  if(editSelectMarca){
    editSelectMarca.addEventListener('change', function(e){ 
      filterModelosByMarcaAndTipo(editSelectModelo, e.target.value, selectTipoEdit ? selectTipoEdit.value : ''); 
    });
  }
  if(selectTipoEdit){
    selectTipoEdit.addEventListener('change', function(e){ 
      filterModelosByMarcaAndTipo(editSelectModelo, editSelectMarca ? editSelectMarca.value : '', e.target.value); 
    });
  }

  // initial filter on load
  filterModelosByMarcaAndTipo(selectModeloNew, selectMarcaNew ? selectMarcaNew.value : '', selectTipoNew ? selectTipoNew.value : '');
  filterModelosByMarcaAndTipo(editSelectModelo, editSelectMarca ? editSelectMarca.value : '', selectTipoEdit ? selectTipoEdit.value : '');
  
  // Event listeners para actualizar identificador cuando cambia empresa o tipo
  const radiosPROIMA = document.getElementById('radioEmpresaPROIMA');
  const radiosELMIGO = document.getElementById('radioEmpresaELMIGO');
  const selectTipo = document.getElementById('selectTipoNew');
  
  if (radiosPROIMA) radiosPROIMA.addEventListener('change', updateIdentificador);
  if (radiosELMIGO) radiosELMIGO.addEventListener('change', updateIdentificador);
  if (selectTipo) selectTipo.addEventListener('change', updateIdentificador);
});

/* ---- */

async function openDeviceHistoryModal(deviceId) {
  const tbody = document.getElementById('deviceHistoryTbody');
  tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; padding:12px;">Cargando...</td></tr>';
  openModal('modalDeviceHistory', true);
  try {
    const resp = await fetch(`/devices/${deviceId}/asignaciones/device`);
    if (!resp.ok) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:#b00020;">Error cargando historial</td></tr>`;
      return;
    }
    const j = await resp.json();
    if (!j || !j.success) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:#b00020;">No se pudo obtener historial</td></tr>`;
      return;
    }
    const rows = j.asignaciones || [];
    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;">No hay historial</td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map(a => {
      const nombre = a.empleado_nombre || a.fk_id_empleado || '-';
      const inicio = a.fecha_inicio_asignacion ? new Date(a.fecha_inicio_asignacion).toLocaleDateString() : '-';
      const fin = a.fecha_fin_asignacion ? new Date(a.fecha_fin_asignacion).toLocaleDateString() : '-';
      return `<tr><td>${nombre}</td><td>${inicio}</td><td>${fin}</td></tr>`;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="3" style="text-align:center; color:#b00020;">Error: ${err && err.message ? err.message : err}</td></tr>`;
  }
}

/* ---- */

// Edit modal handlers: open modal, populate fields and save changes
async function openEditDeviceModal(deviceId) {
  try {
    // clear previous errors
    const errEl = document.getElementById('editDeviceError'); if (errEl) { errEl.style.display='none'; errEl.textContent=''; }
    // reset assignment UI to avoid showing stale data from previous device
    try {
      const fieldset = document.getElementById('fieldsetAsignacion');
      const infoLabel = document.getElementById('labelAsignacionInfo');
      const inline = document.getElementById('inlineFinalizeContainer');
      const btn = document.getElementById('btnFinalizeAsignacion');
      if (inline) inline.style.display = 'none';
      if (infoLabel) {
        infoLabel.style.display = 'flex';
        document.getElementById('infoAsignadoPersona').textContent = '-';
        document.getElementById('infoAsignadoDesde').textContent = '-';
      }
      if (btn) btn.style.display = 'none';
      if (fieldset) fieldset.style.display = 'none';
      pendingFinalizeDeviceId = null;
      pendingAsignacionData = null;
    } catch(e) { console.warn('Could not reset assignment UI', e); }
    // fetch device
    const resp = await fetch(`/devices/${deviceId}`);
    if (!resp.ok) {
      const j = await resp.json().catch(()=>({}));
      return openGlobalMessageModal('error', 'Error', j.message || 'No se pudo cargar el dispositivo');
    }
    const dev = await resp.json();

    // set fields
    const set = (id, value) => { const el = document.getElementById(id); if (!el) return; if (el.tagName === 'SELECT' || el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.value = value ?? ''; };
    document.getElementById('editDeviceId').value = deviceId;
    
    // Set marca y modelo: ensure values exist in selects or create option if needed
    const marcaSelect = document.getElementById('editSelectMarca');
    const modeloSelect = document.getElementById('editSelectModelo');
    
    // For marca: if value not found, add it
    if (dev.fk_id_marca) {
      let marcaOption = marcaSelect.querySelector(`option[value="${dev.fk_id_marca}"]`);
      if (!marcaOption) {
        // Option doesn't exist, create it
        marcaOption = document.createElement('option');
        marcaOption.value = dev.fk_id_marca;
        marcaOption.textContent = dev.nombre_marca || `Marca ${dev.fk_id_marca}`;
        marcaSelect.appendChild(marcaOption);
      }
      marcaSelect.value = dev.fk_id_marca;
    }
    
    // For modelo: if value not found, add it
    if (dev.fk_id_modelo) {
      let modeloOption = modeloSelect.querySelector(`option[value="${dev.fk_id_modelo}"]`);
      if (!modeloOption) {
        // Option doesn't exist, create it
        modeloOption = document.createElement('option');
        modeloOption.value = dev.fk_id_modelo;
        modeloOption.textContent = dev.nombre_modelo || `Modelo ${dev.fk_id_modelo}`;
        modeloSelect.appendChild(modeloOption);
      }
      modeloSelect.value = dev.fk_id_modelo;
    }
    
    set('editDeviceTipo', dev.categoria);
    // Show Components button only for allowed device types
    try {
      const btnComponents = document.getElementById('btnComponents');
      if (btnComponents) {
        const tipo = (dev.categoria || '').toString().toLowerCase();
        const allowed = ['laptop', 'celular', 'tablet'];
        const show = allowed.some(a => tipo.includes(a));
        btnComponents.style.display = show ? '' : 'none';
      }
    } catch (e) { /* ignore */ }
    set('editDeviceSerial', dev.numero_serie);
    // Set identificador if exists
    try { const elId = document.getElementById('editDeviceIdentificador'); if (elId) elId.value = dev.identificador || ''; } catch(e) {}
    set('editDeviceImei', dev.imei);
    set('editDeviceImei2', dev.imei2 || '');
    set('editDeviceMac', dev.direccion_mac);
    set('editDeviceIp', dev.ip_asignada);
    set('editDeviceObservaciones', dev.observaciones);
    // Handle fecha_obt: try multiple sources and normalize to YYYY-MM-DD format
    let fechaValue = dev.fecha_obt || dev.fecha_obtencion || '';
    if (fechaValue && typeof fechaValue === 'string') {
      // Ensure it's in YYYY-MM-DD format for input[type=date]
      if (fechaValue.includes('-') && fechaValue.split('-').length === 3) {
        // Already in YYYY-MM-DD format
        fechaValue = fechaValue.split('T')[0];  // Remove time part if present
      } else if (fechaValue.match(/^\d{4}-\d{2}-\d{2}/)) {
        // Extract YYYY-MM-DD portion
        fechaValue = fechaValue.match(/\d{4}-\d{2}-\d{2}/)[0];
      }
    }
    set('editDeviceFechaObtencion', fechaValue);
    set('editDeviceColor', dev.color);
    set('editDeviceTamano', dev.tamano);
    // Set estado as string to match select options
    set('editDeviceEstado', dev.estado !== null ? String(dev.estado) : '');
    
    // Set checkbox for cargador
    const cargadorEl = document.getElementById('editDeviceCargador');
    if (cargadorEl) cargadorEl.checked = dev.cargador ? true : false;
    
    // Handle IMEI2: mark checkbox if device has IMEI2, store original value for recovery
    const checkEditImei2 = document.getElementById('checkEditImei2');
    const labelEditImei2 = document.getElementById('labelEditImei2');
    const editDeviceImei2 = document.getElementById('editDeviceImei2');
    if (editDeviceImei2 && dev.imei2) {
      // Store original IMEI2 value globally for recovery on re-check
      window.originalEditImei2 = dev.imei2;
      checkEditImei2.checked = true;
      labelEditImei2.style.display = '';
    } else {
      window.originalEditImei2 = '';
      if (checkEditImei2) checkEditImei2.checked = false;
      if (labelEditImei2) labelEditImei2.style.display = 'none';
      if (editDeviceImei2) editDeviceImei2.value = '';
    }

    // Check if there's an active assignment for this device and show finalize button
    try { await checkActiveAsignacionForEdit(deviceId); } catch(e){ console.warn('checkActiveAsignacionForEdit failed', e); }
    
    // Toggle field visibility based on device type
    toggleEditDispositivoFields();

    openModal('modalEditDevice', true);
  } catch (e) {
    console.error('Error loading device:', e);
    openGlobalMessageModal('error', 'Error', 'No se pudo cargar el dispositivo');
  }
}

// Save edit
const btnSaveEditDevice = document.getElementById('btnSaveEditDevice');
if (btnSaveEditDevice) {
  btnSaveEditDevice.addEventListener('click', async () => {
    const id = document.getElementById('editDeviceId').value;
      // Validate fecha_ob not in future before sending
      const editFechaVal = document.getElementById('editDeviceFechaObtencion')?.value || '';
      if (editFechaVal) {
        // Use string comparison to avoid timezone issues
        const today = new Date();
        const todayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
        if (editFechaVal > todayStr) {
          openModal('modalFechaFutura');
          return;
        }
      }

      // Validate serial number uniqueness before submitting
      const editSerialVal = document.getElementById('editDeviceSerial')?.value || '';
      if (editSerialVal && editSerialVal.trim()) {
        try {
          const chkSerial = await fetch('/devices/check-serial', { 
            method: 'POST', 
            headers: {'Content-Type':'application/json'}, 
            credentials: 'same-origin', 
            body: JSON.stringify({ numero_serie: editSerialVal.trim(), device_id: id }) 
          });
          if (chkSerial.ok) {
            const chkData = await chkSerial.json().catch(()=>({}));
            if (chkData.exists) {
              const dev = chkData.device || {};
              const msgEl = document.getElementById('serieDuplicadaMessage');
              if (msgEl) msgEl.textContent = `El número de serie "${editSerialVal}" ya existe en ${dev.categoria || 'un dispositivo'} ${dev.nombre_marca || ''} ${dev.nombre_modelo || ''}.`;
              openModal('modalSerieDuplicada');
              return;
            }
          }
        } catch (e) {
          console.error('Serial check failed', e);
        }
      }

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
      fk_id_modelo: (document.getElementById('editSelectModelo')?.value) || null
    };
    
    // Solo incluir estado si el campo está visible (impresoras) y tiene valor válido
    const estadoSelect = document.getElementById('editDeviceEstado');
    const estadoLabel = document.getElementById('labelEditDeviceEstado');
    if (estadoLabel && estadoLabel.style.display !== 'none' && estadoSelect) {
      const estadoVal = estadoSelect.value;
      if (estadoVal !== null && estadoVal !== '' && estadoVal !== undefined) {
        payload.estado = parseInt(estadoVal);
      }
    }
    
    // Limpiar IP para dispositivos que no usan IP (periféricos, PC, Celular, Tablet)
    const tipoDispositivo = document.getElementById('editDeviceTipo')?.value || '';
    const tipo = tipoDispositivo.toLowerCase();
    if (['teclado', 'mouse', 'auriculares', 'monitor', 'pc', 'celular', 'tablet', 'ups', 'adaptador'].includes(tipo)) {
      payload.ip_asignada = null;
    }
    // Normalizar 'N/A' sólo para tipos que no usan IP; de lo contrario mantener 'N/A'
    if ((payload.ip_asignada || '').toString().toUpperCase() === 'N/A') {
      const noIpTypes = ['teclado', 'mouse', 'auriculares', 'monitor', 'pc', 'celular', 'tablet', 'ups', 'adaptador'];
      if (noIpTypes.includes(tipo)) {
        payload.ip_asignada = null;
      } else {
        payload.ip_asignada = 'N/A';
      }
    }
    
    // Validate identifier uniqueness before submitting
    try {
      const identifierVal = payload.identificador || '';
      if (identifierVal) {
        const chkIdent = await fetch('/devices/check-identifier', { 
          method: 'POST', 
          headers: {'Content-Type':'application/json'}, 
          credentials: 'same-origin', 
          body: JSON.stringify({ identifier: identifierVal, device_id: id }) 
        });
        if (chkIdent.ok) {
          const chkData = await chkIdent.json().catch(()=>({}));
          if (chkData.exists) {
            const dev = chkData.device || {};
            openGlobalMessageModal('error', 'Error', `El identificador "${identifierVal}" ya está asignado a otro dispositivo (${dev.categoria || 'dispositivo'}).`);
            return;
          }
        }
      }
    } catch (e) {
      console.error('Identifier check failed', e);
    }
    
    // If IP provided and different device owns it, show conflict modal first
    try {
      let ipVal = (payload.ip_asignada || '').toString().trim();
      // Normalize 'N/A' to skip validation but keep the explicit 'N/A' value
      // so it is stored when the user intentionally selected it.
      if (ipVal.toUpperCase() === 'N/A') { ipVal = ''; /* keep payload.ip_asignada === 'N/A' */ }
      if (ipVal) {
        // Validar formato de IP
        if (!isValidIpFormat(ipVal)) {
          openGlobalMessageModal('error', 'Error', 'Formato de IP inválido. Debe ser XXX.XXX.XXX.XXX (cada número entre 0-255)');
          return;
        }
        
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
            return; // wait user's decision
          }
        }
      }
    } catch (e) {
      console.error('IP check failed', e);
    }

    try {
      const r = await fetch(`/devices/${id}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, credentials: 'same-origin', body: JSON.stringify(payload) });
      const data = await r.json().catch(()=>({}));
      if (r.ok && data.success) {
        closeModal('modalEditDevice');
        if (typeof reloadDevicesTable === 'function') await reloadDevicesTable();
        openGlobalSuccessModal(data.message || 'Dispositivo actualizado');
      } else {
        const errorMsg = data.message || 'No se pudo actualizar';
        let errorTitle = 'Error al actualizar';
        let errorDetail = errorMsg;
        
        if (errorMsg.toLowerCase().includes('modelo')) {
          errorTitle = 'Error: Modelo requerido';
          errorDetail = 'Debe seleccionar un modelo v\u00e1lido para continuar.';
        } else if (errorMsg.toLowerCase().includes('identificador')) {
          errorTitle = 'Error: Identificador duplicado';
          errorDetail = 'El identificador ingresado ya est\u00e1 en uso por otro dispositivo.';
        } else if (errorMsg.toLowerCase().includes('ip')) {
          errorTitle = 'Error: Direcci\u00f3n IP';
          errorDetail = 'La direcci\u00f3n IP ingresada ya est\u00e1 en uso o no es v\u00e1lida.';
        } else if (errorMsg.toLowerCase().includes('imei')) {
          errorTitle = 'Error: IMEI duplicado';
          errorDetail = 'El IMEI ingresado ya est\u00e1 registrado en otro dispositivo.';
        } else if (errorMsg.toLowerCase().includes('numero') && errorMsg.toLowerCase().includes('serie')) {
          errorTitle = 'Error: N\u00famero de serie';
          errorDetail = 'El n\u00famero de serie ingresado ya existe.';
        } else if (errorMsg.toLowerCase().includes('permiso')) {
          errorTitle = 'Permiso denegado';
          errorDetail = 'No tienes permisos suficientes para editar este dispositivo.';
        }
        
        openGlobalMessageModal('error', errorTitle, errorDetail);
        const err = document.getElementById('editDeviceError'); 
        if (err) { 
          err.textContent = errorDetail; 
          err.style.display='block'; 
        }
      }
    } catch (err) {
      console.error('Error actualizando dispositivo:', err);
      const errorMsg = err.message || 'Error de conexi\u00f3n';
      let errorTitle = 'Error de conexi\u00f3n';
      let errorDetail = 'No se pudo conectar con el servidor. Verifica tu conexi\u00f3n e intenta nuevamente.';
      
      if (errorMsg.toLowerCase().includes('network') || errorMsg.toLowerCase().includes('fetch')) {
        errorTitle = 'Error de red';
        errorDetail = 'No se pudo establecer conexi\u00f3n con el servidor.';
      } else if (errorMsg.toLowerCase().includes('timeout')) {
        errorTitle = 'Tiempo de espera agotado';
        errorDetail = 'La operaci\u00f3n tard\u00f3 demasiado tiempo. Intenta nuevamente.';
      }
      
      openGlobalMessageModal('error', errorTitle, errorDetail);
      const el = document.getElementById('editDeviceError'); 
      if (el) { 
        el.textContent = errorDetail; 
        el.style.display='block'; 
      }
    }
  });
}

// Declare openGestionarMarcasModelosModal early so it's available for inline onclick handlers
// auto-fill tipo when modelo selected in edit modal
let marcasData = [];
const editSelectModeloEl = document.getElementById('editSelectModelo');
if (editSelectModeloEl) {
  editSelectModeloEl.addEventListener('change', async (e) => {
    const selectedOption = e.target.selectedOptions[0];
    const tipo = selectedOption ? selectedOption.getAttribute('data-tipo') : '';
    const selectTipoEdit = document.getElementById('editDeviceTipo');
    if (selectTipoEdit) selectTipoEdit.value = tipo || '';
    
    // Autofill UPS fields from modelo if tipo is UPS
    const modeloId = e.target.value;
    if (tipo && tipo.toLowerCase() === 'ups' && modeloId) {
      try {
        const resp = await fetch(`/devices/modelo/${modeloId}`);
        if (resp.ok) {
          const modelo = await resp.json();
          if (modelo && modelo.salidas) {
            const salidasEl = document.getElementById('salidasEditDevice');
            if (salidasEl) salidasEl.value = modelo.salidas;
          }
          if (modelo && modelo.capacidad) {
            const parts = modelo.capacidad.trim().split(/\s+/);
            if (parts.length >= 2) {
              const vaEl = document.getElementById('capacidadVAEditDevice');
              const wEl = document.getElementById('capacidadWEditDevice');
              if (vaEl) vaEl.value = parts[0];
              if (wEl) wEl.value = parts[1];
            }
          }
        }
      } catch (err) {
        console.error('Error loading modelo UPS data:', err);
      }
    }
    
    // Actualizar visibilidad de campos
    toggleEditDispositivoFields();
  });
}
let modelosData = [];
let marcaActualSeleccionada = null;
let modeloActualSeleccionado = null;

function openGestionarMarcasModelosModal() {
  // Cargar marcas y modelos cuando se abre el modal
  cargarMarcas();
  cargarModelos();
  cargarMarcasParaSelector();
  
  // Resetear selecciones
  marcaActualSeleccionada = null;
  modeloActualSeleccionado = null;
  document.getElementById('selectMarcaGestion').value = '';
  document.getElementById('selectModeloGestion').value = '';
  document.getElementById('botonesGestionMarcas').style.display = 'none';
  document.getElementById('botonesGestionModelos').style.display = 'none';
  
  openModal('modalGestionarMarcasModelos');
}

window.openGestionarMarcasModelosModal = openGestionarMarcasModelosModal;

// edit modal removed; related helpers removed

// --- Finalizar asignación (desde modal Editar Dispositivo) ---
let pendingFinalizeDeviceId = null;
let pendingAsignacionData = null;

async function checkActiveAsignacionForEdit(deviceId) {
  const btn = document.getElementById('btnFinalizeAsignacion');
  const fieldset = document.getElementById('fieldsetAsignacion');
  const infoLabel = document.getElementById('labelAsignacionInfo');
  const inline = document.getElementById('inlineFinalizeContainer');
  if (!btn || !fieldset) return;
  
  pendingFinalizeDeviceId = null;
  pendingAsignacionData = null;
  btn.style.display = 'none';
  fieldset.style.display = 'none';
  
  try {
    const r = await fetch(`/devices/${deviceId}/asignacion-activa`, { credentials: 'same-origin' });
    if (!r.ok) {
      console.warn('API call failed', r.status);
      return;
    }
    const j = await r.json();
    if (window.__DEV_LOGS) console.log('Asignación data:', j);
    
    if (j && j.active && j.asignacion) {
      pendingFinalizeDeviceId = deviceId;
      pendingAsignacionData = j.asignacion;
      fieldset.style.display = 'block';
      if (infoLabel) infoLabel.style.display = 'flex';
      if (inline) inline.style.display = 'none';

      const rawPersona = j.asignacion.empleado_nombre || null;
      const empleadoId = j.asignacion.fk_id_empleado || null;
      const fecha = j.asignacion.fecha_inicio_asignacion ? new Date(j.asignacion.fecha_inicio_asignacion).toLocaleDateString() : '-';

      // If we have a readable name, use it. Otherwise try to fetch employees list and map the id.
      if (rawPersona && String(rawPersona).trim() !== '') {
        document.getElementById('infoAsignadoPersona').textContent = rawPersona;
        document.getElementById('finalizeAsignadoPersona') && (document.getElementById('finalizeAsignadoPersona').textContent = rawPersona);
      } else if (empleadoId) {
        // show temporary id while resolving
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
  } catch (e) {
    console.error('Error checking active assignment', e);
  }
}

function finalizarAsignacionClick() {
  if (!pendingFinalizeDeviceId || !pendingAsignacionData) {
    openGlobalMessageModal('info', 'Info', 'No hay asignación activa para finalizar');
    return;
  }

  // Open modal confirmation (user must type 'CONFIRMAR' to enable Confirm button)
  openFinalizeAsignacionModal();
}

function cancelFinalizeAsignacionInline() {
  const infoLabel = document.getElementById('labelAsignacionInfo');
  const btn = document.getElementById('btnFinalizeAsignacion');
  const inline = document.getElementById('inlineFinalizeContainer');
  const input = document.getElementById('editAsignacionConfirm');
  const err = document.getElementById('inlineFinalizeAsignacionError');
  if (inline) inline.style.display = 'none';
  if (infoLabel) infoLabel.style.display = 'flex';
  if (btn) btn.style.display = 'block';
  if (input) { input.value = ''; }
  if (err) { err.style.display = 'none'; err.textContent = ''; }
}

async function confirmFinalizeAsignacionInline() {
  const btn = document.getElementById('btnConfirmFinalizeInline');
  const errEl = document.getElementById('inlineFinalizeAsignacionError');
  if (!pendingFinalizeDeviceId) return;
  if (btn) { btn.disabled = true; btn.textContent = 'Finalizando...'; }
  if (errEl) { errEl.style.display = 'none'; errEl.textContent = ''; }
  try {
    const r = await fetch(`/devices/${pendingFinalizeDeviceId}/finalizar-asignacion`, {
      method: 'POST',
      credentials: 'same-origin'
    });
    const data = await r.json().catch(()=>({}));
    if (r.ok && data.success) {
      // hide the whole assignment section (no remnants) like the modal flow does
      const inline = document.getElementById('inlineFinalizeContainer');
      const fieldset = document.getElementById('fieldsetAsignacion');
      const btnFin = document.getElementById('btnFinalizeAsignacion');
      if (inline) inline.style.display = 'none';
      if (btnFin) btnFin.style.display = 'none';
      if (fieldset) fieldset.style.display = 'none';
      // update the row immediately so the table reflects the change
      try { await updateDeviceRow(pendingFinalizeDeviceId); } catch(e){ console.warn('updateDeviceRow failed', e); }
      pendingFinalizeDeviceId = null;
      pendingAsignacionData = null;
      openGlobalSuccessModal(data.message || 'Asignación finalizada');
    } else {
      if (errEl) { errEl.textContent = data.message || 'No se pudo finalizar la asignación'; errEl.style.display = 'block'; }
    }
  } catch (e) {
    console.error('Error finalizing assignment (inline)', e);
    if (errEl) { errEl.textContent = 'Error: ' + (e && e.message ? e.message : e); errEl.style.display = 'block'; }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Confirmar'; }
  }
}

function openFinalizeAsignacionModal() {
  if (!pendingFinalizeDeviceId || !pendingAsignacionData) return;
  
  const label = document.getElementById('finalizeDeviceLabel');
  const tipo = document.getElementById('editDeviceTipo')?.value || '';
  const marca = document.getElementById('editSelectMarca')?.selectedOptions[0]?.textContent || '';
  const modelo = document.getElementById('editSelectModelo')?.selectedOptions[0]?.textContent || '';
  const serie = document.getElementById('editDeviceSerial')?.value || '';
  
  if (label) label.textContent = `${tipo} - ${marca} - ${modelo} - ${serie}`;
  document.getElementById('finalizeAsignadoPersona').textContent = pendingAsignacionData.empleado_nombre || pendingAsignacionData.fk_id_empleado || '-';
  document.getElementById('finalizeAsignadoDesde').textContent = pendingAsignacionData.fecha_inicio_asignacion ? new Date(pendingAsignacionData.fecha_inicio_asignacion).toLocaleDateString() : '-';
  
  const err = document.getElementById('finalizeAsignacionError');
  if (err) err.style.display = 'none';
  
  // Clear confirmation input and disable confirm button when opening (enforce fresh input)
  try {
    const modal = document.getElementById('modalFinalizeAsignacion');
    if (modal) {
      const ci = modal.querySelector('#confirmFinalizeInput');
      const btn = modal.querySelector('#btnConfirmFinalizeAsignacion');
      if (ci) ci.value = '';
      if (btn) btn.disabled = true;
    }
  } catch(e) {}

  openModal('modalFinalizeAsignacion', true);
}

// Wire modal confirm input to enable confirm button
document.addEventListener('DOMContentLoaded', function(){
  const modal = document.getElementById('modalFinalizeAsignacion');
  if (!modal) return;
  const input = modal.querySelector('#confirmFinalizeInput');
  const btn = modal.querySelector('#btnConfirmFinalizeAsignacion');
  const btnCancel = modal.querySelector('#btnCancelFinalizeAsignacion');
    if (input && btn) {
    const handler = () => {
      try { btn.disabled = input.value.trim() !== 'CONFIRMAR'; } catch(e){}
    };
    input.removeEventListener('input', handler);
    input.addEventListener('input', handler);
    handler();
  }
  if (btnCancel) {
    btnCancel.addEventListener('click', () => { closeModal('modalFinalizeAsignacion'); });
  }
    if (btn) {
    // ensure confirm button calls existing confirmFinalizeAsignacion
    btn.addEventListener('click', async () => {
      // double-check input (case-sensitive)
      if (input && input.value.trim() !== 'CONFIRMAR') return;
      await confirmFinalizeAsignacion();
    });
  }
});

async function confirmFinalizeAsignacion() {
  const btn = document.getElementById('btnConfirmFinalizeAsignacion');
  if (!pendingFinalizeDeviceId) return;
  
  if (btn) { btn.disabled = true; btn.textContent = 'Finalizando...'; }
  
  try {
    const r = await fetch(`/devices/${pendingFinalizeDeviceId}/finalizar-asignacion`, { 
      method: 'POST', 
      credentials: 'same-origin' 
    });
    const data = await r.json().catch(()=>({}));
    
    if (r.ok && data.success) {
      // hide the assignment section entirely and close modals
      const fieldset = document.getElementById('fieldsetAsignacion');
      const btnFin = document.getElementById('btnFinalizeAsignacion');
      if (btnFin) btnFin.style.display = 'none';
      if (fieldset) fieldset.style.display = 'none';
      closeModal('modalFinalizeAsignacion');
      closeModal('modalEditDevice');
      // update the row immediately so the table reflects the change
      try { await updateDeviceRow(pendingFinalizeDeviceId); } catch(e){ console.warn('updateDeviceRow failed', e); }
      if (data && data.fecha_fin) {
        try {
          const asignId = pendingAsignacionData && (pendingAsignacionData.id_asignacion || pendingAsignacionData.fk_id_asignacion || pendingAsignacionData.id || null);
          if (asignId) updateHistoricoFechaFin(asignId, data.fecha_fin);
        } catch(e) { console.warn('updateHistoricoFechaFin failed', e); }
      }
      openGlobalSuccessModal(data.message || 'Asignación finalizada');
      pendingFinalizeDeviceId = null;
      pendingAsignacionData = null;
    } else {
      const e = document.getElementById('finalizeAsignacionError');
      if (e) {
        e.textContent = data.message || 'No se pudo finalizar la asignación';
        e.style.display = 'block';
      }
    }
  } catch (e) {
    console.error('Error finalizing assignment', e);
    const el = document.getElementById('finalizeAsignacionError');
    if (el) {
      el.textContent = 'Error: ' + e.message;
      el.style.display = 'block';
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Confirmar finalización';
    }
  }
}


// delete logic removed; deletion handled elsewhere or disabled

// Variable temporal para almacenar componentes seleccionados
window.__selectedDeviceComponents = null;

// Auto-fill categoria y marca when modelo is selected, then show suggestions
const selectModeloNew = document.getElementById('selectModeloNew');
if (selectModeloNew) {
  selectModeloNew.addEventListener('change', async (e) => {
    const selectedOption = e.target.selectedOptions[0];
    const tipo = selectedOption ? selectedOption.getAttribute('data-tipo') : '';
    const marcaId = selectedOption ? selectedOption.getAttribute('data-fk-marca') : '';
    const modeloId = e.target.value;
    
    // Autofill tipo
    const selectTipo = document.getElementById('selectTipoNew');
    if (selectTipo) {
      selectTipo.value = tipo || '';
      // Actualizar visibilidad de campos según el tipo
      toggleDispositivoFields();
      // Regenerar identificador con el tipo correcto
      updateIdentificador();
    }
    
    // Autofill marca
    const selectMarca = document.getElementById('selectMarcaNew');
    if (selectMarca && marcaId) {
      selectMarca.value = marcaId;
    }
    
    // Autofill UPS fields from modelo if tipo is UPS
    if (tipo && tipo.toLowerCase() === 'ups' && modeloId) {
      try {
        const resp = await fetch(`/devices/modelo/${modeloId}`);
        if (resp.ok) {
          const modelo = await resp.json();
          if (modelo && modelo.salidas) {
            const salidasEl = document.getElementById('salidasNewDevice');
            if (salidasEl) salidasEl.value = modelo.salidas;
          }
          if (modelo && modelo.capacidad) {
            const parts = modelo.capacidad.trim().split(/\s+/);
            if (parts.length >= 2) {
              const vaEl = document.getElementById('capacidadVANewDevice');
              const wEl = document.getElementById('capacidadWNewDevice');
              if (vaEl) vaEl.value = parts[0];
              if (wEl) wEl.value = parts[1];
            }
          }
        }
      } catch (err) {
        console.error('Error loading modelo UPS data:', err);
      }
    }
    
    // Check if all 3 fields are selected to show device info
    checkDeviceInfoVisibility();
    
    // Cargar sugerencias de dispositivos
    if (modeloId) {
      await loadDeviceSuggestions(modeloId);
    }
  });
}

// Helper: Generate fingerprint for a device to detect duplicates
function getDeviceFingerprint(dev) {
  // Create a unique identifier based on dispositivo + componentes
  const devicePart = `${(dev.categoria || '').toLowerCase()}|${(dev.nombre_marca || '').toLowerCase()}|${(dev.nombre_modelo || '').toLowerCase()}|${(dev.color || '').toLowerCase()}|${(dev.tamano || '').toLowerCase()}`;
  
  // Create fingerprint for each componente ordenado por tipo
  const componenteParts = (dev.componentes || [])
    .map(c => {
      const tipo = c.tipo_componente;
      const modelo = (c.componente_modelo || c.nombre_modelo || '').toLowerCase();
      const capacidad = c.capacidad || '';
      const frecuencia = c.frecuencia || '';
      const tipoMem = (c.tipo_memoria || '').toLowerCase();
      const tipoDisco = (c.tipo_disco || '').toLowerCase();
      return `${tipo}:${modelo}:${capacidad}:${frecuencia}:${tipoMem}:${tipoDisco}`;
    })
    .sort()
    .join('|');
  
  return `${devicePart}||${componenteParts}`;
}

// Deduplicar dispositivos por sus características
function deduplicateDevices(suggestions) {
  const seen = new Set();
  const deduplicated = [];
  
  for (const dev of suggestions) {
    const fingerprint = getDeviceFingerprint(dev);
    if (!seen.has(fingerprint)) {
      seen.add(fingerprint);
      deduplicated.push(dev);
    }
  }
  
  return deduplicated;
}

async function loadDeviceSuggestions(modeloId) {
  try {
    const resp = await fetch(`/devices/suggestions/${modeloId}`);
    if (!resp.ok) throw new Error('Error cargando sugerencias');
    
    const suggestions = await resp.json();
    // Filtrar sugerencias: mostrar dispositivos que tengan al menos un componente con datos relevantes
    const validSuggestions = (suggestions || []).filter(dev => {
      if (!dev || !dev.componentes || dev.componentes.length === 0) return false;
      return dev.componentes.some(c =>
        c.componente_modelo || c.capacidad || c.frecuencia || c.tipo_memoria || c.tipo_disco
      );
    });

    if (validSuggestions && validSuggestions.length > 0) {
      renderSuggestionCards(validSuggestions);
      openModal('modalDeviceSuggestions');
    }
  } catch (err) {
    console.error('Error loading suggestions:', err);
  }
}

function groupAndAnnotateVariants(suggestions) {
  // Crear grupos por modelo+marca para detectar variantes de RAM/DISCO
  const groups = {};
  
  suggestions.forEach(dev => {
    const key = `${dev.nombre_marca}|${dev.nombre_modelo}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(dev);
  });
  
  // Anotar dispositivos que tienen variantes
  Object.values(groups).forEach(group => {
    if (group.length > 1) {
      // Hay múltiples dispositivos del mismo modelo - son variantes
      group.forEach(dev => {
        dev._hasVariants = true;
        dev._variantCount = group.length;
        
        // Extraer specs para mostrar
        const ramCaps = new Set();
        const discoCaps = new Set();
        group.forEach(d => {
          d.componentes?.forEach(c => {
            if (c.tipo_componente === 1 && c.capacidad) ramCaps.add(c.capacidad);
            if (c.tipo_componente === 2 && c.capacidad) discoCaps.add(c.capacidad);
          });
        });
        dev._variantRamOptions = Array.from(ramCaps).sort((a, b) => a - b);
        dev._variantDiscoOptions = Array.from(discoCaps).sort((a, b) => a - b);
      });
    }
  });
}

function renderSuggestionCards(suggestions) {
  const container = document.getElementById('suggestionCardsContainer');
  if (!container) return;
  
  container.innerHTML = suggestions.map(dev => {
    const categoria = dev.categoria || '-';
    const marca = dev.nombre_marca || '-';
    const modelo = dev.nombre_modelo || '-';
    const color = dev.color || '-';
    const tamano = dev.tamano || '-';
    
    // Obtener descripción compacta por componente
    let componentesHtml = '';
    if (dev.componentes && dev.componentes.length > 0) {
      const compLines = dev.componentes.map(comp => {
        const tipoRaw = comp.tipo_componente;
        const tipoStr = (typeof tipoRaw === 'string') ? tipoRaw.toUpperCase() : (tipoRaw === 0 ? 'CPU' : tipoRaw === 1 ? 'RAM' : tipoRaw === 2 ? 'DISCO' : '?');
        let icon = 'memory';
        let label = tipoStr;
        let detail = '';

        if (tipoStr === 'CPU') {
          icon = 'developer_board';
          detail = comp.componente_modelo || comp.nombre_modelo || '';
          if (comp.frecuencia) {
            const ghz = (comp.frecuencia / 100).toFixed(2);
            detail = detail ? `${detail} ${ghz}GHz` : `${ghz}GHz`;
          }
        } else if (tipoStr === 'RAM') {
          icon = 'memory';
          detail = comp.componente_modelo || comp.nombre_modelo || '';
          if (comp.capacidad) detail = detail ? `${detail} ${comp.capacidad}GB` : `${comp.capacidad}GB`;
          if (comp.tipo_memoria) detail += ` ${comp.tipo_memoria}`;
        } else if (tipoStr === 'DISCO') {
          icon = 'storage';
          detail = comp.componente_modelo || comp.nombre_modelo || '';
          if (comp.capacidad) detail = detail ? `${detail} ${comp.capacidad}GB` : `${comp.capacidad}GB`;
          if (comp.tipo_disco) detail += ` ${comp.tipo_disco}`;
        }

        if (!detail) return '';
        return `<div style="margin-top: 0.4rem; display: flex; align-items: center; gap: 0.4rem; font-size: 0.9rem;">
          <span class="material-symbols-outlined" style="font-size: 1.1rem;">${icon}</span>
          <span style="font-weight:500; min-width:3rem;">${label}:</span>
          <span>${detail}</span>
        </div>`;
      }).filter(Boolean);
      componentesHtml = compLines.join('');
    }
    
    // Build specs line: only show fields with meaningful values
    const specs = [];
    if (tamano && tamano !== '-') specs.push(`Pantalla: ${tamano}`);
    if (color && color !== '-') specs.push(`Color: ${color}`);
    const specsLine = specs.length > 0 ? `<div style="color: var(--text-gray); font-size: 0.95rem;">${specs.join(' • ')}</div>` : '';
    
    return `
      <div class="suggestion-card" onclick="selectSuggestion(${dev.id_dispositivo})" style="
        border: 2px solid #e5e7eb;
        border-radius: 8px;
        padding: 1rem;
        cursor: pointer;
        transition: all 0.2s;
        background: var(--bg-card);
      " onmouseover="this.style.borderColor='#3b82f6'; this.style.boxShadow='0 4px 12px rgba(59, 130, 246, 0.2)';" 
         onmouseout="this.style.borderColor='#e5e7eb'; this.style.boxShadow='none';">
        <div style="font-weight: 600; font-size: 1.05rem; margin-bottom: 0.5rem;">
          ${categoria} ${marca} ${modelo}
        </div>
        ${specsLine}
        ${componentesHtml}
      </div>
    `;
  }).join('');
  
  // Store suggestions data for later use
  window.__deviceSuggestions = suggestions;
}

function selectSuggestion(deviceId) {
  const suggestions = window.__deviceSuggestions || [];
  const selected = suggestions.find(d => d.id_dispositivo === deviceId);
  
  if (!selected) return;
  
  // Autofill color y tamaño
  const colorSelect = document.querySelector('select[name="color"]');
  if (colorSelect && selected.color) {
    colorSelect.value = selected.color;
  }
  
  const tamanoSelect = document.getElementById('newDeviceTamano');
  if (tamanoSelect && selected.tamano) {
    tamanoSelect.value = selected.tamano;
  }
  
  // Guardar componentes en variable temporal
  if (selected.componentes && selected.componentes.length > 0) {
    window.__selectedDeviceComponents = selected.componentes;
  }
  
  // Cerrar modal
  closeModal('modalDeviceSuggestions');
}

// Check device info visibility when marca is selected
const selectMarcaNew = document.getElementById('selectMarcaNew');
if (selectMarcaNew) {
  selectMarcaNew.addEventListener('change', () => {
    checkDeviceInfoVisibility();
  });
}

// Toggle IMEI2 field visibility and required state
function toggleImei2Field() {
  const chk = document.getElementById('checkImei2');
  const label = document.getElementById('labelNewImei2');
  const input = document.getElementById('inputImei2');
  if (!chk || !label || !input) return;
  if (chk.checked) {
    label.style.display = '';
    input.required = true;
  } else {
    label.style.display = 'none';
    input.required = false;
    input.value = '';
  }
}

// Toggle tinta tracking detail field
function toggleTintaTrackingField() {
  const chk = document.getElementById('checkTintaTracking');
  const container = document.getElementById('containerTintaDetalle');
  const input = document.getElementById('inputTintaDetalle');
  if (!chk || !container || !input) return;
  if (chk.checked) {
    container.style.display = 'block';
    input.required = true;
    input.focus();
  } else {
    container.style.display = 'none';
    input.required = false;
    input.value = '';
  }
}

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

// Check if all 3 required fields are selected (tipo, marca, modelo) and show/hide device info section
function checkDeviceInfoVisibility() {
  const tipoSelect = document.getElementById('selectTipoNew');
  const marcaSelect = document.getElementById('selectMarcaNew');
  const modeloSelect = document.getElementById('selectModeloNew');
  const fieldsetInfo = document.getElementById('fieldsetDispositivoInfo');
  
  if (!fieldsetInfo) return; // Safety check
  
  const hasType = tipoSelect && tipoSelect.value;
  const hasMarca = marcaSelect && marcaSelect.value;
  const hasModelo = modeloSelect && modeloSelect.value;
  
  // Show device info section ONLY if all 3 fields have values
  const show = (hasType && hasMarca && hasModelo);
  fieldsetInfo.style.display = show ? '' : 'none';
  // Also toggle identificador input visibility specifically
  try {
    const lblIdNew = document.getElementById('labelNewIdentificador');
    if (lblIdNew) lblIdNew.style.display = show ? '' : 'none';
  } catch (e) {}
}

// Toggle dispositivo fields visibility based on type
function toggleDispositivoFields() {
  const tipoSelect = document.getElementById('selectTipoNew');
  const tipo = (tipoSelect?.value || '').toLowerCase();
  
  // Fields that should be shown/hidden based on device type
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
  // Treat monitor, printer, VoIP phone and UPS as peripherals
  const isPeriferico = isAuricular || isTeclado || isRatom || isMonitor || isImpresora || isVoip || isUPS;
  
  // IMEI: only for celular and tablet
  const imeiInput = document.querySelector('input[name="imei"]');
  document.getElementById('labelNewImei').style.display = isMobile ? '' : 'none';
  document.getElementById('labelNewImei2Checkbox').style.display = isMobile ? '' : 'none';
  if (imeiInput) {
    imeiInput.required = isMobile;
  }
  if (!isMobile) {
    document.getElementById('checkImei2').checked = false;
    document.getElementById('labelNewImei2').style.display = 'none';
  }
  
  // MAC: show for all network devices except periféricos, monitor, UPS, Adaptador and explicitly hide for Celular and PC
  document.getElementById('labelNewMac').style.display = (isPeriferico || isMonitor || isCelular || isPC || isAdaptador) ? 'none' : '';

  // IP: show for devices that connect to network (include Celular y PC per nuevo requerimiento)
  const lblNewIp = document.getElementById('labelNewIp');
  lblNewIp.style.display = (isCelular || isTablet || isRouter || isSwitch || isLaptop || isImpresora || isVoip || isPC) ? '' : 'none';
  if (lblNewIp.style.display === 'none') {
    try {
      const ipInp = document.querySelector('input[name="ip_asignada"]');
      if (ipInp) ipInp.value = 'N/A';
      const chk = document.getElementById('checkIpNA');
      if (chk) {
        chk.checked = true;
        try { chk.dispatchEvent(new Event('change', { bubbles: true })); } catch(e) {}
      }
    } catch(e){}
  } else {
    // If shown, ensure the N/A checkbox is unchecked by default and trigger change so handler restores IP
    try {
      const chk = document.getElementById('checkIpNA');
      if (chk) {
        chk.checked = false;
        try { chk.dispatchEvent(new Event('change', { bubbles: true })); } catch(e) {}
      }
      const ipInp = document.querySelector('input[name="ip_asignada"]');
      if (ipInp) ipInp.disabled = false;
      if (ipInp && (!chk || !chk.checked)) {
        const curVal = (ipInp.value || '').trim();
        if (!curVal || curVal === 'N/A' || curVal === '192.168.0.0') {
          fetch('/devices/next-ip')
            .then(r => r.json())
            .then(d => { if (d && d.next_ip) ipInp.value = d.next_ip; })
            .catch(()=>{});
        }
      }
    } catch(e) {}
  }

  // UPS fields: show only for UPS
  const upsFieldsNew = document.getElementById('upsFieldsNewDevice');
  if (upsFieldsNew) {
    upsFieldsNew.style.display = isUPS ? '' : 'none';
    // Make UPS fields required when UPS is selected
    const salidasInput = document.getElementById('salidasNewDevice');
    const vaInput = document.getElementById('capacidadVANewDevice');
    const wInput = document.getElementById('capacidadWNewDevice');
    if (salidasInput) salidasInput.required = isUPS;
    if (vaInput) vaInput.required = isUPS;
    if (wInput) wInput.required = isUPS;
  }

  // Tinta tracking: only for impresoras
  try {
    const lblTinta = document.getElementById('labelNewTintaTracking');
    const chkTinta = document.getElementById('checkTintaTracking');
    const contTinta = document.getElementById('containerTintaDetalle');
    if (lblTinta) lblTinta.style.display = isImpresora ? '' : 'none';
    if (!isImpresora) {
      if (chkTinta) chkTinta.checked = false;
      if (contTinta) { contTinta.style.display = 'none'; const inp = document.getElementById('inputTintaDetalle'); if (inp) inp.value=''; }
    }
  } catch(e) { /* ignore */ }
  
  // Color: show for all devices
  document.getElementById('labelNewColor').style.display = '';
  
  // Tamaño (Screen size): show for celular, tablet, monitor, laptop and NOT for PC, impresora, voip, periféricos, adaptador
  const showTamano = (isCelular || isTablet || isMonitor || isLaptop) ? '' : 'none';
  document.getElementById('labelNewTamano').style.display = showTamano;
  
  // Cargador/Adaptador AC: show for all devices EXCEPT Adaptador
  document.getElementById('labelNewCargador').style.display = isAdaptador ? 'none' : '';
  
  // Observaciones: show for all
  document.getElementById('labelNewObservaciones').style.display = '';
  
  // Extensión VoIP: show only for teléfono voip
  document.getElementById('labelNewExtension').style.display = isVoip ? '' : 'none';
  
  // Fecha obtención: show for all
  document.getElementById('labelNewFechaObt').style.display = '';
}

// Toggle dispositivo fields visibility for edit modal based on type
function toggleEditDispositivoFields() {
  const tipoSelect = document.getElementById('editDeviceTipo');
  const tipo = (tipoSelect?.value || '').toLowerCase();
  
  // Fields that should be shown/hidden based on device type
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
  // Treat monitor, printer, VoIP phone and UPS as peripherals
  const isPeriferico = isAuricular || isTeclado || isRatom || isMonitor || isImpresora || isVoip || isUPS;
  
  // IMEI: only for celular and tablet
  const imeiEditInput = document.getElementById('editDeviceImei');
  document.getElementById('labelEditImei').style.display = isMobile ? '' : 'none';
  document.getElementById('labelEditImei2Checkbox').style.display = isMobile ? '' : 'none';
  if (imeiEditInput) {
    imeiEditInput.required = isMobile;
  }
  if (!isMobile) {
    document.getElementById('checkEditImei2').checked = false;
    document.getElementById('labelEditImei2').style.display = 'none';
  }
  
  // MAC: show for all network devices except periféricos, monitor, UPS, Adaptador and explicitly hide for Celular and PC
  const lblEditMac = document.getElementById('labelEditMac');
  lblEditMac.style.display = (isPeriferico || isMonitor || isCelular || isPC || isAdaptador) ? 'none' : '';
  if (lblEditMac.style.display === 'none') { try { const eMac = document.getElementById('editDeviceMac'); if (eMac) eMac.value = ''; } catch(e){} }

  // IP: show for devices that connect to network but hide for Celular and PC (keep for Tablet, Laptop, Router, Switch, Impresora, VoIP)
  const lblEditIp = document.getElementById('labelEditIp');
  lblEditIp.style.display = (isCelular || isTablet || isRouter || isSwitch || isLaptop || isImpresora || isVoip || isPC) ? '' : 'none';
  if (lblEditIp.style.display === 'none') { try { const eIp = document.getElementById('editDeviceIp'); if (eIp) eIp.value = 'N/A'; } catch(e){} }
  
  // UPS fields: show only for UPS
  const upsFieldsEdit = document.getElementById('upsFieldsEditDevice');
  if (upsFieldsEdit) {
    upsFieldsEdit.style.display = isUPS ? '' : 'none';
  }
  
  // Color: show for all devices
  document.getElementById('labelEditColor').style.display = '';
  
  // Tamaño (Screen size): show for celular, tablet, monitor, laptop and NOT for impresora, voip, periféricos, adaptador
  const showTamano = (isCelular || isTablet || isMonitor || isLaptop) ? '' : 'none';
  document.getElementById('labelEditTamano').style.display = showTamano;
  
  // Cargador/Adaptador AC: show for all devices EXCEPT Adaptador
  document.getElementById('labelEditDeviceCargador').style.display = isAdaptador ? 'none' : '';
  
  // Observaciones: show for all
  document.getElementById('labelEditObservaciones').style.display = '';
  
  // Extensión VoIP: show only for teléfono voip
  document.getElementById('labelEditExtension').style.display = isVoip ? '' : 'none';
  
  // Fecha obtención: show for all
  document.getElementById('labelEditFechaObt').style.display = '';
  
  // Estado: show only for Impresora (permitir que admin/operador cambien entre Sin asignar, En reparación, Uso general)
  document.getElementById('labelEditDeviceEstado').style.display = isImpresora ? '' : 'none';
}

// Open new device modal and initialize field visibility
function openNewDeviceModal() {
  openModal('modalNewDevice');
  // Reset form and toggle fields
  document.getElementById('formNewDevice').reset();
  document.getElementById('selectTipoNew').value = '';
  document.getElementById('checkImei2').checked = false;
  document.getElementById('labelNewImei2').style.display = 'none';
  // reset tinta tracking
  try { const chkT = document.getElementById('checkTintaTracking'); if (chkT) chkT.checked = false; const contT = document.getElementById('containerTintaDetalle'); if (contT) contT.style.display = 'none'; } catch(e) {}
  toggleDispositivoFields();
  // Preselect estado as 'Sin asignar' by default
  const newEstado = document.getElementById('newDeviceEstado');
  if (newEstado) newEstado.value = '0';
  
  // Set default empresa to PROIMA
  const radioPROIMA = document.getElementById('radioEmpresaPROIMA');
  if (radioPROIMA) radioPROIMA.checked = true;
  
  // Hide device info section until all 3 fields (tipo, marca, modelo) are selected
  checkDeviceInfoVisibility();
  
  // Fetch and populate next available IP
  fetch('/devices/next-ip')
    .then(response => response.json())
    .then(data => {
      const ipInput = document.querySelector('input[name="ip_asignada"]');
      try {
        const lbl = document.getElementById('labelNewIp');
        const visible = lbl && lbl.style.display !== 'none';
        if (ipInput && data.next_ip && visible) {
          ipInput.value = data.next_ip;
        }
      } catch(e) { if (ipInput && data.next_ip) { ipInput.value = data.next_ip; } }
    })
    .catch(err => console.error('Error fetching next IP:', err));

  // Ensure N/A checkbox is unchecked and IP input enabled when opening modal
  try {
    const chk = document.getElementById('checkIpNA');
    const ipInput = document.querySelector('input[name="ip_asignada"]');
    if (chk) {
      chk.checked = false;
      // attach handler once
      if (!chk._bound) {
        chk.addEventListener('change', function(){
          try {
            const formEl = document.getElementById('formNewDevice');
            let hidden = document.getElementById('ip_asignada_hidden');
            if (chk.checked) {
              if (ipInput) { ipInput.value = 'N/A'; ipInput.disabled = true; }
              if (!hidden && formEl) {
                hidden = document.createElement('input'); hidden.type = 'hidden'; hidden.id = 'ip_asignada_hidden'; hidden.name = 'ip_asignada'; formEl.appendChild(hidden);
              }
              if (hidden) hidden.value = 'N/A';
            } else {
              if (ipInput) { ipInput.disabled = false; }
              if (hidden && hidden.parentNode) hidden.parentNode.removeChild(hidden);
              // repopulate with next available ip
              if (ipInput) {
                fetch('/devices/next-ip')
                  .then(r => r.json())
                  .then(d => { if (d && d.next_ip) ipInput.value = d.next_ip; })
                  .catch(()=>{});
              }
            }
          } catch(e) { console.warn('error toggling N/A checkbox', e); }
        });
        chk._bound = true;
      }
    }
    if (ipInput) ipInput.disabled = false;
  } catch(e) {}
  
  // Generar identificador inicial con PROIMA por defecto
  updateIdentificador();
}

// Función para actualizar el identificador basado en empresa y tipo
async function updateIdentificador() {
  const empresaRadio = document.querySelector('input[name="empresa"]:checked');
  const tipoSelect = document.getElementById('selectTipoNew');
  const identificadorInput = document.getElementById('newIdentificador');
  
  if (!empresaRadio || !identificadorInput) return;
  
  const empresa = empresaRadio.value;
  const tipo = tipoSelect ? tipoSelect.value : '';
  
  if (!empresa) {
    identificadorInput.value = '';
    return;
  }
  
  // Si no hay tipo, generar con XXX como placeholder
  if (!tipo) {
    try {
      const prefijo = empresa === 'PROIMA' ? 'PRO' : 'ELM';
      const patronBase = `${prefijo}-%`;
      
      const resp = await fetch(`/devices/next-identifier?empresa=${empresa}&tipo=laptop`);
      const data = await resp.json();
      
      if (resp.ok && data.success && data.identifier) {
        // Reemplazar el acrónimo específico con XXX
        const partes = data.identifier.split('-');
        if (partes.length === 3) {
          identificadorInput.value = `${partes[0]}-XXX-${partes[2]}`;
          identificadorInput.readOnly = false;
          identificadorInput.style.backgroundColor = '';
        }
      }
    } catch (err) {
      console.error('Error fetching identifier placeholder:', err);
    }
    return;
  }
  
  try {
    const resp = await fetch(`/devices/next-identifier?empresa=${empresa}&tipo=${encodeURIComponent(tipo)}`);
    const data = await resp.json();
    
    if (resp.ok && data.success && data.identifier) {
      identificadorInput.value = data.identifier;
      // Permitir edición manual
      identificadorInput.readOnly = false;
      identificadorInput.style.backgroundColor = '';
    } else {
      console.error('Error obteniendo identificador:', data.message);
    }
  } catch (err) {
    console.error('Error fetching next identifier:', err);
  }
}

// edit modal removed — edit-related listeners removed

// edit save handler removed

// finalize-assignment controls removed (were part of edit modal)

// Recargar tabla de dispositivos SIN recargar la página
async function reloadDevicesTable() {
  try {
    const table = document.querySelector('#devicesTable');
    if (table) showTableLoader(table.parentElement || table);
    
    // Construir URL con parámetros de ordenamiento si existen
    let url = '/devices/ui/tbody';
    if (window.__devicesSortField && window.__devicesSortDir) {
      url += `?sort=${encodeURIComponent(window.__devicesSortField)}&dir=${encodeURIComponent(window.__devicesSortDir)}`;
    }
    
    const response = await fetch(url);
    if (!response.ok) throw new Error('Error al cargar dispositivos');
    
    const html = await response.text();
    const tbody = document.querySelector('#devicesTable tbody');
    if (tbody) {
      if (typeof window.safeSetHTML === 'function') {
        window.safeSetHTML(tbody, html);
      } else {
        tbody.innerHTML = html;
      }
    }
    
    if (table) hideTableLoader(table.parentElement || table);
  } catch (err) {
    console.error('Error recargando tabla:', err);
    const table = document.querySelector('#devicesTable');
    if (table) hideTableLoader(table.parentElement || table);
  }
}

window.__devicesSortField = null;
window.__devicesSortDir = null; // 'asc' or 'desc'

function toggleSort(field) {
  if (!field) return;
  if (window.__devicesSortField === field) {
    // toggle dir
    window.__devicesSortDir = window.__devicesSortDir === 'asc' ? 'desc' : 'asc';
  } else {
    window.__devicesSortField = field;
    window.__devicesSortDir = 'asc';
  }
  // update indicators: show only the active header's icon and set rotation
  document.querySelectorAll('.sort-icon').forEach(el => { el.classList.remove('active'); el.style.transform = 'rotate(0deg)'; });
  const id = `sortIndicator_${field}`;
  const el = document.getElementById(id);
  if (el) {
    el.classList.add('active');
    el.style.transform = window.__devicesSortDir === 'asc' ? 'rotate(180deg)' : 'rotate(0deg)';
  }
  // reload table
  if (typeof reloadDevicesTable === 'function') reloadDevicesTable();
}

// Initialize shared sorting for devices table and wire Actions to clear sorting + reload
document.addEventListener('DOMContentLoaded', () => {
  try { initTableSorting('#devicesTable', { iconPrefix: 'sortIndicator_', clientSide: false }); } catch(e) {}
  try {
    const table = document.getElementById('devicesTable');
    // When user clicks a header, keep server-side sorting in sync by reloading with params
    if (table && !table._serverSyncBound) {
      table.addEventListener('click', (ev) => {
        try {
          const th = ev.target.closest('th[data-sortable]');
          if (!th) return;
          // Determine field clicked and toggle direction for server-side sort
          const field = th.getAttribute('data-sortable');
          if (!field) return;
          // If currently sorting by this field, toggle dir; otherwise start asc
          if (window.__devicesSortField === field) {
            window.__devicesSortDir = (window.__devicesSortDir === 'asc') ? 'desc' : 'asc';
          } else {
            window.__devicesSortField = field;
            window.__devicesSortDir = 'asc';
          }
          
          // Update sort icons to show active state
          try {
            document.querySelectorAll('.sort-icon').forEach(el => { 
              el.classList.remove('active'); 
              el.style.transform = 'rotate(0deg)'; 
            });
            const iconId = 'sortIndicator_' + field;
            const icon = document.getElementById(iconId);
            if (icon) { 
              icon.classList.add('active'); 
              icon.style.transform = (window.__devicesSortDir === 'asc') ? 'rotate(0deg)' : 'rotate(180deg)'; 
            }
          } catch(e) { console.warn('Error updating sort icons', e); }
          
          // trigger server reload so subsequent operations respect server ordering
          if (typeof reloadDevicesTable === 'function') reloadDevicesTable();
        } catch(e) { /* ignore */ }
      });
      table._serverSyncBound = true;
    }
    // Actions header: reset sort/filters to default when clicked
    const thActions = document.getElementById('thActions');
    if (thActions && !thActions._boundReset) {
      thActions.style.cursor = 'pointer';
      thActions.addEventListener('click', () => {
        try { const t = document.getElementById('devicesTable'); if (t && typeof t.clearSorting === 'function') t.clearSorting(); } catch(e) {}
        // clear shared search state if helper exists
        try { if (typeof window.clearGlobalTableSearch === 'function') { window.clearGlobalTableSearch(); } } catch(e) {}
        try { const p = document.getElementById('devicesPageSearch'); if (p) p.value = ''; } catch(e) {}
        // clear server-side sort state and reload
        try { window.__devicesSortField = null; window.__devicesSortDir = null; } catch(e) {}
        if (typeof reloadDevicesTable === 'function') reloadDevicesTable();
      });
      thActions._boundReset = true;
    }
    // Actions header for celulares table: reset sort/filters when clicked
    const thActionsCelulares = document.getElementById('thActionsCelulares');
    if (thActionsCelulares && !thActionsCelulares._boundReset) {
      thActionsCelulares.style.cursor = 'pointer';
      thActionsCelulares.addEventListener('click', () => {
        try { const t = document.getElementById('celularesTable'); if (t && typeof t.clearSorting === 'function') t.clearSorting(); } catch(e) {}
        // clear shared search state if helper exists
        try { if (typeof window.clearGlobalTableSearch === 'function') { window.clearGlobalTableSearch(); } } catch(e) {}
        try { const p = document.getElementById('devicesPageSearch'); if (p) p.value = ''; } catch(e) {}
      });
      thActionsCelulares._boundReset = true;
    }
  } catch(e) {}
});

// Manejar visibilidad de campos requeridos según tipo de dispositivo seleccionado
// Agrupaciones de tipos para uso local (sin refactorizar el resto del código)
const TIPOS_DISPOSITIVOS = ['Laptop', 'PC', 'Celular', 'Tablet'];
const TIPOS_PERIFERICO = ['Monitor', 'Impresora', 'Telefono VoIP', 'Teclado', 'Mouse', 'Auriculares'];
const TIPOS_RED = ['Router', 'Switch'];
const TIPOS_MOVILES = ['Celular', 'Tablet', 'PC'];

const selectTipoNewEl = document.getElementById('selectTipoNew');
if (selectTipoNewEl) {
  selectTipoNewEl.addEventListener('change', function() {
    const esPeriferico = TIPOS_PERIFERICO.includes(this.value);
    const esCelular = TIPOS_MOVILES.includes(this.value);
    // Keep only the truly required field toggled here (numero_serie).
    // IMEI is required for celular/tablet, MAC and IP and 'tiene cargador' must remain optional per requirements.
    const numeroSerieEl = document.querySelector('input[name="numero_serie"]');
    if (numeroSerieEl) numeroSerieEl.required = true; // always required in the form

    // IMEI: required for celular and tablet
    const imeiInput = document.querySelector('input[name="imei"]');
    if (imeiInput) {
      imeiInput.required = esCelular;
    }

    // IMEI2: only required when device is NOT a peripheral and the 'has 2 IMEI' checkbox is checked
    const imei2Input = document.querySelector('input[name="imei2"]');
    const imei2Check = document.getElementById('checkImei2');
    if (imei2Input) {
      imei2Input.required = !esPeriferico && (!!imei2Check && imei2Check.checked);
    }
    // Ensure the checkbox itself is never required (it only toggles IMEI2)
    if (imei2Check) imei2Check.required = false;
    
    // Toggle field visibility based on device type
    toggleDispositivoFields();
    
    // Check if all 3 fields are selected to show device info
    checkDeviceInfoVisibility();
    
    // Mostrar/Ocultar opción "Uso General" solo para Impresoras
    const estadoUsoGeneral = document.getElementById('newEstadoUsoGeneral');
    const estadoSelect = document.getElementById('newDeviceEstado');
    if (estadoUsoGeneral && estadoSelect) {
      const esImpresora = this.value === 'Impresora';
      estadoUsoGeneral.style.display = esImpresora ? '' : 'none';
      // Si no es impresora y se había seleccionado "Uso General", resetea a "Sin asignar"
      if (!esImpresora && estadoSelect.value === '4') {
        estadoSelect.value = '0';
      }
    }
  });
}

// Event listener for edit device tipo change
const editDeviceTipoEl = document.getElementById('editDeviceTipo');
if (editDeviceTipoEl) {
  editDeviceTipoEl.addEventListener('change', function() {
    toggleEditDispositivoFields();
  });
}

// Global table search/filter is provided by base.html


// Initialize IMEI2 visibility/required state on load to avoid hidden required inputs
document.addEventListener('DOMContentLoaded', () => {
  const chk = document.getElementById('checkImei2');
  if (chk) {
    // ensure unchecked by default
    chk.checked = false;
  }
  // ensure toggle function applies initial state
  if (typeof toggleImei2Field === 'function') toggleImei2Field();
  // initialize tinta tracking checkbox state
  try {
    const chkT = document.getElementById('checkTintaTracking'); if (chkT) chkT.checked = false;
    if (typeof toggleTintaTrackingField === 'function') toggleTintaTrackingField();
    // ensure the label is hidden until device type reveals it
    const lblT = document.getElementById('labelNewTintaTracking'); if (lblT) lblT.style.display = 'none';
  } catch(e) {}
});

// Tamaño manual removido - ahora usa modal

// Manejar envío de formulario de nuevo dispositivo sin reload
async function processNewDeviceForm() {
  const formData = new FormData(document.getElementById('formNewDevice'));

  // Validate fecha_obt is present and not future (required)
  try {
    const fechaEl = document.getElementById('newDeviceFechaObtencion');
    const fechaVal = fechaEl ? (fechaEl.value || '') : '';
    if (!fechaVal) {
      if (fechaEl) {
        try { fechaEl.setCustomValidity('Ingrese una fecha de obtención'); fechaEl.reportValidity(); } catch(e){}
      }
      return;
    }
    // Check not future - use string comparison to avoid timezone issues
    const today = new Date();
    const todayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
    if (fechaVal > todayStr) {
      openModal('modalFechaFutura');
      return;
    }
  } catch (e) { /* ignore date validation errors */ }
  
  // Limpiar IP para dispositivos que no usan IP (solo periféricos y adaptadores)
  const tipo = (formData.get('categoria') || '').toLowerCase();
  if (['teclado', 'mouse', 'auriculares', 'monitor', 'ups', 'adaptador'].includes(tipo)) {
    formData.set('ip_asignada', '');
  }

  // Validar que el número de serie no esté duplicado
  try {
    const numeroSerie = (formData.get('numero_serie') || '').toString().trim().toUpperCase();
    if (numeroSerie) {
      const checkResp = await fetch('/devices/check-serial', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'same-origin',
        body: JSON.stringify({ numero_serie: numeroSerie })
      });
      if (checkResp.ok) {
        const checkData = await checkResp.json().catch(() => ({}));
        if (checkData.exists) {
          const msgEl = document.getElementById('serieDuplicadaMessage');
          if (msgEl) {
            const dev = checkData.device || {};
            msgEl.textContent = `El número de serie "${numeroSerie}" ya está asignado a ${dev.categoria || 'un dispositivo'} ${dev.nombre_marca || ''} ${dev.nombre_modelo || ''}.`;
          }
          openModal('modalSerieDuplicada');
          return;
        }
      }
    }
  } catch (e) {
    console.error('Error validando número de serie:', e);
  }

  // Validate identifier uniqueness before submitting
  try {
    const identifierVal = (formData.get('identificador') || '').trim();
    if (identifierVal) {
      const chkIdent = await fetch('/devices/check-identifier', { 
        method: 'POST', 
        headers: {'Content-Type':'application/json'}, 
        credentials: 'same-origin', 
        body: JSON.stringify({ identifier: identifierVal }) 
      });
      if (chkIdent.ok) {
        const chkData = await chkIdent.json().catch(()=>({}));
        if (chkData.exists) {
          const dev = chkData.device || {};
          openGlobalMessageModal('error', 'Error', `El identificador "${identifierVal}" ya está asignado a otro dispositivo (${dev.categoria || 'dispositivo'}).`);
          return;
        }
      }
    }
  } catch (e) {
    console.error('Identifier check failed', e);
  }

  // Validate IP uniqueness before submitting
  try {
    let ipVal = (formData.get('ip_asignada') || '').trim();
    // If placeholder '192.168.0.0' is present, clear it. If value is 'N/A', skip validation but
    // keep the 'N/A' value in the FormData so backend receives it.
    if (ipVal === '192.168.0.0') { ipVal = ''; formData.set('ip_asignada', ''); }
    // If user explicitly chose 'N/A', skip format validation but keep the 'N/A' value in the FormData
    if ((ipVal || '').toString().toUpperCase() === 'N/A') { ipVal = ''; }
    // Clear any previous inline error
    const newIpErrEl = document.getElementById('newIpError'); if (newIpErrEl) { newIpErrEl.textContent = ''; newIpErrEl.style.display = 'none'; }
    if (ipVal) {
      // Validar formato de IP
      if (!isValidIpFormat(ipVal)) {
        const newIpInput = document.querySelector('input[name="ip_asignada"]');
        if (newIpInput) {
          newIpInput.setCustomValidity('Formato de IP inválido. Debe ser XXX.XXX.XXX.XXX (cada número entre 0-255)');
          newIpInput.reportValidity();
        }
        if (newIpErrEl) {
          newIpErrEl.textContent = 'Formato de IP inválido. Debe ser XXX.XXX.XXX.XXX (cada número entre 0-255)';
          newIpErrEl.style.display = 'block';
        }
        return;
      }
      
      const chk = await fetch('/devices/check-ip', { method: 'POST', headers: {'Content-Type':'application/json'}, credentials: 'same-origin', body: JSON.stringify({ ip: ipVal }) });
      if (chk.ok) {
        const chkData = await chk.json().catch(()=>({}));
        if (chkData.exists) {
          // Show conflict modal with details
          const dev = chkData.device || {};
          const msgEl = document.getElementById('ipConflictMessage');
          if (msgEl) msgEl.textContent = `La dirección IP (${ipVal}) ya está asignada a ${dev.categoria || ''} ${dev.nombre_marca || ''} ${dev.nombre_modelo || ''}`;
          // store pending operation data
          window.__pendingNewDeviceForm = formData;
          window.__pendingNewDeviceIp = ipVal;
          window.__pendingNewDeviceConflictOwner = dev;
          openModal('modalIpConflict');
          return; // pause submission until user decides
        }
      }
    }
  } catch (e) {
    console.error('IP check failed', e);
  }
  
    try {
      // Ensure any previous custom validity is cleared before final submit
      try { const newIpInput = document.querySelector('input[name="ip_asignada"]'); if (newIpInput) { newIpInput.setCustomValidity(''); try { newIpInput.reportValidity(); } catch(e){} } } catch(e){}
      const resp = await fetch('/devices/new', { method: 'POST', body: formData, credentials: 'same-origin' });
      const data = await resp.json().catch(() => ({}));

      // Backend indicates success via data.success. Treat any non-success as failure even if HTTP 200.
      if (data && data.success) {
        const newDeviceId = data.device_id || data.id_dispositivo;
        
        // Si hay componentes seleccionados, copiarlos al nuevo dispositivo
        if (window.__selectedDeviceComponents && window.__selectedDeviceComponents.length > 0 && newDeviceId) {
          try {
            const copyResp = await fetch(`/devices/${newDeviceId}/copy-components`, {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              credentials: 'same-origin',
              body: JSON.stringify({ componentes: window.__selectedDeviceComponents })
            });
            
            if (!copyResp.ok) {
              console.error('Error copying components');
            }
          } catch (err) {
            console.error('Error copying components:', err);
          }
          
          // Limpiar variable temporal
          window.__selectedDeviceComponents = null;
        }
        
        closeModal('modalNewDevice');
        document.getElementById('formNewDevice').reset();
        if (typeof reloadDevicesTable === 'function') await reloadDevicesTable();
        openGlobalSuccessModal(data.message || 'Dispositivo creado exitosamente');
        return;
      }

      // If backend returns conflict details, mark inputs and show error
      const conflictFields = (data && data.conflicts) ? data.conflicts : null;
      const conflictList = [];
      const markInvalid = (selector, message) => {
        const el = document.querySelector(selector);
        if (!el) return;
        try { el.classList.add('input-error'); el.setCustomValidity(message); try { el.reportValidity(); } catch(e){} } catch(e) {}
        try { const _clear = function(){ el.classList.remove('input-error'); el.setCustomValidity(''); el.removeEventListener('input', _clear); }; el.addEventListener('input', _clear); } catch(e) {}
      };

      if (conflictFields && typeof conflictFields === 'object') {
        if (conflictFields.identificador) { conflictList.push('identificador'); markInvalid('input[name="identificador"], #newIdentificador', 'Este identificador ya existe'); }
        if (conflictFields.numero_serie) { conflictList.push('número de serie'); markInvalid('input[name="numero_serie"]', 'Este número de serie ya existe'); }
        if (conflictFields.imei) { conflictList.push('IMEI'); markInvalid('input[name="imei"]', 'Este IMEI ya existe'); }
      } else if (data && data.message) {
        // fallback: try to parse message text for known keywords
        const msgLower = (data.message || '').toLowerCase();
        if (msgLower.includes('identificador')) { conflictList.push('identificador'); markInvalid('input[name="identificador"], #newIdentificador', 'Este identificador ya existe'); }
        if (msgLower.includes('numero') && msgLower.includes('serie')) { conflictList.push('número de serie'); markInvalid('input[name="numero_serie"]', 'Este número de serie ya existe'); }
        if (msgLower.includes('imei')) { conflictList.push('IMEI'); markInvalid('input[name="imei"]', 'Este IMEI ya existe'); }
      }

      if (conflictList.length) {
        openGlobalMessageModal('error', 'Datos duplicados', `El/Los siguiente(s) valor(es) ya existen:\n\n${conflictList.join('\n')}\n\nPor favor, verifica los datos ingresados.`);
      } else {
        // Determinar tipo de error específico
        const msg = data.message || 'No se pudo crear el dispositivo';
        let errorTitle = 'Error al crear dispositivo';
        let errorDetail = msg;
        
        if (msg.toLowerCase().includes('modelo')) {
          errorTitle = 'Error: Modelo requerido';
          errorDetail = 'Debe seleccionar un modelo válido para continuar.';
        } else if (msg.toLowerCase().includes('marca')) {
          errorTitle = 'Error: Marca requerida';
          errorDetail = 'Debe seleccionar una marca válida para continuar.';
        } else if (msg.toLowerCase().includes('numero') && msg.toLowerCase().includes('serie')) {
          errorTitle = 'Error: Número de serie';
          errorDetail = 'El número de serie ingresado ya existe o no es válido.';
        } else if (msg.toLowerCase().includes('ip')) {
          errorTitle = 'Error: Dirección IP';
          errorDetail = 'La dirección IP ingresada ya está en uso o no es válida.';
        } else if (msg.toLowerCase().includes('imei')) {
          errorTitle = 'Error: IMEI duplicado';
          errorDetail = 'El IMEI ingresado ya está registrado en otro dispositivo.';
        } else if (msg.toLowerCase().includes('identificador')) {
          errorTitle = 'Error: Identificador duplicado';
          errorDetail = 'El identificador ingresado ya está en uso por otro dispositivo.';
        }
        
        openGlobalMessageModal('error', errorTitle, errorDetail);
      }

    } catch (err) {
      console.error('Error al guardar dispositivo:', err);
      const errorMsg = err.message || 'Ocurrió un error inesperado';
      let errorTitle = 'Error de conexión';
      let errorDetail = 'No se pudo conectar con el servidor. Verifica tu conexión e intenta nuevamente.';
      
      if (errorMsg.toLowerCase().includes('network') || errorMsg.toLowerCase().includes('fetch')) {
        errorTitle = 'Error de red';
        errorDetail = 'No se pudo establecer conexión con el servidor. Verifica tu conexión a internet.';
      } else if (errorMsg.toLowerCase().includes('timeout')) {
        errorTitle = 'Tiempo de espera agotado';
        errorDetail = 'La operación tardó demasiado tiempo. Intenta nuevamente.';
      } else if (errorMsg) {
        errorTitle = 'Error inesperado';
        errorDetail = errorMsg;
      }
      
      openGlobalMessageModal('error', errorTitle, errorDetail);
    }
}

// submit handler kept for keyboard submit: prevent default and call process function
document.getElementById('formNewDevice').addEventListener('submit', async (e) => { e.preventDefault(); await processNewDeviceForm(); });

// click handler for the new-device save button to bypass browser pre-validation
try {
  const btnSaveNew = document.getElementById('btnSaveNewDevice');
  if (btnSaveNew) btnSaveNew.addEventListener('click', async () => { await processNewDeviceForm(); });
} catch(e) {}

/* ---- */

let currentDeviceForComponents = null;
    let currentDeviceTypeForComponents = null;
    let modelCreatedFromComponent = false; // flag used when opening new-model modal from components
    let modelCreatedFromEditComponent = false; // flag used when opening new-model modal from edit-component modal

    // Open quick-new-model modal from Components modal context
    async function openNewModeloQuickFromComponents(){
      // Determine origin: edit modal or components modal
      const editMarcaEl = document.getElementById('editCompMarca');
      const compMarcaEl = document.getElementById('compMarca');
      let selectedMarca = null;
      // If edit modal is active and editMarca exists, open from edit-component
      const editModal = document.getElementById('modalEditComponente');
      if (editMarcaEl && editModal && editModal.classList.contains('active')) {
        modelCreatedFromEditComponent = true;
        modelCreatedFromComponent = false;
        selectedMarca = editMarcaEl.value || null;
      } else {
        modelCreatedFromComponent = true;
        modelCreatedFromEditComponent = false;
        selectedMarca = compMarcaEl ? (compMarcaEl.value || null) : null;
      }
      await populateSelectMarcaNew(selectedMarca);
      // Ensure tipo is preselected if device type is known
      const tipoSel = document.getElementById('selectTipoNew');
      if (tipoSel && currentDeviceTypeForComponents) tipoSel.value = currentDeviceTypeForComponents;
      
      // Si estamos editando un componente CPU, preseleccionar categoría CPU
      if (modelCreatedFromEditComponent) {
        const tipoComp = document.getElementById('editCompTipo')?.value || '';
        if (tipoComp.toUpperCase() === 'CPU') {
          const catSel = document.getElementById('selectTipoNew');
          if (catSel) catSel.value = 'CPU';
        }
      }
      
      openModal('modalNewModeloQuick');
    }

    async function populateCompModelos(){
      const sel = document.getElementById('compModelo');
      if (!sel) return;
      sel.innerHTML = '<option value="">-- Cargando modelos --</option>';
      try {
        const resp = await fetch('/devices/modelo/?estado=2');
        const data = await resp.json().catch(()=>[]);
        const marcaSel = document.getElementById('compMarca')?.value || '';
        const modelos = Array.isArray(data) ? data : [];
        const filtered = marcaSel ? modelos.filter(m => String(m.fk_id_marca) === String(marcaSel)) : modelos;
        sel.innerHTML = '<option value="">-- Seleccionar modelo --</option>' + filtered.map(m => `<option value="${String(m.id_modelo)}">${m.nombre_modelo}</option>`).join('');
      } catch (e){
        sel.innerHTML = '<option value="">-- Error cargando modelos --</option>';
      }
    }

    async function populateEditCompModelos(){
      const sel = document.getElementById('editCompModelo');
      if (!sel) return;
      sel.innerHTML = '<option value="">-- Cargando modelos --</option>';
      try {
        const tipo = document.getElementById('editCompTipo')?.value || '';
        let url = '/devices/modelo/?estado=2';
        if (tipo.toUpperCase() === 'CPU') {
          url += '&categoria=CPU';
        }
        const resp = await fetch(url);
        const data = await resp.json().catch(()=>[]);
        const marcaSel = document.getElementById('editCompMarca')?.value || '';
        const modelos = Array.isArray(data) ? data : [];
        const filtered = marcaSel ? modelos.filter(m => String(m.fk_id_marca) === String(marcaSel)) : modelos;
        sel.innerHTML = '<option value="">-- Seleccionar modelo --</option>' + filtered.map(m => `<option value="${String(m.id_modelo)}">${m.nombre_modelo}</option>`).join('');
      } catch (e){
        sel.innerHTML = '<option value="">-- Error cargando modelos --</option>';
      }
    }

    function openComponentsFromEdit(){
      const id = document.getElementById('editDeviceId')?.value;
      if (!id) return openGlobalMessageModal('error','Error','No hay dispositivo seleccionado');
      openComponentsModal(id);
    }

    /* openComponentsFromNew was intentionally removed; the Componentes button is hidden for the New Device modal. */

    async function openComponentsModal(deviceId){
      currentDeviceForComponents = deviceId;
      // fetch device for label
      try {
        const r = await fetch(`/devices/${deviceId}`);
        if (r.ok){
            const dev = await r.json();
            currentDeviceTypeForComponents = (dev.categoria || '').toString();
            document.getElementById('compDeviceLabel').textContent = (dev.categoria || '-') + ' - ' + (dev.nombre_marca || '-') + ' - ' + (dev.nombre_modelo || '-') + ' - ' + (dev.numero_serie || '-');
            // adjust modal width for celulares to avoid oversized modal
            try {
              const modalInner = document.querySelector('#modalComponents .modal');
              const devTypeLc = (currentDeviceTypeForComponents || '').toString();
              if (modalInner) {
                if (devTypeLc.includes('celular') || devTypeLc.includes('telefono') || devTypeLc.includes('mobile') || devTypeLc.includes('tablet')) {
                  modalInner.classList.add('modal--small-celular');
                } else {
                  modalInner.classList.remove('modal--small-celular');
                }
              }
            } catch(e) { /* ignore */ }
          }
      } catch(e){ console.warn('No se pudo cargar dispositivo para label', e); }

        await loadComponentsList(deviceId);
        // reset form
        document.getElementById('formNewComponente').reset();
        populateComponenteOptions();
        toggleComponenteFields();
        openModal('modalComponents');
    }

    async function loadComponentsList(deviceId){
      try {
        const resp = await fetch(`/devices/${deviceId}/componentes`);
        const j = await resp.json();
        const tbody = document.querySelector('#componentsTable tbody');
        tbody.innerHTML = '';
        if (!j.success) return;
        const isCel = (currentDeviceTypeForComponents || '').toString() === 'Celular' || (currentDeviceTypeForComponents || '').toString() === 'Tablet';
        // build header
        const thead = document.querySelector('#componentsTable thead');
        if (thead) {
            if (isCel) {
            // For celulares/tablet: show Tipo, Capacidad, Tipo memoria, Acciones
            thead.innerHTML = `<tr><th>Tipo</th><th>Capacidad (GB)</th><th>Tipo memoria</th><th>Acciones</th></tr>`;
            // hide add button and hide Tipo label/input in add form and hide legend
            try { document.getElementById('btnAddComponente').style.display = 'none'; } catch(e){}
            try { const compTipoEl = document.getElementById('compTipo'); if (compTipoEl && compTipoEl.closest) compTipoEl.closest('label').style.display = 'none'; } catch(e){}
            try { const legendNew = document.querySelector('#formNewComponente fieldset legend'); if (legendNew) legendNew.style.display = 'none'; } catch(e){}
            } else {
              thead.innerHTML = `<tr><th>Tipo</th><th>No. Serie</th><th>Frecuencia</th><th>Tipo memoria</th><th>Capacidad (GB)</th><th>Tipo disco</th><th>Marca</th><th>Acciones</th></tr>`;
            try { document.getElementById('btnAddComponente').style.display = ''; } catch(e){}
            try { const compTipoEl = document.getElementById('compTipo'); if (compTipoEl && compTipoEl.closest) compTipoEl.closest('label').style.display = ''; } catch(e){}
            try { const legendNew = document.querySelector('#formNewComponente fieldset legend'); if (legendNew) legendNew.style.display = ''; } catch(e){}
            }
        }

        (j.componentes || []).forEach(c => {
          // detect incomplete components to show an edit badge so user can find them
          const tipo = (c.tipo_componente || '').toString().toUpperCase();
          const isCpu = tipo === 'CPU' || tipo === '0';
          const isRam = tipo === 'RAM' || tipo === '1';
          const isDisco = tipo === 'DISCO' || tipo === '2';
          const nombreModelo = (c.nombre_modelo || '') .toString().trim();
          const fkModelo = (c.fk_id_modelo || '') .toString().trim();
          const nombreMarca = (c.nombre_marca || '') .toString().trim();
          const fkMarca = (c.fk_id_marca || '') .toString().trim();
          const sn = (c.numero_serie || '') .toString().trim();
          const capacidad = (c.capacidad || '') .toString().trim();
          const tipoMem = (c.tipo_memoria || '') .toString().trim();
          const tipoDisco = (c.tipo_disco || '') .toString().trim();
          let isIncomplete = false;
          // For celulares/tablet we show 'Incompleto' only when both Marca and Modelo are missing
          const hasMarca = !!(nombreMarca || fkMarca);
          const hasModelo = !!(nombreModelo || fkModelo);
          if (isCel) {
            // Mobile rules:
            // - RAM: requires capacidad AND tipo_memoria
            // - DISCO: requires capacidad
            // - CPU: keep badge when both Marca and Modelo are missing
            if (isRam) {
              if (!capacidad || !tipoMem) isIncomplete = true;
            } else if (isDisco) {
              if (!capacidad) isIncomplete = true;
            } else if (isCpu) {
              if (!hasMarca && !hasModelo) isIncomplete = true;
            } else {
              // generic fallback: if neither marca nor modelo
              if (!hasMarca && !hasModelo) isIncomplete = true;
            }
          } else {
            if (isCpu) {
              if ((!nombreModelo && !fkModelo) || !c.frecuencia) isIncomplete = true;
            } else if (isRam) {
              if (!capacidad) isIncomplete = true;
              // for non-celulares require more details
              if (!tipoMem || !c.tipo_modulo || !sn) isIncomplete = true;
            } else if (isDisco) {
              if (!capacidad) isIncomplete = true;
              if (!tipoDisco || !sn) isIncomplete = true;
            }
          }
          const incompleteHtml = isIncomplete ? '<span class="comp-incomplete" title="Componente incompleto — editar">Incompleto</span>' : '';
          let row = '';
            if (isCel) {
            // For celulares/tablet: show tipo, capacidad, tipo_memoria and actions
            row = `<tr>
              <td>${incompleteHtml}<span class="comp-type">${c.tipo_componente||''}</span></td>
              <td>${c.capacidad||''}</td>
              <td>${c.tipo_memoria||''}</td>
              <td class="table-actions">
                <button class="btn btn-primary btn-small" title="Editar componente" onclick="openEditComponenteModal(${c.id_componente})" style="width:44px;height:44px;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;">
                  <img src="/static/img/edi.png" alt="Editar" style="width:28px;height:28px;">
                </button>
              </td>
            </tr>`;
          } else {
            // Format frecuencia display
            let frecuenciaDisplay = '';
            try {
              if (c && c.frecuencia !== undefined && c.frecuencia !== null && String(c.frecuencia).trim() !== '') {
                // Backend stores CPU frequency as integer (e.g., 240 -> 2.40)
                const fnum = Number(c.frecuencia);
                const tipoComp = (c.tipo_componente || '').toString().toUpperCase();
                if (!isNaN(fnum) && (tipoComp === 'CPU' || tipoComp === '0' || c.tipo_componente === 0)) {
                  frecuenciaDisplay = `${(fnum/100).toFixed(2)} GHz`;
                } else if (!isNaN(fnum)) {
                  frecuenciaDisplay = `${fnum} MT/s`;
                } else {
                  // If backend returned formatted string already, show as-is
                  frecuenciaDisplay = String(c.frecuencia);
                }
              }
            } catch(e){ frecuenciaDisplay = c.frecuencia || ''; }

            // determine if CPU delete should be shown: hide delete for CPU on Laptop devices
            const isLaptopDevice = (currentDeviceTypeForComponents || '').toString() === 'Laptop';

            row = `
              <tr>
                <td>${incompleteHtml}<span class="comp-type">${c.tipo_componente||''}</span></td>
                <td>${c.numero_serie||''}</td>
                <td>${frecuenciaDisplay||''}</td>
                <td>${c.tipo_memoria||''}</td>
                <td>${c.capacidad||''}</td>
                <td>${c.tipo_disco||''}</td>
                <td>${c.nombre_marca||c.fk_id_marca||''}</td>
                <td class="table-actions">
                  <button class="btn btn-primary btn-small" title="Editar componente" onclick="openEditComponenteModal(${c.id_componente})" style="width:44px;height:44px;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;">
                    <img src="/static/img/edi.png" alt="Editar" style="width:28px;height:28px;">
                  </button>
                  ${ ( (c.tipo_componente||'').toString().toUpperCase() === 'CPU' || (c.tipo_componente||'').toString() === '0') && isLaptopDevice ? '' : `
                  <button class="btn btn-danger btn-small" title="Eliminar componente" onclick="openDeleteComponenteModal(${c.id_componente})" style="width:44px;height:44px;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;">
                    <img src="/static/img/del.png" alt="Eliminar" style="width:28px;height:28px;">
                  </button>` }
                </td>
              </tr>
            `;
          }
          tbody.innerHTML += row;
        });
      } catch (e){ console.error('Error cargando componentes', e); }
    }

    document.getElementById('compTipo')?.addEventListener('change', toggleComponenteFields);
    document.getElementById('compMarca')?.addEventListener('change', populateCompModelos);

    function populateComponenteOptions(){
      const frec = document.getElementById('compFrecuencia');
      const tipoMem = document.getElementById('compTipoMemoria');
      if (!frec || !tipoMem) return;
      // clear
      frec.innerHTML = '<option value="">-- Seleccionar --</option>';
      tipoMem.innerHTML = '<option value="">-- Seleccionar --</option>';
      // common frequencies (MHz) - modern ranges (exclude very low legacy values)
      const frecs = [2400,2666,2933,3000,3200,3600,3733,4000,4266,4800,5200,5600];
      frecs.forEach(f=>{ const o=document.createElement('option'); o.value=f; o.textContent=f; frec.appendChild(o); });
      // memory types (LPDDR variants, DDR variants, plus common embedded storage types)
      const mems = ['LPDDR2','LPDDR4','LPDDR4X','LPDDR5','LPDDR5X','DDR3','DDR4','DDR5','eMMC','UFS'];
      mems.forEach(m=>{ const o=document.createElement('option'); o.value=m; o.textContent=m; tipoMem.appendChild(o); });
    }

    function toggleComponenteFields(){
      const tipo = (document.getElementById('compTipo')?.value||'').toUpperCase();
      const devType = (currentDeviceTypeForComponents || '').toString();
      const isRam = tipo === 'RAM';
      const isDisco = tipo === 'DISCO';
      const isCpu = tipo === 'CPU';
      const isLaptopOrDesktop = devType === 'Laptop' || devType === 'Notebook' || devType === 'Desktop' || devType === 'PC' || devType === 'Escritorio';
      const isCelular = devType === 'Celular' || devType === 'Tablet';
      // If device is celular/tablet, hide form only when not adding CPU
      try {
        const formNew = document.getElementById('formNewComponente');
        if (formNew) formNew.style.display = (isCelular && !isCpu) ? 'none' : '';
      } catch(e) {}
      if (isCelular && !isCpu) return;

      // Capacidad: ocultar cuando el tipo es CPU; mostrar para otros tipos cuando hay selección
      try {
        const labelCap = document.getElementById('labelCapacidad');
        const capEl = document.getElementById('compCapacidad');
        const shouldShowCap = (tipo && !isCpu);
        if (labelCap) labelCap.style.display = shouldShowCap ? '' : 'none';
        if (capEl) {
          if (!shouldShowCap) { capEl.value = ''; capEl.disabled = true; }
          else { capEl.disabled = false; }
        }
      } catch(e){}

      // Frequency and factor: frequency visible for RAM and CPU; factor only for RAM
      try {
        document.getElementById('labelFrecuencia').style.display = (isRam || isCpu) ? '' : 'none';
        document.getElementById('labelTipoModulo').style.display = isRam ? '' : 'none';
      } catch(e) {}

      // Tipo memoria visible only for RAM
      const labelTipoMemEl = document.getElementById('labelTipoMemoria');
      if (labelTipoMemEl) labelTipoMemEl.style.display = isRam ? '' : 'none';

      // Tipo disco only for DISCO
      const labelTipoDiscoEl = document.getElementById('labelTipoDisco');
      if (labelTipoDiscoEl) labelTipoDiscoEl.style.display = isDisco ? '' : 'none';

      // If RAM selected, populate memory-specific options and adjust factor options by device
      if (isRam){
        const tipoMemEl = document.getElementById('compTipoMemoria');
        if (tipoMemEl) tipoMemEl.innerHTML = '<option value="">-- Seleccionar --</option>';
        const factorEl = document.getElementById('compTipoModulo');
        const capEl = document.getElementById('compCapacidad');
        if (isLaptopOrDesktop){
          ['DDR3','DDR4','DDR5'].forEach(m=>{ const o=document.createElement('option'); o.value=m; o.textContent=m; if (tipoMemEl) tipoMemEl.appendChild(o); });
          const frec = document.getElementById('compFrecuencia');
          if (frec) {
            frec.innerHTML = '<option value="">-- Seleccionar --</option>';
            [2400,2666,2933,3000,3200,3600,3733,4000,4266,4800,5200,5600].forEach(f=>{ const o=document.createElement('option'); o.value=f; o.textContent=f; frec.appendChild(o); });
          }
          if (capEl) { capEl.innerHTML = '<option value="">-- Seleccionar --</option>'; [4,8,16,32,64,128,256].forEach(c=>{ const o=document.createElement('option'); o.value=c; o.textContent=c; capEl.appendChild(o); }); }
          if (factorEl){ factorEl.innerHTML = '<option value="">-- Seleccionar --</option>'; ['SODIMM','DIMM'].forEach(ff=>{ const o=document.createElement('option'); o.value=ff; o.textContent=ff; factorEl.appendChild(o); }); }
        } else {
          if (capEl) capEl.innerHTML = '<option value="">-- Seleccionar --</option>';
          if (factorEl) factorEl.innerHTML = '<option value="">-- Seleccionar --</option>';
        }
      } else if (isDisco){
        // For disks, capacity options larger
        const cap = document.getElementById('compCapacidad');
        if (cap) { cap.innerHTML = '<option value="">-- Seleccionar --</option>'; [32,64,128,256,512,1024,2048].forEach(c=>{ const o=document.createElement('option'); o.value=c; o.textContent=c; cap.appendChild(o); }); }
        // Populate tipo disco for DISCO
        const tipoDiscoEl = document.getElementById('compTipoDisco');
        if (tipoDiscoEl) {
          tipoDiscoEl.innerHTML = '<option value="">-- Seleccionar --</option>';
          ['HDD','SSD SATA','SSD NVMe'].forEach(td=>{ const o=document.createElement('option'); o.value=td; o.textContent=td; tipoDiscoEl.appendChild(o); });
        }
        // show serial field for disks
        const serialElD = document.getElementById('labelCompSerial');
        if (serialElD) serialElD.style.display = '';
      } else {
        // no generic fallback: clear component-specific selects
        const frec = document.getElementById('compFrecuencia'); if (frec) frec.innerHTML = '<option value="">-- Seleccionar --</option>';
        const tipoMemEl2 = document.getElementById('compTipoMemoria'); if (tipoMemEl2) tipoMemEl2.innerHTML = '<option value="">-- Seleccionar --</option>';
        const cap2 = document.getElementById('compCapacidad'); if (cap2) cap2.innerHTML = '<option value="">-- Seleccionar --</option>';
        const factorEl2 = document.getElementById('compTipoModulo'); if (factorEl2) factorEl2.innerHTML = '<option value="">-- Seleccionar --</option>';
      }

      // CPU specific: show manual frequency input and limit tipo_memoria to Cache
      const compFreqSelect = document.getElementById('compFrecuencia');
      const compFreqInput = document.getElementById('compFrecuenciaInput');
      const tipoMemEl = document.getElementById('compTipoMemoria');
      const labelCompModeloEl = document.getElementById('labelCompModelo');
      const compModeloEl = document.getElementById('compModelo');
      if (isCpu) {
        if (compFreqSelect) { compFreqSelect.style.display = 'none'; compFreqSelect.name = ''; }
        if (compFreqInput) { compFreqInput.style.display = ''; compFreqInput.name = 'frecuencia'; }
        if (tipoMemEl) { tipoMemEl.innerHTML = '<option value="">-- Seleccionar --</option>'; const o=document.createElement('option'); o.value='Cache'; o.textContent='Cache'; tipoMemEl.appendChild(o); }
        if (labelCompModeloEl) { labelCompModeloEl.style.display = ''; }
        // populate modelos estado=2 for CPU
        if (compModeloEl) populateCompModelos();
        // Ensure the whole Frecuencia label is visible when using manual CPU input
        try { document.getElementById('labelFrecuencia').style.display = ''; } catch(e) {}
        // Ensure capacidad is cleared and disabled for CPU
        try { const capEl = document.getElementById('compCapacidad'); if (capEl) { capEl.value=''; capEl.disabled = true; } } catch(e) {}
        // enforce 3-digit numeric input for CPU frequency
        try { enforceThreeDigitsInput(compFreqInput); } catch(e) {}
      } else {
        if (compFreqSelect) { compFreqSelect.style.display = ''; compFreqSelect.name = 'frecuencia'; }
        if (compFreqInput) { compFreqInput.style.display = 'none'; compFreqInput.name = ''; }
        if (labelCompModeloEl) { labelCompModeloEl.style.display = 'none'; }
      }

      // Serial handling: show for RAM and DISCO where applicable, otherwise hide
      const serialEl = document.getElementById('labelCompSerial');
      if (serialEl) {
        if (isRam) serialEl.style.display = '';
        else if (!isDisco) {
          serialEl.style.display = 'none';
          const snInput = document.getElementById('compNumeroSerie'); if (snInput) snInput.value = '';
        } else {
          serialEl.style.display = '';
        }
      }

      // Marca: always show Marca for non-mobile devices
      try {
        const compMarcaEl = document.getElementById('compMarca');
        if (compMarcaEl && compMarcaEl.closest) {
          const marcaLabel = compMarcaEl.closest('label');
          if (marcaLabel) marcaLabel.style.display = '';
        }
        const editCompMarcaEl = document.getElementById('editCompMarca');
        if (editCompMarcaEl && editCompMarcaEl.closest) {
          const editMarcaLabel = editCompMarcaEl.closest('label');
          if (editMarcaLabel) editMarcaLabel.style.display = '';
        }
      } catch(e) {}

      // Ensure CPU option available for non-mobile
      try {
        const compTipoSel = document.getElementById('compTipo');
        if (compTipoSel) {
          const cpuOpt = compTipoSel.querySelector('option[value="CPU"]');
          if (cpuOpt) {
            // hide CPU option for Laptop devices (CPU is assigned at creation and must not be added/removed)
            if ((currentDeviceTypeForComponents || '').toString() === 'Laptop') {
              cpuOpt.style.display = 'none'; cpuOpt.disabled = true; if (compTipoSel.value === 'CPU') compTipoSel.value = ''; 
            } else {
              cpuOpt.style.display = ''; cpuOpt.disabled = false;
            }
          }
        }
      } catch(e) {}
    }

    async function submitNewComponente(){
      if (!currentDeviceForComponents) return openGlobalMessageModal('error','Error','No hay dispositivo seleccionado');
      const form = document.getElementById('formNewComponente');
      const tipo = document.getElementById('compTipo').value;
      const devType = (currentDeviceTypeForComponents || '').toString();
      const isCelular = devType === 'Celular' || devType === 'Tablet';
      
      // Check if celular already has this component type. For móviles/tablet, do not allow duplicates and block adding if any exists.
      if (isCelular && tipo) {
        try {
          const resp = await fetch(`/devices/${currentDeviceForComponents}/componentes`);
          const j = await resp.json();
          const existeComponente = (j.componentes || []).some(c => {
            const t = (c.tipo_componente || '').toString();
            return t === tipo || ( (t === '0' && tipo === 'CPU') || (t === '1' && tipo === 'RAM') || (t === '2' && tipo === 'DISCO') );
          });
          if (existeComponente) {
            return openGlobalMessageModal('error','Error','No se pueden agregar más componentes de este tipo en celulares/tablet');
          }
        } catch (e) {
          console.error('Error verificando componentes:', e);
        }
      }
      
      // Proceed with adding component
      await proceedAddComponente();
    }

    async function proceedAddComponente() {
      const form = document.getElementById('formNewComponente');

      const devKind = (currentDeviceTypeForComponents || '').toString().trim();
      // Client-side validations: ensure required fields per tipo
      const tipoVal = (document.getElementById('compTipo')?.value || '').toString().trim().toUpperCase();
      const isMobile = devKind === 'Celular' || devKind === 'Tablet';
      // Allow adding components on móviles only for CPU via UI
      if (isMobile && tipoVal !== 'CPU') return openGlobalMessageModal('error','Error','Sólo se permite agregar CPU en celulares/tablet desde la interfaz');
      if (!tipoVal) {
        return openGlobalMessageModal('error', 'Error', 'Seleccione el tipo de componente');
      }
      const compMarcaEl = document.getElementById('compMarca');
      // Device context: minimal variables - exact select values
      const isLaptop = devKind === 'Laptop';
      // Determine if Marca is required: CPU always; RAM/DISCO only on Laptop
      const requireMarca = (tipoVal === 'CPU') || ((tipoVal === 'RAM' || tipoVal === 'DISCO') && isLaptop);
      if (requireMarca && (!compMarcaEl || !compMarcaEl.value)) {
        return openGlobalMessageModal('error', 'Error', 'Seleccione la marca del componente');
      }
      // CPU: require modelo (if visible) and, for non-mobile devices, frecuencia
      if (tipoVal === 'CPU') {
        const labelCompModeloEl = document.getElementById('labelCompModelo');
        const compModeloEl = document.getElementById('compModelo');
        if (labelCompModeloEl && labelCompModeloEl.style.display !== 'none') {
          if (!compModeloEl || !compModeloEl.value) {
            return openGlobalMessageModal('error', 'Error', 'Seleccione el modelo para CPU');
          }
        }
        const compFreqInput = document.getElementById('compFrecuenciaInput');
        const compFreqSelect = document.getElementById('compFrecuencia');
        // Only require frequency for CPU on non-mobile devices
        if (!isMobile) {
          if (compFreqInput && compFreqInput.style.display !== 'none') {
            if (!compFreqInput.value || String(compFreqInput.value).trim() === '') {
              return openGlobalMessageModal('error', 'Error', 'Ingrese la frecuencia para CPU');
            }
          } else if (compFreqSelect && compFreqSelect.style.display !== 'none') {
            if (!compFreqSelect.value) return openGlobalMessageModal('error', 'Error', 'Seleccione la frecuencia para CPU');
          }
        }
      }
      // RAM / DISCO: require capacidad
      if (tipoVal === 'RAM' || tipoVal === 'DISCO') {
        const capEl = document.getElementById('compCapacidad');
        if (!capEl || !capEl.value) {
          return openGlobalMessageModal('error', 'Error', 'Seleccione la capacidad (GB)');
        }
      }
      // Additional requirements for RAM on Laptop only
      if (tipoVal === 'RAM' && isLaptop) {
        const tipoMem = document.getElementById('compTipoMemoria');
        const frecInput = document.getElementById('compFrecuenciaInput');
        const frecSel = document.getElementById('compFrecuencia');
        const ff = document.getElementById('compTipoModulo');
        if (!tipoMem || !tipoMem.value) { return openGlobalMessageModal('error','Error','Seleccione el tipo de memoria'); }
        if (frecInput && frecInput.style.display !== 'none') { if (!frecInput.value || String(frecInput.value).trim()==='') { return openGlobalMessageModal('error','Error','Ingrese la frecuencia'); } }
        else if (frecSel && frecSel.style.display !== 'none') { if (!frecSel.value) { return openGlobalMessageModal('error','Error','Seleccione la frecuencia'); } }
        if (!ff || !ff.value) { return openGlobalMessageModal('error','Error','Seleccione el tipo de módulo'); }
        // Require serial number for RAM on Laptop
        const snRam = document.getElementById('compNumeroSerie');
        if (!snRam || !snRam.value) { return openGlobalMessageModal('error','Error','Ingrese el número de serie del módulo RAM'); }
        
        // Validar que el número de serie no esté duplicado en este dispositivo
        const snValueClean = (snRam.value || '').toString().trim().toUpperCase();
        try {
          const resp = await fetch(`/devices/${currentDeviceForComponents}/componentes`);
          const data = await resp.json();
          if (data.success && data.componentes) {
            const duplicado = data.componentes.some(c => 
              c.tipo_componente === 1 && // RAM
              (c.numero_serie || '').toString().trim().toUpperCase() === snValueClean
            );
            if (duplicado) {
              const msgEl = document.getElementById('serieDuplicadaMessage');
              if (msgEl) msgEl.textContent = `Ya existe un módulo RAM con el número de serie "${snValueClean}" en este dispositivo.`;
              openModal('modalSerieDuplicada');
              return;
            }
          }
        } catch(e) { console.warn('No se pudo validar serie duplicada', e); }
      }

      // DISCO: require capacidad; require tipo_disco and serial only for non-mobile devices
      if (tipoVal === 'DISCO') {
        const tipoDisco = document.getElementById('compTipoDisco');
        if (!isMobile && (!tipoDisco || !tipoDisco.value)) { return openGlobalMessageModal('error','Error','Seleccione el tipo de disco'); }
        if (!isMobile) {
          const sn = document.getElementById('compNumeroSerie');
          if (!sn || !sn.value) { return openGlobalMessageModal('error','Error','Ingrese el número de serie del disco'); }
          
          // Validar que el número de serie no esté duplicado en este dispositivo
          const snValueClean = (sn.value || '').toString().trim().toUpperCase();
          try {
            const resp = await fetch(`/devices/${currentDeviceForComponents}/componentes`);
            const data = await resp.json();
            if (data.success && data.componentes) {
              const duplicado = data.componentes.some(c => 
                c.tipo_componente === 2 && // DISCO
                (c.numero_serie || '').toString().trim().toUpperCase() === snValueClean
              );
              if (duplicado) {
                const msgEl = document.getElementById('serieDuplicadaMessage');
                if (msgEl) msgEl.textContent = `Ya existe un disco con el número de serie "${snValueClean}" en este dispositivo.`;
                openModal('modalSerieDuplicada');
                return;
              }
            }
          } catch(e) { console.warn('No se pudo validar serie duplicada', e); }
        }
      }

      const data = new FormData(form);
      // Normalize tipo_componente to numeric codes expected by backend: CPU=0, RAM=1, DISCO=2
      
      
      
      
      
      
      
      
      
      
      
      
      
      
      const tipoValNormalized = tipoVal;
      let tipoCode = '';
      if (tipoVal === 'CPU') tipoCode = '0';
      else if (tipoVal === 'RAM') tipoCode = '1';
      else if (tipoVal === 'DISCO') tipoCode = '2';
      // Set normalized value in form data (override existing)
      if (tipoCode !== '') data.set('tipo_componente', tipoCode);
      // If CPU, ensure capacidad is not submitted
      if (tipoCode === '0') {
        try { data.delete('capacidad'); } catch(e) {}
      }
      // For CPU, validate and normalize frequency format X.XX -> integer*100
      if (tipoCode === '0') {
        const compFreqInput = document.getElementById('compFrecuenciaInput');
        const compFreqSelect = document.getElementById('compFrecuencia');
        if (compFreqInput && compFreqInput.style.display !== 'none') {
          const raw = (compFreqInput.value || '').toString().trim();
          if (!/^[0-9][.,][0-9]{2}$/.test(raw)) {
            return openGlobalMessageModal('error', 'Error', 'Formato de frecuencia inválido. Debe ser X.XX (por ejemplo 2.42)');
          }
          const norm = raw.replace(',', '.');
          data.set('frecuencia', String(Math.round(Number(norm) * 100)));
        } else if (compFreqSelect && compFreqSelect.style.display !== 'none') {
          data.set('frecuencia', compFreqSelect.value || '');
        }
      }
      const serialInput = document.getElementById('compNumeroSerie');
      if (serialInput && serialInput.value) data.set('numero_serie', serialInput.value.trim());
      try {
        const resp = await fetch(`/devices/${currentDeviceForComponents}/componente/new`, {
          method: 'POST',
          body: data,
          credentials: 'same-origin'
        });
        const j = await resp.json().catch(()=>({}));
        if (resp.ok && j.success){
          closeModal('modalConfirmAddComponente');
          openGlobalSuccessModal(j.message || 'Componente agregado');
          await loadComponentsList(currentDeviceForComponents);
          form.reset();
          toggleComponenteFields();
        } else {
          openGlobalMessageModal('error','Error', j.message || 'No se pudo crear componente');
        }
      } catch (e){
        console.error('Error creando componente:', e);
        openGlobalMessageModal('error','Error','No se pudo crear componente');
      }
    }

    document.getElementById('confirmAddComponenteInput')?.addEventListener('input', (e) => {
      const btn = document.getElementById('confirmAddComponenteBtn');
      btn.disabled = e.target.value.trim() !== 'CONFIRMAR';
    });

    // ===== Funciones para editar y eliminar componentes =====
    // Mapeo de marcas por categoría (solo CPU con filtros específicos)
    const MARCAS_POR_CATEGORIA = {
      'CPU': ['Intel', 'AMD', 'Apple', 'Qualcomm', 'Samsung', 'MediaTek', 'Mediatek']
    };

    function filterMarcasForComponentType(tipoComponente) {
      const tipo = (tipoComponente || '').toString().toUpperCase();
      const marcaSelect = document.getElementById('editCompMarca');
      if (!marcaSelect) return;
      
      // Si es CPU, mostrar solo las marcas especificadas
      if (tipo === 'CPU') {
        const allowedMarcas = MARCAS_POR_CATEGORIA['CPU'] || [];
        const options = marcaSelect.querySelectorAll('option');
        options.forEach(opt => {
          if (opt.value === '') {
            opt.style.display = '';
          } else {
            const marcaName = opt.textContent || '';
            opt.style.display = allowedMarcas.includes(marcaName) ? '' : 'none';
          }
        });
      } else {
        // Para otros tipos, mostrar todas las marcas
        const options = marcaSelect.querySelectorAll('option');
        options.forEach(opt => {
          opt.style.display = '';
        });
      }
    }

    async function openEditComponenteModal(componenteId) {
      if (!componenteId) return openGlobalMessageModal('error', 'Error', 'ID de componente no válido');
      try {
        const resp = await fetch(`/devices/${currentDeviceForComponents}/componentes/${componenteId}`);
        if (!resp.ok) {
          const data = await resp.json().catch(() => ({}));
          return openGlobalMessageModal('error', 'Error', data.message || 'No se pudo cargar el componente');
        }
        const data = await resp.json();
        if (!data.success || !data.componente) {
          return openGlobalMessageModal('error', 'Error', 'Componente no encontrado');
        }
        
        const comp = data.componente;
        
        // Store values to restore after toggle
        const tipoRaw = (comp.tipo_componente !== undefined && comp.tipo_componente !== null) ? comp.tipo_componente : '';
        const tipoMap = (v) => {
          // normalize numeric codes (0=CPU,1=RAM,2=DISCO) or pass-through strings
          if (v === 0 || v === '0' || String(v).trim() === '0') return 'CPU';
          if (v === 1 || v === '1' || String(v).trim() === '1') return 'RAM';
          if (v === 2 || v === '2' || String(v).trim() === '2') return 'DISCO';
          return (String(v || '')).toUpperCase();
        };
        const valores = {
          tipo: tipoMap(tipoRaw),
          capacidad: comp.capacidad || '',
          numero_serie: comp.numero_serie || '',
          frecuencia: comp.frecuencia || '',
          tipo_memoria: comp.tipo_memoria || '',
          tipo_modulo: comp.tipo_modulo || '',
          tipo_disco: comp.tipo_disco || '',
          marca: comp.fk_id_marca || '',
          modelo: comp.fk_id_modelo || '',
          sistema_operativo: comp.observaciones || ''
        };
        
        document.getElementById('editComponenteId').value = componenteId;
        // store normalized tipo in hidden input so UI won't show a select
        const editTipoEl = document.getElementById('editCompTipo');
        if (editTipoEl) editTipoEl.value = valores.tipo;
        
        // Filtrar marcas según tipo de componente
        filterMarcasForComponentType(valores.tipo);
        
        // Trigger field toggle to show/hide based on selected type
        toggleEditComponenteFields();
        
        // Restore all values after toggle populates the fields (set both select and input for frecuencia)
        document.getElementById('editCompTipo').value = valores.tipo;
        document.getElementById('editCompCapacidad').value = valores.capacidad;
        document.getElementById('editCompNumeroSerie').value = valores.numero_serie;
        try {
          // Format frecuencia for display: if component type is CPU (stored as int*100), show as X.XX
          const rawFreq = valores.frecuencia;
          let displayFreq = '';
          try {
            if (rawFreq !== undefined && rawFreq !== null && String(rawFreq).trim() !== '') {
              const tipoUpper = (valores.tipo || '').toString().toUpperCase();
              const fnum = Number(rawFreq);
              if (!isNaN(fnum) && tipoUpper === 'CPU') {
                displayFreq = (fnum/100).toFixed(2);
              } else {
                displayFreq = String(rawFreq);
              }
            }
          } catch(e) { displayFreq = String(rawFreq || ''); }
          document.getElementById('editCompFrecuencia').value = valores.frecuencia;
          document.getElementById('editCompFrecuenciaInput').value = displayFreq;
        } catch(e){}
        document.getElementById('editCompTipoMemoria').value = valores.tipo_memoria;
        document.getElementById('editCompTipoModulo').value = valores.tipo_modulo;
        document.getElementById('editCompTipoDisco').value = valores.tipo_disco;
        document.getElementById('editCompSistemaOperativo').value = valores.sistema_operativo;
        document.getElementById('editCompMarca').value = valores.marca;
        // Populate modelos for edit modal (estado=2) and set selected modelo if available
        try {
          await populateEditCompModelos();
          const labelEditModelo = document.getElementById('labelEditModelo');
          // Always show modelo selector for CPU and try to prefill it
          if ((valores.tipo||'').toString().toUpperCase() === 'CPU') {
            if (labelEditModelo) labelEditModelo.style.display = '';
            const modeloEl = document.getElementById('editCompModelo');
            if (modeloEl) {
              const valStr = String(valores.modelo || '');
              if (valores.modelo) {
                const opt = modeloEl.querySelector(`option[value="${valStr}"]`);
                if (!opt) {
                  const txt = (data.componente && data.componente.nombre_modelo) ? data.componente.nombre_modelo : `Modelo ${valStr}`;
                  const newOpt = document.createElement('option');
                  newOpt.setAttribute('value', valStr);
                  newOpt.textContent = txt;
                  modeloEl.appendChild(newOpt);
                }
                modeloEl.value = valStr;
              } else {
                // No fk_id_modelo: if componente has nombre_modelo, show it as a placeholder option
                const nm = (data.componente && data.componente.nombre_modelo) ? data.componente.nombre_modelo : '';
                if (nm) {
                  let placeholder = modeloEl.querySelector('option[data-placeholder="1"]');
                  if (!placeholder) {
                    const newOpt = document.createElement('option');
                    newOpt.setAttribute('value', '');
                    newOpt.setAttribute('data-placeholder', '1');
                    newOpt.textContent = nm;
                    modeloEl.insertBefore(newOpt, modeloEl.firstChild);
                  } else {
                    placeholder.textContent = nm;
                  }
                  modeloEl.value = '';
                }
              }
            }
          } else {
            if (labelEditModelo) labelEditModelo.style.display = 'none';
          }
        } catch(e) {}
        
        // Ensure toggle uses current hidden tipo value
        try { document.getElementById('editCompTipo')?.removeEventListener('change', toggleEditComponenteFields); } catch(e){}
        try { document.getElementById('editCompTipo')?.addEventListener('change', toggleEditComponenteFields); } catch(e){}
        // Ensure marca change populates modelos in edit modal
        try {
          const editMarcaEl = document.getElementById('editCompMarca');
          if (editMarcaEl) {
            editMarcaEl.removeEventListener('change', populateEditCompModelos);
            editMarcaEl.addEventListener('change', populateEditCompModelos);
          }
        } catch(e) {}
        
        try { const legendEdit = document.querySelector('#formEditComponente fieldset legend'); if (legendEdit) legendEdit.style.display = 'none'; } catch(e) {}
        openModal('modalEditComponente', true);
      } catch (err) {
        console.error('Error cargando componente:', err);
        openGlobalMessageModal('error', 'Error', 'No se pudo cargar el componente');
      }
    }

    function toggleEditComponenteFields() {
      const tipo = document.getElementById('editCompTipo')?.value || '';
      const isRam = tipo.toUpperCase() === 'RAM';
      const isDisco = tipo.toUpperCase() === 'DISCO';
      const isCpu = tipo.toUpperCase() === 'CPU';
      const devType = (currentDeviceTypeForComponents || '').toString().toLowerCase();
      const isLaptopOrDesktop = devType.includes('laptop') || devType.includes('notebook') || devType.includes('desktop') || devType.includes('pc') || devType.includes('comput') || devType.includes('escritorio');
      const isCelular = devType === 'celular' || devType === 'tablet';
      
      // Capacidad visible only after tipo selected (but not for CPU)
      try {
        const labelEditCap = document.getElementById('labelEditCapacidad');
        const capEditEl = document.getElementById('editCompCapacidad');
        const shouldShowEditCap = tipo && !isCpu;
        if (labelEditCap) labelEditCap.style.display = shouldShowEditCap ? '' : 'none';
        if (capEditEl) {
          if (!shouldShowEditCap) { capEditEl.value = ''; capEditEl.disabled = true; }
          else { capEditEl.disabled = false; }
        }
      } catch(e){}
      
      // For celulares: do NOT show Sistema Operativo nor Frecuencia for CPU (mobiles don't need these fields)
      if (isCelular) {
        document.getElementById('labelEditFrecuencia').style.display = 'none';
        // Always hide tipo de módulo in edit modal for Celular/Tablet
        document.getElementById('labelEditTipoModulo').style.display = 'none';
      } else {
        document.getElementById('labelEditFrecuencia').style.display = (isRam || isCpu) ? '' : 'none';
        document.getElementById('labelEditTipoModulo').style.display = isRam ? '' : 'none';
        
        // Populate frecuencia for laptop/desktop RAM
        if (isRam) {
          const frecEl = document.getElementById('editCompFrecuencia');
          const currentFrecValue = frecEl.value;
          frecEl.innerHTML = '<option value="">-- Seleccionar --</option>';
          [2400,2666,2933,3000,3200,3600,3733,4000,4266,4800,5200,5600].forEach(f=>{ 
            const o=document.createElement('option'); 
            o.value=f; 
            o.textContent=f; 
            frecEl.appendChild(o); 
          });
          frecEl.value = currentFrecValue;
          
          // Populate tipo de módulo for laptop/desktop RAM
          const ffEl = document.getElementById('editCompTipoModulo');
          const currentFFValue = ffEl.value;
          ffEl.innerHTML = '<option value="">-- Seleccionar --</option>';
          ['DIMM','SODIMM'].forEach(ff=>{ 
            const o=document.createElement('option'); 
            o.value=ff; 
            o.textContent=ff; 
            ffEl.appendChild(o); 
          });
          ffEl.value = currentFFValue;
        }
      }
      
      // Tipo memoria visible only for RAM
      document.getElementById('labelEditTipoMemoria').style.display = isRam ? '' : 'none';
      // Sistema Operativo visible only for CPU on non-mobile devices
      document.getElementById('labelEditSistemaOperativo').style.display = (isCpu && !isCelular) ? '' : 'none';
      // Hide the whole 'Tipo' label/input for celulares/tablet in edit flow
      try { const editTipoEl = document.getElementById('editCompTipo'); if (editTipoEl && editTipoEl.closest) editTipoEl.closest('label').style.display = isCelular ? 'none' : ''; } catch(e) {}
      
      // Tipo disco only for DISCO and not for celulares
      document.getElementById('labelEditTipoDisco').style.display = (isDisco && !isCelular) ? '' : 'none';
      
      // Populate tipo disco for DISCO on non-celular
      if (isDisco && !isCelular) {
        const tipoDiscoEl = document.getElementById('editCompTipoDisco');
        const currentTipoDisco = tipoDiscoEl?.value || '';
        tipoDiscoEl.innerHTML = '<option value="">-- Seleccionar --</option>';
        ['HDD','SSD SATA','SSD NVMe'].forEach(td=>{ 
          const o=document.createElement('option'); 
          o.value=td; 
          o.textContent=td; 
          tipoDiscoEl.appendChild(o); 
        });
        tipoDiscoEl.value = currentTipoDisco;
      }
      
      // Serial: for DISCO (non-celular) and RAM (non-celular)
      document.getElementById('labelEditCompSerial').style.display = (!isCelular && (isRam || isDisco)) ? '' : 'none';

      // Marca: for celulares/tablet, RAM and DISCO should NOT request marca (edit flow)
      try {
        const editMarcaEl = document.getElementById('editCompMarca');
        if (editMarcaEl && editMarcaEl.closest) {
          const marcaLabelEdit = editMarcaEl.closest('label');
          if (marcaLabelEdit) {
            if ((isRam || isDisco) && isCelular) marcaLabelEdit.style.display = 'none';
            else marcaLabelEdit.style.display = '';
          }
        }
      } catch(e) {}

      // Do not hide CPU option for celulares/tablet — mobiles may have CPUs
      
      // Marca: hide for RAM or DISCO on celulares
      document.getElementById('labelEditMarca').style.display = ((isRam || isDisco) && isCelular) ? 'none' : '';
      
      // If RAM selected, populate memory-specific options based on device
      if (isRam) {
        const tipoMemEl = document.getElementById('editCompTipoMemoria');
        const currentTipoMemValue = tipoMemEl.value;
        tipoMemEl.innerHTML = '<option value="">-- Seleccionar --</option>';
        if (isCelular) {
          ['LPDDR3X','LPDDR4','LPDDR4X','LPDDR5','LPDDR5X'].forEach(m=>{ const o=document.createElement('option'); o.value=m; o.textContent=m; tipoMemEl.appendChild(o); });
        } else if (isLaptopOrDesktop) {
          ['DDR3','DDR4','DDR5'].forEach(m=>{ const o=document.createElement('option'); o.value=m; o.textContent=m; tipoMemEl.appendChild(o); });
        }
        tipoMemEl.value = currentTipoMemValue;
      }

      // CPU: show manual frequency input and set tipo_memoria to Cache
      const frecInp = document.getElementById('editCompFrecuencia');
      const frecText = document.getElementById('editCompFrecuenciaInput');
      const tipoMemEl2 = document.getElementById('editCompTipoMemoria');
      if (isCpu) {
        if (frecInp) { frecInp.style.display = 'none'; frecInp.name = ''; }
        if (frecText) { frecText.style.display = ''; frecText.name = 'frecuencia'; }
        if (tipoMemEl2) { tipoMemEl2.innerHTML = '<option value="">-- Seleccionar --</option>'; const o=document.createElement('option'); o.value='Cache'; o.textContent='Cache'; tipoMemEl2.appendChild(o); }
        // Ensure the edit modal shows the Frecuencia label too when CPU is selected
        try { if (!isCelular) document.getElementById('labelEditFrecuencia').style.display = ''; } catch(e) {}
        // Clear and disable capacidad in edit modal for CPU
        try { const capEdit = document.getElementById('editCompCapacidad'); if (capEdit) { capEdit.value=''; capEdit.disabled = true; } } catch(e) {}
        // Show modelo selector in edit modal for CPU
        try { const labelEditModelo = document.getElementById('labelEditModelo'); if (labelEditModelo) labelEditModelo.style.display = ''; try { populateEditCompModelos(); } catch(e){} } catch(e) {}
        // enforce 3-digit numeric input for edit modal CPU frequency
        try { enforceThreeDigitsInput(document.getElementById('editCompFrecuenciaInput')); } catch(e) {}
      } else {
        if (frecInp) { frecInp.style.display = ''; frecInp.name = 'frecuencia'; }
        if (frecText) { frecText.style.display = 'none'; frecText.name = ''; }
        // Hide modelo selector for non-CPU types
        try { const labelEditModelo = document.getElementById('labelEditModelo'); if (labelEditModelo) labelEditModelo.style.display = 'none'; } catch(e) {}
      }
      
      // Populate capacity options based on tipo and device
      if (tipo) {
        const capEl = document.getElementById('editCompCapacidad');
        const currentValue = capEl.value;
        capEl.innerHTML = '<option value="">-- Seleccionar --</option>';
        
        if (isRam) {
          if (isCelular) {
            [1,2,3,4,6,8,12,16,24,32,64].forEach(c=>{ const o=document.createElement('option'); o.value=c; o.textContent=c; capEl.appendChild(o); });
          } else if (isLaptopOrDesktop) {
            [4,8,16,32,64,128,256].forEach(c=>{ const o=document.createElement('option'); o.value=c; o.textContent=c; capEl.appendChild(o); });
          }
        } else if (isDisco) {
          [32,64,128,256,512,1024,2048].forEach(c=>{ const o=document.createElement('option'); o.value=c; o.textContent=c; capEl.appendChild(o); });
        }
        capEl.value = currentValue;
      }
    }

    async function submitEditComponente() {
      const btn = document.getElementById('btnSaveComponente');
      btn.disabled = true;
      btn.textContent = 'Guardando...';
      try {
        // Normalize tipo_componente to numeric codes: CPU=0, RAM=1, DISCO=2
        const tipoEditRaw = (document.getElementById('editCompTipo').value || '').toString().trim().toUpperCase();
        const devKind = (currentDeviceTypeForComponents || '').toString().trim();
        const isLaptop = devKind === 'Laptop';
        const isMobile = devKind === 'Celular' || devKind === 'Tablet';
        const componenteId = document.getElementById('editComponenteId').value;

        // ===== VALIDACIONES EN ORDEN SECUENCIAL (de arriba a abajo en la modal) =====

        // 1. MARCA (requerida para CPU y para RAM/DISCO en Laptop)
        const editMarcaEl = document.getElementById('editCompMarca');
        const requireEditMarca = (tipoEditRaw === 'CPU') || ((tipoEditRaw === 'RAM' || tipoEditRaw === 'DISCO') && isLaptop);
        if (requireEditMarca && (!editMarcaEl || !editMarcaEl.value)) {
          openGlobalMessageModal('error', 'Error', 'Seleccione la marca del componente');
          return;
        }

        // 2. MODELO (solo para CPU, requerido)
        if (tipoEditRaw === 'CPU') {
          const modeloEl = document.getElementById('editCompModelo');
          if (!modeloEl || !modeloEl.value) {
            openGlobalMessageModal('error', 'Error', 'Seleccione el modelo para CPU');
            return;
          }
        }

        // 3. NÚMERO DE SERIE (requerido para RAM y DISCO en Laptop)
        const snEl = document.getElementById('editCompNumeroSerie');
        if ((tipoEditRaw === 'RAM' || tipoEditRaw === 'DISCO') && isLaptop) {
          if (!snEl || !snEl.value) {
            const tipo = tipoEditRaw === 'RAM' ? 'módulo RAM' : 'disco';
            openGlobalMessageModal('error', 'Error', `Ingrese el número de serie del ${tipo}`);
            return;
          }

          // Validar que no sea duplicado
          const snValueClean = (snEl.value || '').toString().trim().toUpperCase();
          try {
            const resp = await fetch(`/devices/${currentDeviceForComponents}/componentes`);
            const data = await resp.json();
            if (data.success && data.componentes) {
              const tipoCode = tipoEditRaw === 'RAM' ? 1 : 2;
              const currentCompId = String(componenteId).trim();
              const duplicado = data.componentes.some(c => {
                const cId = String(c.id_componente || '').trim();
                const cSerie = (c.numero_serie || '').toString().trim().toUpperCase();
                return cId !== currentCompId && 
                       c.tipo_componente === tipoCode && 
                       cSerie === snValueClean;
              });
              if (duplicado) {
                const tipo = tipoEditRaw === 'RAM' ? 'RAM' : 'disco';
                const msgEl = document.getElementById('serieDuplicadaMessage');
                if (msgEl) msgEl.textContent = `Ya existe un ${tipo} con el número de serie "${snValueClean}" en este dispositivo.`;
                openModal('modalSerieDuplicada');
                return;
              }
            }
          } catch(e) { console.warn('No se pudo validar serie duplicada', e); }
        }

        // 4. CAPACIDAD (requerida para RAM y DISCO)
        if (tipoEditRaw === 'RAM' || tipoEditRaw === 'DISCO') {
          const cap = document.getElementById('editCompCapacidad');
          if (!cap || !cap.value) {
            openGlobalMessageModal('error', 'Error', 'Seleccione la capacidad (GB)');
            return;
          }
        }

        // 5. FRECUENCIA (requerida para CPU en non-mobile y RAM en Laptop)
        if ((tipoEditRaw === 'CPU' && !isMobile) || (tipoEditRaw === 'RAM' && isLaptop)) {
          const frecInput = document.getElementById('editCompFrecuenciaInput');
          const frecSel = document.getElementById('editCompFrecuencia');
          if (frecInput && frecInput.style.display !== 'none') {
            if (!frecInput.value || String(frecInput.value).trim() === '') {
              openGlobalMessageModal('error', 'Error', 'Ingrese la frecuencia');
              return;
            }
          } else if (frecSel && frecSel.style.display !== 'none') {
            if (!frecSel.value) {
              openGlobalMessageModal('error', 'Error', 'Seleccione la frecuencia');
              return;
            }
          }
        }

        // 6. TIPO DE MEMORIA (requerida para RAM en Laptop)
        if (tipoEditRaw === 'RAM' && isLaptop) {
          const tipoMem = document.getElementById('editCompTipoMemoria');
          if (!tipoMem || !tipoMem.value) {
            openGlobalMessageModal('error', 'Error', 'Seleccione el tipo de memoria');
            return;
          }
        }

        // 7. TIPO DE MÓDULO (requerido para RAM en Laptop)
        if (tipoEditRaw === 'RAM' && isLaptop) {
          const ff = document.getElementById('editCompTipoModulo');
          if (!ff || !ff.value) {
            openGlobalMessageModal('error', 'Error', 'Seleccione el tipo de módulo');
            return;
          }
        }

        // 8. TIPO DE DISCO (requerida para DISCO en Laptop)
        if (tipoEditRaw === 'DISCO' && isLaptop) {
          const tipoDisco = document.getElementById('editCompTipoDisco');
          if (!tipoDisco || !tipoDisco.value) {
            openGlobalMessageModal('error', 'Error', 'Seleccione el tipo de disco');
            return;
          }
        }

        // ===== CONSTRUCCIÓN DEL PAYLOAD =====
        let tipoEditCode = null;
        if (tipoEditRaw === 'CPU') tipoEditCode = 0;
        else if (tipoEditRaw === 'RAM') tipoEditCode = 1;
        else if (tipoEditRaw === 'DISCO') tipoEditCode = 2;

        const payload = {
          tipo_componente: tipoEditCode,
          capacidad: (tipoEditCode === 0) ? null : (document.getElementById('editCompCapacidad').value || null),
          numero_serie: document.getElementById('editCompNumeroSerie').value || null,
          observaciones: (tipoEditCode === 0) ? (document.getElementById('editCompSistemaOperativo').value || null) : null,
          frecuencia: (function(){
            const fi = document.getElementById('editCompFrecuenciaInput');
            const fs = document.getElementById('editCompFrecuencia');
            try {
              if (fi && fi.style.display !== 'none') {
                const raw = (fi.value || '').toString().trim();
                if (!raw) return null;
                if (!/^[0-9][.,][0-9]{2}$/.test(raw)) {
                  openGlobalMessageModal('error', 'Error', 'Formato de frecuencia inválido. Debe ser X.XX (por ejemplo 2.42)');
                  throw new Error('invalid-frequency-format');
                }
                const norm = raw.replace(',', '.');
                const intval = Math.round(Number(norm) * 100);
                return intval;
              } else if (fs && fs.style.display !== 'none') {
                return fs.value || null;
              }
            } catch (e) {
              throw e;
            }
            return null;
          })(),
          tipo_memoria: document.getElementById('editCompTipoMemoria').value || null,
          tipo_modulo: document.getElementById('editCompTipoModulo').value || null,
          tipo_disco: document.getElementById('editCompTipoDisco').value || null,
          fk_id_marca: document.getElementById('editCompMarca').value || null,
          fk_id_modelo: (() => { const m = document.getElementById('editCompModelo'); return m ? (m.value || null) : null; })()
        };
        
        const resp = await fetch(`/devices/${currentDeviceForComponents}/componentes/${componenteId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify(payload)
        });
        
        let data = {};
        try {
          data = await resp.json();
        } catch (e) {
          const text = await resp.text().catch(()=>null);
          console.error('Non-JSON response updating componente:', resp.status, text);
          openGlobalMessageModal('error','Error', `Error servidor (${resp.status})`);
          return;
        }

        if (resp.ok && data.success) {
          closeModal('modalEditComponente');
          await loadComponentsList(currentDeviceForComponents);
          openGlobalSuccessModal(data.message || 'Componente actualizado');
        } else {
          console.error('Error response updating componente:', resp.status, data);
          openGlobalMessageModal('error', 'Error', data.message || `No se pudo actualizar el componente (status ${resp.status})`);
        }
      } catch (err) {
        console.error('Error actualizando componente:', err);
        openGlobalMessageModal('error', 'Error', 'No se pudo actualizar el componente');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Guardar';
      }
    }

    // Utility: enforce frequency input in format X.XX (dot or comma). Shows error modal on invalid formats.
    function enforceThreeDigitsInput(el) {
      if (!el) return;
      try { el.setAttribute('maxlength', '4'); } catch(e) {}
      // Allow only digits and one dot or comma while typing
      el.addEventListener('input', function(e){
        let v = this.value || '';
        // remove any char except digits, dot or comma
        v = v.replace(/[^0-9.,]/g, '');
        // if more than one separator, keep first occurrence
        const firstSepIdx = Math.min(
          ...( [v.indexOf('.'), v.indexOf(',')].filter(i => i >= 0).length ? [v.indexOf('.')>=0?v.indexOf('.'):Infinity, v.indexOf(',')>=0?v.indexOf(','):Infinity] : [Infinity])
        );
        if (firstSepIdx !== Infinity) {
          const sep = v[firstSepIdx];
          const parts = v.split(/[.,]/);
          const left = parts.shift();
          const right = parts.join('');
          v = left + sep + right;
        }
        if (this.value !== v) this.value = v;
      });
      el.addEventListener('keydown', function(e){
        const allowed = ['Backspace','Tab','ArrowLeft','ArrowRight','Delete'];
        if (allowed.indexOf(e.key) !== -1) return;
        if (!/^[0-9]$/.test(e.key) && e.key !== '.' && e.key !== ',') e.preventDefault();
      });
      // On blur, validate exact format X.XX or X,XX (one digit before, two after)
      el.addEventListener('blur', function(){
        const v = (this.value || '').trim();
        if (!v) return;
        const valid = /^[0-9][.,][0-9]{2}$/.test(v);
        if (!valid) {
          openGlobalMessageModal('error', 'Formato inválido', 'La frecuencia debe tener el formato X.XX');
          try { this.focus(); } catch(e) {}
        } else {
          const norm = v.replace(',', '.');
          // keep consistent formatting
          try { this.value = Number(norm).toFixed(2); } catch(e) {}
        }
      });
    }

    async function openDeleteComponenteModal(componenteId) {
      if (!componenteId) return openGlobalMessageModal('error', 'Error', 'ID de componente no válido');
      window.pendingComponenteDelete = componenteId;
      // Try to fetch componente details to show in confirmation modal
      let itemName = 'componente';
      try {
        const respInfo = await fetch(`/devices/${currentDeviceForComponents}/componentes/${componenteId}`);
        if (respInfo.ok) {
          const j = await respInfo.json().catch(()=>null);
          if (j && j.success && j.componente) {
            const c = j.componente;
            const tipo = (c.tipo_componente || '').toString().toUpperCase();
            const marca = c.nombre_marca ? c.nombre_marca.toString().trim() : '';
            if (tipo === 'CPU') {
              const modelo = c.nombre_modelo ? c.nombre_modelo.toString().trim() : '';
              itemName = `${tipo}${marca ? ' ' + marca : ''}${modelo ? ' ' + modelo : ''}`.trim();
            } else if (tipo === 'RAM' || tipo === 'DISCO') {
              const capacidad = c.capacidad ? `${c.capacidad}GB` : '';
              itemName = `${tipo}${marca ? ' ' + marca : ''}${capacidad ? ' ' + capacidad : ''}`.trim();
            } else {
              // Generic fallback: show type and brand if available
              itemName = `${tipo}${marca ? ' ' + marca : ''}`.trim() || 'componente';
            }
          }
        }
      } catch (e) {
        console.debug('No se pudo obtener detalle del componente para el modal de borrado', e);
      }

      openGlobalDeleteModal(async () => {
        try {
          const resp = await fetch(`/devices/${currentDeviceForComponents}/componentes/${componenteId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
          });
          const data = await resp.json().catch(() => ({}));
          if (resp.ok && data.success) {
            closeGlobalDeleteModal();
            await loadComponentsList(currentDeviceForComponents);
            openGlobalSuccessModal(data.message || 'Componente eliminado');
          } else {
            openGlobalMessageModal('error', 'Error', data.message || 'No se pudo eliminar el componente');
          }
        } catch (err) {
          console.error('Error eliminando componente:', err);
          openGlobalMessageModal('error', 'Error', 'No se pudo eliminar el componente');
        }
      }, '¿Deseas eliminar este componente?', itemName);
    }

/* ---- */

// ===== GESTIÓN DE MARCAS =====
// marcasData, modelosData, openGestionarMarcasModelosModal already declared earlier

function cargarMarcas() {
  return fetch('/devices/marca/', { credentials: 'same-origin' })
    .then(r => r.json().catch(() => []))
    .then(data => {
      marcasData = data || [];
      const select = document.getElementById('selectMarcaGestion');
      if (select) {
        select.innerHTML = '<option value="">-- Selecciona una marca --</option>' +
          (Array.isArray(data) ? data.map(m => `<option value="${m.id_marca}">${m.nombre_marca}</option>`).join('') : '');
      }
      return marcasData;
    })
    .catch(() => {
      const select = document.getElementById('selectMarcaGestion');
      if (select) select.innerHTML = '<option value="">Error al cargar marcas</option>';
      return [];
    });
}

function mostrarBotonesMarca() {
  const select = document.getElementById('selectMarcaGestion');
  const botones = document.getElementById('botonesGestionMarcas');
  marcaActualSeleccionada = select.value ? parseInt(select.value) : null;
  botones.style.display = marcaActualSeleccionada ? 'flex' : 'none';
}

function editarMarcaModal() {
  if (!marcaActualSeleccionada) return;
  const marca = marcasData.find(m => m.id_marca === marcaActualSeleccionada);
  if (marca) {
    document.getElementById('editMarcaNombreInline').value = marca.nombre_marca;
    openModal('modalEditMarcaInline', true);
  }
}

function guardarMarcaEditada() {
  const nombre = document.getElementById('editMarcaNombreInline').value.trim();
  if (!nombre) {
    showModalMessage('Ingresa un nombre válido', 'error');
    return;
  }
  
  fetch(`/devices/marca/${marcaActualSeleccionada}`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({nombre_marca: nombre})
  })
  .then(r => r.json().catch(() => ({})))
  .then(data => {
    if (data && data.success) {
      closeModal('modalEditMarcaInline');
      // Actualizar dato en array sin recargar
      const marca = marcasData.find(m => m.id_marca === marcaActualSeleccionada);
      if (marca) marca.nombre_marca = nombre;
      // Actualizar select
      const select = document.getElementById('selectMarcaGestion');
      const option = select && select.querySelector(`option[value="${marcaActualSeleccionada}"]`);
      if (option) option.textContent = nombre;
      openGlobalSuccessModal(data.message || 'Se ha realizado con éxito');
    } else {
      const msg = data && (data.message || data.error) ? (data.message || data.error) : 'Error al actualizar';
      showModalMessage(msg, 'error');
    }
  })
  .catch(() => {
    showModalMessage('Error comunicando con el servidor', 'error');
  });
}

function eliminarMarcaModal() {
  if (!marcaActualSeleccionada) return;
  const marca = marcasData.find(m => m.id_marca === marcaActualSeleccionada);
  if (!marca) return;
  
  openGlobalDeleteModal(
    () => {
      fetch(`/devices/marca/${marcaActualSeleccionada}`, {method: 'DELETE'})
        .then(r => r.json())
        .then(data => {
          closeGlobalDeleteModal();
          if (data.success) {
            marcasData = marcasData.filter(m => m.id_marca !== marcaActualSeleccionada);
            const select = document.getElementById('selectMarcaGestion');
            const option = select.querySelector(`option[value="${marcaActualSeleccionada}"]`);
            if (option) option.remove();
            document.getElementById('selectMarcaGestion').value = '';
            document.getElementById('botonesGestionMarcas').style.display = 'none';
            openGlobalSuccessModal(data.message || 'Se ha realizado con éxito');
          } else {
            openGlobalErrorModal(data.message || 'Error al eliminar');
          }
        });
    },
    'Confirmar eliminación',
    marca.nombre_marca
  );
}

function cargarModelos() {
  fetch('/devices/modelo/')
    .then(r => r.json().catch(() => []))
    .then(data => {
      modelosData = data || [];
      const select = document.getElementById('selectModeloGestion');
      if (!select) return;
      // Cargar marcas si no están cargadas
      if (marcasData.length === 0) {
        cargarMarcasParaSelector();
      }
      select.innerHTML = '<option value="">-- Selecciona un modelo --</option>' +
        (Array.isArray(data) ? data.map(m => {
          const marca = marcasData.find(ma => ma.id_marca == m.fk_id_marca);
          return `<option value="${m.id_modelo}">${m.nombre_modelo} (${marca?.nombre_marca || '-'})</option>`;
        }).join('') : '');
    })
    .catch(() => {
      const select = document.getElementById('selectModeloGestion');
      if (select) select.innerHTML = '<option value="">Error al cargar modelos</option>';
    });
}

function cargarMarcasParaSelector() {
  fetch('/devices/marca/')
    .then(r => r.json().catch(() => []))
    .then(marcas => {
      marcasData = marcas || [];
      const select = document.getElementById('editModeloMarcaInline');
      if (select) {
        select.innerHTML = '<option value="">-- Selecciona marca --</option>' +
          (Array.isArray(marcas) ? marcas.map(m => `<option value="${m.id_marca}">${m.nombre_marca}</option>`).join('') : '');
      }
    })
    .catch(() => {
      // fail silently, UI will show empty selector
    });
}

function mostrarBotonesModelo() {
  const select = document.getElementById('selectModeloGestion');
  const botones = document.getElementById('botonesGestionModelos');
  modeloActualSeleccionado = select.value ? parseInt(select.value) : null;
  botones.style.display = modeloActualSeleccionado ? 'flex' : 'none';
}

function editarModeloModal() {
  if (!modeloActualSeleccionado) return;
  const modelo = modelosData.find(m => m.id_modelo === modeloActualSeleccionado);
  if (modelo) {
    document.getElementById('editModeloNombreInline').value = modelo.nombre_modelo;
    document.getElementById('editModeloMarcaInline').value = modelo.fk_id_marca;
    openModal('modalEditModeloInline', true);
  }
}

function guardarModeloEditado() {
  const nombre = document.getElementById('editModeloNombreInline').value.trim();
  const marca = document.getElementById('editModeloMarcaInline').value;
  const modelo = modelosData.find(m => m.id_modelo === modeloActualSeleccionado);
  
  if (!nombre || !marca || !modelo) {
    showModalMessage('Completa todos los campos', 'error');
    return;
  }
  
  fetch(`/devices/modelo/${modeloActualSeleccionado}`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      nombre_modelo: nombre,
      categoria: modelo.categoria,
      fk_id_marca: marca
    })
  })
  .then(r => r.json().catch(() => ({})))
  .then(data => {
    if (data && data.success) {
      closeModal('modalEditModeloInline');
      // Actualizar dato en array sin recargar
      modelo.nombre_modelo = nombre;
      modelo.fk_id_marca = parseInt(marca);
      // Actualizar select
      const select = document.getElementById('selectModeloGestion');
      const marcaNombre = marcasData.find(m => m.id_marca == marca)?.nombre_marca || '-';
      const option = select && select.querySelector(`option[value="${modeloActualSeleccionado}"]`);
      if (option) option.textContent = `${nombre} (${marcaNombre})`;
      openGlobalSuccessModal(data.message || 'Se ha realizado con éxito');
    } else {
      const msg = data && (data.message || data.error) ? (data.message || data.error) : 'Error al actualizar';
      showModalMessage(msg, 'error');
    }
  })
  .catch(() => {
    showModalMessage('Error comunicando con el servidor', 'error');
  });
}

function eliminarModeloModal() {
  if (!modeloActualSeleccionado) return;
  const modelo = modelosData.find(m => m.id_modelo === modeloActualSeleccionado);
  if (!modelo) return;
  
  openGlobalDeleteModal(
    () => {
      fetch(`/devices/modelo/${modeloActualSeleccionado}`, {method: 'DELETE'})
        .then(r => r.json())
        .then(data => {
          closeGlobalDeleteModal();
          if (data.success) {
            modelosData = modelosData.filter(m => m.id_modelo !== modeloActualSeleccionado);
            const select = document.getElementById('selectModeloGestion');
            const option = select.querySelector(`option[value="${modeloActualSeleccionado}"]`);
            if (option) option.remove();
            document.getElementById('selectModeloGestion').value = '';
            document.getElementById('botonesGestionModelos').style.display = 'none';
            openGlobalSuccessModal(data.message || 'Se ha realizado con éxito');
          } else {
            openGlobalErrorModal(data.message || 'Error al eliminar');
          }
        });
    },
    'Confirmar eliminación',
    modelo.nombre_modelo
  );
}

function guardarModeloInline() {
  const nombre = document.getElementById('newModeloNombreInline').value.trim();
  const marca = document.getElementById('newModeloMarcaInline').value;
  const tipo = document.getElementById('newModeloTipoInline').value;
  
  if (!nombre || !marca || !tipo) {
    showModalMessage('Completa todos los campos', 'error');
    return;
  }
  
  fetch('/devices/modelo/new', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      nombre_modelo: nombre,
      fk_id_marca: marca,
      categoria: tipo
    })
  })
  .then(r => r.json())
  .then(data => {
    if (data.success) {
      closeModal('modalNewModeloInline');
      document.getElementById('newModeloNombreInline').value = '';
      // Agregar nuevo modelo al array sin recargar
      const nuevoModelo = {
        id_modelo: data.id_modelo,
        nombre_modelo: nombre,
        fk_id_marca: marca,
        categoria: tipo,
        nombre_marca: marcasData.find(m => m.id_marca == marca)?.nombre_marca || '-'
      };
      modelosData.push(nuevoModelo);
      // Actualizar select
      const select = document.getElementById('selectModeloGestion');
      const option = document.createElement('option');
      option.value = nuevoModelo.id_modelo;
      option.textContent = `${nombre} (${nuevoModelo.nombre_marca})`;
      select.appendChild(option);
      openGlobalSuccessModal(data.message || 'Se ha realizado con éxito');
    } else {
      const msg = data.message || data.error || 'Error al crear';
      showModalMessage(msg, 'error');
    }
  });
}

// Crear marca rápida desde modal Nuevo Dispositivo
async function createNewMarcaFromDevice() {
  const nombre = document.getElementById('inputNewMarcaQuick').value.trim();
  if (!nombre) {
    showModalMessage('error', 'Error', 'Ingrese un nombre válido para la marca');
    return;
  }
  try {
    const resp = await fetch('/devices/marca/new', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ nombre_marca: nombre })
    });
    const data = await resp.json().catch(() => ({}));
    if (resp.ok && data.success) {
      // Cerrar modal y limpiar
      closeModal('modalNewMarcaQuick');
      document.getElementById('inputNewMarcaQuick').value = '';
      // Actualizar cache y selects
      const nuevo = { id_marca: data.id_marca, nombre_marca: nombre };
      marcasData.push(nuevo);
      const selNew = document.getElementById('selectMarcaNew');
      if (selNew) {
        const opt = document.createElement('option');
        opt.value = nuevo.id_marca;
        opt.textContent = nuevo.nombre_marca;
        selNew.appendChild(opt);
        // seleccionar la nueva marca para el dispositivo
        selNew.value = nuevo.id_marca;
      }
      // Also update marca select inside quick-new-model modal if present
      const selNewModelo = document.getElementById('selectMarcaNewModelo');
      if (selNewModelo) {
        const optM = document.createElement('option');
        optM.value = nuevo.id_marca;
        optM.textContent = nuevo.nombre_marca;
        selNewModelo.appendChild(optM);
        selNewModelo.value = nuevo.id_marca;
      }
      // También actualizar el select de Componentes si existe y seleccionarlo
      const selComp = document.getElementById('compMarca');
      if (selComp) {
        const optC = document.createElement('option');
        optC.value = nuevo.id_marca;
        optC.textContent = nuevo.nombre_marca;
        selComp.appendChild(optC);
        selComp.value = nuevo.id_marca;
      }
      // Also update edit component marca select and select it if present
      const editCompMarca = document.getElementById('editCompMarca');
      if (editCompMarca) {
        const optEC = document.createElement('option');
        optEC.value = nuevo.id_marca;
        optEC.textContent = nuevo.nombre_marca;
        editCompMarca.appendChild(optEC);
        editCompMarca.value = nuevo.id_marca;
        // trigger change so modelos are populated
        editCompMarca.dispatchEvent(new Event('change'));
      }
      const selGestion = document.getElementById('selectMarcaGestion');
      if (selGestion) {
        const opt2 = document.createElement('option');
        opt2.value = nuevo.id_marca;
        opt2.textContent = nuevo.nombre_marca;
        selGestion.appendChild(opt2);
      }
      const editMarcaSel = document.getElementById('editModeloMarcaInline');
      if (editMarcaSel) {
        const opt3 = document.createElement('option');
        opt3.value = nuevo.id_marca;
        opt3.textContent = nuevo.nombre_marca;
        editMarcaSel.appendChild(opt3);
      }
      // Actualizar select del modal de edición de dispositivo si está presente
      const editSelectMarca = document.getElementById('editSelectMarca');
      if (editSelectMarca) {
        const optE = document.createElement('option');
        optE.value = nuevo.id_marca;
        optE.textContent = nuevo.nombre_marca;
        editSelectMarca.appendChild(optE);
      }
      openGlobalSuccessModal(data.message || 'Marca creada');
    } else {
      const msg = data.message || data.error || 'No se pudo crear la marca';
      let errorTitle = 'Error al crear marca';
      let errorDetail = msg;
      
      if (msg.toLowerCase().includes('existe') || msg.toLowerCase().includes('duplicad')) {
        errorTitle = 'Marca duplicada';
        errorDetail = 'Ya existe una marca con este nombre.';
      } else if (msg.toLowerCase().includes('nombre') || msg.toLowerCase().includes('requerid')) {
        errorTitle = 'Nombre requerido';
        errorDetail = 'Debe ingresar un nombre v\u00e1lido para la marca.';
      } else if (msg.toLowerCase().includes('permiso')) {
        errorTitle = 'Permiso denegado';
        errorDetail = 'No tienes permisos para crear marcas.';
      }
      
      openGlobalMessageModal('error', errorTitle, errorDetail);
    }
  } catch (err) {
    console.error('Error creando marca:', err);
    openGlobalMessageModal('error', 'Error de conexi\u00f3n', 'No se pudo conectar con el servidor. Verifica tu conexi\u00f3n e intenta nuevamente.');
  }
}

// Crear modelo rápido desde modal Nuevo Dispositivo
async function createNewModeloFromDevice() {
  const nombre = document.getElementById('inputNewModeloQuickNombre').value.trim();
  const fkMarcaEl = document.getElementById('selectMarcaNewModelo');
  const fk_id_marca = fkMarcaEl ? fkMarcaEl.value : '';
  
  // Determinar el tipo: si viene desde edit component con CPU, usar 'CPU' automáticamente
  let tipo = '';
  if (modelCreatedFromEditComponent) {
    const tipoComp = document.getElementById('editCompTipo')?.value || '';
    if (tipoComp.toUpperCase() === 'CPU') {
      tipo = 'CPU';
    }
  } else if (modelCreatedFromComponent) {
    const tipoComp = document.getElementById('compTipo')?.value || '';
    if (tipoComp.toUpperCase() === 'CPU') {
      tipo = 'CPU';
    }
  }
  
  // Si no se asignó automáticamente, obtener del select
  if (!tipo) {
    const tipoEl = document.getElementById('selectTipoNew');
    tipo = tipoEl ? tipoEl.value : '';
  }

  if (!nombre) {
    showModalMessage('error', 'Error', 'Ingrese un nombre válido para el modelo');
    return;
  }
  if (!fk_id_marca) {
    showModalMessage('error', 'Error', 'Seleccione primero la marca asociada');
    return;
  }
  if (!tipo) {
    showModalMessage('error', 'Error', 'Seleccione primero el tipo de dispositivo');
    return;
  }

    try {
    const payload = { nombre_modelo: nombre, fk_id_marca: fk_id_marca, categoria: tipo };
    if (modelCreatedFromComponent || modelCreatedFromEditComponent) payload.estado = 2;
    const resp = await fetch('/devices/modelo/new', {
      method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await resp.json().catch(() => ({}));
    if (resp.ok && data.success) {
      closeModal('modalNewModeloQuick');
      document.getElementById('inputNewModeloQuickNombre').value = '';
      // Añadir al cache y selects
      const marcaNombre = marcasData.find(m => m.id_marca == fk_id_marca)?.nombre_marca || '-';
      const nuevo = {
        id_modelo: data.id_modelo,
        nombre_modelo: nombre,
        fk_id_marca: fk_id_marca,
        categoria: tipo,
        nombre_marca: marcaNombre
      };
      modelosData.push(nuevo);
      const selNew = document.getElementById('selectModeloNew');
      if (selNew) {
        const opt = document.createElement('option');
        opt.value = nuevo.id_modelo;
        opt.textContent = nombre;
        opt.setAttribute('data-tipo', tipo);
        selNew.appendChild(opt);
        // seleccionar el nuevo modelo automáticamente
        selNew.value = nuevo.id_modelo;
        // disparar change para autocompletar tipo
        selNew.dispatchEvent(new Event('change'));
      }
      const selGestion = document.getElementById('selectModeloGestion');
      if (selGestion) {
        const opt2 = document.createElement('option');
        opt2.value = nuevo.id_modelo;
        opt2.textContent = `${nombre} (${marcaNombre})`;
        selGestion.appendChild(opt2);
      }
      // If the model was created from components modal, also update the compModelo select and select it
      if (modelCreatedFromComponent) {
        const compSel = document.getElementById('compModelo');
        if (compSel) {
          const optC = document.createElement('option');
          optC.value = nuevo.id_modelo;
          optC.textContent = nombre;
          compSel.appendChild(optC);
          compSel.value = nuevo.id_modelo;
        }
        modelCreatedFromComponent = false;
      }
      // If the model was created from edit-component modal, update editCompModelo and select it
      if (modelCreatedFromEditComponent) {
        const editSel = document.getElementById('editCompModelo');
        if (editSel) {
          const optE = document.createElement('option');
          optE.value = nuevo.id_modelo;
          optE.textContent = nombre;
          editSel.appendChild(optE);
          editSel.value = nuevo.id_modelo;
        }
        // Also ensure the label is visible
        const labelEditModelo = document.getElementById('labelEditModelo');
        if (labelEditModelo) labelEditModelo.style.display = '';
        modelCreatedFromEditComponent = false;
      }
      openGlobalSuccessModal(data.message || 'Modelo creado');
    } else {
      const msg = data.message || data.error || 'No se pudo crear el modelo';
      let errorTitle = 'Error al crear modelo';
      let errorDetail = msg;
      
      if (msg.toLowerCase().includes('existe') || msg.toLowerCase().includes('duplicad')) {
        errorTitle = 'Modelo duplicado';
        errorDetail = 'Ya existe un modelo con este nombre para esta marca.';
      } else if (msg.toLowerCase().includes('nombre') || msg.toLowerCase().includes('requerid')) {
        errorTitle = 'Nombre requerido';
        errorDetail = 'Debe ingresar un nombre v\u00e1lido para el modelo.';
      } else if (msg.toLowerCase().includes('marca')) {
        errorTitle = 'Marca requerida';
        errorDetail = 'Debe seleccionar una marca antes de crear el modelo.';
      } else if (msg.toLowerCase().includes('permiso')) {
        errorTitle = 'Permiso denegado';
        errorDetail = 'No tienes permisos para crear modelos.';
      }
      
      openGlobalMessageModal('error', errorTitle, errorDetail);
    }
  } catch (err) {
    console.error('Error creando modelo:', err);
    openGlobalMessageModal('error', 'Error de conexi\u00f3n', 'No se pudo conectar con el servidor. Verifica tu conexi\u00f3n e intenta nuevamente.');
  }
}

function addNewTamanoToSelect() {
  const input = document.getElementById('inputNewTamanoQuick');
  if (!input) return;
  
  // Obtener solo dígitos (sin el punto)
  const raw = (input.value || '').replace(/\D/g, '');
  if (!raw || raw.length === 0) {
    openGlobalMessageModal('error', 'Campo requerido', 'Por favor ingrese un tamaño válido');
    return;
  }
  
  // Formatear para guardar con comillas
  let value = formatTamanoForSave(raw);
  
  // Agregar al select de nuevo dispositivo
  const selectNew = document.getElementById('newDeviceTamano');
  if (selectNew) {
    const existingOpt = Array.from(selectNew.options).find(opt => opt.value === value);
    if (!existingOpt) {
      const newOpt = document.createElement('option');
      newOpt.value = value;
      newOpt.textContent = value;
      selectNew.appendChild(newOpt);
    }
    selectNew.value = value;
  }
  
  // Agregar al select de editar dispositivo si existe
  const selectEdit = document.getElementById('editDeviceTamano');
  if (selectEdit) {
    const existingOptEdit = Array.from(selectEdit.options).find(opt => opt.value === value);
    if (!existingOptEdit) {
      const newOptEdit = document.createElement('option');
      newOptEdit.value = value;
      newOptEdit.textContent = value;
      selectEdit.appendChild(newOptEdit);
    }
  }
  
  closeModal('modalNewTamanoQuick');
  input.value = '';
}

// Formato de tamaño: XX.X automático (como identidad)
function formatTamanoDisplay(digits) {
  const d = (digits || '').replace(/\D/g, '').slice(0, 3);
  if (!d) return '';
  
  // Si tiene 3 dígitos: XX.X
  if (d.length === 3) {
    return d.slice(0, 2) + '.' + d.slice(2);
  }
  // Si tiene 2 o menos, devolver tal cual
  return d;
}

// Formato para guardar (agregar comillas)
function formatTamanoForSave(digits) {
  const d = (digits || '').replace(/\D/g, '').slice(0, 3);
  if (!d) return '';
  
  if (d.length === 3) {
    return d.slice(0, 2) + '.' + d.slice(2) + '"';
  }
  return d + '"';
}

function onTamanoInput(inputEl) {
  const raw = (inputEl.value || '').replace(/\D/g, '').slice(0, 3);
  inputEl.value = formatTamanoDisplay(raw);
}

// Formato automático para frecuencia X.XX
function formatFrecuenciaDisplay(value) {
  const digits = (value || '').replace(/\D/g, '').slice(0, 3);
  if (!digits) return '';
  
  // Si tiene 3 dígitos: X.XX
  if (digits.length === 3) {
    return digits.slice(0, 1) + '.' + digits.slice(1);
  }
  // Si tiene 2 dígitos: X.X
  if (digits.length === 2) {
    return digits.slice(0, 1) + '.' + digits.slice(1);
  }
  // Si tiene 1 dígito, devolver tal cual
  return digits;
}

function onFrecuenciaInput(inputEl) {
  const raw = (inputEl.value || '').replace(/\D/g, '').slice(0, 3);
  inputEl.value = formatFrecuenciaDisplay(raw);
}

// Validar formato de dirección IP
function isValidIpFormat(ip) {
  if (!ip || typeof ip !== 'string') return false;
  
  // Patrón: 4 octetos separados por puntos, cada octeto 0-255
  const parts = ip.trim().split('.');
  
  if (parts.length !== 4) return false;
  
  return parts.every(part => {
    // Verificar que sea un número
    if (!/^\d+$/.test(part)) return false;
    
    const num = parseInt(part, 10);
    
    // Verificar rango 0-255
    if (num < 0 || num > 255) return false;
    
    // Verificar que no tenga ceros a la izquierda (excepto "0" solo)
    if (part.length > 1 && part[0] === '0') return false;
    
    return true;
  });
}

function openModalNewModeloWithMarca() {
  // Obtener marca seleccionada en el formulario de nuevo dispositivo
  const selectMarcaNew = document.getElementById('selectMarcaNew');
  const marcaIdSeleccionada = selectMarcaNew ? selectMarcaNew.value : '';
  
  // Abrir el modal
  openModal('modalNewModeloQuick');
  
  // Pre-seleccionar la marca si hay una seleccionada
  if (marcaIdSeleccionada) {
    const selectMarcaModelo = document.getElementById('selectMarcaNewModelo');
    if (selectMarcaModelo) {
      selectMarcaModelo.value = marcaIdSeleccionada;
    }
  }
}

// Poblar select de marca para el modal rápido de nuevo modelo
async function populateSelectMarcaNew(selectedMarcaId) {
  // Asegurarse de tener marcas cargadas
  if (!marcasData || marcasData.length === 0) {
    await cargarMarcas();
  }
  const sel = document.getElementById('selectMarcaNewModelo');
  if (!sel) return;
  sel.innerHTML = '<option value="">-- Selecciona marca --</option>' + (marcasData.map(m => `<option value="${m.id_marca}">${m.nombre_marca}</option>`).join(''));
  if (selectedMarcaId) {
    sel.value = selectedMarcaId;
  } else {
    // si existe la marca seleccionada en el modal de gestión, usarla
    const mg = document.getElementById('selectMarcaGestion');
    if (mg && mg.value) sel.value = mg.value;
  }
}

// Abrir modal NewModeloQuick preseleccionando la marca actualmente seleccionada en la gestión
function openNewModeloQuickWithBrand() {
  (async () => {
    const mg = document.getElementById('selectMarcaGestion');
    const selected = mg && mg.value ? mg.value : null;
    await populateSelectMarcaNew(selected);
    openModal('modalNewModeloQuick');
  })();
}

// Peripherals UI/JS removed — endpoints have been deleted on the backend.

// Eliminada: la función para eliminar carpetas numeradas fue removida por solicitud.

// Check if localStorage flag is set to open new device modal
if(localStorage.getItem('openNewDeviceModal') === 'true'){
  openNewDeviceModal();
  localStorage.removeItem('openNewDeviceModal');
}

// Variable to track current view
let currentDeviceView = 'activos';

// Toggle between activos and eliminados views
function toggleEliminadosView() {
  const viewActivos = document.getElementById('viewActivos');
  const viewEliminados = document.getElementById('viewEliminados');
  if (!viewActivos || !viewEliminados) return;
  
  if (currentDeviceView === 'activos') {
    viewActivos.style.display = 'none';
    viewEliminados.style.display = 'block';
    currentDeviceView = 'eliminados';
    
    const btnVer = document.getElementById('btnVerEliminados');
    const btnVolver = document.getElementById('btnVolverActivos');
    if (btnVer) btnVer.style.display = 'none';
    if (btnVolver) btnVolver.style.display = 'inline-block';
    // Also hide the "Ver Celulares" control to avoid switching directly
    const btnVerCelulares = document.getElementById('btnVerCelulares');
    if (btnVerCelulares) btnVerCelulares.style.display = 'none';
    
    // Update header title
    try {
      const h1 = document.querySelector('.main-header h1');
      if (h1) h1.textContent = 'Dispositivos (Eliminados)';
    } catch(e) {}
    
    // Initialize sorting for deleted table
    try { initTableSorting('#deletedDevicesTable', { iconPrefix: 'sortIndicator_eliminados_' }); } catch(e) {}
  } else {
    viewActivos.style.display = 'block';
    viewEliminados.style.display = 'none';
    currentDeviceView = 'activos';
    
    const btnVer = document.getElementById('btnVerEliminados');
    const btnVolver = document.getElementById('btnVolverActivos');
    if (btnVer) btnVer.style.display = 'inline-block';
    if (btnVolver) btnVolver.style.display = 'none';
    // Restore visibility of "Ver Celulares" when returning to activos
    const btnVerCelulares2 = document.getElementById('btnVerCelulares');
    if (btnVerCelulares2) btnVerCelulares2.style.display = 'inline-block';
    
    // Restore header title
    try {
      const h1 = document.querySelector('.main-header h1');
      if (h1) h1.textContent = 'Dispositivos';
    } catch(e) {}
  }
  
  // Clear search
  try {
    const searchEl = document.getElementById('devicesPageSearch');
    if (searchEl) searchEl.value = '';
    if (typeof window.clearGlobalTableSearch === 'function') window.clearGlobalTableSearch();
  } catch(e) {}
}

// Toggle between activos and celulares views
function toggleCelularesView() {
  const viewActivos = document.getElementById('viewActivos');
  const viewCelulares = document.getElementById('viewCelulares');
  if (!viewActivos || !viewCelulares) return;
  
  if (currentDeviceView === 'activos') {
    viewActivos.style.display = 'none';
    viewCelulares.style.display = 'block';
    currentDeviceView = 'celulares';
    
    const btnVerEliminados = document.getElementById('btnVerEliminados');
    const btnVerCelulares = document.getElementById('btnVerCelulares');
    const btnVolver = document.getElementById('btnVolverCelulares');
    if (btnVerEliminados) btnVerEliminados.style.display = 'none';
    if (btnVerCelulares) btnVerCelulares.style.display = 'none';
    if (btnVolver) btnVolver.style.display = 'inline-block';
    
    // Update header title
    try {
      const h1 = document.querySelector('.main-header h1');
      if (h1) h1.textContent = 'Dispositivos (Celulares)';
    } catch(e) {}
    
    // Initialize sorting for celulares table
    try { initTableSorting('#celularesTable', { iconPrefix: 'sortIndicator_celulares_' }); } catch(e) {}
  } else {
    viewActivos.style.display = 'block';
    viewCelulares.style.display = 'none';
    currentDeviceView = 'activos';
    
    const btnVerEliminados = document.getElementById('btnVerEliminados');
    const btnVerCelulares = document.getElementById('btnVerCelulares');
    const btnVolver = document.getElementById('btnVolverCelulares');
    if (btnVerEliminados) btnVerEliminados.style.display = 'inline-block';
    if (btnVerCelulares) btnVerCelulares.style.display = 'inline-block';
    if (btnVolver) btnVolver.style.display = 'none';
    
    // Restore header title
    try {
      const h1 = document.querySelector('.main-header h1');
      if (h1) h1.textContent = 'Dispositivos';
    } catch(e) {}
  }
  
  // Clear search
  try {
    const searchEl = document.getElementById('devicesPageSearch');
    if (searchEl) searchEl.value = '';
    if (typeof window.clearGlobalTableSearch === 'function') window.clearGlobalTableSearch();
  } catch(e) {}
}

// Function to open restore modal for deleted device
let pendingRestoreId = null;
function openRestoreModal(deviceId, sn, marca, modelo) {
  pendingRestoreId = deviceId;
  document.getElementById('confirmRestoreSN').textContent = sn || '-';
  document.getElementById('confirmRestoreMarca').textContent = marca || '-';
  document.getElementById('confirmRestoreModelo').textContent = modelo || '-';
  openModal('modalConfirmRestore', true);
}

// Function to confirm and restore deleted device
async function confirmRestoreDevice() {
  if (!pendingRestoreId) return;
  const btn = document.getElementById('btnConfirmRestore');
  if (btn) { btn.disabled = true; btn.textContent = 'Restaurando...'; }
  try {
    const resp = await fetch(`/devices/deleted/${pendingRestoreId}/restore`, {
      method: 'POST',
      credentials: 'same-origin'
    });
    const data = await resp.json().catch(() => ({}));
    if (resp.ok && data.success) {
      closeModal('modalConfirmRestore');
      pendingRestoreId = null;
      openGlobalSuccessModal(data.message || 'Dispositivo restaurado correctamente');
      if (typeof reloadDevicesTable === 'function') await reloadDevicesTable();
    } else {
      const errorMsg = data.message || data.error || 'No se pudo restaurar el dispositivo';
      openGlobalMessageModal('error', 'Error al restaurar', errorMsg);
    }
  } catch (err) {
    console.error('Error restaurando dispositivo:', err);
    openGlobalMessageModal('error', 'Error de conexión', 'No se pudo conectar con el servidor');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Restaurar'; }
  }
}

// Function to show employee details in modal
async function showEmpleadoDetails(empleadoId) {
  if (!empleadoId) return;
  
  // Open modal and show loading state
  openModal('modalEmpleadoDetails', true);
  const contentDiv = document.getElementById('empleadoDetailsContent');
  contentDiv.innerHTML = `
    <div style="text-align:center; padding:20px;">
      <span class="spinner" style="display:inline-block;width:24px;height:24px;border:3px solid var(--text-gray);border-top-color:transparent;border-radius:50%;animation:spin 0.6s linear infinite;"></span>
      <p style="margin-top:12px; color:var(--text-gray);">Cargando datos...</p>
    </div>
  `;
  
  try {
    const resp = await fetch(`/devices/empleado/${empleadoId}`);
    if (!resp.ok) {
      throw new Error('No se pudo obtener los datos del empleado');
    }
    
    const empleado = await resp.json();
    
    // Build employee data display
    const nombre = empleado.nombre_completo || '-';
    const sucursal = empleado.sucursal || '-';
    const departamento = empleado.departamento || '-';
    const puesto = empleado.puesto || '-';
    const empresa = empleado.empresa || '-';
    
    contentDiv.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:16px;">
        <div style="border-left:4px solid #007bff; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Nombre Completo</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${nombre}</div>
        </div>
        <div style="border-left:4px solid #28a745; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Sucursal</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${sucursal}</div>
        </div>
        <div style="border-left:4px solid #ffc107; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Departamento</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${departamento}</div>
        </div>
        <div style="border-left:4px solid #17a2b8; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Puesto</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${puesto}</div>
        </div>
        <div style="border-left:4px solid #6f42c1; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Empresa</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${empresa}</div>
        </div>
      </div>
    `;
  } catch (err) {
    console.error('Error cargando datos del empleado:', err);
    contentDiv.innerHTML = `
      <div style="text-align:center; padding:20px;">
        <p style="color:#dc3545; font-weight:600;">Error al cargar los datos del empleado</p>
        <p style="color:var(--text-gray); font-size:0.875rem; margin-top:8px;">Por favor, intenta nuevamente</p>
      </div>
    `;
  }
}

// Function to show device details in modal (including employee data if assigned)
async function showDeviceDetails(deviceId) {
  if (!deviceId) return;
  
  // Open modal and show loading state
  openModal('modalDeviceDetails', true);
  const contentDiv = document.getElementById('deviceDetailsContent');
  contentDiv.innerHTML = `
    <div style="text-align:center; padding:20px;">
      <span class="spinner" style="display:inline-block;width:24px;height:24px;border:3px solid var(--text-gray);border-top-color:transparent;border-radius:50%;animation:spin 0.6s linear infinite;"></span>
      <p style="margin-top:12px; color:var(--text-gray);">Cargando datos...</p>
    </div>
  `;
  
  try {
    // Fetch device data
    const resp = await fetch(`/devices/${deviceId}`);
    if (!resp.ok) {
      throw new Error('No se pudo obtener los datos del dispositivo');
    }
    
    const device = await resp.json();
    
    // Build device data display
    const identificador = device.identificador || '-';
    const imei = device.imei || device.numero_serie || '-';
    const marca = device.nombre_marca || '-';
    const modelo = device.nombre_modelo || '-';
    const estado = device.estado;
    const estadoText = getEstadoText(estado);
    const estadoColor = getEstadoColor(estado);
    const ipAsignada = device.ip_asignada || '-';
    const macAddress = device.direccion_mac || device.mac_address || '-';
    const fechaObt = device.fecha_obt || '-';
    const observaciones = device.observaciones || '-';
    
    let deviceHTML = `
      <div style="display:flex; flex-direction:column; gap:14px;">
        <div style="border-left:4px solid #007bff; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Identificador</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${identificador}</div>
        </div>
        
        <div style="border-left:4px solid #17a2b8; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Marca</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${marca}</div>
        </div>
        
        <div style="border-left:4px solid #28a745; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Modelo</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${modelo}</div>
        </div>
        
        <div style="border-left:4px solid #17a2b8; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">IMEI / Número de Serie</div>
          <div style="font-size:0.95rem; font-weight:600; color:var(--text-primary); word-break:break-all;"><code>${imei}</code></div>
        </div>
        
        <div style="border-left:4px solid #6f42c1; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Estado</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">
            <span class="text-${estadoColor}">${estadoText}</span>
          </div>
        </div>
        
        <div style="border-left:4px solid #e83e8c; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">IP Asignada</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${ipAsignada}</div>
        </div>
        
        <div style="border-left:4px solid #fd7e14; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">MAC Address</div>
          <div style="font-size:0.95rem; font-weight:600; color:var(--text-primary); word-break:break-all;"><code>${macAddress}</code></div>
        </div>
        
        <div style="border-left:4px solid #20c997; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Fecha de Obtención</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${fechaObt}</div>
        </div>
        
        <div style="border-left:4px solid #ffc107; padding-left:12px;">
          <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Observaciones</div>
          <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${observaciones}</div>
        </div>
    `;
    
    // If device is assigned to an employee, show employee data
    if (device.fk_id_empleado && device.empleado_nombre) {
      const nombre = device.empleado_nombre || '-';
      const puesto = device.empleado_puesto || '-';
      const empresa = device.empleado_empresa || '-';
      
      deviceHTML += `
        <div style="border-top: 2px solid #dee2e6; margin-top:8px; padding-top:16px;">
          <h4 style="color:var(--text-primary); margin:0 0 12px 0; font-size:1.05rem;">Datos del Empleado Asignado</h4>
          <div style="display:flex; flex-direction:column; gap:14px;">
            <div style="border-left:4px solid #007bff; padding-left:12px;">
              <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Nombre Completo</div>
              <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${nombre}</div>
            </div>
            
            <div style="border-left:4px solid #17a2b8; padding-left:12px;">
              <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Puesto</div>
              <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${puesto}</div>
            </div>
            
            <div style="border-left:4px solid #6f42c1; padding-left:12px;">
              <div style="font-size:0.875rem; color:var(--text-gray); margin-bottom:4px;">Empresa</div>
              <div style="font-size:1rem; font-weight:600; color:var(--text-primary);">${empresa}</div>
            </div>
          </div>
        </div>
      `;
    }
    
    deviceHTML += `
      </div>
    `;
    
    contentDiv.innerHTML = deviceHTML;
  } catch (err) {
    console.error('Error cargando datos del dispositivo:', err);
    contentDiv.innerHTML = `
      <div style="text-align:center; padding:20px;">
        <p style="color:#dc3545; font-weight:600;">Error al cargar los datos del dispositivo</p>
        <p style="color:var(--text-gray); font-size:0.875rem; margin-top:8px;">Por favor, intenta nuevamente</p>
      </div>
    `;
  }
}

// Legacy function kept for compatibility (redirects to modal)
async function restaurarDispositivo(deviceId) {
  try {
    const resp = await fetch(`/devices/deleted/${deviceId}/restore`, {
      method: 'POST',
      credentials: 'same-origin'
    });
    const data = await resp.json().catch(() => ({}));
    if (resp.ok && data.success) {
      openGlobalSuccessModal(data.message || 'Dispositivo restaurado correctamente');
      if (typeof reloadDevicesTable === 'function') await reloadDevicesTable();
    } else {
      const errorMsg = data.message || data.error || 'No se pudo restaurar el dispositivo';
      let errorTitle = 'Error al restaurar';
      let errorDetail = errorMsg;
      
      if (errorMsg.toLowerCase().includes('estado')) {
        errorTitle = 'Error: Estado inv\u00e1lido';
        errorDetail = 'El dispositivo ya est\u00e1 activo o no puede ser restaurado.';
      } else if (errorMsg.toLowerCase().includes('permiso')) {
        errorTitle = 'Permiso denegado';
        errorDetail = 'No tienes permisos suficientes para restaurar este dispositivo.';
      }
      
      openGlobalMessageModal('error', errorTitle, errorDetail);
    }
  } catch (err) {
    console.error('Error restaurando dispositivo:', err);
    openGlobalMessageModal('error', 'Error de conexi\u00f3n', 'No se pudo conectar con el servidor. Verifica tu conexi\u00f3n e intenta nuevamente.');
  }
}