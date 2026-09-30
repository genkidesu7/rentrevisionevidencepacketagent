# Template Design Specification

## Position in AgentCore Architecture

- **Agent Class**: `RentRevisionEvidencePacketAgent`
- **L1 Base**: **AgentBaseGraph** (outer graph) — Cat 2, GraphNode composition wrapping an
  inner domain workflow graph. No Level-2 base type (RAGAgent/ChatAgent/ReActAgent/
  DocGenerationAgent) is used; this is L1-direct per the approved proposal (§2, §5).
- **Three-Layer Separation**:
  - State: flat TypedDict composition (no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution)

## Architecture Overview

This is a **Cat 2** template: it orchestrates a specific job-to-be-done (determining
rent-revision file readiness for a tenant household) via a fixed multi-step workflow, not
a single reusable capability (Cat 1) and not an autonomous self-directed loop (Cat 3).

Two layers, per the standard Cat 2 pattern:

- **Outer graph** (`src/graph/graph.py`) — inherits `AgentBaseGraph`. Standard 5-node
  backbone (`initialize → pre_process → main → post_process → finalize`). Domain
  complexity is hidden inside the `main` slot via a `GraphNode` subclass
  (`RentEvidenceWorkflowGraphNode`).
- **Inner graph** (`src/graph/domain_workflow_graph.py`) — inherits `BaseGraph` (fully
  custom topology, no pre_process/main/post_process slots). Implements the four
  domain-specific steps between InputValidate and OutputValidate: Retrieve → Normalize →
  EvidenceCheck → PacketAssemble.

Mapping from the proposal's 6-step workflow (`engineer_proposal.md` §4) onto the
AgentCore two-layer pattern:

| Proposal step | AgentCore location |
|---|---|
| 1. InputValidate (S-1 gate) | Outer `pre_process` |
| 2. Retrieve | Inner `retrieve` |
| 3. Normalize | Inner `normalize` |
| 4. EvidenceCheck | Inner `evidence_check` |
| 5. PacketAssemble | Inner `packet_assemble` |
| 6. OutputValidate (S-3 gate) | Outer `post_process` |

### Node Configuration (outer graph)

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | Sets schema_version, session_id, caller_trust_level | — | `schema_version`, `session_id`, `caller_trust_level` | InitializeNode (default) |
| pre_process | S-1 gate: reject requests without a valid `case_id` or outside the caseworker's assigned `jurisdiction` (`_extra_security_gate_input()`); sets `validated_input` | `user_input` | `validated_input`, `case_id`, `jurisdiction`, `status` | `FunctionNode` (`RentEvidencePreProcessNode`) |
| main | Runs the inner domain workflow graph (Retrieve→Normalize→EvidenceCheck→PacketAssemble) and merges its output | `validated_input`, `case_id`, `jurisdiction` | `draft_packet`, `gap_findings`, `checklist_status`, `status` | `GraphNode` (`RentEvidenceWorkflowGraphNode`) |
| post_process | S-3 gate (mandatory): block any rent figure, approval status, or notice language in `draft_packet`; verify every finding cites a source record and rule/checklist item; shape `formatted_output` | `draft_packet`, `gap_findings`, `checklist_status` | `formatted_output`, `status` | `FunctionNode` (`RentEvidencePostProcessNode`) |
| finalize | Builds `response_metadata`, `total_time_ms` | — | `response_metadata`, `total_time_ms` | FinalizeNode (default) |

### Node Configuration (inner graph — `domain_workflow_graph.py`)

| Node | Responsibility | Input State | Output State |
|------|---------------|-------------|--------------|
| retrieve | Pulls tenant income evidence, household-change records, and the applicable rent ordinance / checklist / review-calendar KB for `case_id` | `case_id`, `jurisdiction` | `raw_evidence`, `rule_reference` |
| normalize | LLM-assisted extraction of submitted documents into structured fields (income by source, household size, dependent status) | `raw_evidence` | `normalized_fields` |
| evidence_check | Matches `normalized_fields` against ordinance income bands and checklist items; flags missing/conflicting evidence | `normalized_fields`, `rule_reference` | `checklist_status`, `gap_findings` |
| packet_assemble | Composes the reviewer packet: confirmed evidence, gaps, contradictions, checklist status, each linked to source record and rule/checklist item | `normalized_fields`, `checklist_status`, `gap_findings`, `rule_reference` | `draft_packet` |

