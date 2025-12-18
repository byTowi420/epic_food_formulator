"""Formulation mapper - bridge between UI state and domain models.

Maps between:
- UI representation (dicts, lists for tables)
- Domain models (Formulation, Ingredient, Food)
"""

from decimal import Decimal
from typing import Any, Dict, List

from domain.models import Food, Formulation, Ingredient, Nutrient


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
        food = Food(
            fdc_id=int(ui_item.get("fdc_id", 0)),
            description=ui_item.get("description", ""),
            data_type=ui_item.get("data_type", ""),
            brand_owner=ui_item.get("brand_owner", ""),
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

        return Ingredient(
            food=food,
            amount_g=amount_g,
            locked=bool(ui_item.get("locked", False)),
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
            "brand_owner": ingredient.food.brand_owner,
            "amount_g": float(ingredient.amount_g),
            "locked": ingredient.locked,
            "nutrients": nutrients,
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
    ) -> Dict[str, Dict[str, Any]]:
        """Convert nutrient totals to UI display format.

        Args:
            totals: Dict of nutrient name -> amount (Decimal)

        Returns:
            Dict compatible with UI nutrient tables
        """
        result = {}

        for name, amount in totals.items():
            result[name] = {
                "name": name,
                "amount": float(amount),
                "unit": "",  # Will be filled by normalizer or UI
            }

        return result
