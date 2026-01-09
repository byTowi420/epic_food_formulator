# Architecture Documentation

## Overview

The project uses a layered architecture with a presenter-driven UI. Business logic lives in the domain and application layers; infrastructure handles I/O; the UI is responsible for presentation and user events.

## Layer Structure (high level)

```
UI (ui/)
  - tabs, presenters, adapters, delegates, workers
  - label rendering in ui/presenters/label_presenter.py + ui/tabs/label_tab.py
    |
    v
Application (application/use_cases.py)
    |
    v
Domain (domain/models.py, domain/services/*)
    |
    v
Infrastructure (infrastructure/api, infrastructure/persistence)

Shared utilities:
- domain/services/nutrient_normalizer.py (USDA nutrient normalization)
```

## Dependency Rule

Inner layers do not depend on outer layers.
- Domain: no UI or infrastructure imports
- Application: uses domain + repository interfaces
- Infrastructure: concrete I/O (API, persistence)
- UI: depends on presenters and use cases

## Layers

### Domain (`domain/`)

- `models.py`: Food, Nutrient, Ingredient, Formulation
- `exceptions.py`: domain error types
- `services/`:
  - `formulation_service.py`: locks, scaling, target weight logic
  - `nutrient_calculator.py`: totals per 100 g
  - `unit_normalizer.py`: unit normalization + conversions

### Application (`application/`)

- `use_cases.py`:
  - SearchFoodsUseCase
  - AddIngredientUseCase
  - CalculateTotalsUseCase
  - SaveFormulationUseCase
  - LoadFormulationUseCase
  - ExportFormulationUseCase
  - AdjustFormulationUseCase

### Infrastructure (`infrastructure/`)

- `api/cache.py`: cache interface + implementations
- `api/usda_repository.py`: USDA FoodData Central client
- `persistence/json_repository.py`: save/load formulations
- `persistence/excel_exporter.py`: Excel export
- `persistence/formulation_importer.py`: import helper

### UI (`ui/`)

- `main_window.py`: window composition and signal wiring
- `tabs/`: Search, Formulation, Label UI
- `presenters/`: search/formulation/label orchestration
- `adapters/`: UI <-> domain mapping
- `delegates/`: table delegate styling/editing
- `workers.py`: background tasks

### Config (`config/`)

- `constants.py`: app constants, roles, defaults
- `container.py`: dependency injection container

## Data Flow Example (Add Ingredient)

```
UI (Search tab) -> SearchPresenter.search()
  -> SearchFoodsUseCase.execute()
  -> USDAFoodRepository.search()

UI (Formulation tab) -> FormulationPresenter.add_ingredient_from_details()
  -> normalize_nutrients() (domain/services/nutrient_normalizer.py)
  -> domain models updated
  -> totals calculated via CalculateTotalsUseCase
```

## Testing Strategy

- Unit tests: domain + application services
- Integration tests: presenters/adapters
- Manual UI testing for Qt-specific flows
