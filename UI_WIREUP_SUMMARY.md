# UI Wireup Summary (Current)

## Overview

The UI is wired to presenters and use cases. USDA access is centralized in `infrastructure/api/usda_repository.py`, and label calculations live in `ui/presenters/label_presenter.py`.

## Current Wiring

- **Search**: Search tab -> `SearchPresenter`
- **Formulation**: Formulation tab -> `FormulationPresenter`
- **Label**: Label tab -> `LabelPresenter`
- **Persistence**: JSON + Excel via use cases
- **Normalization**: `services/nutrient_normalizer.py` + `domain/services/unit_normalizer.py`

## Notes

- Formulation state is still dual (UI list + domain formulation) and synced by the presenter.
- Excel export uses the use case; the legacy fallback remains for safety.

## Next Cleanups (optional)

- Remove dual state and use presenter as the single source of truth.
- Review unused error handlers after a broader runtime trace.
