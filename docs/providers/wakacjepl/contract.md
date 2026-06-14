# wakacje.pl — Integration Contract

## Metadata

- Source: reverse-engineering `www.wakacje.pl`
- Last verified: 2026-01-28

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
            "/no-index/hotel/kakkos-terra-blue-obiekt-1748805127-570-428.jpg",
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
- wakacje.pl returns `ratingValue` on a 0–10 scale. During ingest, divide by 2 to get the canonical 0–5 scale.
- Example: `ratingValue: 7.5` → `rating: 3.75`.

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
  - Storing remaining variants in `metadata.sources[]` for debugging/history purposes.
- Composite key for unique provider-level variant identification: `offerHash + departureDate + returnDate + departurePlace + serviceDesc + roomType`.
- Semantic fingerprint for `offer_id` is computed as described in [data-model.md](../../architecture/data-model.md#semantic-fingerprint).
