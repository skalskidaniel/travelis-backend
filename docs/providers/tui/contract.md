# TUI — Integration Contract

## Metadata

- Source: reverse-engineering `www.tui.pl`
- Last verified: 2026-01-28

## Auth / Client Identification

No classic OAuth/BasicAuth. The API functions as a "public" API used by the TUI frontend.

Headers:

- `tui-api-key: www`
- `x-market: pl`
- `x-market-language: pl`
- `x-market-currency: PLN`
- `x-app-id: <uuid>`
- `content-type: application/json;charset=UTF-8`

## Endpoints

### Offer List

- Method: `POST`
- URL: `https://www.tui.pl/api/services/tui-search/api/search/offers`

#### Headers

```http
accept: application/json
origin: https://www.tui.pl
referer: <! Encoded URL with query -->
tui-api-key: www
x-market: pl
x-market-language: pl
x-market-currency: PLN
```

#### Request Body

Date format: `DD.MM.YYYY`.

Filters are described in `filters.json`.

```json
{
  "childrenBirthdays": ["27.02.2021"],
  "departureDateFrom": "01.04.2026",
  "departureDateTo": "25.04.2026",
  "departuresCodes": ["POZ", "WAW"],
  "destinationsCodes": ["GR"],
  "durationFrom": 7,
  "durationTo": 10,
  "occupancies": [
    {
      "adultsCount": 2,
      "childrenBirthDates": [],
      "participantsCount": 2
    },
    {
      "adultsCount": 1,
      "childrenBirthDates": ["27.02.2021"],
      "participantsCount": 2
    }
  ],
  "numberOfAdults": 3,
  "offerType": "BY_PLANE",
  "filters": [
    { "filterId": "priceSelector", "selectedValues": [] },
    {
      "filterId": "board",
      "selectedValues": ["GT06-AI", "GT06-XX"]
    },
    { "filterId": "amountRange", "selectedValues": [] },
    {
      "filterId": "minHotelCategory",
      "selectedValues": ["4s"]
    },
    { "filterId": "flight_category", "selectedValues": [] },
    {
      "filterId": "tripAdvisorRating",
      "selectedValues": ["4t"]
    },
    {
      "filterId": "beach_distance",
      "selectedValues": ["defaultBeachDistance"]
    },
    { "filterId": "facilities", "selectedValues": [] },
    { "filterId": "WIFI", "selectedValues": [] },
    { "filterId": "sport_and_wellness", "selectedValues": [] },
    { "filterId": "room_type", "selectedValues": [] },
    { "filterId": "room_attributes", "selectedValues": [] },
    { "filterId": "hotel_chain", "selectedValues": [] },
    { "filterId": "airport_distance", "selectedValues": [] }
  ],
  "metaData": { "page": 0, "pageSize": 500, "sorting": "price" }
}
```

#### Response

