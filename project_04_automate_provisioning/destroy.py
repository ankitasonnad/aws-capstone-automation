"""Cleanup — Project 4: Automated Provisioning"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def destroy():
    state = load_state(STATE_FILE)
    ec2   = boto3_client("ec2")
    iam   = boto3_client("iam")
    s3    = boto3_client("s3")

    print("\n  Destroying Project 4 resources...")

    # Terminate EC2
    try:
        ec2.terminate_instances(InstanceIds=[state["instance_id"]])
        ok(f"Terminating {state['instance_id']}")
        w = ec2.get_waiter("instance_terminated")
        w.wait(InstanceIds=[state["instance_id"]])
        ok("Instance terminated")
    except Exception as e:
        warn(str(e))

    # Delete Security Group
    time.sleep(10)
    delete_security_group(state["sg_id"])

    # Empty and delete S3 bucket
    try:
        objects = s3.list_objects_v2(Bucket=state["bucket"])
        for obj in objects.get("Contents", []):
            s3.delete_object(Bucket=state["bucket"], Key=obj["Key"])
        s3.delete_bucket(Bucket=state["bucket"])
        ok(f"S3 bucket {state['bucket']} deleted")
    except Exception as e:
        warn(str(e))

    # Detach policies and delete user
    try:
        attached = iam.list_attached_user_policies(UserName=state["user_name"])
        for p in attached["AttachedPolicies"]:
            iam.detach_user_policy(UserName=state["user_name"], PolicyArn=p["PolicyArn"])
        iam.delete_user(UserName=state["user_name"])
        ok(f"IAM User {state['user_name']} deleted")
    except Exception as e:
        warn(str(e))

    # Remove role from profile and delete profile
    try:
        iam.remove_role_from_instance_profile(
            InstanceProfileName=state["profile_name"], RoleName=state["role_name"])
        iam.delete_instance_profile(InstanceProfileName=state["profile_name"])
        ok("Instance Profile deleted")
    except Exception as e:
        warn(str(e))

    # Detach policies and delete role
    try:
        attached = iam.list_attached_role_policies(RoleName=state["role_name"])
        for p in attached["AttachedPolicies"]:
            iam.detach_role_policy(RoleName=state["role_name"], PolicyArn=p["PolicyArn"])
        iam.delete_role(RoleName=state["role_name"])
        ok(f"IAM Role {state['role_name']} deleted")
    except Exception as e:
        warn(str(e))

    os.remove(STATE_FILE)
    print("\n  Cleanup complete!\n")

if __name__ == "__main__":
    destroy()
