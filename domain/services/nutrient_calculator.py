"""Nutrient calculation service.

Handles all nutrient-related calculations for formulations.
Pure business logic with no UI dependencies.
"""

from decimal import Decimal
from typing import Dict

from config.constants import ATWATER_CARBOHYDRATE, ATWATER_FAT, ATWATER_PROTEIN, KCAL_TO_KJ
from domain.models import Formulation, Ingredient


class NutrientCalculator:
    """Calculate nutrient totals and derived values for formulations."""

    def calculate_totals_per_100g(
        self,
        formulation: Formulation,
    ) -> Dict[str, Decimal]:
        """Calculate total nutrients per 100g of final formulation.

        Args:
            formulation: The formulation to calculate

        Returns:
            Dictionary mapping nutrient names to amounts per 100g

        Note:
            USDA nutrient data is per 100g of ingredient.
            This method:
            1. Scales each ingredient's nutrients by its amount
            2. Sums across all ingredients
            3. Normalizes to 100g of final product
        """
        if formulation.is_empty():
            return {}

        total_weight = formulation.total_weight

        if total_weight == 0:
            return {}

        # Accumulate weighted nutrient amounts
        nutrient_sums: Dict[str, Decimal] = {}

        for ingredient in formulation.ingredients:
            ingredient_weight = ingredient.amount_g

            for nutrient in ingredient.food.nutrients:
                name = nutrient.name
                # Nutrient amount is per 100g, scale to ingredient weight
                scaled_amount = nutrient.amount * (ingredient_weight / Decimal("100"))

                if name in nutrient_sums:
                    nutrient_sums[name] += scaled_amount
                else:
                    nutrient_sums[name] = scaled_amount

        # Normalize to per 100g of final product
        normalization_factor = Decimal("100") / total_weight

        return {
            name: amount * normalization_factor for name, amount in nutrient_sums.items()
        }

    def calculate_per_ingredient(
        self,
        formulation: Formulation,
    ) -> Dict[int, Dict[str, Decimal]]:
        """Calculate nutrients for each ingredient (not normalized).

        Args:
            formulation: The formulation to calculate

        Returns:
            Dictionary mapping ingredient index to nutrient amounts
            Amounts are absolute (not per 100g)
        """
        result: Dict[int, Dict[str, Decimal]] = {}

        for idx, ingredient in enumerate(formulation.ingredients):
            ingredient_nutrients: Dict[str, Decimal] = {}
            ingredient_weight = ingredient.amount_g

            for nutrient in ingredient.food.nutrients:
                # Scale from per-100g to actual ingredient amount
                scaled_amount = nutrient.amount * (ingredient_weight / Decimal("100"))
                ingredient_nutrients[nutrient.name] = scaled_amount

            result[idx] = ingredient_nutrients

        return result

    def calculate_energy(
        self,
        protein_g: Decimal,
        carbohydrate_g: Decimal,
        fat_g: Decimal,
    ) -> tuple[Decimal, Decimal]:
        """Calculate energy using Atwater factors.

        Args:
            protein_g: Grams of protein
            carbohydrate_g: Grams of carbohydrate
            fat_g: Grams of fat

        Returns:
            Tuple of (kcal, kJ)

        Note:
            Uses 4-9-4 system:
            - Protein: 4 kcal/g
            - Carbohydrate: 4 kcal/g
            - Fat: 9 kcal/g
        """
        kcal = (
            protein_g * Decimal(str(ATWATER_PROTEIN))
            + carbohydrate_g * Decimal(str(ATWATER_CARBOHYDRATE))
            + fat_g * Decimal(str(ATWATER_FAT))
        )
        kj = kcal * Decimal(str(KCAL_TO_KJ))

        return (kcal, kj)

    def get_nutrient_value(
        self,
        totals: Dict[str, Decimal],
        nutrient_name: str,
    ) -> Decimal:
        """Get a specific nutrient value from totals.

        Args:
            totals: Dictionary of nutrient totals
            nutrient_name: Name of nutrient (case-insensitive)

        Returns:
            Nutrient amount or Decimal("0") if not found
        """
        # Case-insensitive lookup
        nutrient_name_lower = nutrient_name.lower()
        for name, amount in totals.items():
            if name.lower() == nutrient_name_lower:
                return amount

        return Decimal("0")
