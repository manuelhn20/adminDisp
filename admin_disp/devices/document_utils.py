"""
Utilidades para manejo de documentos y correlativos.
Funciones helper reutilizables para evitar duplicación de código.
"""
import re
from typing import List, Optional


def has_correlativo_in_filename(filename: str, correlativos: List[str]) -> bool:
    """
    Verifica si el nombre de archivo contiene alguno de los correlativos dados.
    
    Args:
        filename: Nombre del archivo a verificar
        correlativos: Lista de correlativos a buscar (ej: ['000001', '000002'])
        
    Returns:
        True si el archivo contiene alguno de los correlativos, False en caso contrario
    """
    if not filename or not correlativos:
        return False
    
    # Quitar extensión (.pdf, etc.)
    base = filename.rsplit('.', 1)[0]
    
    # Tokenizar por cualquier separador no alfanumérico
    tokens = re.split(r'[^0-9A-Za-z]+', base)
    
    # Verificar contra TODOS los correlativos
    for correlativo_str in correlativos:
        # Buscar como token completo
        if correlativo_str in tokens:
            return True
        
        # Buscar en grupos de dígitos
        digit_groups = re.findall(r"\d+", base)
        if any(g == correlativo_str for g in digit_groups):
            return True
        
        # Búsqueda segura: correlativo como número entero aislado
        if re.search(r'(?<!\d)' + re.escape(correlativo_str) + r'(?!\d)', base):
            return True
    
    return False


def filter_documents_by_correlativos(documents: List[dict], correlativos: List[str]) -> List[dict]:
    """
    Filtra una lista de documentos para obtener solo aquellos que contienen los correlativos dados.
    
    Args:
        documents: Lista de diccionarios con al menos la clave 'name'
        correlativos: Lista de correlativos a buscar
        
    Returns:
        Lista filtrada de documentos
    """
    if not documents:
        return []
    
    return [
        doc for doc in documents 
        if has_correlativo_in_filename(doc.get('name', ''), correlativos)
    ]
