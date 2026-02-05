from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    CfnOutput,
    Duration,
)
from constructs import Construct


class MeteringStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, *, usage_table, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Table for invoices
        invoices = dynamodb.Table(
            self, "UsageInvoices",
            partition_key=dynamodb.Attribute(
                name="invoice_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # Lambda to aggregate usage → invoices
        aggregator = _lambda.Function(
            self, "MonthlyUsageAggregator",
            code=_lambda.Code.from_inline("def handler(event, ctx): return {}"),
            handler="index.handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            timeout=Duration.minutes(5),
        )

        # ✅ Context flag for scheduling
        enable_schedule = self.node.try_get_context("enable_metering_aggregation")
        if str(enable_schedule).lower() == "true":
            events.Rule(
                self, "MonthlyAggregationSchedule",
                schedule=events.Schedule.rate(Duration.days(30)),
                targets=[targets.LambdaFunction(aggregator)],
            )

        # Outputs
        CfnOutput(self, "MonthlyUsageAggregatorName", value=aggregator.function_name)
        CfnOutput(self, "MeteringTableName", value=invoices.table_name)
        CfnOutput(self, "MeteringTableArn", value=invoices.table_arn)
