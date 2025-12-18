# Epic Food Formulator

A desktop application for formulating food recipes with detailed nutritional analysis using USDA FoodData Central database.

## Features

- **USDA Database Search**: Access 350,000+ foods from FoodData Central
- **Recipe Formulation**: Create formulations with multiple ingredients
- **Nutrient Calculations**: Automatic calculation of nutritional totals per 100g
- **Locking System**: Lock ingredient proportions during adjustments
- **FDA Labels**: Generate nutrition facts labels (FDA/NLEA format)
- **Excel Export**: Professional multi-sheet Excel reports
- **JSON Persistence**: Save and load formulations

## Architecture

This project follows **Clean Architecture** principles:

- **Domain Layer**: Pure business logic (calculations, validations)
- **Application Layer**: Use cases orchestrating workflows
- **Infrastructure Layer**: External APIs, caching, file I/O
- **UI Layer**: PySide6 (Qt) desktop interface

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation.

## Requirements

- Python 3.11+
- USDA FoodData Central API key (free at https://fdc.nal.usda.gov/api-key-signup.html)

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd epic_food_formulator
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (for testing, linting)
pip install -r requirements-dev.txt
```

### 4. Configure API Key

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your USDA API key
# USDA_API_KEY="your-key-here"
```

## Usage

### Run Application

```bash
python main.py
```

### Workflow

1. **Search Foods**: Enter search term and click search
2. **Add Ingredients**: Select food and specify amount
3. **Adjust Formulation**: Modify amounts, lock proportions
4. **View Nutrients**: See totals and FDA label
5. **Save/Export**: Save as JSON or export to Excel

## Development

### Project Structure

```
epic_food_formulator/
├── config/                  # Configuration and DI container
├── domain/                  # Business logic (no dependencies)
│   ├── models.py
│   ├── exceptions.py
│   └── services/
├── application/             # Use cases
│   └── use_cases.py
├── infrastructure/          # External concerns
│   ├── api/                # USDA API client, cache
│   ├── normalizers/        # Data normalization
│   └── persistence/        # JSON, Excel
├── ui/                      # PySide6 UI
│   ├── main_window.py
│   └── workers.py
├── tests/                   # Unit and integration tests
│   ├── unit/
│   └── integration/
└── main.py                  # Entry point
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/unit/test_models.py

# Run only unit tests
pytest tests/unit/

# Run with verbose output
pytest -v
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .

# Type checking
mypy .

# Auto-fix linting issues
ruff check --fix .
```

## API Usage Example

```python
from config.container import Container
from domain.models import Formulation
from decimal import Decimal

# Initialize DI container
container = Container()

# Create formulation
formulation = Formulation(name="My Recipe")

# Add ingredient
food = container.add_ingredient.execute(
    formulation=formulation,
    fdc_id=171705,  # Chicken breast
    amount_g=Decimal("150")
)

# Calculate totals
totals = container.calculate_totals.execute(formulation)
print(f"Protein per 100g: {totals.get('Protein', 0)}g")

# Export to Excel
container.export_formulation.execute(
    formulation=formulation,
    output_path="my_recipe.xlsx"
)
```

## Contributing

See [docs/architecture.md](docs/architecture.md) for architecture details and migration strategy.

## License

[Specify license here]

## Acknowledgments

- USDA FoodData Central for nutrition database
- PySide6 (Qt for Python) for UI framework