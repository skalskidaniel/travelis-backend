# TraveLis Backend

**TraveLis** is a vacation deal aggregator. It scrapes package holidays (flight + hotel) from [wakacje.pl](https://wakacje.pl) and [tui.pl](https://tui.pl), scores them by attractiveness, and serves a personalized feed to users via a PWA frontend. Revenue comes from [travellead.pl](https://travellead.pl) referral links appended to every offer URL.

## Problem

Finding a good last-minute deal across multiple tour operators is tedious and slow. TraveLis automates the search — users set trip preferences once, and get notified when attractive new offers match their criteria. No manual tab-switching or price comparison needed.

## Technologies

| Layer | Stack |
|-------|-------|
| Runtime | Python 3.12+, FastAPI, Mangum (Lambda adapter) |
| Async | `aioboto3`, `httpx.AsyncClient`, `redis.asyncio` |
| Data | DynamoDB (4 tables, no GSIs), Redis Cloud (feed ZSETs) |
| Auth | AWS Cognito + JWT verification |
| Infra | AWS Lambda (lambdalith), API Gateway HTTP v2, EventBridge, Terraform |
| Scraping | `asyncio` worker pool, per-provider adapters |

## Deployment

Two AWS Lambda functions sharing a single artifact ("lambdalith"):
- **API Lambda** — 30s timeout, serves FastAPI routes via Mangum behind API Gateway
- **Cron Lambda** — 15min timeout, runs scrape jobs (3x daily), availability checks (1x daily), and debounced user matching

Provisioned with Terraform under `infra/environments/dev/`. Cognito PostConfirmation triggers auto-provision new users.

## Architecture

```mermaid
flowchart TB
    subgraph "Client Layer"
        PWA[PWA Frontend]
    end

    subgraph "Entrypoints (src/app/)"
        direction LR
        M["main.py<br/>FastAPI + Mangum + Lambda Handler"]
        AUTH["auth/<br/>JWT Deps,<br/>Account Delete"]
        USER["user/<br/>Preferences,<br/>Push Settings"]
        OFFERS["offers/<br/>Feed, Favorites,<br/>Detail"]
        JOBS["jobs/<br/>Coordinator,<br/>Availability"]
    end

    subgraph "Domain Layer (src/core/)"
        direction TB
        subgraph "Models"
            MO["Offer, RawOffer,<br/>MarketCell, User"]
        end
        subgraph "Providers"
            PR["OfferProvider<br/>wakacje.pl, tui.pl"]
        end
        subgraph "Services"
            SI["Ingest<br/>Normalize, Dedup"]
            SC["Scoring<br/>Stage 1+2"]
            MA["Matching<br/>User→Offer"]
            AC["Activation<br/>Cell Ref-Count"]
            NO["Notifications<br/>Web Push VAPID"]
            SA["Scheduler<br/>EventBridge"]
            CJ["CognitoJWT<br/>Verifier"]
        end
        subgraph "Repositories"
            RE["Users, Cells,<br/>Offers, UserOffers<br/>(DynamoDB)"]
            RF["Feed<br/>(Redis)"]
        end
        subgraph "Container"
            CO["container.py<br/>Composition Root"]
        end
    end

    subgraph "Infrastructure"
        DDB[("DynamoDB<br/>4 Tables")]
        REDIS[("Redis Cloud<br/>Feed Cache")]
        COGNITO[AWS Cognito]
        EB[EventBridge<br/>Cron + Scheduler]
        APIGW[API Gateway]
    end

    subgraph "External"
        WAK[wakacje.pl API]
        TUI[tui.pl API]
    end

    PWA --> APIGW
    APIGW --> M
    EB --> M
    M --> AUTH & USER & OFFERS & JOBS
    AUTH --> COGNITO
    AUTH --> CO
    USER --> CO
    OFFERS --> CO
    JOBS --> CO
    CO --> SI & SC & MA & AC & NO & SA & CJ
    CO --> MO
    CO --> PR
    CO --> RE & RF
    PR --> WAK & TUI
    RE --> DDB
    RF --> REDIS
    SA --> EB
    CJ --> COGNITO

    classDef entrypoint fill:#e1f5fe,stroke:#01579b
    classDef domain fill:#f3e5f5,stroke:#7b1fa2
    classDef infra fill:#fff3e0,stroke:#e65100
    classDef external fill:#e8f5e9,stroke:#2e7d32
    class M,AUTH,USER,OFFERS,JOBS entrypoint
    class MO,PR,SI,SC,MA,AC,NO,SA,CJ,RE,RF,CO domain
    class DDB,REDIS,COGNITO,EB,APIGW infra
    class WAK,TUI external
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for execution flows, data flow diagrams, and key architecture decisions.
