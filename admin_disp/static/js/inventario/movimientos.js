let gridApi, columnApi;
let productosStock = {};
const modal = new bootstrap.Modal(document.getElementById('modalMovimiento'));

// Column definitions para ag-grid
const colDefs = [
    { field: 'id', headerName: 'ID', width: 80, pinned: 'left' },
    { field: 'productoNombre', headerName: 'Producto', flex: 1, minWidth: 150 },
    { field: 'nombreMarca', headerName: 'Marca', width: 120 },
    { 
        field: 'tipo', 
        headerName: 'Tipo', 
        width: 100,
        cellRenderer: (params) => {
            const tipos = {
                'entrada': '<span class="badge bg-success">Entrada</span>',
                'salida': '<span class="badge bg-danger">Salida</span>',
                'ajuste': '<span class="badge bg-info">Ajuste</span>'
            };
            return tipos[params.value] || params.value;
        }
    },
    { field: 'cantidad', headerName: 'Cantidad', width: 100, cellStyle: { textAlign: 'right' } },
    { field: 'referencia', headerName: 'Referencia', width: 150 },
    { field: 'observacion', headerName: 'Observación', flex: 1, minWidth: 150 },
    { 
        field: 'fechaMovimiento', 
        headerName: 'Fecha', 
        width: 140,
        valueFormatter: (params) => {
            if (!params.value) return '-';
            return new Date(params.value).toLocaleDateString('es-ES');
        }
    },
    {
        field: 'acciones',
        headerName: 'Acciones',
        width: 120,
        pinned: 'right',
        cellRenderer: (params) => {
            const data = params.data;
            return `<button class="btn btn-sm btn-danger" onclick="eliminarMovimiento(${data.id})">Eliminar</button>`;
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
        cargarProductos();
        cargarStock();
        loadMovimientos();
    }
};

// Inicializar grid cuando se carga la página
document.addEventListener('DOMContentLoaded', () => {
    const gridDiv = document.getElementById('movimientosGrid');
    new agGrid.Grid(gridDiv, gridOptions);
    
    // Cargar stock cuando cambia el producto
    document.getElementById('movimientoProducto').addEventListener('change', actualizarStockActual);
    
    // Búsqueda rápida
    const searchInput = document.getElementById('movimientosPageSearch');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            gridApi.setQuickFilter(e.target.value);
        });
    }
});

/**
 * Cargar productos para select
 */
async function cargarProductos() {
    try {
        const response = await fetch('/inventario/api/productos');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const result = await response.json();
        if (!result.success) throw new Error(result.message);
        
        const selectProducto = document.getElementById('movimientoProducto');
        selectProducto.innerHTML = '<option value="">Seleccionar producto...</option>';
        
        (result.data || []).filter(p => p.estado === 1).forEach(producto => {
            const option = document.createElement('option');
            option.value = producto.id;
            option.textContent = `${producto.nombre} (${producto.upc1})`;
            selectProducto.appendChild(option);
        });
    } catch (error) {
        console.error('Error cargando productos:', error);
    }
}

/**
 * Cargar stock actual de todos los productos
 */
async function cargarStock() {
    try {
        const response = await fetch('/inventario/api/movimientos/stock');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const result = await response.json();
        if (!result.success) throw new Error(result.message);
        
        productosStock = {};
        (result.data || []).forEach(item => {
            productosStock[item.productoId] = item.stock || 0;
        });
    } catch (error) {
        console.error('Error cargando stock:', error);
    }
}

/**
 * Actualizar display de stock actual cuando cambia el producto seleccionado
 */
function actualizarStockActual() {
    const productoId = document.getElementById('movimientoProducto').value;
    const stock = productosStock[productoId] || 0;
    document.getElementById('stockActual').textContent = `Stock: ${stock}`;
}

/**
 * Cargar todos los movimientos
 */
async function loadMovimientos() {
    try {
        const tipo = document.getElementById('filterTipo').value;
        let url = '/inventario/api/movimientos';
        if (tipo) {
            url += `?tipo=${tipo}`;
        }
        
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const result = await response.json();
        if (!result.success) throw new Error(result.message);
        
        gridApi.setRowData(result.data || []);
    } catch (error) {
        console.error('Error cargando movimientos:', error);
        alert(`Error al cargar movimientos: ${error.message}`);
    }
}

/**
 * Abrir modal para crear nuevo movimiento
 */
function openModalCrear() {
    document.getElementById('formMovimiento').reset();
    document.getElementById('tipoEntrada').checked = true;
    document.getElementById('stockActual').textContent = '-';
    modal.show();
}

/**
 * Guardar movimiento
 */
async function guardarMovimiento(event) {
    event.preventDefault();
    
    const productoId = document.getElementById('movimientoProducto').value;
    const tipo = document.querySelector('input[name="movimientoTipo"]:checked').value;
    const cantidad = parseInt(document.getElementById('movimientoCantidad').value);
    const referencia = document.getElementById('movimientoReferencia').value.trim();
    const observacion = document.getElementById('movimientoObservacion').value.trim();
    
    // Validación
    if (!productoId) {
        alert('Debe seleccionar un producto');
        return;
    }
    
    if (cantidad === 0) {
        alert('La cantidad no puede ser cero');
        return;
    }
    
    try {
        const response = await fetch('/inventario/api/movimientos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                productoId: parseInt(productoId),
                tipo,
                cantidad,
                referencia: referencia || null,
                observacion: observacion || null
            })
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.message || 'Error al guardar');
        }
        
        modal.hide();
        cargarStock();
        loadMovimientos();
        alert('Movimiento creado');
    } catch (error) {
        console.error('Error guardando movimiento:', error);
        alert(`Error: ${error.message}`);
    }
}

/**
 * Eliminar movimiento (soft delete)
 */
async function eliminarMovimiento(movimientoId) {
    const confirm_msg = '¿Está seguro de que desea eliminar este movimiento?';
    if (!confirm(confirm_msg)) return;
    
    try {
        const response = await fetch(`/inventario/api/movimientos/${movimientoId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || 'Error al eliminar');
        
        cargarStock();
        loadMovimientos();
        alert('Movimiento eliminado');
    } catch (error) {
        console.error('Error eliminando movimiento:', error);
        alert(`Error: ${error.message}`);
    }
}
