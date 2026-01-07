from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DIRS = (
    "application",
    "config",
    "domain",
    "infrastructure",
    "services",
    "ui",
)


class DefCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.defs: list[tuple[str, int]] = []
        self.defs_with_lines: list[tuple[str, list[int]]] = []
        self._class_stack: list[str] = []
        self._func_depth = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_def(node.name, node.lineno, node.decorator_list)
        self._func_depth += 1
        self.generic_visit(node)
        self._func_depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_def(node.name, node.lineno, node.decorator_list)
        self._func_depth += 1
        self.generic_visit(node)
        self._func_depth -= 1

    def _record_def(
        self,
        name: str,
        line: int,
        decorators: list[ast.expr],
    ) -> None:
        if self._func_depth > 0:
            return
        if self._class_stack:
            qualname = ".".join(self._class_stack + [name])
        else:
            qualname = name
        lines = [line]
        for deco in decorators:
            deco_line = getattr(deco, "lineno", None)
            if isinstance(deco_line, int):
                lines.append(deco_line)
        unique_lines = sorted(set(lines))
        self.defs.append((qualname, line))
        self.defs_with_lines.append((qualname, unique_lines))


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for folder in ALLOWED_DIRS:
        base = ROOT / folder
        if not base.exists():
            continue
        files.extend(base.rglob("*.py"))
    return files


def _load_trace(trace_path: Path) -> tuple[set[tuple[str, int]], set[tuple[str, str]]]:
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    executed_by_line: set[tuple[str, int]] = set()
    executed_by_name: set[tuple[str, str]] = set()
    for record in payload.get("records", []):
        file_path = record.get("file", "")
        qualname = record.get("qualname", "")
        line = record.get("line")
        if file_path and isinstance(line, int):
            executed_by_line.add((file_path, line))
        if file_path and qualname:
            executed_by_name.add((file_path, qualname))
    return executed_by_line, executed_by_name


def _collect_defs() -> list[dict[str, object]]:
    defs: list[dict[str, object]] = []
    for path in _iter_python_files():
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            continue
        collector = DefCollector()
        collector.visit(tree)
        for (qualname, def_line), (_, lines) in zip(
            collector.defs,
            collector.defs_with_lines,
        ):
            defs.append(
                {
                    "file": rel,
                    "qualname": qualname,
                    "line": def_line,
                    "lines": lines,
                }
            )
    return defs


def _build_report(
    trace_path: Path,
    output_path: Path,
) -> None:
    executed_by_line, executed_by_name = _load_trace(trace_path)
    all_defs = _collect_defs()
    unused = [
        item
        for item in all_defs
        if not any(
            (item["file"], line) in executed_by_line
            for line in item.get("lines", [])
        )
        and (item["file"], item["qualname"]) not in executed_by_name
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Runtime audit report")
    lines.append("")
    lines.append(f"Trace file: {trace_path}")
    lines.append(f"Total defs: {len(all_defs)}")
    lines.append(f"Executed defs: {len(all_defs) - len(unused)}")
    lines.append(f"Not executed: {len(unused)}")
    lines.append("")
    lines.append("Notes:")
    lines.append("- Results depend on which UI flows you exercised.")
    lines.append("- Some callbacks may only run under specific conditions.")
    lines.append("- Matching uses file+line to account for mixin methods.")
    lines.append("")
    lines.append("## Not executed (candidates)")

    if not unused:
        lines.append("")
        lines.append("No candidates found in this run.")
    else:
        current_file = None
        for item in sorted(unused, key=lambda x: (x["file"], x["line"], x["qualname"])):
            if item["file"] != current_file:
                current_file = item["file"]
                lines.append("")
                lines.append(f"### {current_file}")
            lines.append(f"- L{item['line']}: {item['qualname']}")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate runtime audit report.")
    parser.add_argument(
        "--trace",
        dest="trace_path",
        default=str(ROOT / "tmp_blobs" / "runtime_trace.json"),
        help="Path to runtime trace JSON.",
    )
    parser.add_argument(
        "--out",
        dest="out_path",
        default=str(ROOT / "tmp_blobs" / "audit_report.md"),
        help="Path to write the report markdown.",
    )
    args = parser.parse_args()

    trace_path = Path(args.trace_path)
    if not trace_path.exists():
        raise SystemExit(f"Trace file not found: {trace_path}")

    _build_report(trace_path, Path(args.out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
