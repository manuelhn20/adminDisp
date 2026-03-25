"""
Helper module for managing correlativos using the new format-based system.

This module provides functions to:
1. Determine the correct format based on device category
2. Generate correlativos using the stored procedure sp_GenerarCorrelativo
3. Extract and format correlativos for display
"""

from typing import Optional, Dict, List
import logging
import pyodbc

logger = logging.getLogger(__name__)

# Mapeo de categorías de dispositivo a formatos de correlativo
CORRELATIVO_FORMATS = {
    # Certificado de Compromiso y Entrega de Teléfono Corporativo
    'PRO-TI-CE-001': ['Celular'],
    
    # Memorando de Entrega (para Celular)
    'PRO-TI-CE-002': ['Celular'],
    
    # Entrega de Tablet / Teléfono
    'PRO-TI-CE-003': ['Tablet'],
    
    # Certificado Entrega de Computadora
    'PRO-TI-CE-004': ['Laptop'],
    
    # Entrega de Periférico
    'PRO-TI-CE-005': ['Teclado', 'Mouse', 'Auriculares', 'Monitor', 'Impresora', 
                       'Teléfono VoIP', 'Router', 'Switch', 'Adaptador']
}


def get_formats_for_categoria(categoria: str) -> List[str]:
    """
    Retorna la lista de formatos de correlativo que corresponden a una categoría de dispositivo.
    
    Args:
        categoria: Categoría del dispositivo (ej: 'Celular', 'Laptop', etc.)
        
    Returns:
        Lista de formatos (ej: ['PRO-TI-CE-001', 'PRO-TI-CE-002'] para Celular)
        
    Raises:
        ValueError: Si la categoría no tiene formatos asociados
    """
    categoria_normalized = (categoria or '').strip()
    
    formatos_encontrados = []
    for formato, categorias in CORRELATIVO_FORMATS.items():
        # Comparación case-insensitive
        if any(cat.lower() == categoria_normalized.lower() for cat in categorias):
            formatos_encontrados.append(formato)
    
    if not formatos_encontrados:
        raise ValueError(f"No se encontró formato de correlativo para la categoría: {categoria}")
    
    return sorted(formatos_encontrados)


def get_primary_format_for_categoria(categoria: str) -> str:
    """
    Retorna el formato primario de correlativo para una categoría.
    
    Args:
        categoria: Categoría del dispositivo
        
    Returns:
        Formato primario (el primero de la lista)
    """
    formatos = get_formats_for_categoria(categoria)
    return formatos[0]


def generar_correlativo(db_connection, formato: str) -> Optional[str]:
    """
    Genera un nuevo correlativo usando el stored procedure sp_GenerarCorrelativo.
    
    Args:
        db_connection: Conexión a la base de datos
        formato: Formato del correlativo (ej: 'PRO-TI-CE-001')
        
    Returns:
        Correlativo completo generado (ej: 'PRO-TI-CE-001-000001')
        None si hay error
    """
    try:
        cursor = db_connection.get_cursor()
        
        # Llamar al SP con auditoría usando snake_case
        cursor.execute("""
            DECLARE @correlativo VARCHAR(100);
            EXEC sp_generar_correlativo_con_log @formato = ?, @correlativo = @correlativo OUTPUT;
            SELECT @correlativo AS correlativo;
        """, (formato,))
        
        row = cursor.fetchone()
        result = row[0] if row else None
        
        cursor.close()
        
        if result:
            logger.debug(f"Correlativo generado para formato {formato}")
            return result
        else:
            logger.error(f"El SP no retornó correlativo para formato {formato}")
            return None
            
    except Exception as e:
        logger.exception(f"Error ejecutando sp_GenerarCorrelativo para formato {formato}: {e}")
        return None


def generar_correlativos_para_asignacion(db_connection, categoria: str) -> Dict[str, str]:
    """
    Genera todos los correlativos necesarios para una asignación según su categoría.
    
    Args:
        db_connection: Conexión a la base de datos
        categoria: Categoría del dispositivo
        
    Returns:
        Diccionario con formato como clave y correlativo generado como valor
        Ejemplo: {'PRO-TI-CE-001': 'PRO-TI-CE-001-000123', 'PRO-TI-CE-002': 'PRO-TI-CE-002-000124'}
    """
    formatos = get_formats_for_categoria(categoria)
    correlativos = {}
    
    for formato in formatos:
        correlativo = generar_correlativo(db_connection, formato)
        if correlativo:
            correlativos[formato] = correlativo
        else:
            logger.error(f"No se pudo generar correlativo para formato {formato}")
    
    return correlativos


