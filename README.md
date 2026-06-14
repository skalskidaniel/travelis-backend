# Omówienie projektu

**TraveLis - nazwa marketingowa**

Aplikacja PWA, której zadaniem jest znajdywanie okazyjnych ofert na wakacje (lot + hotel) ze strony [wakacje.pl](https://wakacje.pl) oraz [tui](https://tui.pl)

Uzytkownik wprowadza swoje preferencje podrozy i na tej podstawie dostaje powiadomienia o nowych ofertach, które są dopasowane pod preferencje.

Deweloper dostaje zarobek z aplikacji za pośrednictwem reflinków z travellead.pl

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