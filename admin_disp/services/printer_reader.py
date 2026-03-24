"""printer_reader.py — Gestión completa de impresoras Canon imageCLASS.

Estructura:
  1. PrinterConfig        — Configuración centralizada
  2. Helpers compartidos  — Auth y apertura de páginas
  3. InkLevelScanner      — Lee niveles de tinta (todas las impresoras, concurrente)
  4. JobHistoryScanner    — Lee historial de una impresora bajo demanda
                            Guarda registros incrementales en JSONL por impresora (30 días)
  5. load_printer_config  — Carga ip_dict desde printer_config.json
  6. Aliases legacy       — read_printers / save_printer_data para compatibilidad
  7. Flask Blueprint      — Rutas HTTP para ambos escáneres
  8. main()               — Punto de entrada CLI (tinta)

Uso desde app.py:
    from printer_reader import bp_printer
    app.register_blueprint(bp_printer)
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from playwright.async_api import async_playwright, Browser, TimeoutError as PlaywrightTimeout

try:
    from flask import Blueprint, jsonify, send_file, abort, request
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

logger = logging.getLogger("admin_disp.services.printer_reader")


# =============================================================================
# 1. CONFIGURACIÓN CENTRALIZADA
# =============================================================================
class PrinterConfig:
    """Parámetros compartidos por ambos escáneres."""

    # Timeouts (ms)
    PAGE_LOAD_TIMEOUT    = 8_000
    AUTH_WAIT_TIMEOUT    = 1_000
    CONTENT_WAIT_TIMEOUT = 200

    # Credenciales
    DEFAULT_USER_ID = "5050"
    DEFAULT_PIN     = "5050"

    # Reintentos / concurrencia
    MAX_RETRIES    = 2
    RETRY_DELAY    = 1.0
    MAX_CONCURRENT = 5

    @staticmethod
    def exports_dir() -> Path:
        return Path(__file__).parent.parent.parent / "exports"

    @staticmethod
    def history_dir() -> Path:
        return PrinterConfig.exports_dir() / "printer_history"


# =============================================================================
# 2. HELPERS COMPARTIDOS
# =============================================================================
async def _authenticate(page, cfg: PrinterConfig) -> None:
    """Login en la UI web de la impresora (flujo Canon imageCLASS)."""
    try:
        for radio in await page.locator('input[type="radio"]').all():
            label = await radio.evaluate('el => el.parentElement?.textContent || ""')
            if "administrador" in label.lower():
                await radio.click()
                break

        id_input = page.locator(
            'label:has-text("ID"), label:has-text("Identificación")'
        ).locator('..').locator('input[type="text"]').first
        if not await id_input.is_visible(timeout=1_000):
            id_input = page.locator('input[type="text"]').first

        pin_input = page.locator(
            'label:has-text("PIN"), label:has-text("Contraseña")'
        ).locator('..').locator('input[type="password"]').first
        if not await pin_input.is_visible(timeout=1_000):
            pin_input = page.locator('input[type="password"]').first

        if await id_input.is_visible(timeout=500):
            await id_input.fill(cfg.DEFAULT_USER_ID)
        if await pin_input.is_visible(timeout=500):
            await pin_input.fill(cfg.DEFAULT_PIN)

        btn = page.locator('#submitButton')
        if await btn.is_visible(timeout=500):
            await btn.click()
            await page.wait_for_timeout(cfg.AUTH_WAIT_TIMEOUT)
            await page.wait_for_load_state("load")

    except Exception as exc:
        logger.debug(f"Auth: no aplica o falló ({exc})")


async def _open_page(browser: Browser, url: str, cfg: PrinterConfig):
    """Abre una URL, hace login y retorna el objeto page listo para leer."""
    page = await browser.new_page()
    page.set_default_timeout(cfg.PAGE_LOAD_TIMEOUT)
    try:
        await page.goto(url, wait_until="load", timeout=cfg.PAGE_LOAD_TIMEOUT)
    except PlaywrightTimeout:
        await page.close()
        raise ConnectionError(f"Timeout al conectar a {url}")
    except Exception as exc:
        await page.close()
        raise ConnectionError(f"Error de conexión: {exc}")
    await _authenticate(page, cfg)
    await page.wait_for_timeout(cfg.CONTENT_WAIT_TIMEOUT)
    return page


# =============================================================================
# 3. NIVELES DE TINTA — todas las impresoras, concurrente
# =============================================================================
class InkLevelScanner:
    """Lee porcentajes de tinta de todas las impresoras en paralelo."""

    def __init__(self, cfg: PrinterConfig | None = None):
        self.cfg = cfg or PrinterConfig()

    # --- Extracción -----------------------------------------------------------
    @staticmethod
    def _extract_ink(html: str) -> Dict[str, int]:
        levels: Dict[str, int] = {}
        patterns = {
            "Cyan":     ["cyan", "cian"],
            "Magenta":  ["magenta"],
            "Amarillo": ["amarillo", "yellow"],
            "Negro":    ["negro", "black", "blac"],
        }
        for color, keywords in patterns.items():
            for kw in keywords:
                m = re.search(rf'{kw}\s*[:\-=]?\s*(\d+)\s*%', html, re.I)
                if not m:
                    m = re.search(
                        rf'<th[^>]*>\s*{kw}\s*</th[^>]*>.*?<td[^>]*>.*?(\d+)\s*%.*?</td>',
                        html, re.I | re.S,
                    )
                if m:
                    levels[color] = int(m.group(1))
                    break
        return levels

    # --- Lectura individual con reintentos ------------------------------------
    async def _read_one(
        self, ip: str, description: str, browser: Browser, attempt: int = 1
    ) -> Dict[str, Any]:
        t0 = time.time()
        try:
            page = await _open_page(browser, f"http://{ip}", self.cfg)
            html = await page.content()
            await page.close()
            levels = self._extract_ink(html)
            elapsed = round(time.time() - t0, 2)

            if not levels:
                raise ValueError("No se encontraron niveles de tinta en el HTML")

            logger.debug(f"[{ip}] Tinta: {levels}")
            return {
                "ip": ip, "description": description or ip,
                "status": "Exito", "tinta_levels": levels,
                "tiempo_segundos": elapsed, "intentos": attempt,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as exc:
            elapsed = round(time.time() - t0, 2)
            if attempt < self.cfg.MAX_RETRIES:
                logger.warning(f"[{ip}] Intento {attempt} falló: {exc}. Reintentando…")
                await asyncio.sleep(self.cfg.RETRY_DELAY)
                return await self._read_one(ip, description, browser, attempt + 1)

            logger.error(f"[{ip}] Falló tras {attempt} intentos: {exc}")
            return {
                "ip": ip, "description": description or ip,
                "status": "Fracaso", "tinta_levels": {},
                "error": str(exc), "tiempo_segundos": elapsed,
                "intentos": attempt, "timestamp": datetime.now().isoformat(),
            }

    # --- API pública ----------------------------------------------------------
    def scan_all(self, ip_dict: Dict[str, str]) -> List[Dict[str, Any]]:
        """Escanea todas las impresoras en paralelo y retorna lista de resultados."""
        async def _run():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                sem = asyncio.Semaphore(self.cfg.MAX_CONCURRENT)

                async def bounded(ip, desc):
                    async with sem:
                        return await self._read_one(ip, desc, browser)

                try:
                    return list(await asyncio.gather(
                        *[bounded(ip, desc) for ip, desc in ip_dict.items()]
                    ))
                finally:
                    await browser.close()

        results = asyncio.run(_run())

        for r in results:
            ip, desc = r.get("ip"), r.get("description")
            status = r.get("status", "Fracaso")
            t = r.get("tiempo_segundos", 0)
            suffix = f" (intento {r['intentos']})" if r.get("intentos", 1) > 1 else ""
            logger.info(f"{ip} ({desc}) -> {status} [{t}s]{suffix}")

        return results

    def save(self, results: List[Dict[str, Any]], output_file: Path | None = None):
        """Guarda los resultados de tinta en JSON."""
        path = output_file or (self.cfg.exports_dir() / "printer_data.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"printers": results, "last_updated": datetime.now().isoformat()},
                f, indent=2, ensure_ascii=False,
            )
        logger.info(f"Datos de tinta guardados en: {path}")


# =============================================================================
# 4. HISTORIAL DE TRABAJOS — una impresora bajo demanda
# =============================================================================
class JobHistoryScanner:
    """
    Descarga el historial de trabajos de impresión y copia de UNA impresora
    y lo persiste de forma incremental en archivos JSONL.

    Archivos generados:
        exports/printer_history/<ip_slug>_print.jsonl
        exports/printer_history/<ip_slug>_copy.jsonl

    La deduplicación usa _key="Nºtrabajo|HoraInicio" en cada línea JSON,
    por lo que solo se insertan registros nuevos en cada llamada.
    Mantiene registros hasta 30 días atrás.
    """

    PRINT_URL = "/jhis_plist.html"
    COPY_URL  = "/jhis_clist.html"

    def __init__(self, cfg: PrinterConfig | None = None):
        self.cfg = cfg or PrinterConfig()

    # --- Parseo de tablas HTML -----------------------------------------------
    @staticmethod
    def _rows_from_html(html: str) -> List[List[str]]:
        rows = []
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S | re.I):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.S | re.I)
            if cells:
                rows.append([re.sub(r'<[^>]+>', '', c).strip() for c in cells])
        return rows

    @staticmethod
    def _parse_print_rows(rows: List[List[str]]) -> List[Dict[str, str]]:
        """
        Índices jhis_plist:
        0:Nº  1:Resultado  2:Hora inicio  3:Hora fin  4:Tipo
        5:Nombre archivo   6:Nombre usuario
        7:Pág orig  8:Pág impresas  9:Hojas x copias  10:Cód error
        """
        records = []
        for row in rows:
            if len(row) < 10:
                continue
            records.append({
                "hora_inicio":    row[2],
                "nombre_archivo": row[5],
                "nombre_usuario": row[6],
                "hojas_x_copias": row[9],
                "_key": f"{row[0]}|{row[2]}",
            })
        return records

    @staticmethod
    def _parse_copy_rows(rows: List[List[str]]) -> List[Dict[str, str]]:
        """
        Índices jhis_clist:
        0:Nº  1:Resultado  2:Hora inicio  3:Hora fin  4:Tipo
        5:Pág orig  6:Pág impresas  7:Hojas x copias  8:Cód error
        """
        records = []
        for row in rows:
            if len(row) < 8:
                continue
            records.append({
                "hora_inicio":    row[2],
                "hojas_x_copias": row[7],
                "_key": f"{row[0]}|{row[2]}",
            })
        return records

    # --- JSONL incremental (30 días) -----------------------------------------
    @staticmethod
    def _load_jsonl_records(jsonl_path: Path) -> Dict[str, Dict[str, Any]]:
        """Lee archivo JSONL y retorna un dict keyed by _key."""
        existing = {}
        if not jsonl_path.exists():
            return existing
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        key = record.get('_key')
                        if key:
                            existing[key] = record
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON line in {jsonl_path}: {line}")
                        continue
        except Exception as e:
            logger.error(f"Error loading JSONL {jsonl_path}: {e}")
        return existing

    def migrate_html_to_jsonl(self, ip_slug: str) -> Dict[str, Any]:
        """
        Migra historial de archivos HTML hacia JSONL.
        Retorna dict con status y cantidad de registros migrados.
        """
        hist_dir = self.cfg.history_dir()
        print_html = hist_dir / f"{ip_slug}_print.html"
        copy_html = hist_dir / f"{ip_slug}_copy.html"
        print_jsonl = hist_dir / f"{ip_slug}_print.jsonl"
        copy_jsonl = hist_dir / f"{ip_slug}_copy.jsonl"

        result = {
            "ip_slug": ip_slug,
            "print_migrated": 0,
            "copy_migrated": 0,
            "errors": []
        }

        # Migrar print.html → print.jsonl
        if print_html.exists() and not print_jsonl.exists():
            try:
                html_content = print_html.read_text(encoding='utf-8')
                # Extraer filas de la tabla
                for tr in re.findall(r'<tr[^>]*data-key="([^\"]+)"[^>]*>(.*?)</tr>', html_content, re.S | re.I):
                    key = tr[0]
                    inner = tr[1]
                    cols = re.findall(r'<td[^>]*>(.*?)</td>', inner, re.S | re.I)
                    cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols]
                    if len(cols) >= 4:
                        record = {
                            '_key': key,
                            'hora_inicio': cols[0],
                            'nombre_archivo': cols[1],
                            'nombre_usuario': cols[2],
                            'hojas_x_copias': cols[3],
                        }
                        # Agregar al JSONL
                        with open(print_jsonl, 'a', encoding='utf-8') as f:
                            f.write(json.dumps(record, ensure_ascii=False) + '\n')
                        result["print_migrated"] += 1
                logger.info(f"[{ip_slug}] Print HTML migrado: {result['print_migrated']} registros")
            except Exception as e:
                msg = f"Error migrando {ip_slug}_print.html: {e}"
                logger.error(msg)
                result["errors"].append(msg)

        # Migrar copy.html → copy.jsonl
        if copy_html.exists() and not copy_jsonl.exists():
            try:
                html_content = copy_html.read_text(encoding='utf-8')
                # Extraer filas de la tabla
                for tr in re.findall(r'<tr[^>]*data-key="([^\"]+)"[^>]*>(.*?)</tr>', html_content, re.S | re.I):
                    key = tr[0]
                    inner = tr[1]
                    cols = re.findall(r'<td[^>]*>(.*?)</td>', inner, re.S | re.I)
                    cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols]
                    if len(cols) >= 2:
                        record = {
                            '_key': key,
                            'hora_inicio': cols[0],
                            'hojas_x_copias': cols[1],
                        }
                        # Agregar al JSONL
                        with open(copy_jsonl, 'a', encoding='utf-8') as f:
                            f.write(json.dumps(record, ensure_ascii=False) + '\n')
                        result["copy_migrated"] += 1
                logger.info(f"[{ip_slug}] Copy HTML migrado: {result['copy_migrated']} registros")
            except Exception as e:
                msg = f"Error migrando {ip_slug}_copy.html: {e}"
                logger.error(msg)
                result["errors"].append(msg)

    @staticmethod
    def _parse_hora_to_dt(hora_str: str):
        """Intentar convertir cadenas de hora a datetime. Retorna None si falla."""
        if not hora_str or not isinstance(hora_str, str):
            return None
        hora = hora_str.strip()
        # Normalizar separadores
        hora = re.sub(r"\s+", " ", hora)

        patterns = [
            "%d/%m/%Y %I:%M:%S %p",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%y %I:%M:%S %p",
            "%d/%m/%y %H:%M:%S",
            "%d/%m %Y %I:%M:%S %p",
            "%d/%m %Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ]
        for fmt in patterns:
            try:
                return datetime.strptime(hora, fmt)
            except Exception:
                pass

        # Try to extract with regex: day/month year time AM/PM
        m = re.search(r"(\d{1,2})[\-/](\d{1,2})[\-/](\d{2,4})\s+(\d{1,2}:\d{2}:\d{2})\s*(AM|PM)?", hora, re.I)
        if m:
            d, mo, y, t, ampm = m.groups()
            if len(y) == 2:
                y = '20' + y
            timestr = f"{d}/{mo}/{y} {t} {ampm or ''}".strip()
            for fmt in ["%d/%m/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S"]:
                try:
                    return datetime.strptime(timestr, fmt)
                except Exception:
                    pass

        return None

    def _append_rows(
        self,
        path: Path,
        ip: str,
        description: str,
        records: List[Dict[str, str]],
        kind: str,  # "print" | "copy"
    ) -> int:
        """
        Inserta solo los registros nuevos en el JSONL incremental.
        Mantiene registros hasta 30 días atrás.
        Retorna cantidad de registros añadidos.
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        # Cargar registros existentes
        existing_rows = self._load_jsonl_records(path)

        # Mergar registros nuevos (sin duplicados)
        for r in records:
            key = r.get('_key')
            if key and key not in existing_rows:
                existing_rows[key] = r

        # Filtrar por fecha: mantener solo registros de los últimos 30 días
        from datetime import timedelta
        now = datetime.now()
        earliest_date = (now.date() - timedelta(days=30))

        def keep_record(rec):
            dt = self._parse_hora_to_dt(rec.get('hora_inicio'))
            if not dt:
                # Si no se puede parsear la hora, mantener conservadoramente
                return True
            return dt.date() >= earliest_date

        filtered = {k: v for k, v in existing_rows.items() if keep_record(v)}

        # Ordenar por hora_inicio descendente (más reciente primero)
        def sort_key(rec):
            dt = self._parse_hora_to_dt(rec.get('hora_inicio')) if isinstance(rec, dict) else self._parse_hora_to_dt(rec[1].get('hora_inicio'))
            return dt or datetime.min

        sorted_recs = sorted(filtered.items(), key=lambda x: sort_key(x[1]), reverse=True)

        # Escribir JSONL
        try:
            with open(path, 'w', encoding='utf-8') as f:
                for key, rec in sorted_recs:
                    f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            logger.info(f"[{ip}] {kind} JSONL: {len(sorted_recs)} registros totales")
            return len(sorted_recs)
        except Exception as e:
            logger.error(f"[{ip}] Error escribiendo JSONL {path}: {e}")
            raise

    # --- Fetch desde la impresora ---------------------------------------------
    async def _fetch(self, ip: str) -> Tuple[List[Dict], List[Dict]]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # Un solo context mantiene cookies/sesión entre navegaciones
            context = await browser.new_context()
            try:
                base = f"http://{ip}"

                # Paso 1: login en la página principal
                page = await context.new_page()
                page.set_default_timeout(self.cfg.PAGE_LOAD_TIMEOUT)
                await page.goto(base, wait_until="load", timeout=self.cfg.PAGE_LOAD_TIMEOUT)
                await _authenticate(page, self.cfg)
                await page.wait_for_timeout(self.cfg.CONTENT_WAIT_TIMEOUT)
                await page.close()

                # Paso 2: historial de impresiones (sesión activa)
                page_print = await context.new_page()
                page_print.set_default_timeout(self.cfg.PAGE_LOAD_TIMEOUT)
                await page_print.goto(base + self.PRINT_URL, wait_until="load",
                                      timeout=self.cfg.PAGE_LOAD_TIMEOUT)
                await page_print.wait_for_timeout(self.cfg.CONTENT_WAIT_TIMEOUT)
                print_html = await page_print.content()
                await page_print.close()

                # Paso 3: historial de copias (misma sesión)
                page_copy = await context.new_page()
                page_copy.set_default_timeout(self.cfg.PAGE_LOAD_TIMEOUT)
                await page_copy.goto(base + self.COPY_URL, wait_until="load",
                                     timeout=self.cfg.PAGE_LOAD_TIMEOUT)
                await page_copy.wait_for_timeout(self.cfg.CONTENT_WAIT_TIMEOUT)
                copy_html = await page_copy.content()
                await page_copy.close()

            finally:
                await context.close()
                await browser.close()

        return (
            self._parse_print_rows(self._rows_from_html(print_html)),
            self._parse_copy_rows(self._rows_from_html(copy_html)),
        )

    # --- API pública ----------------------------------------------------------
    def scan(self, ip: str, description: str = "") -> Dict[str, Any]:
        """
        Escanea historial de UNA impresora y actualiza sus archivos JSONL.

        Retorna dict con: ip, description, print_added, copy_added,
                          print_jsonl, copy_jsonl, status, error (si Fracaso).
        """
        slug       = ip.replace(".", "_")
        hist_dir   = self.cfg.history_dir()
        hist_dir.mkdir(parents=True, exist_ok=True)
        print_path = hist_dir / f"{slug}_print.jsonl"
        copy_path  = hist_dir / f"{slug}_copy.jsonl"
        desc       = description or ip

        try:
            print_records, copy_records = asyncio.run(self._fetch(ip))
            p_added = self._append_rows(print_path, ip, desc, print_records, "print")
            c_added = self._append_rows(copy_path,  ip, desc, copy_records,  "copy")

            logger.info(f"[{ip}] Historial: +{p_added} impresiones, +{c_added} copias")
            return {
                "ip": ip, "description": desc,
                "print_added": p_added, "copy_added": c_added,
                "print_jsonl": str(print_path), "copy_jsonl": str(copy_path),
                "status": "Exito",
            }

        except Exception as exc:
            logger.error(f"[{ip}] Error obteniendo historial: {exc}")
            return {
                "ip": ip, "description": desc,
                "print_added": 0, "copy_added": 0,
                "print_jsonl": str(print_path), "copy_jsonl": str(copy_path),
                "status": "Fracaso", "error": str(exc),
            }


