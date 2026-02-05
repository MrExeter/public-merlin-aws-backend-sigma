# Security

- **AuthN/Z**
  - Cognito authorizer protects API methods
  - Resource Server + scopes for client-credentials
- **Least privilege IAM**
  - Log lambda: write `UsageLogs`, read `Tenants`
  - Aggregator: read `UsageLogs`, write `UsageInvoices`
- **Secrets**
  - OAuth client secrets in Secrets Manager
- **Data isolation**
  - Stamp every row with `tenant_id` (and `app_id`)
  - Optional: per-tenant AWS account as you scale
- **Observability**
  - Enable API GW access logs & metrics
  - CloudWatch alarms on 5XX / throttles
