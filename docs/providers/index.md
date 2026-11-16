# API Integrations — Index

Entry point for all external provider integrations (for humans and AI agents).

## Runtime mappings

Adapters do not open the geo-catalog JSON files in this directory, and they do not call S3. Importing `core.providers.resources` reads three packaged files and keeps the dicts for the life of the process:

| File | Keys the adapter uses |
| ---- | --------------------- |
| [`country_registry.json`](../../src/core/providers/resources/country_registry.json) | `codes` — allow-list for preferences and TUI country labels |
| [`tui_filters.json`](../../src/core/providers/resources/tui_filters.json) | `destinationsCodes`, `board`, `minHotelCategory`, `departureAirports` |
| [`wakacjepl_filters.json`](../../src/core/providers/resources/wakacjepl_filters.json) | `countryId`, `service`, `departurePlaces` |

TUI search sends `departuresCodes: []` and `tripAdvisorRating = defaultTripAdvisorRating`. The `tripAdvisorRating` object in `tui_filters.json` is not read. After a row is mapped, it is kept only when its IATA is a key of `departureAirports`.

wakacje.pl search sends `query.departure: null` (any airport) and `service` from `service[board]`. `departurePlaces[IATA]` supplies `id` and `slug`. A missing id or slug drops that row. The id is stored as `metadata.wakacje_pl.departure_city_id`.

Checked-in catalogs (`*_geo_catalog.json`) are the input to the filter generators, which write the packaged files:

```bash
uv run python scripts/generate_tui_filters.py
uv run python scripts/generate_wakacjepl_filters.py
```

`scripts/fetch_geo_catalog.py` calls the provider, then reads `docs/providers/<provider>/<provider>_filters.json`. Those copies are not in the tree, so the command stops before it writes a catalog. Uploading either catalog to the Terraform geo-catalog bucket does not change a deployed function. The Lambda zip must contain the updated `src/core/providers/resources/*.json`.

## Offer Sources

| Provider   | Contract                             | Filters                                                                             | Geo catalog                                                        | Notes                                                                                                                        |
| ---------- | ------------------------------------ | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| wakacje.pl | [contract.md](wakacjepl/contract.md) | [wakacjepl_filters.json](../../src/core/providers/resources/wakacjepl_filters.json) | [wakacjepl_geo_catalog.json](wakacjepl/wakacjepl_geo_catalog.json) | POST search API; HTTP 200 + `success: false` envelope errors; parameter sensitivity in [contract probe section](wakacjepl/contract.md#contract-probe--parameter-sensitivity) |
| TUI        | [contract.md](tui/contract.md)       | [tui_filters.json](../../src/core/providers/resources/tui_filters.json)             | [tui_geo_catalog.json](tui/tui_geo_catalog.json)                   | POST search API, custom headers, DD.MM.YYYY dates                                                                            |
