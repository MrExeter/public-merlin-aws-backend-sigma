from aws_cdk import Stack
from constructs import Construct

class DebugContextStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        slack_workspace_id = self.node.try_get_context("slackWorkspaceId")
        slack_channel_ids = self.node.try_get_context("slackChannelIds")
        billing_alerts_topic_arn = self.node.try_get_context("billingAlertsTopicArn")

        print("\n=== DEBUG CONTEXT ===")
        print(f"slackWorkspaceId: {slack_workspace_id}")
        print(f"slackChannelIds: {slack_channel_ids}")
        print(f"billingAlertsTopicArn: {billing_alerts_topic_arn}")
        print("=====================\n")
