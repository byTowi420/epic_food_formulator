"""Domain models.

Core business entities that represent the problem domain.
These models are framework-agnostic and contain only business logic.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class Nutrient:
    """A nutrient with its name, unit, and amount.

    Immutable value object representing nutritional information.
    """

    name: str
    unit: str
    amount: Decimal
    nutrient_id: Optional[int] = None
    nutrient_number: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate nutrient data."""
        if not self.name:
            raise ValueError("Nutrient name cannot be empty")
        if not self.unit:
            raise ValueError("Nutrient unit cannot be empty")
        if self.amount < 0:
            raise ValueError(f"Nutrient amount cannot be negative: {self.amount}")

    def scale(self, factor: Decimal) -> "Nutrient":
        """Return a new Nutrient scaled by the given factor."""
        return Nutrient(
            name=self.name,
            unit=self.unit,
            amount=self.amount * factor,
            nutrient_id=self.nutrient_id,
            nutrient_number=self.nutrient_number,
        )


@dataclass(frozen=True)
class Food:
    """A food item from the USDA database.

    Immutable value object representing food data.
    """

    fdc_id: int
    description: str
    data_type: str
    nutrients: tuple[Nutrient, ...] = field(default_factory=tuple)
    brand_owner: str = ""

    def __post_init__(self) -> None:
        """Validate food data."""
        data_type = (self.data_type or "").strip().lower()
        if self.fdc_id <= 0 and data_type != "manual":
            raise ValueError(f"Invalid FDC ID: {self.fdc_id}")
        if not self.description:
            raise ValueError("Food description cannot be empty")
        if not self.data_type:
            raise ValueError("Food data type cannot be empty")

    def get_nutrient(self, name: str) -> Optional[Nutrient]:
        """Get nutrient by name (case-insensitive)."""
        name_lower = name.lower()
        for nutrient in self.nutrients:
            if nutrient.name.lower() == name_lower:
                return nutrient
        return None

    def has_nutrient(self, name: str) -> bool:
        """Check if food has a specific nutrient."""
        return self.get_nutrient(name) is not None


@dataclass
class Ingredient:
    """An ingredient in a formulation with its quantity.

    Mutable because amounts change during formulation adjustments.
    """

    food: Food
    amount_g: Decimal
    locked: bool = False
    cost_pack_amount: Optional[Decimal] = None
    cost_pack_unit: Optional[str] = None
    cost_value: Optional[Decimal] = None
    cost_currency_symbol: Optional[str] = None
    cost_per_g_mn: Optional[Decimal] = None

    def __post_init__(self) -> None:
        """Validate ingredient data."""
        if self.amount_g < 0:
            raise ValueError(f"Ingredient amount cannot be negative: {self.amount_g}")

    @property
    def fdc_id(self) -> int:
        """Convenience accessor for food FDC ID."""
        return self.food.fdc_id

    @property
    def description(self) -> str:
        """Convenience accessor for food description."""
        return self.food.description

    def calculate_percentage(self, total_weight: Decimal) -> Decimal:
        """Calculate percentage of total formulation weight."""
        if total_weight == 0:
            return Decimal("0")
        return (self.amount_g / total_weight) * Decimal("100")

    def get_nutrient_amount(self, nutrient_name: str) -> Decimal:
        """Get scaled nutrient amount for this ingredient's quantity.

        Returns nutrient amount per 100g scaled to ingredient amount.
        """
        nutrient = self.food.get_nutrient(nutrient_name)
        if nutrient is None:
            return Decimal("0")

        # USDA nutrients are per 100g, scale to actual ingredient amount
        scale_factor = self.amount_g / Decimal("100")
        return nutrient.amount * scale_factor


@dataclass
class ProcessCost:
    name: str
    scale_type: str  # "FIXED", "VARIABLE_PER_KG", "MIXED"
    time_value: Optional[Decimal] = None
    time_unit: Optional[str] = None  # "min" or "h"
    cost_per_hour_mn: Optional[Decimal] = None
    total_cost_mn: Optional[Decimal] = None
    setup_time_value: Optional[Decimal] = None
    setup_time_unit: Optional[str] = None
    time_per_kg_value: Optional[Decimal] = None
    notes: Optional[str] = None


