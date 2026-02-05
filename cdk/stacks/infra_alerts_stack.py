from aws_cdk import (
    Stack,
    aws_sns as sns,
)
from constructs import Construct

class InfraAlertsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # App Errors Topic
        self.app_errors_topic = sns.Topic(
            self,
            "AppErrorsTopic",
            display_name="App Errors Alerts"
        )

        # Security Alerts Topic
        self.security_alerts_topic = sns.Topic(
            self,
            "SecurityAlertsTopic",
            display_name="Security Alerts"
        )

        # DevOps Topic
        self.devops_topic = sns.Topic(
            self,
            "DevOpsTopic",
            display_name="DevOps Alerts"
        )
