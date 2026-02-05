
from aws_cdk import (
    Stack,
    Duration,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_sns as sns,
    aws_lambda as _lambda,
    aws_sns_subscriptions as sns_subs,
    aws_iam as iam,
)
from constructs import Construct


class SlackAlertsTestStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, stage: str = "dev", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Import existing SNS topics by ARN from context
        billing_topic_arn = self.node.try_get_context("billingAlertsTopicArn")
        quota_topic_arn = self.node.try_get_context("quotaAlertsTopicArn")
        usage_topic_arn = self.node.try_get_context("usageAlertsTopicArn")
        app_errors_topic_arn = self.node.try_get_context("appErrorsTopicArn")
        security_alerts_topic_arn = self.node.try_get_context("securityAlertsTopicArn")
        devops_topic_arn = self.node.try_get_context("devopsTopicArn")

        billing_topic = sns.Topic.from_topic_arn(self, "BillingTopic", billing_topic_arn)
        quota_topic = sns.Topic.from_topic_arn(self, "QuotaTopic", quota_topic_arn)
        usage_topic = sns.Topic.from_topic_arn(self, "UsageTopic", usage_topic_arn)
        app_errors_topic = sns.Topic.from_topic_arn(self, "AppErrorsTopic", app_errors_topic_arn)
        security_alerts_topic = sns.Topic.from_topic_arn(self, "SecurityAlertsTopic", security_alerts_topic_arn)
        devops_topic = sns.Topic.from_topic_arn(self, "DevOpsTopic", devops_topic_arn)

        # Create a single test Lambda that always errors
        test_lambda = _lambda.Function(
            self,
            "TestErrorLambda",
            function_name=f"TestErrorLambda-{stage}",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.InlineCode("""
def handler(event, context):
    raise Exception("Forced test error for Slack alerts")
"""),
        )

        # Helper to create one alarm per topic
        def create_test_alarm(name: str, topic: sns.ITopic):
            alarm = cloudwatch.Alarm(
                self,
                f"TestErrorLambdaAlarm{name}",
                metric=test_lambda.metric_errors(period=Duration.minutes(1)),
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            alarm.add_alarm_action(cloudwatch_actions.SnsAction(topic))
            return alarm

        # Create alarms per channel/topic
        create_test_alarm("Billing", billing_topic)
        create_test_alarm("Quota", quota_topic)
        create_test_alarm("Usage", usage_topic)
        create_test_alarm("AppErrors", app_errors_topic)
        create_test_alarm("Security", security_alerts_topic)
        create_test_alarm("DevOps", devops_topic)

        # Formatter Lambda for tenant-facing alerts (skeleton)
        # Formatter Lambda for tenant-facing alerts (sanitized)
        formatter_lambda = _lambda.Function(
            self,
            "FormatterLambda",
            function_name=f"FormatterLambda-{stage}",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=_lambda.InlineCode("""
import os
import json
import boto3
import urllib3

http = urllib3.PoolManager()
secrets_client = boto3.client("secretsmanager")

SECRET_NAME = os.environ.get("SLACK_WEBHOOK_SECRET", "SlackWebhookAnnouncements")

def get_slack_webhook():
    response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
    secret = json.loads(response["SecretString"])
    return secret["url"]

def sanitize_message(alarm_event):
    alarm_name = alarm_event.get("AlarmName", "Unknown Alarm")
    new_state = alarm_event.get("NewStateValue", "UNKNOWN")
    reason = alarm_event.get("NewStateReason", "No reason provided")
    return f":rotating_light: Tenant Alert\\nAlarm: *{alarm_name}*\\nStatus: *{new_state}*\\nDetails: {reason}"

def post_to_slack(message, webhook_url):
    payload = {"text": message}
    encoded = json.dumps(payload).encode("utf-8")
    http.request("POST", webhook_url, body=encoded, headers={"Content-Type": "application/json"})

def handler(event, context):
    print("Received event:", json.dumps(event))
    webhook_url = get_slack_webhook()

    for record in event.get("Records", []):
        try:
            sns_message = json.loads(record["Sns"]["Message"])
            clean_message = sanitize_message(sns_message)
            post_to_slack(clean_message, webhook_url)
        except Exception as e:
            print(f"Error processing record: {e}")
"""),
    environment={
        "SLACK_WEBHOOK_SECRET": "SlackWebhookAnnouncements"
    }
)

        formatter_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:SlackWebhookAnnouncements*"
                ],
            )
        )

        # Tenant test SNS topic
        tenant_test_topic = sns.Topic(
            self,
            "TenantTestAlertsTopic",
            display_name="Tenant Test Alerts"
        )

        # Subscribe FormatterLambda to the tenant test topic
        tenant_test_topic.add_subscription(
            sns_subs.LambdaSubscription(formatter_lambda)
        )
