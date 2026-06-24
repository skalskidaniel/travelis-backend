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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **travelis-backend** (1866 symbols, 3525 relationships, 108 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({search_query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.
- For security review, `explain({target: "fileOrSymbol"})` lists taint findings (source→sink flows; needs `analyze --pdg`).

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/travelis-backend/context` | Codebase overview, check index freshness |
| `gitnexus://repo/travelis-backend/clusters` | All functional areas |
| `gitnexus://repo/travelis-backend/processes` | All execution flows |
| `gitnexus://repo/travelis-backend/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
