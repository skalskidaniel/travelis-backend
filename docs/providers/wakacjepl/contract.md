# wakacje.pl — Integration Contract

## Metadata

- Source: reverse-engineering `www.wakacje.pl`
- Last verified: 2026-06-17

## Response envelope semantics

Wakacje.pl JSON APIs use a **two-layer** status model. Always inspect the JSON body — not only the HTTP status.

| Layer | Field | Meaning |
| ----- | ----- | ------- |
| Transport | HTTP status | Usually `200` even when the call logically failed |
| Application | `success` | `true` = envelope OK; `false` = logical failure |
| Application | `error.status` / `status` / `statusCode` | Inner status code (often `400`) when `success` is `false` |
| Application | `error.message` / `msg` | Human-readable or endpoint label (e.g. `getStoreBoxOffers`, `checkOfferAvailability`) |

**Search / calculator** failures observed in contract probing (2026-06-17):

- Most bad requests: **HTTP `200`**, `success: false`, `error.status: 400`.
- Structural breakage (e.g. removing `params.query`): occasionally **HTTP `500`** with no parseable JSON envelope.

**Availability** can return **HTTP `200`**, `success: false`, `msg: "checkOfferAvailability"`, `data: null` with **no** nested `error.status` — e.g. stale `offerHash`, sold-out variant, or upstream operator error. TraveLis treats this as `ProviderAPIException` when `success` is `false`.

Example (search, invalid `content-type`):

```json
{
  "success": false,
  "type": "error",
  "msg": "getStoreBoxOffers",
  "error": {
    "message": "Cannot read properties of undefined (reading 'params')",
    "status": 400
  },
  "data": null
}
```

Example (availability, logical failure without inner status):

```json
{
  "success": false,
  "type": "error",
  "msg": "checkOfferAvailability",
  "data": null
}
```

## Auth / Client Identification

No classic OAuth/BasicAuth.

## Endpoints

### Offer List

- Method: `POST`
- URL: `https://www.wakacje.pl/v2/api/offers`

#### Headers

```http
accept: application/json
content-type: application/json
origin: https://www.wakacje.pl
referer: https://www.wakacje.pl/wczasy/?src=fromSearch
```

#### Request Body

```json
[
  {
    "method": "search.tripsSearch",
    "params": {
      "brand": "WAK",
      "limit": 500,
      "priceHistory": 1,
      "imageSizes": ["570,428"],
      "flatArray": true,
      "multiSearch": true,
      "withHotelRate": 1,
      "withPromoOffer": 0,
      "recommendationVersion": "noTUI",
      "imageLimit": 1,
      "withPromotionsInfo": false,
      "type": "tours",
      "firstMinuteTui": false,
      "countryId": [],
      "regionId": [],
      "cityId": [],
      "hotelId": [],
      "roundTripId": [],
      "cruiseId": [],
      "searchType": "wczasy",
      "offersAttributes": [],
      "alternative": {
        "countryId": [],
        "regionId": [],
        "cityId": []
      },
      "qsVersion": "cx_v2_auction",
      "query": {
        "campTypes": [],
        "qsVersion": "cx_v2_auction",
        "qsVersionLast": 0,
        "tab": false,
        "candy": false,
        "pok": null,
        "flush": false,
        "tourOpAndCode": null,
        "obj_type": null,
        "catalog": null,
        "roomType": null,
        "test": null,
        "year": null,
        "month": null,
        "rangeDate": null,
        "withoutLast": 0,
        "category": false,
        "not-attribute": false,
        "pageNumber": 1,
        "departureDate": "2026-01-30",
        "arrivalDate": "2027-08-01",
        "departure": null,
        "type": [],
        "duration": {
          "min": 5,
          "max": 28
        },
        "minPrice": null,
        "maxPrice": null,
        "service": [],
        "firstminute": null,
        "attribute": [],
        "promotion": [],
        "tourId": null,
        "search": null,
        "minCategory": null,
        "maxCategory": 50,
        "sort": 13,
        "order": 1,
        "totalPrice": true,
        "rank": null, // to digit decimal from range [10-100] rounded to nearest 10 multiple
        "withoutTours": [],
        "withoutCountry": [],
        "withoutTrips": [],
        "rooms": [
          {
            "adult": 2,
            "kid": 0,
            "ages": [] // list of birthdays in format yyyyMMdd
          }
        ],
        "offerCode": null,
        "dedicatedOffer": false
      },
      "durationMin": "5"
    }
  }
]
```

#### Field Notes & Formats

- **Dates**:
  - `departureDate` / `arrivalDate` use format `YYYY-MM-DD`.
