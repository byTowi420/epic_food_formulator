# Food Formulator

Desktop app for building food formulations with nutrition analysis using the USDA FoodData Central database.

## Features

- USDA search with ingredient import
- Formulation in g/% with locks and target-weight normalization (g/kg/ton/lb/oz)
- Nutrient totals per 100 g and per ingredient
- Nutrition label preview (vertical + linear) with manual overrides and PNG export
- Excel export and JSON save/load
- Costs tab with ingredients, processes, yield, packaging, and currency rates by symbol

## Architecture

The app follows a layered architecture with presenters:

- **Domain**: models and core logic (`domain/models.py`, `domain/services/*`)
- **Application**: use cases (`application/use_cases.py`)
- **Infrastructure**: USDA repository + cache and persistence (`infrastructure/*`)
- **UI**: PySide6 tabs, presenters, adapters (`ui/*`)
- **Shared normalization**: USDA nutrient normalization helpers (`domain/services/nutrient_normalizer.py`)

See `docs/architecture.md` for details.

## Requirements

- Python 3.11+
- USDA FoodData Central API key (https://fdc.nal.usda.gov/api-key-signup.html)

## Installation

### 1. Clone Repository

```bash
git clone <repository-url>
cd food_formulator
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
.\.venv\Scriptsctivate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Configure API Key

```bash
# Set environment variable
setx USDA_API_KEY "your-key-here"
```

## Usage

```bash
python main.py
```

Typical workflow:
1. Search foods
2. Add ingredients + quantities
3. Adjust formulation (locks/targets)
4. Review totals + label
5. Manage costs (currency rates, yield, processes, packaging)
6. Save or export

Notes:
- Moneda Nacional usa simbolo "$" y es la base para todos los calculos (1 $ = 1 $).
- Las otras monedas se definen por simbolo y cotizacion: 1 simbolo = X $.
- Yield afecta la masa vendible y el costo por pack/unidad.
- Costos de procesos se calculan por tipo (FIXED / VARIABLE_PER_KG / MIXED).

## Project Structure

```
food_formulator/
|-- application/
|   `-- use_cases.py
|-- config/
|   |-- constants.py
|   `-- container.py
|-- domain/
|   |-- exceptions.py
|   |-- models.py
|   `-- services/
|       |-- formulation_service.py
|       |-- nutrient_calculator.py
|       `-- unit_normalizer.py
|-- infrastructure/
|   |-- api/
|   |   |-- cache.py
|   |   `-- usda_repository.py
|   `-- persistence/
|       |-- excel_exporter.py
|       |-- formulation_importer.py
|       `-- json_repository.py
|-- services/
|   `-- nutrient_normalizer.py
|-- ui/
|   |-- adapters/
|   |-- delegates/
|   |-- presenters/
|   |-- tabs/
|   |-- main_window.py
|   `-- workers.py
|-- tools/
|-- tests/
`-- main.py
```

## API Usage Example

```python
from decimal import Decimal
from config.container import Container
from domain.models import Formulation

container = Container()
formulation = Formulation(name="My Recipe")

food = container.add_ingredient.execute(
    formulation=formulation,
    fdc_id=171705,
    amount_g=Decimal("150"),
)

totals = container.calculate_totals.execute(formulation)
print(f"Protein per 100g: {totals.get('Protein', 0)} g")

container.export_formulation.execute(
    formulation=formulation,
    output_path="my_recipe.xlsx",
)
```
