from typing import Any, Dict, List
from pathlib import Path
import json
import re
import unicodedata
import os

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot, QEvent, QItemSelectionModel, QCoreApplication
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QCheckBox,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QHeaderView,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Alignment

import logging

from services.usda_api import USDAApiError, get_food_details, search_foods, has_cached_food

logging.basicConfig(
    filename="app_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(threadName)s] %(levelname)s %(message)s",
)


class ApiWorker(QObject):
    """Run a callable in a background thread and emit results via signals."""

    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args) -> None:
        super().__init__()
        self.fn = fn
        self.args = args

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn(*self.args)
        except Exception as exc:  # noqa: BLE001 - surface any API/Value errors to UI
            self.error.emit(str(exc))
        else:
            self.finished.emit(result)


class ImportWorker(QObject):
    """Hydrate formulation items in a worker thread with retry + progress feedback."""

    progress = Signal(str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        items: list[Dict[str, Any]],
        max_attempts: int = 4,
        read_timeout: float = 8.0,
    ) -> None:
        super().__init__()
        self.items = items
        self.max_attempts = max_attempts
        self.read_timeout = read_timeout

    @Slot()
    def run(self) -> None:
        hydrated_payload: list[Dict[str, Any]] = []
        total = len(self.items)
        for idx, item in enumerate(self.items, start=1):
            try:
                fdc_id_int = int(item.get("fdc_id"))
            except Exception:
                self.error.emit("Uno de los ingredientes no tiene FDC ID valido.")
                return

            base_item = dict(item)
            base_item["fdc_id"] = fdc_id_int

            attempts = 0
            details: Dict[str, Any] | None = None
            while attempts < self.max_attempts:
                attempts += 1
                self.progress.emit(f"{idx}/{total} ID #{fdc_id_int}")
                try:
                    details = get_food_details(
                        fdc_id_int,
                        timeout=(3.05, self.read_timeout),
                        detail_format="full",
                    )
                    break
                except Exception as exc:  # noqa: BLE001 - bubble up the root error
                    if attempts < self.max_attempts:
                        self.progress.emit(
                            f"{idx}/{total} ID #{fdc_id_int} Failed - Retrying ({attempts}/{self.max_attempts})"
                        )
                        continue
                    self.progress.emit(f"{idx}/{total} ID #{fdc_id_int} Failed")
                    self.error.emit(
                        f"No se pudo cargar el FDC {fdc_id_int} tras {self.max_attempts} intentos: {exc}"
                    )
                    return

            hydrated_payload.append({"base": base_item, "details": details or {}})

        self.finished.emit(hydrated_payload)


