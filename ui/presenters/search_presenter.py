"""Search presenter - handles food search operations."""

from typing import Any, Dict, List, Optional

from config.constants import DATA_TYPE_PRIORITY
from config.container import Container
from domain.services.nutrient_ordering import NutrientOrdering
from services.nutrient_normalizer import augment_fat_nutrients, normalize_nutrients


class SearchPresenter:
    """Presenter for food search operations.

    Handles search queries and result formatting for UI.
    """

    def __init__(self, container: Optional[Container] = None) -> None:
        """Initialize presenter.

        Args:
            container: DI container (creates new one if not provided)
        """
        self._container = container if container is not None else Container()
        self._nutrient_ordering = NutrientOrdering()
        self._last_query = ""
        self._last_results: List[Dict[str, Any]] = []
        self._last_include_branded = False

    def search(
        self,
        query: str,
        page_size: int = 25,
        include_branded: bool = False,
        page_number: int = 1,
    ) -> List[Dict[str, Any]]:
        """Search for foods.

        Args:
            query: Search query
            page_size: Number of results
            include_branded: Whether to include branded foods
            page_number: Page number

        Returns:
            List of search result dicts
        """
        self._last_query = query
        self._last_results = self._container.search_foods.execute(
            query=query,
            page_size=page_size,
            include_branded=include_branded,
            page_number=page_number,
        )
        self._last_include_branded = include_branded
        return self._last_results

    def search_all(
        self,
        query: str,
        include_branded: bool,
        fetch_page_size: int = 200,
        max_pages: int = 5,
    ) -> List[Dict[str, Any]]:
        """Fetch multiple pages, sort and filter results, and cache them."""
        all_results: List[Dict[str, Any]] = []
        page = 1
        while page <= max_pages:
            batch = self._container.search_foods.execute(
                query=query,
                page_size=fetch_page_size,
                include_branded=include_branded,
                page_number=page,
            )
            if not batch:
                break
            all_results.extend(batch)
            if len(batch) < fetch_page_size:
                break
            page += 1

        stripped = query.strip()
        if not all_results and stripped.isdigit():
            try:
                details = self._container.food_repository.get_by_id(
                    int(stripped),
                    detail_format="abridged",
                )
            except Exception:
                all_results = []
            else:
                all_results = [
                    {
                        "fdcId": details.get("fdcId"),
                        "description": details.get("description", ""),
                        "brandOwner": details.get("brandOwner", "") or "",
                        "dataType": details.get("dataType", "") or "",
                    }
                ]

        sorted_results = self._sort_results(all_results)
        filtered = self._filter_results_by_query(sorted_results, query)

        self._last_query = query
        self._last_include_branded = include_branded
        self._last_results = filtered
        return filtered

    def get_page(self, page: int, page_size: int) -> List[Dict[str, Any]]:
        """Return cached results slice for a page."""
        if page < 1 or page_size <= 0:
            return []
        start = (page - 1) * page_size
        end = start + page_size
        return self._last_results[start:end]

    def get_total_pages(self, page_size: int) -> int:
        if page_size <= 0:
            return 1
        return max(1, (len(self._last_results) + page_size - 1) // page_size)

    def get_total_count(self) -> int:
        return len(self._last_results)

    def get_food_details(
        self,
        fdc_id: int,
        *,
        detail_format: str = "abridged",
    ) -> Dict[str, Any]:
        """Fetch food details and return normalized nutrients for display."""
        details = self._container.food_repository.get_by_id(
            fdc_id,
            detail_format=detail_format,
        )
        nutrients = normalize_nutrients(
            details.get("foodNutrients", []) or [], details.get("dataType")
        )
        nutrients = augment_fat_nutrients(nutrients)
        self._nutrient_ordering.update_reference_from_details(details)
        nutrients = self._nutrient_ordering.sort_nutrients_for_display(nutrients)
        return {"details": details, "nutrients": nutrients}

    def prefetch_food_details(
        self,
        fdc_id: int,
        *,
        timeout: tuple[float, float] = (3.05, 6.0),
        detail_format: str = "abridged",
    ) -> None:
        """Warm USDA cache for a food id."""
        self._container.food_repository.get_by_id(
            fdc_id,
            timeout=timeout,
            detail_format=detail_format,
        )

    def get_last_results(self) -> List[Dict[str, Any]]:
        """Get last search results.

        Returns:
            List of search result dicts
        """
        return self._last_results

    def get_last_query(self) -> str:
        """Get last search query.

        Returns:
            Last query string
        """
        return self._last_query

    def get_result_count(self) -> int:
        """Get count of last search results.

        Returns:
            Number of results
        """
        return len(self._last_results)

    def _sort_results(self, foods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def priority(data_type: str) -> int:
            return DATA_TYPE_PRIORITY.get(
                data_type, DATA_TYPE_PRIORITY.get(data_type.strip(), len(DATA_TYPE_PRIORITY))
            )

        return sorted(
            foods,
            key=lambda f: (
                priority(f.get("dataType", "") or ""),
                (f.get("description", "") or "").lower(),
            ),
        )

    def _filter_results_by_query(
        self,
        foods: List[Dict[str, Any]],
        query: str,
    ) -> List[Dict[str, Any]]:
        tokens = [t for t in query.lower().split() if t]
        if not tokens:
            return foods

        filtered: List[Dict[str, Any]] = []
        for food in foods:
            haystack = (
                f"{food.get('description', '')} "
                f"{food.get('brandOwner', '')} "
                f"{food.get('fdcId', '')}"
            ).lower()
            if all(tok in haystack for tok in tokens):
                filtered.append(food)
        return filtered
