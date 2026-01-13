from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem

from domain.services.number_parser import parse_user_number


class SortableTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other: "QTableWidgetItem") -> bool:
        role = Qt.UserRole
        left_key = self.data(role)
        right_key = other.data(role)
        if left_key is not None or right_key is not None:
            return _normalize_sort_key(left_key) < _normalize_sort_key(right_key)
        return super().__lt__(other)


def _normalize_sort_key(key):
    if key is None:
        return (1, 0)
    if isinstance(key, tuple):
        return key
    return (0, key)


def sort_key_numeric(value) -> tuple[int, float]:
    if value is None:
        return (1, 0.0)
    parsed = parse_user_number(value)
    if parsed is None:
        return (1, 0.0)
    try:
        return (0, float(parsed))
    except Exception:
        return (1, 0.0)


def sort_key_text(value: str | None) -> tuple[int, str]:
    text = str(value or "").strip().lower()
    if not text:
        return (1, "")
    return (0, text)
