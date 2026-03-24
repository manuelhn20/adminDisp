"""
Módulo centralizado para autenticación con Microsoft Graph API.
Evita duplicación de credenciales y lógica de autenticación.
"""
import logging
import os
from typing import Optional

import msal
import requests

logger = logging.getLogger("admin_disp.services.graph_auth")

# Credenciales centralizadas
TENANT_ID = os.getenv("MS_TENANT_ID")
CLIENT_ID = os.getenv("MS_CLIENT_ID")
CLIENT_SECRET = os.getenv("MS_CLIENT_SECRET")

# Cache para site_id (evita llamadas repetidas)
_cached_site_id: Optional[str] = None


def get_graph_token() -> Optional[str]:
    """
    Obtiene access token para Microsoft Graph API usando client credentials.
    
    Returns:
        str: Access token o None si hay error
    """
    try:
        if not all([CLIENT_ID, CLIENT_SECRET, TENANT_ID]):
            logger.error('Credenciales de Microsoft Graph no configuradas completamente')
            return None
        
        authority = f'https://login.microsoftonline.com/{TENANT_ID}'
        app = msal.ConfidentialClientApplication(
            client_id=CLIENT_ID,
            authority=authority,
            client_credential=CLIENT_SECRET
        )
        
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        token = result.get('access_token')
        
        if not token:
            error_desc = result.get('error_description') or result.get('error') or 'Unknown error'
            logger.error(f'Error obteniendo token: {error_desc}')
            return None
        
        logger.debug('Token de Graph API obtenido exitosamente')
        return token
        
    except Exception as e:
        logger.exception(f'Error obteniendo token de Microsoft Graph: {e}')
        return None


def get_site_id(hostname: str = "proimamericanos-my.sharepoint.com", 
                site_path: str = "/personal/central_proimahn_com") -> Optional[str]:
    """
    Obtiene el site_id de SharePoint/OneDrive.
    Usa caché para evitar llamadas repetidas.
    
    Args:
        hostname: Hostname del sitio de SharePoint
        site_path: Path del sitio
    
    Returns:
        str: Site ID o None si hay error
    """
    global _cached_site_id
    
    # Retornar caché si existe
    if _cached_site_id:
        return _cached_site_id
    
    try:
        token = get_graph_token()
        if not token:
            logger.error('No se pudo obtener token para resolver site_id')
            return None
        
        url = f'https://graph.microsoft.com/v1.0/sites/{hostname}:{site_path}'
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        logger.debug(f'Obteniendo site_id de: {hostname}:{site_path}')
        
        resp = requests.get(url, headers=headers, timeout=30)
        
        if resp.status_code != 200:
            logger.error(f'Error obteniendo site_id: {resp.status_code} - {resp.text}')
            return None
        
        data = resp.json()
        site_id = data.get('id')
        
        if site_id:
            _cached_site_id = site_id
            logger.info(f'Site ID obtenido y cacheado exitosamente')
            return site_id
        else:
            logger.error('No se encontró site_id en la respuesta')
            return None
        
    except Exception as e:
        logger.exception(f'Error obteniendo site_id: {e}')
        return None


def clear_site_id_cache():
    """Limpia el caché del site_id. Útil para testing o cambios de configuración."""
    global _cached_site_id
    _cached_site_id = None
    logger.debug('Caché de site_id limpiado')
