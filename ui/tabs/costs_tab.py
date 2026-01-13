
from __future__ import annotations

from decimal import Decimal
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from domain.models import CurrencyRate, ProcessCost
from domain.services import cost_service
from domain.services.number_parser import parse_user_number
from domain.services.unit_normalizer import convert_mass, normalize_mass_unit
from ui.actions.normalize_mass_action import NormalizeMassAction
from ui.formatters import fmt_decimal, fmt_money_mn, fmt_percent, fmt_qty
from ui.tabs.table_utils import apply_selection_bar, attach_copy_shortcut
from ui.widgets.composite_table import CompositeGridTable
from ui.widgets.grouped_header import GroupedHeaderView
from ui.widgets.number_spinbox import UserNumberSpinBox
from ui.widgets.sortable_table_item import (
    SortableTableWidgetItem,
    sort_key_numeric,
    sort_key_text,
)


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class StackedBarWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._values = (Decimal("0"), Decimal("0"), Decimal("0"))
        self._colors = (
            QColor("#4caf50"),
            QColor("#f4c542"),
            QColor("#81c4f8"),
        )

    def set_values(self, ingredients: Decimal, processes: Decimal, packaging: Decimal) -> None:
        self._values = (ingredients, processes, packaging)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        total = sum(self._values)
        if total <= 0:
            painter.fillRect(rect, QColor("#e0e0e0"))
            painter.end()
            return

        x = rect.left()
        for value, color in zip(self._values, self._colors):
            if value <= 0:
                continue
            width = int(rect.width() * float(value / total))
            if width <= 0:
                continue
            painter.fillRect(x, rect.top(), width, rect.height(), color)
            x += width

        # Fill any remaining pixels to the end.
        if x < rect.right():
            painter.fillRect(x, rect.top(), rect.right() - x + 1, rect.height(), self._colors[-1])
        painter.end()


