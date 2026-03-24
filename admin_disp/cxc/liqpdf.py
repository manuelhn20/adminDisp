import io
import os
import datetime
from flask import Response

from reportlab.lib.pagesizes import A4, LETTER, landscape
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "static", "img", "proimabg.png"))


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_date_input(date_str):
    if not date_str:
        return None
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_creado_ddmmyyyy(creado_str):
    if not creado_str:
        return None
    try:
        fecha = creado_str.split(" ")[0]
        return datetime.datetime.strptime(fecha, "%d/%m/%Y").date()
    except Exception:
        return None


def _formatea_fecha_ddmmyyyy(date_str):
    if not date_str:
        return ""
    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        return d.strftime("%d/%m/%Y")
    except Exception:
        return date_str


def _draw_header(canvas, doc):
    width, height = doc.pagesize
    margin = 20
    header_height = 50
    x0 = margin
    x1 = width - margin
    y0 = height - margin - header_height

    canvas.setLineWidth(1)
    canvas.rect(x0, y0, x1 - x0, header_height)

    total_width   = x1 - x0
    left_w        = total_width * 0.30
    right_w       = total_width * 0.20
    center_w      = total_width - left_w - right_w
    x_left_end    = x0 + left_w
    x_right_start = x1 - right_w

    canvas.line(x_left_end,    y0, x_left_end,    y0 + header_height)
    canvas.line(x_right_start, y0, x_right_start, y0 + header_height)

    canvas.setFont("Helvetica", 8)
    texto_x = x0 + 4
    line_h  = 9
    y_text  = y0 + header_height - 9

    empresa_txt   = "PROIMA"
    ejecutivo_txt = getattr(doc, "ejecutivo_txt", "Todos")
    rango_txt     = getattr(doc, "rango_txt",     "Todos")
    pagina_txt    = f"{canvas.getPageNumber()}"
    ahora         = datetime.datetime.now()
    fecha_emision = ahora.strftime("%d/%m/%Y %H:%M")

    canvas.drawString(texto_x, y_text, f"Empresa: {empresa_txt}")
    y_text -= line_h
    canvas.drawString(texto_x, y_text, f"Ejecutivo: {ejecutivo_txt}")
    y_text -= line_h
    canvas.drawString(texto_x, y_text, f"Fechas: {rango_txt}")
    y_text -= line_h
    canvas.drawString(texto_x, y_text, f"Fecha emision: {fecha_emision}")
    y_text -= line_h
    canvas.drawString(texto_x, y_text, f"Pagina: {pagina_txt}")

    titulo   = "DOCUMENTO DE LIQUIDACION DE FACTURAS"
    canvas.setFont("Helvetica-Bold", 11)
    center_x = x_left_end + center_w / 2.0
    center_y = y0 + header_height / 2.0 - 4
    canvas.drawCentredString(center_x, center_y, titulo)

    if os.path.exists(LOGO_PATH):
        try:
            logo_w = right_w - 10
            logo_h = header_height - 8
            logo_x = x_right_start + 5
            logo_y = y0 + 4
            canvas.drawImage(
                LOGO_PATH, logo_x, logo_y,
                width=logo_w, height=logo_h,
                preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            pass


def _recibo_key(row):
    raw    = str(row.get("No. Recibo", "")).strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    try:
        return int(digits) if digits else 0
    except Exception:
        return 0


def _parse_valor_to_float(valor_str):
    if not valor_str:
        return 0.0
    s = str(valor_str).replace("L", "").replace(",", "").replace(" ", "")
    try:
        return float(s)
    except Exception:
        return 0.0


def _get_min_max_dates(filtered_items):
    """
    Extrae las fechas mínima y máxima de los items filtrados.
    Retorna tupla (fecha_min, fecha_max) en formato DD/MM/YYYY.
    """
    if not filtered_items:
        return None, None
    
    dates = []
    for row in filtered_items:
        creado = _parse_creado_ddmmyyyy(row.get("Creado", ""))
        if creado:
            dates.append(creado)
    
    if not dates:
        return None, None
    
    min_date = min(dates)
    max_date = max(dates)
    return min_date.strftime("%d/%m/%Y"), max_date.strftime("%d/%m/%Y")


def _has_fecha_cheque(filtered_items):
    """
    Verifica si algún registro tiene datos en 'Fecha_Cheque'.
    """
    if not filtered_items:
        return False
    
    for row in filtered_items:
        fecha_cheque = str(row.get("Fecha_Cheque", "") or "").strip()
        if fecha_cheque:
            return True
    return False


def _get_fecha_cheque(row):
    """
    Obtiene el valor de 'Fecha_Cheque' de una fila.
    """
    return str(row.get("Fecha_Cheque", "") or "")


def build_pdf_report_from_rows(rows, ejecutivo_txt="", rango_txt="Todos"):
    """
    Genera PDF directamente desde una lista de rows (sin query a BD).
    
    Args:
        rows: Lista de diccionarios con los datos
        ejecutivo_txt: Nombre del ejecutivo
        rango_txt: Rango de fechas (formato: "DD/MM/YYYY al DD/MM/YYYY")
    
    Returns:
        Response con PDF
    """
    filtered_items = rows if rows else []
    filtered_items.sort(key=_recibo_key, reverse=False)

    # Si rango_txt no fue pasado (es el default "Todos"), intenta calcularlo desde los datos
    if rango_txt == "Todos":
        fecha_min, fecha_max = _get_min_max_dates(filtered_items)
        if fecha_min and fecha_max:
            rango_txt = f"{fecha_min} hasta {fecha_max}"
        else:
            rango_txt = "Todos"

    # Verificar si existe Fecha Cheque
    tiene_fecha_cheque = _has_fecha_cheque(filtered_items)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(LETTER),
        leftMargin=20, rightMargin=20,
        topMargin=80, bottomMargin=40,
    )
    doc.rango_txt     = rango_txt
    doc.ejecutivo_txt = ejecutivo_txt or "Todos"

    styles = getSampleStyleSheet()
    table_header_style = ParagraphStyle(
        "TableHeader", parent=styles["Normal"],
        fontSize=10, leading=12, textColor=colors.white,
        alignment=1, fontName="Helvetica-Bold",
    )
    table_cell_style = ParagraphStyle(
        "TableCell", parent=styles["Normal"],
        fontSize=9, leading=11, alignment=1,
    )
    table_cell_right_style = ParagraphStyle(
        "TableCellRight", parent=styles["Normal"],
        fontSize=9, leading=11, alignment=2,
    )
    footer_style = ParagraphStyle(
        "FooterText", parent=styles["Normal"],
        fontSize=9, alignment=4, spaceBefore=10, spaceAfter=8,
        textColor=colors.HexColor("#4b5563"),
    )
    signature_style = ParagraphStyle(
        "SignatureText", parent=styles["Normal"],
        fontSize=9, leading=12, alignment=1, spaceBefore=6,
    )

    story = []

    # Construir columnas dinámicamente
    col_labels = ["#", "Codigo", "Nombre cliente", "Metodo pago", "No. Factura", "Valor Pagado", "No. Recibo", "Liquidado"]
    col_keys   = ["#", "Código cliente", "Nombre cliente", "Método pago", "No. Factura", "Valor Pagado", "No. Recibo", "Liquidado"]
    
    if tiene_fecha_cheque:
        col_labels.append("Fecha Cheque")
        col_keys.append("Fecha Cheque")
    
    col_labels.extend(["Comentario Ejecutivo", "Comentario Liquidador"])
    col_keys.extend(["Comentario adicional", "Comentario_Liquidador"])  # Liquidador no existe en BD, será vacío

    table_header = [Paragraph(c, table_header_style) for c in col_labels]
    data        = [table_header]
    total_valor = 0.0

    for idx, row in enumerate(filtered_items, start=1):
        fila = []
        for label, key in zip(col_labels, col_keys):
            if label == "#":
                val = str(idx)
                cell_style = table_cell_style
            elif key == "Liquidado":
                raw = str(row.get(key, "") or "").strip()
                val = raw if raw else "No"
                cell_style = table_cell_style
            elif key == "Valor Pagado":
                val = str(row.get(key, "") or "")
                total_valor += _parse_valor_to_float(val)
                cell_style = table_cell_right_style
            elif label == "Fecha Cheque":
                val = _get_fecha_cheque(row)
                cell_style = table_cell_style
            elif label == "Comentario Ejecutivo":
                raw = str(row.get("Comentario adicional", "") or "")
                # Split visual: si existe \n o ||, solo mostrar primera parte
                split_marker = "\n" if "\n" in raw else ("||" if "||" in raw else None)
                if split_marker and split_marker in raw:
                    val = raw.split(split_marker)[0].strip()
                else:
                    val = raw
                cell_style = table_cell_style
            elif label == "Comentario Liquidador":
                # Siempre vacío para Comentario Liquidador (solo visual)
                val = ""
                cell_style = table_cell_style
            else:
                val = str(row.get(key, "") or "")
                cell_style = table_cell_style
            fila.append(Paragraph(val, cell_style))
        data.append(fila)

    if not filtered_items:
        data.append([Paragraph("No hay registros.", table_cell_style)] + [""] * (len(col_labels) - 1))
    else:
        total_text = f"L {total_valor:,.2f}"
        # Construir fila de totales dinámicamente
        total_row = [""] * 5 + [Paragraph(f"<b>{total_text}</b>", table_cell_right_style)] + [""] * (len(col_labels) - 6)
        data.append(total_row)

    # Calcular anchos de columnas dinámicamente
    # Ancho total disponible: 792 - 40 (márgenes) = 752  [LETTER horizontal]
    # # | Codigo | Nombre | Método | Factura | Valor | Recibo | Liquidado | [Fecha Cheque] | Comentario
    AVAILABLE_WIDTH = 752
    base_widths = [28, 68, 90, 76, 72, 75, 45, 40]
    if tiene_fecha_cheque:
        base_widths.insert(8, 60)  # Fecha Cheque
    # Comentario Ejecutivo y Liquidador
    remaining = max(120, AVAILABLE_WIDTH - sum(base_widths))
    base_widths.extend([remaining // 2, remaining - remaining // 2])

    table = Table(data, repeatRows=1, colWidths=base_widths)
    last_row_idx = len(data) - 1
    valor_pagado_col = 5  # Columna del Valor Pagado

    table_style_commands = [
        ("BOX",        (0, 0), (-1, -1),               0.75, colors.HexColor("#9ca3af")),
        ("GRID",       (0, 0), (-1, -1),               0.25, colors.HexColor("#d1d5db")),
        ("BACKGROUND", (0, 0), (-1, 0),                colors.HexColor("#4b5563")),
        ("TEXTCOLOR",  (0, 0), (-1, 0),                colors.white),
        ("ALIGN",      (0, 0), (-1, 0),                "CENTER"),
        ("FONTNAME",   (0, 0), (-1, 0),                "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, last_row_idx - 1), colors.white),
        ("ALIGN",      (0, 1), (-1, last_row_idx - 1), "CENTER"),
        ("ALIGN",      (valor_pagado_col, 1), (valor_pagado_col, last_row_idx), "RIGHT"),
        ("BACKGROUND", (0, last_row_idx), (-1, last_row_idx), colors.HexColor("#e5e7eb")),
        ("FONTNAME",   (0, last_row_idx), (-1, last_row_idx), "Helvetica-Bold"),
    ]

    table.setStyle(TableStyle(table_style_commands))

    story.append(table)
    story.append(Spacer(1, 10))

    texto_footer = (
        "El presente documento constituye la liquidacion de cobros realizada por el vendedor, "
        "quien declara que toda la informacion contenida facturas, recibos y montos es veridica "
        "y corresponde a operaciones efectivamente realizadas. Asimismo, manifiesta su conformidad "
        "y compromiso de entregar los valores reportados al departamento de Cuentas por Cobrar, "
        "quien a su vez confirma la recepcion y revision de esta liquidacion bajo las politicas "
        "establecidas por la empresa. "
        "<b>Confidencialidad:</b> Este documento es de uso estrictamente interno y confidencial "
        "de PROIMA; queda prohibida su reproduccion, distribucion o divulgacion a terceros sin "
        "autorizacion expresa."
    )
    story.append(Paragraph(texto_footer, footer_style))
    story.append(Spacer(1, 25))

    texto_ejecutivo = f"Ejecutivo: {ejecutivo_txt}" if ejecutivo_txt else "Ejecutivo: ____________________________"
    firmas_data = [[
        Paragraph("Liquidado por:<br/><br/><br/>____________________________", signature_style),
        Paragraph(f"{texto_ejecutivo}<br/><br/><br/>____________________________", signature_style),
        Paragraph("Fecha liquidacion:<br/><br/><br/>____________________________", signature_style),
    ]]
    firmas_table = Table(firmas_data, colWidths=[220, 220, 180], rowHeights=[70])
    firmas_table.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.75, colors.HexColor("#9ca3af")),
        ("GRID",          (0, 0), (-1, -1), 0.75, colors.HexColor("#d1d5db")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(firmas_table)

    doc.build(story, onFirstPage=_draw_header, onLaterPages=_draw_header)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def build_pdf_report(request_args, get_cxc_items_func):
    items, _columns = get_cxc_items_func()

    sucursal_f  = (request_args.get("sucursal")     or "").strip()
    ejecutivo_f = (request_args.get("ejecutivo")    or "").strip()
    cliente_f   = (request_args.get("cliente")      or "").strip().lower()
    recibo_f    = (request_args.get("recibo")       or "").strip().lower()
    f_ini_str   = (request_args.get("fecha_inicio") or "").strip()
    f_fin_str   = (request_args.get("fecha_fin")    or "").strip()
    fecha_ini   = _parse_date_input(f_ini_str)
    fecha_fin   = _parse_date_input(f_fin_str)

    filtered_items = []
    for row in items:
        if sucursal_f and row.get("Sucursal", "") != sucursal_f:
            continue
        if ejecutivo_f and row.get("Ejecutivo", "") != ejecutivo_f:
            continue
        if cliente_f:
            if cliente_f not in str(row.get("Codigo cliente", "")).lower() and \
               cliente_f not in str(row.get("Nombre cliente", "")).lower():
                continue
        if recibo_f and recibo_f not in str(row.get("No. Recibo", "")).lower():
            continue
        if fecha_ini or fecha_fin:
            creado_date = _parse_creado_ddmmyyyy(row.get("Creado", ""))
            if not creado_date:
                continue
            if fecha_ini and creado_date < fecha_ini:
                continue
            if fecha_fin and creado_date > fecha_fin:
                continue
        filtered_items.append(row)

    filtered_items.sort(key=_recibo_key, reverse=False)

    # Calcular rango de fechas desde los datos filtrados
    fecha_min, fecha_max = _get_min_max_dates(filtered_items)
    if fecha_min and fecha_max:
        rango_txt = f"{fecha_min} al {fecha_max}"
    else:
        rango_txt = "Todos"

    # Verificar si existe Fecha Cheque
    tiene_fecha_cheque = _has_fecha_cheque(filtered_items)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(LETTER),
        leftMargin=20, rightMargin=20,
        topMargin=80,  bottomMargin=40,
    )
    doc.rango_txt     = rango_txt
    doc.ejecutivo_txt = ejecutivo_f or "Todos"

    styles = getSampleStyleSheet()
    table_header_style = ParagraphStyle(
        "TableHeader", parent=styles["Normal"],
        fontSize=10, leading=12, textColor=colors.white,
        alignment=1, fontName="Helvetica-Bold",
    )
    table_cell_style = ParagraphStyle(
        "TableCell", parent=styles["Normal"],
        fontSize=9, leading=11, alignment=1,
    )
    table_cell_right_style = ParagraphStyle(
        "TableCellRight", parent=styles["Normal"],
        fontSize=9, leading=11, alignment=2,
    )
    footer_style = ParagraphStyle(
        "FooterText", parent=styles["Normal"],
        fontSize=9, alignment=4, spaceBefore=10, spaceAfter=8,
        textColor=colors.HexColor("#4b5563"),
    )
    signature_style = ParagraphStyle(
        "SignatureText", parent=styles["Normal"],
        fontSize=9, leading=12, alignment=1, spaceBefore=6,
    )

    story = []

    # Construir columnas dinámicamente
    col_labels = ["#", "Codigo", "Nombre cliente", "Metodo pago", "No. Factura", "Valor Pagado", "No. Recibo"]
    col_keys   = ["#", "Codigo cliente", "Nombre cliente", "Metodo pago", "No. Factura", "Valor Pagado", "No. Recibo"]
    
    if tiene_fecha_cheque:
        col_labels.append("Fecha Cheque")
        col_keys.append("Fecha Cheque")
    
    col_labels.append("Comentario")
    col_keys.append("Comentario adicional")

    table_header = [Paragraph(c, table_header_style) for c in col_labels]
    data        = [table_header]
    total_valor = 0.0

    for idx, row in enumerate(filtered_items, start=1):
        fila = []
        for label, key in zip(col_labels, col_keys):
            if label == "#":
                val = str(idx)
                cell_style = table_cell_style
            elif key == "Valor Pagado":
                val = str(row.get(key, "") or "")
                total_valor += _parse_valor_to_float(val)
                cell_style = table_cell_right_style
            elif label == "Fecha Cheque":
                val = _get_fecha_cheque(row)
                cell_style = table_cell_style
            else:
                val = str(row.get(key, "") or "")
                cell_style = table_cell_style
            fila.append(Paragraph(val, cell_style))
        data.append(fila)

    if not filtered_items:
        data.append([Paragraph("No hay registros.", table_cell_style)] + [""] * (len(col_labels) - 1))
    else:
        total_text = f"L {total_valor:,.2f}"
        # Construir fila de totales dinámicamente
        total_row = [""] * 5 + [Paragraph(f"<b>{total_text}</b>", table_cell_right_style)] + [""] * (len(col_labels) - 6)
        data.append(total_row)

    # Calcular anchos de columnas dinámicamente
    # Ancho total disponible: 792 - 40 (márgenes) = 752  [LETTER horizontal]
    # # | Codigo | Nombre | Método | Factura | Valor | Recibo | [Fecha Cheque] | Comentario
    AVAILABLE_WIDTH = 752
    base_widths = [22, 68, 110, 76, 72, 70, 40]
    if tiene_fecha_cheque:
        base_widths.append(55)  # Fecha Cheque
    base_widths.append(max(120, AVAILABLE_WIDTH - sum(base_widths)))  # Comentario

    table = Table(data, repeatRows=1, colWidths=base_widths)
    last_row_idx = len(data) - 1
    valor_pagado_col = 5  # Columna del Valor Pagado

    table_style_commands = [
        ("BOX",        (0, 0), (-1, -1),               0.75, colors.HexColor("#9ca3af")),
        ("GRID",       (0, 0), (-1, -1),               0.25, colors.HexColor("#d1d5db")),
        ("BACKGROUND", (0, 0), (-1, 0),                colors.HexColor("#4b5563")),
        ("TEXTCOLOR",  (0, 0), (-1, 0),                colors.white),
        ("ALIGN",      (0, 0), (-1, 0),                "CENTER"),
        ("FONTNAME",   (0, 0), (-1, 0),                "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, last_row_idx - 1), colors.white),
        ("ALIGN",      (0, 1), (-1, last_row_idx - 1), "CENTER"),
        ("ALIGN",      (valor_pagado_col, 1), (valor_pagado_col, last_row_idx), "RIGHT"),
        ("BACKGROUND", (0, last_row_idx), (-1, last_row_idx), colors.HexColor("#e5e7eb")),
        ("FONTNAME",   (0, last_row_idx), (-1, last_row_idx), "Helvetica-Bold"),
    ]

    table.setStyle(TableStyle(table_style_commands))

    story.append(table)
    story.append(Spacer(1, 10))

    texto_footer = (
        "El presente documento constituye la liquidacion de cobros realizada por el vendedor, "
        "quien declara que toda la informacion contenida facturas, recibos y montos es veridica "
        "y corresponde a operaciones efectivamente realizadas. Asimismo, manifiesta su conformidad "
        "y compromiso de entregar los valores reportados al departamento de Cuentas por Cobrar, "
        "quien a su vez confirma la recepcion y revision de esta liquidacion bajo las politicas "
        "establecidas por la empresa. "
        "<b>Confidencialidad:</b> Este documento es de uso estrictamente interno y confidencial "
        "de PROIMA; queda prohibida su reproduccion, distribucion o divulgacion a terceros sin "
        "autorizacion expresa."
    )
    story.append(Paragraph(texto_footer, footer_style))
    story.append(Spacer(1, 25))

    texto_ejecutivo = (f"Ejecutivo: {ejecutivo_f}" if ejecutivo_f
                       else "Ejecutivo: ____________________________")
    firmas_data = [[
        Paragraph("Liquidado por:<br/><br/><br/>____________________________", signature_style),
        Paragraph(f"{texto_ejecutivo}<br/><br/><br/>____________________________", signature_style),
        Paragraph("Fecha liquidacion:<br/><br/><br/>____________________________", signature_style),
    ]]
    firmas_table = Table(firmas_data, colWidths=[220, 220, 180], rowHeights=[70])
    firmas_table.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.75, colors.HexColor("#9ca3af")),
        ("GRID",          (0, 0), (-1, -1), 0.75, colors.HexColor("#d1d5db")),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(firmas_table)

    doc.build(story, onFirstPage=_draw_header, onLaterPages=_draw_header)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    return Response(pdf_bytes, mimetype="application/pdf",
                    headers={"Content-Disposition": "inline; filename=liquidacion_facturas.pdf"})
