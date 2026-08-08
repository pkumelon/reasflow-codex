#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path


def parse_section_arg(raw: str) -> tuple[str, str]:
    if "::" in raw:
        title, claim = raw.split("::", 1)
        return title.strip(), claim.strip()
    return raw.strip(), ""


def build_draft(sections: list[tuple[str, str]]) -> str:
    lines = [
        "% Auto-generated chapter draft scaffold",
        "% Fill each section with evidence-backed prose and citations.",
        "",
    ]
    for title, claim in sections:
        lines.append(f"\\section{{{title}}}")
        if claim:
            lines.append(f"% Claim: {claim}")
        else:
            lines.append("% Claim: TODO")
        lines.append("% Evidence:")
        lines.append("% -")
        lines.append("% Open questions:")
        lines.append("% -")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a chapter draft scaffold from section titles and claim hints."
    )
    parser.add_argument("--output", required=True, help="Output .tex file path.")
    parser.add_argument(
        "--section",
        action="append",
        required=True,
        dest="sections",
        help="Section spec: 'Section Title::Core claim'. Repeat for multiple sections.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite output file if it exists.")
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    if output_path.exists() and not args.force:
        raise FileExistsError(f"Output already exists: {output_path}. Use --force to overwrite.")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sections = [parse_section_arg(item) for item in args.sections]
    output_path.write_text(build_draft(sections), encoding="utf-8")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
