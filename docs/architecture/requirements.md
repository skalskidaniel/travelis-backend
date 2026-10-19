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
| Availability check | Scrape soft-deletes offers missing from a cell's latest results (4× daily). A separate 4× daily job rechecks bookable offers via the TUI offer-code API and the wakacje.pl calculator + `checkOfferAvailability` APIs (see [contract](../providers/wakacjepl/contract.md#offer-availability)) |

CPU-bound scoring (numpy) runs via `asyncio.to_thread` so it never blocks the event loop.

**Not used in v1:** SQLModel/SQLAlchemy, ElastiCache.

## Implementation TODOs

### API & Infrastructure

- [ ] Implement CORS middleware (frontend origin whitelist)
- [ ] Implement health check endpoint (`/v2/health`)
- [x] API endpoints are mounted under `/v2` (API Gateway `$default` stage; no `/api` prefix)
- [ ] Validate proper use of RESTful HTTP status codes (`200`, `204`, `400`, `401`, `404`, `429`, `500`)

### Core Business Logic

- [ ] Implement preference change debouncing using EventBridge Scheduler one-time schedules (see [pipeline.md](pipeline.md))

### Scraping & Integration

- [x] Find a way to check wakacje.pl offer availability — verified in `notebooks/wakacje_pl_availability.ipynb` (`getCalculatorOfferVariants` + `checkOfferAvailability`). Pipeline integration pending; ingest must persist `metadata.wakacje_pl` (see [data-model.md](data-model.md#metadatawakacje_pl-required-for-availability-checks)).
- [x] Persist `metadata.wakacje_pl` on ingest for every wakacje.pl offer.
- [ ] Wire `jobs.availability` to the wakacje.pl JSON API (after metadata is populated).

## User preferences

Users can configure:

| #   | Field              | Constraints                                                                                                                                          |
| --- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Countries          | Up to 20 codes from [`country_registry.json`](../../src/core/providers/resources/country_registry.json) `codes`. An empty list activates no cells.   |
| 2   | Departure airports | Up to 17 codes matching `^[A-Z]{3}$`. Empty list `[]` means any airport at match time. The code is stored even when no provider catalog emits it. |
| 3   | Travel dates       | Optional `YYYY-MM-DD`. When both are set, `date_to` is on or after `date_from`. See [month windows](#month-windows).                                 |
| 4   | Occupancy          | `adults` 1–6. `children` is up to 5 birth dates (`YYYY-MM-DD`). `adults + len(children)` is at most 8. Single room only.                             |
| 5   | Board type         | One or more of `all-inclusive`, `full-board`, `half-board`, `bed-and-breakfast`, `none`. A JSON string is stored as a one-element list.              |
| 6   | Hotel standard     | `min_stars` 2–5. `min_rating` 0–5 with one decimal place.                                                                                            |
| 7   | Stay length        | `duration_min` ≥ 2 (default 5). `duration_max` is null or ≥ `duration_min`. The scraper queries 2–28 nights; matching applies the user's bounds.    |

### Default preferences

| Field              | Default                             | Behavior / Representation                            |
| ------------------ | ----------------------------------- | ---------------------------------------------------- |
| Countries          | Greece, Italy, Spain, Turkey, Egypt | `["GR", "IT", "ES", "TR", "EG"]`                     |
| Departure airports | Any                                 | Represented as empty list `[]`                       |
| Travel dates       | Any                                 | Slid window: current month + next 5 months (6 total) |
| Occupancy          | 2 adults, 0 children                | `adults = 2`, `children = []`                        |
| Board type         | All-inclusive                       | `["all-inclusive"]`                                  |
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

`PATCH /v2/user/preferences` and first-time provisioning still return `200` when `schedule_match` raises `SchedulerException` (missing `LAMBDA_FUNCTION_ARN` or `SCHEDULER_ROLE_ARN`, or an EventBridge create/update error). Preferences and cell counts are already saved. The next scrape whose cells overlap this user runs `bulk_match_users`.

### Month windows

`resolve_months_for_range` (`core/services/activation.py`) turns dates into `YYYY-MM` buckets. The reference date is today unless a caller passes one (matching's self-heal uses that).

| `date_from` | `date_to` | Months activated |
| ----------- | --------- | ---------------- |
| null        | null      | Reference month and the next 5 months (6 total). |
| set         | null      | Start month through start month + 5. A `date_from` before the reference date is clipped to the reference date first. |
| null        | set       | Reference month through `date_to`'s month. |
| set         | set       | Clipped start month through `date_to`'s month, inclusive. |

A `date_to` before the clipped start still activates that start month. A `date_to` many months ahead activates every month in the span. Each month is crossed with every selected country and every selected board.

Example with reference date `2026-06-15` (covered by `tests/unit/core/services/test_activation.py`): open dates yield `2026-06` through `2026-11`; `date_from=2026-05-01` and `date_to=2026-07-10` yield `2026-06` and `2026-07`; `date_from=2026-08-10` and `date_to` null yields `2026-08` through `2027-01`.

`generate_required_cells` emits one `MarketCell` per `(country, month, board, min_stars, adults, len(children))`. The cell stores the child **count**. Birth dates are applied later, during matching.

A default user (5 countries, open dates, one board) activates 30 cells. Selecting all 5 boards multiplies that by 5.

## Supported departure airports

Preference validation accepts any 3-letter uppercase IATA code. Ingest keeps an offer only when that code is in the provider catalog below. Matching then compares the user's list to `offer.departure_airport`.

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
| Warsaw        | WAW       |       |
| Warsaw-Modlin | WMI       |       |
| Warsaw-Radom  | RDO       |       |
| Wrocław       | WRO       |       |
| Zielona Góra  | IEG       |       |

wakacje.pl `departurePlaces` contains every code in this table. tui.pl `departureAirports` omits `BER`, `DRS`, `IEG`, `OSR`, and `SZY`, so those airports appear only on wakacje.pl offers.

## Supported countries

`UserPreferences` accepts only keys of `codes` in [`country_registry.json`](../../src/core/providers/resources/country_registry.json). `IC` (Canary Islands) and `UK` (United Kingdom) are registry codes.

| Code | Name | wakacje.pl search | tui.pl search |
| ---- | ---- | ----------------- | ------------- |
| AE | United Arab Emirates | no | yes |
| AL | Albania | yes | yes |
| AT | Austria | yes | yes |
| BG | Bulgaria | yes | yes |
| CV | Cape Verde | yes | yes |
| CW | Curaçao | yes | yes |
| CY | Cyprus | yes | yes |
| CZ | Czech Republic | yes | yes |
| DE | Germany | yes | yes |
| DK | Denmark | yes | yes |
| DO | Dominican Republic | yes | yes |
| EG | Egypt | yes | yes |
| ES | Spain | yes | yes |
| FR | France | yes | yes |
| GR | Greece | yes | yes |
| HR | Croatia | yes | yes |
| IC | Canary Islands | no | yes |
| ID | Indonesia | yes | yes |
| IT | Italy | yes | yes |
| JM | Jamaica | yes | yes |
| KE | Kenya | yes | yes |
| LK | Sri Lanka | yes | yes |
| MA | Morocco | yes | yes |
| ME | Montenegro | yes | yes |
| MT | Malta | yes | yes |
| MU | Mauritius | yes | yes |
| MV | Maldives | yes | yes |
| MX | Mexico | yes | yes |
| OM | Oman | no | yes |
| PT | Portugal | yes | yes |
| SC | Seychelles | yes | yes |
| SG | Singapore | yes | yes |
| SN | Senegal | yes | yes |
| TH | Thailand | yes | yes |
| TN | Tunisia | yes | yes |
| TR | Turkey | yes | yes |
| UK | United Kingdom | no | yes |
| US | United States | yes | yes |
| VN | Vietnam | yes | yes |

`AE`, `IC`, `OM`, and `UK` are absent from wakacje.pl `countryId`. `WakacjePlProvider.search` raises `CountryNotFoundException`. The coordinator retries that provider 3 times, logs the failure, and still ingests TUI results for the cell.

## Offers

### Notifications

**v1 push:** one randomly chosen Polish template, sent only when a match **inserts** new `UserOffers` rows and push is enabled. Payload is `{ "title", "body" }` — no offer ids or counts.

| Title            | Body                              |
| ---------------- | --------------------------------- |
| Nowe oferty!     | Sprawdź aplikację!                |
| Nowe wycieczki!  | Zobacz najatrakcyjniejsze opcje!  |
| Nowe okazje!     | Zobacz zanim znikną!              |

The server does **not** track per-offer seen state. It does track a session boundary: authenticated requests refresh Redis `user:{id}:session` (default 30-minute gap). When a new session starts, `Users.new_since` becomes the previous `last_active_at`. `GET /v2/offers?new=true` returns offers whose `UserOffers.matched_at` is at or after that cutoff. `feed_version` still tells the client that the feed was rebuilt.

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
