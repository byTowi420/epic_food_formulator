# Food Formulator Refactor Plan

This document is the persistent reference for the refactor roadmap, structure,
and the prompt template to keep future work consistent across machines/sessions.

## Current Status

- Phase 1 (API unification): **Completed** (USDA access goes through `infrastructure/api/usda_repository.py`).
- Phase 2 (unit normalization): **Completed** (`domain/services/unit_normalizer.py` + `services/nutrient_normalizer.py`).
- Phase 3 (UI logic extraction): **Completed** for Search/Formulation/Label via presenters.
- Current focus: runtime audit + cleanup of unused code.

## Constraints (must keep)

- No changes to UI aesthetics or user-facing behavior.
- Keep each tab logic separate (Search, Formulation, Label).
- Only share common logic through DTOs/use cases/presenters.
- Prefer `infrastructure/api/usda_repository.py` as the single USDA entry point.
- Centralize unit normalization and conversions in one place.

## Goals (now maintained)

1) Unify API flow
   - Use `infrastructure/api/usda_repository.py` as the only path to USDA.
2) Move UI logic to presenters/use cases
   - UI triggers actions and renders DTOs only.
3) Centralize normalization and unit conversions
   - One module for unit normalization (μg, mg, kcal, kJ, mass units).

## Current Structure (implemented)

application/
  use_cases.py

config/
  constants.py
  container.py

domain/
  models.py
  exceptions.py
  services/
    nutrient_calculator.py
    formulation_service.py
    unit_normalizer.py

infrastructure/
  api/
    usda_repository.py
    cache.py
  persistence/
    json_repository.py
    excel_exporter.py
    formulation_importer.py

services/
  nutrient_normalizer.py

ui/
  presenters/
    search_presenter.py
    formulation_presenter.py
    label_presenter.py
  tabs/
    search_tab.py
    formulation_tab.py
    label_tab.py
  adapters/
    formulation_mapper.py
  delegates/
    label_table_delegate.py
  workers.py

## Future Features (placeholders only)

Costs (IMPORTANT: must be costs_tab.py AND sections inside Formulation tab)
- ui/tabs/costs_tab.py
- ui/tabs/formulation_tab.py (cost section)
- domain/services/cost_calculator.py
- application/use_cases/calculate_costs.py

Manual ingredients (non-USDA)
- infrastructure/api/local_food_repository.py
- application/use_cases/create_manual_food.py
- UI dialog for manual ingredient input

Formulation comparison (nutrition + costs)
- application/use_cases/compare_formulations.py
- ui/tabs/comparison_tab.py

## Prompt Template (use after refactor)

Title: Implement <feature> while respecting project structure

Context:
- Project uses layered architecture (domain/application/infrastructure/ui).
- UI tabs are separate; keep logic per tab.
- No UI aesthetics or behavior changes unless explicitly requested.

Goals:
1) <goal 1>
2) <goal 2>

Constraints:
- Use `infrastructure/api/usda_repository.py` for USDA access.
- Use `domain/services/unit_normalizer.py` for conversions.
- Use `services/nutrient_normalizer.py` for USDA nutrient normalization.
- Do not move logic into `ui/tabs`; use presenters + use cases.
- Keep Search, Formulation, Label logic in separate presenters/files.

Files expected to change:
- <list>

Definition of done:
- <checks>

Non-goals:
- UI restyling
- behavior changes not requested
