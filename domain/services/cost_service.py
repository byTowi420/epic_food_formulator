from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from domain.models import Formulation, Ingredient, ProcessCost
from domain.services.number_parser import parse_user_number
from domain.services.unit_normalizer import mass_to_g, mass_to_kg, normalize_mass_unit


def _to_decimal(value: Any) -> Optional[Decimal]:
    return parse_user_number(value)


def _time_to_hours(value: Any, unit: Any) -> Optional[Decimal]:
    amount = _to_decimal(value)
    if amount is None or amount <= 0:
        return None
    unit_clean = str(unit or "").strip().lower()
    if unit_clean == "h":
        return amount
    if unit_clean == "min":
        return amount / Decimal("60")
    return None


def _build_rate_map(currency_rates: list[Any]) -> Dict[str, Decimal]:
    rates: Dict[str, Decimal] = {"$": Decimal("1")}
    for rate in currency_rates or []:
        symbol = str(getattr(rate, "symbol", "") or "").strip()
        if not symbol:
            continue
        if symbol == "$":
            rates["$"] = Decimal("1")
            continue
        rate_val = _to_decimal(getattr(rate, "rate_to_mn", None))
        if rate_val is None or rate_val <= 0:
            continue
        rates[symbol] = rate_val
    return rates


def build_rate_map(currency_rates: list[Any]) -> Dict[str, Decimal]:
    return _build_rate_map(currency_rates)


def convert_currency_to_mn(
    value: Any, symbol: Any, currency_rates: list[Any]
) -> Optional[Decimal]:
    amount = _to_decimal(value)
    if amount is None:
        return None
    currency = str(symbol or "").strip() or "$"
    rate = _build_rate_map(currency_rates).get(currency)
    if rate is None or rate <= 0:
        return None
    return amount * rate


def packaging_unit_cost_mn(item: Any, currency_rates: list[Any]) -> Optional[Decimal]:
    value = _to_decimal(getattr(item, "unit_cost_value", None))
    symbol = str(getattr(item, "unit_cost_currency_symbol", "") or "").strip()
    if value is not None:
        return convert_currency_to_mn(value, symbol, currency_rates)
    return _to_decimal(getattr(item, "unit_cost_mn", None))


def normalize_ingredient_cost_to_mn_per_g(
    pack_amount: Any,
    pack_unit: Any,
    cost_value: Any,
    currency_symbol: Any,
    currency_rates: list[Any],
) -> Optional[Decimal]:
    pack_amount_dec = _to_decimal(pack_amount)
    cost_value_dec = _to_decimal(cost_value)
    if pack_amount_dec is None or cost_value_dec is None:
        return None
    if pack_amount_dec <= 0 or cost_value_dec <= 0:
        return None

    unit = normalize_mass_unit(pack_unit) or ""
    if not unit:
        return None
    pack_amount_g = mass_to_g(pack_amount_dec, unit)
    if pack_amount_g is None or pack_amount_g <= 0:
        return None

    symbol = str(currency_symbol or "").strip()
    if not symbol:
        return None
    rate_map = _build_rate_map(currency_rates)
    rate = rate_map.get(symbol)
    if rate is None or rate <= 0:
        return None
    cost_mn = cost_value_dec * rate

    return cost_mn / pack_amount_g


def update_ingredient_cost_fields(
    ingredient: Ingredient, currency_rates: list[Any]
) -> None:
    pack_unit = normalize_mass_unit(ingredient.cost_pack_unit or "") or None

    ingredient.cost_pack_unit = pack_unit
    ingredient.cost_currency_symbol = (
        str(ingredient.cost_currency_symbol or "").strip() or None
    )

    ingredient.cost_per_g_mn = normalize_ingredient_cost_to_mn_per_g(
        ingredient.cost_pack_amount,
        ingredient.cost_pack_unit,
        ingredient.cost_value,
        ingredient.cost_currency_symbol,
        currency_rates,
    )


def total_ingredients_cost_batch_mn(formulation: Formulation) -> tuple[Decimal, int]:
    total = Decimal("0")
    missing = 0
    for ingredient in formulation.ingredients:
        update_ingredient_cost_fields(ingredient, formulation.currency_rates)
        if ingredient.cost_per_g_mn is None:
            missing += 1
            continue
        total += ingredient.cost_per_g_mn * ingredient.amount_g
    return total, missing


def _resolve_fixed_process(
    process: ProcessCost,
) -> Dict[str, Optional[Decimal]]:
    time_h = _time_to_hours(process.time_value, process.time_unit)
    cost_h = _to_decimal(process.cost_per_hour_mn)
    total = _to_decimal(process.total_cost_mn)

    present = [time_h is not None, cost_h is not None, total is not None]
    if present.count(True) >= 2:
        if total is None and time_h is not None and cost_h is not None:
            total = time_h * cost_h
        elif cost_h is None and time_h is not None and total is not None and time_h > 0:
            cost_h = total / time_h
        elif time_h is None and cost_h is not None and total is not None and cost_h > 0:
            time_h = total / cost_h

    return {
        "time_h": time_h,
        "cost_per_hour": cost_h,
        "total": total,
    }