# =============================================================================
# 5. HELPERS
# =============================================================================
def load_printer_config() -> Dict[str, str]:
    """Carga {ip: descripcion} desde printer_config.json.
    Soporta tanto formato array como dict.
    """
    cfg_file = PrinterConfig.exports_dir() / "printer_config.json"
    if not cfg_file.exists():
        return {}
    try:
        with open(cfg_file, "r", encoding="utf-8") as f:
            cfg = json.load(f) or {}
        result: Dict[str, str] = {}
        printers = cfg.get("printers", {})
        
        # Soportar formato array
        if isinstance(printers, list):
            for item in printers:
                if isinstance(item, dict):
                    ip = item.get("ip")
                    if ip:
                        result[ip] = item.get("description", ip)
        # Soportar formato dict
        elif isinstance(printers, dict):
            for ip, info in printers.items():
                if isinstance(info, dict):
                    if info.get("estado") == 1:
                        result[ip] = info.get("descripcion", ip)
                elif isinstance(info, str):
                    result[ip] = info
        
        return result
    except Exception as exc:
        logger.error(f"Error cargando printer_config.json: {exc}")
        return {}


# Aliases de compatibilidad con código anterior
def read_printers(ip_dict: Dict[str, str]) -> List[Dict[str, Any]]:
    return InkLevelScanner().scan_all(ip_dict)

