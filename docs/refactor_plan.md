# Food Formulator Refactor Plan

This document is the persistent reference for the refactor roadmap, structure,
and the prompt template to keep future work consistent across machines/sessions.

## Constraints (must keep)
- No changes to UI aesthetics or user-facing behavior.
- Keep each tab logic separate (Search, Formulation, Label).
- Only share common logic through DTOs and use cases.
- Prefer infrastructure/api/usda_repository.py as the single API entry point.
- Centralize unit normalization and conversions in one place.

## Goals
1) Unify API flow
   - Use infrastructure/api/usda_repository.py as the only path to USDA.
   - Remove or wrap services/usda_api.py (compat wrapper only if needed).
2) Move UI logic to presenters/use cases
   - UI should trigger actions and render DTOs only.
   - No calculations or API logic inside tabs.
3) Centralize normalization and unit conversions
   - One module for unit normalization (mg, ug, kcal, kJ).
   - No duplicate conversions in UI or infrastructure.

## Phases and Estimate
- Phase 1: Unify API flow
  - Estimate: 0.5 to 1.5 days
  - Output: repository-based API only; optional wrapper for legacy calls.
- Phase 2: Centralize normalization and units
  - Estimate: 1 to 2 days
  - Output: single normalizer + conversion helpers used everywhere.
- Phase 3: Extract UI logic to presenters/use cases
  - Estimate: 3 to 6 days
  - Output: tabs only render DTOs and dispatch actions.

Total estimate: 5 to 10 business days with user review per phase.

## Proposed Structure (target)
application/
  dto/
    search_dto.py
    formulation_dto.py
    label_dto.py
  ports/
    food_repository.py
  use_cases/
    search_foods.py
    get_food_details.py
    add_ingredient.py
    calculate_totals.py
    export_formulation.py
    save_formulation.py
    load_formulation.py
    adjust_formulation.py
    generate_label.py

domain/
  models.py
  exceptions.py
  services/
    nutrient_calculator.py
    formulation_service.py
    label_generator.py
    unit_normalizer.py

infrastructure/
  api/
    usda_repository.py
    cache.py
  persistence/
    json_repository.py
    excel_exporter.py

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

services/
  usda_api.py  # optional temporary wrapper only; remove later

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
- Project uses Clean Architecture (domain/application/infrastructure/ui).
- UI tabs are separate; keep logic per tab.
- No UI aesthetics or behavior changes unless explicitly requested.

Goals:
1) <goal 1>
2) <goal 2>

Constraints:
- Use infrastructure/api/usda_repository.py for USDA access.
- Use domain/services/unit_normalizer.py for unit conversions.
- Do not move logic into ui/tabs; use presenters + DTOs + use cases.
- Keep Search, Formulation, Label logic in separate presenters/files.

Files expected to change:
- <list>

Definition of done:
- <checks>

Non-goals:
- UI restyling
- behavior changes not requested
