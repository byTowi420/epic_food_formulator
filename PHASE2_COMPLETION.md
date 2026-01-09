# Fase 2 - Estado Actual

## Resumen

La fase 2 (CRUD + sincronización UI/Domain) está completada. Las operaciones clave de Formulación están conectadas al presenter y los cálculos usan servicios de dominio. La etiqueta se calcula desde `ui/presenters/label_presenter.py`.

## Operaciones Migradas

- Búsqueda: `SearchPresenter`
- Agregar/Quitar ingredientes: `FormulationPresenter`
- Editar cantidades y locks: `FormulationPresenter`
- Totales nutricionales: `CalculateTotalsUseCase`
- Guardar/Cargar JSON: `JSONFormulationRepository`
- Exportar Excel: `ExportFormulationUseCase` (con fallback legado)
- Etiqueta: `LabelPresenter`

## Notas

- Se mantiene un estado dual temporal (lista UI + dominio) para evitar regresiones.
- Normalización centralizada en `domain/services/nutrient_normalizer.py` y conversiones en `domain/services/unit_normalizer.py`.

## Pendientes (opcionales)

- Consolidar estado dual
- Ampliar el runtime trace para cubrir handlers raros
