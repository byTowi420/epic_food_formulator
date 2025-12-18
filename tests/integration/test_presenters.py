"""Integration tests for presenters.

Tests presenters with real use cases (but mocked infrastructure where needed).
"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from domain.models import Food, Formulation, Ingredient, Nutrient
from ui.presenters.formulation_presenter import FormulationPresenter
from ui.presenters.search_presenter import SearchPresenter


class TestFormulationPresenter:
    """Test FormulationPresenter integration."""

    @pytest.fixture
    def presenter(self):
        """Create presenter instance."""
        return FormulationPresenter()

    def test_initial_state(self, presenter):
        """Test presenter initial state."""
        assert presenter.get_ingredient_count() == 0
        assert presenter.get_total_weight() == 0.0
        assert presenter.formulation_name == "New Formulation"

    def test_add_ingredient_integration(self, presenter):
        """Test adding ingredient through presenter (mocked API)."""
        # Mock the USDA API call
        mock_food_data = {
            "fdcId": 12345,
            "description": "Test Food",
            "dataType": "Foundation",
            "brandOwner": "",
            "foodNutrients": [
                {
                    "nutrient": {
                        "name": "Protein",
                        "unitName": "g",
                        "id": 1,
                        "number": "203",
                    },
                    "amount": 20.0,
                }
            ],
        }

        with patch.object(
            presenter._container.food_repository,
            "get_by_id",
            return_value=mock_food_data,
        ):
            ui_item = presenter.add_ingredient(fdc_id=12345, amount_g=150.0)

            assert ui_item["fdc_id"] == 12345
            assert ui_item["description"] == "Test Food"
            assert ui_item["amount_g"] == 150.0
            assert presenter.get_ingredient_count() == 1
            assert presenter.get_total_weight() == 150.0

    def test_calculate_totals(self, presenter):
        """Test calculating totals through presenter."""
        # Manually add ingredient to domain model
        food = Food(
            fdc_id=1,
            description="Food",
            data_type="Foundation",
            nutrients=(Nutrient(name="Protein", unit="g", amount=Decimal("20")),),
        )
        ingredient = Ingredient(food=food, amount_g=Decimal("100"))
        presenter._formulation.add_ingredient(ingredient)

        totals = presenter.calculate_totals()

        assert "Protein" in totals
        assert totals["Protein"]["amount"] == pytest.approx(20.0)

    def test_toggle_lock(self, presenter):
        """Test toggling ingredient lock."""
        food = Food(
            fdc_id=1,
            description="Food",
            data_type="Foundation",
        )
        ingredient = Ingredient(food=food, amount_g=Decimal("100"))
        presenter._formulation.add_ingredient(ingredient)

        # Initially not locked
        assert not presenter._formulation.ingredients[0].locked

        # Toggle on
        is_locked = presenter.toggle_lock(0)
        assert is_locked is True
        assert presenter._formulation.ingredients[0].locked is True

        # Toggle off
        is_locked = presenter.toggle_lock(0)
        assert is_locked is False

    def test_update_amount(self, presenter):
        """Test updating ingredient amount."""
        food = Food(
            fdc_id=1,
            description="Food",
            data_type="Foundation",
        )
        ingredient = Ingredient(food=food, amount_g=Decimal("100"))
        presenter._formulation.add_ingredient(ingredient)

        presenter.update_ingredient_amount(0, 200.0)

        assert presenter._formulation.ingredients[0].amount_g == Decimal("200")
        assert presenter.get_total_weight() == 200.0

    def test_normalize_to_100g(self, presenter):
        """Test normalizing formulation to 100g."""
        food = Food(
            fdc_id=1,
            description="Food",
            data_type="Foundation",
        )
        ingredient = Ingredient(food=food, amount_g=Decimal("250"))
        presenter._formulation.add_ingredient(ingredient)

        presenter.normalize_to_100g()

        assert presenter.get_total_weight() == pytest.approx(100.0)

    def test_get_ui_items(self, presenter):
        """Test getting UI items."""
        food = Food(
            fdc_id=1,
            description="Test Food",
            data_type="Foundation",
        )
        ingredient = Ingredient(food=food, amount_g=Decimal("150"))
        presenter._formulation.add_ingredient(ingredient)

        ui_items = presenter.get_ui_items()

        assert len(ui_items) == 1
        assert ui_items[0]["fdc_id"] == 1
        assert ui_items[0]["description"] == "Test Food"
        assert ui_items[0]["amount_g"] == 150.0

    def test_clear(self, presenter):
        """Test clearing formulation."""
        food = Food(fdc_id=1, description="Food", data_type="Foundation")
        ingredient = Ingredient(food=food, amount_g=Decimal("100"))
        presenter._formulation.add_ingredient(ingredient)

        presenter.clear()

        assert presenter.get_ingredient_count() == 0
        assert presenter.get_total_weight() == 0.0


class TestSearchPresenter:
    """Test SearchPresenter integration."""

    @pytest.fixture
    def presenter(self):
        """Create presenter instance."""
        return SearchPresenter()

    def test_initial_state(self, presenter):
        """Test presenter initial state."""
        assert presenter.get_last_query() == ""
        assert presenter.get_result_count() == 0

    def test_search_integration(self, presenter):
        """Test search through presenter (mocked API)."""
        mock_results = [
            {
                "fdcId": 1,
                "description": "Apple",
                "brandOwner": "",
                "dataType": "Foundation",
            },
            {
                "fdcId": 2,
                "description": "Banana",
                "brandOwner": "",
                "dataType": "Foundation",
            },
        ]

        with patch.object(
            presenter._container.food_repository,
            "search",
            return_value=mock_results,
        ):
            results = presenter.search("fruit", page_size=10)

            assert len(results) == 2
            assert results[0]["fdcId"] == 1
            assert results[1]["description"] == "Banana"
            assert presenter.get_last_query() == "fruit"
            assert presenter.get_result_count() == 2

    def test_get_last_results(self, presenter):
        """Test retrieving last results."""
        mock_results = [
            {"fdcId": 1, "description": "Test", "brandOwner": "", "dataType": "Foundation"}
        ]

        with patch.object(
            presenter._container.food_repository,
            "search",
            return_value=mock_results,
        ):
            presenter.search("test")
            last = presenter.get_last_results()

            assert last == mock_results
