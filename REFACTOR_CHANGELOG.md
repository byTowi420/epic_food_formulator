# Refactor Changelog - Current Snapshot

## Current State

- Clean Architecture layers are in place and used by the UI presenters.
- USDA access is centralized in `infrastructure/api/usda_repository.py`.
- Label calculations live in `ui/presenters/label_presenter.py` (no domain label_generator).
- Unit normalization is centralized in `domain/services/unit_normalizer.py` and USDA nutrient normalization in `services/nutrient_normalizer.py`.
- `NutrientCalculator` now focuses on totals per 100 g.

## Initial Refactor Summary

- Domain models + exceptions
- Domain services (formulation + nutrients + units)
- Application use cases
- Infrastructure repository + cache + persistence
- Dependency injection container
- Tests (unit + integration)

## Post-Refactor Updates

- Removed legacy USDA API client (`services/usda_api.py`).
- Removed deprecated label generator service and tests.
- Cleaned unused helper methods based on runtime audit.
- Added runtime trace tooling in `tools/` for dead-code review.

## Current File Layout (key parts)

```
application/use_cases.py
config/constants.py
config/container.py

domain/models.py
domain/exceptions.py
domain/services/
  formulation_service.py
  nutrient_calculator.py
  unit_normalizer.py

infrastructure/api/
  cache.py
  usda_repository.py
infrastructure/persistence/
  json_repository.py
  excel_exporter.py
  formulation_importer.py

services/nutrient_normalizer.py

ui/presenters/
  search_presenter.py
  formulation_presenter.py
  label_presenter.py
```
