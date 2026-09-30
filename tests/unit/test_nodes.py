# Unit tests for src/nodes/*.py — Task 5-7 acceptance criteria
# (docs/implement_tasks.md) + TC-08 (required_trust_level enforcement).
#
# All nodes are called via __call__ (not bare execute()) so the S-1 trust
# gate is actually exercised, per sdk-expertise / write-tests.md guidance.

import json


from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel

from src.nodes.evidence_check_node import EvidenceCheckNode
from src.nodes.normalize_node import NormalizeNode
from src.nodes.packet_assemble_node import PacketAssembleNode
from src.nodes.post_process_node import RentEvidencePostProcessNode
from src.nodes.pre_process_node import RentEvidencePreProcessNode
from src.nodes.retrieve_node import RetrieveNode

_CASE_PAYLOAD = json.dumps({"case_id": "CASE-001", "jurisdiction": "muni-tokyo-01"})


def _base_state(**overrides) -> dict:
    state = {
        "caller_trust_level": TrustLevel.VERIFIED_EXTERNAL.value,
        "correlation_id": "test-correlation",
        "session_id": "test-session",
        "thread_id": "test-thread",
        "trace_id": "test-trace",
    }
    state.update(overrides)
    return state


class TestRentEvidencePreProcessNode:
    def test_valid_case_request_succeeds(self):
        node = RentEvidencePreProcessNode()
        result = node(_base_state(user_input=_CASE_PAYLOAD))
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["case_id"] == "CASE-001"
        assert result["jurisdiction"] == "muni-tokyo-01"
        assert json.loads(result["validated_input"]) == {
            "case_id": "CASE-001",
            "jurisdiction": "muni-tokyo-01",
        }

    def test_missing_case_id_rejected(self):
        node = RentEvidencePreProcessNode()
        result = node(_base_state(user_input=json.dumps({"jurisdiction": "muni-tokyo-01"})))
        assert result["status"] == AgentStatus.ERROR.value

    def test_malformed_json_rejected(self):
        node = RentEvidencePreProcessNode()
        result = node(_base_state(user_input="not-json"))
        assert result["status"] == AgentStatus.ERROR.value

    def test_jurisdiction_outside_assigned_scope_rejected(self):
        node = RentEvidencePreProcessNode()
        result = node(
            _base_state(
                user_input=_CASE_PAYLOAD,
                input_context={"assigned_jurisdiction": "muni-osaka-02"},
            )
        )
        assert result["status"] == AgentStatus.ERROR.value

    def test_s1_trust_gate_denies_anonymous_caller(self):
        """TC-08: required_trust_level enforced via __call__(), not execute()."""
        node = RentEvidencePreProcessNode()
        result = node(_base_state(caller_trust_level=TrustLevel.ANONYMOUS.value, user_input=_CASE_PAYLOAD))
        assert result["status"] == AgentStatus.ERROR.value
        assert "S-1" in result["error_log"][0]


class TestRetrieveNode:
    def test_retrieve_succeeds_in_mock_mode(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        node = RetrieveNode()
        result = node(_base_state(validated_input=_CASE_PAYLOAD))
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["raw_evidence"]
        assert result["rule_reference"]

    def test_retrieve_missing_case_id_errors(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        node = RetrieveNode()
        result = node(_base_state(validated_input=json.dumps({"jurisdiction": "muni-tokyo-01"})))
        assert result["status"] == AgentStatus.ERROR.value


class TestNormalizeNode:
    def test_normalize_succeeds_with_no_secret_in_mock_mode(self, monkeypatch):
        """Regression test (.claude/rules/test_rule.md Rule 2): mock mode must
        not depend on a secret being resolvable — no bound_secrets() context
        at all, simulating a fresh checkout with no env/ secret tree."""
        monkeypatch.setenv("USE_MOCK", "true")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        node = NormalizeNode()
        result = node(_base_state(raw_evidence={"documents": [{"type": "payslip", "amount": 1}]}))
        assert result["status"] == AgentStatus.SUCCESS.value
        assert "normalized_fields" in result

    def test_normalize_missing_raw_evidence_errors(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK", "true")
        node = NormalizeNode()
        result = node(_base_state(raw_evidence={}))
        assert result["status"] == AgentStatus.ERROR.value


class TestEvidenceCheckNode:
    def test_check_succeeds(self):
        node = EvidenceCheckNode()
        result = node(
            _base_state(
                normalized_fields={"income_by_source": {"a": 1}, "household_size": 2},
                rule_reference={"income_bands": [], "checklist_items": []},
            )
        )
        assert result["status"] == AgentStatus.SUCCESS.value
        assert "checklist_status" in result
        assert "gap_findings" in result

    def test_check_missing_normalized_fields_errors(self):
        node = EvidenceCheckNode()
        result = node(_base_state(normalized_fields={}, rule_reference={}))
        assert result["status"] == AgentStatus.ERROR.value


class TestPacketAssembleNode:
    def test_assemble_succeeds(self):
        node = PacketAssembleNode()
        result = node(
            _base_state(
                normalized_fields={},
                checklist_status={"income_statement": "confirmed"},
                gap_findings=[],
                rule_reference={"version": "test"},
            )
        )
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["draft_packet"]["disclaimer"]


class TestRentEvidencePostProcessNode:
    def test_valid_packet_passes_s3_gate(self):
        node = RentEvidencePostProcessNode()
        packet = {
            "confirmed_evidence": [],
            "gaps": [
                {
                    "type": "missing_evidence",
                    "checklist_item": "spousal_income_statement",
                    "rule_reference": "ordinance §4-2",
                    "detail": "Required field 'spousal_income' not present.",
                }
            ],
            "contradictions": [],
            "checklist_status": {},
            "rule_version": "test",
            "disclaimer": "test",
        }
        result = node(_base_state(draft_packet=packet))
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["formatted_output"] == packet

    def test_rent_figure_language_blocked(self):
        node = RentEvidencePostProcessNode()
        packet = {
            "confirmed_evidence": [],
            "gaps": [
                {
                    "type": "missing_evidence",
                    "checklist_item": "x",
                    "rule_reference": "ordinance §4-2",
                    "detail": "rent is 250000",
                }
            ],
            "contradictions": [],
            "checklist_status": {},
            "rule_version": "test",
            "disclaimer": "test",
        }
        result = node(_base_state(draft_packet=packet))
        assert result["status"] == AgentStatus.ERROR.value

    def test_missing_citation_blocked(self):
        """S-3 preservation variant: a gap entry with no rule_reference must be rejected."""
        node = RentEvidencePostProcessNode()
        packet = {
            "confirmed_evidence": [],
            "gaps": [{"type": "missing_evidence", "checklist_item": "x", "rule_reference": "", "detail": "missing"}],
            "contradictions": [],
            "checklist_status": {},
            "rule_version": "test",
            "disclaimer": "test",
        }
        result = node(_base_state(draft_packet=packet))
        assert result["status"] == AgentStatus.ERROR.value

    def test_missing_draft_packet_errors(self):
        node = RentEvidencePostProcessNode()
        result = node(_base_state(draft_packet={}))
        assert result["status"] == AgentStatus.ERROR.value
