/* Simplified login - Solo maneja el formulario de inicio de sesión */

let allButtons = document.querySelectorAll(".submit");

let getButtons = (e) => {
    e.preventDefault();
    // Efecto de papel cuando se envía el formulario
    handleFormSubmit(e);
}

// Función para manejar el envío del formulario con efecto de papel
function handleFormSubmit(e) {
    const form = e.target.closest('form');
    const authentModal = document.getElementById('authentModal');
    
    if (!form || form.id !== 'b-form') return;
    
    // Mostrar modal de autenticación centrado
    authentModal.classList.add('show');
    
    setTimeout(function() {
        authentModal.classList.add('visible');
    }, 50);
    
    // Enviar petición AJAX
    setTimeout(function() {
        const formData = new FormData(form);
        const username = formData.get('username');
        const password = formData.get('password');
        
        fetch(form.action, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({username: username, password: password})
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error('Authentication failed');
            }
        })
        .then(data => {
            // AUTENTICACIÓN EXITOSA
            
            // Cambiar el contenido del modal a éxito
            setTimeout(function() {
                authentModal.classList.add('success');
                authentModal.innerHTML = `
                    <div style="text-align: center; padding: 20px 10px;">
                        <svg width="60" height="60" viewBox="0 0 60 60" style="margin-bottom: 15px;">
                            <circle cx="30" cy="30" r="28" fill="none" stroke="#22c997" stroke-width="3"/>
                            <path d="M20 30 L27 37 L42 22" fill="none" stroke="#22c997" stroke-width="4" stroke-linecap="round"/>
                        </svg>
                        <h2 style="color: #22c997; font-size: 20px; margin: 0 0 12px 0; font-weight: 700; letter-spacing: 1px; text-transform: uppercase;">Autenticación Exitosa</h2>
                        <p style="color: #a5a5a5; font-size: 14px; margin: 0; font-weight: 400; letter-spacing: 0.5px;">Redirigiendo al sistema...</p>
                    </div>
                `;
            }, 1500);
            
            // Redireccionar
            setTimeout(function() {
                window.location.href = '/auth/menu';
            }, 3000);
        })
        .catch(error => {
            // AUTENTICACIÓN FALLIDA
            
            // Cambiar el contenido del modal a error
            setTimeout(function() {
                authentModal.classList.add('error');
                authentModal.innerHTML = `
                    <div style="text-align: center; padding: 20px 10px;">
                        <svg width="60" height="60" viewBox="0 0 60 60" style="margin-bottom: 15px;">
                            <circle cx="30" cy="30" r="28" fill="none" stroke="#ea5c54" stroke-width="3"/>
                            <path d="M22 22 L38 38 M38 22 L22 38" stroke="#ea5c54" stroke-width="4" stroke-linecap="round"/>
                        </svg>
                        <h2 style="color: #ea5c54; font-size: 20px; margin: 0 0 12px 0; font-weight: 700; letter-spacing: 1px; text-transform: uppercase;">Error de Autenticación</h2>
                        <p style="color: #a5a5a5; font-size: 14px; margin: 0; font-weight: 400; letter-spacing: 0.5px;">Usuario o contraseña incorrectos</p>
                    </div>
                `;
            }, 1500);
            
            // Ocultar modal y restaurar formulario
            setTimeout(function() {
                authentModal.classList.remove('visible');
                
                setTimeout(function() {
                    authentModal.classList.remove('show', 'error');
                    // Restaurar contenido original del modal
                    authentModal.innerHTML = '<img src="/static/img/cg.png" alt="Autenticando"><p>AUTENTICANDO...</p>';
                    
                    // Limpiar campos
                    form.reset();
                }, 300);
            }, 4000);
        });
    }, 200);
}

let mainF = (e) => {
    for (var i = 0; i < allButtons.length; i++)
        allButtons[i].addEventListener("click", getButtons );
}

window.addEventListener("load", mainF);
