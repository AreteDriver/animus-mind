# Animus-Mind

**Version:** 0.1.0-alpha  
**Architecture:** Mind-class v2.1+  
**License:** MIT  
**Platform:** Linux (primary), macOS (roadmap), Windows (out of scope)

---

> **This is the Mind-class architecture branch.** For the stable Assistant-class release (v2.3), see [`github.com/AreteDriver/animus`](https://github.com/AreteDriver/animus).

---

## What This Is

Animus-Mind is a **persistent, self-improving personal intelligence system** — an exocortex that continuously models the world, detects contradictions, preserves dissent, and refuses to act when evidence is insufficient. It is not a chatbot. It is not an assistant. It is a **research colleague** that operates across sessions with memory, planning, and bounded autonomous execution.

This repository implements the v2.1 Mind-class architecture: 8 technical planes, 22 canonical JSON schemas, PostgreSQL as durable authority, adversarial test harness, and evidence bundles per release.

## What This Is Not

- A general-purpose consumer product (personal use only)
- A multi-tenant SaaS
- A voice/video processor
- A blockchain or crypto tool
- A replacement for Claude Code, Cursor, or Copilot (those are **assistants**; this is a **Mind**)

---

## Architecture

```
Sensor Layer → Event Bus → Event Store → World State Engine
                                                    ↓
Knowledge Graph ← Pattern Detection ← Forecast Engine ← Strategic Intelligence
```

### 8 Technical Planes

| Plane | Module | Responsibility |
|---|---|---|
| **Identity & Policy** | `modules/identity_policy/` | Principals, capability grants, kill switches |
| **Object Core** | `modules/object_core/` | Ledger, versions, projections, outbox |
| **Source Ingestion** | `modules/source_ingestion/` | Immutable source registry, content hashes |
| **Context Service** | `modules/context_service/` | Context Envelope assembly |
| **Memory Service** | `modules/memory_service/` | Candidate pipeline, admission, contradiction |
| **Agent Runtime** | `modules/agent_runtime/` | Agent contracts, budget enforcement, dissent |
| **MCP Gateway** | `modules/mcp_gateway/` | Tool registry, action safety, receipts |
| **Trace & Evaluation** | `modules/trace_eval/` | Evidence bundles, gate evaluation |

### Key Principles

1. **PostgreSQL is the durable authority.** Search, vectors, graphs, and caches are rebuildable projections.
2. **The deterministic core surrounds the probabilistic system.** Policy, authorization, schemas, transitions, budgets, and approvals are code-enforced — not model-enforced.
3. **Default deny and fail closed.** Missing scope, stale approval, unknown schema, or invalid transition → denial or abstention.
4. **No consequential write without a proof chain.** Principal, purpose, workspace, policy decision, approval, idempotency key, precondition, event, object version, and receipt must all be linked.
5. **Material dissent is data.** Critic findings and unresolved contradictions are retained and surfaced.

---

## Quick Start

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+ (for Celery workers)
- Node.js 20+ (for web app)
- Ollama + local models (optional, for local inference)

### 1. Clone and Install

```bash
git clone https://github.com/AreteDriver/animus-mind.git
cd animus-mind
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure PostgreSQL

Copy `.env.example` to `.env` and set your database URL. Then run:

```bash
python scripts/setup_postgres.py
```

### 3. Run Migrations

```bash
cd database/migrations
alembic upgrade head
cd ../..
```

### 4. Start the API

```bash
uvicorn apps.api.main:app --reload --port 8000
```

### 5. Start a Worker (optional)

```bash
celery -A apps.worker.main worker --loglevel=info
```

---

## Repository Structure

```
animus-mind/
├── apps/
│   ├── api/              # Owner/API entry point (FastAPI)
│   ├── worker/           # Outbox and workflow workers (Celery)
│   └── cli/              # Validation, migration, recovery, evidence
├── modules/
│   ├── identity_policy/    # Principals, grants, kill switches
│   ├── object_core/       # Ledger, versions, projections, outbox
│   ├── source_ingestion/  # Immutable source registry
│   ├── context_service/   # Context Envelope assembly
│   ├── memory_service/    # Candidate pipeline, admission
│   ├── agent_runtime/     # Agent contracts, budget enforcement
│   ├── mcp_gateway/       # Tool registry, action safety
│   ├── trace_eval/        # Evidence bundles, gate evaluation
│   ├── projections/       # Search, vectors, graphs (rebuildable)
│   └── recovery_governance/ # Backup, restore, deletion, incident
├── contracts/
│   ├── schemas/           # 22+ JSON schemas (Draft 2020-12)
│   ├── api/               # OpenAPI specs
│   ├── events/            # Event contract definitions
│   ├── policies/          # Deterministic policy rules
│   ├── state_machines/    # Execution, approval, admission
│   └── errors/            # Structured error model
├── database/
│   ├── migrations/        # Alembic
│   ├── constraints/       # DDL for invariants
│   ├── seeds/             # Bootstrap data
│   └── verification/      # Reconciliation scripts
├── tests/
│   ├── unit/              # Fast, isolated
│   ├── schema/            # Schema compilation
│   ├── contract/          # Positive/negative fixtures
│   ├── integration/       # Cross-module flows
│   ├── adversarial/       # Prompt injection, bypass attempts
│   ├── fault_injection/   # Kill, delay, corrupt
│   ├── chaos/             # Randomized failure
│   ├── recovery/          # Restore, rebuild
│   ├── golden/            # Reference trace reproduction
│   └── end_to_end/        # Architecture-corpus vertical slice
├── evals/                 # Labeled corpora, rubrics, scoring
├── operations/            # Runbooks, dashboards, alerts
├── evidence/              # Per-release evidence bundles
└── infra/                 # Docker Compose, evaluation, shadow, limited
```

---

## What's Ready vs. Planned

| Component | Status | Notes |
|---|---|---|
| Contracts (22 schemas) | 🚧 Ported from v2.3; 2 missing | Need `ledger_event`, `agent_contract` |
| PostgreSQL object core | 🚧 Ported; needs bitemporal cols | `DurableMemoryStore` from v2.3 |
| API shell | 🚧 Ported from Bootstrap | Needs policy middleware upgrade |
| Eval harness | 🚧 Ported from Forge | Needs adversarial suites |
| PWA frontend | 🚧 Ported | Needs event streaming |
| Ledger + outbox | 🔴 Not started | Phase 2 of roadmap |
| Identity policy | 🔴 Not started | Phase 3 |
| Source ingestion | 🔴 Not started | Phase 4 |
| Memory admission | 🔴 Not started | Phase 5 |
| Agent contracts | 🔴 Not started | Phase 6 |
| MCP gateway | 🔴 Not started | Phase 7 |
| Evidence bundles | 🔴 Not started | Phase 8 |
| Backup/restore | 🔴 Not started | Phase 9 |
| Vertical slice | 🔴 Not started | Phase 10 |

See `docs/roadmap/v2.2.md` for the full 10-phase implementation plan.

---

## Relationship to Animus v2.3

This repository is a **fork**, not an upgrade.

- **Animus v2.3** (`github.com/AreteDriver/animus`) is the frozen Assistant-class stable release. It remembers, orchestrates workflows, and serves a dashboard. It is your daily driver.
- **Animus-Mind** (this repo) is the Mind-class research platform. It requires the structural redesign that v2.1 specifies: ledger, bitemporal state, policy decision point, agent contracts, adversarial harness.

If you want a working assistant today, use [Animus v2.3](https://github.com/AreteDriver/animus). If you want to build the future, contribute here.

---

## Decision Authority

- **Architecture authority:** ADL-20260618-001 (v2.1 Mind-class commitment)
- **Change control:** ADR process in `docs/architecture/decisions/`
- **Decision maker:** AreteDriver

---

## License

MIT. See LICENSE.
