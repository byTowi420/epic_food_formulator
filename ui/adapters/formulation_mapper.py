"""Formulation mapper - bridge between UI state and domain models.

Maps between:
- UI representation (dicts, lists for tables)
- Domain models (Formulation, Ingredient, Food)
"""

from decimal import Decimal
from typing import Any, Dict, List

from domain.models import Food, Formulation, Ingredient, Nutrient
from domain.services.unit_normalizer import canonical_unit


class FormulationMapper:
    """Maps between UI state and domain Formulation."""

    @staticmethod
    def ui_item_to_ingredient(ui_item: Dict[str, Any]) -> Ingredient:
        """Convert UI formulation item dict to domain Ingredient.

        Args:
            ui_item: Dict with keys: fdc_id, description, amount_g, locked, nutrients, etc.

        Returns:
            Domain Ingredient instance
        """
        # Extract nutrients
        nutrients_list = ui_item.get("nutrients", [])
        nutrients = tuple(
            Nutrient(
                name=n.get("nutrient", {}).get("name", ""),
                unit=n.get("nutrient", {}).get("unitName", ""),
                amount=Decimal(str(n.get("amount", 0))) if n.get("amount") is not None else Decimal("0"),
                nutrient_id=n.get("nutrient", {}).get("id"),
                nutrient_number=n.get("nutrient", {}).get("number"),
            )
            for n in nutrients_list
        )

        # Create Food
        # UI uses "brand" but domain uses "brand_owner", handle both
        brand = ui_item.get("brand_owner") or ui_item.get("brand", "")
        fdc_raw = ui_item.get("fdc_id")
        try:
            fdc_id = int(fdc_raw) if fdc_raw is not None and str(fdc_raw).strip() else 0
        except Exception:
            fdc_id = 0
        data_type = ui_item.get("data_type", "") or ""
        if fdc_id <= 0 and not data_type:
            data_type = "Manual"
        food = Food(
            fdc_id=fdc_id,
            description=ui_item.get("description", ""),
            data_type=data_type,
            brand_owner=brand,
            nutrients=nutrients,
        )

        # Create Ingredient
        amount_g = ui_item.get("amount_g", 0)
        if isinstance(amount_g, str):
            amount_g = Decimal(amount_g) if amount_g else Decimal("0")
        elif amount_g is None:
            amount_g = Decimal("0")
        else:
            amount_g = Decimal(str(amount_g))

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

        return Ingredient(
            food=food,
            amount_g=amount_g,
            locked=bool(ui_item.get("locked", False)),
            cost_pack_amount=_to_decimal(ui_item.get("cost_pack_amount")),
            cost_pack_unit=ui_item.get("cost_pack_unit"),
            cost_value=_to_decimal(ui_item.get("cost_value")),
            cost_currency_symbol=ui_item.get("cost_currency_symbol"),
            cost_per_g_mn=_to_decimal(ui_item.get("cost_per_g_mn")),
        )

    @staticmethod
    def ui_items_to_formulation(
        ui_items: List[Dict[str, Any]],
        name: str = "Current Formulation",
        quantity_mode: str = "g",
    ) -> Formulation:
        """Convert list of UI items to domain Formulation.

        Args:
            ui_items: List of UI formulation item dicts
            name: Formulation name
            quantity_mode: "g" or "%"

        Returns:
            Domain Formulation instance
        """
        formulation = Formulation(name=name, quantity_mode=quantity_mode)

        for ui_item in ui_items:
            ingredient = FormulationMapper.ui_item_to_ingredient(ui_item)
            formulation.add_ingredient(ingredient)

        return formulation

    @staticmethod
    def ingredient_to_ui_item(ingredient: Ingredient, index: int = 0) -> Dict[str, Any]:
        """Convert domain Ingredient to UI item dict.

        Args:
            ingredient: Domain Ingredient
            index: Row index (for UI purposes)

        Returns:
            Dict compatible with UI tables
        """
        # Convert nutrients back to UI format
        nutrients = [
            {
                "nutrient": {
                    "name": n.name,
                    "unitName": n.unit,
                    "id": n.nutrient_id,
                    "number": n.nutrient_number,
                },
                "amount": float(n.amount),
            }
            for n in ingredient.food.nutrients
        ]

        return {
            "index": index,
            "fdc_id": ingredient.food.fdc_id,
            "description": ingredient.food.description,
            "data_type": ingredient.food.data_type,
            "brand": ingredient.food.brand_owner,  # UI expects "brand", not "brand_owner"
            "brand_owner": ingredient.food.brand_owner,  # Keep both for compatibility
            "amount_g": float(ingredient.amount_g),
            "locked": ingredient.locked,
            "nutrients": nutrients,
            "cost_pack_amount": float(ingredient.cost_pack_amount)
            if ingredient.cost_pack_amount is not None
            else None,
            "cost_pack_unit": ingredient.cost_pack_unit,
            "cost_value": float(ingredient.cost_value)
            if ingredient.cost_value is not None
            else None,
            "cost_currency_symbol": ingredient.cost_currency_symbol,
            "cost_per_g_mn": float(ingredient.cost_per_g_mn)
            if ingredient.cost_per_g_mn is not None
            else None,
        }

    @staticmethod
    def formulation_to_ui_items(formulation: Formulation) -> List[Dict[str, Any]]:
        """Convert domain Formulation to list of UI items.

        Args:
            formulation: Domain Formulation

        Returns:
            List of UI item dicts
        """
        return [
            FormulationMapper.ingredient_to_ui_item(ing, idx)
            for idx, ing in enumerate(formulation.ingredients)
        ]


