"""Dependency Injection container.

Provides centralized dependency management for the application.
"""

import os
from typing import Optional

from application.use_cases import (
    AddIngredientUseCase,
    AdjustFormulationUseCase,
    CalculateTotalsUseCase,
    ExportFormulationUseCase,
    LoadFormulationUseCase,
    SaveFormulationUseCase,
    SearchFoodsUseCase,
)
from config.constants import SAVES_DIRECTORY
from domain.services.formulation_service import FormulationService
from domain.services.nutrient_calculator import NutrientCalculator
from infrastructure.api.cache import Cache, InMemoryCache
from infrastructure.api.usda_repository import FoodRepository, USDAFoodRepository
from infrastructure.persistence.excel_exporter import ExcelExporter
from infrastructure.persistence.formulation_importer import FormulationImportService
from infrastructure.persistence.json_repository import JSONFormulationRepository


class Container:
    """Dependency injection container.

    Provides singleton instances of services and use cases.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache: Optional[Cache] = None,
    ) -> None:
        """Initialize container.

        Args:
            api_key: USDA API key (if None, reads from environment)
            cache: Cache implementation (if None, uses InMemoryCache)
        """
        self._api_key = api_key or os.getenv("USDA_API_KEY")
        self._cache = cache if cache is not None else InMemoryCache()

        # Lazy-initialized singletons
        self._food_repository: Optional[FoodRepository] = None
        self._json_repository: Optional[JSONFormulationRepository] = None
        self._excel_exporter: Optional[ExcelExporter] = None
        self._formulation_importer: Optional[FormulationImportService] = None

        self._nutrient_calculator: Optional[NutrientCalculator] = None
        self._formulation_service: Optional[FormulationService] = None

        self._search_foods_use_case: Optional[SearchFoodsUseCase] = None
        self._add_ingredient_use_case: Optional[AddIngredientUseCase] = None
        self._calculate_totals_use_case: Optional[CalculateTotalsUseCase] = None
        self._save_formulation_use_case: Optional[SaveFormulationUseCase] = None
        self._load_formulation_use_case: Optional[LoadFormulationUseCase] = None
        self._export_formulation_use_case: Optional[ExportFormulationUseCase] = None
        self._adjust_formulation_use_case: Optional[AdjustFormulationUseCase] = None

    # Infrastructure
    @property
    def food_repository(self) -> FoodRepository:
        """Get USDA food repository."""
        if self._food_repository is None:
            self._food_repository = USDAFoodRepository(
                api_key=self._api_key,
                cache=self._cache,
            )
        return self._food_repository

    @property
    def json_repository(self) -> JSONFormulationRepository:
        """Get JSON formulation repository."""
        if self._json_repository is None:
            self._json_repository = JSONFormulationRepository(
                base_directory=SAVES_DIRECTORY
            )
        return self._json_repository

    @property
    def excel_exporter(self) -> ExcelExporter:
        """Get Excel exporter."""
        if self._excel_exporter is None:
            self._excel_exporter = ExcelExporter()
        return self._excel_exporter

    @property
    def formulation_importer(self) -> FormulationImportService:
        """Get formulation import service."""
        if self._formulation_importer is None:
            self._formulation_importer = FormulationImportService()
        return self._formulation_importer

    # Domain Services
    @property
    def nutrient_calculator(self) -> NutrientCalculator:
        """Get nutrient calculator service."""
        if self._nutrient_calculator is None:
            self._nutrient_calculator = NutrientCalculator()
        return self._nutrient_calculator

    @property
    def formulation_service(self) -> FormulationService:
        """Get formulation service."""
        if self._formulation_service is None:
            self._formulation_service = FormulationService()
        return self._formulation_service

    # Use Cases
    @property
    def search_foods(self) -> SearchFoodsUseCase:
        """Get search foods use case."""
        if self._search_foods_use_case is None:
            self._search_foods_use_case = SearchFoodsUseCase(self.food_repository)
        return self._search_foods_use_case

    @property
    def add_ingredient(self) -> AddIngredientUseCase:
        """Get add ingredient use case."""
        if self._add_ingredient_use_case is None:
            self._add_ingredient_use_case = AddIngredientUseCase(
                food_repository=self.food_repository,
                formulation_service=self.formulation_service,
            )
        return self._add_ingredient_use_case

    @property
    def calculate_totals(self) -> CalculateTotalsUseCase:
        """Get calculate totals use case."""
        if self._calculate_totals_use_case is None:
            self._calculate_totals_use_case = CalculateTotalsUseCase(self.nutrient_calculator)
        return self._calculate_totals_use_case

    @property
    def save_formulation(self) -> SaveFormulationUseCase:
        """Get save formulation use case."""
        if self._save_formulation_use_case is None:
            self._save_formulation_use_case = SaveFormulationUseCase(self.json_repository)
        return self._save_formulation_use_case

    @property
    def load_formulation(self) -> LoadFormulationUseCase:
        """Get load formulation use case."""
        if self._load_formulation_use_case is None:
            self._load_formulation_use_case = LoadFormulationUseCase(self.json_repository)
        return self._load_formulation_use_case

    @property
    def export_formulation(self) -> ExportFormulationUseCase:
        """Get export formulation use case."""
        if self._export_formulation_use_case is None:
            self._export_formulation_use_case = ExportFormulationUseCase(
                calculator=self.nutrient_calculator,
                exporter=self.excel_exporter,
            )
        return self._export_formulation_use_case

    @property
    def adjust_formulation(self) -> AdjustFormulationUseCase:
        """Get adjust formulation use case."""
        if self._adjust_formulation_use_case is None:
            self._adjust_formulation_use_case = AdjustFormulationUseCase(
                self.formulation_service
            )
        return self._adjust_formulation_use_case
