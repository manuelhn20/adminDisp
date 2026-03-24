// Variables globales
let currentUserId = null;
let currentEmployeeId = null;
let currentSistema = null;
let userRolesCache = {};  // {user_id: {dispositivos: 'admin', kardex: null, ...}}
let empleadosData = [];   // Cache de empleados

// Función para abrir modal
async function openModalUsuarios() {
  const modalEl = document.getElementById('modalUsuarios');
  modalEl.classList.add('active');
  await cargarEmpleados();
  limpiarFormulario();
}

// Función para cerrar modal
function closeModalUsuarios() {
  const modalEl = document.getElementById('modalUsuarios');
  modalEl.classList.remove('active');
  limpiarFormulario();
  // Ocultar y limpiar el botón de código
  const btnMostrar = document.getElementById('containerMostrarCodigo');
  btnMostrar.style.display = 'none';
  btnMostrar.innerHTML = '';
  // Limpiar el ID del usuario actual
  currentUserId = null;
}

// Cargar lista de empleados
async function cargarEmpleados() {
  try {
    const resp = await fetch('/auth/empleados/todos-activos');
    const data = await resp.json();
    
    if (!resp.ok) {
      mostrarError(data.error || 'Error al cargar empleados');
      return;
    }
    
    empleadosData = data.empleados || [];
    
    const selectEmpleado = document.getElementById('selectEmpleado');
    selectEmpleado.innerHTML = '<option value="">-- Seleccionar Empleado --</option>';
    
    // Obtener el ID del usuario actual logueado para filtrarlo
    const currentUsernameSession = document.querySelector('meta[name="current-user"]')?.getAttribute('content') || '';
    
    // Filtrar empleados para excluir al usuario actual
    const empleadosFiltrados = empleadosData.filter(emp => emp.usuario !== currentUsernameSession);
    
    // Separar empleados en dos grupos
    const empleadosConUsuario = empleadosFiltrados.filter(emp => emp.tiene_usuario);
    const empleadosSinUsuario = empleadosFiltrados.filter(emp => !emp.tiene_usuario);
    
    // Crear optgroup para empleados con usuario
    if (empleadosConUsuario.length > 0) {
      const optgroupConUsuario = document.createElement('optgroup');
      optgroupConUsuario.label = 'Usuario Asignado';
      
      empleadosConUsuario.forEach(emp => {
        const option = document.createElement('option');
        option.value = emp.id_empleado;
        option.textContent = emp.nombre_completo;
        option.dataset.usuario = emp.usuario || '';
        option.dataset.estado = emp.estado || '';
        option.dataset.tieneUsuario = '1';
        optgroupConUsuario.appendChild(option);
      });
      
      selectEmpleado.appendChild(optgroupConUsuario);
    }
    
    // Crear optgroup para empleados sin usuario
    if (empleadosSinUsuario.length > 0) {
      const optgroupSinUsuario = document.createElement('optgroup');
      optgroupSinUsuario.label = 'Usuario No Asignado';
      
      empleadosSinUsuario.forEach(emp => {
        const option = document.createElement('option');
        option.value = emp.id_empleado;
        option.textContent = emp.nombre_completo;
        option.dataset.usuario = emp.usuario || '';
        option.dataset.estado = emp.estado || '';
        option.dataset.tieneUsuario = '0';
        optgroupSinUsuario.appendChild(option);
      });
      
      selectEmpleado.appendChild(optgroupSinUsuario);
    }
    
  } catch (error) {
    mostrarError('Error al cargar empleados: ' + error.message);
  }
}

// Cargar rol actual del usuario en el sistema seleccionado
async function cargarRolActual(userId, sistema) {
  try {
    // Verificar si ya tenemos los roles en cache
    if (!userRolesCache[userId]) {
      const resp = await fetch(`/auth/usuarios/${userId}/roles`);
      const data = await resp.json();
      
      if (!resp.ok) {
        mostrarError(data.error || 'Error al cargar roles');
        return null;
      }
      
      userRolesCache[userId] = data.sistemas_roles || {};
    }
    
    const rolesData = userRolesCache[userId];
    const rolNombre = rolesData[sistema];  // 'admin', 'operador', 'auditor', null
    
    // Mapear nombre a ID
    const rolesMap = {
      'admin': 1,
      'operador': 2,
      'auditor': 3
    };
    
    return rolNombre ? rolesMap[rolNombre] : null;
    
  } catch (error) {
    mostrarError('Error al cargar rol actual: ' + error.message);
    return null;
  }
}

