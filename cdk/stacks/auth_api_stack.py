# cdk/stacks/auth_api_stack.py

from typing import Optional

from aws_cdk import (
    Stack,
    aws_apigateway as apigw,
    CfnOutput,
)
from constructs import Construct


class AuthApiStack(Stack):
    """
    Attaches a Cognito User Pool authorizer to an existing API Gateway REST API.

    Parameters:
    - user_pool_arn: ARN of the Cognito User Pool to use for JWT validation.
    - rest_api_id:   ID of the target RestApi (from UsageApiStack.rest_api_id_output).
    - root_resource_id (optional): the API’s rootResourceId (from UsageApiStack.rest_api_root_id_output)
      If provided, the stack will import the API and attach the authorizer to /usage/log and /usage/aggregate.
      If omitted, only the CfnAuthorizer resource is created (sufficient for unit tests).
    """

    def __init__(
            self,
            scope: Construct,
            construct_id: str,
            *,
            user_pool_arn: str,
            rest_api_id: str,
            root_resource_id: Optional[str] = None,
            env=None,
            **kwargs,
    ):
        super().__init__(scope, construct_id, env=env, **kwargs)

        # 1) Define the low-level Cognito authorizer
        authorizer = apigw.CfnAuthorizer(
            self, "CognitoAuthorizer",
            name="CognitoAuthorizer",
            type="COGNITO_USER_POOLS",
            identity_source="method.request.header.Authorization",
            provider_arns=[user_pool_arn],
            rest_api_id=rest_api_id
        )

        # 2) Optionally import the existing RestApi and attach authorizer to methods
        if root_resource_id:
            api = apigw.RestApi.from_rest_api_attributes(
                self, "ImportedApi",
                rest_api_id=rest_api_id,
                root_resource_id=root_resource_id,
            )

            # Protect POST /usage/log
            # usage = api.root.get_resource("usage")

            v1 = api.root.get_resource("v1")
            usage = v1.get_resource("usage") if v1 else None

            if usage is not None:
                log = usage.get_resource("log")
                if log is not None:
                    apigw.CfnMethod(
                        self, "UsageLogPostWithAuth",
                        rest_api_id=rest_api_id,
                        resource_id=log.resource_id,
                        http_method="POST",
                        authorization_type="COGNITO_USER_POOLS",
                        authorizer_id=authorizer.ref,
                        api_key_required=False,
                        # integration is unchanged; authorizer only adds auth
                    )

            # Protect GET /usage/aggregate
            if usage is not None:
                agg = usage.get_resource("aggregate")
                if agg is not None:
                    apigw.CfnMethod(
                        self, "UsageAggregateGetWithAuth",
                        rest_api_id=rest_api_id,
                        resource_id=agg.resource_id,
                        http_method="GET",
                        authorization_type="COGNITO_USER_POOLS",
                        authorizer_id=authorizer.ref,
                        api_key_required=False,
                    )

        # 3) Optionally export the authorizer ID for reference
        CfnOutput(self, "CognitoAuthorizerId", value=authorizer.ref)
