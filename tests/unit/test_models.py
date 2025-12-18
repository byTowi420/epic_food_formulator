"""Tests for domain models."""

from decimal import Decimal

import pytest

from domain.models import Food, Formulation, Ingredient, Nutrient


class TestNutrient:
    """Test Nutrient model."""

    def test_create_nutrient(self) -> None:
        nutrient = Nutrient(
            name="Protein",
            unit="g",
            amount=Decimal("15.5"),
        )

        assert nutrient.name == "Protein"
        assert nutrient.unit == "g"
        assert nutrient.amount == Decimal("15.5")

    def test_nutrient_is_immutable(self) -> None:
        nutrient = Nutrient(name="Protein", unit="g", amount=Decimal("10"))

        with pytest.raises(Exception):  # FrozenInstanceError
            nutrient.amount = Decimal("20")  # type: ignore

    def test_nutrient_validates_name(self) -> None:
        with pytest.raises(ValueError, match="name cannot be empty"):
            Nutrient(name="", unit="g", amount=Decimal("10"))

    def test_nutrient_validates_unit(self) -> None:
        with pytest.raises(ValueError, match="unit cannot be empty"):
            Nutrient(name="Protein", unit="", amount=Decimal("10"))

    def test_nutrient_validates_negative_amount(self) -> None:
        with pytest.raises(ValueError, match="cannot be negative"):
            Nutrient(name="Protein", unit="g", amount=Decimal("-5"))

    def test_nutrient_scale(self) -> None:
        nutrient = Nutrient(name="Protein", unit="g", amount=Decimal("10"))
        scaled = nutrient.scale(Decimal("2.5"))

        assert scaled.amount == Decimal("25")
        assert scaled.name == nutrient.name
        assert scaled.unit == nutrient.unit
        # Original unchanged
        assert nutrient.amount == Decimal("10")


class TestFood:
    """Test Food model."""

    def test_create_food(self) -> None:
        nutrients = (
            Nutrient(name="Protein", unit="g", amount=Decimal("20")),
            Nutrient(name="Fat", unit="g", amount=Decimal("10")),
        )
        food = Food(
            fdc_id=12345,
            description="Chicken breast",
            data_type="Foundation",
            nutrients=nutrients,
        )

        assert food.fdc_id == 12345
        assert food.description == "Chicken breast"
        assert len(food.nutrients) == 2

    def test_food_is_immutable(self) -> None:
        food = Food(fdc_id=123, description="Apple", data_type="Foundation")

        with pytest.raises(Exception):  # FrozenInstanceError
            food.description = "Banana"  # type: ignore

    def test_food_validates_fdc_id(self) -> None:
        with pytest.raises(ValueError, match="Invalid FDC ID"):
            Food(fdc_id=0, description="Test", data_type="Foundation")

        with pytest.raises(ValueError, match="Invalid FDC ID"):
            Food(fdc_id=-1, description="Test", data_type="Foundation")

    def test_food_validates_description(self) -> None:
        with pytest.raises(ValueError, match="description cannot be empty"):
            Food(fdc_id=123, description="", data_type="Foundation")

    def test_get_nutrient_case_insensitive(self) -> None:
        nutrients = (Nutrient(name="Protein", unit="g", amount=Decimal("20")),)
        food = Food(
            fdc_id=123,
            description="Test",
            data_type="Foundation",
            nutrients=nutrients,
        )

        assert food.get_nutrient("protein") is not None
        assert food.get_nutrient("PROTEIN") is not None
        assert food.get_nutrient("Protein") is not None

    def test_get_nutrient_returns_none_if_not_found(self) -> None:
        food = Food(fdc_id=123, description="Test", data_type="Foundation")
        assert food.get_nutrient("NonExistent") is None

    def test_has_nutrient(self) -> None:
        nutrients = (Nutrient(name="Protein", unit="g", amount=Decimal("20")),)
        food = Food(
            fdc_id=123,
            description="Test",
            data_type="Foundation",
            nutrients=nutrients,
        )

        assert food.has_nutrient("Protein") is True
        assert food.has_nutrient("Fat") is False


