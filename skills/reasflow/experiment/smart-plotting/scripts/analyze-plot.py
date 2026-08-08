#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")


def fallback_analysis(image_path: Path, error_message: str) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "fallback",
        "image": str(image_path),
        "analysis": (
            "Remote plot analysis was unavailable. Inspect the plot manually; "
            f"the helper returned fallback metadata only. Error: {error_message}"
        ),
    }
    try:
        from PIL import Image

        with Image.open(image_path) as image:
            result["image_metadata"] = {
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "size_bytes": image_path.stat().st_size,
            }
    except Exception:
        result["image_metadata"] = {"size_bytes": image_path.stat().st_size}
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--question", default="Analyze this scientific plot. Summarize the main trend, obvious quality issues, and improvement suggestions.")
    parser.add_argument("--output")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    if not args.base_url or not args.api_key:
        print(
            "ERROR: OPENAI_BASE_URL and OPENAI_API_KEY must be set "
            "(via environment or --base-url/--api-key) before running analyze-plot.",
            file=sys.stderr,
        )
        return 1

    image_path = Path(args.image).resolve()
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    payload = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    body = {
        "model": args.model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": args.question},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{payload}"},
                    },
                ],
            }
        ],
        "stream": True,
    }

    request = urllib.request.Request(
        args.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {args.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "openai-python/1.0",
        },
        method="POST",
    )
    try:
        chunks = []
        with urllib.request.urlopen(request, timeout=120) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        chunks.append(delta)
                except (KeyError, IndexError, json.JSONDecodeError):
                    continue
        result = {
            "status": "ok",
            "image": str(image_path),
            "analysis": "".join(chunks),
            "model": args.model,
        }
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        result = fallback_analysis(image_path, f"HTTP {exc.code}: {error_body[:300]}")
        result["model"] = args.model
    except Exception as exc:
        result = fallback_analysis(image_path, str(exc))
        result["model"] = args.model

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
