# AdaptiveHoney

AdaptiveHoney is a safe, research-oriented cyber-deception prototype. It simulates a Linux shell in per-session virtual state, profiles observed behavior, exposes only approved synthetic artifacts, and records evidence-backed MITRE ATT&CK mappings.

> **Safety boundary:** submitted commands are parsed and emulated. They are never executed by the host operating system. Network activity is simulated or rejected.

## Included

- Stateful virtual filesystem, identity, process, service, and persistence state
- Deterministic handlers for common Linux commands
- Behavior profile with automation, sophistication, and objective probabilities
- Constrained rule-based adaptation with a valid `do_nothing` action
- Evidence-linked ATT&CK mapping and IOC extraction
- Append-only SQLite event log and replayable state snapshots
- FastAPI REST/WebSocket API
- Responsive analyst dashboard with a built-in live shell simulator
- Pytest coverage for isolation, permissions, persistence, and mappings

## Quick start

Requires Python 3.11+.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn adaptive_honey.main:app --reload --port 8000
```

Open <http://localhost:8000>. The backend serves the dashboard directly, so no Node build is required.

Run tests:

```powershell
pytest
```

## API

- `POST /api/sessions` — create an isolated session
- `GET /api/sessions` — list sessions
- `GET /api/sessions/{id}` — session detail and current state
- `POST /api/sessions/{id}/commands` — emulate a command
- `GET /api/sessions/{id}/replay` — complete evidence package
- `GET /api/metrics` — operational and research metrics
- `WS /ws/sessions` — session update stream

Interactive API documentation is available at `/docs`.

## Architecture

```text
command -> parser -> profiler -> constrained policy -> emulator
        -> validation -> atomic state commit -> evidence/ATT&CK log
```

The emulator is the source of truth. An LLM adapter can later be added behind the same response contract, but it must not receive host tools, secrets, or network access. Invalid model output should fall back to a deterministic shell error.

## Research caveat

This is a functional prototype, not proof of the research claims. Comparative deployment, human review, calibrated models, inter-rater agreement, and controlled experiments are still required before making effectiveness claims.

