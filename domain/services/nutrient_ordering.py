from __future__ import annotations

from typing import Any, Dict, List, Tuple

from domain.services.unit_normalizer import canonical_unit
from domain.services.nutrient_normalizer import canonical_alias_name


class NutrientOrdering:
    """Provide consistent nutrient ordering, keys, and categories."""

    def __init__(self, catalog: List[Tuple[str, List[str]]] | None = None) -> None:
        self._catalog = catalog or build_nutrient_catalog()
        self._order_map: Dict[str, int] = {}
        self._category_map: Dict[str, str] = {}
        for idx, (_, names) in enumerate(self._catalog):
            for offset, name in enumerate(names):
                key = name.strip().lower()
                self._order_map[key] = idx * 1000 + offset
                self._category_map[key] = self._catalog[idx][0]
        self._reference_order_map: Dict[str, Dict[str, Any]] = {}
        self._unit_map = build_nutrient_unit_map()

    @property
    def catalog(self) -> List[Tuple[str, List[str]]]:
        return self._catalog

    def order_for_name(self, name: str) -> int | None:
        return self._order_map.get((name or "").strip().lower())

    def nutrient_key(self, nutrient: Dict[str, Any]) -> str:
        """Build a consistent key for nutrients, preferring id then number then name."""
        name_lower = (nutrient.get("name") or "").strip().lower()
        unit_lower = (nutrient.get("unitName") or "").strip().lower()
        if name_lower == "energy" and unit_lower:
            return f"energy:{unit_lower}"
        if name_lower == "water":
            return f"water|{unit_lower}"
        if "id" in nutrient and nutrient["id"] is not None:
            return f"id:{nutrient['id']}"
        if nutrient.get("number"):
            return f"num:{nutrient['number']}"
        return f"name:{name_lower}" if name_lower else ""

    def reference_info(self, nutrient: Dict[str, Any]) -> Dict[str, Any]:
        key = self.nutrient_key(nutrient)
        return self._reference_order_map.get(key, {})

    def update_reference_from_details(self, details: Dict[str, Any]) -> None:
        nutrients = details.get("foodNutrients", []) or []
        if not nutrients:
            return
        current_category: str | None = None
        for entry in nutrients:
            nut = entry.get("nutrient") or {}
            key = self.nutrient_key(nut)
            if not key:
                continue
            if entry.get("amount") is None:
                current_category = (nut.get("name") or "").strip() or current_category
                self._reference_order_map.setdefault(
                    key,
                    {
                        "rank": nut.get("rank"),
                        "category": current_category,
                        "unit": nut.get("unitName"),
                    },
                )
                continue
            self._reference_order_map[key] = {
                "rank": nut.get("rank"),
                "category": current_category,
                "unit": nut.get("unitName"),
            }

    def sort_nutrients_for_display(self, nutrients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not nutrients:
            return []
        indexed = []
        for idx, entry in enumerate(nutrients):
            nut = entry.get("nutrient") or {}
            order = self.nutrient_order(nut, idx + 10000)
            indexed.append((order, idx, entry))
        indexed.sort(key=lambda t: (t[0], t[1]))
        return [item[2] for item in indexed]

    def header_key(self, nutrient: Dict[str, Any]) -> tuple[str, str, str]:
        name = canonical_alias_name(nutrient.get("name", "") or "")
        unit = canonical_unit(nutrient.get("unitName") or self.infer_unit(nutrient) or "")
        unit_part = unit.strip().lower()
        name_part = name.strip().lower()
        if name_part:
            header_key = f"{name_part}|{unit_part}"
        else:
            base_key = self.nutrient_key(nutrient)
            if not base_key:
                return "", name, unit
            header_key = f"{base_key}|{unit_part}"
        return header_key, name, unit

    def normalize_totals_by_header_key(
        self,
        totals: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Re-key totals using header_key (name|unit) for export flags."""
        normalized: Dict[str, Dict[str, Any]] = {}
        best_priority: Dict[str, int] = {}
        alias_priority = {
            "carbohydrate, by difference": 2,
            "carbohydrate, by summation": 1,
            "carbohydrate by summation": 1,
            "sugars, total": 2,
            "total sugars": 1,
        }

        for entry in totals.values():
            name = entry.get("name", "")
            unit = entry.get("unit", "")
            nut = {"name": name, "unitName": unit}
            header_key, canonical_name, canonical_unit = self.header_key(nut)
            if not header_key:
                continue
            priority = alias_priority.get(str(name).strip().lower(), 0)
            current_best = best_priority.get(header_key, -1)
            if priority < current_best:
                continue
            best_priority[header_key] = priority
            normalized[header_key] = {
                "name": canonical_name or name,
                "unit": canonical_unit or unit,
                "amount": float(entry.get("amount", 0.0) or 0.0),
            }

        return normalized

    def infer_unit(self, nutrient: Dict[str, Any]) -> str:
        unit = nutrient.get("unitName")
        if unit:
            return unit

        number = str(nutrient.get("number") or "").strip()
        name = (nutrient.get("name") or "").lower()

        default_units_by_number = {
            "255": "g",  # Water
            "203": "g",  # Protein
            "204": "g",  # Total lipid (fat)
            "298": "g",  # Total fat (NLEA)
            "202": "g",  # Nitrogen
            "207": "g",  # Ash
            "205": "g",  # Carbohydrate, by difference
            "291": "g",  # Fiber, total dietary
            "269": "g",  # Sugars, total
            "268": "kJ",  # Energy (kJ)
            "208": "kcal",  # Energy (kcal)
            "951": "g",  # Proximates
            "956": "g",  # Carbohydrates
        }
        if number in default_units_by_number:
            return default_units_by_number[number]

        if "energy" in name and "kcal" in name:
            return "kcal"
        if "energy" in name and "kj" in name:
            return "kJ"

        macro_hints = [
            "water",
            "protein",
            "lipid",
            "fat",
            "ash",
            "carbohydrate",
            "fiber",
            "sugar",
            "starch",
            "nitrogen",
            "fatty acids",
            "sfa",
            "mufa",
            "pufa",
        ]
        if any(hint in name for hint in macro_hints) or ":" in name:
            return "g"

        amino_acids = [
            "alanine",
            "arginine",
            "aspartic acid",
            "cystine",
            "cysteine",
            "hydroxyproline",
            "glutamic acid",
            "glycine",
            "histidine",
            "isoleucine",
            "leucine",
            "lysine",
            "methionine",
            "phenylalanine",
            "proline",
            "serine",
            "threonine",
            "tryptophan",
            "tyrosine",
            "valine",
        ]
        if name in amino_acids:
            return "g"

        simple_sugars = [
            "sucrose",
            "glucose",
            "fructose",
            "lactose",
            "maltose",
            "galactose",
        ]
        if name in simple_sugars:
            return "g"

        if name == "alcohol, ethyl":
            return "g"

        return ""

    def unit_for_name(self, name: str) -> str:
        """Return USDA-style unit for a nutrient name."""
        lower = (name or "").strip().lower()
        if not lower:
            return ""
        mapped = self._unit_map.get(lower)
        if mapped:
            return "µg" if mapped == "æg" else mapped
        inferred = self.infer_unit({"name": name})
        normalized = canonical_unit(inferred) or inferred
        return "µg" if normalized == "æg" else normalized

    def nutrient_order(self, nutrient: Dict[str, Any], fallback: int) -> float:
        rank = nutrient.get("rank")
        if rank is None:
            ref = self.reference_info(nutrient)
            rank = ref.get("rank")
        if rank is None:
            name_lower = (nutrient.get("name") or "").strip().lower()
            rank = self._order_map.get(name_lower)
        try:
            return float(rank)
        except (TypeError, ValueError):
            return float(fallback)

    def category_for_nutrient(self, name: str, nutrient: Dict[str, Any] | None = None) -> str:
        lower = (name or "").strip().lower()
        if lower in self._category_map:
            return self._category_map[lower]

        amino_acids = {
            "tryptophan",
            "threonine",
            "isoleucine",
            "leucine",
            "lysine",
            "methionine",
            "phenylalanine",
            "tyrosine",
            "valine",
            "arginine",
            "histidine",
            "alanine",
            "aspartic acid",
            "glutamic acid",
            "glycine",
            "proline",
            "serine",
            "hydroxyproline",
            "cysteine",
            "cystine",
        }
        organic_acids = {
            "citric acid",
            "malic acid",
            "oxalic acid",
            "quinic acid",
        }
        oligosaccharides = {"raffinose", "stachyose", "verbascose"}
        isoflavones = {"daidzein", "genistein", "daidzin", "genistin", "glycitin"}

        vitamin_like = (
            lower.startswith("vitamin ")
            or "tocopherol" in lower
            or "tocotrienol" in lower
            or "carotene" in lower
            or "lycopene" in lower
            or "lutein" in lower
            or "zeaxanthin" in lower
            or "retinol" in lower
            or "folate" in lower
            or "folic acid" in lower
            or "betaine" in lower
            or "choline" in lower
            or "caffeine" in lower
            or "theobromine" in lower
        )
        if vitamin_like:
            return "Vitamins and Other Components"

        if lower in amino_acids:
            return "Amino acids"
        if (
            "fatty acids" in lower
            or lower.startswith(("sfa ", "mufa ", "pufa "))
            or lower in {"cholesterol", "total lipid (fat)", "total fat (nlea)"}
        ):
            return "Lipids"
        if "sterol" in lower:
            return "Phytosterols"
        if lower in organic_acids or (lower.endswith("acid") and lower not in amino_acids):
            return "Organic acids"
        if lower in oligosaccharides:
            return "Oligosaccharides"
        if lower in isoflavones:
            return "Isoflavones"

        if nutrient:
            ref = self.reference_info(nutrient)
            if ref.get("category"):
                return ref["category"]
        return "Nutrientes"


def build_nutrient_catalog() -> List[Tuple[str, List[str]]]:
    return [
        (
            "Proximates",
            [
                "Water",
                "Energy",
                "Nitrogen",
                "Protein",
                "Total fat (NLEA)",
                "Total lipid (fat)",
                "Ash",
                "Carbohydrate, by difference",
            ],
        ),
        (
            "Carbohydrates",
            [
                "Fiber, total dietary",
                "Fiber, soluble",
                "Fiber, insoluble",
                "Total dietary fiber (AOAC 2011.25)",
                "High Molecular Weight Dietary Fiber (HMWDF)",
                "Low Molecular Weight Dietary Fiber (LMWDF)",
                "Sugars, Total",
                "Sucrose",
                "Glucose",
                "Fructose",
                "Lactose",
                "Maltose",
                "Galactose",
                "Starch",
                "Resistant starch",
                "Sugars, added",
            ],
        ),
        (
            "Minerals",
            [
                "Calcium, Ca",
                "Iron, Fe",
                "Magnesium, Mg",
                "Phosphorus, P",
                "Potassium, K",
                "Sodium, Na",
                "Zinc, Zn",
                "Copper, Cu",
                "Manganese, Mn",
                "Iodine, I",
                "Selenium, Se",
                "Molybdenum, Mo",
                "Fluoride, F",
            ],
        ),
        (
            "Vitamins and Other Components",
            [
                "Thiamin",
                "Riboflavin",
                "Niacin",
                "Vitamin B-6",
                "Folate, total",
                "Folic acid",
                "Folate, DFE",
                "Choline, total",
                "Choline, free",
                "Choline, from phosphocholine",
                "Choline, from phosphatidyl choline",
                "Choline, from glycerophosphocholine",
                "Choline, from sphingomyelin",
                "Betaine",
                "Vitamin B-12",
                "Vitamin B-12, added",
                "Vitamin A, RAE",
                "Retinol",
                "Carotene, beta",
                "cis-beta-Carotene",
                "trans-beta-Carotene",
                "Carotene, alpha",
                "Carotene, gamma",
                "Cryptoxanthin, beta",
                "Cryptoxanthin, alpha",
                "Vitamin A, IU",
                "Lycopene",
                "cis-Lycopene",
                "trans-Lycopene",
                "Lutein + zeaxanthin",
                "cis-Lutein/Zeaxanthin",
                "Lutein",
                "Zeaxanthin",
                "Phytoene",
                "Phytofluene",
                "Vitamin D (D2 + D3), International Units",
                "Vitamin D (D2 + D3)",
                "Vitamin D2 (ergocalciferol)",
                "Vitamin D3 (cholecalciferol)",
                "25-hydroxycholecalciferol",
                "Vitamin K (phylloquinone)",
                "Vitamin K (Dihydrophylloquinone)",
                "Vitamin K (Menaquinone-4)",
                "Vitamin E (alpha-tocopherol)",
                "Vitamin E, added",
                "Tocopherol, beta",
                "Tocopherol, gamma",
                "Tocopherol, delta",
                "Tocotrienol, alpha",
                "Tocotrienol, beta",
                "Tocotrienol, gamma",
                "Tocotrienol, delta",
                "Vitamin C, total ascorbic acid",
                "Pantothenic acid",
                "Biotin",
                "Caffeine",
                "Theobromine",
            ],
        ),
        (
            "Lipids",
            [
                "Fatty acids, total saturated",
                "SFA 4:0",
                "SFA 5:0",
                "SFA 6:0",
                "SFA 7:0",
                "SFA 8:0",
                "SFA 9:0",
                "SFA 10:0",
                "SFA 11:0",
                "SFA 12:0",
                "SFA 13:0",
                "SFA 14:0",
                "SFA 15:0",
                "SFA 16:0",
                "SFA 17:0",
                "SFA 18:0",
                "SFA 20:0",
                "SFA 21:0",
                "SFA 22:0",
                "SFA 23:0",
                "SFA 24:0",
                "Fatty acids, total monounsaturated",
                "MUFA 12:1",
                "MUFA 14:1",
                "MUFA 14:1 c",
                "MUFA 15:1",
                "MUFA 16:1",
                "MUFA 16:1 c",
                "MUFA 17:1",
                "MUFA 17:1 c",
                "MUFA 18:1",
                "MUFA 18:1 c",
                "MUFA 20:1",
                "MUFA 20:1 c",
                "MUFA 22:1",
                "MUFA 22:1 c",
                "MUFA 22:1 n-9",
                "MUFA 22:1 n-11",
                "MUFA 24:1 c",
                "Fatty acids, total polyunsaturated",
                "PUFA 18:2",
                "PUFA 18:2 c",
                "PUFA 18:2 n-6 c,c",
                "PUFA 18:2 CLAs",
                "PUFA 18:2 i",
                "PUFA 18:3",
                "PUFA 18:3 c",
                "PUFA 18:3 n-3 c,c,c (ALA)",
                "PUFA 18:3 n-6 c,c,c",
                "PUFA 18:4",
                "PUFA 20:2 c",
                "PUFA 20:2 n-6 c,c",
                "PUFA 20:3",
                "PUFA 20:3 c",
                "PUFA 20:3 n-3",
                "PUFA 20:3 n-6",
                "PUFA 20:3 n-9",
                "PUFA 20:4",
                "PUFA 20:4c",
                "PUFA 20:5c",
                "PUFA 20:5 n-3 (EPA)",
                "PUFA 22:2",
                "PUFA 22:3",
                "PUFA 22:4",
                "PUFA 22:5 c",
                "PUFA 22:5 n-3 (DPA)",
                "PUFA 22:6 c",
                "PUFA 22:6 n-3 (DHA)",
                "Fatty acids, total trans",
                "Fatty acids, total trans-monoenoic",
                "Fatty acids, total trans-dienoic",
                "Fatty acids, total trans-polyenoic",
                "TFA 14:1 t",
                "TFA 16:1 t",
                "TFA 18:1 t",
                "TFA 18:2 t",
                "TFA 18:2 t,t",
                "TFA 18:2 t not further defined",
                "TFA 18:3 t",
                "TFA 20:1 t",
                "TFA 22:1 t",
                "Cholesterol",
            ],
        ),
        (
            "Amino acids",
            [
                "Tryptophan",
                "Threonine",
                "Isoleucine",
                "Leucine",
                "Lysine",
                "Methionine",
                "Phenylalanine",
                "Tyrosine",
                "Valine",
                "Arginine",
                "Histidine",
                "Alanine",
                "Aspartic acid",
                "Glutamic acid",
                "Glycine",
                "Proline",
                "Serine",
                "Hydroxyproline",
                "Cysteine",
            ],
        ),
        (
            "Phytosterols",
            [
                "Phytosterols",
                "Beta-sitosterol",
                "Brassicasterol",
                "Campesterol",
                "Campestanol",
                "Delta-5-avenasterol",
                "Phytosterols, other",
                "Stigmasterol",
                "Beta-sitostanol",
            ],
        ),
        ("Organic acids", ["Citric acid", "Malic acid", "Oxalic acid", "Quinic acid"]),
        ("Oligosaccharides", ["Verbascose", "Raffinose", "Stachyose"]),
        ("Isoflavones", ["Daidzin", "Genistin", "Glycitin", "Daidzein", "Genistein"]),
    ]


def build_nutrient_unit_map() -> Dict[str, str]:
    """Return USDA-like units for known nutrients."""
    unit_map: Dict[str, str] = {}

    def _set(names: List[str], unit: str) -> None:
        for name in names:
            unit_map[name.strip().lower()] = unit

    _set(
        [
            "Calcium, Ca",
            "Iron, Fe",
            "Magnesium, Mg",
            "Phosphorus, P",
            "Potassium, K",
            "Sodium, Na",
            "Zinc, Zn",
            "Copper, Cu",
            "Manganese, Mn",
        ],
        "mg",
    )
    _set(
        [
            "Iodine, I",
            "Selenium, Se",
            "Molybdenum, Mo",
            "Fluoride, F",
        ],
        "µg",
    )
    _set(
        [
            "Thiamin",
            "Riboflavin",
            "Niacin",
            "Vitamin B-6",
            "Choline, total",
            "Choline, free",
            "Choline, from phosphocholine",
            "Choline, from phosphatidyl choline",
            "Choline, from glycerophosphocholine",
            "Choline, from sphingomyelin",
            "Betaine",
            "Vitamin E (alpha-tocopherol)",
            "Vitamin E, added",
            "Tocopherol, beta",
            "Tocopherol, gamma",
            "Tocopherol, delta",
            "Tocotrienol, alpha",
            "Tocotrienol, beta",
            "Tocotrienol, gamma",
            "Tocotrienol, delta",
            "Vitamin C, total ascorbic acid",
            "Pantothenic acid",
            "Caffeine",
            "Theobromine",
        ],
        "mg",
    )
    _set(
        [
            "Folate, total",
            "Folic acid",
            "Folate, DFE",
            "Vitamin B-12",
            "Vitamin B-12, added",
            "Vitamin A, RAE",
            "Retinol",
            "Carotene, beta",
            "cis-beta-Carotene",
            "trans-beta-Carotene",
            "Carotene, alpha",
            "Carotene, gamma",
            "Cryptoxanthin, beta",
            "Cryptoxanthin, alpha",
            "Lycopene",
            "cis-Lycopene",
            "trans-Lycopene",
            "Lutein + zeaxanthin",
            "cis-Lutein/Zeaxanthin",
            "Lutein",
            "Zeaxanthin",
            "Phytoene",
            "Phytofluene",
            "Vitamin D (D2 + D3)",
            "Vitamin D2 (ergocalciferol)",
            "Vitamin D3 (cholecalciferol)",
            "25-hydroxycholecalciferol",
            "Vitamin K (phylloquinone)",
            "Vitamin K (Dihydrophylloquinone)",
            "Vitamin K (Menaquinone-4)",
            "Biotin",
        ],
        "µg",
    )
    _set(
        [
            "Vitamin A, IU",
            "Vitamin D (D2 + D3), International Units",
        ],
        "iu",
    )
    _set(
        [
            "Cholesterol",
            "Phytosterols",
            "Beta-sitosterol",
            "Brassicasterol",
            "Campesterol",
            "Campestanol",
            "Delta-5-avenasterol",
            "Phytosterols, other",
            "Stigmasterol",
            "Beta-sitostanol",
        ],
        "mg",
    )
    _set(
        ["Citric acid", "Malic acid", "Oxalic acid", "Quinic acid"],
        "mg",
    )
    _set(
        ["Daidzin", "Genistin", "Glycitin", "Daidzein", "Genistein"],
        "mg",
    )
    _set(["Verbascose", "Raffinose", "Stachyose"], "g")
    _set(["Energy"], "kcal")

    return unit_map