class NutrientDisplayMapper:
    """Maps nutrient calculation results to UI display format."""

    @staticmethod
    def totals_to_display_dict(
        totals: Dict[str, Decimal],
        formulation: Formulation | None = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Convert nutrient totals to UI display format.

        Args:
            totals: Dict of nutrient name -> amount (Decimal)
            formulation: Optional formulation to extract units from

        Returns:
            Dict compatible with UI nutrient tables
        """
        # Build map of nutrient name -> unit from formulation.
        nutrient_units: Dict[str, str] = {}
        energy_by_unit: Dict[str, Decimal] = {}
        total_weight = None

        if formulation:
            total_weight = formulation.total_weight
            for ingredient in formulation.ingredients:
                for nutrient in ingredient.food.nutrients:
                    if nutrient.name not in nutrient_units:
                        nutrient_units[nutrient.name] = nutrient.unit

                    if nutrient.name.strip().lower() == "energy":
                        unit = canonical_unit(nutrient.unit or "")
                        if not unit:
                            continue
                        scaled_amount = nutrient.amount * (ingredient.amount_g / Decimal("100"))
                        energy_by_unit[unit] = energy_by_unit.get(unit, Decimal("0")) + scaled_amount

        if energy_by_unit and total_weight:
            normalization_factor = Decimal("100") / total_weight
            for unit in list(energy_by_unit.keys()):
                energy_by_unit[unit] = energy_by_unit[unit] * normalization_factor
        else:
            energy_by_unit = {}

        result: Dict[str, Dict[str, Any]] = {}
        for name, amount in totals.items():
            if name.strip().lower() == "energy" and energy_by_unit:
                continue
            result[name] = {
                "name": name,
                "amount": float(amount),
                "unit": nutrient_units.get(name, ""),
            }

        if energy_by_unit:
            ordered_units: list[str] = []
            for unit in ("kcal", "kJ"):
                if unit in energy_by_unit:
                    ordered_units.append(unit)
            for unit in sorted(u for u in energy_by_unit if u not in ordered_units):
                ordered_units.append(unit)

            for unit in ordered_units:
                key = f"Energy|{unit.lower()}"
                result[key] = {
                    "name": "Energy",
                    "amount": float(energy_by_unit[unit]),
                    "unit": unit,
                }

        return result
