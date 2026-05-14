"""Cleanup — Project 7: CI/CD Pipeline Node.js"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def destroy():
    state = load_state(STATE_FILE)
    s3 = boto3_client("s3")
    iam = boto3_client("iam")
    cb = boto3_client("codebuild")
    cp = boto3_client("codepipeline")

    print("\n  Destroying Project 7 resources...")

    # Delete pipeline
    try:
        cp.delete_pipeline(name=state["pipeline_name"])
        ok("Pipeline deleted")
    except Exception as e:
        warn(str(e))

    # Delete CodeBuild project
    try:
        cb.delete_project(name=state["cb_project_name"])
        ok("CodeBuild project deleted")
    except Exception as e:
        warn(str(e))

    # Empty and delete S3 bucket
    try:
        bucket = state["artifact_bucket"]
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                s3.delete_object(Bucket=bucket, Key=obj["Key"])
        # Handle versioned objects
        paginator2 = s3.get_paginator("list_object_versions")
        try:
            for page in paginator2.paginate(Bucket=bucket):
                for v in page.get("Versions", []) + page.get("DeleteMarkers", []):
                    s3.delete_object(Bucket=bucket, Key=v["Key"], VersionId=v["VersionId"])
        except Exception:
            pass
        s3.delete_bucket(Bucket=bucket)
        ok(f"S3 bucket {bucket} deleted")
    except Exception as e:
        warn(str(e))

    # Delete IAM roles
    for role_key in ["cb_role_name", "cp_role_name"]:
        if role_key not in state:
            continue
        rname = state[role_key]
        try:
            attached = iam.list_attached_role_policies(RoleName=rname)
            for p in attached["AttachedPolicies"]:
                iam.detach_role_policy(RoleName=rname, PolicyArn=p["PolicyArn"])
            iam.delete_role(RoleName=rname)
            ok(f"IAM Role {rname} deleted")
        except Exception as e:
            warn(str(e))

    os.remove(STATE_FILE)
    print("\n  Cleanup complete!\n")

if __name__ == "__main__":
    destroy()
