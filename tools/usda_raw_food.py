from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.constants import (  # noqa: E402
    API_CONNECT_TIMEOUT,
    API_READ_TIMEOUT_DEFAULT,
    USDA_API_BASE_URL,
)

load_dotenv(dotenv_path=ROOT / ".env")


def _parse_format(value: str) -> str:
    fmt = value.strip().lower()
    if fmt not in {"abridged", "full"}:
        raise argparse.ArgumentTypeError("format must be 'abridged' or 'full'")
    return fmt


def fetch_raw_food(
    fdc_id: int,
    detail_format: str,
    api_key: str,
    timeout: tuple[float, float],
) -> tuple[int, str]:
    params = {
        "api_key": api_key,
        "format": detail_format,
    }
    url = f"{USDA_API_BASE_URL}/food/{fdc_id}"
    response = requests.get(url, params=params, timeout=timeout)
    return response.status_code, response.text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch raw USDA FoodData Central payload by FDC ID.",
    )
    parser.add_argument("fdc_id", type=int, help="FDC ID to query.")
    parser.add_argument(
        "--format",
        dest="detail_format",
        type=_parse_format,
        default="abridged",
        help="Response format: abridged or full (default: abridged).",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=None,
        help="Override USDA API key (defaults to USDA_API_KEY env var).",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        nargs="?",
        const=".",
        default=None,
        help=(
            "Write raw response to a file instead of stdout. "
            "If a directory (or omitted with --out), writes "
            "fdc_<id>_<format>.json in that directory."
        ),
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=API_CONNECT_TIMEOUT,
        help="Connect timeout in seconds.",
    )
    parser.add_argument(
        "--read-timeout",
        type=float,
        default=API_READ_TIMEOUT_DEFAULT,
        help="Read timeout in seconds.",
    )
    args = parser.parse_args()

    api_key = args.api_key or os.getenv("USDA_API_KEY")
    if not api_key:
        raise SystemExit("USDA_API_KEY not set. Add it to .env or pass --api-key.")

    timeout = (args.connect_timeout, args.read_timeout)
    status_code, body = fetch_raw_food(
        args.fdc_id,
        args.detail_format,
        api_key,
        timeout,
    )

    if args.out_path:
        out_path = Path(args.out_path)
        filename = f"fdc_{args.fdc_id}_{args.detail_format}.json"
        if out_path.exists() and out_path.is_dir():
            out_path = out_path / filename
        elif str(out_path).endswith(("\\", "/")):
            out_path.mkdir(parents=True, exist_ok=True)
            out_path = out_path / filename
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)

    if status_code >= 400:
        print(
            f"\nHTTP {status_code} returned by USDA API.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
