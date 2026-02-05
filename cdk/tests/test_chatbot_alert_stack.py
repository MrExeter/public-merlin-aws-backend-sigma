# cdk/tests/test_chatbot_alert_stack.py

import aws_cdk as core
import aws_cdk.assertions as assertions

from cdk.stacks.chatbot_alert_stack import ChatbotAlertStack

def test_chatbot_stack_contains_slack_channel_config():
    # Dummy values for testing only — not real AWS or Slack identifiers

    app = core.App()
    app.node.set_context("slackWorkspaceId", "T12345678")
    app.node.set_context("slackChannelIds", {
        "billing-alerts": "C0000001",
        "quota-alerts": "C0000002",
        "usage-alerts": "C0000003",
        "app-errors": "C0000004",
        "security-alerts": "C0000005",
        "devops": "C0000006"
    })
    # Dummy values for testing only — not real AWS or Slack identifiers
    app.node.set_context("billingAlertsTopicArn", "arn:aws:sns:us-west-1:123456789012:BillingAlertsTopic")
    app.node.set_context("quotaAlertsTopicArn", "arn:aws:sns:us-west-1:123456789012:QuotaAlertsTopic")
    app.node.set_context("usageAlertsTopicArn", "arn:aws:sns:us-west-1:123456789012:UsageAlertsTopic")
    app.node.set_context("appErrorsTopicArn", "arn:aws:sns:us-west-1:123456789012:AppErrorsTopic")
    app.node.set_context("securityAlertsTopicArn", "arn:aws:sns:us-west-1:123456789012:SecurityAlertsTopic")
    app.node.set_context("devopsTopicArn", "arn:aws:sns:us-west-1:123456789012:DevOpsTopic")

    stack = ChatbotAlertStack(app, "TestChatbotStack")
    template = assertions.Template.from_stack(stack)

    # Verify that 6 Slack channel configurations are created
    template.resource_count_is("AWS::Chatbot::SlackChannelConfiguration", 6)
