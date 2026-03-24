/* ==========================================
   GESTIÓN DE MODALES
   ========================================== */

// Modal stacking: keep track of opened modals and assign increasing z-index
window.__modalStack = window.__modalStack || [];
window.__modalZBase = window.__modalZBase || 12000; // should be above other UI elements

function openModal(modalId, preserveScroll=false) {
  const overlay = document.getElementById(modalId);
  if (!overlay) return;
  // compute z-index for this modal
  const stackIndex = (window.__modalStack.length * 2);
  const overlayZ = window.__modalZBase + stackIndex;
  const modalEl = overlay.querySelector('.modal');
  const modalZ = overlayZ + 1;
  overlay.style.zIndex = overlayZ;
  if (modalEl) modalEl.style.zIndex = modalZ;
  overlay.classList.add('active');
  // Ensure modal appears at the top of the viewport instead of centered
  try {
    overlay.classList.add('align-top');
    // reset any scroll positions
    overlay.scrollTop = 0;
    if (modalEl) modalEl.scrollTop = 0;
    // By default scroll page to top so modal is visible on small screens.
    // If preserveScroll is true (e.g. editing a row in a long table), avoid jumping.
    if (!preserveScroll) {
      try { window.scrollTo(0, 0); } catch(e) {}
    }
  } catch(e) { /* ignore */ }
  // Avoid duplicate entries for the same modal id in the stack. If present,
  // remove the old occurrence so this modal becomes the topmost entry only once.
  const existingIdx = window.__modalStack.lastIndexOf(modalId);
  if (existingIdx !== -1) window.__modalStack.splice(existingIdx, 1);
  window.__modalStack.push(modalId);
  document.body.style.overflow = 'hidden';
}

function closeModal(modalId) {
  const overlay = document.getElementById(modalId);
  if (!overlay) return;
  overlay.classList.remove('active');
  // remove from stack (may be not top if closed programmatically)
  const idx = window.__modalStack.lastIndexOf(modalId);
  if (idx !== -1) window.__modalStack.splice(idx, 1);
  // reset inline z-index styles
  overlay.style.zIndex = '';
  const modalEl = overlay.querySelector('.modal');
  if (modalEl) modalEl.style.zIndex = '';
  // remove top-alignment helper
  overlay.classList.remove('align-top');
  // restore body overflow only if no modals are open
  if (!window.__modalStack.length) document.body.style.overflow = 'auto';
}

// Cerrar modal al hacer clic en el overlay - DESHABILITADO
// Los modales ahora solo se cierran con botón X, botones de cancelar o tecla ESC
document.addEventListener('DOMContentLoaded', function() {
  // COMENTADO: Ya no cerramos modales al hacer clic en el overlay
  /*
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', function(e) {
      if (e.target === this && this.id !== 'modalLinkPlanDevice') {
        // close only this overlay/modal and update stack
        const id = this.id;
        closeModal(id);
      }
    });
  });
  */

  // Cerrar modal con tecla ESC (excepto modalLinkPlanDevice que requiere vinculación obligatoria)
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      // Close only the topmost modal if any (but not modalLinkPlanDevice)
      const stack = window.__modalStack || [];
      if (stack.length) {
        const topId = stack[stack.length - 1];
        if (topId !== 'modalLinkPlanDevice') {
          closeModal(topId);
        }
      }
    }
  });
});

/* ==========================================
   ELIMINACIÓN CON CONFIRMACIÓN
   ========================================== */

function confirmDelete(itemName, onConfirm) {
  // Opens the global delete modal and executes onConfirm() when user accepts.
  // onConfirm may be a function that performs the deletion (can return a Promise).
  openGlobalDeleteModal(onConfirm || null, `Eliminar ${itemName}`, itemName);
}

/* ==========================================
   VALIDACIONES DE FORMULARIO
   ========================================== */

function validateForm(formId) {
  const form = document.getElementById(formId);
  if (!form) return false;
  return form.reportValidity();
}
