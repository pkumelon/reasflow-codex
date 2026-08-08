#!/usr/bin/env python3
"""Prepare and finalize Introduction drafts written by a native Codex subagent."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Style templates
# ---------------------------------------------------------------------------

ML_TEMPLATE = """
Structure for Machine Learning / Deep Learning / AI papers (NeurIPS/ICML/ICLR style):
1. Hook (1-2 sentences): Striking observation or key motivation.
2. Background (2-3 sentences): Research context and problem definition.
3. Gap (2-3 sentences): Limitations of existing methods — what is missing.
4. Our Approach (2-3 sentences): What this paper does and how.
5. Contributions (3-5 bullets): Concrete, evidence-backed claims.
Rules: Emphasize experimental results, performance comparisons, practical applications.
""".strip()

MATH_TEMPLATE = """
Structure for Applied Mathematics / Optimization papers (SIAM / Mathematical Programming style):
1. Hook (1-2 sentences): Research motivation.
2. Objective (2-3 sentences): Formal problem statement with math notation.
3. Background (2-3 sentences): Mathematical context and prior work overview.
4. Related Work (3-4 sentences): Categorized prior work with gaps.
5. Gap (2-3 sentences): What is unsolved or missing in the literature.
6. Contributions (3-5 bullets): Theoretical results and innovations.
7. Notation (1-2 sentences): Key symbols and conventions.
8. Organization (1-2 sentences): Paper structure overview.
Rules: Include formal notation, problem formulation, convergence/complexity results.
""".strip()

DEFAULT_TEMPLATE = """
Structure for General CS papers:
1. Hook (1-2 sentences): Motivation.
2. Background (2-3 sentences): Context.
3. Survey (2-3 sentences): Related work overview.
4. Gap (2-3 sentences): Unresolved issues.
5. Contributions (3-5 bullets): This paper's answers.
""".strip()

WRITER_INSTRUCTIONS = """Write a high-quality academic Introduction in LaTeX.

Write the LaTeX draft and citation trace directly to the exact output paths in the task.
Do not create or edit BibTeX; the coordinator builds it deterministically.

Anti-hallucination rules:
- Every factual claim must be supported by the provided information.
- Every sentence about prior work, field history, established empirical facts, comparisons,
  or limitations of existing methods must contain an inline citation in that sentence.
