Guía de normalización de nutrientes (USDA) — referencia rápida
===============================================================

Energía
-------
- Conservar solo `Energy (kcal)` y `Energy (kJ)`.
- Eliminar: `Energy (Atwater General Factors)`, `Energy (Atwater Specific Factors)`.
- Si falta kcal, calcularla siempre de macros: `kcal = 4*protein + 4*carbs + 9*fat`; kJ = kcal * 4.184.

Grasas totales
--------------
- Conservar un total: `Total fat (NLEA)` como canónico.
- Mapear/combinar: `Total lipid (fat)` → `Total fat (NLEA)` (usar el que exista; si ambos, usar NLEA).
- SFA/MUFA/PUFA: mantener solo los totales si no se usa desglose fino. Si se usa desglose:
  - Evitar duplicados genéricos: preferir isomería explícita (`… c`, `n-3/n-6`) y descartar variantes genéricas (ej. `PUFA 18:2` si hay `PUFA 18:2 n-6 c,c`).
  - Trans: elegir o bien solo el total (`Fatty acids, total trans`) o solo algunas especies, pero no ambos.

Carbohidratos
-------------
- Conservar: `Carbohydrate, by difference`, `Fiber, total dietary`, `Sugars, Total`.
- Opcional: usar azúcares específicos solo para rellenar `Sugars, Total` si falta; luego no exportar ambos (total + desglose) para evitar duplicados.
- Eliminar: `Carbohydrate, by summation` (equivalente).

Proteína / Nitrógeno
--------------------
- Conservar: `Protein`.
- Eliminar o usar solo para cálculo: `Nitrogen` (no reportar ambos).

Aminoácidos
-----------
- Una métrica por aminoácido. Combinar `Cystine`/`Cysteine` en una sola clave (suma).
- Eliminar duplicados exactos de nombres equivalentes.

Colina / Folato / Vit. A / Vit. D / Vit. K
------------------------------------------
- Colina: conservar `Choline, total`; subcomponentes solo para rellenar el total, no exportar todos.
- Folato: conservar `Folate, total` o `Folate, DFE`; eliminar `Folic acid` y `Folate, food` como columnas separadas (o solo para cálculo).
- Vitamina A: conservar `Vitamin A, RAE` (opcional IU). Retinol/carotenos solo si quieres desglose; si no, úsalos para rellenar RAE y no exportarlos todos.
- Vitamina D: conservar `Vitamin D (D2 + D3) (µg)` (opcional IU); D2/D3 separados solo si necesitas desglose, si no descártalos tras sumar.
- Vitamina K: conservar `Vitamin K (phylloquinone)`; otras variantes solo si las usas.

Tocoferoles / Tocotrienoles
---------------------------
- Conservar `Vitamin E (alpha-tocopherol)`; el resto solo si necesitas desglose. Si hay `Vitamin E, added`, decide si lo sumas al alpha o lo muestras aparte, pero evita duplicar el total.

Azúcares y otros desgloses
--------------------------
- Azúcares: o bien `Sugars, Total` o los específicos, no ambos en export. Puedes sumar específicos para rellenar el total si falta.
- Oligosacáridos (raffinose/stachyose/verbascose), ácidos orgánicos, isoflavonas: ocultar/descartar si no se usan.

Regla general de combinación/eliminación
----------------------------------------
- Para cada pareja “total + componentes”, decide: o conservas el total, o el desglose, pero no ambos en export.
- Usa componentes para rellenar el total si está vacío; después elimina los componentes si no se reportarán.
- Mantén unidades en minúscula; infiere unidad por número/alias si falta.
