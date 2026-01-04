"""USDA FoodData Central repository.

Repository pattern implementation for USDA API access.
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from config.constants import (
    API_CONNECT_TIMEOUT,
    API_MAX_RETRY_ATTEMPTS,
    API_POOL_CONNECTIONS,
    API_POOL_MAXSIZE,
    API_READ_TIMEOUT_DEFAULT,
    API_RETRY_BACKOFF_FACTOR,
    API_RETRY_STATUS_CODES,
    USDA_API_BASE_URL,
)
from domain.exceptions import APIKeyMissingError, USDAHTTPError
from infrastructure.api.cache import Cache, InMemoryCache


class FoodRepository(ABC):
    """Abstract repository for food data."""

    @abstractmethod
    def search(
        self,
        query: str,
        page_size: int = 25,
        data_types: Optional[List[str]] = None,
        page_number: int = 1,
    ) -> List[Dict[str, Any]]:
        """Search for foods.

        Args:
            query: Search query
            page_size: Number of results per page
            data_types: Filter by data types (Foundation, SR Legacy, etc.)
            page_number: Page number (1-indexed)

        Returns:
            List of food search results
        """

    @abstractmethod
    def get_by_id(
        self,
        fdc_id: int,
        detail_format: str = "abridged",
        nutrient_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get food details by FDC ID.

        Args:
            fdc_id: FoodData Central ID
            detail_format: "abridged" or "full"
            nutrient_ids: Optional list of specific nutrient IDs to fetch

        Returns:
            Food details dictionary
        """

    @abstractmethod
    def has_cached(
        self,
        fdc_id: int,
        detail_format: str = "abridged",
        nutrient_ids: Optional[List[int]] = None,
    ) -> bool:
        """Check if food details are cached.

        Args:
            fdc_id: FoodData Central ID
            detail_format: "abridged" or "full"
            nutrient_ids: Optional list of nutrient IDs

        Returns:
            True if cached, False otherwise
        """


class USDAFoodRepository(FoodRepository):
    """USDA FoodData Central API repository implementation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache: Optional[Cache] = None,
    ) -> None:
        """Initialize repository.

        Args:
            api_key: USDA API key (if None, reads from environment)
            cache: Cache implementation (if None, uses InMemoryCache)
        """
        self._api_key = api_key or os.getenv("USDA_API_KEY")
        if not self._api_key:
            raise APIKeyMissingError(
                "USDA_API_KEY not found. Set environment variable or pass to constructor."
            )

        self._cache = cache if cache is not None else InMemoryCache()
        self._session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create HTTP session with connection pooling and retries."""
        session = requests.Session()

        retries = Retry(
            total=API_MAX_RETRY_ATTEMPTS,
            connect=API_MAX_RETRY_ATTEMPTS,
            read=API_MAX_RETRY_ATTEMPTS,
            backoff_factor=API_RETRY_BACKOFF_FACTOR,
            status_forcelist=API_RETRY_STATUS_CODES,
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )

        adapter = HTTPAdapter(
            max_retries=retries,
            pool_connections=API_POOL_CONNECTIONS,
            pool_maxsize=API_POOL_MAXSIZE,
        )

        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def search(
        self,
        query: str,
        page_size: int = 25,
        data_types: Optional[List[str]] = None,
        page_number: int = 1,
    ) -> List[Dict[str, Any]]:
        """Search for foods in USDA database."""
        if not query:
            return []

        # Create cache key
        cache_key = f"search:{query.lower().strip()}:{page_size}:{data_types}:{page_number}"

        # Check cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Build request params
        params: Dict[str, Any] = {
            "api_key": self._api_key,
            "query": query,
            "pageSize": page_size,
            "pageNumber": page_number,
        }

        data_type_list = None
        if data_types is not None:
            data_type_list = [dt for dt in data_types if str(dt).strip()]
            if data_type_list:
                params["dataType"] = data_type_list

        # Make request
        url = f"{USDA_API_BASE_URL}/foods/search"
        try:
            response = self._request(url, params=params)
        except USDAHTTPError as exc:
            if exc.status_code != 400:
                raise
            payload: Dict[str, Any] = {
                "query": query,
                "pageSize": page_size,
                "pageNumber": page_number,
            }
            if data_type_list:
                payload["dataType"] = data_type_list
            response = self._request(
                url,
                method="POST",
                json_body=payload,
            )

        # Extract results
        foods = response.get("foods", [])
        results = [
            {
                "fdcId": food.get("fdcId"),
                "description": food.get("description"),
                "brandOwner": food.get("brandOwner", ""),
                "dataType": food.get("dataType", ""),
            }
            for food in foods
        ]

        # Cache results
        self._cache.set(cache_key, results)

        return results

    def get_by_id(
        self,
        fdc_id: int,
        detail_format: str = "abridged",
        nutrient_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Get food details by FDC ID."""
        # Create cache key
        nutrient_tuple = tuple(sorted(nutrient_ids)) if nutrient_ids else None
        cache_key = f"food:{fdc_id}:{detail_format}:{nutrient_tuple}"

        # Check cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Determine request method
        if nutrient_ids:
            # POST endpoint for specific nutrients
            url = f"{USDA_API_BASE_URL}/foods"
            payload = {
                "fdcIds": [fdc_id],
                "format": detail_format if detail_format == "abridged" else None,
                "nutrients": nutrient_ids,
            }
            response = self._request(url, method="POST", json_body=payload)

            if not isinstance(response, list) or not response:
                raise USDAHTTPError(f"No data received for FDC ID {fdc_id}")

            data = response[0]
        else:
            # GET endpoint
            url = f"{USDA_API_BASE_URL}/food/{fdc_id}"
            params = {"api_key": self._api_key}
            if detail_format == "abridged":
                params["format"] = "abridged"

            data = self._request(url, params=params)

        # Cache result
        self._cache.set(cache_key, data)

        return data

    def has_cached(
        self,
        fdc_id: int,
        detail_format: str = "abridged",
        nutrient_ids: Optional[List[int]] = None,
    ) -> bool:
        """Check if food details are cached."""
        nutrient_tuple = tuple(sorted(nutrient_ids)) if nutrient_ids else None
        cache_key = f"food:{fdc_id}:{detail_format}:{nutrient_tuple}"
        return self._cache.get(cache_key) is not None

    def _request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
        json_body: Optional[Any] = None,
        timeout: Optional[tuple[float, float]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to USDA API."""
        if timeout is None:
            timeout = (API_CONNECT_TIMEOUT, API_READ_TIMEOUT_DEFAULT)

        if params is None:
            params = {}

        # Add API key if not present
        if "api_key" not in params:
            params["api_key"] = self._api_key

        try:
            response = self._session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                timeout=timeout,
            )
            response.raise_for_status()

        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            raise USDAHTTPError(
                f"HTTP error calling USDA API: {exc}",
                status_code=status,
            ) from exc

        except requests.RequestException as exc:
            raise USDAHTTPError(f"Network error calling USDA API: {exc}") from exc

        return response.json()
