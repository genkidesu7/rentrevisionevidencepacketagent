"""AgentCore Platform v1.0"""

# Service layer: pure domain logic. No LLM call, no external network call,
# no credentials — packet composition only.

from __future__ import annotations

from typing import Any

# Verbatim disclaimer per engineer_proposal.md §10 (Security & compliance).
PACKET_DISCLAIMER = (
    "This packet identifies evidence gaps only. All rent determinations, "
    "approvals, and notices require authorized staff review and action."
)


class PacketService:
    """Composes the reviewer packet: confirmed evidence, gap list,
    contradiction list, checklist status per item — each linked to its
    source record and applicable rule/checklist item.

    Usage from a node::

        service = PacketService()
        draft_packet = service.assemble(normalized_fields, checklist_status, gap_findings, rule_reference)
    """

    def assemble(
        self,
        normalized_fields: dict[str, Any],  # noqa: ARG002
        checklist_status: dict[str, Any],
        gap_findings: list[dict[str, Any]],
        rule_reference: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble the draft review packet.

        Returns:
            dict with confirmed_evidence, gaps, contradictions, checklist_status,
            rule_version, and disclaimer.
        """
        confirmed_evidence = [
            {"checklist_item": item_id, "status": status, "rule_reference": item_id}
            for item_id, status in checklist_status.items()
            if status == "confirmed"
        ]
        return {
            "confirmed_evidence": confirmed_evidence,
            "gaps": [g for g in gap_findings if g.get("type") == "missing_evidence"],
            "contradictions": [g for g in gap_findings if g.get("type") == "contradiction"],
            "checklist_status": checklist_status,
            "rule_version": rule_reference.get("version", "unknown"),
            "disclaimer": PACKET_DISCLAIMER,
        }
