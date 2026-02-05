# services/usage/iac/usage_stack.py
from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_dynamodb as ddb,
    CfnOutput,
    aws_sns as sns
)
from constructs import Construct


class UsageStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str = "dev",             # accept stage here
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.stage = stage              # stash for later use

        # stage-aware removal policy (optional)
        removal = RemovalPolicy.DESTROY if stage != "prod" else RemovalPolicy.RETAIN

        # Create the table exactly once in this owning stack
        self.usage_table = ddb.Table(
            self, "UsageLogs",
            table_name="UsageLogs",
            partition_key=ddb.Attribute(name="usage_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True),
            removal_policy=removal,
        )

        # (Optional) GSIs you previously had
        self.usage_table.add_global_secondary_index(
            index_name="user_id-index",
            partition_key=ddb.Attribute(name="user_id", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="timestamp", type=ddb.AttributeType.STRING),
        )
        self.usage_table.add_global_secondary_index(
            index_name="tenant_id-ts-index",
            partition_key=ddb.Attribute(name="tenant_id", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="timestamp", type=ddb.AttributeType.STRING),
        )

        usage_alerts_topic = sns.Topic(
            self, "UsageAlertsTopic",
            topic_name=f"UsageAlerts-{stage}"
        )

        CfnOutput(
            self, "UsageAlertsTopicArn",
            value=usage_alerts_topic.topic_arn,
            export_name=f"UsageAlertsTopicArn-{stage}"
        )

        CfnOutput(self, "UsageLogsTableName", value=self.usage_table.table_name)