- **Airports**:
  - `query.departure` is `null` for "any departure"; when narrowed down, a list of airport IDs (numbers) is expected, but sent as strings in the JSON.
- **Children**:
  - `rooms[].ages[]` is a list of dates in format `yyyyMMdd`.

#### Dictionaries / Destination IDs

wakacje.pl exposes "dictionaries" to fetch current IDs:

- Countries: `GET https://www.wakacje.pl/v2/api/geoCatalogCountries`
  - Example: `Grecja` has `value: "29"`.
- Regions and cities within a country: `GET https://www.wakacje.pl/v2/api/geoCatalogRegionsAndCities/{countryId}`
  - Example: `Kreta` in `Grecja (29)` has `value: "29004"`.

A minimal ID snapshot is checked in at [wakacjepl_geo_catalog.json](wakacjepl_geo_catalog.json) (~80 KB). Regenerate with:

```bash
uv run python scripts/fetch_geo_catalog.py
```

Shape:

```json
{
  "generated_at": "…",
  "countries": { "99": { "iso": "MT", "name": "Malta" } },
  "regions": { "312597": { "country_id": "99", "name": "Wyspa Malta" } },
  "cities": {
    "99004948": { "country_id": "99", "region_id": "312597", "name": "Bugibba" }
  },
  "departure_airports": {
    "10119": {
      "iata": "WAW",
      "name": "Warszawa - Chopin",
      "slug": "z-warszawy-chopin"
    }
  }
}
```

- `countries` — `countryId` → ISO + display name
- `regions` — `regionId` → `country_id` + **name**
- `cities` — `cityId` → parent IDs + name (`checkOfferAvailability` / `metadata.wakacje_pl`)
- `departure_airports` — `departureCityId` → IATA, **name**, URL **slug** (`getCalculatorOfferVariants` / `metadata.wakacje_pl.departure_slug`)

Airport IDs are merged from [wakacjepl_filters.json](wakacjepl_filters.json) and `offerConfiguratorV2/filters` labels.

Observation from the UI (selecting "Grecja → Kreta"):

- `params.regionId` receives `"29004"`, while `params.countryId` remains empty.
- The parent country is sometimes passed in `params.alternative.countryId` (here: `"29"`).

> **Note:** For scraping purposes, only `countryId` is used (no `regionId` needed). Set `countryId` in `params.countryId` and leave `regionId` empty.

#### Response

```json
{
  "success": true,
  "type": "info",
  "msg": "getStoreBoxOffers",
  "datetime": "2026-01-28T14:12:03.038Z",
  "data": {
    "count": 2417,
    "qsSegment": "2|1|0|0|0|0",
    "offers": [
      {
        "id": 916232,
        "name": "Kakkos Terra Blue",
        "placeName": "Grecja / Kreta / Ierapetra",
        "photos": {
          "570,428": [
            "/no-index/hotel/kakkos-terra-blue-obiekt-1748805127-570-428.jpg"
          ]
        },
        "hotelId": 17001,
        "offerId": 916232,
        "urlName": "kakkos-terra-blue",
        "category": 5,
        "maxCategory": 5,
        "place": {
          "country": {
            "id": 29,
            "name": "Grecja",
            "slug": "grecja",
            "urlName": "grecja"
          },
          "region": {
            "id": 29004,
            "name": "Kreta",
            "slug": "kreta",
            "urlName": "kreta"
          },
          "city": {
            "id": 29011912,
            "name": "Ierapetra",
            "slug": "ierapetra",
            "urlName": "ierapetra"
          }
        },
        "duration": 7,
        "durationNights": 7,
        "price": 6148,
        "priceDiscount": 0,
        "priceOld": 0,
        "departureDate": "2026-04-26",
        "returnDate": "2026-05-03",
        "departureType": 1,
        "departureTypeName": "Samolot",
        "departurePlaces": ["Warszawa", "Katowice", "Wrocław"],
        "departurePlace": "Rzeszów",
        "returnDestinationPlace": "Heraklion",
        "service": 1,
        "serviceDesc": "All Inclusive Plus",
        "tourOperator": 1588,
        "tourOperatorName": "Grecos",
        "ratingString": "7.5",
        "ratingValue": 7.5,
        "ratingRecommends": 40,
        "ratingReservationCount": 40,
        "originalCurrency": "PLN",
        "shownCurrency": "PLN",
        "roomType": "Pokój standard z widokiem na morze",
        "offerType": "wypoczynek",
        "offerHash": "GRCS:6935",
        "tourOpCode": "GRCS",
        "objType": "H",
        "objCode": "HERKATE"
      }
    ]
  }
}
```

## Notes & Gotchas

