"""
DocumentGenerator – Motor unificado para generar documentos de entrega (DOCX/PDF).

Exposicion de APIs:
  TIER 1 (Reemplazo):     replace_placeholders, apply_extra_replacement_passes
  TIER 2 (Generacion):    generate_from_template_path
  TIER 3 (Orquestacion):  generate_for_assignment
  TIER 4 (Utilitarios):   convert_docx_to_pdf, select_template
"""

import logging
import os
import shutil
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from docx import Document

try:
    from .docx_common import (
        PlaceholderOptions,
        format_costo_con_moneda,
        format_numero_linea,
        replace_placeholders as _replace_placeholders,
    )
except ImportError:
    from docx_common import (
        PlaceholderOptions,
        format_costo_con_moneda,
        format_numero_linea,
        replace_placeholders as _replace_placeholders,
    )

logger = logging.getLogger("admin_disp.services.docgen")

try:
    from docx2pdf import convert as _docx2pdf_convert
    HAS_DOCX2PDF = True
except ImportError:
    logger.info("docx2pdf no esta instalado. Documentos se generaran en formato DOCX.")
    _docx2pdf_convert = None
    HAS_DOCX2PDF = False
except Exception as e:
    logger.warning("Error al importar docx2pdf: %s", e)
    _docx2pdf_convert = None
    HAS_DOCX2PDF = False


# ---------------------------------------------------------------------------
# Helpers de compatibilidad (evitan romper imports externos)
# ---------------------------------------------------------------------------

def _format_numero_linea(numero_linea_raw: str) -> str:
    return format_numero_linea(numero_linea_raw)


def _format_costo_con_moneda(costo_plan: float, moneda_plan: str) -> str:
    return format_costo_con_moneda(costo_plan, moneda_plan)


# ---------------------------------------------------------------------------
# DocumentGenerator
# ---------------------------------------------------------------------------

