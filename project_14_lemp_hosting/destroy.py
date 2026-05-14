"""Cleanup — Project 14: LEMP Hosting"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def destroy():
    state = load_state(STATE_FILE)
    ec2   = boto3_client("ec2")
    rds   = boto3_client("rds")

    print("\n  Destroying Project 14 resources...")

    try:
        ec2.terminate_instances(InstanceIds=[state["instance_id"]])
        ec2.get_waiter("instance_terminated").wait(InstanceIds=[state["instance_id"]])
        ok("EC2 terminated")
    except Exception as e:
        warn(str(e))

    try:
        rds.delete_db_instance(DBInstanceIdentifier=state["rds_id"],
                               SkipFinalSnapshot=True, DeleteAutomatedBackups=True)
        rds.get_waiter("db_instance_deleted").wait(DBInstanceIdentifier=state["rds_id"])
        rds.delete_db_subnet_group(DBSubnetGroupName=state["subnet_group"])
        ok("RDS deleted")
    except Exception as e:
        warn(str(e))

    time.sleep(15)
    delete_security_group(state["db_sg"])
    delete_security_group(state["web_sg"])

    os.remove(STATE_FILE)
    print("\n  Cleanup complete!\n")

if __name__ == "__main__":
    destroy()
