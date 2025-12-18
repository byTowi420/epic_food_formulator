"""JSON persistence for formulations.

Handles saving and loading formulations to/from JSON files.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

from domain.exceptions import FormulationNotFoundError, InvalidFormulationFileError
from domain.models import Food, Formulation, Ingredient, Nutrient


class JSONFormulationRepository:
    """Repository for persisting formulations as JSON files."""

    def __init__(self, base_directory: str = "saves") -> None:
        """Initialize repository.

        Args:
            base_directory: Base directory for saving formulations
        """
        self._base_dir = Path(base_directory)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, formulation: Formulation, filename: str) -> Path:
        """Save formulation to JSON file.

        Args:
            formulation: Formulation to save
            filename: Filename (without path)

        Returns:
            Full path to saved file
        """
        file_path = self._base_dir / filename

        # Convert formulation to dict
        data = self._formulation_to_dict(formulation)

        # Write JSON
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return file_path

    def load(self, filename: str) -> Formulation:
        """Load formulation from JSON file.

        Args:
            filename: Filename (without path)

        Returns:
            Loaded formulation

        Raises:
            FormulationNotFoundError: If file doesn't exist
            InvalidFormulationFileError: If file is malformed
        """
        file_path = self._base_dir / filename

        if not file_path.exists():
            raise FormulationNotFoundError(f"Formulation file not found: {filename}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return self._dict_to_formulation(data)

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
            raise InvalidFormulationFileError(
                f"Invalid formulation file: {filename}"
            ) from exc

    def list_files(self) -> List[str]:
        """List all formulation JSON files.

        Returns:
            List of filenames
        """
        if not self._base_dir.exists():
            return []

        return sorted([f.name for f in self._base_dir.glob("*.json")])

    def delete(self, filename: str) -> None:
        """Delete a formulation file.

        Args:
            filename: Filename to delete

        Raises:
            FormulationNotFoundError: If file doesn't exist
        """
        file_path = self._base_dir / filename

        if not file_path.exists():
            raise FormulationNotFoundError(f"Formulation file not found: {filename}")

        file_path.unlink()

    def _formulation_to_dict(self, formulation: Formulation) -> Dict[str, Any]:
        """Convert Formulation to dictionary."""
        return {
            "name": formulation.name,
            "quantity_mode": formulation.quantity_mode,
            "ingredients": [
                {
                    "fdc_id": ing.food.fdc_id,
                    "description": ing.food.description,
                    "data_type": ing.food.data_type,
                    "brand_owner": ing.food.brand_owner,
                    "amount_g": str(ing.amount_g),
                    "locked": ing.locked,
                    "nutrients": [
                        {
                            "name": nut.name,
                            "unit": nut.unit,
                            "amount": str(nut.amount),
                            "nutrient_id": nut.nutrient_id,
                            "nutrient_number": nut.nutrient_number,
                        }
                        for nut in ing.food.nutrients
                    ],
                }
                for ing in formulation.ingredients
            ],
        }

    def _dict_to_formulation(self, data: Dict[str, Any]) -> Formulation:
        """Convert dictionary to Formulation."""
        formulation = Formulation(
            name=data["name"],
            quantity_mode=data.get("quantity_mode", "g"),
        )

        for ing_data in data.get("ingredients", []):
            nutrients = tuple(
                Nutrient(
                    name=n["name"],
                    unit=n["unit"],
                    amount=Decimal(str(n["amount"])),
                    nutrient_id=n.get("nutrient_id"),
                    nutrient_number=n.get("nutrient_number"),
                )
                for n in ing_data.get("nutrients", [])
            )

            food = Food(
                fdc_id=ing_data["fdc_id"],
                description=ing_data["description"],
                data_type=ing_data.get("data_type", ""),
                brand_owner=ing_data.get("brand_owner", ""),
                nutrients=nutrients,
            )

            ingredient = Ingredient(
                food=food,
                amount_g=Decimal(str(ing_data["amount_g"])),
                locked=ing_data.get("locked", False),
            )

            formulation.add_ingredient(ingredient)

        return formulation
