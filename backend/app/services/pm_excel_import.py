from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import date, datetime, time
import hashlib
import json
from pathlib import PurePosixPath

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.models.pm import PMEstimacion, PMEstimacionDetalle, PMPresupuesto, PMPresupuestoPartida
from app.models.pm_imports import PMEstimacionEvidencia, PMExcelImportRow, PMExcelImportSession
from app.services.pm import (
    PMContext,
    build_budget_item_record,
    build_estimation_detail_values,
    calculate_budget_sale_amount,
    quantize_money,
    quantize_rate,
    decimal_or_zero,
    ensure_pm_budget_manage_access,
    ensure_budget_editable,
    get_budget_for_company,
    generate_next_estimation_folio,
    get_project_for_company,
    refresh_estimation_totals,
    refresh_project_budget_totals,
    normalize_optional_text,
    normalize_required_text,
    refresh_budget_item_totals,
    utcnow,
    can_view_pm_project,
)
from app.services.pm_excel_parser import interpret_sheet, parse_xlsx


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _load(value: str | None, fallback):
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def _session_for_company(db: Session, empresa_id: str, session_id: str) -> PMExcelImportSession:
    session = db.scalar(select(PMExcelImportSession).where(
        PMExcelImportSession.id == session_id,
        PMExcelImportSession.empresa_id == empresa_id,
    ))
    if not session:
        raise HTTPException(status_code=404, detail="Importación no encontrada.")
    return session


def _summarize(rows: list[dict]) -> dict:
    included = [row for row in rows if row.get("include", True)]
    chapters = sum(1 for row in included if row.get("row_type") == "chapter")
    items = [row for row in included if row.get("row_type") == "item"]
    errors = sum(1 for row in items if any(code in {
        "missing_description", "invalid_quantity", "missing_unit", "invalid_unit_price",
        "duplicate_code", "duplicate_row", "accumulated_exceeds_contracted", "negative_remaining",
    } for code in row.get("warnings", [])))
    warnings = sum(len(row.get("warnings", [])) for row in included)
    total = Decimal("0")
    unrounded_total = Decimal("0")
    excel_total = Decimal("0")
    estimate_total_detected = Decimal("0")
    estimate_total_recalculated = Decimal("0")
    contracted_total = Decimal("0")
    accumulated_total = Decimal("0")
    remaining_total = Decimal("0")
    has_excel_total = False
    has_estimate_total = False
    for row in items:
        values = row.get("values") if isinstance(row.get("values"), dict) else row
        try:
            quantity = Decimal(str(values.get("quantity") or "0"))
            price = Decimal(str(values.get("unit_price") or "0"))
            total += calculate_budget_sale_amount(quantity, price)
            unrounded_total += quantize_rate(quantity) * quantize_rate(price)
        except InvalidOperation:
            pass
        try:
            contracted_quantity = Decimal(str(values.get("contracted_quantity") or values.get("quantity") or "0"))
            contracted_price = Decimal(str(values.get("unit_price") or "0"))
            contracted_total += contracted_quantity * contracted_price
        except InvalidOperation:
            pass
        try:
            budget_amount = calculate_budget_sale_amount(Decimal(str(values.get("quantity") or "0")), Decimal(str(values.get("unit_price") or "0")))
            estimate_amount = Decimal(str(values.get("this_estimate") or "0"))
            estimate_total_detected += estimate_amount
            estimate_total_recalculated += quantize_money(min(max(estimate_amount, Decimal("0")), budget_amount))
        except InvalidOperation:
            pass
        try:
            if values.get("amount_excel") not in (None, ""):
                has_excel_total = True
                excel_total += Decimal(str(values.get("amount_excel")))
        except InvalidOperation:
            pass
        if values.get("this_estimate") not in (None, ""):
            has_estimate_total = True
        for field, target in (
            ("accumulated", "accumulated"), ("remaining", "remaining"),
        ):
            try:
                amount = Decimal(str(values.get(field) or "0"))
            except InvalidOperation:
                continue
            if target == "accumulated": accumulated_total += amount
            else: remaining_total += amount
    difference_value = total - excel_total
    reconciliation = "sin_total_detectado"
    if has_excel_total:
        reconciliation = "conciliado" if abs(difference_value) < Decimal("0.01") else "diferencia"
        if reconciliation == "diferencia" and quantize_money(unrounded_total) == quantize_money(excel_total):
            reconciliation = "redondeo"
    estimate_difference_value = estimate_total_recalculated - estimate_total_detected
    return {
        "chapters_count": chapters,
        "items_count": len(items),
        "rows_count": len(included),
        "errors_count": errors,
        "warnings_count": warnings,
        "total_recalculated": str(quantize_money(total)),
        "total_detected": str(quantize_money(excel_total)),
        "difference": str(quantize_money(difference_value)),
        "reconciliation_status": reconciliation,
        "estimate_total_detected": str(estimate_total_detected.quantize(Decimal("0.01"))),
        "estimate_total_recalculated": str(estimate_total_recalculated.quantize(Decimal("0.01"))),
        "estimate_difference": str(estimate_difference_value.quantize(Decimal("0.01"))),
        "estimate_reconciliation_status": "sin_total_detectado" if not has_estimate_total else ("conciliado" if abs(estimate_difference_value) < Decimal("0.01") else "diferencia"),
        "contracted_total": str(contracted_total.quantize(Decimal("0.01"))),
        "accumulated_total": str(accumulated_total.quantize(Decimal("0.01"))),
        "remaining_total": str(remaining_total.quantize(Decimal("0.01"))),
    }


def _refresh_cross_row_warnings(rows: list[PMExcelImportRow]) -> None:
    cross_codes = {"duplicate_code", "duplicate_row", "accumulated_exceeds_contracted", "negative_remaining"}
    active_items = []
    for row in rows:
        values = _load(row.confirmed_values_json, {})
        warnings = [code for code in _load(row.warning_codes_json, []) if code not in cross_codes]
        if row.include and values.get("row_type", row.row_type) == "item":
            active_items.append((row, values, warnings))
    code_counts: dict[str, int] = {}
    signature_counts: dict[tuple[str, ...], int] = {}
    for _row, values, _warnings in active_items:
        code = str(values.get("code") or "").strip().casefold()
        if code:
            code_counts[code] = code_counts.get(code, 0) + 1
        signature = tuple(str(values.get(key) or "").strip().casefold() for key in ("concept", "unit", "quantity", "unit_price"))
        if signature[0]:
            signature_counts[signature] = signature_counts.get(signature, 0) + 1
    for row, values, warnings in active_items:
        code = str(values.get("code") or "").strip().casefold()
        signature = tuple(str(values.get(key) or "").strip().casefold() for key in ("concept", "unit", "quantity", "unit_price"))
        if code and code_counts[code] > 1:
            warnings.append("duplicate_code")
        if signature[0] and signature_counts[signature] > 1:
            warnings.append("duplicate_row")
        try:
            contracted_amount = Decimal(str(values.get("quantity"))) * Decimal(str(values.get("unit_price")))
            if Decimal(str(values.get("accumulated"))) > contracted_amount + Decimal("0.02"):
                warnings.append("accumulated_exceeds_contracted")
        except (InvalidOperation, TypeError):
            pass
        try:
            if Decimal(str(values.get("remaining"))) < 0:
                warnings.append("negative_remaining")
        except (InvalidOperation, TypeError):
            pass
        row.warning_codes_json = _json(list(dict.fromkeys(warnings)))


