# AGENTS.md — TraveLis Backend

## Mandatory Reading
- **`docs/architecture/agent-guidelines.md`**: Non-negotiable rules (layering, imports, normalization).
- **`docs/architecture/`**: System overview, data model, pipeline, scoring, API, infra.

## Rules & Conventions
- **Layering**: `app` (entrypoints) depends on `core` (domain). `core` NEVER imports `app`.
- **Imports**: Absolute imports from `src/` root only (e.g., `from core.models.offer import Offer`).
- **Async**: End-to-end `async`/`await`. Use `asyncio.to_thread()` for CPU-bound tasks.
- **DynamoDB**: No GSIs. Composite key: `PK=cell_id`, `SK=offer_id`.
- **Normalization**: 
  - Ratings: 0–5 scale (wakacje.pl / 2).
  - Boards: Canonical types only (map numeric/code-based).
- **Exceptions**: Use custom exceptions inheriting from `CoreException` or `AppException`.

## Key Commands
```bash
uv sync                          # Install dependencies
uvicorn app.main:app --reload    # Dev server (run from src/)
ruff check src/ tests/           # Lint
ruff format src/ tests/          # Format
```

## Tests
- **Run**: `uv run pytest` (uses `src/` as pythonpath).
- **Async**: All tests must be `@pytest.mark.asyncio`.
- **Integration**: Gated by `RUN_INTEGRATION_TESTS=1` or `RUN_PROVIDER_INTEGRATION=1`.
- **Mocks**: `respx` (HTTP), `moto` (DynamoDB), `fakeredis`.

## Architecture Gotchas
- **Identity**: `CellId` (16 hex chars), `OfferId` (32 hex chars) of SHA-256.
- **Referral URLs**: Append `utm_source=travellead` + params at `Offer` validation.
- **Container**: `core/container.py` is the composition root. Use `AsyncExitStack` for clients.
- **Matching**: Event-driven only (post-scrape or debounced preference updates).

## Infra & Scripts
- **Terraform**: `infra/environments/dev/`.
- **Scripts**: `scripts/` contains one-off contract probes (not part of app).
