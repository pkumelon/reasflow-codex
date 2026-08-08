#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arxiv-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workspace")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser()
    if not output_dir.is_absolute() and args.workspace:
        output_dir = Path(args.workspace).expanduser() / output_dir
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    script_path = Path(__file__).with_name("download-arxiv.sh")
    with tempfile.TemporaryDirectory(prefix="reasflow-dev-arxiv-") as temp_dir:
        temp_output = Path(temp_dir) / "source"
        result = subprocess.run(
            [str(script_path), args.arxiv_id, str(temp_output)],
            check=False,
        )
        if result.returncode != 0:
            return result.returncode
        for child in temp_output.iterdir():
            destination = output_dir / child.name
            if destination.exists():
                if destination.is_dir():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
            if child.is_dir():
                shutil.copytree(child, destination)
            else:
                shutil.copy2(child, destination)

    print(f"Downloaded {args.arxiv_id} into {output_dir}")
    tex_files = sorted(path.relative_to(output_dir) for path in output_dir.rglob("*.tex"))
    if tex_files:
        print("TeX files:")
        for path in tex_files:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
