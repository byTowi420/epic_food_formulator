import os
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

load_dotenv()

USDA_API_KEY = os.getenv("USDA_API_KEY")
BASE_URL = "https://api.nal.usda.gov/fdc/v1"


class USDAApiError(Exception):
    """Generic error for USDA API issues."""


def _ensure_api_key() -> None:
    if not USDA_API_KEY:
        raise USDAApiError(
            "USDA_API_KEY not found. Add it to a .env file (see .env.example)."
        )


def search_foods(query: str, page_size: int = 25) -> List[Dict[str, Any]]:
    """
    Search foods in FoodData Central by name.

    :param query: text to search (e.g., 'apple', 'cheddar', 'rice')
    :param page_size: number of results to return
    :return: list of dicts with basic food info
    """
    if not query:
        return []

    _ensure_api_key()

    url = f"{BASE_URL}/foods/search"
    params = {
        "api_key": USDA_API_KEY,
        "query": query,
        "pageSize": page_size,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise USDAApiError(f"Network error when calling USDA API: {exc}") from exc

    data = response.json()
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

    return results
