import json
import logging
from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QTabWidget, QVBoxLayout, QWidget

from config.container import Container
from infrastructure.api.usda_repository import FoodRepository
from ui.presenters.formulation_presenter import FormulationPresenter
from ui.presenters.label_presenter import LabelPresenter
from ui.presenters.search_presenter import SearchPresenter
from ui.presenters.costs_presenter import CostsPresenter
from ui.tabs.formulation_tab import FormulationTabMixin
from ui.tabs.label_tab import LabelTabMixin
from ui.tabs.search_tab import SearchTabMixin
from ui.tabs.costs_tab import CostsTabMixin

logging.basicConfig(
    filename="app_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(threadName)s] %(levelname)s %(message)s",
)


class MainWindow(SearchTabMixin, FormulationTabMixin, LabelTabMixin, CostsTabMixin, QMainWindow):
    """Top-level window orchestrating the three UI tabs."""

    def __init__(self) -> None:
        super().__init__()

        # Presenters.
        self.container = Container()
        self.formulation_presenter = FormulationPresenter(container=self.container)
        self.search_presenter = SearchPresenter(container=self.container)
        self.label_presenter = LabelPresenter()
        self.costs_presenter = CostsPresenter(self.formulation_presenter)

        # Window setup.
        self.base_window_title = "Food Formulator - Proto"
        self.setWindowTitle(self.base_window_title)
        self.resize(900, 600)

        # Shared UI state.
        self.last_path = self._load_last_path()

        # Tab-specific state.
        self._init_search_state()
        self._init_formulation_state()
        self._init_label_state()
        self._init_costs_state()

        self._build_ui()

    def _set_window_progress(self, progress: str | None = None) -> None:
        """Update the window title with progress info or reset it."""
        title = self.base_window_title
        if progress:
            title = f"{title} | {progress}"
        self.setWindowTitle(title)

    def _build_ui(self) -> None:
        """Create base tabs and delegate each tab build."""
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        self.tabs = QTabWidget()
        self.search_tab = QWidget()
        self.formulation_tab = QWidget()
        self.label_tab = QWidget()
        self.costs_tab = QWidget()
        self.tabs.addTab(self.search_tab, "Búsqueda")
        self.tabs.addTab(self.formulation_tab, "Formulación")
        self.tabs.addTab(self.label_tab, "Etiqueta")
        self.tabs.addTab(self.costs_tab, "Costos")

        main_layout.addWidget(self.tabs)

        self._build_search_tab_ui()
        self._build_formulation_tab_ui()
        self._build_label_tab_ui()
        self._build_costs_tab_ui()

    @property
    def food_repository(self) -> FoodRepository:
        """Lazily resolve the shared USDA repository."""
        return self.container.food_repository

    def _load_last_path(self) -> str:
        """Load last used path from local cache file."""
        try:
            data = json.loads(Path("last_path.json").read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data.get("last_path", "")
        except Exception:
            return ""
        return ""

    def _save_last_path(self, path: str) -> None:
        """Persist last used path for future sessions."""
        try:
            Path("last_path.json").write_text(
                json.dumps({"last_path": str(Path(path).expanduser())}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.last_path = str(Path(path).expanduser())
        except Exception:
            pass
