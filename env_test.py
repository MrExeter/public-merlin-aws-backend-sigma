import os
import sys
# from env import Env  # noqa: E402


if __name__ == "__main__":
    pass

    # Add the parent directory to the system path
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    account = os.getenv("CDK_DEFAULT_ACCOUNT")
    region = os.getenv("CDK_DEFAULT_REGION")


    print(f"Account: {account}, Region: {region}")

