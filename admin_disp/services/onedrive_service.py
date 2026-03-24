"""
Servicio para interactuar con OneDrive/SharePoint usando Microsoft Graph API.
Provee funcionalidades para listar, descargar, eliminar y renombrar archivos PDF.
"""
import requests
import logging
from pathlib import Path
from datetime import datetime

# Importar autenticación centralizada
from .graph_auth import get_graph_token, get_site_id as get_cached_site_id

# Logger específico para operaciones de OneDrive
onedrive_logger = logging.getLogger('admin_disp.services.onedrive')
onedrive_logger.setLevel(logging.DEBUG)
onedrive_logger.propagate = False

# Configurar archivo de log específico
try:
    base_dir = Path(__file__).parent.parent
    log_dir = base_dir / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = str(log_dir / 'onedrive.log')
    if not any(getattr(h, 'baseFilename', None) == log_file for h in onedrive_logger.handlers):
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setLevel(logging.DEBUG)
        fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(fmt)
        onedrive_logger.addHandler(handler)
except Exception as e:
    # Si falla configuración de logger, usar logger básico
    import logging
    logging.getLogger('admin_disp.services.onedrive').error(f"Error configurando logger onedrive: {e}")


def get_site_id():
    """
    Wrapper para compatibilidad con código existente.
    Usa la implementación centralizada de graph_auth.
    """
    return get_cached_site_id()


def list_pdf_files_from_folder(folder_path: str):
    """
    Lista todos los archivos PDF en una carpeta de OneDrive.
    
    Args:
        folder_path: Ruta relativa desde el root del drive, ej: 'IT/Administracion de Dispositivos/2026/P-EM-000125'
    
    Returns:
        tuple: (success: bool, files: list[dict], error: str)
        Cada dict en files tiene: {'name': str, 'id': str, 'size': int, 'modified': str, 'download_url': str}
    """
    try:
        site_id = get_site_id()
        
        if not site_id:
            onedrive_logger.error('No se pudo obtener site_id')
            return False, [], 'No se pudo obtener site_id de SharePoint'
        
        token = get_graph_token()
        if not token:
            return False, [], 'No se pudo obtener token de autenticación'
        
        # Normalizar path - remover slashes al inicio y final
        folder_path = folder_path.strip('/')
        
        # URL para obtener los children de la carpeta
        # El root de /drive apunta directamente al OneDrive personal
        url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{folder_path}:/children'
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        onedrive_logger.info(f'Listando archivos en carpeta: {folder_path}')
        onedrive_logger.debug(f'URL: {url}')
        
        resp = requests.get(url, headers=headers, timeout=30)
        
        if resp.status_code == 404:
            # Carpeta no encontrada - intenta obtener información de la ruta padre para diagnóstico
            onedrive_logger.warning(f'Carpeta no encontrada: {folder_path}')
            onedrive_logger.info(f'Intentando diagnosticar: investigando estructura de carpetas')
            
            # Intenta investigar qué existe en la carpeta padre
            try:
                parent_path = '/'.join(folder_path.split('/')[:-1])  # Quitar último nivel
                if parent_path:
                    parent_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{parent_path}:/children'
                    onedrive_logger.debug(f'Investigando carpeta padre: {parent_path}')
                    parent_resp = requests.get(parent_url, headers=headers, timeout=10)
                    if parent_resp.status_code == 200:
                        parent_items = parent_resp.json().get('value', [])
                        subcarpetas = [item.get('name') for item in parent_items if 'folder' in item]
                        onedrive_logger.info(f'Subcarpetas en {parent_path}: {subcarpetas}')
            except Exception as e:
                onedrive_logger.debug(f'Error investigando carpeta padre: {e}')
            
            error_msg = f'Carpeta no encontrada: {folder_path}. Verifica que la estructura existe en OneDrive (IT/Administracion de Dispositivos/<YEAR>/<CODIGO_EMPLEADO>).'
            return False, [], error_msg
        
        if resp.status_code != 200:
            error_msg = f'Error accediendo a carpeta (HTTP {resp.status_code}): {resp.text}'
            onedrive_logger.error(error_msg)
            return False, [], error_msg
        
        resp.raise_for_status()
        data = resp.json()
        
        items = data.get('value', [])
        onedrive_logger.info(f'Total de items encontrados en {folder_path}: {len(items)}')
        
        # Filtrar solo archivos PDF
        pdf_files = []
        for item in items:
            if 'file' in item:  # Es un archivo, no una carpeta
                name = item.get('name', '')
                if name.lower().endswith('.pdf'):
                    file_info = {
                        'name': name,
                        'id': item.get('id'),
                        'size': item.get('size', 0),
                        'modified': item.get('lastModifiedDateTime', ''),
                        'download_url': item.get('@microsoft.graph.downloadUrl', '')
                    }
                    pdf_files.append(file_info)
                    onedrive_logger.debug(f'PDF encontrado: {name} ({file_info["size"]} bytes)')
        
        onedrive_logger.info(f'Total de archivos PDF: {len(pdf_files)}')
        return True, pdf_files, None
        
    except requests.exceptions.RequestException as e:
        error_msg = f'Error de red al listar archivos: {str(e)}'
        onedrive_logger.exception(error_msg)
        return False, [], error_msg
    except Exception as e:
        error_msg = f'Error inesperado al listar archivos: {str(e)}'
        onedrive_logger.exception(error_msg)
        return False, [], error_msg