// Event listeners (se configuran al cargar el DOM)
document.addEventListener('DOMContentLoaded', function() {
  const selectEmpleado = document.getElementById('selectEmpleado');
  const groupUsuario = document.getElementById('groupUsuario');
  const inputUsuario = document.getElementById('inputUsuario');
  const groupSistema = document.getElementById('groupSistema');
  const selectSistema = document.getElementById('selectSistema');
  const rolesContainer = document.getElementById('rolesContainer');
  const btnGuardar = document.getElementById('btnGuardar');
  
  // Cuando se selecciona un empleado
  selectEmpleado.addEventListener('change', async function() {
    const selectedOption = this.options[this.selectedIndex];
    
    // Reset
    groupUsuario.style.display = 'none';
    groupSistema.style.display = 'none';
    rolesContainer.style.display = 'none';
    document.getElementById('containerMostrarCodigo').style.display = 'none';
    inputUsuario.value = '';
    selectSistema.value = '';
    btnGuardar.disabled = true;
    currentUserId = null;
    currentEmployeeId = null;
    currentSistema = null;
    ocultarMensajes();
    
    if (!selectedOption.value) return;
    
    const tieneUsuario = selectedOption.dataset.tieneUsuario === '1';
    const usuario = selectedOption.dataset.usuario;
    const estadoRaw = selectedOption.dataset.estado;
    currentEmployeeId = parseInt(selectedOption.value);
    
    // Validar estado = 'Active'
    const estadoStr = String(estadoRaw || '').toLowerCase();
    const isActive = ['1', 'true', 'active'].includes(estadoStr);
    
    if (!isActive) {
      mostrarError('El empleado seleccionado no está activo.');
      selectEmpleado.value = '';
      return;
    }
    
    // Si el empleado NO tiene usuario en tabla empleados, mostrar error modal
    if (!tieneUsuario || !usuario || usuario.trim() === '') {
      document.getElementById('modalErrorEmpleado').classList.add('active');
      selectEmpleado.value = '';
      return;
    }
    
    // Autofill exitoso
    inputUsuario.value = usuario;
    groupUsuario.style.display = 'block';
    
    // Buscar si existe un usuario con este username en la tabla usuarios
    try {
      const resp = await fetch('/auth/usuarios');
      const data = await resp.json();
      
      if (resp.ok) {
        const usuarioExistente = (data.usuarios || []).find(u => u.username === usuario);
        if (usuarioExistente) {
          currentUserId = usuarioExistente.id_usuario;
          // Pre-cargar roles
          const respRoles = await fetch(`/auth/usuarios/${currentUserId}/roles`);
          const dataRoles = await respRoles.json();
          userRolesCache[currentUserId] = dataRoles.sistemas_roles || {};
          
          // Verificar si mostrar botón de código
          const respUsuario = await fetch(`/auth/usuarios/${currentUserId}`);
          const dataUsuario = await respUsuario.json();
          logToServer('DEBUG', 'Usuario data: ' + JSON.stringify(dataUsuario.usuario));
          logToServer('DEBUG', 'Roles data: ' + JSON.stringify(dataRoles.sistemas_roles));
          
          if (respUsuario.ok && dataUsuario.usuario) {
            // Verificar si tiene al menos un rol asignado
            const tieneRoles = Object.values(dataRoles.sistemas_roles || {}).some(rol => rol !== null);
            // Normalizar verificación de código: existe y no es cadena vacía
            const tieneCodigo = (typeof dataUsuario.usuario.codigo !== 'undefined' && dataUsuario.usuario.codigo !== null && String(dataUsuario.usuario.codigo).trim() !== '');
            const tienePassword = dataUsuario.usuario.password_hash != null;
            const estadoUsuario = dataUsuario.usuario.estado;
            
            logToServer('DEBUG', 'Tiene roles: ' + String(tieneRoles));
            logToServer('DEBUG', 'Tiene codigo: ' + String(tieneCodigo));
            logToServer('DEBUG', 'Tiene password: ' + String(tienePassword));
            
            if (tieneRoles) {
              const btnMostrar = document.getElementById('containerMostrarCodigo');
              // Si tiene código O no tiene contraseña → Mostrar código
              // Mostrar código sólo si existe un código o si no tiene contraseña (primer acceso)
              // Mostrar 'Mostrar Código' sólo si ya existe un código temporal.
              // En caso contrario, mostrar 'Generar Código' para crearlo.
              if (tieneCodigo) {
                logToServer('INFO', 'Mostrando boton: Mostrar Codigo');
                btnMostrar.innerHTML = '<button type="button" class="btn" style="background-color:#10b981; color:white; padding:10px 20px; border:none; border-radius:6px; cursor:pointer;" onclick="mostrarCodigoTemporal()">Mostrar Código</button>';
                btnMostrar.style.display = 'block';
              } else {
                logToServer('INFO', 'Mostrando boton: Generar Codigo');
                btnMostrar.innerHTML = '<button type="button" class="btn" style="background-color:#10b981; color:white; padding:10px 20px; border:none; border-radius:6px; cursor:pointer;" onclick="generarCodigoRecuperacion()">Generar Código</button>';
                btnMostrar.style.display = 'block';
              }
            } else {
              logToServer('INFO', 'No tiene roles asignados - no se muestra boton');
            }

            // Activation/deactivation handled by SharePoint sync; UI button removed
          }
        }
      }
    } catch (e) {
      console.error('Error buscando usuario:', e);
    }
    
    // Mostrar select de sistema
    groupSistema.style.display = 'block';
  });
  
  // Cuando se selecciona un sistema
  selectSistema.addEventListener('change', async function() {
    currentSistema = this.value || null;
    
    if (!currentSistema) {
      rolesContainer.style.display = 'none';
      btnGuardar.disabled = true;
      return;
    }
    
    // Mostrar radios de roles
    rolesContainer.style.display = 'block';
    
    // Cargar rol actual (solo si el usuario ya existe)
    let rolActual = null;
    if (currentUserId) {
      rolActual = await cargarRolActual(currentUserId, currentSistema);
    }
    
    // Preseleccionar el rol actual (o "Sin acceso" si no existe usuario)
    const radios = document.querySelectorAll('input[name="rol_sistema"]');
    radios.forEach(radio => {
      if (rolActual === null) {
        radio.checked = (radio.value === 'null');
      } else {
        radio.checked = (parseInt(radio.value) === rolActual);
      }
    });
    
    btnGuardar.disabled = false;
  });
  
  // Listener para cuando cambia selección de rol
  document.querySelectorAll('input[name="rol_sistema"]').forEach(radio => {
    radio.addEventListener('change', function() {
      if (currentUserId && currentSistema) {
        btnGuardar.disabled = false;
      }
    });
  });
  
  // Event delegation para cards con data-action
  document.body.addEventListener('click', function(e) {
    const card = e.target.closest('card');
    if (card) {
      const action = card.getAttribute('data-action');
      if (action === 'openModalUsuarios') {
        e.preventDefault();
        e.stopPropagation();
        openModalUsuarios();
        return false;
      }
    }
  });
});

