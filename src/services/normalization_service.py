"""AgentCore Platform v1.0"""

# Service layer: domain queries, external API wrappers, data aggregation.
# Must NOT contain business logic, routing, or credentials.
# Nodes call this; this calls shared/services/ for external integrations.

from __future__ import annotations

from typing import Any

from src.services.mock_mode import mock_mode_enabled


class NormalizationService:
    """LLM-assisted extraction of submitted documents (payslips, pension
    notices, dependent-change forms) into structured fields: income by
    source, household size, dependent status. Low-confidence extractions are
    surfaced explicitly, never silently dropped.

    Usage from a node::

        service = NormalizationService()
        normalized_fields = await service.normalize(raw_evidence, credential_handle)
    """

    def __init__(self) -> None:
        self._mock_mode: bool = mock_mode_enabled()

    async def normalize(self, raw_evidence: dict[str, Any], credential_handle: str) -> dict[str, Any]:
        """Extract structured fields from raw_evidence.

        Args:
            raw_evidence: Retrieved tenant documents, from EvidenceRetrievalService.
            credential_handle: Opaque handle from InvocationContext.secrets.require().
                Never log or store this value. Not required in mock mode.
        """
        if not self._mock_mode and not credential_handle:
            raise ValueError(
                "NormalizationService.normalize: credential_handle is empty — " "check InvocationContext configuration"
            )
        return await self._call_llm(raw_evidence, credential_handle)

    async def _call_llm(
        self,
        raw_evidence: dict[str, Any],
        credential_handle: str,  # noqa: ARG002
    ) -> dict[str, Any]:
        if self._mock_mode:
            from src.services.mock_data import stub_normalize

            return await stub_normalize(raw_evidence)
        raise NotImplementedError(
            "NormalizationService._call_llm: not yet wired. " "Wire shared/services/<llm_client> in the next sprint."
        )
