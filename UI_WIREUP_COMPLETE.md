# UI Wireup - Current Status

**Status**: Complete (core features wired to presenters)

## What Is Wired Today

- Search flows via `SearchPresenter` -> `SearchFoodsUseCase`
- Formulation flows via `FormulationPresenter` (add/remove/edit/locks)
- Totals calculation via `CalculateTotalsUseCase`
- Save/load via `JSONFormulationRepository`
- Excel export via `ExportFormulationUseCase` (+ legacy fallback)
- Label rendering via `LabelPresenter`

## Key Decisions

1. **Presenters as orchestration**
   - UI tabs call presenters only.
2. **Single USDA access point**
   - `USDAFoodRepository` is the only API entry point.
3. **Normalization centralized**
   - `domain/services/nutrient_normalizer.py` for USDA data
   - `domain/services/unit_normalizer.py` for conversions
4. **Dual state (temporary)**
   - UI list + domain formulation are still kept in sync.

## Validation Checklist (current)

- Search results load and paginate
- Ingredients add/remove/edit correctly
- Locks behave as expected
- Totals and label preview update
- Save/load JSON works
- Excel export works

## Remaining Work (optional)

- Remove dual state
- Expand runtime trace for rare error handlers
