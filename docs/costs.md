# Cost Notes (high level)

- **Cognito User Pools**
  - MAU pricing (10k free on Essentials)
  - **M2M App Client**: $6/mo per confidential client (prorated)
- **Secrets Manager**: ~$0.40/secret/month
- **API Gateway**: per-request pricing
- **Lambda**: request + duration
- **DynamoDB**: on-demand reads/writes

## Guardrails
- Set **Budgets** per env/tenant
- Use tagging: `Service`, `Environment`, (`Tenant`)
- Cache tokens; avoid chatty write patterns
