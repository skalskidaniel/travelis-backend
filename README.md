# TraveLis Backend

**TraveLis** is a PWA backend that finds bargain package holidays (flight + hotel) from [wakacje.pl](https://wakacje.pl) and [tui.pl](https://tui.pl). Users set trip preferences and get notified when new matching deals appear.

## Architecture

```mermaid
flowchart TB
    subgraph client [Client]
        PWA[PWA Frontend]
    end

    subgraph aws [AWS]
        APIGW[API Gateway]
        EB[EventBridge Cron]
        Cognito[Cognito]
        Lambda[Lambda Lambdalith]
    end

    subgraph lambda [app/]
        API[FastAPI via Mangum]
        Jobs[jobs: scrape / score / match]
    end

    subgraph data [Data]
        DDB[(DynamoDB)]
        Redis[(Redis Cloud)]
    end

    subgraph providers [Providers]
        WAK[wakacje.pl API]
        TUI[tui.pl API]
    end

    PWA -->|Sign in / Sign up| Cognito
    PWA -->|JWT| APIGW
    APIGW --> Lambda
    EB -->|scheduled| Lambda
    Lambda --> API
    Lambda --> Jobs

    API -->|auth / user / offers| DDB
    API -->|paginated feed| Redis
    Jobs -->|scrape + store| DDB
    Jobs -->|rebuild feed| Redis
    Jobs --> WAK
    Jobs --> TUI
    Jobs -->|Web Push| PWA
```