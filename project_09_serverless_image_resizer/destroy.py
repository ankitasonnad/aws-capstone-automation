"""Cleanup — Project 9: Serverless Image Resizer"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def empty_bucket(s3, bucket):
    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                s3.delete_object(Bucket=bucket, Key=obj["Key"])
        s3.delete_bucket(Bucket=bucket)
        ok(f"Bucket {bucket} deleted")
    except Exception as e:
        warn(str(e))

def destroy():
    state = load_state(STATE_FILE)
    s3    = boto3_client("s3")
    lmb   = boto3_client("lambda")
    iam   = boto3_client("iam")

    print("\n  Destroying Project 9 resources...")

    try:
        lmb.delete_function(FunctionName=state["fn_name"])
        ok("Lambda deleted")
    except Exception as e:
        warn(str(e))

    empty_bucket(s3, state["src_bucket"])
    empty_bucket(s3, state["dst_bucket"])

    try:
        policies = iam.list_role_policies(RoleName=state["role_name"])
        for p in policies["PolicyNames"]:
            iam.delete_role_policy(RoleName=state["role_name"], PolicyName=p)
        iam.delete_role(RoleName=state["role_name"])
        ok("IAM Role deleted")
    except Exception as e:
        warn(str(e))

    os.remove(STATE_FILE)
    print("\n  Cleanup complete!\n")

if __name__ == "__main__":
    destroy()