def save_printer_data(results: List[Dict[str, Any]], output_file: Path | None = None):
    InkLevelScanner().save(results, output_file)


# =============================================================================
# 6. FLASK BLUEPRINT
# =============================================================================
if FLASK_AVAILABLE:
    printerScanner = Blueprint("printer_scanner", __name__, url_prefix="/dispositivos")

    # --- Tinta ----------------------------------------------------------------
    @printerScanner.route("/tinta/scan", methods=["POST"])
    def route_ink_scan():
        """Escanea niveles de tinta de todas las impresoras activas."""
        ip_dict = load_printer_config()
        if not ip_dict:
            return jsonify({"error": "No hay impresoras configuradas"}), 400
        scanner = InkLevelScanner()
        results = scanner.scan_all(ip_dict)
        scanner.save(results)
        return jsonify(results)

    # --- Historial ------------------------------------------------------------
    @printerScanner.route("/historial/scan/<ip>", methods=["POST"])
    def route_history_scan(ip):
        """Escanea y actualiza el historial de UNA impresora por IP."""
        ip_dict = load_printer_config()
        desc    = ip_dict.get(ip, ip)
        result  = JobHistoryScanner().scan(ip=ip, description=desc)
        return jsonify(result)

    @printerScanner.route("/historial/<ip_slug>/print")
    def route_history_print(ip_slug):
        """
        Devuelve datos de historial de impresión en formato JSON paginado.
        Params: page (default 1), limit (default 50)
        """
        try:
            page = max(1, int(request.args.get('page', 1)))
            limit = min(500, max(1, int(request.args.get('limit', 50))))
        except (ValueError, TypeError):
            page, limit = 1, 50

        path = PrinterConfig.history_dir() / f"{ip_slug}_print.jsonl"
        if not path.exists():
            return jsonify({
                'success': False,
                'message': 'Sin historial. Ejecute el escaneo primero.',
                'records': [],
                'total': 0,
                'page': page,
                'limit': limit,
                'pages': 0
            }), 404

        # Cargar JSONL
        scanner = JobHistoryScanner()
        records = scanner._load_jsonl_records(path)
        all_records = list(records.values())

        # Ordenar por hora_inicio descendente (más reciente primero)
        all_records.sort(
            key=lambda r: scanner._parse_hora_to_dt(r.get('hora_inicio')) or datetime.min,
            reverse=True
        )

        # Paginar
        total = len(all_records)
        pages = (total + limit - 1) // limit if total > 0 else 1
        page = min(page, pages)
        offset = (page - 1) * limit
        paged_records = all_records[offset:offset + limit]

        return jsonify({
            'success': True,
            'records': paged_records,
            'total': total,
            'page': page,
            'limit': limit,
            'pages': pages
        }), 200

    @printerScanner.route("/historial/<ip_slug>/copy")
    def route_history_copy(ip_slug):
        """
        Devuelve datos de historial de copias en formato JSON paginado.
        Params: page (default 1), limit (default 50)
        """
        try:
            page = max(1, int(request.args.get('page', 1)))
            limit = min(500, max(1, int(request.args.get('limit', 50))))
        except (ValueError, TypeError):
            page, limit = 1, 50

        path = PrinterConfig.history_dir() / f"{ip_slug}_copy.jsonl"
        if not path.exists():
            return jsonify({
                'success': False,
                'message': 'Sin historial. Ejecute el escaneo primero.',
                'records': [],
                'total': 0,
                'page': page,
                'limit': limit,
                'pages': 0
            }), 404

        # Cargar JSONL
        scanner = JobHistoryScanner()
        records = scanner._load_jsonl_records(path)
        all_records = list(records.values())

        # Ordenar por hora_inicio descendente (más reciente primero)
        all_records.sort(
            key=lambda r: scanner._parse_hora_to_dt(r.get('hora_inicio')) or datetime.min,
            reverse=True
        )

        # Paginar
        total = len(all_records)
        pages = (total + limit - 1) // limit if total > 0 else 1
        page = min(page, pages)
        offset = (page - 1) * limit
        paged_records = all_records[offset:offset + limit]

        return jsonify({
            'success': True,
            'records': paged_records,
            'total': total,
            'page': page,
            'limit': limit,
            'pages': pages
        }), 200

    # --- Sincronización masiva y migración ---------------------------------
    @printerScanner.route("/historial/scan-all", methods=["POST"])
    def route_scan_all_printers():
        """
        Sincroniza el historial de TODAS las impresoras configuradas.
        Devuelve lista con resultados de cada impresora.
        """
        ip_dict = load_printer_config()
        if not ip_dict:
            return jsonify({
                'success': False,
                'message': 'No hay impresoras configuradas',
                'results': []
            }), 400

        scanner = JobHistoryScanner()
        results = []
        
        for ip, desc in ip_dict.items():
            try:
                result = scanner.scan(ip=ip, description=desc)
                results.append({
                    'ip': ip,
                    'description': desc,
                    'status': result.get('status'),
                    'print_added': result.get('print_added', 0),
                    'copy_added': result.get('copy_added', 0),
                    'error': result.get('error')
                })
                logger.info(f"[Sync-All] {ip} -> {result.get('status')}")
            except Exception as e:
                logger.error(f"[Sync-All] Error con {ip}: {e}")
                results.append({
                    'ip': ip,
                    'description': desc,
                    'status': 'Fracaso',
                    'error': str(e)
                })

        # Resumen
        exitosas = sum(1 for r in results if r.get('status') == 'Exito')
        fallidas = len(results) - exitosas

        return jsonify({
            'success': True,
            'message': f'Sincronización completada: {exitosas} exitosas, {fallidas} fallidas',
            'results': results,
            'total': len(results),
            'exitosas': exitosas,
            'fallidas': fallidas
        }), 200


