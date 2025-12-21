"""Label tab UI component."""

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
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
    QHeaderView,
)

from ui.delegates.label_table_delegate import LabelTableDelegate


class LabelTab(QWidget):
    """Tab for configuring and previewing nutritional labels."""

    # Custom item data roles
    FAT_ROW_ROLE = Qt.UserRole + 1
    HEADER_SPAN_ROLE = Qt.UserRole + 2
    MANUAL_ROLE = Qt.UserRole + 3

    def __init__(
        self,
        household_measure_options: list[tuple[str, str]],
        label_base_nutrients: list[dict[str, Any]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.household_measure_options = household_measure_options
        self.label_base_nutrients = label_base_nutrients
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(12)

        # Left group - Rotulado Nutricional
        left_group = QGroupBox("Rotulado Nutricional")
        left_form = QGridLayout()
        left_form.setContentsMargins(10, 10, 10, 10)
        left_form.setHorizontalSpacing(8)
        left_form.setVerticalSpacing(6)
        left_group.setLayout(left_form)

        # Portion size
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

        # Household measure
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

        # Custom household unit input
        self.custom_household_unit_input = QLineEdit()
        self.custom_household_unit_input.setPlaceholderText(
            "Ej.: Envase, Barrita, Paquete"
        )
        self.custom_household_unit_input.setVisible(False)
        left_form.addWidget(self.custom_household_unit_input, 2, 1, 1, 2)

        # Capacity label
        left_form.addWidget(QLabel("Capacidad o dimensión:"), 3, 0)
        self.household_capacity_label = QLabel("-")
        self.household_capacity_label.setStyleSheet("color: gray;")
        left_form.addWidget(self.household_capacity_label, 3, 1, 1, 2)

        # Breakdown checkboxes
        self.breakdown_carb_checkbox = QCheckBox("Desglose Carbohidratos")
        self.breakdown_carb_checkbox.setEnabled(True)
        self.breakdown_fat_checkbox = QCheckBox("Desglose Grasas")
        self.breakdown_fat_checkbox.setEnabled(True)
        left_form.addWidget(self.breakdown_carb_checkbox, 4, 0, 1, 2)
        left_form.addWidget(self.breakdown_fat_checkbox, 4, 2)

        # No significant contributions
        left_form.addWidget(QLabel("Sin aportes significativos:"), 5, 0)
        self.no_significant_display = QLineEdit()
        self.no_significant_display.setReadOnly(True)
        self.no_significant_display.setPlaceholderText("Seleccione nutrientes elegibles")
        self.no_significant_display.setCursor(Qt.PointingHandCursor)
        left_form.addWidget(self.no_significant_display, 5, 1, 1, 2)

        # Additional nutrients
        left_form.addWidget(QLabel("Nutrientes Adicionales:"), 6, 0)
        self.additional_nutrients_display = QLineEdit()
        self.additional_nutrients_display.setReadOnly(True)
        self.additional_nutrients_display.setPlaceholderText("Seleccione nutrientes adicionales")
        self.additional_nutrients_display.setCursor(Qt.PointingHandCursor)
        left_form.addWidget(self.additional_nutrients_display, 6, 1, 1, 2)

        # Placeholder note
        self.label_placeholder_note = QLabel(
            "Espacio reservado para botones de desglose y futuras acciones."
        )
        self.label_placeholder_note.setStyleSheet("color: gray; font-style: italic;")
        left_form.addWidget(self.label_placeholder_note, 7, 0, 1, 3)
        left_form.setRowStretch(8, 1)

        # Right group - Formato Vertical
        right_group = QGroupBox("Formato Vertical")
        right_layout = QVBoxLayout()
        right_group.setLayout(right_layout)

        # Manual value note
        self.manual_note_label = QLabel("Verde: valor manual (Doble clic para editar)")
        self.manual_note_label.setStyleSheet("color: #2e7d32; font-style: italic;")
        note_row = QHBoxLayout()
        note_row.addStretch()
        note_row.addWidget(self.manual_note_label)
        right_layout.addLayout(note_row)

        # Label table
        self.label_table_widget = QTableWidget()
        self._setup_label_table_widget()
        right_layout.addWidget(self.label_table_widget)

        # Export buttons
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

        # Linear format group
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

    def _setup_label_table_widget(self) -> None:
        """Configure the label table widget with custom styling."""
        table = self.label_table_widget

        # Row indices
        self.label_table_title_row = 0
        self.label_table_portion_row = 1
        self.label_table_header_row = 2
        self.label_table_nutrient_start_row = 3
        self.label_table_footer_row = (
            self.label_table_nutrient_start_row + len(self.label_base_nutrients)
        )

        table.setColumnCount(3)
        table.setRowCount(self.label_table_footer_row + 2)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.ExtendedSelection)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setMinimumHeight(360)
        table.setAutoFillBackground(False)
        table.viewport().setAutoFillBackground(False)
        table.setAttribute(Qt.WA_TranslucentBackground, True)
        table.viewport().setAttribute(Qt.WA_TranslucentBackground, True)

        # Configure palette for transparency
        palette = table.palette()
        palette.setColor(QPalette.Base, Qt.transparent)
        palette.setColor(QPalette.Window, Qt.transparent)
        palette.setColor(QPalette.AlternateBase, Qt.transparent)
        text_color = palette.color(QPalette.Text)
        palette.setColor(QPalette.Highlight, Qt.transparent)
        palette.setColor(QPalette.HighlightedText, text_color)
        table.setPalette(palette)
        table.viewport().setPalette(palette)

        # Custom stylesheet
        table.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #c0c0c0;
                background-color: transparent;
                alternate-background-color: transparent;
            }
            QTableWidget::item:selected,
            QTableWidget::item:selected:!active {
                selection-background-color: transparent;
                selection-color: #000;
                background-color: transparent;
                color: #000;
                border: none;
                outline: none;
            }
            QTableWidget::item:focus {
                border: none;
                outline: none;
            }
            QHeaderView::section {
                background-color: transparent;
            }
            QTableCornerButton::section {
                background-color: transparent;
            }
            """
        )
        table.setShowGrid(False)
        table.setWordWrap(True)

        # Set custom delegate
        table.setItemDelegate(LabelTableDelegate(self.FAT_ROW_ROLE, table))

    def get_delegate(self) -> LabelTableDelegate | None:
        """Get the label table delegate for configuration."""
        delegate = self.label_table_widget.itemDelegate()
        if isinstance(delegate, LabelTableDelegate):
            return delegate
        return None
