/* ============================================================ */
/* login.js - Scripts extraídos de login.html                 */
/* ============================================================ */

// ── Utilidades de modal de autenticación ─────────────────────────────
const authentModal = document.getElementById('authentModal');

function mostrarAuthentModal() {
  authentModal.classList.add('show');
  setTimeout(() => authentModal.classList.add('visible'), 50);
}

function ocultarAuthentModal() {
  authentModal.classList.remove('visible');
  setTimeout(() => authentModal.classList.remove('show', 'error', 'success'), 300);
}

function setAuthentSuccess() {
  authentModal.classList.add('success');
  authentModal.innerHTML = `
    <div style="text-align:center; padding:20px 10px;">
      <svg width="60" height="60" viewBox="0 0 60 60" style="margin-bottom:15px;">
        <circle cx="30" cy="30" r="28" fill="none" stroke="#22c997" stroke-width="3"/>
        <path d="M20 30 L27 37 L42 22" fill="none" stroke="#22c997" stroke-width="4" stroke-linecap="round"/>
      </svg>
      <h2 style="color:#22c997; font-size:20px; margin:0 0 12px; font-weight:700; letter-spacing:1px; text-transform:uppercase;">Autenticación Exitosa</h2>
      <p style="color:#a5a5a5; font-size:14px; margin:0; letter-spacing:.5px;">Redirigiendo al sistema...</p>
    </div>`;
}

function setAuthentError() {
  authentModal.classList.add('error');
  authentModal.innerHTML = `
    <div style="text-align:center; padding:20px 10px;">
      <svg width="60" height="60" viewBox="0 0 60 60" style="margin-bottom:15px;">
        <circle cx="30" cy="30" r="28" fill="none" stroke="#ea5c54" stroke-width="3"/>
        <path d="M22 22 L38 38 M38 22 L22 38" stroke="#ea5c54" stroke-width="4" stroke-linecap="round"/>
      </svg>
      <h2 style="color:#ea5c54; font-size:20px; margin:0 0 12px; font-weight:700; letter-spacing:1px; text-transform:uppercase;">Error de Autenticación</h2>
      <p style="color:#a5a5a5; font-size:14px; margin:0; letter-spacing:.5px;">Usuario o contraseña incorrectos</p>
    </div>`;
}

// ── Login principal (sin llamar a validar-usuario) ────────────────────
async function iniciarSesion(event) {
  event.preventDefault();
  
  const loginForm = document.getElementById('b-form');
  const username  = loginForm.querySelector('input[name="username"]').value.trim();
  const password  = loginForm.querySelector('input[name="password"]').value;

  // Si algún campo está vacío, retornar false para que el navegador muestre el mensaje
  if (!username || !password) {
    return false;
  }

  mostrarAuthentModal();

  try {
    const resp = await fetch(loginForm.action, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (resp.ok) {
      setTimeout(setAuthentSuccess, 1500);
      setTimeout(() => { window.location.href = '/auth/menu'; }, 3000);
    } else {
      setTimeout(setAuthentError, 1500);
      setTimeout(() => {
        ocultarAuthentModal();
        setTimeout(() => {
          authentModal.innerHTML = '<img src="{{ url_for("static", filename="img/cg.png") }}" alt="Autenticando"><p>AUTENTICANDO...</p>';
          loginForm.reset();
        }, 300);
      }, 4000);
    }
  } catch (err) {
    console.error('Error en login:', err);
    ocultarAuthentModal();
  }
  
  return false;
}

// ── "¿Olvidó su contraseña?" → llama a validar-usuario ───────────────
document.getElementById('forgotPasswordLink').addEventListener('click', async function (e) {
  e.preventDefault();
  const loginForm     = document.getElementById('b-form');
  const usernameInput = loginForm.querySelector('input[name="username"]');
  const username      = usernameInput.value.trim();

  if (!username) {
    usernameInput.focus();
    return;
  }

  try {
    const resp = await fetch('/auth/validar-usuario', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username }),
    });
    const data = await resp.json();

    if (data.success && data.tiene_codigo && data.codigo_vigente) {
      document.getElementById('tempUsername').value = username;
      document.getElementById('modalCodigo').classList.add('active');
      document.getElementById('codigoInput').focus();
    } else {
      // Sin código vigente → registrar solicitud e informar al usuario
      await fetch('/auth/request-reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username }),
      });
      document.getElementById('modalSinCodigo').classList.add('active');
    }
  } catch (err) {
    console.error('Error solicitando código:', err);
    document.getElementById('modalSinCodigo').classList.add('active');
  }
});

// ── Validar código temporal ───────────────────────────────────────────
async function validarCodigo() {
  const codigo   = document.getElementById('codigoInput').value.trim();
  const username = document.getElementById('tempUsername').value;

  if (!codigo || codigo.length !== 6 || !/^\d{6}$/.test(codigo)) {
    mostrarErrorCodigo('El código debe ser de 6 dígitos numéricos');
    return;
  }

  try {
    const resp = await fetch('/auth/validar-codigo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, codigo }),
    });
    const data = await resp.json();

    if (resp.ok && data.success) {
      document.getElementById('modalCodigo').classList.remove('active');
      document.getElementById('modalPassword').classList.add('active');
      document.getElementById('newPassword').focus();
    } else {
      document.getElementById('mensajeError').textContent    = data.error || 'El código ingresado no es válido';
      document.getElementById('submensajeError').textContent = 'Por favor, verifique e intente nuevamente.';
      document.getElementById('modalError').classList.add('active');
    }
  } catch (err) {
    document.getElementById('mensajeError').textContent    = 'Error de conexión';
    document.getElementById('submensajeError').textContent = err.message;
    document.getElementById('modalError').classList.add('active');
  }
}

