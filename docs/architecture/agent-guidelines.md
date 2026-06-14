# Agent Guidelines

**Mandatory Reading for AI Agents and Engineers**

This document serves as the absolute "rulebook" for writing code in the TraveLis backend. It centralizes all non-negotiable architectural boundaries, coding conventions, and deployment constraints. You must strictly adhere to these rules.

## 1. Strict Layering & Boundaries (`app` vs `core`)

The application follows a Hexagonal (Ports & Adapters) architecture, split between `src/app` (entrypoints) and `src/core` (domain).

- **Rule**: The `app` layer depends on the `core` layer.
- **Rule**: The `core` layer must **NEVER** import from the `app` layer.
- **Rule**: Feature modules within `app` (e.g., `app/offers` and `app/user`) must **NEVER** import each other.
- **Why**: This ensures the core business logic remains independent of AWS Lambda or FastAPI specifics, allowing orchestration mechanisms to be changed without rewriting domain code.

## 2. Absolute Imports Convention

- **Rule**: You must use absolute imports starting from the `src/` root directory.
  - ✅ **DO**: `from app.auth.controller import router`
  - ✅ **DO**: `from core.models.offer import Offer`
  - ❌ **DO NOT**: `from .controller import router`
  - ❌ **DO NOT**: `from auth.controller import router`
- **Why**: This prevents namespace pollution and ensures local execution matches the Lambda runtime, where the contents of `src/` are placed at the root.

## 3. Asynchronous Concurrency

The stack is `async` end-to-end to prevent blocking the event loop.

- **Rule**: API handlers (`FastAPI`) and Repositories (`aioboto3` / `redis.asyncio`) must use `async`/`await`.
- **Rule**: CPU-bound operations (e.g., NumPy array processing in the scoring service) must be wrapped in `asyncio.to_thread()`.
- **Rule**: Bounded concurrency. The orchestration logic in `app/jobs/coordinator` must use an `asyncio.Semaphore` to bound the fan-out of external scraping calls, preventing Lambda timeouts. The `core` layer must expose single-unit async functions and must not handle fan-out concurrency itself.

## 4. DynamoDB Data Model Constraints

DynamoDB tables are heavily optimized for access patterns. Do not "fix" these structures by adding relational concepts.

- **Rule**: The `Offers` table has **NO GSIs**. All offer reads must utilize the composite primary key: `PK = cell_id`, `SK = offer_id`.
- **Rule**: You cannot look up an offer using only `offer_id`. The application requires `(cell_id, offer_id)` to hydrate a single offer (hence denormalizing `cell_id` onto `UserOffers`).
- **Rule**: There is no status attribute for `MarketCells`. A cell exists if and only if its `activation_count > 0`. If `activation_count` reaches 0, the row must be deleted.

## 5. Event-Driven Matching

There is no continuous "sweeper" cron job polling for preference updates.

- **Rule**: Matching is strictly event-driven. It occurs only when triggered by:
  1. **Post-Scrape bulk match**: Initiated by `jobs.coordinator` after completing a scrape.
  2. **Debounced preference updates**: Changing user preferences sets a one-time EventBridge Scheduler task for `at(now + 30s)`.
- **Rule**: Do not add polled timestamps like `refresh_after` to the `Users` table.

## 6. Coding Standards

- **Rule**: Code must be strictly compliant with **Ruff**.
- Ensure code is correctly formatted and linted with `ruff` before finalizing any logic.

## 7. Composition Root Injection

- **Rule**: Do not instantiate clients or providers inside the `app` controllers directly. Use `core/container.py` as the composition root.
- **Rule**: AWS clients (`aioboto3`) are built as async context managers. The container enters them once per Lambda cold start, holding them open via an `AsyncExitStack`. Do not re-create boto3 sessions per request.

## 8. Rating Normalization

- **Rule**: The canonical `Offers.rating` is on a **0–5** scale.
- **Rule**: wakacje.pl returns ratings on a 0–10 scale. During ingest normalization, divide wakacje.pl `ratingValue` by `2`.
- **Rule**: TUI `tripAdvisorRating` is already on a 0–5 scale. Use as-is.
- **Why**: A unified scale ensures the attractiveness scoring algorithm and feed sorting produce correct, comparable results across providers.

## 9. Board Type Normalization

- **Rule**: Canonical board types are: `all-inclusive`, `full-board`, `half-board`, `bed-and-breakfast`, `none`.
- **Rule**: wakacje.pl normalization uses the numeric `service` field from the response (not the `serviceDesc` string). Inverse mapping: `1` → `all-inclusive`, `2` → `half-board`, `3` → `bed-and-breakfast`, `4` → `none`, `6` → `full-board`.
- **Rule**: TUI normalization uses `boardCode` from the response: `GT06-AI`/`GT06-XX` → `all-inclusive`, `GT06-FB`/`GT06-FBP` → `full-board`, `GT06-HB`/`GT06-HBP` → `half-board`, `GT06-BB` → `bed-and-breakfast`, `GT06-AO` → `none`.
- **Why**: Hardcoded string matching on localized labels (e.g. `"Śniadanie"`, `"All Inclusive Plus"`) is fragile and locale-dependent. Numeric/code-based mapping is deterministic.
