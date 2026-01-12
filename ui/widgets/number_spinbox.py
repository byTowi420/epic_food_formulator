from __future__ import annotations

from typing import Tuple

from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox

from domain.services.number_parser import parse_user_number
from ui.formatters import fmt_decimal


class UserNumberSpinBox(QDoubleSpinBox):
    def validate(self, text: str, pos: int) -> Tuple[QValidator.State, str, int]:
        if not text.strip():
            return QValidator.Intermediate, text, pos
        allowed = set("0123456789.,-+ ")
        if any(ch not in allowed for ch in text):
            return QValidator.Invalid, text, pos
        return QValidator.Acceptable, text, pos

    def valueFromText(self, text: str) -> float:  # noqa: N802
        parsed = parse_user_number(text)
        return float(parsed) if parsed is not None else 0.0

    def textFromValue(self, value: float) -> str:  # noqa: N802
        return fmt_decimal(value, decimals=self.decimals(), thousands=True)


class UserIntSpinBox(QSpinBox):
    def validate(self, text: str, pos: int) -> Tuple[QValidator.State, str, int]:
        if not text.strip():
            return QValidator.Intermediate, text, pos
        allowed = set("0123456789.,-+ ")
        if any(ch not in allowed for ch in text):
            return QValidator.Invalid, text, pos
        return QValidator.Acceptable, text, pos

    def valueFromText(self, text: str) -> int:  # noqa: N802
        parsed = parse_user_number(text)
        return int(parsed) if parsed is not None else 0

    def textFromValue(self, value: int) -> str:  # noqa: N802
        return fmt_decimal(value, decimals=0, thousands=True)
