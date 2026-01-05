"""Unit normalization and conversion helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

_MICRO_ALIASES = {"ug", "mcg", "µg", "μg", "æg"}

_MASS_UNIT_ALIASES = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "gramo": "g",
    "gramos": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "kilogramo": "kg",
    "kilogramos": "kg",
    "t": "ton",
    "tn": "ton",
    "ton": "ton",
    "tonne": "ton",
    "tonnes": "ton",
    "tonelada": "ton",
    "toneladas": "ton",
    "lb": "lb",
    "lbs": "lb",
    "libra": "lb",
    "libras": "lb",
    "pound": "lb",
    "pounds": "lb",
    "oz": "oz",
    "onza": "oz",
    "onzas": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "mg": "mg",
}

_MASS_UNIT_TO_G = {
    "μg": Decimal("0.000001"),
    "µg": Decimal("0.000001"),
    "mg": Decimal("0.001"),
    "g": Decimal("1"),
    "kg": Decimal("1000"),
    "ton": Decimal("1000000"),
    "lb": Decimal("453.59237"),
    "oz": Decimal("28.349523125"),
}

_FORMULATION_MASS_UNITS = {"g", "kg", "ton", "lb", "oz"}
_ENERGY_UNITS = {"kcal", "kj", "kjoule", "kilojoule", "kilojoules", "kJ"}
_KCAL_TO_KJ = Decimal("4.184")


def canonical_unit(unit: Optional[str]) -> str:
    """Normalize a unit string to a canonical form."""
    if not unit:
        return ""
    cleaned = str(unit).strip()
    if not cleaned:
        return ""

    lower = cleaned.lower()
    if lower in _MICRO_ALIASES:
        return "μg"
    if lower in {"kj", "kilojoule", "kilojoules"}:
        return "kJ"
    if lower in {"kcal", "kilocalorie", "kilocalories"}:
        return "kcal"
    if lower in {"iu"}:
        return "iu"
    if lower in _MASS_UNIT_ALIASES:
        return _MASS_UNIT_ALIASES[lower]
    return lower


def normalize_mass_unit(unit: Optional[str]) -> str:
    """Normalize mass units to canonical strings."""
    if not unit:
        return ""
    canonical = _MASS_UNIT_ALIASES.get(str(unit).strip().lower(), "")
    if canonical in _FORMULATION_MASS_UNITS:
        return canonical
    return ""


def convert_mass(value: Decimal | float, from_unit: str, to_unit: str) -> Decimal | None:
    """Convert a mass value between units."""
    source = canonical_unit(from_unit)
    target = canonical_unit(to_unit)
    if not source or not target:
        return None
    if source == target:
        return _to_decimal(value)
    if source not in _MASS_UNIT_TO_G or target not in _MASS_UNIT_TO_G:
        return None
    return _to_decimal(value) * _MASS_UNIT_TO_G[source] / _MASS_UNIT_TO_G[target]


def convert_amount(value: Decimal | float, from_unit: str, to_unit: str) -> Decimal | None:
    """Convert between compatible units (mass or energy)."""
    source = canonical_unit(from_unit)
    target = canonical_unit(to_unit)
    if not source or not target:
        return None
    if source == target:
        return _to_decimal(value)

    if source in _MASS_UNIT_TO_G and target in _MASS_UNIT_TO_G:
        return _to_decimal(value) * _MASS_UNIT_TO_G[source] / _MASS_UNIT_TO_G[target]

    if source in _ENERGY_UNITS and target in _ENERGY_UNITS:
        source_lower = source.lower()
        target_lower = target.lower()
        if source_lower == "kcal" and target_lower == "kj":
            return _to_decimal(value) * _KCAL_TO_KJ
        if source_lower == "kj" and target_lower == "kcal":
            return _to_decimal(value) / _KCAL_TO_KJ

    return None


def _to_decimal(value: Decimal | float) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
