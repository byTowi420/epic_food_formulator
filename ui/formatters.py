from __future__ import annotations

from decimal import Decimal
from typing import Any

from domain.services.number_parser import parse_user_number

def _to_decimal(value: Any) -> Decimal | None:
    return parse_user_number(value)


def fmt_decimal(value: Any, decimals: int = 2, thousands: bool = True) -> str:
    dec = _to_decimal(value)
    if dec is None:
        return "-"
    quant = Decimal("1") if decimals <= 0 else Decimal(f"1.{'0' * decimals}")
    dec = dec.quantize(quant)
    pattern = f"{{:,.{decimals}f}}" if thousands else f"{{:.{decimals}f}}"
    formatted = pattern.format(dec)
    if thousands:
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted.replace(".", ",")


def fmt_money_mn(value: Any, decimals: int = 2, thousands: bool = True) -> str:
    dec = _to_decimal(value)
    if dec is None:
        return "-"
    return f"$ {fmt_decimal(dec, decimals=decimals, thousands=thousands)}"


def fmt_percent(value: Any, decimals: int = 1) -> str:
    dec = _to_decimal(value)
    if dec is None:
        return "-"
    return f"{fmt_decimal(dec, decimals=decimals)}%"


def fmt_qty(value: Any, unit: str, decimals: int = 2, thousands: bool = False) -> str:
    return f"{fmt_decimal(value, decimals=decimals, thousands=thousands)} {unit}"
