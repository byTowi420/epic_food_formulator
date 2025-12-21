"""Slim MainWindow - acts as coordinator between tabs.

This is a refactored version that delegates all logic to the tab components.
Each tab handles its own UI and business logic through presenters.
MainWindow only coordinates cross-tab communication.
"""

from typing import Any, Dict, List
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.presenters.formulation_presenter import FormulationPresenter
from ui.presenters.search_presenter import SearchPresenter
from ui.tabs.search_tab import SearchTab
from ui.tabs.formulation_tab import FormulationTab

logging.basicConfig(
    filename="app_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(threadName)s] %(levelname)s %(message)s",
)


class MainWindow(QMainWindow):
    """Main application window - thin coordinator.

    Responsibilities:
    - Create and hold tabs
    - Connect cross-tab signals
    - Display status messages
    - Window-level operations (title, size)

    All business logic is delegated to:
    - SearchTab: USDA food search
    - FormulationTab: Ingredient management, totals, import/export
    - LabelTab: Nutrition label generation (TODO)
    """

    def __init__(self) -> None:
        super().__init__()

        # Shared presenters (tabs can share state through these)
        self._formulation_presenter = FormulationPresenter()
        self._search_presenter = SearchPresenter()

        # Window setup
        self.setWindowTitle("Food Formulator")
        self.resize(900, 600)

        self._build_ui()
        self._connect_cross_tab_signals()

    def _build_ui(self) -> None:
        """Build the main UI structure."""
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Tab widget
        self.tabs = QTabWidget()

        # Create tabs with shared presenters
        self.search_tab = SearchTab(
            search_presenter=self._search_presenter,
        )
        self.formulation_tab = FormulationTab(
            formulation_presenter=self._formulation_presenter,
        )

        # Add tabs
        self.tabs.addTab(self.search_tab, "Buscar")
        self.tabs.addTab(self.formulation_tab, "Formulación")

        main_layout.addWidget(self.tabs)

        # Status bar
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray; padding: 4px;")
        main_layout.addWidget(self.status_label)

    def _connect_cross_tab_signals(self) -> None:
        """Connect signals between tabs for coordination."""

        # SearchTab -> FormulationTab: Add ingredient
        self.search_tab.ingredient_add_requested.connect(
            self.formulation_tab.add_ingredient
        )

        # SearchTab -> FormulationTab: Remove ingredient
        self.search_tab.ingredient_remove_requested.connect(
            self.formulation_tab.remove_ingredient
        )

        # FormulationTab -> SearchTab: Sync formulation preview
        self.formulation_tab.formulation_changed.connect(
            self._sync_formulation_preview
        )

        # Status messages from all tabs
        self.search_tab.status_message.connect(self._show_status)
        self.formulation_tab.status_message.connect(self._show_status)

    def _sync_formulation_preview(self) -> None:
        """Sync formulation items to search tab preview."""
        items = self.formulation_tab.get_formulation_items()
        self.search_tab.set_formulation_items(items)

    def _show_status(self, message: str) -> None:
        """Display status message in status bar."""
        self.status_label.setText(message)
        logging.debug(f"Status: {message}")
