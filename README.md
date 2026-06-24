# TraveLis Backend

**TraveLis** is a PWA backend that finds bargain package holidays (flight + hotel) from [wakacje.pl](https://wakacje.pl) and [tui.pl](https://tui.pl). Users set trip preferences and get notified when new matching deals appear.

## Architecture

```mermaid
flowchart TB
    subgraph client [Client]
        PWA[PWA Frontend]
    end

    subgraph aws [AWS]
        APIGW[API Gateway HTTP v2]
        EB_Cron[EventBridge Cron]
        EB_Sched[EventBridge Scheduler]
        Cognito[AWS Cognito]
        S3[(S3 Geo Catalog)]
        CW[CloudWatch / Grafana]

        subgraph lambda [Lambda Lambdalith x2]
            API_Lambda[API Lambda\n30s timeout]
            Cron_Lambda[Cron Lambda\n15min timeout]
        end
    end

    subgraph app [app/ entrypoints]
        API_Layer[FastAPI via Mangum]
        Jobs_Layer[Jobs]
    end

    subgraph core [core/ domain]
        Ingest[Normalize + Dedup]
        Scoring[Statistical Scoring]
        Matching[Matching Service]
        Activation[Activation Service]
        Notify[Web Push Notifications]
        SchedulerSvc[Scheduler Service]
    end

    subgraph data [Data]
        DDB_Users[(DynamoDB: Users)]
        DDB_Cells[(DynamoDB: MarketCells)]
        DDB_Offers[(DynamoDB: Offers)]
        DDB_UO[(DynamoDB: UserOffers)]
        Redis[(Redis Cloud\nFeed ZSETs + Rate Limiting)]
    end

    subgraph providers [Providers]
        WAK[wakacje.pl API]
        TUI[tui.pl API]
    end

    PWA -->|Sign in / Sign up| Cognito
    PWA -->|JWT| APIGW
    APIGW --> API_Lambda
    API_Lambda --> API_Layer

    Cognito -->|PostConfirmation trigger| API_Lambda

    EB_Cron -->|cron 3x daily| Cron_Lambda
    EB_Cron -->|cron 1x daily| Cron_Lambda
    EB_Sched -->|at(now+15s) debounced| Cron_Lambda

    API_Layer -->|auth| Cognito
    API_Layer -->|user prefs| DDB_Users
    API_Layer -->|cell activation| DDB_Cells
    API_Layer -->|paginated feed| DDB_UO
    API_Layer --> DDB_Offers
    API_Layer --> Redis
    API_Layer -->|rate limit| Redis

    Cron_Lambda --> Jobs_Layer

    Jobs_Layer -->|coordinator| Ingest
    Jobs_Layer -->|coordinator| Scoring
    Jobs_Layer -->|coordinator| Matching
    Jobs_Layer -->|availability| DDB_Offers
    Jobs_Layer -->|match_user| Matching

    Ingest --> DDB_Offers
    Scoring --> DDB_Offers
    Matching --> DDB_UO
    Matching --> Redis
    Activation --> DDB_Cells

    Cron_Lambda -.->|self-continuation\non timeout| Cron_Lambda

    Cron_Lambda -->|scrape| WAK
    Cron_Lambda -->|scrape| TUI
    Cron_Lambda -->|geo catalogs| S3

    Matching --> Notify
    Notify -->|Web Push| PWA

    API_Lambda --> CW
    Cron_Lambda --> CW
```