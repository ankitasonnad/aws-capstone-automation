"""Cleanup — Project 3: Multi-tier Web App"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def destroy():
    state = load_state(STATE_FILE)
    ec2   = boto3_client("ec2")
    elb   = boto3_client("elbv2")
    asg   = boto3_client("autoscaling")
    rds   = boto3_client("rds")

    print("\n  Destroying Project 3 resources...")

    # ASG
    try:
        asg.delete_auto_scaling_group(
            AutoScalingGroupName=state["asg_name"], ForceDelete=True)
        ok("ASG deleted"); time.sleep(15)
    except Exception as e:
        warn(str(e))

    # Launch Template
    try:
        ec2.delete_launch_template(LaunchTemplateId=state["lt_id"])
        ok("Launch Template deleted")
    except Exception as e:
        warn(str(e))

    # ALB
    try:
        listeners = elb.describe_listeners(LoadBalancerArn=state["alb_arn"])
        for l in listeners["Listeners"]:
            elb.delete_listener(ListenerArn=l["ListenerArn"])
        elb.delete_load_balancer(LoadBalancerArn=state["alb_arn"])
        ok("ALB deleted"); time.sleep(10)
    except Exception as e:
        warn(str(e))

    try:
        elb.delete_target_group(TargetGroupArn=state["tg_arn"])
        ok("Target Group deleted")
    except Exception as e:
        warn(str(e))

    # RDS
    try:
        rds.delete_db_instance(
            DBInstanceIdentifier=state["rds_id"],
            SkipFinalSnapshot=True,
            DeleteAutomatedBackups=True,
        )
        ok("RDS deletion initiated (takes ~5 min)...")
        waiter = rds.get_waiter("db_instance_deleted")
        waiter.wait(DBInstanceIdentifier=state["rds_id"])
        ok("RDS deleted")
    except Exception as e:
        warn(str(e))

    try:
        rds.delete_db_subnet_group(DBSubnetGroupName=state["rds_subnet_group"])
        ok("RDS Subnet Group deleted")
    except Exception as e:
        warn(str(e))

    time.sleep(15)
    for sg_key in ["web_sg_id", "db_sg_id"]:
        if sg_key in state:
            delete_security_group(state[sg_key])

    os.remove(STATE_FILE)
    print("\n  Cleanup complete!\n")

if __name__ == "__main__":
    destroy()
