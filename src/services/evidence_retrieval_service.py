"""AgentCore Platform v1.0"""

# Service layer: domain queries, external API wrappers, data aggregation.
# Must NOT contain business logic, routing, or credentials.
# Nodes call this; this calls shared/services/ for external integrations.

from __future__ import annotations

from typing import Any

from src.services.mock_mode import mock_mode_enabled


class EvidenceRetrievalCaseNotFoundError(Exception):
    """case_id is unknown, or outside the caller's configured jurisdiction scope."""


class EvidenceRetrievalService:
    """Retrieves tenant income evidence, household-change records, and the
    applicable rent ordinance income bands / evidence checklist /
    review-calendar rules for a given case, scoped to kb_path: ./kb/.

    Usage from a node::

        service = EvidenceRetrievalService()
        result = await service.retrieve(case_id, jurisdiction)
    """

    def __init__(self) -> None:
        self._mock_mode: bool = mock_mode_enabled()

    async def retrieve(self, case_id: str, jurisdiction: str) -> dict[str, Any]:
        """Retrieve raw_evidence and rule_reference for a case.

        Returns:
            dict with keys "raw_evidence" and "rule_reference".

        Raises:
            EvidenceRetrievalCaseNotFoundError: case_id missing, unknown, or
                outside the caseworker's assigned jurisdiction.
        """
        if not case_id:
            raise EvidenceRetrievalCaseNotFoundError("EvidenceRetrievalService.retrieve: case_id is required")
        return await self._call_external(case_id, jurisdiction)

    async def _call_external(self, case_id: str, jurisdiction: str) -> dict[str, Any]:
        if self._mock_mode:
            from src.services.mock_data import stub_retrieve_evidence

            return await stub_retrieve_evidence(case_id, jurisdiction)
        raise NotImplementedError(
            "EvidenceRetrievalService._call_external: not yet wired. "
            "Wire shared/services/<kb_client> and the tenant-record store client "
            "in the next sprint."
        )