### Hotel Stars (Category)

- wakacje.pl represents hotel standard as numbers multiplied by 10 (e.g., 3 stars = 30, 4 stars = 40, 5 stars = 50).
- In search parameters, pass `minCategory = min_stars * 10` and `maxCategory = 50`.

### Rating Normalization

- wakacje.pl returns `ratingValue` on a 0–10 scale. During ingest, divide by 2 and store the canonical one-decimal 0–5 `Rating`.
- Example: `ratingValue: 7.5` → `rating: 3.8`.

### Board Type Normalization

- Use the numeric `service` field from the response for board type mapping (not `serviceDesc`).
- Inverse mapping of `wakacjepl_filters.json`:
  - `1` → `all-inclusive`
  - `2` → `half-board`
  - `3` → `bed-and-breakfast`
  - `4` → `none`
  - `6` → `full-board`

### Occupancy & Children

- Child birth date format in the `ages` array: `yyyyMMdd` (e.g., `20210227`).
- The request passes an object in `query.rooms`:
  - `adult`: number of adults.
  - `kid`: number of children.
  - `ages`: list of children's birth dates (format `yyyyMMdd`). When scraping for dimensions with children, use a representative birth date of an 8-year-old child (e.g., `(current_year-8)0101`).

### Aggregation & Deduplication

- wakacje.pl often returns offers with the same parameters differing only in price or tour operator — per application requirements, these are treated as "the same offer". Deduplication is performed in the integration service layer (`core/services/ingest.py`).
- Deduplication involves:
  - Grouping offers by the same fingerprint.
  - Keeping the variant with the lowest `price`.
