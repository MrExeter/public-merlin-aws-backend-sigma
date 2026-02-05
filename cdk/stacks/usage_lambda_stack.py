# services/usage/iac/usage_lambda_stack.py
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_lambda as _lambda,
    aws_dynamodb as ddb,
    aws_logs as logs,
    aws_cloudwatch as cw,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_cloudwatch_actions as cw_actions,
)
from constructs import Construct


class UsageLambdaStack(Stack):
    """
    Hosts the Usage lambdas (LogUsage + Aggregator) and related alarms/alerts.
    Consumes the UsageLogs table via constructor (does NOT create it).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        usage_logs_table: ddb.ITable,  # <<< consume the table from the owner stack
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        from pathlib import Path
        services_dir = str(Path(__file__).resolve().parents[2] / "services")

        log_table = usage_logs_table  # alias for readability

        # CloudWatch Log Group for LogUsage (preferred over deprecated log_retention)
        usage_lg = logs.LogGroup(
            self, "UsageLogGroup",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,  # consider RETAIN in prod
        )

        # LogUsage Lambda
        self.log_usage_lambda = _lambda.Function(
            self, "LogUsageFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="usage.lambdas.log_usage.handler.handler",  # ✅
            code=_lambda.Code.from_asset(services_dir),  # ✅
            log_group=usage_lg,
            environment={"USAGE_TABLE_NAME": log_table.table_name},
        )

        log_table.grant_read_write_data(self.log_usage_lambda)

        # Monthly aggregator Lambda (reads the same table)
        agg_lg = logs.LogGroup(
            self, "UsageAggregatorLogGroup",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.aggregate_lambda = _lambda.Function(
            self, "MonthlyUsageAggregator",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="usage.lambdas.aggregate.handler.handler",  # ✅
            code=_lambda.Code.from_asset(services_dir),  # ✅
            log_group=agg_lg,
        )
        log_table.grant_read_data(self.aggregate_lambda)

        # Alarm on LogUsage Lambda errors (>0 in 1 minute)
        usage_err_alarm = cw.Alarm(
            self, "UsageLambdaErrors",
            metric=self.log_usage_lambda.metric_errors(
                period=Duration.minutes(1),
                statistic="sum",
            ),
            threshold=1,
            evaluation_periods=1,
            datapoints_to_alarm=1,
        )

        # (Optional) Alarm on Aggregator errors as well
        agg_err_alarm = cw.Alarm(
            self, "UsageAggregatorErrors",
            metric=self.aggregate_lambda.metric_errors(
                period=Duration.minutes(1),
                statistic="sum",
            ),
            threshold=1,
            evaluation_periods=1,
            datapoints_to_alarm=1,
        )

        # SNS topic + optional email subscription for alerts
        alert_email = self.node.try_get_context("alertEmail")  # cdk -c alertEmail=you@domain
        usage_topic = sns.Topic(self, "UsageAlertsTopic", display_name="Usage Lambda Alerts")
        if alert_email:
            usage_topic.add_subscription(subs.EmailSubscription(alert_email))

        # Send ALARM and OK notifications
        usage_err_alarm.add_alarm_action(cw_actions.SnsAction(usage_topic))
        usage_err_alarm.add_ok_action(cw_actions.SnsAction(usage_topic))
        agg_err_alarm.add_alarm_action(cw_actions.SnsAction(usage_topic))
        agg_err_alarm.add_ok_action(cw_actions.SnsAction(usage_topic))

        # Outputs
        CfnOutput(self, "LogUsageFunctionName", value=self.log_usage_lambda.function_name)
        CfnOutput(self, "UsageAlertsTopicArn", value=usage_topic.topic_arn)
