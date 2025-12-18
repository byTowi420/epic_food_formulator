"""Application use cases.

Use cases orchestrate domain services and infrastructure to fulfill
business workflows.
"""

from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

from domain.models import Food, Formulation, Ingredient, Nutrient
from domain.services.formulation_service import FormulationService
from domain.services.nutrient_calculator import NutrientCalculator
from infrastructure.api.usda_repository import FoodRepository
from infrastructure.normalizers.usda_normalizer import normalize_nutrients
from infrastructure.persistence.excel_exporter import ExcelExporter
from infrastructure.persistence.json_repository import JSONFormulationRepository


class SearchFoodsUseCase:
    """Search for foods in USDA database."""

    def __init__(self, food_repository: FoodRepository) -> None:
        self._repository = food_repository

    def execute(
        self,
        query: str,
        page_size: int = 25,
        include_branded: bool = False,
        page_number: int = 1,
    ) -> List[Dict[str, Any]]:
        """Search for foods.

        Args:
            query: Search query
            page_size: Number of results
            include_branded: Whether to include branded foods
            page_number: Page number

        Returns:
            List of food search results
        """
        data_types: List[str] | None = None
        if not include_branded:
            data_types = ["Foundation", "SR Legacy", "Survey (FNDDS)"]

        return self._repository.search(
            query=query,
            page_size=page_size,
            data_types=data_types,
            page_number=page_number,
        )


class AddIngredientUseCase:
    """Add ingredient to formulation from USDA food."""

    def __init__(
        self,
        food_repository: FoodRepository,
        formulation_service: FormulationService,
    ) -> None:
        self._food_repo = food_repository
        self._formulation_service = formulation_service

    def execute(
        self,
        formulation: Formulation,
        fdc_id: int,
        amount_g: Decimal,
    ) -> Food:
        """Add ingredient to formulation.

        Args:
            formulation: Target formulation
            fdc_id: USDA Food ID
            amount_g: Amount in grams

        Returns:
            The Food that was added
        """
        # Fetch food details
        food_data = self._food_repo.get_by_id(fdc_id, detail_format="abridged")

        # Normalize nutrients
        normalized_nutrients = normalize_nutrients(
            food_data.get("foodNutrients", []),
            data_type=food_data.get("dataType"),
        )

        # Convert to domain model
        nutrients = tuple(
            Nutrient(
                name=n["nutrient"]["name"],
                unit=n["nutrient"].get("unitName", ""),
                amount=Decimal(str(n["amount"])) if n.get("amount") is not None else Decimal("0"),
                nutrient_id=n["nutrient"].get("id"),
                nutrient_number=n["nutrient"].get("number"),
            )
            for n in normalized_nutrients
        )

        food = Food(
            fdc_id=fdc_id,
            description=food_data.get("description", ""),
            data_type=food_data.get("dataType", ""),
            brand_owner=food_data.get("brandOwner", ""),
            nutrients=nutrients,
        )

        # Create and add ingredient
        ingredient = Ingredient(food=food, amount_g=amount_g)
        formulation.add_ingredient(ingredient)

        return food


class CalculateTotalsUseCase:
    """Calculate nutrient totals for formulation."""

    def __init__(self, calculator: NutrientCalculator) -> None:
        self._calculator = calculator

    def execute(self, formulation: Formulation) -> Dict[str, Decimal]:
        """Calculate totals per 100g.

        Args:
            formulation: Formulation to calculate

        Returns:
            Dictionary of nutrient totals
        """
        return self._calculator.calculate_totals_per_100g(formulation)


class SaveFormulationUseCase:
    """Save formulation to file."""

    def __init__(self, json_repository: JSONFormulationRepository) -> None:
        self._repository = json_repository

    def execute(self, formulation: Formulation, filename: str) -> Path:
        """Save formulation.

        Args:
            formulation: Formulation to save
            filename: Filename

        Returns:
            Path to saved file
        """
        return self._repository.save(formulation, filename)


class LoadFormulationUseCase:
    """Load formulation from file."""

    def __init__(self, json_repository: JSONFormulationRepository) -> None:
        self._repository = json_repository

    def execute(self, filename: str) -> Formulation:
        """Load formulation.

        Args:
            filename: Filename to load

        Returns:
            Loaded formulation
        """
        return self._repository.load(filename)


class ExportFormulationUseCase:
    """Export formulation to Excel."""

    def __init__(
        self,
        calculator: NutrientCalculator,
        exporter: ExcelExporter,
    ) -> None:
        self._calculator = calculator
        self._exporter = exporter

    def execute(
        self,
        formulation: Formulation,
        output_path: Path | str,
    ) -> None:
        """Export formulation to Excel.

        Args:
            formulation: Formulation to export
            output_path: Output file path
        """
        totals = self._calculator.calculate_totals_per_100g(formulation)
        self._exporter.export_formulation(formulation, totals, output_path)


class AdjustFormulationUseCase:
    """Adjust formulation to target weight while respecting locks."""

    def __init__(self, formulation_service: FormulationService) -> None:
        self._service = formulation_service

    def execute(
        self,
        formulation: Formulation,
        target_weight_g: Decimal,
    ) -> None:
        """Adjust formulation to target weight.

        Args:
            formulation: Formulation to adjust (modified in-place)
            target_weight_g: Target total weight
        """
        self._service.adjust_to_target_weight(formulation, target_weight_g)