// Guardar cambios de rol
async function guardarCambiosUsuario() {
  try {
    // Si el usuario ya existe, verificar su estado en la base antes de asignar roles
    if (currentUserId) {
      try {
        const usrResp = await fetch(`/auth/usuarios/${currentUserId}`);
        const usrData = await usrResp.json();
        if (usrResp.ok && usrData.usuario) {
          let estadoVal = usrData.usuario.estado;
          let estadoNorm = null;
          if (typeof estadoVal === 'boolean') estadoNorm = estadoVal ? '1' : '0';
          else estadoNorm = String(estadoVal).toLowerCase();

          const isInactive = estadoNorm === '0' || estadoNorm === 'false' || estadoNorm === 'inactive' || estadoNorm === 'none' || estadoNorm === 'null' || estadoNorm === 'undefined';
          if (isInactive) {
            // Mostrar modal indicando que no es posible asignar roles a usuario desactivado
            document.getElementById('modalUsuarioInactivo').classList.add('active');
            return;
          }
        }
      } catch (e) {
        console.error('Error verificando estado de usuario:', e);
        // proceder con precaución si falla la verificación
      }
    }
    if (!currentSistema) {
      mostrarError('Seleccione un sistema');
      return;
    }
    
    if (!currentEmployeeId) {
      mostrarError('Seleccione un empleado');
      return;
    }
    
    // Obtener rol seleccionado
    const rolRadio = document.querySelector('input[name="rol_sistema"]:checked');
    if (!rolRadio) {
      mostrarError('Seleccione un rol');
      return;
    }
    
    const rolId = rolRadio.value === 'null' ? null : parseInt(rolRadio.value);
    
    // Mapear ID a nombre
    const rolesMap = {
      1: 'admin',
      2: 'operador',
      3: 'auditor'
    };
    
    const rolNombre = rolId ? rolesMap[rolId] : null;
    
    // Si el usuario NO existe en tabla usuarios, crearlo primero
    if (!currentUserId) {
      const inputUsuario = document.getElementById('inputUsuario');
      const username = inputUsuario.value.trim();
      
      if (!username) {
        mostrarError('El usuario es requerido');
        return;
      }
      
      // Crear usuario en tabla usuarios
      const createPayload = {
        username: username,
        password: 'temporal',  // No se usa, pero es requerido
        employee_id: currentEmployeeId,
        sistemas_roles: {
          [currentSistema]: rolNombre
        }
      };
      
      const createResponse = await fetch('/auth/usuarios/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(createPayload)
      });
      
      const createData = await createResponse.json();
      
      if (createResponse.ok && createData.success) {
        currentUserId = createData.user_id;
        userRolesCache[currentUserId] = { [currentSistema]: rolNombre };
        
        // El usuario fue creado, ahora asignar roles para generar código
        const sistemasRoles = { [currentSistema]: rolNombre };
        
        const rolesResponse = await fetch(`/auth/usuarios/${currentUserId}/roles`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sistemas_roles: sistemasRoles })
        });
        
        const rolesData = await rolesResponse.json();
        
        if (rolesResponse.ok && rolesData.success) {
          // Obtener el código generado
          const codigoResp = await fetch(`/auth/usuarios/${currentUserId}/codigo`);
          const codigoData = await codigoResp.json();
          
          // Mostrar código solo para usuarios nuevos
          if (codigoResp.ok && codigoData.success && codigoData.codigo) {
            document.getElementById('codigoExitoDisplay').textContent = codigoData.codigo;
            document.getElementById('codigoExitoContainer').style.display = 'block';
          } else {
            document.getElementById('codigoExitoContainer').style.display = 'none';
          }
          
          // Mostrar modal de éxito
          document.getElementById('mensajeExito').textContent = 'Rol asignado con éxito';
          document.getElementById('modalExito').classList.add('active');
        } else {
          mostrarError(rolesData.error || 'Error al asignar roles');
        }
        return;
      } else {
        mostrarError(createData.error || 'Error al crear usuario');
        return;
      }
    }
    
    // Si el usuario YA existe en tabla usuarios, actualizar roles
    // Construir objeto de roles (solo actualizar el sistema actual)
    const sistemasRoles = userRolesCache[currentUserId] || {};
    sistemasRoles[currentSistema] = rolNombre;
    
    // Enviar actualización
    const response = await fetch(`/auth/usuarios/${currentUserId}/roles`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sistemas_roles: sistemasRoles })
    });
    
    const data = await response.json();
    
    if (response.ok && data.success) {
      // Actualizar cache
      userRolesCache[currentUserId] = sistemasRoles;
      
      // No mostrar código aquí - solo asignación de rol a usuario existente
      document.getElementById('codigoExitoContainer').style.display = 'none';
      
      // Mostrar modal de éxito sin cerrar la modal principal
      document.getElementById('mensajeExito').textContent = 'Rol asignado con éxito';
      document.getElementById('modalExito').classList.add('active');
    } else {
      // Mostrar modal de fracaso
      document.getElementById('mensajeFracaso').textContent = 'Error al asignar rol';
      document.getElementById('submensajeFracaso').textContent = data.error || 'Ocurrió un error al asignar el rol.';
      document.getElementById('modalFracaso').classList.add('active');
    }
    
  } catch (error) {
    mostrarError('Error al guardar: ' + error.message);
  }
}