- Use only exact keys from the provided reference catalog and citation contract.
- A citation elsewhere in the paragraph does not cover an uncited literature claim.
- Record every source claim actually used in the trace JSON with its claim_id and cited keys.
- If a literature claim has no verified key, omit or weaken it; never emit unresolved markers.
- Do not invent paper titles, authors, or results.
- Do not invent citation keys or rewrite BibTeX.
"""

CITE_PATTERN = re.compile(
    r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\])?\s*(?:\[[^\]]*\])?\{([^}]*)\}"
)
UNRESOLVED_MARKER_PATTERN = re.compile(
    r"\[(?:needs-citation|needs-result|scope-check|terminology-check|remove-if-unproven)\]|\[VERIFY\s*:",
    re.IGNORECASE,
)
LITERATURE_CUE_PATTERN = re.compile(
    r"\b(?:prior|previous|existing|recent|foundational|classical|literature|studies|researchers|"
    r"methods?|approaches?|algorithms?|frameworks?|baselines?)\b.{0,180}\b(?:show|shows|shown|"
    r"demonstrate|demonstrates|establish|establishes|achieve|achieves|require|requires|rely|relies|"
    r"use|uses|suffer|suffers|lack|lacks|limit|limits|remain|remains|typically|often|widely|can|cannot)\b|"
    r"\b(?:has emerged|have emerged|widely (?:used|adopted)|line of work|body of work|"
    r"state[- ]of[- ]the[- ]art|no existing|most existing)\b",
    re.IGNORECASE,
)
FIRST_PERSON_CLAIM_PATTERN = re.compile(
    r"\b(?:we|our|this paper|this work)\s+(?:propose|introduce|develop|prove|show|establish|present|evaluate|study)\b",
    re.IGNORECASE,
)
ORGANIZATION_SENTENCE_PATTERN = re.compile(
    r"\b(?:the remainder of (?:this|the) paper|the rest of (?:this|the) paper|"
    r"(?:this|the) paper is organized as follows)\b",
    re.IGNORECASE,
)


def _build_writer_task(
    title: str,
    problem_background: str,
    related_works: str,
    method_summary: str,
    style: str,
    results_preview: str,
    user_feedback: str,
    reference_catalog: str,
    citation_claims: list[dict[str, Any]],
    draft_output: str,
    trace_output: str,
    excluded_contract_keys: list[str],
) -> dict[str, Any]:
    template = {"ml": ML_TEMPLATE, "math": MATH_TEMPLATE}.get(style, DEFAULT_TEMPLATE)
    return {
        "task_version": 1,
        "task_type": "intro_writing",
        "executor": "codex_subagent",
        "instructions": WRITER_INSTRUCTIONS,
        "paper_title": title,
        "style": style,
        "template": template,
        "evidence": {
            "problem_background": problem_background,
            "related_works": related_works,
            "method_summary": method_summary,
            "results_preview": results_preview,
        },
        "verified_reference_catalog": reference_catalog,
        "citation_contract": citation_claims,
        "excluded_unverified_keys": excluded_contract_keys,
        "revision_feedback": user_feedback,
        "outputs": {
            "draft_tex": draft_output,
            "citation_trace_json": trace_output,
        },
        "trace_schema": {
            "claims": [
                {"claim_id": "claim-0001", "bibtex_keys": ["exactKey"]}
            ]
        },
    }


def _parse_bib_entries(content: str) -> dict[str, str]:
    starts = [match.start() for match in re.finditer(r"(?m)^\s*@\w+\s*[({]", content)]
    entries: dict[str, str] = {}
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(content)
        entry = content[start:end].strip()
        key_match = re.match(r"@\w+\s*[({]\s*([^,\s]+)\s*,", entry, re.IGNORECASE)
        if key_match:
            entries[key_match.group(1).strip()] = entry
    return entries


def _entry_title(entry: str) -> str:
    title_match = re.search(
        r"\btitle\s*=\s*[\"{](.*?)(?<!\\)[\"}]\s*,?\s*(?:\n|$)",
        entry,
        re.IGNORECASE | re.DOTALL,
    )
    if not title_match:
        return ""
    return re.sub(r"\s+", " ", title_match.group(1)).strip(" {}\"")


def _reference_catalog(entries: dict[str, str]) -> str:
    lines = []
    for key, entry in entries.items():
        title = _entry_title(entry)
        lines.append(f"- {key}: {title or '(title unavailable)'}")
    return "\n".join(lines)


def _verified_citation_claims(
    claims: list[dict[str, Any]],
    entries: dict[str, str],
) -> tuple[list[dict[str, Any]], list[str]]:
    verified: list[dict[str, Any]] = []
    excluded_keys: set[str] = set()
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for claim in claims:
        raw_keys = [str(key) for key in claim.get("bibtex_keys", []) if str(key)]
        valid_keys = [key for key in raw_keys if key in entries]
        excluded_keys.update(set(raw_keys) - set(valid_keys))
        if not valid_keys:
            continue
        normalized_text = re.sub(r"\s+", " ", str(claim.get("text", ""))).strip().lower()
        identity = (normalized_text, tuple(valid_keys))
        if identity in seen:
            continue
        seen.add(identity)
        verified_claim = dict(claim)
        verified_claim["bibtex_keys"] = valid_keys
        verified_claim["citation_required"] = True
        verified.append(verified_claim)
    return verified, sorted(excluded_keys)


def _ordered_cite_keys(tex: str) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for match in CITE_PATTERN.finditer(tex):
        for raw_key in match.group(1).split(","):
            key = raw_key.strip()
            if key and key not in seen:
                keys.append(key)
                seen.add(key)
    return keys


def _strip_tex_for_classification(sentence: str) -> str:
    text = CITE_PATTERN.sub("", sentence)
    text = re.sub(r"\\(?:section|subsection|subsubsection)\*?\{[^}]*\}", "", text)
    text = re.sub(r"\\[a-zA-Z*]+(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z*]+", "", text)
    text = re.sub(r"[$][^$]*[$]", " MATH ", text)
    return re.sub(r"\s+", " ", text).strip()


def _uncited_literature_sentences(tex: str) -> list[str]:
    without_comments = re.sub(r"(?m)(?<!\\)%.*$", "", tex)
    without_displays = re.sub(
        r"\\begin\{(?:equation|align|gather|multline|table|figure)[^}]*\}.*?"
        r"\\end\{(?:equation|align|gather|multline|table|figure)\*?\}",
        " ",
        without_comments,
        flags=re.DOTALL,
    )
    findings: list[str] = []
    for paragraph in re.split(r"\n\s*\n", without_displays):
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z\\])", paragraph.strip()):
            plain = _strip_tex_for_classification(sentence)
            if (
                len(plain.split()) < 6
                or FIRST_PERSON_CLAIM_PATTERN.search(plain)
                or ORGANIZATION_SENTENCE_PATTERN.search(plain)
            ):
                continue
            if LITERATURE_CUE_PATTERN.search(plain) and not CITE_PATTERN.search(sentence):
                findings.append(plain[:300])
    return findings


def _load_organized_info(path: str) -> dict[str, Any]:
    if not path:
        return {}
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(loaded.get("organized_info"), dict):
        return loaded["organized_info"]
    return loaded


def _validate_output(
    tex: str,
    input_entries: dict[str, str],
    citation_claims: list[dict[str, Any]],
    trace: dict[str, Any],
) -> dict[str, Any]:
    cited_keys = _ordered_cite_keys(tex)
    cited_key_set = set(cited_keys)
    missing_keys = sorted(cited_key_set - set(input_entries))
    unresolved_markers = sorted(set(UNRESOLVED_MARKER_PATTERN.findall(tex)))
    uncited_sentences = _uncited_literature_sentences(tex)

    claim_by_id = {
        str(claim.get("claim_id", "")): claim
        for claim in citation_claims
        if str(claim.get("claim_id", ""))
    }
    trace_errors: list[str] = []
    trace_items = trace.get("claims", []) if isinstance(trace, dict) else []
    if cited_keys and citation_claims and not isinstance(trace_items, list):
        trace_errors.append("TRACE must contain a claims list")
        trace_items = []
    if cited_keys and citation_claims and not trace_items:
        trace_errors.append("TRACE must map cited source claims to their verified keys")
    traced_key_set: set[str] = set()
    for item in trace_items if isinstance(trace_items, list) else []:
        if not isinstance(item, dict):
            trace_errors.append("TRACE claim entries must be objects")
            continue
        claim_id = str(item.get("claim_id", ""))
        if claim_id not in claim_by_id:
            trace_errors.append(f"unknown claim_id in TRACE: {claim_id}")
            continue
        allowed = {str(key) for key in claim_by_id[claim_id].get("bibtex_keys", [])}
        traced = {str(key) for key in item.get("bibtex_keys", [])}
        traced_key_set.update(traced)
        if not traced or not traced <= allowed:
            trace_errors.append(f"TRACE keys for {claim_id} are not allowed by the citation contract")
        if not traced <= cited_key_set:
            trace_errors.append(f"TRACE keys for {claim_id} do not appear in the TeX output")
    untraced_keys = sorted(cited_key_set - traced_key_set)
    if citation_claims and untraced_keys:
        trace_errors.append(
            "cited keys missing from TRACE provenance: " + ", ".join(untraced_keys)
        )

    errors: list[str] = []
    if missing_keys:
        errors.append(f"undefined or unverified citation keys: {', '.join(missing_keys)}")
    if unresolved_markers:
        errors.append("unresolved evidence markers remain")
    if citation_claims and not cited_keys:
        errors.append("no citations were generated despite a non-empty citation contract")
    if uncited_sentences:
        errors.append(f"{len(uncited_sentences)} literature claim sentence(s) lack inline citations")
    errors.extend(trace_errors)
    return {
        "passed": not errors,
        "errors": errors,
        "cited_keys": cited_keys,
        "missing_keys": missing_keys,
        "unresolved_markers": unresolved_markers,
        "uncited_literature_sentences": uncited_sentences,
        "trace_errors": trace_errors,
        "trace": trace,
    }


def _load_trace(path: str) -> dict[str, Any]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("citation trace must be a JSON object")
    return loaded


def _make_main_tex(tex_output_path: str, bib_output_path: str) -> str:
    tex_rel = Path(tex_output_path).name
    bib_rel = Path(bib_output_path).stem
    return rf"""\documentclass{{article}}
