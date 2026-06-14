# TraveLis Backend — Architecture Overview

TraveLis is a vacation deal aggregator. Users set trip preferences; the backend scrapes offers from [wakacje.pl](https://wakacje.pl) and [tui.pl](https://tui.pl), scores them statistically, and serves a personalized feed. Revenue comes from [travellead.pl](https://travellead.pl) referral links.

This document is the entry point for architecture documentation. Each linked file is self-contained and agent-friendly (short sections, concrete examples).

## Documentation map

| Document                                              | Contents                                                        |
| ----------------------------------------------------- | --------------------------------------------------------------- |
| [agent-guidelines.md](architecture/agent-guidelines.md)| **Mandatory rules for AI agents and engineers**                 |
| [requirements.md](architecture/requirements.md)       | Product requirements, preferences, supported countries/airports |
| [system-overview.md](architecture/system-overview.md) | Lambdalith layout, modules, runtime model                       |
| [code-structure.md](architecture/code-structure.md)   | Hexagonal layering, models, repositories, container, providers  |
| [data-model.md](architecture/data-model.md)           | DynamoDB tables, Redis keys, offer identity                     |
| [pipeline.md](architecture/pipeline.md)               | Scraping, scoring, matching, debouncing, schedules              |
| [attractiveness.md](architecture/attractiveness.md)   | Two-stage scoring algorithm                                     |
| [api.md](architecture/api.md)                         | REST API (`/api/v2/*`) contracts                                |
| [infrastructure.md](architecture/infrastructure.md)   | Terraform modules, AWS resources, Redis Cloud                   |

## Provider integrations

External API contracts live separately (reverse-engineered, versioned in git):

- [docs/providers/index.md](providers/index.md)

## Key architectural decisions

| Topic                | Decision                                                             |
| -------------------- | -------------------------------------------------------------------- |
| Deployment           | **Lambdalith** — single Lambda, FastAPI via Mangum                   |
| Code layering        | Hexagonal: `src/core` domain + adapters, `src/app` entrypoints       |
| Concurrency          | Async end-to-end (`aioboto3`); `asyncio` fan-out for scraping        |
| Scheduled jobs       | Dual entry handler; EventBridge invokes jobs in-process              |
| Cell scraping        | `asyncio` semaphore fan-out inside one invocation (bounded)          |
| Persistence          | DynamoDB (4 tables) + Redis Cloud (user offer feed)                  |
| Market cells         | Global cells with activation tracking                                |
| Offer identity       | Semantic fingerprint hash; `provider_id` stored separately           |
| Auth                 | Cognito in PWA; backend validates JWT; delete account via API        |
| Account provisioning | Cognito post-confirmation trigger creates `Users` + default cells    |
| Preference updates   | EventBridge Scheduler one-time `at(now+30s)`, debounced by overwrite |
| Matching             | Event-driven (Scheduler + post-scrape); no polling sweeper           |

## Repository layout

```
travelis-backend/
├── src/
│   ├── app/                  # Entrypoints only (controllers + job orchestrators)
│   │   ├── main.py           # FastAPI app + dual-entry Lambda handler
│   │   ├── auth/             # Delete account (Cognito cascade)
│   │   ├── user/             # Preferences, push settings
│   │   ├── offers/           # Paginated offer feed
│   │   └── jobs/             # Coordinator, match, availability (cron)
│   └── core/                 # Domain layer: models, providers, repositories,
│       │                     #   services (ingest, scoring, matching), container
│       ├── models/
│       ├── providers/
│       ├── repositories/
│       ├── services/
│       ├── config.py
│       └── container.py
├── infra/
│   ├── modules/          # lambda, dynamodb, cognito, eventbridge, …
│   └── environments/
│       └── dev/
└── docs/
    ├── architecture/     # This documentation set
    └── providers/        # External API contracts
```

See [code-structure.md](architecture/code-structure.md) for the full layering, dependency rules, and module responsibilities.

## Schedules

| Job                           | Frequency                               | Handler                                    |
| ----------------------------- | --------------------------------------- | ------------------------------------------ |
| Scrape active market cells    | 3× daily                                | `jobs.coordinator` → async scrape per cell |
| Availability / price check    | 1× daily                                | `jobs.availability`                        |
| Match users (debounced prefs) | On preferences change or after scraping | `jobs.match_users`                         |
