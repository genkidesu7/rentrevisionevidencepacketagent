"""AgentCore Platform v1.0"""

# Inner domain-workflow node (src/graph/domain_workflow_graph.py topology).
# Composes the reviewer packet from normalized fields, checklist status,
# gap findings, and the applicable rule reference.

from __future__ import annotations

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.packet_service import PacketService


class PacketAssembleNode(FunctionNode):
    """Composes the draft reviewer packet."""

    # S-1: composes a packet containing tenant-derived evidence — verified caller.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        normalized_fields = state.get("normalized_fields") or {}
        checklist_status = state.get("checklist_status") or {}
        gap_findings = state.get("gap_findings") or []
        rule_reference = state.get("rule_reference") or {}

        service = PacketService()
        draft_packet = service.assemble(normalized_fields, checklist_status, gap_findings, rule_reference)

        emit_trace_event(
            "packet_assembled",
            {
                "gap_count": len(draft_packet.get("gaps", [])),
                "contradiction_count": len(draft_packet.get("contradictions", [])),
            },
            state,
        )

        return {
            "draft_packet": draft_packet,
            "status": AgentStatus.SUCCESS.value,
        }
