"""AgentCore Platform v1.0"""

# Service layer: pure domain logic. No LLM call, no external network call,
# no credentials — rule-matching only.

from __future__ import annotations

from typing import Any


class EvidenceCheckService:
    """Pure rule-matching: compares normalized fields against ordinance
    income bands and checklist items; flags missing or conflicting evidence.

    Usage from a node::

        service = EvidenceCheckService()
        result = service.check(normalized_fields, rule_reference)
    """

    def check(self, normalized_fields: dict[str, Any], rule_reference: dict[str, Any]) -> dict[str, Any]:
        """Match normalized_fields against rule_reference.

        Returns:
            dict with keys "checklist_status" (dict[item_id, "confirmed"|"missing"])
            and "gap_findings" (list of dicts, each citing a rule/checklist item).
        """
        checklist_items = rule_reference.get("checklist_items", [])
        income_bands = rule_reference.get("income_bands", [])
        household_size = normalized_fields.get("household_size")

        checklist_status: dict[str, str] = {}
        gap_findings: list[dict[str, Any]] = []

        for item in checklist_items:
            item_id = item.get("id", "")
            required_field = item.get("field")
            if required_field and normalized_fields.get(required_field) in (None, "", {}):
                checklist_status[item_id] = "missing"
                gap_findings.append(
                    {
                        "type": "missing_evidence",
                        "checklist_item": item_id,
                        "rule_reference": item.get("citation", item_id),
                        "detail": f"Required field '{required_field}' not present in submitted evidence.",
                    }
                )
            else:
                checklist_status[item_id] = "confirmed"

        band_match = any(band.get("household_size") == household_size for band in income_bands)
        if income_bands and not band_match:
            gap_findings.append(
                {
                    "type": "contradiction",
                    "checklist_item": "income_band_match",
                    "rule_reference": "rent_ordinance.income_bands",
                    "detail": f"No configured income band matches household_size={household_size!r}.",
                }
            )

        return {"checklist_status": checklist_status, "gap_findings": gap_findings}
