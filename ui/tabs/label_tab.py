from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def build_label_tab_ui(self: "MainWindow") -> None:
    """Build the Label tab UI."""
    # Layout principal del tab de etiqueta.
    layout = QVBoxLayout(self.label_tab)
    layout.setSpacing(10)

    # Seccion superior con controles y vista vertical.
    top_layout = QHBoxLayout()
    top_layout.setSpacing(12)

    # Grupo izquierdo: controles de rotulado nutricional.
    left_group = QGroupBox("Rotulado Nutricional")
    left_form = QGridLayout()
    left_form.setContentsMargins(10, 10, 10, 10)
    left_form.setHorizontalSpacing(8)
    left_form.setVerticalSpacing(6)
    left_group.setLayout(left_form)

    # Tamano de porcion y unidad.
    left_form.addWidget(QLabel("Tamaño Porción:"), 0, 0)
    self.portion_size_input = QSpinBox()
    self.portion_size_input.setRange(1, 100000)
    self.portion_size_input.setValue(100)
    self.portion_unit_combo = QComboBox()
    self.portion_unit_combo.addItems(["g", "ml"])
    portion_widget = QWidget()
    portion_layout = QHBoxLayout(portion_widget)
    portion_layout.setContentsMargins(0, 0, 0, 0)
    portion_layout.setSpacing(6)
    portion_layout.addWidget(self.portion_size_input)
    portion_layout.addWidget(self.portion_unit_combo)
    left_form.addWidget(portion_widget, 0, 1, 1, 2)

    # Medida casera.
    left_form.addWidget(QLabel("Medida Casera:"), 1, 0)
    self.household_amount_input = QLineEdit()
    self.household_amount_input.setPlaceholderText("1/2, 2/3, 1 1/2")
    self.household_amount_input.setText("1/2")
    self.household_unit_combo = QComboBox()
    for name, _ in self.household_measure_options:
        self.household_unit_combo.addItem(name)
    unidad_index = self.household_unit_combo.findText("Unidad")
    if unidad_index >= 0:
        self.household_unit_combo.setCurrentIndex(unidad_index)
    measure_widget = QWidget()
    measure_layout = QHBoxLayout(measure_widget)
    measure_layout.setContentsMargins(0, 0, 0, 0)
    measure_layout.setSpacing(6)
    measure_layout.addWidget(self.household_amount_input)
    measure_layout.addWidget(self.household_unit_combo)
    left_form.addWidget(measure_widget, 1, 1, 1, 2)

    # Unidad casera personalizada (solo si aplica).
    self.custom_household_unit_input = QLineEdit()
    self.custom_household_unit_input.setPlaceholderText(
        "Ej.: Envase, Barrita, Paquete"
    )
    self.custom_household_unit_input.setVisible(False)
    left_form.addWidget(self.custom_household_unit_input, 2, 1, 1, 2)

    # Capacidad informativa.
    left_form.addWidget(QLabel("Capacidad o dimensión:"), 3, 0)
    self.household_capacity_label = QLabel("-")
    self.household_capacity_label.setStyleSheet("color: gray;")
    left_form.addWidget(self.household_capacity_label, 3, 1, 1, 2)

    # Opciones de desglose.
    self.breakdown_carb_checkbox = QCheckBox("Desglose Carbohidratos")
    self.breakdown_carb_checkbox.setEnabled(True)
    self.breakdown_fat_checkbox = QCheckBox("Desglose Grasas")
    self.breakdown_fat_checkbox.setEnabled(True)
    left_form.addWidget(self.breakdown_carb_checkbox, 4, 0, 1, 2)
    left_form.addWidget(self.breakdown_fat_checkbox, 4, 2)

    # Selecciones guiadas de nutrientes.
    left_form.addWidget(QLabel("Sin aportes significativos:"), 5, 0)
    self.no_significant_display = QLineEdit()
    self.no_significant_display.setReadOnly(True)
    self.no_significant_display.setPlaceholderText("Seleccione nutrientes elegibles")
    self.no_significant_display.setCursor(Qt.PointingHandCursor)
    left_form.addWidget(self.no_significant_display, 5, 1, 1, 2)

    left_form.addWidget(QLabel("Nutrientes Adicionales:"), 6, 0)
    self.additional_nutrients_display = QLineEdit()
    self.additional_nutrients_display.setReadOnly(True)
    self.additional_nutrients_display.setPlaceholderText("Seleccione nutrientes adicionales")
    self.additional_nutrients_display.setCursor(Qt.PointingHandCursor)
    left_form.addWidget(self.additional_nutrients_display, 6, 1, 1, 2)

    self.label_placeholder_note = QLabel(
        "Espacio reservado para botones de desglose y futuras acciones."
    )
    self.label_placeholder_note.setStyleSheet("color: gray; font-style: italic;")
    left_form.addWidget(self.label_placeholder_note, 7, 0, 1, 3)
    left_form.setRowStretch(8, 1)

    # Grupo derecho: tabla vertical de etiqueta.
    right_group = QGroupBox("Formato Vertical")
    right_layout = QVBoxLayout()
    right_group.setLayout(right_layout)

    # Nota de valores manuales.
    self.manual_note_label = QLabel("Verde: valor manual (Doble clic para editar)")
    self.manual_note_label.setStyleSheet("color: #2e7d32; font-style: italic;")
    note_row = QHBoxLayout()
    note_row.addStretch()
    note_row.addWidget(self.manual_note_label)
    right_layout.addLayout(note_row)

    # Tabla principal de etiqueta.
    self.label_table_widget = QTableWidget()
    self._setup_label_table_widget()
    # Configurar el delegado si expone roles personalizados.
    delegate = self.label_table_widget.itemDelegate()
    if hasattr(delegate, "header_span_role"):
        delegate.header_span_role = self._header_span_role
    if hasattr(delegate, "manual_role"):
        delegate.manual_role = self._manual_role
    if hasattr(delegate, "manual_color"):
        delegate.manual_color = self.label_manual_hint_color
    right_layout.addWidget(self.label_table_widget)

    # Exportacion de imagen.
    export_layout = QHBoxLayout()
    export_layout.addStretch()
    export_layout.addWidget(QLabel("Exportar tabla como png:"))
    self.export_label_no_bg_button = QPushButton("Sin Fondo")
    self.export_label_with_bg_button = QPushButton("Con Fondo")
    export_layout.addWidget(self.export_label_no_bg_button)
    export_layout.addWidget(self.export_label_with_bg_button)
    export_layout.addStretch()
    right_layout.addLayout(export_layout)

    top_layout.addWidget(left_group, 1)
    top_layout.addWidget(right_group, 1)
    layout.addLayout(top_layout, 3)

    # Formato lineal.
    linear_group = QGroupBox("Formato Lineal")
    linear_layout = QVBoxLayout()
    linear_group.setLayout(linear_layout)
    self.linear_format_preview = QPlainTextEdit()
    self.linear_format_preview.setReadOnly(True)
    self.linear_format_preview.setStyleSheet(
        "background-color: #f5f5f5; color: #333;"
    )
    self.linear_format_preview.setMinimumHeight(140)
    linear_layout.addWidget(self.linear_format_preview)
    layout.addWidget(linear_group, 1)

    # Conexiones de eventos.
    self.portion_size_input.valueChanged.connect(self._on_portion_value_changed)
    self.portion_unit_combo.currentTextChanged.connect(
        self._on_portion_unit_changed
    )
    self.household_unit_combo.currentTextChanged.connect(
        self._on_household_unit_changed
    )
    self.household_amount_input.textChanged.connect(
        self._on_household_amount_changed
    )
    self.custom_household_unit_input.textChanged.connect(
        self._on_household_unit_changed
    )
    self.breakdown_carb_checkbox.toggled.connect(self._on_breakdown_carb_toggled)
    self.breakdown_fat_checkbox.toggled.connect(self._on_breakdown_fat_toggled)
    self.export_label_no_bg_button.clicked.connect(
        lambda: self._on_export_label_table_clicked(with_background=False)
    )
    self.export_label_with_bg_button.clicked.connect(
        lambda: self._on_export_label_table_clicked(with_background=True)
    )
    self.label_table_widget.cellDoubleClicked.connect(
        self._on_label_table_cell_double_clicked
    )
    self._attach_copy_shortcut(self.label_table_widget)
    self.no_significant_display.installEventFilter(self)
    self.additional_nutrients_display.installEventFilter(self)

    # Estado inicial del formulario.
    self._update_capacity_label()
    self._auto_fill_household_measure()
    self._update_label_preview(force_recalc_totals=True)
