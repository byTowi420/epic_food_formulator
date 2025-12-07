import os
import threading
from typing import Any, Dict, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from dotenv import load_dotenv

load_dotenv()

USDA_API_KEY = os.getenv("USDA_API_KEY")
BASE_URL = "https://api.nal.usda.gov/fdc/v1"
DEFAULT_TIMEOUT = (3.05, 20)  # (connect timeout, read timeout)

_session_lock = threading.Lock()
_session: requests.Session | None = None
_details_cache: Dict[tuple[int, str, tuple[int, ...] | None], Dict[str, Any]] = {}
_search_cache: Dict[tuple[str, int, tuple[str, ...] | None, int], List[Dict[str, Any]]] = {}
_cache_lock = threading.Lock()


class USDAApiError(Exception):
    """Generic error for USDA API issues."""


def _ensure_api_key() -> None:
    if not USDA_API_KEY:
        raise USDAApiError(
            "USDA_API_KEY not found. Add it to a .env file (see .env.example)."
        )


def _get_session() -> requests.Session:
    """Return a shared HTTP session with connection pooling and retries."""
    global _session
    if _session:
        return _session

    with _session_lock:
        if _session:
            return _session

        session = requests.Session()
        retries = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retries,
            pool_connections=8,
            pool_maxsize=8,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _session = session
        return _session


def _request_json(
    path: str,
    params: Dict[str, Any] | None = None,
    timeout: tuple[float, float] | float | None = None,
    method: str = "GET",
    json_body: Any | None = None,
) -> Dict[str, Any]:
    """Make an HTTP request and return parsed JSON with uniform error handling."""
    _ensure_api_key()
    params_with_key = {"api_key": USDA_API_KEY}
    params_with_key.update(params or {})
    url = f"{BASE_URL}/{path.lstrip('/')}"

    try:
        response = _get_session().request(
            method=method,
            url=url,
            params=params_with_key,
            json=json_body,
            timeout=timeout or DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise USDAApiError(f"Network error when calling USDA API: {exc}") from exc

    return response.json()


def _normalize_food_payload(food: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize USDA payload so foodNutrients entries always expose nutrient/amount keys.
    This keeps the rest of the app agnostic to abridged/full response shapes.
    """
    nutrients = food.get("foodNutrients")
    if not nutrients:
        return food

    normalized: list[Dict[str, Any]] = []
    for entry in nutrients:
        raw_entry = dict(entry)
        amount = raw_entry.get("amount", raw_entry.get("value"))
        try:
            amount = float(amount) if amount is not None else None
        except (TypeError, ValueError):
            pass

        nutrient = dict(raw_entry.get("nutrient") or {})
        nutrient.setdefault("id", raw_entry.pop("nutrientId", None))
        nutrient.setdefault(
            "number",
            raw_entry.pop("nutrientNumber", None)
            or raw_entry.get("number"),
        )
        nutrient.setdefault(
            "name",
            raw_entry.pop("nutrientName", None)
            or raw_entry.get("name"),
        )
        if "rank" not in nutrient and "rank" in raw_entry:
            nutrient["rank"] = raw_entry.get("rank")
        if "unitName" not in nutrient and "unitName" in raw_entry:
            nutrient["unitName"] = raw_entry.get("unitName")
        # Normalize unit casing to lower for consistency (e.g., MG -> mg).
        if "unitName" in nutrient and isinstance(nutrient["unitName"], str):
            nutrient["unitName"] = nutrient["unitName"].lower()

        normalized_entry: Dict[str, Any] = {
            "nutrient": {k: v for k, v in nutrient.items() if v is not None},
            "amount": amount,
            # Keep the type marker to detect category rows (Proximates, Minerals, etc.)
            "type": raw_entry.get("type"),
        }

        normalized.append(normalized_entry)

    normalized_food = dict(food)
    normalized_food["foodNutrients"] = normalized
    return normalized_food


def search_foods(
    query: str,
    page_size: int = 25,
    data_types: List[str] | None = None,
    page_number: int = 1,
) -> List[Dict[str, Any]]:
    """
    Search foods in FoodData Central by name.

    :param query: text to search (e.g., 'apple', 'cheddar', 'rice')
    :param page_size: number of results to return
    :param data_types: list of USDA dataType strings. If None, do not filter.
    :param page_number: page to fetch (1-based)
    :return: list of dicts with basic food info
    """
    if not query:
        return []

    normalized_types = None if data_types is None else tuple(data_types)
    cache_key = (query.lower().strip(), page_size, normalized_types, page_number)
    with _cache_lock:
        cached = _search_cache.get(cache_key)
    if cached is not None:
        return cached

    params: Dict[str, Any] = {
        "query": query,
        "pageSize": page_size,
        "pageNumber": page_number,
    }
    if normalized_types is not None:
        params["dataType"] = list(normalized_types)

    data = _request_json("foods/search", params)
    foods = data.get("foods", [])

    results: List[Dict[str, Any]] = []
    for food in foods:
        results.append(
            {
                "fdcId": food.get("fdcId"),
                "description": food.get("description"),
                "brandOwner": food.get("brandOwner", "") or "",
                "dataType": food.get("dataType", "") or "",
            }
        )

    with _cache_lock:
        _search_cache[cache_key] = results

    return results


def get_food_details(
    fdc_id: int,
    timeout: tuple[float, float] | float | None = None,
    detail_format: str = "full",
    nutrient_ids: List[int] | None = None,
) -> Dict[str, Any]:
    """
    Fetch full details for a food item, including all nutrients.

    :param fdc_id: FoodData Central ID
    :param timeout: Optional requests timeout override (connect, read) or float
    :param detail_format: 'abridged' to skip verbose fields or 'full' for everything
    :param nutrient_ids: Optional list of nutrient IDs to request only those values
    :return: raw JSON dict from the USDA API
    """
    fmt = (detail_format or "full").lower()
    if fmt not in {"abridged", "full"}:
        raise ValueError("detail_format must be 'abridged' or 'full'")
    nutrient_tuple = tuple(sorted(set(nutrient_ids))) if nutrient_ids else None
    cache_key = (fdc_id, fmt, nutrient_tuple)

    with _cache_lock:
        cached = _details_cache.get(cache_key)
    if cached is not None:
        normalized = _normalize_food_payload(cached)
        with _cache_lock:
            _details_cache[cache_key] = normalized
        return normalized

    if nutrient_tuple:
        payload = {"fdcIds": [fdc_id], "format": fmt, "nutrients": list(nutrient_tuple)}
        data_list = _request_json("foods", {}, timeout=timeout, method="POST", json_body=payload)
        if not isinstance(data_list, list) or not data_list:
            raise USDAApiError(f"No se recibieron datos para el FDC {fdc_id}.")
        data = data_list[0]
    else:
        params = {"format": fmt}
        data = _request_json(f"food/{fdc_id}", params, timeout=timeout)

    normalized = _normalize_food_payload(data)

    with _cache_lock:
        _details_cache[cache_key] = normalized

    return normalized
