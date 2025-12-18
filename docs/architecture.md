# Architecture Documentation

## Overview

This project follows **Clean Architecture** principles, separating concerns into distinct layers with clear dependencies.

## Layer Structure

```
┌─────────────────────────────────────────────────┐
│              UI Layer (PySide6)                 │
│     (Widgets, Presenters, MainWindow)           │
└──────────────────┬──────────────────────────────┘
                   │ depends on
┌──────────────────▼──────────────────────────────┐
│          Application Layer                      │
│    (Use Cases - Business Workflows)             │
└────┬──────────────────────────────┬─────────────┘
     │ depends on                   │ depends on
┌────▼──────────────┐      ┌────────▼──────────┐
│   Domain Layer    │      │ Infrastructure    │
│  (Business Logic) │◄─────┤  (External APIs)  │
│   Models          │      │  Cache, Persist   │
│   Services        │      │  Normalizers      │
└───────────────────┘      └───────────────────┘
```

## Dependency Rule

**Inner layers never depend on outer layers:**
- Domain has NO dependencies (pure business logic)
- Application depends on Domain + Infrastructure interfaces
- Infrastructure implements domain interfaces
- UI depends on Application + Domain models

## Layers

### 1. Domain Layer (`domain/`)

Pure business logic with no external dependencies.

```
domain/
├── models.py           # Entities (Food, Ingredient, Formulation, Nutrient)
├── exceptions.py       # Domain-specific exceptions
└── services/
    ├── nutrient_calculator.py    # Nutrient calculations
    ├── formulation_service.py    # Formulation operations
    └── label_generator.py        # FDA label generation
```

**Responsibilities:**
- Define core business entities
- Implement business rules and calculations
- Validate business constraints

**Key Principles:**
- Immutable value objects (Food, Nutrient)
- Mutable entities (Ingredient, Formulation)
- Uses Decimal for precision
- Framework-agnostic

### 2. Application Layer (`application/`)

Orchestrates use cases by coordinating domain services and infrastructure.

```
application/
└── use_cases.py       # Business workflows
```

**Use Cases:**
- `SearchFoodsUseCase`: Search USDA database
- `AddIngredientUseCase`: Add ingredient with normalization
- `CalculateTotalsUseCase`: Calculate nutrient totals
- `SaveFormulationUseCase`: Persist formulation
- `LoadFormulationUseCase`: Load formulation
- `ExportFormulationUseCase`: Export to Excel
- `AdjustFormulationUseCase`: Adjust with locks

**Responsibilities:**
- Define application workflows
- Coordinate domain + infrastructure
- Transaction boundaries
- Error handling for business flows

### 3. Infrastructure Layer (`infrastructure/`)

External concerns: APIs, databases, file I/O.

```
infrastructure/
├── api/
│   ├── cache.py              # Cache abstraction + implementations
│   └── usda_repository.py    # USDA API client (Repository pattern)
├── normalizers/
│   └── usda_normalizer.py    # USDA data normalization
└── persistence/
    ├── json_repository.py    # JSON file persistence
    └── excel_exporter.py     # Excel export
```

**Responsibilities:**
- Implement infrastructure interfaces
- Handle external API communication
- Manage caching
- File I/O operations

**Key Patterns:**
- Repository pattern for data access
- Cache abstraction (InMemoryCache, NullCache)
- Adapter pattern for USDA API

### 4. UI Layer (`ui/`)

Presentation layer using PySide6 (Qt).

**Current State:**
- `main_window.py`: Monolithic window (needs refactoring)
- `workers.py`: Background threading

**Target State (for future refactor):**
```
ui/
├── main_window.py         # Coordinator only (< 500 lines)
├── widgets/
│   ├── ingredients_table.py
│   ├── nutrients_table.py
│   └── label_widget.py
└── presenters/
    └── formulation_presenter.py
```

### 5. Configuration Layer (`config/`)

Application configuration and constants.

```
config/
├── constants.py    # All magic numbers/strings
└── container.py    # Dependency Injection
```