def _public_row(row: PMExcelImportRow) -> dict:
    values = _load(row.confirmed_values_json, {})
    values.pop("_excluded_by_user", None)
    values.pop("_include_explicit", None)
    values.pop("_row_type_explicit", None)
    values.setdefault("row_type", row.row_type)
    values.setdefault("include", row.include)
    return {
        "id": row.id,
        "source_sheet": row.source_sheet,
        "source_row": row.source_row,
        "row_type": row.row_type,
        "include": row.include,
        "raw_values": _load(row.raw_values_json, []),
        "interpreted_values": _load(row.interpreted_values_json, {}),
        "values": values,
        "warnings": _load(row.warning_codes_json, []),
        "edited": row.edited_by_user is not None,
    }


def _read_rows(db: Session, session: PMExcelImportSession) -> list[PMExcelImportRow]:
    return db.scalars(select(PMExcelImportRow).where(
        PMExcelImportRow.empresa_id == session.empresa_id,
        PMExcelImportRow.session_id == session.id,
    ).order_by(PMExcelImportRow.source_row.asc(), PMExcelImportRow.id.asc())).all()


def serialize_import_session(db: Session, session: PMExcelImportSession) -> dict:
    metadata = _load(session.metadata_json, {})
    rows = _read_rows(db, session)
    selected_rows = [row for row in rows if row.source_sheet == session.selected_sheet]
    return {
        "id": session.id,
        "proyecto_id": session.proyecto_id,
        "filename": session.filename,
        "file_hash": session.file_hash,
        "source_file_available": bool(session.original_file_reference),
        "source_file_size": session.original_file_size,
        "uploaded_at": session.uploaded_at,
        "source_file": {
            "available": bool(session.original_file_reference),
            "filename": session.filename,
            "sha256": session.file_hash,
            "size_bytes": session.original_file_size,
            "content_type": session.original_file_content_type,
            "uploaded_by": session.uploaded_by,
            "uploaded_at": session.uploaded_at,
        },
        "status": session.status,
        "format_type": session.format_type,
        "selected_sheet": session.selected_sheet,
        "sheets": metadata.get("sheets", []),
        "headers": metadata.get("headers", []),
        "mapping": _load(session.mapping_json, {}),
        "metadata": {key: value for key, value in metadata.items() if key not in {"sheet_rows", "mapping_by_sheet"}},
        "summary": _load(session.summary_json, {}),
        "rows": [_public_row(row) for row in selected_rows],
        "evidences": [serialize_evidence(row) for row in db.scalars(select(PMEstimacionEvidencia).where(
            PMEstimacionEvidencia.empresa_id == session.empresa_id,
            PMEstimacionEvidencia.import_session_id == session.id,
            PMEstimacionEvidencia.activo == True,
        ).order_by(PMEstimacionEvidencia.created_at.asc())).all()],
        "confirmed_at": session.confirmed_at,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def serialize_import_session_summary(session: PMExcelImportSession) -> dict:
    metadata = _load(session.metadata_json, {})
    return {
        "id": session.id,
        "proyecto_id": session.proyecto_id,
        "filename": session.filename,
        "file_hash": session.file_hash,
        "status": session.status,
        "format_type": session.format_type,
        "selected_sheet": session.selected_sheet,
        "summary": _load(session.summary_json, {}),
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "estimation_name": metadata.get("estimation_name"),
    }


def create_import_session(db: Session, pm_context: PMContext, project_id: str, filename: str, data: bytes, content_type: str | None = None) -> dict:
    ensure_pm_budget_manage_access(pm_context)
    project = get_project_for_company(db, pm_context.empresa_id, project_id)
    parsed = parse_xlsx(data, filename, content_type)
    file_hash = hashlib.sha256(data).hexdigest()
    selected = parsed["selected_sheet"]
    metadata = {
        "sheets": parsed["sheets"],
        "mapping_by_sheet": parsed["mapping_by_sheet"],
        "headers": next((sheet["headers"] for sheet in parsed["sheets"] if sheet["name"] == selected), []),
        "source_sheet": selected,
        "estimation_number": parsed["estimation_number"],
        "estimation_name": parsed["estimation_name"],
        "generic_mapping_required": bool(next((sheet["mapping_required"] for sheet in parsed["sheets"] if sheet["name"] == selected), True)),
    }
    session = PMExcelImportSession(
        empresa_id=pm_context.empresa_id,
        proyecto_id=project.id,
        uploaded_by=pm_context.user.id,
        filename=filename[:255],
        file_hash=file_hash,
        status="review",
        format_type=parsed["format_type"],
        selected_sheet=selected,
        mapping_json=_json(parsed["selected_mapping"]),
        metadata_json=_json(metadata),
        summary_json="{}",
    )
    db.add(session)
    db.flush()
    for sheet in parsed["sheets"]:
        sheet_name = sheet["name"]
        sheet_meta = {
            **sheet,
            "rows": parsed["sheet_rows"].get(sheet_name, []),
            "format_type": parsed["format_type"],
        }
        mapping = parsed["mapping_by_sheet"].get(sheet_name, {})
        interpreted_rows = interpret_sheet(sheet_meta, mapping)
        by_source_row = {item["source_row"]: item for item in interpreted_rows}
        for source_row, raw_cells in enumerate(sheet_meta["rows"], 1):
            raw_values = [cell.get("value") for cell in raw_cells]
            if not any(value not in (None, "") for value in raw_values):
                continue
            interpreted = by_source_row.get(source_row, {
                "source_row": source_row, "row_type": "ignored", "code": None,
                "chapter": None, "concept": "", "unit": None, "quantity": None,
                "unit_price": None, "amount_excel": None, "amount_calculated": None,
                "warnings": [], "raw_values": raw_values,
            })
            include = sheet_name == selected and interpreted.get("row_type") in {"item", "chapter"}
            db.add(PMExcelImportRow(
                empresa_id=pm_context.empresa_id,
                session_id=session.id,
                source_sheet=sheet_name,
                source_row=source_row,
                row_type=interpreted.get("row_type", "ignored"),
                raw_values_json=_json(raw_cells),
                interpreted_values_json=_json(interpreted),
                confirmed_values_json=_json({"source_row": source_row, **{key: interpreted.get(key) for key in (
                    "code", "chapter", "concept", "unit", "quantity", "unit_price", "amount_excel", "amount_calculated",
                    "contracted_quantity", "previous_progress", "this_estimate", "accumulated", "remaining",
                )}}),
                warning_codes_json=_json(interpreted.get("warnings", [])),
                include=include,
            ))
    db.flush()
    _refresh_cross_row_warnings([row for row in _read_rows(db, session) if row.source_sheet == selected])
    rows = [_public_row(row) for row in _read_rows(db, session) if row.source_sheet == selected]
    session.summary_json = _json(_summarize(rows))
    db.add(AuditLog(
        empresa_id=pm_context.empresa_id,
        usuario_id=pm_context.user.id,
        action="pm.excel_import.upload",
        entity_name="pm_excel_import_session",
        entity_id=session.id,
        metadata_json={"project_id": project.id, "filename": filename[:255], "sha256": file_hash, "sheet": selected},
    ))
    db.flush()
    return serialize_import_session(db, session)


def get_import_session(db: Session, pm_context: PMContext, session_id: str) -> dict:
    session = _session_for_company(db, pm_context.empresa_id, session_id)
    return serialize_import_session(db, session)


def update_import_mapping(db: Session, pm_context: PMContext, session_id: str, *, selected_sheet: str, mapping: dict[str, int]) -> dict:
    ensure_pm_budget_manage_access(pm_context)
    session = _session_for_company(db, pm_context.empresa_id, session_id)
    if session.status not in {"review", "ready"}:
        raise HTTPException(status_code=409, detail="Esta revisión ya no se puede modificar.")
    metadata = _load(session.metadata_json, {})
    if selected_sheet not in {sheet.get("name") for sheet in metadata.get("sheets", [])}:
        raise HTTPException(status_code=400, detail="Selecciona una hoja disponible.")
    headers = next(sheet.get("headers", []) for sheet in metadata["sheets"] if sheet["name"] == selected_sheet)
    allowed_fields = {"codigo", "capitulo", "concepto", "unidad", "cantidad", "precio_unitario", "importe", "cantidad_contratada", "avance_anterior", "esta_estimacion", "acumulado", "por_ejecutar"}
    if any(key not in allowed_fields or not isinstance(value, int) or value < 0 or value >= len(headers) for key, value in mapping.items()):
        raise HTTPException(status_code=400, detail="Revisa la relación entre columnas y campos.")
    has_quantity = "cantidad" in mapping or "cantidad_contratada" in mapping
    if not {"concepto", "precio_unitario"}.issubset(mapping) or not has_quantity:
        session.status = "review"
    else:
        session.status = "ready"
    session.selected_sheet = selected_sheet
    session.mapping_json = _json(mapping)
    metadata["headers"] = headers
    metadata["source_sheet"] = selected_sheet
    metadata["generic_mapping_required"] = False
    session.metadata_json = _json(metadata)
    db.add(AuditLog(
        empresa_id=pm_context.empresa_id,
        usuario_id=pm_context.user.id,
        action="pm.excel_import.mapping_update",
        entity_name="pm_excel_import_session",
        entity_id=session.id,
        metadata_json={"project_id": session.proyecto_id, "sheet": selected_sheet, "mapping": mapping},
    ))
    all_rows = _read_rows(db, session)
    selected_rows = [row for row in all_rows if row.source_sheet == selected_sheet]
    sheet_rows = [_load(row.raw_values_json, []) for row in selected_rows]
    sheet_meta = {
        "name": selected_sheet,
        "format_type": session.format_type,
        "headers": headers,
        "header_row": next((sheet.get("header_row") for sheet in metadata["sheets"] if sheet.get("name") == selected_sheet), None),
        "rows": sheet_rows,
        "source_row_numbers": [row.source_row for row in selected_rows],
    }
    interpreted = interpret_sheet(sheet_meta, mapping)
    interpreted_by_line = {row["source_row"]: row for row in interpreted}
    for row in all_rows:
        if row.source_sheet != selected_sheet:
            row.include = False
            continue
        prior_values = _load(row.confirmed_values_json, {})
        excluded_by_user = bool(prior_values.get("_excluded_by_user"))
        source_cells = _load(row.raw_values_json, [])
        raw_values = [cell.get("value") if isinstance(cell, dict) else cell for cell in source_cells]
        fresh = interpreted_by_line.get(row.source_row)
        if fresh:
            row.row_type = fresh["row_type"]
            row.include = row.row_type in {"item", "chapter"} and not excluded_by_user
            row.interpreted_values_json = _json(fresh)
            confirmed_values = {"source_row": row.source_row, **{key: fresh.get(key) for key in (
                "code", "chapter", "concept", "unit", "quantity", "unit_price", "amount_excel", "amount_calculated",
                "contracted_quantity", "previous_progress", "this_estimate", "accumulated", "remaining",
            )}}
            if excluded_by_user:
                confirmed_values["_excluded_by_user"] = True
            row.confirmed_values_json = _json(confirmed_values)
            row.warning_codes_json = _json(fresh.get("warnings", []))
        elif raw_values:
            row.row_type = "ignored"
            row.include = False
    db.flush()
    selected_rows = [row for row in all_rows if row.source_sheet == selected_sheet]
    _refresh_cross_row_warnings(selected_rows)
    session.summary_json = _json(_summarize([_public_row(row) for row in selected_rows]))
    return serialize_import_session(db, session)


def update_import_details(db: Session, pm_context: PMContext, session_id: str, payload: dict) -> dict:
    ensure_pm_budget_manage_access(pm_context)
    session = _session_for_company(db, pm_context.empresa_id, session_id)
    if session.status not in {"review", "ready"}:
        raise HTTPException(status_code=409, detail="Esta revisión ya no se puede modificar.")
    metadata = _load(session.metadata_json, {})
    field_limits = {
        "project_name": 180, "client_name": 180, "contract_reference": 120,
        "contractor": 180, "supervisor": 180, "currency": 8,
        "estimation_name": 180, "estimation_period": 120, "estimation_notes": 2000,
    }
    for key, limit in field_limits.items():
        if key in payload:
            value = str(payload.get(key) or "").strip()
            if len(value) > limit:
                raise HTTPException(status_code=400, detail="Uno de los datos generales es demasiado largo.")
            metadata[key] = value or None
    session.metadata_json = _json(metadata)
    db.add(AuditLog(
        empresa_id=pm_context.empresa_id,
        usuario_id=pm_context.user.id,
        action="pm.excel_import.details_update",
        entity_name="pm_excel_import_session",
        entity_id=session.id,
        metadata_json={"project_id": session.proyecto_id, "fields": sorted(key for key in payload if key in field_limits)},
    ))
    db.flush()
    return serialize_import_session(db, session)


def update_import_row(db: Session, pm_context: PMContext, session_id: str, row_id: str, payload: dict) -> dict:
    ensure_pm_budget_manage_access(pm_context)
    session = _session_for_company(db, pm_context.empresa_id, session_id)
    if session.status not in {"review", "ready"}:
        raise HTTPException(status_code=409, detail="Esta revisión ya no se puede modificar.")
    row = db.scalar(select(PMExcelImportRow).where(
        PMExcelImportRow.id == row_id,
        PMExcelImportRow.session_id == session.id,
        PMExcelImportRow.empresa_id == pm_context.empresa_id,
        PMExcelImportRow.source_sheet == session.selected_sheet,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Renglón no encontrado.")
    values = _load(row.confirmed_values_json, {})
    values.setdefault("row_type", row.row_type)
    values.setdefault("include", row.include)
    for key in (
        "code", "chapter", "concept", "unit", "quantity", "unit_price", "amount_excel", "amount_calculated",
        "contracted_quantity", "previous_progress", "this_estimate", "accumulated", "remaining", "row_type", "include",
    ):
        if key in payload:
            values[key] = payload[key]
    if payload.get("_include_explicit") and "include" in payload:
        values["_excluded_by_user"] = payload["include"] is False
    if payload.get("_row_type_explicit") and "row_type" in payload:
        values["_excluded_by_user"] = payload["row_type"] == "ignored"
    if values.get("row_type") not in {"chapter", "item", "ignored"}:
        raise HTTPException(status_code=400, detail="Selecciona un tipo de renglón válido.")
    warnings = [code for code in _load(row.warning_codes_json, []) if code in {"formula_error", "formula_without_cached_value"}]
    if values.get("row_type") == "ignored" and "summary_row" in _load(row.warning_codes_json, []):
        warnings.append("summary_row")
    if values.get("row_type") == "item":
        quantity = None
        price = None
        if not str(values.get("concept") or "").strip():
            warnings.append("missing_description")
        try:
            quantity = Decimal(str(values.get("quantity")))
            if quantity <= 0:
                warnings.append("invalid_quantity")
        except (InvalidOperation, TypeError):
            warnings.append("invalid_quantity")
        if not str(values.get("unit") or "").strip():
            warnings.append("missing_unit")
        try:
            price = Decimal(str(values.get("unit_price")))
            if price < 0:
                warnings.append("invalid_unit_price")
        except (InvalidOperation, TypeError):
            warnings.append("invalid_unit_price")
        try:
            if not warnings:
                values["amount_calculated"] = str(calculate_budget_sale_amount(quantity, price))
                if values.get("amount_excel") not in (None, "") and abs(Decimal(str(values["amount_excel"])) - quantity * price) > Decimal("0.02"):
                    warnings.append("amount_mismatch")
                if values.get("this_estimate") not in (None, "") and Decimal(str(values["this_estimate"])) > quantity * price + Decimal("0.02"):
                    warnings.append("estimate_exceeds_budget")
        except (InvalidOperation, TypeError):
            pass
        if quantity is not None and price is not None:
            try:
                contracted = quantity * price
                accumulated = Decimal(str(values.get("accumulated")))
                remaining = Decimal(str(values.get("remaining")))
                if accumulated > contracted + Decimal("0.02"):
                    warnings.append("accumulated_exceeds_contracted")
                if remaining < 0:
                    warnings.append("negative_remaining")
            except (InvalidOperation, TypeError):
                pass
    row.row_type = values.get("row_type", row.row_type)
    row.include = bool(values.get("include", row.include)) and row.row_type != "ignored"
    row.confirmed_values_json = _json(values)
    row.warning_codes_json = _json(warnings)
    row.edited_by_user = pm_context.user.id
    db.flush()
    selected_rows = [item for item in _read_rows(db, session) if item.source_sheet == session.selected_sheet]
    _refresh_cross_row_warnings(selected_rows)
    rows = [_public_row(item) for item in selected_rows]
    session.summary_json = _json(_summarize(rows))
    session.status = "ready" if _summarize(rows)["errors_count"] == 0 else "review"
    db.add(AuditLog(
        empresa_id=pm_context.empresa_id,
        usuario_id=pm_context.user.id,
        action="pm.excel_import.row_update",
        entity_name="pm_excel_import_row",
        entity_id=row.id,
        metadata_json={"project_id": session.proyecto_id, "source_sheet": row.source_sheet, "source_row": row.source_row, "warnings": _load(row.warning_codes_json, [])},
    ))
    return serialize_import_session(db, session)


def add_import_row(db: Session, pm_context: PMContext, session_id: str, payload: dict) -> dict:
    ensure_pm_budget_manage_access(pm_context)
    session = _session_for_company(db, pm_context.empresa_id, session_id)
    if session.status not in {"review", "ready"}:
        raise HTTPException(status_code=409, detail="Esta revisión ya no se puede modificar.")
    if payload.get("row_type", "item") not in {"item", "chapter"}:
        raise HTTPException(status_code=400, detail="Selecciona capítulo o partida para el nuevo renglón.")
    existing_count = db.scalar(select(func.count(PMExcelImportRow.id)).where(PMExcelImportRow.session_id == session.id)) or 0
    row = PMExcelImportRow(
        empresa_id=pm_context.empresa_id,
        session_id=session.id,
        source_sheet=session.selected_sheet or "Revisión manual",
        source_row=100000 + int(existing_count),
        row_type=payload.get("row_type", "item"),
        raw_values_json="[]",
        interpreted_values_json="{}",
        confirmed_values_json=_json(payload),
        warning_codes_json="[]",
        include=True,
        edited_by_user=pm_context.user.id,
    )
    row.warning_codes_json = _json(_validation_warnings(payload))
    db.add(row)
    db.flush()
    selected_rows = [item for item in _read_rows(db, session) if item.source_sheet == session.selected_sheet]
    _refresh_cross_row_warnings(selected_rows)
    rows = [_public_row(item) for item in selected_rows]
    session.summary_json = _json(_summarize(rows))
    return serialize_import_session(db, session)


def _validation_warnings(values: dict) -> list[str]:
    if values.get("row_type") == "chapter":
        return [] if str(values.get("concept") or "").strip() else ["missing_description"]
    warnings = []
    if not str(values.get("concept") or "").strip():
        warnings.append("missing_description")
    if not str(values.get("unit") or "").strip():
        warnings.append("missing_unit")
    for field in ("quantity", "unit_price"):
        try:
            number = Decimal(str(values.get(field)))
            if number <= 0 if field == "quantity" else number < 0:
                warnings.append("invalid_quantity" if field == "quantity" else "invalid_unit_price")
        except (InvalidOperation, TypeError):
            warnings.append("invalid_quantity" if field == "quantity" else "invalid_unit_price")
    return warnings


def confirm_import(db: Session, pm_context: PMContext, session_id: str, *, warnings_acknowledged: bool) -> dict:
    ensure_pm_budget_manage_access(pm_context)
    session = _session_for_company(db, pm_context.empresa_id, session_id)
    if session.status == "imported":
        return {"ok": True, "already_imported": True, **_load(session.summary_json, {})}
    claimed = db.execute(update(PMExcelImportSession).where(
        PMExcelImportSession.id == session.id,
        PMExcelImportSession.empresa_id == pm_context.empresa_id,
        PMExcelImportSession.status.in_(["ready", "review"]),
    ).values(status="importing").execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        db.refresh(session)
        if session.status == "imported":
            return {"ok": True, "already_imported": True, **_load(session.summary_json, {})}
        raise HTTPException(status_code=409, detail="Esta importación no está disponible para confirmar.")
    session.status = "importing"
    project = get_project_for_company(db, pm_context.empresa_id, session.proyecto_id)
    existing_budget = db.scalar(select(PMPresupuesto.id).where(
        PMPresupuesto.empresa_id == pm_context.empresa_id,
        PMPresupuesto.proyecto_id == project.id,
        PMPresupuesto.activo == True,
        PMPresupuesto.items.any(PMPresupuestoPartida.activo == True),
    ))
    if existing_budget:
        raise HTTPException(status_code=409, detail="Este proyecto ya tiene un presupuesto detallado. Importar sobre un presupuesto existente estará disponible después de crear una revisión.")
    selected_rows = [row for row in _read_rows(db, session) if row.source_sheet == session.selected_sheet]
    _refresh_cross_row_warnings(selected_rows)
    rows = [row for row in selected_rows if row.include]
    confirmed = [(row, _load(row.confirmed_values_json, {})) for row in rows]
    summary = _summarize([_public_row(row) for row, _ in confirmed])
    if summary["errors_count"]:
        raise HTTPException(status_code=400, detail="Corrige los errores marcados antes de confirmar la importación.")
    if summary["warnings_count"] and not warnings_acknowledged:
        raise HTTPException(status_code=400, detail="Confirma que revisaste las advertencias.")
    parts = [values for _, values in confirmed if values.get("row_type", "item") == "item"]
    if not parts:
        raise HTTPException(status_code=400, detail="Agrega al menos una partida antes de confirmar.")
    db.flush()
    metadata = _load(session.metadata_json, {})
    budget = PMPresupuesto(
        empresa_id=pm_context.empresa_id,
        proyecto_id=project.id,
        nombre="Presupuesto importado",
        version=1,
        estatus="borrador",
        moneda=str(metadata.get("currency") or "MXN").upper()[:8],
        activo=True,
        created_by=pm_context.user.id,
        updated_by=pm_context.user.id,
    )
    db.add(budget)
    db.flush()
    created_chapters: dict[str, PMPresupuestoPartida] = {}
    imported_items: list[tuple[PMPresupuestoPartida, dict]] = []
    order = 0
    for source, values in confirmed:
        row_type = values.get("row_type", source.row_type)
        if row_type == "chapter":
            chapter = build_budget_item_record(
                empresa_id=pm_context.empresa_id, presupuesto_id=budget.id, proyecto_id=project.id,
                parent_id=None, codigo=values.get("code"), nombre=str(values.get("concept") or "Capítulo importado")[:180],
                descripcion=None, tipo="capitulo", unidad=None, cantidad=Decimal("1"), margen_pct=Decimal("0"),
                precio_unitario_manual=None, orden=order,
            )
            order += 1
            db.add(chapter)
            db.flush()
            if values.get("code"):
                created_chapters[str(values["code"])] = chapter
            created_chapters[str(values.get("concept") or "").strip().lower()] = chapter
            continue
        chapter_key = str(values.get("chapter") or "").strip().lower()
        chapter = created_chapters.get(chapter_key) if chapter_key else None
        if chapter_key and not chapter:
            chapter = build_budget_item_record(
                empresa_id=pm_context.empresa_id, presupuesto_id=budget.id, proyecto_id=project.id,
                parent_id=None, codigo=None, nombre=str(values.get("chapter"))[:180], descripcion=None,
                tipo="capitulo", unidad=None, cantidad=Decimal("1"), margen_pct=Decimal("0"),
                precio_unitario_manual=None, orden=order,
            )
            order += 1
            db.add(chapter)
            db.flush()
            created_chapters[chapter_key] = chapter
        try:
            quantity = Decimal(str(values.get("quantity")))
            unit_price = Decimal(str(values.get("unit_price")))
        except (InvalidOperation, TypeError):
            raise HTTPException(status_code=400, detail="Revisa cantidad y precio unitario de las partidas.")
        item = build_budget_item_record(
            empresa_id=pm_context.empresa_id, presupuesto_id=budget.id, proyecto_id=project.id,
            parent_id=chapter.id if chapter else None, codigo=values.get("code"),
            nombre=str(values.get("concept") or "").strip()[:180], descripcion=None, tipo="partida",
            unidad=str(values.get("unit") or "").strip()[:40], cantidad=quantity,
            margen_pct=Decimal("0"), precio_unitario_manual=unit_price, orden=order,
        )
        order += 1
        db.add(item)
        db.flush()
        imported_items.append((item, values))
        source.confirmed_values_json = _json(values)
    budget.notas = f"Importado desde {session.filename}; SHA-256 {session.file_hash}. Hoja: {session.selected_sheet}."
    for item, _values in imported_items:
        refresh_budget_item_totals(db, item)
    db.flush()
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=project.id)
    estimation_name = str(metadata.get("estimation_name") or "Estimación importada")[:180]
    estimation = PMEstimacion(
        empresa_id=pm_context.empresa_id,
        proyecto_id=project.id,
        presupuesto_id=budget.id,
        folio=generate_next_estimation_folio(db, empresa_id=pm_context.empresa_id, project_id=project.id),
        nombre=estimation_name,
        descripcion=" · ".join(value for value in (
            f"Importada desde hoja {session.selected_sheet} del archivo {session.filename}.",
            f"Periodo: {metadata.get('estimation_period')}" if metadata.get("estimation_period") else None,
            str(metadata.get("estimation_notes") or "").strip() or None,
        ) if value)[:2000],
        estatus="borrador",
        moneda=budget.moneda,
        retencion_pct=Decimal("0"),
        anticipo_aplicado=Decimal("0"),
        requiere_aprobacion=True,
        created_by=pm_context.user.id,
        updated_by=pm_context.user.id,
        activo=True,
    )
    db.add(estimation)
    db.flush()
    for item, values in imported_items:
        amount_budget = Decimal(str(item.subtotal_venta or "0"))
        estimate_amount = Decimal(str(values.get("this_estimate") or "0"))
        if estimate_amount > amount_budget and amount_budget > 0:
            estimate_amount = amount_budget
        current_progress = (estimate_amount / amount_budget * Decimal("100")) if amount_budget > 0 else Decimal("0")
        current_progress = min(Decimal("100"), max(Decimal("0"), current_progress))
        detail_values = build_estimation_detail_values(
            importe_presupuestado=amount_budget,
            avance_anterior_pct=Decimal("0"),
            avance_actual_pct=current_progress,
        )
        # Imported amounts are explicit; a rounded percentage must not change them.
        imported_amount = quantize_money(max(Decimal("0"), estimate_amount))
        detail_values.update(importe_periodo=imported_amount, importe_acumulado=imported_amount,
                             saldo_por_estimar=quantize_money(max(Decimal("0"), amount_budget - imported_amount)))
        detail = PMEstimacionDetalle(
            empresa_id=pm_context.empresa_id,
            estimacion_id=estimation.id,
            proyecto_id=project.id,
            presupuesto_partida_id=item.id,
            codigo_snapshot=item.codigo,
            concepto_snapshot=item.nombre,
            unidad_snapshot=item.unidad,
            cantidad_presupuestada=item.cantidad,
            precio_unitario_snapshot=item.precio_unitario,
            importe_presupuestado=amount_budget,
            notas=f"Importado de hoja {session.selected_sheet}, fila {values.get('source_row', '')}; valores fuente conservados en la revisión de importación.",
            activo=True,
            **detail_values,
        )
        db.add(detail)
    refresh_estimation_totals(db, estimation_id=estimation.id)
    item_by_source_row = {str(values.get("source_row")): item for item, values in imported_items}
    for evidence in db.scalars(select(PMEstimacionEvidencia).where(
        PMEstimacionEvidencia.empresa_id == pm_context.empresa_id,
        PMEstimacionEvidencia.import_session_id == session.id,
        PMEstimacionEvidencia.activo == True,
    )).all():
        evidence.estimacion_id = estimation.id
        if evidence.source_row is not None:
            linked_item = item_by_source_row.get(str(evidence.source_row))
            evidence.presupuesto_partida_id = linked_item.id if linked_item else None
    session.status = "imported"
    session.confirmed_at = utcnow()
    summary.update({
        "budget_id": budget.id,
        "budget_status": "borrador",
        "estimation_id": estimation.id,
        "estimation_folio": estimation.folio,
        "evidences_count": db.scalar(select(func.count(PMEstimacionEvidencia.id)).where(PMEstimacionEvidencia.import_session_id == session.id)) or 0,
        "warnings_accepted": bool(summary["warnings_count"] and warnings_acknowledged),
        "tasks_created": 0,
        "baseline_created": False,
        "budget_total": str(budget.total_venta),
    })
    session.summary_json = _json(summary)
    db.add(AuditLog(
        empresa_id=pm_context.empresa_id,
        usuario_id=pm_context.user.id,
        action="pm.excel_import.confirm",
        entity_name="pm_excel_import_session",
        entity_id=session.id,
        metadata_json={"project_id": project.id, "file_hash": session.file_hash, "sheet": session.selected_sheet, "budget_id": budget.id, "estimation_id": estimation.id, "chapters": summary["chapters_count"], "items": summary["items_count"], "warnings": summary["warnings_count"]},
    ))
    db.flush()
    return {"ok": True, "already_imported": False, **summary}


def cancel_import(db: Session, pm_context: PMContext, session_id: str) -> dict:
    ensure_pm_budget_manage_access(pm_context)
    session = _session_for_company(db, pm_context.empresa_id, session_id)
    if session.status == "imported":
        raise HTTPException(status_code=409, detail="La importación confirmada no se puede cancelar.")
    if session.status != "cancelled":
        session.original_file_reference = None
        session.status = "cancelled"
        session.cancelled_at = utcnow()
        db.execute(delete(PMExcelImportRow).where(
            PMExcelImportRow.empresa_id == pm_context.empresa_id,
            PMExcelImportRow.session_id == session.id,
        ))
        for evidence in db.scalars(select(PMEstimacionEvidencia).where(
            PMEstimacionEvidencia.empresa_id == pm_context.empresa_id,
            PMEstimacionEvidencia.import_session_id == session.id,
            PMEstimacionEvidencia.activo == True,
        )).all():
            evidence.activo = False
        db.add(AuditLog(empresa_id=pm_context.empresa_id, usuario_id=pm_context.user.id,
            action="pm.excel_import.cancel", entity_name="pm_excel_import_session", entity_id=session.id,
            metadata_json={"project_id": session.proyecto_id, "file_hash": session.file_hash, "staging_rows_removed": True}))
    return serialize_import_session(db, session)


def bulk_add_budget_items(db: Session, pm_context: PMContext, budget_id: str, items: list[dict], *, ip_address: str | None) -> dict:
    ensure_pm_budget_manage_access(pm_context)
    if not items or len(items) > 1000:
        raise HTTPException(status_code=400, detail="Agrega entre 1 y 1,000 partidas por operación.")
    budget = get_budget_for_company(db, pm_context.empresa_id, budget_id)
    ensure_budget_editable(budget)
    parent_ids = {str(item.get("parent_id")) for item in items if item.get("parent_id")}
    if parent_ids:
        valid_parents = set(db.scalars(select(PMPresupuestoPartida.id).where(
            PMPresupuestoPartida.id.in_(parent_ids),
            PMPresupuestoPartida.empresa_id == pm_context.empresa_id,
            PMPresupuestoPartida.presupuesto_id == budget.id,
            PMPresupuestoPartida.tipo == "capitulo",
            PMPresupuestoPartida.activo == True,
        )).all())
        if valid_parents != parent_ids:
            raise HTTPException(status_code=400, detail="Un capítulo seleccionado no pertenece al presupuesto.")
    max_order = db.scalar(select(func.coalesce(func.max(PMPresupuestoPartida.orden), -1)).where(
        PMPresupuestoPartida.empresa_id == pm_context.empresa_id,
        PMPresupuestoPartida.presupuesto_id == budget.id,
        PMPresupuestoPartida.activo == True,
    )) or 0
    for index, payload in enumerate(items):
        try:
            quantity = Decimal(str(payload.get("cantidad")))
            unit_price = Decimal(str(payload.get("precio_unitario_manual")))
        except (InvalidOperation, TypeError):
            raise HTTPException(status_code=400, detail="Revisa la cantidad y el precio unitario.")
        if quantity <= 0 or unit_price < 0:
            raise HTTPException(status_code=400, detail="La cantidad debe ser mayor a cero y el precio no puede ser negativo.")
        item = build_budget_item_record(
            empresa_id=pm_context.empresa_id,
            presupuesto_id=budget.id,
            proyecto_id=budget.proyecto_id,
            parent_id=payload.get("parent_id"),
            codigo=normalize_optional_text(payload.get("codigo")),
            nombre=normalize_required_text(str(payload.get("nombre") or ""), "Concepto"),
            descripcion=normalize_optional_text(payload.get("descripcion")),
            tipo="partida",
            unidad=normalize_optional_text(payload.get("unidad")),
            cantidad=quantity,
            margen_pct=Decimal("0"),
            precio_unitario_manual=unit_price,
            orden=int(payload.get("orden") if payload.get("orden") is not None else max_order + index + 1),
        )
        db.add(item)
    db.flush()
    refresh_project_budget_totals(db, empresa_id=pm_context.empresa_id, project_id=budget.proyecto_id)
    db.add(AuditLog(
        empresa_id=pm_context.empresa_id,
        usuario_id=pm_context.user.id,
        action="pm.budget_items.paste",
        entity_name="pm_presupuesto",
        entity_id=budget.id,
        ip_address=ip_address,
        metadata_json={"project_id": budget.proyecto_id, "rows_added": len(items)},
    ))
    return {"ok": True, "rows_added": len(items), "budget_id": budget.id}


def serialize_evidence(evidence: PMEstimacionEvidencia) -> dict:
    return {
        "id": evidence.id,
        "proyecto_id": evidence.proyecto_id,
        "estimacion_id": evidence.estimacion_id,
        "presupuesto_partida_id": evidence.presupuesto_partida_id,
        "import_session_id": evidence.import_session_id,
        "source_row": evidence.source_row,
        "url_archivo": evidence.url_archivo,
        "nombre_archivo": evidence.nombre_archivo,
        "mime_type": evidence.mime_type,
        "size_bytes": evidence.size_bytes,
        "descripcion": evidence.descripcion,
        "fecha_evidencia": evidence.fecha_evidencia.date().isoformat() if evidence.fecha_evidencia else None,
        "ubicacion": evidence.ubicacion,
        "created_at": evidence.created_at,
    }


def _evidence_calendar_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError("Not a calendar date")
        return datetime.combine(parsed, time.min)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Ingresa una fecha de evidencia válida.") from exc


def create_staged_evidence(db: Session, pm_context: PMContext, *, project_id: str, session_id: str, upload, source_row: int | None, description: str | None, location: str | None, evidence_date: str | None = None) -> dict:
    validate_staged_evidence_target(db, pm_context, project_id=project_id, session_id=session_id, source_row=source_row)
    evidence = PMEstimacionEvidencia(
        empresa_id=pm_context.empresa_id, proyecto_id=project_id, import_session_id=session_id,
        source_row=source_row, url_archivo=upload.archivo_url, blob_path=upload.blob_path,
        nombre_archivo=upload.filename, mime_type=upload.content_type, size_bytes=upload.size_bytes,
        descripcion=(description or "").strip() or None, ubicacion=(location or "").strip() or None,
        fecha_evidencia=_evidence_calendar_date(evidence_date),
        created_by=pm_context.user.id, activo=True,
    )
    db.add(evidence)
    db.flush()
    db.add(AuditLog(
        empresa_id=pm_context.empresa_id,
        usuario_id=pm_context.user.id,
        action="pm.excel_import.evidence_upload",
        entity_name="pm_estimacion_evidencia",
        entity_id=evidence.id,
        metadata_json={"project_id": project_id, "session_id": session_id, "source_row": source_row, "mime_type": evidence.mime_type, "size_bytes": evidence.size_bytes},
    ))
    return serialize_evidence(evidence)


def update_staged_evidence(db: Session, pm_context: PMContext, *, project_id: str, session_id: str, evidence_id: str, payload: dict) -> dict:
    ensure_pm_budget_manage_access(pm_context)
    session = _session_for_company(db, pm_context.empresa_id, session_id)
    if session.proyecto_id != project_id:
        raise HTTPException(status_code=404, detail="Importación no encontrada.")
    if session.status not in {"review", "ready"}:
        raise HTTPException(status_code=409, detail="Esta revisión ya no admite cambios.")
    evidence = db.scalar(select(PMEstimacionEvidencia).where(
        PMEstimacionEvidencia.id == evidence_id,
        PMEstimacionEvidencia.empresa_id == pm_context.empresa_id,
        PMEstimacionEvidencia.proyecto_id == project_id,
        PMEstimacionEvidencia.import_session_id == session_id,
        PMEstimacionEvidencia.activo == True,
    ))
    if not evidence:
        raise HTTPException(status_code=404, detail="Fotografía no encontrada.")

    source_row = payload.get("source_row", evidence.source_row)
    if source_row in ("", None):
        source_row = None
    else:
        try:
            source_row = int(source_row)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Selecciona una partida válida.") from exc
    validate_staged_evidence_target(db, pm_context, project_id=project_id, session_id=session_id, source_row=source_row)

    if "descripcion" in payload:
        description = (payload.get("descripcion") or "").strip()
        if len(description) > 500:
            raise HTTPException(status_code=400, detail="La descripción no puede superar 500 caracteres.")
        evidence.descripcion = description or None
    if "ubicacion" in payload:
        location = (payload.get("ubicacion") or "").strip()
        if len(location) > 255:
            raise HTTPException(status_code=400, detail="La ubicación no puede superar 255 caracteres.")
        evidence.ubicacion = location or None
    if "fecha_evidencia" in payload:
        evidence.fecha_evidencia = _evidence_calendar_date(payload.get("fecha_evidencia"))
    evidence.source_row = source_row
    db.flush()
    db.add(AuditLog(
        empresa_id=pm_context.empresa_id,
        usuario_id=pm_context.user.id,
        action="pm.excel_import.evidence_update",
        entity_name="pm_estimacion_evidencia",
        entity_id=evidence.id,
        metadata_json={"project_id": project_id, "session_id": session_id, "source_row": source_row},
    ))
    db.flush()
    return serialize_evidence(evidence)


def validate_staged_evidence_target(db: Session, pm_context: PMContext, *, project_id: str, session_id: str, source_row: int | None) -> None:
    ensure_pm_budget_manage_access(pm_context)
    session = _session_for_company(db, pm_context.empresa_id, session_id)
    if session.proyecto_id != project_id:
        raise HTTPException(status_code=404, detail="Importación no encontrada.")
    if session.status not in {"review", "ready"}:
        raise HTTPException(status_code=409, detail="Esta revisión ya no admite fotografías.")
    if source_row is not None and not db.scalar(select(PMExcelImportRow.id).where(
        PMExcelImportRow.session_id == session.id,
        PMExcelImportRow.empresa_id == pm_context.empresa_id,
        PMExcelImportRow.source_sheet == session.selected_sheet,
        PMExcelImportRow.source_row == source_row,
        PMExcelImportRow.row_type == "item",
    )):
        raise HTTPException(status_code=400, detail="La partida seleccionada no pertenece a esta revisión.")


def list_estimation_evidences(db: Session, pm_context: PMContext, estimation_id: str) -> list[dict]:
    from app.models.pm import PMEstimacion
    estimation = db.scalar(select(PMEstimacion).where(PMEstimacion.id == estimation_id, PMEstimacion.empresa_id == pm_context.empresa_id))
    if not estimation:
        raise HTTPException(status_code=404, detail="Estimación no encontrada.")
    return [serialize_evidence(evidence) for evidence in db.scalars(select(PMEstimacionEvidencia).where(
        PMEstimacionEvidencia.empresa_id == pm_context.empresa_id,
        PMEstimacionEvidencia.estimacion_id == estimation.id,
        PMEstimacionEvidencia.activo == True,
    ).order_by(PMEstimacionEvidencia.created_at.desc())).all()]


def create_estimation_evidence(db: Session, pm_context: PMContext, *, estimation_id: str, upload, description: str | None, location: str | None) -> dict:
    from app.models.pm import PMEstimacion
    estimation = db.scalar(select(PMEstimacion).where(PMEstimacion.id == estimation_id, PMEstimacion.empresa_id == pm_context.empresa_id))
    if not estimation:
        raise HTTPException(status_code=404, detail="Estimación no encontrada.")
    ensure_pm_budget_manage_access(pm_context)
    if estimation.estatus != "borrador":
        raise HTTPException(status_code=409, detail="Solo puedes agregar evidencias a una estimación en borrador.")
    evidence = PMEstimacionEvidencia(
        empresa_id=pm_context.empresa_id, proyecto_id=estimation.proyecto_id, estimacion_id=estimation.id,
        url_archivo=upload.archivo_url, blob_path=getattr(upload, "blob_path", None), nombre_archivo=upload.filename,
        mime_type=upload.content_type, size_bytes=upload.size_bytes,
        descripcion=(description or "").strip() or None, ubicacion=(location or "").strip() or None,
        created_by=pm_context.user.id, activo=True,
    )
    db.add(evidence)
    db.flush()
    return serialize_evidence(evidence)


def update_estimation_evidence(db: Session, pm_context: PMContext, evidence_id: str, payload: dict) -> dict:
    ensure_pm_budget_manage_access(pm_context)
    evidence = db.scalar(select(PMEstimacionEvidencia).where(PMEstimacionEvidencia.id == evidence_id, PMEstimacionEvidencia.empresa_id == pm_context.empresa_id, PMEstimacionEvidencia.activo == True))
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    if "descripcion" in payload:
        evidence.descripcion = (payload.get("descripcion") or "").strip() or None
    if "ubicacion" in payload:
        evidence.ubicacion = (payload.get("ubicacion") or "").strip() or None
    if "presupuesto_partida_id" in payload:
        part_id = payload.get("presupuesto_partida_id") or None
        if part_id:
            part = db.scalar(select(PMPresupuestoPartida).where(PMPresupuestoPartida.id == part_id, PMPresupuestoPartida.empresa_id == pm_context.empresa_id, PMPresupuestoPartida.proyecto_id == evidence.proyecto_id, PMPresupuestoPartida.tipo == "partida"))
            if not part:
                raise HTTPException(status_code=400, detail="La partida no pertenece a este trabajo.")
        evidence.presupuesto_partida_id = part_id
    db.flush()
    return serialize_evidence(evidence)


def deactivate_estimation_evidence(db: Session, pm_context: PMContext, evidence_id: str) -> dict:
    ensure_pm_budget_manage_access(pm_context)
    evidence = db.scalar(select(PMEstimacionEvidencia).where(PMEstimacionEvidencia.id == evidence_id, PMEstimacionEvidencia.empresa_id == pm_context.empresa_id, PMEstimacionEvidencia.activo == True))
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    evidence.activo = False
    db.add(AuditLog(
        empresa_id=pm_context.empresa_id,
        usuario_id=pm_context.user.id,
        action="pm.estimation.evidence_delete",
        entity_name="pm_estimacion_evidencia",
        entity_id=evidence.id,
        metadata_json={"project_id": evidence.proyecto_id, "estimation_id": evidence.estimacion_id, "import_session_id": evidence.import_session_id},
    ))
    db.flush()
    return {"ok": True}


def get_estimation_evidence_for_delete(db: Session, pm_context: PMContext, evidence_id: str) -> PMEstimacionEvidencia:
    ensure_pm_budget_manage_access(pm_context)
    evidence = db.scalar(select(PMEstimacionEvidencia).where(
        PMEstimacionEvidencia.id == evidence_id,
        PMEstimacionEvidencia.empresa_id == pm_context.empresa_id,
        PMEstimacionEvidencia.activo == True,
    ))
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    return evidence


def get_pm_evidence_for_download(db: Session, pm_context: PMContext, evidence_id: str) -> PMEstimacionEvidencia:
    evidence = db.scalar(select(PMEstimacionEvidencia).where(
        PMEstimacionEvidencia.id == evidence_id,
        PMEstimacionEvidencia.empresa_id == pm_context.empresa_id,
        PMEstimacionEvidencia.activo == True,
    ))
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")

    project = get_project_for_company(db, pm_context.empresa_id, evidence.proyecto_id)
    if not can_view_pm_project(pm_context):
        raise HTTPException(status_code=403, detail="No tienes acceso a este trabajo.")

    if evidence.estimacion_id and not db.scalar(select(PMEstimacion.id).where(
        PMEstimacion.id == evidence.estimacion_id,
        PMEstimacion.empresa_id == pm_context.empresa_id,
        PMEstimacion.proyecto_id == project.id,
    )):
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    if evidence.presupuesto_partida_id and not db.scalar(select(PMPresupuestoPartida.id).where(
        PMPresupuestoPartida.id == evidence.presupuesto_partida_id,
        PMPresupuestoPartida.empresa_id == pm_context.empresa_id,
        PMPresupuestoPartida.proyecto_id == project.id,
    )):
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    if evidence.import_session_id and not db.scalar(select(PMExcelImportSession.id).where(
        PMExcelImportSession.id == evidence.import_session_id,
        PMExcelImportSession.empresa_id == pm_context.empresa_id,
        PMExcelImportSession.proyecto_id == project.id,
    )):
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")

    blob_path = (evidence.blob_path or "").replace("\\", "/")
    path = PurePosixPath(blob_path)
    expected_prefix = f"{pm_context.empresa_id}/pm/projects/{project.id}/"
    if (
        not blob_path
        or "\\" in (evidence.blob_path or "")
        or path.is_absolute()
        or ".." in path.parts
        or not blob_path.startswith(expected_prefix)
    ):
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    return evidence
