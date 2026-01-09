
from __future__ import annotations

from decimal import Decimal
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.models import CurrencyRate
from domain.services.unit_normalizer import convert_mass, normalize_mass_unit
from ui.tabs.table_utils import apply_selection_bar, attach_copy_shortcut


class CostsTabMixin:
    """Costs tab UI and behavior."""

    def _init_costs_state(self) -> None:
        self._costs_block_signals = False
        self._ingredient_cost_columns = {
            "ingredient": 0,
            "amount": 1,
            "pack_amount": 2,
            "pack_unit": 3,
            "currency": 4,
            "cost_value": 5,
            "unit_cost": 6,
            "batch_cost": 7,
            "percent": 8,
        }
        self._process_columns = {
            "name": 0,
            "scale": 1,
            "setup_value": 2,
            "setup_unit": 3,
            "time_per_kg": 4,
            "time_unit": 5,
            "time_total": 6,
            "time_total_unit": 7,
            "cost_per_hour": 8,
            "total_cost": 9,
            "notes": 10,
        }
        self._packaging_columns = {
            "name": 0,
            "qty": 1,
            "unit_cost": 2,
            "subtotal": 3,
            "notes": 4,
        }

    def _build_costs_tab_ui(self) -> None:
        layout = QVBoxLayout(self.costs_tab)

        # Zona 1: Resumen
        summary_widget = QWidget(self.costs_tab)
        summary_layout = QGridLayout(summary_widget)
        summary_layout.setColumnStretch(1, 1)
        summary_layout.setColumnStretch(3, 1)
        summary_layout.setColumnStretch(5, 1)
        summary_layout.setColumnStretch(7, 1)

        self.costs_batch_mass_label = QLabel("-")
        self.costs_yield_input = QDoubleSpinBox()
        self.costs_yield_input.setRange(0.01, 100.0)
        self.costs_yield_input.setDecimals(2)
        self.costs_sellable_mass_label = QLabel("-")
        self.costs_ingredients_total_label = QLabel("$ 0.00")
        self.costs_process_total_label = QLabel("$ 0.00")
        self.costs_total_label = QLabel("$ 0.00")
        self.costs_completeness_label = QLabel("-")
        self.costs_load_rates_button = QPushButton("Cargar cotizaciones")

        summary_layout.addWidget(QLabel("Masa tirada:"), 0, 0)
        summary_layout.addWidget(self.costs_batch_mass_label, 0, 1)
        summary_layout.addWidget(QLabel("Yield (%):"), 0, 2)
        summary_layout.addWidget(self.costs_yield_input, 0, 3)
        summary_layout.addWidget(QLabel("Masa vendible:"), 0, 4)
        summary_layout.addWidget(self.costs_sellable_mass_label, 0, 5)
        summary_layout.addWidget(QLabel("Completitud:"), 0, 6)
        summary_layout.addWidget(self.costs_completeness_label, 0, 7)

        summary_layout.addWidget(QLabel("Costo insumos:"), 1, 0)
        summary_layout.addWidget(self.costs_ingredients_total_label, 1, 1)
        summary_layout.addWidget(QLabel("Costo procesos:"), 1, 2)
        summary_layout.addWidget(self.costs_process_total_label, 1, 3)
        summary_layout.addWidget(QLabel("Costo total tirada:"), 1, 4)
        summary_layout.addWidget(self.costs_total_label, 1, 5)
        summary_layout.addWidget(self.costs_load_rates_button, 1, 6, 1, 2)

        layout.addWidget(summary_widget)

        # Zona 2: tabla de ingredientes
        ingredients_panel = QWidget(self.costs_tab)
        ingredients_layout = QVBoxLayout(ingredients_panel)
        ingredients_layout.setContentsMargins(0, 0, 0, 0)
        ingredients_layout.addWidget(QLabel("Insumos / Ingredientes"))

        self.costs_ingredients_table = QTableWidget(0, len(self._ingredient_cost_columns))
        self.costs_ingredients_table.setHorizontalHeaderLabels(
            [
                "Ingrediente",
                "Cantidad",
                "Presentacion",
                "Unidad",
                "Moneda",
                "Costo",
                "Costo unitario (MN/g)",
                "Costo tirada (MN)",
                "% insumos",
            ]
        )
        self.costs_ingredients_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.costs_ingredients_table.setSelectionMode(QTableWidget.ExtendedSelection)
        apply_selection_bar(self.costs_ingredients_table)
        ingredients_layout.addWidget(self.costs_ingredients_table)

        layout.addWidget(ingredients_panel)

        # Zona 2: tabla de procesos
        processes_panel = QWidget(self.costs_tab)
        processes_layout = QVBoxLayout(processes_panel)
        processes_layout.setContentsMargins(0, 0, 0, 0)
        processes_layout.addWidget(QLabel("Procesos"))

        self.costs_process_table = QTableWidget(0, len(self._process_columns))
        self.costs_process_table.setHorizontalHeaderLabels(
            [
                "Nombre",
                "Tipo",
                "Setup",
                "U",
                "Tiempo/kg",
                "U",
                "Tiempo total",
                "U",
                "Costo/h",
                "Costo total (MN)",
                "Notas",
            ]
        )
        self.costs_process_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.costs_process_table.setSelectionMode(QTableWidget.ExtendedSelection)
        apply_selection_bar(self.costs_process_table)
        processes_layout.addWidget(self.costs_process_table)

        process_buttons = QHBoxLayout()
        self.costs_add_process_button = QPushButton("Agregar proceso")
        self.costs_remove_process_button = QPushButton("Eliminar proceso")
        process_buttons.addWidget(self.costs_add_process_button)
        process_buttons.addWidget(self.costs_remove_process_button)
        process_buttons.addStretch()
        processes_layout.addLayout(process_buttons)

        layout.addWidget(processes_panel)

        # Zona 3: Packaging + resultados
        bottom_splitter = QSplitter(Qt.Horizontal, self.costs_tab)
        packaging_panel = QWidget(self.costs_tab)
        packaging_layout = QVBoxLayout(packaging_panel)
        packaging_layout.setContentsMargins(0, 0, 0, 0)
        packaging_layout.addWidget(QLabel("Packaging"))

        self.costs_packaging_table = QTableWidget(0, len(self._packaging_columns))
        self.costs_packaging_table.setHorizontalHeaderLabels(
            [
                "Nombre",
                "Cantidad/pack",
                "Costo unitario (MN)",
                "Subtotal",
                "Notas",
            ]
        )
        self.costs_packaging_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.costs_packaging_table.setSelectionMode(QTableWidget.ExtendedSelection)
        apply_selection_bar(self.costs_packaging_table)
        packaging_layout.addWidget(self.costs_packaging_table)

        packaging_buttons = QHBoxLayout()
        self.costs_add_packaging_button = QPushButton("Agregar item")
        self.costs_remove_packaging_button = QPushButton("Eliminar item")
        packaging_buttons.addWidget(self.costs_add_packaging_button)
        packaging_buttons.addWidget(self.costs_remove_packaging_button)
        packaging_buttons.addStretch()
        packaging_layout.addLayout(packaging_buttons)

        calc_widget = QWidget(self.costs_tab)
        calc_layout = QGridLayout(calc_widget)
        calc_layout.setColumnStretch(1, 1)

        self.costs_target_mass_input = QDoubleSpinBox()
        self.costs_target_mass_input.setRange(0.01, 1_000_000.0)
        self.costs_target_mass_input.setDecimals(3)
        self.costs_target_mass_input.setValue(100.0)
        self.costs_target_unit_selector = QComboBox()
        self.costs_target_unit_selector.addItems(["g", "kg", "lb", "oz", "ton"])

        self.costs_target_ingredients_label = QLabel("$ 0.00")
        self.costs_target_process_label = QLabel("$ 0.00")
        self.costs_target_total_label = QLabel("$ 0.00")
        self.costs_packaging_total_label = QLabel("$ 0.00")
        self.costs_target_total_pack_label = QLabel("$ 0.00")
        self.costs_units_count_label = QLabel("-")

        calc_layout.addWidget(QLabel("Masa objetivo:"), 0, 0)
        calc_layout.addWidget(self.costs_target_mass_input, 0, 1)
        calc_layout.addWidget(self.costs_target_unit_selector, 0, 2)

        calc_layout.addWidget(QLabel("Costo insumos (unidad):"), 1, 0)
        calc_layout.addWidget(self.costs_target_ingredients_label, 1, 1)
        calc_layout.addWidget(QLabel("Costo procesos (unidad):"), 2, 0)
        calc_layout.addWidget(self.costs_target_process_label, 2, 1)
        calc_layout.addWidget(QLabel("Costo total (sin packaging):"), 3, 0)
        calc_layout.addWidget(self.costs_target_total_label, 3, 1)
        calc_layout.addWidget(QLabel("Packaging por pack:"), 4, 0)
        calc_layout.addWidget(self.costs_packaging_total_label, 4, 1)
        calc_layout.addWidget(QLabel("Total por pack:"), 5, 0)
        calc_layout.addWidget(self.costs_target_total_pack_label, 5, 1)
        calc_layout.addWidget(QLabel("Packs por tirada:"), 6, 0)
        calc_layout.addWidget(self.costs_units_count_label, 6, 1)

        bottom_splitter.addWidget(packaging_panel)

        results_panel = QWidget(self.costs_tab)
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.addWidget(QLabel("Resultados costos"))
        results_layout.addWidget(calc_widget)
        bottom_splitter.addWidget(results_panel)
        bottom_splitter.setStretchFactor(0, 3)
        bottom_splitter.setStretchFactor(1, 2)
        layout.addWidget(bottom_splitter)

        # Conexiones
        self.costs_load_rates_button.clicked.connect(self._on_load_rates_clicked)
        self.costs_yield_input.valueChanged.connect(self._on_yield_changed)
        self.costs_target_mass_input.valueChanged.connect(self._update_costs_calculator)
        self.costs_target_unit_selector.currentTextChanged.connect(
            lambda _text: self._update_costs_calculator()
        )
        self.costs_add_process_button.clicked.connect(self._on_add_process_clicked)
        self.costs_remove_process_button.clicked.connect(self._on_remove_process_clicked)
        self.costs_add_packaging_button.clicked.connect(self._on_add_packaging_clicked)
        self.costs_remove_packaging_button.clicked.connect(self._on_remove_packaging_clicked)
        self.costs_ingredients_table.itemChanged.connect(
            self._on_ingredient_cost_item_changed
        )
        self.costs_process_table.itemChanged.connect(self._on_process_item_changed)
        self.costs_packaging_table.itemChanged.connect(self._on_packaging_item_changed)

        attach_copy_shortcut(self.costs_ingredients_table)
        attach_copy_shortcut(self.costs_process_table)
        attach_copy_shortcut(self.costs_packaging_table)

        paste_shortcut = QShortcut(QKeySequence.Paste, self.costs_ingredients_table)
        paste_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        paste_shortcut.activated.connect(self._paste_ingredients_table)

        self._apply_costs_column_widths()
        self._refresh_costs_view()

    def _apply_costs_column_widths(self) -> None:
        table = self.costs_ingredients_table
        table.setColumnWidth(self._ingredient_cost_columns["ingredient"], 200)
        table.setColumnWidth(self._ingredient_cost_columns["amount"], 90)
        table.setColumnWidth(self._ingredient_cost_columns["pack_amount"], 80)
        table.setColumnWidth(self._ingredient_cost_columns["pack_unit"], 60)
        table.setColumnWidth(self._ingredient_cost_columns["currency"], 70)
        table.setColumnWidth(self._ingredient_cost_columns["cost_value"], 80)
        table.setColumnWidth(self._ingredient_cost_columns["unit_cost"], 110)
        table.setColumnWidth(self._ingredient_cost_columns["batch_cost"], 110)
        table.setColumnWidth(self._ingredient_cost_columns["percent"], 80)

        process_table = self.costs_process_table
        process_table.setColumnWidth(self._process_columns["name"], 140)
        process_table.setColumnWidth(self._process_columns["scale"], 100)
        process_table.setColumnWidth(self._process_columns["setup_value"], 70)
        process_table.setColumnWidth(self._process_columns["setup_unit"], 40)
        process_table.setColumnWidth(self._process_columns["time_per_kg"], 70)
        process_table.setColumnWidth(self._process_columns["time_unit"], 40)
        process_table.setColumnWidth(self._process_columns["time_total"], 80)
        process_table.setColumnWidth(self._process_columns["time_total_unit"], 40)
        process_table.setColumnWidth(self._process_columns["cost_per_hour"], 80)
        process_table.setColumnWidth(self._process_columns["total_cost"], 100)
        process_table.setColumnWidth(self._process_columns["notes"], 120)

        packaging_table = self.costs_packaging_table
        packaging_table.setColumnWidth(self._packaging_columns["name"], 150)
        packaging_table.setColumnWidth(self._packaging_columns["qty"], 90)
        packaging_table.setColumnWidth(self._packaging_columns["unit_cost"], 90)
        packaging_table.setColumnWidth(self._packaging_columns["subtotal"], 90)
        packaging_table.setColumnWidth(self._packaging_columns["notes"], 140)

    def _format_mass(self, value_g: Decimal, unit: str) -> str:
        unit_norm = normalize_mass_unit(unit) or unit
        converted = convert_mass(value_g, "g", unit_norm) or value_g
        decimals = self.formulation_presenter.mass_decimals(unit_norm)
        return f"{float(converted):.{decimals}f} {unit_norm}"

    def _format_money(self, value: Decimal | None) -> str:
        if value is None:
            return "-"
        return f"$ {float(value):.2f}"

    def _format_percent(self, value: Decimal | None) -> str:
        if value is None:
            return "-"
        return f"{float(value):.1f}%"

    def _make_readonly_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _refresh_costs_view(self) -> None:
        if self._costs_block_signals:
            return
        self._costs_block_signals = True
        try:
            self._update_costs_summary()
            self._populate_ingredients_costs_table()
            self._populate_processes_table()
            self._populate_packaging_table()
            self._update_costs_calculator()
        finally:
            self._costs_block_signals = False

    def _update_costs_summary(self) -> None:
        summary = self.costs_presenter.summary()
        unit = self.formulation_presenter.current_mass_unit(self.quantity_mode)
        self.costs_batch_mass_label.setText(
            self._format_mass(summary["batch_mass_g"], unit)
        )
        self.costs_sellable_mass_label.setText(
            self._format_mass(summary["sellable_mass_g"], unit)
        )
        self.costs_yield_input.blockSignals(True)
        self.costs_yield_input.setValue(float(summary["yield_percent"]))
        self.costs_yield_input.blockSignals(False)

        self.costs_ingredients_total_label.setText(
            self._format_money(summary["ingredients_total_mn"])
        )
        self.costs_process_total_label.setText(
            self._format_money(summary["process_total_mn"])
        )
        self.costs_total_label.setText(self._format_money(summary["total_cost_mn"]))

        ingredients_pct = summary["ingredients_percent"]
        process_pct = summary["process_percent"]
        completeness_text = (
            f"Insumos {float(ingredients_pct):.0f}% | Procesos {float(process_pct):.0f}%"
        )
        self.costs_completeness_label.setText(completeness_text)
        if summary["missing_ingredients_count"] > 0 or summary["missing_process_count"] > 0:
            self.costs_completeness_label.setStyleSheet("color: #a66b00;")
        else:
            self.costs_completeness_label.setStyleSheet("")

    def _on_load_rates_clicked(self) -> None:
        rates = self._prompt_currency_rates()
        if rates is None:
            return
        self.costs_presenter.set_currency_rates(rates)
        valid_symbols = {rate.symbol for rate in rates if rate.symbol}
        missing = [
            ing.description
            for ing in self.costs_presenter.formulation.ingredients
            if str(ing.cost_currency_symbol or "").strip()
            and str(ing.cost_currency_symbol or "").strip() not in valid_symbols
        ]
        if missing:
            QMessageBox.warning(
                self,
                "Cotizaciones",
                "Hay ingredientes con moneda sin cotizacion. "
                "Revisa las filas marcadas en la tabla de insumos.",
            )
        self._refresh_costs_view()

    def _prompt_currency_rates(self) -> List[CurrencyRate] | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Cotizaciones")
        layout = QVBoxLayout(dialog)

        table = QTableWidget(0, 3, dialog)
        table.setHorizontalHeaderLabels(
            ["Moneda", "Simbolo", "Cotizacion a MN"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.ExtendedSelection)
        layout.addWidget(table)

        def _set_base_row(row: int) -> None:
            values = ["Moneda Nacional", "$", "1"]
            for col, text in enumerate(values):
                item = table.item(row, col)
                if item is None:
                    item = QTableWidgetItem(text)
                    table.setItem(row, col, item)
                item.setText(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

        def _add_row(rate: CurrencyRate | None = None, *, locked: bool = False) -> None:
            row = table.rowCount()
            table.insertRow(row)
            if locked:
                _set_base_row(row)
                return
            name = "" if rate is None else rate.name
            symbol = "" if rate is None else rate.symbol
            rate_value = "" if rate is None else str(rate.rate_to_mn)
            table.setItem(row, 0, QTableWidgetItem(str(name or "")))
            table.setItem(row, 1, QTableWidgetItem(str(symbol or "")))
            table.setItem(row, 2, QTableWidgetItem(str(rate_value or "")))

        def _add_empty_row() -> None:
            _add_row()
            table.setCurrentCell(table.rowCount() - 1, 0)

        def _remove_selected_rows() -> None:
            rows = sorted({idx.row() for idx in table.selectedIndexes()}, reverse=True)
            for row in rows:
                if row == 0:
                    continue
                table.removeRow(row)

        rates = self.costs_presenter.get_currency_rates()
        base_rate = next((r for r in rates if r.symbol == "$"), None)
        _add_row(base_rate, locked=True)
        for rate in rates:
            if rate.symbol == "$":
                continue
            _add_row(rate)

        buttons_row = QHBoxLayout()
        add_button = QPushButton("Agregar moneda")
        remove_button = QPushButton("Eliminar fila")
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(remove_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        add_button.clicked.connect(_add_empty_row)
        remove_button.clicked.connect(_remove_selected_rows)

        def _to_decimal(value: str) -> Decimal | None:
            if value is None:
                return None
            cleaned = str(value).strip().replace(",", ".")
            if cleaned == "":
                return None
            try:
                return Decimal(cleaned)
            except Exception:
                return None

        def _collect_rates() -> List[CurrencyRate] | None:
            symbols: set[str] = set()
            collected: List[CurrencyRate] = []
            for row in range(table.rowCount()):
                name_item = table.item(row, 0)
                symbol_item = table.item(row, 1)
                rate_item = table.item(row, 2)
                name = (name_item.text() if name_item else "").strip()
                symbol = (symbol_item.text() if symbol_item else "").strip()
                rate_raw = rate_item.text() if rate_item else ""

                if row == 0:
                    name = "Moneda Nacional"
                    symbol = "$"
                    rate_val = Decimal("1")
                else:
                    if not name:
                        QMessageBox.warning(
                            self,
                            "Cotizaciones",
                            "Completa el nombre de la moneda.",
                        )
                        return None
                    if not symbol:
                        QMessageBox.warning(
                            self,
                            "Cotizaciones",
                            "Completa el simbolo de la moneda.",
                        )
                        return None
                    rate_val = _to_decimal(rate_raw)
                    if rate_val is None or rate_val <= 0:
                        QMessageBox.warning(
                            self,
                            "Cotizaciones",
                            "La cotizacion debe ser mayor a 0.",
                        )
                        return None

                if symbol in symbols:
                    QMessageBox.warning(
                        self,
                        "Cotizaciones",
                        f"El simbolo '{symbol}' esta repetido.",
                    )
                    return None
                symbols.add(symbol)
                collected.append(
                    CurrencyRate(name=name, symbol=symbol, rate_to_mn=rate_val)
                )
            return collected

        while True:
            if dialog.exec() != QDialog.Accepted:
                return None
            rates = _collect_rates()
            if rates is not None:
                return rates

    def _populate_ingredients_costs_table(self) -> None:
        rows = self.costs_presenter.build_ingredient_rows(self.quantity_mode)
        table = self.costs_ingredients_table
        symbols = self.costs_presenter.get_currency_symbols()
        table.blockSignals(True)
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            table.setItem(row_idx, self._ingredient_cost_columns["ingredient"], self._make_readonly_item(row["description"]))
            amount_text = self._format_mass(row["amount_g"], row["unit"])
            table.setItem(row_idx, self._ingredient_cost_columns["amount"], self._make_readonly_item(amount_text))

            pack_amount = "" if row["cost_pack_amount"] is None else f"{float(row['cost_pack_amount']):.3f}"
            table.setItem(row_idx, self._ingredient_cost_columns["pack_amount"], QTableWidgetItem(pack_amount))

            unit_combo = QComboBox(table)
            unit_combo.addItems(["g", "kg", "lb", "oz", "ton"])
            unit_combo.setCurrentText(row["cost_pack_unit"] or "g")
            unit_combo.setProperty("row", row_idx)
            unit_combo.currentTextChanged.connect(self._on_ingredient_unit_changed)
            table.setCellWidget(row_idx, self._ingredient_cost_columns["pack_unit"], unit_combo)

            currency_combo = QComboBox(table)
            currency_combo.addItems(symbols)
            currency_combo.setCurrentText(row["cost_currency_symbol"] or "$")
            currency_combo.setProperty("row", row_idx)
            currency_combo.currentTextChanged.connect(self._on_ingredient_currency_changed)
            table.setCellWidget(row_idx, self._ingredient_cost_columns["currency"], currency_combo)

            cost_value = "" if row["cost_value"] is None else f"{float(row['cost_value']):.3f}"
            table.setItem(row_idx, self._ingredient_cost_columns["cost_value"], QTableWidgetItem(cost_value))

            unit_cost_text = (
                f"{float(row['cost_per_g_mn']):.6f}" if row["cost_per_g_mn"] is not None else "-"
            )
            table.setItem(row_idx, self._ingredient_cost_columns["unit_cost"], self._make_readonly_item(unit_cost_text))
            batch_cost_text = self._format_money(row["cost_batch_mn"]) if row["cost_batch_mn"] is not None else "-"
            table.setItem(row_idx, self._ingredient_cost_columns["batch_cost"], self._make_readonly_item(batch_cost_text))
            table.setItem(row_idx, self._ingredient_cost_columns["percent"], self._make_readonly_item(self._format_percent(row["percent_of_ingredients"])))

            if row["cost_per_g_mn"] is None:
                for col in (
                    self._ingredient_cost_columns["pack_amount"],
                    self._ingredient_cost_columns["cost_value"],
                ):
                    item = table.item(row_idx, col)
                    if item:
                        item.setBackground(Qt.yellow)
            if row.get("currency_missing"):
                currency_combo.setStyleSheet("background-color: #fff2cc;")
        table.blockSignals(False)

    def _on_ingredient_unit_changed(self, _text: str) -> None:
        if self._costs_block_signals:
            return
        combo = self.sender()
        if isinstance(combo, QComboBox):
            row = combo.property("row")
            if row is not None:
                self._update_ingredient_from_row(int(row))

    def _on_ingredient_currency_changed(self, _text: str) -> None:
        if self._costs_block_signals:
            return
        combo = self.sender()
        if isinstance(combo, QComboBox):
            row = combo.property("row")
            if row is not None:
                self._update_ingredient_from_row(int(row))

    def _on_ingredient_cost_item_changed(self, item: QTableWidgetItem) -> None:
        if self._costs_block_signals:
            return
        if item.column() in (
            self._ingredient_cost_columns["pack_amount"],
            self._ingredient_cost_columns["cost_value"],
        ):
            self._update_ingredient_from_row(item.row())

    def _update_ingredient_from_row(self, row: int) -> None:
        table = self.costs_ingredients_table
        pack_amount_item = table.item(row, self._ingredient_cost_columns["pack_amount"])
        cost_value_item = table.item(row, self._ingredient_cost_columns["cost_value"])
        unit_combo = table.cellWidget(row, self._ingredient_cost_columns["pack_unit"])
        currency_combo = table.cellWidget(row, self._ingredient_cost_columns["currency"])

        pack_unit = unit_combo.currentText() if isinstance(unit_combo, QComboBox) else "g"
        currency = currency_combo.currentText() if isinstance(currency_combo, QComboBox) else "$"

        self.costs_presenter.update_ingredient_cost(
            row,
            cost_pack_amount=pack_amount_item.text() if pack_amount_item else None,
            cost_pack_unit=pack_unit,
            cost_value=cost_value_item.text() if cost_value_item else None,
            cost_currency_symbol=currency,
        )
        self._refresh_costs_view()
    def _populate_processes_table(self) -> None:
        rows = self.costs_presenter.build_process_rows()
        table = self.costs_process_table
        table.blockSignals(True)
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            table.setItem(row_idx, self._process_columns["name"], QTableWidgetItem(row["name"] or ""))

            scale_combo = QComboBox(table)
            scale_combo.addItems(["FIXED", "VARIABLE_PER_KG", "MIXED"])
            scale_combo.setCurrentText(row["scale_type"] or "FIXED")
            scale_combo.setProperty("row", row_idx)
            scale_combo.currentTextChanged.connect(self._on_process_scale_changed)
            table.setCellWidget(row_idx, self._process_columns["scale"], scale_combo)

            setup_value = "" if row["setup_time_value"] is None else f"{float(row['setup_time_value']):.3f}"
            table.setItem(row_idx, self._process_columns["setup_value"], QTableWidgetItem(setup_value))
            setup_unit_combo = QComboBox(table)
            setup_unit_combo.addItems(["min", "h"])
            setup_unit_combo.setCurrentText(row["setup_time_unit"] or "min")
            setup_unit_combo.setProperty("row", row_idx)
            setup_unit_combo.currentTextChanged.connect(self._on_process_setup_unit_changed)
            table.setCellWidget(row_idx, self._process_columns["setup_unit"], setup_unit_combo)

            time_per_kg = "" if row["time_per_kg_value"] is None else f"{float(row['time_per_kg_value']):.3f}"
            table.setItem(row_idx, self._process_columns["time_per_kg"], QTableWidgetItem(time_per_kg))
            time_unit_combo = QComboBox(table)
            time_unit_combo.addItems(["min", "h"])
            time_unit_combo.setCurrentText(row["time_unit"] or "min")
            time_unit_combo.setProperty("row", row_idx)
            time_unit_combo.currentTextChanged.connect(self._on_process_time_unit_changed)
            table.setCellWidget(row_idx, self._process_columns["time_unit"], time_unit_combo)

            time_total_value = ""
            if row["time_total_h"] is not None:
                time_total_value = f"{float(row['time_total_h']):.3f}"
            table.setItem(row_idx, self._process_columns["time_total"], QTableWidgetItem(time_total_value))
            unit_text = row["time_unit"] if (row["scale_type"] or "").strip().upper() == "FIXED" else "h"
            table.setItem(
                row_idx,
                self._process_columns["time_total_unit"],
                self._make_readonly_item(unit_text or "h"),
            )

            cost_per_hour = "" if row["cost_per_hour_mn"] is None else f"{float(row['cost_per_hour_mn']):.3f}"
            table.setItem(row_idx, self._process_columns["cost_per_hour"], QTableWidgetItem(cost_per_hour))
            scale_type = (row["scale_type"] or "").strip().upper()
            if scale_type == "FIXED":
                total_cost_text = (
                    f"{float(row['total_cost_mn']):.3f}"
                    if row["total_cost_mn"] is not None
                    else ""
                )
            else:
                total_cost_text = (
                    self._format_money(row["total_cost_mn"])
                    if row["total_cost_mn"] is not None
                    else "-"
                )
            table.setItem(
                row_idx,
                self._process_columns["total_cost"],
                QTableWidgetItem(total_cost_text),
            )

            table.setItem(row_idx, self._process_columns["notes"], QTableWidgetItem(row["notes"] or ""))

            self._apply_process_row_state(row_idx, row["scale_type"])

            if row["total_cost_mn"] is None:
                for col in (self._process_columns["cost_per_hour"], self._process_columns["time_total"]):
                    item = table.item(row_idx, col)
                    if item:
                        item.setBackground(Qt.yellow)

        table.blockSignals(False)

    def _apply_process_row_state(self, row: int, scale_type: str) -> None:
        scale = str(scale_type or "").strip().upper()
        table = self.costs_process_table

        def _set_col_enabled(col: int, enabled: bool) -> None:
            item = table.item(row, col)
            if item:
                flags = item.flags()
                if enabled:
                    flags |= Qt.ItemIsEditable
                else:
                    flags &= ~Qt.ItemIsEditable
                item.setFlags(flags)

        _set_col_enabled(self._process_columns["time_total"], scale == "FIXED")
        _set_col_enabled(self._process_columns["cost_per_hour"], True)
        _set_col_enabled(self._process_columns["total_cost"], scale == "FIXED")

        if scale == "FIXED":
            _set_col_enabled(self._process_columns["setup_value"], False)
            _set_col_enabled(self._process_columns["time_per_kg"], False)
            _set_col_enabled(self._process_columns["time_total"], True)
        elif scale == "VARIABLE_PER_KG":
            _set_col_enabled(self._process_columns["setup_value"], False)
            _set_col_enabled(self._process_columns["time_per_kg"], True)
            _set_col_enabled(self._process_columns["time_total"], False)
        elif scale == "MIXED":
            _set_col_enabled(self._process_columns["setup_value"], True)
            _set_col_enabled(self._process_columns["time_per_kg"], True)
            _set_col_enabled(self._process_columns["time_total"], False)

    def _on_process_scale_changed(self, _text: str) -> None:
        if self._costs_block_signals:
            return
        combo = self.sender()
        if isinstance(combo, QComboBox):
            row = combo.property("row")
            if row is not None:
                self._update_process_from_row(int(row))

    def _on_process_setup_unit_changed(self, _text: str) -> None:
        if self._costs_block_signals:
            return
        combo = self.sender()
        if isinstance(combo, QComboBox):
            row = combo.property("row")
            if row is not None:
                self._update_process_from_row(int(row))

    def _on_process_time_unit_changed(self, _text: str) -> None:
        if self._costs_block_signals:
            return
        combo = self.sender()
        if isinstance(combo, QComboBox):
            row = combo.property("row")
            if row is not None:
                self._update_process_from_row(int(row))

    def _on_process_item_changed(self, item: QTableWidgetItem) -> None:
        if self._costs_block_signals:
            return
        if item.column() in (
            self._process_columns["name"],
            self._process_columns["setup_value"],
            self._process_columns["time_per_kg"],
            self._process_columns["time_total"],
            self._process_columns["cost_per_hour"],
            self._process_columns["total_cost"],
            self._process_columns["notes"],
        ):
            self._update_process_from_row(item.row())

    def _update_process_from_row(self, row: int) -> None:
        table = self.costs_process_table
        name_item = table.item(row, self._process_columns["name"])
        setup_value_item = table.item(row, self._process_columns["setup_value"])
        time_per_kg_item = table.item(row, self._process_columns["time_per_kg"])
        time_total_item = table.item(row, self._process_columns["time_total"])
        cost_per_hour_item = table.item(row, self._process_columns["cost_per_hour"])
        total_cost_item = table.item(row, self._process_columns["total_cost"])
        notes_item = table.item(row, self._process_columns["notes"])
        scale_combo = table.cellWidget(row, self._process_columns["scale"])
        setup_unit_combo = table.cellWidget(row, self._process_columns["setup_unit"])
        time_unit_combo = table.cellWidget(row, self._process_columns["time_unit"])

        scale_type = scale_combo.currentText() if isinstance(scale_combo, QComboBox) else "FIXED"
        setup_unit = setup_unit_combo.currentText() if isinstance(setup_unit_combo, QComboBox) else "min"
        time_unit = time_unit_combo.currentText() if isinstance(time_unit_combo, QComboBox) else "min"

        self.costs_presenter.update_process(
            row,
            name=name_item.text() if name_item else "",
            scale_type=scale_type,
            setup_time_value=setup_value_item.text() if setup_value_item else None,
            setup_time_unit=setup_unit,
            time_per_kg_value=time_per_kg_item.text() if time_per_kg_item else None,
            time_unit=time_unit,
            time_value=time_total_item.text() if time_total_item else None,
            cost_per_hour_mn=cost_per_hour_item.text() if cost_per_hour_item else None,
            total_cost_mn=total_cost_item.text() if total_cost_item else None,
            notes=notes_item.text() if notes_item else None,
        )
        self._refresh_costs_view()

    def _on_add_process_clicked(self) -> None:
        self.costs_presenter.add_process()
        self._refresh_costs_view()

    def _on_remove_process_clicked(self) -> None:
        rows = self.costs_process_table.selectionModel().selectedRows()
        if not rows:
            return
        for row in sorted((r.row() for r in rows), reverse=True):
            self.costs_presenter.remove_process(row)
        self._refresh_costs_view()

    def _populate_packaging_table(self) -> None:
        rows = self.costs_presenter.build_packaging_rows()
        table = self.costs_packaging_table
        table.blockSignals(True)
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            table.setItem(row_idx, self._packaging_columns["name"], QTableWidgetItem(row["name"] or ""))
            qty = f"{float(row['quantity_per_pack']):.3f}" if row["quantity_per_pack"] is not None else ""
            table.setItem(row_idx, self._packaging_columns["qty"], QTableWidgetItem(qty))
            unit_cost = f"{float(row['unit_cost_mn']):.3f}" if row["unit_cost_mn"] is not None else ""
            table.setItem(row_idx, self._packaging_columns["unit_cost"], QTableWidgetItem(unit_cost))
            subtotal = self._format_money(row["subtotal_mn"]) if row["subtotal_mn"] is not None else "-"
            table.setItem(row_idx, self._packaging_columns["subtotal"], self._make_readonly_item(subtotal))
            table.setItem(row_idx, self._packaging_columns["notes"], QTableWidgetItem(row["notes"] or ""))
        table.blockSignals(False)

    def _on_packaging_item_changed(self, item: QTableWidgetItem) -> None:
        if self._costs_block_signals:
            return
        if item.column() in (
            self._packaging_columns["name"],
            self._packaging_columns["qty"],
            self._packaging_columns["unit_cost"],
            self._packaging_columns["notes"],
        ):
            self._update_packaging_from_row(item.row())

    def _update_packaging_from_row(self, row: int) -> None:
        table = self.costs_packaging_table
        name_item = table.item(row, self._packaging_columns["name"])
        qty_item = table.item(row, self._packaging_columns["qty"])
        unit_cost_item = table.item(row, self._packaging_columns["unit_cost"])
        notes_item = table.item(row, self._packaging_columns["notes"])
        self.costs_presenter.update_packaging_item(
            row,
            name=name_item.text() if name_item else "",
            quantity_per_pack=qty_item.text() if qty_item else None,
            unit_cost_mn=unit_cost_item.text() if unit_cost_item else None,
            notes=notes_item.text() if notes_item else None,
        )
        self._refresh_costs_view()

    def _on_add_packaging_clicked(self) -> None:
        self.costs_presenter.add_packaging_item()
        self._refresh_costs_view()

    def _on_remove_packaging_clicked(self) -> None:
        rows = self.costs_packaging_table.selectionModel().selectedRows()
        if not rows:
            return
        for row in sorted((r.row() for r in rows), reverse=True):
            self.costs_presenter.remove_packaging_item(row)
        self._refresh_costs_view()

    def _on_yield_changed(self, value: float) -> None:
        ok, error = self.costs_presenter.set_yield_percent(Decimal(str(value)))
        if not ok and error == "yield_range":
            QMessageBox.warning(self, "Yield", "El yield debe estar entre 0 y 100.")
        self._refresh_costs_view()

    def _update_costs_calculator(self) -> None:
        target_value = self.costs_target_mass_input.value()
        target_unit = self.costs_target_unit_selector.currentText()
        data = self.costs_presenter.unit_costs_for_target_mass(target_value, target_unit)
        self.costs_target_ingredients_label.setText(
            self._format_money(data["ingredients_cost_per_target_mn"])
        )
        self.costs_target_process_label.setText(
            self._format_money(data["process_cost_per_target_mn"])
        )
        self.costs_target_total_label.setText(
            self._format_money(data["total_cost_per_target_mn"])
        )
        self.costs_packaging_total_label.setText(
            self._format_money(data["packaging_cost_per_pack_mn"])
        )
        self.costs_target_total_pack_label.setText(
            self._format_money(data["total_pack_cost_mn"])
        )
        units = data["units_count"]
        self.costs_units_count_label.setText(f"{float(units):.2f}" if units else "-")

    def _paste_ingredients_table(self) -> None:
        table = self.costs_ingredients_table
        start = table.currentRow()
        if start < 0:
            return
        clipboard = QApplication.clipboard().text()
        if not clipboard:
            return
        rows = [line.split("\t") for line in clipboard.splitlines() if line.strip()]
        if not rows:
            return
        col_start = self._ingredient_cost_columns["pack_amount"]
        for r_idx, row_values in enumerate(rows):
            target_row = start + r_idx
            if target_row >= table.rowCount():
                break
            for c_idx, value in enumerate(row_values):
                target_col = col_start + c_idx
                if target_col >= table.columnCount():
                    break
                item = table.item(target_row, target_col)
                if item is None:
                    item = QTableWidgetItem("")
                    table.setItem(target_row, target_col, item)
                item.setText(value)
        self._refresh_costs_view()
