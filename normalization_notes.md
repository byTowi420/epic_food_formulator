Guia de normalizacion de nutrientes (USDA) - referencia rapida
====================================================================

Energia
-------
- Conservar solo `Energy (kcal)` y `Energy (kJ)`.
- Eliminar: `Energy (Atwater General Factors)`, `Energy (Atwater Specific Factors)`.
- Si falta kcal, calcular siempre por macros: `kcal = 4*protein + 4*carbs + 9*fat`; `kJ = kcal * 4.184`.

Grasas totales
--------------
- Mantener un total canonico (se usan ambos nombres pero se espejan):
  - `Total fat (NLEA)` y `Total lipid (fat)`
- SFA/MUFA/PUFA: mantener totales; usar desgloses solo si los necesitas.
- Trans: conservar `Fatty acids, total trans` y evitar duplicados de subespecies si no se usan.

Carbohidratos
-------------
- Conservar: `Carbohydrate, by difference`, `Fiber, total dietary`, `Sugars, Total`.
- `Carbohydrate, by summation` se trata como alias y no se exporta.

Proteina / Nitrogeno
--------------------
- Conservar `Protein`.
- `Nitrogen` solo si necesitas calculo interno; no exportar ambos.

Colina / Folato / Vitaminas
---------------------------
- Colina: conservar `Choline, total`; subcomponentes solo para rellenar.
- Folato: elegir `Folate, total` o `Folate, DFE` (no ambos).
- Vitamina A: conservar `Vitamin A, RAE`; IU y carotenos solo si hay desglose.
- Vitamina D: conservar `Vitamin D (D2 + D3) (μg)`; IU opcional.
- Vitamina K: conservar `Vitamin K (phylloquinone)`.

Unidades
--------
- Canonicas: g, mg, μg, kcal, kJ.
- Alias validos: ug / µg / μg -> μg.

Implementacion
-------------
- Normalizacion USDA: `services/nutrient_normalizer.py`
- Conversiones: `domain/services/unit_normalizer.py`
