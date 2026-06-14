# Data Pipeline

End-to-end flow from scraping to user feed.

## Pipeline stages

```mermaid
flowchart TD
    EB1[EventBridge 3x daily] --> COORD[jobs.coordinator]
    COORD --> SCRAPE[Async scrape per active cell]
    SCRAPE --> NORM[Normalize + deduplicate]
    NORM --> SCORE[jobs.score_offers]
    SCORE --> DDB[(Offers table)]
    COORD -->|on completion| MATCH[jobs.match_users]
    MATCH --> UO[(UserOffers table)]
    MATCH --> REDIS[(Redis feed rebuild)]
    MATCH --> PUSH[Web Push notification]
    EB3[EventBridge 1x daily] --> AVAIL[jobs.availability]
    AVAIL --> DDB
    PATCH[PATCH /user/preferences] --> PREFS[(Users table)]
    PATCH --> CELLS[Update cell activation]
    PATCH --> SCHED[Upsert one-time Scheduler at now+30s]
    SIGNUP[Cognito post-confirmation] --> PROV[Create Users row + activate cells]
    PROV --> SCHED
    SCHED -->|fires once| MATCH
```

Matching is **event-driven** — there is no constant poll. Two independent triggers feed `jobs.match_users` (see [Trigger sources](#trigger-sources)).

## Market cells

### Definition

A global market cell is identified by:

```
(country, month, min_stars, board, adults, children)
```

- `country` — ISO 3166-1 alpha-2
- `month` — `YYYY-MM` (derived from user date range)
  - **Travel Month Expansion**: If a user's date range spans multiple months, they activate cells for all months overlapping that range. If the user's travel dates are not configured ("Any"), they activate cells for the current month and the next 8 months (9 months total).
- `min_stars`, `board`, `adults`, `children` — from user preferences

This same tuple is used for **scraping**, **statistical comparison**, and **scoring**.

### Activation and Decoupling Model

Cells are global — not per-user. When any user's preferences require a cell, `activation_count` increments. Scraping runs once per active cell regardless of how many users share it.

To keep cell scraping decoupled from user-specific details (and avoid expensive queries to find active users during scraping):
1. **Departure Airports**: Scraper requests are always sent with "Any" departure airport. User-specific departure airport preferences are applied as filters on the backend during the user matching phase.
2. **Duration / Stay Length**: Scraper requests query a wide default range of `2-28` nights. Exact min/max duration filters are applied during the user matching phase.
3. **Representative Child Age**: Providers require birth dates to calculate prices. Because global cells only track the *number* of children, cells with `children > 0` are scraped using a representative child age of **8 years old** (birth date calculated as January 1st of `current_year - 8`). Exact matching filters on child ages are applied in Python during matching.

### Coordinator (`jobs.coordinator`)

Triggered 3× daily by EventBridge.

1. Scan the `MarketCells` table (all rows are active by definition — a cell exists only when `activation_count > 0`).
2. Schedule one async scrape task per cell with bounded concurrency (`asyncio.Semaphore` ~10).
3. Each task calls wakacje.pl and tui.pl APIs (see [providers/](../providers/index.md)).
4. Pass raw results to normalization → scoring → `Offers` table.

The semaphore/fan-out lives in the orchestrator; per-cell work calls `async` `core` functions, and CPU-bound scoring is offloaded via `asyncio.to_thread`. See [system-overview.md](system-overview.md#concurrency-model-for-jobs).

## Scrape → normalize

Per provider response:

1. Map provider fields to canonical offer schema.
2. Compute semantic fingerprint → `offer_id`.
3. **wakacje.pl dedup:** collapse rows with same fingerprint; keep lowest price.
4. Attach `cell_id` from the scrape context.
5. Forward to scoring.

## Scoring (`jobs.score_offers`)

See [attractiveness.md](attractiveness.md).

Only offers passing stage 2 are written to `Offers`. Existing offers for the same `offer_id` are upserted (price, availability, score may change).

## User matching (`jobs.match_users`)

### Trigger sources

There is **no 2-minute sweeper**. Two distinct events drive matching:

| Trigger           | Cause               | Mechanism                                                                        |
| ----------------- | ------------------- | -------------------------------------------------------------------------------- |
| Per-user re-match | preferences changed | EventBridge Scheduler one-time schedule `at(now + 30s)`, debounced by overwrite  |
| Bulk re-match     | new offers scraped  | `jobs.coordinator`, on completion, matches users of the affected (updated) cells |

### Preference debouncing (EventBridge Scheduler)

On `PATCH /api/v2/user/preferences`:

1. Save latest preferences to `Users`.
2. Update market cell activation (increment/decrement).
3. **Upsert** a one-time schedule named `match-{user_id}` with `ScheduleExpression = at(now + 30s)` and `ActionAfterCompletion: DELETE`.

**Coalescing:** the schedule name is deterministic (`match-{user_id}`), so each edit simply overwrites the fire time — repeated edits collapse into **one** match run 30s after the last edit. No polling, no `refresh_after` field, no GSI.

**Target:** the schedule invokes the lambdalith with payload `{ "type": "match_user", "user_id": "..." }` (handled by the dual-entry handler).

**Race handling:** if a PATCH lands while a match is mid-run, the run used near-current preferences and the new PATCH has already scheduled another run in 30s — eventual consistency without an explicit compare-and-swap.

### Match logic

For each claimed user:

1. Load preferences.
2. Resolve required `cell_id` set.
3. Query `Offers` for those cells.
4. Filter in Python using the user's exact preferences:
   - Match departure airports (if list is not empty `[]`).
   - Match exact stay duration bounds (`duration_min` to `duration_max`).
   - Match travel date range (`date_from` to `date_to`).
   - Match minimum TripAdvisor rating (`min_rating`).
   - Match children exact ages/birthdays (re-checking suitability if children are present).
5. **Sync `UserOffers` rows**:
   - Query existing `UserOffers` keys for the user.
   - Diff the new matches against the old matches.
   - Batch-delete obsolete matches and batch-write new matches (limits DynamoDB write churn).
6. Rebuild Redis feed (increment `feed_version`, invalidating cached ZSETs).
7. If push enabled and feed changed → send generic _"New deals available"_ notification (in Polish language).

## Availability check (`jobs.availability`)

Triggered 1× daily.

Baseline is **availability-by-absence**, which works for both providers without a per-offer endpoint: an offer no longer returned by the latest scrape of its cell is marked `available = false`, and the `departure_date` TTL eventually removes it.

Optional refinement for fresher availability _between_ scrapes:

- **tui.pl:** `GET /api/www/hotel-cards/offers?offerCode={provider_id}` (returns `OK` / `UNAVAILABLE`).
- **wakacje.pl:** no clean per-offer endpoint — use scraper to mock the browser and check whether the site says available.

Update `Offers.available` and `price_total` when they change.

## Redis feed rebuild and lazy ZSET pagination

### Lazy ZSET Building

The ZSET is built lazily on the first `GET /api/v2/offers` request for a specific sort field and order:

1. Retrieve the user's current `feed_version` from the key `user:{user_id}:feed_version`.
2. Check if ZSET key `user:{user_id}:sort:{field}:{order}:v{version}` exists in Redis.
3. If not cached:
   - Query all `UserOffers` for the `user_id` from DynamoDB.
   - Batch-get corresponding offers from the `Offers` table using their `(cell_id, offer_id)` keys.
   - Sort the offers in Python by the requested field and order, and calculate unique ZSET scores (see [data-model.md](data-model.md#lazy-sort-views-zset)).
   - Write the members (`offer_id`) and their computed scores to the ZSET key with a TTL of 24 hours.
4. Paginate using the ZSET:
   - If `order == desc`, execute `ZREVRANGEBYSCORE` or `ZRANGE ... REV`.
   - If `order == asc`, execute `ZRANGEBYSCORE` or `ZRANGE`.

### Cursor-Based Pagination

- **Cursor Structure**: The cursor is a base64-encoded JSON string:
  ```json
  {
    "offset": 20,
    "feed_version": 42
  }
  ```
- **Query Resolution**:
  - The API decodes the cursor and reads the limit (default `20`).
  - If the cursor's `feed_version` matches the current `feed_version` in Redis, fetch ZSET elements from index `offset` to `offset + limit - 1`.
  - If the `feed_version` does not match, the feed has changed. The API resets the request to page 1 (`offset = 0`), rebuilds the ZSET, and returns the new `feed_version` in the response, allowing the client to reset pagination and reload the feed.

## Error handling

| Failure                        | Behavior                                                                                               |
| ------------------------------ | ------------------------------------------------------------------------------------------------------ |
| Provider timeout               | Retry up to 3× per cell per run; log and continue                                                      |
| Scoring error for one offer    | Skip offer; log                                                                                        |
| Match job failure for one user | EventBridge Scheduler retry policy (max attempts → DLQ); next PATCH or post-scrape run also re-matches |
| Lambda timeout approaching     | Coordinator stops spawning new tasks; resume next cron                                                 |

## Future escape hatch

If active cell count exceeds single-Lambda capacity:

- Split `app/jobs/` into separate Lambda functions.
- Replace the in-process `asyncio` fan-out with Lambda async invoke per cell.

Domain logic in `core/` remains unchanged.
