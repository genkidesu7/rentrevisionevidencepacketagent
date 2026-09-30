# Unit tests for src/services/*.py — Task 2-4 acceptance criteria
# (docs/implement_tasks.md).

import pytest

from src.services.evidence_check_service import EvidenceCheckService
from src.services.evidence_retrieval_service import (
    EvidenceRetrievalCaseNotFoundError,
    EvidenceRetrievalService,
)
from src.services.normalization_service import NormalizationService
from src.services.packet_service import PacketService

_RULE_REFERENCE = {
    "version": "2026-mock-1",
    "income_bands": [{"household_size": 2, "max_income": 320000}],
    "checklist_items": [
        {"id": "income_statement", "field": "income_by_source", "citation": "ordinance §4-1"},
        {"id": "spousal_income_statement", "field": "spousal_income", "citation": "ordinance §4-2"},
    ],
}


class TestEvidenceRetrievalService:
    @pytest.mark.asyncio
    async def test_retrieve_found_case_mock_mode(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        service = EvidenceRetrievalService()
        result = await service.retrieve("CASE-001", "muni-tokyo-01")
        assert "raw_evidence" in result
        assert "rule_reference" in result

    @pytest.mark.asyncio
    async def test_retrieve_missing_case_id_raises(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        service = EvidenceRetrievalService()
        with pytest.raises(EvidenceRetrievalCaseNotFoundError):
            await service.retrieve("", "muni-tokyo-01")

    @pytest.mark.asyncio
    async def test_retrieve_out_of_scope_not_wired_without_mock(self, monkeypatch):
        """Without mock mode, the real KB client is not yet wired (NotImplementedError)."""
        monkeypatch.delenv("USE_MOCK", raising=False)
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        service = EvidenceRetrievalService()
        with pytest.raises(NotImplementedError):
            await service.retrieve("CASE-001", "muni-tokyo-01")


class TestNormalizationService:
    @pytest.mark.asyncio
    async def test_normalize_mock_mode_no_credential_required(self, monkeypatch):
        """Mock mode must not require a real credential_handle."""
        monkeypatch.setenv("USE_MOCK", "true")
        service = NormalizationService()
        result = await service.normalize({"documents": [{"type": "payslip", "amount": 1}]}, "")
        assert "income_by_source" in result
        assert "low_confidence_fields" in result

    @pytest.mark.asyncio
    async def test_normalize_requires_credential_outside_mock_mode(self, monkeypatch):
        monkeypatch.delenv("USE_MOCK", raising=False)
        monkeypatch.delenv("STG_MOCK_MODE", raising=False)
        service = NormalizationService()
        with pytest.raises(ValueError):
            await service.normalize({"documents": []}, "")

    @pytest.mark.asyncio
    async def test_normalize_mixed_format_inputs(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        service = NormalizationService()
        for raw in (
            {"documents": []},
            {"documents": [{"type": "pension_notice"}]},
            {"documents": [{"type": "payslip", "amount": 100}, {"type": "dependent_change_form"}]},
        ):
            result = await service.normalize(raw, "")
            assert isinstance(result, dict)


class TestEvidenceCheckService:
    def test_all_evidence_present(self):
        service = EvidenceCheckService()
        normalized = {"income_by_source": {"a": 1}, "spousal_income": {"b": 1}, "household_size": 2}
        result = service.check(normalized, _RULE_REFERENCE)
        assert result["checklist_status"] == {
            "income_statement": "confirmed",
            "spousal_income_statement": "confirmed",
        }
        assert result["gap_findings"] == []

    def test_missing_evidence_flagged_with_citation(self):
        service = EvidenceCheckService()
        normalized = {"income_by_source": {"a": 1}, "household_size": 2}
        result = service.check(normalized, _RULE_REFERENCE)
        assert result["checklist_status"]["spousal_income_statement"] == "missing"
        gap = next(g for g in result["gap_findings"] if g["checklist_item"] == "spousal_income_statement")
        assert gap["rule_reference"] == "ordinance §4-2"

    def test_contradictory_household_size_flagged(self):
        service = EvidenceCheckService()
        normalized = {"income_by_source": {"a": 1}, "spousal_income": {"b": 1}, "household_size": 99}
        result = service.check(normalized, _RULE_REFERENCE)
        contradictions = [g for g in result["gap_findings"] if g["type"] == "contradiction"]
        assert len(contradictions) == 1


class TestPacketService:
    def test_assemble_includes_disclaimer_and_citations(self):
        service = PacketService()
        checklist_status = {"income_statement": "confirmed", "spousal_income_statement": "missing"}
        gap_findings = [
            {
                "type": "missing_evidence",
                "checklist_item": "spousal_income_statement",
                "rule_reference": "ordinance §4-2",
                "detail": "missing",
            }
        ]
        packet = service.assemble({}, checklist_status, gap_findings, _RULE_REFERENCE)
        assert packet["disclaimer"]
        assert packet["gaps"] == gap_findings
        assert packet["contradictions"] == []
        assert packet["rule_version"] == "2026-mock-1"
        assert all(g.get("rule_reference") for g in packet["gaps"])
