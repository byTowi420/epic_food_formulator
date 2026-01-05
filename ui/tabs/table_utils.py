from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QHeaderView, QTableWidget

from ui.delegates.selection_bar_delegate import SelectionBarDelegate


def apply_selection_bar(table: QTableWidget) -> None:
    table.setItemDelegate(SelectionBarDelegate(parent=table))


def attach_copy_shortcut(table: QTableWidget) -> None:
    shortcut = QShortcut(QKeySequence.Copy, table)
    shortcut.setContext(Qt.WidgetWithChildrenShortcut)
    shortcut.activated.connect(lambda t=table: copy_table_selection(t))


def copy_table_selection(table: QTableWidget) -> None:
    sel_model = table.selectionModel()
    if not sel_model or not sel_model.hasSelection():
        return
    ranges = table.selectedRanges()
    if not ranges:
        return
    selected_range = ranges[0]
    rows = range(selected_range.topRow(), selected_range.bottomRow() + 1)
    cols = range(selected_range.leftColumn(), selected_range.rightColumn() + 1)

    headers: list[str] = []
    for col in cols:
        header_item = table.horizontalHeaderItem(col)
        headers.append(header_item.text() if header_item else "")
    lines = ["\t".join(headers)]

    for row in rows:
        row_vals: list[str] = []
        for col in cols:
            item = table.item(row, col)
            row_vals.append("" if item is None else item.text())
        lines.append("\t".join(row_vals))

    QApplication.clipboard().setText("\n".join(lines))


def set_search_column_widths(
    table: QTableWidget,
    details_table: QTableWidget,
    formulation_preview: QTableWidget,
) -> None:
    for view in (table, details_table, formulation_preview):
        header = view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)

    table.setColumnWidth(0, 75)   # FDC ID
    table.setColumnWidth(1, 340)  # Descripcion
    table.setColumnWidth(2, 200)  # Marca / Origen
    table.setColumnWidth(3, 120)  # Tipo de dato

    details_table.setColumnWidth(0, 200)  # Nutriente
    details_table.setColumnWidth(1, 90)   # Cantidad
    details_table.setColumnWidth(2, 70)   # Unidad

    formulation_preview.setColumnWidth(0, 70)  # FDC ID
    formulation_preview.setColumnWidth(1, 290)  # Ingrediente


def set_formulation_column_widths(
    formulation_table: QTableWidget,
    totals_table: QTableWidget,
) -> None:
    for view in (formulation_table, totals_table):
        header = view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)

    formulation_table.setColumnWidth(0, 75)   # FDC ID
    formulation_table.setColumnWidth(1, 330)  # Ingrediente
    formulation_table.setColumnWidth(2, 95)   # Cantidad (g)
    formulation_table.setColumnWidth(3, 85)   # Cantidad (%)
    formulation_table.setColumnWidth(4, 65)   # Fijar %
    formulation_table.setColumnWidth(5, 150)  # Marca / Origen

    totals_table.setColumnWidth(0, 210)  # Nutriente
    totals_table.setColumnWidth(1, 85)   # Total
    totals_table.setColumnWidth(2, 60)   # Unidad
    totals_table.setColumnWidth(3, 80)   # Exportar
