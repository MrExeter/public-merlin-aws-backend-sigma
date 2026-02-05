import json
import os

import boto3


def handler(event, context):
    """
    GET /admin/users

    Lists Cognito users and their groups.
    """
    user_pool_id = os.getenv("COGNITO_USER_POOL_ID")
    if not user_pool_id:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "COGNITO_USER_POOL_ID not set"}),
        }

    try:
        cognito = boto3.client("cognito-idp")

        resp = cognito.list_users(UserPoolId=user_pool_id, Limit=60)
        users = resp.get("Users", [])

        result = []
        for u in users:
            username = u.get("Username")
            attrs = u.get("Attributes", [])

            email = None
            for attr in attrs:
                if attr.get("Name") == "email":
                    email = attr.get("Value")
                    break

            groups_resp = cognito.list_groups_for_user(
                Username=username,
                UserPoolId=user_pool_id,
            )
            groups = [g["GroupName"] for g in groups_resp.get("Groups", [])]

            result.append(
                {
                    "username": username,
                    "email": email,
                    "groups": groups,
                }
            )

        body = {
            "users": result,
            "count": len(result),
        }

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
