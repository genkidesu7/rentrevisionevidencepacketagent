"""AgentCore Platform v1.0"""

# Mock-mode stub data. Used only when mock_mode_enabled() is True (see
# src/services/mock_mode.py). Keeps deterministic fixtures out of the
# services themselves.

from __future__ import annotations

from typing import Any


async def stub_retrieve_evidence(case_id: str, jurisdiction: str) -> dict[str, Any]:
    """Deterministic fixture standing in for tenant record store + ordinance/checklist KB."""
    return {
        "raw_evidence": {
            "case_id": case_id,
            "jurisdiction": jurisdiction,
            "documents": [
                {"type": "payslip", "source": "employer_a", "amount": 210000},
                {"type": "household_change_form", "filed_on": "2026-04-01", "change": "spouse_added"},
            ],
        },
        "rule_reference": {
            "version": "2026-mock-1",
            "income_bands": [
                {"household_size": 1, "max_income": 250000},
                {"household_size": 2, "max_income": 320000},
            ],
            "checklist_items": [
                {"id": "income_statement", "field": "income_by_source", "citation": "ordinance §4-1"},
                {"id": "spousal_income_statement", "field": "spousal_income", "citation": "ordinance §4-2"},
            ],
        },
    }


async def stub_normalize(raw_evidence: dict[str, Any]) -> dict[str, Any]:
    """Deterministic fixture standing in for LLM-assisted document extraction."""
    documents = raw_evidence.get("documents", [])
    payslip: dict[str, Any] = next((d for d in documents if d.get("type") == "payslip"), {})
    return {
        "income_by_source": {"employer_a": payslip.get("amount", 0)},
        "household_size": 2,
        "dependent_status": {"spouse_added": True},
        "low_confidence_fields": [],
    }
