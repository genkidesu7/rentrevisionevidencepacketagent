"""AgentCore Platform v1.0"""

# Node contract (agents_layer_design.md §1):
#  - Extend FunctionNode; implement execute(state) -> dict
#  - Return ONLY the fields this node changes (never full state)
#  - Return AgentStatus.<X>.value — never bare Enum or plain string
#  - Read input_context via state.get("input_context", {}) — read-only [C1]
#  - Never import from mediator/, api/, or other agents

from __future__ import annotations

import json
import re
from typing import Any, ClassVar

from framework.errors import SecurityViolationError
from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

# Accepted case_id shape, e.g. "CASE-001". Adjust only alongside the tenant
# record store's actual case identifier format.
_CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_]{2,63}$")


def _parse_case_request(user_input: str) -> dict[str, str]:
    """Parse the {"case_id": ..., "jurisdiction": ...} request payload.

    Raises SecurityViolationError on invalid JSON — shared by the S-2 gate
    (validation) and execute() (extraction), so the request is parsed with
    identical rules in both places without stashing private keys on state.
    """
    try:
        payload = json.loads(user_input) if user_input else {}
    except (TypeError, json.JSONDecodeError) as exc:
        raise SecurityViolationError(f"RentEvidencePreProcessNode: input is not valid JSON: {exc}") from exc
    return {
        "case_id": payload.get("case_id", ""),
        "jurisdiction": payload.get("jurisdiction", ""),
    }


class RentEvidencePreProcessNode(FunctionNode):
    """S-1 gate: validates case_id + jurisdiction before evidence retrieval.

    Expects request input as JSON: {"case_id": "...", "jurisdiction": "..."}.
    """

    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def _extra_security_gate_input(self, state: dict[str, Any]) -> dict[str, Any]:
        """S-2 domain extension: reject requests without a valid case_id or
        outside the caseworker's assigned jurisdiction (engineer_proposal.md
        §4, InputValidate step)."""
        parsed = _parse_case_request(state.get("user_input", ""))
        case_id = parsed["case_id"]
        jurisdiction = parsed["jurisdiction"]

        if not case_id or not _CASE_ID_PATTERN.match(case_id):
            raise SecurityViolationError("RentEvidencePreProcessNode: missing or malformed case_id")
        if not jurisdiction:
            raise SecurityViolationError("RentEvidencePreProcessNode: missing jurisdiction")

        assigned_jurisdiction = (state.get("input_context") or {}).get("assigned_jurisdiction")
        if assigned_jurisdiction and jurisdiction != assigned_jurisdiction:
            raise SecurityViolationError("RentEvidencePreProcessNode: jurisdiction outside caseworker's assigned scope")
        return state  # required — framework crashes on None

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        parsed = _parse_case_request(state.get("user_input", ""))
        case_id = parsed["case_id"]
        jurisdiction = parsed["jurisdiction"]

        # validated_input carries the case identifier bundle across the
        # GraphNode -> inner-graph boundary as JSON (BaseGraph.invoke() only
        # forwards a single string as the inner graph's user_input).
        validated_input = json.dumps({"case_id": case_id, "jurisdiction": jurisdiction})

        emit_trace_event("case_validated", {"case_id": case_id, "jurisdiction": jurisdiction}, state)

        return {
            "validated_input": validated_input,
            "case_id": case_id,
            "jurisdiction": jurisdiction,
            "status": AgentStatus.SUCCESS.value,
        }
