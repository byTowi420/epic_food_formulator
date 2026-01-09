"""Search presenter - handles food search operations."""

from typing import Any, Dict, List, Optional

from config.constants import DATA_TYPE_PRIORITY
from config.container import Container
from domain.services.nutrient_ordering import NutrientOrdering
from domain.services.nutrient_normalizer import augment_fat_nutrients, normalize_nutrients


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

    def build_details_rows(
        self,
        nutrients: List[Dict[str, Any]],
        *,
        ordering: NutrientOrdering | None = None,
    ) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        ordering = ordering or self._nutrient_ordering
        nutrients = ordering.sort_nutrients_for_display(nutrients or [])
        for nutrient in nutrients:
            if nutrient.get("amount") is None:
                continue
            nut = nutrient.get("nutrient") or {}
            name = nut.get("name", "") or ""
            unit = nut.get("unitName", "") or ""
            amount = nutrient.get("amount")
            amount_text = "" if amount is None else str(amount)
            rows.append({"name": name, "amount": amount_text, "unit": unit})
        return rows

    def build_result_rows(
        self,
        foods: List[Dict[str, Any]],
        *,
        base_index: int = 0,
    ) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        for row_idx, food in enumerate(foods):
            rows.append(
                {
                    "fdc_id": str(food.get("fdcId", "")),
                    "description": food.get("description", "") or "",
                    "brand": food.get("brandOwner", "") or "",
                    "data_type": food.get("dataType", "") or "",
                    "row_number": str(base_index + row_idx + 1),
                }
            )
        return rows

    def build_search_status(self, total_count: int, page: int, page_size: int) -> str:
        total_pages = self.get_total_pages(page_size)
        return f"Se encontraron {total_count} resultados (pagina {page}/{total_pages})."

    def build_details_status(self, details: Dict[str, Any], nutrient_count: int) -> str:
        desc = details.get("description", "") or ""
        fdc_id = details.get("fdcId", "")
        return f"Detalles de {fdc_id} - {desc} ({nutrient_count} nutrientes)"

    def build_paging_state(
        self,
        *,
        has_query: bool,
        page: int,
        page_size: int,
        total_count: int,
    ) -> Dict[str, bool]:
        enable_prev = has_query and page > 1
        enable_next = has_query and (page * page_size < total_count)
        return {"enable_prev": enable_prev, "enable_next": enable_next}

    def collect_prefetch_ids(
        self,
        foods: List[Dict[str, Any]],
        *,
        limit: int = 2,
    ) -> List[Any]:
        ids: List[Any] = []
        for food in foods:
            fdc_id = food.get("fdcId")
            if fdc_id is None:
                continue
            ids.append(fdc_id)
            if len(ids) >= limit:
                break
        return ids

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
