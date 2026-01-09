# UI Integration Guide (Current)

This guide reflects the **current** UI architecture. The UI is already wired to presenters; legacy `services/usda_api.py` is removed.

## Current Wiring

- **Search**: `SearchPresenter` -> `SearchFoodsUseCase` -> `USDAFoodRepository`
- **Formulation**: `FormulationPresenter` -> use cases/services
- **Label**: `LabelPresenter` drives label calculations and formatting

Shared helpers:
- `domain/services/nutrient_normalizer.py` for USDA nutrient normalization
- `domain/services/unit_normalizer.py` for unit conversions

## Rules for New UI Work

1. **UI tabs only trigger actions and render DTOs**.
2. **Presenters own orchestration** (they call use cases and normalize data).
3. **Keep each tab isolated**; share logic via presenters/use cases only.
4. **No direct USDA calls from UI**; always go through `USDAFoodRepository` via the container.

## Minimal Example (Search)

```python
# ui/tabs/search_tab.py
results = self.search_presenter.search(
    query=query,
    page_size=page_size,
    include_branded=include_branded,
    page_number=page,
)
self._render_search_results(results)
```

## Minimal Example (Add Ingredient)

```python
# ui/tabs/formulation_tab.py
nutrients = self.formulation_presenter.add_ingredient_from_details(details, amount_g)
self._refresh_tables(nutrients)
```

## If You Need a New Use Case

1. Add the use case in `application/use_cases.py`.
2. Wire it in `config/container.py`.
3. Call it from the relevant presenter.
4. Render the returned DTOs in the tab.

## Debugging Tip

Use the runtime trace tool for coverage of UI flows:

```bash
python tools/run_with_trace.py
python tools/audit_report.py
```
