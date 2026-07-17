# Product Requirements

## Product summary

**TraveLis** is a PWA that finds bargain package holidays (flight + hotel) from wakacje.pl and tui.pl.

Users configure trip preferences and receive notifications when new matching deals appear. The developer earns revenue via travellead.pl referral links.

## Technology stack

| Layer              | Choice                                                                                                                                                                                                                      |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| API runtime        | AWS Lambda + Mangum + FastAPI (`async def` handlers)                                                                                                                                                                        |
| Concurrency        | Async end-to-end; `asyncio` worker pool for scrape fan-out                                                                                                                                                                  |
| Rate limiting      | FastAPI Limiter (async Redis)                                                                                                                                                                                               |
| Infrastructure     | Terraform (+ Vault provider for secrets)                                                                                                                                                                                    |
| Primary database   | DynamoDB (on-demand capacity for low operational overhead)                                                                                                                                                                  |
| Offer feed cache   | Redis Cloud                                                                                                                                                                                                                 |
| Scraping           | HTTP JSON APIs (no browser required for v1)                                                                                                                                                                                 |
| Statistics         | NumPy or pandas                                                                                                                                                                                                             |
| Logging            | AWS Lambda Powertools                                                                                                                                                                                                       |
| Monitoring         | Grafana (Sentry on frontend)                                                                                                                                                                                                |
| AWS SDK            | aioboto3 (async; aiobotocore under the hood)                                                                                                                                                                                |
| Authentication     | AWS Cognito                                                                                                                                                                                                                 |
| Availability check | Baseline: availability-by-absence (3× scrape). Optional 1× daily: TUI per-offer API; wakacje.pl two-step calculator API using `metadata.wakacje_pl` (see [contract](../providers/wakacjepl/contract.md#offer-availability)) |

CPU-bound scoring (numpy) runs via `asyncio.to_thread` so it never blocks the event loop.

**Not used in v1:** SQLModel/SQLAlchemy, ElastiCache.

## Implementation TODOs

### API & Infrastructure

- [ ] Implement CORS middleware (frontend origin whitelist)
- [ ] Implement health check endpoint (`/v2/health`)
- [ ] Ensure all API endpoints are mounted under `/api/v2`
- [ ] Validate proper use of RESTful HTTP status codes (`200`, `204`, `400`, `401`, `404`, `429`, `500`)

### Core Business Logic

- [ ] Implement preference change debouncing using EventBridge Scheduler one-time schedules (see [pipeline.md](pipeline.md))

### Scraping & Integration

- [x] Find a way to check wakacje.pl offer availability — verified in `notebooks/wakacje_pl_availability.ipynb` (`getCalculatorOfferVariants` + `checkOfferAvailability`). Pipeline integration pending; ingest must persist `metadata.wakacje_pl` (see [data-model.md](data-model.md#metadatawakacje_pl-required-for-availability-checks)).
- [x] Persist `metadata.wakacje_pl` on ingest for every wakacje.pl offer.
- [ ] Wire `jobs.availability` to the wakacje.pl JSON API (after metadata is populated).

## User preferences

Users can configure:

| #   | Field              | Constraints                                                                                  |
| --- | ------------------ | -------------------------------------------------------------------------------------------- |
| 1   | Countries          | Unlimited selection                                                                          |
| 2   | Departure airports | Unlimited selection (IATA codes; represented as an empty list `[]` for "Any")                |
| 3   | Travel dates       | Date range (as ISO 8601 strings `YYYY-MM-DD`)                                                |
| 4   | Occupancy          | Adults + children (children require birth dates formatted as `YYYY-MM-DD`). Single room only |
| 5   | Board type         | `all-inclusive`, `full-board`, `half-board`, `bed-and-breakfast`, `none`                     |
| 6   | Hotel standard     | Minimum stars (2–5) and minimum rating (0–5)                                                 |
| 7   | Stay length        | Minimum and maximum nights (the scraper queries `2–28` nights; matching filters user exact)  |

### Default preferences

| Field              | Default                             | Behavior / Representation                            |
| ------------------ | ----------------------------------- | ---------------------------------------------------- |
| Countries          | Greece, Italy, Spain, Turkey, Egypt | `["GR", "IT", "ES", "TR", "EG"]`                     |
| Departure airports | Any                                 | Represented as empty list `[]`                       |
| Travel dates       | Any                                 | Slid window: current month + next 5 months (6 total) |
| Occupancy          | 2 adults, 0 children                | `adults = 2`, `children = []`                        |
| Board type         | All-inclusive                       | `"all-inclusive"`                                    |
| Hotel stars        | 2                                   | `min_stars = 2, min_rating = 0`                      |
| Stay length        | Minimum 5 nights                    | `duration_min = 5, duration_max = null`              |

### Preference debouncing

Use **frontend debounce + EventBridge Scheduler coalescing**:

1. User changes preferences.
2. Backend saves the latest preferences immediately.
3. Backend upserts a one-time schedule named `match-{user_id}` for `at(now + 15s)` (not a new job per request).
4. Each subsequent change overwrites the schedule's fire time — multiple edits collapse into **one** match run.
5. After input stabilizes (~15s), the schedule fires once and matching runs with the latest saved preferences, then the schedule auto-deletes.

No polled `refresh_after` field and no sweeper job.

See [pipeline.md](pipeline.md) for implementation details.

## Supported departure airports

Stored as IATA codes:

| City         | IATA Code | Notes |
| ------------ | --------- | ----- |
| Berlin       | BER       |       |
| Bydgoszcz    | BZG       |       |
| Dresden      | DRS       |       |
| Gdańsk       | GDN       |       |
| Katowice     | KTW       |       |
| Kraków       | KRK       |       |
| Lublin       | LUZ       |       |
| Łódź         | LCJ       |       |
| Olsztyn      | SZY       |       |
| Ostrava      | OSR       |       |
| Poznań       | POZ       |       |
| Rzeszów      | RZE       |       |
| Szczecin     | SZZ       |       |
| Warsaw       | WAW/WMI   |       |
| Warsaw-Radom | RDO       |       |
| Wrocław      | WRO       |       |
| Zielona Góra | IEG       |

## Supported countries

Stored as ISO 3166-1 alpha-2; regions as ISO 3166-2 where applicable.

Albania (AL), Andorra (AD), Aruba (AW), Austria (AT), Bulgaria (BG), Croatia (HR), Curaçao (CW), Cyprus (CY), Montenegro (ME), Czech Republic (CZ), Denmark (DK), Dominican Republic (DO), Egypt (EG), France (FR), Greece (GR), Spain (ES), Jamaica (JM), Qatar (QA), Kenya (KE), Cuba (CU), Maldives (MV), Malta (MT), Morocco (MA), Mauritius (MU), Mexico (MX), Oman (OM), Portugal (PT), Senegal (SN), Seychelles (SC), Singapore (SG), Sri Lanka (LK), United States (US), Thailand (TH), Tunisia (TN), Turkey (TR), Hungary (HU), United Kingdom (GB), Vietnam (VN), Italy (IT), Cape Verde (CV), United Arab Emirates (AE), Switzerland (CH), Indonesia (ID), Tanzania (TZ).

## Offers

### Notifications

**v1 push:** generic message — _"New deals available"_(in Polish language) — sent after a match job when the user's feed changes. No offer count in the push payload.

In-app, the client can show how many offers are new since last open (client-side watermark or `feed_version` metadata from the API).

Server does **not** track per-offer seen state.

### Favorited Offers

Users can mark specific offers as "favorited". The server persists this state per user-offer pair as long as the underlying offer is still present in the `Offers` table. When an offer is soft-deleted as sold (`available = false`, 14-day TTL), matching keeps favorited `UserOffers` rows so favorites remain hydratable; non-favorited matches are pruned from the feed. Favorited rows are removed only after the Offer expires via DynamoDB TTL (hydration miss) or when the user unfavorites.

### Offer acquisition

- Sources: wakacje.pl and tui.pl public JSON APIs (see [providers/](../providers/index.md)).
- Scraping targets **active global market cells** (see [pipeline.md](pipeline.md)).
- When a user changes preferences, the backend updates which market cells are active.
- Scrape schedule: **4× daily**.
- Availability / price check: **4× daily**.
- Only statistically attractive offers are persisted (no per-cell quantity cap).
- wakacje.pl duplicates (same trip, different tour operator or price) are treated as **one offer** (see [data-model.md](data-model.md)).

### Statistical comparison groups

Offers are grouped for scoring by:

`(country, month, min_stars, board, adults, children)`

Only offers passing the attractiveness gate are written to DynamoDB. See [attractiveness.md](attractiveness.md).

### Attractiveness signals

| Signal                                   | v1 weight | Notes                                |
| ---------------------------------------- | --------- | ------------------------------------ |
| Price per day per person (Z-score / 2QR) | 0.4       | Primary deal detector (stage 1 gate) |
| Rating                                   | 0.4       | Stage 2 composite                    |
| Review count                             | 0.2       | Stage 2 composite                    |
| Departure time                           | —         | Optional, future                     |
| Distance to beach                        | —         | Optional, future                     |
| Distance to center                       | —         | Optional, future                     |
| Distance to airport                      | —         | Optional, future                     |

Weights are fixed constants in v1. AHP-based calibration is a future improvement.

## Rating normalization

Providers use different rating scales:

| Provider   | Native Scale | Source             |
| ---------- | ------------ | ------------------ |
| wakacje.pl | 0–10         | Provider ratings   |
| tui.pl     | 0–5          | TripAdvisor rating |

Canonical `Offers.rating` is on a **0–5 scale**. During ingest normalization, wakacje.pl ratings are **divided by 2** to map to the canonical scale. TUI ratings are used as-is.

## Board type normalization

Canonical board types: `all-inclusive`, `full-board`, `half-board`, `bed-and-breakfast`, `none`.

### wakacje.pl

Uses a numeric `service` field (inverse mapping from `wakacjepl_filters.json`):

| `service` value | Canonical board type |
| --------------- | -------------------- |
| 1               | `all-inclusive`      |
| 2               | `half-board`         |
| 3               | `bed-and-breakfast`  |
| 4               | `none`               |
| 6               | `full-board`         |

### tui.pl

Uses `boardCode` string values:

| `boardCode`           | Canonical board type |
| --------------------- | -------------------- |
| `GT06-AI`, `GT06-XX`  | `all-inclusive`      |
| `GT06-FB`, `GT06-FBP` | `full-board`         |
| `GT06-HB`, `GT06-HBP` | `half-board`         |
| `GT06-BB`             | `bed-and-breakfast`  |
| `GT06-AO`             | `none`               |
