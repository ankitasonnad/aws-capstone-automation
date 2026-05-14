"""Cleanup — Project 6: Cost Optimizer"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def destroy():
    state   = load_state(STATE_FILE)
    iam     = boto3_client("iam")
    lmb     = boto3_client("lambda")
    events  = boto3_client("events")
    cw      = boto3_client("cloudwatch")

    print("\n  Destroying Project 6 resources...")

    # Remove targets and delete rule
    try:
        targets = events.list_targets_by_rule(Rule=state["rule_name"])
        ids = [t["Id"] for t in targets["Targets"]]
        if ids:
            events.remove_targets(Rule=state["rule_name"], Ids=ids)
        events.delete_rule(Name=state["rule_name"])
        ok("CloudWatch Events rule deleted")
    except Exception as e:
        warn(str(e))

    # Delete Lambda
    try:
        lmb.delete_function(FunctionName=state["fn_name"])
        ok("Lambda function deleted")
    except Exception as e:
        warn(str(e))

    # Delete CloudWatch alarm
    try:
        cw.delete_alarms(AlarmNames=[state["alarm_name"]])
        ok("CloudWatch alarm deleted")
    except Exception as e:
        warn(str(e))

    # Delete IAM role
    try:
        policies = iam.list_role_policies(RoleName=state["role_name"])
        for p in policies["PolicyNames"]:
            iam.delete_role_policy(RoleName=state["role_name"], PolicyName=p)
        iam.delete_role(RoleName=state["role_name"])
        ok(f"IAM Role {state['role_name']} deleted")
    except Exception as e:
        warn(str(e))

    os.remove(STATE_FILE)
    print("\n  Cleanup complete!\n")

if __name__ == "__main__":
    destroy()