class TestIngredient:
    """Test Ingredient model."""

    def test_create_ingredient(self) -> None:
        food = Food(fdc_id=123, description="Chicken", data_type="Foundation")
        ingredient = Ingredient(food=food, amount_g=Decimal("150"))

        assert ingredient.food == food
        assert ingredient.amount_g == Decimal("150")
        assert ingredient.locked is False

    def test_ingredient_validates_negative_amount(self) -> None:
        food = Food(fdc_id=123, description="Chicken", data_type="Foundation")

        with pytest.raises(ValueError, match="cannot be negative"):
            Ingredient(food=food, amount_g=Decimal("-10"))

    def test_calculate_percentage(self) -> None:
        food = Food(fdc_id=123, description="Chicken", data_type="Foundation")
        ingredient = Ingredient(food=food, amount_g=Decimal("25"))

        percentage = ingredient.calculate_percentage(Decimal("100"))
        assert percentage == Decimal("25")

    def test_calculate_percentage_zero_total(self) -> None:
        food = Food(fdc_id=123, description="Chicken", data_type="Foundation")
        ingredient = Ingredient(food=food, amount_g=Decimal("25"))

        percentage = ingredient.calculate_percentage(Decimal("0"))
        assert percentage == Decimal("0")

    def test_get_nutrient_amount_scales_correctly(self) -> None:
        """Nutrient amounts should be scaled from per-100g to ingredient amount."""
        nutrients = (Nutrient(name="Protein", unit="g", amount=Decimal("20")),)  # 20g per 100g
        food = Food(
            fdc_id=123,
            description="Chicken",
            data_type="Foundation",
            nutrients=nutrients,
        )
        ingredient = Ingredient(food=food, amount_g=Decimal("200"))  # 200g total

        # Should be 20 * (200/100) = 40g
        protein_amount = ingredient.get_nutrient_amount("Protein")
        assert protein_amount == Decimal("40")

    def test_get_nutrient_amount_returns_zero_if_not_found(self) -> None:
        food = Food(fdc_id=123, description="Chicken", data_type="Foundation")
        ingredient = Ingredient(food=food, amount_g=Decimal("100"))

        assert ingredient.get_nutrient_amount("NonExistent") == Decimal("0")


class TestFormulation:
    """Test Formulation model."""

    def test_create_formulation(self) -> None:
        formulation = Formulation(name="My Recipe")

        assert formulation.name == "My Recipe"
        assert formulation.ingredients == []
        assert formulation.quantity_mode == "g"

    def test_formulation_validates_name(self) -> None:
        with pytest.raises(ValueError, match="name cannot be empty"):
            Formulation(name="")

    def test_formulation_validates_quantity_mode(self) -> None:
        with pytest.raises(ValueError, match="Invalid quantity mode"):
            Formulation(name="Test", quantity_mode="invalid")

    def test_total_weight(self) -> None:
        food1 = Food(fdc_id=1, description="Food1", data_type="Foundation")
        food2 = Food(fdc_id=2, description="Food2", data_type="Foundation")

        formulation = Formulation(name="Test")
        formulation.add_ingredient(Ingredient(food=food1, amount_g=Decimal("100")))
        formulation.add_ingredient(Ingredient(food=food2, amount_g=Decimal("50")))

        assert formulation.total_weight == Decimal("150")

    def test_add_and_remove_ingredient(self) -> None:
        food = Food(fdc_id=1, description="Food1", data_type="Foundation")
        formulation = Formulation(name="Test")

        formulation.add_ingredient(Ingredient(food=food, amount_g=Decimal("100")))
        assert formulation.ingredient_count == 1

        formulation.remove_ingredient(0)
        assert formulation.ingredient_count == 0

    def test_remove_ingredient_invalid_index(self) -> None:
        formulation = Formulation(name="Test")

        with pytest.raises(IndexError):
            formulation.remove_ingredient(0)

    def test_get_locked_and_unlocked_ingredients(self) -> None:
        food1 = Food(fdc_id=1, description="Food1", data_type="Foundation")
        food2 = Food(fdc_id=2, description="Food2", data_type="Foundation")
        food3 = Food(fdc_id=3, description="Food3", data_type="Foundation")

        formulation = Formulation(name="Test")
        formulation.add_ingredient(Ingredient(food=food1, amount_g=Decimal("100"), locked=True))
        formulation.add_ingredient(Ingredient(food=food2, amount_g=Decimal("50"), locked=False))
        formulation.add_ingredient(Ingredient(food=food3, amount_g=Decimal("75"), locked=True))

        locked = formulation.get_locked_ingredients()
        unlocked = formulation.get_unlocked_ingredients()

        assert len(locked) == 2
        assert len(unlocked) == 1
        assert locked[0][1].food.fdc_id == 1
        assert locked[1][1].food.fdc_id == 3
        assert unlocked[0][1].food.fdc_id == 2

    def test_get_total_locked_weight(self) -> None:
        food1 = Food(fdc_id=1, description="Food1", data_type="Foundation")
        food2 = Food(fdc_id=2, description="Food2", data_type="Foundation")

        formulation = Formulation(name="Test")
        formulation.add_ingredient(Ingredient(food=food1, amount_g=Decimal("100"), locked=True))
        formulation.add_ingredient(Ingredient(food=food2, amount_g=Decimal("50"), locked=False))

        assert formulation.get_total_locked_weight() == Decimal("100")

    def test_clear(self) -> None:
        food = Food(fdc_id=1, description="Food1", data_type="Foundation")
        formulation = Formulation(name="Test")
        formulation.add_ingredient(Ingredient(food=food, amount_g=Decimal("100")))

        formulation.clear()
        assert formulation.is_empty() is True
        assert formulation.ingredient_count == 0
