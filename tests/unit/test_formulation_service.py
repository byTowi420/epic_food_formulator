"""Tests for FormulationService."""

from decimal import Decimal

import pytest

from domain.exceptions import InvalidFormulationError
from domain.models import Food, Formulation, Ingredient
from domain.services.formulation_service import FormulationService


@pytest.fixture
def service() -> FormulationService:
    """Create FormulationService instance."""
    return FormulationService()


@pytest.fixture
def sample_formulation() -> Formulation:
    """Create a sample formulation with 3 ingredients."""
    food1 = Food(fdc_id=1, description="Food1", data_type="Foundation")
    food2 = Food(fdc_id=2, description="Food2", data_type="Foundation")
    food3 = Food(fdc_id=3, description="Food3", data_type="Foundation")

    formulation = Formulation(name="Test")
    formulation.add_ingredient(Ingredient(food=food1, amount_g=Decimal("50")))
    formulation.add_ingredient(Ingredient(food=food2, amount_g=Decimal("30")))
    formulation.add_ingredient(Ingredient(food=food3, amount_g=Decimal("20")))

    return formulation  # Total: 100g


class TestAdjustToTargetWeight:
    """Test adjust_to_target_weight method."""

    def test_scales_all_unlocked_to_target(
        self,
        service: FormulationService,
        sample_formulation: Formulation,
    ) -> None:
        # Target 200g (double everything)
        service.adjust_to_target_weight(sample_formulation, Decimal("200"))

        assert sample_formulation.ingredients[0].amount_g == Decimal("100")
        assert sample_formulation.ingredients[1].amount_g == Decimal("60")
        assert sample_formulation.ingredients[2].amount_g == Decimal("40")
        assert sample_formulation.total_weight == Decimal("200")

    def test_respects_locked_ingredients(
        self,
        service: FormulationService,
        sample_formulation: Formulation,
    ) -> None:
        # Lock first ingredient at 50g
        sample_formulation.ingredients[0].locked = True

        # Target 150g total
        # Locked: 50g
        # Available for unlocked: 100g
        # Current unlocked: 30 + 20 = 50g
        # Scale factor: 100/50 = 2
        service.adjust_to_target_weight(sample_formulation, Decimal("150"))

        assert sample_formulation.ingredients[0].amount_g == Decimal("50")  # locked
        assert sample_formulation.ingredients[1].amount_g == Decimal("60")  # 30 * 2
        assert sample_formulation.ingredients[2].amount_g == Decimal("40")  # 20 * 2
        assert sample_formulation.total_weight == Decimal("150")

    def test_raises_if_locked_exceeds_target(
        self,
        service: FormulationService,
        sample_formulation: Formulation,
    ) -> None:
        sample_formulation.ingredients[0].locked = True  # 50g locked

        with pytest.raises(InvalidFormulationError, match="Locked weight.*exceeds target"):
            service.adjust_to_target_weight(sample_formulation, Decimal("40"))

    def test_raises_if_target_not_positive(
        self,
        service: FormulationService,
        sample_formulation: Formulation,
    ) -> None:
        with pytest.raises(InvalidFormulationError, match="must be positive"):
            service.adjust_to_target_weight(sample_formulation, Decimal("0"))


class TestNormalizeTo100g:
    """Test normalize_to_100g method."""

    def test_scales_to_100g(
        self,
        service: FormulationService,
    ) -> None:
        food = Food(fdc_id=1, description="Food1", data_type="Foundation")
        formulation = Formulation(name="Test")
        formulation.add_ingredient(Ingredient(food=food, amount_g=Decimal("250")))

        service.normalize_to_100g(formulation)

        assert formulation.total_weight == Decimal("100")
        assert formulation.ingredients[0].amount_g == Decimal("100")

    def test_maintains_proportions(
        self,
        service: FormulationService,
        sample_formulation: Formulation,
    ) -> None:
        # Start with 100g: 50%, 30%, 20%
        # Scale to 200g
        for ing in sample_formulation.ingredients:
            ing.amount_g *= Decimal("2")

        service.normalize_to_100g(sample_formulation)

        # Should be back to 50, 30, 20
        assert sample_formulation.ingredients[0].amount_g == Decimal("50")
        assert sample_formulation.ingredients[1].amount_g == Decimal("30")
        assert sample_formulation.ingredients[2].amount_g == Decimal("20")

    def test_does_nothing_if_already_100g(
        self,
        service: FormulationService,
        sample_formulation: Formulation,
    ) -> None:
        # Already 100g
        service.normalize_to_100g(sample_formulation)

        assert sample_formulation.total_weight == Decimal("100")


class TestLockUnlock:
    """Test lock/unlock operations."""

    def test_lock_ingredient(
        self,
        service: FormulationService,
        sample_formulation: Formulation,
    ) -> None:
        assert sample_formulation.ingredients[0].locked is False

        service.lock_ingredient(sample_formulation, 0)

        assert sample_formulation.ingredients[0].locked is True

    def test_unlock_ingredient(
        self,
        service: FormulationService,
        sample_formulation: Formulation,
    ) -> None:
        sample_formulation.ingredients[0].locked = True

        service.unlock_ingredient(sample_formulation, 0)

        assert sample_formulation.ingredients[0].locked is False


class TestSetIngredientAmount:
    """Test set_ingredient_amount method."""

    def test_sets_amount_without_maintaining_total(
        self,
        service: FormulationService,
        sample_formulation: Formulation,
    ) -> None:
        service.set_ingredient_amount(
            sample_formulation,
            0,
            Decimal("75"),
            maintain_total_weight=False,
        )

        assert sample_formulation.ingredients[0].amount_g == Decimal("75")
        # Total changes
        assert sample_formulation.total_weight == Decimal("125")

    def test_maintains_total_weight_by_adjusting_others(
        self,
        service: FormulationService,
        sample_formulation: Formulation,
    ) -> None:
        original_total = sample_formulation.total_weight

        # Change first ingredient from 50 to 60 (+10)
        # Others should adjust proportionally to compensate
        service.set_ingredient_amount(
            sample_formulation,
            0,
            Decimal("60"),
            maintain_total_weight=True,
        )

        # Total should remain the same
        assert sample_formulation.total_weight == original_total

    def test_raises_for_negative_amount(
        self,
        service: FormulationService,
        sample_formulation: Formulation,
    ) -> None:
        with pytest.raises(InvalidFormulationError, match="cannot be negative"):
            service.set_ingredient_amount(sample_formulation, 0, Decimal("-10"))
