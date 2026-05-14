"""Cleanup — Project 12: Bus Booking App"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.aws_config import *

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

def destroy():
    state = load_state(STATE_FILE)
    ec2  = boto3_client("ec2")
    rds  = boto3_client("rds")
    elb  = boto3_client("elbv2")
    asg  = boto3_client("autoscaling")

    print("\n  Destroying Project 12 resources...")

    try:
        asg.delete_auto_scaling_group(
            AutoScalingGroupName=state["asg_name"], ForceDelete=True)
        ok("ASG deleted"); time.sleep(15)
    except Exception as e:
        warn(str(e))

    try:
        ec2.delete_launch_template(LaunchTemplateId=state["lt_id"])
        ok("Launch Template deleted")
    except Exception as e:
        warn(str(e))

    try:
        listeners = elb.describe_listeners(LoadBalancerArn=state["alb_arn"])
        for l in listeners["Listeners"]:
            elb.delete_listener(ListenerArn=l["ListenerArn"])
        elb.delete_load_balancer(LoadBalancerArn=state["alb_arn"])
        ok("ALB deleted"); time.sleep(10)
        elb.delete_target_group(TargetGroupArn=state["tg_arn"])
        ok("TG deleted")
    except Exception as e:
        warn(str(e))

    try:
        rds.delete_db_instance(DBInstanceIdentifier=state["rds_id"],
                               SkipFinalSnapshot=True, DeleteAutomatedBackups=True)
        ok("RDS deleting...")
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
