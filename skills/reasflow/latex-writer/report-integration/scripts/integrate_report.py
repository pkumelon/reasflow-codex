#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


def normalize_title(path: Path) -> str:
    name = path.stem.replace("_", " ").replace("-", " ").strip()
    return name.title() if name else path.name


def load_content(path: Path, max_chars: int) -> str:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[... truncated ...]"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge multiple notes/reports into one provenance-preserving markdown report."
    )
    parser.add_argument("--output", required=True, help="Output markdown path.")
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        dest="inputs",
        help="Input note/report file path. Repeat for multiple files.",
    )
    parser.add_argument(
        "--max-chars-per-input",
        type=int,
        default=20_000,
        help="Truncate each input after this many characters.",
    )
    args = parser.parse_args()

    input_paths = [Path(path).resolve() for path in args.inputs]
    for input_path in input_paths:
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    sections: list[str] = [
        "# Integrated Report",
        "",
        f"_Generated at: {generated_at}_",
        "",
        "## Sources",
    ]
    for input_path in input_paths:
        sections.append(f"- {input_path}")

    for input_path in input_paths:
        sections.extend(
            [
                "",
                f"## {normalize_title(input_path)}",
                f"_Source: {input_path}_",
                "",
                load_content(input_path, args.max_chars_per_input),
            ]
        )

    output_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
