from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPalette
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem, QStyledItemDelegate, QWidget


class LabelTableDelegate(QStyledItemDelegate):
    """Custom grid painter to hide vertical separators for fat breakdown rows."""

    def __init__(
        self,
        fat_row_role: int,
        parent: QWidget | None = None,
        manual_role: int | None = None,
        manual_color: QColor | None = None,
    ) -> None:
        super().__init__(parent)
        self.fat_row_role = fat_row_role
        self.header_span_role = None
        self.manual_role = manual_role
        self.manual_color = manual_color or QColor(204, 255, 204)
        self.manual_overlay = QColor(0, 0, 0, 50)
        self.selection_fill_active = QColor(0, 0, 0, 22)
        self.selection_fill_inactive = QColor(0, 0, 0, 12)
        # Color fijo para la barrita de selección personalizada
        self.handle_color = QColor("#1f6fbd")
        self.grid_color = QColor("#c0c0c0")

    def paint(self, painter: QPainter, option, index) -> None:  # type: ignore[override]
        is_fat_child = bool(index.data(self.fat_row_role))
        is_header_span = bool(self.header_span_role and index.data(self.header_span_role))
        is_manual = bool(self.manual_role and index.data(self.manual_role))
        is_selected = bool(option.state & QStyle.State_Selected)
        is_active = bool(option.state & QStyle.State_Active)

        # Base fill for manual values (under the text/content).
        if is_manual:
            painter.save()
            painter.fillRect(option.rect, self.manual_color)
            if is_selected:
                painter.fillRect(option.rect, self.manual_overlay)
            painter.restore()
        elif is_selected:
            painter.save()
            base_color = self._resolve_background_color(option)
            painter.fillRect(option.rect, base_color)
            painter.restore()

        # For fat-child name column, avoid elide and draw across the adjacent amount column.
        if (is_fat_child and index.column() == 0) or (is_header_span and index.column() == 1):
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            opt.state &= ~(QStyle.State_HasFocus | QStyle.State_Selected)
            opt.palette.setBrush(QPalette.Base, Qt.transparent)
            opt.palette.setBrush(QPalette.Window, Qt.transparent)
            opt.palette.setBrush(QPalette.AlternateBase, Qt.transparent)
            opt.palette.setBrush(QPalette.Highlight, Qt.transparent)
            opt.palette.setBrush(QPalette.HighlightedText, opt.palette.brush(QPalette.Text))
            opt.backgroundBrush = QBrush(Qt.transparent)
            opt.text = ""
            opt.icon = QIcon()
            style = opt.widget.style() if opt.widget else QApplication.style()
            style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

            painter.save()
            text_rect = opt.rect
            extra = 0
            if is_fat_child:
                try:
                    extra = opt.widget.columnWidth(1) - 6  # leave small gap before amount text
                except Exception:
                    extra = 0
                if extra > 0:
                    text_rect.setWidth(text_rect.width() + extra)
                text_rect.adjust(4, 0, -2, 0)  # small padding, avoid hitting amount text
                align = Qt.AlignLeft | Qt.AlignVCenter
            else:
                # Header span: extend into VD column to avoid elide, keep centered on its own column.
                try:
                    extra = opt.widget.columnWidth(2) - 6
                except Exception:
                    extra = 0
                if extra > 0:
                    shift = extra // 2
                    text_rect.adjust(-shift, 0, extra - shift, 0)
                text_rect.adjust(0, 0, -2, 0)
                align = Qt.AlignCenter
            painter.setPen(opt.palette.color(QPalette.Text))
            painter.setFont(opt.font)
            painter.drawText(text_rect, align, str(index.data() or ""))
            painter.restore()
        else:
            # Camino normal sin super().paint para evitar que Qt re-inserte State_Selected
            base_opt = QStyleOptionViewItem(option)
            self.initStyleOption(base_opt, index)
            # Quitar selección/foco para que Qt no pinte su highlight nativo
            base_opt.state &= ~(QStyle.State_HasFocus | QStyle.State_Selected)
            base_opt.palette.setBrush(QPalette.Base, Qt.transparent)
            base_opt.palette.setBrush(QPalette.Window, Qt.transparent)
            base_opt.palette.setBrush(QPalette.AlternateBase, Qt.transparent)
            base_opt.palette.setBrush(QPalette.Highlight, Qt.transparent)
            base_opt.palette.setBrush(QPalette.HighlightedText, base_opt.palette.brush(QPalette.Text))
            base_opt.backgroundBrush = QBrush(Qt.transparent)
            # Dibujar manualmente el item (lo que hace QStyledItemDelegate por dentro)
            style = base_opt.widget.style() if base_opt.widget else QApplication.style()
            style.drawControl(QStyle.CE_ItemViewItem, base_opt, painter, base_opt.widget)

        painter.save()
        pen = QPen(self.grid_color)
        painter.setPen(pen)
        rect = option.rect
        last_col = index.model().columnCount() - 1

        # Horizontal lines
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if index.row() == 0:
            painter.drawLine(rect.topLeft(), rect.topRight())

        # Left border on first column
        if index.column() == 0:
            painter.drawLine(rect.topLeft(), rect.bottomLeft())

        # Right border (skip inner separators for fat breakdown rows and header span left edge)
        skip_right = False
        if is_fat_child and index.column() < last_col:
            skip_right = True
        if is_header_span and index.column() in (0, 1):
            skip_right = True
        if not skip_right:
            painter.drawLine(rect.topRight(), rect.bottomRight())

        painter.restore()

        # Draw selection bar on all selected cells (our custom handle)
        if is_selected:
            painter.save()
            self._draw_selection_handles(painter, option.rect, option.palette, index)
            painter.restore()

    def _resolve_background_color(self, option: QStyleOptionViewItem) -> QColor:
        widget = option.widget
        parent = widget.parentWidget() if widget else None
        while parent is not None:
            palette = parent.palette()
            for role in (QPalette.Window, QPalette.Base, QPalette.AlternateBase):
                color = palette.color(role)
                if color.alpha() > 0 and color.value() > 0:
                    return color
            parent = parent.parentWidget()
        app_palette = QApplication.palette()
        for role in (QPalette.Window, QPalette.Base, QPalette.AlternateBase):
            color = app_palette.color(role)
            if color.alpha() > 0 and color.value() > 0:
                return color
        return QColor("#ffffff")

    def _draw_selection_handles(self, painter: QPainter, rect, palette: QPalette, index) -> None:
        """Draw thin selection marker on the left edge of the cell."""
        color = self.handle_color
        width = 2
        painter.fillRect(rect.left(), rect.top(), width, rect.height(), color)


