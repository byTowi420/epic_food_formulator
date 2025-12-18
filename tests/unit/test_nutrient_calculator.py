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


class TestCalculatePerIngredient:
    """Test calculate_per_ingredient method."""

    def test_calculates_absolute_amounts_per_ingredient(
        self,
        calculator: NutrientCalculator,
        sample_food_chicken: Food,
        sample_food_rice: Food,
    ) -> None:
        formulation = Formulation(name="Test")
        formulation.add_ingredient(
            Ingredient(food=sample_food_chicken, amount_g=Decimal("200"))
        )
        formulation.add_ingredient(Ingredient(food=sample_food_rice, amount_g=Decimal("150")))

        per_ingredient = calculator.calculate_per_ingredient(formulation)

        # Chicken: 200g * (31.0 / 100) = 62.0g protein
        assert per_ingredient[0]["Protein"] == Decimal("62.0")

        # Rice: 150g * (7.1 / 100) = 10.65g protein
        assert per_ingredient[1]["Protein"] == Decimal("10.65")


class TestCalculateEnergy:
    """Test calculate_energy method."""

    def test_calculates_energy_using_atwater_factors(
        self,
        calculator: NutrientCalculator,
    ) -> None:
        protein = Decimal("10")
        carbs = Decimal("20")
        fat = Decimal("5")

        kcal, kj = calculator.calculate_energy(protein, carbs, fat)

        # Expected: 10*4 + 20*4 + 5*9 = 40 + 80 + 45 = 165 kcal
        assert kcal == Decimal("165.0")

        # kJ = kcal * 4.184
        expected_kj = Decimal("165.0") * Decimal("4.184")
        assert kj == expected_kj

    def test_zero_macros_gives_zero_energy(
        self,
        calculator: NutrientCalculator,
    ) -> None:
        kcal, kj = calculator.calculate_energy(
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
        )

        assert kcal == Decimal("0")
        assert kj == Decimal("0")


class TestGetNutrientValue:
    """Test get_nutrient_value method."""

    def test_gets_nutrient_case_insensitive(
        self,
        calculator: NutrientCalculator,
    ) -> None:
        totals = {
            "Protein": Decimal("20.0"),
            "Total lipid (fat)": Decimal("10.0"),
        }

        assert calculator.get_nutrient_value(totals, "protein") == Decimal("20.0")
        assert calculator.get_nutrient_value(totals, "PROTEIN") == Decimal("20.0")
        assert calculator.get_nutrient_value(totals, "Protein") == Decimal("20.0")

    def test_returns_zero_for_missing_nutrient(
        self,
        calculator: NutrientCalculator,
    ) -> None:
        totals = {"Protein": Decimal("20.0")}

        assert calculator.get_nutrient_value(totals, "Vitamin C") == Decimal("0")
