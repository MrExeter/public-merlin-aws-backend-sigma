from aws_cdk import (
    Stack,
    aws_chatbot as chatbot,
    aws_iam as iam,
    aws_sns as sns,
)
from constructs import Construct

class ChatbotAlertStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #  Context
        slack_workspace_id = self.node.try_get_context("slackWorkspaceId")
        slack_channel_ids = self.node.try_get_context("slackChannelIds") or {}

        billing_topic_arn = self.node.try_get_context("billingAlertsTopicArn")
        quota_topic_arn = self.node.try_get_context("quotaAlertsTopicArn")
        usage_topic_arn = self.node.try_get_context("usageAlertsTopicArn")

        app_errors_topic_arn = self.node.try_get_context("appErrorsTopicArn")
        security_alerts_topic_arn = self.node.try_get_context("securityAlertsTopicArn")
        devops_topic_arn = self.node.try_get_context("devopsTopicArn")

        # deployment_status_topic_arn = self.node.try_get_context("deploymentStatusTopicArn")
        # devops_topic_arn = self.node.try_get_context("devOpsAlertsTopicArn")


        # metering_topic_arn = self.node.try_get_context("meteringAlertsTopicArn")

        if not slack_workspace_id:
            raise ValueError("Missing Slack workspace ID in context.")
        if not slack_channel_ids:
            raise ValueError("Missing Slack channel IDs in context.")

        # Role for Chatbot
        chatbot_role = iam.Role(
            self, "ChatbotSlackRole",
            assumed_by=iam.ServicePrincipal("chatbot.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("ReadOnlyAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchReadOnlyAccess"),
            ],
        )

        # Define channel → topic mapping
        slack_channel_configs = {
            "billing-alerts": {
                "topic_arn": billing_topic_arn,
                "config_name": "BillingAlertsSlackChannel"
            },
            "quota-alerts": {
                "topic_arn": quota_topic_arn,
                "config_name": "QuotaAlertsSlackChannel"
            },
            "usage-alerts": {
                "topic_arn": usage_topic_arn,
                "config_name": "UsageAlertsSlackChannel"
            },
            "app-errors": {
                "topic_arn": app_errors_topic_arn,
                "config_name": "AppErrorsAlertsSlackChannel"
            },
            "security-alerts": {
                "topic_arn": security_alerts_topic_arn,
                "config_name": "SecurityAlertsSlackChannel"
            },
            "devops": {
                "topic_arn": devops_topic_arn,
                "config_name": "DevOpsAlertsSlackChannel"
            },

        }

        for channel_key, config in slack_channel_configs.items():
            channel_id = slack_channel_ids.get(channel_key)
            topic_arn = config["topic_arn"]
            config_name = config["config_name"]

            if not channel_id:
                raise ValueError(f"Missing Slack channel ID for '{channel_key}' in context.")
            if not topic_arn:
                raise ValueError(f"Missing Topic ARN for '{channel_key}' in context.")

            topic = sns.Topic.from_topic_arn(self, f"{config_name}Topic", topic_arn)

            chatbot.SlackChannelConfiguration(
                self, config_name,
                slack_channel_configuration_name=config_name,
                slack_workspace_id=slack_workspace_id,
                slack_channel_id=channel_id,
                notification_topics=[topic],
                logging_level=chatbot.LoggingLevel.INFO,
                role=chatbot_role,
            )
