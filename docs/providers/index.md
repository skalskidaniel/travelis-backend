# API Integrations — Index

Entry point for all external provider integrations (for humans and AI agents).

## Offer Sources

| Provider   | Contract                             | Filters                                                                             | Geo catalog                                                        | Notes                                                                                                                        |
| ---------- | ------------------------------------ | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| wakacje.pl | [contract.md](wakacjepl/contract.md) | [wakacjepl_filters.json](../../src/core/providers/resources/wakacjepl_filters.json) | [wakacjepl_geo_catalog.json](wakacjepl/wakacjepl_geo_catalog.json) | POST search API; HTTP 200 + `success: false` envelope errors; parameter sensitivity in [contract probe section](wakacjepl/contract.md#contract-probe--parameter-sensitivity) |
| TUI        | [contract.md](tui/contract.md)       | [tui_filters.json](../../src/core/providers/resources/tui_filters.json)             | [tui_geo_catalog.json](tui/tui_geo_catalog.json)                   | POST search API, custom headers, DD.MM.YYYY dates                                                                            |
