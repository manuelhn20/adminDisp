let gridApi, columnApi;
const modal = new bootstrap.Modal(document.getElementById('modalProducto'));

// Column definitions para ag-grid
const colDefs = [
    { field: 'id', headerName: 'ID', width: 80, pinned: 'left' },
    { field: 'nombre', headerName: 'Nombre', flex: 1, minWidth: 150 },
    { field: 'nombreMarca', headerName: 'Marca', width: 120 },
    { field: 'descripcion', headerName: 'Descripción', flex: 1, minWidth: 180 },
    { field: 'upc1', headerName: 'UPC 1', width: 130, cellStyle: { fontFamily: 'monospace' } },
    { field: 'upc2', headerName: 'UPC 2', width: 130, cellStyle: { fontFamily: 'monospace' } },
    { field: 'precio', headerName: 'Precio', width: 100, valueFormatter: (params) => {
        return params.value ? `$${parseFloat(params.value).toFixed(2)}` : '-';
    }},
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
        width: 240,
        pinned: 'right',
        cellRenderer: (params) => {
            const data = params.data;
            const btnEditar = `<button class="btn btn-sm btn-warning" onclick="editarProducto(${data.id})">Editar</button>`;
            const btnEstado = data.estado === 1 
                ? `<button class="btn btn-sm btn-danger" onclick="toggleEstadoProducto(${data.id})">Desactivar</button>`
                : `<button class="btn btn-sm btn-success" onclick="toggleEstadoProducto(${data.id})">Activar</button>`;
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
    paginationPageSize: 15,
    onGridReady: (event) => {
        gridApi = event.api;
        columnApi = event.columnApi;
        cargarMarcas();
        loadProductos();
    }
};

// Inicializar grid cuando se carga la página
document.addEventListener('DOMContentLoaded', () => {
    const gridDiv = document.getElementById('productosGrid');
    new agGrid.Grid(gridDiv, gridOptions);
    
    // Búsqueda rápida
    const searchInput = document.getElementById('productosPageSearch');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            gridApi.setQuickFilter(e.target.value);
        });
    }
});

/**
 * Cargar marcas para select
 */
async function cargarMarcas() {
    try {
        const response = await fetch('/inventario/api/marcas/activas');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const result = await response.json();
        if (!result.success) throw new Error(result.message);
        
        const selectMarca = document.getElementById('productoMarca');
        selectMarca.innerHTML = '<option value="">Seleccionar marca...</option>';
        
        (result.data || []).forEach(marca => {
            const option = document.createElement('option');
            option.value = marca.id;
            option.textContent = marca.nombre;
            selectMarca.appendChild(option);
        });
    } catch (error) {
        console.error('Error cargando marcas:', error);
        alert(`Error al cargar marcas: ${error.message}`);
    }
}

/**
 * Cargar todos los productos
 */
async function loadProductos(includeInactive = true) {
    try {
        const response = await fetch('/inventario/api/productos');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const result = await response.json();
        if (!result.success) throw new Error(result.message);
        
        gridApi.setRowData(result.data || []);
    } catch (error) {
        console.error('Error cargando productos:', error);
        alert(`Error al cargar productos: ${error.message}`);
    }
}

/**
 * Abrir modal para crear nuevo producto
 */
function openModalCrear() {
    document.getElementById('productoId').value = '';
    document.getElementById('formProducto').reset();
    document.querySelector('.modal-title').textContent = 'Nuevo Producto';
    modal.show();
}

/**
 * Cargar producto para editar
 */
async function editarProducto(productoId) {
    try {
        const response = await fetch(`/inventario/api/productos/${productoId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const result = await response.json();
        if (!result.success) throw new Error(result.message);
        
        const producto = result.data;
        document.getElementById('productoId').value = producto.id;
        document.getElementById('productoNombre').value = producto.nombre;
        document.getElementById('productoMarca').value = producto.marcaId;
        document.getElementById('productoDescripcion').value = producto.descripcion || '';
        document.getElementById('productoUpc1').value = producto.upc1;
        document.getElementById('productoUpc2').value = producto.upc2 || '';
        document.getElementById('productoPrecio').value = producto.precio;
        
        document.querySelector('.modal-title').textContent = 'Editar Producto';
        modal.show();
    } catch (error) {
        console.error('Error cargando producto:', error);
        alert(`Error al cargar producto: ${error.message}`);
    }
}

/**
 * Guardar producto (crear o actualizar)
 */
async function guardarProducto(event) {
    event.preventDefault();
    
    const productoId = document.getElementById('productoId').value;
    const nombre = document.getElementById('productoNombre').value.trim();
    const marcaId = document.getElementById('productoMarca').value;
    const descripcion = document.getElementById('productoDescripcion').value.trim();
    const upc1 = document.getElementById('productoUpc1').value.trim();
    const upc2 = document.getElementById('productoUpc2').value.trim();
    const precio = document.getElementById('productoPrecio').value;
    
    // Validación
    if (!nombre || !marcaId || !upc1 || !precio) {
        alert('Nombre, Marca, UPC 1 y Precio son requeridos');
        return;
    }
    
    if (upc1 === upc2 && upc2) {
        alert('UPC 1 y UPC 2 no pueden ser iguales');
        document.getElementById('productoUpc2').focus();
        return;
    }
    
    try {
        let url, method, body;
        
        if (productoId) {
            // Actualizar
            url = `/inventario/api/productos/${productoId}`;
            method = 'PUT';
            body = JSON.stringify({ 
                nombre, 
                descripcion, 
                upc1, 
                upc2: upc2 || null, 
                marcaId: parseInt(marcaId), 
                precio: parseFloat(precio)
            });
        } else {
            // Crear
            url = '/inventario/api/productos';
            method = 'POST';
            body = JSON.stringify({ 
                nombre, 
                descripcion, 
                upc1, 
                upc2: upc2 || null, 
                marcaId: parseInt(marcaId), 
                precio: parseFloat(precio)
            });
        }
        
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            if (response.status === 409) {
                // Conflict - UPC duplicado
                if (result.message.includes('upc1') || result.message.includes('UPC 1')) {
                    document.getElementById('productoUpc1').focus();
                } else {
                    document.getElementById('productoUpc2').focus();
                }
            }
            throw new Error(result.message || 'Error al guardar');
        }
        
        modal.hide();
        loadProductos();
        alert(productoId ? 'Producto actualizado' : 'Producto creado');
    } catch (error) {
        console.error('Error guardando producto:', error);
        alert(`Error: ${error.message}`);
    }
}

/**
 * Cambiar estado de producto (activar/desactivar)
 */
async function toggleEstadoProducto(productoId) {
    const confirm_msg = 'Esta acción debe ser confirmada';
    if (!confirm(confirm_msg)) return;
    
    try {
        const response = await fetch(`/inventario/api/productos/${productoId}/estado`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || 'Error al cambiar estado');
        
        loadProductos();
        alert('Estado actualizado');
    } catch (error) {
        console.error('Error cambiando estado:', error);
        alert(`Error: ${error.message}`);
    }
}
