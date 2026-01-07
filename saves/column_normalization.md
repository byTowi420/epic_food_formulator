Guia de normalizacion y columnas finales (Excel)
=====================================================

Estrategia general
------------------
- Energia: siempre calcular `Energy (kcal)` = 4*protein + 4*carbs + 9*fat y `Energy (kJ)` = kcal*4.184.
- Totales duplicados: mantener un total por macro (`Total fat (NLEA)`, `Carbohydrate, by difference`, `Protein`).
  `Total lipid (fat)` se espeja con `Total fat (NLEA)`.
- Desgloses: usar componentes solo para completar el total si falta; evitar exportar total + desglose completo.

Columnas finales sugeridas (orden)
----------------------------------
1) Detalles de formulacion
   - FDC ID, Ingrediente, Marca/Origen, Tipo de dato, Cantidad (unidad), Cantidad (%)

2) Proximate
   - Water (g)
   - Energy (kcal)
   - Energy (kJ)
   - Nitrogen (g) (si se calcula, no exportar junto a Protein)
   - Protein (g)
   - Total lipid (fat) (g)
   - Total fat (NLEA) (g)
   - Ash (g)
   - Carbohydrate, by difference (g)

3) Carbohydrates
   - Fiber, total dietary (g)
   - Sugars, Total (g)
   - Starch (g)
   - Resistant starch (g)

4) Minerals
   - Calcium, Ca (mg)
   - Iron, Fe (mg)
   - Magnesium, Mg (mg)
   - Phosphorus, P (mg)
   - Potassium, K (mg)
   - Sodium, Na (mg)
   - Zinc, Zn (mg)
   - Copper, Cu (mg)
   - Manganese, Mn (mg)
   - Iodine, I (μg)
   - Selenium, Se (μg)
   - Molybdenum, Mo (μg)
   - Fluoride, F (μg) (opcional)

5) Vitamins and other
   - Vitamin C, total ascorbic acid (mg)
   - Thiamin (mg)
   - Riboflavin (mg)
   - Niacin (mg)
   - Pantothenic acid (mg)
   - Vitamin B-6 (mg)
   - Biotin (μg)
   - Folate, total (μg) (o Folate, DFE; elegir una)
   - Choline, total (mg)
   - Vitamin B-12 (μg)
   - Vitamin A, RAE (μg)
   - Vitamin E (alpha-tocopherol) (mg)
   - Vitamin D (D2 + D3) (μg) (IU opcional)
   - Vitamin K (phylloquinone) (μg)

6) Lipids
   - Fatty acids, total saturated (g)
   - Fatty acids, total monounsaturated (g)
   - Fatty acids, total polyunsaturated (g)
   - Fatty acids, total trans (g)
   - Cholesterol (mg)

7) Amino acids (si se exportan)
   - Tryptophan, Threonine, Isoleucine, Leucine, Lysine, Methionine,
     Phenylalanine, Tyrosine, Valine, Arginine, Histidine, Alanine,
     Aspartic acid, Glutamic acid, Glycine, Proline, Serine, Cysteine

Eliminar o usar solo para calculo
---------------------------------
- Energy (Atwater General Factors)
- Energy (Atwater Specific Factors)
- Duplicados de azucares cuando ya existe `Sugars, Total`
- Columnas casi siempre vacias (acidos organicos, isoflavonas, etc.) salvo uso explicito
