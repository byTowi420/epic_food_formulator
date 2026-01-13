"""JSON persistence for formulations.

Handles saving and loading formulations to/from JSON files.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

from domain.exceptions import FormulationNotFoundError, InvalidFormulationFileError
from domain.models import CurrencyRate, Food, Formulation, Ingredient, Nutrient, PackagingItem, ProcessCost


class JSONFormulationRepository:
    """Repository for persisting formulations as JSON files."""

    def __init__(self, base_directory: str = "saves") -> None:
        """Initialize repository.

        Args:
            base_directory: Base directory for saving formulations
        """
        self._base_dir = Path(base_directory)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, formulation: Formulation, filename: str) -> Path:
        """Save formulation to JSON file.

        Args:
            formulation: Formulation to save
            filename: Filename (without path)

        Returns:
            Full path to saved file
        """
        file_path = self._base_dir / filename

        # Convert formulation to dict
        data = self._formulation_to_dict(formulation)

        # Write JSON
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return file_path

    def load(self, filename: str) -> Formulation:
        """Load formulation from JSON file.

        Args:
            filename: Filename (without path)

        Returns:
            Loaded formulation

        Raises:
            FormulationNotFoundError: If file doesn't exist
            InvalidFormulationFileError: If file is malformed
        """
        file_path = self._base_dir / filename

        if not file_path.exists():
            raise FormulationNotFoundError(f"Formulation file not found: {filename}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return self._dict_to_formulation(data)

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            raise InvalidFormulationFileError(
                f"Invalid formulation file: {filename}"
            ) from exc

    def list_files(self) -> List[str]:
        """List all formulation JSON files.

        Returns:
            List of filenames
        """
        if not self._base_dir.exists():
            return []

        return sorted([f.name for f in self._base_dir.glob("*.json")])

    def delete(self, filename: str) -> None:
        """Delete a formulation file.

        Args:
            filename: Filename to delete

        Raises:
            FormulationNotFoundError: If file doesn't exist
        """
        file_path = self._base_dir / filename

        if not file_path.exists():
            raise FormulationNotFoundError(f"Formulation file not found: {filename}")

        file_path.unlink()

    def _formulation_to_dict(self, formulation: Formulation) -> Dict[str, Any]:
        """Convert Formulation to dictionary."""
        def _as_str(value: Decimal | None) -> str | None:
            if value is None:
                return None
            return str(value)

        return {
            "name": formulation.name,
            "quantity_mode": formulation.quantity_mode,
            "yield_percent": _as_str(formulation.yield_percent),
            "cost_target_mass_value": _as_str(formulation.cost_target_mass_value),
            "cost_target_mass_unit": formulation.cost_target_mass_unit,
            "currency_rates": [
                {
                    "name": rate.name,
                    "symbol": rate.symbol,
                    "rate_to_mn": _as_str(rate.rate_to_mn),
                }
                for rate in formulation.currency_rates
            ],
            "process_costs": [
                {
                    "name": process.name,
                    "scale_type": process.scale_type,
                    "time_value": _as_str(process.time_value),
                    "time_unit": process.time_unit,
                    "cost_per_hour_mn": _as_str(process.cost_per_hour_mn),
                    "total_cost_mn": _as_str(process.total_cost_mn),
                    "setup_time_value": _as_str(process.setup_time_value),
                    "setup_time_unit": process.setup_time_unit,
                    "time_per_kg_value": _as_str(process.time_per_kg_value),
                    "notes": process.notes,
                }
                for process in formulation.process_costs
            ],
            "packaging_items": [
                {
                    "name": item.name,
                    "quantity_per_pack": _as_str(item.quantity_per_pack),
                    "unit_cost_mn": _as_str(item.unit_cost_mn),
                    "unit_cost_value": _as_str(item.unit_cost_value),
                    "unit_cost_currency_symbol": item.unit_cost_currency_symbol,
                    "notes": item.notes,
                }
                for item in formulation.packaging_items
            ],
            "ingredients": [
                {
                    "fdc_id": ing.food.fdc_id,
                    "description": ing.food.description,
                    "data_type": ing.food.data_type,
                    "brand_owner": ing.food.brand_owner,
                    "amount_g": str(ing.amount_g),
                    "locked": ing.locked,
                    "cost_pack_amount": _as_str(ing.cost_pack_amount),
                    "cost_pack_unit": ing.cost_pack_unit,
                    "cost_value": _as_str(ing.cost_value),
                    "cost_currency_symbol": ing.cost_currency_symbol,
                    "cost_per_g_mn": _as_str(ing.cost_per_g_mn),
                    "nutrients": [
                        {
                            "name": nut.name,
                            "unit": nut.unit,
                            "amount": str(nut.amount),
                            "nutrient_id": nut.nutrient_id,
                            "nutrient_number": nut.nutrient_number,
                        }
                        for nut in ing.food.nutrients
                    ],
                }
                for ing in formulation.ingredients
            ],
        }

    def _dict_to_formulation(self, data: Dict[str, Any]) -> Formulation:
        """Convert dictionary to Formulation."""
        def _to_decimal(value: Any) -> Decimal | None:
            if value is None:
                return None
            if isinstance(value, Decimal):
                return value
            if isinstance(value, str):
                cleaned = value.strip().replace(",", ".")
                if cleaned == "":
                    return None
                return Decimal(cleaned)
            return Decimal(str(value))

        yield_raw = _to_decimal(data.get("yield_percent"))
        if yield_raw is None or yield_raw <= 0 or yield_raw > 100:
            yield_raw = Decimal("100")

        formulation = Formulation(
            name=data["name"],
            quantity_mode=data.get("quantity_mode", "g"),
            yield_percent=yield_raw,
        )

        target_value = _to_decimal(data.get("cost_target_mass_value"))
        if target_value is not None and target_value > 0:
            formulation.cost_target_mass_value = target_value
        target_unit = str(data.get("cost_target_mass_unit") or "").strip()
        if target_unit in {"g", "kg", "lb", "oz", "ton"}:
            formulation.cost_target_mass_unit = target_unit

        rates: list[CurrencyRate] = []
        for entry in data.get("currency_rates", []) or []:
            if not isinstance(entry, dict):
                continue
            symbol = str(entry.get("symbol", "") or "").strip()
            name = str(entry.get("name", "") or "").strip()
            rate_val = _to_decimal(entry.get("rate_to_mn"))
            if not symbol or rate_val is None:
                continue
            rates.append(
                CurrencyRate(
                    name=name or symbol,
                    symbol=symbol,
                    rate_to_mn=rate_val,
                )
            )
        if rates:
            formulation.currency_rates = rates
            formulation._ensure_currency_rates()

        for process_data in data.get("process_costs", []) or []:
            if not isinstance(process_data, dict):
                continue
            formulation.process_costs.append(
                ProcessCost(
                    name=process_data.get("name", "") or "",
                    scale_type=process_data.get("scale_type", "") or "",
                    time_value=_to_decimal(process_data.get("time_value")),
                    time_unit=process_data.get("time_unit"),
                    cost_per_hour_mn=_to_decimal(process_data.get("cost_per_hour_mn")),
                    total_cost_mn=_to_decimal(process_data.get("total_cost_mn")),
                    setup_time_value=_to_decimal(process_data.get("setup_time_value")),
                    setup_time_unit=process_data.get("setup_time_unit"),
                    time_per_kg_value=_to_decimal(process_data.get("time_per_kg_value")),
                    notes=process_data.get("notes"),
                )
            )

        for item_data in data.get("packaging_items", []) or []:
            if not isinstance(item_data, dict):
                continue
            quantity = _to_decimal(item_data.get("quantity_per_pack")) or Decimal("0")
            unit_cost_mn = _to_decimal(item_data.get("unit_cost_mn"))
            unit_cost_value = _to_decimal(item_data.get("unit_cost_value"))
            unit_cost_symbol = str(
                item_data.get("unit_cost_currency_symbol") or ""
            ).strip() or "$"
            if unit_cost_value is None:
                unit_cost_value = unit_cost_mn
            if unit_cost_mn is None:
                unit_cost_mn = unit_cost_value or Decimal("0")
            formulation.packaging_items.append(
                PackagingItem(
                    name=item_data.get("name", "") or "",
                    quantity_per_pack=quantity,
                    unit_cost_mn=unit_cost_mn,
                    unit_cost_value=unit_cost_value,
                    unit_cost_currency_symbol=unit_cost_symbol,
                    notes=item_data.get("notes"),
                )
            )

        for ing_data in data.get("ingredients", []):
            nutrients = tuple(
                Nutrient(
                    name=n["name"],
                    unit=n["unit"],
                    amount=Decimal(str(n["amount"])),
                    nutrient_id=n.get("nutrient_id"),
                    nutrient_number=n.get("nutrient_number"),
                )
                for n in ing_data.get("nutrients", [])
            )

            fdc_id = ing_data.get("fdc_id", 0)
            data_type = ing_data.get("data_type", "") or ""
            if not data_type:
                try:
                    if int(fdc_id) <= 0:
                        data_type = "Manual"
                except Exception:
                    data_type = "Manual"
            food = Food(
                fdc_id=fdc_id,
                description=ing_data["description"],
                data_type=data_type,
                brand_owner=ing_data.get("brand_owner", ""),
                nutrients=nutrients,
            )

            legacy_symbol = ing_data.get("cost_currency_symbol")
            legacy_type = ing_data.get("cost_currency_type")
            legacy_rate = ing_data.get("cost_me_rate_to_mn")
            if legacy_symbol and legacy_rate is not None:
                if not any(rate.symbol == legacy_symbol for rate in formulation.currency_rates):
                    formulation.currency_rates.append(
                        CurrencyRate(
                            name=str(legacy_symbol),
                            symbol=str(legacy_symbol),
                            rate_to_mn=_to_decimal(legacy_rate) or Decimal("1"),
                        )
                    )
                    formulation._ensure_currency_rates()
            elif legacy_type and str(legacy_type).strip().upper() == "MN":
                legacy_symbol = "$"

            ingredient = Ingredient(
                food=food,
                amount_g=Decimal(str(ing_data["amount_g"])),
                locked=ing_data.get("locked", False),
                cost_pack_amount=_to_decimal(ing_data.get("cost_pack_amount")),
                cost_pack_unit=ing_data.get("cost_pack_unit"),
                cost_value=_to_decimal(ing_data.get("cost_value")),
                cost_currency_symbol=legacy_symbol or ing_data.get("cost_currency_symbol"),
                cost_per_g_mn=_to_decimal(ing_data.get("cost_per_g_mn")),
            )

            formulation.add_ingredient(ingredient)

        return formulation
