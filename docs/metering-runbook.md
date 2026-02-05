# Metering Runbook

## Enable monthly aggregation (OFF by default)
```bash
cdk deploy MeteringStack -c enable_metering_aggregation=true


Disable

Set to false and redeploy.
Manual invoke (one-off)


aws lambda invoke --function-name <MonthlyUsageAggregatorName> out.json && cat out.json
