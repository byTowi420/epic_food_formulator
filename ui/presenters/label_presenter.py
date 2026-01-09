"""Label presenter - shared label mapping helpers."""

from __future__ import annotations

import math
import re
from fractions import Fraction
from typing import Any, Dict, List

from domain.services.unit_normalizer import canonical_unit, convert_amount
from domain.services.nutrient_normalizer import canonical_alias_name


class LabelPresenter:
    """Presenter for label helpers shared across the UI."""

    def build_base_label_nutrients(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "Energia",
                "type": "energy",
                "kcal": 0.0,
                "kj": 0.0,
                "vd": None,
                "vd_reference": 2000.0,
            },
            {
                "name": "Carbohidratos",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 300.0,
                "carb_parent": True,
            },
            {
                "name": "Azúcares",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "carb_child": True,
                "carb_breakdown_only": True,
            },
            {
                "name": "Polialcoholes",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "carb_child": True,
                "carb_breakdown_only": True,
            },
            {
                "name": "Almidón",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "carb_child": True,
                "carb_breakdown_only": True,
            },
            {
                "name": "Polidextrosas",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "carb_child": True,
                "carb_breakdown_only": True,
            },
            {
                "name": "Proteinas",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 75.0,
            },
            {
                "name": "Grasas totales",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 55.0,
                "fat_parent": True,
            },
            {
                "name": "Grasas saturadas",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 22.0,
                "fat_child": True,
            },
            {
                "name": "Grasas monoinsaturadas",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "fat_child": True,
                "fat_breakdown_only": True,
            },
            {
                "name": "Grasas poliinsaturadas",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "fat_child": True,
                "fat_breakdown_only": True,
            },
            {
                "name": "Grasas trans",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "fat_child": True,
            },
            {
                "name": "Colesterol",
                "unit": "mg",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "fat_child": True,
                "fat_breakdown_only": True,
            },
            {
                "name": "Fibra alimentaria",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 25.0,
            },
            {
                "name": "Sodio",
                "unit": "mg",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 2400.0,
            },
        ]

    def build_additional_nutrients(self) -> List[Dict[str, Any]]:
        return [
            {"name": "Vitamina A", "unit": "μg", "vd_reference": 600.0, "ref": "(2)"},
            {"name": "Vitamina D", "unit": "μg", "vd_reference": 5.0, "ref": "(2)"},
            {"name": "Vitamina C", "unit": "mg", "vd_reference": 45.0, "ref": "(2)"},
            {"name": "Vitamina E", "unit": "mg", "vd_reference": 10.0, "ref": "(2)"},
            {"name": "Tiamina", "unit": "mg", "vd_reference": 1.2, "ref": "(2)"},
            {"name": "Riboflavina", "unit": "mg", "vd_reference": 1.3, "ref": "(2)"},
            {"name": "Niacina", "unit": "mg", "vd_reference": 16.0, "ref": "(2)"},
            {"name": "Vitamina B6", "unit": "mg", "vd_reference": 1.3, "ref": "(2)"},
            {"name": "Acido fólico", "unit": "μg", "vd_reference": 400.0, "ref": "(2)"},
            {"name": "Vitaminia B12", "unit": "μg", "vd_reference": 2.4, "ref": "(2)"},
            {"name": "Biotina", "unit": "μg", "vd_reference": 30.0, "ref": "(2)"},
            {"name": "Acido pantoténico", "unit": "mg", "vd_reference": 5.0, "ref": "(2)"},
            {"name": "Calcio", "unit": "mg", "vd_reference": 1000.0, "ref": "(2)"},
            {"name": "Hierro", "unit": "mg", "vd_reference": 14.0, "ref": "(2) (*)"},
            {"name": "Magnesio", "unit": "mg", "vd_reference": 260.0, "ref": "(2)"},
            {"name": "Zinc", "unit": "mg", "vd_reference": 7.0, "ref": "(2) (**)"},
            {"name": "Yodo", "unit": "μg", "vd_reference": 130.0, "ref": "(2)"},
            {"name": "Vitamina K", "unit": "μg", "vd_reference": 65.0, "ref": "(2)"},
            {"name": "Fósforo", "unit": "mg", "vd_reference": 700.0, "ref": "(3)"},
            {"name": "Flúor", "unit": "mg", "vd_reference": 4.0, "ref": "(3)"},
            {"name": "Cobre", "unit": "mg", "vd_reference": 0.9, "ref": "(3)"},
            {"name": "Selenio", "unit": "μg", "vd_reference": 34.0, "ref": "(2)"},
            {"name": "Molibdeno", "unit": "μg", "vd_reference": 45.0, "ref": "(3)"},
            {"name": "Cromo", "unit": "μg", "vd_reference": 35.0, "ref": "(3)"},
            {"name": "Manganeso", "unit": "mg", "vd_reference": 2.3, "ref": "(3)"},
            {"name": "Colina", "unit": "mg", "vd_reference": 550.0, "ref": "(3)"},
        ]

    def build_household_measure_options(self) -> List[tuple[str, int | None]]:
        return [
            ("Taza de té", 200),
            ("Vaso", 200),
            ("Cuchara de sopa", 10),
            ("Cuchara de té", 5),
            ("Plato hondo", 250),
            ("Unidad", None),
            ("Otro", None),
        ]

    def build_no_significant_order(self) -> List[str]:
        return [
            "Energia",
            "Carbohidratos",
            "Proteinas",
            "Grasas totales",
            "Grasas saturadas",
            "Grasas trans",
            "Fibra alimentaria",
            "Sodio",
        ]

    def build_nutrient_usda_map(self) -> Dict[str, str]:
        return {
            "Energia": "Energy (kcal)",
            "Carbohidratos": "Carbohydrate, by difference (g)",
            "Azúcares": "Sugars, Total (g)",
            "Polialcoholes": "Sugar alcohol (g)",
            "Almidón": "Starch (g)",
            "Polidextrosas": "Polydextrose (g)",
            "Proteinas": "Protein (g)",
            "Grasas totales": "Total lipid (fat) (g)",
            "Grasas saturadas": "Fatty acids, total saturated (g)",
            "Grasas monoinsaturadas": "Fatty acids, total monounsaturated (g)",
            "Grasas poliinsaturadas": "Fatty acids, total polyunsaturated (g)",
            "Grasas trans": "Fatty acids, total trans (g)",
            "Colesterol": "Cholesterol (mg)",
            "Fibra alimentaria": "Fiber, total dietary (g)",
            "Sodio": "Sodium, Na (mg)",
            "Vitamina A": "Vitamin A, RAE (μg)",
            "Vitamina D": "Vitamin D (D2 + D3) (μg)",
            "Vitamina C": "Vitamin C, total ascorbic acid (mg)",
            "Vitamina E": "Vitamin E (alpha-tocopherol) (mg)",
            "Tiamina": "Thiamin (mg)",
            "Riboflavina": "Riboflavin (mg)",
            "Niacina": "Niacin (mg)",
            "Vitamina B6": "Vitamin B-6 (mg)",
            "Acido fólico": "Folate, total (μg)",
            "Vitaminia B12": "Vitamin B-12 (μg)",
            "Biotina": "Biotin (μg)",
            "Acido pantoténico": "Pantothenic acid (mg)",
            "Calcio": "Calcium, Ca (mg)",
            "Hierro": "Iron, Fe (mg)",
            "Magnesio": "Magnesium, Mg (mg)",
            "Zinc": "Zinc, Zn (mg)",
            "Yodo": "Iodine, I (μg)",
            "Vitamina K": "Vitamin K (phylloquinone) (μg)",
            "Fósforo": "Phosphorus, P (mg)",
            "Flúor": "Fluoride, F (μg)",
            "Cobre": "Copper, Cu (mg)",
            "Selenio": "Selenium, Se (μg)",
            "Molibdeno": "Molybdenum, Mo (μg)",
            "Cromo": "Chromium, Cr (μg)",
            "Manganeso": "Manganese, Mn (mg)",
            "Colina": "Choline, total (mg)",
        }

    def build_no_significant_thresholds(self) -> Dict[str, Dict[str, Any]]:
        return {
            "Energia": {"unit": "kcal", "max": 4.0, "kj_max": 17.0},
            "Carbohidratos": {"unit": "g", "max": 0.5},
            "Proteinas": {"unit": "g", "max": 0.5},
            "Grasas totales": {"unit": "g", "max": 0.5},
            "Grasas saturadas": {"unit": "g", "max": 0.2},
            "Grasas trans": {"unit": "g", "max": 0.2},
            "Fibra alimentaria": {"unit": "g", "max": 0.5},
            "Sodio": {"unit": "mg", "max": 5.0},
        }

    def build_no_significant_display_map(self) -> Dict[str, str]:
        return {"Energia": "Valor energético"}

    def filter_no_significant_for_fat(self, names: List[str]) -> List[str]:
        fat_names = {
            "Grasas totales",
            "Grasas saturadas",
            "Grasas trans",
            "Grasas monoinsaturadas",
            "Grasas poliinsaturadas",
            "Colesterol",
        }
        return [name for name in names if name not in fat_names]

    def filter_no_significant_for_carb(self, names: List[str]) -> List[str]:
        carb_names = {
            "Carbohidratos",
            "Azúcares",
            "Polialcoholes",
            "Almidón",
            "Polidextrosas",
        }
        return [name for name in names if name not in carb_names]

    def parse_label_mapping(
        self,
        nutrient_map: Dict[str, str],
        label_name: str,
    ) -> tuple[str, str]:
        mapped = nutrient_map.get(label_name, "")
        mapped_clean = mapped.strip()
        if not mapped_clean:
            return "", ""
        match = re.search(r"\(([^()]*)\)\s*$", mapped_clean)
        if match:
            unit_candidate = match.group(1).strip()
            if re.fullmatch(r"(?i)(mg|g|ug|kcal|kj|μg|µg)", unit_candidate):
                base = mapped_clean[: match.start()].strip()
                return canonical_alias_name(base), canonical_unit(unit_candidate)
        return canonical_alias_name(mapped_clean), ""

    def find_total_entry(
        self,
        totals: Dict[str, Dict[str, Any]],
        canonical_name: str,
        unit: str,
    ) -> Dict[str, Any] | None:
        target = canonical_alias_name(canonical_name).lower()
        target_unit = canonical_unit(unit).lower()
        target_key = re.sub(r"[^a-z0-9]", "", target)
        entries = list(totals.values())

        def _match_entry(entry: Dict[str, Any]) -> bool:
            entry_name = canonical_alias_name(entry.get("name", "")).lower()
            entry_unit = canonical_unit(entry.get("unit", "")).lower()
            entry_key = re.sub(r"[^a-z0-9]", "", entry_name)
            name_match = (
                entry_name == target
                or entry_name.startswith(target)
                or target in entry_name
                or entry_key == target_key
                or entry_key.startswith(target_key)
                or target_key in entry_key
            )
            unit_match = (not target_unit) or entry_unit == target_unit
            return name_match and unit_match

        for entry in entries:
            if _match_entry(entry):
                return entry

        raw_target = canonical_name.lower()
        for entry in entries:
            raw_name = (entry.get("name") or "").lower()
            if raw_target in raw_name:
                if not target_unit or canonical_unit(entry.get("unit", "")).lower() == target_unit:
                    return entry
        return None

    def convert_label_amount_unit(
        self,
        amount: float,
        from_unit: str,
        to_unit: str,
    ) -> float | None:
        converted = convert_amount(amount, from_unit, to_unit)
        return float(converted) if converted is not None else None

    def format_fraction_amount(self, value: float) -> str:
        if value <= 0:
            return ""
        frac = Fraction(value).limit_denominator(12)
        whole, remainder = divmod(frac.numerator, frac.denominator)
        if remainder == 0:
            return str(whole)
        if whole == 0:
            return f"{remainder}/{frac.denominator}"
        return f"{whole} {remainder}/{frac.denominator}"

    def fraction_from_ratio(self, ratio: float) -> str:
        percent = ratio * 100.0
        if percent <= 30:
            return "1/4"
        if percent <= 70:
            return "1/2"
        if percent <= 130:
            return "1"
        if percent <= 170:
            return "1 1/2"
        if percent <= 230:
            return "2"
        return self.format_fraction_amount(ratio)

    def portion_factor(self, portion_value: float) -> float:
        return float(portion_value or 0.0) / 100.0

    def household_unit_label(self, unit_name: str, custom_text: str) -> str:
        if unit_name == "Otro":
            custom = custom_text.strip()
            return custom or "Unidad"
        return unit_name

    def capacity_label(
        self,
        unit_name: str,
        capacity: int | None,
        custom_visible: bool,
    ) -> str:
        if unit_name == "Otro" and custom_visible:
            return "Definir capacidad manualmente"
        if capacity:
            return f"{capacity} ml"
        return "-"

    def auto_household_amount(
        self,
        portion_unit: str,
        portion_value: float,
        capacity: int | None,
    ) -> str:
        if portion_unit != "ml" or not capacity:
            return ""
        if portion_value <= 0:
            return ""
        ratio = float(portion_value) / float(capacity)
        return self.fraction_from_ratio(ratio)

    def portion_description(
        self,
        portion_value: int | float,
        portion_unit: str,
        measure_amount: str,
        measure_unit: str,
    ) -> str:
        measure_amount = measure_amount.strip()
        measure_display = measure_unit if not measure_amount else f"{measure_amount} {measure_unit}"
        return f"Porción {portion_value} {portion_unit} ({measure_display})"

    def format_number_for_unit(self, value: float, unit: str) -> str:
        if math.isclose(value, 0.0, abs_tol=1e-9):
            return f"0 {unit}".strip()
        if unit == "mg":
            return f"{value:.0f} mg"
        if unit == "g":
            if abs(value) < 10:
                return f"{value:.1f} g"
            return f"{value:.0f} g"
        if value >= 10:
            return f"{value:.0f} {unit}"
        if value >= 1:
            return f"{value:.1f} {unit}"
        return f"{value:.2f} {unit}"

    def format_additional_amount(self, value: float, unit: str) -> str:
        unit = unit.lower()
        if unit == "mg":
            if math.isclose(value, 0.0, abs_tol=1e-9):
                return "0 mg"
            if value < 10:
                return f"{value:.1f} mg"
            return f"{value:.0f} mg"
        if unit in ("μg", "ug"):
            if math.isclose(value, 0.0, abs_tol=1e-9):
                return "0 μg"
            if value < 10:
                return f"{value:.1f} μg"
            return f"{value:.0f} μg"
        return self.format_number_for_unit(value, unit)

    def format_nutrient_amount(self, nutrient: Dict[str, Any], factor: float) -> str:
        if nutrient.get("type") == "energy":
            kcal_val = nutrient.get("kcal", 0.0) * factor
            kj_val = nutrient.get("kj", 0.0) * factor
            kcal_text = f"{kcal_val:.0f}"
            kj_text = f"{kj_val:.0f}"
            return f"{kcal_text} kcal = {kj_text} kJ"
        amount = nutrient.get("amount", 0.0) * factor
        unit = nutrient.get("unit", "")
        return self.format_number_for_unit(amount, unit)

    def format_vd_value(
        self,
        nutrient: Dict[str, Any],
        factor: float,
        effective_amount: float | None = None,
    ) -> str:
        vd_percent = nutrient.get("vd")
        base_amount = nutrient.get("vd_reference", nutrient.get("amount", 0.0))
        eff_amount = (
            effective_amount if effective_amount is not None else nutrient.get("amount", 0.0)
        )
        if nutrient.get("type") == "energy":
            base_amount = nutrient.get("vd_reference", nutrient.get("kcal", 0.0))
            eff_amount = (
                effective_amount if effective_amount is not None else nutrient.get("kcal", 0.0)
            )

        portion_amount = eff_amount * factor
        if vd_percent is None and base_amount and base_amount > 0:
            vd_val = portion_amount * 100.0 / base_amount
        elif vd_percent is not None and base_amount and base_amount > 0:
            vd_val = vd_percent * (portion_amount / base_amount)
        else:
            return "-"
        return f"{vd_val:.0f}%"

    def format_manual_amount(self, nutrient: Dict[str, Any], manual_amount: float) -> str:
        if nutrient.get("type") == "energy":
            kcal_val = manual_amount
            kj_conv = convert_amount(manual_amount, "kcal", "kJ")
            kj_val = float(kj_conv) if kj_conv is not None else manual_amount * 4.184
            kcal_text = f"{kcal_val:.0f}"
            kj_text = f"{kj_val:.0f}"
            return f"{kcal_text} kcal = {kj_text} kJ"
        unit = nutrient.get("unit", "")
        return self.format_number_for_unit(manual_amount, unit)

    def format_manual_vd(self, nutrient: Dict[str, Any], manual_amount: float) -> str:
        vd_ref = nutrient.get("vd")
        if vd_ref is None:
            vd_reference = nutrient.get("vd_reference")
            if not vd_reference:
                return "-"
            vd_val = manual_amount * 100.0 / float(vd_reference)
        else:
            base_amount = (
                nutrient.get("kcal")
                if nutrient.get("type") == "energy"
                else nutrient.get("amount")
            )
            if not base_amount:
                return "-"
            vd_val = vd_ref * (manual_amount / base_amount)
        return f"{vd_val:.0f}%"

    def parse_user_float(self, text: str) -> float | None:
        clean = text.strip().replace(",", ".")
        if not clean:
            return None
        try:
            return float(clean)
        except ValueError:
            return None

    def active_label_nutrients(
        self,
        *,
        base_nutrients: List[Dict[str, Any]],
        no_significant: List[str],
        breakdown_fat: bool,
        breakdown_carb: bool,
    ) -> List[Dict[str, Any]]:
        display: List[Dict[str, Any]] = []
        for nutrient in base_nutrients:
            name = nutrient.get("name", "")
            if name in no_significant:
                continue
            if nutrient.get("fat_breakdown_only") and not breakdown_fat:
                continue
            if nutrient.get("carb_breakdown_only") and not breakdown_carb:
                continue
            entry = dict(nutrient)
            indent = 0
            if (
                (breakdown_fat and entry.get("fat_child") and not entry.get("fat_parent"))
                or (breakdown_carb and entry.get("carb_child") and not entry.get("carb_parent"))
            ):
                indent = 1
            entry["indent_level"] = indent
            display.append(entry)
        return display

    def build_label_table_rows(
        self,
        *,
        display_nutrients: List[Dict[str, Any]],
        additional_selected: List[str],
        additional_catalog: List[Dict[str, Any]],
        no_significant: List[str],
        no_significant_display_map: Dict[str, str],
        no_sig_order: List[str],
        breakdown_fat: bool,
        breakdown_carb: bool,
        manual_overrides: Dict[str, float],
        totals: Dict[str, Dict[str, Any]],
        nutrient_map: Dict[str, str],
        portion_factor: float,
    ) -> Dict[str, Any]:
        filtered_rows: List[Dict[str, Any]] = []
        filtered_nutrients: List[Dict[str, Any]] = []
        carb_children_present = False
        hide_zero_carb = {"Polialcoholes", "Polidextrosas"}

        for nutrient in display_nutrients:
            effective = self.effective_label_nutrient(
                nutrient,
                totals=totals,
                nutrient_map=nutrient_map,
                manual_overrides=manual_overrides,
                display_nutrients=display_nutrients,
                portion_factor=portion_factor,
            )
            name = effective.get("name", nutrient.get("name", ""))
            if (
                nutrient.get("carb_child")
                and name in hide_zero_carb
                and math.isclose(
                    effective.get("amount", 0.0) or 0.0, 0.0, abs_tol=1e-9
                )
            ):
                continue
            if nutrient.get("carb_child") and not nutrient.get("carb_parent"):
                carb_children_present = True

            if effective.get("manual"):
                manual_amount = manual_overrides.get(name, 0.0)
                amount_text = self.format_manual_amount(effective, manual_amount)
                vd_text = self.format_manual_vd(effective, manual_amount)
            else:
                amount_text = self.format_nutrient_amount(effective, portion_factor)
                eff_amount = (
                    effective.get("kcal", 0.0)
                    if effective.get("type") == "energy"
                    else effective.get("amount", 0.0)
                )
                vd_text = self.format_vd_value(effective, portion_factor, eff_amount)

            if breakdown_fat and nutrient.get("fat_parent"):
                amount_text = f"{amount_text}, de las cuales"
            if breakdown_carb and nutrient.get("carb_parent") and carb_children_present:
                amount_text = f"{amount_text}, de los cuales"

            indent_level = nutrient.get("indent_level", 0)
            display_name = ("    " * indent_level) + name
            is_breakdown_child = bool(
                (breakdown_fat and nutrient.get("fat_child") and not nutrient.get("fat_parent"))
                or (breakdown_carb and nutrient.get("carb_child") and not nutrient.get("carb_parent"))
            )

            filtered_nutrients.append(nutrient)
            filtered_rows.append(
                {
                    "nutrient": nutrient,
                    "display_name": display_name,
                    "amount_text": amount_text,
                    "vd_text": vd_text,
                    "manual": bool(effective.get("manual")),
                    "is_breakdown_child": is_breakdown_child,
                }
            )

        additional_rows: List[Dict[str, Any]] = []
        for add_name in additional_selected:
            nutrient = next((n for n in additional_catalog if n["name"] == add_name), None)
            if not nutrient:
                continue
            effective = self.effective_label_nutrient(
                nutrient,
                totals=totals,
                nutrient_map=nutrient_map,
                manual_overrides=manual_overrides,
                display_nutrients=display_nutrients,
                portion_factor=portion_factor,
            )
            amount_portion = (effective.get("amount", 0.0) or 0.0) * portion_factor
            amount_text = self.format_additional_amount(
                amount_portion, nutrient.get("unit", "")
            )
            eff_amount = effective.get("amount", 0.0) or 0.0
            vd_text = self.format_vd_value(effective, portion_factor, eff_amount)
            additional_rows.append(
                {
                    "name": add_name,
                    "amount_text": amount_text,
                    "vd_text": vd_text,
                    "manual": bool(effective.get("manual")),
                }
            )

        note_text = None
        if no_significant:
            names = [
                no_significant_display_map.get(name, name)
                for name in self.sort_no_significant_list(no_significant, no_sig_order)
            ]
            note_text = f"No aporta cantidades significativas de {self.human_join(names)}."

        return {
            "nutrient_rows": filtered_rows,
            "filtered_nutrients": filtered_nutrients,
            "additional_rows": additional_rows,
            "note_text": note_text,
        }

    def build_linear_preview_text(
        self,
        *,
        portion_desc: str,
        display_nutrients: List[Dict[str, Any]],
        additional_selected: List[str],
        additional_catalog: List[Dict[str, Any]],
        no_significant: List[str],
        no_significant_display_map: Dict[str, str],
        no_sig_order: List[str],
        breakdown_fat: bool,
        breakdown_carb: bool,
        manual_overrides: Dict[str, float],
        totals: Dict[str, Dict[str, Any]],
        nutrient_map: Dict[str, str],
        portion_factor: float,
    ) -> str:
        parts: List[str] = []
        fat_children: List[str] = []
        fat_parent_text = None
        fat_parent_index = None
        carb_children: List[str] = []
        carb_parent_text = None
        carb_parent_index = None
        hide_zero_carb = {"Polialcoholes", "Polidextrosas"}

        for nutrient in display_nutrients:
            effective = self.effective_label_nutrient(
                nutrient,
                totals=totals,
                nutrient_map=nutrient_map,
                manual_overrides=manual_overrides,
                display_nutrients=display_nutrients,
                portion_factor=portion_factor,
            )
            if effective.get("manual"):
                manual_amount = manual_overrides.get(effective.get("name", ""), 0.0)
                amount = self.format_manual_amount(effective, manual_amount)
                vd = self.format_manual_vd(effective, manual_amount)
            else:
                amount = self.format_nutrient_amount(effective, portion_factor)
                eff_amount = (
                    effective.get("kcal", 0.0)
                    if effective.get("type") == "energy"
                    else effective.get("amount", 0.0)
                )
                vd = self.format_vd_value(effective, portion_factor, eff_amount)
            vd_suffix = "" if vd in ("", "-") else f" ({vd} VD*)"
            line_text = f"{nutrient.get('name', '')} {amount}{vd_suffix}"

            if breakdown_fat and nutrient.get("fat_child") and not nutrient.get("fat_parent"):
                fat_children.append(line_text)
                continue

            if breakdown_fat and nutrient.get("fat_parent"):
                fat_parent_text = line_text
                fat_parent_index = len(parts)
                continue

            if breakdown_carb and nutrient.get("carb_child") and not nutrient.get("carb_parent"):
                if nutrient.get("name", "") in hide_zero_carb and math.isclose(
                    effective.get("amount", 0.0) or 0.0, 0.0, abs_tol=1e-9
                ):
                    continue
                carb_children.append(line_text)
                continue

            if breakdown_carb and nutrient.get("carb_parent"):
                carb_parent_text = line_text
                carb_parent_index = len(parts)
                continue

            parts.append(line_text)

        if breakdown_fat and fat_parent_text:
            fat_block = fat_parent_text
            if fat_children:
                fat_block = f"{fat_block}, de los cuales: " + ", ".join(fat_children)
            insert_idx = fat_parent_index if fat_parent_index is not None else len(parts)
            parts.insert(insert_idx, fat_block)

        if breakdown_carb and carb_parent_text:
            carb_block = carb_parent_text
            if carb_children:
                carb_block = f"{carb_block}, de los cuales: " + ", ".join(carb_children)
            insert_idx = carb_parent_index if carb_parent_index is not None else len(parts)
            parts.insert(insert_idx, carb_block)

        for add_name in additional_selected:
            nutrient = next((n for n in additional_catalog if n["name"] == add_name), None)
            if not nutrient:
                continue
            effective = self.effective_label_nutrient(
                nutrient,
                totals=totals,
                nutrient_map=nutrient_map,
                manual_overrides=manual_overrides,
                display_nutrients=display_nutrients,
                portion_factor=portion_factor,
            )
            amount_portion = (effective.get("amount", 0.0) or 0.0) * portion_factor
            amount = self.format_additional_amount(amount_portion, nutrient.get("unit", ""))
            eff_amount = effective.get("amount", 0.0) or 0.0
            vd = self.format_vd_value(effective, portion_factor, eff_amount)
            vd_suffix = "" if vd in ("", "-") else f" ({vd} VD*)"
            parts.append(f"{add_name} {amount}{vd_suffix}")

        note_text = ""
        if no_significant:
            names = [
                no_significant_display_map.get(name, name)
                for name in self.sort_no_significant_list(no_significant, no_sig_order)
            ]
            note_text = f" No aporta cantidades significativas de {self.human_join(names)}."

        return (
            "Información Nutricional: "
            f"{portion_desc}. "
            + "; ".join(parts)
            + ";"
            + note_text
            + " (*) % Valores Diarios con base a una dieta de 2.000 kcal u 8.400 kJ. "
            "Sus valores diarios pueden ser mayores o menores dependiendo de sus necesidades energéticas."
        )

    def eligible_no_significant(
        self,
        *,
        base_nutrients: List[Dict[str, Any]],
        thresholds: Dict[str, Dict[str, Any]],
        breakdown_fat: bool,
        breakdown_carb: bool,
        totals: Dict[str, Dict[str, Any]],
        nutrient_map: Dict[str, str],
        manual_overrides: Dict[str, float],
        display_nutrients: List[Dict[str, Any]],
        portion_factor: float,
    ) -> List[str]:
        eligible: List[str] = []
        fat_names = {
            "Grasas totales",
            "Grasas saturadas",
            "Grasas trans",
            "Grasas monoinsaturadas",
            "Grasas poliinsaturadas",
            "Colesterol",
        }

        def portion_amount(name: str) -> float:
            for nutrient in base_nutrients:
                if nutrient.get("name") != name:
                    continue
                eff = self.effective_label_nutrient(
                    nutrient,
                    totals=totals,
                    nutrient_map=nutrient_map,
                    manual_overrides=manual_overrides,
                    display_nutrients=display_nutrients,
                    portion_factor=portion_factor,
                )
                if eff.get("type") == "energy":
                    return (eff.get("kcal") or 0.0) * portion_factor
                return (eff.get("amount") or 0.0) * portion_factor
            return 0.0

        for nutrient in base_nutrients:
            eff = self.effective_label_nutrient(
                nutrient,
                totals=totals,
                nutrient_map=nutrient_map,
                manual_overrides=manual_overrides,
                display_nutrients=display_nutrients,
                portion_factor=portion_factor,
            )
            name = eff.get("name", nutrient.get("name", ""))
            if breakdown_fat and name in fat_names:
                continue
            if breakdown_carb and name in {
                "Carbohidratos",
                "Azúcares",
                "Polialcoholes",
                "Almidón",
                "Polidextrosas",
            }:
                continue
            thresh = thresholds.get(name)
            if not thresh:
                continue
            if eff.get("type") == "energy":
                kcal_portion = (eff.get("kcal") or 0.0) * portion_factor
                kj_portion = (eff.get("kj") or 0.0) * portion_factor
                if kcal_portion <= thresh.get("max", 0) or kj_portion < thresh.get("kj_max", 0):
                    eligible.append(name)
                continue
            amount_portion = (eff.get("amount") or 0.0) * portion_factor
            unit = eff.get("unit", nutrient.get("unit", "")).lower()
            max_allowed = thresh.get("max", 0.0)
            if name == "Grasas totales":
                sat = portion_amount("Grasas saturadas")
                trans = portion_amount("Grasas trans")
                if (
                    amount_portion <= max_allowed + 1e-9
                    and sat <= thresholds["Grasas saturadas"]["max"] + 1e-9
                    and trans <= thresholds["Grasas trans"]["max"] + 1e-9
                ):
                    eligible.append(name)
            elif amount_portion <= max_allowed + 1e-9:
                eligible.append(name)
        return eligible

    def human_join(self, items: List[str]) -> str:
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        return ", ".join(items[:-1]) + " y " + items[-1]

    def sort_no_significant_list(self, names: List[str], order: List[str]) -> List[str]:
        order_index = {name: idx for idx, name in enumerate(order)}
        return sorted(
            names,
            key=lambda n: (
                order_index.get(n, len(order_index)),
                n.lower(),
            ),
        )

    def factor_for_energy(self, name: str) -> float | None:
        factor_map: List[tuple[str, float]] = [
            ("alcohol", 7.0),
            ("ethanol", 7.0),
            ("protein", 4.0),
            ("carbohydrate", 4.0),
            ("carbohydrate, by difference", 4.0),
            ("polydextrose", 1.0),
            ("polyol", 2.4),
            ("sugar alcohol", 2.4),
            ("organic acid", 3.0),
            ("total lipid", 9.0),
        ]
        lower = name.lower()
        for key, factor in factor_map:
            if key in lower:
                return factor
        return None

    def compute_energy_label_values(
        self,
        *,
        display_nutrients: List[Dict[str, Any]],
        nutrient_map: Dict[str, str],
        manual_overrides: Dict[str, float],
        totals: Dict[str, Dict[str, Any]],
        portion_factor: float,
    ) -> Dict[str, float] | None:
        factor = portion_factor if portion_factor > 0 else 1.0

        carb_parent_present = any(n.get("carb_parent") for n in display_nutrients)
        fat_parent_present = any(n.get("fat_parent") for n in display_nutrients)

        kcal_portion = 0.0

        for nutrient in display_nutrients:
            name = nutrient.get("name", "")
            if nutrient.get("type") == "energy":
                continue
            if carb_parent_present and nutrient.get("carb_child") and not nutrient.get("carb_parent"):
                continue
            if fat_parent_present and nutrient.get("fat_child") and not nutrient.get("fat_parent"):
                continue

            mapped_name, _ = self.parse_label_mapping(nutrient_map, name)
            factor_energy = self.factor_for_energy(mapped_name or name)
            if factor_energy is None:
                continue

            manual_amount = manual_overrides.get(name)
            if manual_amount is not None:
                amount_portion = float(manual_amount)
            else:
                totals_amount = self.label_amount_from_totals(
                    nutrient,
                    totals=totals,
                    nutrient_map=nutrient_map,
                    manual_overrides=manual_overrides,
                    display_nutrients=display_nutrients,
                    portion_factor=factor,
                )
                if not totals_amount:
                    continue
                amount_portion = float(totals_amount.get("amount", 0.0)) * factor

            unit = (nutrient.get("unit", "") or "").lower()
            amount_g = amount_portion / 1000.0 if unit == "mg" else amount_portion
            kcal_portion += amount_g * factor_energy

        if math.isclose(kcal_portion, 0.0, abs_tol=1e-6):
            return None

        kcal_per_100 = kcal_portion / factor
        kj_conv = convert_amount(kcal_per_100, "kcal", "kJ")
        kj_val = float(kj_conv) if kj_conv is not None else kcal_per_100 * 4.184
        return {"kcal": kcal_per_100, "kj": kj_val}

    def label_amount_from_totals(
        self,
        nutrient: Dict[str, Any],
        *,
        totals: Dict[str, Dict[str, Any]],
        nutrient_map: Dict[str, str],
        manual_overrides: Dict[str, float],
        display_nutrients: List[Dict[str, Any]],
        portion_factor: float,
    ) -> Dict[str, float] | None:
        name = nutrient.get("name", "")
        mapped_name, mapped_unit = self.parse_label_mapping(nutrient_map, name)
        if not mapped_name:
            return None
        if nutrient.get("type") == "energy":
            computed = self.compute_energy_label_values(
                display_nutrients=display_nutrients,
                nutrient_map=nutrient_map,
                manual_overrides=manual_overrides,
                totals=totals,
                portion_factor=portion_factor,
            )
            if computed:
                return computed
            return None

        entry = self.find_total_entry(totals, mapped_name, mapped_unit)
        if not entry and mapped_unit:
            entry_any = self.find_total_entry(totals, mapped_name, "")
            if entry_any:
                converted = self.convert_label_amount_unit(
                    float(entry_any.get("amount", 0.0) or 0.0),
                    entry_any.get("unit", ""),
                    mapped_unit,
                )
                if converted is not None:
                    return {"amount": converted}
        if not entry and name == "Grasas totales":
            for candidate in totals.values():
                raw_name = (candidate.get("name") or "").lower()
                if "total lipid" in raw_name:
                    entry = candidate
                    break
        if not entry:
            return None
        return {"amount": float(entry.get("amount", 0.0))}

    def effective_label_nutrient(
        self,
        nutrient: Dict[str, Any],
        *,
        totals: Dict[str, Dict[str, Any]],
        nutrient_map: Dict[str, str],
        manual_overrides: Dict[str, float],
        display_nutrients: List[Dict[str, Any]],
        portion_factor: float,
    ) -> Dict[str, Any]:
        name = nutrient.get("name", "")
        manual_amount = manual_overrides.get(name)
        if nutrient.get("type") == "energy":
            manual_amount = None
        totals_amount = self.label_amount_from_totals(
            nutrient,
            totals=totals,
            nutrient_map=nutrient_map,
            manual_overrides=manual_overrides,
            display_nutrients=display_nutrients,
            portion_factor=portion_factor,
        )

        effective = dict(nutrient)
        effective["vd_reference"] = nutrient.get("vd_reference") or (
            nutrient.get("kcal", nutrient.get("amount", 0.0))
            if nutrient.get("type") == "energy"
            else nutrient.get("amount", 0.0)
        )

        if manual_amount is not None:
            if nutrient.get("type") == "energy":
                effective["kcal"] = manual_amount
                kj_conv = convert_amount(manual_amount, "kcal", "kJ")
                effective["kj"] = float(kj_conv) if kj_conv is not None else manual_amount * 4.184
                effective["amount"] = manual_amount
            else:
                effective["amount"] = manual_amount
            effective["manual"] = True
            return effective

        if totals_amount:
            if nutrient.get("type") == "energy":
                effective["kcal"] = totals_amount.get("kcal", nutrient.get("kcal", 0.0))
                effective["kj"] = totals_amount.get("kj", nutrient.get("kj", 0.0))
                effective["amount"] = effective["kcal"]
            else:
                effective["amount"] = totals_amount.get(
                    "amount", nutrient.get("amount", 0.0)
                )
            effective["manual"] = False
            effective["from_totals"] = True
            return effective

        effective["manual"] = False
        effective["from_totals"] = False
        return effective
