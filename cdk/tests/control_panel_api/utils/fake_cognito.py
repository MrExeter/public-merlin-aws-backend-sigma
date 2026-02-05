# cdk/tests/control_panel_api/utils/fake_cognito.py

class FakeCognitoClient:
    """
    Minimal fake Cognito Identity Provider client for unit tests.
    Simulates:
    - list_users
    - list_groups_for_user
    - admin_create_user
    - admin_add_user_to_group
    """

    def __init__(self, users=None, user_groups=None):
        # users: {username: { "Username": ..., "Attributes": [...] }}
        self.users = users or {}
        # user_groups: {username: ["Admins", "Developers", ...]}
        self.user_groups = user_groups or {}

    # ---- listing users ----
    def list_users(self, UserPoolId, Limit=60):
        return {"Users": list(self.users.values())}

    # ---- list groups for a user ----
    def list_groups_for_user(self, Username, UserPoolId):
        groups = self.user_groups.get(Username, [])
        return {"Groups": [{"GroupName": g} for g in groups]}

    # ---- admin create user ----
    def admin_create_user(self, UserPoolId, Username, UserAttributes=None, MessageAction=None):
        if Username in self.users:
            # Overwrite for simplicity
            pass

        attrs = UserAttributes or []
        self.users[Username] = {
            "Username": Username,
            "Attributes": attrs,
        }
        return {"User": self.users[Username]}

    # ---- add user to group ----
    def admin_add_user_to_group(self, UserPoolId, Username, GroupName):
        if Username not in self.users:
            raise KeyError("User not found")

        self.user_groups.setdefault(Username, [])
        if GroupName not in self.user_groups[Username]:
            self.user_groups[Username].append(GroupName)
        return {}


class FakeBoto3:
    """
    Very small stand-in for boto3 that only supports client("cognito-idp").
    """

    def __init__(self, client):
        self._client = client

    def client(self, name):
        assert name == "cognito-idp"
        return self._client
