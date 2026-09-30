"""AgentCore Platform v1.0"""

# Node contract (agents_layer_design.md §1):
#  - Extend FunctionNode; implement execute(state) -> dict
#  - Return ONLY the fields this node changes (never full state)
#  - Return AgentStatus.<X>.value — never bare Enum or plain string
#  - Never import from mediator/, api/, or other agents

from __future__ import annotations

import re
from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

# Blocks any rent figure, approval status, or notice language from leaving the
# packet (engineer_proposal.md §4, OutputValidate step — mandatory S-3 gate).
_BLOCKED_PATTERNS = (
    re.compile(r"\brent\s+(?:is|of|amount|due)\b", re.IGNORECASE),
    re.compile(r"\b(approved|denied|rejected)\b", re.IGNORECASE),
    re.compile(r"\bnotice\s+(?:of|is|issued)\b", re.IGNORECASE),
    re.compile(r"[¥$]\s?\d", re.IGNORECASE),
)


class RentEvidencePostProcessNode(FunctionNode):
    """S-3 gate (mandatory): blocks rent/approval/notice language and
    verifies every finding cites a source record and rule/checklist item."""

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        draft_packet = state.get("draft_packet") or {}
        if not draft_packet:
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["RentEvidencePostProcessNode: draft_packet missing — main step must run first"],
            }

        emit_trace_event(
            "packet_gate_cleared",
            {
                "gap_count": len(draft_packet.get("gaps", [])),
                "contradiction_count": len(draft_packet.get("contradictions", [])),
            },
            state,
        )

        return {
            "formatted_output": draft_packet,
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, result: dict[str, Any]) -> dict[str, Any]:
        """S-3 domain extension (mandatory, not optional for this template):
        - Content filtering: block any rent figure, approval status, or notice language.
        - Preservation verification: every gap/contradiction entry must cite a
          source record / rule reference — reject output that silently drops it.
        """
        packet = result.get("formatted_output")
        if not isinstance(packet, dict):
            return result

        for section in ("gaps", "contradictions"):
            for entry in packet.get(section, []):
                text_blob = " ".join(str(v) for v in entry.values())
                for pattern in _BLOCKED_PATTERNS:
                    if pattern.search(text_blob):
                        raise SecurityViolationError(
                            f"RentEvidencePostProcessNode: S-3 blocked rent/approval/notice "
                            f"language in packet {section} entry: {pattern.pattern!r}"
                        )
                if not entry.get("rule_reference"):
                    raise SecurityViolationError(
                        f"RentEvidencePostProcessNode: S-3 preservation check failed — "
                        f"{section} entry missing required rule_reference citation"
                    )

        return result  # required — framework returns this directly