def download_pdf_bytes(file_id: str):
    """
    Descarga los bytes de un archivo PDF desde OneDrive.
    
    Args:
        file_id: ID del archivo en OneDrive
    
    Returns:
        tuple: (success: bool, file_bytes: bytes, error: str)
    """
    try:
        site_id = get_site_id()
        
        if not site_id:
            onedrive_logger.error('No se pudo obtener site_id')
            return False, None, 'No se pudo obtener site_id'
        
        token = get_graph_token()
        if not token:
            return False, None, 'No se pudo obtener token de autenticación'
        
        # URL para descargar el contenido del archivo
        url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{file_id}/content'
        
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        onedrive_logger.info(f'Descargando archivo con ID: {file_id}')
        
        resp = requests.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        
        file_bytes = resp.content
        onedrive_logger.info(f'Archivo descargado exitosamente: {len(file_bytes)} bytes')
        
        return True, file_bytes, None
        
    except requests.exceptions.RequestException as e:
        error_msg = f'Error de red al descargar archivo: {str(e)}'
        onedrive_logger.exception(error_msg)
        return False, None, error_msg
    except Exception as e:
        error_msg = f'Error inesperado al descargar archivo: {str(e)}'
        onedrive_logger.exception(error_msg)
        return False, None, error_msg


