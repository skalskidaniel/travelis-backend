# API Integrations — Index

Entry point for all external provider integrations (for humans and AI agents).

## Offer Sources

| Provider   | Contract                             | Filters                                                                             | Geo catalog                                                        | Notes                                                                                                                        |
| ---------- | ------------------------------------ | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| wakacje.pl | [contract.md](wakacjepl/contract.md) | [wakacjepl_filters.json](../../src/core/providers/resources/wakacjepl_filters.json) | [wakacjepl_geo_catalog.json](wakacjepl/wakacjepl_geo_catalog.json) | POST search API; HTTP 200 + `success: false` envelope errors; parameter sensitivity in [contract probe section](wakacjepl/contract.md#contract-probe--parameter-sensitivity) |
| TUI        | [contract.md](tui/contract.md)       | [tui_filters.json](../../src/core/providers/resources/tui_filters.json)             | [tui_geo_catalog.json](tui/tui_geo_catalog.json)                   | POST search API, custom headers, DD.MM.YYYY dates                                                                            |

## Adapter limits

The checked-in contracts describe the provider APIs. The adapters in `src/core/providers/` add their own stops. Both searches use page size 500. Wakacje.pl fetches at most pages 1–29. TUI fetches at most 30 pages (`page` 0–29). The shared HTTP client timeout is 15 seconds; TUI search overrides that one POST to 30 seconds. Anything the adapter drops or never requests is absent from the cell's stage-1 set, and a non-empty persist soft-deletes stored offers outside that set. Details: [pipeline.md](../architecture/pipeline.md#provider-search-bounds).
