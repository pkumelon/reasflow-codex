from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extract = load_module(
    "test_extract_workspace_info",
    "skills/reasflow/intro/introduction-framing/scripts/extract-workspace-info.py",
)
writer = load_module(
    "test_write_introduction",
    "skills/reasflow/intro/introduction-framing/scripts/write-introduction.py",
)
hygiene = load_module(
    "test_citation_hygiene",
    "skills/reasflow/shared/citation-hygiene/scripts/check_citation_hygiene.py",
)
supplement = load_module(
    "test_supplement_intro_bib",
    "skills/reasflow/intro/introduction-framing/scripts/supplement-intro-bib.py",
)


class ExtractionTests(unittest.TestCase):
    def test_tex_inputs_are_expanded_and_citations_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir).resolve()
            child = workspace / "section.tex"
            child.write_text(
                "Prior methods are expensive \\citep{smith2024method}.\n",
                encoding="utf-8",
            )
            main = workspace / "main.tex"
            main.write_text("\\section{Background}\n\\input{section}\n", encoding="utf-8")

            content, error = extract._read_source("main.tex", workspace)

            self.assertIsNone(error)
            self.assertIn("Prior methods are expensive", content)
            self.assertIn("[CITE:smith2024method]", content)
            self.assertNotIn("\\input{section}", content)

    def test_long_content_is_split_without_truncation(self) -> None:
        content = "\n\n".join(f"paragraph-{index}-" + "x" * 80 for index in range(100))
        chunks = extract._split_content(content, 2000)

        self.assertGreater(len(chunks), 1)
        for index in range(100):
            self.assertIn(f"paragraph-{index}-", "\n".join(chunks))

    def test_prepare_task_contains_every_chunk_and_native_output_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            source = workspace / "survey.md"
            source.write_text("\n\n".join("claim " + "x" * 100 for _ in range(50)), encoding="utf-8")
            task_path = workspace / "task.json"
            args = argparse.Namespace(
                workspace=str(workspace),
                source="survey.md",
                source_type="survey",
                chunk_chars=2000,
                focus="",
                extracted_output="intro/survey_info.json",
                output=str(task_path),
            )
            with contextlib.redirect_stdout(io.StringIO()):
                status = extract.cmd_prepare(args)
            task = json.loads(task_path.read_text(encoding="utf-8"))

        self.assertEqual(status, 0)
        self.assertGreater(len(task["chunks"]), 1)
        self.assertFalse(task["source_metadata"]["truncated"])
        self.assertEqual(
            task["output_contract"]["extraction_metadata"]["executor"],
            "codex_subagent",
        )
        self.assertEqual(
            task["output_contract"]["extraction_metadata"]["processed_chunk_ids"],
            [chunk["chunk_id"] for chunk in task["chunks"]],
        )

    def test_validate_extraction_requires_all_prepared_chunks(self) -> None:
        task = {
            "source_type": "survey",
            "source_path": "survey.md",
            "source_metadata": {"source_chars": 20, "chunk_chars": 2000},
            "chunks": [{"chunk_id": 1}, {"chunk_id": 2}],
        }
        extraction = {
            "source_type": "survey",
            "source_path": "survey.md",
            "extracted": {},
            "extraction_metadata": {
                "source_chars": 20,
                "chunk_chars": 2000,
                "chunks_processed": 1,
                "processed_chunk_ids": [1],
                "truncated": False,
                "executor": "codex_subagent",
            },
        }

        errors = extract.validate_extraction(task, extraction)

        self.assertTrue(any("chunks_processed" in error for error in errors))
        self.assertTrue(any("processed_chunk_ids" in error for error in errors))

    def test_organize_retains_claim_to_bibtex_mapping(self) -> None:
        survey = {
            "source_type": "survey",
            "source_path": "survey/final_report/main.tex",
            "extracted": {
                "background": {
                    "research_field": "Optimization",
                    "importance": "Important",
                    "applications": ["learning"],
                    "claims": [
                        {
                            "claim": "Existing methods require two communication rounds.",
                            "bibtex_keys": ["smith2024method"],
                            "evidence": "The source states two rounds.",
                        }
                    ],
                },
                "related_works": {
                    "categories": [
                        {
                            "category_name": "Tracking",
                            "description": "Tracking methods use auxiliary variables.",
                            "bibtex_keys": ["smith2024method"],
                            "representative_works": [
                                {
                                    "method_name": "MethodX",
                                    "paper_title": "Method X",
                                    "bibtex_key": "smith2024method",
                                    "key_contribution": "MethodX tracks gradients.",
                                }
                            ],
                        }
                    ]
                },
                "gaps": [
                    {
                        "gap_description": "Existing methods need extra communication.",
                        "impact": "Higher cost",
                        "evidence": "Two exchanges per step.",
                        "bibtex_keys": ["smith2024method"],
                    }
                ],
                "citations": [
                    {
                        "bibtex_key": "smith2024method",
                        "paper_title": "Method X",
                        "authors": "Smith",
                    }
                ],
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            survey_path = temp / "survey.json"
            output_path = temp / "organized.json"
            survey_path.write_text(json.dumps(survey), encoding="utf-8")
            args = argparse.Namespace(inputs=[str(survey_path)], output=str(output_path))
            with contextlib.redirect_stdout(io.StringIO()):
                status = extract.cmd_organize(args)
            organized = json.loads(output_path.read_text(encoding="utf-8"))["organized_info"]

        self.assertEqual(status, 0)
        self.assertIn("bibtex_key: smith2024method", organized["related_works"])
        self.assertIn("[cite: smith2024method]", organized["related_works"])
        self.assertTrue(organized["citation_claims"])
        self.assertTrue(
            all(
                claim["bibtex_keys"] == ["smith2024method"]
                for claim in organized["citation_claims"]
            )
        )


class WriterValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entry = """@article{smith2024method,
  title={Method X},
  author={Smith, A.},
  year={2024}
}"""
        self.claims = [
            {
                "claim_id": "claim-0001",
                "text": "Existing methods require two communication rounds.",
                "citation_required": True,
                "bibtex_keys": ["smith2024method"],
            }
        ]

    def test_uncited_literature_sentence_fails_validation(self) -> None:
        tex = (
            "\\section{Introduction}\n\n"
            "Existing methods often require two communication rounds, which increases cost."
        )
        report = writer._validate_output(
            tex,
            {"smith2024method": self.entry},
            self.claims,
            {"claims": []},
        )

        self.assertFalse(report["passed"])
        self.assertEqual(len(report["uncited_literature_sentences"]), 1)

    def test_inline_citation_and_valid_trace_pass(self) -> None:
        tex = (
            "\\section{Introduction}\n\n"
            "Existing methods often require two communication rounds, which increases cost "
            "\\citep{smith2024method}."
        )
        report = writer._validate_output(
            tex,
            {"smith2024method": self.entry},
            self.claims,
            {
                "claims": [
                    {
                        "claim_id": "claim-0001",
                        "bibtex_keys": ["smith2024method"],
                    }
                ]
            },
        )

        self.assertTrue(report["passed"], report)

    def test_cited_key_without_trace_provenance_fails(self) -> None:
        tex = "Existing methods often require two rounds \\citep{smith2024method}."

        report = writer._validate_output(
            tex,
            {"smith2024method": self.entry},
            self.claims,
            {"claims": []},
        )

        self.assertFalse(report["passed"])
        self.assertTrue(any("TRACE" in error for error in report["trace_errors"]))

    def test_bibliography_entries_are_parsed_and_cataloged(self) -> None:
        entries = writer._parse_bib_entries(self.entry)

        self.assertEqual(set(entries), {"smith2024method"})
        self.assertIn("smith2024method: Method X", writer._reference_catalog(entries))

    def test_claim_contract_excludes_keys_missing_from_input_bibliography(self) -> None:
        claims = self.claims + [
            {
                "claim_id": "claim-0002",
                "text": "An unavailable source makes another claim.",
                "citation_required": True,
                "bibtex_keys": ["missing2025source"],
            }
        ]

        verified, excluded = writer._verified_citation_claims(
            claims,
            {"smith2024method": self.entry},
        )

        self.assertEqual([claim["claim_id"] for claim in verified], ["claim-0001"])
        self.assertEqual(excluded, ["missing2025source"])

    def test_native_writer_task_contains_outputs_and_no_api_configuration(self) -> None:
        task = writer._build_writer_task(
            title="Title",
            problem_background="Background",
            related_works="Related work",
            method_summary="Method",
            style="math",
            results_preview="Result",
            user_feedback="",
            reference_catalog="- smith2024method: Method X",
            citation_claims=self.claims,
            draft_output="intro/introduction.draft.tex",
            trace_output="intro/citation_trace.json",
            excluded_contract_keys=[],
        )

        self.assertEqual(task["executor"], "codex_subagent")
        self.assertEqual(task["outputs"]["draft_tex"], "intro/introduction.draft.tex")
        self.assertNotIn("model", task)
        self.assertNotIn("api_key", task)


class SupplementTests(unittest.TestCase):
    def test_explicit_identifiers_are_normalized_as_lookup_candidates(self) -> None:
        candidates = supplement.normalize_candidates(
            [],
            ["1602.05629", "10.1000/example", "A Paper Title"],
        )

        self.assertEqual(candidates[0]["arxiv_id"], "arXiv:1602.05629")
        self.assertEqual(candidates[0]["paper_title"], "")
        self.assertEqual(candidates[1]["doi"], "DOI:10.1000/example")
        self.assertEqual(candidates[2]["paper_title"], "A Paper Title")

    def test_existing_bibliography_entries_expose_raw_bibtex_for_deduplication(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "references.bib"
            path.write_text(
                "@article{duplicate, title={First}}\n\n"
                "@article{duplicate, title={Second}}\n",
                encoding="utf-8",
            )

            entries = supplement.tools.parse_bib_entries(path)
            _, duplicates = supplement.tools.parse_bib_keys(path)

        self.assertEqual(list(entries), ["duplicate"])
        self.assertIn("title={Second}", entries["duplicate"]["raw_bibtex"])
        self.assertEqual(duplicates, ["duplicate"])

    def test_required_claim_keys_are_reported_independently_of_candidates(self) -> None:
        payload = {
            "organized_info": {
                "citation_claims": [
                    {"claim_id": "claim-1", "bibtex_keys": ["keyA", "keyB"]},
                    {"claim_id": "claim-2", "bibtex_keys": "keyB,keyC"},
                ]
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "organized.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            keys = supplement.required_claim_keys([path])

        self.assertEqual(keys, {"keyA", "keyB", "keyC"})

    def test_required_claim_contexts_preserve_support_for_each_key(self) -> None:
        payload = {
            "organized_info": {
                "citation_claims": [
                    {"text": "Consensus contracts disagreement.", "bibtex_keys": ["keyA"]},
                    {"text": "Gossip uses local communication.", "bibtex_keys": ["keyA", "keyB"]},
                ]
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "organized.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            contexts = supplement.required_claim_contexts([path])

        self.assertEqual(len(contexts["keyA"]), 2)
        self.assertEqual(contexts["keyB"], ["Gossip uses local communication."])

    def test_semantic_scholar_key_accepts_canonical_and_alias_names(self) -> None:
        with mock.patch.dict(
            supplement.literature.os.environ,
            {"SEMANTIC_SCHOLAR_API_KEY": "canonical", "S2_API_KEY": "alias"},
            clear=True,
        ):
            self.assertEqual(supplement.literature.semantic_scholar_api_key(), "canonical")
        with mock.patch.dict(
            supplement.literature.os.environ,
            {"S2_API_KEY": "alias"},
            clear=True,
        ):
            self.assertEqual(supplement.literature.semantic_scholar_api_key(), "alias")

    def test_bibtex_key_fallback_query_and_match_require_key_hints(self) -> None:
        self.assertEqual(
            supplement._bibtex_key_query("Nedic2016AchievingGC"),
            "Nedic 2016 Achieving GC",
        )
        matching = {
            "year": 2016,
            "authors": ["Angelia Nedic"],
            "title": "Achieving Geometric Convergence for Distributed Optimization",
            "abstract": "We study gradient tracking over time-varying graphs.",
        }
        wrong_year = {**matching, "year": 2017}
        wrong_author = {**matching, "authors": ["Other Author"]}
        wrong_title = {**matching, "title": "A Different Paper"}

        context = "Gradient tracking achieves convergence for distributed optimization."
        self.assertTrue(supplement._key_match_is_strong("Nedic2016AchievingGC", matching, context))
        self.assertFalse(supplement._key_match_is_strong("Nedic2016AchievingGC", wrong_year, context))
        self.assertFalse(supplement._key_match_is_strong("Nedic2016AchievingGC", wrong_author, context))
        self.assertFalse(supplement._key_match_is_strong("Nedic2016AchievingGC", wrong_title, context))

    def test_bibtex_key_fallback_rejects_related_but_different_title(self) -> None:
        wrong_paper = {
            "year": 2010,
            "authors": ["Ruggero Carli"],
            "title": "Discrete Partitioning and Coverage Control for Gossiping Robots",
        }
        expected_paper = {
            "year": 2010,
            "authors": ["Ruggero Carli"],
            "title": "Gossip Consensus Algorithms via Quantized Communication",
        }
        context = "Local gossip communication establishes consensus between network nodes."

        self.assertFalse(supplement._key_match_is_strong("carli2010gossip", wrong_paper, context))
        self.assertTrue(supplement._key_match_is_strong("carli2010gossip", expected_paper, context))

    def test_context_rejects_same_author_year_and_generic_title_hint(self) -> None:
        wrong_paper = {
            "year": 2004,
            "authors": ["I. L. Boyd"],
            "title": "Energetics of the moult fast in female macaroni penguins",
            "abstract": "This study measures energy expenditure during a penguin moult.",
        }
        context = "Spectral polynomial filtering accelerates distributed consensus averaging."

        self.assertFalse(supplement._key_match_is_strong("boyd2004fast", wrong_paper, context))

class HygieneTests(unittest.TestCase):
    def test_sentence_level_check_does_not_let_one_citation_cover_a_paragraph(self) -> None:
        tex = (
            "\\section{Introduction}\n\n"
            "Prior methods reduce bandwidth \\citep{smith2024method}. "
            "Existing approaches often retain full-dimensional memory buffers.\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "intro.tex"
            path.write_text(tex, encoding="utf-8")
            findings = hygiene.detect_unsupported_claims([path])

        self.assertEqual(len(findings), 1)
        self.assertIn("retain full-dimensional memory buffers", findings[0]["text"])

    def test_verify_comments_are_unresolved_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "intro.tex"
            path.write_text("% [VERIFY: missing support]\nText.\n", encoding="utf-8")
            findings = hygiene.detect_unresolved_markers([path])

        self.assertEqual(len(findings), 1)
        self.assertIn("VERIFY", findings[0]["marker"])

    def test_paper_organization_sentence_is_not_a_literature_claim(self) -> None:
        tex = (
            "The remainder of the paper derives the algorithms, establishes the results, "
            "and reports the experiments."
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "intro.tex"
            path.write_text(tex, encoding="utf-8")
            findings = hygiene.detect_unsupported_claims([path])

        self.assertEqual(findings, [])

    def test_first_order_term_is_not_treated_as_a_novelty_claim(self) -> None:
        tex = "The construction includes the first-order optimality condition and closed form."
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "intro.tex"
            path.write_text(tex, encoding="utf-8")
            findings = hygiene.detect_unsupported_claims([path])

        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
