from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.runtime_trace import install_trace  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run app with runtime tracing enabled.")
    parser.add_argument(
        "--out",
        dest="out_path",
        default=str(ROOT / "tmp_blobs" / "runtime_trace.json"),
        help="Path to write trace JSON.",
    )
    args = parser.parse_args()

    os.environ["FF_TRACE_PATH"] = args.out_path
    install_trace(args.out_path)

    import main as app_main  # noqa: E402

    app_main.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
