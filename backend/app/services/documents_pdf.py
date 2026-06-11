from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import HTTPException, status

from app.models import Empresa
from app.models.pm import PMProyecto
from app.schemas.pm import PMEstimacionDetailOut
from app.schemas.procurement import PurchaseOrderResponse


ZERO = Decimal("0")


def _load_reportlab():
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La exportacion PDF no esta disponible en este entorno.",
        ) from exc

    return {
        "colors": colors,
        "TA_CENTER": TA_CENTER,
        "TA_RIGHT": TA_RIGHT,
        "A4": A4,
        "ParagraphStyle": ParagraphStyle,
        "getSampleStyleSheet": getSampleStyleSheet,
        "mm": mm,
        "Image": Image,
        "Paragraph": Paragraph,
        "SimpleDocTemplate": SimpleDocTemplate,
        "Spacer": Spacer,
        "Table": Table,
        "TableStyle": TableStyle,
    }


def _to_decimal(value) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return ZERO


def _money(value) -> str:
    amount = _to_decimal(value)
    return f"${amount:,.2f}"


def _number(value) -> str:
    amount = _to_decimal(value)
    if amount == amount.to_integral():
        return f"{amount:,.0f}"
    return f"{amount:,.2f}"


def _percent(value) -> str:
    amount = _to_decimal(value)
    return f"{amount:,.2f}%"


