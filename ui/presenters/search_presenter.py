"""Search presenter - handles food search operations."""

from typing import Any, Dict, List, Optional

from config.container import Container


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
        self._last_query = ""
        self._last_results: List[Dict[str, Any]] = []

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
        return self._last_results

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
