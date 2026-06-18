# AGENTS.md — TraveLis Backend

## First read

- **`docs/architecture/agent-guidelines.md`** — mandatory. Non-negotiable rules (layering, imports, rating/board normalization, etc).
- **`docs/architecture/`** — 9 docs covering requirements, system overview, code structure, data model, pipeline, scoring, API, infra.

## Project state

| Area | Status |
|---|---|
| `src/core/models/` | Built (Cell, Offer, RawOffer, ScoredOffer, User, Preferences, common types) |
| `src/core/providers/` | Built (TUI + wakacje.pl adapters, `OfferProvider` Protocol, resource JSON files) |
| `src/core/exceptions/` | Built (`CoreException` → `ProviderException`/`RepositoryException` + specific types) |
| `src/core/services/` | Built (ingest, scoring pipeline with `StatisticalOfferScorer`) |
| `src/core/repositories/` | Built (DynamoDB adapters for cells, offers, users, user_offers; Redis feed repo) |
| `src/core/config.py` | **Not yet built** |
| `src/core/container.py` | **Not yet built** |
| `src/app/{auth,offers,user}/` | Stub controllers (`router = APIRouter()`), empty `models.py` |
| `src/app/health/` | Empty directory |
| `src/app/jobs/` | **Not yet built** |
| `tests/` | Unit tests for models, providers, services (ingest + scoring), repositories (DynamoDB + Redis via moto + fakeredis) |
| `.github/workflows/` | None |

## Key commands

```bash
uv sync                          # install deps (uv only; no pip/poetry)
uvicorn app.main:app --reload --port 8000 --app-dir src   # dev server
ruff check src/ tests/           # lint (no pyproject.toml [tool.ruff] section yet; uses defaults)
ruff format src/ tests/          # format
```

Python 3.13 required (`.python-version`). No type checker configured.

## Tests

```bash
pytest                           # runs all; pyproject.toml sets pythonpath = ["src"]
pytest -xvs tests/path/to/test   # single test file, verbose
pytest -k "test_name"            # filtered run
```

- Framework: `pytest` + `pytest-asyncio` (all async tests need `@pytest.mark.asyncio`).
- HTTP mocking: `respx` (used in provider tests to mock `httpx`).
- Repository tests: use `moto` (DynamoDB) + `fakeredis` in `tests/core/repositories/conftest.py`.
- Integration tests: gated behind `RUN_INTEGRATION_TESTS=1` env var. Live provider tests hit real TUI/wakacje.pl APIs.
- Provider URL consistency integration tests (`RUN_PROVIDER_INTEGRATION=1`) require Playwright Chromium:

```bash
uv run playwright install chromium
RUN_PROVIDER_INTEGRATION=1 pytest -xvs tests/core/providers/test_wakacjepl_integration.py -k referral_url
```

## Architecture rules (not in agent-guidelines.md)

- **Dual-entry handler**: `app.main` will dispatch HTTP (Mangum), EventBridge cron, Cognito triggers, and Scheduler one-time jobs.
- **Container**: `core/container.py` (not yet built) enters `aioboto3`/`redis.asyncio` clients once per cold start via `AsyncExitStack`.
- **Offer identity**: `CellId` = first 16 hex chars of SHA-256. `OfferId` = first 32 hex chars of SHA-256.
- **Referral URLs**: All offer URLs get `utm_source=travellead` + referral params appended at `Offer` model validation time.
- **Share URLs**: Must start with `https://wakacje-travelis.pl/` (validated by `Offer` model).
- **Feed**: Redis sorted sets built per-user; `FeedRepository` handles pagination with versioned ZSETs.

## Exceptions

`CoreException` → `ProviderException` (→ `ProviderAPIException`/`ProviderTimeoutException`/`TooManyRequestsException`, etc) + `RepositoryException` (→ `ItemNotFoundException`/`ConditionalCheckFailedException`/`WriteException`).

## Infra

- Terraform (AWS provider ~> 5.0, `>= 1.5`) in `infra/environments/dev/`.
- Currently only `geo_catalog` module deployed. AWS profile: `travelis-terraform`.

## Scripts

`scripts/` contains one-off provider contract probes (`probe_wakacjepl_api_contract.py`, `generate_tui_filters.py`, etc). Not part of the app.