def _date_label(value: date | datetime | str | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _text(value: object | None, fallback: str = "-") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or fallback
    return str(value)


def _sanitize_filename(value: str, fallback: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in _text(value, fallback))
    cleaned = cleaned.strip("-_")
    return cleaned or fallback


def _company_title(company: Empresa) -> str:
    return _text(
        getattr(company, "nombre_comercial", None)
        or getattr(company, "razon_social", None)
        or company.name,
        "Empresa",
    )


def _company_location(company: Empresa) -> str | None:
    parts = [company.ciudad, company.estado, company.codigo_postal, company.pais]
    cleaned = [item.strip() for item in parts if isinstance(item, str) and item.strip()]
    if not cleaned:
        return None
    return ", ".join(cleaned)


def _company_lines(company: Empresa) -> list[str]:
    lines = [_company_title(company)]
    if company.razon_social and company.razon_social.strip() and company.razon_social.strip() != lines[0]:
        lines.append(company.razon_social.strip())
    if company.rfc:
        lines.append(f"RFC: {company.rfc.strip()}")
    if company.direccion and company.direccion.strip():
        lines.append(company.direccion.strip())
    location = _company_location(company)
    if location:
        lines.append(location)
    contact_parts = [item.strip() for item in [company.email_contacto, company.telefono] if isinstance(item, str) and item.strip()]
    if contact_parts:
        lines.append(" | ".join(contact_parts))
    return lines


def _maybe_read_logo_bytes(company: Empresa) -> bytes | None:
    for field_name in ("logo_url", "logo", "logo_path", "imagen_url", "image_url"):
        raw_value = getattr(company, field_name, None)
        if not isinstance(raw_value, str) or not raw_value.strip():
            continue
        value = raw_value.strip()
        try:
            parsed = urlparse(value)
            if parsed.scheme in {"http", "https"}:
                with urlopen(value, timeout=3) as response:  # noqa: S310
                    return response.read()
            path = Path(value)
            if path.exists() and path.is_file():
                return path.read_bytes()
        except Exception:
            continue
    return None


def _build_logo_flowable(rl: dict, company: Empresa):
    logo_bytes = _maybe_read_logo_bytes(company)
    if not logo_bytes:
        return None
    image_stream = BytesIO(logo_bytes)
    image = rl["Image"](image_stream)
    image._restrictSize(42 * rl["mm"], 20 * rl["mm"])
    return image


def _build_styles(rl: dict):
    styles = rl["getSampleStyleSheet"]()
    base_font = "Helvetica"
    colors = rl["colors"]
    return {
        "title": rl["ParagraphStyle"](
            "DocTitle",
            parent=styles["Heading1"],
            fontName=base_font,
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=6,
        ),
        "subtitle": rl["ParagraphStyle"](
            "DocSubtitle",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569"),
        ),
        "section": rl["ParagraphStyle"](
            "DocSection",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#111827"),
            spaceBefore=8,
            spaceAfter=6,
        ),
        "body": rl["ParagraphStyle"](
            "DocBody",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#111827"),
        ),
        "muted": rl["ParagraphStyle"](
            "DocMuted",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748b"),
        ),
        "small": rl["ParagraphStyle"](
            "DocSmall",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#334155"),
        ),
        "right": rl["ParagraphStyle"](
            "DocRight",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=9,
            leading=12,
            alignment=rl["TA_RIGHT"],
            textColor=colors.HexColor("#111827"),
        ),
        "center": rl["ParagraphStyle"](
            "DocCenter",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=9,
            leading=12,
            alignment=rl["TA_CENTER"],
            textColor=colors.HexColor("#111827"),
        ),
        "stamp": rl["ParagraphStyle"](
            "DocStamp",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=18,
            alignment=rl["TA_CENTER"],
            textColor=colors.HexColor("#b91c1c"),
        ),
    }


def _paragraph(rl: dict, text: str, style):
    escaped = (
        _text(text, "-")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    return rl["Paragraph"](escaped, style)


def _build_company_header(rl: dict, styles: dict, company: Empresa, title: str, subtitle: str):
    left_content = []
    logo = _build_logo_flowable(rl, company)
    if logo is not None:
        left_content.append(logo)
        left_content.append(rl["Spacer"](1, 3 * rl["mm"]))
    left_content.append(_paragraph(rl, _company_title(company), styles["title"]))
    left_content.append(_paragraph(rl, subtitle, styles["subtitle"]))

    right_lines = [_paragraph(rl, line, styles["body"]) for line in _company_lines(company)]
    header = rl["Table"](
        [[left_content, right_lines]],
        colWidths=[68 * rl["mm"], 110 * rl["mm"]],
    )
    header.setStyle(
        rl["TableStyle"](
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    title_block = rl["Table"](
        [[_paragraph(rl, title, styles["title"])]],
        colWidths=[178 * rl["mm"]],
    )
    title_block.setStyle(
        rl["TableStyle"](
            [
                ("BACKGROUND", (0, 0), (0, 0), rl["colors"].HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.6, rl["colors"].HexColor("#cbd5e1")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [header, rl["Spacer"](1, 4 * rl["mm"]), title_block]


def _build_meta_table(rl: dict, styles: dict, rows: list[tuple[str, str]], *, col_widths: list[float]):
    table_rows = []
    for label, value in rows:
        table_rows.append(
            [
                _paragraph(rl, label, styles["small"]),
                _paragraph(rl, value, styles["body"]),
            ]
        )
    table = rl["Table"](table_rows, colWidths=col_widths)
    table.setStyle(
        rl["TableStyle"](
            [
                ("BACKGROUND", (0, 0), (-1, -1), rl["colors"].white),
                ("BOX", (0, 0), (-1, -1), 0.5, rl["colors"].HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, rl["colors"].HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _build_line_table(rl: dict, styles: dict, headers: list[str], rows: list[list[str]], *, col_widths: list[float]):
    table_rows = [[_paragraph(rl, header, styles["small"]) for header in headers]]
    for row in rows:
        table_rows.append([_paragraph(rl, value, styles["body"]) for value in row])
    table = rl["Table"](table_rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        rl["TableStyle"](
            [
                ("BACKGROUND", (0, 0), (-1, 0), rl["colors"].HexColor("#e2e8f0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), rl["colors"].HexColor("#0f172a")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOX", (0, 0), (-1, -1), 0.5, rl["colors"].HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, rl["colors"].HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _build_totals_table(rl: dict, styles: dict, rows: list[tuple[str, str]]):
    content = [[_paragraph(rl, label, styles["body"]), _paragraph(rl, value, styles["right"])] for label, value in rows]
    table = rl["Table"](content, colWidths=[60 * rl["mm"], 38 * rl["mm"]], hAlign="RIGHT")
    table.setStyle(
        rl["TableStyle"](
            [
                ("BOX", (0, 0), (-1, -1), 0.5, rl["colors"].HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, rl["colors"].HexColor("#e2e8f0")),
                ("BACKGROUND", (0, 0), (-1, -1), rl["colors"].HexColor("#f8fafc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _build_story_shell(
    rl: dict,
    styles: dict,
    *,
    company: Empresa,
    document_title: str,
    subtitle: str,
    intro_rows: list[tuple[str, str]],
    secondary_rows: list[tuple[str, str]],
    line_section_title: str,
    line_headers: list[str],
    line_rows: list[list[str]],
    line_col_widths: list[float],
    totals_rows: list[tuple[str, str]],
    notes: str | None,
    cancelled: bool = False,
):
    story = []
    story.extend(_build_company_header(rl, styles, company, document_title, subtitle))
    story.append(rl["Spacer"](1, 4 * rl["mm"]))
    story.append(_build_meta_table(rl, styles, intro_rows, col_widths=[38 * rl["mm"], 51 * rl["mm"]]))
    story.append(rl["Spacer"](1, 3 * rl["mm"]))
    story.append(_build_meta_table(rl, styles, secondary_rows, col_widths=[38 * rl["mm"], 140 * rl["mm"]]))
    if cancelled:
        story.append(rl["Spacer"](1, 4 * rl["mm"]))
        story.append(_paragraph(rl, "VENTA CANCELADA", styles["stamp"]))
    story.append(rl["Spacer"](1, 4 * rl["mm"]))
    story.append(_paragraph(rl, line_section_title, styles["section"]))
    story.append(_build_line_table(rl, styles, line_headers, line_rows, col_widths=line_col_widths))
    story.append(rl["Spacer"](1, 4 * rl["mm"]))
    story.append(_build_totals_table(rl, styles, totals_rows))
    story.append(rl["Spacer"](1, 4 * rl["mm"]))
    story.append(_paragraph(rl, "Notas", styles["section"]))
    story.append(_paragraph(rl, _text(notes, "Sin notas"), styles["body"]))
    story.append(rl["Spacer"](1, 4 * rl["mm"]))
    story.append(_paragraph(rl, "Documento operativo. No es comprobante fiscal.", styles["muted"]))
    return story


def _render_pdf(story_builder):
    rl = _load_reportlab()
    styles = _build_styles(rl)
    buffer = BytesIO()
    document = rl["SimpleDocTemplate"](
        buffer,
        pagesize=rl["A4"],
        leftMargin=16 * rl["mm"],
        rightMargin=16 * rl["mm"],
        topMargin=14 * rl["mm"],
        bottomMargin=14 * rl["mm"],
        title="Documento operativo",
        author="CapellaOpsV2",
        pageCompression=0,
    )

    def draw_page_footer(canvas, doc):
        footer = f"Impreso: {_date_label(datetime.utcnow())} | Pagina {canvas.getPageNumber()}"
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(rl["colors"].HexColor("#64748b"))
        canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 10 * rl["mm"], footer)
        canvas.restoreState()

    story = story_builder(rl, styles)
    document.build(story, onFirstPage=draw_page_footer, onLaterPages=draw_page_footer)
    return buffer.getvalue()


def build_pm_estimation_pdf(company: Empresa, project: PMProyecto, estimation: PMEstimacionDetailOut) -> tuple[bytes, str]:
    subtitle = "Documento operativo. No es comprobante fiscal."

    def story_builder(rl: dict, styles: dict):
        intro_rows = [
            ("Folio", _text(estimation.folio, "Sin folio")),
            ("Fecha", _date_label(estimation.created_at)),
            ("Proyecto", _text(project.nombre)),
            ("Cliente", _text(project.cliente_nombre_snapshot, "Sin cliente")),
        ]
        periodo = _text(
            " - ".join(
                [
                    item
                    for item in [
                        _date_label(estimation.periodo_inicio) if estimation.periodo_inicio else "",
                        _date_label(estimation.periodo_fin) if estimation.periodo_fin else "",
                    ]
                    if item
                ]
            ),
            "Sin periodo",
        )
        secondary_rows = [
            ("Nombre", _text(estimation.nombre)),
            ("Estatus", _text(estimation.estatus)),
            ("Periodo", periodo),
            ("Moneda", _text(estimation.moneda, "MXN")),
        ]
        line_rows = [
            [
                _text(
                    f"{detail.codigo_snapshot or '-'} - {detail.concepto_snapshot}"
                    if detail.codigo_snapshot
                    else detail.concepto_snapshot
                ),
                _percent(detail.avance_anterior_pct),
                _percent(detail.avance_actual_pct),
                _percent(detail.avance_periodo_pct),
                _money(detail.importe_periodo),
            ]
            for detail in estimation.details
        ]
        totals_rows = [
            ("Subtotal", _money(estimation.monto_bruto)),
            ("Retencion", _money(estimation.retencion_monto)),
            ("Anticipo aplicado", _money(estimation.anticipo_aplicado)),
            ("Total neto", _money(estimation.monto_neto)),
        ]
        return _build_story_shell(
            rl,
            styles,
            company=company,
            document_title="Estimacion",
            subtitle=subtitle,
            intro_rows=intro_rows,
            secondary_rows=secondary_rows,
            line_section_title="Partidas",
            line_headers=["Concepto", "Av. anterior", "Av. actual", "Av. periodo", "Importe"],
            line_rows=line_rows or [["Sin partidas", "-", "-", "-", _money(0)]],
            line_col_widths=[82 * rl["mm"], 24 * rl["mm"], 24 * rl["mm"], 24 * rl["mm"], 24 * rl["mm"]],
            totals_rows=totals_rows,
            notes=estimation.descripcion,
            cancelled=_string_contains(estimation.estatus, "cancel"),
        )

    pdf_bytes = _render_pdf(story_builder)
    folio = _sanitize_filename(estimation.folio or estimation.nombre, "estimacion")
    return pdf_bytes, f"estimacion-{folio}.pdf"


def build_purchase_order_pdf(company: Empresa, order: PurchaseOrderResponse) -> tuple[bytes, str]:
    subtitle = "Documento operativo. No es comprobante fiscal."

    def story_builder(rl: dict, styles: dict):
        intro_rows = [
            ("Folio", _text(order.folio)),
            ("Fecha", _date_label(order.created_at)),
            ("Proveedor", _text(order.proveedor_nombre)),
            ("Almacen destino", _text(order.almacen_destino_nombre)),
        ]
        secondary_rows = [
            ("Estatus", _text(order.estatus)),
            ("Creada por", _text(order.created_by_nombre)),
            ("Actualizada", _date_label(order.updated_at)),
            ("Requisicion", _text(order.requisicion_folio, "Sin vinculo")),
            ("Contacto proveedor", _text(order.proveedor_contacto_snapshot, "No registrado")),
            ("Email proveedor", _text(order.proveedor_email_snapshot, "No registrado")),
            ("Telefono proveedor", _text(order.proveedor_telefono_snapshot, "No registrado")),
            ("Condiciones de pago", _text(order.condiciones_pago_snapshot, "No registradas")),
            ("Moneda", _text(order.moneda_snapshot, "No registrada")),
        ]
        line_rows = [
            [
                _text(detail.material_sku),
                _text(detail.material_nombre),
                _number(detail.cantidad),
                _text(detail.material_unidad),
                _money(detail.costo_unitario),
                _money(detail.total_linea),
            ]
            for detail in order.details
        ]
        totals_rows = [
            ("Subtotal", _money(order.subtotal)),
            ("Impuestos", _money(order.impuesto_total)),
            ("Total", _money(order.total)),
        ]
        return _build_story_shell(
            rl,
            styles,
            company=company,
            document_title="Orden de compra",
            subtitle=subtitle,
            intro_rows=intro_rows,
            secondary_rows=secondary_rows,
            line_section_title="Materiales",
            line_headers=["SKU", "Material", "Cantidad", "Unidad", "Costo unitario", "Subtotal"],
            line_rows=line_rows or [["-", "Sin renglones", "-", "-", _money(0), _money(0)]],
            line_col_widths=[24 * rl["mm"], 66 * rl["mm"], 20 * rl["mm"], 20 * rl["mm"], 24 * rl["mm"], 24 * rl["mm"]],
            totals_rows=totals_rows,
            notes=order.notas,
        )

    pdf_bytes = _render_pdf(story_builder)
    folio = _sanitize_filename(order.folio, "orden-compra")
    return pdf_bytes, f"orden-compra-{folio}.pdf"


def _string_contains(value: str | None, token: str) -> bool:
    return token.lower() in _text(value, "").lower()
