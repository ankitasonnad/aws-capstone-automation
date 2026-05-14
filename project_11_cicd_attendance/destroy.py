"""Cleanup — Project 11: CI/CD Attendance App"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def destroy():
    state = load_state(STATE_FILE)
    s3  = boto3_client("s3")
    iam = boto3_client("iam")
    ec2 = boto3_client("ec2")
    cb  = boto3_client("codebuild")
    cp  = boto3_client("codepipeline")

    print("\n  Destroying Project 11 resources...")

    # Pipeline
    try:
        cp.delete_pipeline(name=state["pipeline_name"])
        ok("Pipeline deleted")
    except Exception as e:
        warn(str(e))

    # CodeBuild
    try:
        cb.delete_project(name=state["cb_name"])
        ok("CodeBuild project deleted")
    except Exception as e:
        warn(str(e))

    # EC2
    try:
        ec2.terminate_instances(InstanceIds=[state["instance_id"]])
        ok("EC2 terminating...")
        w = ec2.get_waiter("instance_terminated")
        w.wait(InstanceIds=[state["instance_id"]])
        ok("EC2 terminated")
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
    for role_key in ["cb_role", "cp_role"]:
        rname = state.get(role_key)
        if not rname:
            continue
        try:
            attached = iam.list_attached_role_policies(RoleName=rname)
            for p in attached["AttachedPolicies"]:
                iam.detach_role_policy(RoleName=rname, PolicyArn=p["PolicyArn"])
            iam.delete_role(RoleName=rname)
            ok(f"Role {rname} deleted")
        except Exception as e:
            warn(str(e))

    time.sleep(10)
    delete_security_group(state["sg_id"])

    os.remove(STATE_FILE)
    print("\n  Cleanup complete!\n")

if __name__ == "__main__":
    destroy()
