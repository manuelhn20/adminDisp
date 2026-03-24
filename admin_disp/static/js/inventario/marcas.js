let gridApi, columnApi;
const modal = new bootstrap.Modal(document.getElementById('modalMarca'));

// Column definitions para ag-grid
const colDefs = [
    { field: 'id', headerName: 'ID', width: 80, pinned: 'left' },
    { field: 'nombre', headerName: 'Nombre', flex: 1, minWidth: 200 },
    { 
        field: 'estado', 
        headerName: 'Estado', 
        width: 120,
        cellRenderer: (params) => {
            const estado = params.value === 1 ? 'Activo' : 'Inactivo';
            const clase = params.value === 1 ? 'badge-success' : 'badge-danger';
            return `<span class="badge ${clase}">${estado}</span>`;
        }
    },
    {
        field: 'acciones',
        headerName: 'Acciones',
        width: 220,
        pinned: 'right',
        cellRenderer: (params) => {
            const data = params.data;
            const btnEditar = `<button class="btn btn-sm btn-warning" onclick="editarMarca(${data.id})">Editar</button>`;
            const btnEstado = data.estado === 1 
                ? `<button class="btn btn-sm btn-danger" onclick="toggleEstadoMarca(${data.id})">Desactivar</button>`
                : `<button class="btn btn-sm btn-success" onclick="toggleEstadoMarca(${data.id})">Activar</button>`;
            return `${btnEditar} ${btnEstado}`;
        }
    }
];

// Opciones de grid
const gridOptions = {
    columnDefs: colDefs,
    defaultColDef: {
        resizable: true,
        sortable: true,
        filter: true
    },
    rowData: [],
    pagination: true,
    paginationPageSize: 20,
    onGridReady: (event) => {
        gridApi = event.api;
        columnApi = event.columnApi;
        loadMarcas();
    }
};

// Inicializar grid cuando se carga la página
document.addEventListener('DOMContentLoaded', () => {
    const gridDiv = document.getElementById('marcasGrid');
    new agGrid.Grid(gridDiv, gridOptions);
    
    // Búsqueda rápida
    const searchInput = document.getElementById('marcasPageSearch');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            gridApi.setQuickFilter(e.target.value);
        });
    }
});

/**
 * Cargar todas las marcas
 */
async function loadMarcas(includeInactive = true) {
    try {
        const url = includeInactive ? '/inventario/api/marcas' : '/inventario/api/marcas/activas';
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const result = await response.json();
        if (!result.success) throw new Error(result.message);
        
        gridApi.setRowData(result.data || []);
    } catch (error) {
        console.error('Error cargando marcas:', error);
        alert(`Error al cargar marcas: ${error.message}`);
    }
}

/**
 * Abrir modal para crear nueva marca
 */
function openModalCrear() {
    document.getElementById('marcaId').value = '';
    document.getElementById('formMarca').reset();
    document.querySelector('.modal-title').textContent = 'Nueva Marca';
    modal.show();
}

/**
 * Cargar marca para editar
 */
async function editarMarca(marcaId) {
    try {
        const response = await fetch(`/inventario/api/marcas/${marcaId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const result = await response.json();
        if (!result.success) throw new Error(result.message);
        
        const marca = result.data;
        document.getElementById('marcaId').value = marca.id;
        document.getElementById('marcaNombre').value = marca.nombre;
        document.querySelector('.modal-title').textContent = 'Editar Marca';
        modal.show();
    } catch (error) {
        console.error('Error cargando marca:', error);
        alert(`Error al cargar marca: ${error.message}`);
    }
}

/**
 * Guardar marca (crear o actualizar)
 */
async function guardarMarca(event) {
    event.preventDefault();
    
    const marcaId = document.getElementById('marcaId').value;
    const nombre = document.getElementById('marcaNombre').value.trim();
    
    if (!nombre) {
        alert('El nombre es requerido');
        return;
    }
    
    try {
        let url, method, body;
        
        if (marcaId) {
            // Actualizar
            url = `/inventario/api/marcas/${marcaId}`;
            method = 'PUT';
            body = JSON.stringify({ nombre });
        } else {
            // Crear
            url = '/inventario/api/marcas';
            method = 'POST';
            body = JSON.stringify({ nombre });
        }
        
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            if (response.status === 409) {
                alert(`La marca "${nombre}" ya existe`);
                document.getElementById('marcaNombre').focus();
                return;
            }
            throw new Error(result.message || 'Error al guardar');
        }
        
        modal.hide();
        loadMarcas();
        alert(marcaId ? 'Marca actualizada' : 'Marca creada');
    } catch (error) {
        console.error('Error guardando marca:', error);
        alert(`Error: ${error.message}`);
    }
}

/**
 * Cambiar estado de marca (activar/desactivar)
 */
async function toggleEstadoMarca(marcaId) {
    const confirm_msg = 'Esta acción debe ser confirmada';
    if (!confirm(confirm_msg)) return;
    
    try {
        const response = await fetch(`/inventario/api/marcas/${marcaId}/estado`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || 'Error al cambiar estado');
        
        loadMarcas();
        alert('Estado actualizado');
    } catch (error) {
        console.error('Error cambiando estado:', error);
        alert(`Error: ${error.message}`);
    }
}
