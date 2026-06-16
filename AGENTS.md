# AGENTS.md — TraveLis Backend

## First read

- **`docs/architecture/agent-guidelines.md`** — mandatory. Non-negotiable rules (layering, imports, rating/board normalization, etc).
- **`docs/architecture/`** — 9 docs covering requirements, system overview, code structure, data model, pipeline, scoring, API, infra.

## Project state

| Area | Status |
|---|---|
| `src/core/models/`, `src/core/providers/`, `src/core/exceptions/` | Built |
| `src/core/services/`, `src/core/repositories/`, `config.py`, `container.py` | **Not yet built** — will add |
| `src/app/{auth,offers,user}/` | Stub controllers (just `router = APIRouter()`), empty `models.py` |
| `src/app/health/` | Empty directory |
| `src/app/jobs/` | Not yet built |
| `tests/` | Unit tests exist under `tests/core/models/` and `tests/core/providers/` |
| `.github/workflows/` | None |

## Key commands

```bash
uv sync                          # install deps (uv only; no pip/poetry)
uvicorn app.main:app --reload --port 8000 --app-dir src   # dev server
ruff check src/ tests/           # lint (no config file yet)
ruff format src/ tests/          # format
```

## Tests

```bash
pytest                           # runs all; pyproject.toml sets pythonpath = ["src"]
pytest -xvs tests/path/to/test   # single test file, verbose
pytest -k "test_name"            # filtered run
```

- Framework: `pytest` + `pytest-asyncio` (all async tests need `@pytest.mark.asyncio`).
- HTTP mocking: `respx` (used in provider tests to mock `httpx`).
- No test markers yet (no `slow`, `integration`, etc).

## Architecture rules (from code + agent-guidelines.md)

- **Hexagonal layering**: `src/app/` (entrypoints) → `src/core/` (domain). `core` must **never** import `app`. Feature modules in `app/` must **never** import each other.
- **Absolute imports** from `src/` root: `from core.models.offer import Offer`, not relative imports.
- **Dual-entry handler**: `app.main.handler` (not yet built) will dispatch HTTP (Mangum), EventBridge cron, Cognito triggers, and Scheduler one-time jobs.
- **Container**: `core/container.py` (not yet built) is the composition root, entered once per cold start via `AsyncExitStack`. Controllers access it via trivial `Depends` wrappers.
- **DynamoDB**: No GSIs on `Offers` table; always query by `(cell_id, offer_id)`. `MarketCells` exist iff `activation_count > 0`.
- **Matching**: Event-driven only (post-scrape bulk + debounced per-user via EventBridge Scheduler `at(now+30s)`). No sweeper/poll.
- **Rating**: 0–5 canonical scale. wakacje.pl ÷2, tui.pl as-is.
- **Board types**: Normalize via numeric `service` (wakacje) or `boardCode` (tui), never by localized string.
- **Concurrency**: Bounded `asyncio.Semaphore` (~10) for scrape fan-out in `app/jobs/coordinator`. `core` exposes single-unit async fns only.
- **Scoring**: CPU-bound numpy wrapped in `asyncio.to_thread()`.
- **Referral URLs**: All offer URLs get `utm_source=travellead` + referral params appended at `Offer` model validation time.
- **Share URLs**: Must start with `https://wakacje-travelis.pl/` (validated by `Offer` model).
- **Offer identity**: Semantic fingerprint hash (`OfferId` = first 32 hex chars of SHA-256). `CellId` = first 16 hex chars of SHA-256.

## Provider adapters

Clients: `httpx.AsyncClient`. Contracts reverse-engineered, documented in `docs/providers/`.

- wakacje.pl: `POST` search blob, `YYYY-MM-DD` dates, composite dedup key. Not yet implemented (only TUI exists).
- tui.pl: `tui-api-key` / `x-market` headers, `DD.MM.YYYY` dates, `boardCode` → board map, `offerUrl` prefixing.

## Exception hierarchy

All in `core/exceptions/`. Base: `CoreException` → `ProviderException` → specific types (`ProviderAPIException`, `InvalidOfferMetadataException`, `CountryNotFoundException`, `BoardTypeNotSupportedException`, `MinStarsNotSupportedException`, `PastDatesException`, `DateMismatchException`, `DurationMismatchException`).

## Infra

- Terraform (AWS provider ~> 5.0, `>= 1.5`) in `infra/environments/dev/`.
- Cursor IDE has plugins for Databases-on-AWS, AWS Serverless, Redis, Grafana Cloud, Deploy-on-AWS enabled.
