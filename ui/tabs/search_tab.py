from __future__ import annotations

import logging
from typing import Any, Dict, List

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
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.nutrient_normalizer import augment_fat_nutrients, normalize_nutrients
from services.usda_api import get_food_details


class SearchTabMixin:
    """Search tab UI and behavior."""

    # ---- State ----
    def _init_search_state(self) -> None:
        """Initialize search tab state."""
        self._prefetching_fdc_ids: set[int] = set()
        self.search_page = 1
        self.search_page_size = 25
        self.search_fetch_page_size = 200
        self.search_max_pages = 5
        self.search_results: List[Dict[str, Any]] = []
        self.last_query = ""
        self.last_include_brands = False
        self._last_results_count = 0

    # ---- UI build ----
    def _build_search_tab_ui(self) -> None:
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
        self._apply_table_selection_bar(self.table)
    
        self.details_table = QTableWidget(0, 3)
        self.details_table.setHorizontalHeaderLabels(
            ["Nutriente", "Cantidad", "Unidad"]
        )
        self.details_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.details_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.details_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.details_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.details_table.horizontalHeader().setStretchLastSection(True)
        self._apply_table_selection_bar(self.details_table)
    
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
        self._apply_table_selection_bar(self.formulation_preview)
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

    # ---- Search actions ----
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
            # Use presenter instead of direct API call
            include_branded = data_types is None
            batch = self.search_presenter.search(
                query=query,
                page_size=self.search_fetch_page_size,
                include_branded=include_branded,
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


    def on_formulation_preview_double_clicked(self, row: int, column: int) -> None:
        """Allow quick edit from the preview table."""
        if not self._can_edit_column(column):
            return
        self._edit_quantity_for_row(row)


    def on_preview_selection_changed(self) -> None:
        """Update nutrients panel when preview selection changes."""
        self._show_nutrients_for_selected_preview()


    # ---- Table helpers ----
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
        nutrients = self._sort_nutrients_for_display(augment_fat_nutrients(nutrients or []))
        self.details_table.setRowCount(0)

        row_idx = 0
        for n in nutrients:
            if n.get("amount") is None:
                continue
            self.details_table.insertRow(row_idx)
            nut = n.get("nutrient") or {}
            name = nut.get("name", "") or ""
            unit = nut.get("unitName", "") or ""
            amount = n.get("amount")
            amount_text = "" if amount is None else str(amount)

            self.details_table.setItem(row_idx, 0, QTableWidgetItem(name))
            self.details_table.setItem(row_idx, 1, QTableWidgetItem(amount_text))
            self.details_table.setItem(row_idx, 2, QTableWidgetItem(unit))
            row_idx += 1


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
        nutrients = normalize_nutrients(
            details.get("foodNutrients", []) or [], details.get("dataType")
        )
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

