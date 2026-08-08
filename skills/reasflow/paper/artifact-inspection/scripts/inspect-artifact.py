#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
from pathlib import Path


def read_csv(path: Path, preview_rows: int) -> str:
    try:
        import pandas as pd
    except ImportError:
        with path.open(newline="", encoding="utf-8", errors="ignore") as handle:
            rows = list(csv.reader(handle))
        return json.dumps({"file": str(path), "preview": rows[: preview_rows + 1]}, indent=2)
    frame = pd.read_csv(path)
    payload = {
        "file": str(path),
        "shape": list(frame.shape),
        "columns": list(frame.columns),
        "preview": frame.head(preview_rows).to_dict(orient="records"),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def read_jsonl(path: Path, preview_rows: int) -> str:
    rows = []
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for index, line in enumerate(handle):
            if index >= preview_rows:
                break
            rows.append(json.loads(line))
    return json.dumps({"file": str(path), "preview": rows}, indent=2, ensure_ascii=False)


def read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SystemExit(
            "pypdf is required for PDF inspection. Install it in Alg_Exp/.venv: "
            "Alg_Exp/.venv/bin/pip install pypdf"
        ) from exc
    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages[:10], start=1):
        pages.append({"page": index, "text": page.extract_text() or ""})
    return json.dumps({"file": str(path), "pages": len(reader.pages), "preview": pages}, indent=2, ensure_ascii=False)


def read_image(path: Path, emit_base64: bool) -> str:
    payload = {
        "file": str(path),
        "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        "size_bytes": path.stat().st_size,
    }
    try:
        from PIL import Image

        with Image.open(path) as image:
            payload["width"] = image.width
            payload["height"] = image.height
            payload["mode"] = image.mode
    except Exception:
        pass
    if emit_base64:
        payload["base64"] = base64.b64encode(path.read_bytes()).decode("utf-8")
    return json.dumps(payload, indent=2, ensure_ascii=False)


def read_text(path: Path, start_line: int, end_line: int) -> str:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    start = max(1, start_line)
    stop = len(lines) if end_line < 0 else min(end_line, len(lines))
    selected = [{"line": idx, "text": lines[idx - 1]} for idx in range(start, stop + 1)]
    return json.dumps({"file": str(path), "preview": selected}, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--start-line", type=int, default=1)
    parser.add_argument("--end-line", type=int, default=-1)
    parser.add_argument("--preview-rows", type=int, default=10)
    parser.add_argument("--emit-base64", action="store_true")
    args = parser.parse_args()

    path = Path(args.path).resolve()
    suffix = path.suffix.lower()
    if suffix == ".csv":
        print(read_csv(path, args.preview_rows))
    elif suffix == ".json":
        print(json.dumps(json.loads(path.read_text()), indent=2, ensure_ascii=False))
    elif suffix == ".jsonl":
        print(read_jsonl(path, args.preview_rows))
    elif suffix == ".pdf":
        print(read_pdf(path))
    elif suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}:
        print(read_image(path, args.emit_base64))
    else:
        print(read_text(path, args.start_line, args.end_line))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
