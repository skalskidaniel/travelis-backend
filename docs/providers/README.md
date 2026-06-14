# Dokumentacja integracji API (lokalnie)

Celem tego folderu jest trzymanie **lokalnej, wersjonowanej** dokumentacji integracji z zewnętrznymi serwisami (np. wakacje.pl, tui.pl, travellead). To jest „źródło prawdy” dla zespołu i dla agenta.

Dlaczego lokalnie?
- Linki do zewnętrznych docs potrafią się zmieniać albo znikać.
- Agent działa najlepiej na krótkich, konkretnych plikach z przykładami request/response.
- Możesz łatwo śledzić zmiany (git) i mieć historię kompatybilności.

## Struktura

- `docs/api/index.md` – spis integracji i szybkie linki.
- `docs/api/<provider>/contract.md` – opis kontraktu: endpointy, parametry, przykłady, błędy.
- `docs/api/<provider>/openapi.yaml` (opcjonalnie) – jeśli da się utrzymać OpenAPI jako formalną specyfikację.

## Zasady jakości (pod agenta)

- Krótkie sekcje, nagłówki H2/H3: "Auth", "Endpointy", "Przykłady", "Błędy", "Uwagi".
- Konkretne przykłady JSON (request/response) + statusy HTTP.
- Na górze pliku metadane: "Źródło URL", "Ostatnio zweryfikowano", "Zakres".
- Nigdy nie zapisuj sekretów: tokenów, kluczy API, cookies. Używaj placeholderów i `.env.example`.
