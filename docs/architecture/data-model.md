# Data Model

## Storage overview

| Store       | Role                                                              |
| ----------- | ----------------------------------------------------------------- |
| DynamoDB    | Durable entities: users, market cells, offers, user-offer matches |
| Redis Cloud | Ephemeral user offer feeds (paginated, sortable)                  |

No relational database in v1.

## DynamoDB tables

Four domain tables (provisioned capacity):

### `Users`

| Attribute           | Type    | Description                |
| ------------------- | ------- | -------------------------- |
| `user_id` (PK)      | String  | Cognito `sub`              |
| `preferences`       | Map     | Full preference document   |
| `push_enabled`      | Boolean | Web push opt-in            |
| `push_subscription` | Map     | Web Push subscription JSON |
| `created_at`        | String  |                            |
| `updated_at`        | String  |                            |

No `refresh_after` field and no GSI: debouncing is handled by EventBridge Scheduler one-time schedules (see [pipeline.md](pipeline.md#preference-debouncing-eventbridge-scheduler)), not by a polled timestamp.

`feed_version` lives in **Redis** (`user:{user_id}:feed_version`), not here — it is ephemeral feed-cache metadata, not durable user state.

### `MarketCells`

| Attribute          | Type   | Description                           |
| ------------------ | ------ | ------------------------------------- |
| `cell_id` (PK)     | String | Deterministic hash of cell dimensions |
| `country`          | String | ISO 3166-1 alpha-2                    |
| `month`            | String | `YYYY-MM`                             |
| `min_stars`        | Number |                                       |
| `board`            | String | Normalized board type                 |
| `adults`           | Number |                                       |
| `children`         | Number |                                       |
| `activation_count` | Number | Ref-count of users needing this cell  |
| `last_scraped_at`  | String |                                       |

There is **no status attribute or status GSI**. A cell exists in this table only when it is active (i.e. `activation_count > 0`). When a cell's `activation_count` drops to `0`, the row is deleted. To retrieve all active cells to scrape, perform a DynamoDB `Scan` (table size is small, bounded by active user configurations, typically < 1000 items).

**Cell ID computation:**

```
cell_id = sha256("{country}:{month}:{min_stars}:{board}:{adults}:{children}")[:16]
```

### `Offers`

Canonical attractive offers (post-scoring, deduplicated).

| Attribute                  | Type    | Description                                                                                                                                                                                                                                                                                 |
| -------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cell_id` (PK)             | String  | Market cell this offer belongs to                                                                                                                                                                                                                                                           |
| `offer_id` (SK)            | String  | Semantic fingerprint hash (globally unique)                                                                                                                                                                                                                                                 |
| `provider`                 | String  | `wakacje_pl` or `tui`                                                                                                                                                                                                                                                                       |
| `external_offer_id`        | String  | Provider-native ID (e.g. wakacje `offerId`, tui `offerCode`)                                                                                                                                                                                                                                |
| `hotel_name`               | String  |                                                                                                                                                                                                                                                                                             |
| `location`                 | String  | Stored in format `Country/Region/City`. **Normalization:** wakacje.pl `placeName` is already in `Country / Region / City` format (normalize separators to `Country/Region/City`); TUI is constructed from `breadcrumbs[0].label` (country) + `breadcrumbs[1].label` (region) + `city` field |
| `departure_airport`        | String  | IATA                                                                                                                                                                                                                                                                                        |
| `departure_date`           | String  | ISO date                                                                                                                                                                                                                                                                                    |
| `return_date`              | String  | ISO date                                                                                                                                                                                                                                                                                    |
| `duration`                 | Number  | Nights                                                                                                                                                                                                                                                                                      |
| `board`                    | String  | Normalized                                                                                                                                                                                                                                                                                  |
| `stars`                    | Number  |                                                                                                                                                                                                                                                                                             |
| `rating`                   | Number  | Canonical 0–5 scale. wakacje.pl ratings (0–10) are divided by 2 during ingest normalization. TUI ratings (0–5, TripAdvisor) are used as-is                                                                                                                                                  |
| `review_count`             | Number  |                                                                                                                                                                                                                                                                                             |
| `price_total`              | Number  | PLN                                                                                                                                                                                                                                                                                         |
| `price_per_day_one_person` | Number  | PLN; `price_total / duration / (adults + children)`                                                                                                                                                                                                                                         |
| `attractiveness_score`     | Number  | Stage 2 composite (used for sorting)                                                                                                                                                                                                                                                        |
| `referral_url`             | String  | travellead / provider deep link                                                                                                                                                                                                                                                             |
| `share_url`                | String  | Constructed automatically on save: `f"{settings.FRONTEND_URL}/offer/{cell_id}/{offer_id}"`. Appears in **both** list and detail API responses                                                                                                                                               |
| `scraped_at`               | String  |                                                                                                                                                                                                                                                                                             |
| `updated_at`               | String  |                                                                                                                                                                                                                                                                                             |
| `available`                | Boolean | Updated by daily availability job                                                                                                                                                                                                                                                           |
| `ttl`                      | Number  | Epoch seconds derived from `departure_date` (DynamoDB TTL)                                                                                                                                                                                                                                  |
| `metadata`                 | Map     | Internal/debug fields not surfaced in the feed (see [Offer metadata](#offer-metadata))                                                                                                                                                                                                      |

**Primary key (No GSIs):** `PK = cell_id`, `SK = offer_id`. The hot path (`jobs.match_users` reading all attractive offers for a set of cells) becomes a single `Query` per cell instead of a GSI lookup, and scrape upserts are `PutItem` on the composite key.

Because there are **no GSIs** on this table, searching for an offer by `offer_id` alone is not supported for unauthenticated or direct share lookups. To view details, the consumer must provide both the `cell_id` and the `offer_id` (reflected in the `share_url` format and the direct look-up API). For standard user feed hydration, the single-offer detail path uses the `cell_id` denormalized onto `UserOffers` (below) to issue a direct `GetItem(cell_id, offer_id)`.

> Hot-partition note: very popular cells (e.g. Greece / 4★ / AI / 2 adults) concentrate writes on one partition. At 3×-daily write volume with spread reads this is acceptable; revisit if throttling appears.

TTL: `ttl` attribute (epoch of `departure_date`) lets DynamoDB expire past trips automatically.

### `UserOffers`

User-to-offer matches with denormalized sort fields for Redis rebuild.

| Attribute       | Type   | Description                                                                                            |
| --------------- | ------ | ------------------------------------------------------------------------------------------------------ |
| `user_id` (PK)  | String |                                                                                                        |
| `offer_id` (SK) | String | References `Offers.offer_id`                                                                           |
| `cell_id`       | String | The offer's market cell — enables direct `GetItem` on `Offers(cell_id, offer_id)` for detail/hydration |
| `matched_at`    | String |                                                                                                        |

**Primary key:** `PK = user_id`, `SK = offer_id`. Sort/feed values are read from the `Offers` table (joined in Python via numpy/pandas) when rebuilding the feed, so they are not duplicated here beyond `cell_id`.

**Cascading Deletes & Self-Cleaning**: DynamoDB does not support native cascading deletes when offers are removed from the `Offers` table (due to TTL expiration or being marked unavailable). Instead, the system relies on eventual consistency: during the periodic 3×-daily scrape and match run, the match job queries the current active offers from `Offers` and syncs them with `UserOffers` (performing writes for new matches and deleting obsolete matches). Any expired or deleted offer is automatically pruned from `UserOffers` and the Redis feed.

## Offer identity

### Semantic fingerprint

Canonical `offer_id` is a hash of the trip semantics, not the provider's native ID:

```
fingerprint = sha256(join([
  normalize_hotel(hotel_name, country, region),
  departure_date,
  return_date,
  departure_airport,   # IATA
  board,               # normalized
  room_type,           # normalized
  adults,
  children,
]))
offer_id = fingerprint[:32]
```

### Deduplication and variant collapsing

Deduplication occurs at multiple levels to ensure a clean, unified feed with the best prices:

1. **Intra-Scrape Deduplication (Same Provider)**:
   - wakacje.pl often returns identical trips differing only in price or tour operator. During normalization, these are collapsed into one canonical offer.
   - We keep the variant with the **lowest `price_total`**.
   - All collapsed provider variants are stored in `metadata.sources[]`.
   - The top-level `external_offer_id` is set to the winning variant's ID.
   - Reference key fields for wakacje.pl variant matching: `offerHash`, `departureDate`, `returnDate`, `departurePlace`, `service`, `roomType`.

2. **Cross-Provider Deduplication (Fingerprint Collision)**:
   - When the same trip (same hotel, dates, airport, board, room, occupancy) is offered by both wakacje.pl and tui.pl, they compute to the same `offer_id`.
   - If they are processed in the same scrape batch, they are collapsed into a single canonical offer based on the lowest price, with both providers' details stored as separate entries in `metadata.sources[]`.

3. **Database-Level Deduplication (Cross-Scrape / Existing Offer in DB)**:
   - When a scraped offer is being saved, the system checks if an offer with the same `(cell_id, offer_id)` already exists in the `Offers` table.
   - If it exists, the system **merges** the existing and new items instead of performing a blind overwrite:
     - The existing item is loaded from DynamoDB.
     - The `sources` lists from both the existing and new offers are merged and deduplicated (using provider name and native ID).
     - The variant with the **lowest `price_total`** across all combined sources is selected as the winner.
     - The top-level offer fields (`price_total`, `price_per_day_one_person`, `provider`, `external_offer_id`, `referral_url`) are updated to reflect the winning variant.
     - The provider-specific metadata blocks (`metadata.wakacje_pl` and `metadata.tui`) are both preserved if variants from both providers exist in the merged sources list.
     - The `updated_at` and `scraped_at` timestamps are refreshed, and the merged offer is saved back to DynamoDB.

## Offer metadata

`metadata` holds fields needed for background jobs and provider-specific follow-up calls. None of it is returned in the user feed.

### Common keys (all providers)

| Key             | Type   | Description                                                                  |
| --------------- | ------ | ---------------------------------------------------------------------------- |
| `price_z_score` | Number | Stage-1 price z-score (debugging / attractiveness)                           |
| `sources[]`     | List   | Collapsed provider variants after dedup (lowest price wins on the top level) |

Each `sources[]` entry mirrors the provider-specific availability block below for that variant (same shape as `metadata.wakacje_pl` or `metadata.tui`).

### `metadata.wakacje_pl` (required for availability checks)

Persisted at **ingest** from the wakacje.pl search response (and airport catalog lookup). Together with the canonical offer columns (`external_offer_id`, `departure_date`, `return_date`, `duration`, `board`, `departure_airport`, plus cell `adults` / `children`), this must be sufficient to run the availability pipeline **without re-fetching the offer page HTML**.

| Key                 | Type   | Source (search / ingest)                                                                          | Role                                                                                                       |
| ------------------- | ------ | ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `hotel_id`          | Number | `hotelId`                                                                                         | `getCalculatorOfferVariants` payload, `checkOfferAvailability` headers                                     |
| `tour_operator_id`  | Number | `tourOperator`                                                                                    | `getCalculatorOfferVariants` payload (`tourId`)                                                            |
| `tour_op_code`      | String | `tourOpCode` (optional — may be absent on SSR)                                                    | `getCalculatorOfferVariants` (`tourOp`), `checkOfferAvailability` (`providerCode`) fallback                |
| `country_id`        | Number | `place.country.id`                                                                                | `checkOfferAvailability` query                                                                             |
| `region_id`         | Number | `place.region.id`                                                                                 | `checkOfferAvailability` query                                                                             |
| `city_id`           | Number | `place.city.id`                                                                                   | `checkOfferAvailability` query                                                                             |
| `departure_city_id` | Number | mapped from `departurePlace` via airport catalog                                                  | `getCalculatorOfferVariants` (`departureCityId`) — **not** the IATA on `departure_airport`                 |
| `service_id`        | Number | `service` (raw numeric board)                                                                     | `getCalculatorOfferVariants` (`serviceId`)                                                                 |
| `transport_id`      | Number | `departureType` (default `1` = flight)                                                            | `getCalculatorOfferVariants` (`transportId`)                                                               |
| `departure_slug`    | String | derived from `departurePlace` (e.g. `z-wroclawia`, `z-warszawy-chopin`)                           | Reconstructs the `od-...` URL selector; airport-specific slugs matter (Chopin ≠ Modlin ≠ generic Warszawa) |
| `offer_page_path`   | String | geo slugs + `urlName` + `offerId` (e.g. `/oferty/egipt/hurghada/hurghada/hotel-name-745287.html`) | `Referer` on API calls                                                                                     |

**Not stored** — resolved at check time:

- `offer_hash` (long room variant id): returned by `POST /v2/api/getCalculatorOfferVariants/{offerId}` for the stored configuration. The short `offerHash` from search (e.g. `GRCS:6935`) is not usable for live checks.

**Availability semantics** (see [pipeline.md](pipeline.md#availability-check-jobsavailability)):

1. `getCalculatorOfferVariants` with stored params + canonical dates/occupancy.
2. `offers: []` → configuration unavailable (`available = false`); skip step 3.
3. Otherwise `checkOfferAvailability` with the chosen variant's `id` as `offerHash`.

Canonical columns already cover: `external_offer_id` (= wakacje `offerId`), `departure_date`, `return_date`, `duration`, normalized `board`, `departure_airport` (IATA, feed-facing), and occupancy from the scrape cell (`adults`, `children`).

### `metadata.tui` (required for availability checks)

| Key          | Type   | Source      | Role                                         |
| ------------ | ------ | ----------- | -------------------------------------------- |
| `offer_code` | String | `offerCode` | `GET /api/www/hotel-cards/offers?offerCode=` |

(`external_offer_id` on the offer row should match `offer_code`.)

### Cross-provider matching

wakacje.pl and tui.pl offers are **not** merged across providers unless fingerprints collide (same hotel + dates + airport + board + room + occupancy). In practice they remain separate canonical offers.

## Redis Cloud keys

### Feed version

```
user:{user_id}:feed_version → integer
```

Incremented on every feed rebuild. Invalidates cached sort views.

### Lazy sort views (ZSET)

One ZSET per `(user, sort_field, sort_order, feed_version)`:

```
user:{user_id}:sort:{field}:{order}:v{version}  →  ZSET
  member: offer_id
  score:  normalized sort key (with tie-breaker)
```

Built lazily on first request for that sort. TTL: 24 hours.

**Score Construction and Tie-Breaking**: Redis ZSET scores must be double-precision floats. Because multiple offers can have identical sort values (e.g. same price or same rating), the score is constructed deterministically to embed a lexicographical tie-breaker:

- **Formula**: `score = primary_sort_value + (tie_breaker_fraction)`
- **Price Sort (`price_total` or `price_per_day`)**: `score = price + (hash_fraction)`
- **Attractiveness / Rating (`attractiveness_score`, `rating`)**: Since these are normalized values between `[0, 1]`, scale them: `score = (value * 1e8) + (hash_fraction)`.
- **Hash Fraction**: Calculated by taking the first 6 hexadecimal digits of `offer_id`, converting to an integer, and dividing by `1e7` (ensuring it is a small fractional addition `0.0000000` to `0.0016777`). This guarantees distinct scores and stable, deterministic sorting within Redis without relying on client-side sorting.

### Supported sort fields (v1)

| `sort` param               | Score source                |
| -------------------------- | --------------------------- |
| `attractiveness` (default) | `attractiveness_score` desc |
| `departure_date`           | epoch of departure_date     |
| `price_total`              | price_total                 |
| `price_per_day`            | price_per_day_one_person    |
| `rating`                   | rating                      |
| `duration`                 | duration nights             |

### Offer payload cache (optional)

```
user:{user_id}:offer:{offer_id} → JSON blob
```

Populated during feed rebuild for fast page hydration. Alternatively, batch-get from DynamoDB `Offers` table on read.

## Market cell activation

When user preferences change:

1. Compute old and new sets of required `cell_id` values.
2. Decrement `activation_count` on cells no longer needed.
3. Increment `activation_count` on newly required cells.
4. If a cell's `activation_count` drops to `0`, delete the cell row from `MarketCells` table.
5. If a cell's `activation_count` goes from `0` to `1` (new cell), create the cell row in `MarketCells` with `activation_count = 1` and `last_scraped_at = null`.

Only cells present in the `MarketCells` table are scraped on the 3× daily schedule.
