"""Label generation service.

Generates nutrition facts label data in FDA/NLEA format.
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple


class LabelRow:
    """Represents a row in the nutrition facts label."""

    def __init__(
        self,
        nutrient_name: str,
        amount: str,
        daily_value: str = "",
        indent_level: int = 0,
    ) -> None:
        self.nutrient_name = nutrient_name
        self.amount = amount
        self.daily_value = daily_value
        self.indent_level = indent_level


class LabelGenerator:
    """Generate FDA/NLEA nutrition facts label data."""

    # Daily Values (DV) for adults - FDA 2020 guidelines
    # Values are per day
    DAILY_VALUES = {
        "Total Fat": Decimal("78"),  # g
        "Saturated Fat": Decimal("20"),  # g
        "Cholesterol": Decimal("300"),  # mg
        "Sodium": Decimal("2300"),  # mg
        "Total Carbohydrate": Decimal("275"),  # g
        "Dietary Fiber": Decimal("28"),  # g
        "Protein": Decimal("50"),  # g (not typically shown as %DV)
        "Vitamin D": Decimal("20"),  # µg
        "Calcium": Decimal("1300"),  # mg
        "Iron": Decimal("18"),  # mg
        "Potassium": Decimal("4700"),  # mg
    }

    def generate_label(
        self,
        nutrient_totals: Dict[str, Decimal],
        serving_size_g: Decimal = Decimal("100"),
    ) -> List[LabelRow]:
        """Generate nutrition facts label rows.

        Args:
            nutrient_totals: Dictionary of nutrient names to amounts (per 100g)
            serving_size_g: Serving size in grams (default 100g)

        Returns:
            List of LabelRow objects for display

        Note:
            Output follows FDA nutrition facts label format with required nutrients,
            indentation, and daily value percentages.
        """
        rows: List[LabelRow] = []

        # Scale nutrients to serving size
        scale_factor = serving_size_g / Decimal("100")
        scaled = {name: amount * scale_factor for name, amount in nutrient_totals.items()}

        # Serving size header
        rows.append(
            LabelRow(
                nutrient_name="Serving Size",
                amount=f"{serving_size_g}g",
                indent_level=0,
            )
        )

        # Calories (required)
        calories = scaled.get("Energy", Decimal("0"))
        rows.append(
            LabelRow(
                nutrient_name="Calories",
                amount=self._format_amount(calories, "kcal"),
                indent_level=0,
            )
        )

        # Total Fat (required)
        total_fat = self._get_nutrient_flexible(
            scaled,
            ["Total fat (NLEA)", "Total lipid (fat)"],
        )
        if total_fat is not None:
            rows.append(
                LabelRow(
                    nutrient_name="Total Fat",
                    amount=self._format_amount(total_fat, "g"),
                    daily_value=self._calc_dv_percent(total_fat, "Total Fat"),
                    indent_level=0,
                )
            )

            # Saturated Fat (indented)
            sat_fat = self._get_nutrient_flexible(
                scaled,
                ["Fatty acids, total saturated"],
            )
            if sat_fat is not None:
                rows.append(
                    LabelRow(
                        nutrient_name="Saturated Fat",
                        amount=self._format_amount(sat_fat, "g"),
                        daily_value=self._calc_dv_percent(sat_fat, "Saturated Fat"),
                        indent_level=1,
                    )
                )

            # Trans Fat (indented, no DV)
            trans_fat = self._get_nutrient_flexible(
                scaled,
                ["Fatty acids, total trans"],
            )
            if trans_fat is not None:
                rows.append(
                    LabelRow(
                        nutrient_name="Trans Fat",
                        amount=self._format_amount(trans_fat, "g"),
                        indent_level=1,
                    )
                )

        # Cholesterol (required)
        cholesterol = self._get_nutrient_flexible(scaled, ["Cholesterol"])
        if cholesterol is not None:
            rows.append(
                LabelRow(
                    nutrient_name="Cholesterol",
                    amount=self._format_amount(cholesterol, "mg"),
                    daily_value=self._calc_dv_percent(cholesterol, "Cholesterol"),
                    indent_level=0,
                )
            )

        # Sodium (required)
        sodium = self._get_nutrient_flexible(scaled, ["Sodium, Na"])
        if sodium is not None:
            rows.append(
                LabelRow(
                    nutrient_name="Sodium",
                    amount=self._format_amount(sodium, "mg"),
                    daily_value=self._calc_dv_percent(sodium, "Sodium"),
                    indent_level=0,
                )
            )

        # Total Carbohydrate (required)
        total_carb = self._get_nutrient_flexible(
            scaled,
            ["Carbohydrate, by difference"],
        )
        if total_carb is not None:
            rows.append(
                LabelRow(
                    nutrient_name="Total Carbohydrate",
                    amount=self._format_amount(total_carb, "g"),
                    daily_value=self._calc_dv_percent(total_carb, "Total Carbohydrate"),
                    indent_level=0,
                )
            )

            # Dietary Fiber (indented)
            fiber = self._get_nutrient_flexible(scaled, ["Fiber, total dietary"])
            if fiber is not None:
                rows.append(
                    LabelRow(
                        nutrient_name="Dietary Fiber",
                        amount=self._format_amount(fiber, "g"),
                        daily_value=self._calc_dv_percent(fiber, "Dietary Fiber"),
                        indent_level=1,
                    )
                )

            # Total Sugars (indented, no DV)
            sugars = self._get_nutrient_flexible(scaled, ["Sugars, Total", "Sugars, total"])
            if sugars is not None:
                rows.append(
                    LabelRow(
                        nutrient_name="Total Sugars",
                        amount=self._format_amount(sugars, "g"),
                        indent_level=1,
                    )
                )

        # Protein (required)
        protein = self._get_nutrient_flexible(scaled, ["Protein"])
        if protein is not None:
            rows.append(
                LabelRow(
                    nutrient_name="Protein",
                    amount=self._format_amount(protein, "g"),
                    indent_level=0,
                )
            )

        # Micronutrients (Vitamin D, Calcium, Iron, Potassium)
        vitamin_d = self._get_nutrient_flexible(scaled, ["Vitamin D (D2 + D3)", "Vitamin D"])
        if vitamin_d is not None:
            rows.append(
                LabelRow(
                    nutrient_name="Vitamin D",
                    amount=self._format_amount(vitamin_d, "µg"),
                    daily_value=self._calc_dv_percent(vitamin_d, "Vitamin D"),
                    indent_level=0,
                )
            )

        calcium = self._get_nutrient_flexible(scaled, ["Calcium, Ca"])
        if calcium is not None:
            rows.append(
                LabelRow(
                    nutrient_name="Calcium",
                    amount=self._format_amount(calcium, "mg"),
                    daily_value=self._calc_dv_percent(calcium, "Calcium"),
                    indent_level=0,
                )
            )

        iron = self._get_nutrient_flexible(scaled, ["Iron, Fe"])
        if iron is not None:
            rows.append(
                LabelRow(
                    nutrient_name="Iron",
                    amount=self._format_amount(iron, "mg"),
                    daily_value=self._calc_dv_percent(iron, "Iron"),
                    indent_level=0,
                )
            )

        potassium = self._get_nutrient_flexible(scaled, ["Potassium, K"])
        if potassium is not None:
            rows.append(
                LabelRow(
                    nutrient_name="Potassium",
                    amount=self._format_amount(potassium, "mg"),
                    daily_value=self._calc_dv_percent(potassium, "Potassium"),
                    indent_level=0,
                )
            )

        return rows

    def _get_nutrient_flexible(
        self,
        nutrients: Dict[str, Decimal],
        possible_names: List[str],
    ) -> Optional[Decimal]:
        """Get nutrient value trying multiple possible names (case-insensitive)."""
        for name in possible_names:
            name_lower = name.lower()
            for key, value in nutrients.items():
                if key.lower() == name_lower:
                    return value
        return None

    def _format_amount(self, amount: Decimal, unit: str) -> str:
        """Format nutrient amount with appropriate precision."""
        if amount >= 10:
            return f"{amount:.0f}{unit}"
        elif amount >= 1:
            return f"{amount:.1f}{unit}"
        else:
            return f"{amount:.2f}{unit}"

    def _calc_dv_percent(self, amount: Decimal, nutrient_name: str) -> str:
        """Calculate daily value percentage."""
        dv = self.DAILY_VALUES.get(nutrient_name)
        if dv is None or dv == 0:
            return ""

        percent = (amount / dv) * Decimal("100")

        if percent < 1:
            return "<1%"
        else:
            return f"{percent:.0f}%"
