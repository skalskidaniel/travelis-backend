# AGENTS.md — TraveLis Backend

## First read

- **`docs/architecture/agent-guidelines.md`** — mandatory. Non-negotiable rules (layering, imports, rating/board normalization, etc).
- **`docs/architecture/`** — 9 docs covering requirements, system overview, code structure, data model, pipeline, scoring, API, infra.

## Project state

| Area | Status |
|---|---|
| `src/core/models/` | Built (Cell, Offer, RawOffer, common types) |
| `src/core/providers/` | Built (TUI + wakacje.pl adapters, Protocol port, resource JSON files) |
| `src/core/exceptions/` | Built (hierarchy under `CoreException`) |
| `src/core/services/` | **Not yet built** |
| `src/core/repositories/` | **Not yet built** |
| `src/core/config.py` | **Not yet built** |
| `src/core/container.py` | **Not yet built** |
| `src/app/{auth,offers,user}/` | Stub controllers (`router = APIRouter()`), empty `models.py` |
| `src/app/health/` | Empty directory |
| `src/app/jobs/` | **Not yet built** |
| `tests/` | Unit tests under `tests/core/models/` and `tests/core/providers/` |
| `.github/workflows/` | None |

## Key commands

```bash
uv sync                          # install deps (uv only; no pip/poetry)
uvicorn app.main:app --reload --port 8000 --app-dir src   # dev server
ruff check src/ tests/           # lint (no config file yet)
ruff format src/ tests/          # format
```

Python 3.13 required (`.python-version`). No type checker configured.

## Tests

```bash
pytest                           # runs all; pyproject.toml sets pythonpath = ["src"]
pytest -xvs tests/path/to/test   # single test file, verbose
pytest -k "test_name"            # filtered run
pytest -x --timeout=60           # with xdist: pytest -n auto
```

- Framework: `pytest` + `pytest-asyncio` (all async tests need `@pytest.mark.asyncio`).
- HTTP mocking: `respx` (used in provider tests to mock `httpx`).
- Integration tests: gated behind `RUN_INTEGRATION_TESTS=1` env var. Live provider tests hit real TUI/wakacje.pl APIs.
- No conftest.py; `pythonpath` set via `pyproject.toml`.

## Architecture rules (from code + agent-guidelines.md)

- **Hexagonal layering**: `src/app/` → `src/core/`. `core` never imports `app`. Feature modules in `app/` never import each other.
- **Absolute imports** from `src/` root: `from core.models.offer import Offer`, not relative.
- **Dual-entry handler**: `app.main` will dispatch HTTP (Mangum), EventBridge cron, Cognito triggers, and Scheduler one-time jobs.
- **Container**: `core/container.py` (not yet built) is the composition root, entered once per cold start via `AsyncExitStack`.
- **DynamoDB**: No GSIs on `Offers` table. Always query by `(cell_id, offer_id)`. `MarketCells` exist iff `activation_count > 0`.
- **Matching**: Event-driven only (post-scrape bulk + debounced per-user via EventBridge Scheduler `at(now+30s)`). No sweeper/poll.
- **Rating**: 0–5 canonical scale. wakacje.pl ÷2, tui.pl as-is.
- **Board types**: Normalize via numeric `service` (wakacje) or `boardCode` (tui), never by localized string.
- **Concurrency**: Bounded `asyncio.Semaphore` (~10) for scrape fan-out in `app/jobs/coordinator`. `core` exposes single-unit async fns only.
- **Scoring**: CPU-bound numpy wrapped in `asyncio.to_thread()`.
- **Referral URLs**: All offer URLs get `utm_source=travellead` + referral params appended at `Offer` model validation time.
- **Share URLs**: Must start with `https://wakacje-travelis.pl/` (validated by `Offer` model).
- **Offer identity**: `CellId` = first 16 hex chars of SHA-256. `OfferId` = first 32 hex chars of SHA-256.

## Provider adapters

Clients: `httpx.AsyncClient`. Contracts reverse-engineered, documented in `docs/providers/`.
Filter/registry JSON files live in `core/providers/resources/` (loaded at import time).

- **wakacje.pl**: `POST` search blob, `YYYY-MM-DD` dates, `service` (numeric) → board map. Two-step availability/price check (calculator + availability API).
- **tui.pl**: `tui-api-key` / `x-market` headers, `DD.MM.YYYY` dates, `boardCode` → board map, `offerUrl` prefixing.

Both `WakacjePlProvider` and `TuiProvider` implement `OfferProvider` Protocol from `base.py`.

## Exception hierarchy

`CoreException` → `ProviderException` → specific types (`ProviderAPIException`, `InvalidOfferMetadataException`, `CountryNotFoundException`, `BoardTypeNotSupportedException`, `MinStarsNotSupportedException`, `PastDatesException`, `DateMismatchException`, `DurationMismatchException`, `ProviderTimeoutException`, `TooManyRequestsException`).

All in `core/exceptions/`.

## Scripts

`scripts/` contains provider contract probes (`probe_wakacjepl_api_contract.py`, `generate_tui_filters.py`, etc). These are one-off reverse-engineering tools, not part of the app.

## Infra

- Terraform (AWS provider ~> 5.0, `>= 1.5`) in `infra/environments/dev/`.
- Currently only `geo_catalog` module deployed. AWS profile: `travelis-terraform`.