## Key Design Patterns

### Repository Pattern
```python
class FoodRepository(ABC):
    @abstractmethod
    def search(self, query: str) -> List[Dict]: ...

class USDAFoodRepository(FoodRepository):
    def search(self, query: str) -> List[Dict]:
        # Implementation with caching
```

**Benefits:**
- Decouples domain from data source
- Enables testing with mock repositories
- Swappable implementations

### Dependency Injection
```python
# config/container.py
class Container:
    @property
    def add_ingredient(self) -> AddIngredientUseCase:
        return AddIngredientUseCase(
            food_repository=self.food_repository,
            formulation_service=self.formulation_service,
        )
```

**Benefits:**
- Centralized dependency management
- Easy testing (inject mocks)
- Clear dependency graph

### Use Case Pattern
```python
class AddIngredientUseCase:
    def __init__(self, food_repository, formulation_service):
        self._food_repo = food_repository
        self._formulation_service = formulation_service

    def execute(self, formulation, fdc_id, amount_g):
        # Orchestrate domain + infrastructure
```

**Benefits:**
- Clear business workflows
- Single responsibility
- Testable without UI

## Data Flow Example

**User adds an ingredient:**

```
1. UI: User clicks "Add Ingredient" with FDC ID 12345

2. UI calls Use Case:
   container.add_ingredient.execute(formulation, 12345, Decimal("100"))

3. Use Case orchestrates:
   a) Repository fetches from USDA API (with caching)
   b) Normalizer processes nutrient data
   c) Use Case creates domain Food model
   d) Domain Formulation validates and adds Ingredient

4. UI updates:
   a) Use Case returns Food
   b) UI recalculates totals via CalculateTotalsUseCase
   c) UI refreshes tables
```

## Testing Strategy

### Unit Tests (`tests/unit/`)
- Test domain models in isolation
- Test domain services with fake data
- Test use cases with mock repositories
- Fast, no I/O

### Integration Tests (`tests/integration/`)
- Test infrastructure with real APIs (or test API)
- Test persistence with temp files
- Slower, real I/O

### Coverage Goals
- Domain layer: 100%
- Application layer: >90%
- Infrastructure: >80%
- UI: Manual testing + smoke tests

## Migration Strategy

### Current State
- Most logic in `ui/main_window.py` (4554 lines)
- Tightly coupled UI and business logic
- Original code still in `services/` folder

### New Code Location
- All new clean code in proper layers
- Original code remains functional
- Gradual migration possible

### Integration Points

**To use new architecture in existing UI:**

```python
# In MainWindow.__init__
from config.container import Container

self.container = Container()

# To add ingredient (old way replaced):
def add_ingredient_new_way(self, fdc_id: int):
    # Create domain formulation from current state
    formulation = self._convert_to_domain_formulation()

    # Use new use case
    food = self.container.add_ingredient.execute(
        formulation, fdc_id, Decimal("100")
    )

    # Update UI from domain formulation
    self._update_ui_from_formulation(formulation)
```

## Benefits of This Architecture

1. **Testability**: Domain logic fully testable without UI
2. **Maintainability**: Clear separation of concerns
3. **Flexibility**: Easy to swap implementations (different DB, API client)
4. **Scalability**: Add features without touching existing code
5. **Clarity**: Each layer has single responsibility
6. **Reusability**: Domain logic reusable in CLI, web API, etc.

## Next Steps for Full Migration

1. Extract widgets from MainWindow
2. Implement Presenter pattern
3. Refactor MainWindow to use Presenters and Use Cases
4. Remove old services/ code once migration complete
5. Add integration tests
6. Add pre-commit hooks (ruff, black, mypy)

## Dependencies Graph

```
main.py
  └─> ui/main_window.py
        └─> config/container.py
              ├─> application/use_cases.py
              │     ├─> domain/services/*.py
              │     ├─> domain/models.py
              │     └─> infrastructure/**/*.py
              └─> domain/**/*.py
```

## References

- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
