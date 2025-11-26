from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.usda_api import USDAApiError, search_foods


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Food Formulator - Proto")
        self.resize(900, 600)

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Buscar alimento (ej: apple, rice, cheese)..."
        )

        self.search_button = QPushButton("Buscar")

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignLeft)
        self.status_label.setStyleSheet("color: gray;")

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["FDC ID", "Descripcion", "Marca / Origen", "Tipo de dato"]
        )
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)

        main_layout.addWidget(self.table)

        self.search_button.clicked.connect(self.on_search_clicked)
        self.search_input.returnPressed.connect(self.on_search_clicked)

    def on_search_clicked(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.status_label.setText("Ingresa un termino de busqueda.")
            return

        self.status_label.setText("Buscando en FoodData Central...")
        self.search_button.setEnabled(False)

        try:
            foods = search_foods(query)
        except USDAApiError as exc:
            self.status_label.setText(f"Error: {exc}")
            self.search_button.setEnabled(True)
            return

        self._populate_table(foods)
        self.status_label.setText(f"Se encontraron {len(foods)} resultados.")
        self.search_button.setEnabled(True)

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
