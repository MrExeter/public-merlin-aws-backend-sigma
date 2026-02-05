# cdk/stacks/usage_api_stack.py
from aws_cdk import (
    Stack, CfnOutput,
    aws_apigateway as apigw,
    aws_cognito as cognito,
)
from constructs import Construct

class UsageApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        user_pool: cognito.IUserPool,   # pass the object
        log_usage_lambda,
        aggregate_lambda,
        env=None,
        **kwargs,
    ):
        super().__init__(scope, construct_id, env=env, **kwargs)

        api = apigw.RestApi(
            self, "UsageApi",
            rest_api_name="UsageApi",
            description="Public API for logging and aggregating usage",
        )

        authorizer = apigw.CognitoUserPoolsAuthorizer(
            self, "UsageApiAuthorizer",
            cognito_user_pools=[user_pool],
        )

        v1 = api.root.add_resource("v1")
        usage = v1.add_resource("usage")

        # POST /v1/usage/log  (protected)
        usage.add_resource("log").add_method(
            "POST",
            apigw.LambdaIntegration(log_usage_lambda),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        # GET /v1/usage/aggregate  (protected)
        usage.add_resource("aggregate").add_method(
            "GET",
            apigw.LambdaIntegration(aggregate_lambda),
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )

        self.rest_api_id_output = CfnOutput(self, "UsageApiId", value=api.rest_api_id)
        self.rest_api_root_id_output = CfnOutput(self, "UsageApiRootId", value=api.rest_api_root_resource_id)
