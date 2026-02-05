# Metering Stack

## MeteringStack
- DynamoDB `UsageInvoices`
- Lambda `MonthlyUsageAggregator`
  - Reads `UsageLogs`, groups by `tenant_id`, writes draft invoices
- EventBridge Rule (monthly) — **OFF by default**
  - Enable via context: `enable_metering_aggregation=true`

### Outputs
- `MonthlyUsageAggregatorName`
- `UsageInvoicesTableName`

### Manual run
```bash
aws lambda invoke --function-name <MonthlyUsageAggregatorName> out.json && cat out.json
