# Wymagania

## Technologie

- AWS Lambda + Mangum
- FastAPI + FastAPI Limiter
- Terraform + Terraform Vault
- DynamoDB z trybem provisioned aby ograniczyć koszty
- SQLModel lub SQLAlchemy
- Redis cache (pobieranie ofert użytkownika)
- Scrapy oraz scrapy-playwright lub crawlee
- Numpy lub pandas
- AWS Powertools logging
- Grafana (Sentry dla front endu)
- AWS Boto3 dla dostępu do bazy danych
- AWS Cognito

## TODO's

- CORS Middleware
- Health Check
- Wszystkie endpointy zaczynające się od /api/v2
- Odpowiednie kody odpowiedzi RESTfulAPI
- Debouncing zmian preferencji

```text
Recommended pattern
In your case, the best design is usually frontend debounce + backend coalescing. Debounce on the client reduces unnecessary API calls, and backend coalescing makes the system safe even if the client sends multiple requests anyway because of retries, multiple tabs, or race conditions.
medium +1
How it should work
Use this flow:
1. User changes trip preferences.
2. Backend saves the latest preferences immediately.
3. Instead of recomputing offers right away, schedule a refresh job for that user/trip with a debounce key like tripId or userId+tripId.
4. If another change arrives before the delay expires, update the scheduled job time instead of creating a new one.
5. Only when no more changes arrive for, say, 2 to 10 seconds, run filtering once using the latest saved preferences. inngest
That is backend debouncing in practice: one delayed job per entity, continuously postponed until the input stabilizes.
```


### Użytkownik może wybrać:

1. Kraj (nielimitowana ilość)
2. Lotnisko startowe (nielimitowana ilość)
3. Daty podróży
4. Ilość osób dorosłych oraz dzieci (potrzebne daty urodzenia dzieci). Rezerwacja zawsze dla jednego pokoju (brak obsługi wielu pokoi).
5. Typ wyżywienia (all-inclusive, full-board, half-board, bed-and-breakfast, none)
6. Minimalny standard hotelu (2-5 gwiazdek) oraz minimalna ocena (0-5)
7. Długość pobytu (minimalna i maksymalna ilość dni)

### Domyślne preferencje:

1. Grecja, Włochy, Hiszpania, Turcja, Egipt
2. Dowolne
3. Dowolne
4. 2 dorosłych, 0 dzieci
5. all-inclusive
6. 2 gwiazdki
7. Domyślnie min. 5 dni

### Obsługiwane lotniska

Lotniska są przechowywane w kodach IATA

- Berlin
- Bydgoszcz
- Drezno
- Gdańsk
- Katowice
- Kraków
- Lublin
- Łódź
- Olsztyn
- Ostrawa
- Poznań
- Rzeszów
- Szczecin
- Warszawa
- Warszawa-Radom
- Wrocław
- Zielona Góra

### Obsługiwane kraje

Kraje są przechowywane w kodach ISO 3166-1 alpha-2 oraz regiony w ISO 3166-2

- Albania
- Andorra
- Aruba
- Austria
- Bulgaria
- Croatia
- Curacao
- Cyprus
- Montenegro
- Czech Republic
- Denmark
- Dominican Republic
- Egypt
- France
- Greece
- Spain
- Jamaica
- Qatar
- Kenya
- Cuba
- Maldives
- Malta
- Morocco
- Mauritius
- Mexico
- Oman
- Portugal
- Senegal
- Seychelles
- Singapore
- Sri Lanka
- United States
- Thailand
- Tunisia
- Turkey
- Hungary
- United Kingdom
- Vietnam
- Italy
- Cape Verde
- United Arab Emirates
- Switzerland

## Oferty

### Powiadomienie o ofertach

Powiadomienie powinno zawierać informacje, ile nowych ofert od ostatniego uruchomienia aplikacji czeka na przejrzenie.

### Metoda pozyskiwania ofert

Oferty są pobierane poprzez API wakacje.pl oraz tui.pl

Mechanizm szuka oferty dla aktywnych komórek marketu (gdy użytkownik zmienia preferencje, backend musi dodać do bazy danych aktywne komórki marketu)

Backend dostaje sygnał 3 razy dziennie aby pobrać nowe oferty.

Oferty są sprawdzane pod kątem dostępności/zmian cen raz dziennie.

W bazie danych są zapisywane tylko atrakcyjne oferty, bez limitu ilości na jedną komórkę marketu.

Oferty z wakacje.pl często mają te same parametry, ale inną cenę i inne biuro podróży. W tej aplikacji muszą być traktowane jako ta sama oferta.

Pobrane oferty są analizowane statystycznie, aby zapewnić atrakcyjność oferty.

Aby moc porownywac oferty, dla kazdej kombinacji (kraj, miesiac podrozy, standard hotelu, wyżywienie, ilosc doroslych, ilosc dzieci) są zbierane oferty.

Atrakcyjność oferty jest obliczana na podstawie nowo pobranych ofert, tylko te które spełniają kryterium atrakcyjności są zapisywane na dysku.

### Definicja atrakcyjności oferty

- Z-score
- Cena/dzień/osoba mieszcząca się w 2QR (waga 0.4 lub ustawić za pomocą algorytmu AHP)
- Ocena (waga 0.4 lub ustawić za pomocą algorytmu AHP)
- Ilość recenzji (waga 0.2 lub ustawić za pomocą algorytmu AHP)
- Godziny wylotu opcjonalnie
- Odległość od morza opcjonalnie
- Odległość od centrum opcjonalnie
- Odległość od lotniska opcjonalnie