// Limpiar formulario
function limpiarFormulario() {
  document.getElementById('formUsuario').reset();
  document.getElementById('groupUsuario').style.display = 'none';
  document.getElementById('groupSistema').style.display = 'none';
  document.getElementById('rolesContainer').style.display = 'none';
  document.getElementById('inputUsuario').value = '';
  document.getElementById('btnGuardar').disabled = true;
  // Ocultar botón de código
  const btnMostrar = document.getElementById('containerMostrarCodigo');
  btnMostrar.style.display = 'none';
  btnMostrar.innerHTML = '';
  // Deactivate button removed; nothing to hide
  currentUserId = null;
  currentSistema = null;
  ocultarMensajes();
}

// Mostrar/ocultar mensajes
function mostrarError(mensaje) {
  const errorDiv = document.getElementById('errorMessage');
  errorDiv.textContent = mensaje;
  errorDiv.style.display = 'block';
  document.getElementById('successMessage').style.display = 'none';
}

function mostrarExito(mensaje) {
  const successDiv = document.getElementById('successMessage');
  successDiv.textContent = mensaje;
  successDiv.style.display = 'block';
  document.getElementById('errorMessage').style.display = 'none';
}

function ocultarMensajes() {
  document.getElementById('errorMessage').style.display = 'none';
  document.getElementById('successMessage').style.display = 'none';
}