class AddWorker(QObject):
    """Fetch a single ingredient with retries and progress feedback."""

    progress = Signal(str)
    finished = Signal(dict, str, float)
    error = Signal(str)

    def __init__(
        self,
        fdc_id: int,
        max_attempts: int,
        read_timeout: float,
        mode: str,
        value: float,
    ) -> None:
        super().__init__()
        self.fdc_id = fdc_id
        self.max_attempts = max_attempts
        self.read_timeout = read_timeout
        self.mode = mode
        self.value = value

    @Slot()
    def run(self) -> None:
        logging.debug(f"AddWorker start fdc_id={self.fdc_id} attempts={self.max_attempts}")
        attempts = 0
        while attempts < self.max_attempts:
            attempts += 1
            self.progress.emit(f"1/1 ID #{self.fdc_id}")
            try:
                logging.debug(
                    f"AddWorker attempt {attempts} fetching fdc_id={self.fdc_id} timeout={self.read_timeout}"
                )
                details = get_food_details(
                    self.fdc_id,
                    timeout=(3.05, max(self.read_timeout, 8.0)),
                    detail_format="abridged",
                )
                logging.debug(
                    f"AddWorker success fdc_id={self.fdc_id} nutrients={len(details.get('foodNutrients', []) or [])}"
                )
                self.finished.emit(details, self.mode, self.value)
                return
            except Exception as exc:  # noqa: BLE001 - show after retries
                logging.exception(f"AddWorker error fdc_id={self.fdc_id} attempt={attempts}: {exc}")
                if attempts < self.max_attempts:
                    self.progress.emit(
                        f"1/1 ID #{self.fdc_id} Failed - Retrying ({attempts}/{self.max_attempts})"
                    )
                    continue
                self.progress.emit(f"1/1 ID #{self.fdc_id} Failed")
                self.error.emit(
                    f"No se pudo cargar el FDC {self.fdc_id} tras {self.max_attempts} intentos: {exc}"
                )
                return


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.base_window_title = "Food Formulator - Proto"
        self.setWindowTitle(self.base_window_title)
        self.import_max_attempts = 4
        self.import_read_timeout = 8.0
        self.resize(900, 600)
        self._threads: list[QThread] = []
        self._workers: list[QObject] = []
        self._current_import_worker: ImportWorker | None = None
        self._current_add_worker: AddWorker | None = None
        self._prefetching_fdc_ids: set[int] = set()
        self.formulation_items: List[Dict] = []
        self.quantity_mode: str = "g"
        self.amount_g_column_index = 2
        self.percent_column_index = 3
        self.lock_column_index = 4
        self.nutrient_export_flags: Dict[str, bool] = {}
        self.last_path = self._load_last_path()
        self.search_page = 1
        self.search_page_size = 25
        self.search_fetch_page_size = 200
        self.search_max_pages = 5
        self.search_results: List[Dict[str, Any]] = []
        self.last_query = ""
        self.last_include_brands = False
        self._last_results_count = 0
        self.data_type_priority = {
            "Foundation": 0,
            "SR Legacy": 1,
            "Survey": 2,
            "Survey (FNDDS)": 2,
            "Experimental": 3,
            "Branded": 4,
        }
        self._reference_order_map: Dict[str, Dict[str, Any]] = {}

        self._build_ui()

    def _set_window_progress(self, progress: str | None = None) -> None:
        """Update the window title with progress info or reset it."""
        title = self.base_window_title
        if progress:
            title = f"{title} | {progress}"
        self.setWindowTitle(title)

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        self.search_tab = QWidget()
        self.formulation_tab = QWidget()
        self.tabs.addTab(self.search_tab, "Búsqueda")
        self.tabs.addTab(self.formulation_tab, "Formulación")

        main_layout.addWidget(self.tabs)

        self._build_search_tab_ui()
        self._build_formulation_tab_ui()

    def _build_search_tab_ui(self) -> None:
        layout = QVBoxLayout(self.search_tab)
        layout.setSpacing(6)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Buscar alimento (ej: apple, rice, cheese)..."
        )
        self.search_button = QPushButton("Buscar")

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

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

        # Tabla de resultados (arriba)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["FDC ID", "Descripción", "Marca / Origen", "Tipo de dato"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.details_table = QTableWidget(0, 3)
        self.details_table.setHorizontalHeaderLabels(
            ["Nutriente", "Cantidad", "Unidad"]
        )
        self.details_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.details_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.details_table.setSelectionMode(QTableWidget.NoSelection)
        self.details_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.details_table.horizontalHeader().setStretchLastSection(True)

        bottom_layout = QHBoxLayout()

        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("Ingredientes en formulación"))
        self.formulation_preview = QTableWidget(0, 2)
        self.formulation_preview.setHorizontalHeaderLabels(["FDC ID", "Ingrediente"])
        self.formulation_preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.formulation_preview.setSelectionBehavior(QTableWidget.SelectRows)
        self.formulation_preview.setSelectionMode(QTableWidget.SingleSelection)
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
        self._set_default_column_widths()

    def _build_formulation_tab_ui(self) -> None:
        layout = QVBoxLayout(self.formulation_tab)

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
        self.formulation_table.setSelectionMode(QTableWidget.SingleSelection)
        self.formulation_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.formulation_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.formulation_table)

        buttons_layout = QHBoxLayout()
        self.edit_quantity_button = QPushButton("Editar cantidad seleccionada")
        self.remove_formulation_button = QPushButton(
            "Eliminar ingrediente seleccionado"
        )
        buttons_layout.addWidget(self.edit_quantity_button)
        buttons_layout.addWidget(self.remove_formulation_button)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

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
        self.totals_table.setSelectionMode(QTableWidget.NoSelection)
        self.totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.totals_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.totals_table)

        export_buttons_layout = QHBoxLayout()
        self.toggle_export_button = QPushButton("Deseleccionar todos")
        self.export_excel_button = QPushButton("Exportar a Excel")
        export_buttons_layout.addStretch()
        export_buttons_layout.addWidget(self.toggle_export_button)
        export_buttons_layout.addWidget(self.export_excel_button)
        export_buttons_layout.addStretch()
        layout.addLayout(export_buttons_layout)

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
        self._set_default_column_widths(formulation=True)

    def _set_default_column_widths(self, formulation: bool = False) -> None:
        """
        Set sensible initial column widths while keeping them resizable.
        """
        if not formulation:
            for table in (
                self.table,
                self.details_table,
                self.formulation_preview,
            ):
                header = table.horizontalHeader()
                header.setSectionResizeMode(QHeaderView.Interactive)

            self.table.setColumnWidth(0, 75)   # FDC ID
            self.table.setColumnWidth(1, 340)  # Descripcion
            self.table.setColumnWidth(2, 200)  # Marca / Origen
            self.table.setColumnWidth(3, 120)  # Tipo de dato

            self.details_table.setColumnWidth(0, 200)  # Nutriente
            self.details_table.setColumnWidth(1, 90)   # Cantidad
            self.details_table.setColumnWidth(2, 70)   # Unidad

            self.formulation_preview.setColumnWidth(0, 70)  # FDC ID
            self.formulation_preview.setColumnWidth(1, 290)  # Ingrediente
            return

        for table in (self.formulation_table, self.totals_table):
            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Interactive)

        self.formulation_table.setColumnWidth(0, 75)   # FDC ID
        self.formulation_table.setColumnWidth(1, 330)  # Ingrediente
        self.formulation_table.setColumnWidth(2, 95)   # Cantidad (g)
        self.formulation_table.setColumnWidth(3, 85)   # Cantidad (%)
        self.formulation_table.setColumnWidth(4, 65)   # Fijar %
        self.formulation_table.setColumnWidth(5, 150)  # Marca / Origen

        self.totals_table.setColumnWidth(0, 210)  # Nutriente
        self.totals_table.setColumnWidth(1, 85)   # Total
        self.totals_table.setColumnWidth(2, 60)   # Unidad
        self.totals_table.setColumnWidth(3, 80)   # Exportar

    def on_search_clicked(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText("Ingresa un termino de busqueda.")
            return

        self.search_page = 1
        self.last_query = query
        self.last_include_brands = self.include_brands_checkbox.isChecked()
        self._start_search()

    def on_prev_page_clicked(self) -> None:
        if self.search_page <= 1:
            return
        self.search_page -= 1
        self._show_current_search_page()
        self._update_paging_buttons(len(self.search_results))

    def on_next_page_clicked(self) -> None:
        total = len(self.search_results)
        if self.search_page * self.search_page_size >= total:
            return
        self.search_page += 1
        self._show_current_search_page()
        self._update_paging_buttons(total)

    def on_include_brands_toggled(self) -> None:
        # Re-lanzar búsqueda con el filtro actualizado si ya hay texto
        if not self.search_input.text().strip():
            return
        self.search_page = 1
        self.last_query = self.search_input.text().strip()
        self.last_include_brands = self.include_brands_checkbox.isChecked()
        self._start_search()

    def _start_search(self) -> None:
        if not self.last_query:
            self.status_label.setText("Ingresa un termino de busqueda.")
            return

        self.search_button.setEnabled(False)
        self.prev_page_button.setEnabled(False)
        self.next_page_button.setEnabled(False)
        self.search_results = []
        self._last_results_count = 0
        self._populate_table([])  # clear while loading

        data_types = self._data_types_for_search()
        self.status_label.setText(
            f"Buscando en FoodData Central... (pagina {self.search_page})"
        )

        self._run_in_thread(
            fn=self._fetch_all_pages,
            args=(self.last_query, data_types),
            on_success=self._on_search_success,
            on_error=self._on_search_error,
        )

    def _data_types_for_search(self) -> List[str] | None:
        if self.last_include_brands:
            # None => sin filtro de tipos (trae todos)
            return None
        return ["Foundation", "SR Legacy"]

    def _fetch_all_pages(self, query: str, data_types: List[str] | None) -> List[Dict[str, Any]]:
        all_results: List[Dict[str, Any]] = []
        page = 1
        while page <= self.search_max_pages:
            batch = search_foods(
                query,
                page_size=self.search_fetch_page_size,
                data_types=data_types,
                page_number=page,
            )
            if not batch:
                break
            all_results.extend(batch)
            if len(batch) < self.search_fetch_page_size:
                break
            page += 1

        # Fallback: if no search results and the query looks like an FDC ID, try direct lookup.
        stripped = query.strip()
        if not all_results and stripped.isdigit():
            try:
                details = get_food_details(int(stripped), detail_format="abridged")
            except Exception:
                return all_results
            all_results.append(
                {
                    "fdcId": details.get("fdcId"),
                    "description": details.get("description", ""),
                    "brandOwner": details.get("brandOwner", "") or "",
                    "dataType": details.get("dataType", "") or "",
                }
            )
        return all_results

    def _sort_search_results(self, foods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def priority(data_type: str) -> int:
            return self.data_type_priority.get(
                data_type, self.data_type_priority.get(data_type.strip(), len(self.data_type_priority))
            )

        return sorted(
            foods,
            key=lambda f: (
                priority(f.get("dataType", "") or ""),
                (f.get("description", "") or "").lower(),
            ),
        )

    def _filter_results_by_query(self, foods: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        tokens = [t for t in query.lower().split() if t]
        if not tokens:
            return foods

        filtered: List[Dict[str, Any]] = []
        for f in foods:
            haystack = f"{f.get('description', '')} {f.get('brandOwner', '')} {f.get('fdcId', '')}".lower()
            if all(tok in haystack for tok in tokens):
                filtered.append(f)
        return filtered

    def _prefetch_fdc_id(self, fdc_id: Any) -> None:
        """Warm USDA cache for a given FDC ID in background (no UI impact)."""
        try:
            fdc_int = int(fdc_id)
        except Exception:
            return
        if fdc_int in self._prefetching_fdc_ids:
            return
        self._prefetching_fdc_ids.add(fdc_int)
        logging.debug(f"Prefetching fdc_id={fdc_int}")

        def _on_done(_: object) -> None:
            self._prefetching_fdc_ids.discard(fdc_int)
            logging.debug(f"Prefetch done fdc_id={fdc_int}")

        self._run_in_thread(
            fn=lambda fid=fdc_int: get_food_details(
                fid,
                timeout=(3.05, 6.0),
                detail_format="abridged",
            ),
            args=(),
            on_success=_on_done,
            on_error=_on_done,
        )

    def _show_current_search_page(self) -> None:
        start = (self.search_page - 1) * self.search_page_size
        end = start + self.search_page_size
        slice_results = self.search_results[start:end]
        self._populate_table(slice_results, base_index=start)
        self._prefetch_visible_results(slice_results)
        total_pages = max(1, (len(self.search_results) + self.search_page_size - 1) // self.search_page_size)
        self.status_label.setText(
            f"Se encontraron {len(self.search_results)} resultados (pagina {self.search_page}/{total_pages})."
        )

    def _prefetch_visible_results(self, foods, limit: int = 2) -> None:
        """Proactively fetch details for the first results on screen to warm the cache."""
        count = 0
        for food in foods:
            fdc_id = food.get("fdcId")
            if fdc_id is None:
                continue
            self._prefetch_fdc_id(fdc_id)
            count += 1
            if count >= limit:
                break

    def _update_paging_buttons(self, count: int) -> None:
        has_query = bool(self.last_query)
        self.prev_page_button.setEnabled(has_query and self.search_page > 1)
        self.next_page_button.setEnabled(
            has_query and (self.search_page * self.search_page_size < count)
        )

    def on_fdc_search_clicked(self) -> None:
        fdc_id_text = self.fdc_id_input.text().strip()
        if not fdc_id_text.isdigit():
            self.status_label.setText("Ingresa un FDC ID numérico.")
            return

        self.status_label.setText(f"Cargando detalles de {fdc_id_text}...")
        self.fdc_id_button.setEnabled(False)
        self._run_in_thread(
            fn=get_food_details,
            args=(int(fdc_id_text),),
            on_success=self._on_details_success,
            on_error=self._on_details_error,
        )

    def on_result_double_clicked(self, row: int, _: int) -> None:
        """Double click on a search row -> add to formulation with quantity."""
        logging.debug(f"UI double click row={row}")
        self._add_row_to_formulation(row)

    def on_search_selection_changed(self) -> None:
        """Prefetch details for the selected search result to speed up adding."""
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return
        row = indexes[0].row()
        fdc_item = self.table.item(row, 0)
        if not fdc_item:
            return
        fdc_id_text = fdc_item.text().strip()
        self._prefetch_fdc_id(fdc_id_text)

    def on_add_selected_clicked(self) -> None:
        self._add_row_to_formulation()

    def on_remove_preview_clicked(self) -> None:
        self._remove_selected_from_formulation(self.formulation_preview)

    def on_remove_formulation_clicked(self) -> None:
        self._remove_selected_from_formulation(self.formulation_table)

    def on_formulation_preview_double_clicked(self, row: int, column: int) -> None:
        """Allow quick edit from the preview table."""
        if not self._can_edit_column(column):
            return
        self._edit_quantity_for_row(row)

    def on_preview_selection_changed(self) -> None:
        """Update nutrients panel when preview selection changes."""
        self._show_nutrients_for_selected_preview()

    def on_formulation_cell_double_clicked(self, row: int, column: int) -> None:
        """Double click on formulation row -> edit its quantity."""
        if not self._can_edit_column(column):
            return
        self._edit_quantity_for_row(row)

    def on_lock_toggled_from_table(self, item: QTableWidgetItem) -> None:
        """Handle lock/unlock toggles coming from any formulation table."""
        if item.column() != self.lock_column_index:
            return
        if self.quantity_mode == "g":
            return
        table = item.tableWidget()
        if table not in (self.formulation_table, self.formulation_preview):
            return
        row = item.row()
        if row < 0 or row >= len(self.formulation_items):
            return

        desired_locked = item.checkState() == Qt.Checked
        if desired_locked and self._locked_count(exclude_row=row) >= len(
            self.formulation_items
        ) - 1:
            # Avoid all items locked: keep one free.
            table.blockSignals(True)
            item.setCheckState(Qt.Unchecked)
            table.blockSignals(False)
            self.status_label.setText("Debe quedar al menos un ingrediente sin fijar.")
            return

        self.formulation_items[row]["locked"] = desired_locked
        self._refresh_formulation_views()

    def on_edit_quantity_clicked(self) -> None:
        indexes = self.formulation_table.selectionModel().selectedRows()
        if not indexes:
            self.status_label.setText("Selecciona un ingrediente para editar.")
            return
        self._edit_quantity_for_row(indexes[0].row())

    def on_quantity_mode_changed(self) -> None:
        """Switch between grams and percent modes for quantities."""
        self.quantity_mode = "g" if self.quantity_mode_selector.currentIndex() == 0 else "%"
        self._refresh_formulation_views()
        mode_text = "gramos (g)" if self.quantity_mode == "g" else "porcentaje (%)"
        self.status_label.setText(f"Modo de cantidad cambiado a {mode_text}.")

    def on_export_to_excel_clicked(self) -> None:
        """Export current formulation and totals to an Excel file."""
        if not self.formulation_items:
            QMessageBox.information(
                self,
                "Exportar a Excel",
                "No hay ingredientes en la formulacion para exportar.",
            )
            return

        default_name = f"{self._safe_base_name()}.xlsx"
        initial_path = (
            str(Path(self.last_path or "").with_name(default_name))
            if self.last_path
            else default_name
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar formulacion a Excel",
            initial_path,
            "Archivos de Excel (*.xlsx)",
        )
        if not path:
            return

        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        self._save_last_path(path)
        try:
            self._export_formulation_to_excel(path)
        except Exception as exc:  # noqa: BLE001 - surface the error to the user
            QMessageBox.critical(
                self,
                "Error al exportar",
                f"No se pudo exportar el archivo:\n{exc}",
            )
        else:
            QMessageBox.information(
                self,
                "Exportado",
                f"Archivo guardado en:\n{path}",
            )

    def on_export_state_clicked(self) -> None:
        """Export formulation state (ingredientes + cantidades + flags) a JSON."""
        if not self.formulation_items:
            QMessageBox.information(
                self,
                "Exportar formulación",
                "No hay ingredientes en la formulación para exportar.",
            )
            return

        default_name = f"{self._safe_base_name()}.json"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar formulación",
            str(Path(self.last_path or "").with_name(default_name)) if self.last_path else default_name,
            "Archivos JSON (*.json)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"

        self._save_last_path(path)
        payload_items: list[Dict[str, Any]] = []
        for item in self.formulation_items:
            payload_items.append(
                {
                    "fdc_id": item.get("fdc_id"),
                    "description": item.get("description", ""),
                    "brand": item.get("brand", ""),
                    "data_type": item.get("data_type", ""),
                    "amount_g": float(item.get("amount_g", 0.0) or 0.0),
                    "locked": bool(item.get("locked", False)),
                }
            )

        payload = {
            "quantity_mode": self.quantity_mode,
            "items": payload_items,
            "nutrient_export_flags": self.nutrient_export_flags,
            "formula_name": self.formula_name_input.text(),
            "version": 2,
        }
        try:
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Error al exportar",
                f"No se pudo exportar la formulación:\n{exc}",
            )
            return

        self.status_label.setText(f"Formulación exportada en {path}")

    def on_import_state_clicked(self) -> None:
        """Import formulation state from JSON or Excel and refresh UI."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar formulación",
            self.last_path or "",
            "Archivos JSON (*.json);;Archivos Excel (*.xlsx)",
        )
        if not path:
            return
        self._save_last_path(path)

        ext = Path(path).suffix.lower()
        if ext == ".json":
            parsed = self._load_state_from_json(path)
        elif ext in (".xlsx", ".xls"):
            parsed = self._load_state_from_excel(path)
        else:
            QMessageBox.warning(
                self,
                "Formato no soportado",
                "Selecciona un archivo .json o .xlsx",
            )
            return

        if not parsed:
            return

        base_items, meta = parsed
        meta.setdefault("path", path)
        self._start_import_hydration(base_items, meta)

    def _load_state_from_json(self, path: str) -> tuple[list[Dict[str, Any]], Dict[str, Any]] | None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Error al importar",
                f"No se pudo leer el archivo:\n{exc}",
            )
            return None

        if not isinstance(data, dict):
            QMessageBox.warning(
                self,
                "Formato inválido",
                "El archivo no contiene una formulación válida.",
            )
            return None

        items = data.get("items") or []
        if not isinstance(items, list) or not items:
            QMessageBox.warning(
                self,
                "Formato inválido",
                "El archivo no contiene ingredientes válidos.",
            )
            return None

        base_items: list[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                fdc_int = int(item.get("fdc_id") or item.get("fdcId"))
            except Exception:
                QMessageBox.warning(
                    self,
                    "FDC ID inválido",
                    f"FDC ID no numérico: {item.get('fdc_id') or item.get('fdcId')}",
                )
                return None
            base_items.append(
                {
                    "fdc_id": fdc_int,
                    "amount_g": float(item.get("amount_g", 0.0) or 0.0),
                    "locked": bool(item.get("locked", False)),
                    "description": item.get("description", ""),
                    "brand": item.get("brand", ""),
                    "data_type": item.get("data_type", ""),
                }
            )

        flags = data.get("nutrient_export_flags")
        nutrient_flags = (
            {k: bool(v) for k, v in flags.items()} if isinstance(flags, dict) else {}
        )

        mode = data.get("quantity_mode", "g")
        quantity_mode = "g" if mode != "%" else "%"

        meta = {
            "nutrient_export_flags": nutrient_flags,
            "quantity_mode": quantity_mode,
            "formula_name": data.get("formula_name", ""),
            "path": path,
            "respect_existing_formula_name": False,
        }
        return base_items, meta

    def _load_state_from_excel(self, path: str) -> tuple[list[Dict[str, Any]], Dict[str, Any]] | None:
        def _read(sheet: str | int, header_row: int) -> pd.DataFrame:
            return pd.read_excel(path, sheet_name=sheet, header=header_row)

        df: pd.DataFrame | None = None
        # Prefer sheet "Ingredientes" with headers on second row (row index 1)
        for sheet in ("Ingredientes", 0):
            for header_row in (1, 0):
                try:
                    tmp = _read(sheet, header_row)
                    if not tmp.empty:
                        df = tmp
                        break
                except Exception:
                    continue
            if df is not None:
                break

        if df is None or df.empty:
            QMessageBox.warning(
                self,
                "Sin datos",
                "El archivo no tiene filas para importar.",
            )
            return None

        # Normalize columns for matching
        cols_norm: Dict[str, str] = {self._normalize_label(c): c for c in df.columns}
        fdc_candidates = [
            "fdc id",
            "fdc_id",
            "fdcid",
            "fdc",
        ]
        amount_candidates = [
            "cantidad (g)",
            "cantidad g",
            "cantidad",
            "cantidad gramos",
            "cantidad en gramos",
            "amount g",
            "amount_g",
            "g",
            "grams",
        ]

        fdc_col = next((cols_norm[c] for c in fdc_candidates if c in cols_norm), None)
        amount_col = next(
            (cols_norm[c] for c in amount_candidates if c in cols_norm), None
        )
        if not fdc_col or not amount_col:
            QMessageBox.warning(
                self,
                "Columnas faltantes",
                "Se requieren columnas FDC ID y Cantidad (g).",
            )
            return None

        base_items: list[Dict[str, Any]] = []
        for _, row in df.iterrows():
            fdc_val = row.get(fdc_col)
            amt_val = row.get(amount_col)
            if pd.isna(fdc_val):
                continue
            try:
                fdc_int = int(fdc_val)
            except Exception:
                continue
            try:
                amt = float(amt_val) if not pd.isna(amt_val) else 0.0
            except Exception:
                amt = 0.0
            base_items.append(
                {
                    "fdc_id": fdc_int,
                    "amount_g": amt,
                    "locked": False,
                }
            )

        if not base_items:
            QMessageBox.warning(
                self,
                "Sin ingredientes",
                "No se encontraron filas válidas con FDC ID y Cantidad (g).",
            )
            return None

        meta = {
            "nutrient_export_flags": {},
            "quantity_mode": "g",
            "formula_name": self.formula_name_input.text() or Path(path).stem,
            "path": path,
            "respect_existing_formula_name": True,
        }
        return base_items, meta

    def _start_import_hydration(
        self, base_items: list[Dict[str, Any]], meta: Dict[str, Any]
    ) -> None:
        if not base_items:
            QMessageBox.warning(
                self,
                "Sin ingredientes",
                "El archivo no contiene ingredientes para importar.",
            )
            return

        self.import_state_button.setEnabled(False)
        self.export_state_button.setEnabled(False)
        self.status_label.setText("Importando ingredientes...")
        self._set_window_progress("Importando ingredientes")

        thread = QThread(self)
        worker = ImportWorker(
            base_items,
            max_attempts=self.import_max_attempts,
            read_timeout=self.import_read_timeout,
        )
        worker.moveToThread(thread)
        self._workers.append(worker)
        self._threads.append(thread)
        self._current_import_worker = worker

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_import_progress)
        worker.finished.connect(lambda payload, m=meta: self._on_import_finished(payload, m))
        worker.error.connect(self._on_import_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        def _cleanup() -> None:
            if thread in self._threads:
                self._threads.remove(thread)
            if worker in self._workers:
                self._workers.remove(worker)
            if self._current_import_worker is worker:
                self._current_import_worker = None

        thread.finished.connect(_cleanup)
        thread.start()

    def _on_import_progress(self, message: str) -> None:
        self._set_window_progress(message)
        self.status_label.setText(f"Importando ingredientes: {message}")

    def _on_import_finished(self, payload: list[Dict[str, Any]], meta: Dict[str, Any]) -> None:
        self._reset_import_ui_state()
        hydrated: list[Dict[str, Any]] = []
        for entry in payload:
            base = entry.get("base") or {}
            details = entry.get("details") or {}
            fdc_id = base.get("fdc_id") or details.get("fdcId")
            try:
                fdc_id_int = int(fdc_id) if fdc_id is not None else None
            except Exception:
                fdc_id_int = fdc_id

            nutrients = self._augment_fat_nutrients(details.get("foodNutrients", []) or [])
            self._update_reference_from_details(details)
            hydrated.append(
                {
                    "fdc_id": fdc_id_int,
                    "description": details.get("description", "") or base.get("description", ""),
                    "brand": details.get("brandOwner", "") or base.get("brand", ""),
                    "data_type": details.get("dataType", "") or base.get("data_type", ""),
                    "amount_g": float(base.get("amount_g", 0.0) or 0.0),
                    "nutrients": nutrients,
                    "locked": bool(base.get("locked", False)),
                }
            )

        self.formulation_items = hydrated
        self.nutrient_export_flags = meta.get("nutrient_export_flags", {})
        mode = meta.get("quantity_mode", "g")
        self.quantity_mode = "g" if mode != "%" else "%"
        self.quantity_mode_selector.blockSignals(True)
        self.quantity_mode_selector.setCurrentIndex(
            0 if self.quantity_mode == "g" else 1
        )
        self.quantity_mode_selector.blockSignals(False)

        formula_name = meta.get("formula_name", "")
        respect_existing = meta.get("respect_existing_formula_name", False)
        if not respect_existing or not self.formula_name_input.text().strip():
            self.formula_name_input.setText(formula_name)

        self._refresh_formulation_views()
        source = meta.get("path", "archivo")
        self.status_label.setText(f"Formulación importada desde {source}")

    def _on_import_error(self, message: str) -> None:
        self._reset_import_ui_state()
        self.status_label.setText("Error al importar ingredientes.")
        QMessageBox.critical(self, "Error al cargar ingrediente", message)

    def _reset_import_ui_state(self) -> None:
        self.import_state_button.setEnabled(True)
        self.export_state_button.setEnabled(True)
        self._set_window_progress(None)
        self._current_import_worker = None

    def _populate_table(self, foods, base_index: int = 0) -> None:
        self.table.setRowCount(0)

        for row_idx, food in enumerate(foods):
            self.table.insertRow(row_idx)

            fdc_id = str(food.get("fdcId", ""))
            description = food.get("description", "") or ""
            brand = food.get("brandOwner", "") or ""
            data_type = food.get("dataType", "") or ""

            self.table.setItem(row_idx, 0, QTableWidgetItem(fdc_id))
            self.table.setItem(row_idx, 1, QTableWidgetItem(description))
            self.table.setItem(row_idx, 2, QTableWidgetItem(brand))
            self.table.setItem(row_idx, 3, QTableWidgetItem(data_type))
            self.table.setVerticalHeaderItem(
                row_idx, QTableWidgetItem(str(base_index + row_idx + 1))
            )

    def _populate_details_table(self, nutrients) -> None:
        nutrients = self._sort_nutrients_for_display(self._augment_fat_nutrients(nutrients or []))
        self.details_table.setRowCount(0)

        for row_idx, n in enumerate(nutrients):
            self.details_table.insertRow(row_idx)
            nut = n.get("nutrient") or {}
            name = nut.get("name", "") or ""
            unit = nut.get("unitName", "") or ""
            amount = n.get("amount")
            amount_text = "" if amount is None else str(amount)

            self.details_table.setItem(row_idx, 0, QTableWidgetItem(name))
            self.details_table.setItem(row_idx, 1, QTableWidgetItem(amount_text))
            self.details_table.setItem(row_idx, 2, QTableWidgetItem(unit))

    def _total_weight(self) -> float:
        """Total weight of current formulation in grams."""
        return sum((item.get("amount_g", 0) or 0) for item in self.formulation_items)

    def _locked_count(self, exclude_row: int | None = None) -> int:
        """How many items are locked, optionally ignoring one row."""
        count = 0
        for idx, item in enumerate(self.formulation_items):
            if exclude_row is not None and idx == exclude_row:
                continue
            if item.get("locked"):
                count += 1
        return count

    def _amount_to_percent(self, amount_g: float, total: float | None = None) -> float:
        total_weight = self._total_weight() if total is None else total
        if total_weight <= 0:
            return 0.0
        return (amount_g / total_weight) * 100.0

    def _update_quantity_headers(self) -> None:
        self.formulation_preview.setHorizontalHeaderLabels(
            ["FDC ID", "Ingrediente"]
        )
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

    def _set_item_enabled(self, item: QTableWidgetItem | None, enabled: bool) -> None:
        if item is None:
            return
        flags = item.flags()
        if enabled:
            flags |= Qt.ItemIsEnabled
        else:
            flags &= ~Qt.ItemIsEnabled
        item.setFlags(flags)
        item.setBackground(QColor("#f0f0f0") if not enabled else QColor("white"))

    def _apply_column_state(self, table: QTableWidget, row: int) -> None:
        grams_enabled = self.quantity_mode == "g"
        percent_enabled = self.quantity_mode == "%"

        self._set_item_enabled(
            table.item(row, self.amount_g_column_index), grams_enabled
        )
        self._set_item_enabled(
            table.item(row, self.percent_column_index), percent_enabled
        )
        self._set_item_enabled(
            table.item(row, self.lock_column_index), percent_enabled
        )

    def _can_edit_column(self, column: int | None) -> bool:
        if column is None:
            return True
        if self.quantity_mode == "g":
            return column == self.amount_g_column_index
        return column == self.percent_column_index

    def _nutrients_by_header(
        self, nutrients: List[Dict[str, Any]], header_by_key: Dict[str, str]
    ) -> Dict[str, float]:
        """
        Build a mapping of template header -> nutrient amount (per 100 g),
        aligned to a precomputed header key map to avoid duplicate columns.
        """
        out: Dict[str, float] = {}
        best_priority: Dict[str, int] = {}
        allowed_keys = set(header_by_key.keys())
        alias_priority = {
            "carbohydrate, by difference": 2,
            "carbohydrate, by summation": 1,
            "carbohydrate by summation": 1,
            "sugars, total": 2,
            "total sugars": 1,
        }

        for entry in nutrients:
            amount = entry.get("amount")
            if amount is None:
                continue
            nut = entry.get("nutrient") or {}
            header_key, name, unit = self._header_key(nut)
            if not header_key or header_key not in allowed_keys:
                continue
            header = header_by_key[header_key]
            priority = alias_priority.get((nut.get("name") or "").strip().lower(), 0)
            current_best = best_priority.get(header, -1)
            if priority < current_best:
                continue

            best_priority[header] = priority
            out[header] = amount

        return out

    def _collect_nutrient_columns(self) -> tuple[list[str], Dict[str, str], Dict[str, str]]:
        """
        Collect ordered nutrient headers and their categories.
        Category is taken from USDA "group" rows (amount/unit missing) when present.
        """
        candidates: Dict[str, Dict[str, Any]] = {}
        categories_seen_order: Dict[str, int] = {}
        preferred_order = [
            "Proximates",
            "Carbohydrates",
            "Minerals",
            "Vitamins and Other Components",
            "Lipids",
            "Amino acids",
        ]
        preferred_count = len(preferred_order)

        for item in self.formulation_items:
            current_category = "Nutrientes"
            if current_category not in categories_seen_order:
                categories_seen_order[current_category] = len(categories_seen_order)

            data_priority = self.data_type_priority.get(
                (item.get("data_type") or "").strip(), len(self.data_type_priority)
            )
            for entry in item.get("nutrients", []):
                nut = entry.get("nutrient") or {}
                amount = entry.get("amount")
                nut_key = self._nutrient_key(nut)
                if nut_key and not self.nutrient_export_flags.get(nut_key, True):
                    continue

                name = self._canonical_alias_name(nut.get("name", "") or "")
                unit = nut.get("unitName") or self._infer_unit(nut) or ""

                if amount is None and name:
                    current_category = name
                    if current_category not in categories_seen_order:
                        categories_seen_order[current_category] = len(
                            categories_seen_order
                        )
                    continue

                if amount is None:
                    continue

                header_key, canonical_name, canonical_unit = self._header_key(nut)
                if not header_key:
                    continue
                ref_info = self._reference_info(nut)
                category_hint = ref_info.get("category")
                if category_hint:
                    current_category = category_hint
                    if current_category not in categories_seen_order:
                        categories_seen_order[current_category] = len(
                            categories_seen_order
                        )
                header = (
                    f"{canonical_name} ({canonical_unit})"
                    if canonical_unit
                    else canonical_name
                )
                if not header:
                    continue

                order = self._nutrient_order(nut, len(candidates))
                existing = candidates.get(header_key)
                if existing is None or (
                    data_priority < existing["data_priority"]
                    or (
                        data_priority == existing["data_priority"]
                        and order < existing["order"]
                    )
                    or (
                        data_priority == existing["data_priority"]
                        and order == existing["order"]
                        and header < existing["header"]
                    )
                ):
                    candidates[header_key] = {
                        "header_key": header_key,
                        "header": header,
                        "category": current_category,
                        "order": order,
                        "data_priority": data_priority,
                    }

        # Flatten by preferred category order then any remaining categories
        def category_rank(cat: str) -> int:
            if cat in preferred_order:
                return preferred_order.index(cat)
            return preferred_count + categories_seen_order.get(cat, preferred_count)

        sorted_candidates = sorted(
            candidates.values(),
            key=lambda c: (
                category_rank(c["category"]),
                c["order"],
                c["header"].lower(),
            ),
        )

        ordered_headers: list[str] = [c["header"] for c in sorted_candidates]
        categories: Dict[str, str] = {c["header"]: c["category"] for c in sorted_candidates}
        header_key_map: Dict[str, str] = {c["header"]: c["header_key"] for c in sorted_candidates}

        return ordered_headers, categories, header_key_map

    def _augment_fat_nutrients(self, nutrients: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """
        Ensure Total lipid (fat) and Total fat (NLEA) mirror each other if one is missing.
        Insert the cloned entry next to its counterpart to preserve order/category.
        Ensures there is at most one entry for each of the two names.
        Returns a new list without mutating the original to avoid duplication on refresh.
        """
        if not nutrients:
            return []
        logging.debug(f"_augment_fat_nutrients input={len(nutrients)}")

        target_a = "total lipid (fat)"
        target_b = "total fat (nlea)"
        mapping = {
            target_a: ("Total fat (NLEA)", "298"),
            target_b: ("Total lipid (fat)", "204"),
        }

        def _norm_name(entry: Dict[str, Any]) -> str:
            nut = entry.get("nutrient") or {}
            return (nut.get("name") or "").strip().lower()

        first_lipid_idx = None
        first_nlea_idx = None
        lipid_amount = None
        nlea_amount = None
        lipid_entry = None
        nlea_entry = None
        filtered: list[Dict[str, Any]] = []

        for idx, entry in enumerate(nutrients):
            name = _norm_name(entry)
            if name == target_a:
                if first_lipid_idx is None:
                    first_lipid_idx = len(filtered)
                    lipid_amount = entry.get("amount")
                    lipid_entry = dict(entry)
                    # normalize key to name to merge originals/clones
                    lip_nut = dict(lipid_entry.get("nutrient") or {})
                    lip_nut.pop("id", None)
                    lip_nut.pop("number", None)
                    lipid_entry["nutrient"] = lip_nut
                continue  # skip for now to avoid duplicates
            if name == target_b:
                if first_nlea_idx is None:
                    first_nlea_idx = len(filtered)
                    nlea_amount = entry.get("amount")
                    nlea_entry = dict(entry)
                    # normalize key to name to merge originals/clones
                    nlea_nut = dict(nlea_entry.get("nutrient") or {})
                    nlea_nut.pop("id", None)
                    nlea_nut.pop("number", None)
                    nlea_entry["nutrient"] = nlea_nut
                continue
            filtered.append(entry)

        def _clone_with_name(source: Dict[str, Any], new_name: str, number: str) -> Dict[str, Any]:
            nut = dict(source.get("nutrient") or {})
            nut["name"] = new_name
            # Evitar colisiones en _nutrient_key: quitamos id/number y dejamos que use el nombre
            nut.pop("id", None)
            nut.pop("number", None)
            clone = dict(source)
            clone["nutrient"] = nut
            return clone

        # Build final list with controlled insertion
        result = list(filtered)

        # Decide amounts
        if lipid_amount is None and nlea_amount is None:
            return nutrients  # nothing to do

        if lipid_amount is None:
            # Only NLEA present: clone for lipid
            source = nlea_entry or {"nutrient": {"name": "Total fat (NLEA)"}}
            lipid_clone = _clone_with_name(source, *mapping[target_b])
            lipid_clone["amount"] = nlea_amount
            insert_at = first_nlea_idx if first_nlea_idx is not None else len(result)
            result.insert(insert_at, lipid_clone)
            # Insert original NLEA at same position (already removed)
            result.insert(insert_at + 1, nlea_entry)
            return result

        if nlea_amount is None:
            # Only lipid present: clone for NLEA
            source = lipid_entry or {"nutrient": {"name": "Total lipid (fat)"}}
            nlea_clone = _clone_with_name(source, *mapping[target_a])
            nlea_clone["amount"] = lipid_amount
            insert_at = first_lipid_idx if first_lipid_idx is not None else len(result)
            result.insert(insert_at, lipid_entry)
            result.insert(insert_at + 1, nlea_clone)
            return result

        # Both present: reinsert originals once, preserving relative order
        if first_lipid_idx is not None and first_nlea_idx is not None:
            insert_first = min(first_lipid_idx, first_nlea_idx)
            insert_second = max(first_lipid_idx, first_nlea_idx)
            first_entry = lipid_entry if first_lipid_idx < first_nlea_idx else nlea_entry
            second_entry = nlea_entry if first_entry is lipid_entry else lipid_entry
            result.insert(insert_first, first_entry)
            result.insert(insert_second, second_entry)
            return result

        return result

    def _augment_energy_nutrients(self, nutrients: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """
        Ensure Energy (kcal/kJ) exists using macros if missing; deduplicate extras.
        kcal = protein*4 + carbs*4 + fat*9 ; kJ = kcal*4.184
        """
        if not nutrients:
            return []

        def _norm_name(entry: Dict[str, Any]) -> str:
            nut = entry.get("nutrient") or {}
            return (nut.get("name") or "").strip().lower()

        def _clone_energy(unit: str, amount: float) -> Dict[str, Any]:
            nut = {"name": "Energy", "unitName": unit}
            return {"nutrient": nut, "amount": amount}

        result: list[Dict[str, Any]] = []
        kcal_entry = None
        kj_entry = None

        for entry in nutrients:
            name = _norm_name(entry)
            if name != "energy":
                result.append(entry)
                continue
            unit = (entry.get("nutrient") or {}).get("unitName", "").lower()
            if unit == "kcal" and kcal_entry is None:
                kcal_entry = dict(entry)
                kcal_entry.get("nutrient", {}).pop("id", None)
                kcal_entry.get("nutrient", {}).pop("number", None)
                result.append(kcal_entry)
            elif unit == "kj" and kj_entry is None:
                kj_entry = dict(entry)
                kj_entry.get("nutrient", {}).pop("id", None)
                kj_entry.get("nutrient", {}).pop("number", None)
                result.append(kj_entry)
            # drop duplicates silently

        # Gather macros from current list (which may already include fat clone)
        def _find_amount(names: list[str]) -> float | None:
            for entry in result:
                if _norm_name(entry) in names:
                    amt = entry.get("amount")
                    if amt is not None:
                        return float(amt)
            return None

        protein = _find_amount(["protein"])
        carbs = _find_amount(["carbohydrate, by difference"])
        fat = _find_amount(["total lipid (fat)", "total fat (nlea)"])

        if protein is None and carbs is None and fat is None:
            kcal_amount = None
        else:
            kcal_amount = (protein or 0.0) * 4.0 + (carbs or 0.0) * 4.0 + (fat or 0.0) * 9.0

        insert_pos = 0
        macro_indices = []
        for idx, entry in enumerate(result):
            if _norm_name(entry) in [
                "protein",
                "carbohydrate, by difference",
                "total lipid (fat)",
                "total fat (nlea)",
            ]:
                macro_indices.append(idx)
        if macro_indices:
            insert_pos = min(macro_indices)

        if kcal_entry is None and kcal_amount is not None:
            kcal_entry = _clone_energy("kcal", kcal_amount)
            result.insert(insert_pos, kcal_entry)

        if kj_entry is None and kcal_amount is not None:
            kj_entry = _clone_energy("kJ", kcal_amount * 4.184)
            # place kJ after kcal if inserted together
            insert_kj = insert_pos + 1 if kcal_entry in result else insert_pos
            result.insert(insert_kj, kj_entry)

        return result

    def _augment_pair(self, nutrients: list[Dict[str, Any]], target_a: str, target_b: str) -> list[Dict[str, Any]]:
        """Generic helper: ensure both targets exist, deduplicate, insert clone next to original."""
        if not nutrients:
            return []

        def _norm(entry: Dict[str, Any]) -> str:
            return (entry.get("nutrient", {}).get("name") or "").strip().lower()

        first_a_idx = None
        first_b_idx = None
        a_amt = None
        b_amt = None
        a_entry = None
        b_entry = None
        filtered: list[Dict[str, Any]] = []

        for entry in nutrients:
            name = _norm(entry)
            if name == target_a:
                if first_a_idx is None:
                    first_a_idx = len(filtered)
                    a_amt = entry.get("amount")
                    a_entry = dict(entry)
                    a_nut = dict(a_entry.get("nutrient") or {})
                    a_nut.pop("id", None)
                    a_nut.pop("number", None)
                    a_entry["nutrient"] = a_nut
                continue
            if name == target_b:
                if first_b_idx is None:
                    first_b_idx = len(filtered)
                    b_amt = entry.get("amount")
                    b_entry = dict(entry)
                    b_nut = dict(b_entry.get("nutrient") or {})
                    b_nut.pop("id", None)
                    b_nut.pop("number", None)
                    b_entry["nutrient"] = b_nut
                continue
            filtered.append(entry)

        def _clone(source: Dict[str, Any], new_name: str, amount: float | None) -> Dict[str, Any]:
            nut = dict(source.get("nutrient") or {})
            nut["name"] = new_name
            nut.pop("id", None)
            nut.pop("number", None)
            clone = dict(source)
            clone["nutrient"] = nut
            clone["amount"] = amount
            return clone

        result = list(filtered)

        if a_amt is None and b_amt is None:
            return nutrients

        if a_amt is None:
            # only B present
            a_clone = _clone(b_entry or {"nutrient": {"name": target_b}}, target_a, b_amt)
            insert_at = first_b_idx if first_b_idx is not None else len(result)
            result.insert(insert_at, a_clone)
            result.insert(insert_at + 1, b_entry)
            return result

        if b_amt is None:
            # only A present
            b_clone = _clone(a_entry or {"nutrient": {"name": target_a}}, target_b, a_amt)
            insert_at = first_a_idx if first_a_idx is not None else len(result)
            result.insert(insert_at, a_entry)
            result.insert(insert_at + 1, b_clone)
            return result

        # both present: reinsert once each preserving original order
        if first_a_idx is not None and first_b_idx is not None:
            insert_first = min(first_a_idx, first_b_idx)
            insert_second = max(first_a_idx, first_b_idx)
            first_entry = a_entry if first_a_idx < first_b_idx else b_entry
            second_entry = b_entry if first_entry is a_entry else a_entry
            result.insert(insert_first, first_entry)
            result.insert(insert_second, second_entry)
            return result

        return result

    def _augment_alias_nutrients(self, nutrients: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """Ensure paired aliases are both present (e.g., sugars total, carbs by diff/summation)."""
        pairs = [
            ("sugars, total", "total sugars"),
            ("carbohydrate, by difference", "carbohydrate, by summation"),
        ]
        augmented = nutrients or []
        for a, b in pairs:
            augmented = self._augment_pair(augmented, a, b)
        return augmented

    def _canonical_alias_name(self, name: str) -> str:
        """Return a display name for known aliases to keep one column in Excel."""
        lower = (name or "").strip().lower()
        mapping = {
            "sugars, total": "Sugars, Total",
            "total sugars": "Sugars, Total",
            "carbohydrate, by difference": "Carbohydrate, by difference",
            "carbohydrate, by summation": "Carbohydrate, by difference",
            "carbohydrate by summation": "Carbohydrate, by difference",
        }
        return mapping.get(lower, name)

    def _normalize_nutrients(self, nutrients: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """Apply all nutrient augmentation steps (fat + alias + energy) in order."""
        return self._augment_energy_nutrients(
            self._augment_alias_nutrients(self._augment_fat_nutrients(nutrients or []))
        )

    def _load_last_path(self) -> str:
        try:
            data = json.loads(Path("last_path.json").read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data.get("last_path", "")
        except Exception:
            return ""
        return ""

    def _save_last_path(self, path: str) -> None:
        try:
            Path("last_path.json").write_text(
                json.dumps({"last_path": str(Path(path).expanduser())}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.last_path = str(Path(path).expanduser())
        except Exception:
            pass

    def _ensure_normalized_items(self) -> None:
        """Normalize all formulation_items in-place (fat + energy)."""
        for idx, item in enumerate(self.formulation_items):
            original = item.get("nutrients", []) or []
            normalized = self._normalize_nutrients(original)
            if normalized != original:
                # preserve reference to allow downstream updates
                item["nutrients"] = normalized

    def _split_header_unit(self, header: str) -> tuple[str, str]:
        if header.endswith(")") and " (" in header:
            name, unit = header.rsplit(" (", 1)
            return name, unit[:-1]
        return header, ""

    def _hydrate_items(self, items: list[Dict[str, Any]]) -> list[Dict[str, Any]] | None:
        """Fetch USDA details for items to populate description/nutrients."""
        hydrated: list[Dict[str, Any]] = []
        total = len(items)
        for item in items:
            fdc_id = item.get("fdc_id") or item.get("fdcId")
            if fdc_id is None:
                QMessageBox.warning(
                    self,
                    "FDC ID faltante",
                    "Uno de los ingredientes no tiene FDC ID.",
                )
                return None
            try:
                fdc_id_int = int(fdc_id)
            except ValueError:
                QMessageBox.warning(
                    self,
                    "FDC ID inválido",
                    f"FDC ID no numérico: {fdc_id}",
                )
                return None

            self.status_label.setText(
                f"Importando ingrediente {len(hydrated)+1}/{total} (FDC {fdc_id_int})..."
            )
            QCoreApplication.processEvents()
            try:
                details = get_food_details(fdc_id_int)
            except Exception as exc:  # noqa: BLE001 - surface to user
                QMessageBox.critical(
                    self,
                    "Error al cargar ingrediente",
                    f"No se pudo cargar el FDC {fdc_id_int}:\n{exc}",
                )
                return None
            self._update_reference_from_details(details)

            hydrated.append(
                {
                    "fdc_id": fdc_id_int,
                    "description": details.get("description", "")
                    or item.get("description", ""),
                    "brand": details.get("brandOwner", "") or item.get("brand", ""),
                    "data_type": details.get("dataType", "") or item.get("data_type", ""),
                    "amount_g": float(item.get("amount_g", 0.0) or 0.0),
                    "nutrients": self._augment_fat_nutrients(
                        details.get("foodNutrients", []) or []
                    ),
                    "locked": bool(item.get("locked", False)),
                }
            )

        return hydrated

    def _normalize_label(self, label: str) -> str:
        """Normalize column labels for loose matching (casefold + strip accents)."""
        if label is None:
            return ""
        text = str(label)
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.replace("_", " ").replace("-", " ")
        return re.sub(r"\s+", " ", text).strip().lower()

    def _populate_formulation_tables(self) -> None:
        """Refresh formulation tables with current items."""
        logging.debug(f"_populate_formulation_tables rows={len(self.formulation_items)}")
        self._update_quantity_headers()
        total_weight = self._total_weight()

        # Left preview (ID + Ingrediente)
        self.formulation_preview.blockSignals(True)
        self.formulation_preview.setRowCount(len(self.formulation_items))
        for idx, item in enumerate(self.formulation_items):
            self.formulation_items[idx].setdefault("locked", False)
            self.formulation_preview.setItem(
                idx, 0, QTableWidgetItem(str(item.get("fdc_id", "")))
            )
            self.formulation_preview.setItem(
                idx, 1, QTableWidgetItem(item.get("description", ""))
            )
        self.formulation_preview.blockSignals(False)

        # Main formulation table
        self.formulation_table.blockSignals(True)
        self.formulation_table.setRowCount(len(self.formulation_items))
        for idx, item in enumerate(self.formulation_items):
            amount_g = float(item.get("amount_g", 0.0) or 0.0)
            percent = self._amount_to_percent(amount_g, total_weight)

            cells: list[QTableWidgetItem] = [
                QTableWidgetItem(str(item.get("fdc_id", ""))),
                QTableWidgetItem(item.get("description", "")),
                QTableWidgetItem(f"{amount_g:.1f}"),
                QTableWidgetItem(f"{percent:.2f}"),
            ]

            lock_item = QTableWidgetItem("")
            lock_item.setFlags(
                Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled
            )
            lock_item.setCheckState(
                Qt.Checked if item.get("locked") else Qt.Unchecked
            )
            cells.append(lock_item)

            cells.append(QTableWidgetItem(item.get("brand", "")))

            for col, cell in enumerate(cells):
                self.formulation_table.setItem(idx, col, cell)

            self._apply_column_state(self.formulation_table, idx)
        self.formulation_table.blockSignals(False)
        logging.debug("_populate_formulation_tables done")

    def _populate_totals_table(self) -> None:
        logging.debug("_populate_totals_table start")
        totals = self._calculate_totals()
        sorted_totals = sorted(
            totals.items(),
            key=lambda item: item[1].get("order", float("inf")),
        )

        self.totals_table.blockSignals(True)
        self.totals_table.setRowCount(len(sorted_totals))
        new_flags: Dict[str, bool] = {}

        for row_idx, (nut_key, entry) in enumerate(sorted_totals):
            name_item = QTableWidgetItem(entry["name"])
            name_item.setData(Qt.UserRole, nut_key)
            self.totals_table.setItem(row_idx, 0, name_item)

            self.totals_table.setItem(
                row_idx, 1, QTableWidgetItem(f"{entry['amount']:.2f}")
            )
            self.totals_table.setItem(row_idx, 2, QTableWidgetItem(entry["unit"]))

            export_item = QTableWidgetItem("")
            export_item.setFlags(
                Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            current_checked = self.nutrient_export_flags.get(nut_key, True)
            export_item.setCheckState(Qt.Checked if current_checked else Qt.Unchecked)
            export_item.setData(Qt.UserRole, nut_key)
            self.totals_table.setItem(row_idx, 3, export_item)
            new_flags[nut_key] = current_checked

        self.nutrient_export_flags = new_flags
        self.totals_table.blockSignals(False)
        self._update_toggle_export_button()
        logging.debug("_populate_totals_table done")

    def _update_toggle_export_button(self) -> None:
        if not hasattr(self, "toggle_export_button"):
            return
        all_checked = self.nutrient_export_flags and all(
            self.nutrient_export_flags.values()
        )
        text = "Deseleccionar todos" if all_checked else "Seleccionar todos"
        self.toggle_export_button.setText(text)

    def _create_question_icon(self) -> QIcon:
        """Create a small yellow square icon with a '?' centered."""
        size = 16
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(0, 0, size, size, QColor(255, 236, 179))
        painter.setPen(Qt.black)
        font: QFont = painter.font()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "?")
        painter.end()
        return QIcon(pixmap)

    def _refresh_formulation_views(self) -> None:
        logging.debug(f"_refresh_formulation_views count={len(self.formulation_items)}")
        self._ensure_normalized_items()
        self._populate_formulation_tables()
        self._populate_totals_table()
        logging.debug("_refresh_formulation_views done")
        self._ensure_preview_selection()

    def _select_preview_row(self, row: int) -> None:
        if row < 0 or row >= self.formulation_preview.rowCount():
            return
        sel_model = self.formulation_preview.selectionModel()
        if sel_model is None:
            return
        sel_model.clearSelection()
        index = self.formulation_preview.model().index(row, 0)
        sel_model.select(
            index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
        )
        self.formulation_preview.setCurrentIndex(index)

    def _ensure_preview_selection(self) -> None:
        if not self.formulation_items:
            self.details_table.setRowCount(0)
            return
        self._ensure_normalized_items()
        sel_model = self.formulation_preview.selectionModel()
        has_sel = sel_model and sel_model.hasSelection()
        if not has_sel:
            self._select_preview_row(len(self.formulation_items) - 1)
        self._show_nutrients_for_selected_preview()

    def _show_nutrients_for_row(self, row: int) -> None:
        if row < 0 or row >= len(self.formulation_items):
            self.details_table.setRowCount(0)
            return
        nutrients = self.formulation_items[row].get("nutrients", []) or []
        self._populate_details_table(nutrients)

    def _show_nutrients_for_selected_preview(self) -> None:
        sel_model = self.formulation_preview.selectionModel()
        if not sel_model or not sel_model.hasSelection():
            self._show_nutrients_for_row(-1)
            return
        row = sel_model.selectedRows()[0].row()
        self._show_nutrients_for_row(row)

    def _export_formulation_to_excel(self, filepath: str) -> None:
        """Build Excel from scratch with nutrient categories as in USDA view."""
        self._ensure_normalized_items()
        wb = Workbook()
        ws = wb.active
        ws.title = "Ingredientes"
        totals_sheet = wb.create_sheet("Totales")

        base_headers = [
            "FDC ID",
            "Ingrediente",
            "Marca / Origen",
            "Tipo de dato",
            "Cantidad (g)",
            "Cantidad (%)",
        ]

        nutrient_headers, header_categories, header_key_map = self._collect_nutrient_columns()
        header_by_key = {v: k for k, v in header_key_map.items()}

        header_fill = PatternFill("solid", fgColor="D9D9D9")
        total_fill = PatternFill("solid", fgColor="FFF2CC")
        category_fills = {
            "Proximates": PatternFill("solid", fgColor="DAEEF3"),
            "Carbohydrates": PatternFill("solid", fgColor="E6B8B7"),
            "Minerals": PatternFill("solid", fgColor="C4D79B"),
            "Vitamins and Other Components": PatternFill("solid", fgColor="FFF2CC"),
            "Lipids": PatternFill("solid", fgColor="D9E1F2"),
            "Amino acids": PatternFill("solid", fgColor="E4DFEC"),
        }
        center = Alignment(horizontal="center", vertical="center")

        # Row 1: group titles (base + nutrient categories)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(base_headers))
        ws.cell(row=1, column=1, value="Detalles de formulación").alignment = center

        if nutrient_headers:
            start_col = len(base_headers) + 1
            col = start_col
            while col < start_col + len(nutrient_headers):
                idx = col - start_col
                category = header_categories.get(nutrient_headers[idx], "Nutrientes")
                run_start = col
                while (
                    col < start_col + len(nutrient_headers)
                    and header_categories.get(nutrient_headers[col - start_col], "Nutrientes")
                    == category
                ):
                    col += 1
                run_end = col - 1
                ws.merge_cells(start_row=1, start_column=run_start, end_row=1, end_column=run_end)
                cat_cell = ws.cell(row=1, column=run_start, value=category)
                cat_cell.alignment = center
                cat_cell.fill = category_fills.get(category, header_fill)

        # Row 2: headers
        headers = base_headers + nutrient_headers
        for col_idx, name in enumerate(headers, start=1):
            cell = ws.cell(row=2, column=col_idx, value=name)
            cell.fill = category_fills.get(
                header_categories.get(name, ""), header_fill
            ) if col_idx > len(base_headers) else header_fill
            cell.alignment = center

        start_row = 3
        grams_col = base_headers.index("Cantidad (g)") + 1
        percent_col = base_headers.index("Cantidad (%)") + 1
        data_rows = len(self.formulation_items)
        end_row = start_row + data_rows - 1

        # Write ingredient rows
        for idx, item in enumerate(self.formulation_items):
            row = start_row + idx
            values = [
                item.get("fdc_id", ""),
                item.get("description", ""),
                item.get("brand", ""),
                item.get("data_type", ""),
                float(item.get("amount_g", 0.0) or 0.0),
                None,  # placeholder for percent formula
            ]
            for col_idx, val in enumerate(values, start=1):
                ws.cell(row=row, column=col_idx, value=val)

            gram_cell = f"{get_column_letter(grams_col)}{row}"
            total_range = f"${get_column_letter(grams_col)}${start_row}:${get_column_letter(grams_col)}${end_row}"
            ws.cell(
                row=row,
                column=percent_col,
                value=f"={gram_cell}/SUM({total_range})",
            ).number_format = "0.00%"

            nut_map = self._nutrients_by_header(item.get("nutrients", []), header_by_key)
            for offset, header in enumerate(nutrient_headers, start=len(base_headers) + 1):
                if header in nut_map:
                    ws.cell(row=row, column=offset, value=nut_map[header])

        total_row = end_row + 1
        ws.cell(row=total_row, column=1, value="Total")
        ws.cell(row=total_row, column=2, value="Formulado")
        ws.cell(row=total_row, column=3, value="Formulado")
        ws.cell(row=total_row, column=4, value="Formulado")

        gram_total_cell = ws.cell(
            row=total_row,
            column=grams_col,
            value=f"=SUBTOTAL(9,{get_column_letter(grams_col)}{start_row}:{get_column_letter(grams_col)}{end_row})",
        )
        gram_total_cell.fill = total_fill
        percent_total_cell = ws.cell(row=total_row, column=percent_col, value="100%")
        percent_total_cell.number_format = "0.00%"
        percent_total_cell.fill = total_fill

        for offset, header in enumerate(nutrient_headers, start=len(base_headers) + 1):
            col_letter = get_column_letter(offset)
            formula = (
                f"=SUMPRODUCT(${get_column_letter(percent_col)}${start_row}:${get_column_letter(percent_col)}${end_row},"
                f"${col_letter}${start_row}:${col_letter}${end_row})"
            )
            cell = ws.cell(row=total_row, column=offset, value=formula)
            cell.fill = total_fill

        # Styles for data rows
        for row in range(start_row, total_row + 1):
            ws.cell(row=row, column=grams_col).number_format = "0.0"

        # Freeze panes to keep headers/base columns visible
        freeze_col = len(base_headers) + 1 if nutrient_headers else 1
        ws.freeze_panes = f"{get_column_letter(freeze_col)}3"

        # Adjust widths
        widths = {
            "A": 12,
            "B": 35,
            "C": 18,
            "D": 14,
            "E": 12,
            "F": 12,
        }
        for col_letter, width in widths.items():
            ws.column_dimensions[col_letter].width = width

        # Totales sheet: simple reference to totals row
        totals_headers = ["Nutriente", "Total", "Unidad"]
        for col_idx, name in enumerate(totals_headers, start=1):
            cell = totals_sheet.cell(row=1, column=col_idx, value=name)
            cell.fill = header_fill
            cell.alignment = center

        for idx, header in enumerate(nutrient_headers, start=1):
            name_part, unit = self._split_header_unit(header)
            totals_sheet.cell(row=idx + 1, column=1, value=name_part)
            totals_sheet.cell(row=idx + 1, column=3, value=unit or "")
            source_cell = f"Ingredientes!{get_column_letter(len(base_headers) + idx)}{total_row}"
            totals_sheet.cell(row=idx + 1, column=2, value=f"={source_cell}")

        wb.save(filepath)

    def _calculate_totals(self) -> Dict[str, Dict[str, Any]]:
        """
        Sum nutrients across all ingredients and normalize to 100 g de producto final.
        Assumes nutrient amounts from the API are per 100 g of ingredient.
        Groups by nutrient id/number to merge Foundation + SR Legacy entries.
        """
        logging.debug(f"_calculate_totals start items={len(self.formulation_items)}")
        self._ensure_normalized_items()
        totals: Dict[str, Dict[str, Any]] = {}
        total_weight = self._total_weight()
        for item in self.formulation_items:
            qty = item.get("amount_g", 0) or 0
            for nutrient in self._sort_nutrients_for_display(item.get("nutrients", [])):
                amount = nutrient.get("amount")
                if amount is None:
                    continue
                nut = nutrient.get("nutrient") or {}
                key = self._nutrient_key(nut)
                if not key:
                    continue
                entry = totals.setdefault(
                    key,
                    {
                        "name": nut.get("name", ""),
                        "unit": "",
                        "amount": 0.0,
                        "order": self._nutrient_order(nut, len(totals)),
                    },
                )
                if nut.get("name") and not entry["name"]:
                    entry["name"] = nut["name"]
                inferred_unit = self._infer_unit(nut)
                if inferred_unit and not entry["unit"]:
                    entry["unit"] = inferred_unit
                entry["order"] = min(
                    entry.get("order", float("inf")),
                    self._nutrient_order(nut, len(totals)),
                )
                entry["amount"] += amount * qty / 100.0

        if total_weight > 0:
            factor = 100.0 / total_weight
            for entry in totals.values():
                entry["amount"] *= factor
        logging.debug(f"_calculate_totals done nutrients={len(totals)} total_weight={total_weight}")
        return totals

    def _nutrient_key(self, nutrient: Dict[str, Any]) -> str:
        """
        Build a consistent key for nutrients, preferring id then number then name.
        This avoids duplicates when some records lack unitName (Foundation vs SR).
        """
        name_lower = (nutrient.get("name") or "").strip().lower()
        unit_lower = (nutrient.get("unitName") or "").strip().lower()
        # Special-case Energy to keep kcal/kJ separated when ids/numbers are missing.
        if name_lower == "energy" and unit_lower:
            return f"energy:{unit_lower}"
        if "id" in nutrient and nutrient["id"] is not None:
            return f"id:{nutrient['id']}"
        if nutrient.get("number"):
            return f"num:{nutrient['number']}"
        name = name_lower
        return f"name:{name}" if name else ""

    def _reference_info(self, nutrient: Dict[str, Any]) -> Dict[str, Any]:
        """Return cached rank/category info for a nutrient key if available."""
        key = self._nutrient_key(nutrient)
        return self._reference_order_map.get(key, {})

    def _update_reference_from_details(self, details: Dict[str, Any]) -> None:
        """Update reference rank/category map from a full USDA response."""
        nutrients = details.get("foodNutrients", []) or []
        if not nutrients:
            return
        current_category: str | None = None
        for entry in nutrients:
            nut = entry.get("nutrient") or {}
            key = self._nutrient_key(nut)
            if not key:
                continue
            if entry.get("amount") is None:
                # category row
                current_category = (nut.get("name") or "").strip() or current_category
                self._reference_order_map.setdefault(
                    key,
                    {
                        "rank": nut.get("rank"),
                        "category": current_category,
                        "unit": nut.get("unitName"),
                    },
                )
                continue
            self._reference_order_map[key] = {
                "rank": nut.get("rank"),
                "category": current_category,
                "unit": nut.get("unitName"),
            }

    def _sort_nutrients_for_display(self, nutrients: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """Return nutrients ordered by USDA rank or reference map."""
        if not nutrients:
            return []
        indexed = []
        for idx, entry in enumerate(nutrients):
            nut = entry.get("nutrient") or {}
            order = self._nutrient_order(nut, idx + 10000)
            indexed.append((order, idx, entry))
        indexed.sort(key=lambda t: (t[0], t[1]))
        return [item[2] for item in indexed]

    def _header_key(self, nutrient: Dict[str, Any]) -> tuple[str, str, str]:
        """Return a stable header key plus canonical name and unit for a nutrient."""
        name = self._canonical_alias_name(nutrient.get("name", "") or "")
        unit = nutrient.get("unitName") or self._infer_unit(nutrient) or ""
        unit_part = unit.strip().lower()
        name_part = name.strip().lower()
        if name_part:
            header_key = f"{name_part}|{unit_part}"
        else:
            base_key = self._nutrient_key(nutrient)
            if not base_key:
                return "", name, unit
            header_key = f"{base_key}|{unit_part}"
        return header_key, name, unit

    def _infer_unit(self, nutrient: Dict[str, Any]) -> str:
        """Try to fill missing unit from nutrient metadata or heuristic defaults."""
        unit = nutrient.get("unitName")
        if unit:
            return unit

        number = str(nutrient.get("number") or "").strip()
        name = (nutrient.get("name") or "").lower()

        default_units_by_number = {
            # Proximates / macros
            "255": "g",  # Water
            "203": "g",  # Protein
            "204": "g",  # Total lipid (fat)
            "298": "g",  # Total fat (NLEA)
            "202": "g",  # Nitrogen
            "207": "g",  # Ash
            "205": "g",  # Carbohydrate, by difference
            "291": "g",  # Fiber, total dietary
            "269": "g",  # Sugars, total
            "268": "kJ",  # Energy (kJ)
            "208": "kcal",  # Energy (kcal)
            "951": "g",  # Proximates
            "956": "g",  # Carbohydrates
        }
        if number in default_units_by_number:
            return default_units_by_number[number]

        if "energy" in name and "kcal" in name:
            return "kcal"
        if "energy" in name and "kj" in name:
            return "kJ"

        macro_hints = [
            "water",
            "protein",
            "lipid",
            "fat",
            "ash",
            "carbohydrate",
            "fiber",
            "sugar",
            "starch",
            "nitrogen",
            "fatty acids",
            "sfa",
            "mufa",
            "pufa",
        ]
        if any(hint in name for hint in macro_hints) or ":" in name:
            return "g"

        amino_acids = [
            "alanine",
            "arginine",
            "aspartic acid",
            "cystine",
            "cysteine",
            "hydroxyproline",
            "glutamic acid",
            "glycine",
            "histidine",
            "isoleucine",
            "leucine",
            "lysine",
            "methionine",
            "phenylalanine",
            "proline",
            "serine",
            "threonine",
            "tryptophan",
            "tyrosine",
            "valine",
        ]
        if name in amino_acids:
            return "g"

        simple_sugars = [
            "sucrose",
            "glucose",
            "fructose",
            "lactose",
            "maltose",
            "galactose",
        ]
        if name in simple_sugars:
            return "g"

        if name == "alcohol, ethyl":
            return "g"

        return ""

    def _nutrient_order(self, nutrient: Dict[str, Any], fallback: int) -> float:
        """Return USDA rank if available; otherwise keep insertion order fallback."""
        rank = nutrient.get("rank")
        if rank is None:
            ref = self._reference_info(nutrient)
            rank = ref.get("rank")
        try:
            return float(rank)
        except (TypeError, ValueError):
            return float(fallback)

    def _add_row_to_formulation(self, row: int | None = None) -> None:
        logging.debug(f"_add_row_to_formulation row={row}")
        if row is None:
            indexes = self.table.selectionModel().selectedRows()
            if not indexes:
                self.status_label.setText("Selecciona un alimento para agregar.")
                return
            row = indexes[0].row()

        fdc_item = self.table.item(row, 0)
        if not fdc_item:
            return
        fdc_id_text = fdc_item.text().strip()
        if not fdc_id_text or not fdc_id_text.isdigit():
            self.status_label.setText("FDC ID inválido.")
            return

        mode, value = self._prompt_quantity()
        logging.debug(f"_prompt_quantity returned mode={mode} value={value}")
        if mode is None:
            return

        display_amount = (
            self._format_amount_for_status(value, include_new=True)
            if mode == "g"
            else f"{value:.2f} %"
        )
        self.status_label.setText(
            f"Agregando {fdc_id_text} ({display_amount})..."
        )
        self.add_button.setEnabled(False)
        self._start_add_fetch(int(fdc_id_text), mode, value)

    def _start_add_fetch(self, fdc_id: int, mode: str, value: float) -> None:
        logging.debug(f"_start_add_fetch fdc_id={fdc_id} mode={mode} value={value}")
        self._set_window_progress(f"1/1 ID #{fdc_id}")
        thread = QThread(self)
        worker = AddWorker(
            fdc_id,
            max_attempts=self.import_max_attempts,
            read_timeout=self.import_read_timeout,
            mode=mode,
            value=value,
        )
        worker.moveToThread(thread)
        self._workers.append(worker)
        self._threads.append(thread)
        self._current_add_worker = worker

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_add_progress)
        worker.finished.connect(self._on_add_finished)
        worker.error.connect(self._on_add_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        def _cleanup() -> None:
            if thread in self._threads:
                self._threads.remove(thread)
            if worker in self._workers:
                self._workers.remove(worker)
            if self._current_add_worker is worker:
                self._current_add_worker = None

        thread.finished.connect(_cleanup)
        thread.start()

    def _on_add_progress(self, message: str) -> None:
        self._set_window_progress(message)
        self.status_label.setText(f"Agregando ingrediente: {message}")

    def _on_add_finished(self, details, mode: str, value: float) -> None:
        logging.debug(
            f"_on_add_finished fdc_id={details.get('fdcId', '?')} "
            f"mode={mode} value={value} nutrients={len(details.get('foodNutrients', []) or [])}"
        )
        self._reset_add_ui_state()
        self._on_add_details_loaded(details, mode, value)

    def _reset_add_ui_state(self) -> None:
        self.add_button.setEnabled(True)
        self._set_window_progress(None)
        if self._current_add_worker:
            self._current_add_worker = None

    def _format_amount_for_status(self, amount_g: float, include_new: bool = False) -> str:
        """Return a user-facing label for a quantity using the active mode."""
        if self.quantity_mode == "g":
            return f"{amount_g:.1f} g"

        total = self._total_weight()
        if include_new:
            total += amount_g
        percent = 0.0 if total <= 0 else (amount_g / total) * 100.0
        return f"{percent:.2f} %"

    def _safe_base_name(self, fallback: str = "formulacion") -> str:
        """Return a filesystem-safe base name using the formula input or fallback."""
        name = (self.formula_name_input.text() or "").strip()
        clean = re.sub(r'[\\/:*?"<>|]+', "_", name).strip(". ")
        return clean or fallback

    def _prompt_quantity(
        self, default_amount: float | None = None, editing_index: int | None = None
    ) -> tuple[str | None, float]:
        if self.quantity_mode == "g":
            start_value = default_amount if default_amount is not None else 100.0
            title = "Cantidad"
            label = "Cantidad del ingrediente (g):"
            min_value, max_value, decimals = 0.1, 1_000_000.0, 1
        else:
            start_value = (
                self._amount_to_percent(default_amount or 0.0)
                if default_amount is not None
                else 10.0
            )
            title = "Porcentaje"
            label = "Porcentaje del ingrediente sobre la formulación (%):"
            min_value, max_value, decimals = 0.01, 100.0, 2

        raw_value, ok = QInputDialog.getDouble(
            self,
            title,
            label,
            start_value,
            min_value,
            max_value,
            decimals,
        )
        if not ok:
            return None, 0.0

        return ("g", raw_value) if self.quantity_mode == "g" else ("percent", raw_value)

    def _edit_quantity_for_row(self, row: int) -> None:
        """Prompt the user to update the quantity of a specific row."""
        if row < 0 or row >= len(self.formulation_items):
            self.status_label.setText("Fila seleccionada inválida.")
            return

        item = self.formulation_items[row]
        default_amount = item.get("amount_g", 0.0)
        mode, value = self._prompt_quantity(default_amount, editing_index=row)
        if mode is None:
            return

        if mode == "g":
            item["amount_g"] = value
        else:
            if not self._apply_percent_edit(row, value):
                return

        self._refresh_formulation_views()
        if mode == "g":
            msg_value = self._format_amount_for_status(item.get("amount_g", 0.0))
        else:
            msg_value = f"{value:.2f} %"
        self.status_label.setText(
            f"Actualizado {item.get('fdc_id', '')} a {msg_value}"
        )

    def _apply_percent_edit(self, target_idx: int, target_percent: float) -> bool:
        """Redistribute quantities so locked percentages stay fixed."""
        if target_percent < 0 or target_percent > 100:
            QMessageBox.warning(self, "Porcentaje inválido", "Ingresa un valor entre 0 y 100.")
            return False

        if target_idx < 0 or target_idx >= len(self.formulation_items):
            self.status_label.setText("Fila seleccionada inválida.")
            return False

        total_weight = self._total_weight()
        base_total = total_weight if total_weight > 0 else 100.0
        if base_total <= 0:
            QMessageBox.warning(
                self,
                "Porcentaje inválido",
                "No hay cantidad total para calcular porcentajes.",
            )
            return False

        current_percents = [
            (item.get("amount_g", 0.0) or 0.0) * 100.0 / base_total
            for item in self.formulation_items
        ]

        locked_sum = sum(
            current_percents[idx]
            for idx, item in enumerate(self.formulation_items)
            if item.get("locked") and idx != target_idx
        )
        if locked_sum > 100.0:
            QMessageBox.warning(
                self,
                "Porcentaje inválido",
                "Los ingredientes fijados ya superan el 100%. Libera uno para continuar.",
            )
            return False

        remaining = 100.0 - locked_sum - target_percent
        free_indices = [
            idx
            for idx, item in enumerate(self.formulation_items)
            if not item.get("locked") and idx != target_idx
        ]

        if remaining < -0.0001:
            QMessageBox.warning(
                self,
                "Sin grado de libertad",
                "No hay porcentaje libre suficiente. Libera un ingrediente o reduce el valor.",
            )
            return False

        if not free_indices and abs(remaining) > 0.0001:
            QMessageBox.warning(
                self,
                "Sin grado de libertad",
                "Debe quedar al menos un ingrediente sin fijar para ajustar porcentajes.",
            )
            return False

        cur_free_sum = sum(current_percents[idx] for idx in free_indices)
        new_percents = [0.0 for _ in self.formulation_items]

        for idx, item in enumerate(self.formulation_items):
            if item.get("locked") and idx != target_idx:
                new_percents[idx] = current_percents[idx]
            elif idx == target_idx:
                new_percents[idx] = target_percent
            else:
                if cur_free_sum > 0:
                    new_percents[idx] = (
                        current_percents[idx] * remaining / cur_free_sum
                    )
                elif free_indices:
                    new_percents[idx] = remaining if idx == free_indices[0] else 0.0

        if any(pct < -0.001 for pct in new_percents):
            QMessageBox.warning(
                self,
                "Sin grado de libertad",
                "No hay porcentaje libre suficiente. Ajusta los valores o libera un ingrediente.",
            )
            return False

        for idx, pct in enumerate(new_percents):
            safe_pct = max(pct, 0.0)
            self.formulation_items[idx]["amount_g"] = safe_pct * base_total / 100.0
        return True

    def _remove_selected_from_formulation(self, table: QTableWidget) -> None:
        indexes = table.selectionModel().selectedRows()
        if not indexes:
            self.status_label.setText("Selecciona un ingrediente para eliminar.")
            return
        row = indexes[0].row()
        if 0 <= row < len(self.formulation_items):
            removed = self.formulation_items.pop(row)
            if self.formulation_items and self._locked_count() == len(
                self.formulation_items
            ):
                self.formulation_items[0]["locked"] = False
            self._refresh_formulation_views()
            self.status_label.setText(
                f"Eliminado {removed.get('fdc_id', '')} - {removed.get('description', '')}"
            )
        else:
            self.status_label.setText("Fila seleccionada inválida.")

    def _run_in_thread(self, fn, args, on_success, on_error) -> None:
        """Start a worker thread for API calls and handle cleanup."""
        thread = QThread(self)
        worker = ApiWorker(fn, *args)
        worker.moveToThread(thread)
        self._workers.append(worker)

        thread.started.connect(worker.run)
        worker.finished.connect(on_success)
        worker.error.connect(on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        def _cleanup() -> None:
            if thread in self._threads:
                self._threads.remove(thread)
            if worker in self._workers:
                self._workers.remove(worker)

        thread.finished.connect(_cleanup)

        self._threads.append(thread)
        thread.start()

    # ---- Callbacks for async ops ----
    def _on_search_success(self, foods) -> None:
        foods_sorted = self._sort_search_results(foods)
        filtered = self._filter_results_by_query(foods_sorted, self.last_query)
        self.search_results = filtered
        self._last_results_count = len(filtered)
        self.search_page = 1
        self._show_current_search_page()
        total_pages = max(1, (len(filtered) + self.search_page_size - 1) // self.search_page_size)
        self.status_label.setText(
            f"Se encontraron {len(filtered)} resultados (pagina {self.search_page}/{total_pages})."
        )
        self.search_button.setEnabled(True)
        self._update_paging_buttons(len(filtered))

    def _on_search_error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")
        self.search_button.setEnabled(True)
        self._update_paging_buttons(self._last_results_count)

    def _on_details_success(self, details) -> None:
        nutrients = self._normalize_nutrients(details.get("foodNutrients", []) or [])
        self._populate_details_table(nutrients)

        desc = details.get("description", "") or ""
        fdc_id = details.get("fdcId", "")
        self.status_label.setText(
            f"Detalles de {fdc_id} - {desc} ({len(nutrients)} nutrientes)"
        )
        self.fdc_id_button.setEnabled(True)

    def _on_details_error(self, message: str) -> None:
        self.status_label.setText(f"Error al cargar detalles: {message}")
        self.fdc_id_button.setEnabled(True)

    def _on_add_details_loaded(self, details, mode: str, value: float) -> None:
        logging.debug(
            f"_on_add_details_loaded fdc_id={details.get('fdcId', '?')} "
            f"mode={mode} value={value}"
        )
        nutrients = self._augment_fat_nutrients(details.get("foodNutrients", []) or [])
        self._update_reference_from_details(details)
        desc = details.get("description", "") or ""
        brand = details.get("brandOwner", "") or ""
        data_type = details.get("dataType", "") or ""
        fdc_id = details.get("fdcId", "")

        new_item = {
            "fdc_id": fdc_id,
            "description": desc,
            "brand": brand,
            "data_type": data_type,
            "amount_g": value if mode == "g" else 0.0,
            "nutrients": nutrients,
            "locked": False,
        }
        self.formulation_items.append(new_item)

        if mode == "percent":
            success = self._apply_percent_edit(len(self.formulation_items) - 1, value)
            if not success:
                self.formulation_items.pop()
                self.add_button.setEnabled(True)
                return

        self._populate_details_table(nutrients)
        self._refresh_formulation_views()
        self._select_preview_row(len(self.formulation_items) - 1)
        msg_value = (
            self._format_amount_for_status(new_item.get("amount_g", 0.0))
            if mode == "g"
            else f"{value:.2f} %"
        )
        self.status_label.setText(
            f"Agregado {fdc_id} - {desc} ({msg_value})"
        )
        self.add_button.setEnabled(True)
        self._upgrade_item_to_full(len(self.formulation_items) - 1, int(fdc_id))

    def _on_add_error(self, message: str) -> None:
        self._reset_add_ui_state()
        self.status_label.setText(f"Error al agregar: {message}")
        logging.error(f"_on_add_error: {message}")

    def _upgrade_item_to_full(self, index: int, fdc_id: int) -> None:
        """Fetch full details in background to enrich ordering/categorias without bloquear UI."""
        if has_cached_food(fdc_id, detail_format="full"):
            return

        def _on_success(details: Dict[str, Any]) -> None:
            if index < 0 or index >= len(self.formulation_items):
                return
            nutrients = self._augment_fat_nutrients(details.get("foodNutrients", []) or [])
            self._update_reference_from_details(details)
            item = self.formulation_items[index]
            item["nutrients"] = nutrients
            item["description"] = details.get("description", item.get("description", ""))
            item["brand"] = details.get("brandOwner", item.get("brand", ""))
            item["data_type"] = details.get("dataType", item.get("data_type", ""))
            self._refresh_formulation_views()
            # Si el item sigue seleccionado, actualizar panel de detalles.
            indexes = self.formulation_preview.selectionModel().selectedRows()
            if indexes and indexes[0].row() == index:
                self._populate_details_table(nutrients)

        def _on_error(message: str) -> None:
            logging.debug(f"Background full fetch failed for {fdc_id}: {message}")

        self._run_in_thread(
            fn=lambda: get_food_details(
                fdc_id,
                timeout=(3.05, 20.0),
                detail_format="full",
            ),
            args=(),
            on_success=_on_success,
            on_error=_on_error,
        )

    def on_totals_checkbox_changed(self, item: QTableWidgetItem) -> None:
        """Sync export checkbox state into memory and update toggle label."""
        if item.column() != 3:
            return
        nut_key = item.data(Qt.UserRole)
        if not nut_key:
            return
        self.nutrient_export_flags[nut_key] = item.checkState() == Qt.Checked
        self._update_toggle_export_button()

    def on_toggle_export_clicked(self) -> None:
        """Toggle all nutrient export checkboxes on/off."""
        if not self.nutrient_export_flags:
            return
        all_checked = all(self.nutrient_export_flags.values())
        new_state = not all_checked
        for key in list(self.nutrient_export_flags.keys()):
            self.nutrient_export_flags[key] = new_state
        self._populate_totals_table()
