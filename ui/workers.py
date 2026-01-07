from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

from PySide6.QtCore import QObject, Signal, Slot

from domain.exceptions import USDAHTTPError
from infrastructure.api.usda_repository import FoodRepository


class ApiWorker(QObject):
    """Run a callable in a background thread and emit results via signals."""

    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args) -> None:
        super().__init__()
        self.fn = fn
        self.args = args

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn(*self.args)
        except Exception as exc:  # noqa: BLE001 - surface any API/Value errors to UI
            self.error.emit(str(exc))
        else:
            self.finished.emit(result)


class ImportWorker(QObject):
    """Hydrate formulation items in a worker thread with retry + progress feedback."""

    progress = Signal(str)
    finished = Signal(list, list)
    error = Signal(str)

    def __init__(
        self,
        food_repository_provider: Callable[[], FoodRepository],
        items: list[Dict[str, Any]],
        max_attempts: int = 4,
        read_timeout: float = 8.0,
    ) -> None:
        super().__init__()
        self._food_repository_provider = food_repository_provider
        self.items = items
        self.max_attempts = max_attempts
        self.read_timeout = read_timeout

    @Slot()
    def run(self) -> None:
        hydrated_payload: list[Dict[str, Any]] = []
        warnings: list[str] = []
        try:
            repository = self._food_repository_provider()
        except Exception as exc:  # noqa: BLE001 - surface setup errors
            self.error.emit(str(exc))
            return
        total = len(self.items)
        for idx, item in enumerate(self.items, start=1):
            try:
                fdc_id_int = int(item.get("fdc_id"))
            except Exception:
                warnings.append(
                    f"Ingrediente omitido: FDC ID invalido ({item.get('fdc_id')})."
                )
                continue

            base_item = dict(item)
            base_item["fdc_id"] = fdc_id_int

            attempts = 0
            details: Dict[str, Any] | None = None
            skip_item = False
            while attempts < self.max_attempts:
                attempts += 1
                self.progress.emit(f"{idx}/{total} ID #{fdc_id_int}")
                try:
                    details = repository.get_by_id(
                        fdc_id_int,
                        timeout=(3.05, self.read_timeout),
                        detail_format="abridged",
                    )
                    break
                except Exception as exc:  # noqa: BLE001 - bubble up the root error
                    if isinstance(exc, USDAHTTPError):
                        msg = str(exc)
                        if exc.status_code == 404 or "No data received for FDC ID" in msg:
                            warnings.append(
                                f"Ingrediente omitido: FDC {fdc_id_int} no encontrado en USDA."
                            )
                            skip_item = True
                            break
                    if attempts < self.max_attempts:
                        self.progress.emit(
                            f"{idx}/{total} ID #{fdc_id_int} Failed - Retrying ({attempts}/{self.max_attempts})"
                        )
                        continue
                    self.progress.emit(f"{idx}/{total} ID #{fdc_id_int} Failed")
                    self.error.emit(
                        f"No se pudo cargar el FDC {fdc_id_int} tras {self.max_attempts} intentos: {exc}"
                    )
                    return

            if skip_item:
                continue
            if details is None:
                continue

            hydrated_payload.append({"base": base_item, "details": details or {}})

        self.finished.emit(hydrated_payload, warnings)


class AddWorker(QObject):
    """Fetch a single ingredient with retries and progress feedback."""

    progress = Signal(str)
    finished = Signal(dict, str, float)
    error = Signal(str)

    def __init__(
        self,
        food_repository_provider: Callable[[], FoodRepository],
        fdc_id: int,
        max_attempts: int,
        read_timeout: float,
        mode: str,
        value: float,
    ) -> None:
        super().__init__()
        self._food_repository_provider = food_repository_provider
        self.fdc_id = fdc_id
        self.max_attempts = max_attempts
        self.read_timeout = read_timeout
        self.mode = mode
        self.value = value

    @Slot()
    def run(self) -> None:
        logging.debug(f"AddWorker start fdc_id={self.fdc_id} attempts={self.max_attempts}")
        try:
            repository = self._food_repository_provider()
        except Exception as exc:  # noqa: BLE001 - surface setup errors
            self.error.emit(str(exc))
            return
        attempts = 0
        while attempts < self.max_attempts:
            attempts += 1
            self.progress.emit(f"1/1 ID #{self.fdc_id}")
            try:
                logging.debug(
                    f"AddWorker attempt {attempts} fetching fdc_id={self.fdc_id} timeout={self.read_timeout}"
                )
                details = repository.get_by_id(
                    self.fdc_id,
                    timeout=(3.05, max(self.read_timeout, 8.0)),
                    detail_format="abridged",
                )
                logging.debug(
                    f"AddWorker success fdc_id={self.fdc_id} nutrients={len(details.get('foodNutrients', []) or [])}"
                )
                self.finished.emit(details, self.mode, self.value)
                return
            except Exception as exc:  # noqa: BLE001 - show after retries
                logging.exception(f"AddWorker error fdc_id={self.fdc_id} attempt={attempts}: {exc}")
                if attempts < self.max_attempts:
                    self.progress.emit(
                        f"1/1 ID #{self.fdc_id} Failed - Retrying ({attempts}/{self.max_attempts})"
                    )
                    continue
                self.progress.emit(f"1/1 ID #{self.fdc_id} Failed")
                self.error.emit(
                    f"No se pudo cargar el FDC {self.fdc_id} tras {self.max_attempts} intentos: {exc}"
                )
                return
