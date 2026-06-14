# Provider Integration Docs (Local)

This folder holds **locally versioned** documentation for external service integrations (e.g., wakacje.pl, tui.pl, travellead). This is the single source of truth for the team and for AI agents.

## Why local?

- External docs can change or disappear.
- AI agents work best with short, concrete files containing request/response examples.
- Changes are tracked via git, providing a compatibility history.

## Structure

- `docs/providers/index.md` — Integration index and quick links.
- `docs/providers/<provider>/contract.md` — Contract description: endpoints, parameters, examples, errors.
- `docs/providers/<provider>/openapi.yaml` (optional) — Formal OpenAPI spec if maintainable.
- `docs/providers/<provider>/<provider>_filters.json` — Filter/mapping dictionaries for request construction.

## Quality guidelines (agent-friendly)

- Short sections with H2/H3 headings: "Auth", "Endpoints", "Examples", "Errors", "Notes".
- Concrete JSON examples (request/response) with HTTP status codes.
- Metadata at the top of each file: "Source URL", "Last verified", "Scope".
- Never store secrets: tokens, API keys, cookies. Use placeholders and `.env.example`.