function closeModalUsuarioInactivo() {
  document.getElementById('modalUsuarioInactivo').classList.remove('active');
}

// Enviar logs al servidor (archivo logs/menu.log)
function logToServer(level, message) {
  try {
    const payload = { level: level || 'INFO', message: (typeof message === 'string') ? message : JSON.stringify(message) };
    fetch('/auth/logs/menu', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).catch(() => {});
  } catch (e) {
    // no-op
  }
}

// Mostrar código temporal
async function mostrarCodigoTemporal() {
  if (!currentUserId) {
    mostrarError('No se ha identificado el usuario');
    return;
  }
  
  try {
    const resp = await fetch(`/auth/usuarios/${currentUserId}/codigo`);
    const data = await resp.json();
    
    if (resp.ok && data.success) {
      // Mostrar modal con el código
      document.getElementById('codigoTemporalDisplay').textContent = data.codigo;
      
      const fechaGen = new Date(data.fecha_generacion);
      document.getElementById('codigoFechaGeneracion').textContent = fechaGen.toLocaleString('es-HN');
      
      // Calcular vigencia: fecha_generacion + 1 hora
      const fechaExp = new Date(fechaGen.getTime() + 60 * 60 * 1000);
      const horaExp = fechaExp.toLocaleTimeString('es-HN', {hour: '2-digit', minute: '2-digit'});
      document.getElementById('codigoVigenciaHora').textContent = `Hasta las ${horaExp}`;
      
      // Mostrar si fue regenerado
      document.getElementById('codigoRegenerado').textContent = data.codigo_regenerado ? 'Sí' : 'No';
      
      // Actualizar estado (Activo/Expirado)
      actualizarEstadoCodigo(fechaExp);
      if (window.codigoInterval) clearInterval(window.codigoInterval);
      window.codigoInterval = setInterval(() => actualizarEstadoCodigo(fechaExp), 10000);
      
      document.getElementById('modalVerCodigo').classList.add('active');
    } else {
      mostrarError(data.error || 'Error al obtener el código');
    }
  } catch (error) {
    mostrarError('Error al obtener código: ' + error.message);
  }
}

// Función para actualizar el estado del código (Activo/Expirado)
function actualizarEstadoCodigo(fechaExp) {
  const ahora = new Date();
  const estadoSpan = document.getElementById('codigoEstado');
  if (ahora > fechaExp) {
    estadoSpan.textContent = '(Expirado)';
    estadoSpan.style.color = '#ef4444';
  } else {
    estadoSpan.textContent = '(Activo)';
    estadoSpan.style.color = '#10b981';
  }
}

// Generar código para recuperación de contraseña
async function generarCodigoRecuperacion() {
  if (!currentUserId) {
    mostrarError('No se ha identificado el usuario');
    return;
  }
  // Usar modal de confirmación en lugar de confirm()
  document.getElementById('modalConfirmRegenerar').classList.add('active');
  return;
}

// Cerrar modal de código
function closeModalCodigo() {
  document.getElementById('modalVerCodigo').classList.remove('active');
  if (window.codigoInterval) {
    clearInterval(window.codigoInterval);
    window.codigoInterval = null;
  }
}

// Regenerar código - abrir modal de confirmación
function regenerarCodigo() {
  if (!currentUserId) {
    mostrarError('No se ha identificado el usuario');
    return;
  }
  document.getElementById('modalConfirmRegenerar').classList.add('active');
}

// Activation/deactivation UI and handlers removed: state sync now performed by SharePoint webhook

// Cerrar modal de confirmación
function closeModalConfirmRegenerar() {
  document.getElementById('modalConfirmRegenerar').classList.remove('active');
}

