from aws_cdk import Stack, RemovalPolicy, aws_dynamodb as ddb, CfnOutput
from constructs import Construct

from aws_cdk import aws_s3 as s3

class TenantsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, env=None, **kwargs):
        super().__init__(scope, construct_id, env=env, **kwargs)

        tenants = ddb.Table(
            self, "Tenants",
            table_name="Tenants",
            partition_key=ddb.Attribute(name="client_id", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
        )

        s3.Bucket.from_bucket_name(self, "BrokenBucket", "this-bucket-does-not-exist-123456789")

        # 🛡️ Prevent deletion during deploy
        tenants.apply_removal_policy(RemovalPolicy.RETAIN)

        # ✅ Enable PITR safely at L1 level (no table replacement)
        cfn_tenants: ddb.CfnTable = tenants.node.default_child
        cfn_tenants.point_in_time_recovery_specification = ddb.CfnTable.PointInTimeRecoverySpecificationProperty(
            point_in_time_recovery_enabled=True
        )

        CfnOutput(
            self, "TenantsTableNameExport",
            value=tenants.table_name,
            # export_name="TenantsStack:TenantsTableNameV2",  # changed
        )

        CfnOutput(
            self, "TenantsTableArnExport",
            value=tenants.table_arn,
            # export_name="TenantsStack:TenantsTableArnV2",  # changed
        )


        self.tenants_table = tenants