```json
{
  "pagination": {
      "page": 0,
      "pageSize": 10,
      "totalResults": 2508,
      "sorting": "price",
      "pagesCount": 251
  },
  "offers": [
{
            "hotelCode": "<>",
            "hotelName": "<>",
            "city": "<>",
            "roomCode": "<>",
            "roomName": "<>",
            "hotelStandard": 4.0,
            "offerCode": "<>",
            "duration": 6,
            "durationText": "noclegów",
            "zoom": 8,
            "offerUrl": "/wypoczynek/<>",
            "breadcrumbs": [
                {
                    "label": "<country>",
                    "url": "/wypoczynek/<country>"
                },
                {
                    "label": "<city>",
                    "url": "/wypoczynek/<country>/<city>"
                },
                {
                    "label": "<hotel>"
                }
            ],
            "features": [],
            "discountFullPrice": "<>", // int
            "originalFullPrice": "<>", //int
            "discountPerPersonPrice": "<>", //int
            "originalPerPersonPrice": "<>", //int
            "departureDate": "16.04.2026",
            "returnDate": "22.04.2026",
            "departureTime": "19:45",
            "departureAirport": "Kraków",
            "latitude": 39.8757,
            "longitude": 18.2248,
            "imageUrl": "https://r.cdn.redgalaxy.com/scale/o2/TUI/hotels/BDS23000/w2425/29857469.jpg?dstw=268&dsth=266&srcw=268&srch=266&srcx=1/2&srcy=1/2&srcmode=3&type=1&quality=80",
            "boardType": "Śniadanie",
            "boardCode": "GT06-BB",
            "promotions": [
                {
                    "label": "Zaliczka 25%",
                    "description": "",
                    "promotionType": "OTHER",
                    "backgroundColor": "#3567F6",
                    "fontColor": "#ffffff"
                }
            ],
            "tripAdvisorRating": 4.2,
            "tripAdvisorReviewsNo": 544,
            "tripAdvisorReviewsText": "opinie",
            "participants": "2 Dorosłych + 0 Dzieci",
            "currency": "PLN",
            "priceCheckingAvailable": false,
            "onWishlist": false,
            "soldOut": false,
            "promoted": false,
            "gallery": [
                {
                    "url": "https://r.cdn.redgalaxy.com/scale/o2/TUI/hotels/BDS23000/w2425/29857469.jpg?dstw=1157&dsth=621&srcw=1157&srch=621&srcx=1/2&srcy=1/2&srcmode=3&type=1&quality=80",
                    "thumbnailUrl": "https://r.cdn.redgalaxy.com/scale/o2/TUI/hotels/BDS23000/w2425/29857469.jpg?dstw=268&dsth=266&srcw=268&srch=266&srcx=1/2&srcy=1/2&srcmode=3&type=1&quality=80",
                    "alt": "Masseria Le Pajare Włochy - Hotel",
                    "galleryItemType": "IMAGE"
                },
            ],
            "departureFlight": {
                "flightDuration": "1h 55min",
                "flightNumber": "2966",
                "airLineCode": "FR",
                "departure": {
                    "date": "16.04.2026",
                    "airportName": "Kraków",
                    "airportCode": "KRK",
                    "time": "19:45"
                },
                "arrival": {
                    "date": "16.04.2026",
                    "airportName": "Bari",
                    "airportCode": "BRI",
                    "time": "21:40"
                },
                "carrierName": "Ryanair",
                "segments": [
                    {
                        "flightNumber": "FR2966",
                        "airLineCode": "FR",
                        "departureDateTime": "2026-04-16T19:45:00",
                        "departureAirportName": "Kraków",
                        "departureAirportCode": "KRK",
                        "arrivalDateTime": "2026-04-16T21:40:00",
                        "arrivalAirportName": "Bari",
                        "arrivalAirportCode": "BRI",
                        "carrierName": "Ryanair",
                        "durationInMinutes": 115
                    }
                ],
                "bookingClass": "ECONOMY"
            },
            "returnFlight": {
                "flightDuration": "1h 55min",
                "flightNumber": "2723",
                "airLineCode": "FR",
                "departure": {
                    "date": "22.04.2026",
                    "airportName": "Bari",
                    "airportCode": "BRI",
                    "time": "08:10"
                },
                "arrival": {
                    "date": "22.04.2026",
                    "airportName": "Kraków",
                    "airportCode": "KRK",
                    "time": "10:05"
                },
                "carrierName": "Ryanair",
                "segments": [
                    {
                        "flightNumber": "FR2723",
                        "airLineCode": "FR",
                        "departureDateTime": "2026-04-22T08:10:00",
                        "departureAirportName": "Bari",
                        "departureAirportCode": "BRI",
                        "arrivalDateTime": "2026-04-22T10:05:00",
                        "arrivalAirportName": "Kraków",
                        "arrivalAirportCode": "KRK",
                        "carrierName": "Ryanair",
                        "durationInMinutes": 115
                    }
                ],
                "bookingClass": "ECONOMY"
            },
            "season": "S26",
            "priceAlert": false,
            "tags": [
                "LOW_COST",
                "LINEAR_FLIGHT"
            ]
        },
    "responseType": "NORMAL",
    "currency": "PLN"
  ]
}
```

## Field Mapping & Query Construction Notes

### Board Type