def extraer_numero_correlativo(correlativo_completo) -> str:
    """
    Extrae el número de 6 dígitos de un correlativo completo.
    
    Args:
        correlativo_completo: Correlativo en formato PRO-TI-CE-XXX-NNNNNN (str) o número (int)
        
    Returns:
        Número de correlativo con 6 dígitos (ej: '000123')
        '000000' si no se puede extraer
    """
    if not correlativo_completo:
        return '000000'
    
    try:
        # Si es un INT, formatearlo directamente
        if isinstance(correlativo_completo, int):
            return str(correlativo_completo).zfill(6)
        
        # Si es string, intentar extraer del formato completo
        # El correlativo tiene formato: PRO-TI-CE-XXX-NNNNNN
        # Tomamos la última parte después del último guión
        partes = correlativo_completo.split('-')
        if len(partes) >= 5:  # PRO, TI, CE, XXX, NNNNNN
            return partes[-1].zfill(6)
        
        # Si el string es solo un número, formatearlo
        if correlativo_completo.isdigit():
            return correlativo_completo.zfill(6)
            
        return '000000'
    except Exception as e:
        logger.warning(f"Error extrayendo número de correlativo de '{correlativo_completo}': {e}")
        return '000000'


def formatear_correlativo_para_display(correlativo_completo: Optional[str]) -> str:
    """
    Formatea un correlativo para mostrar en la UI.
    
    Args:
        correlativo_completo: Correlativo completo o None
        
    Returns:
        Correlativo formateado para display
    """
    if not correlativo_completo:
        return '-'
    
    return correlativo_completo


def validar_formato(formato: str) -> bool:
    """
    Valida si un formato de correlativo es válido.
    
    Args:
        formato: Formato a validar (ej: 'PRO-TI-CE-001')
        
    Returns:
        True si el formato es válido, False en caso contrario
    """
    return formato in CORRELATIVO_FORMATS


def get_all_formats() -> List[str]:
    """
    Retorna todos los formatos de correlativo disponibles.
    
    Returns:
        Lista de todos los formatos
    """
    return sorted(CORRELATIVO_FORMATS.keys())


# Función de conveniencia para obtener el formato y generar en un solo paso
def obtener_o_generar_correlativo(db_connection, asignacion_id: int, categoria: str, 
                                   correlativo_actual: Optional[int] = None) -> Optional[str]:
    """
    Obtiene el correlativo actual o genera uno nuevo si no existe.
    
    Esta es una función de conveniencia que:
    1. Si ya existe un correlativo (INT), lo formatea y retorna
    2. Si no existe, genera uno nuevo usando el formato primario de la categoría
    3. Guarda el correlativo en la base de datos como INT
    
    Args:
        db_connection: Conexión a la base de datos
        asignacion_id: ID de la asignación
        categoria: Categoría del dispositivo
        correlativo_actual: Correlativo actual como INT (si existe)
        
    Returns:
        Correlativo completo en formato PRO-TI-CE-XXX-NNNNNN (existente o generado)
        None si hay error
    """
    # Si ya existe, formatearlo y retornarlo
    if correlativo_actual:
        # correlativo_actual es INT, necesitamos formatearlo al formato completo
        formato = get_primary_format_for_categoria(categoria)
        numero_formateado = str(correlativo_actual).zfill(6)
        correlativo_completo = f"{formato}-{numero_formateado}"
        return correlativo_completo
    
    try:
        # Obtener el formato primario para la categoría
        formato = get_primary_format_for_categoria(categoria)
        
        # Generar el correlativo (retorna formato completo PRO-TI-CE-XXX-NNNNNN)
        correlativo_completo = generar_correlativo(db_connection, formato)
        
        if correlativo_completo:
            # Extraer el número INT para guardar en BD
            correlativo_numero = int(correlativo_completo.split('-')[-1])
            
            # Guardar en la base de datos como INT
            cursor = db_connection.get_cursor()
            cursor.execute(
                "UPDATE asignacion SET correlativo = ? WHERE id_asignacion = ? AND correlativo IS NULL",
                (correlativo_numero, asignacion_id)
            )
            db_connection.commit()
            cursor.close()
            
            return correlativo_completo
        else:
            logger.error(f"No se pudo generar correlativo para asignación {asignacion_id}")
            return None
            
    except Exception as e:
        logger.exception(f"Error obteniendo/generando correlativo para asignación {asignacion_id}: {e}")
        return None