\usepackage{{amsmath,amssymb,amsthm}}
\usepackage{{hyperref}}
\usepackage{{natbib}}
\begin{{document}}
\input{{{tex_rel}}}
\bibliographystyle{{plainnat}}
\bibliography{{{bib_rel}}}
\end{{document}}
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or finalize a native Codex Introduction writing task"
    )
    parser.add_argument("--mode", required=True, choices=["prepare", "finalize"])
    parser.add_argument("--title", default="")
    parser.add_argument("--organized-info", default="", help="Structured JSON produced by extract-workspace-info.py --mode organize")
    parser.add_argument("--task-output", default="", help="Prepared writer task JSON")
    parser.add_argument("--draft-output", default="", help="Draft path assigned to intro-writer")
    parser.add_argument("--trace-output", default="", help="Trace path assigned to intro-writer")
    parser.add_argument("--draft-input", default="", help="Draft produced by intro-writer")
    parser.add_argument("--trace-input", default="", help="Trace produced by intro-writer")
    parser.add_argument("--tex-output", default="", help="Final output .tex path")
    parser.add_argument("--bib-output", default="", help="Final output .bib path")
    parser.add_argument("--style", default="default", choices=["ml", "math", "default"])
    parser.add_argument("--user-feedback", default="")
    parser.add_argument("--bib-input", default="", help="Existing .bib file to reuse")
    parser.add_argument("--no-generate-main", action="store_true")
    parser.add_argument("--citation-report", default="", help="Write citation validation details as JSON")
    parser.add_argument("--strict-citations", action="store_true", help="Fail when citations or provenance do not pass validation")
    args = parser.parse_args()

    try:
        organized_info = _load_organized_info(args.organized_info)
    except Exception as exc:
        print(f"ERROR: could not read --organized-info: {exc}", file=sys.stderr)
        return 1

    problem_background = str(organized_info.get("problem_background", ""))
    related_works = str(organized_info.get("related_works", ""))
    method_summary = str(organized_info.get("method_summary", ""))
    results_preview = str(organized_info.get("results_preview", ""))
    citation_claims_raw = organized_info.get("citation_claims", [])
    unverified_citation_claims = citation_claims_raw if isinstance(citation_claims_raw, list) else []

    if not problem_background or not related_works or not method_summary:
        print(
            "ERROR: problem background, related works, and method summary are required "
            "through --organized-info",
            file=sys.stderr,
        )
        return 1

    bib_content = ""
    if args.bib_input and Path(args.bib_input).exists():
        bib_content = Path(args.bib_input).read_text(encoding="utf-8")
    input_entries = _parse_bib_entries(bib_content)
    citation_claims, excluded_contract_keys = _verified_citation_claims(
        unverified_citation_claims,
        input_entries,
    )

    if args.mode == "prepare":
        if not args.title or not args.task_output or not args.draft_output or not args.trace_output:
            print(
                "ERROR: --title, --task-output, --draft-output, and --trace-output "
                "are required for prepare mode",
                file=sys.stderr,
            )
            return 1
        task = _build_writer_task(
            title=args.title,
            problem_background=problem_background,
            related_works=related_works,
            method_summary=method_summary,
            style=args.style,
            results_preview=results_preview,
            user_feedback=args.user_feedback,
            reference_catalog=_reference_catalog(input_entries),
            citation_claims=citation_claims,
            draft_output=args.draft_output,
            trace_output=args.trace_output,
            excluded_contract_keys=excluded_contract_keys,
        )
        task_path = Path(args.task_output)
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task_path.write_text(
            json.dumps(task, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "task_output": str(task_path),
                    "draft_output": args.draft_output,
                    "trace_output": args.trace_output,
                    "citation_contract_claims": len(citation_claims),
                    "unverified_contract_keys_excluded": excluded_contract_keys,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    required_finalize = {
        "--draft-input": args.draft_input,
        "--trace-input": args.trace_input,
        "--tex-output": args.tex_output,
        "--bib-output": args.bib_output,
    }
    missing_finalize = [name for name, value in required_finalize.items() if not value]
    if missing_finalize:
        print(
            "ERROR: required for finalize mode: " + ", ".join(missing_finalize),
            file=sys.stderr,
        )
        return 1
    try:
        tex_content = Path(args.draft_input).read_text(encoding="utf-8").strip()
        trace = _load_trace(args.trace_input)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not read native writer outputs: {exc}", file=sys.stderr)
        return 1

    validation_report = _validate_output(
        tex_content,
        input_entries,
        citation_claims,
        trace,
    )

    cited_keys = _ordered_cite_keys(tex_content)
    selected_entries: list[str] = []
    for key in cited_keys:
        entry = input_entries.get(key)
        if entry:
            selected_entries.append(entry.rstrip())
    bib_content_out = "\n\n".join(selected_entries)
    if bib_content_out:
        bib_content_out += "\n"

    tex_path = Path(args.tex_output)
    bib_path = Path(args.bib_output)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    bib_path.parent.mkdir(parents=True, exist_ok=True)

    tex_path.write_text(tex_content, encoding="utf-8")
    bib_path.write_text(bib_content_out, encoding="utf-8")

    citation_report_path = (
        Path(args.citation_report)
        if args.citation_report
        else tex_path.parent / "citation_report.json"
    )
    citation_report_path.parent.mkdir(parents=True, exist_ok=True)
    validation_report.update(
        {
            "tex_output": str(tex_path),
            "bib_output": str(bib_path),
            "citation_contract_claims": len(citation_claims),
            "unverified_contract_keys_excluded": excluded_contract_keys,
            "input_bib_entries": len(input_entries),
            "output_bib_entries": len(selected_entries),
            "strict": args.strict_citations,
            "executor": "codex_subagent",
            "draft_input": args.draft_input,
            "trace_input": args.trace_input,
        }
    )
    citation_report_path.write_text(
        json.dumps(validation_report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    output: dict[str, object] = {
        "tex_output": str(tex_path),
        "bib_output": str(bib_path),
        "citation_report": str(citation_report_path),
        "citation_validation_passed": validation_report["passed"],
    }

    if not args.no_generate_main:
        main_path = tex_path.parent / "main.tex"
        main_path.write_text(
            _make_main_tex(args.tex_output, args.bib_output), encoding="utf-8"
        )
        output["main_tex"] = str(main_path)

    print(json.dumps(output, indent=2))
    if args.strict_citations and not validation_report["passed"]:
        print(
            "ERROR: introduction failed strict citation validation; see citation report",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
