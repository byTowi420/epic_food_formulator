from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def build_search_tab_ui(self: "MainWindow") -> None:
    """Build the Search tab UI."""
    # Layout base del tab de busqueda.
    layout = QVBoxLayout(self.search_tab)
    layout.setSpacing(6)

    # Barra de busqueda.
    search_layout = QHBoxLayout()
    self.search_input = QLineEdit()
    self.search_input.setPlaceholderText(
        "Buscar alimento (ej: apple, rice, cheese)..."
    )
    self.search_button = QPushButton("Buscar")

    search_layout.addWidget(self.search_input)
    search_layout.addWidget(self.search_button)

    # Filtros y paginado.
    self.include_brands_checkbox = QCheckBox("Incluir Marcas")
    self.prev_page_button = QPushButton("<")
    self.prev_page_button.setFixedWidth(32)
    self.next_page_button = QPushButton(">")
    self.next_page_button.setFixedWidth(32)
    self.prev_page_button.setEnabled(False)
    self.next_page_button.setEnabled(False)

    # Controles legacy ocultos (buscar por FDC y botón de agregar)
    self.fdc_id_input = QLineEdit()
    self.fdc_id_input.hide()
    self.fdc_id_button = QPushButton("Cargar FDC ID")
    self.fdc_id_button.hide()
    self.add_button = QPushButton("Agregar seleccionado a formulación")
    self.add_button.hide()

    # Estado y feedback de la busqueda.
    self.status_label = QLabel("")
    self.status_label.setAlignment(Qt.AlignLeft)
    self.status_label.setStyleSheet("color: gray;")
    self.status_label.setTextInteractionFlags(
        Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
    )
    self.status_label.setWordWrap(True)
    self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    self.status_label.setMaximumHeight(
        int(self.status_label.fontMetrics().height() * 2.4)
    )

    layout.addLayout(search_layout)
    status_controls_layout = QHBoxLayout()
    status_controls_layout.setContentsMargins(0, 0, 0, 0)
    status_controls_layout.addWidget(self.status_label, 1)
    status_controls_layout.addStretch()
    status_controls_layout.addWidget(self.include_brands_checkbox)
    status_controls_layout.addWidget(self.prev_page_button)
    status_controls_layout.addWidget(self.next_page_button)
    layout.addLayout(status_controls_layout)

    # Tablas de resultados y detalles.
    # Tabla de resultados (arriba)
    self.table = QTableWidget(0, 4)
    self.table.setHorizontalHeaderLabels(
        ["FDC ID", "Descripción", "Marca / Origen", "Tipo de dato"]
    )
    self.table.setEditTriggers(QTableWidget.NoEditTriggers)
    self.table.setSelectionBehavior(QTableWidget.SelectRows)
    self.table.setSelectionMode(QTableWidget.ExtendedSelection)
    self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.table.horizontalHeader().setStretchLastSection(True)

    self.details_table = QTableWidget(0, 3)
    self.details_table.setHorizontalHeaderLabels(
        ["Nutriente", "Cantidad", "Unidad"]
    )
    self.details_table.setEditTriggers(QTableWidget.NoEditTriggers)
    self.details_table.setSelectionBehavior(QTableWidget.SelectRows)
    self.details_table.setSelectionMode(QTableWidget.ExtendedSelection)
    self.details_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    self.details_table.horizontalHeader().setStretchLastSection(True)

    # Panel inferior: preview de formulacion + nutrientes.
    bottom_layout = QHBoxLayout()

    left_panel = QVBoxLayout()
    left_panel.addWidget(QLabel("Ingredientes en formulación"))
    self.formulation_preview = QTableWidget(0, 2)
    self.formulation_preview.setHorizontalHeaderLabels(["FDC ID", "Ingrediente"])
    self.formulation_preview.setEditTriggers(QTableWidget.NoEditTriggers)
    self.formulation_preview.setSelectionBehavior(QTableWidget.SelectRows)
    self.formulation_preview.setSelectionMode(QTableWidget.ExtendedSelection)
    self.formulation_preview.horizontalHeader().setStretchLastSection(True)
    left_panel.addWidget(self.formulation_preview)

    self.remove_preview_button = QPushButton("Eliminar ingrediente seleccionado")
    left_panel.addWidget(self.remove_preview_button)

    right_panel = QVBoxLayout()
    right_panel.addWidget(QLabel("Nutrientes del ingrediente seleccionado"))
    right_panel.addWidget(self.details_table)

    bottom_layout.addLayout(left_panel, 1)
    bottom_layout.addLayout(right_panel, 1)

    bottom_widget = QWidget()
    bottom_widget.setLayout(bottom_layout)

    splitter = QSplitter(Qt.Vertical)
    splitter.addWidget(self.table)
    splitter.addWidget(bottom_widget)
    splitter.setStretchFactor(0, 3)
    splitter.setStretchFactor(1, 2)
    splitter.setSizes([400, 500])

    layout.addWidget(splitter)

    # Conexiones de eventos.
    self.search_button.clicked.connect(self.on_search_clicked)
    self.search_input.returnPressed.connect(self.on_search_clicked)
    self.table.cellDoubleClicked.connect(self.on_result_double_clicked)
    self.table.itemSelectionChanged.connect(self.on_search_selection_changed)
    self.remove_preview_button.clicked.connect(self.on_remove_preview_clicked)
    self.formulation_preview.cellDoubleClicked.connect(
        self.on_formulation_preview_double_clicked
    )
    self.formulation_preview.itemSelectionChanged.connect(
        self.on_preview_selection_changed
    )
    self.prev_page_button.clicked.connect(self.on_prev_page_clicked)
    self.next_page_button.clicked.connect(self.on_next_page_clicked)
    self.include_brands_checkbox.stateChanged.connect(
        self.on_include_brands_toggled
    )
    # Ajuste inicial de columnas.
    self._set_default_column_widths()
