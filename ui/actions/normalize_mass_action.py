from __future__ import annotations

from decimal import Decimal
from typing import Callable

from PySide6.QtWidgets import QDialog, QMessageBox, QPushButton, QWidget

from ui.dialogs.normalize_mass_dialog import NormalizeMassDialog


class NormalizeMassAction:
    def __init__(
        self,
        parent: QWidget,
        *,
        get_current_unit: Callable[[], str],
        get_total_mass_g: Callable[[], float],
        apply_normalization: Callable[[float], None],
        set_unit: Callable[[str], None],
        after_apply: Callable[[Decimal, str], None] | None = None,
        decimals_for_unit: Callable[[str], int] | None = None,
        can_run: Callable[[], tuple[bool, str | None] | bool] | None = None,
        on_blocked: Callable[[str], None] | None = None,
    ) -> None:
        self._parent = parent
        self._get_current_unit = get_current_unit
        self._get_total_mass_g = get_total_mass_g
        self._apply_normalization = apply_normalization
        self._set_unit = set_unit
        self._after_apply = after_apply
        self._decimals_for_unit = decimals_for_unit
        self._can_run = can_run
        self._on_blocked = on_blocked

    def create_button(self, text: str = "Normalizar masa") -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(self.run)
        return button

    def run(self) -> None:
        if self._can_run:
            result = self._can_run()
            if isinstance(result, tuple):
                can_run, message = result
            else:
                can_run, message = result, None
            if not can_run:
                if message:
                    if self._on_blocked:
                        self._on_blocked(message)
                    else:
                        QMessageBox.information(self._parent, "Normalizar masa", message)
                return
        dialog = NormalizeMassDialog(
            self._parent,
            current_total_g=self._get_total_mass_g(),
            current_unit=self._get_current_unit(),
            decimals_for_unit=self._decimals_for_unit,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        result = dialog.result_values()
        if result is None:
            return
        value, unit, target_g = result
        try:
            self._apply_normalization(float(target_g))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self._parent,
                "Error al normalizar",
                f"No se pudo normalizar la formulación:\n{exc}",
            )
            return

        self._set_unit(unit)
        if self._after_apply:
            self._after_apply(value, unit)
