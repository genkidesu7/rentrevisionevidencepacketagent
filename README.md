# GOV-C2-094 — Municipal Public-Housing Rent Revision Evidence Packet Agent

> **Category**: Cat 2 (orchestrates a specific job-to-be-done: rent-revision evidence review)
> **Industry**: GOV (government)

## Overview

Triggered when a municipal public-housing office opens a periodic rent-revision review for a
tenant household. The agent retrieves the tenant's income evidence and household-change
records plus the municipality's rent ordinance and evidence checklist, normalizes submitted
documents into structured fields, checks them against ordinance income bands and checklist
requirements, and assembles a source-linked human-review packet listing confirmed evidence,
gaps, and contradictions. It never calculates a rent figure, approves, or issues a notice
itself — those decisions remain with authorized public-housing staff.

- **InputValidate** (S-1 gate) — rejects requests without a valid case ID or outside the
  caseworker's assigned jurisdiction.
- **Retrieve** — pulls tenant income evidence, household-change records, and the applicable
  rent ordinance / checklist / review-calendar KB.
- **Normalize** — LLM-assisted extraction of submitted documents into structured fields
  (income by source, household size, dependent status).
- **EvidenceCheck** — matches normalized fields against ordinance income bands and checklist
  items; flags missing or conflicting evidence.
- **PacketAssemble** — composes the reviewer packet with source-linked findings, gaps, and
  contradictions.
- **OutputValidate** (S-3 gate, mandatory) — blocks any rent figure, approval, or notice
  language; verifies every finding cites a source record and rule/checklist item.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| **Anthropic API key** | Required for the Normalize step's LLM-assisted extraction (outside mock mode — see below). |
| Python | >=3.11 |

```bash
pip install -e .
```

### Behaviour without the platform

This agent is written against the `agenticstar-agentcore` framework and is
runnable standalone via `src/api/server.py` — it does not require the wider
AgentCore platform (registry, gateway, orchestrator) to function. Outside the
platform: request authentication falls back to an optional bearer token read
from an environment variable (unset means every caller is treated as
unauthenticated), there is no persistent checkpointer unless you wire one
yourself, and the Anthropic API key is read directly from the process
environment rather than through the platform's secret-provisioning layer.
Setting `USE_MOCK=true` runs the Retrieve and Normalize steps against
deterministic fixtures instead of the tenant record store / KB and the LLM
client — see `src/services/mock_mode.py`.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

`input` is a JSON string: `{"case_id": "...", "jurisdiction": "..."}`.

```bash
curl -X POST http://127.0.0.1:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": "{\"case_id\": \"CASE-001\", \"jurisdiction\": \"muni-tokyo-01\"}"}'
```

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and operational documentation
```

See `docs/` for the design spec and test specification.

## Customising

1. Adjust `config/` for your own environment and rent ordinance rules.
2. Replace the income-evidence taxonomy and checklist data with your own.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.