class TotalBadgeWidget(QFrame):
    def __init__(self, label_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("costs_total_badge")
        self.setStyleSheet(
            "QFrame#costs_total_badge { border: 1px solid #e0e0e0; border-radius: 8px; "
            "padding: 6px 10px; background: #f7f7f7; }"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)
        self._label = QLabel(label_text)
        self._value = QLabel("$ 0.00")
        font = self._value.font()
        font.setBold(True)
        self._value.setFont(font)
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_value(self, text: str) -> None:
        self._value.setText(text)


class CostsTabMixin:
    """Costs tab UI and behavior."""

    def _init_costs_state(self) -> None:
        self._costs_block_signals = False
        self._costs_total_batch_mn = Decimal("0")
        self._row_index_role = Qt.UserRole + 1
        self._costs_sort_state = {
            "ingredients": {"column": None, "order": Qt.AscendingOrder},
            "processes": {"column": None, "order": Qt.AscendingOrder},
            "packaging": {"column": None, "order": Qt.AscendingOrder},
        }
        self._ingredient_cost_columns = {
            "ingredient": 0,
            "amount": 1,
            "pack_amount": 2,
            "pack_unit": 3,
            "currency": 4,
            "cost_value": 5,
            "unit_cost": 6,
            "batch_cost": 7,
            "percent": 8,
        }
        self._process_columns = {
            "name": 0,
            "time_total": 1,
            "total_cost": 2,
            "delete": 3,
        }
        self._packaging_columns = {
            "name": 0,
            "qty": 1,
            "currency": 2,
            "unit_cost": 3,
            "subtotal": 4,
            "delete": 5,
        }

    def _build_costs_tab_ui(self) -> None:
        layout = QVBoxLayout(self.costs_tab)
        layout.setSpacing(8)

        def _card_title(text: str) -> QLabel:
            label = QLabel(text)
            font = label.font()
            font.setBold(True)
            label.setFont(font)
            return label

        def _build_card() -> QFrame:
            frame = QFrame(self.costs_tab)
            frame.setObjectName("costs_card")
            frame.setStyleSheet(
                "QFrame#costs_card { border: 1px solid #e0e0e0; border-radius: 10px; "
                "padding: 6px; background: #ffffff; }"
            )
            return frame

        def _build_panel() -> QFrame:
            frame = QFrame(self.costs_tab)
            frame.setObjectName("costs_panel")
            frame.setStyleSheet(
                "QFrame#costs_panel { border: 1px solid #e6e6e6; border-radius: 10px; "
                "padding: 10px; background: #ffffff; }"
            )
            return frame

        # Zona 1: KPIs / Cards
        header_container = QWidget(self.costs_tab)
        header_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)
        self._costs_header_container = header_container

        # Card 1: Tirada
        tirada_card = _build_card()
        tirada_layout = QGridLayout(tirada_card)
        tirada_layout.setContentsMargins(0, 0, 0, 0)
        tirada_layout.setVerticalSpacing(4)
        tirada_layout.setHorizontalSpacing(6)
        tirada_header = QHBoxLayout()
        self.costs_normalize_action = NormalizeMassAction(
            self,
            get_current_unit=self._current_mass_unit,
            get_total_mass_g=self._total_weight,
            apply_normalization=self.formulation_presenter.normalize_to_target_weight,
            set_unit=self._set_quantity_mode,
            after_apply=self._after_normalize_from_costs,
            decimals_for_unit=self.formulation_presenter.mass_decimals,
            can_run=self._can_normalize_mass,
            on_blocked=self._show_status_message,
        )
        self.costs_normalize_button = self.costs_normalize_action.create_button("Normalizar masa")
        tirada_header.addWidget(_card_title("Tirada"))
        tirada_header.addStretch()
        tirada_header.addWidget(self.costs_normalize_button)
        self.costs_batch_mass_label = QLabel("-")
        self.costs_yield_input = UserNumberSpinBox()
        self.costs_yield_input.setRange(0.01, 100.0)
        self.costs_yield_input.setDecimals(2)
        self.costs_sellable_mass_label = QLabel("-")
        tirada_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        tirada_layout.addLayout(tirada_header, 0, 0, 1, 2)
        tirada_layout.addWidget(QLabel("Masa tirada:"), 1, 0)
        tirada_layout.addWidget(self.costs_batch_mass_label, 1, 1)
        tirada_layout.addWidget(QLabel("Rendimiento (%):"), 2, 0)
        tirada_layout.addWidget(self.costs_yield_input, 2, 1)
        tirada_layout.addWidget(QLabel("Masa vendible:"), 3, 0)
        tirada_layout.addWidget(self.costs_sellable_mass_label, 3, 1)

        # Card 2: Totales
        totals_card = _build_card()
        totals_layout = QVBoxLayout(totals_card)
        totals_layout.setContentsMargins(0, 0, 0, 0)
        totals_layout.setSpacing(4)
        totals_header = QHBoxLayout()
        totals_header.addWidget(_card_title("Totales"))
        totals_header.addStretch()
        self.costs_load_rates_button = QPushButton("Cargar cotizaciones")
        totals_header.addWidget(self.costs_load_rates_button)
        totals_layout.addLayout(totals_header)
        totals_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        totals_grid = QGridLayout()
        self.costs_total_label = QLabel("$ 0.00")
        self.costs_total_packaged_label = QLabel("$ 0.00")
        total_font = self.costs_total_label.font()
        total_font.setBold(True)
        self.costs_total_label.setFont(total_font)
        packaged_font = self.costs_total_packaged_label.font()
        packaged_font.setBold(True)
        self.costs_total_packaged_label.setFont(packaged_font)
        totals_grid.addWidget(QLabel("Costo total tirada:"), 0, 0)
        totals_grid.addWidget(self.costs_total_label, 0, 1)
        totals_grid.addWidget(QLabel("Costo total envasado:"), 1, 0)
        totals_grid.addWidget(self.costs_total_packaged_label, 1, 1)
        totals_layout.addLayout(totals_grid)

        # Card 3: Total por pack
        pack_card = _build_card()
        pack_card.setStyleSheet(
            "QFrame#costs_card { border: 1px solid #d0d0d0; border-radius: 12px; "
            "padding: 6px; background: #f7f7f7; }"
        )
        pack_layout = QVBoxLayout(pack_card)
        pack_layout.setContentsMargins(0, 0, 0, 0)
        pack_layout.setSpacing(6)
        pack_header = QHBoxLayout()
        pack_header.addWidget(_card_title("Total por pack"))
        pack_header.addStretch()
        pack_header.addWidget(QLabel("Masa objetivo:"))
        self.costs_target_mass_input = UserNumberSpinBox()
        self.costs_target_mass_input.setRange(0.01, 1_000_000.0)
        self.costs_target_mass_input.setDecimals(3)
        self.costs_target_mass_input.setValue(100.0)
        self.costs_target_unit_selector = QComboBox()
        self.costs_target_unit_selector.addItems(["g", "kg", "lb", "oz", "ton"])
        pack_header.addWidget(self.costs_target_mass_input)
        pack_header.addWidget(self.costs_target_unit_selector)
        pack_layout.addLayout(pack_header)
        pack_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.costs_pack_total_label = QLabel("$ 0.00")
        pack_total_font = self.costs_pack_total_label.font()
        pack_total_font.setPointSize(pack_total_font.pointSize() + 8)
        pack_total_font.setBold(True)
        self.costs_pack_total_label.setFont(pack_total_font)
        self.costs_pack_total_label.setStyleSheet("color: #111111;")
        pack_total_row = QHBoxLayout()
        pack_total_row.addWidget(self.costs_pack_total_label)
        pack_total_row.addStretch()

        self.costs_pack_bar = StackedBarWidget(pack_card)
        self.costs_pack_bar.setFixedHeight(10)
        self.costs_units_count_label = QLabel("Packs por tirada: -")
        self.costs_pack_composition_label = QLabel("Ingredientes - | Procesos - | Packaging -")
        self.costs_pack_composition_label.setWordWrap(True)
        secondary_labels = [self.costs_units_count_label, self.costs_pack_composition_label]
        for label in secondary_labels:
            font = label.font()
            font.setPointSize(max(font.pointSize() - 1, 8))
            label.setFont(font)
            label.setStyleSheet("color: #555555;")
        pack_total_row.addWidget(self.costs_units_count_label)
        pack_layout.addLayout(pack_total_row)
        pack_layout.addWidget(self.costs_pack_bar)
        pack_layout.addWidget(self.costs_pack_composition_label)

        header_layout.addWidget(tirada_card, 2)
        header_layout.addWidget(totals_card, 2)
        header_layout.addWidget(pack_card, 3)
        self._costs_kpi_cards = [tirada_card, totals_card, pack_card]
        layout.addWidget(header_container)

        # Zona 2: Body (ingredientes arriba, procesos/packaging abajo)
        body_splitter = QSplitter(Qt.Vertical, self.costs_tab)
        body_splitter.setChildrenCollapsible(False)
        self._costs_body_splitter = body_splitter
        layout.addWidget(body_splitter, 1)

        # Insumos (ancho completo)
        ingredients_panel = _build_panel()
        ingredients_layout = QVBoxLayout(ingredients_panel)
        ingredients_layout.setContentsMargins(0, 0, 0, 0)
        ingredients_header = QHBoxLayout()
        ingredients_header.addWidget(_card_title("Insumos / Ingredientes"))
        self.costs_ingredients_completion_label = QLabel("Completo: -")
        ingredients_header.addWidget(self.costs_ingredients_completion_label)
        ingredients_header.addStretch()
        ingredients_layout.addLayout(ingredients_header)

        self.costs_ingredients_table = CompositeGridTable(0, len(self._ingredient_cost_columns))
        self.costs_ingredients_table.setHorizontalHeaderLabels(
            [
                "Ingrediente",
                "Cantidad",
                "",
                "",
                "",
                "",
                "$/kg",
                "$ tirada",
                "% insumos",
            ]
        )
        ingredients_header = GroupedHeaderView(Qt.Horizontal, self.costs_ingredients_table)
        ingredients_header.set_groups(
            [
                (
                    self._ingredient_cost_columns["pack_amount"],
                    self._ingredient_cost_columns["pack_unit"],
                    "Presentacion",
                ),
                (
                    self._ingredient_cost_columns["currency"],
                    self._ingredient_cost_columns["cost_value"],
                    "Costo",
                ),
            ]
        )
        self.costs_ingredients_table.setHorizontalHeader(ingredients_header)
        self.costs_ingredients_table.set_hidden_vertical_borders(
            [
                self._ingredient_cost_columns["pack_amount"],
                self._ingredient_cost_columns["currency"],
            ]
        )
        self.costs_ingredients_table.horizontalHeader().setSectionResizeMode(
            self._ingredient_cost_columns["ingredient"], QHeaderView.Stretch
        )
        for col_key in (
            "amount",
            "pack_amount",
            "pack_unit",
            "currency",
            "cost_value",
            "unit_cost",
            "batch_cost",
            "percent",
        ):
            self.costs_ingredients_table.horizontalHeader().setSectionResizeMode(
                self._ingredient_cost_columns[col_key], QHeaderView.ResizeToContents
            )
        self.costs_ingredients_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.costs_ingredients_table.setSelectionMode(QTableWidget.ExtendedSelection)
        apply_selection_bar(self.costs_ingredients_table)
        ingredients_layout.addWidget(self.costs_ingredients_table)
        self.costs_ingredients_total_badge = TotalBadgeWidget("Total insumos:")
        ingredients_total_row = QHBoxLayout()
        ingredients_total_row.addStretch()
        ingredients_total_row.addWidget(self.costs_ingredients_total_badge)
        ingredients_layout.addLayout(ingredients_total_row)

        body_splitter.addWidget(ingredients_panel)

        # Procesos + Packaging (en paralelo)
        processes_packaging_container = QWidget(self.costs_tab)
        processes_packaging_layout = QHBoxLayout(processes_packaging_container)
        processes_packaging_layout.setContentsMargins(0, 0, 0, 0)
        processes_packaging_layout.setSpacing(10)
        self._costs_processes_packaging_container = processes_packaging_container
        body_splitter.addWidget(processes_packaging_container)
        body_splitter.setStretchFactor(0, 4)
        body_splitter.setStretchFactor(1, 1)

        # Panel Procesos
        processes_panel = _build_panel()
        processes_layout = QVBoxLayout(processes_panel)
        processes_layout.setContentsMargins(0, 0, 0, 0)
        processes_header = QHBoxLayout()
        processes_header.addWidget(_card_title("Procesos"))
        processes_header.addStretch()
        self.costs_add_process_button = QPushButton("+ Agregar proceso")
        processes_header.addWidget(self.costs_add_process_button)
        processes_layout.addLayout(processes_header)

        self.costs_process_stack = QStackedWidget(processes_panel)

        process_table_container = QWidget(processes_panel)
        process_table_layout = QVBoxLayout(process_table_container)
        process_table_layout.setContentsMargins(0, 0, 0, 0)
        self.costs_process_table = QTableWidget(0, len(self._process_columns))
        self.costs_process_table.setHorizontalHeaderLabels(
            ["Nombre", "Tiempo total", "$ total", ""]
        )
        self.costs_process_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.costs_process_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.costs_process_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.costs_process_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self.costs_process_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.costs_process_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.costs_process_table.setEditTriggers(QTableWidget.NoEditTriggers)
        apply_selection_bar(self.costs_process_table)
        process_table_layout.addWidget(self.costs_process_table)


        process_empty = QWidget(processes_panel)
        process_empty_layout = QVBoxLayout(process_empty)
        process_empty_layout.addStretch()
        empty_label = QLabel("No hay procesos cargados.")
        empty_label.setStyleSheet("color: gray;")
        self.costs_add_process_button_empty = QPushButton("+ Agregar proceso")
        process_empty_layout.addWidget(empty_label, alignment=Qt.AlignCenter)
        process_empty_layout.addWidget(self.costs_add_process_button_empty, alignment=Qt.AlignCenter)
        process_empty_layout.addStretch()

        self.costs_process_stack.addWidget(process_table_container)
        self.costs_process_stack.addWidget(process_empty)
        processes_layout.addWidget(self.costs_process_stack)
        self.costs_process_total_badge = TotalBadgeWidget("Total procesos:")
        processes_total_row = QHBoxLayout()
        processes_total_row.addStretch()
        processes_total_row.addWidget(self.costs_process_total_badge)
        processes_layout.addLayout(processes_total_row)
        processes_packaging_layout.addWidget(processes_panel, 1)

        # Panel Packaging
        packaging_panel = _build_panel()
        packaging_layout = QVBoxLayout(packaging_panel)
        packaging_layout.setContentsMargins(0, 0, 0, 0)
        packaging_header = QHBoxLayout()
        packaging_header.addWidget(_card_title("Packaging"))
        packaging_header.addStretch()
        self.costs_add_packaging_button = QPushButton("+ Agregar packaging")
        packaging_header.addWidget(self.costs_add_packaging_button)
        packaging_layout.addLayout(packaging_header)

        self.costs_packaging_stack = QStackedWidget(packaging_panel)

        packaging_table_container = QWidget(packaging_panel)
        packaging_table_layout = QVBoxLayout(packaging_table_container)
        packaging_table_layout.setContentsMargins(0, 0, 0, 0)
        self.costs_packaging_table = CompositeGridTable(0, len(self._packaging_columns))
        self.costs_packaging_table.setHorizontalHeaderLabels(
            [
                "Nombre",
                "Cantidad/pack",
                "",
                "",
                "Subtotal",
                "",
            ]
        )
        packaging_header = GroupedHeaderView(Qt.Horizontal, self.costs_packaging_table)
        packaging_header.set_groups(
            [
                (
                    self._packaging_columns["currency"],
                    self._packaging_columns["unit_cost"],
                    "Costo Unitario",
                ),
            ]
        )
        self.costs_packaging_table.setHorizontalHeader(packaging_header)
        self.costs_packaging_table.set_hidden_vertical_borders(
            [self._packaging_columns["currency"]]
        )
        self.costs_packaging_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.costs_packaging_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.costs_packaging_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.costs_packaging_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeToContents
        )
        self.costs_packaging_table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeToContents
        )
        self.costs_packaging_table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeToContents
        )
        self.costs_packaging_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.costs_packaging_table.setSelectionMode(QTableWidget.ExtendedSelection)
        apply_selection_bar(self.costs_packaging_table)
        packaging_table_layout.addWidget(self.costs_packaging_table)


        packaging_empty = QWidget(packaging_panel)
        packaging_empty_layout = QVBoxLayout(packaging_empty)
        packaging_empty_layout.addStretch()
        packaging_label = QLabel("No hay items de packaging.")
        packaging_label.setStyleSheet("color: gray;")
        self.costs_add_packaging_button_empty = QPushButton("+ Agregar packaging")
        packaging_empty_layout.addWidget(packaging_label, alignment=Qt.AlignCenter)
        packaging_empty_layout.addWidget(
            self.costs_add_packaging_button_empty, alignment=Qt.AlignCenter
        )
        packaging_empty_layout.addStretch()

        self.costs_packaging_stack.addWidget(packaging_table_container)
        self.costs_packaging_stack.addWidget(packaging_empty)
        packaging_layout.addWidget(self.costs_packaging_stack)
        self.costs_packaging_total_badge = TotalBadgeWidget("Total Packaging:")
        packaging_total_row = QHBoxLayout()
        packaging_total_row.addStretch()
        packaging_total_row.addWidget(self.costs_packaging_total_badge)
        packaging_layout.addLayout(packaging_total_row)
        processes_packaging_layout.addWidget(packaging_panel, 1)

        # Conexiones
        self.costs_load_rates_button.clicked.connect(self._on_load_rates_clicked)
        self.costs_yield_input.valueChanged.connect(self._on_yield_changed)
        self.costs_target_mass_input.valueChanged.connect(self._update_costs_calculator)
        self.costs_target_unit_selector.currentTextChanged.connect(
            lambda _text: self._update_costs_calculator()
        )
        self.costs_add_process_button.clicked.connect(self._on_add_process_clicked)
        self.costs_add_process_button_empty.clicked.connect(self._on_add_process_clicked)
        self.costs_process_table.itemDoubleClicked.connect(self._on_process_double_clicked)
        self.costs_add_packaging_button.clicked.connect(self._on_add_packaging_clicked)
        self.costs_add_packaging_button_empty.clicked.connect(self._on_add_packaging_clicked)
        self.costs_ingredients_table.itemChanged.connect(
            self._on_ingredient_cost_item_changed
        )
        self.costs_packaging_table.itemChanged.connect(self._on_packaging_item_changed)

        attach_copy_shortcut(self.costs_ingredients_table)
        attach_copy_shortcut(self.costs_process_table)
        attach_copy_shortcut(self.costs_packaging_table)

        paste_shortcut = QShortcut(QKeySequence.Paste, self.costs_ingredients_table)
        paste_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        paste_shortcut.activated.connect(self._paste_ingredients_table)

        self._apply_costs_column_widths()
        self._setup_costs_sorting()
        self._refresh_costs_view()
        self._apply_costs_layout_sizing()

    def _apply_costs_column_widths(self) -> None:
        table = self.costs_ingredients_table
        table.setColumnWidth(self._ingredient_cost_columns["ingredient"], 200)
        table.setColumnWidth(self._ingredient_cost_columns["amount"], 90)
        table.setColumnWidth(self._ingredient_cost_columns["pack_amount"], 90)
        table.setColumnWidth(self._ingredient_cost_columns["pack_unit"], 60)
        table.setColumnWidth(self._ingredient_cost_columns["currency"], 70)
        table.setColumnWidth(self._ingredient_cost_columns["cost_value"], 80)
        table.setColumnWidth(self._ingredient_cost_columns["unit_cost"], 90)
        table.setColumnWidth(self._ingredient_cost_columns["batch_cost"], 100)
        table.setColumnWidth(self._ingredient_cost_columns["percent"], 70)

        process_table = self.costs_process_table
        process_table.setColumnWidth(self._process_columns["name"], 140)
        process_table.setColumnWidth(self._process_columns["time_total"], 90)
        process_table.setColumnWidth(self._process_columns["total_cost"], 90)
        process_table.setColumnWidth(self._process_columns["delete"], 30)

        packaging_table = self.costs_packaging_table
        packaging_table.setColumnWidth(self._packaging_columns["name"], 150)
        packaging_table.setColumnWidth(self._packaging_columns["qty"], 90)
        packaging_table.setColumnWidth(self._packaging_columns["currency"], 70)
        packaging_table.setColumnWidth(self._packaging_columns["unit_cost"], 90)
        packaging_table.setColumnWidth(self._packaging_columns["subtotal"], 90)
        packaging_table.setColumnWidth(self._packaging_columns["delete"], 30)

    def _apply_costs_layout_sizing(self) -> None:
        self._sync_costs_card_heights()

        self._set_table_min_rows(self.costs_process_table, 3)
        self._set_table_min_rows(self.costs_packaging_table, 3)

        splitter = getattr(self, "_costs_body_splitter", None)
        container = getattr(self, "_costs_processes_packaging_container", None)
        if splitter is not None and container is not None:
            bottom_size = container.sizeHint().height()
            top_hint = self.costs_ingredients_table.sizeHint().height()
            top_size = max(top_hint, bottom_size * 3)
            splitter.setSizes([top_size, bottom_size])

    def _set_table_min_rows(self, table: QTableWidget, rows: int) -> None:
        header_height = table.horizontalHeader().sizeHint().height()
        row_height = table.verticalHeader().defaultSectionSize()
        frame = table.frameWidth() * 2
        target = header_height + (row_height * rows) + frame
        table.setMinimumHeight(target)

    def _setup_costs_sorting(self) -> None:
        for table in (
            self.costs_ingredients_table,
            self.costs_process_table,
            self.costs_packaging_table,
        ):
            table.setSortingEnabled(True)
            header = table.horizontalHeader()
            header.setSortIndicatorShown(True)

        self.costs_ingredients_table.horizontalHeader().sectionClicked.connect(
            lambda section: self._on_costs_sort_clicked(
                "ingredients", self.costs_ingredients_table, section
            )
        )
        self.costs_process_table.horizontalHeader().sectionClicked.connect(
            lambda section: self._on_costs_sort_clicked(
                "processes", self.costs_process_table, section
            )
        )
        self.costs_packaging_table.horizontalHeader().sectionClicked.connect(
            lambda section: self._on_costs_sort_clicked(
                "packaging", self.costs_packaging_table, section
            )
        )

    def _on_costs_sort_clicked(self, key: str, table: QTableWidget, section: int) -> None:
        header = table.horizontalHeader()
        target = section
        if isinstance(header, GroupedHeaderView):
            target = header.left_for_section(section)
        state = self._costs_sort_state.get(key)
        order = Qt.AscendingOrder
        if state is not None:
            if state["column"] == target:
                order = (
                    Qt.DescendingOrder
                    if state["order"] == Qt.AscendingOrder
                    else Qt.AscendingOrder
                )
            state["column"] = target
            state["order"] = order
        table.sortItems(target, order)
        header.setSortIndicator(target, order)

    def _sync_costs_card_heights(self) -> None:
        cards = getattr(self, "_costs_kpi_cards", None)
        if not cards:
            return
        max_height = max(card.sizeHint().height() for card in cards)
        for card in cards:
            card.setMinimumHeight(max_height)
            card.setMaximumHeight(max_height)

        header_container = getattr(self, "_costs_header_container", None)
        if header_container is not None:
            header_container.setMinimumHeight(max_height)
            header_container.setMaximumHeight(max_height)

    def _format_mass(self, value_g: Decimal, unit: str) -> str:
        unit_norm = normalize_mass_unit(unit) or unit
        converted = convert_mass(value_g, "g", unit_norm) or value_g
        decimals = self.formulation_presenter.mass_decimals(unit_norm)
        return fmt_qty(converted, unit_norm, decimals=decimals)

    def _format_money(self, value: Decimal | None) -> str:
        return fmt_money_mn(value, decimals=2, thousands=True)

    def _format_percent(self, value: Decimal | None) -> str:
        return fmt_percent(value, decimals=1)

    def _format_time_total(self, value_h: Decimal | None) -> str:
        if value_h is None:
            return "-"
        try:
            value = Decimal(str(value_h))
        except Exception:
            return "-"
        if value <= 0:
            return "-"
        if value >= 1:
            return f"{fmt_decimal(value, decimals=2)} h"
        minutes = value * Decimal("60")
        return f"{fmt_decimal(minutes, decimals=0)} min"


    def _make_readonly_item(
        self, text: str, sort_key=None
    ) -> QTableWidgetItem:
        item = SortableTableWidgetItem(text)
        if sort_key is not None:
            item.setData(Qt.UserRole, sort_key)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _make_numeric_item(
        self, text: str, readonly: bool = True, sort_key=None
    ) -> QTableWidgetItem:
        item = SortableTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if sort_key is not None:
            item.setData(Qt.UserRole, sort_key)
        if readonly:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _set_row_index(self, item: QTableWidgetItem, index: int) -> None:
        item.setData(self._row_index_role, index)

    def _get_row_index(self, table: QTableWidget, row: int) -> int | None:
        if row < 0 or row >= table.rowCount():
            return None
        item = table.item(row, 0)
        if item is None:
            return None
        data = item.data(self._row_index_role)
        if data is None:
            return row
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def _find_row_for_index(self, table: QTableWidget, index: int) -> int | None:
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item is None:
                continue
            data = item.data(self._row_index_role)
            if data is None:
                continue
            try:
                if int(data) == index:
                    return row
            except (TypeError, ValueError):
                continue
        return None

    def _make_delete_button(self) -> QPushButton:
        button = QPushButton("✖")
        button.setFixedWidth(22)
        button.setFlat(True)
        button.setStyleSheet(
            "QPushButton { color: #c62828; font-weight: bold; border: none; }"
            "QPushButton:hover { color: #8e0000; }"
        )
        return button

    def _refresh_costs_view(self) -> None:
        if self._costs_block_signals:
            return
        self._costs_block_signals = True
        try:
            self._sync_target_mass_inputs()
            self._update_costs_summary()
            self._populate_ingredients_costs_table()
            self._populate_processes_table()
            self._populate_packaging_table()
            self._update_costs_calculator()
        finally:
            self._costs_block_signals = False

    def _after_normalize_from_costs(self, value: Decimal, unit: str) -> None:
        self._refresh_formulation_views()
        self._refresh_costs_view()
        decimals = self.formulation_presenter.mass_decimals(unit)
        message = f"Formulacion normalizada a {fmt_decimal(value, decimals=decimals)} {unit}."
        self._show_status_message(message)

    def _update_costs_summary(self) -> None:
        summary = self.costs_presenter.summary()
        unit = self.formulation_presenter.current_mass_unit(self.quantity_mode)
        self.costs_batch_mass_label.setText(
            self._format_mass(summary["batch_mass_g"], unit)
        )
        self.costs_sellable_mass_label.setText(
            self._format_mass(summary["sellable_mass_g"], unit)
        )
        self.costs_yield_input.blockSignals(True)
        self.costs_yield_input.setValue(float(summary["yield_percent"]))
        self.costs_yield_input.blockSignals(False)

        self.costs_ingredients_total_badge.set_value(
            self._format_money(summary["ingredients_total_mn"])
        )
        self.costs_process_total_badge.set_value(
            self._format_money(summary["process_total_mn"])
        )
        self.costs_total_label.setText(self._format_money(summary["total_cost_mn"]))
        self._costs_total_batch_mn = summary["total_cost_mn"]

        ingredients_pct = summary["ingredients_percent"]
        completeness_text = f"Completo: {fmt_decimal(ingredients_pct, decimals=0)}%"
        self.costs_ingredients_completion_label.setText(completeness_text)
        if ingredients_pct >= 100:
            self.costs_ingredients_completion_label.setStyleSheet("color: #2e7d32;")
        elif ingredients_pct >= 50:
            self.costs_ingredients_completion_label.setStyleSheet("color: #f9a825;")
        else:
            self.costs_ingredients_completion_label.setStyleSheet("color: #c62828;")

    def _on_load_rates_clicked(self) -> None:
        rates = self._prompt_currency_rates()
        if rates is None:
            return
        self.costs_presenter.set_currency_rates(rates)
        valid_symbols = {rate.symbol for rate in rates if rate.symbol}
        missing = [
            ing.description
            for ing in self.costs_presenter.formulation.ingredients
            if str(ing.cost_currency_symbol or "").strip()
            and str(ing.cost_currency_symbol or "").strip() not in valid_symbols
        ]
        if missing:
            QMessageBox.warning(
                self,
                "Cotizaciones",
                "Hay ingredientes con moneda sin cotizacion. "
                "Revisa las filas marcadas en la tabla de insumos.",
            )
        self._refresh_costs_view()

    def _prompt_currency_rates(self) -> List[CurrencyRate] | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Cotizaciones")
        layout = QVBoxLayout(dialog)

        table = QTableWidget(0, 3, dialog)
        table.setHorizontalHeaderLabels(
            ["Moneda", "Simbolo", "Cotizacion a MN"]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.ExtendedSelection)
        layout.addWidget(table)

        def _set_base_row(row: int) -> None:
            values = ["Moneda Nacional", "$", "1"]
            for col, text in enumerate(values):
                item = table.item(row, col)
                if item is None:
                    item = QTableWidgetItem(text)
                    table.setItem(row, col, item)
                item.setText(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

        def _add_row(rate: CurrencyRate | None = None, *, locked: bool = False) -> None:
            row = table.rowCount()
            table.insertRow(row)
            if locked:
                _set_base_row(row)
                return
            name = "" if rate is None else rate.name
            symbol = "" if rate is None else rate.symbol
            rate_value = "" if rate is None else str(rate.rate_to_mn)
            table.setItem(row, 0, QTableWidgetItem(str(name or "")))
            table.setItem(row, 1, QTableWidgetItem(str(symbol or "")))
            table.setItem(row, 2, QTableWidgetItem(str(rate_value or "")))

        def _add_empty_row() -> None:
            _add_row()
            table.setCurrentCell(table.rowCount() - 1, 0)

        def _remove_selected_rows() -> None:
            rows = sorted({idx.row() for idx in table.selectedIndexes()}, reverse=True)
            for row in rows:
                if row == 0:
                    continue
                table.removeRow(row)

        rates = self.costs_presenter.get_currency_rates()
        base_rate = next((r for r in rates if r.symbol == "$"), None)
        _add_row(base_rate, locked=True)
        for rate in rates:
            if rate.symbol == "$":
                continue
            _add_row(rate)

        buttons_row = QHBoxLayout()
        add_button = QPushButton("Agregar moneda")
        remove_button = QPushButton("Eliminar fila")
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(remove_button)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        add_button.clicked.connect(_add_empty_row)
        remove_button.clicked.connect(_remove_selected_rows)

        def _to_decimal(value: str) -> Decimal | None:
            return parse_user_number(value)

        def _collect_rates() -> List[CurrencyRate] | None:
            symbols: set[str] = set()
            collected: List[CurrencyRate] = []
            for row in range(table.rowCount()):
                name_item = table.item(row, 0)
                symbol_item = table.item(row, 1)
                rate_item = table.item(row, 2)
                name = (name_item.text() if name_item else "").strip()
                symbol = (symbol_item.text() if symbol_item else "").strip()
                rate_raw = rate_item.text() if rate_item else ""

                if row == 0:
                    name = "Moneda Nacional"
                    symbol = "$"
                    rate_val = Decimal("1")
                else:
                    if not name:
                        QMessageBox.warning(
                            self,
                            "Cotizaciones",
                            "Completa el nombre de la moneda.",
                        )
                        return None
                    if not symbol:
                        QMessageBox.warning(
                            self,
                            "Cotizaciones",
                            "Completa el simbolo de la moneda.",
                        )
                        return None
                    rate_val = _to_decimal(rate_raw)
                    if rate_val is None or rate_val <= 0:
                        QMessageBox.warning(
                            self,
                            "Cotizaciones",
                            "La cotizacion debe ser mayor a 0.",
                        )
                        return None

                if symbol in symbols:
                    QMessageBox.warning(
                        self,
                        "Cotizaciones",
                        f"El simbolo '{symbol}' esta repetido.",
                    )
                    return None
                symbols.add(symbol)
                collected.append(
                    CurrencyRate(name=name, symbol=symbol, rate_to_mn=rate_val)
                )
            return collected

        while True:
            if dialog.exec() != QDialog.Accepted:
                return None
            rates = _collect_rates()
            if rates is not None:
                return rates

    def _prompt_process_dialog(self, process: ProcessCost | None = None) -> ProcessCost | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Proceso")
        layout = QVBoxLayout(dialog)

        form = QFormLayout()
        name_input = QLineEdit(dialog)
        type_combo = QComboBox(dialog)
        type_combo.addItems(["Tiempo fijo", "Tiempo variable", "Hibrido"])
        cost_input = UserNumberSpinBox(dialog)
        cost_input.setDecimals(3)
        cost_input.setRange(0.0, 1_000_000.0)

        notes_input = QPlainTextEdit(dialog)
        notes_input.setPlaceholderText("Notas (opcional)")
        notes_input.setFixedHeight(60)

        form.addRow("Nombre:", name_input)
        form.addRow("Tipo:", type_combo)
        form.addRow("Costo/h:", cost_input)
        layout.addLayout(form)

        fixed_time_value = UserNumberSpinBox(dialog)
        fixed_time_value.setDecimals(3)
        fixed_time_value.setRange(0.0, 1_000_000.0)
        fixed_time_unit = QComboBox(dialog)
        fixed_time_unit.addItems(["min", "h"])

        setup_time_value = UserNumberSpinBox(dialog)
        setup_time_value.setDecimals(3)
        setup_time_value.setRange(0.0, 1_000_000.0)
        setup_time_unit = QComboBox(dialog)
        setup_time_unit.addItems(["min", "h"])

        time_per_kg_value = UserNumberSpinBox(dialog)
        time_per_kg_value.setDecimals(3)
        time_per_kg_value.setRange(0.0, 1_000_000.0)
        time_per_kg_unit = QComboBox(dialog)
        time_per_kg_unit.addItems(["min", "h"])

        def _time_row(
            value_widget: UserNumberSpinBox, unit_widget: QComboBox, suffix: str = ""
        ) -> QWidget:
            row_widget = QWidget(dialog)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(value_widget)
            row_layout.addWidget(unit_widget)
            if suffix:
                row_layout.addWidget(QLabel(suffix))
            row_layout.addStretch()
            return row_widget

        fixed_row = _time_row(fixed_time_value, fixed_time_unit)
        setup_row = _time_row(setup_time_value, setup_time_unit)
        per_kg_row = _time_row(time_per_kg_value, time_per_kg_unit, "/kg")

        fixed_label = QLabel("Tiempo:")
        setup_label = QLabel("Tiempo fijo:")
        per_kg_label = QLabel("Tiempo/kg:")
        form.addRow(fixed_label, fixed_row)
        form.addRow(setup_label, setup_row)
        form.addRow(per_kg_label, per_kg_row)

        layout.addWidget(notes_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog
        )
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        type_map = {
            "Tiempo fijo": "FIXED",
            "Tiempo variable": "VARIABLE_PER_KG",
            "Hibrido": "MIXED",
        }

        if process is not None:
            name_input.setText(process.name or "")
            scale_type = (process.scale_type or "FIXED").strip().upper()
            if scale_type == "VARIABLE_PER_KG":
                type_combo.setCurrentText("Tiempo variable")
            elif scale_type == "MIXED":
                type_combo.setCurrentText("Hibrido")
            else:
                type_combo.setCurrentText("Tiempo fijo")

            if process.cost_per_hour_mn is not None:
                cost_input.setValue(float(process.cost_per_hour_mn))
            if process.time_value is not None:
                fixed_time_value.setValue(float(process.time_value))
            if process.time_unit:
                fixed_time_unit.setCurrentText(process.time_unit)
                time_per_kg_unit.setCurrentText(process.time_unit)
            if process.setup_time_value is not None:
                setup_time_value.setValue(float(process.setup_time_value))
            if process.setup_time_unit:
                setup_time_unit.setCurrentText(process.setup_time_unit)
            if process.time_per_kg_value is not None:
                time_per_kg_value.setValue(float(process.time_per_kg_value))
            if process.notes:
                notes_input.setPlainText(process.notes)

        def _toggle_fields() -> None:
            selected = type_combo.currentText()
            show_fixed = selected == "Tiempo fijo"
            show_setup = selected == "Hibrido"
            show_per_kg = selected in {"Tiempo variable", "Hibrido"}
            fixed_row.setVisible(show_fixed)
            fixed_label.setVisible(show_fixed)
            setup_row.setVisible(show_setup)
            setup_label.setVisible(show_setup)
            per_kg_row.setVisible(show_per_kg)
            per_kg_label.setVisible(show_per_kg)

        type_combo.currentTextChanged.connect(lambda _text: _toggle_fields())
        _toggle_fields()

        def _to_hours(value: Decimal, unit: str) -> Decimal | None:
            if value <= 0:
                return None
            if unit == "h":
                return value
            if unit == "min":
                return value / Decimal("60")
            return None

        while True:
            if dialog.exec() != QDialog.Accepted:
                return None
            name = name_input.text().strip()
            if not name:
                QMessageBox.warning(self, "Proceso", "Ingresa un nombre.")
                continue

            cost_h = Decimal(str(cost_input.value()))
            if cost_h <= 0:
                QMessageBox.warning(self, "Proceso", "El costo por hora debe ser mayor a 0.")
                continue

            scale_key = type_map.get(type_combo.currentText(), "FIXED")

            time_value = None
            time_unit = None
            setup_value = None
            setup_unit = None
            time_per_kg = None

            if scale_key == "FIXED":
                time_value = Decimal(str(fixed_time_value.value()))
                time_unit = fixed_time_unit.currentText()
                if time_value <= 0:
                    QMessageBox.warning(self, "Proceso", "El tiempo debe ser mayor a 0.")
                    continue
            elif scale_key == "VARIABLE_PER_KG":
                time_per_kg = Decimal(str(time_per_kg_value.value()))
                time_unit = time_per_kg_unit.currentText()
                if time_per_kg <= 0:
                    QMessageBox.warning(self, "Proceso", "El tiempo por kg debe ser mayor a 0.")
                    continue
            elif scale_key == "MIXED":
                setup_value = Decimal(str(setup_time_value.value()))
                setup_unit = setup_time_unit.currentText()
                time_per_kg = Decimal(str(time_per_kg_value.value()))
                time_unit = time_per_kg_unit.currentText()
                if time_per_kg <= 0:
                    QMessageBox.warning(self, "Proceso", "El tiempo por kg debe ser mayor a 0.")
                    continue

            batch_mass_kg = self.costs_presenter.formulation.total_weight / Decimal("1000")
            time_total_h = None
            if scale_key == "FIXED" and time_value is not None and time_unit is not None:
                time_total_h = _to_hours(time_value, time_unit)
            elif scale_key == "VARIABLE_PER_KG" and time_per_kg is not None and time_unit is not None:
                per_kg_h = _to_hours(time_per_kg, time_unit)
                if per_kg_h is not None:
                    time_total_h = per_kg_h * batch_mass_kg
            elif scale_key == "MIXED" and time_per_kg is not None and time_unit is not None:
                setup_h = Decimal("0")
                if setup_value is not None and setup_value > 0:
                    setup_h = _to_hours(setup_value, setup_unit or "min") or Decimal("0")
                per_kg_h = _to_hours(time_per_kg, time_unit)
                if per_kg_h is not None:
                    time_total_h = setup_h + (per_kg_h * batch_mass_kg)

            total_cost = time_total_h * cost_h if time_total_h is not None else None

            return ProcessCost(
                name=name,
                scale_type=scale_key,
                time_value=time_value,
                time_unit=time_unit,
                setup_time_value=setup_value,
                setup_time_unit=setup_unit,
                time_per_kg_value=time_per_kg,
                cost_per_hour_mn=cost_h,
                total_cost_mn=total_cost,
                notes=notes_input.toPlainText().strip() or None,
            )

    def _populate_ingredients_costs_table(self) -> None:
        rows = self.costs_presenter.build_ingredient_rows(self.quantity_mode)
        table = self.costs_ingredients_table
        symbols = self.costs_presenter.get_currency_symbols()
        rate_map = cost_service.build_rate_map(self.costs_presenter.formulation.currency_rates)
        table.blockSignals(True)
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            name_item = self._make_readonly_item(
                row["description"], sort_key=sort_key_text(row["description"])
            )
            self._set_row_index(name_item, row["index"])
            table.setItem(
                row_idx,
                self._ingredient_cost_columns["ingredient"],
                name_item,
            )
            amount_text = self._format_mass(row["amount_g"], row["unit"])
            amount_key = sort_key_numeric(row.get("amount_display"))
            table.setItem(
                row_idx,
                self._ingredient_cost_columns["amount"],
                self._make_numeric_item(amount_text, sort_key=amount_key),
            )

            pack_amount = "" if row["cost_pack_amount"] is None else fmt_decimal(row["cost_pack_amount"], decimals=3)
            present_grams = None
            if row["cost_pack_amount"] is not None and row.get("cost_pack_unit"):
                present_grams = convert_mass(row["cost_pack_amount"], row["cost_pack_unit"], "g")
            present_key = sort_key_numeric(present_grams)
            table.setItem(
                row_idx,
                self._ingredient_cost_columns["pack_amount"],
                self._make_numeric_item(pack_amount, readonly=False, sort_key=present_key),
            )
            table.setItem(
                row_idx,
                self._ingredient_cost_columns["pack_unit"],
                self._make_readonly_item("", sort_key=present_key),
            )

            unit_combo = NoWheelComboBox(table)
            unit_combo.addItems(["g", "kg", "lb", "oz", "ton"])
            unit_combo.setCurrentText(row["cost_pack_unit"] or "g")
            unit_combo.setProperty("index", row["index"])
            unit_combo.currentTextChanged.connect(self._on_ingredient_unit_changed)
            table.setCellWidget(row_idx, self._ingredient_cost_columns["pack_unit"], unit_combo)

            currency_combo = NoWheelComboBox(table)
            currency_combo.addItems(symbols)
            currency_combo.setCurrentText(row["cost_currency_symbol"] or "$")
            currency_combo.setProperty("index", row["index"])
            currency_combo.currentTextChanged.connect(self._on_ingredient_currency_changed)
            table.setCellWidget(row_idx, self._ingredient_cost_columns["currency"], currency_combo)
            cost_value = "" if row["cost_value"] is None else fmt_decimal(row["cost_value"], decimals=3)
            cost_mn = None
            if not row.get("currency_missing"):
                rate = rate_map.get(row["cost_currency_symbol"] or "")
                if row["cost_value"] is not None and rate is not None:
                    cost_mn = row["cost_value"] * rate
            cost_key = sort_key_numeric(cost_mn)
            table.setItem(
                row_idx,
                self._ingredient_cost_columns["currency"],
                self._make_readonly_item("", sort_key=cost_key),
            )

            table.setItem(
                row_idx,
                self._ingredient_cost_columns["cost_value"],
                self._make_numeric_item(cost_value, readonly=False, sort_key=cost_key),
            )

            unit_cost_text = "-"
            unit_cost_tooltip = ""
            if row["cost_per_g_mn"] is not None:
                per_kg = row["cost_per_g_mn"] * Decimal("1000")
                unit_cost_text = fmt_decimal(per_kg, decimals=4)
                unit_cost_tooltip = fmt_decimal(per_kg, decimals=8)
            unit_cost_item = self._make_numeric_item(
                unit_cost_text,
                sort_key=sort_key_numeric(
                    row["cost_per_g_mn"] * Decimal("1000")
                    if row["cost_per_g_mn"] is not None
                    else None
                ),
            )
            if unit_cost_tooltip:
                unit_cost_item.setToolTip(unit_cost_tooltip)
            table.setItem(
                row_idx,
                self._ingredient_cost_columns["unit_cost"],
                unit_cost_item,
            )
            batch_cost_text = (
                self._format_money(row["cost_batch_mn"]) if row["cost_batch_mn"] is not None else "-"
            )
            table.setItem(
                row_idx,
                self._ingredient_cost_columns["batch_cost"],
                self._make_numeric_item(
                    batch_cost_text,
                    sort_key=sort_key_numeric(row["cost_batch_mn"]),
                ),
            )
            table.setItem(
                row_idx,
                self._ingredient_cost_columns["percent"],
                self._make_numeric_item(
                    self._format_percent(row["percent_of_ingredients"]),
                    sort_key=sort_key_numeric(row["percent_of_ingredients"]),
                ),
            )

            if row["cost_per_g_mn"] is None:
                for col in (
                    self._ingredient_cost_columns["pack_amount"],
                    self._ingredient_cost_columns["cost_value"],
                ):
                    item = table.item(row_idx, col)
                    if item:
                        item.setBackground(Qt.yellow)
            if row.get("currency_missing"):
                currency_combo.setStyleSheet("background-color: #fff2cc;")
        table.blockSignals(False)
        table.setSortingEnabled(True)

    def _on_ingredient_unit_changed(self, _text: str) -> None:
        if self._costs_block_signals:
            return
        combo = self.sender()
        if isinstance(combo, QComboBox):
            index = combo.property("index")
            if index is not None:
                row = self._find_row_for_index(self.costs_ingredients_table, int(index))
                if row is not None:
                    self._update_ingredient_from_row(row)

    def _on_ingredient_currency_changed(self, _text: str) -> None:
        if self._costs_block_signals:
            return
        combo = self.sender()
        if isinstance(combo, QComboBox):
            index = combo.property("index")
            if index is not None:
                row = self._find_row_for_index(self.costs_ingredients_table, int(index))
                if row is not None:
                    self._update_ingredient_from_row(row)

    def _on_ingredient_cost_item_changed(self, item: QTableWidgetItem) -> None:
        if self._costs_block_signals:
            return
        if item.column() in (
            self._ingredient_cost_columns["pack_amount"],
            self._ingredient_cost_columns["cost_value"],
        ):
            self._update_ingredient_from_row(item.row())

    def _update_ingredient_from_row(self, row: int) -> None:
        table = self.costs_ingredients_table
        actual_index = self._get_row_index(table, row)
        if actual_index is None:
            return
        pack_amount_item = table.item(row, self._ingredient_cost_columns["pack_amount"])
        cost_value_item = table.item(row, self._ingredient_cost_columns["cost_value"])
        unit_combo = table.cellWidget(row, self._ingredient_cost_columns["pack_unit"])
        currency_combo = table.cellWidget(row, self._ingredient_cost_columns["currency"])

        pack_unit = unit_combo.currentText() if isinstance(unit_combo, QComboBox) else "g"
        currency = currency_combo.currentText() if isinstance(currency_combo, QComboBox) else "$"

        self.costs_presenter.update_ingredient_cost(
            actual_index,
            cost_pack_amount=pack_amount_item.text() if pack_amount_item else None,
            cost_pack_unit=pack_unit,
            cost_value=cost_value_item.text() if cost_value_item else None,
            cost_currency_symbol=currency,
        )
        self._refresh_costs_view()

    def _populate_processes_table(self) -> None:
        rows = self.costs_presenter.build_process_rows()
        table = self.costs_process_table
        table.blockSignals(True)
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            name_item = self._make_readonly_item(
                row["name"] or "", sort_key=sort_key_text(row["name"])
            )
            self._set_row_index(name_item, row["index"])
            table.setItem(
                row_idx,
                self._process_columns["name"],
                name_item,
            )
            time_text = self._format_time_total(row["time_total_h"])
            table.setItem(
                row_idx,
                self._process_columns["time_total"],
                self._make_numeric_item(
                    time_text, sort_key=sort_key_numeric(row["time_total_h"])
                ),
            )
            total_text = (
                self._format_money(row["total_cost_mn"])
                if row["total_cost_mn"] is not None
                else "-"
            )
            table.setItem(
                row_idx,
                self._process_columns["total_cost"],
                self._make_numeric_item(
                    total_text, sort_key=sort_key_numeric(row["total_cost_mn"])
                ),
            )
            delete_button = self._make_delete_button()
            delete_button.clicked.connect(
                lambda _checked=False, index=row["index"]: self._remove_process_at(index)
            )
            table.setCellWidget(row_idx, self._process_columns["delete"], delete_button)

        table.blockSignals(False)
        table.setSortingEnabled(True)
        if rows:
            self.costs_process_stack.setCurrentIndex(0)
        else:
            self.costs_process_stack.setCurrentIndex(1)

    def _on_add_process_clicked(self) -> None:
        process = self._prompt_process_dialog()
        if process is None:
            return
        self.costs_presenter.formulation.process_costs.append(process)
        self._refresh_costs_view()

    def _on_process_double_clicked(self, item: QTableWidgetItem) -> None:
        self._edit_process_row(item.row())

    def _edit_process_row(self, row: int) -> None:
        actual_index = self._get_row_index(self.costs_process_table, row)
        if actual_index is None:
            return
        if actual_index < 0 or actual_index >= len(self.costs_presenter.formulation.process_costs):
            return
        current = self.costs_presenter.formulation.process_costs[actual_index]
        updated = self._prompt_process_dialog(current)
        if updated is None:
            return
        self.costs_presenter.update_process(
            actual_index,
            name=updated.name,
            scale_type=updated.scale_type,
            setup_time_value=updated.setup_time_value,
            setup_time_unit=updated.setup_time_unit,
            time_per_kg_value=updated.time_per_kg_value,
            time_unit=updated.time_unit,
            time_value=updated.time_value,
            cost_per_hour_mn=updated.cost_per_hour_mn,
            total_cost_mn=updated.total_cost_mn,
            notes=updated.notes,
        )
        self._refresh_costs_view()

    def _remove_process_at(self, index: int) -> None:
        self.costs_presenter.remove_process(index)
        self._refresh_costs_view()

    def _populate_packaging_table(self) -> None:
        rows = self.costs_presenter.build_packaging_rows()
        table = self.costs_packaging_table
        symbols = self.costs_presenter.get_currency_symbols()
        table.blockSignals(True)
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            name_item = self._make_readonly_item(
                row["name"] or "", sort_key=sort_key_text(row["name"])
            )
            self._set_row_index(name_item, row["index"])
            table.setItem(row_idx, self._packaging_columns["name"], name_item)
            qty = (
                fmt_decimal(row["quantity_per_pack"], decimals=3)
                if row["quantity_per_pack"] is not None
                else ""
            )
            table.setItem(
                row_idx,
                self._packaging_columns["qty"],
                self._make_numeric_item(
                    qty,
                    readonly=False,
                    sort_key=sort_key_numeric(row["quantity_per_pack"]),
                ),
            )
            currency_combo = NoWheelComboBox(table)
            currency_combo.addItems(symbols)
            currency_combo.setCurrentText(row.get("currency_symbol") or "$")
            currency_combo.setProperty("index", row["index"])
            currency_combo.currentTextChanged.connect(self._on_packaging_currency_changed)
            table.setCellWidget(row_idx, self._packaging_columns["currency"], currency_combo)
            unit_cost_key = sort_key_numeric(
                None if row.get("currency_missing") else row.get("unit_cost_mn")
            )
            table.setItem(
                row_idx,
                self._packaging_columns["currency"],
                self._make_readonly_item("", sort_key=unit_cost_key),
            )
            unit_cost = (
                fmt_decimal(row["unit_cost_value"], decimals=3)
                if row.get("unit_cost_value") is not None
                else ""
            )
            table.setItem(
                row_idx,
                self._packaging_columns["unit_cost"],
                self._make_numeric_item(unit_cost, readonly=False, sort_key=unit_cost_key),
            )
            subtotal = self._format_money(row["subtotal_mn"]) if row["subtotal_mn"] is not None else "-"
            table.setItem(
                row_idx,
                self._packaging_columns["subtotal"],
                self._make_numeric_item(
                    subtotal, sort_key=sort_key_numeric(row["subtotal_mn"])
                ),
            )
            delete_button = self._make_delete_button()
            delete_button.clicked.connect(
                lambda _checked=False, index=row["index"]: self._remove_packaging_at(index)
            )
            table.setCellWidget(row_idx, self._packaging_columns["delete"], delete_button)
            if row.get("currency_missing"):
                currency_combo.setStyleSheet("background-color: #fff2cc;")
        table.blockSignals(False)
        table.setSortingEnabled(True)
        if rows:
            self.costs_packaging_stack.setCurrentIndex(0)
        else:
            self.costs_packaging_stack.setCurrentIndex(1)

    def _on_packaging_item_changed(self, item: QTableWidgetItem) -> None:
        if self._costs_block_signals:
            return
        if item.column() in (
            self._packaging_columns["name"],
            self._packaging_columns["qty"],
            self._packaging_columns["unit_cost"],
        ):
            self._update_packaging_from_row(item.row())

    def _on_packaging_currency_changed(self, _text: str) -> None:
        if self._costs_block_signals:
            return
        combo = self.sender()
        if isinstance(combo, QComboBox):
            index = combo.property("index")
            if index is not None:
                row = self._find_row_for_index(self.costs_packaging_table, int(index))
                if row is not None:
                    self._update_packaging_from_row(row)

    def _update_packaging_from_row(self, row: int) -> None:
        table = self.costs_packaging_table
        actual_index = self._get_row_index(table, row)
        if actual_index is None:
            return
        name_item = table.item(row, self._packaging_columns["name"])
        qty_item = table.item(row, self._packaging_columns["qty"])
        unit_cost_item = table.item(row, self._packaging_columns["unit_cost"])
        currency_combo = table.cellWidget(row, self._packaging_columns["currency"])
        currency_symbol = "$"
        if isinstance(currency_combo, QComboBox):
            currency_symbol = currency_combo.currentText()
        self.costs_presenter.update_packaging_item(
            actual_index,
            name=name_item.text() if name_item else "",
            quantity_per_pack=qty_item.text() if qty_item else None,
            unit_cost_value=unit_cost_item.text() if unit_cost_item else None,
            unit_cost_currency_symbol=currency_symbol,
        )
        self._refresh_costs_view()

    def _remove_packaging_at(self, index: int) -> None:
        self.costs_presenter.remove_packaging_item(index)
        self._refresh_costs_view()

    def _on_add_packaging_clicked(self) -> None:
        self.costs_presenter.add_packaging_item()
        self._refresh_costs_view()

    def _on_yield_changed(self, value: float) -> None:
        ok, error = self.costs_presenter.set_yield_percent(Decimal(str(value)))
        if not ok and error == "yield_range":
            QMessageBox.warning(self, "Yield", "El yield debe estar entre 0 y 100.")
        self._refresh_costs_view()

    def _update_costs_calculator(self) -> None:
        if not self._costs_block_signals:
            self._sync_target_mass_to_formulation()
        target_value = self.costs_target_mass_input.value()
        target_unit = self.costs_target_unit_selector.currentText()
        data = self.costs_presenter.unit_costs_for_target_mass(target_value, target_unit)
        ingredients_pack = data["ingredients_cost_per_target_mn"]
        process_pack = data["process_cost_per_target_mn"]
        packaging_pack = data["packaging_cost_per_pack_mn"]
        total_pack = data["total_pack_cost_mn"]

        self.costs_pack_total_label.setText(self._format_money(total_pack))
        units = data["units_count"]
        self.costs_units_count_label.setText(
            f"Packs por tirada: {fmt_decimal(units, decimals=2)}"
            if units
            else "Packs por tirada: -"
        )
        packaging_batch = packaging_pack * units if units and units > 0 else Decimal("0")
        total_packaged = self._costs_total_batch_mn + packaging_batch
        self.costs_total_packaged_label.setText(self._format_money(total_packaged))

        if total_pack and total_pack > 0:
            pct_ing = (ingredients_pack / total_pack) * Decimal("100")
            pct_proc = (process_pack / total_pack) * Decimal("100")
            pct_pack = (packaging_pack / total_pack) * Decimal("100")
            composition = (
                f"Ingredientes {fmt_decimal(pct_ing, decimals=0)}% "
                f"({self._format_money(ingredients_pack)}) | "
                f"Procesos {fmt_decimal(pct_proc, decimals=0)}% "
                f"({self._format_money(process_pack)}) | "
                f"Packaging {fmt_decimal(pct_pack, decimals=0)}% "
                f"({self._format_money(packaging_pack)})"
            )
        else:
            composition = "Ingredientes - | Procesos - | Packaging -"
        self.costs_pack_composition_label.setText(composition)
        self.costs_pack_bar.set_values(ingredients_pack, process_pack, packaging_pack)
        packaging_badge_value = (
            f"Unidad: {self._format_money(packaging_pack)} | "
            f"Tirada: {self._format_money(packaging_batch)}"
        )
        self.costs_packaging_total_badge.set_value(packaging_badge_value)

    def _sync_target_mass_inputs(self) -> None:
        formulation = self.costs_presenter.formulation
        value = formulation.cost_target_mass_value or Decimal("100")
        unit = formulation.cost_target_mass_unit or "g"
        if unit not in {"g", "kg", "lb", "oz", "ton"}:
            unit = "g"
        self.costs_target_mass_input.blockSignals(True)
        self.costs_target_mass_input.setValue(float(value))
        self.costs_target_mass_input.blockSignals(False)
        self.costs_target_unit_selector.blockSignals(True)
        self.costs_target_unit_selector.setCurrentText(unit)
        self.costs_target_unit_selector.blockSignals(False)

    def _sync_target_mass_to_formulation(self) -> None:
        formulation = self.costs_presenter.formulation
        value = Decimal(str(self.costs_target_mass_input.value()))
        unit = self.costs_target_unit_selector.currentText()
        formulation.cost_target_mass_value = value
        formulation.cost_target_mass_unit = unit

    def _paste_ingredients_table(self) -> None:
        table = self.costs_ingredients_table
        start = table.currentRow()
        if start < 0:
            return
        clipboard = QApplication.clipboard().text()
        if not clipboard:
            return
        rows = [line.split("\t") for line in clipboard.splitlines() if line.strip()]
        if not rows:
            return
        col_start = self._ingredient_cost_columns["pack_amount"]
        for r_idx, row_values in enumerate(rows):
            target_row = start + r_idx
            if target_row >= table.rowCount():
                break
            for c_idx, value in enumerate(row_values):
                target_col = col_start + c_idx
                if target_col >= table.columnCount():
                    break
                item = table.item(target_row, target_col)
                if item is None:
                    item = QTableWidgetItem("")
                    table.setItem(target_row, target_col, item)
                item.setText(value)
        self._refresh_costs_view()
