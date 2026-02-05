#!/usr/bin/env python3
import os
import aws_cdk as cdk
from aws_cdk import CfnOutput


# Usage stacks
from stacks.usage_stack import UsageStack
from stacks.usage_lambda_stack import UsageLambdaStack
from stacks.usage_api_stack import UsageApiStack
from stacks.metering_stack import MeteringStack
from stacks.tenants_stack import TenantsStack
from stacks.billing_lambda_stack import BillingLambdaStack
from stacks.chatbot_alert_stack import ChatbotAlertStack
from stacks.control_panel_api_stack import ControlPanelApiStack

from stacks.plans_stack import PlansStack

from stacks.quota_stack import QuotaStack

# Temp Test stack for Slack alerts
from stacks.slack_alerts_test_stack import SlackAlertsTestStack

from stacks.infra_alerts_stack import InfraAlertsStack

# Auth stacks
from stacks.auth_api_stack import AuthApiStack
from stacks.auth_stack import AuthStack

from stacks.debug_context_stack import DebugContextStack

app = cdk.App()

stage = app.node.try_get_context("stage") or "dev"

# from aws_cdk import Tags

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

def persistent_name(base: str) -> str:
    # persistent data stores: same name in dev (and later in other accounts)
    return base

def env_name(base: str) -> str:
    # per-environment (alarms, SNS topics, ephemeral tables, etc.)
    return base if stage == "prod" else f"{base}-{stage}"


# ──── 1) Usage Infrastructure ────────────────────────────────────────────────

auth_stack = AuthStack(app, f"AuthStack-{stage}", stage=stage, env=env)

usage_stack_id = "UsageStack" if stage == "dev" else f"UsageStack-{stage}"
usage_stack = UsageStack(app, usage_stack_id, stage=stage, env=env)


tenants_stack = TenantsStack(app, "TenantsStack", env=env)

quota_stack = QuotaStack(app, f"QuotaStack-{stage}", stage=stage, env=env)

usage_lambda_stack = UsageLambdaStack(
    app,
   # f"UsageLambdaStack-{stage}",
    f"UsageLambdaStack",
    usage_logs_table=usage_stack.usage_table,  # <<< pass the table here
    env=env,
)

usage_lambda_stack.add_dependency(usage_stack)

metering = MeteringStack(
    app, "MeteringStack",
    usage_table=usage_stack.usage_table,
    env=env
)

usage_api_stack = UsageApiStack(
    app, "UsageApiStack",
    user_pool=auth_stack.user_pool,
    log_usage_lambda=usage_lambda_stack.log_usage_lambda,
    aggregate_lambda=usage_lambda_stack.aggregate_lambda,
    env=env
)


ENABLE_PHASE4_ALERTS = False

if ENABLE_PHASE4_ALERTS:
    InfraAlertsStack(app, f"InfraAlertsStack-{stage}")

    ChatbotAlertStack(
        app,
        f"ChatbotAlertStack-{stage}",
        env=env,
    )

    SlackAlertsTestStack(app, "SlackAlertsTestStack-dev", stage="dev", env=cdk.Environment(
        account="686116998270",
        region="us-west-1"
    ))

for env_name in ["dev"]:  # add "staging", "prod" later
    ControlPanelApiStack(
        app, f"MerlinSigma-CP-Api-{env_name}",
        env=cdk.Environment(account="686116998270", region="us-west-1"),
        env_name=env_name,
    )

    PlansStack(
        app,
        f"PlansStack-{env_name}",
        env=cdk.Environment(
            account="686116998270",
            region="us-west-1"
        )
    )


# ──── 4) Stack Dependencies ──────────────────────────────────────────────────
metering.add_dependency(usage_stack)           # aggregator reads UsageLogs
usage_api_stack.add_dependency(usage_lambda_stack)  # API uses those Lambdas

# ──── 5) CDK Tags for Tracing ────────────────────────────────────────────────

cdk.Tags.of(app).add("Project", "MerlinSigma")
cdk.Tags.of(app).add("Stage", stage)

# Optional: Stack-specific tags if needed
# cdk.Tags.of(auth_stack).add("Service", "Auth")
# cdk.Tags.of(lambda_stack).add("Service", "UsageLambda")
# cdk.Tags.of(usage_stack).add("Service", "Usage")


DebugContextStack(app, f"DebugContextStack-{stage}", env=env)

app.synth()
