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
DEFAULT_TIMEOUT = (3.05, 10)  # (connect timeout, read timeout)

_session_lock = threading.Lock()
_session: requests.Session | None = None
_details_cache: Dict[int, Dict[str, Any]] = {}
_search_cache: Dict[tuple[str, int, tuple[str, ...]], List[Dict[str, Any]]] = {}
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
            total=2,
            connect=2,
            read=2,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
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


def _request_json(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make a GET request and return parsed JSON with uniform error handling."""
    _ensure_api_key()
    params_with_key = {"api_key": USDA_API_KEY}
    params_with_key.update(params)
    url = f"{BASE_URL}/{path.lstrip('/')}"

    try:
        response = _get_session().get(
            url,
            params=params_with_key,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise USDAApiError(f"Network error when calling USDA API: {exc}") from exc

    return response.json()


def search_foods(
    query: str,
    page_size: int = 25,
    data_types: List[str] | None = None,
) -> List[Dict[str, Any]]:
    """
    Search foods in FoodData Central by name.

    :param query: text to search (e.g., 'apple', 'cheddar', 'rice')
    :param page_size: number of results to return
    :return: list of dicts with basic food info
    """
    if not query:
        return []

    normalized_types = tuple(data_types or ("Foundation", "SR Legacy"))
    cache_key = (query.lower().strip(), page_size, normalized_types)
    with _cache_lock:
        cached = _search_cache.get(cache_key)
    if cached is not None:
        return cached

    params: Dict[str, Any] = {
        "query": query,
        "pageSize": page_size,
        "dataType": list(normalized_types),
    }

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


def get_food_details(fdc_id: int) -> Dict[str, Any]:
    """
    Fetch full details for a food item, including all nutrients.

    :param fdc_id: FoodData Central ID
    :return: raw JSON dict from the USDA API
    """
    with _cache_lock:
        cached = _details_cache.get(fdc_id)
    if cached is not None:
        return cached

    data = _request_json(f"food/{fdc_id}", {})

    with _cache_lock:
        _details_cache[fdc_id] = data

    return data
