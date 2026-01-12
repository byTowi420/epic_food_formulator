from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QMessageBox, QVBoxLayout

from domain.services.number_parser import parse_user_number
from domain.services.unit_normalizer import convert_mass, normalize_mass_unit
from ui.widgets.number_spinbox import UserNumberSpinBox


class NormalizeMassDialog(QDialog):
    MAX_TON = Decimal("1000")
    MAX_G = Decimal("1000000000")

    def __init__(
        self,
        parent,
        *,
        current_total_g: float,
        current_unit: str,
        decimals_for_unit: Callable[[str], int] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Normalizar masa")
        self._decimals_for_unit = decimals_for_unit

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.value_input = UserNumberSpinBox(self)
        self.value_input.setRange(0.01, float(self.MAX_G))
        self.value_input.setDecimals(3)

        self.unit_combo = QComboBox(self)
        self.unit_combo.addItems(["g", "kg", "lb", "oz", "ton"])

        unit = normalize_mass_unit(current_unit) or "g"
        idx = self.unit_combo.findText(unit)
        if idx >= 0:
            self.unit_combo.setCurrentIndex(idx)
        self._current_unit = unit

        self._sync_unit_limits()
        start_value = convert_mass(current_total_g, "g", unit) or current_total_g
        self.value_input.setValue(float(start_value))

        row_widget = self._build_row_widget()
        form.addRow("Masa total objetivo:", row_widget)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        self._result: tuple[Decimal, str, Decimal] | None = None

    def _build_row_widget(self):
        from PySide6.QtWidgets import QHBoxLayout, QWidget

        row_widget = QWidget(self)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.value_input)
        row_layout.addWidget(self.unit_combo)
        return row_widget

    def _sync_unit_limits(self) -> None:
        unit = normalize_mass_unit(self.unit_combo.currentText()) or "g"
        max_value = convert_mass(self.MAX_G, "g", unit) or self.MAX_G
        self.value_input.setMaximum(float(max_value))
        if self._decimals_for_unit:
            self.value_input.setDecimals(self._decimals_for_unit(unit))

    def _on_unit_changed(self) -> None:
        new_unit = normalize_mass_unit(self.unit_combo.currentText()) or "g"
        if new_unit == self._current_unit:
            self._sync_unit_limits()
            return

        current_value = parse_user_number(self.value_input.text())
        if current_value is None:
            current_value = Decimal(str(self.value_input.value()))

        value_g = convert_mass(current_value, self._current_unit, "g")
        if value_g is None:
            value_g = current_value
        new_value = convert_mass(value_g, "g", new_unit)
        if new_value is None:
            new_value = current_value

        self._current_unit = new_unit
        self._sync_unit_limits()
        max_value = Decimal(str(self.value_input.maximum()))
        if new_value > max_value:
            new_value = max_value
        self.value_input.setValue(float(new_value))

    def accept(self) -> None:  # noqa: N802
        unit = normalize_mass_unit(self.unit_combo.currentText()) or "g"
        raw_value = self.value_input.text()
        value_dec = parse_user_number(raw_value)
        if value_dec is None or value_dec <= 0:
            QMessageBox.warning(self, "Valor inválido", "Ingresa una masa total válida.")
            return

        target_g = convert_mass(value_dec, unit, "g")
        if target_g is None or target_g <= 0:
            QMessageBox.warning(self, "Valor inválido", "Ingresa una masa total válida.")
            return
        if target_g > self.MAX_G:
            QMessageBox.warning(
                self,
                "Valor inválido",
                "La masa total supera el máximo permitido (1000 ton).",
            )
            return

        self._result = (value_dec, unit, target_g)
        super().accept()

    def result_values(self) -> tuple[Decimal, str, Decimal] | None:
        return self._result
