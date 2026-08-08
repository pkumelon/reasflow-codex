#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import tarfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


def download(url: str, destination: Path) -> None:
    with urllib.request.urlopen(url, timeout=300) as response:
        destination.write_bytes(response.read())


def maybe_extract(path: Path, output_dir: Path) -> list[str]:
    extracted: list[str] = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            archive.extractall(output_dir)
            extracted = archive.namelist()
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as archive:
            archive.extractall(output_dir)
            extracted = archive.getnames()
    return extracted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-dir", default="Alg_Exp/data/raw")
    parser.add_argument("--extract", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source = args.source
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in {"http", "https"}:
        filename = Path(parsed.path).name or "downloaded_dataset"
        destination = output_dir / filename
        download(source, destination)
    else:
        source_path = Path(source).resolve()
        destination = output_dir / source_path.name
        if source_path.is_dir():
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source_path, destination)
        else:
            shutil.copy2(source_path, destination)

    extracted = maybe_extract(destination, output_dir) if args.extract and destination.is_file() else []
    print(
        json.dumps(
            {
                "source": source,
                "staged_to": str(destination),
                "output_dir": str(output_dir),
                "extracted": extracted,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
