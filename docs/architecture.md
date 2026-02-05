# Architecture

- **API Gateway (REST)** under `/v1`
- **Lambda** handlers (usage logging)
- **DynamoDB**:
  - `UsageLogs` (usage events)
  - `Tenants` (client_id → tenant mapping)
  - `UsageInvoices` (metering drafts)
- **Cognito**: User Pool with Web & Backend App Clients; Resource Server `myapi-<stage>`; scope `usage.read`
- **Authorizer**: API methods protected by Cognito JWT

```mermaid
flowchart LR
  Client -->|JWT| APIGW[API Gateway (/v1)]
  APIGW --> L1[Lambda: LogUsage]
  L1 --> DDB1[(DynamoDB: UsageLogs)]
  APIGW -->|Cognito Authorizer| COG[User Pool]

  subgraph Tenancy
    L1 --> DDBT[(DynamoDB: Tenants)]
  end

  subgraph Metering
    AGL[Lambda: MonthlyUsageAggregator] --> DDB2[(DynamoDB: UsageInvoices)]
    AGL -. read .-> DDB1
  end
