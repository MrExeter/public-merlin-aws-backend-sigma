from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    CfnOutput,
)
from constructs import Construct


class PlansStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB table for plans
        plans_table = dynamodb.Table(
            self, "PlansTable",
            partition_key=dynamodb.Attribute(
                name="plan_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # Lambda for creating new plans
        create_plan_lambda = _lambda.Function(
            self, "CreatePlanLambda",
            code=_lambda.Code.from_asset("../services/plans/lambdas"),
            handler="create_plan.handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            environment={
                "PLANS_TABLE_NAME": plans_table.table_name
            }
        )
        plans_table.grant_write_data(create_plan_lambda)

        # Outputs for integration
        CfnOutput(self, "PlansTableName", value=plans_table.table_name)
        CfnOutput(self, "CreatePlanLambdaName", value=create_plan_lambda.function_name)
