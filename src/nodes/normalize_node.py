"""AgentCore Platform v1.0"""

# Inner domain-workflow node (src/graph/domain_workflow_graph.py topology).
# LLM-assisted extraction of submitted documents into structured fields.

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.mock_mode import mock_mode_enabled
from src.services.normalization_service import NormalizationService


class NormalizeNode(FunctionNode):
    """Extracts structured fields from raw_evidence via NormalizationService."""

    # S-1: reads tenant PII and calls the shared LLM client — verified caller only.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw_evidence = state.get("raw_evidence") or {}
        if not raw_evidence:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["NormalizeNode: raw_evidence missing — Retrieve must run first"],
            }

        # Mock mode must short-circuit before any credential is required
        # (.claude/rules/implementation_rule.md Rule 2) — the mock stub path
        # never touches credential_handle.
        if mock_mode_enabled():
            credential_handle = "mock"
        else:
            ctx = InvocationContext.from_state(state)
            credential_handle = ctx.secrets.require("ANTHROPIC_API_KEY")

        service = NormalizationService()
        normalized_fields = asyncio.run(service.normalize(raw_evidence, credential_handle))

        emit_trace_event(
            "fields_normalized",
            {"low_confidence_count": len(normalized_fields.get("low_confidence_fields", []))},
            state,
        )

        return {
            "normalized_fields": normalized_fields,
            "status": AgentStatus.SUCCESS.value,
        }
