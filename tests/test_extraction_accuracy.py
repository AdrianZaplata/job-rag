"""Extraction accuracy tests — compare pre-stored extraction results against ground truth.

These tests validate that LLM extraction produces correct structured data
by comparing stored extraction outputs against manually verified ground truth.

Marked with @pytest.mark.eval so they can be run separately:
    pytest -m eval
"""

import json
from pathlib import Path

import pytest

EVAL_DIR = Path("data/eval")


def _load_json(filename: str) -> list[dict]:
    return json.loads((EVAL_DIR / filename).read_text(encoding="utf-8"))


def _build_cases() -> list[tuple[dict, dict]]:
    ground_truth = {g["source_file"]: g for g in _load_json("extraction_ground_truth.json")}
    results = {r["source_file"]: r for r in _load_json("extraction_results.json")}
    return [
        (ground_truth[key]["expected"], results[key]["extracted"])
        for key in ground_truth
        if key in results
    ]


CASES = _build_cases()
CASE_IDS = [c[0].get("company", "unknown") for c in CASES]


@pytest.mark.eval
class TestExtractionAccuracy:
    @pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
    def test_company_name(self, expected: dict, extracted: dict):
        assert extracted["company"] == expected["company"]

    @pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
    def test_remote_policy(self, expected: dict, extracted: dict):
        assert extracted["remote_policy"] == expected["remote_policy"]

    @pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
    def test_seniority(self, expected: dict, extracted: dict):
        assert extracted["seniority"] == expected["seniority"]

    @pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
    def test_salary_presence(self, expected: dict, extracted: dict):
        has_salary = extracted.get("salary_min") is not None
        assert has_salary == expected["has_salary"]

    @pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
    def test_salary_values(self, expected: dict, extracted: dict):
        if not expected["has_salary"]:
            pytest.skip("No salary expected for this posting")
        if "salary_min_eur_year" in expected:
            assert extracted["salary_min"] == expected["salary_min_eur_year"]
            assert extracted["salary_max"] == expected["salary_max_eur_year"]

    @pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
    def test_must_have_count_in_range(self, expected: dict, extracted: dict):
        must_have = [r for r in extracted["requirements"] if r["required"]]
        lo, hi = expected["must_have_count_min"], expected["must_have_count_max"]
        assert lo <= len(must_have) <= hi, (
            f"Expected {lo}-{hi} must-haves, got {len(must_have)}"
        )

    @pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
    def test_nice_to_have_count_in_range(self, expected: dict, extracted: dict):
        nice_to_have = [r for r in extracted["requirements"] if not r["required"]]
        lo, hi = expected["nice_to_have_count_min"], expected["nice_to_have_count_max"]
        assert lo <= len(nice_to_have) <= hi, (
            f"Expected {lo}-{hi} nice-to-haves, got {len(nice_to_have)}"
        )

    @pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
    def test_key_must_have_skills_present(self, expected: dict, extracted: dict):
        extracted_must_have = {
            r["skill"].lower() for r in extracted["requirements"] if r["required"]
        }
        for skill in expected.get("must_have_skills", []):
            assert any(
                skill.lower() in s for s in extracted_must_have
            ), f"Expected must-have skill '{skill}' not found in {extracted_must_have}"

    @pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
    def test_key_nice_to_have_skills_present(self, expected: dict, extracted: dict):
        if not expected.get("nice_to_have_skills"):
            pytest.skip("No specific nice-to-have skills to check")
        extracted_nice = {
            r["skill"].lower() for r in extracted["requirements"] if not r["required"]
        }
        for skill in expected["nice_to_have_skills"]:
            assert any(
                skill.lower() in s for s in extracted_nice
            ), f"Expected nice-to-have skill '{skill}' not found in {extracted_nice}"

    @pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
    def test_benefits_presence(self, expected: dict, extracted: dict):
        has_benefits = len(extracted.get("benefits", [])) > 0
        assert has_benefits == expected["has_benefits"]
