# Code Structure

How the application code is organized internally. This is the source-of-truth for module boundaries, layering, and dependency direction.

## Layering: ports & adapters

The backend follows a **hexagonal (ports & adapters)** layout split across two top-level packages under `src/`:

| Package    | Role                                                                              |
| ---------- | --------------------------------------------------------------------------------- |
| `src/core` | Domain layer: models, ports (interfaces), infra adapters, and business algorithms |
| `src/app`  | Entrypoints only: FastAPI controllers and job orchestrators                       |

**Dependency rule:** `app` depends on `core`; `core` never imports `app`. Feature modules in `app/` never import each other.

The execution concerns live in `app/` (the `asyncio` fan-out, the Lambda deadline, HTTP status mapping). The pure domain logic (normalize, dedup, fingerprint, scoring, matching) lives in `core/`. This is what makes the "split jobs into a separate Lambda later" change a no-op for the domain, and what makes scoring/matching unit-testable without AWS.

The stack is **async end-to-end**: `async def` handlers, `aioboto3` repositories, `httpx.AsyncClient` providers, and `redis.asyncio` for the feed.

## Directory layout

```
src/
├── core/
│   ├── models/            # domain models (Cell, Offer, RawOffer, Preferences, UserOffer)
│   ├── providers/
│   │   ├── base.py        # Provider port (Protocol): async search(cell), check_availability(id)
│   │   ├── wakacjepl/     # wakacje.pl adapter directory
│   │   │   ├── main.py    # adapter + field mapping + API contracts
│   │   │   └── utils.py
│   │   └── tui/           # tui.pl adapter directory
│   │       ├── main.py    # adapter + field mapping + API contracts
│   │       └── utils.py
│   ├── repositories/
│   │   ├── base.py        # repository ports (Protocol)
│   │   ├── users.py
│   │   ├── cells.py
│   │   ├── offers.py
│   │   ├── user_offers.py # aioboto3 (DynamoDB) adapters
│   │   └── feed.py        # redis.asyncio feed (ZSET) adapter
│   ├── services/
│   │   ├── ingest.py      # normalize + dedup + fingerprint
│   │   ├── scoring.py     # two-stage attractiveness (pure, numpy)
│   │   ├── matching.py    # cell resolution + user filter + feed rebuild
│   │   ├── activation.py  # market-cell ref-counting
│   │   └── notifications.py
│   ├── exceptions/        # custom exceptions (CoreException, ProviderException, etc.)
│   ├── config.py          # pydantic-settings Settings
│   └── container.py       # composition root (see below)
└── app/
    ├── main.py            # FastAPI app + dual-entry Lambda handler
    ├── dependencies.py    # common API dependencies (auth validation, db session getters)
    ├── exceptions.py      # HTTP-facing custom exceptions (AppException, etc.)
    ├── auth/              # controller (def handlers) + request/response schemas
    ├── user/
    ├── offers/
    └── jobs/
        ├── __init__.py
        ├── coordinator.py    # scrape orchestrator (asyncio fan-out)
        ├── match_users.py    # user matching (per-user + bulk)
        ├── availability.py   # daily availability check
        └── score_offers.py   # two-stage attractiveness scoring
```

`src/` is the source root. The Lambda deployment artifact places the **contents** of `src/` at the artifact root, so `app` and `core` are importable as top-level packages and the handler is `app.main.handler`. Locally, run with `--app-dir src` (or `PYTHONPATH=src`).

### Python Import Conventions

To prevent import errors across local development, testing, and production Lambda runtimes, the project strictly adheres to absolute imports starting from the source root (`src/`):

- **Rule**: Always import using the full module path from `src/`.
  - **Correct**: `from app.auth.controller import router`
  - **Correct**: `from core.models.offer import Offer`
  - **Incorrect**: `from auth.controller import router` (relative to `app/`)
  - **Incorrect**: `from ..models.offer import Offer`
- **Pathing Rationale**: Sub-folders (like `src/app/` or `src/core/`) must never be added to Python's `sys.path`. This prevents namespace pollution and guarantees that local execution exactly mirrors the deployed Lambda environment.

## Models: two layers

We use **domain models + API schemas**. There is no separate dedicated "persistence model" class.

| Layer        | Location           | Purpose                                                              |
| ------------ | ------------------ | -------------------------------------------------------------------- |
| Domain model | `core/models`      | Canonical Pydantic types every service speaks                        |
| API schema   | `app/*/schemas.py` | Request/response DTOs (partial PATCH bodies, cursors, hidden fields) |

