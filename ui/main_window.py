from typing import Any, Dict, List
from pathlib import Path
import json
import re
import unicodedata

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QHeaderView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Alignment

from services.usda_api import USDAApiError, get_food_details, search_foods


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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Food Formulator - Proto")
        self.resize(900, 600)
        self._threads: list[QThread] = []
        self._workers: list[ApiWorker] = []
        self.formulation_items: List[Dict] = []
        self.quantity_mode: str = "g"
        self.amount_g_column_index = 2
        self.percent_column_index = 3
        self.lock_column_index = 4
        self.nutrient_export_flags: Dict[str, bool] = {}

        self._build_ui()

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

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Buscar alimento (ej: apple, rice, cheese)..."
        )
        self.search_button = QPushButton("Buscar")

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        fdc_layout = QHBoxLayout()
        self.fdc_id_input = QLineEdit()
        self.fdc_id_input.setPlaceholderText("Buscar por FDC ID (ej: 169910)")
        self.fdc_id_button = QPushButton("Cargar FDC ID")
        fdc_layout.addWidget(self.fdc_id_input)
        fdc_layout.addWidget(self.fdc_id_button)

        self.add_button = QPushButton("Agregar seleccionado a formulación")

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
        layout.addLayout(fdc_layout)
        layout.addWidget(self.add_button)
        layout.addWidget(self.status_label)

        splitter = QSplitter(Qt.Vertical)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["FDC ID", "Descripción", "Marca / Origen", "Tipo de dato"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.table)

        self.details_table = QTableWidget(0, 3)
        self.details_table.setHorizontalHeaderLabels(
            ["Nutriente", "Cantidad", "Unidad"]
        )
        self.details_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.details_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.details_table.setSelectionMode(QTableWidget.NoSelection)
        self.details_table.horizontalHeader().setStretchLastSection(True)
        splitter.addWidget(self.details_table)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        layout.addWidget(QLabel("Ingredientes en formulación (vista rápida)"))
        self.formulation_preview = QTableWidget(0, 5)
        self.formulation_preview.setHorizontalHeaderLabels(
            ["FDC ID", "Ingrediente", "Cantidad (g)", "Cantidad (%)", "Fijar %"]
        )
        self.formulation_preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self.formulation_preview.setSelectionBehavior(QTableWidget.SelectRows)
        self.formulation_preview.setSelectionMode(QTableWidget.SingleSelection)
        self.formulation_preview.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.formulation_preview)

        self.remove_preview_button = QPushButton("Eliminar ingrediente seleccionado")
        layout.addWidget(self.remove_preview_button)

        self.search_button.clicked.connect(self.on_search_clicked)
        self.search_input.returnPressed.connect(self.on_search_clicked)
        self.table.cellDoubleClicked.connect(self.on_result_double_clicked)
        self.add_button.clicked.connect(self.on_add_selected_clicked)
        self.fdc_id_button.clicked.connect(self.on_fdc_search_clicked)
        self.fdc_id_input.returnPressed.connect(self.on_fdc_search_clicked)
        self.remove_preview_button.clicked.connect(self.on_remove_preview_clicked)
        self.formulation_preview.cellDoubleClicked.connect(
            self.on_formulation_preview_double_clicked
        )
        self.formulation_preview.itemChanged.connect(self.on_lock_toggled_from_table)
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

            self.table.setColumnWidth(0, 90)   # FDC ID
            self.table.setColumnWidth(1, 340)  # Descripcion
            self.table.setColumnWidth(2, 200)  # Marca / Origen
            self.table.setColumnWidth(3, 120)  # Tipo de dato

            self.details_table.setColumnWidth(0, 220)  # Nutriente
            self.details_table.setColumnWidth(1, 120)  # Cantidad
            self.details_table.setColumnWidth(2, 80)   # Unidad

            self.formulation_preview.setColumnWidth(0, 90)   # FDC ID
            self.formulation_preview.setColumnWidth(1, 320)  # Descripcion
            self.formulation_preview.setColumnWidth(2, 120)  # Cantidad
            self.formulation_preview.setColumnWidth(3, 70)   # Fijar %
            return

        for table in (self.formulation_table, self.totals_table):
            header = table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.Interactive)

        self.formulation_table.setColumnWidth(0, 90)   # FDC ID
        self.formulation_table.setColumnWidth(1, 320)  # Descripcion
        self.formulation_table.setColumnWidth(2, 120)  # Cantidad
        self.formulation_table.setColumnWidth(3, 70)   # Fijar %
        self.formulation_table.setColumnWidth(4, 200)  # Marca / Origen

        self.totals_table.setColumnWidth(0, 220)  # Nutriente
        self.totals_table.setColumnWidth(1, 100)  # Total
        self.totals_table.setColumnWidth(2, 70)   # Unidad
        self.totals_table.setColumnWidth(3, 90)   # Exportar

    def on_search_clicked(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText("Ingresa un termino de busqueda.")
            return

        self.status_label.setText("Buscando en FoodData Central...")
        self.search_button.setEnabled(False)

        self._run_in_thread(
            fn=search_foods,
            args=(query,),
            on_success=self._on_search_success,
            on_error=self._on_search_error,
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
        self._add_row_to_formulation(row)

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
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar formulacion a Excel",
            default_name,
            "Archivos de Excel (*.xlsx)",
        )
        if not path:
            return

        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

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
            default_name,
            "Archivos JSON (*.json)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"

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
            "",
            "Archivos JSON (*.json);;Archivos Excel (*.xlsx)",
        )
        if not path:
            return

        ext = Path(path).suffix.lower()
        if ext == ".json":
            success = self._load_state_from_json(path)
        elif ext in (".xlsx", ".xls"):
            success = self._load_state_from_excel(path)
        else:
            QMessageBox.warning(
                self,
                "Formato no soportado",
                "Selecciona un archivo .json o .xlsx",
            )
            return

        if success:
            self._refresh_formulation_views()
            self.status_label.setText(f"Formulación importada desde {path}")

    def _load_state_from_json(self, path: str) -> bool:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Error al importar",
                f"No se pudo leer el archivo:\n{exc}",
            )
            return False

        if not isinstance(data, dict):
            QMessageBox.warning(
                self,
                "Formato inválido",
                "El archivo no contiene una formulación válida.",
            )
            return False

        items = data.get("items") or []
        if not isinstance(items, list) or not items:
            QMessageBox.warning(
                self,
                "Formato inválido",
                "El archivo no contiene ingredientes válidos.",
            )
            return False

        base_items: list[Dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            base_items.append(
                {
                    "fdc_id": item.get("fdc_id") or item.get("fdcId"),
                    "amount_g": float(item.get("amount_g", 0.0) or 0.0),
                    "locked": bool(item.get("locked", False)),
                    "description": item.get("description", ""),
                    "brand": item.get("brand", ""),
                    "data_type": item.get("data_type", ""),
                }
            )

        hydrated = self._hydrate_items(base_items)
        if hydrated is None:
            return False

        self.formulation_items = hydrated

        flags = data.get("nutrient_export_flags")
        self.nutrient_export_flags = (
            {k: bool(v) for k, v in flags.items()} if isinstance(flags, dict) else {}
        )

        mode = data.get("quantity_mode", "g")
        self.quantity_mode = "g" if mode != "%" else "%"
        self.quantity_mode_selector.setCurrentIndex(
            0 if self.quantity_mode == "g" else 1
        )

        self.formula_name_input.setText(data.get("formula_name", ""))
        return True

    def _load_state_from_excel(self, path: str) -> bool:
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
            return False

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
            return False

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
            return False

        hydrated = self._hydrate_items(base_items)
        if hydrated is None:
            return False

        self.formulation_items = hydrated
        self.nutrient_export_flags = {}
        self.quantity_mode = "g"
        self.quantity_mode_selector.setCurrentIndex(0)
        if not self.formula_name_input.text().strip():
            self.formula_name_input.setText(Path(path).stem)
        return True

    def _populate_table(self, foods) -> None:
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

    def _populate_details_table(self, nutrients) -> None:
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
            ["FDC ID", "Ingrediente", "Cantidad (g)", "Cantidad (%)", "Fijar %"]
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

    def _nutrients_by_header(self, nutrients: List[Dict[str, Any]]) -> Dict[str, float]:
        """Build a mapping of template header -> nutrient amount (per 100 g)."""
        out: Dict[str, float] = {}
        for entry in nutrients:
            amount = entry.get("amount")
            if amount is None:
                continue
            nut = entry.get("nutrient") or {}
            name = nut.get("name", "")
            unit = nut.get("unitName") or self._infer_unit(nut) or ""
            header = f"{name} ({unit})" if unit else name
            if header:
                out[header] = amount
        return out

    def _collect_nutrient_columns(self) -> tuple[list[str], Dict[str, str]]:
        """
        Collect ordered nutrient headers and their categories.
        Category is taken from USDA "group" rows (amount/unit missing) when present.
        """
        headers: list[str] = []
        categories: Dict[str, str] = {}
        preferred_order = [
            "Proximates",
            "Carbohydrates",
            "Minerals",
            "Vitamins and Other Components",
            "Lipids",
            "Amino acids",
        ]
        category_seen: Dict[str, list[str]] = {cat: [] for cat in preferred_order}

        for item in self.formulation_items:
            current_category = "Nutrientes"
            for entry in item.get("nutrients", []):
                nut = entry.get("nutrient") or {}
                name = nut.get("name", "") or ""
                unit = nut.get("unitName") or self._infer_unit(nut) or ""
                amount = entry.get("amount")
                nut_key = self._nutrient_key(nut)
                if nut_key and not self.nutrient_export_flags.get(nut_key, True):
                    continue

                if amount is None and name:
                    current_category = name
                    continue

                if amount is None:
                    continue

                header = f"{name} ({unit})" if unit else name
                if not header:
                    continue
                categories[header] = current_category
                if header not in category_seen.setdefault(current_category, []):
                    category_seen[current_category].append(header)

        # Flatten by preferred category order then any remaining categories
        ordered_headers: list[str] = []
        for cat in preferred_order + [c for c in category_seen if c not in preferred_order]:
            ordered_headers.extend(category_seen.get(cat, []))

        # Preserve only those actually present
        return [h for h in ordered_headers if h in categories], categories

    def _split_header_unit(self, header: str) -> tuple[str, str]:
        if header.endswith(")") and " (" in header:
            name, unit = header.rsplit(" (", 1)
            return name, unit[:-1]
        return header, ""

    def _hydrate_items(self, items: list[Dict[str, Any]]) -> list[Dict[str, Any]] | None:
        """Fetch USDA details for items to populate description/nutrients."""
        hydrated: list[Dict[str, Any]] = []
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

            try:
                details = get_food_details(fdc_id_int)
            except Exception as exc:  # noqa: BLE001 - surface to user
                QMessageBox.critical(
                    self,
                    "Error al cargar ingrediente",
                    f"No se pudo cargar el FDC {fdc_id_int}:\n{exc}",
                )
                return None

            hydrated.append(
                {
                    "fdc_id": fdc_id_int,
                    "description": details.get("description", "")
                    or item.get("description", ""),
                    "brand": details.get("brandOwner", "") or item.get("brand", ""),
                    "data_type": details.get("dataType", "") or item.get("data_type", ""),
                    "amount_g": float(item.get("amount_g", 0.0) or 0.0),
                    "nutrients": details.get("foodNutrients", []) or [],
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
        """Refresh both formulation tables with current items."""
        self._update_quantity_headers()
        total_weight = self._total_weight()
        tables = [
            (self.formulation_preview, False),
            (self.formulation_table, True),
        ]
        for table, include_brand in tables:
            table.blockSignals(True)
            table.setRowCount(len(self.formulation_items))
            for idx, item in enumerate(self.formulation_items):
                self.formulation_items[idx].setdefault("locked", False)
                amount_g = item.get("amount_g", 0.0) or 0.0
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

                if include_brand:
                    cells.append(QTableWidgetItem(item.get("brand", "")))

                for col, cell in enumerate(cells):
                    table.setItem(idx, col, cell)

                self._apply_column_state(table, idx)
            table.blockSignals(False)

    def _populate_totals_table(self) -> None:
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
        self._populate_formulation_tables()
        self._populate_totals_table()

    def _export_formulation_to_excel(self, filepath: str) -> None:
        """Build Excel from scratch with nutrient categories as in USDA view."""
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

        nutrient_headers, header_categories = self._collect_nutrient_columns()

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

            nut_map = self._nutrients_by_header(item.get("nutrients", []))
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
        totals: Dict[str, Dict[str, Any]] = {}
        total_weight = self._total_weight()
        for item in self.formulation_items:
            qty = item.get("amount_g", 0) or 0
            for nutrient in item.get("nutrients", []):
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
        return totals

    def _nutrient_key(self, nutrient: Dict[str, Any]) -> str:
        """
        Build a consistent key for nutrients, preferring id then number then name.
        This avoids duplicates when some records lack unitName (Foundation vs SR).
        """
        if "id" in nutrient and nutrient["id"] is not None:
            return f"id:{nutrient['id']}"
        if nutrient.get("number"):
            return f"num:{nutrient['number']}"
        name = nutrient.get("name", "").strip().lower()
        return f"name:{name}" if name else ""

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
        try:
            return float(rank)
        except (TypeError, ValueError):
            return float(fallback)

    def _add_row_to_formulation(self, row: int | None = None) -> None:
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
        self._run_in_thread(
            fn=get_food_details,
            args=(int(fdc_id_text),),
            on_success=lambda details, m=mode, v=value: self._on_add_details_loaded(
                details, m, v
            ),
            on_error=self._on_add_error,
        )

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
        self._populate_table(foods)
        self.status_label.setText(f"Se encontraron {len(foods)} resultados.")
        self.search_button.setEnabled(True)

    def _on_search_error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")
        self.search_button.setEnabled(True)

    def _on_details_success(self, details) -> None:
        nutrients = details.get("foodNutrients", []) or []
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
        nutrients = details.get("foodNutrients", []) or []
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
        msg_value = (
            self._format_amount_for_status(new_item.get("amount_g", 0.0))
            if mode == "g"
            else f"{value:.2f} %"
        )
        self.status_label.setText(
            f"Agregado {fdc_id} - {desc} ({msg_value})"
        )
        self.add_button.setEnabled(True)

    def _on_add_error(self, message: str) -> None:
        self.status_label.setText(f"Error al agregar: {message}")
        self.add_button.setEnabled(True)

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