def delete_file_by_id(file_id: str):
    """
    Elimina un archivo de OneDrive usando su ID.
    
    Args:
        file_id: ID del archivo en OneDrive
    
    Returns:
        tuple: (success: bool, error: str)
    """
    try:
        site_id = get_site_id()
        
        if not site_id:
            onedrive_logger.error('No se pudo obtener site_id')
            return False, 'No se pudo obtener site_id'
        
        token = get_graph_token()
        if not token:
            return False, 'No se pudo obtener token de autenticación'
        
        # URL para eliminar el archivo
        url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{file_id}'
        
        headers = {
            'Authorization': f'Bearer {token}'
        }
        
        onedrive_logger.info(f'Eliminando archivo con ID: {file_id}')
        
        resp = requests.delete(url, headers=headers, timeout=30)
        
        if resp.status_code == 204:
            onedrive_logger.info(f'✓ Archivo eliminado exitosamente: {file_id}')
            return True, None
        else:
            error_msg = f'Error eliminando archivo (HTTP {resp.status_code}): {resp.text}'
            onedrive_logger.error(error_msg)
            return False, error_msg
        
    except requests.exceptions.RequestException as e:
        error_msg = f'Error de red al eliminar archivo: {str(e)}'
        onedrive_logger.exception(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f'Error inesperado al eliminar archivo: {str(e)}'
        onedrive_logger.exception(error_msg)
        return False, error_msg


def rename_file_by_id(file_id: str, new_name: str):
    """
    Renombra un archivo en OneDrive usando su ID.
    
    Args:
        file_id: ID del archivo en OneDrive
        new_name: Nuevo nombre del archivo (incluyendo extensión)
    
    Returns:
        tuple: (success: bool, error: str)
    """
    try:
        site_id = get_site_id()
        
        if not site_id:
            onedrive_logger.error('No se pudo obtener site_id')
            return False, 'No se pudo obtener site_id'
        
        token = get_graph_token()
        if not token:
            return False, 'No se pudo obtener token de autenticación'
        
        # URL para actualizar el archivo
        url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{file_id}'
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        # Payload con el nuevo nombre
        payload = {
            'name': new_name
        }
        
        onedrive_logger.info(f'Renombrando archivo {file_id} a: {new_name}')
        
        resp = requests.patch(url, headers=headers, json=payload, timeout=30)
        
        if resp.status_code == 200:
            onedrive_logger.info(f'✓ Archivo renombrado exitosamente a: {new_name}')
            return True, None
        else:
            error_msg = f'Error renombrando archivo (HTTP {resp.status_code}): {resp.text}'
            onedrive_logger.error(error_msg)
            return False, error_msg
        
    except requests.exceptions.RequestException as e:
        error_msg = f'Error de red al renombrar archivo: {str(e)}'
        onedrive_logger.exception(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f'Error inesperado al renombrar archivo: {str(e)}'
        onedrive_logger.exception(error_msg)
        return False, error_msg


def ensure_folder_path(folder_path: str):
    """
    Crea la cadena de carpetas en SharePoint si no existe.
    
    Args:
        folder_path: Ruta relativa, ej: 'IT/CxC/2026'
    
    Returns:
        tuple: (success: bool, error: str)
    """
    try:
        site_id = get_site_id()
        token   = get_graph_token()
        if not site_id or not token:
            return False, 'No se pudo obtener credenciales'

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

        parts = folder_path.strip('/').split('/')
        current = ''
        for part in parts:
            parent = current if current else ''
            if parent:
                url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{parent}:/children'
            else:
                url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root/children'

            payload = {
                'name': part,
                'folder': {},
                '@microsoft.graph.conflictBehavior': 'replace',
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code not in (200, 201):
                # 409 Conflict también es válido (ya existe)
                if resp.status_code != 409:
                    onedrive_logger.warning(f'ensure_folder {part}: HTTP {resp.status_code}')
            current = f'{current}/{part}'.lstrip('/')

        return True, None

    except Exception as e:
        onedrive_logger.exception(f'Error en ensure_folder_path: {e}')
        return False, str(e)


def upload_file_bytes(folder_path: str, file_name: str, file_bytes: bytes):
    """
    Sube un archivo de bytes a SharePoint.
    Crea la carpeta si no existe.

    Args:
        folder_path: Ruta relativa, ej: 'IT/CxC/2026'
        file_name:   Nombre del archivo, ej: 'liq_2026-03-03_143022.pdf'
        file_bytes:  Contenido del archivo

    Returns:
        tuple: (success: bool, file_id: str, download_url: str, error: str)
    """
    try:
        site_id = get_site_id()
        token   = get_graph_token()
        if not site_id or not token:
            return False, None, None, 'No se pudo obtener credenciales'

        # Garantizar que la carpeta exista
        ok, err = ensure_folder_path(folder_path)
        if not ok:
            onedrive_logger.warning(f'ensure_folder_path falló: {err}')

        full_path = f'{folder_path.strip("/")}/{file_name}'
        url = (
            f'https://graph.microsoft.com/v1.0/sites/{site_id}'
            f'/drive/root:/{full_path}:/content'
        )

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/pdf',
        }

        onedrive_logger.info(f'Subiendo archivo: {full_path} ({len(file_bytes)} bytes)')
        resp = requests.put(url, headers=headers, data=file_bytes, timeout=120)

        if resp.status_code in (200, 201):
            data = resp.json()
            file_id      = data.get('id', '')
            download_url = data.get('@microsoft.graph.downloadUrl', '')
            onedrive_logger.info(f'✓ Archivo subido: {full_path} (id={file_id})')
            return True, file_id, download_url, None
        else:
            error_msg = f'Error subiendo archivo (HTTP {resp.status_code}): {resp.text[:200]}'
            onedrive_logger.error(error_msg)
            return False, None, None, error_msg

    except requests.exceptions.RequestException as e:
        error_msg = f'Error de red al subir archivo: {str(e)}'
        onedrive_logger.exception(error_msg)
        return False, None, None, error_msg
    except Exception as e:
        error_msg = f'Error inesperado al subir archivo: {str(e)}'
        onedrive_logger.exception(error_msg)
        return False, None, None, error_msg
