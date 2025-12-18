"""Excel export functionality.

Exports formulations and nutrient data to Excel with formatting.
"""

from decimal import Decimal
from pathlib import Path
from typing import Dict

from openpyxl import Workbook
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils import get_column_letter

from domain.exceptions import ExportError
from domain.models import Formulation


class ExcelExporter:
    """Export formulations to Excel format."""

    def export_formulation(
        self,
        formulation: Formulation,
        nutrient_totals: Dict[str, Decimal],
        output_path: Path | str,
    ) -> None:
        """Export formulation with nutrient breakdown to Excel.

        Args:
            formulation: Formulation to export
            nutrient_totals: Nutrient totals (per 100g)
            output_path: Path to save Excel file

        Raises:
            ExportError: If export fails
        """
        try:
            wb = Workbook()
            wb.remove(wb.active)  # Remove default sheet

            # Create ingredients sheet
            self._create_ingredients_sheet(wb, formulation)

            # Create nutrients sheet
            self._create_nutrients_sheet(wb, formulation, nutrient_totals)

            # Save workbook
            wb.save(output_path)

        except Exception as exc:
            raise ExportError(f"Failed to export to Excel: {exc}") from exc

    def _create_ingredients_sheet(
        self,
        wb: Workbook,
        formulation: Formulation,
    ) -> None:
        """Create ingredients sheet."""
        ws = wb.create_sheet("Ingredients")

        # Headers
        headers = ["Ingredient", "FDC ID", "Amount (g)", "Percentage", "Locked"]
        ws.append(headers)

        # Style headers
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        for col_num, _ in enumerate(headers, 1):
            cell = ws.cell(1, col_num)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Data rows
        total_weight = formulation.total_weight
        for ingredient in formulation.ingredients:
            percentage = ingredient.calculate_percentage(total_weight)
            ws.append(
                [
                    ingredient.food.description,
                    ingredient.food.fdc_id,
                    float(ingredient.amount_g),
                    float(percentage),
                    "Yes" if ingredient.locked else "No",
                ]
            )

        # Total row
        ws.append(["TOTAL", "", float(total_weight), 100.0, ""])

        # Auto-size columns
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            ws.column_dimensions[column_letter].width = min(max_length + 2, 50)

    def _create_nutrients_sheet(
        self,
        wb: Workbook,
        formulation: Formulation,
        nutrient_totals: Dict[str, Decimal],
    ) -> None:
        """Create nutrients sheet with per-ingredient breakdown."""
        ws = wb.create_sheet("Nutrients")

        # Build headers: Nutrient | Unit | Ing1 | Ing2 | ... | Total
        headers = ["Nutrient", "Unit"]
        for ingredient in formulation.ingredients:
            # Truncate long names
            name = ingredient.food.description
            if len(name) > 20:
                name = name[:17] + "..."
            headers.append(name)
        headers.append("Total (per 100g)")

        ws.append(headers)

        # Style headers
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        for col_num, _ in enumerate(headers, 1):
            cell = ws.cell(1, col_num)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Get all unique nutrients across all ingredients
        all_nutrients: set[str] = set()
        for ingredient in formulation.ingredients:
            for nutrient in ingredient.food.nutrients:
                all_nutrients.add(nutrient.name)

        # Add rows for each nutrient
        for nutrient_name in sorted(all_nutrients):
            row_data = [nutrient_name]

            # Get unit from first ingredient that has this nutrient
            unit = ""
            for ingredient in formulation.ingredients:
                nut = ingredient.food.get_nutrient(nutrient_name)
                if nut:
                    unit = nut.unit
                    break
            row_data.append(unit)

            # Per-ingredient values (scaled to ingredient amount)
            for ingredient in formulation.ingredients:
                amount = ingredient.get_nutrient_amount(nutrient_name)
                row_data.append(float(amount) if amount > 0 else "")

            # Total (per 100g)
            total = nutrient_totals.get(nutrient_name, Decimal("0"))
            row_data.append(float(total) if total > 0 else "")

            ws.append(row_data)

        # Auto-size columns
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            ws.column_dimensions[column_letter].width = min(max_length + 2, 30)
