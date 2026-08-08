#!/usr/bin/env python3

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arxiv-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--use-llm", choices=["yes", "no"], default="no")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    target = (
        script_dir.parent.parent.parent
        / "domain-knowledge-cards"
        / "scripts"
        / "create-knowledge-card-from-arxiv.py"
    )

    cmd = [
        sys.executable,
        str(target),
        "--arxiv-id",
        args.arxiv_id,
        "--output-dir",
        args.output_dir,
        "--use-llm",
        args.use_llm,
    ]
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
