# UI Integration Summary (Current)

## Components in Use

- **Presenters**: `FormulationPresenter`, `SearchPresenter`, `LabelPresenter`
- **Adapters**: `FormulationMapper`, `NutrientDisplayMapper`
- **Use cases**: `SearchFoodsUseCase`, `AddIngredientUseCase`, `CalculateTotalsUseCase`, `SaveFormulationUseCase`, `LoadFormulationUseCase`, `ExportFormulationUseCase`, `AdjustFormulationUseCase`
- **Repositories**: `USDAFoodRepository`, `JSONFormulationRepository`
- **Normalization**: `domain/services/nutrient_normalizer.py`
- **Units**: `domain/services/unit_normalizer.py`

## Flow Snapshot

```
UI Tabs -> Presenters -> Use Cases -> Domain Services
                         |
                         v
                 Infrastructure (API / Persistence)
```

## Integration Rules

- UI tabs should not call repositories directly.
- Presenters return DTOs; UI renders them.
- Keep tab logic separated; share only through presenters/use cases.

## Known Temporary State

- Dual state in formulation (UI list + domain formulation). Planned cleanup after audits.
