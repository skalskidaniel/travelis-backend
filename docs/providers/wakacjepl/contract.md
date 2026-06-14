# wakacje.pl — kontrakt integracji

## Metadane

- Źródło: reverse-engineering `www.wakacje.pl`
- Ostatnio zweryfikowano: 2026-01-28

## Auth / identyfikacja klienta

Brak klasycznego OAuth/BasicAuth.

## Endpointy

### Lista ofert

- Metoda: `POST`
- URL: `https://www.wakacje.pl/v2/api/offers`

#### Nagłówki

```http
accept: application/json
content-type: application/json
origin: https://www.wakacje.pl
referer: https://www.wakacje.pl/wczasy/?src=fromSearch
```

#### Request body

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

Uwagi do pól i formatów:

- Daty:
  - `departureDate` / `arrivalDate` mają format `YYYY-MM-DD`.
- Lotniska:
  - `query.departure` bywa `null` dla „dowolnego wylotu”; po zawężeniu spodziewana jest lista ID lotnisk (liczby), ale w JSON wysyłane jako stringi.
- Dzieci:
  - `rooms[].ages[]` to lista dat w formacie `yyyyMMdd`.

#### Słowniki / ID kierunków

Wakacje.pl wystawia „słowniki” do pobrania aktualnych ID:

- Kraje: `GET https://www.wakacje.pl/v2/api/geoCatalogCountries`
  - przykład: `Grecja` ma `value: "29"`.
- Regiony i miasta w kraju: `GET https://www.wakacje.pl/v2/api/geoCatalogRegionsAndCities/{countryId}`
  - przykład: `Kreta` w `Grecja (29)` ma `value: "29004"`.

Obserwacja z UI (wybór „Grecja → Kreta”):

- w `params.regionId` ląduje `"29004"`, natomiast `params.countryId` pozostaje puste,
- kraj rodzica bywa przekazywany w `params.alternative.countryId` (tu: `"29"`).

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

## Uwagi / pułapki

- Wakacje.pl często zwraca oferty o tych samych parametrach różniące się ceną lub biurem podróży — w wymaganiach aplikacji traktujemy je jako „tę samą ofertę”. Obecny provider nie deduplikuje, więc deduplikacja powinna być w warstwie agregacji.
- Klucz do identyfikacji oferty → klucz złożony, `offerHash + departureDate + returnDate + departurePlace + service + roomType`.