API schemas differ from domain models in real ways: partial `PATCH` bodies, the opaque pagination cursor, and hiding internal fields (`price_z_score`, `sources`, `cell_id`) from the feed response.

DynamoDB-specific concerns are owned by the **repository**, not a separate model:

- `float` ↔ `Decimal` conversion (DynamoDB rejects floats),
- composite key / GSI attribute construction,
- empty-string / `None` handling.

Rationale: a single shared model forces `Optional` everywhere and leaks storage details into the API; a standalone persistence model is boilerplate the repo can replace with a Decimal-aware `model_dump()`.

## Repositories: central in `core/repositories`

Repositories are centralized (not per-feature) because tables are shared:

- `app/offers` and `app/jobs/match_users` both touch `Offers` / `UserOffers`.
- The auth delete cascade touches all four tables plus Redis.

Centralizing keeps each table's access in one place, lets both the API and jobs depend on `core` only (never on each other), and keeps `app/` feature modules free of boto3.

## Composition root: `core/container.py`

FastAPI's `Depends` only covers the HTTP path; the EventBridge path never touches it. The container is the single place that constructs `Settings`, the shared `aioboto3` clients, the `redis.asyncio` client, provider adapters, and repositories **once per Lambda cold start** (module scope = reused across warm invocations).

- The **jobs handler** imports the container directly.
- The **API** wraps container objects in trivial `Depends` providers (e.g. `def get_offers_repo(): return container.offers_repo`), so controllers keep clean injection and tests can override.

`aioboto3` clients are **async context managers**. The container enters them once at cold start via an `AsyncExitStack` and holds the references for the life of the execution environment, reusing them across warm invocations rather than re-entering per request or per task.

## Provider abstraction

A `Provider` Protocol (`async search(cell) -> list[RawOffer]`, `async check_availability(offer) -> bool`), one adapter per site, behind a registry. All contract messiness is contained in the adapter and never leaks past `RawOffer`:

- wakacje.pl: `POST` search blob, `YYYY-MM-DD` dates, composite dedup key; ingest persists `metadata.wakacje_pl` for per-offer availability (`getCalculatorOfferVariants` + `checkOfferAvailability`).
- tui.pl: `tui-api-key` / `x-market` headers, `DD.MM.YYYY` dates, `boardCode` → board-type map, `offerUrl` prefixing.

Adding a third source later is one new adapter + one registry line. See [providers/](../providers/index.md) for the reverse-engineered contracts.

## Concurrency

The fan-out concurrency strategy lives in the orchestration layer (`app/jobs/coordinator`), not in `core`. `core` exposes `async`, single-unit functions with no shared mutable state; the coordinator schedules them on the event loop with a bounded `asyncio.Semaphore`. CPU-bound scoring is offloaded with `asyncio.to_thread` so it never blocks the loop. See [system-overview.md](system-overview.md#concurrency-model-for-jobs).

## Exception handling

The application uses custom, typed exception hierarchies to decouple layers, prevent raw client/dependency exceptions from leaking, and provide clean catch points.

- **`core/exceptions/`**:
  - `CoreException` (defined in `common.py`) is the base exception class for all errors arising in the domain or integration adapters.
  - Custom category-specific subclasses inherit from `CoreException` (e.g. `ProviderException` in `provider.py`, `RepositoryException` in `repository.py`, and `SchedulerException` in `scheduler.py`).
  - Implementation adapters (e.g., DynamoDB repository adapters or TUI/wakacje.pl providers) must wrap third-party/SDK client errors (such as `botocore.exceptions.ClientError` or `httpx.HTTPError`) in corresponding custom exceptions (like `ItemNotFoundException` or `ProviderAPIException`) before throwing them.
- **`app/exceptions.py`**:
  - `AppException` is the base for entrypoint-specific errors, particularly HTTP-facing API errors.
  - Subclasses represent specific failure scenarios (like `AuthenticationException` for JWT validation issues or `RetryableServiceException` for transient system errors).
- **Propagation & Translation**:
  - FastAPI controllers catch `core` exceptions (or custom `app` exceptions) either locally or via global `@app.exception_handler` decorators registered in `app/main.py`.
  - The handler translates the custom exception into a semantic HTTP response (e.g. mapping `AuthenticationException` to HTTP 401, or `RetryableServiceException` / `SchedulerException` to HTTP 503).
