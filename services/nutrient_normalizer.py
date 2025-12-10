from __future__ import annotations

import logging
from typing import Any, Dict, List


def canonical_alias_name(name: str) -> str:
    """Return a display name for known aliases to keep one column in Excel."""
    lower = (name or "").strip().lower()
    mapping = {
        "sugars, total": "Sugars, Total",
        "total sugars": "Sugars, Total",
        "carbohydrate, by difference": "Carbohydrate, by difference",
        "carbohydrate, by summation": "Carbohydrate, by difference",
        "carbohydrate by summation": "Carbohydrate, by difference",
        "energy (atwater general factors)": "",
        "energy (atwater specific factors)": "",
        "choline, from phosphotidyl choline": "Choline, from phosphatidyl choline",
    }
    return mapping.get(lower, name)


def canonical_unit(unit: str | None) -> str:
    """Normalize unit strings to avoid duplicate columns (ug vs µg, mcg)."""
    if not unit:
        return ""
    u = unit.strip()
    lower = u.lower()
    if lower in {"ug", "µg", "mcg"}:
        return "µg"
    if lower == "iu":
        return "iu"
    if lower == "kj":
        return "kJ"
    return lower


def augment_fat_nutrients(nutrients: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Ensure Total lipid (fat) and Total fat (NLEA) mirror each other if one is missing.
    Insert the cloned entry next to its counterpart to preserve order/category.
    Ensures there is at most one entry for each of the two names.
    Returns a new list without mutating the original to avoid duplication on refresh.
    """
    if not nutrients:
        return []
    logging.debug(f"_augment_fat_nutrients input={len(nutrients)}")

    target_a = "total lipid (fat)"
    target_b = "total fat (nlea)"
    mapping = {
        target_a: ("Total fat (NLEA)", "298"),
        target_b: ("Total lipid (fat)", "204"),
    }

    def _norm_name(entry: Dict[str, Any]) -> str:
        nut = entry.get("nutrient") or {}
        return (nut.get("name") or "").strip().lower()

    first_lipid_idx = None
    first_nlea_idx = None
    lipid_amount = None
    nlea_amount = None
    lipid_entry = None
    nlea_entry = None
    filtered: list[Dict[str, Any]] = []

    for entry in nutrients:
        name = _norm_name(entry)
        if name == target_a:
            if first_lipid_idx is None:
                first_lipid_idx = len(filtered)
                lipid_amount = entry.get("amount")
                lipid_entry = dict(entry)
                lip_nut = dict(lipid_entry.get("nutrient") or {})
                lip_nut.pop("id", None)
                lip_nut.pop("number", None)
                lipid_entry["nutrient"] = lip_nut
            continue
        if name == target_b:
            if first_nlea_idx is None:
                first_nlea_idx = len(filtered)
                nlea_amount = entry.get("amount")
                nlea_entry = dict(entry)
                nlea_nut = dict(nlea_entry.get("nutrient") or {})
                nlea_nut.pop("id", None)
                nlea_nut.pop("number", None)
                nlea_entry["nutrient"] = nlea_nut
            continue
        filtered.append(entry)

    def _clone_with_name(source: Dict[str, Any], new_name: str, number: str) -> Dict[str, Any]:
        nut = dict(source.get("nutrient") or {})
        nut["name"] = new_name
        nut.pop("id", None)
        nut.pop("number", None)
        clone = dict(source)
        clone["nutrient"] = nut
        return clone

    result = list(filtered)

    if lipid_amount is None and nlea_amount is None:
        return nutrients  # nothing to do

    if lipid_amount is None:
        source = nlea_entry or {"nutrient": {"name": "Total fat (NLEA)"}}
        lipid_clone = _clone_with_name(source, *mapping[target_b])
        lipid_clone["amount"] = nlea_amount
        insert_at = first_nlea_idx if first_nlea_idx is not None else len(result)
        result.insert(insert_at, lipid_clone)
        result.insert(insert_at + 1, nlea_entry)
        return result

    if nlea_amount is None:
        source = lipid_entry or {"nutrient": {"name": "Total lipid (fat)"}}
        nlea_clone = _clone_with_name(source, *mapping[target_a])
        nlea_clone["amount"] = lipid_amount
        insert_at = first_lipid_idx if first_lipid_idx is not None else len(result)
        result.insert(insert_at, lipid_entry)
        result.insert(insert_at + 1, nlea_clone)
        return result

    if first_lipid_idx is not None and first_nlea_idx is not None:
        insert_first = min(first_lipid_idx, first_nlea_idx)
        insert_second = max(first_lipid_idx, first_nlea_idx)
        first_entry = lipid_entry if first_lipid_idx < first_nlea_idx else nlea_entry
        second_entry = nlea_entry if first_entry is lipid_entry else lipid_entry
        result.insert(insert_first, first_entry)
        result.insert(insert_second, second_entry)
        return result

    return result


def _augment_energy_nutrients(nutrients: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Ensure Energy (kcal/kJ) is always computed from macros (4/9/4) and deduplicate extras.
    kcal = protein*4 + carbs*4 + fat*9 ; kJ = kcal*4.184
    """
    if not nutrients:
        return []

    def _norm_name(entry: Dict[str, Any]) -> str:
        nut = entry.get("nutrient") or {}
        return (nut.get("name") or "").strip().lower()

    def _clone_energy(unit: str, amount: float) -> Dict[str, Any]:
        nut = {"name": "Energy", "unitName": unit}
        return {"nutrient": nut, "amount": amount}

    result: list[Dict[str, Any]] = []
    kcal_entry = None
    kj_entry = None

    for entry in nutrients:
        name = _norm_name(entry)
        if name != "energy":
            result.append(entry)
            continue
        unit = (entry.get("nutrient") or {}).get("unitName", "").lower()
        if unit == "kcal" and kcal_entry is None:
            kcal_entry = dict(entry)
            kcal_entry.get("nutrient", {}).pop("id", None)
            kcal_entry.get("nutrient", {}).pop("number", None)
            result.append(kcal_entry)
        elif unit == "kj" and kj_entry is None:
            kj_entry = dict(entry)
            kj_entry.get("nutrient", {}).pop("id", None)
            kj_entry.get("nutrient", {}).pop("number", None)
            result.append(kj_entry)
        # drop duplicates silently

    def _find_amount(names: list[str]) -> float | None:
        for entry in result:
            if _norm_name(entry) in names:
                amt = entry.get("amount")
                if amt is not None:
                    try:
                        return float(amt)
                    except (TypeError, ValueError):
                        return None
        return None

    protein = _find_amount(["protein"]) or 0.0
    carbs = _find_amount(["carbohydrate, by difference"]) or 0.0
    fat = _find_amount(["total lipid (fat)", "total fat (nlea)"]) or 0.0

    kcal_amount = (protein * 4.0) + (carbs * 4.0) + (fat * 9.0)

    insert_pos = 0
    macro_indices = []
    for idx, entry in enumerate(result):
        if _norm_name(entry) in [
            "protein",
            "carbohydrate, by difference",
            "total lipid (fat)",
            "total fat (nlea)",
        ]:
            macro_indices.append(idx)
    if macro_indices:
        insert_pos = min(macro_indices)

    if kcal_entry is None:
        kcal_entry = _clone_energy("kcal", kcal_amount)
        result.insert(insert_pos, kcal_entry)
    else:
        kcal_entry["amount"] = kcal_amount
        kcal_entry.setdefault("nutrient", {})["unitName"] = "kcal"

    if kj_entry is None:
        kj_entry = _clone_energy("kJ", kcal_amount * 4.184)
        insert_kj = insert_pos + 1 if kcal_entry in result else insert_pos
        result.insert(insert_kj, kj_entry)
    else:
        kj_entry["amount"] = kcal_amount * 4.184
        kj_entry.setdefault("nutrient", {})["unitName"] = "kJ"

    return result


def _augment_branded_water(
    nutrients: list[Dict[str, Any]], data_type: str | None = None
) -> list[Dict[str, Any]]:
    """
    For Branded foods missing Water, estimate it as:
    water = 100 - (fat + protein + carbs + ash + fiber)
    If result < 0, clamp to 0.
    """
    if not nutrients:
        return []
    if (data_type or "").strip().lower() != "branded":
        return nutrients

    def _norm(entry: Dict[str, Any]) -> str:
        nut = entry.get("nutrient") or {}
        return (nut.get("name") or "").strip().lower()

    has_water = any(_norm(e) == "water" and e.get("amount") is not None for e in nutrients)
    if has_water:
        return nutrients

    def _find(names: list[str]) -> float:
        for entry in nutrients:
            if _norm(entry) in names:
                amt = entry.get("amount")
                if amt is not None:
                    try:
                        return float(amt)
                    except (TypeError, ValueError):
                        pass
        return 0.0

    fat = _find(["total lipid (fat)", "total fat (nlea)"])
    protein = _find(["protein"])
    carbs = _find(["carbohydrate, by difference"])
    ash = _find(["ash"])
    fiber = _find(["fiber, total dietary"])

    water_amount = 100.0 - (fat + protein + carbs + ash + fiber)
    if water_amount < 0:
        water_amount = 0.0

    water_entry = {"nutrient": {"name": "Water", "unitName": "g"}, "amount": water_amount}

    insert_pos = 0
    macro_indices = []
    macro_names = {
        "protein",
        "carbohydrate, by difference",
        "total lipid (fat)",
        "total fat (nlea)",
        "ash",
        "fiber, total dietary",
    }
    for idx, entry in enumerate(nutrients):
        if _norm(entry) in macro_names:
            macro_indices.append(idx)
    if macro_indices:
        insert_pos = min(macro_indices)

    result = list(nutrients)
    result.insert(insert_pos, water_entry)
    return result


def _augment_nitrogen(nutrients: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Ensure Nitrogen exists; if missing and Protein is present, compute N = Protein/6.25.
    Insert near Protein to preserve ordering.
    """
    if not nutrients:
        return []

    def _norm(entry: Dict[str, Any]) -> str:
        nut = entry.get("nutrient") or {}
        return (nut.get("name") or "").strip().lower()

    has_nitrogen = None
    protein_amount = None
    protein_idx = None
    for idx, entry in enumerate(nutrients):
        name = _norm(entry)
        if name == "nitrogen" and entry.get("amount") is not None:
            has_nitrogen = idx
            break
        if name == "protein" and protein_amount is None and entry.get("amount") is not None:
            protein_amount = float(entry.get("amount") or 0.0)
            protein_idx = idx

    if has_nitrogen is not None or protein_amount is None:
        return nutrients

    nitrogen_amount = protein_amount / 6.25
    nitrogen_entry = {"nutrient": {"name": "Nitrogen", "unitName": "g"}, "amount": nitrogen_amount}

    insert_pos = protein_idx if protein_idx is not None else 0
    result = list(nutrients)
    result.insert(insert_pos, nitrogen_entry)
    return result


def _augment_alias_nutrients(nutrients: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Normalize aliases choosing one canonical entry (no duplicates):
    - sugars, total / total sugars -> Sugars, Total
    - cystine / cysteine -> Cysteine
    - carbohydrate by summation -> carbohydrate by difference
    - drop Atwater energy rows
    - fix minor name typos (phosphotidyl -> phosphatidyl)
    """
    if not nutrients:
        return []

    canonical_map = {
        "total sugars": "Sugars, Total",
        "sugars, total": "Sugars, Total",
        "cystine": "Cysteine",
        "cysteine": "Cysteine",
        "carbohydrate, by summation": "Carbohydrate, by difference",
        "choline, from phosphotidyl choline": "Choline, from phosphatidyl choline",
    }
    drop_names = {
        "energy (atwater general factors)",
        "energy (atwater specific factors)",
    }
    merged: Dict[str, Dict[str, Any]] = {}

    def _key(name: str) -> str:
        lower = (name or "").strip().lower()
        if lower in drop_names:
            return ""
        mapped = canonical_map.get(lower)
        return (mapped or name).strip()

    for entry in nutrients:
        nut = entry.get("nutrient") or {}
        name = (nut.get("name") or "").strip()
        canonical = _key(name)
        if not canonical:
            continue
        existing = merged.get(canonical)
        if existing is None:
            new_entry = dict(entry)
            new_nut = dict(nut)
            new_nut["name"] = canonical
            new_entry["nutrient"] = new_nut
            merged[canonical] = new_entry
        else:
            amt = entry.get("amount")
            if amt is not None and existing.get("amount") is None:
                existing["amount"] = amt
    return list(merged.values())


def normalize_nutrients(
    nutrients: list[Dict[str, Any]], data_type: str | None = None
) -> list[Dict[str, Any]]:
    """Apply all nutrient augmentation steps (fat + alias + nitrogen + branded water + energy) in order."""
    normalized = augment_fat_nutrients(nutrients or [])
    for entry in normalized:
        nut = entry.get("nutrient") or {}
        unit = nut.get("unitName")
        canonical = canonical_unit(unit)
        if canonical:
            nut["unitName"] = canonical
            entry["nutrient"] = nut
    normalized = _augment_alias_nutrients(normalized)
    normalized = _augment_nitrogen(normalized)
    normalized = _augment_branded_water(normalized, data_type=data_type)
    return _augment_energy_nutrients(normalized)
