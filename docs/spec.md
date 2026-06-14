# Wymagania

## Social media

- [Instagram](https://www.instagram.com/wakacje.travelis/)
- [Facebook](https://www.facebook.com/profile.php?id=61583160197758)
- [TikTok](https://www.tiktok.com/@wakacje.travelis)

## Konto użytkownika

### Przechowywane informacje:

- Imię
- adres email
- preferencje

### Metody logowania:

- adres email (konieczne potwierdzenie maila)
- konto google
- konto facebook

### Usuwanie konta

Użytkownik może w dowolnej chwili usunąć wszystkie swoje dane.

## Preferencje uzytkowników

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

Mechanizm musi być asynchroniczny, aby uniknąć długiego oczekiwania na otrzymanie odpowiedzi z API.

Mechanizm szuka oferty tylko dla aktywnych użytkowników (takich, którzy zalogowali się w ciągu ostatnich 7 dni).

Backend dostaje sygnał raz na 10 minut aby pobrać nowe oferty dla oczekujących użytkowników.

Oczekujący użytkownik - użytkownik, dla którego ostatnie sprawdzenie nowych ofert nastąpiło wcześniej niż 2 godziny temu.

Wysyłane oferty nie mogą się powtarzać w panelu z ofertami.

Świeżo wysłane oferty nie mogą być wyprzedane.

Oferty starsze niż 14 dni są usuwane z konta użytkownika, chyba że są dodane do ulubionych.

Oferty z wakacje.pl często mają te same parametry, ale inną cenę i inne biuro podróży. W tej aplikacji muszą być traktowane jako ta sama oferta.

Pobrane oferty są analizowane statystycznie, aby zapewnić atrakcyjność oferty.

Aby moc porownywac oferty, dla kazdej kombinacji (kraj, miesiac podrozy, standard hotelu, wyżywienie) są zbierane oferty. Zebrane oferty mają zapisane: id oferty (aby sie nie powtarzaly) cenę za osobę na dzień, standard hotelu, typ wyżywienia, ocena hotelu, ilosc recenzji, miesiąc w którym jest pobyt. Reszta danych jest niepotrzebna do analizy atrakcyjności, zatem oszczędzamy miejsce w bazie danych.

Atrakcyjnosc ceny jest obliczana na podstawie zapisanych wczesniej ofert.

### Definicja atrakcyjności oferty

_Oferta musi w całości spełniać wymagania użytkownika_

_Atrakcyjność ceny jest liczona na podstawie „ceny za osobę za dzień” oraz porównania do historycznych ofert w tej samej komórce rynku (poza dokładną datą — daty są zaokrąglane do miesięcy wg miesiąca początku podróży)._

Definicje:

- $p$ — cena za osobę za dzień, tj. $p = \frac{(\text{cena całkowita}/\text{liczba osób})}{\text{liczba dni}}$
- Benchmark (zbiór porównawczy) — oferty z bazy dla kombinacji: $(kraj,\ miesiąc\ podróży,\ minimalny\ standard\ hotelu,\ wyżywienie)$
- $m$ — mediana wartości $p$ w benchmarku
- $MAD$ — median absolute deviation, tj. $MAD = median(|p_i - m|)$
- $z_r$ — robust z-score: $z_r = \frac{p - m}{1.4826 \cdot MAD}$

Oferta jest uznana za atrakcyjną cenowo, jeśli:

- $z_r \le -2$

Jeśli dana komórka rynku ma poniżej 200 ofert, powiększ tę komórkę o miesiąc poprzedni oraz następny. Jeśli to nie pomoże, miarą atrakcyjności oferty zamiast $z_r$ jest pozycja w top 10% ofertach

**Przykład 1:**

- Użytkownik chce wakacje w Grecji all-inclusive w 4 gwiazdkowym hotelu (lub lepszym) w dniach 14.06.2026-28.06.2026.
- Oferty pobrane dla niego są porównywane z wszystkimi oferatami zapisanymi w bazie z Grecji, 4 lub 5 gwiazdkowe hotele, w miesiacu czerwcu

**Przykład 2:**

- Użytkownik chce wakacje w Grecji all-inclusive w 4 gwiazdkowym hotelu (lub lepszym) w dniach 20.06.2026-3.07.2026.
- Oferty pobrane dla niego są porównywane z wszystkimi oferatami zapisanymi w bazie z Grecji, 4 lub 5 gwiazdkowe hotele, w miesiacu czerwcu

### Czynniki dodatkowo podbijające atrakcyjność oferty

1. Wysoka liczba wyświetleń oferty (popularność hotelu na podstawie offers_count)
2. Wysokie opinie (tylko wtedy, jeśli jest ponad 100 opinii)
3. Ilość wystawionych opinii

## Zbieranie danych przez dewelopera

1. Wysłane oferty do użytkowników (przechowywane 14 dni)
2. Kliknięcia w ofertę
3. Ilość odwiedzin strony
4. Odinstalowanie aplikacji PWA, tak aby bez potrzeby serwer nie wyszukiwał ofert dla nieaktywnych użytkowników
5. Logi do wykrywania błędów
6. Logi podsumowujące call mechanizmu wyszukiwania ofert (ile użytkowników obsłużono, ile ofert wysłano)
7. Oferty dodane do ulubionych przez użytkownika
