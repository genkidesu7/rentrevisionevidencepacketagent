# Test Specification

## Test Strategy
- Coverage target: 80%
- Test types: Unit / Integration
- Test locations:
  - `tests/unit/test_mock_mode.py` — mock-mode flag resolution (alias coverage)
  - `tests/unit/test_services.py` — service-layer domain logic
  - `tests/unit/test_nodes.py` — node-level contract, S-1/S-2/S-3 gates
  - `tests/proof_of_boundary/` — framework boundary verification (PB-1–PB-7)
  - `tests/integration/test_graph.py` — outer graph `.compile()` + `.invoke()`
  - `tests/integration/test_domain_workflow_graph.py` — inner graph `.compile()` + `.invoke()`
  - `tests/integration/test_server_http.py` — HTTP-level `/invoke` via real ASGI transport

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict | Type check pass, no Pydantic/dataclass | Pass — `tests/proof_of_boundary/test_state_safety.py` |
| TC-02 | SecurityViolationError fires on invalid input | Error raised | Pass — `test_nodes.py::TestRentEvidencePreProcessNode` (malformed JSON, missing case_id, out-of-jurisdiction) |
| TC-03 | No JWT/Credential in State | CI `gate-credential-scan`: 0 violations (S-5 enforcement moved to CI) | Pass — no credential-named fields in `src/schemas/state.py` |
| TC-04 | InvocationContext via configurable only | Direct access raises error | Pass — nodes use `InvocationContext.from_state(state)` only (`normalize_node.py`); never store ctx in State |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start` / `node_complete` / `node_error` absent from `execute()` body | Pass — verified by code review; `check-security.sh` confirms `emit_trace_event` domain calls only |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | Pass — no node overrides it; framework `__init_subclass__` enforces |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final` enforced by framework) | Pass — no node overrides it |
| TC-08 | `required_trust_level` enforced | Insufficient trust → refused | Pass — `test_nodes.py::test_s1_trust_gate_denies_anonymous_caller` (called via `__call__`, not `execute()`) |
| TC-09 | S-2: `_extra_security_gate_input()` non-trivial when domain checks needed | Domain-specific input checks execute correctly | Pass — `RentEvidencePreProcessNode._extra_security_gate_input()` validates case_id format + jurisdiction scope; `test_nodes.py` |
| TC-10 | S-3: `_extra_security_gate_output()` non-trivial when domain checks needed | Domain-specific output checks execute correctly | Pass — `RentEvidencePostProcessNode._extra_security_gate_output()` blocks rent/approval/notice language + verifies citations; `test_nodes.py::test_rent_figure_language_blocked`, `test_missing_citation_blocked` |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` | Domain event emitted on every invocation path | Pass — `check-security.sh` `check_emit_trace_event`; all 6 nodes emit (`case_validated`, `evidence_retrieved`, `fields_normalized`, `evidence_checked`, `packet_assembled`, `packet_gate_cleared`) |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | Pass — covered by TC-11 + `test_pb_invoke_order.py` |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass | Pass — `tests/proof_of_boundary/test_state_safety.py` |
| PB-3 | L1 → External service | Real external service connection | Data retrieved | **Deferred** — Retrieve/Normalize wire to a real KB/tenant-record store and LLM client in a future sprint (`_call_external`/`_call_llm` raise `NotImplementedError` outside mock mode, per design); mock-mode path verified in `test_services.py` and integration tests instead |
| PB-4 | Import isolation | No Level 0 imports | AST scan: 0 violations | Pass — `tests/proof_of_boundary/test_import_isolation.py` |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass | Pass — `tests/proof_of_boundary/test_state_safety.py` |
| PB-6 | Invoke execution order | `__call__()`: S-1 trust gate → S-4 `node_start` → S-2 `_security_gate_input` → `execute()` → S-3 `_security_gate_output` → S-4 `node_complete` | Order verified | Pass — `tests/proof_of_boundary/test_pb_invoke_order.py` (customized with per-node valid state + mock mode) |
| PB-7 | HITL interrupt propagation *(conditional)* | Required only when `config.yaml` sets `hitl.enabled: true`; otherwise record **Auto-waived — non-HITL** | `GraphInterrupt` propagates to the LangGraph engine; `status` is not set to `error` | **Auto-waived — non-HITL** (no `config.yaml`/`hitl.enabled: true` in this template) |

> **Pre-CoE gate checklist:** PB-1 through PB-6 are mandatory. Evaluate PB-7 only for HITL-enabled templates. When neither HITL setting is true, mark PB-7 **Auto-waived — non-HITL**; its test is not required and must not block the gate.

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | Evidence check flags missing evidence with citation | normalized_fields missing `spousal_income` | `gap_findings` includes entry citing `ordinance §4-2` | Pass — `test_services.py::TestEvidenceCheckService::test_missing_evidence_flagged_with_citation` |
| BL-02 | Evidence check flags income-band contradiction | `household_size` not in configured income bands | `gap_findings` includes a `contradiction` entry | Pass — `test_services.py::TestEvidenceCheckService::test_contradictory_household_size_flagged` |
| BL-03 | Packet includes mandatory disclaimer | any valid packet | `disclaimer` field present verbatim (engineer_proposal.md §10) | Pass — `test_services.py::TestPacketService::test_assemble_includes_disclaimer_and_citations` |
| BL-04 | S-3 gate blocks rent/approval language | packet finding text contains "rent is 250000" | `SecurityViolationError` → node `status: error` | Pass — `test_nodes.py::test_rent_figure_language_blocked` |
| BL-05 | S-3 preservation check rejects missing citation | gap entry with empty `rule_reference` | `SecurityViolationError` → node `status: error` | Pass — `test_nodes.py::test_missing_citation_blocked` |
| BL-06 | Mock-mode helper resolves under either alias | `USE_MOCK=true` alone; `STG_MOCK_MODE=true` alone; neither set | `mock_mode_enabled()` True / True / False respectively | Pass — `test_mock_mode.py` (regression test per `.claude/rules/test_rule.md` Rule 1) |
| BL-07 | Normalize succeeds in mock mode with zero secrets bound | `USE_MOCK=true`, `ANTHROPIC_API_KEY` unset, no `bound_secrets()` context | `status: success`, no `MissingSecret` | Pass — `test_nodes.py::test_normalize_succeeds_with_no_secret_in_mock_mode` (regression test per `.claude/rules/test_rule.md` Rule 2) |
| BL-08 | `/invoke` succeeds over real HTTP/ASGI transport | valid case JSON payload, real event loop | HTTP 200, `status: success` | Pass — `test_server_http.py::test_invoke_endpoint_succeeds_over_http` (regression test per `.claude/rules/test_rule.md` Rule 3 — exercises the `asyncio.to_thread` async/sync boundary fix) |
| BL-09 | Outer + inner graph compile and invoke end-to-end | valid/invalid case JSON | `status: success`/`error`; correct `node_history` | Pass — `test_graph.py`, `test_domain_workflow_graph.py` |

## Test Execution Summary
- Execution date: 2026-07-21
- Total tests: 41 (39 passed, 2 skipped — PB-7 auto-waived, non-HITL)
- Pass: 39 / Fail: 0 / Skip: 2
- Coverage: 97% (`src/`, via `pytest --cov=src`)
- Local gate mirror: `bash .claude/common-scripts/check-local.sh` — all mandatory local checks passed (exit 0). The Stage 5 STG invoke-evidence sub-check (WARN-only/manual gate, not part of this stage's DoD) failed due to a timing race in the scaffold's own check script (no warm-up delay before curling uvicorn) — the server log (`/tmp/stg-server.log`) confirms both `/health` and `/invoke` actually returned 200 OK; not an agent defect.
