"""Nutrient calculation service.

Handles all nutrient-related calculations for formulations.
Pure business logic with no UI dependencies.
"""

from decimal import Decimal
from typing import Dict

from domain.models import Formulation


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

