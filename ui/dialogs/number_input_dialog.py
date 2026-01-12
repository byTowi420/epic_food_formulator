from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout

from domain.services.number_parser import parse_user_number
from ui.widgets.number_spinbox import UserNumberSpinBox


class NumberInputDialog(QDialog):
    def __init__(
        self,
        parent,
        *,
        title: str,
        label: str,
        value: float,
        min_value: float,
        max_value: float,
        decimals: int,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._result: Decimal | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.value_input = UserNumberSpinBox(self)
        self.value_input.setRange(min_value, max_value)
        self.value_input.setDecimals(decimals)
        self.value_input.setValue(value)
        form.addRow(QLabel(label), self.value_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:  # noqa: N802
        value = parse_user_number(self.value_input.text())
        if value is None:
            self._result = None
        else:
            self._result = value
        super().accept()

    def result_value(self) -> Decimal | None:
        return self._result
