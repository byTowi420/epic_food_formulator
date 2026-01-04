from __future__ import annotations

import json
import logging
import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils import get_column_letter

from PySide6.QtCore import QCoreApplication, QItemSelectionModel, QThread, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from services.nutrient_normalizer import (
    augment_fat_nutrients,
    canonical_alias_name,
    canonical_unit,
    normalize_nutrients,
)
from services.usda_api import get_food_details
from ui.workers import AddWorker, ApiWorker, ImportWorker


class FormulationTabMixin:
    """Formulation tab UI and behavior."""

    # ---- State ----
    def _init_formulation_state(self) -> None:
        """Initialize formulation tab state."""
        # Async worker management.
        self._threads: list[QThread] = []
        self._workers: list[object] = []
        self._current_import_worker: ImportWorker | None = None
        self._current_add_worker: AddWorker | None = None

        # Import/add defaults.
        self.import_max_attempts = 4
        self.import_read_timeout = 8.0

        # Formulation UI state.
        self.quantity_mode = "g"
        self.amount_g_column_index = 2
        self.percent_column_index = 3
        self.lock_column_index = 4
        self.nutrient_export_flags: Dict[str, bool] = {}

        # Nutrient ordering helpers.
        self._reference_order_map: Dict[str, Dict[str, Any]] = {}
        self._nutrient_catalog: list[tuple[str, list[str]]] = self._build_nutrient_catalog()
        self._nutrient_order_map: dict[str, int] = {}
        self._nutrient_category_map: dict[str, str] = {}
        for idx, (_, names) in enumerate(self._nutrient_catalog):
            for offset, name in enumerate(names):
                self._nutrient_order_map[name.strip().lower()] = idx * 1000 + offset
                self._nutrient_category_map[name.strip().lower()] = self._nutrient_catalog[idx][0]

        # Cache for totals used by label preview.
        self._last_totals: Dict[str, Dict[str, Any]] = {}

        # Shared data type priority (search + formulation).
        self.data_type_priority = {
            "Foundation": 0,
            "SR Legacy": 1,
            "Survey": 2,
            "Survey (FNDDS)": 2,
            "Experimental": 3,
            "Branded": 4,
        }

    # ---- UI build ----
    def _build_formulation_tab_ui(self) -> None:
        """Build the Formulation tab UI."""
        # Layout base del tab de formulacion.
        layout = QVBoxLayout(self.formulation_tab)
    
        # Encabezado: export/import, nombre y unidad.
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
    
        # Tabla principal de ingredientes.
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
    
        # Acciones sobre ingredientes.
        buttons_layout = QHBoxLayout()
        self.edit_quantity_button = QPushButton("Editar cantidad seleccionada")
        self.remove_formulation_button = QPushButton(
            "Eliminar ingrediente seleccionado"
        )
        buttons_layout.addWidget(self.edit_quantity_button)
        buttons_layout.addWidget(self.remove_formulation_button)
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
    
        # Totales nutricionales.
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
        self.totals_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.totals_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.totals_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.totals_table)
    
        # Acciones de exportacion.
        export_buttons_layout = QHBoxLayout()
        self.toggle_export_button = QPushButton("Deseleccionar todos")
        self.export_excel_button = QPushButton("Exportar a Excel")
        export_buttons_layout.addStretch()
        export_buttons_layout.addWidget(self.toggle_export_button)
        export_buttons_layout.addWidget(self.export_excel_button)
        export_buttons_layout.addStretch()
        layout.addLayout(export_buttons_layout)
    
        # Conexiones de eventos.
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
    
        # Atajos de copia para tablas (Ctrl+C).
        # Copy shortcuts (Ctrl+C) for all tables
        for table in (
            self.table,
            self.details_table,
            self.formulation_preview,
            self.formulation_table,
            self.totals_table,
        ):
            self._attach_copy_shortcut(table)
    
        # Ajuste inicial de columnas.
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


    def _attach_copy_shortcut(self, table: QTableWidget) -> None:
        """Attach Ctrl+C to copy the current selection of a table as TSV to clipboard."""
        shortcut = QShortcut(QKeySequence.Copy, table)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(lambda t=table: self._copy_table_selection(t))


    def _copy_table_selection(self, table: QTableWidget) -> None:
        """Copy selected cells/rows to clipboard (TSV) with headers."""
        sel_model = table.selectionModel()
        if not sel_model or not sel_model.hasSelection():
            return
        ranges = table.selectedRanges()
        if not ranges:
            return
        selected_range = ranges[0]
        rows = range(selected_range.topRow(), selected_range.bottomRow() + 1)
        cols = range(selected_range.leftColumn(), selected_range.rightColumn() + 1)

        headers: list[str] = []
        for col in cols:
            header_item = table.horizontalHeaderItem(col)
            headers.append(header_item.text() if header_item else "")
        lines = ["\t".join(headers)]

        for row in rows:
            row_vals: list[str] = []
            for col in cols:
                item = table.item(row, col)
                row_vals.append("" if item is None else item.text())
            lines.append("\t".join(row_vals))

        QApplication.clipboard().setText("\n".join(lines))


    def _is_importing(self) -> bool:
        """Return True if an import hydration worker is running."""
        return self._current_import_worker is not None


    # ---- Formulation actions ----
    def on_remove_formulation_clicked(self) -> None:
        if self._is_importing():
            self.status_label.setText("Importacion en curso. Espera para editar.")
            return
        self._remove_selected_from_formulation(self.formulation_table)


    def on_formulation_cell_double_clicked(self, row: int, column: int) -> None:
        """Double click on formulation row -> edit its quantity."""
        if self._is_importing():
            self.status_label.setText("Importacion en curso. Espera para editar.")
            return
        if not self._can_edit_column(column):
            return
        self._edit_quantity_for_row(row)


    def on_lock_toggled_from_table(self, item: QTableWidgetItem) -> None:
        """Handle lock/unlock toggles coming from any formulation table."""
        if self._is_importing():
            return
        if item.column() != self.lock_column_index:
            return
        if self.quantity_mode == "g":
            return
        table = item.tableWidget()
        if table not in (self.formulation_table, self.formulation_preview):
            return
        row = item.row()
        if row < 0 or row >= self.formulation_presenter.get_ingredient_count():
            return

        desired_locked = item.checkState() == Qt.Checked
        if desired_locked and self.formulation_presenter.get_locked_count(exclude_index=row) >= (
            self.formulation_presenter.get_ingredient_count() - 1
        ):
            # Avoid all items locked: keep one free.
            table.blockSignals(True)
            item.setCheckState(Qt.Unchecked)
            table.blockSignals(False)
            self.status_label.setText("Debe quedar al menos un ingrediente sin fijar.")
            return

        # Toggle lock via presenter
        try:
            self.formulation_presenter.toggle_lock(row)
        except Exception as e:
            logging.error(f"Error toggling lock via presenter: {e}")

        self._refresh_formulation_views()


    def on_edit_quantity_clicked(self) -> None:
        if self._is_importing():
            self.status_label.setText("Importacion en curso. Espera para editar.")
            return
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
        if not self.formulation_presenter.has_ingredients():
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


    # ---- Import/export ----
    def on_export_state_clicked(self) -> None:
        """Export formulation state (ingredientes + cantidades + flags) a JSON."""
        if not self.formulation_presenter.has_ingredients():
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

        try:
            # Update formulation name from UI input and build JSON payload.
            formulation_name = self.formula_name_input.text() or "Current Formulation"
            self.formulation_presenter.formulation_name = formulation_name
            data = self._build_formulation_export_payload()
            Path(path).write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

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


    def _build_formulation_export_payload(self) -> Dict[str, Any]:
        """Assemble formulation + UI config into a JSON-friendly payload."""
        items: list[Dict[str, Any]] = []
        for item in self.formulation_presenter.get_ui_items():
            fdc_raw = item.get("fdc_id")
            try:
                fdc_id = int(fdc_raw)
            except Exception:
                fdc_id = fdc_raw

            amount_raw = item.get("amount_g", 0.0)
            try:
                amount_g = float(amount_raw) if amount_raw is not None else 0.0
            except Exception:
                amount_g = 0.0

            items.append(
                {
                    "fdc_id": fdc_id,
                    "description": item.get("description", "") or "",
                    "brand": item.get("brand") or item.get("brand_owner") or "",
                    "data_type": item.get("data_type", "") or "",
                    "amount_g": amount_g,
                    "locked": bool(item.get("locked", False)),
                }
            )

        return {
            "version": 3,
            "formula_name": self.formula_name_input.text() or "Current Formulation",
            "quantity_mode": self.quantity_mode,
            "items": items,
            "nutrient_export_flags": self._snapshot_export_flags(),
            "label_settings": self._snapshot_label_settings(),
        }


    def _snapshot_export_flags(self) -> Dict[str, bool]:
        """Return export flag map using stable header keys."""
        flags: Dict[str, bool] = {}
        for key, value in (self.nutrient_export_flags or {}).items():
            if key is None:
                continue
            key_text = str(key).strip().lower()
            if not key_text:
                continue
            flags[key_text] = bool(value)
        return flags


    def _normalize_export_flags(
        self, raw_flags: Dict[str, Any] | None
    ) -> tuple[Dict[str, bool], Dict[str, bool]]:
        """Split export flags into header-key and legacy formats."""
        normalized: Dict[str, bool] = {}
        legacy: Dict[str, bool] = {}
        if not isinstance(raw_flags, dict):
            return normalized, legacy

        for key, value in raw_flags.items():
            if key is None:
                continue
            key_text = str(key).strip()
            if not key_text:
                continue
            enabled = value
            if isinstance(enabled, str):
                lowered = enabled.strip().lower()
                if lowered in {"true", "1", "yes", "si"}:
                    enabled = True
                elif lowered in {"false", "0", "no"}:
                    enabled = False
            enabled = bool(enabled)
            lower = key_text.lower()

            if "|" in lower:
                name_part, unit_part = lower.split("|", 1)
                if name_part:
                    normalized[f"{name_part.strip()}|{unit_part.strip()}"] = enabled
                continue

            if lower.endswith(")") and " (" in lower:
                name_part, unit_part = lower.rsplit(" (", 1)
                unit_part = unit_part[:-1]
                if name_part:
                    normalized[f"{name_part.strip()}|{unit_part.strip()}"] = enabled
                continue

            if lower.startswith("energy:"):
                unit_part = lower.split(":", 1)[1].strip()
                if unit_part:
                    normalized[f"energy|{unit_part}"] = enabled
                continue

            legacy[lower] = enabled

        return normalized, legacy


    def _resolve_legacy_export_flags(
        self,
        legacy_flags: Dict[str, bool],
        hydrated_items: list[Dict[str, Any]],
    ) -> Dict[str, bool]:
        """Map old-style flag keys (id/num/name) to header keys."""
        if not legacy_flags:
            return {}

        legacy_to_header: Dict[str, str] = {}
        name_to_headers: Dict[str, set[str]] = {}

        for item in hydrated_items:
            for entry in item.get("nutrients", []) or []:
                nut = entry.get("nutrient") or {}
                header_key, _, _ = self._header_key(nut)
                if not header_key:
                    continue
                legacy_key = self._nutrient_key(nut)
                if legacy_key:
                    legacy_to_header.setdefault(legacy_key.lower(), header_key)
                name_part = header_key.split("|", 1)[0]
                name_to_headers.setdefault(name_part, set()).add(header_key)

        resolved: Dict[str, bool] = {}
        for key, value in legacy_flags.items():
            norm = str(key).strip().lower()
            if not norm:
                continue

            if norm.startswith("energy:"):
                unit = norm.split(":", 1)[1].strip()
                if unit:
                    resolved[f"energy|{unit}"] = bool(value)
                continue

            if norm.startswith("name:"):
                name = norm.split(":", 1)[1].strip()
                for header_key in name_to_headers.get(name, set()):
                    resolved[header_key] = bool(value)
                continue

            header_key = legacy_to_header.get(norm)
            if header_key:
                resolved[header_key] = bool(value)
                continue

            for header_key in name_to_headers.get(norm, set()):
                resolved[header_key] = bool(value)

        return resolved


    def _load_state_from_json(self, path: str) -> tuple[list[Dict[str, Any]], Dict[str, Any]] | None:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))

            items = data.get("items")
            if not items:
                items = data.get("ingredients")

            if not isinstance(items, list) or not items:
                QMessageBox.warning(
                    self,
                    "Formato invalido",
                    "El archivo no contiene ingredientes validos.",
                )
                return None

            base_items: list[Dict[str, Any]] = []
            for item in items:
                if not isinstance(item, dict):
                    continue

                fdc_raw = item.get("fdc_id") or item.get("fdcId") or item.get("fdcID")
                if fdc_raw is None:
                    QMessageBox.warning(
                        self,
                        "FDC ID invalido",
                        "Uno de los ingredientes no tiene FDC ID.",
                    )
                    return None

                try:
                    fdc_int = int(fdc_raw)
                except Exception:
                    QMessageBox.warning(
                        self,
                        "FDC ID invalido",
                        f"FDC ID no numerico: {fdc_raw}",
                    )
                    return None

                amount_raw = item.get("amount_g")
                if amount_raw is None:
                    amount_raw = item.get("amountG")
                if amount_raw is None:
                    amount_raw = item.get("amount")
                try:
                    amount_g = float(amount_raw) if amount_raw is not None else 0.0
                except Exception:
                    amount_g = 0.0

                base_items.append(
                    {
                        "fdc_id": fdc_int,
                        "amount_g": amount_g,
                        "locked": bool(item.get("locked", False)),
                        "description": item.get("description") or item.get("name") or "",
                        "brand": item.get("brand")
                        or item.get("brand_owner")
                        or item.get("brandOwner")
                        or "",
                        "data_type": item.get("data_type") or item.get("dataType") or "",
                    }
                )

            if not base_items:
                QMessageBox.warning(
                    self,
                    "Formato invalido",
                    "El archivo no contiene ingredientes validos.",
                )
                return None

            raw_flags = data.get("nutrient_export_flags")
            nutrient_flags, legacy_flags = self._normalize_export_flags(raw_flags)

            mode_raw = str(data.get("quantity_mode", "g") or "g").strip().lower()
            quantity_mode = "%" if mode_raw in ("%", "percent", "percentage") else "g"

            formula_name = data.get("formula_name") or data.get("name") or Path(path).stem
            label_settings = (
                data.get("label_settings")
                or data.get("label")
                or data.get("label_state")
                or {}
            )
            if not isinstance(label_settings, dict):
                label_settings = {}

            meta = {
                "nutrient_export_flags": nutrient_flags,
                "legacy_nutrient_export_flags": legacy_flags,
                "quantity_mode": quantity_mode,
                "formula_name": formula_name,
                "label_settings": label_settings,
                "path": path,
                "respect_existing_formula_name": False,
            }
            return base_items, meta

        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Error al importar",
                f"No se pudo leer el archivo:\n{exc}",
            )
            return None


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


    def _set_import_controls_enabled(self, enabled: bool) -> None:
        """Toggle formulation controls while import is running."""
        for widget in (
            self.edit_quantity_button,
            self.remove_formulation_button,
            self.export_excel_button,
            self.toggle_export_button,
            self.quantity_mode_selector,
        ):
            if widget is not None:
                widget.setEnabled(enabled)


    def _prefill_import_state(
        self, base_items: list[Dict[str, Any]], meta: Dict[str, Any]
    ) -> None:
        """Populate UI with base items before USDA hydration."""
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

        label_settings = meta.get("label_settings") or {}
        if label_settings:
            self._apply_label_settings(label_settings, defer_preview=True)

        ui_items: list[Dict[str, Any]] = []
        for item in base_items:
            fdc_id = item.get("fdc_id")
            description = (item.get("description") or "").strip()
            if not description:
                description = f"FDC {fdc_id}"
            data_type = (item.get("data_type") or "").strip() or "Imported"
            ui_items.append(
                {
                    "fdc_id": fdc_id,
                    "description": description,
                    "brand": item.get("brand", "") or "",
                    "data_type": data_type,
                    "amount_g": float(item.get("amount_g", 0.0) or 0.0),
                    "locked": bool(item.get("locked", False)),
                    "nutrients": [],
                }
            )

        self.formulation_presenter.load_from_ui_items(
            ui_items,
            self.formula_name_input.text() or "Imported",
        )
        self._last_totals = {}
        self.details_table.setRowCount(0)
        self.totals_table.setRowCount(0)
        self._populate_formulation_tables()
        self._ensure_preview_selection()
        self._update_label_preview(force_recalc_totals=True)


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
        self._set_import_controls_enabled(False)
        self._suspend_no_sig_update = True
        self.status_label.setText("Importando ingredientes...")
        self._set_window_progress("Importando ingredientes")

        self._pending_import_meta = meta
        self._prefill_import_state(base_items, meta)

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
        worker.finished.connect(self._on_import_finished)
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


    def _on_import_finished(self, payload: list[Dict[str, Any]]) -> None:
        meta = getattr(self, "_pending_import_meta", {}) or {}
        self._pending_import_meta = {}
        if QThread.currentThread() is not self.thread():
            QTimer.singleShot(0, lambda p=payload, m=meta: self._on_import_finished(p))
            return
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

            nutrients = augment_fat_nutrients(details.get("foodNutrients", []) or [])
            self._update_reference_from_details(details)
            hydrated.append(
                {
                    "fdc_id": fdc_id_int,
                    "description": details.get("description", "") or base.get("description", ""),
                    "brand": details.get("brandOwner", "") or base.get("brand", ""),
                    "data_type": details.get("dataType", "") or base.get("data_type", ""),
                    "amount_g": float(base.get("amount_g", 0.0) or 0.0),
                    "nutrients": normalize_nutrients(
                        nutrients, details.get("dataType")
                    ),
                    "locked": bool(base.get("locked", False)),
                }
            )

        self.formulation_presenter.load_from_ui_items(
            hydrated, self.formula_name_input.text() or "Imported"
        )
        resolved_flags: Dict[str, bool] = {}
        resolved_flags.update(
            self._resolve_legacy_export_flags(
                meta.get("legacy_nutrient_export_flags", {}),
                hydrated,
            )
        )
        resolved_flags.update(meta.get("nutrient_export_flags", {}))
        self.nutrient_export_flags = resolved_flags
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
        self._set_import_controls_enabled(True)
        self._suspend_no_sig_update = False
        self._set_window_progress(None)
        self._current_import_worker = None


    def _total_weight(self) -> float:
        """Total weight of current formulation in grams."""
        return self.formulation_presenter.get_total_weight()


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


    def _category_for_nutrient(self, name: str, nutrient: Dict[str, Any] | None = None) -> str:
        """Resolve a nutrient category using the static catalog then reference hints."""
        lower = (name or "").strip().lower()
        if lower in self._nutrient_category_map:
            return self._nutrient_category_map[lower]

        amino_acids = {
            "tryptophan",
            "threonine",
            "isoleucine",
            "leucine",
            "lysine",
            "methionine",
            "phenylalanine",
            "tyrosine",
            "valine",
            "arginine",
            "histidine",
            "alanine",
            "aspartic acid",
            "glutamic acid",
            "glycine",
            "proline",
            "serine",
            "hydroxyproline",
            "cysteine",
            "cystine",
        }
        organic_acids = {
            "citric acid",
            "malic acid",
            "oxalic acid",
            "quinic acid",
        }
        oligosaccharides = {"raffinose", "stachyose", "verbascose"}
        isoflavones = {"daidzein", "genistein", "daidzin", "genistin", "glycitin"}

        vitamin_like = (
            lower.startswith("vitamin ")
            or "tocopherol" in lower
            or "tocotrienol" in lower
            or "carotene" in lower
            or "lycopene" in lower
            or "lutein" in lower
            or "zeaxanthin" in lower
            or "retinol" in lower
            or "folate" in lower
            or "folic acid" in lower
            or "betaine" in lower
            or "choline" in lower
            or "caffeine" in lower
            or "theobromine" in lower
        )
        if vitamin_like:
            return "Vitamins and Other Components"

        if lower in amino_acids:
            return "Amino acids"
        if (
            "fatty acids" in lower
            or lower.startswith(("sfa ", "mufa ", "pufa "))
            or lower in {"cholesterol", "total lipid (fat)", "total fat (nlea)"}
        ):
            return "Lipids"
        if "sterol" in lower:
            return "Phytosterols"
        if lower in organic_acids or (lower.endswith("acid") and lower not in amino_acids):
            return "Organic acids"
        if lower in oligosaccharides:
            return "Oligosaccharides"
        if lower in isoflavones:
            return "Isoflavones"

        if nutrient:
            ref = self._reference_info(nutrient)
            if ref.get("category"):
                return ref["category"]
        return "Nutrientes"


    def _collect_nutrient_columns(self) -> tuple[list[str], Dict[str, str], Dict[str, str]]:
        """
        Collect ordered nutrient headers and their categories.
        Uses the static catalog to force a default ordering/grouping and only keeps
        nutrients that appear with a value in any ingredient.
        """
        candidates: Dict[str, Dict[str, Any]] = {}
        categories_seen_order: Dict[str, int] = {}
        preferred_order = [cat for cat, _ in self._nutrient_catalog]
        preferred_count = len(preferred_order)

        for item in self.formulation_presenter.get_ui_items():
            data_priority = self.data_type_priority.get(
                (item.get("data_type") or "").strip(), len(self.data_type_priority)
            )
            for entry in self._sort_nutrients_for_display(item.get("nutrients", [])):
                nut = entry.get("nutrient") or {}
                amount = entry.get("amount")
                if amount is None:
                    continue
                header_key, canonical_name, canonical_unit = self._header_key(nut)
                if header_key and not self.nutrient_export_flags.get(header_key, True):
                    continue

                if not header_key or not canonical_name:
                    continue

                category = self._category_for_nutrient(canonical_name, nut)
                if category not in categories_seen_order:
                    categories_seen_order[category] = len(categories_seen_order)

                order = self._nutrient_order_map.get(canonical_name.strip().lower())
                if order is None:
                    order = self._nutrient_order(nut, len(candidates))
                # Keep kcal ahead of kJ when both present
                unit_lower = (canonical_unit or "").strip().lower()
                if canonical_name.strip().lower() == "energy":
                    if unit_lower == "kcal":
                        order = order - 0.1 if isinstance(order, (int, float)) else order
                    elif unit_lower == "kj":
                        order = order + 0.1 if isinstance(order, (int, float)) else order

                header = (
                    f"{canonical_name} ({canonical_unit})"
                    if canonical_unit
                    else canonical_name
                )

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
                        "category": category,
                        "order": order,
                        "data_priority": data_priority,
                    }

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


    def _ensure_normalized_items(self) -> None:
        """Normalize all ingredients' nutrients in-place (fat + energy)."""
        for idx, item in enumerate(self.formulation_presenter.get_ui_items()):
            original = item.get("nutrients", []) or []
            normalized = normalize_nutrients(original, item.get("data_type"))
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
                    "nutrients": normalize_nutrients(
                        details.get("foodNutrients", []) or [], details.get("dataType")
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


    # ---- Table refresh ----
    def _populate_formulation_tables(self) -> None:
        """Refresh formulation tables with current items."""
        logging.debug(f"_populate_formulation_tables rows={self.formulation_presenter.get_ingredient_count()}")
        self._update_quantity_headers()
        total_weight = self._total_weight()

        # Left preview (ID + Ingrediente)
        self.formulation_preview.blockSignals(True)
        self.formulation_preview.setRowCount(self.formulation_presenter.get_ingredient_count())
        for idx, item in enumerate(self.formulation_presenter.get_ui_items()):
            # Locked default handled by domain model
            self.formulation_preview.setItem(
                idx, 0, QTableWidgetItem(str(item.get("fdc_id", "")))
            )
            self.formulation_preview.setItem(
                idx, 1, QTableWidgetItem(item.get("description", ""))
            )
        self.formulation_preview.blockSignals(False)

        # Main formulation table
        self.formulation_table.blockSignals(True)
        self.formulation_table.setRowCount(self.formulation_presenter.get_ingredient_count())
        for idx, item in enumerate(self.formulation_presenter.get_ui_items()):
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
        self._last_totals = totals

        category_order = [cat for cat, _ in self._nutrient_catalog]

        def _cat_rank(name: str) -> int:
            cat = self._category_for_nutrient(name)
            if cat in category_order:
                return category_order.index(cat)
            return len(category_order) + 1

        def _order_val(name: str) -> float:
            return float(self._nutrient_order_map.get(name.strip().lower(), float("inf")))

        sorted_totals = sorted(
            totals.items(),
            key=lambda item: (
                _cat_rank(item[1].get("name", "")),
                _order_val(item[1].get("name", "")),
                item[1].get("name", "").lower(),
            ),
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
        logging.debug(f"_refresh_formulation_views count={self.formulation_presenter.get_ingredient_count()}")
        if QThread.currentThread() is not self.thread():
            QTimer.singleShot(0, self._refresh_formulation_views)
            return
        self._ensure_normalized_items()
        self._populate_formulation_tables()
        self._populate_totals_table()
        self._update_label_preview(force_recalc_totals=True)
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
        if not self.formulation_presenter.has_ingredients():
            self.details_table.setRowCount(0)
            return
        self._ensure_normalized_items()
        sel_model = self.formulation_preview.selectionModel()
        has_sel = sel_model and sel_model.hasSelection()
        if not has_sel:
            self._select_preview_row(self.formulation_presenter.get_ingredient_count() - 1)
        self._show_nutrients_for_selected_preview()


    def _show_nutrients_for_row(self, row: int) -> None:
        if row < 0 or row >= self.formulation_presenter.get_ingredient_count():
            self.details_table.setRowCount(0)
            return
        nutrients = self.formulation_presenter.get_ui_item(row).get("nutrients", []) or []
        self._populate_details_table(nutrients)


    def _show_nutrients_for_selected_preview(self) -> None:
        sel_model = self.formulation_preview.selectionModel()
        if not sel_model or not sel_model.hasSelection():
            self._show_nutrients_for_row(-1)
            return
        row = sel_model.selectedRows()[0].row()
        self._show_nutrients_for_row(row)


    def _export_formulation_to_excel(self, filepath: str) -> None:
        """Export formulation to Excel via presenter."""
        # Update formulation name from UI input
        formulation_name = self.formula_name_input.text() or "Current Formulation"
        self.formulation_presenter.formulation_name = formulation_name

        try:
            self.formulation_presenter.export_to_excel(
                filepath,
                export_flags=self.nutrient_export_flags,
            )
            return
        except Exception as e:
            logging.error(
                f"Error exporting via presenter: {e}, falling back to old method"
            )

        # Fallback to old implementation
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
        data_rows = self.formulation_presenter.get_ingredient_count()
        end_row = start_row + data_rows - 1

        # Write ingredient rows
        for idx, item in enumerate(self.formulation_presenter.get_ui_items()):
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


    def _normalize_totals_by_header_key(
        self, totals: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Re-key totals using header_key (name|unit) for export flags."""
        normalized: Dict[str, Dict[str, Any]] = {}
        best_priority: Dict[str, int] = {}
        alias_priority = {
            "carbohydrate, by difference": 2,
            "carbohydrate, by summation": 1,
            "carbohydrate by summation": 1,
            "sugars, total": 2,
            "total sugars": 1,
        }

        for entry in totals.values():
            name = entry.get("name", "")
            unit = entry.get("unit", "")
            nut = {"name": name, "unitName": unit}
            header_key, canonical_name, canonical_unit = self._header_key(nut)
            if not header_key:
                continue
            priority = alias_priority.get(str(name).strip().lower(), 0)
            current_best = best_priority.get(header_key, -1)
            if priority < current_best:
                continue
            best_priority[header_key] = priority
            normalized[header_key] = {
                "name": canonical_name or name,
                "unit": canonical_unit or unit,
                "amount": float(entry.get("amount", 0.0) or 0.0),
            }

        return normalized


    def _calculate_totals(self) -> Dict[str, Dict[str, Any]]:
        """Calculate nutrient totals via presenter."""
        logging.debug(f"_calculate_totals start items={self.formulation_presenter.get_ingredient_count()}")

        try:
            # Calculate totals via presenter
            totals = self.formulation_presenter.calculate_totals()
            totals = self._normalize_totals_by_header_key(totals)
            logging.debug(f"_calculate_totals done (via presenter) nutrients={len(totals)}")
            return totals

        except Exception as e:
            logging.error(f"Error calculating totals via presenter: {e}")
            # Fallback to old implementation
            self._ensure_normalized_items()
            totals: Dict[str, Dict[str, Any]] = {}
            total_weight = self._total_weight()
            for item in self.formulation_presenter.get_ui_items():
                qty = item.get("amount_g", 0) or 0
                for nutrient in self._sort_nutrients_for_display(item.get("nutrients", [])):
                    amount = nutrient.get("amount")
                    if amount is None:
                        continue
                    nut = nutrient.get("nutrient") or {}
                    header_key, canonical_name, canonical_unit = self._header_key(nut)
                    if not header_key:
                        continue
                    entry = totals.setdefault(
                        header_key,
                        {
                            "name": canonical_name or nut.get("name", ""),
                            "unit": canonical_unit or "",
                            "amount": 0.0,
                            "order": self._nutrient_order(nut, len(totals)),
                        },
                    )
                    if canonical_name and not entry["name"]:
                        entry["name"] = canonical_name
                    if canonical_unit and not entry["unit"]:
                        entry["unit"] = canonical_unit
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
            logging.debug(f"_calculate_totals done (fallback) nutrients={len(totals)} total_weight={total_weight}")
            return totals


    # ---- Nutrient ordering ----
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
        # Special-case Water to merge branded-calculated (no id) with USDA water (id present).
        if name_lower == "water":
            return f"water|{unit_lower}"
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


    def _build_nutrient_catalog(self) -> list[tuple[str, list[str]]]:
        """Static catalog to enforce ordering/categories when using abridged."""
        return [
            (
                "Proximates",
                [
                    "Water",
                    "Energy",
                    "Nitrogen",
                    "Protein",
                    "Total fat (NLEA)",
                    "Total lipid (fat)",
                    "Ash",
                    "Carbohydrate, by difference",
                ],
            ),
            (
                "Carbohydrates",
                [
                    "Fiber, total dietary",
                    "Fiber, soluble",
                    "Fiber, insoluble",
                    "Total dietary fiber (AOAC 2011.25)",
                    "High Molecular Weight Dietary Fiber (HMWDF)",
                    "Low Molecular Weight Dietary Fiber (LMWDF)",
                    "Sugars, Total",
                    "Sucrose",
                    "Glucose",
                    "Fructose",
                    "Lactose",
                    "Maltose",
                    "Galactose",
                    "Starch",
                    "Resistant starch",
                    "Sugars, added",
                ],
            ),
            (
                "Minerals",
                [
                    "Calcium, Ca",
                    "Iron, Fe",
                    "Magnesium, Mg",
                    "Phosphorus, P",
                    "Potassium, K",
                    "Sodium, Na",
                    "Zinc, Zn",
                    "Copper, Cu",
                    "Manganese, Mn",
                    "Iodine, I",
                    "Selenium, Se",
                    "Molybdenum, Mo",
                    "Fluoride, F",
                ],
            ),
            (
                "Vitamins and Other Components",
                [
                    "Thiamin",
                    "Riboflavin",
                    "Niacin",
                    "Vitamin B-6",
                    "Folate, total",
                    "Folic acid",
                    "Folate, DFE",
                    "Choline, total",
                    "Choline, free",
                    "Choline, from phosphocholine",
                    "Choline, from phosphatidyl choline",
                    "Choline, from glycerophosphocholine",
                    "Choline, from sphingomyelin",
                    "Betaine",
                    "Vitamin B-12",
                    "Vitamin B-12, added",
                    "Vitamin A, RAE",
                    "Retinol",
                    "Carotene, beta",
                    "cis-beta-Carotene",
                    "trans-beta-Carotene",
                    "Carotene, alpha",
                    "Carotene, gamma",
                    "Cryptoxanthin, beta",
                    "Cryptoxanthin, alpha",
                    "Vitamin A, IU",
                    "Lycopene",
                    "cis-Lycopene",
                    "trans-Lycopene",
                    "Lutein + zeaxanthin",
                    "cis-Lutein/Zeaxanthin",
                    "Lutein",
                    "Zeaxanthin",
                    "Phytoene",
                    "Phytofluene",
                    "Vitamin D (D2 + D3), International Units",
                    "Vitamin D (D2 + D3)",
                    "Vitamin D2 (ergocalciferol)",
                    "Vitamin D3 (cholecalciferol)",
                    "25-hydroxycholecalciferol",
                    "Vitamin K (phylloquinone)",
                    "Vitamin K (Dihydrophylloquinone)",
                    "Vitamin K (Menaquinone-4)",
                    "Vitamin E (alpha-tocopherol)",
                    "Vitamin E, added",
                    "Tocopherol, beta",
                    "Tocopherol, gamma",
                    "Tocopherol, delta",
                    "Tocotrienol, alpha",
                    "Tocotrienol, beta",
                    "Tocotrienol, gamma",
                    "Tocotrienol, delta",
                    "Vitamin C, total ascorbic acid",
                    "Pantothenic acid",
                    "Biotin",
                    "Caffeine",
                    "Theobromine",
                ],
            ),
            (
                "Lipids",
                [
                    "Fatty acids, total saturated",
                    "SFA 4:0",
                    "SFA 5:0",
                    "SFA 6:0",
                    "SFA 7:0",
                    "SFA 8:0",
                    "SFA 9:0",
                    "SFA 10:0",
                    "SFA 11:0",
                    "SFA 12:0",
                    "SFA 13:0",
                    "SFA 14:0",
                    "SFA 15:0",
                    "SFA 16:0",
                    "SFA 17:0",
                    "SFA 18:0",
                    "SFA 20:0",
                    "SFA 21:0",
                    "SFA 22:0",
                    "SFA 23:0",
                    "SFA 24:0",
                    "Fatty acids, total monounsaturated",
                    "MUFA 12:1",
                    "MUFA 14:1",
                    "MUFA 14:1 c",
                    "MUFA 15:1",
                    "MUFA 16:1",
                    "MUFA 16:1 c",
                    "MUFA 17:1",
                    "MUFA 17:1 c",
                    "MUFA 18:1",
                    "MUFA 18:1 c",
                    "MUFA 20:1",
                    "MUFA 20:1 c",
                    "MUFA 22:1",
                    "MUFA 22:1 c",
                    "MUFA 22:1 n-9",
                    "MUFA 22:1 n-11",
                    "MUFA 24:1 c",
                    "Fatty acids, total polyunsaturated",
                    "PUFA 18:2",
                    "PUFA 18:2 c",
                    "PUFA 18:2 n-6 c,c",
                    "PUFA 18:2 CLAs",
                    "PUFA 18:2 i",
                    "PUFA 18:3",
                    "PUFA 18:3 c",
                    "PUFA 18:3 n-3 c,c,c (ALA)",
                    "PUFA 18:3 n-6 c,c,c",
                    "PUFA 18:4",
                    "PUFA 20:2 c",
                    "PUFA 20:2 n-6 c,c",
                    "PUFA 20:3",
                    "PUFA 20:3 c",
                    "PUFA 20:3 n-3",
                    "PUFA 20:3 n-6",
                    "PUFA 20:3 n-9",
                    "PUFA 20:4",
                    "PUFA 20:4c",
                    "PUFA 20:5c",
                    "PUFA 20:5 n-3 (EPA)",
                    "PUFA 22:2",
                    "PUFA 22:3",
                    "PUFA 22:4",
                    "PUFA 22:5 c",
                    "PUFA 22:5 n-3 (DPA)",
                    "PUFA 22:6 c",
                    "PUFA 22:6 n-3 (DHA)",
                    "Fatty acids, total trans",
                    "Fatty acids, total trans-monoenoic",
                    "Fatty acids, total trans-dienoic",
                    "Fatty acids, total trans-polyenoic",
                    "TFA 14:1 t",
                    "TFA 16:1 t",
                    "TFA 18:1 t",
                    "TFA 18:2 t",
                    "TFA 18:2 t,t",
                    "TFA 18:2 t not further defined",
                    "TFA 18:3 t",
                    "TFA 20:1 t",
                    "TFA 22:1 t",
                    "Cholesterol",
                ],
            ),
            (
                "Amino acids",
                [
                    "Tryptophan",
                    "Threonine",
                    "Isoleucine",
                    "Leucine",
                    "Lysine",
                    "Methionine",
                    "Phenylalanine",
                    "Tyrosine",
                    "Valine",
                    "Arginine",
                    "Histidine",
                    "Alanine",
                    "Aspartic acid",
                    "Glutamic acid",
                    "Glycine",
                    "Proline",
                    "Serine",
                    "Hydroxyproline",
                    "Cysteine",
                ],
            ),
            (
                "Phytosterols",
                [
                    "Phytosterols",
                    "Beta-sitosterol",
                    "Brassicasterol",
                    "Campesterol",
                    "Campestanol",
                    "Delta-5-avenasterol",
                    "Phytosterols, other",
                    "Stigmasterol",
                    "Beta-sitostanol",
                ],
            ),
            ("Organic acids", ["Citric acid", "Malic acid", "Oxalic acid", "Quinic acid"]),
            ("Oligosaccharides", ["Verbascose", "Raffinose", "Stachyose"]),
            ("Isoflavones", ["Daidzin", "Genistin", "Glycitin", "Daidzein", "Genistein"]),
        ]


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
        name = canonical_alias_name(nutrient.get("name", "") or "")
        unit = canonical_unit(nutrient.get("unitName") or self._infer_unit(nutrient) or "")
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
        if rank is None:
            name_lower = (nutrient.get("name") or "").strip().lower()
            rank = self._nutrient_order_map.get(name_lower)
        try:
            return float(rank)
        except (TypeError, ValueError):
            return float(fallback)


    # ---- Add/edit flows ----
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
        if row < 0 or row >= self.formulation_presenter.get_ingredient_count():
            self.status_label.setText("Fila seleccionada inválida.")
            return

        item = self.formulation_presenter.get_ui_item(row)
        default_amount = item.get("amount_g", 0.0)
        mode, value = self._prompt_quantity(default_amount, editing_index=row)
        if mode is None:
            return

        if mode == "g":
            # Update the domain model directly so the change persists.
            self.formulation_presenter.update_ingredient_amount(
                row,
                value,
                maintain_total=False,
            )
        else:
            if not self._apply_percent_edit(row, value):
                return

        self._refresh_formulation_views()
        if mode == "g":
            msg_value = self._format_amount_for_status(value)
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

        if target_idx < 0 or target_idx >= self.formulation_presenter.get_ingredient_count():
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
            for item in self.formulation_presenter.get_ui_items()
        ]

        locked_sum = sum(
            current_percents[idx]
            for idx, item in enumerate(self.formulation_presenter.get_ui_items())
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
            for idx, item in enumerate(self.formulation_presenter.get_ui_items())
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
        new_percents = [0.0 for _ in range(self.formulation_presenter.get_ingredient_count())]

        for idx, item in enumerate(self.formulation_presenter.get_ui_items()):
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
            # Amount updated via presenter.update_ingredient_amount(idx, safe_pct * base_total / 100.0)

            self.formulation_presenter.update_ingredient_amount(idx, safe_pct * base_total / 100.0)
        return True


    def _remove_selected_from_formulation(self, table: QTableWidget) -> None:
        indexes = table.selectionModel().selectedRows()
        if not indexes:
            self.status_label.setText("Selecciona un ingrediente para eliminar.")
            return
        row = indexes[0].row()
        if 0 <= row < self.formulation_presenter.get_ingredient_count():
            # Ingredient removed via presenter

            removed = {"fdc_id": "", "description": "Removed"}

            # Remove from presenter
            try:
                self.formulation_presenter.remove_ingredient(row)
            except Exception as e:
                logging.error(f"Error removing ingredient via presenter: {e}")

            # If all remaining ingredients are locked, unlock the first one
            if (self.formulation_presenter.has_ingredients() and
                self.formulation_presenter.get_locked_count() == self.formulation_presenter.get_ingredient_count()):
                self.formulation_presenter.toggle_lock(0)
            self._refresh_formulation_views()
            self.status_label.setText(
                f"Eliminado {removed.get('fdc_id', '')} - {removed.get('description', '')}"
            )
        else:
            self.status_label.setText("Fila seleccionada inválida.")


    # ---- Async helpers ----
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

    def _on_add_details_loaded(self, details, mode: str, value: float) -> None:
        logging.debug(
            f"_on_add_details_loaded fdc_id={details.get('fdcId', '?')} "
            f"mode={mode} value={value} "
            f"nutrients_count={len(details.get('foodNutrients', []) or [])}"
        )

        # Use details that AddWorker already fetched (avoid double API call)
        fdc_id = details.get("fdcId", "")
        amount_g = value if mode == "g" else 100.0

        # Normalize nutrients from the details we already have
        nutrients = normalize_nutrients(
            details.get("foodNutrients", []) or [],
            details.get("dataType")
        )
        self._update_reference_from_details(details)

        desc = details.get("description", "") or ""
        brand = details.get("brandOwner", "") or ""
        data_type = details.get("dataType", "") or ""

        # Add ingredient directly to presenter using fetched data
        # (avoiding duplicate API call since AddWorker already fetched details)
        try:
            from domain.models import Food, Ingredient, Nutrient
            from decimal import Decimal

            domain_nutrients = tuple(
                Nutrient(
                    name=n["nutrient"]["name"],
                    unit=n["nutrient"].get("unitName", ""),
                    amount=Decimal(str(n["amount"])) if n.get("amount") is not None else Decimal("0"),
                    nutrient_id=n["nutrient"].get("id"),
                    nutrient_number=n["nutrient"].get("number"),
                )
                for n in nutrients
            )

            food = Food(
                fdc_id=fdc_id,
                description=desc,
                data_type=data_type,
                brand_owner=brand,
                nutrients=domain_nutrients,
            )

            ingredient = Ingredient(food=food, amount_g=Decimal(str(amount_g)))
            self.formulation_presenter._formulation.add_ingredient(ingredient)

        except Exception as e:
            logging.error(f"Error adding ingredient to presenter: {e}")

        self._update_reference_from_details(details)

        if mode == "percent":
            success = self._apply_percent_edit(self.formulation_presenter.get_ingredient_count() - 1, value)
            if not success:
                # Percentage adjustment failed, remove last ingredient
                self.formulation_presenter.remove_ingredient(
                    self.formulation_presenter.get_ingredient_count() - 1
                )
                self.add_button.setEnabled(True)
                return

        self._populate_details_table(nutrients)
        self._refresh_formulation_views()
        self._select_preview_row(self.formulation_presenter.get_ingredient_count() - 1)
        msg_value = (
            self._format_amount_for_status(amount_g)
            if mode == "g"
            else f"{value:.2f} %"
        )
        self.status_label.setText(
            f"Agregado {fdc_id} - {desc} ({msg_value})"
        )
        self.add_button.setEnabled(True)
        self._upgrade_item_to_full(self.formulation_presenter.get_ingredient_count() - 1, int(fdc_id))


    def _on_add_error(self, message: str) -> None:
        self._reset_add_ui_state()
        self.status_label.setText(f"Error al agregar: {message}")
        logging.error(f"_on_add_error: {message}")


    def _upgrade_item_to_full(self, index: int, fdc_id: int) -> None:
        """Upgrade no-op: abridged es la única fuente ahora."""
        return

    def on_totals_checkbox_changed(self, item: QTableWidgetItem) -> None:
        """Sync export checkbox state into memory and update toggle label."""
        if self._is_importing():
            return
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
