"""Search tab UI component with integrated presenter logic."""

from typing import Any, Dict, List, Optional
import logging

from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QInputDialog,
    QMessageBox,
)

from ui.presenters.search_presenter import SearchPresenter
from ui.workers import ApiWorker
from services.usda_api import get_food_details


class SearchTab(QWidget):
    """Tab for searching USDA food database and previewing ingredients.

    Signals:
        ingredient_add_requested: Emitted when user wants to add ingredient (fdc_id, amount_g)
        ingredient_remove_requested: Emitted when user wants to remove ingredient (index)
        status_message: Emitted to display status messages
    """

    # Signals for cross-tab communication
    ingredient_add_requested = Signal(int, float)  # fdc_id, amount_g
    ingredient_remove_requested = Signal(int)  # index
    status_message = Signal(str)

    def __init__(
        self,
        search_presenter: Optional[SearchPresenter] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # Presenter
        self._presenter = search_presenter or SearchPresenter()

        # Search state
        self._search_results: List[Dict[str, Any]] = []
        self._search_page = 1
        self._search_page_size = 25
        self._search_fetch_page_size = 200
        self._search_max_pages = 4
        self._last_query = ""
        self._last_include_brands = False
        self._prefetching_fdc_ids: set[int] = set()

        # Data type priority for sorting
        self._data_type_priority = {
            "Foundation": 0,
            "SR Legacy": 1,
            "Survey (FNDDS)": 2,
            "Branded": 3,
            "Experimental": 4,
        }

        # Thread management
        self._threads: list[QThread] = []
        self._workers: list[QObject] = []

        # External formulation items reference (set by MainWindow)
        self._formulation_items: List[Dict[str, Any]] = []

        self._build_ui()
        self._connect_signals()

    def set_formulation_items(self, items: List[Dict[str, Any]]) -> None:
        """Set reference to formulation items for preview sync."""
        self._formulation_items = items
        self._refresh_formulation_preview()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Buscar alimento (ej: apple, rice, cheese)..."
        )
        self.search_button = QPushButton("Buscar")

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        # Pagination and filter controls
        self.include_brands_checkbox = QCheckBox("Incluir Marcas")
        self.prev_page_button = QPushButton("<")
        self.prev_page_button.setFixedWidth(32)
        self.next_page_button = QPushButton(">")
        self.next_page_button.setFixedWidth(32)
        self.prev_page_button.setEnabled(False)
        self.next_page_button.setEnabled(False)

        # Legacy controls (hidden)
        self.fdc_id_input = QLineEdit()
        self.fdc_id_input.hide()
        self.fdc_id_button = QPushButton("Cargar FDC ID")
        self.fdc_id_button.hide()
        self.add_button = QPushButton("Agregar seleccionado a formulación")
        self.add_button.hide()

        # Status label
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

        # Status and controls row
        status_controls_layout = QHBoxLayout()
        status_controls_layout.setContentsMargins(0, 0, 0, 0)
        status_controls_layout.addWidget(self.status_label, 1)
        status_controls_layout.addStretch()
        status_controls_layout.addWidget(self.include_brands_checkbox)
        status_controls_layout.addWidget(self.prev_page_button)
        status_controls_layout.addWidget(self.next_page_button)
        layout.addLayout(status_controls_layout)

        # Results table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["FDC ID", "Descripción", "Marca / Origen", "Tipo de dato"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.horizontalHeader().setStretchLastSection(True)

        # Details table (nutrients)
        self.details_table = QTableWidget(0, 3)
        self.details_table.setHorizontalHeaderLabels(
            ["Nutriente", "Cantidad", "Unidad"]
        )
        self.details_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.details_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.details_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.details_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.details_table.horizontalHeader().setStretchLastSection(True)

        # Bottom section with formulation preview and details
        bottom_layout = QHBoxLayout()

        # Left panel - formulation preview
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

        # Right panel - nutrient details
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Nutrientes del ingrediente seleccionado"))
        right_panel.addWidget(self.details_table)

        bottom_layout.addLayout(left_panel, 1)
        bottom_layout.addLayout(right_panel, 1)

        bottom_widget = QWidget()
        bottom_widget.setLayout(bottom_layout)

        # Vertical splitter
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([400, 500])

        layout.addWidget(splitter)

        self._set_default_column_widths()

    def _connect_signals(self) -> None:
        """Connect internal signals to handlers."""
        self.search_button.clicked.connect(self._on_search_clicked)
        self.search_input.returnPressed.connect(self._on_search_clicked)
        self.prev_page_button.clicked.connect(self._on_prev_page_clicked)
        self.next_page_button.clicked.connect(self._on_next_page_clicked)
        self.include_brands_checkbox.stateChanged.connect(self._on_include_brands_toggled)
        self.table.cellDoubleClicked.connect(self._on_result_double_clicked)
        self.table.itemSelectionChanged.connect(self._on_search_selection_changed)
        self.formulation_preview.cellDoubleClicked.connect(self._on_preview_double_clicked)
        self.formulation_preview.itemSelectionChanged.connect(self._on_preview_selection_changed)
        self.remove_preview_button.clicked.connect(self._on_remove_preview_clicked)

    def _set_default_column_widths(self) -> None:
        """Set sensible initial column widths while keeping them resizable."""
        for table in (self.table, self.details_table, self.formulation_preview):
            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Interactive)

        self.table.setColumnWidth(0, 75)   # FDC ID
        self.table.setColumnWidth(1, 340)  # Descripcion
        self.table.setColumnWidth(2, 200)  # Marca / Origen
        self.table.setColumnWidth(3, 120)  # Tipo de dato

        self.details_table.setColumnWidth(0, 200)  # Nutriente
        self.details_table.setColumnWidth(1, 90)   # Cantidad
        self.details_table.setColumnWidth(2, 70)   # Unidad

        self.formulation_preview.setColumnWidth(0, 70)   # FDC ID
        self.formulation_preview.setColumnWidth(1, 290)  # Ingrediente

    # ==================== Search Handlers ====================

    def _on_search_clicked(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self._set_status("Ingresa un término de búsqueda.")
            return

        self._search_page = 1
        self._last_query = query
        self._last_include_brands = self.include_brands_checkbox.isChecked()
        self._start_search()

    def _on_prev_page_clicked(self) -> None:
        if self._search_page <= 1:
            return
        self._search_page -= 1
        self._show_current_search_page()
        self._update_paging_buttons()

    def _on_next_page_clicked(self) -> None:
        total = len(self._search_results)
        if self._search_page * self._search_page_size >= total:
            return
        self._search_page += 1
        self._show_current_search_page()
        self._update_paging_buttons()

    def _on_include_brands_toggled(self) -> None:
        if not self.search_input.text().strip():
            return
        self._search_page = 1
        self._last_query = self.search_input.text().strip()
        self._last_include_brands = self.include_brands_checkbox.isChecked()
        self._start_search()

    def _on_result_double_clicked(self, row: int, _: int) -> None:
        """Double click on a search row -> add to formulation with quantity."""
        self._add_row_to_formulation(row)

    def _on_search_selection_changed(self) -> None:
        """Prefetch details for the selected search result."""
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return
        row = indexes[0].row()
        fdc_item = self.table.item(row, 0)
        if not fdc_item:
            return
        fdc_id_text = fdc_item.text().strip()
        self._prefetch_fdc_id(fdc_id_text)

    def _on_preview_double_clicked(self, row: int, column: int) -> None:
        """Double click on preview -> show nutrients."""
        self._show_nutrients_for_row(row)

    def _on_preview_selection_changed(self) -> None:
        """Update nutrients panel when preview selection changes."""
        self._show_nutrients_for_selected_preview()

    def _on_remove_preview_clicked(self) -> None:
        """Remove selected ingredient from formulation."""
        indexes = self.formulation_preview.selectionModel().selectedRows()
        if not indexes:
            self._set_status("Selecciona un ingrediente para eliminar.")
            return

        # Remove in reverse order to maintain indices
        rows_to_remove = sorted([idx.row() for idx in indexes], reverse=True)
        for row in rows_to_remove:
            self.ingredient_remove_requested.emit(row)

    # ==================== Search Logic ====================

    def _start_search(self) -> None:
        if not self._last_query:
            self._set_status("Ingresa un término de búsqueda.")
            return

        self.search_button.setEnabled(False)
        self.prev_page_button.setEnabled(False)
        self.next_page_button.setEnabled(False)
        self._search_results = []
        self._populate_table([])

        self._set_status(f"Buscando en FoodData Central... (página {self._search_page})")

        self._run_in_thread(
            fn=self._fetch_all_pages,
            args=(self._last_query, self._last_include_brands),
            on_success=self._on_search_success,
            on_error=self._on_search_error,
        )

    def _fetch_all_pages(self, query: str, include_branded: bool) -> List[Dict[str, Any]]:
        """Fetch search results from USDA API."""
        all_results: List[Dict[str, Any]] = []
        page = 1

        while page <= self._search_max_pages:
            batch = self._presenter.search(
                query=query,
                page_size=self._search_fetch_page_size,
                include_branded=include_branded,
                page_number=page,
            )
            if not batch:
                break
            all_results.extend(batch)
            if len(batch) < self._search_fetch_page_size:
                break
            page += 1

        # Fallback: if query looks like FDC ID, try direct lookup
        stripped = query.strip()
        if not all_results and stripped.isdigit():
            try:
                details = get_food_details(int(stripped), detail_format="abridged")
                all_results.append({
                    "fdcId": details.get("fdcId"),
                    "description": details.get("description", ""),
                    "brandOwner": details.get("brandOwner", "") or "",
                    "dataType": details.get("dataType", "") or "",
                })
            except Exception:
                pass

        return all_results

    def _on_search_success(self, results: List[Dict[str, Any]]) -> None:
        """Handle successful search results."""
        self.search_button.setEnabled(True)

        # Sort and filter results
        sorted_results = self._sort_search_results(results)
        filtered_results = self._filter_results_by_query(sorted_results, self._last_query)

        self._search_results = filtered_results
        self._search_page = 1
        self._show_current_search_page()
        self._update_paging_buttons()

    def _on_search_error(self, error: str) -> None:
        """Handle search error."""
        self.search_button.setEnabled(True)
        self._set_status(f"Error en búsqueda: {error}")
        logging.error(f"Search error: {error}")

    def _sort_search_results(self, foods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort results by data type priority, then by description."""
        def priority(data_type: str) -> int:
            return self._data_type_priority.get(
                data_type,
                self._data_type_priority.get(data_type.strip(), len(self._data_type_priority))
            )

        return sorted(
            foods,
            key=lambda f: (
                priority(f.get("dataType", "") or ""),
                (f.get("description", "") or "").lower(),
            ),
        )

    def _filter_results_by_query(self, foods: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Filter results to ensure all query tokens are present."""
        tokens = [t for t in query.lower().split() if t]
        if not tokens:
            return foods

        filtered: List[Dict[str, Any]] = []
        for f in foods:
            haystack = f"{f.get('description', '')} {f.get('brandOwner', '')} {f.get('fdcId', '')}".lower()
            if all(tok in haystack for tok in tokens):
                filtered.append(f)
        return filtered

    def _show_current_search_page(self) -> None:
        """Display current page of search results."""
        start = (self._search_page - 1) * self._search_page_size
        end = start + self._search_page_size
        slice_results = self._search_results[start:end]
        self._populate_table(slice_results, base_index=start)
        self._prefetch_visible_results(slice_results)

        total_pages = max(1, (len(self._search_results) + self._search_page_size - 1) // self._search_page_size)
        self._set_status(
            f"Se encontraron {len(self._search_results)} resultados (página {self._search_page}/{total_pages})."
        )

    def _update_paging_buttons(self) -> None:
        """Update pagination button states."""
        count = len(self._search_results)
        has_query = bool(self._last_query)
        self.prev_page_button.setEnabled(has_query and self._search_page > 1)
        self.next_page_button.setEnabled(
            has_query and (self._search_page * self._search_page_size < count)
        )

    def _populate_table(self, foods: List[Dict[str, Any]], base_index: int = 0) -> None:
        """Populate search results table."""
        self.table.setRowCount(len(foods))
        for i, food in enumerate(foods):
            fdc_id = str(food.get("fdcId", ""))
            desc = food.get("description", "") or ""
            brand = food.get("brandOwner", "") or ""
            data_type = food.get("dataType", "") or ""

            self.table.setItem(i, 0, QTableWidgetItem(fdc_id))
            self.table.setItem(i, 1, QTableWidgetItem(desc))
            self.table.setItem(i, 2, QTableWidgetItem(brand))
            self.table.setItem(i, 3, QTableWidgetItem(data_type))

    # ==================== Add to Formulation ====================

    def _add_row_to_formulation(self, row: Optional[int] = None) -> None:
        """Add selected search result to formulation."""
        if row is None:
            indexes = self.table.selectionModel().selectedRows()
            if not indexes:
                self._set_status("Selecciona un alimento para agregar.")
                return
            row = indexes[0].row()

        fdc_item = self.table.item(row, 0)
        if not fdc_item:
            return

        try:
            fdc_id = int(fdc_item.text().strip())
        except ValueError:
            self._set_status("ID de alimento inválido.")
            return

        # Ask for quantity
        desc_item = self.table.item(row, 1)
        desc = desc_item.text() if desc_item else f"FDC {fdc_id}"

        amount, ok = QInputDialog.getDouble(
            self,
            "Cantidad",
            f"Cantidad en gramos para '{desc[:50]}...':" if len(desc) > 50 else f"Cantidad en gramos para '{desc}':",
            value=100.0,
            min=0.01,
            max=1000000.0,
            decimals=2,
        )

        if not ok:
            return

        self.ingredient_add_requested.emit(fdc_id, amount)

    # ==================== Prefetching ====================

    def _prefetch_fdc_id(self, fdc_id: Any) -> None:
        """Warm USDA cache for a given FDC ID in background."""
        try:
            fdc_int = int(fdc_id)
        except Exception:
            return

        if fdc_int in self._prefetching_fdc_ids:
            return

        self._prefetching_fdc_ids.add(fdc_int)
        logging.debug(f"Prefetching fdc_id={fdc_int}")

        def on_done(_: object) -> None:
            self._prefetching_fdc_ids.discard(fdc_int)
            logging.debug(f"Prefetch done fdc_id={fdc_int}")

        self._run_in_thread(
            fn=lambda fid=fdc_int: get_food_details(fid, timeout=(3.05, 6.0), detail_format="abridged"),
            args=(),
            on_success=on_done,
            on_error=on_done,
        )

    def _prefetch_visible_results(self, foods: List[Dict[str, Any]], limit: int = 2) -> None:
        """Prefetch details for first visible results."""
        count = 0
        for food in foods:
            fdc_id = food.get("fdcId")
            if fdc_id is None:
                continue
            self._prefetch_fdc_id(fdc_id)
            count += 1
            if count >= limit:
                break

    # ==================== Formulation Preview ====================

    def _refresh_formulation_preview(self) -> None:
        """Refresh the formulation preview table."""
        self.formulation_preview.setRowCount(len(self._formulation_items))
        for i, item in enumerate(self._formulation_items):
            fdc_id = str(item.get("fdc_id", ""))
            desc = item.get("description", "") or ""
            self.formulation_preview.setItem(i, 0, QTableWidgetItem(fdc_id))
            self.formulation_preview.setItem(i, 1, QTableWidgetItem(desc))

    def _show_nutrients_for_selected_preview(self) -> None:
        """Show nutrients for selected preview item."""
        indexes = self.formulation_preview.selectionModel().selectedRows()
        if not indexes:
            self.details_table.setRowCount(0)
            return
        self._show_nutrients_for_row(indexes[0].row())

    def _show_nutrients_for_row(self, row: int) -> None:
        """Show nutrients for a formulation item."""
        if row < 0 or row >= len(self._formulation_items):
            return

        item = self._formulation_items[row]
        nutrients = item.get("nutrients", {})

        self.details_table.setRowCount(len(nutrients))
        for i, (name, data) in enumerate(nutrients.items()):
            amount = data.get("amount", 0)
            unit = data.get("unit", "")
            self.details_table.setItem(i, 0, QTableWidgetItem(name))
            self.details_table.setItem(i, 1, QTableWidgetItem(f"{amount:.2f}"))
            self.details_table.setItem(i, 2, QTableWidgetItem(unit))

    # ==================== Thread Management ====================

    def _run_in_thread(
        self,
        fn,
        args: tuple,
        on_success,
        on_error,
    ) -> None:
        """Run a function in a background thread."""
        thread = QThread()
        worker = ApiWorker(fn, *args)
        worker.moveToThread(thread)

        worker.finished.connect(on_success)
        worker.error.connect(on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.started.connect(worker.run)

        # Cleanup
        thread.finished.connect(lambda: self._cleanup_thread(thread, worker))

        self._threads.append(thread)
        self._workers.append(worker)
        thread.start()

    def _cleanup_thread(self, thread: QThread, worker: QObject) -> None:
        """Clean up finished thread and worker."""
        if thread in self._threads:
            self._threads.remove(thread)
        if worker in self._workers:
            self._workers.remove(worker)
        thread.deleteLater()
        worker.deleteLater()

    # ==================== Utilities ====================

    def _set_status(self, message: str) -> None:
        """Set status message and emit signal."""
        self.status_label.setText(message)
        self.status_message.emit(message)
