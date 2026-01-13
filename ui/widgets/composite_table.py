from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QPainter, QPalette
from PySide6.QtWidgets import QTableWidget


class CompositeGridTable(QTableWidget):
    def __init__(self, rows: int, columns: int, parent=None) -> None:
        super().__init__(rows, columns, parent)
        self._hidden_verticals: set[int] = set()
        self._forced_verticals: set[int] = set()

    def set_hidden_vertical_borders(self, columns: Iterable[int]) -> None:
        self._hidden_verticals = set(columns)
        self.viewport().update()

    def set_forced_vertical_borders(self, columns: Iterable[int]) -> None:
        self._forced_verticals = set(columns)
        self.viewport().update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        self._cover_hidden_verticals()
        self._draw_forced_verticals()

    def _cover_hidden_verticals(self) -> None:
        if not self._hidden_verticals:
            return
        rect = self.viewport().rect()
        if rect.isNull():
            return
        painter = QPainter(self.viewport())
        selection = self.selectionModel()
        base = self.palette().color(QPalette.Base)
        alt = self.palette().color(QPalette.AlternateBase)
        highlight = self.palette().color(QPalette.Highlight)
        use_alt = self.alternatingRowColors()
        for col in self._hidden_verticals:
            if col < 0 or col >= self.columnCount():
                continue
            x = self.columnViewportPosition(col) + self.columnWidth(col) - 1
            for row in range(self.rowCount()):
                y = self.rowViewportPosition(row)
                if y < 0:
                    continue
                height = self.rowHeight(row)
                if y > rect.bottom():
                    break
                line_color = None
                if selection is not None and selection.isRowSelected(row, QModelIndex()):
                    line_color = highlight
                else:
                    item = self.item(row, col)
                    if item is not None:
                        brush = item.background()
                        if brush.style() != Qt.NoBrush:
                            line_color = brush.color()
                    if line_color is None:
                        if use_alt and row % 2 == 1:
                            line_color = alt
                        else:
                            line_color = base
                painter.setPen(line_color)
                painter.drawLine(x, y, x, y + height - 1)
        painter.end()

    def _draw_forced_verticals(self) -> None:
        if not self._forced_verticals:
            return
        rect = self.viewport().rect()
        if rect.isNull():
            return
        painter = QPainter(self.viewport())
        painter.setPen(self.palette().color(QPalette.Mid))
        for col in self._forced_verticals:
            if col < 0 or col >= self.columnCount():
                continue
            x = self.columnViewportPosition(col) + self.columnWidth(col)
            painter.drawLine(x - 1, rect.top(), x - 1, rect.bottom())
        painter.end()