@dataclass
class PackagingItem:
    name: str
    quantity_per_pack: Decimal
    unit_cost_mn: Decimal
    notes: Optional[str] = None


@dataclass
class CurrencyRate:
    name: str
    symbol: str
    rate_to_mn: Decimal


def _default_currency_rates() -> list[CurrencyRate]:
    return [CurrencyRate(name="Moneda Nacional", symbol="$", rate_to_mn=Decimal("1"))]


@dataclass
class Formulation:
    """A formulation containing multiple ingredients.

    Represents a recipe or product formula.
    """

    name: str
    ingredients: list[Ingredient] = field(default_factory=list)
    quantity_mode: str = "g"  # "g" or "%"
    yield_percent: Decimal = Decimal("100")
    process_costs: list[ProcessCost] = field(default_factory=list)
    packaging_items: list[PackagingItem] = field(default_factory=list)
    currency_rates: list[CurrencyRate] = field(default_factory=_default_currency_rates)

    def __post_init__(self) -> None:
        """Validate formulation data."""
        if not self.name:
            raise ValueError("Formulation name cannot be empty")
        if self.quantity_mode not in ("g", "%"):
            raise ValueError(f"Invalid quantity mode: {self.quantity_mode}")
        if self.yield_percent <= 0 or self.yield_percent > Decimal("100"):
            self.yield_percent = Decimal("100")
        self._ensure_currency_rates()

    def _ensure_currency_rates(self) -> None:
        seen: set[str] = set()
        cleaned: list[CurrencyRate] = []
        for rate in self.currency_rates:
            symbol = (rate.symbol or "").strip()
            if not symbol:
                continue
            if symbol == "$":
                rate.name = "Moneda Nacional"
                rate.symbol = "$"
                rate.rate_to_mn = Decimal("1")
            if symbol in seen:
                continue
            cleaned.append(rate)
            seen.add(symbol)
        if "$" not in seen:
            cleaned.insert(0, CurrencyRate(name="Moneda Nacional", symbol="$", rate_to_mn=Decimal("1")))
        self.currency_rates = cleaned

    @property
    def total_weight(self) -> Decimal:
        """Calculate total weight of all ingredients in grams."""
        return sum((ing.amount_g for ing in self.ingredients), Decimal("0"))

    @property
    def ingredient_count(self) -> int:
        """Get number of ingredients."""
        return len(self.ingredients)

    def add_ingredient(self, ingredient: Ingredient) -> None:
        """Add an ingredient to the formulation."""
        self.ingredients.append(ingredient)

    def remove_ingredient(self, index: int) -> None:
        """Remove ingredient at the given index."""
        if 0 <= index < len(self.ingredients):
            del self.ingredients[index]
        else:
            raise IndexError(f"Invalid ingredient index: {index}")

    def get_ingredient(self, index: int) -> Ingredient:
        """Get ingredient at the given index."""
        if 0 <= index < len(self.ingredients):
            return self.ingredients[index]
        raise IndexError(f"Invalid ingredient index: {index}")

    def get_locked_ingredients(self) -> list[tuple[int, Ingredient]]:
        """Get all locked ingredients with their indices."""
        return [(i, ing) for i, ing in enumerate(self.ingredients) if ing.locked]

    def get_unlocked_ingredients(self) -> list[tuple[int, Ingredient]]:
        """Get all unlocked ingredients with their indices."""
        return [(i, ing) for i, ing in enumerate(self.ingredients) if not ing.locked]

    def get_total_locked_weight(self) -> Decimal:
        """Get total weight of locked ingredients."""
        return sum(
            (ing.amount_g for ing in self.ingredients if ing.locked),
            Decimal("0"),
        )

    def clear(self) -> None:
        """Remove all ingredients."""
        self.ingredients.clear()

    def is_empty(self) -> bool:
        """Check if formulation has no ingredients."""
        return len(self.ingredients) == 0
