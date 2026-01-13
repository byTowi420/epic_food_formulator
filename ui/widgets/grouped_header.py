from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHeaderView, QStyle, QStyleOptionHeader


class GroupedHeaderView(QHeaderView):
    def __init__(self, orientation: Qt.Orientation, parent=None) -> None:
        super().__init__(orientation, parent)
        self._groups: dict[int, tuple[int, str]] = {}
        self._right_to_left: dict[int, int] = {}
        self.setDefaultAlignment(Qt.AlignCenter)
        self.setSectionsClickable(True)

    def set_groups(self, groups: Iterable[tuple[int, int, str]]) -> None:
        self._groups.clear()
        self._right_to_left.clear()
        for left, right, label in groups:
            self._groups[int(left)] = (int(right), str(label))
            self._right_to_left[int(right)] = int(left)
        self.viewport().update()

    def left_for_section(self, section: int) -> int:
        if section in self._groups:
            return section
        return self._right_to_left.get(section, section)

    def paintSection(self, painter: QPainter, rect: QRect, logical_index: int) -> None:  # noqa: N802
        left = self.left_for_section(logical_index)
        if left in self._groups:
            right, label = self._groups[left]
            x = self.sectionViewportPosition(left)
            if x < 0:
                return
            width = self.sectionSize(left) + self.sectionSize(right)
            span_rect = QRect(x, rect.y(), width, rect.height())
            option = QStyleOptionHeader()
            self.initStyleOption(option)
            option.rect = span_rect
            option.section = left
            option.text = label
            option.textAlignment = Qt.AlignCenter
            if left == 0 and right == self.count() - 1:
                option.position = QStyleOptionHeader.OnlyOneSection
            elif left == 0:
                option.position = QStyleOptionHeader.Beginning
            elif right == self.count() - 1:
                option.position = QStyleOptionHeader.End
            else:
                option.position = QStyleOptionHeader.Middle
            if self.isSortIndicatorShown() and self.sortIndicatorSection() == left:
                option.sortIndicator = (
                    QStyleOptionHeader.SortDown
                    if self.sortIndicatorOrder() == Qt.DescendingOrder
                    else QStyleOptionHeader.SortUp
                )
            painter.save()
            painter.setClipRect(span_rect, Qt.ReplaceClip)
            self.style().drawControl(QStyle.CE_Header, option, painter, self)
            painter.restore()
            return
        super().paintSection(painter, rect, logical_index)
