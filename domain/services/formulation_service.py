"""Formulation service.

Handles business logic for formulation operations like adjusting
ingredient amounts while respecting locks.
"""

from decimal import Decimal

from domain.exceptions import InvalidFormulationError
from domain.models import Formulation, Ingredient


class FormulationService:
    """Service for formulation business operations."""

    def adjust_to_target_weight(
        self,
        formulation: Formulation,
        target_weight_g: Decimal,
    ) -> None:
        """Adjust unlocked ingredients to reach target total weight.

        Args:
            formulation: The formulation to adjust (modified in-place)
            target_weight_g: Desired total weight in grams

        Raises:
            InvalidFormulationError: If adjustment is impossible

        Note:
            Locked ingredients maintain their absolute weights.
            Unlocked ingredients are scaled proportionally.
        """
        if target_weight_g <= 0:
            raise InvalidFormulationError(f"Target weight must be positive: {target_weight_g}")

        locked_weight = formulation.get_total_locked_weight()

        if locked_weight > target_weight_g:
            raise InvalidFormulationError(
                f"Locked weight ({locked_weight}g) exceeds target ({target_weight_g}g)"
            )

        unlocked = formulation.get_unlocked_ingredients()

        if not unlocked:
            # All locked, nothing to adjust
            if formulation.total_weight != target_weight_g:
                raise InvalidFormulationError(
                    "All ingredients locked, cannot reach target weight"
                )
            return

        # Calculate current unlocked weight
        current_unlocked_weight = sum((ing.amount_g for _, ing in unlocked), Decimal("0"))

        if current_unlocked_weight == 0:
            raise InvalidFormulationError("Unlocked ingredients have zero weight")

        # Available weight for unlocked ingredients
        available_weight = target_weight_g - locked_weight

        # Scale unlocked ingredients proportionally
        scale_factor = available_weight / current_unlocked_weight

        for _, ingredient in unlocked:
            ingredient.amount_g *= scale_factor

    def distribute_percentages(
        self,
        formulation: Formulation,
        target_total_g: Decimal = Decimal("100"),
    ) -> None:
        """Set ingredient amounts from their current percentages.

        Args:
            formulation: The formulation to update (modified in-place)
            target_total_g: Total weight to distribute (default 100g)

        Raises:
            InvalidFormulationError: If percentages don't sum to ~100%

        Note:
            Useful when switching from percentage mode to grams mode.
        """
        if formulation.is_empty():
            return

        # Calculate target amounts from percentages
        for ingredient in formulation.ingredients:
            percentage = ingredient.calculate_percentage(formulation.total_weight)
            ingredient.amount_g = (percentage / Decimal("100")) * target_total_g

    def normalize_to_100g(
        self,
        formulation: Formulation,
    ) -> None:
        """Scale all ingredients so total weight is 100g.

        Args:
            formulation: The formulation to normalize (modified in-place)

        Note:
            Maintains relative proportions while setting total to 100g.
            All locks are ignored (this is a proportional scaling).
        """
        current_weight = formulation.total_weight

        if current_weight == 0:
            return

        if current_weight == Decimal("100"):
            return  # Already normalized

        scale_factor = Decimal("100") / current_weight

        for ingredient in formulation.ingredients:
            ingredient.amount_g *= scale_factor

    def lock_ingredient(
        self,
        formulation: Formulation,
        index: int,
    ) -> None:
        """Lock an ingredient at its current amount.

        Args:
            formulation: The formulation
            index: Index of ingredient to lock
        """
        ingredient = formulation.get_ingredient(index)
        ingredient.locked = True

    def unlock_ingredient(
        self,
        formulation: Formulation,
        index: int,
    ) -> None:
        """Unlock an ingredient.

        Args:
            formulation: The formulation
            index: Index of ingredient to unlock
        """
        ingredient = formulation.get_ingredient(index)
        ingredient.locked = False

    def set_ingredient_amount(
        self,
        formulation: Formulation,
        index: int,
        amount_g: Decimal,
        maintain_total_weight: bool = True,
    ) -> None:
        """Set ingredient amount and optionally adjust others.

        Args:
            formulation: The formulation (modified in-place)
            index: Index of ingredient to modify
            amount_g: New amount in grams
            maintain_total_weight: If True, adjust other unlocked ingredients
                                   to maintain the same total weight

        Raises:
            InvalidFormulationError: If adjustment is impossible
        """
        if amount_g < 0:
            raise InvalidFormulationError(f"Amount cannot be negative: {amount_g}")

        ingredient = formulation.get_ingredient(index)

        if not maintain_total_weight:
            ingredient.amount_g = amount_g
            return

        # Maintain total weight by adjusting unlocked ingredients
        old_amount = ingredient.amount_g
        target_total = formulation.total_weight

        ingredient.amount_g = amount_g

        # New total after change
        delta = amount_g - old_amount
        new_target = target_total + delta

        try:
            # Temporarily lock the changed ingredient to protect it
            was_locked = ingredient.locked
            ingredient.locked = True

            self.adjust_to_target_weight(formulation, target_total)

        finally:
            # Restore original lock state
            ingredient.locked = was_locked
