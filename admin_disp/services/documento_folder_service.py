"""
Servicio para gestión de documentos en OneDrive usando Microsoft Graph API
Estructura: IT/Administracion de Dispositivos/{YEAR}/{CODIGO_EMPLEADO}/

Ejemplo: IT/Administracion de Dispositivos/2026/P-EM-000125/documento.pdf
Todos los archivos se almacenan directamente en OneDrive (no hay guardado local).
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from flask import current_app
from functools import lru_cache
import time

# Logger - usa configuración centralizada de app.py (escribirá a services.log)
logger = logging.getLogger("admin_disp.services.documento_folder_service")
logger.setLevel(logging.DEBUG)  # Asegurar que DEBUG está habilitado

# Caché simple en memoria para evitar llamadas repetidas a OneDrive
# Almacena: (employee_code, timestamp) -> (success, files, error)
_onedrive_cache = {}
# Disable onedrive in-memory cache globally. Set to False to bypass cache entirely.
_CACHE_ENABLED = False
_CACHE_TTL = 60  # segundos (kept for compatibility if re-enabled)

# ==============================================================================
# FUNCIONES PRINCIPALES - TODO EN ONEDRIVE (SIN GUARDADO LOCAL)
# ==============================================================================
# save_documento_file y save_firma_file ahora usan Graph API directamente
# ==============================================================================

def save_documento_file(year, month, employee_code, filename, file_content):
    """
    Guarda un archivo de documento directamente en OneDrive usando Graph API.
    
    Args:
        year (int): Año (ej: 2026)
        month (int): Mes (1-12)
        employee_code (str): Código del empleado (ej: P-EM-000125)
        filename (str): Nombre del archivo (ej: "asignacion.pdf")
        file_content (bytes): Contenido del archivo
    
    Returns:
        tuple: (success: bool, file_path: str, error_msg: str or None)
    """
    try:
        # Validar que file_content es bytes
        if not isinstance(file_content, bytes):
            error_msg = f"Error: file_content no es bytes, es {type(file_content).__name__}"
            logger.error(error_msg)
            return False, None, error_msg

        if len(file_content) == 0:
            error_msg = "Error: file_content está vacío (0 bytes)"
            logger.error(error_msg)
            return False, None, error_msg

        # Subir directamente a OneDrive usando Graph API
        year_str = str(year)
        folder_path = f"IT/Administracion de Dispositivos/{year_str}/{employee_code}"
        
        logger.info(f"Subiendo archivo a OneDrive: {folder_path}/{filename} ({len(file_content)} bytes)")
        
        from admin_disp.services.onedrive_service import get_graph_token, get_site_id
        import requests
        
        site_id = get_site_id()
        if not site_id:
            error_msg = "No se pudo obtener site_id de OneDrive"
            logger.error(error_msg)
            return False, None, error_msg
        
        token = get_graph_token()
        if not token:
            error_msg = "No se pudo obtener token de autenticación"
            logger.error(error_msg)
            return False, None, error_msg
        
        # URL para subir archivo (PUT method crea carpetas automáticamente)
        upload_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{folder_path}/{filename}:/content'
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/octet-stream'
        }
        
        resp = requests.put(upload_url, headers=headers, data=file_content, timeout=60)
        
        if resp.status_code in (200, 201):
            try:
                data = resp.json()
                web_url = data.get('webUrl', 'uploaded')
                logger.info(f"Archivo subido exitosamente: {folder_path}/{filename}")
                return True, web_url, None
            except:
                logger.info(f"Archivo subido exitosamente (sin URL): {folder_path}/{filename}")
                return True, 'uploaded', None
        else:
            error_msg = f"Error subiendo archivo (HTTP {resp.status_code}): {resp.text}"
            logger.error(error_msg)
            return False, None, error_msg
        
    except Exception as e:
        logger.exception('Error subiendo archivo a OneDrive: %s', e)
        return False, None, str(e)


def save_firma_file(year, month, employee_code, signature_type, file_content, filename=None):
    """
    Guarda un archivo de firma directamente en OneDrive usando Graph API.
    
    Args:
        year (int): Año (ej: 2026)
        month (int): Mes (1-12)
        employee_code (str): Código del empleado (ej: P-EM-000125)
        signature_type (str): Tipo de firma ('responsable' o 'empleado')
        file_content (bytes): Contenido del archivo
        filename (str, optional): Nombre custom del archivo
    
    Returns:
        tuple: (success: bool, file_path: str, error_msg: str or None)
    """
    try:
        # Generar nombre de archivo si no se proporciona
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"firma_{signature_type}_{timestamp}.pdf"

        year_str = str(year)
        folder_path = f"IT/Administracion de Dispositivos/{year_str}/{employee_code}"
        
        logger.info(f"Subiendo firma a OneDrive: {folder_path}/{filename} ({len(file_content)} bytes)")
        
        from admin_disp.services.onedrive_service import get_graph_token, get_site_id
        import requests
        
        site_id = get_site_id()
        if not site_id:
            error_msg = "No se pudo obtener site_id de OneDrive"
            logger.error(error_msg)
            return False, None, error_msg
        
        token = get_graph_token()
        if not token:
            error_msg = "No se pudo obtener token de autenticación"
            logger.error(error_msg)
            return False, None, error_msg
        
        # URL para subir archivo
        upload_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{folder_path}/{filename}:/content'
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/pdf'
        }
        
        resp = requests.put(upload_url, headers=headers, data=file_content, timeout=60)
        
        if resp.status_code in (200, 201):
            try:
                data = resp.json()
                web_url = data.get('webUrl', 'uploaded')
                logger.info(f"Firma subida exitosamente: {folder_path}/{filename}")
                return True, web_url, None
            except:
                logger.info(f"Firma subida exitosamente (sin URL): {folder_path}/{filename}")
                return True, 'uploaded', None
        else:
            error_msg = f"Error subiendo firma (HTTP {resp.status_code}): {resp.text}"
            logger.error(error_msg)
            return False, None, error_msg
        
    except Exception as e:
        logger.exception('Error subiendo firma a OneDrive: %s', e)
        return False, None, str(e)

# ==============================================================================
# NUEVAS FUNCIONES - SISTEMA DE DOCUMENTACIÓN CON ONEDRIVE DIRECTO
# Basado en doc/proceso.txt
# ==============================================================================

def save_documento_to_onedrive(employee_code, filename, file_content):
    """
    Guarda un documento PDF directamente en OneDrive usando Microsoft Graph.
    
    Ruta OneDrive: IT/Administracion de Dispositivos/{YEAR}/{CODIGO_EMPLEADO}/filename.pdf
    
    Args:
        employee_code (str): Código del empleado (ej: P-EM-000125)
        filename (str): Nombre del archivo PDF
        file_content (bytes): Contenido del archivo PDF
    
    Returns:
        tuple: (success: bool, url_or_path: str, error_msg: str or None)
    """
    try:
        # Validar que file_content es bytes
        if not isinstance(file_content, bytes):
            error_msg = f"Error: file_content no es bytes, es {type(file_content).__name__}"
            logger.error(error_msg)
            return False, None, error_msg
        
        if len(file_content) == 0:
            error_msg = "Error: file_content está vacío (0 bytes)"
            logger.error(error_msg)
            return False, None, error_msg
        
        # Validar que es PDF
        if not filename.lower().endswith('.pdf'):
            error_msg = f"Error: Solo se permiten archivos PDF. Recibido: {filename}"
            logger.error(error_msg)
            return False, None, error_msg
        
        # Obtener año actual
        year = str(datetime.now().year)
        
        # Ruta en OneDrive: IT/Administracion de Dispositivos/{YEAR}/{CODIGO_EMPLEADO}
        folder_path = f"IT/Administracion de Dispositivos/{year}/{employee_code}"
        
        logger.info(f"Subiendo PDF a OneDrive: {folder_path}/{filename} ({len(file_content)} bytes)")
        
        # Usar onedrive_service para subir
        from admin_disp.services.onedrive_service import get_graph_token, get_site_id
        
        site_id = get_site_id()
        if not site_id:
            error_msg = "No se pudo obtener site_id de OneDrive"
            logger.error(error_msg)
            return False, None, error_msg
        
        token = get_graph_token()
        if not token:
            error_msg = "No se pudo obtener token de autenticación"
            logger.error(error_msg)
            return False, None, error_msg
        
        # URL para subir el archivo (PUT)
        upload_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{folder_path}/{filename}:/content'
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/pdf'
        }
        
        logger.info(f"Subiendo a: {upload_url}")
        
        import requests
        resp = requests.put(upload_url, headers=headers, data=file_content, timeout=60)
        
        if resp.status_code in (200, 201):
            try:
                data = resp.json()
                web_url = data.get('webUrl', 'uploaded')
                logger.info(f"PDF subido exitosamente: {folder_path}/{filename}")
                logger.info(f"URL: {web_url}")
                return True, web_url, None
            except:
                logger.info(f"PDF subido exitosamente (sin URL): {folder_path}/{filename}")
                return True, 'uploaded', None
        else:
            error_msg = f"Error subiendo PDF (HTTP {resp.status_code}): {resp.text}"
            logger.error(error_msg)
            return False, None, error_msg
        
    except Exception as e:
        error_msg = f"Error subiendo a OneDrive: {str(e)}"
        logger.exception(error_msg)
        return False, None, error_msg


def list_documentos_from_onedrive(employee_code, use_cache=False):
    """
    Lista todos los documentos PDFs de un empleado en OneDrive.
    
    Ruta: IT/Administracion de Dispositivos/{YEAR}/{CODIGO_EMPLEADO}/
    
    Args:
        employee_code (str): Código del empleado
        use_cache (bool): Si True, usa caché para evitar llamadas repetidas (default: True)
    
    Returns:
        tuple: (success: bool, files_list: list, error_msg: str or None)
    """
    # [DIAGNÓSTICO] Logging de entrada para rastrear ejecución
    logger.info(f"[ENTRY] list_documentos_from_onedrive llamado - employee: {employee_code}, use_cache={use_cache}")
    
    # Verificar caché primero (solo si está habilitado y se solicitó)
    if _CACHE_ENABLED and use_cache and employee_code in _onedrive_cache:
        cached_result, cached_time = _onedrive_cache[employee_code]
        if time.time() - cached_time < _CACHE_TTL:
            logger.info(f"[CACHE-HIT] ✓ Usando caché para {employee_code} (edad: {int(time.time() - cached_time)}s)")
            return cached_result
        else:
            # Cache expirado, eliminarlo
            logger.info(f"[CACHE-EXPIRED] Caché expirado para {employee_code} (edad: {int(time.time() - cached_time)}s)")
            del _onedrive_cache[employee_code]
    
    try:
        # Obtener año actual
        year = str(datetime.now().year)
        folder_path = f"IT/Administracion de Dispositivos/{year}/{employee_code}"
        
        logger.info(f"Listando documentos de OneDrive: {folder_path}")
        
        # Usar onedrive_service
        from admin_disp.services.onedrive_service import list_pdf_files_from_folder
        
        success, files, error = list_pdf_files_from_folder(folder_path)
        
        result = None
        if success:
            logger.info(f"Documentos listados: {len(files)} archivos encontrados")
            result = (True, files, None)
        else:
            logger.warning(f"Error listando documentos: {error}")
            result = (False, [], error)
        
        # Guardar en caché solo si fue exitoso y la caché está habilitada
        if _CACHE_ENABLED and use_cache and success:
            _onedrive_cache[employee_code] = (result, time.time())
            logger.info(f"[CACHE-SAVE] ✓ Guardado caché para {employee_code} ({len(files)} archivos)")
        
        return result
        
    except Exception as e:
        error_msg = f"Error listando archivos de OneDrive: {str(e)}"
        logger.exception(error_msg)
        return False, None, error_msg


def delete_documento_from_onedrive(employee_code, filename):
    """
    Elimina un documento PDF de OneDrive usando Microsoft Graph API.
    
    Args:
        employee_code (str): Código del empleado
        filename (str): Nombre del archivo a eliminar
    
    Returns:
        tuple: (success: bool, error_msg: str or None)
    """
    try:
        from datetime import datetime
        
        year = datetime.now().year
        remote_path = f"IT/Administracion de Dispositivos/{year}/{employee_code}"
        
        logger.info(f'[DELETE-DOC] Iniciando eliminación: {remote_path}/{filename}')
        
        # Importar funciones de onedrive_service
        from admin_disp.services.onedrive_service import list_pdf_files_from_folder, delete_file_by_id
        
        # Primero listar archivos para obtener el ID del archivo
        success, files, error = list_pdf_files_from_folder(remote_path)
        if not success:
            logger.error(f'[DELETE-DOC] Error listando archivos: {error}')
            return False, f"Error listando archivos: {error}"
        
        # Buscar el archivo por nombre
        file_to_delete = None
        for f in files:
            if f.get('name') == filename:
                file_to_delete = f
                break
        
        if not file_to_delete:
            logger.warning(f'[DELETE-DOC] Archivo no encontrado: {filename}')
            return False, f"Archivo no encontrado: {filename}"
        
        file_id = file_to_delete.get('id')
        logger.info(f'[DELETE-DOC] Archivo encontrado: {filename}, ID: {file_id}')
        
        # Eliminar usando la API
        success, error = delete_file_by_id(file_id)
        if success:
            logger.info(f"[DELETE-DOC] ✓ Archivo eliminado exitosamente: {filename}")
            return True, None
        else:
            logger.error(f'[DELETE-DOC] Error eliminando archivo: {error}')
            return False, error
        
    except Exception as e:
        error_msg = f"Error eliminando archivo de OneDrive: {str(e)}"
        logger.exception(error_msg)
        return False, error_msg


def delete_all_documentos_from_onedrive(employee_code):
    """
    Elimina TODOS los documentos de un empleado en OneDrive.
    Útil para cancelar proceso de documentación (FLUJO D).
    
    Args:
        employee_code (str): Código del empleado
    
    Returns:
        tuple: (success: bool, deleted_count: int, error_msg: str or None)
    """
    try:
        # Listar archivos primero
        success, files, error = list_documentos_from_onedrive(employee_code)
        if not success:
            return False, 0, error
        
        if not files:
            return True, 0, None
        
        # Eliminar cada archivo
        deleted_count = 0
        for file_info in files:
            success, error = delete_documento_from_onedrive(employee_code, file_info['name'])
            if success:
                deleted_count += 1
            else:
                logger.warning(f"No se pudo eliminar {file_info['name']}: {error}")
        
        logger.info(f"Eliminados {deleted_count}/{len(files)} archivos de {employee_code}")
        
        return True, deleted_count, None
        
    except Exception as e:
        error_msg = f"Error eliminando todos los documentos: {str(e)}"
        logger.exception(error_msg)
        return False, 0, error_msg


def rename_documento_in_onedrive(employee_code, old_filename, new_filename):
    """
    Renombra un documento en OneDrive usando Microsoft Graph API.
    
    Args:
        employee_code (str): Código del empleado
        old_filename (str): Nombre actual del archivo
        new_filename (str): Nuevo nombre del archivo
    
    Returns:
        tuple: (success: bool, error_msg: str or None)
    """
    try:
        from datetime import datetime
        
        year = datetime.now().year
        remote_path = f"IT/Administracion de Dispositivos/{year}/{employee_code}"
        
        logger.info(f'[RENAME-DOC] Iniciando renombrado: {old_filename} -> {new_filename}')
        
        # Importar funciones de onedrive_service
        from admin_disp.services.onedrive_service import list_pdf_files_from_folder, rename_file_by_id
        
        # Primero listar archivos para obtener el ID del archivo
        success, files, error = list_pdf_files_from_folder(remote_path)
        if not success:
            logger.error(f'[RENAME-DOC] Error listando archivos: {error}')
            return False, f"Error listando archivos: {error}"
        
        # Buscar el archivo por nombre
        file_to_rename = None
        for f in files:
            if f.get('name') == old_filename:
                file_to_rename = f
                break
        
        if not file_to_rename:
            logger.warning(f'[RENAME-DOC] Archivo no encontrado: {old_filename}')
            return False, f"Archivo no encontrado: {old_filename}"
        
        file_id = file_to_rename.get('id')
        logger.info(f'[RENAME-DOC] Archivo encontrado: {old_filename}, ID: {file_id}')
        
        # Renombrar usando la API
        success, error = rename_file_by_id(file_id, new_filename)
        if success:
            logger.info(f"[RENAME-DOC] ✓ Archivo renombrado exitosamente: {old_filename} -> {new_filename}")
            return True, None
        else:
            logger.error(f'[RENAME-DOC] Error renombrando archivo: {error}')
            return False, error
        
    except Exception as e:
        error_msg = f"Error renombrando archivo: {str(e)}"
        logger.exception(error_msg)
        return False, error_msg


# ============================================================================
# FIN NUEVAS FUNCIONES
# ============================================================================


def write_revision_log(year, month, employee_code, usuario, archivos_aprobados, observaciones=""):
    """
    Crea/actualiza archivo de log de revisión de documentos.
    
    Args:
        year (int): Año
        month (int): Mes
        employee_code (str): Código del empleado
        usuario (str): Usuario que realizó la revisión
        archivos_aprobados (list): Lista de nombres de archivos aprobados
        observaciones (str): Observaciones adicionales (opcional)
    
    Returns:
        tuple: (success: bool, file_path: str, error_msg: str or None)
    """
    try:
        # Construir contenido del log
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"\n{'='*80}\n"
        log_entry += f"REVISIÓN - {timestamp}\n"
        log_entry += f"Usuario: {usuario}\n"
        log_entry += f"Archivos Aprobados:\n"
        for archivo in archivos_aprobados:
            log_entry += f"  ✓ {archivo}\n"
        if observaciones:
            log_entry += f"Observaciones: {observaciones}\n"
        log_entry += f"{'='*80}\n"

        # Subir log como archivo de texto a OneDrive en la carpeta del empleado
        year_str = str(year)
        folder_path = f"IT/Administracion de Dispositivos/{year_str}/{employee_code}"
        filename = "revision_log.log"
        
        logger.info(f"Subiendo log de revisión a OneDrive: {folder_path}/{filename}")
        
        # Usar Graph API directamente para subir el archivo
        from admin_disp.services.onedrive_service import get_graph_token, get_site_id
        import requests
        
        site_id = get_site_id()
        if not site_id:
            error_msg = "No se pudo obtener site_id de OneDrive"
            logger.error(error_msg)
            return False, None, error_msg
        
        token = get_graph_token()
        if not token:
            error_msg = "No se pudo obtener token de autenticación"
            logger.error(error_msg)
            return False, None, error_msg
        
        # URL para subir archivo
        upload_url = f'https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{folder_path}/{filename}:/content'
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'text/plain; charset=utf-8'
        }
        
        content_bytes = log_entry.encode('utf-8')
        resp = requests.put(upload_url, headers=headers, data=content_bytes, timeout=60)
        
        if resp.status_code in (200, 201):
            try:
                data = resp.json()
                web_url = data.get('webUrl', 'uploaded')
                logger.info(f"Log de revisión subido exitosamente: {folder_path}/{filename}")
                return True, web_url, None
            except:
                logger.info(f"Log de revisión subido exitosamente (sin URL): {folder_path}/{filename}")
                return True, 'uploaded', None
        else:
            error_msg = f"Error subiendo log (HTTP {resp.status_code}): {resp.text}"
            logger.error(error_msg)
            return False, None, error_msg

    except Exception as e:
        logger.exception('Error escribiendo log de revisión en OneDrive: %s', e)
        return False, None, str(e)

def download_documento_from_onedrive(employee_code, filename):
    """
    Descarga un documento PDF de OneDrive usando onedrive_service.
    Estructura: IT/Administracion de Dispositivos/{YEAR}/{employee_code}/
    
    Args:
        employee_code (str): Código del empleado
        filename (str): Nombre del archivo a descargar
    
    Returns:
        tuple: (success: bool, file_bytes: bytes or None, error: str or None)
    """
    try:
        from datetime import datetime
        
        year = datetime.now().year
        folder_path = f"IT/Administracion de Dispositivos/{year}/{employee_code}"
        
        logger.info(f"[DOWNLOAD-DOC] Iniciando descarga: {folder_path}/{filename}")
        
        # 1. Listar archivos en la carpeta para obtener el file_id
        from admin_disp.services.onedrive_service import list_pdf_files_from_folder, download_pdf_bytes
        
        logger.info(f"[DOWNLOAD-DOC] Listando archivos en: {folder_path}")
        success, files, error = list_pdf_files_from_folder(folder_path)
        
        if not success:
            error_msg = f"Error listando carpeta {folder_path}: {error}"
            logger.error(f"[DOWNLOAD-DOC] {error_msg}")
            return False, None, error_msg
        
        logger.info(f"[DOWNLOAD-DOC] Encontrados {len(files)} archivos en carpeta")
        
        # 2. Buscar el archivo por nombre
        file_item = None
        for file_info in files:
            logger.debug(f"[DOWNLOAD-DOC] Comparando: '{file_info.get('name')}' == '{filename}'")
            if file_info.get('name') == filename:
                file_item = file_info
                logger.info(f"[DOWNLOAD-DOC] Archivo encontrado: {filename}, ID: {file_info.get('id')}")
                break
        
        if not file_item:
            available_files = [f.get('name') for f in files]
            error_msg = f"Archivo '{filename}' no encontrado en {folder_path}. Archivos disponibles: {available_files}"
            logger.error(f"[DOWNLOAD-DOC] {error_msg}")
            return False, None, error_msg
        
        file_id = file_item.get('id')
        if not file_id:
            error_msg = f"ID no disponible para archivo {filename}"
            logger.error(f"[DOWNLOAD-DOC] {error_msg}")
            return False, None, error_msg
        
        # 3. Descargar usando el file_id
        logger.info(f"[DOWNLOAD-DOC] Descargando archivo con ID: {file_id}")
        success, file_bytes, error = download_pdf_bytes(file_id)
        
        if not success:
            error_msg = f"Error descargando archivo: {error}"
            logger.error(f"[DOWNLOAD-DOC] {error_msg}")
            return False, None, error_msg
        
        logger.info(f"[DOWNLOAD-DOC] ✓ Archivo descargado exitosamente: {filename} ({len(file_bytes)} bytes)")
        return True, file_bytes, None
        
    except Exception as e:
        error_msg = f"Error inesperado descargando documento: {str(e)}"
        logger.exception(f"[DOWNLOAD-DOC] {error_msg}")
        return False, None, error_msg

