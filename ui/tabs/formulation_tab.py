from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def build_formulation_tab_ui(self: "MainWindow") -> None:
    """Build the Formulation tab UI."""
    # Layout base del tab de formulacion.
    layout = QVBoxLayout(self.formulation_tab)

    # Encabezado: export/import, nombre y unidad.
    header_layout = QHBoxLayout()
    self.export_state_button = QPushButton("Exportar")
    self.import_state_button = QPushButton("Importar")
    header_layout.addWidget(self.export_state_button)
    header_layout.addWidget(self.import_state_button)
    header_layout.addStretch()
    self.formula_name_input = QLineEdit()
    self.formula_name_input.setPlaceholderText(
        "Nombre Fórmula Ej.: Pan dulce con chocolate"
    )
    self.formula_name_input.setAlignment(Qt.AlignCenter)
    header_layout.addWidget(self.formula_name_input, 1)
    header_layout.addStretch()
    header_layout.addWidget(QLabel("Unidad de formulación:"))
    self.quantity_mode_selector = QComboBox()
    self.quantity_mode_selector.addItems(["Gramos (g)", "Porcentaje (%)"])
    header_layout.addWidget(self.quantity_mode_selector)
    layout.addLayout(header_layout)

    # Tabla principal de ingredientes.
    self.formulation_table = QTableWidget(0, 6)
    self.formulation_table.setHorizontalHeaderLabels(
        [
            "FDC ID",
            "Ingrediente",
            "Cantidad (g)",
            "Cantidad (%)",
            "Fijar %",
            "Marca / Origen",
        ]
    )
    self.formulation_table.setEditTriggers(QTableWidget.NoEditTriggers)
    self.formulation_table.setSelectionBehavior(QTableWidget.SelectRows)
    self.formulation_table.setSelectionMode(QTableWidget.ExtendedSelection)
    self.formulation_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.formulation_table.horizontalHeader().setStretchLastSection(True)
    layout.addWidget(self.formulation_table)

    # Acciones sobre ingredientes.
    buttons_layout = QHBoxLayout()
    self.edit_quantity_button = QPushButton("Editar cantidad seleccionada")
    self.remove_formulation_button = QPushButton(
        "Eliminar ingrediente seleccionado"
    )
    buttons_layout.addWidget(self.edit_quantity_button)
    buttons_layout.addWidget(self.remove_formulation_button)
    buttons_layout.addStretch()
    layout.addLayout(buttons_layout)

    # Totales nutricionales.
    layout.addWidget(
        QLabel(
            "Totales nutricionales (asumiendo valores por 100 g del alimento origen)"
        )
    )
    self.totals_table = QTableWidget(0, 4)
    self.totals_table.setHorizontalHeaderLabels(
        ["Nutriente", "Total", "Unidad", "Exportar"]
    )
    export_header = QTableWidgetItem("Exportar")
    export_header.setIcon(self._create_question_icon())
    export_header.setToolTip(
        "Los nutrientes seleccionados seran exportados al excel"
    )
    self.totals_table.setHorizontalHeaderItem(3, export_header)
    self.totals_table.setEditTriggers(QTableWidget.NoEditTriggers)
    self.totals_table.setSelectionBehavior(QTableWidget.SelectRows)
    self.totals_table.setSelectionMode(QTableWidget.ExtendedSelection)
    self.totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.totals_table.horizontalHeader().setStretchLastSection(True)
    layout.addWidget(self.totals_table)

    # Acciones de exportacion.
    export_buttons_layout = QHBoxLayout()
    self.toggle_export_button = QPushButton("Deseleccionar todos")
    self.export_excel_button = QPushButton("Exportar a Excel")
    export_buttons_layout.addStretch()
    export_buttons_layout.addWidget(self.toggle_export_button)
    export_buttons_layout.addWidget(self.export_excel_button)
    export_buttons_layout.addStretch()
    layout.addLayout(export_buttons_layout)

    # Conexiones de eventos.
    self.remove_formulation_button.clicked.connect(
        self.on_remove_formulation_clicked
    )
    self.export_excel_button.clicked.connect(self.on_export_to_excel_clicked)
    self.quantity_mode_selector.currentIndexChanged.connect(
        self.on_quantity_mode_changed
    )
    self.formulation_table.cellDoubleClicked.connect(
        self.on_formulation_cell_double_clicked
    )
    self.edit_quantity_button.clicked.connect(self.on_edit_quantity_clicked)
    self.formulation_table.itemChanged.connect(self.on_lock_toggled_from_table)
    self.totals_table.itemChanged.connect(self.on_totals_checkbox_changed)
    self.toggle_export_button.clicked.connect(self.on_toggle_export_clicked)
    self.export_state_button.clicked.connect(self.on_export_state_clicked)
    self.import_state_button.clicked.connect(self.on_import_state_clicked)

    # Atajos de copia para tablas (Ctrl+C).
    # Copy shortcuts (Ctrl+C) for all tables
    for table in (
        self.table,
        self.details_table,
        self.formulation_preview,
        self.formulation_table,
        self.totals_table,
    ):
        self._attach_copy_shortcut(table)

    # Ajuste inicial de columnas.
    self._set_default_column_widths(formulation=True)
