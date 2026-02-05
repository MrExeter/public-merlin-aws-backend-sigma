# Usage Stacks

## UsageStack
- DynamoDB `UsageLogs`
  - PK `usage_id` (S)
  - GSI `user_id-index`: PK `user_id`, SK `timestamp`

## UsageLambdaStack
- Lambda `log_usage`
  - Env:
    - `USAGE_TABLE_NAME` (from CDK)
    - `TENANTS_TABLE_NAME` (from CDK; optional but recommended)
  - Permissions:
    - write `UsageLogs`
    - read `Tenants` (for tenant lookup)

## UsageApiStack
- API Gateway REST API
- Routes:
  - `POST /v1/usage/log` → `log_usage` Lambda
- Outputs:
  - `UsageApiId`, `UsageApiRootId`

**Calling the API**