- Storing remaining variants in `metadata.sources[]` for debugging/history purposes. Each source entry includes a full `metadata.wakacje_pl` block (see below) so availability can be re-checked for any collapsed variant.
- Composite key for unique provider-level variant identification: `offerHash + departureDate + returnDate + departurePlace + serviceDesc + roomType`.
- Semantic fingerprint for `offer_id` is computed as described in [data-model.md](../../architecture/data-model.md#semantic-fingerprint).

## Offer availability

### Pipeline (no HTML scrape at check time)

If ingest persisted [metadata.wakacje_pl](../../architecture/data-model.md#metadatawakacje_pl-required-for-availability-checks), the daily job can check availability using only HTTP JSON APIs:

1. **Resolve room variant** — `POST /v2/api/getCalculatorOfferVariants/{offerId}`
2. **Live check** — `GET /v2/api/checkOfferAvailability` (only when step 1 returns variants)

Canonical offer columns supply `offerId` (`external_offer_id`), dates, duration, board, and occupancy. `metadata.wakacje_pl` supplies geo/operator/airport IDs.

### Step 1 — Calculator variants

- Method: `POST`
- URL: `https://www.wakacje.pl/v2/api/getCalculatorOfferVariants/{offerId}`

#### Headers

```http
accept: application/json
content-type: application/json
origin: https://www.wakacje.pl
referer: https://www.wakacje.pl/oferty/...  # metadata.wakacje_pl.offer_page_path
```

#### Request body

```json
{
  "adults": 2,
  "kids": 0,
  "infants": 0,
  "kidsAges": [],
  "serviceId": 1,
  "duration": 7,
  "departureDate": "2026-06-11",
  "transportId": 1,
  "departureCityId": 10119,
  "departureCityCode": "WMI",
  "hotelId": 2178,
  "tourOp": "VITX",
  "tourId": 17,
  "cruiseId": 0,
  "roundTripId": 0,
  "isAlternativeRoom": false,
  "isOffer77": false
}
```

| Field                          | Source in TraveLis                                                                                              |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| `offerId` (path)               | `Offers.external_offer_id`                                                                                      |
| `adults` / `kids` / `kidsAges` | scrape cell (`adults`, `children`; representative child ages per [pipeline.md](../../architecture/pipeline.md)) |
| `serviceId`                    | `metadata.wakacje_pl.service_id`                                                                                |
| `duration`                     | `Offers.duration`                                                                                               |
| `departureDate`                | `Offers.departure_date`                                                                                         |
| `transportId`                  | `metadata.wakacje_pl.transport_id`                                                                              |
| `departureCityId`              | `metadata.wakacje_pl.departure_city_id`                                                                         |
| `hotelId`                      | `metadata.wakacje_pl.hotel_id`                                                                                  |
| `tourId`                       | `metadata.wakacje_pl.tour_operator_id`                                                                          |
| `tourOp`                       | `metadata.wakacje_pl.tour_op_code` (optional — omit if absent)                                                  |

#### Response

```json
{
  "success": true,
  "data": {
    "offers": [
      {
        "id": "paFObzVUbnhuFqjOwvxb-jAAog4KHuC94PJ1Q6a...",
        "providerCode": "VITX",
        "roomDesc": "Rm standard room",
        "totalPrice": 4720,
        "priceCurrency": "PLN",
        "departStart": { "name": "Warszawa - Chopin", "date": "2026-06-18" }
      }
    ]
  }
}
```

- **`data.offers: []`** — exact configuration not sold (same as on-site _“Oferta w tej konfiguracji jest niedostępna”_). Treat as **unavailable**; do not call step 2.
- Variant `id` is the long **`offerHash`** required by step 2. The short search `offerHash` (e.g. `GRCS:6935`) is not valid here.

### Step 2 — Live availability

- Method: `GET`
- URL: `https://www.wakacje.pl/v2/api/checkOfferAvailability`

#### Query parameters

| Parameter                                        | Source                                                          |
| ------------------------------------------------ | --------------------------------------------------------------- |
| `providerCode`                                   | variant `providerCode`, else `metadata.wakacje_pl.tour_op_code` |
| `offerHash`                                      | variant `id` from step 1                                        |
| `offerType`                                      | `tour`                                                          |
| `includeTfgService`                              | `true`                                                          |
| `isAlternativeRoom`                              | `false`                                                         |
| `cityId` / `countryId` / `regionId`              | `metadata.wakacje_pl`                                           |
| `participantsObject[participants][n][birthDate]` | representative adult `1988-01-01`; children per scrape rules    |
| `participantsObject[participants][n][type]`      | `adult` / `child`                                               |

#### Headers

```http
accept: application/json
referer: https://www.wakacje.pl/oferty/...
customHeaders: {"Page-Source":"PO","Tour-Operator-Code":"VITX","Tour-Operator-Id":"17","Object-Id":"2178"}
```

#### Response (available)

```json
{
  "success": true,
  "data": {
    "availability": true,
    "status": "OK",
    "price": 4720,
    "currency": "PLN",
    "departureStringValue": "Kraków"
  }
}
```

Use `data.availability === true` and `data.status === "OK"`. Update `Offers.available` and `price_total` when changed.

### Departure airport IDs

URL slugs (`z-wroclawia`, `z-warszawy-chopin`) map to wakacje **city IDs**, not IATA codes. Airport-specific slugs must not be collapsed (Chopin `10119` ≠ generic Warszawa `278` ≠ Modlin `9758`). See `wakacjepl_filters.json` `departure` and ingest-time mapping from `departurePlace`.

Optional catalog: `POST /v2/api/offerConfiguratorV2/filters` with `{ "offerId": … }` lists valid `departurePlaces` for an offer.

## Contract probe — parameter sensitivity

Automated one-by-one mutation probe against live Wakacje.pl (2026-06-17).

- **Script:** `scripts/probe_wakacjepl_api_contract.py`
- **Artifact:** `scripts/artifacts/wakacjepl_contract_probe.json`
- **Baseline cell:** `GR`, `2026-07`, `min_stars=4`, `all-inclusive`, `adults=2`, `children=0`

For each endpoint the script sends a valid baseline request, then mutates every header and every body/query field individually:

1. **Remove** the field entirely.
2. **Invalidate** the value (wrong type / sentinel string).

A field is classified as:

| Classification | Remove tolerated | Invalid value tolerated | Integration implication |
| -------------- | ---------------- | ----------------------- | ----------------------- |
| **Required** | No | No | Must be present with a valid value |
| **Presence-required** | No | Yes | Key must exist; exact value may be loosely validated |
| **Valid-if-present** | Yes | No | May be omitted; if sent, must be correct |
| **Optional** | Yes | Yes | Cosmetic / defaulted server-side |

Logical success criteria used by the probe:

- **Search / calculator:** `success !== false` and `data.offers` is a list.
- **Availability:** `success !== false` and `data` is a dict.

Re-run after API changes:

```bash
uv run scripts/probe_wakacjepl_api_contract.py
```

### Search (`POST /v2/api/offers`)

Baseline: **150 mutations**, **30** changed logical outcome (baseline succeeded).

#### Headers

| Header | Classification | Notes |
| ------ | -------------- | ----- |
| `content-type` | Valid-if-present | Omit OK; invalid value → `success: false`, `error.status: 400` |
| `referer` | Valid-if-present | Omit OK; invalid value → logical failure |
| `accept` | Optional | |
| `origin` | Optional | |

#### Request body (RPC envelope)

| Field | Classification | Notes |
| ----- | -------------- | ----- |
| `method` | Optional | Must stay `search.tripsSearch` in production; probe invalid sentinel was tolerated |
| `params` | Valid-if-present | Top-level `params` object; invalidating entire block fails |
| `params.query` | **Required** | Removing breaks search (`HTTP 500` in probe) |
| `params.query.rooms` | **Required** | Occupancy block must be present |
| `params.query.rooms[].ages` | **Required** | Must be present (empty list when `kid: 0`) |
| `params.query.duration` | Presence-required | Object key required; probe tolerated invalid inner values |
| `params.query.attribute` | Presence-required | Key required; invalid value tolerated in probe |
| `params.cityId` | **Required** | Key must be present (use `[]` when not filtering by city) |
| `params.countryId` | Valid-if-present | Omit OK; invalid array content fails |
| `params.query.departureDate` | Valid-if-present | |
| `params.query.arrivalDate` | Valid-if-present | |
| `params.query.service` | Valid-if-present | Board filter IDs |
| `params.query.minCategory` | Optional | Star filter; probe tolerated removal |
| `params.query.sort` / `pageNumber` | Valid-if-present | |
| `params.query.departure` | Valid-if-present | `null` = any airport |
| `params.limit` | Valid-if-present | |
| `params.brand`, `flatArray`, `multiSearch`, `imageSizes`, `withPromoOffer`, `qsVersion`, `searchType`, `type`, `priceHistory`, `withHotelRate`, `withPromotionsInfo`, `recommendationVersion`, `firstMinuteTui`, `offersAttributes`, `alternative.*` | Optional | Branding / feature toggles |

> **Practical minimum for TraveLis search:** keep the full envelope shape from the adapter (`WakacjePlProvider._build_search_payload`). Do not drop `params.query`, `params.query.rooms`, `params.cityId`, or `params.query.rooms[].ages`. Send valid `content-type` and `referer` when calling the API.

### Calculator (`POST /v2/api/getCalculatorOfferVariants/{offerId}`)

Baseline: **42 mutations**, **10** changed logical outcome (baseline succeeded).

#### Headers

| Header | Classification |
| ------ | -------------- |
| `content-type` | Valid-if-present |
| `referer` | Valid-if-present |
| `accept`, `origin` | Optional |

#### Request body

| Field | Classification | Notes |
| ----- | -------------- | ----- |
| `departureDate` | **Required** | `YYYY-MM-DD` in calculator payload (adapter uses `yyyyMMdd` internally, formatted at send time) |
| `tourId` | **Required** | `metadata.wakacje_pl.tour_operator_id` |
| `kidsAges` | **Required** | Must be present (empty when `kids: 0`) |
| `adults` | Presence-required | Key required |
| `transportId` | Valid-if-present | |
| `departureCityId`, `departureCityCode`, `hotelId`, `serviceId`, `duration`, `kids`, `infants`, `tourOp`, `cruiseId`, `roundTripId`, `isAlternativeRoom`, `isOffer77` | Optional | Probe tolerated removal; keep populated values from ingest for correct variant matching |

> **Practical minimum:** never omit `adults`, `departureDate`, `tourId`, or `kidsAges`. Match occupancy and dates to the persisted offer / scrape cell.

### Availability (`GET /v2/api/checkOfferAvailability`)

Baseline in this probe run: **logical failure** (`success: false`, `msg: "checkOfferAvailability"`, `data: null`) even before mutations.

- **34 / 34** mutations also failed with the same envelope shape.
- Parameter **required vs optional** could not be determined from this run — sensitivity analysis needs a rerun where step 1 returns a live variant and the availability baseline returns `success: true` with `data.status: "OK"`.

Until a successful baseline probe exists, treat **all** documented query parameters and headers as required:

- Query: `providerCode`, `offerHash`, `offerType`, `includeTfgService`, `isAlternativeRoom`, `cityId`, `countryId`, `regionId`, full `participantsObject[…]` block.
- Headers: `accept`, `referer`, `customHeaders` (JSON with `Page-Source`, `Tour-Operator-Code`, `Tour-Operator-Id`, `Object-Id`).

TraveLis availability logic: `data.availability === true` **and** `data.status === "OK"`. A `success: false` envelope is an API error, not “sold out”.

### Ingest: fields to persist

On every wakacje.pl row normalized into `Offers`, populate `metadata.wakacje_pl` per [data-model.md](../../architecture/data-model.md#metadatawakacje_pl-required-for-availability-checks). Minimum required keys:

`hotel_id`, `tour_operator_id`, `country_id`, `region_id`, `city_id`, `departure_city_id`, `service_id`, `transport_id`, `departure_slug`, `offer_page_path`; `tour_op_code` when present in search results.