// ── Indicador de fortaleza de contraseña ─────────────────────────────
function validarFortalezaPassword() {
  const password   = document.getElementById('newPassword').value;
  const hasLength  = password.length >= 8;
  const hasLower   = /[a-z]/.test(password);
  const hasUpper   = /[A-Z]/.test(password);
  const hasNumber  = /[0-9]/.test(password);
  const hasSymbol  = /[!@#$%^&*()_+\-=\[\]{};:'",.<>?/\\|`~]/.test(password);

  document.getElementById('req-length').classList.toggle('met', hasLength);
  document.getElementById('req-lowercase').classList.toggle('met', hasLower);
  document.getElementById('req-uppercase').classList.toggle('met', hasUpper);
  document.getElementById('req-number').classList.toggle('met', hasNumber);
  document.getElementById('req-symbol').classList.toggle('met', hasSymbol);

  const strength = [hasLength, hasLower, hasUpper, hasNumber, hasSymbol].filter(Boolean).length;
  const fill  = document.getElementById('strengthFill');
  const label = document.getElementById('strengthLabel');
  const text  = document.getElementById('strengthText');

  fill.className  = 'strength-fill';
  label.className = 'strength-label';

  if (!password.length) {
    text.textContent = 'Fortaleza de contraseña';
  } else if (strength < 3) {
    fill.classList.add('weak');   label.classList.add('weak');   text.textContent = 'DÉBIL';
  } else if (strength < 5) {
    fill.classList.add('medium'); label.classList.add('medium'); text.textContent = 'MEDIA';
  } else {
    fill.classList.add('strong'); label.classList.add('strong'); text.textContent = 'FUERTE';
  }
}

// ── Establecer contraseña ─────────────────────────────────────────────
async function establecerPassword() {
  const password = document.getElementById('newPassword').value;
  const confirm  = document.getElementById('confirmPassword').value;

  if (!password || !confirm)                         { mostrarErrorPassword('Por favor, complete todos los campos'); return; }
  if (password !== confirm)                          { mostrarErrorPassword('Las contraseñas no coinciden'); return; }
  if (password.length < 8 || password.length > 24)  { mostrarErrorPassword('La contraseña debe tener entre 8 y 24 caracteres'); return; }
  if (!/[A-Z]/.test(password))                       { mostrarErrorPassword('La contraseña debe contener al menos una mayúscula'); return; }
  if (!/[0-9]/.test(password))                       { mostrarErrorPassword('La contraseña debe contener al menos un número'); return; }
  if (!/[!@#$%^&*()_+\-=\[\]{};:'",.<>?/\\|`~]/.test(password)) { mostrarErrorPassword('La contraseña debe contener al menos un símbolo especial'); return; }

  try {
    const resp = await fetch('/auth/establecer-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password, password_confirm: confirm }),
    });
    const data = await resp.json();

    if (resp.ok && data.success) {
      document.getElementById('modalPassword').classList.remove('active');
      document.getElementById('modalExito').classList.add('active');
    } else {
      mostrarErrorPassword(data.error || 'Error al establecer contraseña');
    }
  } catch (err) {
    mostrarErrorPassword('Error de conexión: ' + err.message);
  }
}

// ── Helpers de error ──────────────────────────────────────────────────
function mostrarErrorCodigo(msg) {
  const el = document.getElementById('codigoError');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 5000);
}

function mostrarErrorPassword(msg) {
  const el = document.getElementById('passwordError');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 5000);
}

// ── Cerrar modales ───────────────────────────────────────────────────
function closeModalCodigo() {
  document.getElementById('modalCodigo').classList.remove('active');
  document.getElementById('codigoInput').value  = '';
  document.getElementById('tempUsername').value = '';
}
function closeModalError() {
  document.getElementById('modalError').classList.remove('active');
  document.getElementById('codigoInput').value = '';
  document.getElementById('codigoInput').focus();
}
function closeModalExito() {
  document.getElementById('modalExito').classList.remove('active');
  window.location.reload();
}
function closeModalSinCodigo() {
  document.getElementById('modalSinCodigo').classList.remove('active');
}

// ── Enter en input de código ──────────────────────────────────────────
// Enter en input de contraseña: enviar login al presionar Enter
document.addEventListener('DOMContentLoaded', function() {
  const pwd = document.querySelector('input[name="password"]');
  if (pwd) {
    pwd.addEventListener('keypress', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        // Disparar validación HTML5 y onsubmit haciendo click en el botón
        document.querySelector('#b-form button[type="submit"]').click();
      }
    });
  }

  const codigoInput = document.getElementById('codigoInput');
  if (codigoInput) {
    codigoInput.addEventListener('keypress', e => {
      if (e.key === 'Enter') validarCodigo();
    });
  }
});
