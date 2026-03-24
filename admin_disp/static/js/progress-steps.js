// Minimal helper to set documentation progress steps in modals
(function(){
  function setDocumentationProgress(step){
    try{
      var wrapper = document.getElementById('docProgressContainer');
      if(!wrapper) return;
      var circles = wrapper.querySelectorAll('.doc-circle');
      var progress = wrapper.querySelector('.doc-progress') || document.getElementById('docProgressBar');
      var total = circles.length || 1;
      var current = parseInt(step,10) || 1;
      if(current < 1) current = 1;
      if(current > total) current = total;

      circles.forEach(function(c, idx){
        // idx is zero-based. current is 1-based.
        // Mark previous steps as 'visited' (outlined), current as 'active', others cleared.
        if(idx < (current-1)){
          c.classList.add('visited');
          c.classList.remove('active');
        } else if(idx === (current-1)){
          c.classList.add('active');
          c.classList.remove('visited');
        } else {
          c.classList.remove('active');
          c.classList.remove('visited');
        }
        // Ensure 'completed' is not applied anywhere
        c.classList.remove('completed');
      });

      if(progress){
        try{
          // Calculate width based on actual circle centers so the bar reaches the center of the current circle
          var rect = wrapper.getBoundingClientRect();
          var centers = Array.prototype.map.call(circles, function(c){
            var r = c.getBoundingClientRect();
            return r.left + r.width/2;
          });
          var firstCenter = centers[0];
          var lastCenter = centers[centers.length-1];
          var currentCenter = centers[Math.max(0, Math.min(circles.length-1, current-1))];
          var leftPx = Math.max(0, firstCenter - rect.left);
          var widthPx = Math.max(0, currentCenter - firstCenter);
          progress.style.left = leftPx + 'px';
          progress.style.width = widthPx + 'px';
        }catch(e){
          // Fallback to percentage if something goes wrong
          var width = ((Math.max(current-1,0)) / Math.max(total-1,1)) * 100;
          progress.style.width = width + '%';
          progress.style.left = '0%';
        }
      }
    }catch(e){ console.warn('setDocumentationProgress error', e); }
  }

  // remember last step globally so ensureDocProgress can reapply it
  var originalSetDocumentationProgress = setDocumentationProgress;
  window.setDocumentationProgress = function(step, modalId){
    window._docProgressStep = parseInt(step,10) || 1;
    if(modalId && typeof window.ensureDocProgress === 'function'){
      try{ window.ensureDocProgress(modalId); } catch(e){}
    }
    try{ originalSetDocumentationProgress(window._docProgressStep); } catch(e){ console.warn(e); }
  };
  // (wrapper) expose globally as window.setDocumentationProgress

  // Ensure the doc progress container exists inside the given modal (move if exists elsewhere)
  function ensureDocProgress(modalId){
    try{
      var modal = document.getElementById(modalId);
      if(!modal) return;

      // Remove existing global container if present (we keep a single instance)
      var existing = document.getElementById('docProgressContainer');
      if(existing && existing.parentNode && existing.parentNode !== modal.querySelector('.doc-progress-steps-wrapper')){
        existing.parentNode.removeChild(existing);
      }

      // If modal already has a container, keep it
      var wrapper = modal.querySelector('.doc-progress-steps-wrapper');
      if(!wrapper){
        // create wrapper at top of modal (before .modal-body if present)
        wrapper = document.createElement('div');
        wrapper.className = 'doc-progress-steps-wrapper';
        var modalBody = modal.querySelector('.modal-body');
        if(modalBody) modal.insertBefore(wrapper, modalBody);
        else modal.appendChild(wrapper);
      }

      var container = wrapper.querySelector('#docProgressContainer');
      if(!container){
        container = document.createElement('div');
        container.className = 'doc-progress-container';
        container.id = 'docProgressContainer';
        container.innerHTML = '<div class="doc-progress" id="docProgressBar"></div>' +
                              '<div class="doc-circle">1</div>' +
                              '<div class="doc-circle">2</div>' +
                              '<div class="doc-circle">3</div>' +
                              '<div class="doc-circle">4</div>';
        wrapper.appendChild(container);
      }

      // After creating/moving, re-run progress to reflect last known step
      try{ setDocumentationProgress(window._docProgressStep || 1); } catch(e){}
    }catch(e){ console.warn('ensureDocProgress error', e); }
  }

  window.ensureDocProgress = ensureDocProgress;

  // Auto-init when DOM ready: ensure the stepper exists in known modals
  document.addEventListener('DOMContentLoaded', function(){
    var modalCandidates = ['modalSeleccionarTipoDocumentacion','modalDocumentosOneDrive'];
    var injected = false;
    for(var i=0;i<modalCandidates.length;i++){
      if(document.getElementById(modalCandidates[i])){
        try{
          ensureDocProgress(modalCandidates[i]);
          window.setDocumentationProgress(window._docProgressStep || 1, modalCandidates[i]);
          injected = true;
          break;
        }catch(e){}
      }
    }
    if(!injected){
      var firstModal = document.querySelector('.modal');
      if(firstModal && firstModal.id){
        try{ ensureDocProgress(firstModal.id); window.setDocumentationProgress(window._docProgressStep || 1, firstModal.id); }catch(e){}
      }
    }
  });
})();
