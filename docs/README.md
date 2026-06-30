# Animus-Mind Documentation

**Version:** 0.1.0-alpha  
**Architecture:** Mind-class v2.1+  
**Last updated:** 2026-06-30

---

## What This Is

This directory contains the canonical documentation for **Animus-Mind** — the Mind-class architecture branch of the Animus exocortex system. For the stable Assistant-class release (v2.3), see the [`animus`](https://github.com/AreteDriver/animus) repository.

---

## Navigation

### 🚀 Getting Started
- [Quick Start](../README.md#quick-start) — Clone, install, and run (on root README)
- [Migration Guide](migration/v2.3-to-mind.md) — Moving from Animus v2.3 Assistant to Animus-Mind

### 🏛️ Architecture
- [World Model Architecture](architecture/Animus_World_Model_Architecture_v1.0.md) — Core design reference for Mind-class systems
- [Decisions](architecture/decisions/) — Architecture Decision Log (ADL) and ADRs
  - [ADL-20260618-001](architecture/decisions/ADL-20260618-001.md) — v2.1 Mind-class commitment
  - [ADR-001](architecture/decisions/ADR-001.md) — Initial schema validation approach

### 🗺️ Roadmap & Planning
- [v2.2 Roadmap](roadmap/v2.2.md) — 10-phase implementation plan (high-level)
- [v2.2 Implementation Roadmap & Engineering Guidelines](artifacts/Animus_v2.2_Implementation_Roadmap_and_Engineering_Guidelines.md) — Full detailed roadmap

### 📦 Per-Module Documentation
| Module | Path | Status |
|---|---|---|
| Identity & Policy | `modules/identity_policy/` | 🔴 Not started |
| Object Core | `modules/object_core/` | 🚧 Scaffolded |
| Source Ingestion | `modules/source_ingestion/` | 🔴 Not started |
| Context Service | `modules/context_service/` | 🔴 Not started |
| Memory Service | `modules/memory_service/` | 🔴 Not started |
| Agent Runtime | `modules/agent_runtime/` | 🔴 Not started |
| MCP Gateway | `modules/mcp_gateway/` | 🔴 Not started |
| Trace & Evaluation | `modules/trace_eval/` | 🔴 Not started |

---

## Documentation Principles

1. **Mind-class only.** This repo documents the Mind architecture (persistent context, world model, policy decision point, agent contracts). Assistant-class docs (Bootstrap dashboard, PWA setup, Forge eval calibration) remain in the `animus` repo.
2. **Every claim is dated.** Time-sensitive information includes a verification date.
3. **Link, don't copy.** Cross-references use relative paths. No raw code dumps.
4. **Decision authority.** All significant architectural changes require an ADR in `docs/architecture/decisions/`.

---

## Decision Authority

- **Architecture authority:** [ADL-20260618-001](architecture/decisions/ADL-20260618-001.md)
- **Change control:** ADR process in `docs/architecture/decisions/`
- **Decision maker:** AreteDriver
