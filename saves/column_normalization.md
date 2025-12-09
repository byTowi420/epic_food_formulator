Guía de normalización y columnas finales (DeTodoElVerdaderoFull.xlsx)
====================================================================

Estrategia general
------------------
- Energía: siempre calcular `Energy (kcal)` = 4*protein + 4*carbs + 9*fat y `Energy (kJ)` = kcal*4.184. Eliminar Atwater (General/Specific).
- Totales duplicados: mantener un total por macro (`Total fat (NLEA)`, `Carbohydrate, by difference`, `Protein`). `Total lipid (fat)` se absorbe en `Total fat (NLEA)`.
- Desgloses y sumas:
  - Azúcares específicos solo para rellenar `Sugars, Total` si falta; no exportar ambos (total + todos los específicos) salvo que necesites el desglose.
  - Cystine y Cysteine: combinarlas y reportar una sola (suma).
  - Choline: conservar solo `Choline, total`; subcomponentes solo para rellenar.
  - Vitamina A: conservar `Vitamin A, RAE`; descartar IU y carotenos si no necesitas el desglose (si quieres carotenoides, conservar solo `Lutein + zeaxanthin`).
  - Vitamina D: conservar `Vitamin D (D2 + D3) (µg)` (IU opcional); descartar D2/D3 separados si no hay desglose.
  - Vitamina E: conservar `Vitamin E (alpha-tocopherol)`; descartar tocopheroles/tocotrienoles salvo que necesites desglose.
- Lípidos detallados: conservar totales SFA/MUFA/PUFA/Trans y un subconjunto de especies clave; descartar isómeros genéricos/duplicados.
- Columnas casi siempre vacías (ácidos orgánicos, isoflavonas, etc.) pueden eliminarse si no se usan.

Columnas finales sugeridas (orden y grupos del Excel)
-----------------------------------------------------
1) Detalles de formulación  
   FDC ID, Ingrediente, Marca / Origen, Tipo de dato, Cantidad (g), Cantidad (%)

2) Proximates  
   Water (g)  
   Energy (kcal)  ← calculada siempre  
   Energy (kJ)    ← calculada siempre  
   Nitrogen (g) (Si no existe calcularlo como Protein/6.25)
   Protein (g)  
   Total lipid (fat) (g) (Se completa con valores de Total fat (NLEA))
   Total fat (NLEA) (g)  (Se completa con valores de Total lipid (fat))  
   Ash (g)  
   Carbohydrate, by difference (g)

3) Carbohydrates  
   Fiber, total dietary (g)  
   Sugars, Total (g)  
   Starch (g)  
   Resistant starch (g)
   exportar específicos En el orden del excel pero subiendo el Starch 


4) Minerals  
   Calcium, Ca (mg)  
   Iron, Fe (mg)  
   Magnesium, Mg (mg)  
   Phosphorus, P (mg)  
   Potassium, K (mg)  
   Sodium, Na (mg)  
   Zinc, Zn (mg)  
   Copper, Cu (mg)  
   Manganese, Mn (mg)  
   Iodine, I (µg)  
   Selenium, Se (µg)  
   Molybdenum, Mo (µg)  
   Fluoride, F (µg) (opcional)

5) Vitamins and Other Components  
   Vitamin C, total ascorbic acid (mg)  
   Thiamin (mg)  
   Riboflavin (mg)  
   Niacin (mg)  
   Pantothenic acid (mg)  
   Vitamin B-6 (mg)  
   Biotin (µg)  
   Folate, total (µg)  (o Folate, DFE; elegir una)  
   Choline, total (mg)  
   Vitamin B-12 (µg)  
   Vitamin A, RAE (µg)  
   Vitamin E (alpha-tocopherol) (mg)  
   Vitamin D (D2 + D3) (µg)  (IU opcional)  
   Vitamin K (phylloquinone) (µg)  
   (Opcional) Lutein + zeaxanthin (µg)

6) Lipids  
   Fatty acids, total saturated (g)  
     - SFA 14:0 (g), SFA 16:0 (g), SFA 18:0 (g) (principales)  
   Fatty acids, total monounsaturated (g)  
     - MUFA 16:1 c (g), MUFA 18:1 c (g)  
   Fatty acids, total polyunsaturated (g)  
     - PUFA 18:2 n-6 c,c (g), PUFA 18:3 n-3 (ALA) (g)  
     - PUFA 20:4 n-6 (g), PUFA 20:5 n-3 (EPA) (g)  
     - PUFA 22:5 n-3 (DPA) (g), PUFA 22:6 n-3 (DHA) (g)  
   Fatty acids, total trans (g) (y opcional total trans-monoenoic)  
   Cholesterol (mg)

7) Amino acids  
   Tryptophan, Threonine, Isoleucine, Leucine, Lysine, Methionine, Phenylalanine, Tyrosine, Valine, Arginine, Histidine, Alanine, Aspartic acid, Glutamic acid, Glycine, Proline, Serine  
   Cysteine (g) ← suma de Cystine + Cysteine  

8) Otros (opcionales)  
   Phytosterols (mg) (total)  
   Ácidos orgánicos / oligosacáridos / isoflavonas solo si los usas; de lo contrario, eliminarlos.

Eliminar o usar solo para cálculo (no exportar)
-----------------------------------------------
- Energy (Atwater General Factors), Energy (Atwater Specific Factors)     
- Cystine duplicada (sumarla en Cysteine)  
- Columnas casi siempre vacías: ácidos orgánicos, isoflavonas, oligosacáridos, etc., salvo uso explícito.
