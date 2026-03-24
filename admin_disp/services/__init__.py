# Módulo de servicios
"""
Servicios de la aplicación:
- docexp: Generación de documentos DOCX
- docgen: Generación de documentos (legacy)
- docx_common: Utilidades comunes para DOCX
- documento_folder_service: Gestión de documentos en OneDrive (Graph API)
- empleados_sync: Sincronización de empleados
- printer_reader: Lectura de configuración de impresoras
- onedrive_service: Interacción con OneDrive/SharePoint (Graph API)
- graph_auth: Autenticación centralizada para Microsoft Graph
"""

# Importar módulos principales para que estén disponibles
try:
    from . import docexp
    from . import docgen
    from . import docx_common
    from . import documento_folder_service
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"No se pudieron importar algunos módulos de services: {e}")

__all__ = [
    'docexp',
    'docgen',
    'docx_common',
    'documento_folder_service',
]