### Data Flow

```
START → initialize → pre_process → main → {route} → post_process → finalize → END
                                            ↓ (retry)
                                          pre_process

Inside `main` (RentEvidenceWorkflowGraphNode.execute()):
  GraphNode.get_subgraph() → RentEvidenceWorkflowGraph.invoke(validated_input, ctx=ctx)
  Inner graph: START → retrieve → normalize → evidence_check → packet_assemble → END
  merge_output() maps inner sub_result fields back into outer state.
```

### State Definition

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `case_id` | `str` | Rent-revision review case identifier, validated by S-1 in `pre_process` | Yes |
| `jurisdiction` | `str` | Caseworker's assigned jurisdiction, used to scope retrieval | Yes |
| `raw_evidence` | `dict` | Retrieved tenant income evidence + household-change records (inner `retrieve`) | No (set by inner graph) |
| `rule_reference` | `dict` | Retrieved rent ordinance income bands, checklist, review-calendar rules (inner `retrieve`) | No |
| `normalized_fields` | `dict` | Structured fields from Normalize: income by source, household size, dependent status | No |
| `checklist_status` | `dict` | Per-checklist-item match results from EvidenceCheck | No |
| `gap_findings` | `list[dict]` | Missing/conflicting evidence findings, each with source citation and rule/checklist reference | No |
| `draft_packet` | `dict` | Assembled reviewer packet prior to the S-3 output gate | No |
| `formatted_output` | `dict` | Final gate-cleared review packet (confirmed evidence, gaps, contradictions, checklist status) | No |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

`gap_findings` is a plain `list[dict]`, replaced wholesale by `packet_assemble` on each
invocation — not `Annotated[list, operator.add]`, since it is not an append-only
accumulator across multiple node calls within one invocation.

## Framework Utilization

### Services (`src/services/`)

- **`evidence_retrieval_service.py`** — retrieves tenant income evidence, household-change
  records, and the applicable rent ordinance / income-evidence checklist / review-calendar
  KB for a `case_id` + `jurisdiction`, scoped to `kb_path: ./kb/` (per-municipality config
  surface, per `engineer_proposal.md` §10). Used by inner `retrieve`.
- **`normalization_service.py`** — wraps the shared platform LLM client (via
  `framework`/`shared` — no direct provider SDK import) for LLM-assisted extraction of
  submitted documents into structured fields. Used by inner `normalize`.
- **`evidence_check_service.py`** — pure rule-matching logic: compares normalized fields
  against ordinance income bands and checklist items, no LLM or external call. Used by
  inner `evidence_check`.
- **`packet_service.py`** — composes the reviewer packet structure (confirmed evidence,
  gaps, contradictions, checklist status) with source/rule citations. Used by inner
  `packet_assemble` and referenced by the outer `post_process` S-3 preservation check.

All services live in `src/services/`, contain no `agenticstar` imports, and receive
credentials only via `ctx.secrets.require()` (declared in `config/agent.yaml`
`requires.secrets` — `ANTHROPIC_API_KEY` for the normalization service's LLM client).

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, permissions, credential handle)
- [x] ConnectionPolicy (retry/timeout strategy) — `max_retry: 3` per `config/agent.yaml`
- [x] SecurityViolationError
- [x] S-2: `_extra_security_gate_input()` — validates `case_id` format and that
      `jurisdiction` matches the caller's assigned jurisdiction (from
      `InvocationContext`); rejects out-of-scope household reviews. Runs after the
      default PII scan on `user_input`/`validated_input`.
- [x] S-3: `_extra_security_gate_output()` — mandatory domain check: scans
      `formatted_output` for rent-figure, approval, or notice language and raises
      `SecurityViolationError` if found; verifies every entry in `gap_findings` /
      `checklist_status` cites a source record and rule/checklist item (preservation
      variant — rejects output that drops required citations). Runs after the default
      credential scan.
