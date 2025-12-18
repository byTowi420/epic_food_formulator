"""Tests for LabelGenerator service."""

from decimal import Decimal

import pytest

from domain.services.label_generator import LabelGenerator, LabelRow


@pytest.fixture
def generator() -> LabelGenerator:
    """Create LabelGenerator instance."""
    return LabelGenerator()


@pytest.fixture
def sample_nutrients() -> dict[str, Decimal]:
    """Sample nutrient totals (per 100g)."""
    return {
        "Energy": Decimal("150"),
        "Total fat (NLEA)": Decimal("5"),
        "Fatty acids, total saturated": Decimal("2"),
        "Cholesterol": Decimal("50"),
        "Sodium, Na": Decimal("200"),
        "Carbohydrate, by difference": Decimal("20"),
        "Fiber, total dietary": Decimal("3"),
        "Sugars, Total": Decimal("5"),
        "Protein": Decimal("10"),
    }


class TestGenerateLabel:
    """Test generate_label method."""

    def test_generates_basic_label(
        self,
        generator: LabelGenerator,
        sample_nutrients: dict[str, Decimal],
    ) -> None:
        rows = generator.generate_label(sample_nutrients, Decimal("100"))

        # Should have serving size
        assert rows[0].nutrient_name == "Serving Size"
        assert "100g" in rows[0].amount

        # Should have calories
        calories_row = next((r for r in rows if r.nutrient_name == "Calories"), None)
        assert calories_row is not None

    def test_includes_required_macronutrients(
        self,
        generator: LabelGenerator,
        sample_nutrients: dict[str, Decimal],
    ) -> None:
        rows = generator.generate_label(sample_nutrients)

        nutrient_names = [r.nutrient_name for r in rows]

        assert "Total Fat" in nutrient_names
        assert "Total Carbohydrate" in nutrient_names
        assert "Protein" in nutrient_names

    def test_indents_sub_nutrients(
        self,
        generator: LabelGenerator,
        sample_nutrients: dict[str, Decimal],
    ) -> None:
        rows = generator.generate_label(sample_nutrients)

        # Total Fat should be indent 0
        total_fat = next((r for r in rows if r.nutrient_name == "Total Fat"), None)
        assert total_fat is not None
        assert total_fat.indent_level == 0

        # Saturated Fat should be indent 1
        sat_fat = next((r for r in rows if r.nutrient_name == "Saturated Fat"), None)
        assert sat_fat is not None
        assert sat_fat.indent_level == 1

    def test_calculates_daily_values(
        self,
        generator: LabelGenerator,
        sample_nutrients: dict[str, Decimal],
    ) -> None:
        rows = generator.generate_label(sample_nutrients)

        # Total Fat: 5g / 78g DV = ~6%
        total_fat = next((r for r in rows if r.nutrient_name == "Total Fat"), None)
        assert total_fat is not None
        assert total_fat.daily_value != ""
        assert "%" in total_fat.daily_value

    def test_scales_to_serving_size(
        self,
        generator: LabelGenerator,
        sample_nutrients: dict[str, Decimal],
    ) -> None:
        # Serving size = 50g (half of 100g basis)
        rows = generator.generate_label(sample_nutrients, Decimal("50"))

        # Protein was 10g per 100g, should be 5g per 50g
        protein = next((r for r in rows if r.nutrient_name == "Protein"), None)
        assert protein is not None
        assert "5" in protein.amount


class TestFormatAmount:
    """Test _format_amount method."""

    def test_formats_large_amounts_without_decimals(
        self,
        generator: LabelGenerator,
    ) -> None:
        result = generator._format_amount(Decimal("150"), "kcal")
        assert result == "150kcal"

    def test_formats_medium_amounts_with_one_decimal(
        self,
        generator: LabelGenerator,
    ) -> None:
        result = generator._format_amount(Decimal("5.5"), "g")
        assert result == "5.5g"

    def test_formats_small_amounts_with_two_decimals(
        self,
        generator: LabelGenerator,
    ) -> None:
        result = generator._format_amount(Decimal("0.25"), "mg")
        assert result == "0.25mg"


class TestCalcDvPercent:
    """Test _calc_dv_percent method."""

    def test_calculates_percentage(
        self,
        generator: LabelGenerator,
    ) -> None:
        # Sodium: 2300mg DV
        # 460mg = 20%
        result = generator._calc_dv_percent(Decimal("460"), "Sodium")
        assert result == "20%"

    def test_returns_empty_for_unknown_nutrient(
        self,
        generator: LabelGenerator,
    ) -> None:
        result = generator._calc_dv_percent(Decimal("100"), "Unknown")
        assert result == ""

    def test_returns_less_than_one_for_small_amounts(
        self,
        generator: LabelGenerator,
    ) -> None:
        # Sodium: 2300mg DV
        # 10mg = ~0.4% -> "<1%"
        result = generator._calc_dv_percent(Decimal("10"), "Sodium")
        assert result == "<1%"