// Confirmar regeneración de código
async function confirmarRegenerarCodigo() {
  closeModalConfirmRegenerar();
  
  try {
    const resp = await fetch(`/auth/usuarios/${currentUserId}/codigo/regenerar`, {
      method: 'POST'
    });
    const data = await resp.json();
    
    if (resp.ok && data.success) {
      // Actualizar el modal con el nuevo código
      document.getElementById('codigoTemporalDisplay').textContent = data.codigo;
      const fechaGen = new Date(data.fecha_generacion);
      document.getElementById('codigoFechaGeneracion').textContent = fechaGen.toLocaleString('es-HN');
      document.getElementById('codigoRegenerado').textContent = 'Sí';
      
      // Actualizar hora de expiración
      const fechaExp = new Date(fechaGen.getTime() + 60 * 60 * 1000);
      const horaExp = fechaExp.toLocaleTimeString('es-HN', {hour: '2-digit', minute: '2-digit'});
      document.getElementById('codigoVigenciaHora').textContent = `Hasta las ${horaExp}`;
      
      // Actualizar estado
      actualizarEstadoCodigo(fechaExp);
      if (window.codigoInterval) clearInterval(window.codigoInterval);
      window.codigoInterval = setInterval(() => actualizarEstadoCodigo(fechaExp), 10000);

      // Mostrar modal de éxito con el nuevo código
      try {
        document.getElementById('mensajeExito').textContent = 'Código regenerado exitosamente';
        // Mostrar código en el modal de éxito si existe el contenedor
        const codigoCont = document.getElementById('codigoExitoContainer');
        const codigoDisplay = document.getElementById('codigoExitoDisplay');
        if (codigoCont && codigoDisplay) {
          codigoDisplay.textContent = data.codigo || '------';
          codigoCont.style.display = 'block';
        }
        document.getElementById('modalExito').classList.add('active');
      } catch (e) {
        // fallback a mensaje en pantalla
        mostrarExito('Código regenerado exitosamente');
      }

      // Asegurar que el botón de Mostrar Código esté disponible para este usuario
      try {
        const btnMostrar = document.getElementById('containerMostrarCodigo');
        btnMostrar.innerHTML = '<button type="button" class="btn" style="background-color:#10b981; color:white; padding:10px 20px; border:none; border-radius:6px; cursor:pointer;" onclick="mostrarCodigoTemporal()">Mostrar Código</button>';
        btnMostrar.style.display = 'block';
      } catch (e) {
        // no-op
      }
    } else {
      mostrarError(data.error || 'Error al regenerar código');
    }
  } catch (error) {
    mostrarError('Error al regenerar código: ' + error.message);
  }
}

// Cerrar modal de éxito
function closeModalExito() {
  document.getElementById('modalExito').classList.remove('active');
  // Ocultar código
  document.getElementById('codigoExitoContainer').style.display = 'none';
  document.getElementById('codigoExitoDisplay').textContent = '------';
  // Hacer refresh del formulario sin cerrar la modal principal
  limpiarFormulario();
  // Recargar la lista de empleados
  cargarEmpleados();
}

// Cerrar modal de fracaso
function closeModalFracaso() {
  document.getElementById('modalFracaso').classList.remove('active');
}

// Cerrar modal de error de empleado
function closeModalErrorEmpleado() {
  document.getElementById('modalErrorEmpleado').classList.remove('active');
}

// Local dark-mode toggle for menu page sidebar
function updateDarkModeIconLocal(isDark) {
  const icon = document.getElementById('darkModeIcon');
  const label = document.getElementById('darkModeLabel');
  if (icon) icon.textContent = isDark ? 'dark_mode' : 'light_mode';
  if (label) label.textContent = isDark ? 'Modo: Oscuro' : 'Modo: Claro';
}

function toggleDarkMode() {
  const body = document.body;
  const isDark = body.classList.toggle('dark-mode');
  try { localStorage.setItem('darkMode', isDark ? 'true' : 'false'); } catch(e){}
  updateDarkModeIconLocal(isDark);
}

function initializeDarkModeLocal() {
  try {
    const stored = localStorage.getItem('darkMode');
    const useDark = (stored === 'true');
    if (useDark) document.body.classList.add('dark-mode');
    updateDarkModeIconLocal(useDark);
  } catch(e) { updateDarkModeIconLocal(false); }
}

document.addEventListener('DOMContentLoaded', initializeDarkModeLocal);

// Friendly visibility handler for menu page
(function () {
  try {
    const originalTitle = document.title || 'PROIMA - Menú Principal';
    const hiddenTitle = 'PROIMA - Te esperamos';
    // If you later want to change favicon on hide, set hrefs here
    document.addEventListener('visibilitychange', function () {
      try {
        document.title = document.hidden ? hiddenTitle : originalTitle;
      } catch (e) { /* ignore */ }
    });
  } catch (e) { console.warn('visibility handler menu failed', e); }
})();
