from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd

from domain.exceptions import FormulationImportError
from domain.services.nutrient_ordering import NutrientOrdering
from domain.services.unit_normalizer import convert_mass, normalize_mass_unit


class FormulationImportService:
    """Parse formulation files into base items + metadata."""

    def __init__(self, nutrient_ordering: NutrientOrdering | None = None) -> None:
        self._nutrient_ordering = nutrient_ordering or NutrientOrdering()

    def normalize_export_flags(
        self, raw_flags: Dict[str, Any] | None
    ) -> tuple[Dict[str, bool], Dict[str, bool]]:
        """Split export flags into header-key and legacy formats."""
        normalized: Dict[str, bool] = {}
        legacy: Dict[str, bool] = {}
        if not isinstance(raw_flags, dict):
            return normalized, legacy

        for key, value in raw_flags.items():
            if key is None:
                continue
            key_text = str(key).strip()
            if not key_text:
                continue
            enabled = value
            if isinstance(enabled, str):
                lowered = enabled.strip().lower()
                if lowered in {"true", "1", "yes", "si"}:
                    enabled = True
                elif lowered in {"false", "0", "no"}:
                    enabled = False
            enabled = bool(enabled)
            lower = key_text.lower()

            if "|" in lower:
                name_part, unit_part = lower.split("|", 1)
                if name_part:
                    normalized[f"{name_part.strip()}|{unit_part.strip()}"] = enabled
                continue

            if lower.endswith(")") and " (" in lower:
                name_part, unit_part = lower.rsplit(" (", 1)
                unit_part = unit_part[:-1]
                if name_part:
                    normalized[f"{name_part.strip()}|{unit_part.strip()}"] = enabled
                continue

            if lower.startswith("energy:"):
                unit_part = lower.split(":", 1)[1].strip()
                if unit_part:
                    normalized[f"energy|{unit_part}"] = enabled
                continue

            legacy[lower] = enabled

        return normalized, legacy

    def resolve_legacy_export_flags(
        self,
        legacy_flags: Dict[str, bool],
        hydrated_items: list[Dict[str, Any]],
    ) -> Dict[str, bool]:
        """Map old-style flag keys (id/num/name) to header keys."""
        if not legacy_flags:
            return {}

        legacy_to_header: Dict[str, str] = {}
        name_to_headers: Dict[str, set[str]] = {}

        for item in hydrated_items:
            for entry in item.get("nutrients", []) or []:
                nut = entry.get("nutrient") or {}
                header_key, _, _ = self._nutrient_ordering.header_key(nut)
                if not header_key:
                    continue
                legacy_key = self._nutrient_ordering.nutrient_key(nut)
                if legacy_key:
                    legacy_to_header.setdefault(legacy_key.lower(), header_key)
                name_part = header_key.split("|", 1)[0]
                name_to_headers.setdefault(name_part, set()).add(header_key)

        resolved: Dict[str, bool] = {}
        for key, value in legacy_flags.items():
            norm = str(key).strip().lower()
            if not norm:
                continue

            if norm.startswith("energy:"):
                unit = norm.split(":", 1)[1].strip()
                if unit:
                    resolved[f"energy|{unit}"] = bool(value)
                continue

            if norm.startswith("name:"):
                name = norm.split(":", 1)[1].strip()
                for header_key in name_to_headers.get(name, set()):
                    resolved[header_key] = bool(value)
                continue

            header_key = legacy_to_header.get(norm)
            if header_key:
                resolved[header_key] = bool(value)
                continue

            for header_key in name_to_headers.get(norm, set()):
                resolved[header_key] = bool(value)

        return resolved

    def load_state_from_json(self, path: str) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise FormulationImportError(
                "Error al importar",
                f"No se pudo leer el archivo:\n{exc}",
                severity="critical",
            ) from exc

        items = data.get("items")
        if not items:
            items = data.get("ingredients")

        if not isinstance(items, list) or not items:
            raise FormulationImportError(
                "Formato invalido",
                "El archivo no contiene ingredientes validos.",
            )

        base_items: list[Dict[str, Any]] = []
        raw_rates = data.get("currency_rates") or []
        currency_rates: list[Dict[str, Any]] = []
        if isinstance(raw_rates, list):
            for entry in raw_rates:
                if not isinstance(entry, dict):
                    continue
                symbol = str(entry.get("symbol", "") or "").strip()
                name = str(entry.get("name", "") or "").strip()
                rate = entry.get("rate_to_mn")
                if not symbol or rate is None:
                    continue
                currency_rates.append(
                    {"name": name or symbol, "symbol": symbol, "rate_to_mn": rate}
                )
        has_base = any(rate.get("symbol") == "$" for rate in currency_rates)
        if not has_base:
            currency_rates.insert(
                0, {"name": "Moneda Nacional", "symbol": "$", "rate_to_mn": 1}
            )
        warnings: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue

            data_type_raw = item.get("data_type") or item.get("dataType") or ""
            source_raw = item.get("source") or ""
            is_manual = str(data_type_raw).strip().lower() == "manual" or str(source_raw).strip().lower() == "manual"

            if is_manual:
                amount_raw = item.get("amount_g")
                if amount_raw is None:
                    amount_raw = item.get("amountG")
                if amount_raw is None:
                    amount_raw = item.get("amount")
                try:
                    amount_g = float(amount_raw) if amount_raw is not None else 0.0
                except Exception:
                    warnings.append("Cantidad invalida para ingrediente manual. Se usa 0.")
                    amount_g = 0.0
                if amount_g < 0:
                    warnings.append(
                        f"Ingrediente manual omitido: cantidad negativa ({amount_g})."
                    )
                    continue

                raw_nutrients = item.get("nutrients") or []
                manual_nutrients: list[Dict[str, Any]] = []
                for entry in raw_nutrients:
                    if not isinstance(entry, dict):
                        continue
                    if "nutrient" in entry:
                        nut = entry.get("nutrient") or {}
                        name = nut.get("name") or ""
                        unit = nut.get("unitName") or nut.get("unit") or ""
                        amount = entry.get("amount")
                        nutrient_id = nut.get("id")
                        nutrient_number = nut.get("number")
                    else:
                        name = entry.get("name") or ""
                        unit = entry.get("unit") or ""
                        amount = entry.get("amount")
                        nutrient_id = entry.get("nutrient_id")
                        nutrient_number = entry.get("nutrient_number")
                    if not name or not unit:
                        continue
                    try:
                        amount_val = float(amount) if amount is not None else 0.0
                    except Exception:
                        amount_val = 0.0
                    manual_nutrients.append(
                        {
                            "nutrient": {
                                "name": name,
                                "unitName": unit,
                                "id": nutrient_id,
                                "number": nutrient_number,
                            },
                            "amount": amount_val,
                        }
                    )

                if not manual_nutrients:
                    warnings.append(
                        "Ingrediente manual sin nutrientes. Se importo sin datos nutricionales."
                    )

                legacy_symbol = item.get("cost_currency_symbol")
                legacy_type = item.get("cost_currency_type")
                legacy_rate = item.get("cost_me_rate_to_mn")
                if legacy_symbol and legacy_rate is not None:
                    if not any(rate.get("symbol") == legacy_symbol for rate in currency_rates):
                        currency_rates.append(
                            {
                                "name": str(legacy_symbol),
                                "symbol": str(legacy_symbol),
                                "rate_to_mn": legacy_rate,
                            }
                        )
                elif legacy_type and str(legacy_type).strip().upper() == "MN":
                    legacy_symbol = "$"
                base_items.append(
                    {
                        "fdc_id": 0,
                        "amount_g": amount_g,
                        "locked": bool(item.get("locked", False)),
                        "description": item.get("description") or item.get("name") or "Manual",
                        "brand": item.get("brand")
                        or item.get("brand_owner")
                        or item.get("brandOwner")
                        or "",
                        "data_type": "Manual",
                        "cost_pack_amount": item.get("cost_pack_amount"),
                        "cost_pack_unit": item.get("cost_pack_unit"),
                        "cost_value": item.get("cost_value"),
                        "cost_currency_symbol": legacy_symbol or item.get("cost_currency_symbol"),
                        "cost_per_g_mn": item.get("cost_per_g_mn"),
                        "manual": True,
                        "nutrients": manual_nutrients,
                    }
                )
                continue

            fdc_raw = item.get("fdc_id") or item.get("fdcId") or item.get("fdcID")
            if fdc_raw is None:
                warnings.append("Ingrediente omitido: no tiene FDC ID.")
                continue

            try:
                fdc_int = int(fdc_raw)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Ingrediente omitido: FDC ID no numerico ({fdc_raw}).")
                continue

            amount_raw = item.get("amount_g")
            if amount_raw is None:
                amount_raw = item.get("amountG")
            if amount_raw is None:
                amount_raw = item.get("amount")
            try:
                amount_g = float(amount_raw) if amount_raw is not None else 0.0
            except Exception:
                warnings.append(f"Cantidad invalida para FDC {fdc_int}. Se usa 0.")
                amount_g = 0.0
            if amount_g < 0:
                warnings.append(
                    f"Ingrediente omitido: FDC {fdc_int} con cantidad negativa ({amount_g})."
                )
                continue

            legacy_symbol = item.get("cost_currency_symbol")
            legacy_type = item.get("cost_currency_type")
            legacy_rate = item.get("cost_me_rate_to_mn")
            if legacy_symbol and legacy_rate is not None:
                if not any(rate.get("symbol") == legacy_symbol for rate in currency_rates):
                    currency_rates.append(
                        {
                            "name": str(legacy_symbol),
                            "symbol": str(legacy_symbol),
                            "rate_to_mn": legacy_rate,
                        }
                    )
            elif legacy_type and str(legacy_type).strip().upper() == "MN":
                legacy_symbol = "$"
            base_items.append(
                {
                    "fdc_id": fdc_int,
                    "amount_g": amount_g,
                    "locked": bool(item.get("locked", False)),
                    "description": item.get("description") or item.get("name") or "",
                    "brand": item.get("brand")
                    or item.get("brand_owner")
                    or item.get("brandOwner")
                    or "",
                    "data_type": item.get("data_type") or item.get("dataType") or "",
                    "cost_pack_amount": item.get("cost_pack_amount"),
                    "cost_pack_unit": item.get("cost_pack_unit"),
                    "cost_value": item.get("cost_value"),
                    "cost_currency_symbol": legacy_symbol or item.get("cost_currency_symbol"),
                    "cost_per_g_mn": item.get("cost_per_g_mn"),
                }
            )

        if not base_items:
            raise FormulationImportError(
                "Formato invalido",
                "El archivo no contiene ingredientes validos.",
            )

        raw_flags = data.get("nutrient_export_flags")
        nutrient_flags, legacy_flags = self.normalize_export_flags(raw_flags)

        mode_raw = str(data.get("quantity_mode", "g") or "g").strip().lower()
        if mode_raw in ("%", "percent", "percentage"):
            quantity_mode = "%"
        else:
            quantity_mode = normalize_mass_unit(mode_raw) or "g"

        formula_name = data.get("formula_name") or data.get("name") or Path(path).stem
        label_settings = (
            data.get("label_settings")
            or data.get("label")
            or data.get("label_state")
            or {}
        )
        if not isinstance(label_settings, dict):
            label_settings = {}

        meta = {
            "nutrient_export_flags": nutrient_flags,
            "legacy_nutrient_export_flags": legacy_flags,
            "quantity_mode": quantity_mode,
            "formula_name": formula_name,
            "label_settings": label_settings,
            "yield_percent": data.get("yield_percent"),
            "cost_target_mass_value": data.get("cost_target_mass_value"),
            "cost_target_mass_unit": data.get("cost_target_mass_unit"),
            "process_costs": data.get("process_costs") or [],
            "packaging_items": data.get("packaging_items") or [],
            "currency_rates": currency_rates,
            "path": path,
            "respect_existing_formula_name": False,
            "warnings": warnings,
        }
        return base_items, meta

    def load_state_from_excel(
        self,
        path: str,
        *,
        default_formula_name: str,
    ) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
        def _read(sheet: str | int, header_row: int) -> pd.DataFrame:
            return pd.read_excel(path, sheet_name=sheet, header=header_row)

        df: pd.DataFrame | None = None
        for sheet in ("Ingredientes", 0):
            for header_row in (1, 0):
                try:
                    tmp = _read(sheet, header_row)
                    if not tmp.empty:
                        df = tmp
                        break
                except Exception:
                    continue
            if df is not None:
                break

        if df is None or df.empty:
            raise FormulationImportError(
                "Sin datos",
                "El archivo no tiene filas para importar.",
            )

        cols_norm: Dict[str, str] = {
            self.normalize_label(c): c for c in df.columns
        }
        fdc_candidates = [
            "fdc id",
            "fdc_id",
            "fdcid",
            "fdc",
        ]
        amount_candidates_by_unit = {
            "g": [
                "cantidad (g)",
                "cantidad g",
                "cantidad",
                "cantidad gramos",
                "cantidad en gramos",
                "amount g",
                "amount_g",
                "g",
                "grams",
            ],
            "kg": [
                "cantidad (kg)",
                "cantidad kg",
                "cantidad kilogramos",
                "cantidad en kilogramos",
                "amount kg",
                "amount_kg",
                "kg",
                "kilograms",
            ],
            "ton": [
                "cantidad (ton)",
                "cantidad ton",
                "cantidad toneladas",
                "cantidad en toneladas",
                "amount ton",
                "amount_ton",
                "ton",
                "toneladas",
            ],
            "lb": [
                "cantidad (lb)",
                "cantidad lb",
                "cantidad libras",
                "cantidad en libras",
                "amount lb",
                "amount_lb",
                "lb",
                "lbs",
                "pounds",
            ],
            "oz": [
                "cantidad (oz)",
                "cantidad oz",
                "cantidad onzas",
                "cantidad en onzas",
                "amount oz",
                "amount_oz",
                "oz",
                "ounces",
            ],
        }

        fdc_col = next((cols_norm[c] for c in fdc_candidates if c in cols_norm), None)
        amount_col = None
        amount_unit = "g"
        for unit, candidates in amount_candidates_by_unit.items():
            for candidate in candidates:
                if candidate in cols_norm:
                    amount_col = cols_norm[candidate]
                    amount_unit = unit
                    break
            if amount_col:
                break
        if not amount_col:
            for norm_label, original in cols_norm.items():
                if not (norm_label.startswith("cantidad") or norm_label.startswith("amount")):
                    continue
                match = re.search(r"\(([^)]+)\)", norm_label)
                if not match:
                    continue
                parsed_unit = normalize_mass_unit(match.group(1))
                if parsed_unit:
                    amount_col = original
                    amount_unit = parsed_unit
                    break

        if not fdc_col or not amount_col:
            raise FormulationImportError(
                "Columnas faltantes",
                "Se requieren columnas FDC ID y Cantidad (g/kg/ton/lb/oz).",
            )

        base_items: list[Dict[str, Any]] = []
        warnings: list[str] = []
        for _, row in df.iterrows():
            fdc_val = row.get(fdc_col)
            amt_val = row.get(amount_col)
            if pd.isna(fdc_val):
                continue
            try:
                fdc_int = int(fdc_val)
            except Exception:
                continue
            try:
                amt = float(amt_val) if not pd.isna(amt_val) else 0.0
            except Exception:
                amt = 0.0
            amt_g = convert_mass(amt, amount_unit, "g")
            if amt_g is None:
                amt_g = amt
            if float(amt_g) < 0:
                warnings.append(
                    f"Ingrediente omitido: FDC {fdc_int} con cantidad negativa ({amt_g})."
                )
                continue

            base_items.append(
                {
                    "fdc_id": fdc_int,
                    "amount_g": float(amt_g),
                    "locked": False,
                }
            )

        if not base_items:
            raise FormulationImportError(
                "Sin ingredientes",
                "No se encontraron filas validas con FDC ID y Cantidad.",
            )

        formula_name = default_formula_name or Path(path).stem
        meta = {
            "nutrient_export_flags": {},
            "quantity_mode": amount_unit,
            "formula_name": formula_name,
            "path": path,
            "respect_existing_formula_name": True,
            "warnings": warnings,
        }
        return base_items, meta

    def normalize_label(self, label: str) -> str:
        """Normalize column labels for loose matching (casefold + strip accents)."""
        if label is None:
            return ""
        text = str(label)
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.replace("_", " ").replace("-", " ")
        return re.sub(r"\s+", " ", text).strip().lower()
