#!/usr/bin/env python3
"""Smart plotting helper.

Two modes:
  --request   Natural-language description → LLM generates matplotlib code →
              execute → vision-analyze → iterate (up to --max-iterations).
  --spec-file / --spec-json  Structured JSON spec → direct rendering.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
DEFAULT_API_KEY = os.getenv("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def _call_llm(system: str, user: str, base_url: str, api_key: str, model: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": True,
    }).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "openai-python/1.0",
        },
        method="POST",
    )
    chunks: list[str] = []
    with urllib.request.urlopen(req, timeout=120) as resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                delta = json.loads(data)["choices"][0]["delta"].get("content", "")
                if delta:
                    chunks.append(delta)
            except (KeyError, json.JSONDecodeError):
                continue
    return "".join(chunks)


def _extract_code(text: str) -> str:
    """Pull the first ```python ... ``` block, or return text as-is."""
    import re
    m = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


# ---------------------------------------------------------------------------
# Request mode: LLM code generation + execution + vision iteration
# ---------------------------------------------------------------------------

CODEGEN_SYSTEM = textwrap.dedent("""\
    You are a matplotlib expert writing publication-quality figures for academic papers.
    Generate self-contained Python code that:
    - loads the data files listed in the user prompt,
    - renders the requested figure,
    - saves it to the exact output path given,
    - uses DPI=300, tight layout, paper-style aesthetics,
    - includes mean±std shading for multi-seed data when groupby is possible.
    Output ONLY the Python code block. No explanation.""")

CODEFIX_SYSTEM = textwrap.dedent("""\
    You are a matplotlib debugging expert.
    The following Python plotting code raised an error. Fix it.
    Output ONLY the corrected Python code block. No explanation.""")

IMPROVE_SYSTEM = textwrap.dedent("""\
    You are a matplotlib expert improving an academic figure based on visual review.
    The current code is provided. Apply the feedback to improve it.
    Output ONLY the corrected Python code block. No explanation.""")


def _run_code(code: str, python: str) -> tuple[bool, str]:
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp = f.name
    try:
        result = subprocess.run(
            [python, tmp], capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return False, (result.stderr or result.stdout)[:2000]
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "execution timed out after 60s"
    finally:
        Path(tmp).unlink(missing_ok=True)


def _vision_score(image_path: str, request: str, analyze_script: str, python: str,
                  base_url: str, api_key: str, model: str) -> tuple[float, str]:
    """Run analyze-plot.py and return (score, feedback)."""
    tmp_out = tempfile.mktemp(suffix=".json")
    cmd = [
        python, analyze_script,
        "--image", image_path,
        "--question", (
            f"Review this figure for academic paper quality. "
            f"The intended content: {request}. "
            "Score from 0-10 and provide one concrete improvement suggestion. "
            "Output JSON: {\"score\": <float>, \"feedback\": \"<one sentence>\"}"
        ),
        "--output", tmp_out,
        "--base-url", base_url,
        "--api-key", api_key,
        "--model", model,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=90)
        data = json.loads(Path(tmp_out).read_text())
        analysis = data.get("analysis", "")
        # parse score/feedback from analysis JSON or text
        import re
        m = re.search(r'"score"\s*:\s*([\d.]+)', analysis)
        score = float(m.group(1)) if m else 7.0
        m2 = re.search(r'"feedback"\s*:\s*"([^"]+)"', analysis)
        feedback = m2.group(1) if m2 else analysis[:200]
        return score, feedback
    except Exception as exc:
        return 7.0, str(exc)
    finally:
        Path(tmp_out).unlink(missing_ok=True)


def run_request_mode(args: argparse.Namespace) -> int:
    if not args.api_key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1
    if not args.base_url:
        print("ERROR: OPENAI_BASE_URL not set (required for request mode)", file=sys.stderr)
        return 1

    data_list = args.data_sources or []
    skill_dir = Path(__file__).parent
    analyze_script = str(skill_dir / "analyze-plot.py")
    python = args.python

    # Build initial codegen prompt
    data_info = "\n".join(f"  - {d}" for d in data_list)
    user_prompt = (
        f"Request: {args.request}\n\n"
        f"Data files:\n{data_info}\n\n"
        f"Output path: {args.output}\n"
        f"Style: paper, DPI=300, tight_layout"
    )
    if args.previous_feedback:
        user_prompt += f"\n\nPrevious feedback to address: {args.previous_feedback}"

    code = ""
    history: list[dict] = []

    for iteration in range(1, args.max_iterations + 1):
        print(f"[smart-plot] iteration {iteration}/{args.max_iterations}", file=sys.stderr)

        if not code:
            response = _call_llm(CODEGEN_SYSTEM, user_prompt, args.base_url, args.api_key, args.model)
            code = _extract_code(response)

        # Save code for inspection
        code_path = Path(args.output).with_suffix(".py")
        code_path.parent.mkdir(parents=True, exist_ok=True)
        code_path.write_text(code, encoding="utf-8")

        ok, error = _run_code(code, python)
        if not ok:
            print(f"[smart-plot] execution error: {error[:200]}", file=sys.stderr)
            if iteration < args.max_iterations:
                fix_prompt = f"Code:\n```python\n{code}\n```\n\nError:\n{error}"
                response = _call_llm(CODEFIX_SYSTEM, fix_prompt, args.base_url, args.api_key, args.model)
                code = _extract_code(response)
                continue
            result = {"status": "error", "error": error, "code_path": str(code_path)}
            print(json.dumps(result, indent=2))
            return 1

        # Execution succeeded
        entry: dict[str, Any] = {"iteration": iteration, "status": "ok"}
        history.append(entry)

        if args.auto_analyze and Path(args.output).exists():
            score, feedback = _vision_score(
                args.output, args.request, analyze_script, python,
                args.base_url, args.api_key, args.model
            )
            entry["vision_score"] = score
            entry["feedback"] = feedback
            print(f"[smart-plot] vision score: {score:.1f}  feedback: {feedback}", file=sys.stderr)

            if score < 8.5 and iteration < args.max_iterations:
                improve_prompt = (
                    f"Current code:\n```python\n{code}\n```\n\n"
                    f"Visual feedback: {feedback}\n"
                    f"Original request: {args.request}"
                )
                response = _call_llm(IMPROVE_SYSTEM, improve_prompt, args.base_url, args.api_key, args.model)
                code = _extract_code(response)
                continue

        # Done
        result = {
            "status": "success",
            "output": args.output,
            "code_path": str(code_path),
            "iterations": history,
        }
        if args.metadata_output:
            Path(args.metadata_output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.metadata_output).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0

    # Exhausted iterations but last attempt succeeded
    result = {"status": "success", "output": args.output, "iterations": history}
    if args.metadata_output:
        Path(args.metadata_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.metadata_output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Spec mode (original structured rendering)
# ---------------------------------------------------------------------------

def load_spec(args: argparse.Namespace) -> dict[str, Any]:
    if args.spec_json:
        return json.loads(args.spec_json)
    if args.spec_file:
        return json.loads(Path(args.spec_file).read_text())
    raise SystemExit("Provide --spec-json or --spec-file, or use --request for LLM mode")


def load_frame(path: Path):
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("pandas required. Install: Alg_Exp/.venv/bin/pip install pandas") from exc
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".json":
        return pd.read_json(path)
    if suffix == ".jsonl":
        return pd.read_json(path, lines=True)
    raise SystemExit(f"Unsupported data source: {path}")


def style_plot(style: str) -> None:
    try:
        import seaborn as sns
        if style == "paper":
            sns.set_theme(style="whitegrid", context="paper")
        elif style == "presentation":
            sns.set_theme(style="ticks", context="talk")
        else:
            sns.set_theme(style="whitegrid")
    except ImportError:
        pass
    import matplotlib.pyplot as plt
    plt.rcParams["figure.dpi"] = 300
    plt.rcParams["savefig.dpi"] = 300


def run_spec_mode(args: argparse.Namespace) -> int:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit("matplotlib required. Install: Alg_Exp/.venv/bin/pip install matplotlib") from exc

    spec = load_spec(args)
    style_plot(spec.get("style", "paper"))
    fig, ax = plt.subplots(figsize=tuple(spec.get("figsize", [6.4, 4.2])))
    chart = spec.get("chart", "line")
    entries = spec.get("data", [])
    if not entries:
        raise SystemExit("spec.data must contain at least one series")

    for entry in entries:
        frame = load_frame(Path(entry["file"]).resolve())
        if chart == "line":
            label = entry.get("label")
            x, y, groupby = entry["x"], entry["y"], entry.get("groupby")
            if groupby and groupby in frame.columns:
                g = frame.groupby(x)[y]
                mean, std = g.mean(), g.std().fillna(0)
                ax.plot(mean.index, mean.values, label=label)
                ax.fill_between(mean.index, mean - std, mean + std, alpha=0.2)
            else:
                ax.plot(frame[x], frame[y], label=label)
        elif chart == "bar":
            ax.bar(frame[entry["x"]], frame[entry["y"]], label=entry.get("label"), alpha=0.85)
        elif chart == "scatter":
            ax.scatter(frame[entry["x"]], frame[entry["y"]], label=entry.get("label"), s=24)
        elif chart == "heatmap":
            try:
                import seaborn as sns
            except ImportError as exc:
                raise SystemExit("seaborn required for heatmap") from exc
            pivot = frame.pivot(index=entry["index"], columns=entry["columns"], values=entry["values"])
            sns.heatmap(pivot, ax=ax, cmap=entry.get("cmap", "viridis"))
        else:
            raise SystemExit(f"Unsupported chart type: {chart}")

    ax.set_title(spec.get("title", ""))
    ax.set_xlabel(spec.get("xlabel", ""))
    ax.set_ylabel(spec.get("ylabel", ""))
    if spec.get("xscale"):
        ax.set_xscale(spec["xscale"])
    if spec.get("yscale"):
        ax.set_yscale(spec["yscale"])
    if spec.get("legend", True) and chart != "heatmap":
        ax.legend()
    if spec.get("grid", chart != "heatmap"):
        ax.grid(True, alpha=0.3)

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)

    metadata = {"status": "success", "output": str(output), "chart": chart, "series": len(entries)}
    if args.metadata_output:
        Path(args.metadata_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.metadata_output).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Smart plotting: LLM request mode or structured spec mode")
    # Shared
    parser.add_argument("--output", required=True, help="Output image path")
    parser.add_argument("--metadata-output", default="")
    # Request mode
    parser.add_argument("--request", default="", help="Natural-language figure description (triggers LLM mode)")
    parser.add_argument("--data-sources", nargs="+", default=[], help="Data files for request mode")
    parser.add_argument("--auto-analyze", action="store_true", default=True, help="Run vision analysis after each iteration")
    parser.add_argument("--no-auto-analyze", dest="auto_analyze", action="store_false")
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--previous-feedback", default="")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter for code execution")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=DEFAULT_API_KEY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    # Spec mode
    parser.add_argument("--spec-file", default="")
    parser.add_argument("--spec-json", default="")
    args = parser.parse_args()

    if args.request:
        return run_request_mode(args)
    return run_spec_mode(args)


if __name__ == "__main__":
    raise SystemExit(main())
