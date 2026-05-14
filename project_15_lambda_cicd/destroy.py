"""Cleanup — Project 15: Lambda CI/CD"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def destroy():
    state   = load_state(STATE_FILE)
    s3      = boto3_client("s3")
    iam     = boto3_client("iam")
    lmb     = boto3_client("lambda")
    cb      = boto3_client("codebuild")
    cp      = boto3_client("codepipeline")
    events  = boto3_client("events")

    print("\n  Destroying Project 15 resources...")

    # CloudWatch Events
    try:
        targets = events.list_targets_by_rule(Rule=state["rule_name"])
        ids = [t["Id"] for t in targets["Targets"]]
        if ids:
            events.remove_targets(Rule=state["rule_name"], Ids=ids)
        events.delete_rule(Name=state["rule_name"])
        ok("CW Events rule deleted")
    except Exception as e:
        warn(str(e))

    # Lambdas
    for fn in state.get("lambdas", []):
        try:
            lmb.delete_function(FunctionName=fn)
            ok(f"Lambda {fn} deleted")
        except Exception as e:
            warn(str(e))

    # Pipeline
    try:
        cp.delete_pipeline(name=state["pipeline_name"])
        ok("Pipeline deleted")
    except Exception as e:
        warn(str(e))

    # CodeBuild
    try:
        cb.delete_project(name=state["cb_name"])
        ok("CodeBuild deleted")
    except Exception as e:
        warn(str(e))

    # S3
    try:
        bucket = state["bucket"]
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                s3.delete_object(Bucket=bucket, Key=obj["Key"])
        try:
            pag2 = s3.get_paginator("list_object_versions")
            for page in pag2.paginate(Bucket=bucket):
                for v in page.get("Versions", []) + page.get("DeleteMarkers", []):
                    s3.delete_object(Bucket=bucket, Key=v["Key"], VersionId=v["VersionId"])
        except Exception:
            pass
        s3.delete_bucket(Bucket=bucket)
        ok(f"S3 bucket deleted")
    except Exception as e:
        warn(str(e))

    # IAM Roles
    for rname in state.get("lambda_roles", []):
        try:
            attached = iam.list_attached_role_policies(RoleName=rname)
            for p in attached["AttachedPolicies"]:
                iam.detach_role_policy(RoleName=rname, PolicyArn=p["PolicyArn"])
            iam.delete_role(RoleName=rname)
            ok(f"Role {rname} deleted")
        except Exception as e:
            warn(str(e))

    os.remove(STATE_FILE)
    print("\n  All resources cleaned up!\n")

if __name__ == "__main__":
    destroy()
