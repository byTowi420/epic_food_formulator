"""Formulation presenter - orchestrates formulation use cases for UI.

Handles all formulation-related operations:
- Add/remove ingredients
- Calculate totals
- Adjust amounts/locks
- Generate label data
"""

from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.container import Container
from domain.models import Formulation
from domain.services.label_generator import LabelRow
from domain.exceptions import FormulationImportError
from ui.adapters.formulation_mapper import FormulationMapper, NutrientDisplayMapper


class FormulationPresenter:
    """Presenter for formulation operations.

    Coordinates use cases and prepares data for UI display.
    UI should only call presenter methods, not use cases directly.
    """

    def __init__(self, container: Optional[Container] = None) -> None:
        """Initialize presenter.

        Args:
            container: DI container (creates new one if not provided)
        """
        self._container = container if container is not None else Container()
        self._formulation: Formulation = Formulation(name="New Formulation")

    @property
    def formulation_name(self) -> str:
        """Get current formulation name."""
        return self._formulation.name

    @formulation_name.setter
    def formulation_name(self, value: str) -> None:
        """Set formulation name."""
        # Since Formulation is mutable, we can just update
        # (Or recreate if we want immutability - decision: keep simple)
        object.__setattr__(self._formulation, "name", value)

    def get_ui_items(self) -> List[Dict[str, Any]]:
        """Get current formulation as list of UI items.

        Returns:
            List of dicts for UI tables
        """
        return FormulationMapper.formulation_to_ui_items(self._formulation)

    def add_ingredient(
        self,
        fdc_id: int,
        amount_g: float,
    ) -> Dict[str, Any]:
        """Add ingredient to formulation.

        Args:
            fdc_id: USDA Food ID
            amount_g: Amount in grams

        Returns:
            UI item dict for the added ingredient

        Raises:
            Exception: If ingredient cannot be added
        """
        # Use AddIngredientUseCase
        food = self._container.add_ingredient.execute(
            self._formulation,
            fdc_id,
            Decimal(str(amount_g)),
        )

        # Return last added ingredient as UI item
        last_ingredient = self._formulation.ingredients[-1]
        return FormulationMapper.ingredient_to_ui_item(
            last_ingredient,
            len(self._formulation.ingredients) - 1,
        )

    def remove_ingredient(self, index: int) -> None:
        """Remove ingredient at index.

        Args:
            index: Index of ingredient to remove
        """
        self._formulation.remove_ingredient(index)

    def update_ingredient_amount(
        self,
        index: int,
        amount_g: float,
        maintain_total: bool = False,
    ) -> None:
        """Update ingredient amount.

        Args:
            index: Ingredient index
            amount_g: New amount in grams
            maintain_total: Whether to adjust other ingredients
        """
        if maintain_total:
            self._container.formulation_service.set_ingredient_amount(
                self._formulation,
                index,
                Decimal(str(amount_g)),
                maintain_total_weight=True,
            )
        else:
            ingredient = self._formulation.get_ingredient(index)
            ingredient.amount_g = Decimal(str(amount_g))

    def toggle_lock(self, index: int) -> bool:
        """Toggle ingredient lock state.

        Args:
            index: Ingredient index

        Returns:
            New lock state
        """
        ingredient = self._formulation.get_ingredient(index)
        ingredient.locked = not ingredient.locked
        return ingredient.locked

    def calculate_totals(self) -> Dict[str, Dict[str, Any]]:
        """Calculate nutrient totals per 100g.

        Returns:
            Dict of nutrient name -> display dict
        """
        totals = self._container.calculate_totals.execute(self._formulation)
        return NutrientDisplayMapper.totals_to_display_dict(totals, self._formulation)

    def get_label_rows(self, serving_size_g: float = 100.0) -> List[LabelRow]:
        """Get FDA nutrition label rows.

        Args:
            serving_size_g: Serving size in grams

        Returns:
            List of LabelRow objects
        """
        totals = self._container.calculate_totals.execute(self._formulation)
        return self._container.label_generator.generate_label(
            totals,
            Decimal(str(serving_size_g)),
        )

    def adjust_to_target_weight(self, target_g: float) -> None:
        """Adjust unlocked ingredients to reach target weight.

        Args:
            target_g: Target total weight in grams
        """
        self._container.adjust_formulation.execute(
            self._formulation,
            Decimal(str(target_g)),
        )

    def normalize_to_100g(self) -> None:
        """Normalize formulation to 100g total."""
        self._container.formulation_service.normalize_to_100g(self._formulation)

    def normalize_to_target_weight(self, target_g: float) -> None:
        """Normalize formulation to a target total weight in grams."""
        self._container.formulation_service.scale_to_target_weight(
            self._formulation,
            Decimal(str(target_g)),
        )

    def clear(self) -> None:
        """Clear all ingredients."""
        self._formulation.clear()

    def load_from_file(self, filename: str) -> None:
        """Load formulation from file.

        Args:
            filename: Filename to load
        """
        loaded = self._container.load_formulation.execute(filename)
        self._formulation = loaded

    def save_to_file(self, filename: str) -> str:
        """Save formulation to file.

        Args:
            filename: Filename to save

        Returns:
            Full path to saved file
        """
        path = self._container.save_formulation.execute(self._formulation, filename)
        return str(path)

    def export_to_excel(
        self,
        output_path: str,
        export_flags: Dict[str, bool] | None = None,
        mass_unit: str | None = None,
    ) -> None:
        """Export formulation to Excel.

        Args:
            output_path: Output file path
        """
        self._container.export_formulation.execute(
            self._formulation,
            output_path,
            export_flags=export_flags,
            mass_unit=mass_unit,
        )

    def parse_import_file(
        self,
        path: str,
        *,
        current_formula_name: str = "",
    ) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
        """Parse a formulation file into base items + metadata."""
        ext = Path(path).suffix.lower()
        importer = self._container.formulation_importer
        if ext == ".json":
            return importer.load_state_from_json(path)
        if ext in (".xlsx", ".xls"):
            return importer.load_state_from_excel(
                path,
                default_formula_name=current_formula_name,
            )
        raise FormulationImportError(
            "Formato no soportado",
            "Selecciona un archivo .json o .xlsx",
        )

    def resolve_legacy_export_flags(
        self,
        legacy_flags: Dict[str, bool],
        hydrated_items: list[Dict[str, Any]],
    ) -> Dict[str, bool]:
        """Map legacy export flag keys to header-key flags."""
        return self._container.formulation_importer.resolve_legacy_export_flags(
            legacy_flags, hydrated_items
        )

    def get_total_weight(self) -> float:
        """Get total weight of formulation.

        Returns:
            Total weight in grams
        """
        return float(self._formulation.total_weight)

    def get_ingredient_count(self) -> int:
        """Get number of ingredients.

        Returns:
            Count of ingredients
        """
        return self._formulation.ingredient_count

    def has_ingredients(self) -> bool:
        """Check if formulation has any ingredients.

        Returns:
            True if formulation has ingredients
        """
        return self._formulation.ingredient_count > 0

    def get_ui_item(self, index: int) -> Dict[str, Any]:
        """Get single UI item by index.

        Args:
            index: Ingredient index

        Returns:
            UI item dict

        Raises:
            IndexError: If index out of range
        """
        ingredient = self._formulation.get_ingredient(index)
        return FormulationMapper.ingredient_to_ui_item(ingredient, index)

    def get_locked_count(self, exclude_index: Optional[int] = None) -> int:
        """Count locked ingredients.

        Args:
            exclude_index: Optional index to exclude from count

        Returns:
            Number of locked ingredients
        """
        count = 0
        for idx, ingredient in enumerate(self._formulation.ingredients):
            if exclude_index is not None and idx == exclude_index:
                continue
            if ingredient.locked:
                count += 1
        return count

    def load_from_ui_items(
        self,
        ui_items: List[Dict[str, Any]],
        name: str = "Loaded Formulation",
    ) -> None:
        """Load formulation from UI item list (for compatibility).

        Args:
            ui_items: List of UI item dicts
            name: Formulation name
        """
        self._formulation = FormulationMapper.ui_items_to_formulation(ui_items, name)
