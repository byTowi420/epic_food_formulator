"""Formulation tab UI component with integrated presenter logic."""

from typing import Any, Dict, List, Optional
from pathlib import Path
from decimal import Decimal
import json
import logging
import unicodedata

import pandas as pd

from PySide6.QtCore import Qt, Signal, QThread, QObject
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from ui.presenters.formulation_presenter import FormulationPresenter
from ui.workers import ApiWorker, ImportWorker, AddWorker
from services.usda_api import get_food_details
from services.nutrient_normalizer import normalize_nutrients


class FormulationTab(QWidget):
    """Tab for managing ingredient formulation and nutritional totals.

    Signals:
        formulation_changed: Emitted when formulation is modified
        totals_updated: Emitted with calculated totals dict
        status_message: Emitted to display status messages
    """

    # Signals for cross-tab communication
    formulation_changed = Signal()  # Emitted when ingredients change
    totals_updated = Signal(dict)  # Emitted with totals data
    status_message = Signal(str)
    label_update_requested = Signal()  # Request label tab to update

    def __init__(
        self,
        formulation_presenter: Optional[FormulationPresenter] = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        # Presenter
        self._presenter = formulation_presenter or FormulationPresenter()

        # State
        self._quantity_mode = "g"  # "g" or "%"
        self._nutrient_export_flags: Dict[str, bool] = {}
        self._last_path: Optional[str] = None
        self._lock_column_index = 4

        # Thread management
        self._threads: list[QThread] = []
        self._workers: list[QObject] = []
        self._current_import_worker: Optional[ImportWorker] = None

        # Import settings
        self._import_max_attempts = 4
        self._import_read_timeout = 8.0

        self._build_ui()
        self._connect_signals()

    @property
    def presenter(self) -> FormulationPresenter:
        """Get the formulation presenter."""
        return self._presenter

    @property
    def quantity_mode(self) -> str:
        """Get current quantity mode ('g' or '%')."""
        return self._quantity_mode

    @property
    def nutrient_export_flags(self) -> Dict[str, bool]:
        """Get nutrient export flags."""
        return self._nutrient_export_flags

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Header with import/export and formula name
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

        # Formulation table
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

        # Action buttons
        buttons_layout = QHBoxLayout()
        self.edit_quantity_button = QPushButton("Editar cantidad seleccionada")
        self.remove_formulation_button = QPushButton(
            "Eliminar ingrediente seleccionado"
        )
        buttons_layout.addWidget(self.edit_quantity_button)
        buttons_layout.addWidget(self.remove_formulation_button)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        # Totals section
        layout.addWidget(
            QLabel(
                "Totales nutricionales (asumiendo valores por 100 g del alimento origen)"
            )
        )
        self.totals_table = QTableWidget(0, 4)
        self.totals_table.setHorizontalHeaderLabels(
            ["Nutriente", "Total", "Unidad", "Exportar"]
        )

        # Add icon to export header
        export_header = QTableWidgetItem("Exportar")
        export_header.setIcon(self._create_question_icon())
        export_header.setToolTip(
            "Los nutrientes seleccionados serán exportados al excel"
        )
        self.totals_table.setHorizontalHeaderItem(3, export_header)
        self.totals_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.totals_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.totals_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.totals_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.totals_table)

        # Export buttons
        export_buttons_layout = QHBoxLayout()
        self.toggle_export_button = QPushButton("Deseleccionar todos")
        self.export_excel_button = QPushButton("Exportar a Excel")
        export_buttons_layout.addStretch()
        export_buttons_layout.addWidget(self.toggle_export_button)
        export_buttons_layout.addWidget(self.export_excel_button)
        export_buttons_layout.addStretch()
        layout.addLayout(export_buttons_layout)

        self._set_default_column_widths()
        self._setup_copy_shortcut()

    def _connect_signals(self) -> None:
        """Connect internal signals to handlers."""
        self.edit_quantity_button.clicked.connect(self._on_edit_quantity_clicked)
        self.remove_formulation_button.clicked.connect(self._on_remove_clicked)
        self.quantity_mode_selector.currentIndexChanged.connect(self._on_quantity_mode_changed)
        self.formulation_table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.formulation_table.itemChanged.connect(self._on_item_changed)
        self.totals_table.itemChanged.connect(self._on_totals_checkbox_changed)
        self.toggle_export_button.clicked.connect(self._on_toggle_export_clicked)
        self.export_excel_button.clicked.connect(self._on_export_excel_clicked)
        self.export_state_button.clicked.connect(self._on_export_state_clicked)
        self.import_state_button.clicked.connect(self._on_import_state_clicked)

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

    def _set_default_column_widths(self) -> None:
        """Set sensible initial column widths while keeping them resizable."""
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

    def _setup_copy_shortcut(self) -> None:
        """Setup Ctrl+C shortcut for tables."""
        for table in (self.formulation_table, self.totals_table):
            shortcut = QShortcut(QKeySequence.Copy, table)
            shortcut.activated.connect(lambda t=table: self._copy_selection(t))

    def _copy_selection(self, table: QTableWidget) -> None:
        """Copy selected cells to clipboard."""
        selection = table.selectedRanges()
        if not selection:
            return

        lines = []
        for sel in selection:
            for row in range(sel.topRow(), sel.bottomRow() + 1):
                row_vals = []
                for col in range(sel.leftColumn(), sel.rightColumn() + 1):
                    item = table.item(row, col)
                    row_vals.append(item.text() if item else "")
                lines.append("\t".join(row_vals))

        QApplication.clipboard().setText("\n".join(lines))

    # ==================== Add Ingredient ====================

    def add_ingredient(self, fdc_id: int, amount_g: float) -> None:
        """Add an ingredient to the formulation (called from SearchTab signal)."""
        self._set_status(f"Cargando detalles de FDC {fdc_id}...")

        def fetch_and_add():
            details = get_food_details(fdc_id)
            return details

        def on_success(details: dict):
            try:
                # Normalize nutrients
                nutrients = normalize_nutrients(details.get("foodNutrients", []))

                # Create UI item
                item = {
                    "fdc_id": fdc_id,
                    "description": details.get("description", ""),
                    "brand": details.get("brandOwner", "") or "",
                    "data_type": details.get("dataType", ""),
                    "amount_g": amount_g,
                    "locked": False,
                    "nutrients": nutrients,
                }

                # Add to presenter
                self._presenter.add_ingredient(fdc_id, amount_g)

                self._refresh_views()
                self._set_status(f"Agregado: {item['description'][:50]}")
                self.formulation_changed.emit()
                self.label_update_requested.emit()

            except Exception as e:
                self._set_status(f"Error al agregar: {e}")
                logging.error(f"Error adding ingredient: {e}")

        def on_error(error: str):
            self._set_status(f"Error: {error}")
            logging.error(f"Error fetching food details: {error}")

        self._run_in_thread(fetch_and_add, (), on_success, on_error)

    def remove_ingredient(self, index: int) -> None:
        """Remove ingredient at index."""
        if index < 0 or index >= self._presenter.get_ingredient_count():
            return

        self._presenter.remove_ingredient(index)
        self._refresh_views()
        self.formulation_changed.emit()
        self.label_update_requested.emit()
        self._set_status("Ingrediente eliminado.")

    # ==================== Handlers ====================

    def _on_edit_quantity_clicked(self) -> None:
        """Edit quantity of selected ingredient."""
        indexes = self.formulation_table.selectionModel().selectedRows()
        if not indexes:
            self._set_status("Selecciona un ingrediente para editar.")
            return
        self._edit_quantity_for_row(indexes[0].row())

    def _on_remove_clicked(self) -> None:
        """Remove selected ingredients."""
        indexes = self.formulation_table.selectionModel().selectedRows()
        if not indexes:
            self._set_status("Selecciona un ingrediente para eliminar.")
            return

        # Remove in reverse order
        rows = sorted([idx.row() for idx in indexes], reverse=True)
        for row in rows:
            self.remove_ingredient(row)

    def _on_quantity_mode_changed(self) -> None:
        """Switch between grams and percent modes."""
        self._quantity_mode = "g" if self.quantity_mode_selector.currentIndex() == 0 else "%"
        self._refresh_views()
        mode_text = "gramos (g)" if self._quantity_mode == "g" else "porcentaje (%)"
        self._set_status(f"Modo de cantidad cambiado a {mode_text}.")

    def _on_cell_double_clicked(self, row: int, column: int) -> None:
        """Handle double click on formulation table."""
        # Only allow editing amount columns
        if column not in (2, 3):
            return
        self._edit_quantity_for_row(row)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Handle lock checkbox toggle."""
        if item.column() != self._lock_column_index:
            return
        if self._quantity_mode == "g":
            return

        row = item.row()
        if row < 0 or row >= self._presenter.get_ingredient_count():
            return

        desired_locked = item.checkState() == Qt.Checked

        # Prevent all items from being locked
        if desired_locked and self._presenter.get_locked_count(exclude_index=row) >= (
            self._presenter.get_ingredient_count() - 1
        ):
            self.formulation_table.blockSignals(True)
            item.setCheckState(Qt.Unchecked)
            self.formulation_table.blockSignals(False)
            self._set_status("Debe quedar al menos un ingrediente sin fijar.")
            return

        try:
            self._presenter.toggle_lock(row)
        except Exception as e:
            logging.error(f"Error toggling lock: {e}")

        self._refresh_views()

    def _on_totals_checkbox_changed(self, item: QTableWidgetItem) -> None:
        """Handle export checkbox toggle in totals table."""
        if item.column() != 3:
            return

        nutrient_item = self.totals_table.item(item.row(), 0)
        if not nutrient_item:
            return

        nutrient_name = nutrient_item.text()
        self._nutrient_export_flags[nutrient_name] = item.checkState() == Qt.Checked

    def _on_toggle_export_clicked(self) -> None:
        """Toggle all export checkboxes."""
        # Check if any are checked
        any_checked = any(self._nutrient_export_flags.values())

        # Toggle all
        self.totals_table.blockSignals(True)
        for row in range(self.totals_table.rowCount()):
            checkbox = self.totals_table.item(row, 3)
            if checkbox:
                new_state = Qt.Unchecked if any_checked else Qt.Checked
                checkbox.setCheckState(new_state)
                nutrient_item = self.totals_table.item(row, 0)
                if nutrient_item:
                    self._nutrient_export_flags[nutrient_item.text()] = not any_checked
        self.totals_table.blockSignals(False)

        self.toggle_export_button.setText(
            "Seleccionar todos" if any_checked else "Deseleccionar todos"
        )

    def _on_export_excel_clicked(self) -> None:
        """Export formulation to Excel."""
        if not self._presenter.has_ingredients():
            QMessageBox.information(
                self,
                "Exportar a Excel",
                "No hay ingredientes en la formulación para exportar.",
            )
            return

        default_name = f"{self._safe_formula_name()}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar formulación a Excel",
            default_name,
            "Archivos de Excel (*.xlsx)",
        )
        if not path:
            return

        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            self._presenter.export_to_excel(path)
            QMessageBox.information(
                self,
                "Exportado",
                f"Archivo guardado en:\n{path}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error al exportar",
                f"No se pudo exportar el archivo:\n{exc}",
            )

    def _on_export_state_clicked(self) -> None:
        """Export formulation state to JSON."""
        if not self._presenter.has_ingredients():
            QMessageBox.information(
                self,
                "Exportar formulación",
                "No hay ingredientes en la formulación para exportar.",
            )
            return

        default_name = f"{self._safe_formula_name()}.json"
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

        try:
            # Update presenter with current formula name
            self._presenter.formulation_name = self.formula_name_input.text() or "Formulación"

            # Save via presenter
            self._presenter.save_to_file(path)

            # Add UI metadata
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            data["quantity_mode"] = self._quantity_mode
            data["nutrient_export_flags"] = self._nutrient_export_flags
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            self._set_status(f"Formulación exportada en {path}")

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error al exportar",
                f"No se pudo exportar la formulación:\n{exc}",
            )

    def _on_import_state_clicked(self) -> None:
        """Import formulation state from JSON or Excel."""
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
            self._import_from_json(path)
        elif ext in (".xlsx", ".xls"):
            self._import_from_excel(path)
        else:
            QMessageBox.warning(
                self,
                "Formato no soportado",
                "Selecciona un archivo .json o .xlsx",
            )

    def _import_from_json(self, path: str) -> None:
        """Import formulation from JSON file."""
        try:
            self._presenter.load_from_file(path)

            # Read UI metadata
            data = json.loads(Path(path).read_text(encoding="utf-8"))

            # Apply quantity mode
            mode = data.get("quantity_mode", "g")
            self._quantity_mode = "g" if mode != "%" else "%"
            self.quantity_mode_selector.setCurrentIndex(0 if self._quantity_mode == "g" else 1)

            # Apply export flags
            flags = data.get("nutrient_export_flags", {})
            self._nutrient_export_flags = {k: bool(v) for k, v in flags.items()}

            # Apply formula name
            name = data.get("formula_name", "")
            if name:
                self.formula_name_input.setText(name)

            self._refresh_views()
            self.formulation_changed.emit()
            self.label_update_requested.emit()
            self._set_status(f"Formulación importada desde {path}")

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error al importar",
                f"No se pudo importar la formulación:\n{exc}",
            )

    def _import_from_excel(self, path: str) -> None:
        """Import formulation from Excel file."""
        def _read(sheet, header_row: int) -> pd.DataFrame:
            return pd.read_excel(path, sheet_name=sheet, header=header_row)

        df: pd.DataFrame | None = None
        # Prefer sheet "Ingredientes" with headers on second row
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
            return

        # Normalize column names for matching
        def normalize_label(s: str) -> str:
            s = s.lower().strip()
            s = unicodedata.normalize("NFD", s)
            s = "".join(c for c in s if unicodedata.category(c) != "Mn")
            return s

        cols_norm: Dict[str, str] = {normalize_label(c): c for c in df.columns}
        fdc_candidates = ["fdc id", "fdc_id", "fdcid", "fdc"]
        amount_candidates = [
            "cantidad (g)", "cantidad g", "cantidad", "cantidad gramos",
            "cantidad en gramos", "amount g", "amount_g", "g", "grams",
        ]

        fdc_col = next((cols_norm[c] for c in fdc_candidates if c in cols_norm), None)
        amount_col = next((cols_norm[c] for c in amount_candidates if c in cols_norm), None)

        if not fdc_col or not amount_col:
            QMessageBox.warning(
                self,
                "Columnas faltantes",
                "Se requieren columnas FDC ID y Cantidad (g).",
            )
            return

        # Parse rows
        items_to_add: List[tuple[int, float]] = []
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
            items_to_add.append((fdc_int, amt))

        if not items_to_add:
            QMessageBox.warning(
                self,
                "Sin ingredientes",
                "No se encontraron filas válidas con FDC ID y Cantidad (g).",
            )
            return

        # Clear existing formulation and add new items
        self._presenter.clear()
        self.formula_name_input.setText(Path(path).stem)

        self._set_status(f"Importando {len(items_to_add)} ingredientes desde Excel...")

        # Add items one by one (this will fetch from USDA API)
        for fdc_id, amount in items_to_add:
            self.add_ingredient(fdc_id, amount)

    # ==================== View Updates ====================

    def _refresh_views(self) -> None:
        """Refresh formulation table and totals."""
        self._refresh_formulation_table()
        self._refresh_totals_table()

    def _refresh_formulation_table(self) -> None:
        """Refresh the formulation ingredients table."""
        items = self._presenter.get_ui_items()
        total_weight = self._presenter.get_total_weight()

        self.formulation_table.blockSignals(True)
        self.formulation_table.setRowCount(len(items))

        for i, item in enumerate(items):
            fdc_id = str(item.get("fdc_id", ""))
            desc = item.get("description", "") or ""
            amount_g = float(item.get("amount_g", 0))
            locked = item.get("locked", False)
            brand = item.get("brand", "") or ""

            # Calculate percentage
            pct = (amount_g / total_weight * 100) if total_weight > 0 else 0

            self.formulation_table.setItem(i, 0, QTableWidgetItem(fdc_id))
            self.formulation_table.setItem(i, 1, QTableWidgetItem(desc))
            self.formulation_table.setItem(i, 2, QTableWidgetItem(f"{amount_g:.2f}"))
            self.formulation_table.setItem(i, 3, QTableWidgetItem(f"{pct:.2f}"))

            # Lock checkbox
            lock_item = QTableWidgetItem()
            lock_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            lock_item.setCheckState(Qt.Checked if locked else Qt.Unchecked)
            self.formulation_table.setItem(i, 4, lock_item)

            self.formulation_table.setItem(i, 5, QTableWidgetItem(brand))

        self.formulation_table.blockSignals(False)

    def _refresh_totals_table(self) -> None:
        """Refresh the nutrient totals table."""
        if not self._presenter.has_ingredients():
            self.totals_table.setRowCount(0)
            return

        try:
            totals = self._presenter.calculate_totals()
        except Exception as e:
            logging.error(f"Error calculating totals: {e}")
            return

        self.totals_table.blockSignals(True)
        self.totals_table.setRowCount(len(totals))

        for i, (nutrient, data) in enumerate(totals.items()):
            amount = data.get("amount", 0)
            unit = data.get("unit", "")

            self.totals_table.setItem(i, 0, QTableWidgetItem(nutrient))
            self.totals_table.setItem(i, 1, QTableWidgetItem(f"{amount:.2f}"))
            self.totals_table.setItem(i, 2, QTableWidgetItem(unit))

            # Export checkbox
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            is_checked = self._nutrient_export_flags.get(nutrient, True)
            checkbox.setCheckState(Qt.Checked if is_checked else Qt.Unchecked)
            self.totals_table.setItem(i, 3, checkbox)

        self.totals_table.blockSignals(False)
        self.totals_updated.emit(totals)

    def _edit_quantity_for_row(self, row: int) -> None:
        """Open dialog to edit quantity for a row."""
        if row < 0 or row >= self._presenter.get_ingredient_count():
            return

        item = self._presenter.get_ui_item(row)
        current_amount = float(item.get("amount_g", 100))
        desc = item.get("description", "")[:50]

        if self._quantity_mode == "g":
            new_amount, ok = QInputDialog.getDouble(
                self,
                "Editar cantidad",
                f"Nueva cantidad en gramos para '{desc}':",
                value=current_amount,
                min=0.01,
                max=1000000.0,
                decimals=2,
            )
        else:
            total = self._presenter.get_total_weight()
            current_pct = (current_amount / total * 100) if total > 0 else 0
            new_pct, ok = QInputDialog.getDouble(
                self,
                "Editar porcentaje",
                f"Nuevo porcentaje para '{desc}':",
                value=current_pct,
                min=0.01,
                max=100.0,
                decimals=2,
            )
            if ok:
                new_amount = total * new_pct / 100

        if not ok:
            return

        try:
            self._presenter.update_ingredient_amount(row, new_amount)
            self._refresh_views()
            self.formulation_changed.emit()
            self.label_update_requested.emit()
        except Exception as e:
            self._set_status(f"Error al actualizar: {e}")

    # ==================== Utilities ====================

    def _safe_formula_name(self) -> str:
        """Get safe filename from formula name."""
        name = self.formula_name_input.text().strip()
        if not name:
            name = "formulacion"
        # Remove invalid characters
        for char in '<>:"/\\|?*':
            name = name.replace(char, "_")
        return name[:50]

    def _set_status(self, message: str) -> None:
        """Emit status message."""
        self.status_message.emit(message)

    def _run_in_thread(self, fn, args: tuple, on_success, on_error) -> None:
        """Run a function in a background thread."""
        thread = QThread()
        worker = ApiWorker(fn, *args)
        worker.moveToThread(thread)

        worker.finished.connect(on_success)
        worker.error.connect(on_error)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.started.connect(worker.run)

        thread.finished.connect(lambda: self._cleanup_thread(thread, worker))

        self._threads.append(thread)
        self._workers.append(worker)
        thread.start()

    def _cleanup_thread(self, thread: QThread, worker: QObject) -> None:
        """Clean up finished thread."""
        if thread in self._threads:
            self._threads.remove(thread)
        if worker in self._workers:
            self._workers.remove(worker)
        thread.deleteLater()
        worker.deleteLater()

    # ==================== Public Methods for External Sync ====================

    def get_formulation_items(self) -> List[Dict[str, Any]]:
        """Get current formulation items for other tabs."""
        return self._presenter.get_ui_items()

    def refresh(self) -> None:
        """Public method to refresh views."""
        self._refresh_views()
