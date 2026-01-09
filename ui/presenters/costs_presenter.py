from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from domain.models import CurrencyRate, PackagingItem, ProcessCost
from domain.services import cost_service
from domain.services.unit_normalizer import convert_mass, mass_to_kg, normalize_mass_unit
from ui.presenters.formulation_presenter import FormulationPresenter


class CostsPresenter:
    """Presenter for costs tab operations."""

    def __init__(self, formulation_presenter: FormulationPresenter) -> None:
        self._formulation_presenter = formulation_presenter

    @property
    def formulation(self):
        return self._formulation_presenter.formulation

    def set_yield_percent(self, value: Decimal) -> tuple[bool, str | None]:
        if value <= 0 or value > 100:
            return False, "yield_range"
        self.formulation.yield_percent = value
        return True, None

    def get_yield_percent(self) -> Decimal:
        return self.formulation.yield_percent

    def get_currency_rates(self) -> List[CurrencyRate]:
        return list(self.formulation.currency_rates)

    def set_currency_rates(self, rates: List[CurrencyRate]) -> None:
        self.formulation.currency_rates = list(rates)
        ensure = getattr(self.formulation, "_ensure_currency_rates", None)
        if callable(ensure):
            ensure()

    def get_currency_symbols(self) -> List[str]:
        symbols: List[str] = []
        seen: set[str] = set()
        for rate in self.formulation.currency_rates:
            symbol = str(rate.symbol or "").strip()
            if not symbol or symbol in seen:
                continue
            symbols.append(symbol)
            seen.add(symbol)
        if "$" not in seen:
            symbols.insert(0, "$")
        return symbols

    def _to_decimal(self, value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            if isinstance(value, str):
                cleaned = value.strip().replace(",", ".")
                if cleaned == "":
                    return None
                return Decimal(cleaned)
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    def build_ingredient_rows(self, quantity_mode: str) -> List[Dict[str, Any]]:
        total_cost, _ = cost_service.total_ingredients_cost_batch_mn(self.formulation)
        rows: List[Dict[str, Any]] = []
        unit = self._formulation_presenter.current_mass_unit(quantity_mode)
        symbols = self.get_currency_symbols()
        for idx, ingredient in enumerate(self.formulation.ingredients):
            stored_symbol = str(ingredient.cost_currency_symbol or "").strip()
            if not stored_symbol:
                stored_symbol = "$"
                ingredient.cost_currency_symbol = stored_symbol
            currency_missing = stored_symbol not in symbols
            display_symbol = stored_symbol if not currency_missing else "$"
            cost_service.update_ingredient_cost_fields(
                ingredient, self.formulation.currency_rates
            )
            amount_display = convert_mass(ingredient.amount_g, "g", unit)
            cost_per_g = ingredient.cost_per_g_mn
            cost_batch = (
                cost_per_g * ingredient.amount_g if cost_per_g is not None else None
            )
            percent = (
                (cost_batch / total_cost * Decimal("100"))
                if cost_batch is not None and total_cost > 0
                else None
            )
            rows.append(
                {
                    "index": idx,
                    "description": ingredient.description,
                    "amount_g": ingredient.amount_g,
                    "amount_display": amount_display if amount_display is not None else ingredient.amount_g,
                    "unit": unit,
                    "cost_pack_amount": ingredient.cost_pack_amount,
                    "cost_pack_unit": ingredient.cost_pack_unit,
                    "cost_value": ingredient.cost_value,
                    "cost_currency_symbol": display_symbol,
                    "currency_missing": currency_missing,
                    "cost_per_g_mn": cost_per_g,
                    "cost_batch_mn": cost_batch,
                    "percent_of_ingredients": percent,
                }
            )
        return rows

    def update_ingredient_cost(
        self,
        index: int,
        *,
        cost_pack_amount: Any = None,
        cost_pack_unit: Any = None,
        cost_value: Any = None,
        cost_currency_symbol: Any = None,
    ) -> None:
        if index < 0 or index >= len(self.formulation.ingredients):
            return
        ingredient = self.formulation.ingredients[index]
        if cost_pack_amount is not None:
            ingredient.cost_pack_amount = self._to_decimal(cost_pack_amount)
        if cost_pack_unit is not None:
            ingredient.cost_pack_unit = str(cost_pack_unit).strip() or None
        if cost_value is not None:
            ingredient.cost_value = self._to_decimal(cost_value)
        if cost_currency_symbol is not None:
            ingredient.cost_currency_symbol = str(cost_currency_symbol).strip() or None
        cost_service.update_ingredient_cost_fields(
            ingredient, self.formulation.currency_rates
        )

    def build_process_rows(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        batch_mass_kg = mass_to_kg(self.formulation.total_weight, "g") or Decimal("0")

        def _to_hours(value: Any, unit: Any) -> Optional[Decimal]:
            amount = self._to_decimal(value)
            if amount is None or amount <= 0:
                return None
            unit_clean = str(unit or "").strip().lower()
            if unit_clean == "h":
                return amount
            if unit_clean == "min":
                return amount / Decimal("60")
            return None

        for idx, process in enumerate(self.formulation.process_costs):
            scale_type = str(process.scale_type or "").strip().upper()
            total_cost = cost_service.process_total_cost_mn(process, batch_mass_kg)
            time_total_h = None
            if scale_type == "FIXED":
                time_total_h = _to_hours(process.time_value, process.time_unit)
                if total_cost is None:
                    cost_h = self._to_decimal(process.cost_per_hour_mn)
                    if time_total_h is not None and cost_h is not None:
                        total_cost = time_total_h * cost_h
            elif scale_type == "VARIABLE_PER_KG":
                time_per_kg_h = _to_hours(process.time_per_kg_value, process.time_unit)
                if time_per_kg_h is not None:
                    time_total_h = time_per_kg_h * batch_mass_kg
                if total_cost is None and time_total_h is not None:
                    cost_h = self._to_decimal(process.cost_per_hour_mn)
                    if cost_h is not None:
                        total_cost = time_total_h * cost_h
            elif scale_type == "MIXED":
                setup_h = _to_hours(process.setup_time_value, process.setup_time_unit)
                time_per_kg_h = _to_hours(process.time_per_kg_value, process.time_unit)
                if setup_h is not None and time_per_kg_h is not None:
                    time_total_h = setup_h + time_per_kg_h * batch_mass_kg
                if total_cost is None and time_total_h is not None:
                    cost_h = self._to_decimal(process.cost_per_hour_mn)
                    if cost_h is not None:
                        total_cost = time_total_h * cost_h
            rows.append(
                {
                    "index": idx,
                    "name": process.name,
                    "scale_type": process.scale_type,
                    "setup_time_value": process.setup_time_value,
                    "setup_time_unit": process.setup_time_unit,
                    "time_per_kg_value": process.time_per_kg_value,
                    "time_unit": process.time_unit,
                    "time_value": process.time_value,
                    "time_total_h": time_total_h,
                    "cost_per_hour_mn": process.cost_per_hour_mn,
                    "total_cost_mn": total_cost,
                    "notes": process.notes,
                }
            )
        return rows

    def add_process(self) -> None:
        self.formulation.process_costs.append(
            ProcessCost(name="", scale_type="FIXED", time_unit="min", setup_time_unit="min")
        )

    def remove_process(self, index: int) -> None:
        if 0 <= index < len(self.formulation.process_costs):
            del self.formulation.process_costs[index]

    def update_process(
        self,
        index: int,
        *,
        name: Any = None,
        scale_type: Any = None,
        setup_time_value: Any = None,
        setup_time_unit: Any = None,
        time_per_kg_value: Any = None,
        time_unit: Any = None,
        time_value: Any = None,
        cost_per_hour_mn: Any = None,
        total_cost_mn: Any = None,
        notes: Any = None,
    ) -> None:
        if index < 0 or index >= len(self.formulation.process_costs):
            return
        process = self.formulation.process_costs[index]
        if name is not None:
            process.name = str(name)
        if scale_type is not None:
            process.scale_type = str(scale_type).strip().upper()
        if setup_time_value is not None:
            process.setup_time_value = self._to_decimal(setup_time_value)
        if setup_time_unit is not None:
            process.setup_time_unit = str(setup_time_unit).strip().lower() or None
        if time_per_kg_value is not None:
            process.time_per_kg_value = self._to_decimal(time_per_kg_value)
        if time_unit is not None:
            process.time_unit = str(time_unit).strip().lower() or None
        if time_value is not None:
            process.time_value = self._to_decimal(time_value)
        if cost_per_hour_mn is not None:
            process.cost_per_hour_mn = self._to_decimal(cost_per_hour_mn)
        if total_cost_mn is not None:
            process.total_cost_mn = self._to_decimal(total_cost_mn)
        if notes is not None:
            process.notes = str(notes)

    def build_packaging_rows(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for idx, item in enumerate(self.formulation.packaging_items):
            subtotal = item.quantity_per_pack * item.unit_cost_mn
            rows.append(
                {
                    "index": idx,
                    "name": item.name,
                    "quantity_per_pack": item.quantity_per_pack,
                    "unit_cost_mn": item.unit_cost_mn,
                    "subtotal_mn": subtotal,
                    "notes": item.notes,
                }
            )
        return rows

    def add_packaging_item(self) -> None:
        self.formulation.packaging_items.append(
            PackagingItem(name="", quantity_per_pack=Decimal("1"), unit_cost_mn=Decimal("0"))
        )

    def remove_packaging_item(self, index: int) -> None:
        if 0 <= index < len(self.formulation.packaging_items):
            del self.formulation.packaging_items[index]

    def update_packaging_item(
        self,
        index: int,
        *,
        name: Any = None,
        quantity_per_pack: Any = None,
        unit_cost_mn: Any = None,
        notes: Any = None,
    ) -> None:
        if index < 0 or index >= len(self.formulation.packaging_items):
            return
        item = self.formulation.packaging_items[index]
        if name is not None:
            item.name = str(name)
        if quantity_per_pack is not None:
            qty = self._to_decimal(quantity_per_pack)
            if qty is not None:
                item.quantity_per_pack = qty
        if unit_cost_mn is not None:
            cost = self._to_decimal(unit_cost_mn)
            if cost is not None:
                item.unit_cost_mn = cost
        if notes is not None:
            item.notes = str(notes)

    def summary(self) -> Dict[str, Decimal]:
        batch_mass_g = self.formulation.total_weight
        yield_percent = self.formulation.yield_percent
        sellable_mass_g = batch_mass_g * yield_percent / Decimal("100")
        ingredients_total, missing_ing = cost_service.total_ingredients_cost_batch_mn(
            self.formulation
        )
        processes_total, missing_proc = cost_service.total_process_cost_batch_mn(
            self.formulation
        )
        total_cost = ingredients_total + processes_total
        ingredient_comp = cost_service.ingredient_cost_completeness(self.formulation)
        process_comp = cost_service.process_cost_completeness(self.formulation)
        return {
            "batch_mass_g": batch_mass_g,
            "yield_percent": yield_percent,
            "sellable_mass_g": sellable_mass_g,
            "ingredients_total_mn": ingredients_total,
            "process_total_mn": processes_total,
            "total_cost_mn": total_cost,
            "ingredients_defined": ingredient_comp["defined"],
            "ingredients_missing": ingredient_comp["missing"],
            "ingredients_percent": ingredient_comp["percent"],
            "process_defined": process_comp["defined"],
            "process_missing": process_comp["missing"],
            "process_percent": process_comp["percent"],
            "missing_ingredients_count": Decimal(str(missing_ing)),
            "missing_process_count": Decimal(str(missing_proc)),
        }

    def unit_costs_for_target_mass(
        self, target_value: Any, target_unit: Any
    ) -> Dict[str, Decimal]:
        unit = normalize_mass_unit(target_unit) or target_unit or "g"
        return cost_service.unit_costs_for_target_mass(
            self.formulation, target_value, unit
        )
