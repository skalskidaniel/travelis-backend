# API Integrations — Index

Entry point for all external provider integrations (for humans and AI agents).

## Offer Sources

| Provider   | Contract                             | Filters                                                    | Notes                                                                                                                     |
| ---------- | ------------------------------------ | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| wakacje.pl | [contract.md](wakacjepl/contract.md) | [wakacjepl_filters.json](wakacjepl/wakacjepl_filters.json) | POST search API; per-offer availability via calculator + `checkOfferAvailability` (requires `metadata.wakacje` at ingest) |
| TUI        | [contract.md](tui/contract.md)       | [tui_filters.json](tui/tui_filters.json)                   | POST search API, custom headers, DD.MM.YYYY dates                                                                         |