- **App → TUI (Request)**: The `tui_filters.json` dictionary defines values like `"board": { "all-inclusive": "GT06-AI GT06-XX", ... }`. Values are space-separated. Before sending a request to TUI, split them (by space) into a list of strings and pass them in the `selectedValues` array for the filter with `filterId: "board"`.
- **TUI → App (Response)**: The `boardCode` field from the TUI response is mapped to the canonical board type in the application:
  - `GT06-AI` / `GT06-XX` → `all-inclusive`
  - `GT06-FB` / `GT06-FBP` → `full-board`
  - `GT06-HB` / `GT06-HBP` → `half-board`
  - `GT06-BB` → `bed-and-breakfast`
  - `GT06-AO` → `none`

### Departure Airport Codes

TUI uses standard IATA codes directly in the `departuresCodes` array (e.g., `["POZ", "WAW", "KRK"]`). No lookup mapping is needed.

### Travel Dates vs Market Cell Bounds

Our canonical preference/cell model uses an explicit trip window:

- `departure_date` (trip start, inclusive)
- `return_date` (trip end, inclusive)

TUI search does not accept an explicit return-date bound. Instead, it accepts a departure window:

- `departureDateFrom`
- `departureDateTo`

This means a TUI result can have a valid `departureDate` but still have a `returnDate` outside the current market cell window.

**Required behavior for TUI ingest/matching:** after receiving offers, always enforce the canonical cell bounds in application code:

- `offer.departure_date` must be within the cell's departure window.
- `offer.return_date` must be within the cell's return window.

If either boundary fails, discard the offer for that cell (do not persist/match it under that market cell).

### Destination Codes / Geo Catalog

TUI exposes the destination tree and departure airports via the search bootstrap endpoint:

- `POST https://www.tui.pl/api/services/tui-search/api/gs/initial`
  - `filters` entry with `filterType: "REGION"` — countries and nested regions (or leaf single-destination countries such as `MLA` for Malta)
  - `filters` entry with `filterType: "AIRPORT"` — Polish departure airports

A minimal ID snapshot is checked in at [tui_geo_catalog.json](tui_geo_catalog.json) (~13 KB). Regenerate with:

```bash
uv run python scripts/fetch_geo_catalog.py --provider tui
```

Shape:

```json
{
  "generated_at": "…",
  "countries": { "GR": { "iso": "GR", "name": "Grecja" } },
  "regions": { "CHQ": { "country_code": "GR", "name": "Kreta" } },
  "departure_airports": { "KRK": { "code": "KRK", "name": "Kraków" } }
}
```

- `countries` — TUI destination code → ISO + display name (ISO enriched from `tui_filters.json` `destinationsCodes`)
- `regions` — TUI destination/region code → `country_code` + name (single-destination countries also appear here with `country_code` equal to their own code)
- `departure_airports` — IATA code → code + name

Use `destinationsCodes` / `departuresCodes` in search requests; there is no separate city level.

### Occupancy & Children

- Child birth date format expected by TUI: `DD.MM.YYYY`.
- The request includes:
  - `numberOfAdults`: number of adults from the search dimension.
  - `childrenBirthdays`: list of children's birth dates (format `DD.MM.YYYY`). When scraping for dimensions with children, use a representative birth date of an 8-year-old child (e.g., `01.01.<current_year-8>`).
  - `occupancies`: list of objects containing:
    - `adultsCount`: number of adults.
    - `childrenBirthDates`: list of children's birth dates (format `DD.MM.YYYY`).
    - `participantsCount`: `adultsCount` + number of children.

### Other Fields

- `offerUrl` must be prefixed with `https://www.tui.pl` (e.g., `https://www.tui.pl/wypoczynek/...`).
- Location in the application is normalized to `Country/Region/City`. It is derived from `breadcrumbs[0].label` (country), `breadcrumbs[1].label` (region), and either `breadcrumbs[2].label` (city) if present or the fallback `city` field. All slashes (`/`) in labels are normalized to `-`.

### Offer Availability

- `GET https://www.tui.pl/api/www/hotel-cards/offers?offerCode=<offerCode>`

Example response:

```json
{
  "message": "Wybrana oferta nie jest już dostępna.",
  "status": "UNAVAILABLE" // or "OK" if available
}
```
