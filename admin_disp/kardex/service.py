# admin_disp/kardex/service.py
"""
Servicio de sincronización SharePoint → BD para el módulo KARDEX.
Descarga RPT---AT---Reporte-de-Productos.xlsx y RPT---AT---Almacenes.xlsx
desde la carpeta 'Reportes Power Bi' en SharePoint, parsea y persiste.

Reutiliza el patrón de empleados_sync.py (GraphClient / SharePointConfig).
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import msal
import openpyxl
import requests

from .db import upsert_marcas, upsert_productos, upsert_almacenes

logger = logging.getLogger("admin_disp.kardex")
# Session update: 2026-03-24 14:39:20 - Rebuild schema support and extraction compatibility.

# ---------------------------------------------------------------------------
# Configuración SharePoint (mismas credenciales que empleados_sync)
# ---------------------------------------------------------------------------

@dataclass
class KardexSPConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    site_hostname: str
    site_path: str
    drive_name: str
    filename: str

    @staticmethod
    def from_env(filename: str) -> "KardexSPConfig":
        tenant_id = os.getenv("MS_TENANT_ID")
        client_id = os.getenv("MS_CLIENT_ID")
        client_secret = os.getenv("MS_CLIENT_SECRET")
        if not all([tenant_id, client_id, client_secret]):
            raise RuntimeError("Faltan variables de entorno requeridas: MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET")

        site_hostname = os.getenv("SP_SITE_HOSTNAME", "proimamericanos.sharepoint.com")
        site_path = os.getenv("SP_SITE_PATH", "/sites/ERPNext-Reportes")
        drive_name = os.getenv("SP_DRIVE_NAME", "Reportes Power Bi")

        return KardexSPConfig(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            site_hostname=site_hostname,
            site_path=site_path,
            drive_name=drive_name,
            filename=filename,
        )


# ---------------------------------------------------------------------------
# GraphClient (igual que empleados_sync)
# ---------------------------------------------------------------------------

class GraphClient:
    def __init__(self, cfg: KardexSPConfig,
                 session: Optional[requests.Session] = None) -> None:
        self.cfg = cfg
        self.session = session or requests.Session()

    def get_token(self) -> str:
        authority = f"https://login.microsoftonline.com/{self.cfg.tenant_id}"
        app = msal.ConfidentialClientApplication(
            client_id=self.cfg.client_id,
            authority=authority,
            client_credential=self.cfg.client_secret,
        )
        result = app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        token = result.get("access_token")
        if not token:
            raise RuntimeError(
                f"Error obteniendo token: {result.get('error_description') or result}"
            )
        return token

    def _headers(self, token: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def get_site_id(self, token: str) -> str:
        url = (f"https://graph.microsoft.com/v1.0/sites/"
               f"{self.cfg.site_hostname}:{self.cfg.site_path}")
        r = self.session.get(url, headers=self._headers(token), timeout=60)
        r.raise_for_status()
        return r.json()["id"]

    def get_drive_id(self, token: str, site_id: str) -> str:
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
        r = self.session.get(url, headers=self._headers(token), timeout=60)
        r.raise_for_status()
        for drive in r.json().get("value", []):
            if drive.get("name") == self.cfg.drive_name:
                return drive["id"]
        available = [d.get("name", "") for d in r.json().get("value", [])]
        raise RuntimeError(
            f"Drive '{self.cfg.drive_name}' no encontrado. Disponibles: {available}"
        )

    def download_file(self, token: str, drive_id: str) -> bytes:
        url = (f"https://graph.microsoft.com/v1.0/drives/{drive_id}"
               f"/root:/{self.cfg.filename}:/content")
        r = self.session.get(url, headers=self._headers(token), timeout=120)
        r.raise_for_status()
        return r.content


def _download_excel(filename: str) -> bytes:
    cfg = KardexSPConfig.from_env(filename)
    client = GraphClient(cfg)
    token = client.get_token()
    site_id = client.get_site_id(token)
    drive_id = client.get_drive_id(token, site_id)
    return client.download_file(token, drive_id)


def _norm(value: Any, max_len: Optional[int] = None) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:max_len] if max_len else s


# ---------------------------------------------------------------------------
# Parser — Productos (RPT---AT---Reporte-de-Productos.xlsx)
# Columnas: ID | Document Status | Item Name | Brand | Item Group |
#           Default Unit of Measure | Disabled | End of Life |
#           Item Tax Template | Maintain Stock
# Índices (base 0, col A es índice 0):
#   col B (1) = ID del item en ERPNext
#   col C (2) = Document Status  <- ignorar
#   col D (3) = Item Name
#   col E (4) = Brand
#   col F (5) = Item Group (categoria)
#   col G (6) = Default Unit of Measure (um)
#   col H (7) = Disabled
#   col I (8) = End of Life       <- ignorar
#   col J (9) = Item Tax Template <- ignorar
#   col K (10) = Maintain Stock (ms)
# La fila 1 es encabezado, datos desde fila 2.
# ---------------------------------------------------------------------------

def parse_productos(excel_bytes: bytes):
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=True)
    ws = wb.active

    marcas_set: Dict[str, str] = {}   # name -> description
    productos: List[Dict[str, Any]] = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row:
            continue

        # Col B=index 1 es el ID del item
        item_id   = _norm(row[1] if len(row) > 1 else None, 50)
        item_name = _norm(row[3] if len(row) > 3 else None, 200)

        if not item_id or not item_name:
            continue

        brand     = _norm(row[4] if len(row) > 4 else None, 50)
        categoria = _norm(row[5] if len(row) > 5 else None, 100)
        um        = _norm(row[6] if len(row) > 6 else None, 20)
        disabled  = row[7] if len(row) > 7 else 0
        ms_raw    = row[10] if len(row) > 10 else 1

        # ms = 1 si Maintain Stock está activo y no está deshabilitado
        disabled_flag = 1 if disabled in (1, True, "1", "Yes") else 0
        ms_flag = 1 if ms_raw in (1, True, "1", "Yes") else 0
        disponible = 1 if (ms_flag == 1 and disabled_flag == 0) else 0

        # Solo incluir productos disponibles
        if disponible != 1:
            continue

        # Recolectar marcas únicas para upsert separado
        if brand and brand not in marcas_set:
            marcas_set[brand] = brand

        productos.append({
            "id":       item_id,
            "itemName": item_name,
            "brand":    brand,
            "categoria": categoria,
            "um":       um,
            "status":   disponible,
        })

    marcas = [{"name": k, "description": v} for k, v in marcas_set.items()]
    return marcas, productos


# ---------------------------------------------------------------------------
# Parser — Almacenes (RPT---AT---Almacenes.xlsx)
# Estructura real del Excel:
#   row[1] = Identificador (ID almacén)
#   row[2] = Estado del Documento <- ignorar
#   row[3] = Es Almacén de Grupo (flag para filtrar grupos)
#   row[4] = Compañía
#   row[5] = Almacén Padre (usar como descripcion)
#   row[6] = Tipo de almacén (está vacío, no usar)
#   row[9] = Tipo de Almacen (datos reales: "Almacén de Unidades", "Almacén de Cajas", etc)
# ---------------------------------------------------------------------------

def parse_almacenes(excel_bytes: bytes) -> List[Dict[str, Any]]:
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), data_only=True)
    ws = wb.active
    almacenes: List[Dict[str, Any]] = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row:
            continue

        aid     = _norm(row[1] if len(row) > 1 else None, 50)
        if not aid:
            continue

        is_group_raw = row[3] if len(row) > 3 else 0
        # Solo incluir almacenes que NO sean Group Warehouse (Is Group Warehouse = 0)
        if is_group_raw in (1, True, "1", "Yes"):
            continue

        company = _norm(row[4] if len(row) > 4 else None, 100)
        descripcion = _norm(row[5] if len(row) > 5 else None, 150)
        # row[9] contiene el "Tipo de Almacen" real (Almacén de Unidades, Almacén de Cajas, etc)
        # row[6] está vacío en los datos pero tiene el encabezado "Tipo de almacén"
        tipoAlmacen = _norm(row[9] if len(row) > 9 else None, 100)

        almacenes.append({
            "idName":      aid,
            "status":      1,
            "company":     company,
            "description": descripcion or aid,
            "type": tipoAlmacen or "General",
        })

    return almacenes


# ---------------------------------------------------------------------------
# Funciones públicas de sincronización
# ---------------------------------------------------------------------------

def sync_productos() -> Dict[str, Any]:
    """
    Descarga el Excel de productos desde SharePoint, parsea y persiste
    en las tablas `marca` y `producto`.
    """
    logger.info("[KARDEX] Iniciando sync productos desde SharePoint")
    filename = os.getenv(
        "KARDEX_SP_PRODUCTOS_FILE",
        "RPT---AT---Reporte-de-Productos.xlsx"
    )
    try:
        excel_bytes = _download_excel(filename)
        marcas, productos = parse_productos(excel_bytes)

        res_marcas = upsert_marcas(marcas)
        res_productos = upsert_productos(productos)

        logger.info(
            "[KARDEX] Sync productos OK — marcas: %s | productos: %s",
            res_marcas, res_productos
        )
        return {
            "success": True,
            "marcas": res_marcas,
            "productos": res_productos,
            "total_marcas": len(marcas),
            "total_productos": len(productos),
        }
    except Exception as e:
        logger.error("[KARDEX] Error en sync productos: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


def sync_almacenes() -> Dict[str, Any]:
    """
    Descarga el Excel de almacenes desde SharePoint, parsea y persiste
    en la tabla `almacen`.
    """
    logger.info("[KARDEX] Iniciando sync almacenes desde SharePoint")
    filename = os.getenv(
        "KARDEX_SP_ALMACENES_FILE",
        "RPT---AT---Almacenes.xlsx"
    )
    try:
        excel_bytes = _download_excel(filename)
        almacenes = parse_almacenes(excel_bytes)
        result = upsert_almacenes(almacenes)

        logger.info("[KARDEX] Sync almacenes OK — %s", result)
        return {
            "success": True,
            "almacenes": result,
            "total": len(almacenes),
        }
    except Exception as e:
        logger.error("[KARDEX] Error en sync almacenes: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
