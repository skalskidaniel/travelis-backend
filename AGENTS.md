# AGENTS.md — TraveLis Backend

## First read

- **`docs/architecture/agent-guidelines.md`** — mandatory. All non-negotiable rules (layering, imports, rating/board normalization, etc.)
- **`docs/architecture/`** — 9 short docs covering requirements, system overview, code structure, data model, pipeline, scoring, API, infra.

## Project state (early scaffold)

| Area | Status |
|---|---|
| `src/core/` | **Empty** — needs `models/`, `providers/`, `repositories/`, `services/`, `config.py`, `container.py` |
| `src/app/{auth,offers,user}/controller.py` | Empty stubs |
| `src/app/health/` | Empty directory |
| `tests/` | Empty |
| `.github/workflows/` | None |

## Key commands

```bash
uv sync                          # install deps (uv, not pip/poetry)
uvicorn app.main:app --reload --port 8000 --app-dir src   # dev server
ruff check src/                  # lint (no config file yet — will need one)
ruff format src/                 # format
```

Python 3.13, async end-to-end. No test framework configured yet.

## Architecture rules

- **Hexagonal layering**: `src/app/` (entrypoints) → `src/core/` (domain). `core` must **never** import `app`. Feature modules in `app/` must **never** import each other.
- **Absolute imports** from `src/` root: `from core.models.offer import Offer`, not `from ..models.offer import Offer`.
- **Dual-entry Lambda handler**: `app.main.handler` dispatches HTTP (via Mangum), EventBridge cron, Cognito triggers, and Scheduler one-time jobs.
- **Container**: `core/container.py` is the composition root, entered once per cold start via `AsyncExitStack`. Controllers access it via trivial `Depends` wrappers.
- **DynamoDB**: No GSIs on `Offers` table; always query by `(cell_id, offer_id)`. `MarketCells` exist iff `activation_count > 0`.
- **Matching**: Event-driven only (post-scrape bulk + debounced per-user via EventBridge Scheduler `at(now+30s)`). No sweeper/poll.
- **Rating**: 0–5 canonical scale. wakacje.pl ÷2, tui.pl as-is.
- **Board types**: Normalize via numeric `service` (wakacje) or `boardCode` (tui), never by localized string.
- **Concurrency**: Bounded `asyncio.Semaphore` (~10) for scrape fan-out in `app/jobs/coordinator`. `core` exposes single-unit async fns only.
- **Scoring**: CPU-bound numpy wrapped in `asyncio.to_thread()`.

## Provider adapters

Clients: `httpx.AsyncClient`. Contracts reverse-engineered, documented in `docs/providers/`.

- wakacje.pl: `POST` search blob, `YYYY-MM-DD` dates, composite dedup key
- tui.pl: `tui-api-key` / `x-market` headers, `DD.MM.YYYY` dates, `boardCode` → board map, `offerUrl` prefixing

## Observability

- Structured JSON logs via AWS Lambda Powertools
- Grafana dashboards

## Docs as source of truth

All external provider contracts live in `docs/providers/` (versioned, not linked to external URLs). If prose in `docs/` conflicts with code or config, the executable source wins.
