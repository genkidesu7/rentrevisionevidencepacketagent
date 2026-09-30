"""AgentCore Platform v1.0"""

# Inner domain-workflow node (src/graph/domain_workflow_graph.py topology).
# Retrieves tenant income evidence, household-change records, and the
# applicable rent ordinance / checklist / review-calendar KB for a case.

from __future__ import annotations

import asyncio
import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.evidence_retrieval_service import (
    EvidenceRetrievalCaseNotFoundError,
    EvidenceRetrievalService,
)


class RetrieveNode(FunctionNode):
    """Retrieves tenant evidence + applicable rules for the case."""

    # S-1: reads tenant PII / internal records — requires a verified caller.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # Inner graph starts with fresh state — only "user_input" is forwarded
        # by BaseGraph.invoke(); "validated_input" is not copied in unless the
        # outer GraphNode.extract_input() returned it as user_input. Fall back
        # for both, per sdk-expertise / creat-node skill guidance.
        validated_input = state.get("validated_input", state.get("user_input", ""))
        try:
            payload = json.loads(validated_input) if validated_input else {}
        except (TypeError, json.JSONDecodeError):
            payload = {}

        case_id = payload.get("case_id", "")
        jurisdiction = payload.get("jurisdiction", "")

        if not case_id:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["RetrieveNode: case_id missing from inner input payload"],
            }

        service = EvidenceRetrievalService()
        try:
            result = asyncio.run(service.retrieve(case_id, jurisdiction))
        except EvidenceRetrievalCaseNotFoundError as exc:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": [f"RetrieveNode: {exc}"],
            }

        emit_trace_event(
            "evidence_retrieved",
            {
                "case_id": case_id,
                "document_count": len(result.get("raw_evidence", {}).get("documents", [])),
            },
            state,
        )

        return {
            "raw_evidence": result.get("raw_evidence", {}),
            "rule_reference": result.get("rule_reference", {}),
            "status": AgentStatus.SUCCESS.value,
        }
