from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_logs as logs,
    aws_dynamodb as ddb,
    RemovalPolicy,
    aws_secretsmanager as secrets
)
from constructs import Construct
from aws_cdk import CfnOutput  # ✅ Add this to your imports at the top
import os

from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs
from aws_cdk import aws_cloudwatch_actions as cw_actions

from aws_cdk import Duration, aws_cloudwatch as cw

from pathlib import Path
billing_root = Path(__file__).resolve().parents[2] / "services" / "billing"
billing_lambdas_dir = str(billing_root / "lambdas")
billing_dir = str(billing_root)

class BillingLambdaStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        stage = kwargs.pop("stage", "dev")  # ✅ Extract first
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB Table (Assume already exists elsewhere)
        subscriptions_table = ddb.Table.from_table_name(
            self, "SubscriptionsTable", table_name=f"Subscriptions-{stage}"
        )

        # Stripe SDK layer
        stripe_layer = _lambda.LayerVersion(
            self, "StripeSdkLayer",
            # this folder must CONTAIN a "python/" subfolder
            code=_lambda.Code.from_asset(billing_lambdas_dir),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Stripe SDK layer for billing Lambda",
        )

        # Webhook Lambda  explicit LogGroup (replaces deprecated log_retention)
        webhook_lg = logs.LogGroup(
            self, "StripeWebhookLogGroup",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,  # keep DESTROY for dev; RETAIN in prod later if you prefer
        )
        billing_lambda = _lambda.Function(
            self,
            "StripeWebhookHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="stripe_webhook_lambda.handler",
            code=_lambda.Code.from_asset(billing_dir),
            timeout=Duration.seconds(10),
            environment={
                "SUBSCRIPTIONS_TABLE": subscriptions_table.table_name,
            },
            layers=[stripe_layer],
            log_group=webhook_lg,
        )

        # Secrets Manager refs (must exist in the account)
        stripe_key = secrets.Secret.from_secret_name_v2(self, "StripeApiKey", "stripe/secret_key")
        stripe_hook = secrets.Secret.from_secret_name_v2(self, "StripeWebhookSecret", "stripe/webhook_secret")

        # Pass ARNs to the Lambda; CI/local can still use plain envs
        billing_lambda.add_environment("STRIPE_SECRET_ARN", stripe_key.secret_arn)
        billing_lambda.add_environment("STRIPE_WEBHOOK_SECRET_ARN", stripe_hook.secret_arn)

        # Allow Lambda to read the secrets at runtime
        stripe_key.grant_read(billing_lambda)
        stripe_hook.grant_read(billing_lambda)

        err_alarm = cw.Alarm(
            self, "BillingWebhookErrors",
            metric=billing_lambda.metric_errors(period=Duration.minutes(1), statistic="sum"),
            threshold=1,
            evaluation_periods=1,
            datapoints_to_alarm=1,
        )

        #########################################################
        #
        # SNS topic for webhook alerts
        alert_email = self.node.try_get_context("alertEmail")  # set via: cdk deploy -c alertEmail=you@domain.com
        alerts_topic = sns.Topic(self, "BillingAlertsTopic", display_name="Billing Webhook Alerts")

        # Optional: email subscription (must confirm the email from AWS)
        if alert_email:
            alerts_topic.add_subscription(subs.EmailSubscription(alert_email))

        # Hook the alarm to SNS (and optionally recovery notifications)
        err_alarm.add_alarm_action(cw_actions.SnsAction(alerts_topic))
        # Optional: notify when it recovers too
        # err_alarm.add_ok_action(cw_actions.SnsAction(alerts_topic))

        app_err_metric = cw.Metric(
            namespace="MerlinSigma",
            metric_name="WebhookError",
            dimensions_map={"service": "billing-webhook"},
            period=Duration.minutes(1),
            statistic="sum",
        )

        #########################################################
        app_alarm = cw.Alarm(
            self, "BillingWebhookAppErrors",
            metric=app_err_metric,
            threshold=1,
            evaluation_periods=1,
            datapoints_to_alarm=1,
        )
        app_alarm.add_alarm_action(cw_actions.SnsAction(alerts_topic))


        # --- StripeEvents idempotency table ---
        events_table = ddb.Table(
            self, "StripeEvents",
            partition_key=ddb.Attribute(name="event_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # DEV; use RETAIN in prod
        )

        # Lambda env + permissions
        billing_lambda.add_environment("STRIPE_EVENTS_TABLE", events_table.table_name)
        events_table.grant_read_write_data(billing_lambda)


        # Grant write access to DynamoDB
        subscriptions_table.grant_write_data(billing_lambda)

        # ✅ Subscribe Lambda (creates customer + subscription)
        subscribe_lambda = _lambda.Function(
            self,
            "SubscribeLambda",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="subscribe_lambda.handler",
            code=_lambda.Code.from_asset(billing_lambdas_dir),
            # Stripe secrets injected via Secrets Manager in production
            environment={
                "SUBSCRIPTIONS_TABLE": subscriptions_table.table_name,
            },

        layers=[stripe_layer],
        )
        subscriptions_table.grant_write_data(subscribe_lambda)


        # API Gateway
        api = apigw.RestApi(
            self,
            "BillingApi",
            rest_api_name=f"Billing API ({stage})",
            deploy_options=apigw.StageOptions(stage_name=stage),
        )

        v1 = api.root.add_resource("v1")
        billing = v1.add_resource("billing")
        webhook = billing.add_resource("webhook")

        webhook_integration = apigw.LambdaIntegration(billing_lambda)
        webhook.add_method(
            "POST",
            webhook_integration,
            authorization_type=apigw.AuthorizationType.NONE,  # ✅ Allow unauthenticated POST
            api_key_required=False  # ✅ No API key required
        )

        # /v1/billing/subscribe
        subscribe = billing.add_resource("subscribe")
        subscribe_integration = apigw.LambdaIntegration(subscribe_lambda)

        subscribe.add_method(
            "POST",
            subscribe_integration,
            authorization_type=apigw.AuthorizationType.NONE,  # Public for now — lock later if needed
            api_key_required=False
        )

        # ✅ Output the full API URL after all resources are set up
        CfnOutput(self, "BillingApiUrl", value=api.url)