class DocumentGenerator:
    """Motor unificado para generar documentos Word/PDF de entrega de dispositivos."""

    def __init__(self, *, base_dir: str | os.PathLike | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parent

    # ------------------------------------------------------------------ TIER 1

    def replace_placeholders(self, doc, replacements: dict) -> None:
        """Reemplaza placeholders [CLAVE] en todo el documento.

        Delega a docx_common.replace_placeholders.
        Keys en replacements deben ser MAYUSCULAS (el motor ya normaliza,
        pero es buena practica para claridad).
        """
        logo_path = self.base_dir.parent / "static" / "img" / "LogoProima.png"
        opts = PlaceholderOptions(logo_path=logo_path if logo_path.exists() else None)
        _replace_placeholders(doc, replacements, options=opts)

    # ------------------------------------------------------------------ TIER 2

    def generate_from_template_path(self, template_path, fields: dict, save_as_pdf: bool = True) -> BytesIO:
        """Genera un documento (DOCX/PDF) a partir de una plantilla y campos.

        Args:
            template_path: Ruta a la plantilla .docx
            fields:        Dict {CLAVE: valor} para reemplazar placeholders [CLAVE]
            save_as_pdf:   Si True, intenta convertir a PDF con docx2pdf

        Returns:
            BytesIO con el contenido del PDF o DOCX generado.
        """
        template_path = str(template_path)
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template no encontrado: {template_path}")

        tmp_src = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        tmp_src.close()
        tmp_out = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        tmp_out.close()

        try:
            shutil.copy2(template_path, tmp_src.name)
            doc = Document(tmp_src.name)
            self.replace_placeholders(doc, fields)
            doc.save(tmp_out.name)

            if save_as_pdf:
                try:
                    pdf_path = self.convert_docx_to_pdf(tmp_out.name)
                    with open(pdf_path, "rb") as f:
                        buffer = BytesIO(f.read())
                    self._safe_unlink(pdf_path)
                except RuntimeError:
                    # docx2pdf no disponible: devolver DOCX como fallback
                    with open(tmp_out.name, "rb") as f:
                        buffer = BytesIO(f.read())
            else:
                with open(tmp_out.name, "rb") as f:
                    buffer = BytesIO(f.read())

        finally:
            self._safe_unlink(tmp_src.name)
            self._safe_unlink(tmp_out.name)

        buffer.seek(0)
        return buffer

    # ------------------------------------------------------------------ TIER 3

    def generate_for_assignment(self, asignacion_id, empleado_data: dict | None = None) -> BytesIO:
        """Genera un documento para una asignacion consultando la BD.

        Args:
            asignacion_id: ID de la asignacion
            empleado_data: Dict con 'nombre_completo' y 'numero_identidad' (opcional)

        Returns:
            BytesIO con el documento generado.
        """
        from ..devices.service import DeviceService
        from .docexp import TEMPLATE_PRO_TI_003, select_template

        svc = DeviceService()

        asignacion = svc.get_asignacion(asignacion_id)
        if not asignacion:
            raise FileNotFoundError(f"Asignacion {asignacion_id} no encontrada")

        device_id = asignacion.get("fk_id_dispositivo")
        if not device_id:
            raise RuntimeError("Dispositivo no especificado en asignacion")

        dispositivo = svc.get_device(device_id)
        if not dispositivo:
            raise FileNotFoundError(f"Dispositivo {device_id} no encontrado")

        # Formatear numero de linea y costo
        numero_linea_raw = (asignacion.get("numero_linea") or "").strip()
        numero_linea = format_numero_linea(numero_linea_raw) if numero_linea_raw else "N/A"
        costo_plan = format_costo_con_moneda(
            asignacion.get("costo_plan") or 0,
            asignacion.get("moneda_plan") or "L",
        )

        # Obtener empleado si no fue pasado como parametro
        if not empleado_data:
            empleado_id = asignacion.get("fk_id_empleado")
            if empleado_id:
                try:
                    empleado_data = svc.get_empleado(empleado_id)
                except Exception as e:
                    logger.warning("No se pudo obtener datos de empleado %s: %s", empleado_id, e)

        # Extraer datos del empleado con fallback a N/A
        nombre_empleado = identidad_empleado = ""
        if isinstance(empleado_data, dict):
            nombre_empleado = (empleado_data.get("nombre_completo") or "").strip()
            identidad_empleado = (empleado_data.get("numero_identidad") or "").strip()

        if not nombre_empleado:
            logger.warning("Empleado sin nombre_completo en asignacion %s", asignacion_id)
            nombre_empleado = "N/A"
        if not identidad_empleado:
            logger.warning("Empleado sin numero_identidad en asignacion %s", asignacion_id)
            identidad_empleado = "N/A"

        # Calcular meses usando fecha_inicio y fecha_fin del plan
        meses_str = self._calcular_meses(asignacion)
        logger.info(f"Asignación {asignacion_id}: meses calculados = '{meses_str}' "
                   f"(plan_inicio={asignacion.get('plan_fecha_inicio')}, "
                   f"plan_fin={asignacion.get('plan_fecha_fin')})")

        # Fecha del documento (desde fecha_inicio_asignacion)
        fecha_field = self._parse_fecha(asignacion.get("fecha_inicio_asignacion")) or datetime.now().strftime("%d/%m/%Y")

        fields = {
            "NOMBRE_EMPLEADO": nombre_empleado,
            "IDENTIDAD_EMPLEADO": identidad_empleado,
            "NOMBRE_USUARIO": "[NOMBRE_USUARIO]",
            "IDENTIDAD_USUARIO": "[IDENTIDAD_USUARIO]",
            "PUESTO": "[PUESTO]",
            "FECHA": fecha_field,
            "MARCA": dispositivo.get("nombre_marca") or "[MARCA]",
            "MODELO": dispositivo.get("nombre_modelo") or "[MODELO]",
            "NUMERO_LINEA": numero_linea,
            "IMEI": dispositivo.get("imei") or "[IMEI]",
            "COSTO": costo_plan,
            "MESES": meses_str,
        }

        try:
            tpl_path = select_template(dispositivo.get("categoria") or "")
        except Exception as e:
            logger.warning(
                "No se pudo seleccionar plantilla para categoria '%s': %s. Usando plantilla por defecto.",
                dispositivo.get("categoria"), e,
            )
            tpl_path = TEMPLATE_PRO_TI_003

        return self.generate_from_template_path(str(tpl_path), fields, save_as_pdf=True)

    # ------------------------------------------------------------------ TIER 4

    @staticmethod
    def convert_docx_to_pdf(input_docx, output_pdf=None) -> str:
        """Convierte DOCX a PDF usando docx2pdf (requiere MS Office).

        Returns:
            Ruta al archivo PDF generado.

        Raises:
            RuntimeError: si docx2pdf no esta disponible o falla la conversion.
        """
        if not HAS_DOCX2PDF or _docx2pdf_convert is None:
            raise RuntimeError(
                "docx2pdf no esta disponible. "
                "Instale docx2pdf en el entorno para habilitar exportacion a PDF."
            )

        input_path = Path(input_docx)
        if not input_path.exists():
            raise FileNotFoundError(f"Archivo DOCX no encontrado: {input_path}")

        out_path = Path(output_pdf) if output_pdf else input_path.with_suffix(".pdf")
        try:
            _docx2pdf_convert(str(input_path), str(out_path))
        except Exception as e:
            raise RuntimeError(f"Error al convertir DOCX a PDF: {e}") from e

        if not out_path.exists():
            raise RuntimeError(f"docx2pdf no genero el archivo de salida: {out_path}")

        return str(out_path)

    @staticmethod
    def select_template(categoria: str):
        """Selecciona la plantilla segun el tipo de dispositivo."""
        from .docexp import select_template
        return select_template(categoria)

    # ------------------------------------------------------------------ Privados

    @staticmethod
    def _safe_unlink(path: str) -> None:
        try:
            os.unlink(path)
        except Exception as e:
            logger.debug("No se pudo eliminar archivo temporal '%s': %s", path, e)

    @staticmethod
    def _calcular_meses(asignacion: dict) -> str:
        """Calcula la diferencia en meses usando fecha_inicio y fecha_fin del plan.

        Si plan_fecha_fin es None (plan vigente sin fecha de fin), usa la fecha actual.
        Retorna el número de meses como string, o "N/A" si hay error."""
        try:
            from dateutil.relativedelta import relativedelta

            fecha_inicio = asignacion.get("plan_fecha_inicio")
            fecha_fin = asignacion.get("plan_fecha_fin")

            # Validar fecha_inicio del plan (requerida)
            if not fecha_inicio:
                logger.warning("plan_fecha_inicio no disponible en asignacion")
                return "N/A"

            # Si fecha_fin del plan es None, usar fecha actual
            if not fecha_fin:
                fecha_fin = datetime.now()
                logger.debug("plan_fecha_fin no disponible, usando fecha actual")

            def to_date(val):
                if isinstance(val, str):
                    return datetime.fromisoformat(val).date()
                if isinstance(val, datetime):
                    return val.date()
                return val.date() if hasattr(val, "date") else val

            fecha_inicio_date = to_date(fecha_inicio)
            fecha_fin_date = to_date(fecha_fin)

            diff = relativedelta(fecha_fin_date, fecha_inicio_date)
            meses = diff.years * 12 + diff.months

            logger.debug(f"_calcular_meses: plan {fecha_inicio_date} → {fecha_fin_date} = {meses} meses")
            return str(meses)
        except Exception as e:
            logger.warning("Error calculando meses: %s (plan_inicio=%s, plan_fin=%s)",
                          e, asignacion.get("plan_fecha_inicio"), asignacion.get("plan_fecha_fin"))
            return "N/A"

    @staticmethod
    def _parse_fecha(fecha_raw) -> str | None:
        """Parsea una fecha y la retorna en formato dd/mm/yyyy."""
        if not fecha_raw:
            return None
        try:
            if isinstance(fecha_raw, str):
                fecha_raw = datetime.fromisoformat(fecha_raw).date()
            elif hasattr(fecha_raw, "date"):
                fecha_raw = fecha_raw.date()
            return fecha_raw.strftime("%d/%m/%Y")
        except Exception as e:
            logger.debug("No se pudo formatear fecha '%s': %s", fecha_raw, e)
            return None
