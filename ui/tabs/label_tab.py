from __future__ import annotations

import math
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtCore import QEvent, QObject, QItemSelectionModel, QPoint, QThread, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QMessageBox,
)

from services.nutrient_normalizer import canonical_alias_name, canonical_unit
from ui.delegates.label_table_delegate import LabelTableDelegate


class LabelTabMixin:
    """Label tab UI and behavior."""

    # ---- State ----
    def _init_label_state(self) -> None:
        """Initialize label tab state."""
        self._fat_row_role = Qt.UserRole + 501
        self._header_span_role = Qt.UserRole + 502
        self._manual_role = Qt.UserRole + 503

        self.label_base_nutrients = self._build_base_label_nutrients()
        self.household_measure_options = self._build_household_measure_options()
        self.household_capacity_map = {
            name: capacity for name, capacity in self.household_measure_options
        }
        self._auto_updating_household_amount = False
        self._suspend_no_sig_update = False
        self.label_manual_overrides: dict[str, float] = {}
        self.label_no_significant: list[str] = []
        self.label_additional_selected: list[str] = []
        self._label_display_nutrients: list[Dict[str, Any]] = []
        self.label_manual_hint_color = QColor(204, 255, 204)
        self.label_no_sig_order = [
            "Energia",
            "Carbohidratos",
            "Proteinas",
            "Grasas totales",
            "Grasas saturadas",
            "Grasas trans",
            "Fibra alimentaria",
            "Sodio",
        ]
        self.label_nutrient_usda_map = {
            "Energia": "Energy (kcal)",
            "Carbohidratos": "Carbohydrate, by difference (g)",
            "Azúcares": "Sugars, Total (g)",
            "Polialcoholes": "Sugar alcohol (g)",
            "Almidón": "Starch (g)",
            "Polidextrosas": "Polydextrose (g)",
            "Proteinas": "Protein (g)",
            "Grasas totales": "Total lipid (fat) (g)",
            "Grasas saturadas": "Fatty acids, total saturated (g)",
            "Grasas monoinsaturadas": "Fatty acids, total monounsaturated (g)",
            "Grasas poliinsaturadas": "Fatty acids, total polyunsaturated (g)",
            "Grasas trans": "Fatty acids, total trans (g)",
            "Colesterol": "Cholesterol (mg)",
            "Fibra alimentaria": "Fiber, total dietary (g)",
            "Sodio": "Sodium, Na (mg)",
            "Vitamina A": "Vitamin A, RAE (µg)",
            "Vitamina D": "Vitamin D (D2 + D3) (µg)",
            "Vitamina C": "Vitamin C, total ascorbic acid (mg)",
            "Vitamina E": "Vitamin E (alpha-tocopherol) (mg)",
            "Tiamina": "Thiamin (mg)",
            "Riboflavina": "Riboflavin (mg)",
            "Niacina": "Niacin (mg)",
            "Vitamina B6": "Vitamin B-6 (mg)",
            "Acido fólico": "Folate, DFE (µg)",
            "Vitaminia B12": "Vitamin B-12 (µg)",
            "Biotina": "Biotin (µg)",
            "Acido pantoténico": "Pantothenic acid (mg)",
            "Calcio": "Calcium, Ca (mg)",
            "Hierro": "Iron, Fe (mg)",
            "Magnesio": "Magnesium, Mg (mg)",
            "Zinc": "Zinc, Zn (mg)",
            "Yodo": "Iodine, I (µg)",
            "Vitamina K": "Vitamin K (phylloquinone) (µg)",
            "Fósforo": "Phosphorus, P (mg)",
            "Flúor": "Fluoride, F (mg)",
            "Cobre": "Copper, Cu (mg)",
            "Selenio": "Selenium, Se (µg)",
            "Molibdeno": "Molybdenum, Mo (µg)",
            "Cromo": "Chromium, Cr (µg)",
            "Manganeso": "Manganese, Mn (mg)",
            "Colina": "Choline, total (mg)",
        }
        self.label_no_significant_thresholds = {
            "Energia": {"unit": "kcal", "max": 4.0, "kj_max": 17.0},
            "Carbohidratos": {"unit": "g", "max": 0.5},
            "Proteinas": {"unit": "g", "max": 0.5},
            "Grasas totales": {"unit": "g", "max": 0.5},
            "Grasas saturadas": {"unit": "g", "max": 0.2},
            "Grasas trans": {"unit": "g", "max": 0.2},
            "Fibra alimentaria": {"unit": "g", "max": 0.5},
            "Sodio": {"unit": "mg", "max": 5.0},
        }
        self.label_no_significant_display_map = {"Energia": "Valor energético"}
        self.label_additional_catalog = self._build_additional_nutrients()
        self.label_additional_refs = {
            item["name"]: item.get("ref", "") for item in self.label_additional_catalog
        }

    # ---- UI build ----
    def _build_label_tab_ui(self) -> None:
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
        self.no_significant_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.no_significant_display.setPlaceholderText("Seleccione nutrientes elegibles")
        self.no_significant_display.setCursor(Qt.PointingHandCursor)
        left_form.addWidget(self.no_significant_display, 5, 1, 1, 2)

        left_form.addWidget(QLabel("Nutrientes Adicionales:"), 6, 0)
        self.additional_nutrients_display = QLineEdit()
        self.additional_nutrients_display.setReadOnly(True)
        self.additional_nutrients_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
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

    # ---- Table setup ----
    def _setup_label_table_widget(self) -> None:
        table = self.label_table_widget
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

        palette = table.palette()
        palette.setColor(QPalette.Base, Qt.transparent)
        palette.setColor(QPalette.Window, Qt.transparent)
        palette.setColor(QPalette.AlternateBase, Qt.transparent)
        # Highlight nativo -> transparente, mantiene color de texto
        text_color = palette.color(QPalette.Text)
        palette.setColor(QPalette.Highlight, Qt.transparent)
        palette.setColor(QPalette.HighlightedText, text_color)
        table.setPalette(palette)
        table.viewport().setPalette(palette)
        table.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #c0c0c0;
                background-color: transparent;
                alternate-background-color: transparent;
            }
            /* Desactiva el highlight nativo (fondo/borde) para que solo se use el delegado */
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
        table.setItemDelegate(LabelTableDelegate(self._fat_row_role, table))


    def _build_base_label_nutrients(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "Energia",
                "type": "energy",
                "kcal": 0.0,
                "kj": 0.0,
                "vd": 13.0,
                "vd_reference": 263.0,
            },
            {
                "name": "Carbohidratos",
                "unit": "g",
                "amount": 0.0,
                "vd": 7.0,
                "vd_reference": 20.0,
                "carb_parent": True,
            },
            {
                "name": "Azúcares",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "carb_child": True,
                "carb_breakdown_only": True,
            },
            {
                "name": "Polialcoholes",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "carb_child": True,
                "carb_breakdown_only": True,
            },
            {
                "name": "Almidón",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "carb_child": True,
                "carb_breakdown_only": True,
            },
            {
                "name": "Polidextrosas",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "carb_child": True,
                "carb_breakdown_only": True,
            },
            {
                "name": "Proteinas",
                "unit": "g",
                "amount": 0.0,
                "vd": 16.0,
                "vd_reference": 12.0,
            },
            {
                "name": "Grasas totales",
                "unit": "g",
                "amount": 0.0,
                "vd": 27.0,
                "vd_reference": 15.0,
                "fat_parent": True,
            },
            {
                "name": "Grasas saturadas",
                "unit": "g",
                "amount": 0.0,
                "vd": 23.0,
                "vd_reference": 5.0,
                "fat_child": True,
            },
            {
                "name": "Grasas monoinsaturadas",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "fat_child": True,
                "fat_breakdown_only": True,
            },
            {
                "name": "Grasas poliinsaturadas",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "fat_child": True,
                "fat_breakdown_only": True,
            },
            {
                "name": "Grasas trans",
                "unit": "g",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "fat_child": True,
            },
            {
                "name": "Colesterol",
                "unit": "mg",
                "amount": 0.0,
                "vd": None,
                "vd_reference": 0.0,
                "fat_child": True,
                "fat_breakdown_only": True,
            },
            {
                "name": "Fibra alimentaria",
                "unit": "g",
                "amount": 0.0,
                "vd": 12.0,
                "vd_reference": 3.0,
            },
            {
                "name": "Sodio",
                "unit": "mg",
                "amount": 0.0,
                "vd": 5.0,
                "vd_reference": 120.0,
            },
        ]


    def _build_additional_nutrients(self) -> list[dict[str, Any]]:
        return [
            {"name": "Vitamina A", "unit": "µg", "vd_reference": 600.0, "ref": "(2)"},
            {"name": "Vitamina D", "unit": "µg", "vd_reference": 5.0, "ref": "(2)"},
            {"name": "Vitamina C", "unit": "mg", "vd_reference": 45.0, "ref": "(2)"},
            {"name": "Vitamina E", "unit": "mg", "vd_reference": 10.0, "ref": "(2)"},
            {"name": "Tiamina", "unit": "mg", "vd_reference": 1.2, "ref": "(2)"},
            {"name": "Riboflavina", "unit": "mg", "vd_reference": 1.3, "ref": "(2)"},
            {"name": "Niacina", "unit": "mg", "vd_reference": 16.0, "ref": "(2)"},
            {"name": "Vitamina B6", "unit": "mg", "vd_reference": 1.3, "ref": "(2)"},
            {"name": "Acido fólico", "unit": "µg", "vd_reference": 400.0, "ref": "(2)"},
            {"name": "Vitaminia B12", "unit": "µg", "vd_reference": 2.4, "ref": "(2)"},
            {"name": "Biotina", "unit": "µg", "vd_reference": 30.0, "ref": "(2)"},
            {"name": "Acido pantoténico", "unit": "mg", "vd_reference": 5.0, "ref": "(2)"},
            {"name": "Calcio", "unit": "mg", "vd_reference": 1000.0, "ref": "(2)"},
            {"name": "Hierro", "unit": "mg", "vd_reference": 14.0, "ref": "(2) (*)"},
            {"name": "Magnesio", "unit": "mg", "vd_reference": 260.0, "ref": "(2)"},
            {"name": "Zinc", "unit": "mg", "vd_reference": 7.0, "ref": "(2) (**)"},
            {"name": "Yodo", "unit": "µg", "vd_reference": 130.0, "ref": "(2)"},
            {"name": "Vitamina K", "unit": "µg", "vd_reference": 65.0, "ref": "(2)"},
            {"name": "Fósforo", "unit": "mg", "vd_reference": 700.0, "ref": "(3)"},
            {"name": "Flúor", "unit": "mg", "vd_reference": 4.0, "ref": "(3)"},
            {"name": "Cobre", "unit": "mg", "vd_reference": 0.9, "ref": "(3)"},
            {"name": "Selenio", "unit": "µg", "vd_reference": 34.0, "ref": "(2)"},
            {"name": "Molibdeno", "unit": "µg", "vd_reference": 45.0, "ref": "(3)"},
            {"name": "Cromo", "unit": "µg", "vd_reference": 35.0, "ref": "(3)"},
            {"name": "Manganeso", "unit": "mg", "vd_reference": 2.3, "ref": "(3)"},
            {"name": "Colina", "unit": "mg", "vd_reference": 550.0, "ref": "(3)"},
        ]


    def _build_household_measure_options(self) -> list[tuple[str, int | None]]:
        return [
            ("Taza de té", 200),
            ("Vaso", 200),
            ("Cuchara de sopa", 10),
            ("Cuchara de té", 5),
            ("Plato hondo", 250),
            ("Unidad", None),
            ("Otro", None),
        ]


    # ---- Label settings persistence ----
    def _snapshot_label_settings(self) -> Dict[str, Any]:
        """Capture label tab state for JSON export."""
        manual: Dict[str, float] = {}
        for name, value in self.label_manual_overrides.items():
            try:
                manual[name] = float(value)
            except (TypeError, ValueError):
                continue
        return {
            "portion_size": int(self.portion_size_input.value()),
            "portion_unit": self.portion_unit_combo.currentText(),
            "household_amount": self.household_amount_input.text(),
            "household_unit": self.household_unit_combo.currentText(),
            "custom_household_unit": self.custom_household_unit_input.text(),
            "breakdown_carb": self.breakdown_carb_checkbox.isChecked(),
            "breakdown_fat": self.breakdown_fat_checkbox.isChecked(),
            "no_significant": list(self.label_no_significant),
            "additional_nutrients": list(self.label_additional_selected),
            "manual_overrides": manual,
        }


    def _apply_label_settings(self, settings: Dict[str, Any], *, defer_preview: bool = False) -> None:
        """Apply label tab state from JSON import."""
        if not isinstance(settings, dict) or not settings:
            return

        widgets = [
            self.portion_size_input,
            self.portion_unit_combo,
            self.household_amount_input,
            self.household_unit_combo,
            self.custom_household_unit_input,
            self.breakdown_carb_checkbox,
            self.breakdown_fat_checkbox,
        ]
        for widget in widgets:
            widget.blockSignals(True)

        try:
            portion_size = settings.get("portion_size")
            if portion_size is not None:
                try:
                    self.portion_size_input.setValue(int(portion_size))
                except (TypeError, ValueError):
                    pass

            portion_unit = str(settings.get("portion_unit") or "").strip()
            if portion_unit:
                idx = self.portion_unit_combo.findText(portion_unit)
                if idx >= 0:
                    self.portion_unit_combo.setCurrentIndex(idx)

            household_amount = settings.get("household_amount")
            if household_amount is not None:
                self.household_amount_input.setText(str(household_amount))

            household_unit = str(settings.get("household_unit") or "").strip()
            custom_unit = str(settings.get("custom_household_unit") or "").strip()
            if household_unit:
                idx = self.household_unit_combo.findText(household_unit)
                if idx >= 0:
                    self.household_unit_combo.setCurrentIndex(idx)
                else:
                    other_idx = self.household_unit_combo.findText("Otro")
                    if other_idx >= 0:
                        self.household_unit_combo.setCurrentIndex(other_idx)
                        if not custom_unit:
                            custom_unit = household_unit

            is_custom = self.household_unit_combo.currentText() == "Otro"
            self.custom_household_unit_input.setVisible(is_custom)
            if custom_unit is not None:
                self.custom_household_unit_input.setText(custom_unit)

            if "breakdown_carb" in settings:
                self.breakdown_carb_checkbox.setChecked(bool(settings.get("breakdown_carb")))
            if "breakdown_fat" in settings:
                self.breakdown_fat_checkbox.setChecked(bool(settings.get("breakdown_fat")))

        finally:
            for widget in widgets:
                widget.blockSignals(False)

        self._update_capacity_label()

        manual_overrides = (
            settings.get("manual_overrides")
            or settings.get("label_manual_overrides")
            or {}
        )
        parsed_manual: dict[str, float] = {}
        if isinstance(manual_overrides, dict):
            for name, value in manual_overrides.items():
                try:
                    parsed_manual[str(name)] = float(value)
                except (TypeError, ValueError):
                    continue
        self.label_manual_overrides = parsed_manual

        no_sig = settings.get("no_significant") or settings.get("label_no_significant") or []
        if isinstance(no_sig, list):
            self.label_no_significant = [str(name) for name in no_sig if name]

        additional = (
            settings.get("additional_nutrients")
            or settings.get("label_additional_selected")
            or []
        )
        if isinstance(additional, list):
            self.label_additional_selected = [str(name) for name in additional if name]

        self._refresh_no_significant_display()
        self._update_additional_controls()

        if not defer_preview:
            self._update_label_preview(force_recalc_totals=True)


    # ---- Label calculations ----
    def _current_portion_factor(self) -> float:
        return float(self.portion_size_input.value() or 0) / 100.0


    def _format_fraction_amount(self, value: float) -> str:
        if value <= 0:
            return ""
        frac = Fraction(value).limit_denominator(12)
        whole, remainder = divmod(frac.numerator, frac.denominator)
        if remainder == 0:
            return str(whole)
        if whole == 0:
            return f"{remainder}/{frac.denominator}"
        return f"{whole} {remainder}/{frac.denominator}"


    def _fraction_from_ratio(self, ratio: float) -> str:
        percent = ratio * 100.0
        if percent <= 30:
            return "1/4"
        if percent <= 70:
            return "1/2"
        if percent <= 130:
            return "1"
        if percent <= 170:
            return "1 1/2"
        if percent <= 230:
            return "2"
        return self._format_fraction_amount(ratio)


    def _update_capacity_label(self) -> None:
        unit_name = self.household_unit_combo.currentText()
        capacity = self.household_capacity_map.get(unit_name)
        if capacity:
            label_text = f"{capacity} ml"
        else:
            label_text = "-"
        if unit_name == "Otro" and self.custom_household_unit_input.isVisible():
            label_text = "Definir capacidad manualmente"
        self.household_capacity_label.setText(label_text)


    def _auto_fill_household_measure(self) -> None:
        if self.portion_unit_combo.currentText() != "ml":
            return
        unit_name = self.household_unit_combo.currentText()
        capacity = self.household_capacity_map.get(unit_name)
        if not capacity:
            return
        portion_value = float(self.portion_size_input.value() or 0)
        if portion_value <= 0:
            return
        ratio = portion_value / float(capacity)
        text = self._fraction_from_ratio(ratio)
        self._auto_updating_household_amount = True
        try:
            self.household_amount_input.setText(text or "")
        finally:
            self._auto_updating_household_amount = False


    def _on_portion_value_changed(self, _: int) -> None:
        if self.portion_unit_combo.currentText() == "ml":
            self._auto_fill_household_measure()
        self._update_label_preview()


    def _on_portion_unit_changed(self, _: str) -> None:
        if self.portion_unit_combo.currentText() == "ml":
            self._auto_fill_household_measure()
        self._update_capacity_label()
        self._update_label_preview()


    def _on_household_unit_changed(self, _: str) -> None:
        is_custom = self.household_unit_combo.currentText() == "Otro"
        self.custom_household_unit_input.setVisible(is_custom)
        self._update_capacity_label()
        if self.portion_unit_combo.currentText() == "ml":
            self._auto_fill_household_measure()
        self._update_label_preview()


    def _on_household_amount_changed(self, _: str) -> None:
        if self._auto_updating_household_amount:
            return
        self._update_label_preview()


    def _on_breakdown_fat_toggled(self, _: bool) -> None:
        fat_names = {
            "Grasas totales",
            "Grasas saturadas",
            "Grasas trans",
            "Grasas monoinsaturadas",
            "Grasas poliinsaturadas",
            "Colesterol",
        }
        self.label_no_significant = [n for n in self.label_no_significant if n not in fat_names]
        self._update_label_preview()


    def _on_breakdown_carb_toggled(self, _: bool) -> None:
        carb_names = {
            "Carbohidratos",
            "Azúcares",
            "Polialcoholes",
            "Almidón",
            "Polidextrosas",
        }
        self.label_no_significant = [n for n in self.label_no_significant if n not in carb_names]
        self._update_label_preview()


    def _current_household_unit_label(self) -> str:
        if self.household_unit_combo.currentText() == "Otro":
            custom = self.custom_household_unit_input.text().strip()
            return custom or "Unidad"
        return self.household_unit_combo.currentText()


    def _portion_description_for_table(self) -> str:
        measure_amount = self.household_amount_input.text().strip()
        measure_unit = self._current_household_unit_label()
        portion_unit = self.portion_unit_combo.currentText()
        portion_value = self.portion_size_input.value()
        measure_display = measure_unit if not measure_amount else f"{measure_amount} {measure_unit}"
        return f"Porción {portion_value} {portion_unit} ({measure_display})"


    def _format_number_for_unit(self, value: float, unit: str) -> str:
        if math.isclose(value, 0.0, abs_tol=1e-9):
            return f"0 {unit}".strip()
        if unit == "mg":
            return f"{value:.0f} mg"
        if unit == "g":
            if abs(value) < 10:
                return f"{value:.1f} g"
            return f"{value:.0f} g"
        if value >= 10:
            return f"{value:.0f} {unit}"
        if value >= 1:
            return f"{value:.1f} {unit}"
        return f"{value:.2f} {unit}"


    def _format_additional_amount(self, value: float, unit: str) -> str:
        unit = unit.lower()
        if unit == "mg":
            if math.isclose(value, 0.0, abs_tol=1e-9):
                return "0 mg"
            if value < 10:
                return f"{value:.1f} mg"
            return f"{value:.0f} mg"
        if unit in ("µg", "ug"):
            if math.isclose(value, 0.0, abs_tol=1e-9):
                return "0 µg"
            if value < 10:
                return f"{value:.1f} µg"
            return f"{value:.0f} µg"
        return self._format_number_for_unit(value, unit)


    def _format_nutrient_amount(self, nutrient: Dict[str, Any], factor: float) -> str:
        if nutrient.get("type") == "energy":
            kcal_val = nutrient.get("kcal", 0.0) * factor
            kj_val = nutrient.get("kj", 0.0) * factor
            kcal_text = f"{kcal_val:.0f}"
            kj_text = f"{kj_val:.0f}"
            return f"{kcal_text} kcal = {kj_text} kJ"
        amount = nutrient.get("amount", 0.0) * factor
        unit = nutrient.get("unit", "")
        return self._format_number_for_unit(amount, unit)


    def _format_vd_value(self, nutrient: Dict[str, Any], factor: float, effective_amount: float | None = None) -> str:  # type: ignore[override]
        vd_percent = nutrient.get("vd")
        base_amount = nutrient.get("vd_reference", nutrient.get("amount", 0.0))
        eff_amount = (
            effective_amount if effective_amount is not None else nutrient.get("amount", 0.0)
        )
        if nutrient.get("type") == "energy":
            base_amount = nutrient.get("vd_reference", nutrient.get("kcal", 0.0))
            eff_amount = effective_amount if effective_amount is not None else nutrient.get("kcal", 0.0)

        portion_amount = eff_amount * factor
        if vd_percent is None and base_amount and base_amount > 0:
            vd_val = portion_amount * 100.0 / base_amount
        elif vd_percent is not None and base_amount and base_amount > 0:
            vd_val = vd_percent * (portion_amount / base_amount)
        else:
            return "-"
        return f"{vd_val:.0f}%"


    def _format_manual_amount(self, nutrient: Dict[str, Any], manual_amount: float) -> str:
        if nutrient.get("type") == "energy":
            kcal_val = manual_amount
            kj_val = manual_amount * 4.184
            kcal_text = f"{kcal_val:.0f}"
            kj_text = f"{kj_val:.0f}"
            return f"{kcal_text} kcal = {kj_text} kJ"
        unit = nutrient.get("unit", "")
        return self._format_number_for_unit(manual_amount, unit)


    def _format_manual_vd(self, nutrient: Dict[str, Any], manual_amount: float) -> str:
        vd_ref = nutrient.get("vd")
        if vd_ref is None:
            return "-"
        base_amount = nutrient.get("kcal") if nutrient.get("type") == "energy" else nutrient.get("amount")
        if not base_amount:
            return "-"
        vd_val = vd_ref * (manual_amount / base_amount)
        if vd_val >= 10:
            return f"{vd_val:.0f}%"
        return f"{vd_val:.1f}%"


    def _parse_user_float(self, text: str) -> float | None:
        clean = text.strip().replace(",", ".")
        if not clean:
            return None
        try:
            return float(clean)
        except ValueError:
            return None


    def _active_label_nutrients(self) -> list[Dict[str, Any]]:
        breakdown_fat = self.breakdown_fat_checkbox.isChecked()
        breakdown_carb = self.breakdown_carb_checkbox.isChecked()
        display: list[Dict[str, Any]] = []
        for nutrient in self.label_base_nutrients:
            name = nutrient.get("name", "")
            if name in self.label_no_significant:
                continue
            if nutrient.get("fat_breakdown_only") and not breakdown_fat:
                continue
            if nutrient.get("carb_breakdown_only") and not breakdown_carb:
                continue
            entry = dict(nutrient)
            indent = 0
            if (
                (breakdown_fat and entry.get("fat_child") and not entry.get("fat_parent"))
                or (breakdown_carb and entry.get("carb_child") and not entry.get("carb_parent"))
            ):
                indent = 1
            entry["indent_level"] = indent
            display.append(entry)
        return display


    def _on_label_table_cell_double_clicked(self, row: int, _: int) -> None:
        if (
            row < self.label_table_nutrient_start_row
            or row >= self.label_table_nutrient_start_row + len(self._label_display_nutrients)
        ):
            return
        idx = row - self.label_table_nutrient_start_row
        nutrient = self._label_display_nutrients[idx]
        self._prompt_manual_value_for_nutrient(nutrient)


    def _prompt_manual_value_for_nutrient(self, nutrient: Dict[str, Any]) -> None:
        name = nutrient.get("name", "")
        unit = "kcal" if nutrient.get("type") == "energy" else nutrient.get("unit", "")
        current = self.label_manual_overrides.get(name)
        default_text = "" if current is None else str(current)
        text, ok = QInputDialog.getText(
            self,
            "Valor manual",
            f"Ingrese la cantidad por porción para {name} ({unit}).\n"
            "Deje vacío para volver al cálculo automático.",
            text=default_text,
        )
        if not ok:
            return
        if text.strip() == "":
            self.label_manual_overrides.pop(name, None)
            self._update_label_preview()
            return
        value = self._parse_user_float(text)
        if value is None:
            QMessageBox.warning(self, "Valor inválido", "Ingresa un número válido (ej.: 12.5).")
            return
        self.label_manual_overrides[name] = value
        self._update_label_preview()


    def _eligible_no_significant(self) -> list[str]:
        eligible: list[str] = []
        factor = self._current_portion_factor()
        fat_locked = self.breakdown_fat_checkbox.isChecked()
        fat_names = {
            "Grasas totales",
            "Grasas saturadas",
            "Grasas trans",
            "Grasas monoinsaturadas",
            "Grasas poliinsaturadas",
            "Colesterol",
        }
        def portion_amount(name: str) -> float:
            for nutrient in self.label_base_nutrients:
                if nutrient.get("name") != name:
                    continue
                eff = self._effective_label_nutrient(nutrient)
                if eff.get("type") == "energy":
                    return (eff.get("kcal") or 0.0) * factor
                return (eff.get("amount") or 0.0) * factor
            return 0.0
        for nutrient in self.label_base_nutrients:
            eff = self._effective_label_nutrient(nutrient)
            name = eff.get("name", nutrient.get("name", ""))
            if fat_locked and name in fat_names:
                continue
            if self.breakdown_carb_checkbox.isChecked() and name in {
                "Carbohidratos",
                "Azúcares",
                "Polialcoholes",
                "Almidón",
                "Polidextrosas",
            }:
                continue
            thresh = self.label_no_significant_thresholds.get(name)
            if not thresh:
                continue
            if eff.get("type") == "energy":
                kcal_portion = (eff.get("kcal") or 0.0) * factor
                kj_portion = (eff.get("kj") or 0.0) * factor
                if kcal_portion <= thresh.get("max", 0) or kj_portion < thresh.get("kj_max", 0):
                    eligible.append(name)
                continue
            amount_portion = (eff.get("amount") or 0.0) * factor
            unit = eff.get("unit", nutrient.get("unit", "")).lower()
            max_allowed = thresh.get("max", 0.0)
            if name == "Grasas totales":
                sat = portion_amount("Grasas saturadas")
                trans = portion_amount("Grasas trans")
                if (
                    amount_portion <= max_allowed + 1e-9
                    and sat <= self.label_no_significant_thresholds["Grasas saturadas"]["max"] + 1e-9
                    and trans <= self.label_no_significant_thresholds["Grasas trans"]["max"] + 1e-9
                ):
                    eligible.append(name)
            elif amount_portion <= max_allowed + 1e-9:
                eligible.append(name)
        return eligible


    def _update_no_significant_controls(self) -> None:
        eligible = self._eligible_no_significant()
        self.label_no_significant = self._sort_no_significant_list(
            [name for name in self.label_no_significant if name in eligible]
        )
        display_names = [
            self.label_no_significant_display_map.get(name, name)
            for name in self.label_no_significant
        ]
        self._refresh_no_significant_display(display_names)
        has_options = bool(eligible)
        self.no_significant_display.setEnabled(has_options)
        self.no_significant_display.setToolTip(
            ""
            if has_options
            else "No hay nutrientes elegibles con la porción y valores actuales."
        )


    def _update_additional_controls(self) -> None:
        display = [
            name
            for name in self.label_additional_selected
            if any(c["name"] == name for c in self.label_additional_catalog)
        ]
        self.label_additional_selected = display
        self._refresh_additional_display(display)


    def _on_select_no_significant_clicked(self) -> None:
        eligible = self._eligible_no_significant()
        if not eligible:
            QMessageBox.information(
                self,
                "Sin opciones",
                "No hay nutrientes elegibles para 'sin aportes significativos' con la porción actual.",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Sin aportes significativos")
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget(dialog)
        prev_state_role = Qt.UserRole + 100
        for name in eligible:
            item = QListWidgetItem(self.label_no_significant_display_map.get(name, name))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if name in self.label_no_significant else Qt.Unchecked)
            item.setData(Qt.UserRole, name)
            item.setData(prev_state_role, item.checkState())
            list_widget.addItem(item)
        def _remember_state(item: QListWidgetItem) -> None:
            item.setData(prev_state_role, item.checkState())
        def _toggle_if_unchanged(item: QListWidgetItem) -> None:
            prev = item.data(prev_state_role)
            if prev is None:
                prev = item.checkState()
            if item.checkState() == prev:
                item.setCheckState(
                    Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
                )
            item.setData(prev_state_role, item.checkState())
        list_widget.itemPressed.connect(_remember_state)
        list_widget.itemClicked.connect(_toggle_if_unchanged)
        layout.addWidget(list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() == QDialog.Accepted:
            selected: list[str] = []
            for idx in range(list_widget.count()):
                item = list_widget.item(idx)
                if item.checkState() == Qt.Checked:
                    selected.append(item.data(Qt.UserRole))
            if "Grasas totales" in selected:
                for dep in ("Grasas saturadas", "Grasas trans"):
                    if dep not in selected and dep in eligible:
                        selected.append(dep)
            self.label_no_significant = self._sort_no_significant_list(selected)
            self._update_label_preview()


    def _on_select_additional_clicked(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Nutrientes adicionales")
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget(dialog)
        prev_state_role = Qt.UserRole + 200
        for nutrient in self.label_additional_catalog:
            name = nutrient["name"]
            ref = nutrient.get("ref", "")
            display = f"{name} {ref}".strip()
            item = QListWidgetItem(display)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if name in self.label_additional_selected else Qt.Unchecked)
            item.setData(Qt.UserRole, name)
            item.setData(prev_state_role, item.checkState())
            list_widget.addItem(item)
        def _remember_state(item: QListWidgetItem) -> None:
            item.setData(prev_state_role, item.checkState())
        def _toggle_if_unchanged(item: QListWidgetItem) -> None:
            prev = item.data(prev_state_role)
            if prev is None:
                prev = item.checkState()
            if item.checkState() == prev:
                item.setCheckState(
                    Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
                )
            item.setData(prev_state_role, item.checkState())
        list_widget.itemPressed.connect(_remember_state)
        list_widget.itemClicked.connect(_toggle_if_unchanged)
        layout.addWidget(list_widget)

        notes = QLabel(
            "(* ) 10% de biodisponibilidad\n"
            "(**) Moderada biodisponibilidad\n\n"
            "NOTAS:\n\n"
            "(1) FAO/OMS -Diet, Nutrition and Prevention of Chronic Diseases. WHO Technical Report Series 916 Geneva, 2003.\n\n"
            "(2) Human Vitamin and Mineral Requirements, Report 07ª Joint FAO/OMS Expert Consultation Bangkok, Thailand, 2001\n\n"
            "(3) Dietary Reference Intake, Food and Nutrition Broad, Institute of Medicine. 1999-2001."
        )
        notes.setStyleSheet("color: gray; font-size: 10px;")
        notes.setWordWrap(True)
        layout.addWidget(notes)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() == QDialog.Accepted:
            selected: list[str] = []
            for idx in range(list_widget.count()):
                item = list_widget.item(idx)
                if item.checkState() == Qt.Checked:
                    selected.append(item.data(Qt.UserRole))
            self.label_additional_selected = selected
            self._update_label_preview()


    def eventFilter(self, obj: QObject, event) -> bool:
        if obj is self.no_significant_display and event.type() == QEvent.Resize:
            self._refresh_no_significant_display()
            return False
        if obj is self.additional_nutrients_display and event.type() == QEvent.Resize:
            self._refresh_additional_display()
            return False
        if obj is self.no_significant_display and event.type() == QEvent.MouseButtonPress:
            if self.no_significant_display.isEnabled():
                self._on_select_no_significant_clicked()
            return True
        if obj is self.additional_nutrients_display and event.type() == QEvent.MouseButtonPress:
            if self.additional_nutrients_display.isEnabled():
                self._on_select_additional_clicked()
            return True
        return super().eventFilter(obj, event)


    def _format_compact_display(self, names: list[str], field: QLineEdit) -> str:
        if not names:
            return ""
        full_text = ", ".join(names)
        available = field.contentsRect().width()
        if available <= 0:
            return full_text
        margins = field.textMargins()
        available -= margins.left() + margins.right() + 4
        if available <= 0:
            return full_text
        metrics = field.fontMetrics()
        if metrics.horizontalAdvance(full_text) <= available:
            return full_text
        total = len(names)
        for shown_count in range(total - 1, 0, -1):
            remaining = total - shown_count
            shown_text = ", ".join(names[:shown_count])
            suffix = f" y {remaining} más"
            candidate = f"{shown_text}{suffix}"
            if metrics.horizontalAdvance(candidate) <= available:
                return candidate
        if total > 1:
            suffix = f" y {total - 1} más"
            available_first = available - metrics.horizontalAdvance(suffix)
            if available_first > 0:
                first = metrics.elidedText(names[0], Qt.ElideRight, available_first)
                return f"{first}{suffix}"
            return metrics.elidedText(suffix.strip(), Qt.ElideRight, available)
        return metrics.elidedText(names[0], Qt.ElideRight, available)


    def _refresh_no_significant_display(self, display_names: list[str] | None = None) -> None:
        if display_names is None:
            display_names = [
                self.label_no_significant_display_map.get(name, name)
                for name in self.label_no_significant
            ]
        self.no_significant_display.setText(
            self._format_compact_display(display_names, self.no_significant_display)
        )


    def _refresh_additional_display(self, display_names: list[str] | None = None) -> None:
        if display_names is None:
            display_names = list(self.label_additional_selected)
        self.additional_nutrients_display.setText(
            self._format_compact_display(
                display_names, self.additional_nutrients_display
            )
        )


    def _human_join(self, items: list[str]) -> str:
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        return ", ".join(items[:-1]) + " y " + items[-1]


    def _sort_no_significant_list(self, names: list[str]) -> list[str]:
        order_index = {name: idx for idx, name in enumerate(self.label_no_sig_order)}
        return sorted(
            names,
            key=lambda n: (
                order_index.get(n, len(order_index)),
                n.lower(),
            ),
        )


    def _parse_label_mapping(self, label_name: str) -> tuple[str, str]:
        mapped = self.label_nutrient_usda_map.get(label_name, "")
        mapped_clean = mapped.strip()
        if not mapped_clean:
            return "", ""
        # Si el paréntesis final es una unidad, úsalo; de lo contrario, ignora paréntesis de aclaración.
        m = re.search(r"\(([^()]*)\)\s*$", mapped_clean)
        if m:
            unit_candidate = m.group(1).strip()
            if re.fullmatch(r"(?i)(mg|g|µg|ug|kcal|kj)", unit_candidate):
                base = mapped_clean[: m.start()].strip()
                return canonical_alias_name(base), canonical_unit(unit_candidate)
        return canonical_alias_name(mapped_clean), ""


    def _find_total_entry(self, canonical_name: str, unit: str) -> Dict[str, Any] | None:
        if not self._last_totals:
            self._last_totals = self._calculate_totals()
        target = canonical_alias_name(canonical_name).lower()
        target_unit = canonical_unit(unit).lower()
        target_key = re.sub(r"[^a-z0-9]", "", target)
        entries = list(self._last_totals.values())

        def _match_entry(entry: Dict[str, Any]) -> bool:
            entry_name = canonical_alias_name(entry.get("name", "")).lower()
            entry_unit = canonical_unit(entry.get("unit", "")).lower()
            entry_key = re.sub(r"[^a-z0-9]", "", entry_name)
            name_match = (
                entry_name == target
                or entry_name.startswith(target)
                or target in entry_name
                or entry_key == target_key
                or entry_key.startswith(target_key)
                or target_key in entry_key
            )
            unit_match = (not target_unit) or entry_unit == target_unit
            return name_match and unit_match

        for entry in entries:
            if _match_entry(entry):
                return entry

        # Fallback: raw substring match (e.g., "total lipid (fat)")
        raw_target = canonical_name.lower()
        for entry in entries:
            raw_name = (entry.get("name") or "").lower()
            if raw_target in raw_name:
                if not target_unit or canonical_unit(entry.get("unit", "")).lower() == target_unit:
                    return entry
        return None


    def _convert_label_amount_unit(
        self, amount: float, from_unit: str, to_unit: str
    ) -> float | None:
        source = canonical_unit(from_unit).lower()
        target = canonical_unit(to_unit).lower()
        if not source or not target:
            return None
        if source == target:
            return amount
        if source == "µg" and target == "mg":
            return amount / 1000.0
        if source == "mg" and target == "µg":
            return amount * 1000.0
        return None


    def _factor_for_energy(self, name: str) -> float | None:
        factor_map: list[tuple[str, float]] = [
            ("alcohol", 7.0),
            ("ethanol", 7.0),
            ("protein", 4.0),
            ("carbohydrate", 4.0),
            ("carbohydrate, by difference", 4.0),
            ("polydextrose", 1.0),
            ("polyol", 2.4),
            ("sugar alcohol", 2.4),
            ("organic acid", 3.0),
            ("total lipid", 9.0),  # Solo lipidos totales, no Fat (NLEA)
        ]
        lower = name.lower()
        for key, factor in factor_map:
            if key in lower:
                return factor
        return None


    def _compute_energy_label_values(self) -> Dict[str, float] | None:
        factor = self._current_portion_factor()
        if factor <= 0:
            factor = 1.0

        display_nutrients = self._active_label_nutrients()
        carb_parent_present = any(n.get("carb_parent") for n in display_nutrients)
        fat_parent_present = any(n.get("fat_parent") for n in display_nutrients)

        kcal_portion = 0.0

        for nutrient in display_nutrients:
            name = nutrient.get("name", "")
            if nutrient.get("type") == "energy":
                continue
            if carb_parent_present and nutrient.get("carb_child") and not nutrient.get("carb_parent"):
                continue
            if fat_parent_present and nutrient.get("fat_child") and not nutrient.get("fat_parent"):
                continue

            mapped_name, _ = self._parse_label_mapping(name)
            factor_energy = self._factor_for_energy(mapped_name or name)
            if factor_energy is None:
                continue

            manual_amount = self.label_manual_overrides.get(name)
            if manual_amount is not None:
                amount_portion = float(manual_amount)
            else:
                totals_amount = self._label_amount_from_totals(nutrient)
                if not totals_amount:
                    continue
                amount_portion = float(totals_amount.get("amount", 0.0)) * factor

            unit = (nutrient.get("unit", "") or "").lower()
            amount_g = amount_portion / 1000.0 if unit == "mg" else amount_portion
            kcal_portion += amount_g * factor_energy

        if math.isclose(kcal_portion, 0.0, abs_tol=1e-6):
            return None

        kcal_per_100 = kcal_portion / factor
        return {"kcal": kcal_per_100, "kj": kcal_per_100 * 4.184}


    def _label_amount_from_totals(self, nutrient: Dict[str, Any]) -> Dict[str, float] | None:
        name = nutrient.get("name", "")
        mapped_name, mapped_unit = self._parse_label_mapping(name)
        if not mapped_name:
            return None
        if nutrient.get("type") == "energy":
            computed = self._compute_energy_label_values()
            if computed:
                return computed
            return None
        entry = self._find_total_entry(mapped_name, mapped_unit)
        if not entry and mapped_unit:
            entry_any = self._find_total_entry(mapped_name, "")
            if entry_any:
                converted = self._convert_label_amount_unit(
                    float(entry_any.get("amount", 0.0) or 0.0),
                    entry_any.get("unit", ""),
                    mapped_unit,
                )
                if converted is not None:
                    return {"amount": converted}
        if not entry and name == "Grasas totales":
            # Fallback: cualquier nutriente que contenga "total fat" o "total lipid"
            for e in (self._last_totals or {}).values():
                raw_name = (e.get("name") or "").lower()
                if "total lipid" in raw_name:
                    entry = e
                    break
        if not entry:
            return None
        return {"amount": float(entry.get("amount", 0.0))}


    def _effective_label_nutrient(self, nutrient: Dict[str, Any]) -> Dict[str, Any]:
        name = nutrient.get("name", "")
        manual_amount = self.label_manual_overrides.get(name)
        if nutrient.get("type") == "energy":
            manual_amount = None
        totals_amount = self._label_amount_from_totals(nutrient)

        effective = dict(nutrient)
        effective["vd_reference"] = nutrient.get("vd_reference") or (
            nutrient.get("kcal", nutrient.get("amount", 0.0))
            if nutrient.get("type") == "energy"
            else nutrient.get("amount", 0.0)
        )

        if manual_amount is not None:
            if nutrient.get("type") == "energy":
                effective["kcal"] = manual_amount
                effective["kj"] = manual_amount * 4.184
                effective["amount"] = manual_amount
            else:
                effective["amount"] = manual_amount
            effective["manual"] = True
            return effective

        if totals_amount:
            if nutrient.get("type") == "energy":
                effective["kcal"] = totals_amount.get("kcal", nutrient.get("kcal", 0.0))
                effective["kj"] = totals_amount.get("kj", nutrient.get("kj", 0.0))
                effective["amount"] = effective["kcal"]
            else:
                effective["amount"] = totals_amount.get("amount", nutrient.get("amount", 0.0))
            effective["manual"] = False
            effective["from_totals"] = True
            return effective

        effective["manual"] = False
        effective["from_totals"] = False
        return effective


    def _update_label_table_preview(self) -> None:
        table = self.label_table_widget
        factor = self._current_portion_factor()
        table.clearSpans()

        display_nutrients = self._active_label_nutrients()
        filtered_nutrients: list[tuple[Dict[str, Any], Dict[str, Any]]] = []
        carb_children_present = False
        hide_zero_carb = {"Polialcoholes", "Polidextrosas"}
        for nutrient in display_nutrients:
            effective = self._effective_label_nutrient(nutrient)
            name = effective.get("name", nutrient.get("name", ""))
            if (
                nutrient.get("carb_child")
                and name in hide_zero_carb
                and math.isclose(effective.get("amount", 0.0) or 0.0, 0.0, abs_tol=1e-9)
            ):
                continue
            if nutrient.get("carb_child") and not nutrient.get("carb_parent"):
                carb_children_present = True
            filtered_nutrients.append((nutrient, effective))
        self._label_display_nutrients = [n for n, _ in filtered_nutrients]

        total_rows = (
            3
            + len(filtered_nutrients)
            + len(self.label_additional_selected)
            + (1 if self.label_no_significant else 0)
            + 1
        )
        table.setRowCount(total_rows)

        title_item = QTableWidgetItem("INFORMACIÓN NUTRICIONAL")
        title_font = title_item.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        title_item.setFont(title_font)
        title_item.setTextAlignment(Qt.AlignCenter)
        table.setItem(0, 0, title_item)

        portion_item = QTableWidgetItem(self._portion_description_for_table())
        portion_item.setTextAlignment(Qt.AlignCenter)
        table.setItem(1, 0, portion_item)

        header_font = QFont()
        header_font.setBold(True)
        header_item_amount = QTableWidgetItem("Cantidad por porción")
        header_item_amount.setFont(header_font)
        header_item_amount.setTextAlignment(Qt.AlignCenter)
        header_item_vd = QTableWidgetItem("% VD(*)")
        header_item_vd.setFont(header_font)
        header_item_vd.setTextAlignment(Qt.AlignCenter)
        header_placeholder = QTableWidgetItem("")
        header_placeholder.setFlags(header_placeholder.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEditable)
        header_placeholder.setData(self._header_span_role, True)
        header_item_amount.setData(self._header_span_role, True)
        header_item_vd.setData(self._header_span_role, True)
        table.setItem(2, 1, header_item_amount)
        table.setItem(2, 2, header_item_vd)
        table.setItem(2, 0, header_placeholder)

        for idx, (nutrient, effective) in enumerate(filtered_nutrients):
            row = 3 + idx
            name = effective.get("name", nutrient.get("name", ""))
            indent_level = nutrient.get("indent_level", 0)
            display_name = ("    " * indent_level) + name
            name_item = QTableWidgetItem(display_name)

            if effective.get("manual"):
                manual_amount = self.label_manual_overrides.get(name, 0.0)
                amount_text = self._format_manual_amount(effective, manual_amount)
                vd_text = self._format_manual_vd(effective, manual_amount)
            else:
                amount_text = self._format_nutrient_amount(effective, factor)
                eff_amount = (
                    effective.get("kcal", 0.0)
                    if effective.get("type") == "energy"
                    else effective.get("amount", 0.0)
                )
                vd_text = self._format_vd_value(effective, factor, eff_amount)
            if self.breakdown_fat_checkbox.isChecked() and nutrient.get("fat_parent"):
                amount_text = f"{amount_text}, de las cuales"
            if (
                self.breakdown_carb_checkbox.isChecked()
                and nutrient.get("carb_parent")
                and carb_children_present
            ):
                amount_text = f"{amount_text}, de los cuales"

            amount_item = QTableWidgetItem(amount_text)
            vd_item = QTableWidgetItem(vd_text)
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            amount_item.setTextAlignment(Qt.AlignCenter)
            vd_item.setTextAlignment(Qt.AlignCenter)
            if effective.get("manual"):
                brush = QBrush(self.label_manual_hint_color)
                for itm in (name_item, amount_item, vd_item):
                    itm.setBackground(brush)
                    itm.setData(self._manual_role, True)
            is_breakdown_child_row = bool(
                (self.breakdown_fat_checkbox.isChecked() and nutrient.get("fat_child") and not nutrient.get("fat_parent"))
                or (self.breakdown_carb_checkbox.isChecked() and nutrient.get("carb_child") and not nutrient.get("carb_parent"))
            )
            for itm in (name_item, amount_item, vd_item):
                itm.setData(self._fat_row_role, is_breakdown_child_row)
                if not itm.data(self._manual_role):
                    itm.setData(self._manual_role, False)
            table.setItem(row, 0, name_item)
            table.setItem(row, 1, amount_item)
            table.setItem(row, 2, vd_item)

        additional_rows_start = 3 + len(display_nutrients)
        for add_idx, add_name in enumerate(self.label_additional_selected):
            nutrient = next((n for n in self.label_additional_catalog if n["name"] == add_name), None)
            if not nutrient:
                continue
            effective = self._effective_label_nutrient(nutrient)
            row = additional_rows_start + add_idx
            name_item = QTableWidgetItem(add_name)
            amount_portion = (effective.get("amount", 0.0) or 0.0) * factor
            amount_item = QTableWidgetItem(self._format_additional_amount(amount_portion, nutrient.get("unit", "")))
            eff_amount = effective.get("amount", 0.0) or 0.0
            vd_item = QTableWidgetItem(self._format_vd_value(effective, factor, eff_amount))
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            amount_item.setTextAlignment(Qt.AlignCenter)
            vd_item.setTextAlignment(Qt.AlignCenter)
            for itm in (name_item, amount_item, vd_item):
                itm.setData(self._manual_role, bool(effective.get("manual")))
                if effective.get("manual"):
                    itm.setBackground(QBrush(self.label_manual_hint_color))
            table.setItem(row, 0, name_item)
            table.setItem(row, 1, amount_item)
            table.setItem(row, 2, vd_item)

        note_row = 3 + len(filtered_nutrients) + len(self.label_additional_selected)
        if self.label_no_significant:
            names = [
                self.label_no_significant_display_map.get(name, name)
                for name in self._sort_no_significant_list(self.label_no_significant)
            ]
            note_text = (
                f"No aporta cantidades significativas de {self._human_join(names)}."
            )
            note_item = QTableWidgetItem(note_text)
            note_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            table.setItem(note_row, 0, note_item)
            table.setSpan(note_row, 0, 1, 3)
            footer_row = note_row + 1
        else:
            footer_row = note_row

        footer_text = (
            "*% Valores Diarios con base a una dieta de 2000 kcal u 8400 kJ. "
            "Sus valores diarios pueden ser mayores o menores dependiendo de sus necesidades energéticas."
        )
        footer_item = QTableWidgetItem(footer_text)
        footer_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        table.setItem(footer_row, 0, footer_item)
        table.setSpan(0, 0, 1, 3)
        table.setSpan(1, 0, 1, 3)
        table.setSpan(footer_row, 0, 1, 3)
        self.label_table_footer_row = footer_row
        # Fix height for single-line rows (all menos notas/final), allow wrapping only on notes/footer.
        base_height = table.fontMetrics().height() + 6
        wrap_rows = {footer_row}
        if self.label_no_significant:
            wrap_rows.add(note_row)
        for r in range(table.rowCount()):
            if r in wrap_rows:
                table.resizeRowToContents(r)
            else:
                table.setRowHeight(r, base_height)


    def _update_linear_preview(self) -> None:
        factor = self._current_portion_factor()
        portion_desc = self._portion_description_for_table()
        display_nutrients = self._active_label_nutrients()
        parts: list[str] = []
        fat_children: list[str] = []
        fat_parent_text = None
        fat_parent_index = None
        carb_children: list[str] = []
        carb_parent_text = None
        carb_parent_index = None
        hide_zero_carb = {"Polialcoholes", "Polidextrosas"}

        for nutrient in display_nutrients:
            effective = self._effective_label_nutrient(nutrient)
            if effective.get("manual"):
                manual_amount = self.label_manual_overrides.get(
                    effective.get("name", ""), 0.0
                )
                amount = self._format_manual_amount(effective, manual_amount)
                vd = self._format_manual_vd(effective, manual_amount)
            else:
                amount = self._format_nutrient_amount(effective, factor)
                eff_amount = (
                    effective.get("kcal", 0.0)
                    if effective.get("type") == "energy"
                    else effective.get("amount", 0.0)
                )
                vd = self._format_vd_value(effective, factor, eff_amount)
            vd_suffix = "" if vd in ("", "-") else f" ({vd} VD*)"
            line_text = f"{nutrient.get('name', '')} {amount}{vd_suffix}"

            if (
                self.breakdown_fat_checkbox.isChecked()
                and nutrient.get("fat_child")
                and not nutrient.get("fat_parent")
            ):
                fat_children.append(line_text)
                continue

            if self.breakdown_fat_checkbox.isChecked() and nutrient.get("fat_parent"):
                fat_parent_text = line_text
                fat_parent_index = len(parts)
                continue

            if (
                self.breakdown_carb_checkbox.isChecked()
                and nutrient.get("carb_child")
                and not nutrient.get("carb_parent")
            ):
                if nutrient.get("name", "") in hide_zero_carb and math.isclose(
                    effective.get("amount", 0.0) or 0.0, 0.0, abs_tol=1e-9
                ):
                    continue
                carb_children.append(line_text)
                continue

            if self.breakdown_carb_checkbox.isChecked() and nutrient.get("carb_parent"):
                carb_parent_text = line_text
                carb_parent_index = len(parts)
                continue

            parts.append(line_text)

        if self.breakdown_fat_checkbox.isChecked() and fat_parent_text:
            fat_block = fat_parent_text
            if fat_children:
                fat_block = f"{fat_block}, de los cuales: " + ", ".join(fat_children)
            insert_idx = fat_parent_index if fat_parent_index is not None else len(parts)
            parts.insert(insert_idx, fat_block)

        if self.breakdown_carb_checkbox.isChecked() and carb_parent_text:
            carb_block = carb_parent_text
            if carb_children:
                carb_block = f"{carb_block}, de los cuales: " + ", ".join(carb_children)
            insert_idx = carb_parent_index if carb_parent_index is not None else len(parts)
            parts.insert(insert_idx, carb_block)

        for add_name in self.label_additional_selected:
            nutrient = next((n for n in self.label_additional_catalog if n["name"] == add_name), None)
            if not nutrient:
                continue
            effective = self._effective_label_nutrient(nutrient)
            amount_portion = (effective.get("amount", 0.0) or 0.0) * factor
            amount = self._format_additional_amount(amount_portion, nutrient.get("unit", ""))
            eff_amount = effective.get("amount", 0.0) or 0.0
            vd = self._format_vd_value(effective, factor, eff_amount)
            vd_suffix = "" if vd in ("", "-") else f" ({vd} VD*)"
            parts.append(f"{add_name} {amount}{vd_suffix}")

        note_text = ""
        if self.label_no_significant:
            names = [
                self.label_no_significant_display_map.get(name, name)
                for name in self._sort_no_significant_list(self.label_no_significant)
            ]
            note_text = f" No aporta cantidades significativas de {self._human_join(names)}."

        base_text = (
            "Información Nutricional: "
            f"{portion_desc}. "
            + "; ".join(parts)
            + ";"
            + note_text
            + " (*) % Valores Diarios con base a una dieta de 2.000 kcal u 8.400 kJ. "
            "Sus valores diarios pueden ser mayores o menores dependiendo de sus necesidades energéticas."
        )
        self.linear_format_preview.setPlainText(base_text)


    # ---- Rendering/export ----
    def _render_label_pixmap(self, with_background: bool) -> QPixmap | None:
        table = self.label_table_widget

        header = table.horizontalHeader()
        content_width = header.length()
        if content_width <= 0:
            content_width = sum(table.columnWidth(c) for c in range(table.columnCount()))

        v_header = table.verticalHeader()
        content_height = v_header.length()
        if content_height <= 0:
            content_height = sum(table.rowHeight(r) for r in range(table.rowCount()))

        padding = 2
        content_width += table.frameWidth() * 2
        content_height += table.frameWidth() * 2
        export_width = content_width + padding * 2
        export_height = content_height + padding * 2

        if content_width <= 0 or content_height <= 0:
            return None

        original_size = table.size()
        original_style = table.styleSheet()
        original_palette = table.palette()
        original_autofill = table.autoFillBackground()
        original_viewport_autofill = table.viewport().autoFillBackground()
        original_h_policy = table.horizontalScrollBarPolicy()
        original_v_policy = table.verticalScrollBarPolicy()
        original_table_attr = table.testAttribute(Qt.WA_TranslucentBackground)
        original_viewport_attr = table.viewport().testAttribute(Qt.WA_TranslucentBackground)

        sel_model = table.selectionModel()
        selected_indexes = list(sel_model.selectedIndexes()) if sel_model else []
        table.clearSelection()

        cleared_backgrounds: list[tuple[int, int, QBrush]] = []
        for r in range(table.rowCount()):
            for c in range(table.columnCount()):
                item = table.item(r, c)
                if not item:
                    continue
                bg = item.background()
                if bg.style() != Qt.NoBrush:
                    cleared_backgrounds.append((r, c, bg))
                    item.setBackground(QBrush(Qt.transparent))

        try:
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            table.setAttribute(Qt.WA_TranslucentBackground, True)
            table.viewport().setAttribute(Qt.WA_TranslucentBackground, True)
            table.viewport().setAutoFillBackground(False)
            table.setAutoFillBackground(False)

            pal = QPalette(table.palette())
            pal.setColor(QPalette.Text, QColor("#272727"))
            pal.setColor(QPalette.WindowText, QColor("#272727"))
            grid_color = "#c0c0c0"
            if with_background:
                pal.setColor(QPalette.Base, Qt.white)
                pal.setColor(QPalette.Window, Qt.white)
                pal.setColor(QPalette.AlternateBase, Qt.white)
                fill_color = Qt.white
                bg_style = "background-color: white; alternate-background-color: white;"
            else:
                pal.setColor(QPalette.Base, Qt.transparent)
                pal.setColor(QPalette.Window, Qt.transparent)
                pal.setColor(QPalette.AlternateBase, Qt.transparent)
                fill_color = Qt.transparent
                bg_style = (
                    "background-color: transparent; "
                    "alternate-background-color: transparent; "
                    "selection-background-color: transparent;"
                )

            table.setAutoFillBackground(False)
            table.setPalette(pal)
            table.setStyleSheet(
                f"{original_style} "
                f"QTableWidget {{ {bg_style} gridline-color: {grid_color}; }} "
                "QTableWidget::viewport { background: transparent; } "
                "QHeaderView::section { background-color: transparent; } "
                "QTableCornerButton::section { background-color: transparent; } "
            )

            table.resize(content_width, content_height)

            scale = 1.0 if with_background else 2.0
            scaled_width = int(export_width * scale)
            scaled_height = int(export_height * scale)
            image = QImage(scaled_width, scaled_height, QImage.Format_ARGB32_Premultiplied)
            image.fill(fill_color)

            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)
            if not with_background:
                painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.translate(padding * scale, padding * scale)
            painter.scale(scale, scale)
            table.render(painter, QPoint(0, 0))
            painter.end()
            if scale != 1.0:
                image = image.scaled(
                    export_width,
                    export_height,
                    Qt.IgnoreAspectRatio,
                    Qt.SmoothTransformation,
                )
            return QPixmap.fromImage(image)
        finally:
            table.resize(original_size)
            table.setStyleSheet(original_style)
            table.setPalette(original_palette)
            table.setAutoFillBackground(original_autofill)
            table.viewport().setAutoFillBackground(original_viewport_autofill)
            table.setHorizontalScrollBarPolicy(original_h_policy)
            table.setVerticalScrollBarPolicy(original_v_policy)
            table.setAttribute(Qt.WA_TranslucentBackground, original_table_attr)
            table.viewport().setAttribute(Qt.WA_TranslucentBackground, original_viewport_attr)
            for r, c, bg in cleared_backgrounds:
                item = table.item(r, c)
                if item:
                    item.setBackground(bg)
            if sel_model:
                for idx in selected_indexes:
                    sel_model.select(idx, QItemSelectionModel.Select)


    def _remove_image_background(self, image: QImage, tolerance: int = 6) -> QImage:
        """
        Convierte en transparente los píxeles que coinciden con el color de fondo dentro de una tolerancia.
        Esto permite exportar la tabla sin fondo (solo texto y líneas).
        """
        bg = image.pixelColor(0, 0)
        result = QImage(image)
        width = result.width()
        height = result.height()

        for y in range(height):
            for x in range(width):
                c = result.pixelColor(x, y)
                if (
                    abs(c.red() - bg.red()) <= tolerance
                    and abs(c.green() - bg.green()) <= tolerance
                    and abs(c.blue() - bg.blue()) <= tolerance
                ):
                    c.setAlpha(0)
                    result.setPixelColor(x, y, c)
        return result


    def _strip_to_strokes(self, image: QImage) -> QImage:
        """
        Deja solo trazos (texto y líneas) eliminando fondos claros residuales.
        Conserva píxeles cercanos al color de texto (#272727) o líneas (#c0c0c0) y elimina el resto.
        """
        text_color = QColor("#272727")
        grid_color = QColor("#c0c0c0")
        text_r, text_g, text_b = text_color.red(), text_color.green(), text_color.blue()
        grid_r, grid_g, grid_b = grid_color.red(), grid_color.green(), grid_color.blue()
        text_tol = 45  # distancia máxima para conservar texto (cubre antialias y #8F8F8F/#9B9B9B)
        grid_tol = 8   # líneas muy cercanas al gris exacto
        result = QImage(image.size(), QImage.Format_ARGB32)
        result.fill(Qt.transparent)
        width = image.width()
        height = image.height()

        for y in range(height):
            for x in range(width):
                c = image.pixelColor(x, y)
                if c.alpha() == 0:
                    continue
                r, g, b = c.red(), c.green(), c.blue()
                dist_text = ((r - text_r) ** 2 + (g - text_g) ** 2 + (b - text_b) ** 2) ** 0.5
                dist_grid = ((r - grid_r) ** 2 + (g - grid_g) ** 2 + (b - grid_b) ** 2) ** 0.5
                if dist_text <= text_tol:
                    out = QColor(text_color)
                    out.setAlpha(c.alpha())
                    result.setPixelColor(x, y, out)
                    continue
                if dist_grid <= grid_tol:
                    out = QColor(grid_color)
                    out.setAlpha(c.alpha())
                    result.setPixelColor(x, y, out)
                    continue
                # otherwise leave transparent
        return result


    def _clear_white_background(self, image: QImage, threshold: int = 245) -> QImage:
        """
        Hace transparente cualquier pixel casi blanco (>= threshold en R,G,B), preservando otros colores.
        """
        result = QImage(image)
        width = result.width()
        height = result.height()
        for y in range(height):
            for x in range(width):
                c = result.pixelColor(x, y)
                if c.red() >= threshold and c.green() >= threshold and c.blue() >= threshold:
                    c.setAlpha(0)
                    result.setPixelColor(x, y, c)
        return result


    def _update_label_preview(self, force_recalc_totals: bool = False) -> None:
        if QThread.currentThread() is not self.thread():
            QTimer.singleShot(0, lambda: self._update_label_preview(force_recalc_totals))
            return
        if force_recalc_totals or not self._last_totals:
            self._last_totals = self._calculate_totals()
        if not self._suspend_no_sig_update:
            self._update_no_significant_controls()
        self._update_additional_controls()
        self._update_label_table_preview()
        self._update_linear_preview()


    def _on_export_label_table_clicked(self, with_background: bool) -> None:
        default_name = "etiqueta_con_fondo.png" if with_background else "etiqueta_sin_fondo.png"
        initial_path = (
            str(Path(self.last_path or "").with_name(default_name)) if self.last_path else default_name
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar tabla como PNG",
            initial_path,
            f"PNG (*.png);;Todos los archivos (*)",
        )
        if not path:
            return

        pixmap = self._render_label_pixmap(with_background)
        if pixmap is None:
            QMessageBox.warning(self, "Error", "No se pudo generar la imagen.")
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        if pixmap.save(path, "PNG"):
            self.last_path = Path(path).parent
            self._save_last_path(self.last_path)
            QMessageBox.information(self, "Exportado", f"Tabla guardada en:\n{path}")
        else:
            QMessageBox.warning(self, "Error", "No se pudo guardar la imagen.")