def process_total_cost_mn(process: ProcessCost, batch_mass_kg: Decimal) -> Optional[Decimal]:
    scale_type = str(process.scale_type or "").strip().upper()
    if scale_type == "FIXED":
        resolved = _resolve_fixed_process(process)
        return resolved["total"]
    if scale_type == "VARIABLE_PER_KG":
        time_per_kg_h = _time_to_hours(process.time_per_kg_value, process.time_unit)
        cost_h = _to_decimal(process.cost_per_hour_mn)
        if time_per_kg_h is None or cost_h is None:
            return None
        return time_per_kg_h * batch_mass_kg * cost_h
    if scale_type == "MIXED":
        setup_h = _time_to_hours(process.setup_time_value, process.setup_time_unit)
        time_per_kg_h = _time_to_hours(process.time_per_kg_value, process.time_unit)
        cost_h = _to_decimal(process.cost_per_hour_mn)
        if setup_h is None or time_per_kg_h is None or cost_h is None:
            return None
        total_time_h = setup_h + (time_per_kg_h * batch_mass_kg)
        return total_time_h * cost_h
    return None


def total_process_cost_batch_mn(formulation: Formulation) -> tuple[Decimal, int]:
    total = Decimal("0")
    incomplete = 0
    batch_mass_kg = mass_to_kg(formulation.total_weight, "g") or Decimal("0")
    for process in formulation.process_costs:
        cost = process_total_cost_mn(process, batch_mass_kg)
        if cost is None:
            incomplete += 1
            continue
        total += cost
    return total, incomplete


def total_batch_cost_mn(formulation: Formulation) -> Decimal:
    ingredients_total, _ = total_ingredients_cost_batch_mn(formulation)
    processes_total, _ = total_process_cost_batch_mn(formulation)
    return ingredients_total + processes_total


def ingredient_cost_completeness(formulation: Formulation) -> Dict[str, Decimal]:
    total = Decimal(str(len(formulation.ingredients)))
    if total <= 0:
        return {"defined": Decimal("0"), "missing": Decimal("0"), "percent": Decimal("0")}
    defined = Decimal("0")
    missing = Decimal("0")
    for ingredient in formulation.ingredients:
        update_ingredient_cost_fields(ingredient, formulation.currency_rates)
        if ingredient.cost_per_g_mn is None:
            missing += 1
        else:
            defined += 1
    percent = (defined / total) * Decimal("100")
    return {"defined": defined, "missing": missing, "percent": percent}


def process_cost_completeness(formulation: Formulation) -> Dict[str, Decimal]:
    total = Decimal(str(len(formulation.process_costs)))
    if total <= 0:
        return {"defined": Decimal("0"), "missing": Decimal("0"), "percent": Decimal("0")}
    defined = Decimal("0")
    missing = Decimal("0")
    batch_mass_kg = mass_to_kg(formulation.total_weight, "g") or Decimal("0")
    for process in formulation.process_costs:
        cost = process_total_cost_mn(process, batch_mass_kg)
        if cost is None:
            missing += 1
        else:
            defined += 1
    percent = (defined / total) * Decimal("100")
    return {"defined": defined, "missing": missing, "percent": percent}


def unit_costs_for_target_mass(
    formulation: Formulation,
    target_mass_value: Any,
    target_mass_unit: Any,
) -> Dict[str, Decimal]:
    batch_mass_g = formulation.total_weight
    target_mass_g = mass_to_g(_to_decimal(target_mass_value) or Decimal("0"), target_mass_unit or "") or Decimal("0")
    if target_mass_g <= 0:
        target_mass_g = Decimal("0")

    yield_percent = _to_decimal(formulation.yield_percent) or Decimal("100")
    if yield_percent <= 0:
        yield_percent = Decimal("0")
    if yield_percent > 100:
        yield_percent = Decimal("100")
    sellable_mass_g = (batch_mass_g * yield_percent) / Decimal("100")

    units_count = Decimal("0")
    if target_mass_g > 0 and sellable_mass_g > 0:
        units_count = sellable_mass_g / target_mass_g

    ingredients_total, _ = total_ingredients_cost_batch_mn(formulation)
    processes_total, _ = total_process_cost_batch_mn(formulation)

    ingredients_cost_per_target = (
        ingredients_total / units_count if units_count > 0 else Decimal("0")
    )
    process_cost_per_target = (
        processes_total / units_count if units_count > 0 else Decimal("0")
    )
    total_cost_per_target = ingredients_cost_per_target + process_cost_per_target

    packaging_cost = Decimal("0")
    for item in formulation.packaging_items:
        qty = _to_decimal(item.quantity_per_pack) or Decimal("0")
        unit_cost = packaging_unit_cost_mn(item, formulation.currency_rates)
        if unit_cost is None:
            unit_cost = Decimal("0")
        packaging_cost += qty * unit_cost

    total_pack_cost = total_cost_per_target + packaging_cost

    return {
        "batch_mass_g": batch_mass_g,
        "sellable_mass_g": sellable_mass_g,
        "target_mass_g": target_mass_g,
        "ingredients_cost_per_target_mn": ingredients_cost_per_target,
        "process_cost_per_target_mn": process_cost_per_target,
        "process_cost_per_unit": process_cost_per_target,
        "total_cost_per_target_mn": total_cost_per_target,
        "packaging_cost_per_pack_mn": packaging_cost,
        "total_pack_cost_mn": total_pack_cost,
        "units_count": units_count,
    }
