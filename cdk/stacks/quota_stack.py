from aws_cdk import aws_dynamodb as ddb, Stack, RemovalPolicy
from constructs import Construct
from aws_cdk import ( aws_sns as sns,
                      Duration,
                      CfnOutput,
                      aws_cloudwatch_actions as cw_actions,
                      aws_cloudwatch as cw)

from aws_cdk.aws_dynamodb import Table, CfnTable
from aws_cdk.aws_dynamodb import Operation

class QuotaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, stage: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # stage-aware removal policy (optional)
        removal = RemovalPolicy.DESTROY if stage != "prod" else RemovalPolicy.RETAIN

        self.quota_table = ddb.Table(
            self, "QuotaPlans",
            table_name="QuotaPlans",
            partition_key=ddb.Attribute(name="plan_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True),
            removal_policy=removal,  # 🚨 Use RETAIN in prod
        )

        quota_alerts_topic = sns.Topic(self, "QuotaAlertsTopic", display_name="Quota Alerts")

        # Attach to an alarm (this must exist in your stack)
        # Simple alarm on read throttle events (as a placeholder)
        metric = cw.Metric(
            namespace="AWS/DynamoDB",
            metric_name="ReadThrottleEvents",
            dimensions_map={"TableName": self.quota_table.table_name},
            period=Duration.minutes(1),
            statistic="sum"
        )

        read_throttle_metric = cw.Metric(
            namespace="AWS/DynamoDB",
            metric_name="ReadThrottleEvents",
            dimensions_map={
                "TableName": self.quota_table.table_name  # ITable object
            },
            period=Duration.minutes(1),
            statistic="sum"
        )

        read_throttle_alarm = cw.Alarm(
            self, "QuotaReadThrottleAlarm",
            metric=read_throttle_metric,
            threshold=1,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            alarm_description="Alarm if quota table experiences read throttles"
        )

        read_throttle_alarm.add_alarm_action(cw_actions.SnsAction(quota_alerts_topic))
        read_throttle_alarm.add_ok_action(cw_actions.SnsAction(quota_alerts_topic))

        # Optional: expose it for use in other stacks like ChatbotAlertStack
        CfnOutput(self, "QuotaAlertsTopicArn", value=quota_alerts_topic.topic_arn)
