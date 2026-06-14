# Tui — kontrakt integracji

## Metadane

- Źródło: reverse-engineering `www.tui.pl`
- Ostatnio zweryfikowano: 2026-01-28

## Auth / identyfikacja klienta

Brak klasycznego OAuth/BasicAuth. API działa jako „publiczne” API wykorzystywane przez frontend TUI.

Nagłówki:

- `tui-api-key: www`
- `x-market: pl`
- `x-market-language: pl`
- `x-market-currency: PLN`
- `x-app-id: <uuid>`
- `content-type: application/json;charset=UTF-8`

## Endpointy

### Lista ofert

- Metoda: `POST`
- URL: `https://www.tui.pl/api/services/tui-search/api/search/offers`

#### Nagłówki

```http
accept: application/json
origin: https://www.tui.pl
referer: <! Zakodowany url z zapytaniem -->
tui-api-key: www
x-market: pl
x-market-language: pl
x-market-currency: PLN
```

#### Request body

Format dat: `DD.MM.YYYY`.

Filtry opisane w `filters.json`

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
            "childrenBirthDates": [
                "27.02.2021"
            ],
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

Uwagi do mapowania pól:

- `offerUrl` musi być prefixowane z `http://tui.pl/`
- `boardCode` jest mapowane na typ wyżywienia po stronie aplikacji:
  - `GT06-AI` / `GT06-XX` → `All inclusive`
  - `GT06-FB` / `GT06-FBP` → `FB`
  - `GT06-HB` / `GT06-HBP` → `HB`
  - `GT06-BB` → `BB`
  - `GT06-AO` → `None`
- Lokalizacja w aplikacji pochodzi z `breadcrumbs[0].label` (kraj) i `breadcrumbs[1].label` (region).

### Dostępność oferty

- `GET https://www.tui.pl/api/www/hotel-cards/offers?offerCode=<offerCode>`

Przykładowa odpowiedź:

```json
{
    "message": "Wybrana oferta nie jest już dostępna.",
    "status": "UNAVAILABLE" // lub "OK" jeśli dostępna
}
```