- [x] S-4: `emit_trace_event()` — at least one domain-specific event inside each
      `execute()`:
      - `pre_process`: `case_validated` (`case_id`, `jurisdiction`)
      - inner `retrieve`: `evidence_retrieved` (`case_id`, record counts)
      - inner `normalize`: `fields_normalized`
      - inner `evidence_check`: `evidence_checked` (gap/contradiction counts)
      - inner `packet_assemble`: `packet_assembled`
      - `post_process`: `packet_gate_cleared`
      (does NOT re-emit `node_start`/`node_complete`/`node_error` — framework-owned)

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass (`pre_process`, `post_process`) → framework `@final` gate
>   always runs automatically; extended via `_extra_security_gate_input()` /
>   `_extra_security_gate_output()` as above
> - `GraphNode` (`main`) → deliberate no-op — the inner graph's own nodes are
>   `FunctionNode` subclasses with their own S-2/S-3 gates; the outer `post_process`
>   FunctionNode applies the mandatory packet-level S-3 gate described above
> - No custom `BaseNode` subclass is used in this template

### Composition Pattern

- **Pattern**: GraphNode (subgraph)
- **Composition target**: `src/graph/domain_workflow_graph.py` — `RentEvidenceWorkflowGraph`
  (inherits `BaseGraph`, fully custom `retrieve → normalize → evidence_check →
  packet_assemble` linear topology; no HITL/routing branch needed for the initial
  release, since gap/contradiction detection does not require a human-in-the-loop pause —
  the caseworker/supervisor review happens *after* the packet is returned, not mid-graph)
- **Error propagation strategy**: `propagate` (default) — a retrieval, normalization, or
  evidence-check failure inside the inner graph is re-raised as `SubgraphError` and
  routed to `finalize` via the outer graph's standard error routing; no graceful
  degradation is defined for this template, since a partial/degraded evidence packet
  would risk a caseworker acting on incomplete evidence-gap information
- `propagate_hitl`: `False` (default) — this template does not set `hitl.enabled: true`;
  no HITL interrupts are used at any layer

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: framework/ and shared/ only (no agents/base/ required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | **AgentBaseGraph** | Fixed multi-step workflow for a specific job-to-be-done (Cat 2), not a self-directed think→act→observe loop — proposal §2-2 confirms no autonomous termination logic |
| Composition pattern | Standalone (all logic in outer `main` FunctionNode) | GraphNode (inner domain workflow graph) | **GraphNode** | Four distinct domain steps (Retrieve/Normalize/EvidenceCheck/PacketAssemble) with different responsibilities and failure modes justify a dedicated inner graph rather than one monolithic `main` node; matches the standard Cat 2 pattern (`graph_cat2_sample.py`) |
| Inner graph parent | `BaseGraph` (custom topology) | `AgentBaseGraph` (5-node pipeline) | **BaseGraph** | The four inner steps do not map onto the pre_process/main/post_process shape — each is a distinct sequential transform with its own state output, so a fully custom linear topology is clearer than forcing a 3-slot pipeline |
| S-3 gate strategy | Content filtering only | Content filtering + preservation verification | **Both** | Must block rent/approval/notice language (filtering) AND must not silently drop required source citations from findings (preservation) — proposal's OutputValidate step requires both per `engineer_proposal.md` §4 |
| HITL | Enabled (interrupt before packet release) | Disabled | **Disabled** | Proposal's human review happens after the agent returns the packet (caseworker approves/returns/escalates) — this is downstream of the agent's own execution, not a mid-graph pause; no `interrupt()` trigger condition applies |
| Error strategy (`GraphNode`) | `propagate` | `handle` | **propagate** | An evidence-check failure should surface as a hard error rather than a degraded packet, since a caseworker must not receive a packet claiming completeness when retrieval/normalization/checking actually failed |

---

*Status: completed*
*Date: 2026-07-21*
*Reviewer: TBD*
*Source: `docs/01_proposal.md` (approved), `engineer_proposal.md` §2–§4*
