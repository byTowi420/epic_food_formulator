from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyleOptionViewItem,
    QStyledItemDelegate,
)


class SelectionBarDelegate(QStyledItemDelegate):
    """Delegate that draws a left-edge selection bar and removes focus rects."""

    def __init__(
        self,
        parent: QWidget | None = None,
        handle_color: QColor | None = None,
        handle_width: int = 2,
    ) -> None:
        super().__init__(parent)
        self.handle_color = handle_color or QColor("#1f6fbd")
        self.handle_width = handle_width

    def paint(self, painter: QPainter, option, index) -> None:  # type: ignore[override]
        is_selected = bool(option.state & QStyle.State_Selected)

        if is_selected:
            painter.save()
            base_color = option.palette.color(QPalette.Base)
            if base_color.alpha() == 0:
                base_color = option.palette.color(QPalette.Window)
            if base_color.alpha() == 0:
                base_color = QColor("#ffffff")
            painter.fillRect(option.rect, base_color)
            painter.restore()

        base_opt = QStyleOptionViewItem(option)
        self.initStyleOption(base_opt, index)
        base_opt.state &= ~(QStyle.State_HasFocus | QStyle.State_Selected)
        base_opt.palette.setBrush(QPalette.Base, QBrush(Qt.transparent))
        base_opt.palette.setBrush(QPalette.Window, QBrush(Qt.transparent))
        base_opt.palette.setBrush(QPalette.AlternateBase, QBrush(Qt.transparent))
        base_opt.palette.setBrush(QPalette.Highlight, QBrush(Qt.transparent))
        base_opt.palette.setBrush(
            QPalette.HighlightedText, base_opt.palette.brush(QPalette.Text)
        )
        base_opt.backgroundBrush = QBrush(Qt.transparent)
        style = base_opt.widget.style() if base_opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, base_opt, painter, base_opt.widget)

        if is_selected:
            painter.save()
            rect = option.rect
            painter.fillRect(
                rect.left(), rect.top(), self.handle_width, rect.height(), self.handle_color
            )
            painter.restore()