# =============================================================================
# 7. MAIN — CLI para escaneo de tinta
# =============================================================================
def main(ip_dict: Dict[str, str] | None = None):
    try:
        try:
            from ..devices.service import ensure_admin_exists
        except ImportError:
            from ..cxc.service import ensure_admin_exists
        ensure_admin_exists()
    except Exception:
        pass
    if ip_dict is None:
        ip_dict = load_printer_config()

    if not ip_dict:
        ip_dict = {
            "192.168.0.138": "Facturacion ElmigoTGU",
            "192.168.0.187": "PROIMA 1er piso TGU",
            "192.168.0.155": "Elmigo TGU",
            "192.168.0.102": "Facturacion PROIMA TGU",
            "192.168.0.29":  "Contabilidad TGU",
            "192.168.0.10":  "Canon color",
            "192.168.2.202": "Elmigo SPS",
        }

    cfg = PrinterConfig()
    logger.info(f"{'='*70}")
    logger.info(f"Iniciando revisión de {len(ip_dict)} impresoras")
    logger.info(f"Timeout={cfg.PAGE_LOAD_TIMEOUT}ms | Reintentos={cfg.MAX_RETRIES} | "
                f"Concurrencia={cfg.MAX_CONCURRENT}")
    logger.info(f"{'='*70}")

    t0      = time.time()
    scanner = InkLevelScanner()
    results = scanner.scan_all(ip_dict)
    scanner.save(results)

    total_t  = round(time.time() - t0, 2)
    exitosas = sum(1 for r in results if r.get("status") == "Exito")
    fallidas = len(results) - exitosas
    logger.info(f"RESUMEN: {exitosas} exitosas / {fallidas} fallidas — {total_t}s total")
    return results


if __name__ == "__main__":
    main()
