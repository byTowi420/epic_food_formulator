"""Tests for NutrientCalculator service."""

from decimal import Decimal

import pytest

from domain.models import Food, Formulation, Ingredient, Nutrient
from domain.services.nutrient_calculator import NutrientCalculator


@pytest.fixture
def calculator() -> NutrientCalculator:
    """Create a NutrientCalculator instance."""
    return NutrientCalculator()


@pytest.fixture
def sample_food_chicken() -> Food:
    """Create sample chicken food with nutrients."""
    return Food(
        fdc_id=1,
        description="Chicken breast",
        data_type="Foundation",
        nutrients=(
            Nutrient(name="Protein", unit="g", amount=Decimal("31.0")),  # per 100g
            Nutrient(name="Total lipid (fat)", unit="g", amount=Decimal("3.6")),
            Nutrient(name="Carbohydrate, by difference", unit="g", amount=Decimal("0")),
        ),
    )


@pytest.fixture
def sample_food_rice() -> Food:
    """Create sample rice food with nutrients."""
    return Food(
        fdc_id=2,
        description="White rice",
        data_type="Foundation",
        nutrients=(
            Nutrient(name="Protein", unit="g", amount=Decimal("7.1")),
            Nutrient(name="Total lipid (fat)", unit="g", amount=Decimal("0.7")),
            Nutrient(name="Carbohydrate, by difference", unit="g", amount=Decimal("79.0")),
        ),
    )


class TestCalculateTotalsPer100g:
    """Test calculate_totals_per_100g method."""

    def test_empty_formulation_returns_empty(
        self,
        calculator: NutrientCalculator,
    ) -> None:
        formulation = Formulation(name="Empty")
        totals = calculator.calculate_totals_per_100g(formulation)

        assert totals == {}

    def test_single_ingredient_100g_returns_same_values(
        self,
        calculator: NutrientCalculator,
        sample_food_chicken: Food,
    ) -> None:
        formulation = Formulation(name="Test")
        formulation.add_ingredient(
            Ingredient(food=sample_food_chicken, amount_g=Decimal("100"))
        )

        totals = calculator.calculate_totals_per_100g(formulation)

        # Should be same as ingredient nutrients (already per 100g)
        assert totals["Protein"] == Decimal("31.0")
        assert totals["Total lipid (fat)"] == Decimal("3.6")

    def test_single_ingredient_200g_returns_same_per_100g(
        self,
        calculator: NutrientCalculator,
        sample_food_chicken: Food,
    ) -> None:
        formulation = Formulation(name="Test")
        formulation.add_ingredient(
            Ingredient(food=sample_food_chicken, amount_g=Decimal("200"))
        )

        totals = calculator.calculate_totals_per_100g(formulation)

        # Should still be per 100g of final product (which is 100% chicken)
        assert totals["Protein"] == Decimal("31.0")
        assert totals["Total lipid (fat)"] == Decimal("3.6")

    def test_two_ingredients_equal_amounts(
        self,
        calculator: NutrientCalculator,
        sample_food_chicken: Food,
        sample_food_rice: Food,
    ) -> None:
        formulation = Formulation(name="Test")
        formulation.add_ingredient(
            Ingredient(food=sample_food_chicken, amount_g=Decimal("100"))
        )
        formulation.add_ingredient(
            Ingredient(food=sample_food_rice, amount_g=Decimal("100"))
        )

        totals = calculator.calculate_totals_per_100g(formulation)

        # Total weight = 200g
        # Per 100g of final product = (chicken + rice) / 2
        # Protein: (31.0 + 7.1) / 2 = 19.05
        expected_protein = (Decimal("31.0") + Decimal("7.1")) / Decimal("2")
        assert totals["Protein"] == expected_protein

        expected_fat = (Decimal("3.6") + Decimal("0.7")) / Decimal("2")
        assert totals["Total lipid (fat)"] == expected_fat

    def test_two_ingredients_different_amounts(
        self,
        calculator: NutrientCalculator,
        sample_food_chicken: Food,
        sample_food_rice: Food,
    ) -> None:
        formulation = Formulation(name="Test")
        # 75g chicken, 25g rice = 100g total
        formulation.add_ingredient(
            Ingredient(food=sample_food_chicken, amount_g=Decimal("75"))
        )
        formulation.add_ingredient(Ingredient(food=sample_food_rice, amount_g=Decimal("25")))

        totals = calculator.calculate_totals_per_100g(formulation)

        # Protein per 100g: (31.0 * 75/100 + 7.1 * 25/100) / (100/100)
        # = (23.25 + 1.775) = 25.025
        expected_protein = Decimal("31.0") * Decimal("0.75") + Decimal("7.1") * Decimal("0.25")
        assert totals["Protein"] == expected_protein


